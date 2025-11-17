"""
RecursoProcessor (Automação)
Orquestra o fluxo de Aprovação do Conteúdo de Recurso: navegação, leitura DNNR, decisão e confirmação.
"""
import logging
import time
from typing import Dict
from automation.actions.lecom_recurso_action import LecomRecursoAction
from automation.repositories.recurso_repository import RecursoRepository
from automation.services.recurso_service import RecursoService

logger = logging.getLogger(__name__)


class RecursoProcessor:
    def __init__(self, driver):
        self.lecom = LecomRecursoAction(driver)
        self.repo = RecursoRepository()
        self.service = RecursoService()

    def processar_codigo(self, codigo: str) -> Dict:
        """Processa um único código e retorna dict compatível com o arquivo original."""
        resultado = {
            'codigo': codigo,
            'decisao': None,
            'status': 'erro',
            'erro': None
        }
        try:
            if not self.lecom.navegar_para_processo(codigo):
                resultado['erro'] = 'Falha ao navegar para processo'
                return resultado
            if not self.lecom.selecionar_atividade_aprovacao_conteudo():
                resultado['erro'] = 'Atividade não encontrada'
                return resultado
            if not self.lecom.abrir_form_iframe():
                resultado['erro'] = 'Falha ao abrir form-app'
                return resultado
            valor = self.lecom.ler_valor_dnnr()
            logger.info(f"[DNNR] Valor: {valor}")
            decisao = self.service.decidir_por_dnnr(valor)
            if not decisao:
                resultado['erro'] = 'Valor DNNR não mapeado'
                return resultado
            ok = self.lecom.aplicar_decisao(decisao)
            if not ok:
                resultado['erro'] = 'Falha ao aplicar decisão'
                return resultado
            # aguardar confirmação
            if not self.lecom.aguardar_confirmacao(timeout=30):
                logger.warning('[AVISO] Confirmação não detectada – tentando voltar para workspace')
                self.lecom.voltar_workspace()
            resultado['decisao'] = decisao
            resultado['valor_dnnr'] = valor
            resultado['status'] = 'sucesso'
            time.sleep(1.5)
            return resultado
        except Exception as e:
            resultado['erro'] = str(e)
            return resultado

    def ler_codigos_planilha(self, caminho_planilha: str, nome_coluna: str = 'codigo') -> list[str]:
        return self.repo.ler_planilha_codigos(caminho_planilha, nome_coluna)
