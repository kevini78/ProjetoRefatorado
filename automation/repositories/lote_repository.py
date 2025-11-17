"""
LoteRepository (Automação)
Responsável por ler dados da tabela de Aprovação em Lote no form-web.
"""

import logging
from typing import List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class LoteRepository:
    """Repository com acesso à tabela de processos da tela de Aprovação em Lote."""

    def __init__(self, driver, wait_timeout: int = 10):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, wait_timeout)

    def listar_linhas_tabela(self) -> List[Any]:
        """Retorna as linhas da tabela atual de processos.

        Retorna uma lista de WebElements (tr.table-row).
        """
        try:
            # Aguarda o container da tabela existir
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".table.striped"))
            )

            # A tela em React pode demorar alguns segundos para popular as linhas;
            # repetir a leitura por alguns ciclos antes de concluir que não há linhas.
            linhas: List[Any] = []
            for tentativa in range(5):  # ~5 segundos no total
                linhas = self.driver.find_elements(By.CSS_SELECTOR, ".table-row")
                if linhas:
                    break
                logger.info(
                    f"[TABELA] Nenhuma linha ainda (tentativa {tentativa + 1}/5), aguardando..."
                )
                import time as _time
                _time.sleep(1)

            logger.info(f"[TABELA] Encontradas {len(linhas)} linhas na tabela")
            return linhas
        except Exception as e:
            logger.error(f"Erro ao listar linhas da tabela: {str(e)}")
            return []

    def extrair_dados_linha(self, linha) -> Dict[str, str]:
        """Extrai número do processo e análise do MJ de uma linha da tabela."""
        dados: Dict[str, str] = {}
        try:
            numero = linha.find_element(
                By.CSS_SELECTOR, ".table-cell--NAT_PROCESSO .table-cell__content"
            ).text
            analise_mj = linha.find_element(
                By.CSS_SELECTOR, ".table-cell--NAT_ANALISE_MJ .table-cell__content"
            ).text
            dados["numero_processo"] = numero.strip() if numero else ""
            dados["analise_mj"] = analise_mj.strip() if analise_mj else ""
            return dados
        except Exception as e:
            logger.error(f"Erro ao extrair dados da linha da tabela: {str(e)}")
            return {}
