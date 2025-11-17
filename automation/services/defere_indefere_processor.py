"""
DefereIndefereProcessor (Automação)
Orquestra navegação + leitura DNNR + decisão + confirmação para Defere/Indefere Recurso.
"""
import time
from typing import Dict
from automation.actions.lecom_defere_indefere_action import LecomDefereIndefereAction
from automation.services.defere_indefere_service import DefereIndefereService


class DefereIndefereProcessor:
    def __init__(self, driver):
        self.lecom = LecomDefereIndefereAction(driver)
        self.service = DefereIndefereService()

    def processar_codigo(self, codigo: str) -> Dict:
        resultado = {
            'codigo': codigo,
            'status': 'erro',
            'decisao': '',
            'valor_dnnr': '',
            'decisao_enviada': False,
            'erro': ''
        }
        try:
            if not self.lecom.navegar_para_processo(codigo):
                resultado['erro'] = 'Falha ao navegar para processo'
                return resultado
            if not self.lecom.selecionar_atividade_defere_indefere():
                resultado['erro'] = 'Atividade não encontrada'
                return resultado
            if not self.lecom.abrir_form():
                resultado['erro'] = 'Falha ao abrir formulário'
                return resultado
            valor = self.lecom.ler_valor_dnnr()
            resultado['valor_dnnr'] = valor or ''
            decisao = self.service.decidir(valor)
            if not decisao:
                resultado['erro'] = 'Valor DNNR não mapeado'
                return resultado
            ok = self.lecom.aplicar_decisao(decisao)
            if not ok:
                resultado['erro'] = 'Falha ao aplicar decisão'
                return resultado
            if not self.lecom.aguardar_confirmacao(timeout=30):
                self.lecom.voltar_workspace()
            resultado['decisao'] = decisao
            resultado['decisao_enviada'] = True
            resultado['status'] = 'sucesso'
            time.sleep(1.5)
            return resultado
        except Exception as e:
            resultado['erro'] = str(e)
            return resultado
