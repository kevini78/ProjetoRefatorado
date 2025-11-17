"""
ProvisoriaAction
Action de navegação para Naturalização Provisória localizada em automation/actions.
- Cria e gerencia o driver Selenium (modo visual)
- Executa login automático via .env (LECOM_USER/LECOM_PASS)
- Delegação controlada para métodos complexos da NavegacaoProvisoria original
"""
import os
import time
from typing import Any, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv

# Carregar .env da raiz
ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
try:
    load_dotenv(ROOT_ENV)
except Exception:
    pass

LECOM_URL = "https://justica.servicos.gov.br/bpm"
LECOM_USER = os.environ.get("LECOM_USER")
LECOM_PASS = os.environ.get("LECOM_PASS")


class ProvisoriaAction:
    def __init__(self, driver: Any | None = None, wait_timeout: int = 40) -> None:
        if driver:
            self.driver = driver
            self.wait = WebDriverWait(self.driver, wait_timeout)
        else:
            self.driver = self._create_driver()
            self.wait = WebDriverWait(self.driver, wait_timeout)
        # Expor atributos esperados externamente
        self.data_inicial_processo = None
        self.numero_processo_limpo = None
        self.ciclo_processo = 2

    def _create_driver(self) -> webdriver.Chrome:
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-plugins-discovery")
        chrome_options.add_argument("--disable-pdf-viewer")
        # Downloads padrão
        download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        # Manter janela aberta mesmo após o script (útil p/ inspeção visual)
        try:
            chrome_options.add_experimental_option("detach", True)
        except Exception:
            pass
        drv = webdriver.Chrome(options=chrome_options)
        try:
            drv.maximize_window()
        except Exception:
            pass
        return drv

    def login(self) -> bool:
        try:
            self.driver.get(LECOM_URL)
            # Usuário → Próxima
            username_input = self.wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@name='username']")))
            username_input.clear()
            username_input.send_keys(LECOM_USER or "")
            proxima_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and .//span[text()='Próxima']]")))
            proxima_btn.click()
            # Senha → Entrar
            password_input = self.wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@name='password' and @type='password']")))
            password_input.clear()
            password_input.send_keys(LECOM_PASS or "")
            entrar_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and .//span[text()='Entrar']]")))
            entrar_btn.click()
            # Popups ocasionais
            try:
                botao_entendi = WebDriverWait(self.driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and contains(@class,'ant-btn-primary') and .//span[text()='Entendi']]"))
                )
                botao_entendi.click()
                time.sleep(1)
            except TimeoutException:
                pass
            # Fechar chat
            try:
                fechar_chat = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//svg[path[@d='M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z']]"))
                )
                fechar_chat.click()
            except TimeoutException:
                pass
            # Verificar se chegou ao workspace; caso contrário, forçar
            try:
                WebDriverWait(self.driver, 15).until(lambda d: 'workspace' in (d.current_url or '').lower())
            except TimeoutException:
                self.driver.get('https://justica.servicos.gov.br/workspace')
                try:
                    WebDriverWait(self.driver, 10).until(lambda d: 'workspace' in (d.current_url or '').lower())
                except TimeoutException:
                    return False
            # Marcar logado para evitar relogar no Processor
            try:
                self.ja_logado = True
            except Exception:
                pass
            return True
        except Exception:
            return False

    # Delegações controladas
    def _try_extract_data_inicial_from_subtitle(self) -> None:
        """Extrai data inicial do subtitle e normaliza em dd/mm/yyyy."""
        try:
            # Esperar mais tempo e usar XPath mais flexível
            subtitle = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//span[@class='subtitle' or contains(@class,'subtitle')]"))
            )
            print(f"[DEBUG] (Provisória) Subtitle encontrado: '{subtitle.text[:100]}...'")
            texto = (subtitle.text or '').strip()
            # Procurar padrao dd de Mmm de yyyy
            import re
            m = re.search(r"(\d{1,2})\s+de\s+([A-Za-zçÇãÃéÉêÊôÔõÕíÍáÁúÚ]{3,})\s+de\s+(\d{4})", texto, flags=re.I)
            if m:
                dia, mes_nome, ano = m.group(1), m.group(2).lower(), m.group(3)
                meses = {
                    'janeiro':'01','fevereiro':'02','março':'03','marco':'03','abril':'04','maio':'05','junho':'06',
                    'julho':'07','agosto':'08','setembro':'09','outubro':'10','novembro':'11','dezembro':'12',
                    'jan':'01','fev':'02','mar':'03','abr':'04','mai':'05','jun':'06','jul':'07','ago':'08','set':'09','out':'10','nov':'11','dez':'12'
                }
                # Normalizar nomes curtos: 'jul', 'set', etc.
                mes_nome_norm = mes_nome[:3] if mes_nome not in meses else mes_nome
                mm = meses.get(mes_nome_norm, meses.get(mes_nome))
                if mm:
                    dia = dia.zfill(2)
                    self.data_inicial_processo = f"{dia}/{mm}/{ano}"
        except Exception:
            pass

    def aplicar_filtros(self, numero_processo: str) -> Dict[str, Any] | bool | None:
        """Navega até o processo Provisório e abre o form-web, como na Ordinária.

        Retorna True/False indicando se a navegação básica deu certo.
        """
        try:
            import re
            from selenium.common.exceptions import TimeoutException as _T

            numero_limpo = re.sub(r"\D", "", numero_processo or "")
            if not numero_limpo:
                return False

            # Guardar número limpo para uso em outros métodos (download de PDFs, etc.)
            self.numero_processo_limpo = numero_limpo

            # PASSO 1: Navegar para a página do flow do processo
            url = f"https://justica.servicos.gov.br/workspace/flow/{numero_limpo}"
            print(f"[NAV] (Provisória) Navegando para: {url}")
            self.driver.get(url)
            time.sleep(3)  # Aguardar página carregar

            # PASSO 2: Aguardar tabela de atividades carregar (ANTES de extrair data)
            print("[NAV] (Provisória) Aguardando página carregar...")
            WebDriverWait(self.driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-table-tbody"))
            )
            print("[OK] (Provisória) Tabela de atividades carregada")

            # PASSO 3: AGORA extrair data inicial do processo (após página carregar)
            print("[DATA] (Provisória) Extraindo data inicial do processo...")
            try:
                self._try_extract_data_inicial_from_subtitle()
                if self.data_inicial_processo:
                    print(f"[OK] (Provisória) Data inicial extraída: {self.data_inicial_processo}")
                else:
                    print("[AVISO] (Provisória) Data inicial não encontrada no subtitle")
            except _T:
                print("[AVISO] (Provisória) Timeout ao extrair data inicial")
            except Exception as e:
                print(f"[AVISO] (Provisória) Erro ao extrair data inicial: {e}")


            # PASSO 4: Buscar atividade "Efetuar Distribuição"
            linhas = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            print(f"[NAV] (Provisória) {len(linhas)} atividades encontradas na tabela")

            # Procurar especificamente "Efetuar Distribuição" com href contendo /24/ (mesma regra da Ordinária)
            efetuar_distribuicao_links = []
            for linha in linhas:
                try:
                    link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    titulo = (link.get_attribute('title') or link.text or '').strip()
                    href = link.get_attribute('href') or ''

                    if ('/24/' in href) and ('efetuar distribui' in titulo.lower()):
                        match = re.search(r'/24/(\d+)', href)
                        if match:
                            ciclo = int(match.group(1))
                            efetuar_distribuicao_links.append((link, titulo, href, ciclo))
                            print(f"[NAV] (Provisória) Encontrada atividade ciclo {ciclo}: {href}")
                except Exception:
                    continue

            # Se não achou pelo filtro de ciclo, usar fallback simples (primeira atividade "efetuar distribui")
            if not efetuar_distribuicao_links:
                print("[NAV] (Provisória) Nenhum link com /24/ encontrado, usando fallback simples")
                for linha in linhas:
                    try:
                        link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                        titulo = (link.get_attribute('title') or link.text or '').strip().lower()
                        if 'efetuar distribui' in titulo:
                            efetuar_distribuicao_links.append((link, titulo, link.get_attribute('href') or '', 0))
                            print(f"[NAV] (Provisória) Fallback: usando atividade '{titulo}'")
                            break
                    except Exception:
                        continue

            if not efetuar_distribuicao_links:
                print("[ERRO] (Provisória) Atividade 'Efetuar Distribuição' não encontrada")
                return False

            # Ordenar por ciclo (maior primeiro) e pegar o mais recente, se tivermos ciclos
            efetuar_distribuicao_links.sort(key=lambda x: x[3], reverse=True)
            link_escolhido, titulo_escolhido, href_escolhido, ciclo_escolhido = efetuar_distribuicao_links[0]
            self.ciclo_processo = ciclo_escolhido
            print(f"[NAV] (Provisória) Selecionado ciclo {ciclo_escolhido}: {titulo_escolhido}")

            # Clicar na atividade (como na Ordinária)
            try:
                link_escolhido.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", link_escolhido)

            # Aguardar navegação para /form-app/
            try:
                WebDriverWait(self.driver, 15).until(EC.url_contains('/form-app/'))
            except _T:
                # Dar mais um tempo mesmo assim
                time.sleep(3)

            # PASSO 3: Navegar diretamente para o form-web, igual à Ordinária
            ciclo_para_usar = getattr(self, 'ciclo_processo', 2)
            form_url = (
                f"https://justica.servicos.gov.br/form-web?processInstanceId={numero_limpo}"
                f"&activityInstanceId=24&cycle={ciclo_para_usar}&newWS=true"
            )
            print(f"[NAV] (Provisória) Navegando para form-web: {form_url}")

            self.driver.get(form_url)
            time.sleep(5)

            current_url = self.driver.current_url
            if 'form-web' in current_url and numero_limpo in current_url:
                print('[NAV] (Provisória) Navegação para form-web bem-sucedida!')
            else:
                print(f"[AVISO] (Provisória) URL inesperada após navegação: {current_url}")

            return True

        except Exception as e:
            print(f"[ERRO] (Provisória) Falha em aplicar_filtros: {e}")
            return False


    def baixar_todos_documentos_e_ocr(self, *args, **kwargs):
        """Método de compatibilidade - retorna dicionário vazio.
        Download/OCR agora é gerenciado pelo ProvisoriaService.
        """
        return {}

    def baixar_documento_e_ocr(self, *args, **kwargs):
        """Método de compatibilidade - retorna None.
        Download/OCR agora é gerenciado pelo ProvisoriaService.
        """
        return None

    def extrair_dados_pessoais_formulario(self) -> Dict[str, Any]:
        """
        Extrai dados pessoais garantindo que estamos dentro do iframe do form-app.
        Primeiro tenta delegar para a NavegacaoProvisoria original (_orig); se não
        conseguir (ou se retornar vazio), faz um fallback direto no driver atual
        usando a mesma lógica de campos utilizada na Provisória legada.
        """
        print('[BUSCA] (ProvisóriaAction) Extraindo dados pessoais diretamente no driver/form-web...')
        dados_pessoais: Dict[str, Any] = {}

        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException as _T

            # Garantir contexto principal
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass

            # Tentar entrar no iframe form-app
            try:
                iframe = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, 'iframe-form-app'))
                )
                self.driver.switch_to.frame(iframe)
                print('[IFRAME] (ProvisóriaAction) Contexto trocado para iframe-form-app')
            except _T:
                print('[AVISO] (ProvisóriaAction) iframe-form-app não encontrado; tentando contexto atual mesmo')

            # Nome completo
            try:
                nome_element = WebDriverWait(self.driver, 8).until(
                    EC.visibility_of_element_located((By.ID, 'ORD_NOM_COMPLETO'))
                )
                dados_pessoais['nome_completo'] = (nome_element.get_attribute('value') or '').strip() or None
                print(f"[OK] (ProvisóriaAction) Nome completo: {dados_pessoais['nome_completo']}")
            except Exception as e:
                print(f"[AVISO] (ProvisóriaAction) Erro ao extrair nome completo: {e}")
                dados_pessoais['nome_completo'] = None

            # Data de entrada/residência no Brasil (tentar por label + input)
            try:
                from selenium.common.exceptions import TimeoutException as _T
                xpath_label_date = (
                    "//label["
                    "contains(translate(normalize-space(.), "
                    "'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç', "
                    "'AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'), 'brasil') and ("
                    "contains(translate(normalize-space(.), 'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'entrada') or "
                    "contains(translate(normalize-space(.), 'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'ingresso') or "
                    "contains(translate(normalize-space(.), 'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'chegada') or "
                    "contains(translate(normalize-space(.), 'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç', 'AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'resid')"
                    ")]/following::input[@type='date'][1]"
                )
                try:
                    inp = WebDriverWait(self.driver, 5).until(
                        EC.visibility_of_element_located((By.XPATH, xpath_label_date))
                    )
                    dt_val = (inp.get_attribute('value') or '').strip()
                except _T:
                    # Fallback: qualquer input date com id/name sugestivo
                    inp = None
                    sugestivos = [
                        "//input[@type='date' and (contains(translate(@id,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'brasil') or contains(translate(@name,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'brasil'))]",
                        "//input[@type='date' and (contains(translate(@id,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'entrada') or contains(translate(@name,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'entrada'))]",
                        "//input[@type='date' and (contains(translate(@id,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'ingresso') or contains(translate(@name,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'ingresso'))]",
                        "//input[@type='date' and (contains(translate(@id,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'chegada') or contains(translate(@name,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'chegada'))]",
                        "//input[@type='date' and (contains(translate(@id,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'resid') or contains(translate(@name,'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç','AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'),'resid'))]",
                    ]
                    dt_val = None
                    for xp in sugestivos:
                        try:
                            el = WebDriverWait(self.driver, 3).until(
                                EC.visibility_of_element_located((By.XPATH, xp))
                            )
                            val = (el.get_attribute('value') or '').strip()
                            if val:
                                dt_val = val
                                break
                        except _T:
                            continue
                if dt_val:
                    dados_pessoais['data_entrada_brasil'] = dt_val
                    dados_pessoais['data_residencia_inicial'] = dt_val
                    print(f"[OK] (ProvisóriaAction) Data de entrada/residência: {dt_val}")
            except Exception as e:
                print(f"[AVISO] (ProvisóriaAction) Erro ao procurar data de entrada/residência: {e}")

            # Nome do pai
            try:
                pai_element = WebDriverWait(self.driver, 8).until(
                    EC.visibility_of_element_located((By.ID, 'ORD_FI1'))
                )
                dados_pessoais['nome_pai'] = (pai_element.get_attribute('value') or '').strip() or None
                print(f"[OK] (ProvisóriaAction) Nome do pai: {dados_pessoais['nome_pai']}")
            except Exception as e:
                print(f"[AVISO] (ProvisóriaAction) Erro ao extrair nome do pai: {e}")
                dados_pessoais['nome_pai'] = None

            # Nome da mãe
            try:
                mae_element = WebDriverWait(self.driver, 8).until(
                    EC.visibility_of_element_located((By.ID, 'ORD_FI2'))
                )
                dados_pessoais['nome_mae'] = (mae_element.get_attribute('value') or '').strip() or None
                print(f"[OK] (ProvisóriaAction) Nome da mãe: {dados_pessoais['nome_mae']}")
            except Exception as e:
                print(f"[AVISO] (ProvisóriaAction) Erro ao extrair nome da mãe: {e}")
                dados_pessoais['nome_mae'] = None

            # Data de nascimento - usar mesmas estratégias robustas da navegação Provisória
            try:
                # Estratégia 1: ID direto (layout antigo)
                try:
                    nascimento_element = WebDriverWait(self.driver, 6).until(
                        EC.visibility_of_element_located((By.ID, 'ORD_NAS'))
                    )
                    origem = 'ID=ORD_NAS'
                except Exception:
                    nascimento_element = None
                    origem = None

                # Estratégia 2: input associado à label "Data de nascimento" (layout novo)
                if nascimento_element is None:
                    try:
                        print('[BUSCA] (ProvisóriaAction) Procurando data de nascimento por label...')
                        xpath_label = (
                            "//label[contains("  # normaliza acentos para comparar texto
                            "translate(normalize-space(.), "
                            "'ÁÀÃÂÉÈÊÍÌÎÓÒÔÕÚÙÛÇáàãâéèêíìîóòôõúùûç', "
                            "'AAAAEEEIIIOOOOUUUCaaaaeeeiiioooouuuuc'), "
                            "'data de nascimento')]//following::input[1]"
                        )
                        nascimento_element = WebDriverWait(self.driver, 6).until(
                            EC.visibility_of_element_located((By.XPATH, xpath_label))
                        )
                        origem = 'label:data de nascimento'
                    except Exception:
                        nascimento_element = None

                # Estratégia 3: qualquer input type=date com NAS/NASC
                if nascimento_element is None:
                    try:
                        print('[BUSCA] (ProvisóriaAction) Procurando data de nascimento por type=date...')
                        xpath_date = (
                            "//input[@type='date' and "
                            "(contains(@id,'NAS') or contains(@name,'NAS') or contains(@id,'NASC'))]"
                        )
                        nascimento_element = WebDriverWait(self.driver, 6).until(
                            EC.visibility_of_element_located((By.XPATH, xpath_date))
                        )
                        origem = 'input[type=date] com NAS/NASC'
                    except Exception:
                        nascimento_element = None

                if nascimento_element is not None:
                    valor = (nascimento_element.get_attribute('value') or '').strip()
                    dados_pessoais['data_nascimento'] = valor or None
                    print(f"[OK] (ProvisóriaAction) Data de nascimento extraída ({origem}): {dados_pessoais['data_nascimento']}")
                else:
                    print('[AVISO] (ProvisóriaAction) Campo de data de nascimento não encontrado por nenhuma estratégia')
                    dados_pessoais['data_nascimento'] = None

            except Exception as e:
                print(f"[ERRO] (ProvisóriaAction) Erro inesperado ao extrair data de nascimento: {e}")
                dados_pessoais['data_nascimento'] = None

            print(f"[OK] (ProvisóriaAction) Dados pessoais extraídos via fallback: {dados_pessoais}")
            return dados_pessoais

        except Exception as e:
            print(f"[ERRO] (ProvisóriaAction) Erro no fallback de extração de dados pessoais: {e}")
            return {}

    def extrair_data_inicial_processo(self) -> str | None:
        """Retorna a data inicial do processo extraída durante aplicação de filtros."""
        return getattr(self, 'data_inicial_processo', None)
    
    def extrair_parecer_pf(self) -> Dict[str, Any]:
        """
        Extrai e analisa o parecer da Polícia Federal.
        Importante para determinar se residiu no Brasil antes dos 10 anos.
        """
        try:
            import re
            from selenium.common.exceptions import NoSuchElementException
            
            # Garantir contexto correto (tentar iframe primeiro)
            try:
                self.driver.switch_to.default_content()
                iframe = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.ID, 'iframe-form-app'))
                )
                self.driver.switch_to.frame(iframe)
            except Exception:
                # Se não tiver iframe, continuar no contexto atual
                pass
            
            # Tentar localizar o campo do parecer PF
            # IDs possíveis: CHPF_PARECER (Ordinária), pode ser diferente na Provisória
            ids_possiveis = ['CHPF_PARECER', 'PF_PARECER', 'PARECER_PF', 'PARECER']
            
            parecer_texto = ''
            for campo_id in ids_possiveis:
                try:
                    elemento_parecer = self.driver.find_element(By.ID, campo_id)
                    parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
                    if parecer_texto:
                        print(f'[OK] (ProvisóriaAction) Parecer PF encontrado no campo: {campo_id}')
                        break
                except NoSuchElementException:
                    continue
            
            if not parecer_texto:
                print('[AVISO] (ProvisóriaAction) Parecer PF não encontrado')
                return {
                    'parecer_texto': '',
                    'proposta_pf': 'Não encontrado',
                    'antes_10_anos': None,
                    'alertas': ['Parecer PF não encontrado no formulário']
                }
            
            alertas = []
            
            # Análise específica para Provisória: idade de entrada no Brasil
            # Procurar padrões que indiquem entrada antes ou depois dos 10 anos
            
            padroes_antes_10 = [
                r'antes\s+de\s+completar\s*10',
                r'antes\s+dos\s*10\s+anos',
                r'com\s+menos\s+de\s*10\s+anos',
                r'antes\s+de\s*10\s+anos',
                r'menor\s+de\s*10\s+anos',
                r'idade\s+inferior\s+a\s*10',
                r'ingressou.*com.*[0-9]\s+anos',  # Capturar idade específica
            ]
            
            padroes_depois_10 = [
                r'após\s+os\s*10\s+anos',
                r'depois\s+dos\s*10\s+anos',
                r'após\s+completar\s*10',
                r'maior\s+de\s*10\s+anos',
                r'idade\s+superior\s+a\s*10',
            ]
            
            antes_10_anos = None
            
            # Verificar padrões de "antes dos 10"
            for padrao in padroes_antes_10:
                match = re.search(padrao, parecer_texto, re.IGNORECASE)
                if match:
                    antes_10_anos = True
                    alertas.append(f'PF indica ingresso antes dos 10 anos')
                    print(f'[OK] (ProvisóriaAction) PF: Ingresso ANTES dos 10 anos identificado')
                    break
            
            # Se não encontrou "antes", verificar "depois"
            if antes_10_anos is None:
                for padrao in padroes_depois_10:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        antes_10_anos = False
                        alertas.append(f'PF indica ingresso DEPOIS dos 10 anos')
                        print(f'[AVISO] (ProvisóriaAction) PF: Ingresso DEPOIS dos 10 anos identificado')
                        break
            
            # Extrair proposta da PF (deferimento/indeferimento)
            proposta_pf = 'Indeferimento'  # Default
            
            padroes_deferimento = [
                r'proposta.*deferimento',
                r'recomenda.*deferimento',
                r'sugere.*deferimento',
                r'favorável.*ao.*pedido',
                r'parecer.*favorável'
            ]
            
            for padrao in padroes_deferimento:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    proposta_pf = 'Deferimento'
                    break
            
            resultado = {
                'parecer_texto': parecer_texto,
                'proposta_pf': proposta_pf,
                'antes_10_anos': antes_10_anos,  # True/False/None
                'alertas': alertas
            }
            
            print(f'[PARECER PF] Proposta: {proposta_pf}, Antes 10 anos: {antes_10_anos}')
            
            return resultado
            
        except Exception as e:
            print(f"[ERRO] (ProvisóriaAction) Erro ao extrair parecer PF: {e}")
            return {
                'parecer_texto': '',
                'proposta_pf': 'Erro na extração',
                'antes_10_anos': None,
                'alertas': [f'Erro na extração: {e}']
            }

    def voltar_para_pesquisa_processos(self) -> bool:
        """Volta para a página de workspace."""
        try:
            self.driver.get('https://justica.servicos.gov.br/workspace')
            time.sleep(2)
            return True
        except Exception:
            return False

    def processar_processo(self, numero_processo: str, dados_texto: dict | None = None):
        """Processa um processo de Naturalização Provisória.
        
        Aplica filtros e navega para o formulário. O download e análise de
        documentos é gerenciado pelo ProvisoriaService.
        """
        ok = self.aplicar_filtros(numero_processo)
        if not ok:
            return {'status': 'Erro', 'erro': 'Falha ao navegar para o processo'}
        return {'status': 'Processado com sucesso', 'numero_processo': numero_processo}

    def fechar(self):
        """Fecha o driver do navegador."""
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
