"""
Repository (Analista) - Acesso/leitura de dados do formulário e utilidades
"""
import logging
import time
from typing import Dict, List
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class AnalistaRepository:
    def __init__(self, driver, wait_timeout: int = 10):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, wait_timeout)
        self.seletores = {
            'parecer_pf': 'label[for^="CHPF_ACAO_"]',
            'parecer_mj': '#DNN_DEC',
            'biometria': 'label[for^="COL_BIOMETRIA_ITEM_"]',
            'tipo_naturalizacao': 'label[for^="TIPO_NAT_"]',
            'data_nascimento': '#ORD_NAS',
        }

    def extrair_dados_formulario(self) -> Dict[str, str]:
        dados: Dict[str, str] = {}
        try:
            time.sleep(2)
            # parecer PF
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['parecer_pf'])
                for e in elems:
                    if e.get_attribute('aria-checked') == 'true':
                        dados['parecer_pf'] = (e.text or '').strip()
                        break
                else:
                    dados['parecer_pf'] = 'Não encontrado'
            except Exception as e:
                logger.warning(f"[AVISO] parecer PF: {e}")
                dados['parecer_pf'] = 'Erro na extração'
            # parecer MJ
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, self.seletores['parecer_mj'])
                dados['parecer_mj'] = el.get_attribute('value') or el.get_attribute('title') or 'Não encontrado'
            except Exception as e:
                logger.warning(f"[AVISO] parecer MJ: {e}")
                dados['parecer_mj'] = 'Erro na extração'
            # biometria
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['biometria'])
                for e in elems:
                    if e.get_attribute('aria-checked') == 'true':
                        dados['biometria'] = (e.text or '').strip()
                        break
                else:
                    dados['biometria'] = 'Não encontrado'
            except Exception as e:
                logger.warning(f"[AVISO] biometria: {e}")
                dados['biometria'] = 'Erro na extração'
            # tipo naturalização
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['tipo_naturalizacao'])
                for e in elems:
                    if e.get_attribute('aria-checked') == 'true':
                        dados['tipo_naturalizacao'] = (e.text or '').strip()
                        break
                else:
                    dados['tipo_naturalizacao'] = 'Não encontrado'
            except Exception as e:
                logger.warning(f"[AVISO] tipo naturalização: {e}")
                dados['tipo_naturalizacao'] = 'Erro na extração'
            # data nascimento
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, self.seletores['data_nascimento'])
                dados['data_nascimento'] = el.get_attribute('value') or 'Não encontrado'
            except Exception as e:
                logger.warning(f"[AVISO] data nascimento: {e}")
                dados['data_nascimento'] = 'Erro na extração'
            return dados
        except Exception as e:
            logger.error(f"[ERRO] extrair_dados_formulario: {e}")
            return {}

    def ler_planilha_codigos(self, caminho_planilha: str, nome_coluna_codigo: str = 'codigo') -> List[str]:
        try:
            if caminho_planilha.endswith('.xlsx'):
                df = pd.read_excel(caminho_planilha)
            elif caminho_planilha.endswith('.csv'):
                df = pd.read_csv(caminho_planilha)
            else:
                df = pd.read_excel(caminho_planilha)
            col_map = {str(c).strip().lower(): c for c in df.columns}
            alvo = (nome_coluna_codigo or 'codigo').strip().lower()
            real = None
            for cand in [alvo, 'codigo', 'código']:
                if cand in col_map:
                    real = col_map[cand]
                    break
            if not real:
                for low, orig in col_map.items():
                    if 'codigo' in low or 'código' in low:
                        real = orig
                        break
            if not real:
                logger.error(f"Coluna '{nome_coluna_codigo}' não encontrada")
                return []
            codigos: List[str] = []
            for v in df[real]:
                if pd.notna(v):
                    s = str(v).strip()
                    if s:
                        codigos.append(s)
            return codigos
        except Exception as e:
            logger.error(f"[ERRO] ler_planilha_codigos: {e}")
            return []
