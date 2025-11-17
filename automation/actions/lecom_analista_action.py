"""
Action (Analista) - Operações de navegação/interação no LECOM
Focada no fluxo "Aprovar Parecer do Analista".
"""
import os
import time
import logging
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class LecomAnalistaAction:
    def __init__(self, driver=None, wait_timeout: int = 10):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, wait_timeout) if driver else None
        self.url_workspace = "https://justica.servicos.gov.br/workspace/"

        # seletores reutilizados
        self.seletores = {
            'menu_caixa_entrada': 'li.ant-menu-item[role="menuitem"]',
            'botao_filtro': 'button.ant-btn.bt-filter-actions.with-filters, .ant-dropdown-trigger, button[class*="header-btn"]',
            'campo_filtro_steps': '#filterSteps',
            'botao_aplicar_filtros': 'button.ant-btn.bt-submit.ant-btn-primary',
            'link_aprovar_parecer': 'a[title="Aprovar Parecer do Analista"]',
            'iframe_form_app': '#iframe-form-app',
            'proximo_pagina_alternativos': 'li.ant-pagination-next a, li.ant-pagination-next button, button[aria-label="Next Page"], a[title=""].pagination.next-page'
        }

    def inicializar_driver(self, headless: bool = False):
        if not self.driver:
            from selenium.webdriver.chrome.options import Options
            chrome_options = Options()
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-plugins-discovery")
            chrome_options.add_argument("--disable-pdf-viewer")
            if headless:
                chrome_options.add_argument("--headless")
                logger.info("Driver inicializado em modo headless")
            downloads_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'downloads')
            downloads_dir = os.path.abspath(downloads_dir)
            os.makedirs(downloads_dir, exist_ok=True)
            prefs = {
                "download.default_directory": downloads_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            }
            chrome_options.add_experimental_option("prefs", prefs)
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            try:
                if not headless:
                    self.driver.maximize_window()
            except Exception:
                pass
        return self.driver

    def login_manual(self, timeout: int = 300) -> bool:
        try:
            logger.info('[WEB] Acessando o LECOM...')
            self.driver.get('https://justica.servicos.gov.br/bpm')
            logger.info('[USER] Aguarde e faça o login manual...')
            start = time.time()
            while time.time() - start < timeout:
                cur = self.driver.current_url
                if 'workspace' in cur or 'dashboard' in cur:
                    logger.info('[OK] Login detectado!')
                    return True
                time.sleep(2)
            logger.error('[ERRO] Timeout aguardando login manual')
            return False
        except Exception as e:
            logger.error(f"[ERRO] Login manual: {e}")
            return False

    def go_to_workspace(self) -> bool:
        try:
            self.driver.get(self.url_workspace)
            time.sleep(2)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            return True
        except Exception as e:
            logger.error(f"[ERRO] Navegar workspace: {e}")
            return False

    def click_inbox(self) -> bool:
        try:
            menus = self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, self.seletores['menu_caixa_entrada'])))
            for m in menus:
                try:
                    if 'Caixa de entrada' in (m.text or ''):
                        m.click()
                        time.sleep(2)
                        return True
                except Exception:
                    continue
            logger.error("Menu 'Caixa de entrada' não encontrado")
            return False
        except Exception as e:
            logger.error(f"[ERRO] click_inbox: {e}")
            return False

    def _click_filters_button(self) -> bool:
        seletores_filtro = [
            'button.ant-btn.bt-filter-actions.with-filters',
            '.ant-dropdown-trigger',
            'button[class*="header-btn"]',
        ]
        for sel in seletores_filtro:
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    return True
            except Exception:
                continue
        try:
            btn_xpath = self.driver.find_element(By.XPATH, "//button[contains(., 'Filtro') or contains(@class, 'filter')]")
            btn_xpath.click()
            return True
        except Exception:
            pass
        return False

    def _select_process_fluxo_principal(self) -> bool:
        # Simplificado: abrir dropdown do processo e escolher opção que contenha "Naturalizar-se Brasileiro - Fluxo Principal"
        try:
            campos = ['#filterProcess .ant-select-selection', '#filterProcess', 'div[id="filterProcess"]']
            field = None
            for sel in campos:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if el.is_displayed():
                        el.click()
                        time.sleep(2)
                        field = el
                        break
                except Exception:
                    continue
            if not field:
                return False
            opc_sel = ['li.ant-select-dropdown-menu-item[role="option"]', '.ant-select-dropdown-menu-item', 'li[role="option"]']
            for sel in opc_sel:
                try:
                    opts = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for o in opts:
                        t = (o.text or '').strip()
                        if 'Naturalizar-se Brasileiro - Fluxo Principal' in t:
                            o.click()
                            time.sleep(1)
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def _select_activity_analista(self) -> bool:
        try:
            campos = ['#filterSteps .ant-select-selection', '#filterSteps', 'div[id="filterSteps"]']
            field = None
            for sel in campos:
                try:
                    el = self.driver.find_element(By.CSS_SELECTOR, sel)
                    if el.is_displayed():
                        el.click()
                        time.sleep(2)
                        field = el
                        break
                except Exception:
                    continue
            if not field:
                return False
            opc_sel = ['li.ant-select-dropdown-menu-item[role="option"]', '.ant-select-dropdown-menu-item', 'li[role="option"]']
            for sel in opc_sel:
                try:
                    opts = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for o in opts:
                        t = (o.text or '').strip()
                        if 'Aprovar Parecer do Analista' in t:
                            o.click()
                            time.sleep(1)
                            return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def apply_filters_for_analista(self) -> bool:
        try:
            time.sleep(2)
            if not self._click_filters_button():
                logger.error('[ERRO] Botão de filtros não encontrado')
                return False
            time.sleep(1)
            if not self._select_process_fluxo_principal():
                logger.error('[ERRO] Processo Fluxo Principal não selecionado')
                return False
            if not self._select_activity_analista():
                logger.error('[ERRO] Atividade Aprovar Parecer do Analista não selecionada')
                return False
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, self.seletores['botao_aplicar_filtros'])
                if 'Aplicar filtros' in (btn.text or ''):
                    btn.click()
                    time.sleep(3)
                    return True
            except Exception:
                pass
            try:
                btn = self.driver.find_element(By.XPATH, "//button[contains(@class,'bt-submit') and .//span[contains(text(),'Aplicar')]]")
                btn.click()
                time.sleep(3)
                return True
            except Exception:
                pass
            return False
        except Exception as e:
            logger.error(f"[ERRO] apply_filters_for_analista: {e}")
            return False

    def list_processes(self):
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-table-body')))
            time.sleep(1)
            containers = self.driver.find_elements(By.CSS_SELECTOR, '.ant-table-body')
            container = next((c for c in containers if c.is_displayed()), None)
            if not container:
                return []
            rows = container.find_elements(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
            items = []
            seen = set()
            for i, row in enumerate(rows):
                try:
                    link = row.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                    href = link.get_attribute('href')
                    if not href or href in seen:
                        continue
                    seen.add(href)
                    codigo = self._extract_code_from_href(href) or ''
                    items.append({'codigo': codigo or 'DESCONHECIDO', 'href': href, 'linha_index': i})
                except Exception:
                    continue
            return items
        except Exception as e:
            logger.error(f"[ERRO] list_processes: {e}")
            return []

    def open_process_by_href(self, item) -> bool:
        try:
            self.driver.get(item['href'])
            time.sleep(2)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
            return True
        except Exception as e:
            logger.error(f"[ERRO] open_process_by_href: {e}")
            return False

    def open_form_iframe(self) -> bool:
        try:
            iframe = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.seletores['iframe_form_app'])))
            src = iframe.get_attribute('src')
            if not src:
                return False
            self.driver.get(src)
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"[ERRO] open_form_iframe: {e}")
            return False

    def enviar_para_cpmig(self) -> bool:
        try:
            # Abrir dropdown
            triggers = ['#CHDNN_DEC_caret', '.caret.caret_search', '#CHDNN_DEC']
            opened = False
            for sel in triggers:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el.is_displayed():
                            el.click()
                            time.sleep(1)
                            opened = True
                            break
                    if opened:
                        break
                except Exception:
                    continue
            if not opened:
                return False
            # Selecionar opção
            options_sel = ['#CHDNN_DEC_list li', 'li.input-autocomplete__option', 'li[id*="CHDNN_DEC_"]']
            chosen = False
            for sel in options_sel:
                try:
                    opts = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for o in opts:
                        txt = ''
                        try:
                            span = o.find_element(By.TAG_NAME, 'span')
                            txt = span.get_attribute('title') or span.text or o.text
                        except Exception:
                            txt = o.text or o.get_attribute('textContent')
                        if 'Enviar para CPMIG' in (txt or ''):
                            o.click()
                            time.sleep(1)
                            chosen = True
                            break
                    if chosen:
                        break
                except Exception:
                    continue
            if not chosen:
                return False
            # Confirmar
            btn_sel = [
                'a.button.btn.aprovar[id="aprovar"]', 'a#aprovar', 'a.aprovar',
                'button[type="submit"]', 'a[data-method="POST"]', 'a.button.btn[id*="aprovar"]'
            ]
            clicked = False
            for sel in btn_sel:
                try:
                    btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for b in btns:
                        if b.is_displayed():
                            self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', b)
                            time.sleep(0.3)
                            b.click()
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception:
                    continue
            if not clicked:
                return False
            # Aguardar confirmação
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'p[aria-label*="Próximos responsáveis"]'))
                )
            except Exception:
                pass
            return True
        except Exception as e:
            logger.error(f"[ERRO] enviar_para_cpmig: {e}")
            return False

    def next_page(self) -> bool:
        try:
            assinatura_atual = None
            try:
                container = self.driver.find_element(By.CSS_SELECTOR, '.ant-table-body')
                primeira = container.find_element(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
                link = primeira.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                assinatura_atual = link.get_attribute('href')
            except Exception:
                pass
            # procurar next
            sels = self.seletores['proximo_pagina_alternativos']
            candidatos = self.driver.find_elements(By.CSS_SELECTOR, sels)
            btn = None
            for c in candidatos:
                try:
                    if c.is_displayed() and 'disabled' not in (c.get_attribute('class') or '').lower():
                        btn = c
                        break
                except Exception:
                    continue
            if not btn:
                return False
            try:
                self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', btn)
                time.sleep(0.2)
                self.driver.execute_script('arguments[0].click();', btn)
            except Exception:
                btn.click()
            # esperar mudança de assinatura
            for _ in range(40):
                time.sleep(0.2)
                try:
                    container2 = self.driver.find_element(By.CSS_SELECTOR, '.ant-table-body')
                    primeira2 = container2.find_element(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
                    link2 = primeira2.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                    assinatura_nova = link2.get_attribute('href')
                    if assinatura_nova and assinatura_nova != assinatura_atual:
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            return False
        except Exception as e:
            logger.error(f"[ERRO] next_page: {e}")
            return False

    def back_to_inbox(self) -> bool:
        try:
            if not self.go_to_workspace():
                return False
            if not self.click_inbox():
                return False
            return True
        except Exception as e:
            logger.error(f"[ERRO] back_to_inbox: {e}")
            return False

    def navigate_direct_to_process(self, codigo_processo: str) -> bool:
        try:
            numero_limpo = re.sub(r"\D", "", codigo_processo or '')
            workspace_url = f'https://justica.servicos.gov.br/workspace/flow/{numero_limpo}'
            self.driver.get(workspace_url)
            time.sleep(3)
            # buscar atividade Aprovar Parecer do Analista e clicar
            rows = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            chosen = None
            for i, row in enumerate(rows, start=1):
                try:
                    link = row.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    titulo = (link.get_attribute('title') or link.text or '').strip().lower()
                    if ('aprovar' in titulo or 'aprovação' in titulo) and 'parecer' in titulo and 'analista' in titulo:
                        chosen = link
                        break
                except Exception:
                    continue
            if not chosen:
                logger.error("Atividade 'Aprovar Parecer do Analista' não encontrada no flow")
                return False
            try:
                chosen.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", chosen)
            # esperar ir para form-app
            try:
                WebDriverWait(self.driver, 15).until(EC.url_contains('/form-app/'))
                return True
            except Exception:
                return 'form-app' in (self.driver.current_url or '')
        except Exception as e:
            logger.error(f"[ERRO] navigate_direct_to_process: {e}")
            return False

    def extract_data_inicio(self) -> str | None:
        try:
            # Tenta ler etiqueta com "Início em dd/mm/yyyy" como no módulo original
            try:
                el = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.activity-start-date')))
                txt = el.text or ''
                if 'Início em' in txt:
                    return txt.split('Início em ')[1].split(' ')[0]
            except Exception:
                pass
            # fallback: buscar em texto de subtítulo
            sels = [".subtitle", "[class*='subtitle']"]
            for sel in sels:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in els:
                        t = (e.text or '').strip()
                        if not t:
                            continue
                        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', t)
                        if m:
                            return f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{m.group(3)}"
                except Exception:
                    continue
            return None
        except Exception as e:
            logger.warning(f"[AVISO] extract_data_inicio: {e}")
            return None

    def _extract_code_from_href(self, href: str) -> str | None:
        try:
            m1 = re.search(r"/workspace/flow/(\d+)", href or '')
            if m1:
                return m1.group(1)
            m2 = re.search(r"/workspace/form-app/(\d+)/", href or '')
            if m2:
                return m2.group(1)
            return None
        except Exception:
            return None
