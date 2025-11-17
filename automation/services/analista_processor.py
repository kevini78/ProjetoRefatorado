"""
Processor (Analista) - Orquestração do fluxo Aprovar Parecer do Analista
"""
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from automation.actions.lecom_analista_action import LecomAnalistaAction
from automation.repositories.analista_repository import AnalistaRepository
from automation.services.analista_service import AnalistaService

logger = logging.getLogger(__name__)


class AnalistaProcessor:
    def __init__(self, driver=None):
        self.lecom = LecomAnalistaAction(driver)
        self.repo = AnalistaRepository(self.lecom.driver, wait_timeout=10)
        self.service = AnalistaService()
        self.resultados: List[Dict[str, Any]] = []

    def executar(self, modo: str = 'versao', caminho_planilha: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.info(f"[EXEC] Iniciando Processor Analista - modo={modo}")
        if modo == 'planilha':
            if not caminho_planilha:
                logger.error('[ERRO] Caminho da planilha não informado')
                return []
            codigos = self.repo.ler_planilha_codigos(caminho_planilha)
            if not codigos:
                logger.error('[ERRO] Nenhum código encontrado na planilha')
                return []
            return self._executar_por_planilha(codigos)
        else:
            return self._executar_por_versao()

    def _executar_por_versao(self) -> List[Dict[str, Any]]:
        try:
            # Login manual (mesmo padrão das outras automações)
            if not self.lecom.login_manual():
                logger.error('[ERRO] Falha no login manual')
                return []
            if not self.lecom.go_to_workspace():
                return []
            if not self.lecom.click_inbox():
                return []
            if not self.lecom.apply_filters_for_analista():
                return []

            pagina = 1
            processados_total = 0
            while True:
                logger.info(f"[PÁGINA] Processando página {pagina}...")
                itens = self.lecom.list_processes() or []
                if not itens:
                    logger.info('[INFO] Nenhum processo na página')
                for idx, item in enumerate(itens, 1):
                    try:
                        if not self.lecom.open_process_by_href(item):
                            continue
                        data_inicio = self.lecom.extract_data_inicio() or ''
                        if not self.lecom.open_form_iframe():
                            continue
                        dados = self.repo.extrair_dados_formulario() or {}
                        analise = self.service.analisar_requisitos(dados, data_inicio)
                        decisao_ok = False
                        if analise.get('status') == 'ENVIAR PARA CPMIG':
                            decisao_ok = self.lecom.enviar_para_cpmig()
                        self._registrar_resultado(item.get('codigo'), dados, analise, data_inicio, decisao_ok)
                        processados_total += 1
                        time.sleep(1.5)
                        # Volta para inbox somente entre itens
                        if idx < len(itens):
                            self.lecom.back_to_inbox()
                            self.lecom.apply_filters_for_analista()
                    except Exception as e:
                        logger.error(f"[ERRO] Processo {item.get('codigo')}: {e}")
                        continue
                # próxima página
                if not self.lecom.next_page():
                    break
                pagina += 1
            logger.info(f"[OK] Concluído - {processados_total} processos")
            return self.resultados
        except Exception as e:
            logger.error(f"[ERRO] _executar_por_versao: {e}")
            return self.resultados

    def _executar_por_planilha(self, codigos: List[str]) -> List[Dict[str, Any]]:
        try:
            if not self.lecom.login_manual():
                logger.error('[ERRO] Falha no login manual')
                return []
            for i, codigo in enumerate(codigos, 1):
                try:
                    logger.info(f"[PLANILHA] {i}/{len(codigos)} - {codigo}")
                    if not self.lecom.navigate_direct_to_process(codigo):
                        continue
                    data_inicio = self.lecom.extract_data_inicio() or ''
                    if not self.lecom.open_form_iframe():
                        continue
                    dados = self.repo.extrair_dados_formulario() or {}
                    analise = self.service.analisar_requisitos(dados, data_inicio)
                    decisao_ok = False
                    if analise.get('status') == 'ENVIAR PARA CPMIG':
                        decisao_ok = self.lecom.enviar_para_cpmig()
                    self._registrar_resultado(codigo, dados, analise, data_inicio, decisao_ok)
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"[ERRO] Código {codigo}: {e}")
                    continue
            return self.resultados
        except Exception as e:
            logger.error(f"[ERRO] _executar_por_planilha: {e}")
            return self.resultados

    def _registrar_resultado(self, codigo: str, dados: dict, analise: dict, data_inicio: str, decisao_ok: bool):
        try:
            self.resultados.append({
                'processo': codigo,
                'data_inicio': data_inicio or 'N/A',
                'parecer_pf': dados.get('parecer_pf', 'N/A'),
                'parecer_mj': dados.get('parecer_mj', 'N/A'),
                'biometria': dados.get('biometria', 'N/A'),
                'tipo_naturalizacao': dados.get('tipo_naturalizacao', 'N/A'),
                'data_nascimento': dados.get('data_nascimento', 'N/A'),
                'status': analise.get('status', 'ANÁLISE MANUAL'),
                'decisao_automatica': 'Sim' if decisao_ok and analise.get('status') == 'ENVIAR PARA CPMIG' else 'Não',
                'motivo_analise_manual': '; '.join(analise.get('motivo_analise_manual') or []) if analise.get('motivo_analise_manual') else '',
                'timestamp_processamento': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            })
        except Exception as e:
            logger.warning(f"[AVISO] Falha ao registrar resultado de {codigo}: {e}")
