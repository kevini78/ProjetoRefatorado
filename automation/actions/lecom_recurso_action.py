"""
LecomRecursoAction (Automação)
Ações de navegação/interação no LECOM para o fluxo "Aprovação do Conteúdo de Recurso" (atividade 15).
"""
import time
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)


class LecomRecursoAction:
    def __init__(self, driver, wait_timeout: int = 15):
        self.driver = driver
        self.wait = WebDriverWait(self.driver, wait_timeout)
        self.process_instance_id = None
        self.ciclo_processo = 1

    # ======= Navegação de alto nível =======
    def navegar_para_processo(self, codigo_processo: str) -> bool:
        try:
            numero_limpo = re.sub(r"\D", "", codigo_processo or "")
            url = f"https://justica.servicos.gov.br/workspace/flow/{numero_limpo}"
            logger.info(f"[WEB] Navegando para: {url}")
            self.driver.get(url)
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"[ERRO] navegar_para_processo: {e}")
            return False

    def selecionar_atividade_aprovacao_conteudo(self) -> bool:
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-table-tbody")))
            time.sleep(1)
            linhas = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            logger.info(f"[BUSCA] {len(linhas)} atividades listadas")

            candidatos = []
            for i, linha in enumerate(linhas, 1):
                try:
                    link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    titulo = (link.get_attribute('title') or link.text or '').strip()
                    href = link.get_attribute('href') or ''
                    logger.info(f"  - {i}: '{titulo}' -> {href}")
                    # preferir atividade 15
                    ciclo = None
                    m = re.search(r"/15/(\d+)", href)
                    if m:
                        ciclo = int(m.group(1))
                    candidatos.append((link, titulo, href, ciclo))
                except Exception:
                    continue

            # Filtrar por título e ordenar pelo maior ciclo quando for atividade 15
            filtrados = []
            for link, titulo, href, ciclo in candidatos:
                t = titulo.lower()
                if (('aprovação' in t or 'aprovacao' in t) and ('conteúdo' in t or 'conteudo' in t) and 'recurso' in t):
                    filtrados.append((link, titulo, href, ciclo if ciclo is not None else -1))
            if not filtrados:
                logger.error("[ERRO] Atividade 'Aprovação do Conteúdo de Recurso' não encontrada")
                return False
            filtrados.sort(key=lambda x: x[3], reverse=True)
            link_escolhido, titulo, href, ciclo = filtrados[0]
            if ciclo and ciclo > 0:
                self.ciclo_processo = ciclo
            logger.info(f"[TARGET] Selecionado: '{titulo}' (ciclo={self.ciclo_processo})")

            try:
                link_escolhido.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", link_escolhido)

            try:
                WebDriverWait(self.driver, 15).until(EC.url_contains('/form-app/'))
            except Exception:
                time.sleep(2)
            cur = self.driver.current_url
            logger.info(f"[URL] Após clique: {cur}")
            m2 = re.search(r"/form-app/(\d+)/", cur)
            if m2:
                self.process_instance_id = m2.group(1)
                logger.info(f"[SALVO] processInstanceId={self.process_instance_id}")
            return 'form-app' in cur
        except Exception as e:
            logger.error(f"[ERRO] selecionar_atividade_aprovacao_conteudo: {e}")
            return False

    def abrir_form_iframe(self) -> bool:
        try:
            # tentar iframe existente
            try:
                iframe = self.wait.until(EC.presence_of_element_located((By.ID, "iframe-form-app")))
                src = iframe.get_attribute('src')
                if src and 'form-web' in src:
                    self.driver.switch_to.frame(iframe)
                    time.sleep(2)
                    return True
            except Exception:
                pass
            # fallback: construir URL
            if not self.process_instance_id:
                logger.error('[ERRO] processInstanceId não disponível')
                return False
            iframe_url = (
                f"https://justica.servicos.gov.br/form-web?processInstanceId={self.process_instance_id}"
                f"&activityInstanceId=15&cycle={self.ciclo_processo}&newWS=true"
            )
            logger.info(f"[WEB] Abrindo form-web: {iframe_url}")
            self.driver.get(iframe_url)
            time.sleep(3)
            return 'form-web' in (self.driver.current_url or '')
        except Exception as e:
            logger.error(f"[ERRO] abrir_form_iframe: {e}")
            return False

    # ======= Leitura e decisão =======
    def ler_valor_dnnr(self) -> str | None:
        try:
            campo = self.wait.until(EC.presence_of_element_located((By.ID, 'DNNR_DEC')))
            return (campo.get_attribute('value') or '').strip()
        except Exception as e:
            logger.error(f"[ERRO] ler_valor_dnnr: {e}")
            return None

    def aplicar_decisao(self, decisao: str) -> bool:
        try:
            if decisao == 'Nego Provimento':
                # Selecionar radio CPMIGR_DEC_1 e clicar botão Negar Provimento
                try:
                    opc = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='CPMIGR_DEC_1']")))
                    opc.click()
                    time.sleep(1)
                except Exception:
                    logger.warning('[AVISO] Não foi possível selecionar radio CPMIGR_DEC_1')
                # procurar botão
                seletores = ["a.rejeitar", "a#rejeitar", "a.button-danger.red", "a[id='rejeitar']"]
                btn = None
                for sel in seletores:
                    try:
                        cand = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if cand.is_displayed() and cand.is_enabled():
                            txt = (cand.text or '').strip()
                            if 'Negar' in txt or 'Nego Provimento' in txt:
                                btn = cand
                                break
                    except Exception:
                        continue
                if not btn:
                    # tentar por texto
                    xps = ["//a[contains(text(),'Negar Provimento')]", "//a[contains(text(),'Nego Provimento')]"]
                    for xp in xps:
                        try:
                            cand = self.driver.find_element(By.XPATH, xp)
                            if cand.is_displayed():
                                btn = cand
                                break
                        except Exception:
                            continue
                if not btn:
                    logger.error('[ERRO] Botão Negar Provimento não encontrado')
                    return False
                try:
                    btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", btn)
                return True

            elif decisao == 'Dou Provimento':
                # Selecionar radio CPMIGR_DEC_0 e clicar botão Dou Provimento
                try:
                    opc = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='CPMIGR_DEC_0']")))
                    opc.click()
                    time.sleep(1)
                except Exception:
                    logger.warning('[AVISO] Não foi possível selecionar radio CPMIGR_DEC_0')
                # procurar botão por diversos seletores
                candidatos = self.driver.find_elements(By.CSS_SELECTOR, "a.button.btn")
                btn = None
                for cand in candidatos:
                    try:
                        if cand.is_displayed() and cand.is_enabled():
                            t = (cand.text or '').strip()
                            if 'Dou Provimento' in t or 'Dar Provimento' in t:
                                btn = cand
                                break
                    except Exception:
                        continue
                if not btn:
                    xps = ["//a[contains(text(),'Dou Provimento')]", "//a[contains(text(),'Dar Provimento')]"]
                    for xp in xps:
                        try:
                            cand = self.driver.find_element(By.XPATH, xp)
                            if cand.is_displayed():
                                btn = cand
                                break
                        except Exception:
                            continue
                if not btn:
                    logger.error('[ERRO] Botão Dou Provimento não encontrado')
                    return False
                try:
                    btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", btn)
                return True
            else:
                logger.error(f"[ERRO] Decisão desconhecida: {decisao}")
                return False
        except Exception as e:
            logger.error(f"[ERRO] aplicar_decisao: {e}")
            return False

    def aguardar_confirmacao(self, timeout: int = 30) -> bool:
        try:
            ini = time.time()
            while time.time() - ini < timeout:
                try:
                    elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Próxima atividade')]")
                    for el in elems:
                        if not el.is_displayed():
                            continue
                        txt = (el.text or el.get_attribute('aria-label') or '').lower()
                        if 'atividade' in txt:
                            return True
                except Exception:
                    pass
                time.sleep(1)
            return False
        except Exception:
            return False

    def voltar_workspace(self) -> bool:
        try:
            self.driver.get('https://justica.servicos.gov.br/workspace')
            time.sleep(2)
            return 'workspace' in (self.driver.current_url or '')
        except Exception:
            return False
