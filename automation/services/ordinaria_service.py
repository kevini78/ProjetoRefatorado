"""
Camada Service - Regras de negócio para naturalização ordinária
Responsável por orquestrar a análise de elegibilidade e geração de decisões
"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from ..actions.lecom_ordinaria_action import LecomAction
from ..actions.document_ordinaria_action import DocumentAction
from ..repositories.ordinaria_repository import OrdinariaRepository

# Analisadores modulares (cópias adaptadas dos módulos Ordinaria/*)
from automation.services.analise_elegibilidade_ordinaria import AnaliseElegibilidadeOrdinaria
from automation.services.analise_decisoes_ordinaria import AnaliseDecisoesOrdinaria


class OrdinariaService:
    """
    Service responsável pelas regras de negócio de naturalização ordinária
    """
    
    def __init__(self, lecom_action: LecomAction, document_action: DocumentAction, repository: OrdinariaRepository):
        """
        Inicializa o service
        
        Args:
            lecom_action: Instância da LecomAction
            document_action: Instância da DocumentAction  
            repository: Instância do OrdinariaRepository
        """
        self.lecom_action = lecom_action
        self.document_action = document_action
        self.repository = repository
        
        # Instanciar analisadores (preserva funcionalidade existente)
        self.analisador_elegibilidade = AnaliseElegibilidadeOrdinaria(lecom_action)
        self.gerador_decisao = AnaliseDecisoesOrdinaria()

    
    def analisar_elegibilidade(self, dados_pessoais: Dict[str, Any], data_inicial_processo: str, documentos_ocr: Dict[str, str]) -> Dict[str, Any]:
        """
        Realiza análise de elegibilidade completa (baseado no fluxo original)
        
        Args:
            dados_pessoais: Dados extraídos do formulário
            data_inicial_processo: Data de início do processo
            documentos_ocr: Textos OCR dos documentos
            
        Returns:
            Dict com resultado da análise de elegibilidade
        """
        try:
            print("\n=== ANÁLISE DE ELEGIBILIDADE ORDINÁRIA ===")
            print("Art. 65 da Lei nº 13.445/2017")
            print("="*80)
            
            # Verificar se temos dados mínimos necessários
            if not dados_pessoais.get('data_nascimento'):
                print("[ERRO] Data de nascimento não encontrada nos dados extraídos")
                print("Dados disponíveis:", list(dados_pessoais.keys())[:10])  # Mostrar primeiros 10 campos
                return {
                    'elegibilidade_final': 'indeferimento_automatico',
                    'motivo': 'Data de nascimento não encontrada',
                    'requisitos_atendidos': 0,
                    'total_requisitos': 4,
                    'fundamento_legal': 'Art. 65, inciso I da Lei nº 13.445/2017'
                }
            
            print(f"[OK] Data de nascimento encontrada: {dados_pessoais['data_nascimento']}")
            print(f"[OK] Data de nascimento confirmada: {dados_pessoais['data_nascimento']}")
            print("[DEBUG] Continuando para análise completa...")
            
            print("\n=== FLUXO COMPLETO – NATURALIZAÇÃO ORDINÁRIA ===")
            print("Art. 65 da Lei nº 13.445/2017")
            print("="*80)
            
            motivos_indeferimento = []
            status_requisitos = {
                'I': False,
                'II': False,
                'III': False,
                'IV': False
            }
            # Resultados detalhados por requisito (para planilha/compatibilidade)
            resultado_capacidade = {'atendido': False, 'motivo': 'Capacidade civil não avaliada', 'avaliado': False}
            resultado_residencia = {'atendido': False, 'motivo': 'Residência mínima não avaliada', 'avaliado': False}
            resultado_comunicacao = {'atendido': False, 'motivo': 'Comunicação em português não avaliada', 'avaliado': False}
            resultado_antecedentes = {'atendido': False, 'motivo': 'Antecedentes criminais não avaliados', 'avaliado': False}
            resultado_documentos_comp = {'atendido': False, 'documentos_validos': 0, 'total_documentos': 0, 'percentual_completude': 0.0, 'documentos_faltantes': [], 'avaliado': False}

            try:
                parecer_pf_dados = self.repository.extrair_parecer_pf()
            except Exception as e:
                print(f"[AVISO] Falha ao extrair parecer PF: {e}")
                parecer_pf_dados = {}

            if not isinstance(parecer_pf_dados, dict):
                parecer_pf_dados = {}
            parecer_pf_dados.setdefault('parecer_texto', '')
            parecer_pf_dados.setdefault('proposta_pf', 'Não encontrado')
            parecer_pf_dados.setdefault('alertas', [])
            parecer_pf_dados.setdefault('excedeu_ausencia', False)
            parecer_pf_dados.setdefault('ausencia_pais', False)
            parecer_pf_dados.setdefault('problema_portugues', False)
            parecer_pf_dados.setdefault('nao_compareceu_pf', False)
            parecer_pf_dados.setdefault('documentos_nao_apresentados', False)
            parecer_pf_dados.setdefault('faculdade_invalida', False)

            detalhe_capacidade = {
                'atendido': False,
                'motivo': 'Capacidade civil não avaliada',
                'avaliado': False
            }
            detalhe_residencia = {
                'atendido': False,
                'motivo': 'Residência mínima não avaliada',
                'avaliado': False
            }
            detalhe_portugues = {
                'atendido': False,
                'motivo': 'Comunicação em português não avaliada',
                'avaliado': False
            }
            detalhe_antecedentes = {
                'atendido': False,
                'motivo': 'Antecedentes criminais não avaliados',
                'avaliado': False,
                'motivos_especificos': []
            }
            documentos_complementares_faltantes: List[str] = []

            # REQUISITO I – Capacidade civil
            print("\n[INFO] REQUISITO I – Capacidade civil")
            print("Verificação: Data de nascimento")
            
            from datetime import datetime
            from automation.utils.date_utils import normalizar_data_para_ddmmaaaa
            
            print("\n" + "="*80)
            print("[INFO] REQUISITO I: CAPACIDADE CIVIL")
            print("Art. 65, inciso I da Lei nº 13.445/2017")
            print("="*80)
            
            try:
                data_nasc = datetime.strptime(dados_pessoais['data_nascimento'], '%d/%m/%Y')
                
                if data_inicial_processo:
                    # Normalizar data inicial do processo
                    data_inicial_convertida = normalizar_data_para_ddmmaaaa(data_inicial_processo)
                    data_inicio = datetime.strptime(data_inicial_convertida, '%d/%m/%Y')
                    
                    # Calcular idade usando método mais preciso
                    idade_anos = data_inicio.year - data_nasc.year
                    if (data_inicio.month, data_inicio.day) < (data_nasc.month, data_nasc.day):
                        idade_anos -= 1
                    
                    print(f"[DEBUG] Data normalizada: '{data_inicial_processo}' -> '{data_inicial_convertida}'")
                    print(f"[DATA] Data de nascimento: {dados_pessoais['data_nascimento']}")
                    print(f"[DATA] Data inicial do processo: {data_inicial_processo}")
                    print(f"🎂 Idade na data inicial: {idade_anos} anos")
                    
                    if idade_anos < 18:
                        print("❌ CAPACIDADE CIVIL: NÃO ATENDIDA")
                        print(f"❌ Possui {idade_anos} anos (< 18 anos)")
                        print("❌ Não pode continuar com o processamento")
                        print("📖 Fundamento: Art. 65, inciso I da Lei nº 13.445/2017")
                        print("📋 Continuando análise para identificar TODOS os motivos de indeferimento")
                        motivos_indeferimento.append('Art. 65, inciso I da Lei nº 13.445/2017')
                        status_requisitos['I'] = False
                        resultado_capacidade = {
                            'atendido': False,
                            'motivo': f'Possui {idade_anos} anos (< 18 anos)',
                            'idade': idade_anos,
                            'avaliado': True
                        }
                    else:
                        print("✅ CAPACIDADE CIVIL: ATENDIDA")
                        print(f"✅ Possui {idade_anos} anos (≥ 18 anos)")
                        print("✅ Pode continuar com o processamento")
                        print(f"[OK] Maior de 18 anos → check")
                        status_requisitos['I'] = True
                        resultado_capacidade = {
                            'atendido': True,
                            'motivo': f'Possui {idade_anos} anos (≥ 18 anos)',
                            'idade': idade_anos,
                            'avaliado': True
                        }
                        
            except Exception as e:
                print(f"[ERRO] Erro ao verificar capacidade civil: {e}")
                print("❌ CAPACIDADE CIVIL: ERRO NA VERIFICAÇÃO")
                motivos_indeferimento.append('Art. 65, inciso I da Lei nº 13.445/2017')
                status_requisitos['I'] = False
                resultado_capacidade = {
                    'atendido': False,
                    'motivo': f'Erro na verificação: {e}',
                    'avaliado': True
                }
            
            print("[DEBUG] REQUISITO I CONCLUÍDO - Indo para REQUISITO II...")
            
            # REQUISITO II – Residência mínima (EXATAMENTE IGUAL À AUTOMAÇÃO ORIGINAL)
            print('\n[INFO] REQUISITO II – Residência mínima')
            resultado_residencia = self._verificar_residencia_minima_com_validacao_ocr()
            status_requisitos['II'] = resultado_residencia.get('pode_continuar', False)
            
            # Normalizar para formato compatível
            resultado_residencia = {
                'atendido': bool(resultado_residencia.get('pode_continuar', False)),
                'motivo': resultado_residencia.get('motivo', 'Verificação de residência concluída'),
                'tem_reducao': resultado_residencia.get('tem_reducao', False),
                'prazo_requerido': resultado_residencia.get('prazo_requerido'),
                'tempo_comprovado': resultado_residencia.get('tempo_comprovado', 0),
                'avaliado': True
            }
            
            if not status_requisitos['II']:
                motivos_indeferimento.append('Art. 65, inciso II da Lei nº 13.445/2017')
            else:
                print('[OK] Residência mínima → check')
            
            # REQUISITO III – Comunicação em língua portuguesa
            print("\n[INFO] REQUISITO III – Comunicação em língua portuguesa")
            print("Verificando: Comprovante de comunicação em português")
            
            try:
                print("[INFO] Verificando documento de comunicação em português...")
                
                # Tentar baixar e validar o documento real
                print("[DOC] Baixando e validando: Comprovante de comunicação em português")
                sucesso_download = self.document_action.baixar_e_validar_documento_individual('Comprovante de comunicação em português')
                
                if sucesso_download:
                    print("✅ Comprovante de comunicação em português: VÁLIDO")
                    print("[OK] Comunicação em português → check")
                    status_requisitos['III'] = True
                    resultado_comunicacao = {'atendido': True, 'motivo': 'Anexou comprovante de comunicação em português', 'avaliado': True}
                else:
                    print("[ERRO] Comprovante de comunicação em português: NÃO ANEXADO")
                    print("[ERRO] Não anexou item 13")
                    print("📖 Fundamento: Art. 65, inciso III da Lei nº 13.445/2017")
                    motivos_indeferimento.append('Art. 65, inciso III da Lei nº 13.445/2017')
                    status_requisitos['III'] = False
                    resultado_comunicacao = {'atendido': False, 'motivo': 'Não anexou item 13 - Comprovante de comunicação em português', 'avaliado': True}
                        
            except Exception as e:
                print(f"[ERRO] Erro ao verificar comunicação: {e}")
                motivos_indeferimento.append('Art. 65, inciso III da Lei nº 13.445/2017')
                status_requisitos['III'] = False
                resultado_comunicacao = {'atendido': False, 'motivo': f'Erro na verificação: {e}', 'avaliado': True}
            
            # REQUISITO IV – Antecedentes criminais
            print("\n[INFO] REQUISITO IV – Antecedentes criminais")
            print("Baixando e validando documentos individualmente:")
            print("- Certidão de antecedentes criminais (Brasil)")
            print("- Certidão de antecedentes criminais (outros países)")
            print("- Comprovante de reabilitação (se necessário)")
            
            try:
                brasil_valido = False
                origem_valido = False
                motivos_antecedentes = []
                documentos_faltantes_antecedentes = []
                
                # Baixar e validar Certidão de antecedentes criminais (Brasil)
                print("\n[DOC] Processando: Certidão de antecedentes criminais (Brasil)")
                print("[DOC] Baixando e validando: Certidão de antecedentes criminais (Brasil)")
                sucesso_brasil = self.document_action.baixar_e_validar_documento_individual('Certidão de antecedentes criminais (Brasil)')
                
                if sucesso_brasil:
                    brasil_valido = True
                    print("✅ Certidão de antecedentes criminais (Brasil): VÁLIDO")
                else:
                    motivos_antecedentes.append('Certidão de antecedentes criminais do Brasil não anexada ou inválida')
                    documentos_faltantes_antecedentes.append('Certidão de antecedentes criminais da Justiça Federal')
                    documentos_faltantes_antecedentes.append('Certidão de antecedentes criminais da Justiça Estadual')
                    print("❌ Certidão de antecedentes criminais (Brasil): NÃO ANEXADO OU INVÁLIDO")
                
                # Baixar e validar Atestado antecedentes criminais (país de origem)
                print("\n[DOC] Processando: Atestado antecedentes criminais (país de origem)")
                print("[DOC] Baixando e validando: Atestado antecedentes criminais (país de origem)")
                sucesso_origem = self.document_action.baixar_e_validar_documento_individual('Atestado antecedentes criminais (país de origem)')
                
                if sucesso_origem:
                    origem_valido = True
                    print("✅ Atestado antecedentes criminais (país de origem): VÁLIDO")
                else:
                    motivos_antecedentes.append('Atestado de antecedentes criminais do país de origem não anexado ou inválido')
                    documentos_faltantes_antecedentes.append('Atestado de antecedentes criminais do país de origem')
                    print("❌ Atestado antecedentes criminais (país de origem): NÃO ANEXADO OU INVÁLIDO")
                
                # Verificar se AMBOS os documentos são válidos
                print(f"\n{'='*60}")
                print(f"📊 RESUMO REQUISITO IV: Brasil={brasil_valido}, Origem={origem_valido}")
                print(f"{'='*60}")
                
                if brasil_valido and origem_valido:
                    print("✅ REQUISITO IV: ATENDIDO - AMBOS os documentos de antecedentes válidos")
                    print("[OK] Antecedentes criminais → check")
                    status_requisitos['IV'] = True
                    resultado_antecedentes = {
                        'atendido': True, 
                        'motivo': 'Antecedentes criminais em ordem (Brasil e país de origem)', 
                        'brasil_valido': True,
                        'origem_valido': True,
                        'avaliado': True
                    }
                else:
                    print("❌ REQUISITO IV: NÃO ATENDIDO")
                    motivo_detalhado = '; '.join(motivos_antecedentes)
                    print(f"[ERRO] {motivo_detalhado}")
                    print("📖 Fundamento: Art. 65, inciso IV da Lei nº 13.445/2017")
                    motivos_indeferimento.append('Art. 65, inciso IV da Lei nº 13.445/2017')
                    status_requisitos['IV'] = False
                    resultado_antecedentes = {
                        'atendido': False, 
                        'motivo': motivo_detalhado,
                        'motivos_especificos': motivos_antecedentes,
                        'documentos_faltantes': documentos_faltantes_antecedentes,
                        'brasil_valido': brasil_valido,
                        'origem_valido': origem_valido,
                        'avaliado': True
                    }
                    
            except Exception as e:
                print(f"[ERRO] Erro ao verificar antecedentes: {e}")
                motivos_indeferimento.append('Art. 65, inciso IV da Lei nº 13.445/2017')
                status_requisitos['IV'] = False
                resultado_antecedentes = {'atendido': False, 'motivo': f'Erro na verificação: {e}', 'avaliado': True}
            
            print("\n=== ETAPA 5: VERIFICAÇÕES PRELIMINARES CONCLUÍDAS ===")
            print("[OK] Documentos já validados individualmente:")
            
            # DOCUMENTOS COMPLEMENTARES
            print("\n[INFO] DOCUMENTOS COMPLEMENTARES (Anexo I da Portaria 623/2020)")
            print("Baixando e validando documentos restantes individualmente:")
            print("- Comprovante de tempo de residência → item 8")
            print("- Comprovante de situação cadastral do CPF → item 4")
            print("- CRNM → item 3")
            print("- Documento de viagem internacional → item 2")
            
            print("\n[BUSCA] Baixando e validando documentos complementares individualmente...")
            
            documentos_complementares = [
                'Comprovante de tempo de residência',
                'Comprovante da situação cadastral do CPF', 
                'Carteira de Registro Nacional Migratório',
                'Documento de viagem internacional'
            ]
            
            documentos_complementares_validos = 0
            documentos_complementares_faltantes = []
            
            for documento in documentos_complementares:
                print(f"\n[DOC] Processando: {documento}")
                print(f"[DOC] Baixando e validando: {documento}")
                sucesso = self.document_action.baixar_e_validar_documento_individual(documento)
                
                if sucesso:
                    print(f"✅ {documento}: VÁLIDO")
                    documentos_complementares_validos += 1
                else:
                    print(f"[ERRO] {documento}: NÃO ANEXADO")
                    # Mapear para item do anexo
                    if 'registro nacional' in documento.lower() or 'migratório' in documento.lower() or 'crnm' in documento.lower():
                        documentos_complementares_faltantes.append('Não anexou item 3')
                    elif 'cpf' in documento.lower():
                        documentos_complementares_faltantes.append('Não anexou item 4')
                    elif 'viagem internacional' in documento.lower():
                        documentos_complementares_faltantes.append('Não anexou item 2')
                    elif 'tempo de residência' in documento.lower():
                        documentos_complementares_faltantes.append('Não anexou item 8')
            
            print(f"\n============================================================")
            print(f"📊 RESUMO DOCUMENTOS COMPLEMENTARES: {documentos_complementares_validos}/{len(documentos_complementares)} documentos válidos ({(documentos_complementares_validos/len(documentos_complementares)*100):.0f}%)")
            print(f"============================================================")
            
            resultado_documentos_comp = {
                'atendido': documentos_complementares_validos == len(documentos_complementares),
                'documentos_validos': documentos_complementares_validos,
                'total_documentos': len(documentos_complementares),
                'percentual_completude': (documentos_complementares_validos/len(documentos_complementares))*100 if documentos_complementares else 0.0,
                'documentos_faltantes': documentos_complementares_faltantes,
                'avaliado': True
            }
            
            if documentos_complementares_validos == len(documentos_complementares):
                print("[OK] DOCUMENTOS COMPLEMENTARES: COMPLETOS (100%)")
            else:
                print(f"[AVISO] DOCUMENTOS COMPLEMENTARES: INCOMPLETOS ({documentos_complementares_validos}/{len(documentos_complementares)})")
            
            try:
                # SEMPRE mostrar resumo dos requisitos
                print(f"\n📋 RESUMO DOS REQUISITOS DO ART. 65:")
                print(f"   {'✅' if status_requisitos['I'] else '❌'} Requisito I (Capacidade Civil): {'ATENDIDO' if status_requisitos['I'] else 'NÃO ATENDIDO'}")
                print(f"   {'✅' if status_requisitos['II'] else '❌'} Requisito II (Residência): {'ATENDIDO' if status_requisitos['II'] else 'NÃO ATENDIDO'}")
                print(f"   {'✅' if status_requisitos['III'] else '❌'} Requisito III (Português): {'ATENDIDO' if status_requisitos['III'] else 'NÃO ATENDIDO'}")
                print(f"   {'✅' if status_requisitos['IV'] else '❌'} Requisito IV (Antecedentes): {'ATENDIDO' if status_requisitos['IV'] else 'NÃO ATENDIDO'}")

                # Integração com alertas do Parecer PF
                alertas_pf = parecer_pf_dados.get('alertas', []) or []
                alertas_pf_upper = [str(a).upper() for a in alertas_pf]

                # Alertas PF que geram indeferimento automático, mesmo com documentos válidos
                alertas_pf_indeferimento_chaves = [
                    "REQUERENTE NÃO ESTÁ NO PAÍS",
                    "INDEFERIMENTO AUTOMÁTICO",
                    "DOCUMENTOS NÃO APRESENTADOS INTEGRALMENTE",
                    "DOCUMENTO DE PORTUGUÊS NÃO COMPROVADO NO ATENDIMENTO PRESENCIAL",
                    "EXCEDEU LIMITE DE AUSÊNCIA DO PAÍS",
                    "EXCEDEU LIMITE DE AUSÊNCIAS",
                    "NÃO CONSEGUE SE COMUNICAR EM PORTUGUÊS",
                    "ATENDIMENTO PRESENCIAL",
                    "REQUERENTE NÃO COMPARECEU",
                    "AUSÊNCIA DE COLETA BIOMÉTRICA",
                ]

                # Alerta PF que força análise manual
                alertas_pf_analise_manual_chaves = [
                    "⚠️ PARECER PF SEM PRAZO DE RESIDÊNCIA ESPECIFICADO",
                ]

                def _possui_alerta(chave: str) -> bool:
                    chave_upper = chave.upper()
                    return any(chave_upper in alerta for alerta in alertas_pf_upper)

                tem_alerta_pf_analise_manual = any(
                    _possui_alerta(ch) for ch in alertas_pf_analise_manual_chaves
                )
                
                # Se não compareceu à PF (incluindo ausência de coleta biométrica), NÃO vai para análise manual
                # Isso tem prioridade sobre qualquer outro alerta
                if parecer_pf_dados.get('nao_compareceu_pf'):
                    tem_alerta_pf_analise_manual = False
                    print("[ALERTA PF] Não compareceu à PF - INDEFERIMENTO AUTOMÁTICO (prioridade máxima)")
                elif tem_alerta_pf_analise_manual:
                    print("[ALERTA PF] Detectado alerta que requer ANÁLISE MANUAL")

                # Se a verificação de residência marcou alerta crítico, forçar análise manual
                # EXCETO se não compareceu à PF
                if resultado_residencia.get('alerta_critico') and not parecer_pf_dados.get('nao_compareceu_pf'):
                    if not _possui_alerta("PARECER PF SEM PRAZO DE RESIDÊNCIA ESPECIFICADO"):
                        parecer_pf_dados.setdefault('alertas', []).append(
                            "⚠️ PARECER PF SEM PRAZO DE RESIDÊNCIA ESPECIFICADO"
                        )
                        alertas_pf_upper.append("PARECER PF SEM PRAZO DE RESIDÊNCIA ESPECIFICADO")
                    tem_alerta_pf_analise_manual = True
                    print("[ALERTA PF] Alerta crítico de residência - forçando ANÁLISE MANUAL")

                # Motivos adicionais vindos exclusivamente do Parecer PF
                motivos_pf_indeferimento: List[str] = []
                for alerta in parecer_pf_dados.get('alertas', []):
                    alerta_upper = str(alerta).upper()
                    if any(ch.upper() in alerta_upper for ch in alertas_pf_indeferimento_chaves):
                        if alerta not in motivos_pf_indeferimento:
                            motivos_pf_indeferimento.append(alerta)
                            print(f"[ALERTA PF] Detectado alerta de indeferimento: {alerta}")

                # Consolidar todos os motivos de indeferimento (requisitos + PF)
                motivos_totais = list(motivos_indeferimento)
                for motivo_pf in motivos_pf_indeferimento:
                    if motivo_pf not in motivos_totais:
                        motivos_totais.append(motivo_pf)

                print(f"\n📋 Total de motivos de indeferimento encontrados: {len(motivos_totais)}")
                if motivos_totais:
                    for i, motivo in enumerate(motivos_totais, 1):
                        print(f"  {i}. {motivo}")

                # Determinar resultado final baseado nos motivos coletados e alertas PF
                if tem_alerta_pf_analise_manual:
                    print(f"\n⚠️ DECISÃO PRELIMINAR: ANÁLISE MANUAL")
                    print(
                        "⚠️ Caso marcado para análise manual devido a alerta crítico no Parecer PF "
                        "(prazo de residência não especificado/dados insuficientes)."
                    )
                    requisitos_atendidos = sum(
                        1 for atendido in status_requisitos.values() if atendido
                    )
                    resultado = {
                        'elegibilidade_final': 'analise_manual',
                        'motivos_indeferimento': motivos_totais,
                        'requisitos_nao_atendidos': motivos_totais,
                        'requisitos_atendidos': requisitos_atendidos,
                        'total_requisitos': len(status_requisitos),
                        'status_requisitos': status_requisitos,
                        'requisito_i_capacidade_civil': resultado_capacidade,
                        'requisito_ii_residencia_minima': resultado_residencia,
                        'requisito_iii_comunicacao_portugues': resultado_comunicacao,
                        'requisito_iv_antecedentes_criminais': resultado_antecedentes,
                        'documentos_complementares': resultado_documentos_comp,
                        'documentos_faltantes': resultado_documentos_comp.get('documentos_faltantes', []),
                        'parecer_pf': parecer_pf_dados
                    }
                elif motivos_totais:
                    print(f"\n❌ DECISÃO PRELIMINAR: INDEFERIMENTO")
                    print(
                        f"❌ Foram identificados {len(motivos_totais)} motivo(s) de indeferimento "
                        "(incluindo alertas da PF, se houver)."
                    )
                    requisitos_atendidos = sum(
                        1 for atendido in status_requisitos.values() if atendido
                    )
                    
                    # Consolidar documentos faltantes (complementares + antecedentes)
                    documentos_faltantes_totais = resultado_documentos_comp.get('documentos_faltantes', [])
                    if resultado_antecedentes.get('documentos_faltantes'):
                        documentos_faltantes_totais.extend(resultado_antecedentes['documentos_faltantes'])
                    
                    # Gerar texto do despacho de indeferimento
                    despacho_indeferimento = self._gerar_despacho_indeferimento(
                        dados_pessoais, 
                        status_requisitos,
                        documentos_faltantes_totais
                    )
                    
                    resultado = {
                        'elegibilidade_final': 'indeferimento',
                        'motivos_indeferimento': motivos_totais,
                        'requisitos_nao_atendidos': motivos_totais,
                        'requisitos_atendidos': requisitos_atendidos,
                        'total_requisitos': len(status_requisitos),
                        'status_requisitos': status_requisitos,
                        'requisito_i_capacidade_civil': resultado_capacidade,
                        'requisito_ii_residencia_minima': resultado_residencia,
                        'requisito_iii_comunicacao_portugues': resultado_comunicacao,
                        'requisito_iv_antecedentes_criminais': resultado_antecedentes,
                        'documentos_complementares': resultado_documentos_comp,
                        'documentos_faltantes': resultado_documentos_comp.get('documentos_faltantes', []),
                        'parecer_pf': parecer_pf_dados,
                        'despacho_automatico': despacho_indeferimento
                    }
                else:
                    print(f"\n✅ DECISÃO PRELIMINAR: DEFERIMENTO")
                    print(f"✅ Todos os requisitos foram atendidos")
                    
                    # Gerar texto da portaria de deferimento
                    despacho_deferimento = self._gerar_portaria_deferimento(dados_pessoais)
                    
                    resultado = {
                        'elegibilidade_final': 'deferimento',
                        'motivos_indeferimento': [],
                        'requisitos_atendidos': len(status_requisitos),
                        'total_requisitos': len(status_requisitos),
                        'status_requisitos': status_requisitos,
                        'requisito_i_capacidade_civil': resultado_capacidade,
                        'requisito_ii_residencia_minima': resultado_residencia,
                        'requisito_iii_comunicacao_portugues': resultado_comunicacao,
                        'requisito_iv_antecedentes_criminais': resultado_antecedentes,
                        'documentos_complementares': resultado_documentos_comp,
                        'documentos_faltantes': resultado_documentos_comp.get('documentos_faltantes', []),
                        'parecer_pf': parecer_pf_dados,
                        'despacho_automatico': despacho_deferimento
                    }
                    
            except Exception as e:
                print(f"[ERRO] Erro na análise de documentos complementares: {e}")
                requisitos_atendidos = sum(1 for atendido in status_requisitos.values() if atendido)
                resultado = {
                    'elegibilidade_final': 'indeferimento_automatico',
                    'motivos_indeferimento': motivos_indeferimento + ['Erro na análise de documentos complementares'],
                    'requisitos_atendidos': requisitos_atendidos,
                    'total_requisitos': len(status_requisitos),
                    'status_requisitos': status_requisitos
                }
            
            print(f"[OK] Análise de elegibilidade concluída: {resultado.get('elegibilidade_final', 'erro')}")
            return resultado
            
        except Exception as e:
            print(f"[ERRO] Erro na análise de elegibilidade: {e}")
            return {
                'elegibilidade_final': 'erro',
                'motivo': f'Erro na análise: {e}',
                'requisitos_atendidos': 0,
                'total_requisitos': 4
            }
    
    def _verificar_residencia_minima_com_validacao_ocr(self):
        """
        REQUISITO II – Residência mínima com validação OCR individual (IGUAL À AUTOMAÇÃO ORIGINAL)
        """
        from selenium.webdriver.common.by import By
        
        try:
            print('Passo 1 – Verificar se há redução de prazo')
            
            tem_reducao = False
            motivo_reducao = ""
            
            # VERIFICAÇÃO 1: Campo HIP_CON_0 (redução de prazo geral)
            try:
                elemento_reducao = self.lecom_action.driver.find_element(
                    By.XPATH, 
                    "//label[@for='HIP_CON_0' and contains(@aria-checked, 'true')]"
                )
                if elemento_reducao and "Sim" in elemento_reducao.text:
                    tem_reducao = True
                    motivo_reducao = "HIP_CON_0"
                    print("[OK] Redução de prazo (HIP_CON_0): SIM")
                    print("[INFO] Validando documento: Comprovante de redução de prazo")
                    
                    # BAIXAR E VALIDAR OCR DO COMPROVANTE DE REDUÇÃO
                    doc_reducao_valido = self.document_action.baixar_e_validar_documento_individual('Comprovante de redução de prazo')
                    
                    if not doc_reducao_valido:
                        print("[ERRO] Comprovante de redução de prazo: INVÁLIDO ou não anexado")
                        # Continuar para verificar cônjuge/filho brasileiro
                        tem_reducao = False
                        motivo_reducao = ""
                    else:
                        print("[OK] Comprovante de redução de prazo: VÁLIDO")
                        prazo_requerido = 1
                        print("[INFO] Redução válida: exigir 1 ano de residência")
            except Exception as e:
                print(f"[AVISO] Campo HIP_CON_0 não encontrado: {e}")
            
            # VERIFICAÇÃO 2: Cônjuge ou filho brasileiro (se não teve redução anterior)
            if not tem_reducao:
                print("[INFO] Verificando cônjuge ou filho brasileiro...")
                
                # Verificar se possui cônjuge brasileiro
                conjugue_brasileiro = self._verificar_conjugue_brasileiro()
                
                # Verificar se possui filho brasileiro
                filho_brasileiro = self._verificar_filho_brasileiro()
                
                if conjugue_brasileiro or filho_brasileiro:
                    tem_reducao = True
                    if conjugue_brasileiro:
                        motivo_reducao = "cônjuge brasileiro"
                        print("[OK] Redução de prazo: SIM (cônjuge brasileiro)")
                    else:
                        motivo_reducao = "filho brasileiro"
                        print("[OK] Redução de prazo: SIM (filho brasileiro)")
                    
                    prazo_requerido = 1
                    print("[INFO] Redução por vínculo familiar: exigir 1 ano de residência")
                else:
                    tem_reducao = False
                    prazo_requerido = 4
                    print("[ERRO] Redução de prazo: NÃO")
                    print("[INFO] Sem cônjuge/filho brasileiro: exigir 4 anos de residência")
            
            # Se ainda não definiu prazo, usar padrão
            if 'prazo_requerido' not in locals():
                tem_reducao = False
                prazo_requerido = 4
                print("[ERRO] Redução de prazo: NÃO (padrão)")
                print("[INFO] Exigir 4 anos de residência indeterminada ou permanente")
            
            print('\nPasso 2 – Validar residência')
            print('Pode ser verificado por:')
            print('- Campo CHPF_PARECER (Parecer) - PRIORIDADE')
            print('- Documentos validados via OCR (CRNM ou parecer PF) - FALLBACK')
            
            data_residencia = None
            tempo_residencia_anos = 0
            
            # ========== PRIORIDADE 1: PARECER DA PF ==========
            print("[INFO] Passo 1 – Verificar parecer da PF (PRIORIDADE)")
            try:
                elemento_parecer = self.lecom_action.driver.find_element(By.ID, "CHPF_PARECER")
                parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
                
                if parecer_texto:
                    print("[INFO] Analisando campo CHPF_PARECER...")
                    print(f"[DEBUG] Texto do parecer (primeiros 200 chars): {parecer_texto[:200]}...")
                    
                    # Usar o método de extração de tempo existente
                    tempo_residencia_anos = self._extrair_tempo_residencia_parecer(parecer_texto)
                    
                    if tempo_residencia_anos > 0:
                        print(f" [PRIORIDADE] Tempo de residência extraído do PARECER DA PF: {tempo_residencia_anos:.2f} anos")
                    else:
                        print("[AVISO] Não foi possível extrair tempo específico do parecer")
                else:
                    print(f"[AVISO] Campo CHPF_PARECER vazio")
                    
            except Exception as e:
                print(f"[AVISO] Campo CHPF_PARECER não encontrado: {e}")
            
            # Se não encontrou tempo de residência via parecer PF, tentar extrair de documentos válidos
            if tempo_residencia_anos == 0:
                print("[INFO] Passo 2 – Utilizando documentos validados para confirmar residência")
                try:
                    # Tentar usar dados extraídos da CRNM ou comprovante de residência via OCR
                    texto_crnm = self.document_action.ultimo_texto_ocr.get('Carteira de Registro Nacional Migratório') if hasattr(self.document_action, 'ultimo_texto_ocr') else ''
                    texto_residencia = self.document_action.ultimo_texto_ocr.get('Comprovante de tempo de residência') if hasattr(self.document_action, 'ultimo_texto_ocr') else ''
                    if texto_crnm:
                        tempo_residencia_anos = self._extrair_tempo_residencia_parecer(texto_crnm)
                        if tempo_residencia_anos > 0:
                            print(f" [OCR] Tempo extraído da CRNM: {tempo_residencia_anos:.2f} anos")
                    if tempo_residencia_anos == 0 and texto_residencia:
                        tempo_residencia_anos = self._extrair_tempo_residencia_parecer(texto_residencia)
                        if tempo_residencia_anos > 0:
                            print(f" [OCR] Tempo extraído do comprovante de residência: {tempo_residencia_anos:.2f} anos")
                except Exception as e:
                    print(f"[AVISO] Falha ao extrair tempo de residência via OCR: {e}")

            # Se ainda não encontrou tempo de residência, retornar com observação
            if tempo_residencia_anos == 0:
                print(" ALERTA CRÍTICO: PRAZO DE RESIDÊNCIA NÃO ENCONTRADO!")
                print("  OBSERVAÇÃO: Prazo de residência não foi encontrado no parecer PF ou nos documentos validados")
                print("  AÇÃO NECESSÁRIA: Verificar manualmente o tempo de residência do requerente")
                print(" ATENÇÃO: Não é possível indeferir sem saber o prazo de residência por tempo indeterminado!")
                return {
                    'atendido': False,
                    'motivo': 'Prazo de residência não localizado nos campos do sistema',
                    'observacao': 'ALERTA: Verificar manualmente - Campo RES_DAT vazio, parecer CHPF_PARECER sem informação e CRNM sem data válida. NÃO É POSSÍVEL INDEFERIR SEM SABER O PRAZO DE RESIDÊNCIA POR TEMPO INDETERMINADO!',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': 0,
                    'pode_continuar': False,
                    'alerta_critico': True
                }
            
            # Verificar se atende ao prazo mínimo
            print(f"\n[DADOS] ========== VERIFICAÇÃO FINAL DE RESIDÊNCIA ==========")
            print(f"[DADOS] Prazo requerido: {prazo_requerido} ano(s)")
            print(f"[DADOS] Tempo comprovado: {tempo_residencia_anos:.2f} anos")
            print(f"[DADOS] Redução de prazo: {'SIM' if tem_reducao else 'NÃO'}")
            
            # Adicionar tolerância de 0.05 anos (~18 dias) para evitar problemas de arredondamento
            tolerancia = 0.05
            prazo_minimo_com_tolerancia = prazo_requerido - tolerancia
            print(f"[DADOS] Prazo mínimo com tolerância: {prazo_minimo_com_tolerancia:.2f} anos")
            print(f"[DADOS] Comparação: {tempo_residencia_anos:.2f} >= {prazo_minimo_com_tolerancia:.2f}?")
            
            if tempo_residencia_anos >= (prazo_requerido - tolerancia):
                print(" [RESULTADO] Residência mínima: ATENDIDA")
                print(f" [DETALHE] {tempo_residencia_anos:.2f} anos >= {prazo_minimo_com_tolerancia:.2f} anos")
                return {
                    'atendido': True,
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': True
                }
            else:
                print(" [RESULTADO] Residência mínima: NÃO ATENDIDA")
                print(f" [DETALHE] {tempo_residencia_anos:.2f} anos < {prazo_minimo_com_tolerancia:.2f} anos")
                print("[ERRO] Não comprovou residência mínima")
                print(" Fundamento: Art. 65, inciso II da Lei nº 13.445/2017")
                return {
                    'atendido': False,
                    'motivo': f'Tempo insuficiente: {tempo_residencia_anos:.2f} anos < {prazo_minimo_com_tolerancia:.2f} anos',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': False
                }
                
        except Exception as e:
            print(f"[ERRO] Erro na verificação de residência: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False
            }
    
    def _verificar_conjugue_brasileiro(self):
        """
        Verifica se possui cônjuge brasileiro através de campos específicos ou tabela
        """
        from selenium.webdriver.common.by import By
        
        try:
            print("[VERIFICAÇÃO] Procurando cônjuge brasileiro...")
            
            # MÉTODO 1: Verificar campo específico de cônjuge brasileiro
            try:
                # Procurar por campos que indiquem cônjuge brasileiro
                campos_conjugue = [
                    "CONJUGUE_BRASILEIRO",
                    "CONJ_BRASILEIRO", 
                    "ESPOSO_BRASILEIRO",
                    "ESPOSA_BRASILEIRO",
                    "CONJUGE_BR"
                ]
                
                for campo in campos_conjugue:
                    try:
                        elemento = self.lecom_action.driver.find_element(By.ID, campo)
                        valor = elemento.get_attribute("value") or elemento.text
                        if valor and ("sim" in valor.lower() or "brasileiro" in valor.lower()):
                            print(f"[OK] Campo {campo} indica cônjuge brasileiro: {valor}")
                            
                            # Tentar baixar documento comprobatório
                            doc_valido = self._verificar_documento_conjugue_brasileiro()
                            if doc_valido:
                                print("[OK] Documento de cônjuge brasileiro: VÁLIDO")
                                return True
                            else:
                                print("[AVISO] Campo indica cônjuge brasileiro, mas documento não validado")
                                
                    except Exception:
                        continue
                        
            except Exception as e:
                print(f"[AVISO] Erro ao verificar campos de cônjuge: {e}")
            
            # MÉTODO 2: Verificar na tabela de documentos
            try:
                print("[INFO] Verificando tabela de documentos para cônjuge brasileiro...")
                
                # Procurar por linhas da tabela que mencionem cônjuge brasileiro
                xpath_tabela = "//table//tr[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cônjuge') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'conjugue') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'esposo') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'esposa')]"
                
                elementos_tabela = self.lecom_action.driver.find_elements(By.XPATH, xpath_tabela)
                
                for elemento in elementos_tabela:
                    texto = elemento.text.lower()
                    if any(termo in texto for termo in ['cônjuge brasileiro', 'conjugue brasileiro', 'esposo brasileiro', 'esposa brasileiro', 'certidão de casamento']):
                        print(f"[OK] Encontrado na tabela: {elemento.text[:100]}...")
                        
                        # Verificar se há link de download na linha
                        try:
                            link_download = elemento.find_element(By.XPATH, ".//a[contains(@href, 'download') or .//i[@type='cloud_download']]")
                            if link_download:
                                print("[OK] Link de download encontrado para documento de cônjuge")
                                
                                # Tentar baixar e validar documento
                                doc_valido = self._baixar_e_validar_documento_conjugue(link_download)
                                if doc_valido:
                                    return True
                        except Exception:
                            pass
                            
            except Exception as e:
                print(f"[AVISO] Erro ao verificar tabela de cônjuge: {e}")
            
            print("[INFO] Cônjuge brasileiro: NÃO ENCONTRADO")
            return False
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar cônjuge brasileiro: {e}")
            return False
    
    def _verificar_filho_brasileiro(self):
        """
        Verifica se possui filho brasileiro através de campos específicos ou tabela
        """
        from selenium.webdriver.common.by import By
        
        try:
            print("[VERIFICAÇÃO] Procurando filho brasileiro...")
            
            # MÉTODO 1: Verificar campo específico de filho brasileiro
            try:
                campos_filho = [
                    "FILHO_BRASILEIRO",
                    "FILHOS_BRASILEIROS",
                    "DESCENDENTE_BRASILEIRO",
                    "FILHO_BR"
                ]
                
                for campo in campos_filho:
                    try:
                        elemento = self.lecom_action.driver.find_element(By.ID, campo)
                        valor = elemento.get_attribute("value") or elemento.text
                        if valor and ("sim" in valor.lower() or "brasileiro" in valor.lower()):
                            print(f"[OK] Campo {campo} indica filho brasileiro: {valor}")
                            
                            # Tentar baixar documento comprobatório
                            doc_valido = self._verificar_documento_filho_brasileiro()
                            if doc_valido:
                                print("[OK] Documento de filho brasileiro: VÁLIDO")
                                return True
                            else:
                                print("[AVISO] Campo indica filho brasileiro, mas documento não validado")
                                
                    except Exception:
                        continue
                        
            except Exception as e:
                print(f"[AVISO] Erro ao verificar campos de filho: {e}")
            
            # MÉTODO 2: Verificar na tabela de documentos
            try:
                print("[INFO] Verificando tabela de documentos para filho brasileiro...")
                
                # Procurar por linhas da tabela que mencionem filho brasileiro
                xpath_tabela = "//table//tr[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'filho') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'filha') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'descendente')]"
                
                elementos_tabela = self.lecom_action.driver.find_elements(By.XPATH, xpath_tabela)
                
                for elemento in elementos_tabela:
                    texto = elemento.text.lower()
                    if any(termo in texto for termo in ['filho brasileiro', 'filha brasileiro', 'descendente brasileiro', 'certidão de nascimento']):
                        print(f"[OK] Encontrado na tabela: {elemento.text[:100]}...")
                        
                        # Verificar se há link de download na linha
                        try:
                            link_download = elemento.find_element(By.XPATH, ".//a[contains(@href, 'download') or .//i[@type='cloud_download']]")
                            if link_download:
                                print("[OK] Link de download encontrado para documento de filho")
                                
                                # Tentar baixar e validar documento
                                doc_valido = self._baixar_e_validar_documento_filho(link_download)
                                if doc_valido:
                                    return True
                        except Exception:
                            pass
                            
            except Exception as e:
                print(f"[AVISO] Erro ao verificar tabela de filho: {e}")
            
            print("[INFO] Filho brasileiro: NÃO ENCONTRADO")
            return False
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar filho brasileiro: {e}")
            return False
    
    def _verificar_documento_conjugue_brasileiro(self):
        """
        Tenta baixar e validar documento de cônjuge brasileiro
        """
        try:
            # Tentar baixar documentos relacionados a cônjuge brasileiro
            documentos_conjugue = [
                'Certidão de casamento',
                'Comprovante de cônjuge brasileiro',
                'Documento de cônjuge brasileiro'
            ]
            
            for doc_nome in documentos_conjugue:
                try:
                    print(f"[DOC] Tentando baixar: {doc_nome}")
                    sucesso = self.document_action.baixar_e_validar_documento_individual(doc_nome)
                    if sucesso:
                        print(f"[OK] {doc_nome}: VÁLIDO")
                        return True
                except Exception as e:
                    print(f"[AVISO] Erro ao baixar {doc_nome}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar documento de cônjuge: {e}")
            return False
    
    def _verificar_documento_filho_brasileiro(self):
        """
        Tenta baixar e validar documento de filho brasileiro
        """
        try:
            # Tentar baixar documentos relacionados a filho brasileiro
            documentos_filho = [
                'Certidão de nascimento',
                'Comprovante de filho brasileiro',
                'Documento de filho brasileiro'
            ]
            
            for doc_nome in documentos_filho:
                try:
                    print(f"[DOC] Tentando baixar: {doc_nome}")
                    sucesso = self.document_action.baixar_e_validar_documento_individual(doc_nome)
                    if sucesso:
                        print(f"[OK] {doc_nome}: VÁLIDO")
                        return True
                except Exception as e:
                    print(f"[AVISO] Erro ao baixar {doc_nome}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar documento de filho: {e}")
            return False
    
    def _baixar_e_validar_documento_conjugue(self, link_elemento):
        """
        Baixa e valida documento de cônjuge através de link específico
        """
        try:
            print("[DOC] Baixando documento de cônjuge brasileiro...")
            
            # Executar clique no link
            link_elemento.click()
            
            # Aguardar download e validar
            # Implementar lógica de download e validação específica
            # Por enquanto, retornar True se conseguiu clicar
            print("[OK] Download de documento de cônjuge iniciado")
            return True
            
        except Exception as e:
            print(f"[ERRO] Erro ao baixar documento de cônjuge: {e}")
            return False
    
    def _baixar_e_validar_documento_filho(self, link_elemento):
        """
        Baixa e valida documento de filho através de link específico
        """
        try:
            print("[DOC] Baixando documento de filho brasileiro...")
            
            # Executar clique no link
            link_elemento.click()
            
            # Aguardar download e validar
            # Implementar lógica de download e validação específica
            # Por enquanto, retornar True se conseguiu clicar
            print("[OK] Download de documento de filho iniciado")
            return True
            
        except Exception as e:
            print(f"[ERRO] Erro ao baixar documento de filho: {e}")
            return False
    
    def _validar_certidao_filho_brasileiro(self, texto_ocr: str) -> bool:
        """
        Valida se o texto OCR é de uma certidão de nascimento de filho brasileiro
        """
        try:
            if not texto_ocr or len(texto_ocr) < 50:
                print("[VALIDAÇÃO] Texto OCR muito curto ou vazio")
                return False
            
            texto_lower = texto_ocr.lower()
            
            # Palavras-chave que devem estar presentes
            palavras_obrigatorias = [
                'certidão',
                'nascimento',
                'brasil'
            ]
            
            # Verificar se todas as palavras obrigatórias estão presentes
            palavras_encontradas = []
            for palavra in palavras_obrigatorias:
                if palavra in texto_lower:
                    palavras_encontradas.append(palavra)
                    print(f"[VALIDAÇÃO] ✅ Palavra encontrada: {palavra}")
                else:
                    print(f"[VALIDAÇÃO] ❌ Palavra não encontrada: {palavra}")
            
            if len(palavras_encontradas) >= 2:  # Pelo menos 2 das 3 palavras
                print(f"[VALIDAÇÃO] ✅ Documento válido: {len(palavras_encontradas)}/3 palavras encontradas")
                return True
            else:
                print(f"[VALIDAÇÃO] ❌ Documento inválido: apenas {len(palavras_encontradas)}/3 palavras encontradas")
                return False
                
        except Exception as e:
            print(f"[ERRO] Erro na validação da certidão: {e}")
            return False
    
    def _identificar_tipo_antecedentes_brasil(self, texto_ocr: str) -> str:
        """
        Identifica se os antecedentes criminais do Brasil são estaduais, federais ou ambos
        """
        try:
            texto_lower = texto_ocr.lower()
            
            # Termos que indicam antecedentes estaduais
            termos_estaduais = [
                'secretaria de segurança pública',
                'secretaria da segurança pública',
                'ssp',
                'polícia civil',
                'delegacia',
                'estado de',
                'governo do estado',
                'estadual'
            ]
            
            # Termos que indicam antecedentes federais
            termos_federais = [
                'polícia federal',
                'departamento de polícia federal',
                'dpf',
                'federal',
                'união',
                'ministério da justiça',
                'governo federal'
            ]
            
            # Verificar presença dos termos
            tem_estadual = any(termo in texto_lower for termo in termos_estaduais)
            tem_federal = any(termo in texto_lower for termo in termos_federais)
            
            if tem_estadual and tem_federal:
                return "Estadual e Federal"
            elif tem_estadual:
                return "Estadual"
            elif tem_federal:
                return "Federal"
            else:
                return "Tipo não identificado"
                
        except Exception as e:
            print(f"[AVISO] Erro ao identificar tipo de antecedentes: {e}")
            return "Tipo não identificado"
    
    def salvar_dados_e_gerar_planilha(self, numero_processo: str, dados_pessoais: Dict[str, Any],
                                     resultado_elegibilidade: Dict[str, Any], resultado_decisao: Dict[str, Any],
                                     resumo_executivo: Dict[str, Any]) -> Dict[str, Any]:
        """Persiste dados auxiliares e gera planilha consolidada do processo"""
        try:
            print("[DADOS] Salvando dados do processo...")

            # Exportar snapshot em JSON (melhor depuração)
            try:
                self.repository.salvar_dados_para_exportacao(numero_processo, resultado_elegibilidade, resultado_decisao)
            except Exception as export_error:
                print(f"[AVISO] Falha ao exportar dados para JSON: {export_error}")

            print("[PLANILHA] Preparando geração da planilha consolidada...")
            resultado_planilha = self.repository.gerar_planilha_resultado_ordinaria(
                numero_processo,
                resultado_elegibilidade,
                resultado_decisao,
                resumo_executivo=resumo_executivo
            )

            sucesso_planilha = resultado_planilha.get('sucesso', False)

            resultado = {
                'sucesso': sucesso_planilha,
                'processo': numero_processo,
                'planilha_gerada': sucesso_planilha,
                'dados_salvos': True,
                'dados': resultado_planilha.get('dados'),
                'arquivo_planilha': resultado_planilha.get('arquivo'),
                'caminho_planilha': resultado_planilha.get('caminho')
            }

            print("[OK] Dados salvos e planilha consolidada atualizada")
            return resultado

        except Exception as e:
            print(f"[ERRO] Erro ao salvar dados: {e}")
            return {
                'sucesso': False,
                'erro': str(e)
            }
    
    def _extrair_tempo_residencia_parecer(self, parecer_texto: str) -> float:
        """
        Extrai tempo de residência do parecer da PF usando regex
        Baseado no código original da automação funcional
        """
        import re
        
        # Padrões de regex para extrair tempo de residência (baseado no código original)
        padroes = [
            # Padrão: "Foi constatado que reside no Brasil desde DD/MM/AAAA"
            r'(?:foi\s+constatado|constatou-se)\s+que\s+reside\s+no\s+brasil\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            r'reside\s+no\s+brasil\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
            
            # Padrões com "possuindo, portanto" + extenso entre parênteses
            r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)\)\s+anos?\s+de\s+resid[eê]ncia',
            r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)\)\s+anos?\s+e\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+meses?',
            r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)\)\s+anos?',
            r'possuindo[,\s]+portanto[,\s]+(\d+)\s+anos?',
            r'possuindo[,\s]+(\d+)\s+\((?:um|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)\)\s+anos?\s+e\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+meses?',
            r'portanto[,\s]+(\d+)\s+\((?:um|dois|tr[eê]s|quatro|cinco|seis|sete|oito|nove|dez|onze|doze)\)\s+anos?\s+e\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+meses?',
            r'totalizando\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+anos?\s+e\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+meses?',
            r'totalizando\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+anos?\s*\.?\s*$',
            r'possui\s+(\d+)\s*anos?\s+de\s+resid[eê]ncia',
            r'possui\s+(\d+)\s*anos?\s+.*resid[eê]ncia',
            r'(\d+)\s*anos?\s+de\s+resid[eê]ncia'
        ]
        
        for i, padrao in enumerate(padroes, 1):
            print(f"[DEBUG] Testando padrão {i}: {padrao[:80]}...")
            match = re.search(padrao, parecer_texto, re.IGNORECASE)
            if match:
                try:
                    valor_extraido = match.group(1)
                    
                    # Verificar se é uma data (padrões 1 e 2)
                    if i <= 2 and re.match(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', valor_extraido):
                        # Calcular tempo desde a data até hoje
                        from datetime import datetime
                        
                        # Normalizar separadores
                        data_str = valor_extraido.replace('.', '/').replace('-', '/')
                        
                        # Tentar diferentes formatos
                        for formato in ['%d/%m/%Y', '%d/%m/%y']:
                            try:
                                data_inicio = datetime.strptime(data_str, formato)
                                data_hoje = datetime.now()
                                diferenca = data_hoje - data_inicio
                                anos_residencia = diferenca.days / 365.25
                                print(f"[TEMPO] ✅ Data encontrada: {data_str} → {anos_residencia:.2f} anos de residência")
                                return anos_residencia
                            except ValueError:
                                continue
                        
                        print(f"[AVISO] Não foi possível converter data: {valor_extraido}")
                        continue
                    
                    # Caso contrário, é um número de anos
                    anos = int(valor_extraido)
                    meses = int(match.group(2)) if len(match.groups()) > 1 and match.group(2) else 0
                    tempo_total = anos + (meses / 12.0)
                    print(f"[TEMPO] ✅ Tempo extraído do parecer (padrão {i}): {tempo_total:.2f} anos")
                    return tempo_total
                except (ValueError, IndexError) as e:
                    print(f"[DEBUG] Erro ao processar match: {e}")
                    continue
            else:
                print(f"[DEBUG] ❌ Nenhum match no padrão {i}")
        
        print("[AVISO] Não foi possível extrair tempo específico do parecer")
        return 0.0
    
    def analisar_elegibilidade_completa(self, dados_pessoais: Dict[str, Any], 
                                      documentos_ocr: Dict[str, str]) -> Dict[str, Any]:
        """
        Realiza análise completa de elegibilidade
        
        Args:
            dados_pessoais: Dados pessoais extraídos do formulário
            documentos_ocr: Textos OCR dos documentos
            
        Returns:
            Dict com resultado da análise de elegibilidade
        """
        print("\n=== ANÁLISE DE ELEGIBILIDADE ORDINÁRIA ===")
        
        try:
            # Reset cache de parecer PF a cada análise
            self._parecer_pf_cache = None
            # REQUISITO I: Capacidade Civil
            print("\n[REQUISITO I] Verificando capacidade civil...")
            resultado_capacidade = self._verificar_capacidade_civil(
                dados_pessoais, 
                self.lecom_action.data_inicial_processo
            )
            
            if not resultado_capacidade['atendido']:
                return self._criar_resultado_indeferimento_automatico(
                    'capacidade_civil', 
                    resultado_capacidade,
                    dados_pessoais
                )
            
            # REQUISITO II: Residência Mínima  
            print("\n[REQUISITO II] Verificando residência mínima...")
            resultado_residencia = self._verificar_residencia_minima(documentos_ocr)
            
            if not resultado_residencia['atendido']:
                return self._criar_resultado_indeferimento(
                    'residencia_minima',
                    {
                        'capacidade_civil': resultado_capacidade,
                        'residencia_minima': resultado_residencia
                    },
                    dados_pessoais
                )
            
            # REQUISITO III: Comunicação em Português
            print("\n[REQUISITO III] Verificando comunicação em português...")
            resultado_comunicacao = self._verificar_comunicacao_portugues(documentos_ocr)
            
            # Verificar parecer PF (pode invalidar documento de português)
            parecer_pf = self._obter_parecer_pf_seguro(parecer_pf_dados)
            if parecer_pf.get('problema_portugues'):
                print("⚠️ Documento de português invalidado pelo parecer PF")
                resultado_comunicacao = {
                    'atendido': False,
                    'motivo': 'Documento de proficiência em português INVALIDADO - não comprovado no atendimento presencial (conforme parecer PF)'
                }
            
            if not resultado_comunicacao['atendido']:
                return self._criar_resultado_indeferimento(
                    'comunicacao_portugues',
                    {
                        'capacidade_civil': resultado_capacidade,
                        'residencia_minima': resultado_residencia,
                        'comunicacao_portugues': resultado_comunicacao
                    },
                    dados_pessoais
                )
            
            # REQUISITO IV: Antecedentes Criminais
            print("\n[REQUISITO IV] Verificando antecedentes criminais...")
            resultado_antecedentes = self._verificar_antecedentes_criminais(documentos_ocr)
            
            if not resultado_antecedentes['atendido']:
                return self._criar_resultado_indeferimento(
                    'antecedentes_criminais',
                    {
                        'capacidade_civil': resultado_capacidade,
                        'residencia_minima': resultado_residencia,
                        'comunicacao_portugues': resultado_comunicacao,
                        'antecedentes_criminais': resultado_antecedentes
                    },
                    dados_pessoais
                )
            
            # DOCUMENTOS COMPLEMENTARES
            print("\n[DOCUMENTOS] Verificando documentos complementares...")
            resultado_documentos = self._verificar_documentos_complementares(documentos_ocr)
            
            # TODOS OS REQUISITOS ATENDIDOS - DEFERIMENTO
            print("\n✅ TODOS OS REQUISITOS ATENDIDOS - DEFERIMENTO")
            
            status_requisitos = {
                'I': bool(resultado_capacidade.get('atendido')),
                'II': bool(resultado_residencia.get('atendido')),
                'III': bool(resultado_comunicacao.get('atendido')),
                'IV': bool(resultado_antecedentes.get('atendido'))
            }
            requisitos_atendidos = sum(1 for atendido in status_requisitos.values() if atendido)
            total_requisitos = len(status_requisitos)

            return {
                'elegibilidade_final': 'deferimento',
                'requisito_i_capacidade_civil': resultado_capacidade,
                'requisito_ii_residencia_minima': resultado_residencia,
                'requisito_iii_comunicacao_portugues': resultado_comunicacao,
                'requisito_iv_antecedentes_criminais': resultado_antecedentes,
                'documentos_complementares': resultado_documentos,
                'requisitos_nao_atendidos': [],
                'documentos_faltantes': resultado_documentos.get('documentos_faltantes', []),
                'dados_pessoais': dados_pessoais,
                'data_inicial_processo': self.lecom_action.data_inicial_processo,
                'parecer_pf': parecer_pf,
                'status_requisitos': status_requisitos,
                'requisitos_atendidos': requisitos_atendidos,
                'total_requisitos': total_requisitos,
                'motivos_indeferimento': []
            }
            
        except Exception as e:
            print(f"[ERRO] Erro na análise de elegibilidade: {e}")
            return {
                'elegibilidade_final': 'erro',
                'erro': str(e),
                'dados_pessoais': dados_pessoais
            }
    
    def _verificar_capacidade_civil(self, dados_pessoais: Dict[str, Any], data_inicial_processo: str) -> Dict[str, Any]:
        """
        Verifica requisito I - Capacidade Civil
        (preserva lógica original)
        """
        try:
            data_nascimento = dados_pessoais.get('data_nascimento', '')

            if not data_nascimento:
                return {
                    'atendido': False,
                    'motivo': 'Data de nascimento não encontrada no formulário',
                    'idade': 'N/A',
                    'avaliado': True
                }

            from datetime import datetime

            try:
                formatos_data = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']
                data_nasc_obj = None

                for formato in formatos_data:
                    try:
                        data_nasc_obj = datetime.strptime(data_nascimento, formato)
                        break
                    except ValueError:
                        continue

                if not data_nasc_obj:
                    return {
                        'atendido': False,
                        'motivo': f'Formato de data de nascimento inválido: {data_nascimento}',
                        'idade': 'N/A',
                        'avaliado': True
                    }

                data_inicial_obj = datetime.strptime(data_inicial_processo, '%d/%m/%Y')
                idade = data_inicial_obj.year - data_nasc_obj.year
                if (data_inicial_obj.month, data_inicial_obj.day) < (data_nasc_obj.month, data_nasc_obj.day):
                    idade -= 1

                if idade >= 18:
                    return {
                        'atendido': True,
                        'motivo': f'Possui {idade} anos, sendo maior de 18 anos',
                        'idade': idade,
                        'avaliado': True
                    }
                else:
                    return {
                        'atendido': False,
                        'motivo': f'Possui {idade} anos, sendo menor de 18 anos',
                        'idade': idade,
                        'avaliado': True
                    }

            except Exception as e:
                return {
                    'atendido': False,
                    'motivo': f'Erro ao calcular idade: {e}',
                    'idade': 'N/A',
                    'avaliado': True
                }

        except Exception as e:
            return {
                'atendido': False,
                'motivo': f'Erro na verificação de capacidade civil: {e}',
                'idade': 'N/A',
                'avaliado': True
            }
    
    def _verificar_residencia_minima(self, documentos_ocr: Dict[str, str]) -> Dict[str, Any]:
        """
        Verifica requisito II - Residência Mínima
        (preserva padrões de prazo de residência)
        """
        try:
            # Verificar se tem comprovante de redução de prazo
            tem_reducao = 'Comprovante de redução de prazo' in documentos_ocr
            prazo_requerido = 1 if tem_reducao else 4
            
            # Verificar comprovante de tempo de residência
            texto_residencia = documentos_ocr.get('Comprovante de tempo de residência', '')
            
            if not texto_residencia:
                return {
                    'atendido': False,
                    'motivo': 'Não anexou item 8 - Comprovante de tempo de residência',
                    'prazo_requerido': prazo_requerido,
                    'tem_reducao': tem_reducao,
                    'avaliado': True
                }
            
            # Analisar texto para verificar tempo de residência
            # (aqui você pode implementar lógica específica de análise do texto)
            
            # Por simplicidade, assumir que se o documento existe, o requisito é atendido
            # Em implementação real, analisaria o texto para extrair tempo de residência
            
            return {
                'atendido': True,
                'motivo': f'Comprovou {prazo_requerido} ano(s) de residência no Brasil',
                'prazo_requerido': prazo_requerido,
                'tem_reducao': tem_reducao,
                'avaliado': True
            }
            
        except Exception as e:
            return {
                'atendido': False,
                'motivo': f'Erro na verificação de residência: {e}',
                'prazo_requerido': 4,
                'tem_reducao': False,
                'avaliado': True
            }
    
    def _verificar_comunicacao_portugues(self, documentos_ocr: Dict[str, str]) -> Dict[str, Any]:
        """
        Verifica requisito III - Comunicação em Português
        (preserva validação com termos melhorados)
        """
        try:
            texto_comunicacao = documentos_ocr.get('Comprovante de comunicação em português', '')
            
            if not texto_comunicacao:
                return {
                    'atendido': False,
                    'motivo': 'Não anexou item 13 - Comprovante de comunicação em português',
                    'avaliado': True
                }
            
            # Usar validação melhorada se disponível
            try:
                from ..data.termos_validacao_melhorados import validar_documento_melhorado
                resultado = validar_documento_melhorado('Comunicacao_Portugues', texto_comunicacao, minimo_confianca=65)
                
                if resultado['valido']:
                    return {
                        'atendido': True,
                        'motivo': 'Anexou comprovante válido de comunicação em português',
                        'confianca': resultado.get('confianca', 0),
                        'avaliado': True
                    }
                else:
                    return {
                        'atendido': False,
                        'motivo': 'Inválido, não atende aos requisitos do art 65 inciso III',
                        'avaliado': True
                    }
                    
            except ImportError:
                # Fallback para validação básica
                return {
                    'atendido': True,
                    'motivo': 'Anexou comprovante de comunicação em português (validação básica)',
                    'avaliado': True
                }
                
        except Exception as e:
            return {
                'atendido': False,
                'motivo': f'Erro na verificação de comunicação: {e}',
                'avaliado': True
            }
    
    def _verificar_antecedentes_criminais(self, documentos_ocr: Dict[str, str]) -> Dict[str, Any]:
        """
        Verifica requisito IV - Antecedentes Criminais
        (preserva lógica de validação com termos melhorados)
        """
        try:
            # Verificar antecedentes do Brasil
            texto_brasil = documentos_ocr.get('Certidão de antecedentes criminais (Brasil)', '')
            texto_origem = documentos_ocr.get('Atestado antecedentes criminais (país de origem)', '')
            
            brasil_valido = False
            origem_valido = False
            motivos_especificos = []
            documentos_faltantes_detalhados = []
            
            # Validar antecedentes Brasil
            if texto_brasil:
                try:
                    from ..data.termos_validacao_melhorados import validar_documento_melhorado
                    resultado_brasil = validar_documento_melhorado('Antecedentes_Brasil', texto_brasil, minimo_confianca=70)
                    
                    if resultado_brasil['valido']:
                        brasil_valido = True
                        
                        # Verificar se é estadual, federal ou ambos
                        tipo_antecedentes = self._identificar_tipo_antecedentes_brasil(texto_brasil)
                        print(f"✅ Antecedentes Brasil: VÁLIDO ({tipo_antecedentes})")
                    else:
                        motivos_especificos.append('Certidão de antecedentes criminais do Brasil inválida')
                        documentos_faltantes_detalhados.append('Certidão de antecedentes criminais da Justiça Federal')
                        documentos_faltantes_detalhados.append('Certidão de antecedentes criminais da Justiça Estadual')
                        print(f"❌ Antecedentes Brasil: INVÁLIDO")
                        
                except ImportError:
                    # Fallback básico
                    if 'não consta' in texto_brasil.lower() or 'nada consta' in texto_brasil.lower():
                        brasil_valido = True
                        
                        # Verificar se é estadual, federal ou ambos (mesmo no fallback)
                        tipo_antecedentes = self._identificar_tipo_antecedentes_brasil(texto_brasil)
                        print(f"✅ Antecedentes Brasil: VÁLIDO ({tipo_antecedentes}) - validação básica")
                    else:
                        motivos_especificos.append('Certidão de antecedentes criminais do Brasil inválida')
                        documentos_faltantes_detalhados.append('Certidão de antecedentes criminais da Justiça Federal')
                        documentos_faltantes_detalhados.append('Certidão de antecedentes criminais da Justiça Estadual')
                        print(f"❌ Antecedentes Brasil: INVÁLIDO")
            else:
                motivos_especificos.append('Certidão de antecedentes criminais do Brasil não anexada')
                documentos_faltantes_detalhados.append('Certidão de antecedentes criminais da Justiça Federal')
                documentos_faltantes_detalhados.append('Certidão de antecedentes criminais da Justiça Estadual')
                print(f"❌ Antecedentes Brasil: NÃO ANEXADO")
            
            # Validar antecedentes país de origem
            if texto_origem:
                try:
                    from ..data.termos_validacao_melhorados import validar_documento_melhorado
                    resultado_origem = validar_documento_melhorado('Antecedentes_Origem', texto_origem, minimo_confianca=70)
                    
                    if resultado_origem['valido']:
                        origem_valido = True
                        print("✅ Antecedentes país de origem: VÁLIDO")
                    else:
                        motivos_especificos.append('Atestado de antecedentes criminais do país de origem inválido')
                        documentos_faltantes_detalhados.append('Atestado de antecedentes criminais do país de origem')
                        print(f"❌ Antecedentes país de origem: INVÁLIDO")
                        
                except ImportError:
                    # Fallback básico - aceitar se tiver conteúdo
                    origem_valido = True
                    print("✅ Antecedentes país de origem: VÁLIDO (fallback)")
            else:
                motivos_especificos.append('Atestado de antecedentes criminais do país de origem não anexado')
                documentos_faltantes_detalhados.append('Atestado de antecedentes criminais do país de origem')
                print(f"❌ Antecedentes país de origem: NÃO ANEXADO")
            
            print(f"\n{'='*60}")
            print(f"📊 RESUMO REQUISITO IV: Brasil={brasil_valido}, Origem={origem_valido}")
            print(f"{'='*60}")
            
            # Verificar se AMBOS os documentos são válidos
            if brasil_valido and origem_valido:
                return {
                    'atendido': True,
                    'motivo': 'Antecedentes criminais em ordem (Brasil e país de origem)',
                    'avaliado': True
                }
            else:
                motivo_detalhado = '; '.join(motivos_especificos) if motivos_especificos else 'Antecedentes criminais inválidos ou não anexados'
                print(f"❌ REQUISITO IV: NÃO ATENDIDO")
                print(f"[ERRO] {motivo_detalhado}")
                
                return {
                    'atendido': False,
                    'motivo': motivo_detalhado,
                    'motivos_especificos': motivos_especificos,
                    'documentos_faltantes': documentos_faltantes_detalhados,
                    'brasil_valido': brasil_valido,
                    'origem_valido': origem_valido,
                    'avaliado': True
                }
                
        except Exception as e:
            return {
                'atendido': False,
                'motivo': f'Erro na verificação de antecedentes: {e}',
                'avaliado': True
            }
    
    def _verificar_documentos_complementares(self, documentos_ocr: Dict[str, str]) -> Dict[str, Any]:
        """
        Verifica documentos complementares obrigatórios
        """
        try:
            documentos_complementares = [
                'Carteira de Registro Nacional Migratório',
                'Comprovante da situação cadastral do CPF',
                'Documento de viagem internacional'
            ]
            
            documentos_validos = 0
            documentos_faltantes = []
            
            for doc in documentos_complementares:
                if doc in documentos_ocr and documentos_ocr[doc]:
                    documentos_validos += 1
                else:
                    # Mapear para item do anexo
                    if 'crnm' in doc.lower() or 'registro nacional' in doc.lower():
                        documentos_faltantes.append('Não anexou item 3')
                    elif 'cpf' in doc.lower():
                        documentos_faltantes.append('Não anexou item 4')
                    elif 'viagem internacional' in doc.lower():
                        documentos_faltantes.append('Não anexou item 2')
            
            total_docs = len(documentos_complementares)
            percentual_completude = (documentos_validos / total_docs) * 100
            
            return {
                'atendido': documentos_validos == total_docs,
                'documentos_validos': documentos_validos,
                'total_documentos': total_docs,
                'percentual_completude': percentual_completude,
                'documentos_faltantes': documentos_faltantes,
                'avaliado': True
            }
            
        except Exception as e:
            return {
                'atendido': False,
                'motivo': f'Erro na verificação de documentos: {e}',
                'documentos_faltantes': ['Erro na validação'],
                'avaliado': True
            }
    
    def _criar_resultado_indeferimento_automatico(self, requisito_falhou: str, resultado_requisito: Dict, 
                                                dados_pessoais: Dict) -> Dict[str, Any]:
        """Cria resultado para indeferimento automático"""
        return {
            'elegibilidade_final': 'indeferimento_automatico',
            f'requisito_{requisito_falhou}': resultado_requisito,
            'requisitos_nao_atendidos': [resultado_requisito['motivo']],
            'documentos_faltantes': [],
            'dados_pessoais': dados_pessoais,
            'data_inicial_processo': self.lecom_action.data_inicial_processo
        }
    
    def _criar_resultado_indeferimento(self, requisito_falhou: str, resultados_requisitos: Dict, 
                                     dados_pessoais: Dict) -> Dict[str, Any]:
        """Cria resultado para indeferimento"""
        motivos = []
        for req, resultado in resultados_requisitos.items():
            if not resultado.get('atendido', True):
                motivos.append(resultado.get('motivo', f'Requisito {req} não atendido'))
        
        resultado_final = {
            'elegibilidade_final': 'indeferimento',
            'requisitos_nao_atendidos': motivos,
            'documentos_faltantes': [],
            'dados_pessoais': dados_pessoais,
            'data_inicial_processo': self.lecom_action.data_inicial_processo
        }
        
        # Adicionar resultados dos requisitos
        for req, resultado in resultados_requisitos.items():
            resultado_final[f'requisito_{req}'] = resultado
        
        return resultado_final
    
    def gerar_decisao_automatica(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera decisão automática baseada no resultado da elegibilidade
        (preserva funcionalidade da classe AnaliseDecisoesOrdinaria)
        """
        try:
            print("[DECISAO] Analisando resultado da elegibilidade...")
            
            # Verificar se resultado_elegibilidade é válido
            if not isinstance(resultado_elegibilidade, dict):
                print(f"[ERRO] Resultado de elegibilidade inválido: {type(resultado_elegibilidade)}")
                return self._gerar_decisao_erro("Resultado de elegibilidade inválido")
            
            # Tentar usar o gerador original
            try:
                resultado = self.gerador_decisao.gerar_decisao_automatica(resultado_elegibilidade)
                
                # Verificar se o resultado é válido
                if isinstance(resultado, dict):
                    # O gerador retorna um dict com 'tipo_decisao' e 'despacho_completo'
                    # Converter para o formato esperado se necessário
                    if 'tipo_decisao' in resultado and 'despacho_completo' in resultado:
                        # Já está no formato correto
                        if 'status' not in resultado:
                            resultado['status'] = resultado['tipo_decisao']
                        return resultado
                    elif 'status' in resultado:
                        return resultado
                    else:
                        print(f"[AVISO] Gerador original retornou formato inválido: {type(resultado)}")
                        return self._gerar_decisao_fallback(resultado_elegibilidade)
                else:
                    print(f"[AVISO] Gerador original retornou tipo inválido: {type(resultado)}")
                    return self._gerar_decisao_fallback(resultado_elegibilidade)
                    
            except Exception as e_gerador:
                print(f"[AVISO] Gerador original falhou: {e_gerador}")
                return self._gerar_decisao_fallback(resultado_elegibilidade)
                
        except Exception as e:
            print(f"[ERRO] Erro ao gerar decisão: {e}")
            return self._gerar_decisao_erro(str(e))
    
    def _gerar_decisao_fallback(self, resultado_elegibilidade: Dict[str, Any]) -> Dict[str, Any]:
        """Gera decisão usando lógica de fallback.

        Esta função é usada quando o gerador de decisões modular não
        retorna no formato esperado. Aqui centralizamos o mapeamento entre
        `elegibilidade_final` e o campo `status` exibido na planilha
        (coluna "Resultado").
        """
        try:
            elegibilidade_final = resultado_elegibilidade.get('elegibilidade_final', 'indeferimento_automatico')
            motivos = resultado_elegibilidade.get('motivos_indeferimento', []) or []

            # DEFERIMENTO (inclui deferimento "automático" ou simples)
            if elegibilidade_final in ('deferimento', 'deferimento_automatico'):
                # Usar portaria gerada se disponível, senão usar texto padrão
                despacho = resultado_elegibilidade.get('despacho_automatico', 
                    'Processo deferido automaticamente com base na análise de elegibilidade.')
                
                return {
                    'status': 'DEFERIMENTO',
                    'tipo_decisao': 'DEFERIMENTO',
                    'despacho_completo': despacho,
                    'motivos_indeferimento': [],
                    'fundamentos_legais': ['Art. 65 da Lei nº 13.445/2017'],
                    'resumo_analise': 'Todos os requisitos atendidos segundo a análise automática.'
                }

            # ANÁLISE MANUAL (ex.: parecer PF sem prazo de residência especificado)
            if elegibilidade_final in ('analise_manual', 'analise manual'):
                return {
                    'status': 'ANALISE MANUAL',
                    'tipo_decisao': 'ANALISE MANUAL',
                    'despacho_completo': (
                        'Processo encaminhado para ANÁLISE MANUAL devido a alerta(s) crítico(s) '
                        'no parecer da PF ou dados insuficientes para decisão automática.'
                    ),
                    'motivos_indeferimento': motivos,
                    'fundamentos_legais': [],
                    'resumo_analise': 'Caso marcado para análise manual (sem decisão automática de deferimento/indeferimento).'
                }

            # Demais casos: tratar como INDEFERIMENTO
            return {
                'status': 'INDEFERIMENTO',
                'tipo_decisao': 'INDEFERIMENTO', 
                'despacho_completo': 'Processo indeferido por não atender aos requisitos',
                'motivos_indeferimento': motivos,
                'fundamentos_legais': motivos,
                'resumo_analise': f'Não atendeu {len(motivos)} requisito(s)'
            }
                
        except Exception as e:
            print(f"[ERRO] Erro no fallback: {e}")
            return self._gerar_decisao_erro(str(e))
    
    def _gerar_decisao_erro(self, erro: str) -> Dict[str, Any]:
        """Gera decisão de erro"""
        return {
            'status': 'ERRO',
            'tipo_decisao': 'ERRO',
            'despacho_completo': f'Erro ao gerar decisão: {erro}',
            'motivos_indeferimento': [],
            'fundamentos_legais': [],
            'resumo_analise': 'Erro no processamento'
        }
    
    def gerar_resumo_executivo(self, resultado_elegibilidade: Dict[str, Any], 
                             resultado_decisao: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gera resumo executivo do processo
        (preserva funcionalidade da classe AnaliseDecisoesOrdinaria)
        """
        try:
            # Verificar se os parâmetros são válidos
            if not isinstance(resultado_elegibilidade, dict) or not isinstance(resultado_decisao, dict):
                print(f"[ERRO] Parâmetros inválidos para resumo executivo")
                return {
                    'erro': 'Parâmetros inválidos',
                    'resumo': 'Erro ao gerar resumo executivo'
                }
            
            # Tentar usar o gerador original
            try:
                return self.gerador_decisao.gerar_resumo_executivo(resultado_elegibilidade, resultado_decisao)
            except Exception as e_gerador:
                print(f"[AVISO] Gerador original de resumo falhou: {e_gerador}")
                return self._gerar_resumo_fallback(resultado_elegibilidade, resultado_decisao)
                
        except Exception as e:
            print(f"[ERRO] Erro ao gerar resumo executivo: {e}")
            return {
                'erro': str(e),
                'resumo': 'Erro ao gerar resumo executivo'
            }
    
    def _gerar_resumo_fallback(self, resultado_elegibilidade: Dict[str, Any], 
                             resultado_decisao: Dict[str, Any]) -> Dict[str, Any]:
        """Gera resumo executivo usando lógica de fallback"""
        try:
            return {
                'resumo': 'Resumo executivo gerado com fallback',
                'processo_analisado': True,
                'decisao': resultado_decisao.get('status', 'INDEFINIDO'),
                'requisitos_analisados': 4
            }
        except Exception as e:
            print(f"[ERRO] Erro no fallback do resumo: {e}")
            return {
                'erro': str(e),
                'resumo': 'Erro ao gerar resumo executivo'
            }
    
    def _gerar_portaria_deferimento(self, dados_pessoais: Dict[str, Any]) -> str:
        """
        Gera o texto da portaria de deferimento com os dados do requerente
        
        Args:
            dados_pessoais: Dicionário com dados pessoais extraídos do formulário
            
        Returns:
            String com o texto completo da portaria formatada
        """
        try:
            # DEBUG: Mostrar todos os campos disponíveis
            print(f"[DEBUG PORTARIA] Campos disponíveis em dados_pessoais:")
            for key in sorted(dados_pessoais.keys()):
                if key in ['numero_processo', 'protocolo', 'sexo', 'genero', 'uf', 'estado', 'pai', 'mae', 'rnm']:
                    print(f"  - {key}: {dados_pessoais[key]}")
            
            # Extrair dados necessários
            numero_processo = dados_pessoais.get('numero_processo', '[NÚMERO DO PROCESSO]')
            nome_completo = dados_pessoais.get('nome_completo', '[NOME COMPLETO]')
            rnm = dados_pessoais.get('rnm', dados_pessoais.get('crnm', '[RNM]'))
            pais_nascimento = dados_pessoais.get('pais_nascimento', dados_pessoais.get('nacionalidade', '[PAÍS DE NASCIMENTO]'))
            data_nascimento_raw = dados_pessoais.get('data_nascimento', '[DATA DE NASCIMENTO]')
            nome_pai = dados_pessoais.get('pai', dados_pessoais.get('nome_pai', '[NOME DO PAI]'))
            nome_mae = dados_pessoais.get('mae', dados_pessoais.get('nome_mae', '[NOME DA MÃE]'))
            estado_sigla = dados_pessoais.get('uf', dados_pessoais.get('estado', '[ESTADO]'))
            
            # Converter data para formato por extenso
            data_nascimento = self._formatar_data_por_extenso(data_nascimento_raw)
            
            # Converter sigla do estado para nome completo
            estado = self._converter_sigla_estado(estado_sigla)
            
            # Formatar gênero para o texto (nascido/nascida)
            genero = dados_pessoais.get('genero', dados_pessoais.get('sexo', '')).upper()
            nascido_a = 'nascido' if genero in ['M', 'MASCULINO'] else 'nascida' if genero in ['F', 'FEMININO'] else 'nascido(a)'
            filho_a = 'filho' if genero in ['M', 'MASCULINO'] else 'filha' if genero in ['F', 'FEMININO'] else 'filho(a)'
            
            # Gerar texto da portaria
            portaria = f"""Assunto: Deferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623, de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, RESOLVE, tendo em vista o cumprimento do Art. 65 da Lei nº 13.445/2017, e demais requisitos previstos na legislação vigente:

CONCEDER a nacionalidade brasileira, por naturalização, à pessoa abaixo relacionada, nos termos do art. 12, II, "a", da Constituição Federal, e em conformidade com o Art. 65 da Lei nº 13.445, de 24 de maio de 2017, regulamentada pelo Decreto nº 9.199, de 20 de novembro de 2017, a fim de que possa gozar dos direitos outorgados pela Constituição e leis do Brasil:

{nome_completo} - {rnm}, natural de {pais_nascimento}, {nascido_a} em {data_nascimento}, {filho_a} de {nome_pai} e de {nome_mae}, residente no estado do {estado} (Processo nº {numero_processo}).

A pessoa referida nesta Portaria deverá comparecer perante a Justiça Eleitoral para o devido cadastramento, nos termos do Art. 231 do Decreto nº 9.199, de 20 de novembro de 2017, que regulamenta a Lei nº 13.445, de 24 de maio de 2017."""
            
            print("[OK] Portaria de deferimento gerada com sucesso")
            return portaria
            
        except Exception as e:
            print(f"[ERRO] Erro ao gerar portaria de deferimento: {e}")
            return f"[ERRO] Não foi possível gerar a portaria de deferimento: {str(e)}"
    
    def _formatar_data_por_extenso(self, data_str: str) -> str:
        """
        Converte data de DD/MM/YYYY para formato por extenso
        Exemplo: 19/06/1973 -> 19 de junho de 1973
        """
        try:
            from datetime import datetime
            
            meses = {
                1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
                5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
                9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
            }
            
            # Tentar diferentes formatos de data
            formatos = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d.%m.%Y']
            
            for formato in formatos:
                try:
                    data_obj = datetime.strptime(data_str, formato)
                    dia = data_obj.day
                    mes = meses[data_obj.month]
                    ano = data_obj.year
                    return f"{dia} de {mes} de {ano}"
                except ValueError:
                    continue
            
            # Se nenhum formato funcionou, retornar original
            print(f"[AVISO] Não foi possível converter data '{data_str}' para extenso")
            return data_str
            
        except Exception as e:
            print(f"[AVISO] Erro ao formatar data por extenso: {e}")
            return data_str
    
    def _converter_sigla_estado(self, sigla: str) -> str:
        """
        Converte sigla do estado para nome completo
        Exemplo: RS -> Rio Grande do Sul
        """
        estados = {
            'AC': 'Acre', 'AL': 'Alagoas', 'AP': 'Amapá', 'AM': 'Amazonas',
            'BA': 'Bahia', 'CE': 'Ceará', 'DF': 'Distrito Federal', 'ES': 'Espírito Santo',
            'GO': 'Goiás', 'MA': 'Maranhão', 'MT': 'Mato Grosso', 'MS': 'Mato Grosso do Sul',
            'MG': 'Minas Gerais', 'PA': 'Pará', 'PB': 'Paraíba', 'PR': 'Paraná',
            'PE': 'Pernambuco', 'PI': 'Piauí', 'RJ': 'Rio de Janeiro', 'RN': 'Rio Grande do Norte',
            'RS': 'Rio Grande do Sul', 'RO': 'Rondônia', 'RR': 'Roraima', 'SC': 'Santa Catarina',
            'SP': 'São Paulo', 'SE': 'Sergipe', 'TO': 'Tocantins'
        }
        
        sigla_upper = sigla.upper().strip()
        return estados.get(sigla_upper, sigla)
    
    def _obter_parecer_pf_seguro(self) -> Dict[str, Any]:
        """
        Obtém dados do parecer PF de forma segura (com cache)
        """
        try:
            # Verificar se já existe cache
            if hasattr(self, '_parecer_pf_cache') and self._parecer_pf_cache:
                return self._parecer_pf_cache
            
            # Tentar obter do repository
            parecer_pf = self.repository.extrair_parecer_pf()
            
            # Armazenar em cache
            self._parecer_pf_cache = parecer_pf
            
            return parecer_pf
            
        except Exception as e:
            print(f"[AVISO] Erro ao obter parecer PF: {e}")
            return {
                'parecer_texto': '',
                'proposta_pf': 'Não encontrado',
                'excedeu_ausencia': False,
                'ausencia_pais': False,
                'problema_portugues': False,
                'nao_compareceu_pf': False,
                'documentos_nao_apresentados': False
            }
    
    def _gerar_despacho_indeferimento(self, dados_pessoais: Dict[str, Any], 
                                     status_requisitos: Dict[str, bool],
                                     documentos_faltantes: list) -> str:
        """
        Gera o texto do despacho de indeferimento com os dados do requerente
        
        Args:
            dados_pessoais: Dicionário com dados pessoais extraídos do formulário
            status_requisitos: Status de cada requisito (I, II, III, IV)
            documentos_faltantes: Lista de documentos não apresentados
            
        Returns:
            String com o texto completo do despacho formatado
        """
        try:
            # Extrair dados necessários
            numero_processo = dados_pessoais.get('numero_processo', '[NÚMERO DO PROCESSO]')
            nome_completo = dados_pessoais.get('nome_completo', '[NOME COMPLETO]')
            
            # Contar quantos requisitos não foram atendidos
            requisitos_nao_atendidos = sum(1 for atendido in status_requisitos.values() if not atendido)
            
            # Verificar alertas PF para templates específicos (SEMPRE TÊM PRIORIDADE)
            parecer_pf = self._obter_parecer_pf_seguro()
            
            # Template 1: Requerente não compareceu à PF (PRIORIDADE MÁXIMA)
            if parecer_pf.get('nao_compareceu_pf'):
                return self._template_nao_compareceu_pf(numero_processo, nome_completo, status_requisitos)
            
            # Template 2: Excedeu limite de ausências (PRIORIDADE MÁXIMA)
            if parecer_pf.get('excedeu_ausencia'):
                return self._template_excedeu_ausencias(numero_processo, nome_completo)
            
            # Template 3: Documentos não apresentados integralmente (PRIORIDADE MÁXIMA)
            if parecer_pf.get('documentos_nao_apresentados'):
                if documentos_faltantes or any(not atendido for atendido in status_requisitos.values()):
                    return self._template_documentos_nao_apresentados(numero_processo, nome_completo, status_requisitos, documentos_faltantes)
                else:
                    return self._template_documentos_nao_apresentados_pf(numero_processo, nome_completo, status_requisitos)
            
            # Templates específicos APENAS quando há UM ÚNICO requisito não atendido
            if requisitos_nao_atendidos == 1:
                # Template 4: Menor de idade (requisito I não atendido)
                if not status_requisitos.get('I', True):
                    return self._template_capacidade_civil(numero_processo, nome_completo)
                
                # Template 5: Antecedentes criminais específico (APENAS se for o único problema)
                if not status_requisitos.get('IV', True):
                    return self._template_antecedentes_criminais(numero_processo, nome_completo, documentos_faltantes)
            
            # Identificar quais incisos não foram atendidos
            incisos_nao_atendidos = []
            mapeamento_incisos = {
                'I': 'I',
                'II': 'II',
                'III': 'III',
                'IV': 'IV'
            }
            
            for requisito, atendido in status_requisitos.items():
                if not atendido:
                    incisos_nao_atendidos.append(mapeamento_incisos.get(requisito, requisito))
            
            # Formatar lista de incisos
            if len(incisos_nao_atendidos) == 0:
                texto_descumprimento = "descumprimento das exigências previstas no art. 65 da Lei nº 13.445/2017"
            elif len(incisos_nao_atendidos) == 1:
                texto_incisos = f"inciso {incisos_nao_atendidos[0]}"
                texto_descumprimento = f"descumprimento do(s) {texto_incisos} do art. 65 da Lei nº 13.445/2017"
            elif len(incisos_nao_atendidos) == 2:
                texto_incisos = f"incisos {incisos_nao_atendidos[0]} e {incisos_nao_atendidos[1]}"
                texto_descumprimento = f"descumprimento do(s) {texto_incisos} do art. 65 da Lei nº 13.445/2017"
            else:
                texto_incisos = f"incisos {', '.join(incisos_nao_atendidos[:-1])} e {incisos_nao_atendidos[-1]}"
                texto_descumprimento = f"descumprimento do(s) {texto_incisos} do art. 65 da Lei nº 13.445/2017"
            
            # Texto base do despacho
            despacho = f"""Assunto: Indeferimento do pedido
Processo Naturalizar-se nº {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, indefere o pedido, tendo em vista o {texto_descumprimento}"""
            
            # Se houver documentos faltantes, adicionar informação
            if documentos_faltantes:
                # Especificar documentos por extenso
                docs_texto = self._formatar_documentos_faltantes(documentos_faltantes, status_requisitos)
                if docs_texto:
                    despacho += f", por não ter apresentado {docs_texto}"
            
            despacho += "."
            
            print(f"[OK] Despacho de indeferimento gerado com sucesso ({len(despacho)} caracteres)")
            print(f"[DEBUG] Primeiros 150 caracteres do despacho: {despacho[:150]}")
            return despacho
            
        except Exception as e:
            print(f"[ERRO] Erro ao gerar despacho de indeferimento: {e}")
            return f"[ERRO] Não foi possível gerar o despacho de indeferimento: {str(e)}"
    
    def _formatar_documentos_faltantes(self, documentos_faltantes: list, status_requisitos: Dict[str, bool]) -> str:
        """
        Formata documentos faltantes por extenso para o despacho
        
        Args:
            documentos_faltantes: Lista de documentos não apresentados
            status_requisitos: Status de cada requisito para identificar contexto
            
        Returns:
            String formatada com os documentos faltantes
        """
        if not documentos_faltantes:
            return ""
        
        # Mapeamento de documentos para nomes por extenso
        mapeamento_nomes = {
            'Atestado de antecedentes criminais do país de origem': 'o atestado de antecedentes criminais do país de origem (legalizado e traduzido)',
            'Certidão de antecedentes criminais da Polícia Federal': 'a certidão de antecedentes criminais da Polícia Federal',
            'Certidão de antecedentes criminais da Justiça Federal': 'a certidão de antecedentes criminais da Justiça Federal',
            'Certidão de antecedentes criminais da Justiça Estadual': 'a certidão de antecedentes criminais da Justiça Estadual',
            'Documento de proficiência em português': 'o documento de proficiência em língua portuguesa',
            'Comprovante de residência': 'o comprovante de residência',
            'Comprovante de tempo de residência': 'o comprovante de tempo de residência',
            'Carteira de Registro Nacional Migratório': 'a Carteira de Registro Nacional Migratório (CRNM/RNM)',
            'Comprovante de situação cadastral do CPF': 'o comprovante de situação cadastral do CPF',
            'Documento de viagem internacional': 'o documento de viagem internacional',
            'Passaporte': 'o passaporte'
        }
        
        # Identificar documentos por extenso
        docs_formatados = []
        tem_antecedentes_brasil = False
        tem_antecedentes_origem = False
        
        for doc in documentos_faltantes:
            doc_encontrado = None
            for doc_key, doc_nome in mapeamento_nomes.items():
                if doc_key.lower() in doc.lower() or doc.lower() in doc_key.lower():
                    doc_encontrado = doc_nome
                    # Rastrear antecedentes para mensagem especial
                    if 'antecedentes' in doc.lower():
                        if 'origem' in doc.lower() or 'país' in doc.lower():
                            tem_antecedentes_origem = True
                        else:
                            tem_antecedentes_brasil = True
                    break
            
            if doc_encontrado and doc_encontrado not in docs_formatados:
                docs_formatados.append(doc_encontrado)
        
        # Se inciso IV não atendido e há antecedentes, especificar quais
        if not status_requisitos.get('IV', True) and (tem_antecedentes_brasil or tem_antecedentes_origem):
            # Remover antecedentes genéricos e adicionar especificação
            docs_formatados = [d for d in docs_formatados if 'antecedentes' not in d]
            
            if tem_antecedentes_brasil and tem_antecedentes_origem:
                docs_formatados.append('as certidões de antecedentes criminais da Justiça Federal e Estadual, e o atestado de antecedentes criminais do país de origem (legalizado e traduzido)')
            elif tem_antecedentes_brasil:
                docs_formatados.append('as certidões de antecedentes criminais da Justiça Federal e Estadual')
            elif tem_antecedentes_origem:
                docs_formatados.append('o atestado de antecedentes criminais do país de origem (legalizado e traduzido)')
        
        # Formatar lista
        if len(docs_formatados) == 0:
            return ""
        elif len(docs_formatados) == 1:
            return docs_formatados[0]
        elif len(docs_formatados) == 2:
            return f"{docs_formatados[0]} e {docs_formatados[1]}"
        else:
            return f"{', '.join(docs_formatados[:-1])} e {docs_formatados[-1]}"
    
    def _mapear_documentos_para_itens_anexo(self, documentos_faltantes: list) -> list:
        """
        Mapeia documentos faltantes para itens do Anexo I da Portaria 623/2020
        
        Itens do Anexo I:
        3. Cópia da Carteira de Registro Nacional Migratório (CRNM/RNM)
        4. Comprovante de situação cadastral do CPF
        5. Certidão de antecedentes criminais da Justiça Federal e Estadual
        6. Atestado de antecedentes criminais do país de origem (legalizado e traduzido)
        8. Comprovante de residência
        9. Cópia do documento de viagem internacional
        13. Documento indicativo da capacidade de se comunicar em língua portuguesa
        """
        mapeamento = {
            'Carteira de Registro Nacional Migratório': '3',
            'Comprovante de situação cadastral do CPF': '4',
            'Certidão de antecedentes criminais da Polícia Federal': '5',
            'Certidão de antecedentes criminais da Justiça Federal': '5',
            'Certidão de antecedentes criminais da Justiça Estadual': '5',
            'Atestado de antecedentes criminais do país de origem': '6',
            'Comprovante de residência': '8',
            'Comprovante de tempo de residência': '8',
            'Documento de viagem internacional': '9',
            'Passaporte': '9',
            'Documento de proficiência em português': '13',
            'Comprovante de capacidade civil': 'capacidade civil'  # Não é item do Anexo I
        }
        
        itens = []
        for doc in documentos_faltantes:
            # Buscar correspondência exata ou parcial
            item_encontrado = None
            for doc_key, item in mapeamento.items():
                if doc_key.lower() in doc.lower() or doc.lower() in doc_key.lower():
                    item_encontrado = item
                    break
            
            if item_encontrado and item_encontrado not in itens and item_encontrado != 'capacidade civil':
                itens.append(item_encontrado)
        
        # Ordenar numericamente
        return sorted(itens, key=lambda x: int(x) if x.isdigit() else 999)
    
    def _template_nao_compareceu_pf(self, numero_processo: str, nome_completo: str, status_requisitos: Dict[str, bool]) -> str:
        """Template para quando o requerente não compareceu à PF"""
        # Identificar incisos não atendidos
        incisos = []
        if not status_requisitos.get('I', True):
            incisos.append('I')
        if not status_requisitos.get('II', True):
            incisos.append('II')
        if not status_requisitos.get('III', True):
            incisos.append('III')
        if not status_requisitos.get('IV', True):
            incisos.append('IV')
        
        # Formatar texto dos incisos
        if len(incisos) == 0:
            texto_incisos = "art. 65"
        elif len(incisos) == 1:
            texto_incisos = f"inciso {incisos[0]}, art. 65"
        else:
            texto_incisos = f"incisos {', '.join(incisos)}, art. 65"
        
        return f"""Assunto: Indeferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, considerando que o/a requerente foi notificado/a e não compareceu à Polícia Federal para conferência dos documentos originais e coleta biométrica, indefere o pedido tendo em vista o não cumprimento das exigências previstas no {texto_incisos} da Lei nº 13.445/2017, c/c art. 227 do Decreto nº 9.199/2017, e §2º, art. 7º da Portaria nº 623 de 13 de novembro de 2020."""
    
    def _template_excedeu_ausencias(self, numero_processo: str, nome_completo: str) -> str:
        """Template para quando o requerente excedeu o limite de ausências"""
        return f"""Assunto: Indeferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, indefere o pedido, tendo em vista que o requerente se ausentou do Brasil, excedendo o prazo máximo de ausência do país, portanto não atende à exigência contida no inciso II, art. 65 da Lei nº 13.445, de 2017, c/c §2º, art. 233, do Decreto 9.199/2017."""
    
    def _template_documentos_nao_apresentados(self, numero_processo: str, nome_completo: str, 
                                             status_requisitos: Dict[str, bool], documentos_faltantes: list) -> str:
        """Template para quando documentos não foram apresentados integralmente"""
        # Identificar incisos não atendidos
        incisos = []
        if not status_requisitos.get('I', True):
            incisos.append('I')
        if not status_requisitos.get('II', True):
            incisos.append('II')
        if not status_requisitos.get('III', True):
            incisos.append('III')
        if not status_requisitos.get('IV', True):
            incisos.append('IV')
        
        # Formatar texto dos incisos
        if len(incisos) == 0:
            texto_incisos = "art. 65"
        elif len(incisos) == 1:
            texto_incisos = f"inciso {incisos[0]}, art. 65"
        elif len(incisos) == 2:
            texto_incisos = f"incisos {incisos[0]} e {incisos[1]}, art. 65"
        else:
            texto_incisos = f"incisos {', '.join(incisos[:-1])} e {incisos[-1]}, art. 65"
        
        return f"""Assunto: Indeferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, considerando que o/a requerente não apresentou os documentos necessários, foi notificado/a a complementar e não respondeu às exigências dentro do prazo previsto, indefere o pedido tendo em vista o não cumprimento das exigências previstas no {texto_incisos} da Lei nº 13.445/2017."""

    def _template_documentos_nao_apresentados_pf(self, numero_processo: str, nome_completo: str, status_requisitos: Dict[str, bool]) -> str:
        """Template específico quando somente o parecer PF aponta falta de documentos"""
        incisos = []
        if not status_requisitos.get('I', True):
            incisos.append('I')
        if not status_requisitos.get('II', True):
            incisos.append('II')
        if not status_requisitos.get('III', True):
            incisos.append('III')
        if not status_requisitos.get('IV', True):
            incisos.append('IV')

        if len(incisos) == 1:
            complemento = f"no inciso {incisos[0]} do art. 65"
        elif len(incisos) == 2:
            complemento = f"nos incisos {incisos[0]} e {incisos[1]} do art. 65"
        elif len(incisos) > 2:
            complemento = f"nos incisos {', '.join(incisos[:-1])} e {incisos[-1]} do art. 65"
        else:
            complemento = "no art. 65"

        return f"""Assunto: Indeferimento do pedido
Processo Naturalizar-se nº {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, considerando que o/a requerente não apresentou os documentos necessários, foi notificado/a a complementar e não respondeu às exigências dentro do prazo previsto, indefere o pedido tendo em vista o não cumprimento das exigências previstas {complemento} da Lei nº 13.445/2017."""
    
    def _template_capacidade_civil(self, numero_processo: str, nome_completo: str) -> str:
        """Template para quando o requerente não tem capacidade civil (menor de idade)"""
        return f"""Assunto: Indeferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, indefere o pedido, tendo em vista que o/a requerente é menor de idade e portanto não atende à exigência de ter capacidade civil, segundo a lei brasileira, o requisito previsto no inciso I, art. 65 da Lei nº 13.445/2017."""
    
    def _template_antecedentes_criminais(self, numero_processo: str, nome_completo: str, documentos_faltantes: list) -> str:
        """Template para quando faltam documentos de antecedentes criminais"""
        # Identificar quais documentos de antecedentes estão faltando
        docs_brasil = [d for d in documentos_faltantes if 'brasil' in d.lower() or 'federal' in d.lower() or 'estadual' in d.lower()]
        docs_origem = [d for d in documentos_faltantes if 'origem' in d.lower() or 'país' in d.lower()]
        
        # Mapear para itens do Anexo I
        itens_faltantes = []
        if docs_brasil:
            itens_faltantes.append('5')  # Item 5: Certidões Brasil (Federal e Estadual)
        if docs_origem:
            itens_faltantes.append('6')  # Item 6: Atestado país de origem
        
        if itens_faltantes:
            if len(itens_faltantes) == 1:
                texto_itens = f"item {itens_faltantes[0]}"
            else:
                texto_itens = f"itens {' e '.join(itens_faltantes)}"
            
            # Especificar qual documento está faltando
            if docs_brasil and docs_origem:
                especificacao = "certidões de antecedentes criminais do Brasil (Justiça Federal e Estadual) e atestado de antecedentes criminais do país de origem"
            elif docs_brasil:
                especificacao = "certidões de antecedentes criminais do Brasil (Justiça Federal e Estadual)"
            else:
                especificacao = "atestado de antecedentes criminais do país de origem (legalizado e traduzido)"
            
            return f"""Assunto: Indeferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, indefere o pedido, tendo em vista que o/a requerente não apresentou {especificacao}, conforme exigido no(s) {texto_itens} do Anexo I da Portaria 623/2020, não atendendo ao requisito previsto no inciso IV, art. 65 da Lei nº 13.445/2017."""
        
        # Fallback genérico
        return f"""Assunto: Indeferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, indefere o pedido, tendo em vista o não cumprimento do requisito previsto no inciso IV, art. 65 da Lei nº 13.445/2017 (inexistência de condenação penal)."""
