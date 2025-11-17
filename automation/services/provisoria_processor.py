"""
ProvisoriaProcessor (Automação)
Orquestra navegação + extração de dados + download/OCR + avaliação de elegibilidade
para Naturalização Provisória, reaproveitando o código original via loader dinâmico.
"""
from typing import Dict, Any
import re

from automation.actions.provisoria_action import ProvisoriaAction
from automation.services.provisoria_service import ProvisoriaService


class ProvisoriaProcessor:
    def __init__(self, driver):
        self.lecom = ProvisoriaAction(driver)
        self.service = ProvisoriaService()

    def _digits(self, s: str) -> str:
        return re.sub(r"\D", "", s or "")

    def _mapear_textos_documentos(self, resultados_docs: Dict[str, Any]) -> Dict[str, str]:
        textos: Dict[str, str] = {}
        for nome, dados in (resultados_docs or {}).items():
            try:
                txt = (dados or {}).get('texto_extraido')
                if isinstance(txt, str):
                    textos[nome] = txt
                else:
                    textos[nome] = ''
            except Exception:
                textos[nome] = ''
        return textos

    def processar_codigo(self, codigo: str) -> Dict[str, Any]:
        resultado = {
            'codigo': codigo,
            'status': 'erro',
            'erro': '',
            'analise_elegibilidade': {},
            'documentos_processados': [],
            'total_documentos': 0,
        }
        try:
            # 1) Garantir LOGIN no LECOM (evita ficar em data:, página em branco)
            try:
                if not getattr(self.lecom, 'ja_logado', False):
                    ok_login = self.lecom.login()
                    if not ok_login:
                        resultado['erro'] = 'Falha no login no LECOM'
                        return resultado
            except Exception as e_login:
                resultado['erro'] = f'Falha no login: {e_login}'
                return resultado

            # 2) Navegar para o processo (aplicar filtros)
            try:
                ok_nav = self.lecom.aplicar_filtros(codigo)
                if not ok_nav:
                    resultado['erro'] = 'Falha na navegação para o processo'
                    return resultado
            except Exception as e_nav:
                resultado['erro'] = f'Falha na navegação: {e_nav}'
                return resultado

            # 3) Fluxo (placeholder): tentar pipeline completo caso disponível
            try:
                res_full = self.service.analisar_fluxo_completo(self.lecom, codigo) or {}
            except Exception:
                # Fallback básico: extrair dados e avaliar se possível
                try:
                    dados = self.lecom.extrair_dados_pessoais_formulario() or {}
                    data_ref = getattr(self.lecom, 'data_inicial_processo', None)
                    res_full = self.service.avaliar(self.lecom, dados, data_ref) or {}
                except Exception as e_eval:
                    resultado['erro'] = f'Falha na avaliação: {e_eval}'
                    return resultado

            # 4) Normalizar saída
            resultado['analise_elegibilidade'] = res_full.get('analise_elegibilidade') or res_full
            resultado['status'] = 'sucesso' if (res_full.get('status') or '').lower() not in ('erro', 'timeout') else 'erro'
            resultado['erro'] = res_full.get('erro', '')
            resultado['total_documentos'] = res_full.get('total_documentos', 0)
            if 'documentos_processados' in res_full:
                resultado['documentos_processados'] = res_full.get('documentos_processados')
            return resultado
        except Exception as e:
            resultado['erro'] = str(e)
            return resultado
