"""
ProvisoriaService: coordena a avaliação de elegibilidade de Naturalização Provisória
usando o analisador original (carregado dinamicamente) e expõe uma API simples.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import re

from automation.utils.date_utils import normalizar_data_para_ddmmaaaa


class ProvisoriaService:
    """Regras de elegibilidade para Naturalização Provisória (fluxo correto).
    
    Etapas:
    1) Pré-requisitos (gatilhos):
       - Idade do naturalizando na data inicial do processo < 18 anos
       - Residência/ingresso no Brasil antes dos 10 anos
    2) Se (1) atendido, validar SOMENTE 4 documentos (lista configurável)
    3) Considerar parecer PF (banco) como reforço informativo
    """

    # Lista padrão de 4 documentos para Provisória (confirme/ajuste conforme regra interna)
    DOCS_PROVISORIA = [
        'Documento de identificacao do representante legal',
        'Carteira de Registro Nacional Migratorio',
        'Comprovante de tempo de residência',
        'Documento de viagem internacional',
    ]

    def __init__(self) -> None:
        # Se existir analisador modular específico, usar; senão segue regras abaixo
        self._analisador_cls = None
        try:
            from automation.services.analise_elegibilidade_provisoria import AnaliseElegibilidadeProvisoria  # type: ignore
            self._analisador_cls = AnaliseElegibilidadeProvisoria
        except Exception:
            self._analisador_cls = None

    # ------------------------ Utilidades ---------------------------------
    def _parse_data(self, s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            s_norm = normalizar_data_para_ddmmaaaa(s)
            return datetime.strptime(s_norm, '%d/%m/%Y')
        except Exception:
            return None

    def _extrair_data_residencia_inicial(self, dados: Dict[str, Any], repo) -> datetime | None:
        """Tenta inferir a data de residência/ingresso no Brasil.
        Estratégias:
        - Procurar em 'dados' chaves com 'entrada', 'ingresso', 'chegada', 'brasil desde', 'resid' com valor data
        - Se não achar, usar varredura completa do formulário via repo (JS) e vasculhar por datas
        """
        # 1) Procurar diretamente em 'dados'
        candidatos = []
        for k, v in (dados or {}).items():
            k_low = str(k).lower()
            v_str = str(v or '').strip()
            if not v_str:
                continue
            if any(p in k_low for p in ['entrada', 'ingresso', 'chegada', 'brasil', 'resid']):
                d = self._parse_data(v_str)
                if d:
                    candidatos.append(('dados', k, d))
        # 2) Varredura ampliada via repo (JS), caso ainda não tenhamos
        if not candidatos and repo is not None:
            try:
                js = repo._extrair_dados_basicos_formulario()  # reusa coleta ampla de campos
                for k, v in (js or {}).items():
                    k_low = str(k).lower()
                    v_str = str(v or '').strip()
                    if not v_str:
                        continue
                    if any(p in k_low for p in ['entrada', 'ingresso', 'chegada', 'brasil', 'resid']):
                        d = self._parse_data(v_str)
                        if d:
                            candidatos.append(('js', k, d))
            except Exception:
                pass
        # Escolher a data mais antiga entre candidatos
        if candidatos:
            candidatos.sort(key=lambda x: x[2])
            return candidatos[0][2]
        return None

    # ------------------------ Regra principal -----------------------------
    def _texto_norm(self, s: str) -> str:
        import unicodedata
        s = (s or '').lower()
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')

    def _pf_antes_de_10(self, texto: str) -> bool:
        t = self._texto_norm(texto)
        padroes = [
            r"antes\s+de\s+completar\s*10",
            r"antes\s+dos\s*10",
            r"com\s+menos\s+de\s*10",
            r"antes\s+de\s*10\s+anos",
        ]
        return any(re.search(p, t) for p in padroes)

    def _pf_depois_de_10(self, texto: str) -> bool:
        t = self._texto_norm(texto)
        padroes = [
            r"apos\s+os\s*10",
            r"depois\s+dos\s*10",
            r"ap[o\-]s\s+10\s+anos",
        ]
        return any(re.search(p, t) for p in padroes)

    def avaliar(self, lecom: Any, dados_formulario: Optional[Dict[str, Any]], data_inicial_processo: Optional[str], documentos_ja_baixados: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        dados = dados_formulario or {}
        data_ref_dt = self._parse_data(data_inicial_processo or '')

        # Preparar DocumentProvisoriaAction para downloads e validações
        try:
            from automation.actions.document_provisoria_action import DocumentProvisoriaAction
            doc_action = DocumentProvisoriaAction(lecom.driver, lecom.wait)
        except Exception:
            doc_action = None

        # 1) Gatilho: idade < 18 anos na data inicial
        idade_anos = None
        dn_str = (dados.get('data_nascimento') or dados.get('nascimento') or '').strip() if dados else ''
        dn_dt = self._parse_data(dn_str)
        if dn_dt and data_ref_dt:
            idade_anos = data_ref_dt.year - dn_dt.year - ((data_ref_dt.month, data_ref_dt.day) < (dn_dt.month, dn_dt.day))
        if idade_anos is None:
            return {
                'status': 'Erro',
                'elegibilidade_final': 'erro',
                'motivo_final': 'Data de nascimento ou data inicial do processo indisponível',
                'percentual_final': 0.0,
                'idade_naturalizando': None,
                'idade_entrada_brasil': None,
                'data_residencia_inicial': None,
            }
        if idade_anos >= 18:
            return {
                'status': 'Indeferimento automático',
                'elegibilidade_final': 'indeferimento_automatico',
                'motivo_final': f'Idade {idade_anos} anos (≥ 18) na data do processo',
                'percentual_final': 0.0,
                'idade_naturalizando': idade_anos,
                'idade_entrada_brasil': None,
                'data_residencia_inicial': None,
            }

        # 2) Gatilho: residência/ingresso no Brasil antes dos 10 anos
        # Estratégia: usar parecer PF como fonte prioritária
        parecer_pf = {}
        try:
            parecer_pf = lecom.extrair_parecer_pf() or {}
            print(f'[PARECER PF] Extraído: {parecer_pf.get("proposta_pf")}, Antes 10 anos: {parecer_pf.get("antes_10_anos")}')
        except Exception as e:
            print(f'[AVISO] Não foi possível extrair parecer PF: {e}')
            parecer_pf = {}

        antes10_ok = False
        idade_entrada = None
        data_resid_dt = None
        justificativa_gatilho = None

        # ESTRATÉGIA 1: Parecer PF (prioritário)
        if parecer_pf.get('antes_10_anos') is True:
            antes10_ok = True
            justificativa_gatilho = 'PF: ingresso antes dos 10 anos'
            print('[GATILHO] Aprovado via parecer PF (antes dos 10)')
        elif parecer_pf.get('antes_10_anos') is False:
            # PF indica depois dos 10 => falha direta
            justificativa_gatilho = 'PF: ingresso depois dos 10 anos'
            print('[GATILHO] Reprovado via parecer PF (depois dos 10)')
        else:
            # ESTRATÉGIA 2: Extrair data de residência/ingresso do formulário
            print('[GATILHO] Parecer PF não conclusivo, usando dados do formulário')
            data_resid_dt = self._extrair_data_residencia_inicial(dados, None)
            if data_resid_dt and dn_dt:
                idade_entrada = data_resid_dt.year - dn_dt.year - ((data_resid_dt.month, data_resid_dt.day) < (dn_dt.month, dn_dt.day))
                if idade_entrada < 10:
                    antes10_ok = True
                    justificativa_gatilho = f'Form: data de ingresso indica idade {idade_entrada} anos (< 10)'
                    print(f'[GATILHO] Aprovado via formulário (idade entrada: {idade_entrada} anos)')
            
            # ESTRATÉGIA 3: Fallback - se idade atual < 10, aceitar
            if not antes10_ok and idade_anos is not None and idade_anos < 10:
                antes10_ok = True
                justificativa_gatilho = f'Idade atual {idade_anos} anos (< 10)'
                print(f'[GATILHO] Aprovado via fallback (idade atual: {idade_anos} anos)')

        if not antes10_ok:
            return {
                'status': 'Indeferimento automático',
                'elegibilidade_final': 'indeferimento_automatico',
                'motivo_final': justificativa_gatilho or 'Residência/ingresso no Brasil antes dos 10 anos não comprovado',
                'percentual_final': 0.0,
                'idade_naturalizando': idade_anos,
                'idade_entrada_brasil': idade_entrada,
                'data_residencia_inicial': data_resid_dt.strftime('%d/%m/%Y') if data_resid_dt else None,
                'parecer_pf': parecer_pf,
            }

        # 3) Validar APENAS 4 documentos
        documentos_processados: list[dict] = []
        documentos_validos = 0
        faltantes: list[str] = []
        
        if doc_action is None:
            return {
                'status': 'Erro',
                'elegibilidade_final': 'erro',
                'motivo_final': 'DocumentProvisoriaAction indisponível',
                'percentual_final': 0.0,
            }

        for nome_doc in self.DOCS_PROVISORIA:
            try:
                ok = doc_action.baixar_e_validar_documento_individual(nome_doc)
            except Exception as e:
                print(f'[ERRO] ProvisoriaService: Exceção ao validar {nome_doc}: {e}')
                ok = False
            documentos_processados.append({'documento': nome_doc, 'status': 'VÁLIDO' if ok else 'INVÁLIDO'})
            if ok:
                documentos_validos += 1
            else:
                faltantes.append(nome_doc)

        # 4) Consolidação
        elegivel_docs = documentos_validos >= len(self.DOCS_PROVISORIA)  # todos válidos
        elegivel = elegivel_docs

        return {
            'status': 'Processado com sucesso' if elegivel else 'Indeferimento automático',
            'elegibilidade_final': 'deferimento' if elegivel else 'indeferimento_automatico',
            'percentual_final': round((documentos_validos / max(1, len(self.DOCS_PROVISORIA))) * 100.0, 2),
            'motivo_final': None if elegivel else f'Documentos inválidos/faltantes: {", ".join(faltantes)}',
            'idade_naturalizando': idade_anos,
            'idade_entrada_brasil': idade_entrada,
            'data_residencia_inicial': data_resid_dt.strftime('%d/%m/%Y') if data_resid_dt else None,
            'justificativa_gatilho_10anos': justificativa_gatilho,  # Justificativa de como foi aprovado o gatilho
            'parecer_pf': parecer_pf,
            'documentos_processados': documentos_processados,
            'total_documentos': len(self.DOCS_PROVISORIA),
        }

    def analisar_fluxo_completo(self, lecom: Any, codigo: str) -> Dict[str, Any]:
        """Fluxo completo usando a regra acima.
        - Garante dados (nome, filiação, data nasc.) via navegação atual
        - Avalia gatilhos e valida os 4 documentos
        """
        try:
            try:
                dados = lecom.extrair_dados_pessoais_formulario() or {}
            except Exception:
                dados = {}
            return self.avaliar(lecom, dados, getattr(lecom, 'data_inicial_processo', None))
        except Exception as e:
            return {'status': 'Erro', 'erro': str(e)}

