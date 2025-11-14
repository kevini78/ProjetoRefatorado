"""
Módulo para automação de aprovação de parecer do analista no sistema LECOM
"""

import os
import time
import logging
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    ElementClickInterceptedException,
    ElementNotInteractableException,
    StaleElementReferenceException
)
from automation.adapters.navegacao_ordinaria_adapter import NavegacaoOrdinaria

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AprovacaoParecerAnalista:
    """Classe para automação de aprovação de parecer do analista no sistema LECOM"""
    
    def __init__(self, driver=None, modo_selecao='versao', caminho_planilha=None):
        """Inicializa a classe de aprovação de parecer do analista
        
        Args:
            driver: WebDriver do Selenium
            modo_selecao: 'versao' ou 'planilha' - define o modo de seleção dos processos
            caminho_planilha: Caminho para a planilha (quando modo_selecao='planilha')
        """
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 10) if driver else None
        self.navegacao_ordinaria = NavegacaoOrdinaria(driver) if driver else None
        
        # URLs do sistema
        self.url_workspace = "https://justica.servicos.gov.br/workspace/"
        
        # Controle de login
        self.ja_logado = False
        
        # Lista para armazenar resultados
        self.resultados_processamento = []
        
        # Configuração do modo de seleção
        self.modo_selecao = modo_selecao
        self.caminho_planilha = caminho_planilha
        self.codigos_processos = []  # Para armazenar códigos da planilha quando necessário
        
        # Seletores dos elementos
        self.seletores = {
            'menu_caixa_entrada': 'li.ant-menu-item[role="menuitem"]',
            'botao_filtro': 'button.ant-btn.bt-filter-actions.with-filters, .ant-dropdown-trigger, button[class*="header-btn"]',
            'dropdown_menu': '.ant-select-dropdown-menu, .ant-dropdown-menu',
            'opcoes_dropdown': 'li[role="option"], .ant-select-dropdown-menu-item',
            'campo_filtro_steps': '#filterSteps',
            'botao_aplicar_filtros': 'button.ant-btn.bt-submit.ant-btn-primary',
            'tabela_processos': 'tbody.ant-table-tbody',
            'linhas_processos': 'tr.ant-table-row',
            'link_aprovar_parecer': 'a[title="Aprovar Parecer do Analista"]',
            'data_inicio_atividade': '.activity-start-date',
            'iframe_form_app': '#iframe-form-app',
            'parecer_pf': 'label[for^="CHPF_ACAO_"]',
            'parecer_mj': '#DNN_DEC',
            'biometria': 'label[for^="COL_BIOMETRIA_ITEM_"]',
            'tipo_naturalizacao': 'label[for^="TIPO_NAT_"]',
            'data_nascimento': '#ORD_NAS',
            'decisao_campo_trigger': '#CHDNN_DEC_caret',
            'decisao_campo_input': '#CHDNN_DEC',
            'decisao_dropdown': '#CHDNN_DEC_list',
            'opcao_enviar_cpmig': '#CHDNN_DEC_0',
            'botao_enviar_cpmig': 'a.button.btn.aprovar[id="aprovar"]',
            'confirmacao_sucesso': 'p[aria-label*="Próximos responsáveis"]',
            'proximo_pagina': 'svg[viewBox="0 0 24 24"]',
            'proximo_pagina_link': 'a.pagination.next-page',
            'proximo_pagina_alternativos': 'li.ant-pagination-next a, li.ant-pagination-next button, button[aria-label="Next Page"], a[title=""].pagination.next-page'
        }
        
    def inicializar_driver(self, headless=False):
        """Inicializa o driver do navegador com modo visual"""
        if not self.driver:
            try:
                from selenium.webdriver.chrome.options import Options
                import os
                
                chrome_options = Options()
                
                # Configurações básicas
                chrome_options.add_argument("--disable-extensions")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-plugins")
                chrome_options.add_argument("--disable-plugins-discovery")
                chrome_options.add_argument("--disable-pdf-viewer")
                
                # MODO VISUAL - Não adicionar headless a menos que especificado
                if headless:
                    chrome_options.add_argument("--headless")
                    logger.info("Driver inicializado em modo headless")
                else:
                    logger.info("Driver inicializado em modo VISUAL")
                
                # Configurar diretório de downloads
                downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads')
                os.makedirs(downloads_dir, exist_ok=True)
                
                prefs = {
                    "download.default_directory": downloads_dir,
                    "download.prompt_for_download": False,
                    "download.directory_upgrade": True,
                    "safebrowsing.enabled": True,
                    "profile.content_settings.plugin_whitelist.adobe-flash-player": 0,
                    "profile.default_content_setting_values.plugins": 2
                }
                chrome_options.add_experimental_option("prefs", prefs)
                
                self.driver = webdriver.Chrome(options=chrome_options)
                self.wait = WebDriverWait(self.driver, 10)
                
                # Maximizar janela para melhor visualização
                if not headless:
                    self.driver.maximize_window()
                
                # Inicializar navegacao_ordinaria com o driver criado
                self.navegacao_ordinaria = NavegacaoOrdinaria(self.driver)
                
                logger.info("[OK] Driver inicializado com sucesso")
                return self.driver
                
            except Exception as e:
                logger.error(f"Erro ao inicializar driver: {str(e)}")
                return None
        
        return self.driver
    
    def fazer_login(self):
        """Realiza login no sistema usando o módulo de navegação ordinária"""
        try:
            if not self.navegacao_ordinaria:
                logger.error("Módulo de navegação ordinária não inicializado")
                return False
            
            # Verificar se já está logado
            if self.ja_logado:
                current_url = self.driver.current_url
                if 'justica.servicos.gov.br' in current_url:
                    logger.info("[OK] Usuário já está logado - pulando processo de login")
                    return True
                else:
                    logger.warning("[AVISO] Marcado como logado mas não está no domínio correto - fazendo login novamente")
                    self.ja_logado = False
                
            logger.info("Iniciando processo de login...")
            
            # Executar login
            self.navegacao_ordinaria.login()
            
            # Aguardar um momento para garantir que a página carregou
            time.sleep(2)
            
            # Verificar se login foi bem-sucedido checando a URL atual
            current_url = self.driver.current_url
            logger.info(f"URL atual após login: {current_url}")
            
            if 'workspace' in current_url.lower() or 'justica.servicos.gov.br' in current_url:
                logger.info("[OK] Login realizado com sucesso")
                self.ja_logado = True
                return True
            else:
                logger.error(f"[ERRO] Falha no login - URL não é do sistema esperado: {current_url}")
                self.ja_logado = False
                return False
                
        except Exception as e:
            logger.error(f"Erro durante o login: {str(e)}")
            self.ja_logado = False
            return False
    
    def fazer_login_manual(self):
        """Aguarda login manual no LECOM - para permitir usar diferentes contas"""
        try:
            logger.info('=== INÍCIO LOGIN MANUAL ===')
            logger.info('[WEB] Acessando o LECOM...')
            self.driver.get('https://justica.servicos.gov.br/bpm')
            
            logger.info('[USER] AGUARDANDO LOGIN MANUAL...')
            logger.info('[INFO] Instruções:')
            logger.info('   1. Faça o login manualmente na página do LECOM')
            logger.info('   2. O sistema detectará automaticamente quando o login for concluído')
            logger.info('   3. Aguarde até aparecer "[OK] Login detectado!" antes de continuar')
            logger.info('')
            logger.info('[AGUARDE] Monitorando... (aguardando até 300 segundos)')
            
            # Aguardar até 5 minutos pelo login manual
            timeout = 300  # 5 minutos
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    current_url = self.driver.current_url
                    
                    # Verificar se chegou no workspace (login bem-sucedido)
                    if "workspace" in current_url or "dashboard" in current_url:
                        logger.info('[OK] Login detectado com sucesso!')
                        logger.info(f'[LINK] URL atual: {current_url}')
                        self.ja_logado = True
                        return True
                    
                    # Log de progresso a cada 10 segundos
                    elapsed = int(time.time() - start_time)
                    if elapsed % 10 == 0 and elapsed > 0:
                        remaining = timeout - elapsed
                        logger.info(f'[AGUARDE] Aguardando login... {elapsed}s decorridos ({remaining}s restantes)')
                        logger.info(f'📍 URL atual: {current_url}')
                    
                    # Aguardar 2 segundos antes da próxima verificação
                    time.sleep(2)
                    
                except Exception as e:
                    logger.warning(f'[AVISO] Erro durante monitoramento: {e}')
                    time.sleep(2)
                    continue
            
            # Timeout
            logger.error('[ERRO] Timeout aguardando login manual!')
            logger.error(f'[TEMPO] Tempo limite de {timeout} segundos excedido')
            logger.error('[RELOAD] Você pode tentar novamente fazendo o login e reiniciando o processo')
            return False
            
        except Exception as e:
            logger.error(f'[ERRO] Erro durante login manual: {str(e)}')
            return False
    
    def navegar_para_workspace(self):
        """Navega para a página inicial do workspace"""
        try:
            logger.info("Navegando para o workspace...")
            self.driver.get(self.url_workspace)
            time.sleep(2)
            
            # Aguardar carregamento da página
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            logger.info("[OK] Navegação para workspace concluída")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao navegar para workspace: {str(e)}")
            return False
    
    def clicar_caixa_entrada(self):
        """Clica no menu 'Caixa de entrada'"""
        try:
            logger.info("Procurando menu 'Caixa de entrada'...")
            
            # Aguardar e buscar o menu Caixa de entrada
            menus = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, self.seletores['menu_caixa_entrada']))
            )
            
            for menu in menus:
                try:
                    if "Caixa de entrada" in menu.text:
                        menu.click()
                        logger.info("[OK] Menu 'Caixa de entrada' clicado com sucesso")
                        time.sleep(2)
                        return True
                except:
                    continue
                    
            logger.error("Menu 'Caixa de entrada' não encontrado")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao clicar no menu 'Caixa de entrada': {str(e)}")
            return False
    
    def aplicar_filtros_caixa_entrada(self):
        """Aplica filtros na Caixa de Entrada para mostrar apenas processos de Aprovar Parecer do Analista"""
        try:
            logger.info("🔽 INICIANDO APLICAÇÃO DE FILTROS NA CAIXA DE ENTRADA...")
            
            # Aguardar carregamento da página
            logger.info("[AGUARDE] Aguardando carregamento da página...")
            time.sleep(3)
            
            # Capturar URL atual para debug
            current_url = self.driver.current_url
            logger.info(f"📍 URL atual: {current_url}")
            
            # 1. Clicar no botão de filtros
            logger.info("🔲 PASSO 1: Clicando no botão de filtros...")
            if not self.clicar_botao_filtro():
                logger.error("[ERRO] FALHA NO PASSO 1: Não foi possível clicar no botão de filtros")
                return False
            
            # Aguardar carregamento da interface de filtros
            logger.info("[AGUARDE] Aguardando carregamento da interface de filtros...")
            if not self.aguardar_elementos_filtro():
                logger.error("[ERRO] Elementos de filtro não carregaram corretamente")
                return False
            
            # 2. Selecionar processo "Naturalizar-se Brasileiro - Fluxo Principal - v.11"
            logger.info("🔲 PASSO 2: Selecionando processo Fluxo Principal...")
            if not self.selecionar_processo_fluxo_principal():
                logger.error("[ERRO] FALHA NO PASSO 2: Não foi possível selecionar o processo")
                return False
            
            # 3. Selecionar atividade "Aprovar Parecer do Analista"
            logger.info("🔲 PASSO 3: Selecionando atividade Aprovar Parecer...")
            if not self.selecionar_atividade_aprovar_parecer():
                logger.error("[ERRO] FALHA NO PASSO 3: Não foi possível selecionar a atividade")
                return False
            
            # 4. Aplicar filtros
            logger.info("🔲 PASSO 4: Aplicando filtros...")
            if not self.clicar_aplicar_filtros():
                logger.error("[ERRO] FALHA NO PASSO 4: Não foi possível aplicar os filtros")
                return False
            
            logger.info("[SUCCESS] FILTROS APLICADOS COM SUCESSO!")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao aplicar filtros: {str(e)}")
            return False
    
    def aguardar_elementos_filtro(self):
        """Aguarda os elementos de filtro aparecerem na página"""
        try:
            logger.info("🕐 Aguardando elementos de filtro carregarem...")
            
            # Lista de elementos que indicam que a interface de filtros carregou
            elementos_indicadores = [
                '.ant-select-dropdown-menu',
                '.ant-dropdown-menu', 
                'li[role="option"]',
                '.ant-select-dropdown-menu-item',
                '#filterSteps',
                '.ant-select-selection'
            ]
            
            # Aguardar até 10 segundos pelos elementos
            for tentativa in range(10):
                logger.info(f"[AGUARDE] Tentativa {tentativa + 1}/10 - Verificando elementos...")
                
                for seletor in elementos_indicadores:
                    try:
                        elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                        if elementos:
                            logger.info(f"[OK] Elemento encontrado: {seletor}")
                            # Aguardar mais um pouco para estabilizar
                            time.sleep(2)
                            return True
                    except:
                        continue
                
                # Se não encontrou nada, aguardar 1 segundo e tentar novamente
                time.sleep(1)
            
            # Se chegou aqui, não encontrou os elementos
            logger.warning("[AVISO] Elementos de filtro não encontrados, tentando continuar mesmo assim...")
            time.sleep(3)  # Aguardar um tempo adicional
            return True  # Retornar True para tentar continuar mesmo assim
            
        except Exception as e:
            logger.error(f"Erro ao aguardar elementos de filtro: {str(e)}")
            time.sleep(4)  # Tempo de fallback
            return True  # Tentar continuar mesmo com erro
    
    def clicar_botao_filtro(self):
        """Clica no botão de filtros"""
        try:
            logger.info("Procurando botão de filtros...")
            
            # Lista de seletores alternativos para o botão de filtros
            seletores_filtro = [
                'button.ant-btn.bt-filter-actions.with-filters',
                '.ant-dropdown-trigger',
                'button[class*="header-btn"]',
                'button:contains("Filtros")',
                'span:contains("Filtros")',
                '.ant-dropdown-trigger[role="button"]'
            ]
            
            for seletor in seletores_filtro:
                try:
                    botao = self.driver.find_element(By.CSS_SELECTOR, seletor)
                    if botao.is_displayed() and botao.is_enabled():
                        botao.click()
                        logger.info(f"[OK] Botão de filtros clicado usando seletor: {seletor}")
                        return True
                except:
                    continue
            
            # Se não encontrou com CSS, tentar por XPath
            try:
                botao_xpath = self.driver.find_element(By.XPATH, "//button[contains(., 'Filtro') or contains(@class, 'filter')]")
                botao_xpath.click()
                logger.info("[OK] Botão de filtros clicado usando XPath")
                return True
            except:
                pass
            
            logger.error("[ERRO] Botão de filtros não encontrado")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao clicar no botão de filtros: {str(e)}")
            return False
    
    def selecionar_processo_fluxo_principal(self):
        """Seleciona o processo 'Naturalizar-se Brasileiro - Fluxo Principal - v.11'"""
        try:
            logger.info("[BUSCA] Iniciando seleção do processo...")
            
            # 1. Primeiro, clicar no campo de processo para abrir o dropdown
            try:
                logger.info("👆 Clicando no campo 'Processos' para abrir dropdown...")
                
                # Tentar múltiplos seletores para o campo de processo
                seletores_campo = [
                    '#filterProcess .ant-select-selection',
                    '#filterProcess',
                    '.form-filter-process .ant-select-selection',
                    '.form-filter-process',
                    'div[id="filterProcess"]'
                ]
                
                campo_clicado = False
                for seletor in seletores_campo:
                    try:
                        campo_processo = self.driver.find_element(By.CSS_SELECTOR, seletor)
                        if campo_processo.is_displayed():
                            campo_processo.click()
                            logger.info(f"[OK] Campo de processo clicado usando: {seletor}")
                            time.sleep(3)  # Aguardar mais tempo
                            campo_clicado = True
                            break
                    except:
                        continue
                
                if not campo_clicado:
                    logger.error("[ERRO] Não foi possível clicar no campo de processo")
                    return False
                    
            except Exception as e:
                logger.warning(f"Erro ao clicar no campo processo: {str(e)}")
                return False
            
            # 2. Aguardar dropdown aparecer e procurar a opção
            logger.info("[BUSCA] Aguardando dropdown aparecer...")
            time.sleep(2)
            
            # Buscar opções no dropdown com múltiplos seletores
            try:
                seletores_opcoes = [
                    'li.ant-select-dropdown-menu-item[role="option"]',
                    '.ant-select-dropdown-menu-item',
                    'li[role="option"]',
                    '.ant-dropdown-menu li'
                ]
                
                opcoes_encontradas = []
                for seletor in seletores_opcoes:
                    try:
                        opcoes = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                        if opcoes:
                            opcoes_encontradas = opcoes
                            logger.info(f"[INFO] {len(opcoes)} opções encontradas usando: {seletor}")
                            break
                    except:
                        continue
                
                if not opcoes_encontradas:
                    logger.error("[ERRO] Nenhuma opção encontrada no dropdown")
                    return False
                
                # Procurar a opção desejada
                for i, opcao in enumerate(opcoes_encontradas):
                    try:
                        texto_opcao = opcao.text.strip()
                        logger.info(f"   Processo {i+1}: '{texto_opcao}'")
                        
                        if "Naturalizar-se Brasileiro - Fluxo Principal - v.11" in texto_opcao:
                            logger.info("[TARGET] Encontrou a opção v.11! Clicando...")
                            opcao.click()
                            time.sleep(2)
                            
                            # Verificar se foi realmente selecionado
                            if self._verificar_selecao_processo():
                                logger.info("[OK] Processo v.11 selecionado com sucesso!")
                                return True
                                
                    except Exception as e:
                        logger.debug(f"Erro ao processar opção {i+1}: {str(e)}")
                        continue
                
                # Se não encontrou v.11, tentar outras versões
                logger.warning("[RELOAD] v.11 não encontrada, tentando outras versões...")
                for i, opcao in enumerate(opcoes_encontradas):
                    try:
                        texto_opcao = opcao.text.strip()
                        if "Naturalizar-se Brasileiro - Fluxo Principal" in texto_opcao and "v." in texto_opcao:
                            logger.info(f"[RELOAD] Tentando versão alternativa: {texto_opcao}")
                            opcao.click()
                            time.sleep(2)
                            
                            if self._verificar_selecao_processo_alternativo(texto_opcao):
                                logger.info(f"[OK] Processo alternativo selecionado: {texto_opcao}")
                                return True
                                
                    except Exception as e:
                        continue
                
            except Exception as e:
                logger.error(f"Erro ao buscar opções: {str(e)}")
            
            logger.error("[ERRO] Não foi possível selecionar nenhum processo")
            return False
            
        except Exception as e:
            logger.error(f"💥 Erro ao selecionar processo: {str(e)}")
            return False
    
    def _verificar_selecao_processo(self):
        """Verifica se o processo foi realmente selecionado procurando pelo div de confirmação"""
        try:
            # Procurar pelo div que aparece quando o processo é selecionado
            elemento_selecionado = self.driver.find_element(
                By.CSS_SELECTOR, 
                'div.ant-select-selection-selected-value[title="Naturalizar-se Brasileiro - Fluxo Principal - v.11"]'
            )
            
            if elemento_selecionado.is_displayed():
                logger.info("[BUSCA] Confirmado: Processo aparece como selecionado no HTML")
                return True
            else:
                logger.warning("[AVISO] Elemento encontrado mas não está visível")
                return False
                
        except Exception as e:
            logger.debug(f"Processo não confirmado como selecionado: {str(e)}")
            return False
    
    def _verificar_selecao_atividade(self):
        """Verifica se a atividade foi realmente selecionada procurando pelo div de confirmação"""
        try:
            # Procurar pelo div que aparece quando a atividade é selecionada
            elemento_selecionado = self.driver.find_element(
                By.CSS_SELECTOR, 
                'div.ant-select-selection-selected-value[title="Aprovar Parecer do Analista"]'
            )
            
            if elemento_selecionado.is_displayed():
                logger.info("[BUSCA] Confirmado: Atividade aparece como selecionada no HTML")
                return True
            else:
                logger.warning("[AVISO] Elemento encontrado mas não está visível")
                return False
                
        except Exception as e:
            logger.debug(f"Atividade não confirmada como selecionada: {str(e)}")
            return False
    
    def _verificar_selecao_processo_alternativo(self, texto_processo):
        """Verifica se um processo alternativo foi selecionado"""
        try:
            # Procurar pelo div que aparece quando o processo é selecionado
            elemento_selecionado = self.driver.find_element(
                By.CSS_SELECTOR, 
                f'div.ant-select-selection-selected-value[title="{texto_processo}"]'
            )
            
            if elemento_selecionado.is_displayed():
                logger.info(f"[BUSCA] Confirmado: Processo '{texto_processo}' aparece como selecionado no HTML")
                return True
            else:
                logger.warning("[AVISO] Elemento encontrado mas não está visível")
                return False
                
        except Exception as e:
            logger.debug(f"Processo alternativo não confirmado como selecionado: {str(e)}")
            return False
    
    def selecionar_atividade_aprovar_parecer(self):
        """Seleciona a atividade 'Aprovar Parecer do Analista'"""
        try:
            logger.info("[BUSCA] Iniciando seleção da atividade...")
            
            # 1. Primeiro, clicar no campo de atividade para abrir o dropdown
            try:
                logger.info("👆 Clicando no campo 'Atividades' para abrir dropdown...")
                
                # Tentar múltiplos seletores para o campo de atividade
                seletores_campo = [
                    '#filterSteps .ant-select-selection',
                    '#filterSteps',
                    '.form-filter-activity .ant-select-selection',
                    '.form-filter-activity',
                    'div[id="filterSteps"]'
                ]
                
                campo_clicado = False
                for seletor in seletores_campo:
                    try:
                        campo_atividade = self.driver.find_element(By.CSS_SELECTOR, seletor)
                        if campo_atividade.is_displayed():
                            campo_atividade.click()
                            logger.info(f"[OK] Campo de atividade clicado usando: {seletor}")
                            time.sleep(3)  # Aguardar mais tempo
                            campo_clicado = True
                            break
                    except:
                        continue
                
                if not campo_clicado:
                    logger.error("[ERRO] Não foi possível clicar no campo de atividade")
                    return False
                    
            except Exception as e:
                logger.warning(f"Erro ao clicar no campo atividade: {str(e)}")
                return False
            
            # 2. Aguardar dropdown aparecer e procurar a opção
            logger.info("[BUSCA] Aguardando dropdown de atividades aparecer...")
            time.sleep(2)
            
            # Buscar opções no dropdown com múltiplos seletores
            try:
                seletores_opcoes = [
                    'li.ant-select-dropdown-menu-item[role="option"]',
                    '.ant-select-dropdown-menu-item',
                    'li[role="option"]',
                    '.ant-dropdown-menu li'
                ]
                
                opcoes_encontradas = []
                for seletor in seletores_opcoes:
                    try:
                        opcoes = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                        if opcoes:
                            opcoes_encontradas = opcoes
                            logger.info(f"[INFO] {len(opcoes)} opções de atividade encontradas usando: {seletor}")
                            break
                    except:
                        continue
                
                if not opcoes_encontradas:
                    logger.error("[ERRO] Nenhuma opção de atividade encontrada no dropdown")
                    return False
                
                # Procurar a atividade desejada
                for i, opcao in enumerate(opcoes_encontradas):
                    try:
                        texto_opcao = opcao.text.strip()
                        logger.info(f"   Atividade {i+1}: '{texto_opcao}'")
                        
                        if "Aprovar Parecer do Analista" in texto_opcao:
                            logger.info("[TARGET] Encontrou a atividade! Clicando...")
                            opcao.click()
                            time.sleep(2)
                            
                            # Verificar se foi realmente selecionado
                            if self._verificar_selecao_atividade():
                                logger.info("[OK] Atividade selecionada com sucesso!")
                                return True
                                
                    except Exception as e:
                        logger.debug(f"Erro ao processar atividade {i+1}: {str(e)}")
                        continue
                
            except Exception as e:
                logger.error(f"Erro ao buscar atividades: {str(e)}")
            
            logger.error("[ERRO] Não foi possível selecionar a atividade")
            return False
            
        except Exception as e:
            logger.error(f"💥 Erro ao selecionar atividade: {str(e)}")
            return False
    
    def clicar_aplicar_filtros(self):
        """Clica no botão 'Aplicar filtros'"""
        try:
            logger.info("[BUSCA] Procurando botão 'Aplicar filtros'...")
            
            # Aguardar um momento
            time.sleep(1)
            
            # Buscar especificamente o botão com a classe e texto exato
            try:
                # Primeiro tentar encontrar o botão pela classe específica
                botao = self.driver.find_element(By.CSS_SELECTOR, 'button.ant-btn.bt-submit.ant-btn-primary')
                
                # Verificar se o texto do botão contém "Aplicar filtros"
                if "Aplicar filtros" in botao.text:
                    logger.info("[TARGET] Encontrou o botão 'Aplicar filtros' exato! Clicando...")
                    botao.click()
                    logger.info("[OK] Filtros aplicados!")
                    time.sleep(3)  # Aguardar carregamento dos resultados
                    return True
                    
            except Exception as e:
                logger.warning(f"Erro ao buscar botão por CSS selector: {str(e)}")
            
            # Se não encontrou com CSS, tentar XPath
            try:
                logger.info("[RELOAD] Tentando encontrar botão via XPath...")
                xpath_botao = self.driver.find_element(
                    By.XPATH, 
                    "//button[@class='ant-btn bt-submit ant-btn-primary' and .//span[text()='Aplicar filtros']]"
                )
                xpath_botao.click()
                logger.info("[OK] Botão aplicar filtros clicado via XPath!")
                time.sleep(3)
                return True
                
            except Exception as e:
                logger.warning(f"XPath para botão também falhou: {str(e)}")
            
            # Tentar busca mais flexível
            try:
                logger.info("[RELOAD] Tentando busca flexível para botão...")
                xpath_flexivel = self.driver.find_element(
                    By.XPATH, 
                    "//button[contains(@class, 'ant-btn') and contains(@class, 'bt-submit') and .//span[contains(text(), 'Aplicar filtros')]]"
                )
                xpath_flexivel.click()
                logger.info("[OK] Botão aplicar filtros clicado via busca flexível!")
                time.sleep(3)
                return True
                
            except Exception as e:
                logger.warning(f"Busca flexível para botão também falhou: {str(e)}")
            
            # Última tentativa - qualquer botão com "Aplicar"
            try:
                logger.info("[RELOAD] Última tentativa - qualquer botão com 'Aplicar'...")
                botao_qualquer = self.driver.find_element(
                    By.XPATH, 
                    "//button[contains(text(), 'Aplicar') or .//span[contains(text(), 'Aplicar')]]"
                )
                botao_qualquer.click()
                logger.info("[OK] Botão aplicar encontrado e clicado!")
                time.sleep(3)
                return True
                
            except Exception as e:
                logger.warning(f"Última tentativa também falhou: {str(e)}")
            
            logger.error("[ERRO] Não foi possível encontrar o botão 'Aplicar filtros'")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao aplicar filtros: {str(e)}")
            return False
    
    def obter_processos_da_tabela(self):
        """Obtém todos os processos da tabela atual"""
        try:
            logger.info("Obtendo processos da tabela (escopo: .ant-table-body)...")
            
            # Aguardar container do corpo da tabela visível
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '.ant-table-body'))
            )
            time.sleep(1)

            # Encontrar o container visível do body (evita tabelas fixas duplicadas)
            containers = self.driver.find_elements(By.CSS_SELECTOR, '.ant-table-body')
            container_visivel = None
            for c in containers:
                try:
                    if c.is_displayed():
                        container_visivel = c
                        break
                except Exception:
                    continue
            
            if not container_visivel:
                logger.warning("Container .ant-table-body não encontrado visível")
                return []
            
            # Buscar linhas apenas dentro do container visível
            linhas = container_visivel.find_elements(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
            logger.info(f"Encontradas {len(linhas)} linhas visíveis no corpo da tabela")
            
            processos = []
            hrefs_vistos = set()
            for i, linha in enumerate(linhas):
                try:
                    # Buscar link de "Aprovar Parecer do Analista"
                    link_elemento = linha.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                    href = link_elemento.get_attribute('href')
                    if not href or href in hrefs_vistos:
                        # Evitar duplicados (pode ocorrer com tabelas fixas)
                        continue
                    
                    # Extrair código do processo de forma robusta
                    codigo_processo = self._extrair_codigo_processo_de_href(href)
                    if not codigo_processo:
                        # Tentativa extra: ler a primeira coluna (código em texto)
                        try:
                            codigo_texto = linha.find_element(By.CSS_SELECTOR, 'td:nth-child(2) a').text.strip()
                            if codigo_texto:
                                codigo_processo = codigo_texto
                        except Exception:
                            pass
                    if not codigo_processo:
                        codigo_processo = 'DESCONHECIDO'
                    
                    hrefs_vistos.add(href)
                    logger.info(f"→ Processo: {codigo_processo}")
                    processos.append({
                        'codigo': codigo_processo,
                        'href': href,
                        'linha_index': i
                    })
                    
                except NoSuchElementException:
                    # Linha não contém processo de "Aprovar Parecer do Analista"
                    continue
                except Exception as e:
                    logger.warning(f"Erro ao processar linha {i}: {str(e)}")
                    continue
            
            logger.info(f"[OK] Encontrados {len(processos)} processos para aprovação de parecer")
            # Listagem resumida dos códigos encontrados para conferência
            try:
                codigos_preview = ', '.join([p.get('codigo', '') for p in processos[:10]])
                logger.info(f"Primeiros 10 processos: {codigos_preview}")
            except Exception:
                pass
            return processos
            
        except Exception as e:
            logger.error(f"Erro ao obter processos da tabela: {str(e)}")
            return []
    
    def navegar_para_processo(self, processo):
        """Navega para um processo específico"""
        try:
            logger.info(f"Navegando para processo {processo['codigo']}...")
            
            # Navegar para a URL do processo
            self.driver.get(processo['href'])
            time.sleep(2)
            
            # Aguardar carregamento da página
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            logger.info(f"[OK] Navegação para processo {processo['codigo']} concluída")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao navegar para processo {processo['codigo']}: {str(e)}")
            return False
    
    def extrair_data_inicio_processo(self):
        """Extrai a data de início do processo"""
        try:
            # Buscar elemento com data de início
            data_elemento = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.seletores['data_inicio_atividade']))
            )
            
            texto_data = data_elemento.text
            # Extrair data do texto "• Início em 08/09/2025 11:24"
            if "Início em" in texto_data:
                data_str = texto_data.split("Início em ")[1].split(" ")[0]
                logger.info(f"Data de início extraída: {data_str}")
                return data_str
            
            return None
            
        except Exception as e:
            logger.warning(f"Erro ao extrair data de início: {str(e)}")
            return None
    
    def navegar_para_iframe(self):
        """Navega para a URL do iframe do formulário"""
        try:
            logger.info("Aguardando iframe aparecer...")
            
            # Aguardar o iframe aparecer
            iframe = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.seletores['iframe_form_app']))
            )
            
            # Extrair a URL do iframe
            iframe_src = iframe.get_attribute('src')
            logger.info(f"URL do iframe encontrada: {iframe_src}")
            
            # Navegar diretamente para a URL do iframe na aba atual
            self.driver.get(iframe_src)
            logger.info("[OK] Navegação para URL do formulário concluída")
            
            # Aguardar carregamento
            time.sleep(3)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar iframe: {str(e)}")
            return False
    
    def extrair_dados_formulario(self):
        """Extrai dados do formulário para análise"""
        try:
            logger.info("Extraindo dados do formulário...")
            
            # Aguardar carregamento do formulário
            time.sleep(2)
            
            dados = {}
            
            # Extrair parecer da PF
            try:
                parecer_pf_elementos = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['parecer_pf'])
                for elemento in parecer_pf_elementos:
                    if elemento.get_attribute('aria-checked') == 'true':
                        dados['parecer_pf'] = elemento.text.strip()
                        break
                else:
                    dados['parecer_pf'] = "Não encontrado"
            except Exception as e:
                logger.warning(f"Erro ao extrair parecer PF: {str(e)}")
                dados['parecer_pf'] = "Erro na extração"
            
            # Extrair parecer do MJ
            try:
                parecer_mj_elemento = self.driver.find_element(By.CSS_SELECTOR, self.seletores['parecer_mj'])
                dados['parecer_mj'] = parecer_mj_elemento.get_attribute('value') or parecer_mj_elemento.get_attribute('title') or "Não encontrado"
            except Exception as e:
                logger.warning(f"Erro ao extrair parecer MJ: {str(e)}")
                dados['parecer_mj'] = "Erro na extração"
            
            # Extrair status da biometria
            try:
                biometria_elementos = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['biometria'])
                for elemento in biometria_elementos:
                    if elemento.get_attribute('aria-checked') == 'true':
                        dados['biometria'] = elemento.text.strip()
                        break
                else:
                    dados['biometria'] = "Não encontrado"
            except Exception as e:
                logger.warning(f"Erro ao extrair biometria: {str(e)}")
                dados['biometria'] = "Erro na extração"
            
            # Extrair tipo de naturalização
            try:
                tipo_nat_elementos = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['tipo_naturalizacao'])
                for elemento in tipo_nat_elementos:
                    if elemento.get_attribute('aria-checked') == 'true':
                        dados['tipo_naturalizacao'] = elemento.text.strip()
                        break
                else:
                    dados['tipo_naturalizacao'] = "Não encontrado"
            except Exception as e:
                logger.warning(f"Erro ao extrair tipo de naturalização: {str(e)}")
                dados['tipo_naturalizacao'] = "Erro na extração"
            
            # Extrair data de nascimento
            try:
                data_nasc_elemento = self.driver.find_element(By.CSS_SELECTOR, self.seletores['data_nascimento'])
                dados['data_nascimento'] = data_nasc_elemento.get_attribute('value') or "Não encontrado"
            except Exception as e:
                logger.warning(f"Erro ao extrair data de nascimento: {str(e)}")
                dados['data_nascimento'] = "Erro na extração"
            
            logger.info(f"[OK] Dados extraídos:")
            logger.info(f"   - Parecer PF: {dados.get('parecer_pf', 'N/A')}")
            logger.info(f"   - Parecer MJ: {dados.get('parecer_mj', 'N/A')}")
            logger.info(f"   - Biometria: {dados.get('biometria', 'N/A')}")
            logger.info(f"   - Tipo Naturalização: {dados.get('tipo_naturalizacao', 'N/A')}")
            logger.info(f"   - Data Nascimento: {dados.get('data_nascimento', 'N/A')}")
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao extrair dados do formulário: {str(e)}")
            return {}
    
    def calcular_idade(self, data_nascimento, data_referencia=None):
        """Calcula a idade baseada na data de nascimento"""
        try:
            if not data_referencia:
                data_referencia = datetime.now()
            elif isinstance(data_referencia, str):
                # Converter string de data para datetime (formato DD/MM/YYYY)
                data_referencia = datetime.strptime(data_referencia, "%d/%m/%Y")
            
            # Converter data de nascimento (formato DD/MM/YYYY)
            if isinstance(data_nascimento, str):
                data_nasc = datetime.strptime(data_nascimento, "%d/%m/%Y")
            else:
                data_nasc = data_nascimento
            
            idade = data_referencia.year - data_nasc.year
            
            # Ajustar se ainda não fez aniversário no ano
            if (data_referencia.month, data_referencia.day) < (data_nasc.month, data_nasc.day):
                idade -= 1
            
            return idade
            
        except Exception as e:
            logger.error(f"Erro ao calcular idade: {str(e)}")
            return None
    
    def analisar_requisitos(self, dados, data_inicio=None):
        """Analisa os requisitos para aprovação automática"""
        try:
            logger.info("[BUSCA] Iniciando análise de requisitos...")
            resultado = {
                'pode_aprovar_automaticamente': False,
                'motivo_analise_manual': [],
                'status': 'ANÁLISE MANUAL'
            }
            
            # Verificar se pareceres PF e MJ são iguais
            parecer_pf = dados.get('parecer_pf', '').strip()
            parecer_mj = dados.get('parecer_mj', '').strip()
            
            logger.info(f"[BUSCA] Analisando pareceres: PF='{parecer_pf}' | MJ='{parecer_mj}'")
            
            if not parecer_pf or not parecer_mj:
                resultado['motivo_analise_manual'].append("Parecer PF ou MJ não encontrado")
                logger.warning("[ERRO] Parecer PF ou MJ não encontrado")
                return resultado
            
            # Coletar campos necessários para exceções e validações
            biometria = dados.get('biometria', '').strip()
            tipo_naturalizacao = dados.get('tipo_naturalizacao', '').strip()
            
            # ===== EXCEÇÕES ESPECÍFICAS (têm prioridade sobre validações normais) =====
            # 1) PF e MJ = Indeferimento e biometria NÃO coletada -> ENVIAR PARA CPMIG
            if (
                parecer_pf == "Propor Indeferimento"
                and parecer_mj == "Propor Indeferimento"
                and biometria not in ["Sim", "Não se aplica"]
            ):
                logger.info("[TARGET] EXCEÇÃO: Indeferimento (PF e MJ) + biometria não coletada → ENVIAR PARA CPMIG")
                resultado['pode_aprovar_automaticamente'] = True
                resultado['status'] = 'ENVIAR PARA CPMIG'
                return resultado
            
            # 2) Tipo Provisória + pareceres iguais + biometria NÃO coletada -> ENVIAR PARA CPMIG
            if (
                tipo_naturalizacao == "Provisória"
                and parecer_pf == parecer_mj
                and biometria not in ["Sim", "Não se aplica"]
            ):
                logger.info("[TARGET] EXCEÇÃO: Provisória + pareceres iguais + biometria não coletada → ENVIAR PARA CPMIG")
                resultado['pode_aprovar_automaticamente'] = True
                resultado['status'] = 'ENVIAR PARA CPMIG'
                return resultado
            
            # 3) PF = Propor Arquivamento e MJ = Propor Indeferimento -> ENVIAR PARA CPMIG
            if parecer_pf == "Propor Arquivamento" and parecer_mj == "Propor Indeferimento":
                logger.info("[TARGET] EXCEÇÃO: PF Arquivamento + MJ Indeferimento → ENVIAR PARA CPMIG")
                resultado['pode_aprovar_automaticamente'] = True
                resultado['status'] = 'ENVIAR PARA CPMIG'
                return resultado
            
            if parecer_pf != parecer_mj:
                resultado['motivo_analise_manual'].append("Pareceres PF e MJ divergentes")
                logger.warning("[ERRO] Pareceres PF e MJ divergentes")
                return resultado
            
            logger.info("[OK] Pareceres PF e MJ são iguais")
            
            # Verificar se é um parecer válido (qualquer proposta é aceita desde que sejam iguais)
            pareceres_validos = ["Propor Deferimento", "Propor Indeferimento", "Propor Arquivamento"]
            if not any(parecer_valido in parecer_pf for parecer_valido in pareceres_validos):
                resultado['motivo_analise_manual'].append("Parecer PF não é uma proposta válida")
                logger.warning(f"[ERRO] Parecer PF não é válido: '{parecer_pf}'")
                return resultado
            
            logger.info(f"[OK] Parecer válido: '{parecer_pf}'")
            
            # Verificar biometria (aceita "Sim" ou "Não se aplica")
            logger.info(f"[BUSCA] Verificando biometria: '{biometria}'")
            
            if biometria not in ["Sim", "Não se aplica"]:
                resultado['motivo_analise_manual'].append("Biometria não coletada ou inválida")
                logger.warning(f"[ERRO] Biometria inválida: '{biometria}'")
                return resultado
            
            logger.info(f"[OK] Biometria válida: '{biometria}'")
            
            # Verificar idade APENAS se ambos os pareceres forem "Propor Deferimento"
            if parecer_pf == "Propor Deferimento" and parecer_mj == "Propor Deferimento":
                logger.info("[BUSCA] Pareceres são de deferimento - validando idade...")
                
                data_nascimento = dados.get('data_nascimento', '').strip()
                
                logger.info(f"[BUSCA] Verificando idade: Tipo='{tipo_naturalizacao}' | Data Nascimento='{data_nascimento}'")
                
                if not data_nascimento or data_nascimento == "Não encontrado":
                    resultado['motivo_analise_manual'].append("Data de nascimento não encontrada")
                    logger.warning("[ERRO] Data de nascimento não encontrada")
                    return resultado
                
                try:
                    idade = self.calcular_idade(data_nascimento, data_inicio)
                    if idade is None:
                        resultado['motivo_analise_manual'].append("Erro ao calcular idade")
                        logger.warning("[ERRO] Erro ao calcular idade")
                        return resultado
                    
                    logger.info(f"[BUSCA] Idade calculada: {idade} anos para tipo '{tipo_naturalizacao}'")
                    
                    # Validar idade conforme tipo de naturalização
                    if tipo_naturalizacao == "Ordinária" and idade < 18:
                        resultado['motivo_analise_manual'].append(f"Idade insuficiente para Ordinária: {idade} anos")
                        logger.warning(f"[ERRO] Idade insuficiente para Ordinária: {idade} anos (precisa ≥18)")
                        return resultado
                    elif tipo_naturalizacao == "Extraordinária" and idade < 18:
                        resultado['motivo_analise_manual'].append(f"Idade insuficiente para Extraordinária: {idade} anos")
                        logger.warning(f"[ERRO] Idade insuficiente para Extraordinária: {idade} anos (precisa ≥18)")
                        return resultado
                    elif tipo_naturalizacao == "Provisória" and idade > 17:
                        resultado['motivo_analise_manual'].append(f"Idade excessiva para Provisória: {idade} anos")
                        logger.warning(f"[ERRO] Idade excessiva para Provisória: {idade} anos (precisa ≤17)")
                        return resultado
                    elif tipo_naturalizacao == "Definitiva" and (idade < 18 or idade > 20):
                        resultado['motivo_analise_manual'].append(f"Idade inválida para Definitiva: {idade} anos")
                        logger.warning(f"[ERRO] Idade inválida para Definitiva: {idade} anos (precisa entre 18-20)")
                        return resultado
                    
                    logger.info(f"[OK] Idade válida: {idade} anos para tipo '{tipo_naturalizacao}'")
                        
                except Exception as e:
                    resultado['motivo_analise_manual'].append(f"Erro na validação de idade: {str(e)}")
                    logger.warning(f"[ERRO] Erro na validação de idade: {str(e)}")
                    return resultado
            else:
                logger.info("ℹ️ Pareceres não são de deferimento - pulando validação de idade")
            
            # Se chegou até aqui, pode aprovar automaticamente
            logger.info("[SUCCESS] TODOS OS REQUISITOS ATENDIDOS - APROVAÇÃO AUTOMÁTICA!")
            resultado['pode_aprovar_automaticamente'] = True
            resultado['status'] = 'ENVIAR PARA CPMIG'
            resultado['motivo_analise_manual'] = []
            
            return resultado
            
        except Exception as e:
            logger.error(f"Erro ao analisar requisitos: {str(e)}")
            return {
                'pode_aprovar_automaticamente': False,
                'motivo_analise_manual': [f"Erro na análise: {str(e)}"],
                'status': 'ANÁLISE MANUAL'
            }
    
    def processar_processo_individual(self, processo):
        """Processa um processo individual"""
        try:
            logger.info(f"[RELOAD] Processando processo {processo['codigo']}...")
            
            # Navegar para o processo
            if not self.navegar_para_processo(processo):
                logger.warning(f"Falha ao navegar para processo {processo['codigo']}, mas continuando...")
                return False
            
            # Extrair data de início
            data_inicio = self.extrair_data_inicio_processo()
            
            # Navegar para o iframe do formulário
            if not self.navegar_para_iframe():
                logger.warning(f"Falha ao navegar para iframe do processo {processo['codigo']}, mas continuando...")
                return False
            
            # Extrair dados do formulário
            dados = self.extrair_dados_formulario()
            if not dados:
                logger.warning(f"Falha ao extrair dados do processo {processo['codigo']}, mas continuando...")
                # Criar resultado com dados incompletos
                resultado = {
                    'processo': processo['codigo'],
                    'data_inicio': data_inicio or 'N/A',
                    'parecer_pf': 'Erro na extração',
                    'parecer_mj': 'Erro na extração',
                    'biometria': 'Erro na extração',
                    'tipo_naturalizacao': 'Erro na extração',
                    'data_nascimento': 'Erro na extração',
                    'status': 'ANÁLISE MANUAL',
                    'motivo_analise_manual': 'Erro ao extrair dados do formulário',
                    'timestamp_processamento': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
                self.resultados_processamento.append(resultado)
                return False
            
            # Analisar requisitos
            logger.info(f"[BUSCA] Iniciando análise para processo {processo['codigo']}...")
            logger.info(f"[DADOS] Dados extraídos: {dados}")
            analise = self.analisar_requisitos(dados, data_inicio)
            logger.info(f"[INFO] Resultado da análise: {analise}")
            
            # Tomar decisão automática se aplicável
            decisao_executada = self.tomar_decisao_automatica(analise['status'])
            
            # Salvar resultado
            resultado = {
                'processo': processo['codigo'],
                'data_inicio': data_inicio,
                'parecer_pf': dados.get('parecer_pf', 'N/A'),
                'parecer_mj': dados.get('parecer_mj', 'N/A'),
                'biometria': dados.get('biometria', 'N/A'),
                'tipo_naturalizacao': dados.get('tipo_naturalizacao', 'N/A'),
                'data_nascimento': dados.get('data_nascimento', 'N/A'),
                'status': analise['status'],
                'decisao_automatica': 'Sim' if decisao_executada and analise['status'] == 'ENVIAR PARA CPMIG' else 'Não',
                'motivo_analise_manual': '; '.join(analise['motivo_analise_manual']) if analise['motivo_analise_manual'] else '',
                'timestamp_processamento': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            }
            
            self.resultados_processamento.append(resultado)
            
            # Salvar planilha a cada processo processado
            logger.info(f"[NOTA] Incluindo no relatório/planilha: processo {resultado['processo']}")
            self.salvar_planilha_incremental()
            
            status_msg = f"Status: {analise['status']}"
            if analise['status'] == 'ENVIAR PARA CPMIG':
                status_msg += f" - Decisão automática: {'[OK] Executada' if decisao_executada else '[ERRO] Falhou'}"
            
            logger.info(f"[OK] Processo {processo['codigo']} processado - {status_msg}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar processo {processo['codigo']}: {str(e)}")
            # Mesmo com erro, salvar resultado para não perder o processo
            try:
                resultado = {
                    'processo': processo['codigo'],
                    'data_inicio': 'N/A',
                    'parecer_pf': 'Erro na extração',
                    'parecer_mj': 'Erro na extração',
                    'biometria': 'Erro na extração',
                    'tipo_naturalizacao': 'Erro na extração',
                    'data_nascimento': 'Erro na extração',
                    'status': 'ANÁLISE MANUAL',
                    'motivo_analise_manual': f'Erro durante processamento: {str(e)}',
                    'timestamp_processamento': datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                }
                self.resultados_processamento.append(resultado)
            except:
                pass  # Se não conseguir nem salvar o erro, continua
            return False
    
    def processar_todos_processos_pagina(self):
        """Processa todos os processos da página atual, verificando múltiplas vezes se necessário"""
        try:
            logger.info("[INFO] Processando todos os processos da página atual...")
            
            processos_processados_na_pagina = set()
            tentativas_sem_novos_processos = 0
            max_tentativas_sem_novos = 3
            total_processados = 0
            
            while tentativas_sem_novos_processos < max_tentativas_sem_novos:
                # Obter processos atuais da página
                processos = self.obter_processos_da_tabela()
                if not processos:
                    logger.warning("Nenhum processo encontrado na página")
                    break
                
                # Filtrar processos que ainda não foram processados
                processos_novos = [p for p in processos if p['codigo'] not in processos_processados_na_pagina]
                
                if not processos_novos:
                    logger.info(f"[INFO] Nenhum processo novo encontrado (tentativa {tentativas_sem_novos_processos + 1}/{max_tentativas_sem_novos})")
                    tentativas_sem_novos_processos += 1
                    time.sleep(3)  # Aguardar um pouco antes de verificar novamente
                    continue
                
                logger.info(f"[INFO] Encontrados {len(processos_novos)} processos novos nesta verificação")
                tentativas_sem_novos_processos = 0  # Reset contador pois encontrou novos processos
                
                processos_analisados_nesta_rodada = 0
                processos_pulados_nesta_rodada = 0
                
                for i, processo in enumerate(processos_novos, 1):
                    try:
                        logger.info(f"[RELOAD] Processando {i}/{len(processos_novos)}: {processo['codigo']}")
                        
                        # Processar o processo individual
                        if self.processar_processo_individual(processo):
                            processos_analisados_nesta_rodada += 1
                            total_processados += 1
                            logger.info(f"[OK] Processo {processo['codigo']} processado com sucesso")
                        else:
                            processos_pulados_nesta_rodada += 1
                            logger.warning(f"[AVISO] Processo {processo['codigo']} processado com problemas")
                        
                        # Marcar como processado independente do resultado
                        processos_processados_na_pagina.add(processo['codigo'])
                        
                        # Voltar para a Caixa de Entrada antes do próximo processo
                        if i < len(processos_novos):  # Não fazer no último processo da rodada
                            logger.info("[VOLTA] Voltando para Caixa de Entrada...")
                            if not self.voltar_para_caixa_entrada():
                                logger.warning("Falha ao voltar para Caixa de Entrada")
                        
                        # Pequena pausa entre processos
                        time.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Erro ao processar processo {processo['codigo']}: {str(e)}")
                        # Marcar como processado mesmo com erro para não tentar novamente
                        processos_processados_na_pagina.add(processo['codigo'])
                        processos_pulados_nesta_rodada += 1
                        
                        # Tentar voltar para caixa de entrada mesmo com erro
                        try:
                            if i < len(processos_novos):
                                self.voltar_para_caixa_entrada()
                        except:
                            pass
                        continue
                
                logger.info(f"[DADOS] Rodada concluída: {processos_analisados_nesta_rodada} analisados, {processos_pulados_nesta_rodada} pulados")
                
                # Se não analisou nenhum processo nesta rodada, incrementar contador
                if processos_analisados_nesta_rodada == 0:
                    tentativas_sem_novos_processos += 1
                    logger.info(f"[AVISO] Nenhum processo analisado nesta rodada - pode ser que restam apenas análises manuais")
                
                # Pequena pausa antes da próxima verificação
                time.sleep(2)
            
            logger.info(f"[OK] Página processada completamente: {total_processados} processos únicos processados")
            return total_processados > 0
            
        except Exception as e:
            logger.error(f"Erro ao processar página: {str(e)}")
            return False
    
    def voltar_para_caixa_entrada(self):
        """Volta para a página da Caixa de Entrada"""
        try:
            logger.info("Voltando para Caixa de Entrada...")
            
            # Navegar para workspace primeiro
            if not self.navegar_para_workspace():
                return False
            
            # Clicar em Caixa de entrada novamente
            if not self.clicar_caixa_entrada():
                return False
            
            logger.info("[OK] Voltou para Caixa de Entrada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao voltar para Caixa de Entrada: {str(e)}")
            return False
    
    def navegar_proxima_pagina(self):
        """Navega para a próxima página da tabela"""
        try:
            logger.info("Tentando navegar para próxima página...")
            
            # Verificar se estamos na página correta (Caixa de entrada/Minhas atividades)
            try:
                self.driver.find_element(By.CSS_SELECTOR, '.ant-table-body')
                logger.info("[OK] Confirmado: estamos na página de atividades")
            except Exception:
                logger.warning("[AVISO] Não estamos na página de atividades, tentando voltar...")
                if not self.voltar_para_caixa_entrada():
                    logger.error("[ERRO] Falha ao voltar para página de atividades")
                    return False
            
            # Capturar uma assinatura simples do primeiro href da página atual
            assinatura_atual = None
            try:
                container = self.driver.find_element(By.CSS_SELECTOR, '.ant-table-body')
                primeira_linha = container.find_element(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
                link = primeira_linha.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                assinatura_atual = link.get_attribute('href')
                logger.info(f"[INFO] Página atual: {assinatura_atual.split('/')[-1] if assinatura_atual else 'N/A'}")
            except Exception:
                logger.debug("Não foi possível capturar assinatura da página atual")

            # 1) Tentar clicar no link de paginação explícito e alternativas
            try:
                seletores_next = [
                    'a.pagination.next-page',
                    'a[title=""].pagination.next-page', 
                    'li.ant-pagination-next a',
                    'li.ant-pagination-next button',
                    'button[aria-label="Next Page"]'
                ]
                
                logger.info("[BUSCA] Procurando botão de próxima página...")
                btn_next = None
                
                for i, sel in enumerate(seletores_next):
                    try:
                        candidatos = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        logger.info(f"  Seletor {i+1} '{sel}': {len(candidatos)} elementos encontrados")
                        
                        for j, cand in enumerate(candidatos):
                            try:
                                classes = (cand.get_attribute('class') or '').lower()
                                aria_dis = (cand.get_attribute('aria-disabled') or '').lower()
                                is_displayed = cand.is_displayed()
                                
                                logger.info(f"    Elemento {j+1}: displayed={is_displayed}, classes='{classes}', aria-disabled='{aria_dis}'")
                                
                                if not is_displayed:
                                    continue
                                if 'disabled' in classes or aria_dis == 'true':
                                    logger.info(f"    Elemento {j+1} está desabilitado")
                                    continue
                                    
                                btn_next = cand
                                logger.info(f"[OK] Botão de próxima página encontrado com seletor '{sel}'")
                                break
                            except Exception as e:
                                logger.debug(f"    Erro ao verificar elemento {j+1}: {str(e)}")
                                continue
                        if btn_next:
                            break
                    except Exception as e:
                        logger.debug(f"  Erro com seletor '{sel}': {str(e)}")
                        continue

                if btn_next:
                    try:
                        self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', btn_next)
                        time.sleep(0.2)
                        self.driver.execute_script('arguments[0].click();', btn_next)
                    except Exception:
                        btn_next.click()
                    logger.info("[OK] Próxima página (botão de paginação) clicado, aguardando mudança...")
                    # aguardar mudança
                    mudou = False
                    for _ in range(40):  # ~8s
                        time.sleep(0.2)
                        try:
                            container2 = self.driver.find_element(By.CSS_SELECTOR, '.ant-table-body')
                            primeira_linha2 = container2.find_element(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
                            link2 = primeira_linha2.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                            assinatura_nova = link2.get_attribute('href')
                            if assinatura_nova and assinatura_nova != assinatura_atual:
                                mudou = True
                                break
                        except Exception:
                            continue
                    if not mudou:
                        logger.info("[AVISO] Conteúdo não mudou após clicar próxima página (pode ser última página)")
                        return False
                    time.sleep(1)
                    return True
            except Exception as e:
                logger.warning(f"Erro ao procurar botão de paginação: {str(e)}")

                if not btn_next:
                    logger.info("[ERRO] Botão de próxima página não encontrado ou está desabilitado")
                    return False

            # 2) Fallback: buscar seta SVG de próxima página
            proxima_elementos = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['proximo_pagina'])
            for elemento in proxima_elementos:
                try:
                    path = elemento.find_element(By.TAG_NAME, 'path')
                    if "M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" in path.get_attribute('d'):
                        botao_container = elemento.find_element(By.XPATH, './../..')
                        botao_container.click()
                        logger.info("[OK] Próxima página (ícone) clicado, aguardando mudança...")
                        mudou = False
                        for _ in range(30):
                            time.sleep(0.2)
                            try:
                                container2 = self.driver.find_element(By.CSS_SELECTOR, '.ant-table-body')
                                primeira_linha2 = container2.find_element(By.CSS_SELECTOR, 'tbody.ant-table-tbody > tr.ant-table-row')
                                link2 = primeira_linha2.find_element(By.CSS_SELECTOR, self.seletores['link_aprovar_parecer'])
                                assinatura_nova = link2.get_attribute('href')
                                if assinatura_nova and assinatura_nova != assinatura_atual:
                                    mudou = True
                                    break
                            except Exception:
                                continue
                        if not mudou:
                            logger.info("[AVISO] Conteúdo não mudou após clicar próxima página (provável última página)")
                            return False
                        time.sleep(1)
                        return True
                except Exception:
                    continue
            
            logger.info("Não há próxima página ou botão não encontrado")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao navegar para próxima página: {str(e)}")
            return False
    
    def gerar_planilha_resultados(self):
        """Gera planilha com os resultados processados (conforme LGPD)"""
        try:
            if not self.resultados_processamento:
                logger.warning("Nenhum resultado para gerar planilha")
                return False
            
            logger.info(f"Gerando planilha com {len(self.resultados_processamento)} processos...")
            
            # Criar DataFrame com dados anonimizados conforme LGPD
            df = pd.DataFrame(self.resultados_processamento)
            
            # Aplicar mascaramento básico de dados sensíveis
            df['data_nascimento_mascarada'] = df['data_nascimento'].apply(self._mascarar_data_nascimento)
            
            # Remover dados sensíveis desnecessários para o relatório
            colunas_relatorio = [
                'processo',
                'parecer_pf', 
                'parecer_mj',
                'biometria',
                'tipo_naturalizacao',
                'status',
                'decisao_automatica',
                'motivo_analise_manual',
                'timestamp_processamento'
            ]
            
            df_relatorio = df[colunas_relatorio].copy()
            
            # Gerar nome do arquivo com timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo = f"aprovacao_parecer_analista_{timestamp}.xlsx"
            
            # Criar caminho completo do arquivo
            import os
            caminho_completo = os.path.abspath(nome_arquivo)
            
            # Salvar planilha
            df_relatorio.to_excel(caminho_completo, index=False, engine='openpyxl')
            
            # Verificar se arquivo foi criado
            if os.path.exists(caminho_completo):
                # Log de resumo
                total_processos = len(df_relatorio)
                processos_cpmig = len(df_relatorio[df_relatorio['status'] == 'ENVIAR PARA CPMIG'])
                processos_manual = len(df_relatorio[df_relatorio['status'] == 'ANÁLISE MANUAL'])
                
                logger.info(f"[OK] Planilha gerada com sucesso: {nome_arquivo}")
                logger.info(f"[PASTA] Caminho completo: {caminho_completo}")
                logger.info(f"[DADOS] Resumo: {total_processos} processos | {processos_cpmig} para CPMIG | {processos_manual} análise manual")
                
                return {
                    'nome_arquivo': nome_arquivo,
                    'caminho_completo': caminho_completo,
                    'total_processos': total_processos,
                    'processos_cpmig': processos_cpmig,
                    'processos_manual': processos_manual
                }
            else:
                logger.error("Arquivo não foi criado")
                return False
            
        except Exception as e:
            logger.error(f"Erro ao gerar planilha: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def salvar_planilha_incremental(self):
        """Salva a planilha a cada processo processado (salvamento incremental)"""
        try:
            if not self.resultados_processamento:
                return False
            
            # Criar DataFrame com dados
            df = pd.DataFrame(self.resultados_processamento)
            
            # Aplicar mascaramento básico de dados sensíveis
            if 'data_nascimento' in df.columns:
                df['data_nascimento_mascarada'] = df['data_nascimento'].apply(self._mascarar_data_nascimento)
            
            # Colunas para o relatório
            colunas_relatorio = [
                'processo',
                'parecer_pf', 
                'parecer_mj',
                'biometria',
                'tipo_naturalizacao',
                'status',
                'decisao_automatica',
                'motivo_analise_manual',
                'timestamp_processamento'
            ]
            
            df_relatorio = df[colunas_relatorio].copy()
            
            # Nome do arquivo fixo (sempre sobrescreve)
            nome_arquivo = "aprovacao_parecer_analista_atual.xlsx"
            
            # Salvar planilha
            df_relatorio.to_excel(nome_arquivo, index=False, engine='openpyxl')
            
            # Salvar o caminho do arquivo para uso posterior
            import os
            self.arquivo_planilha_atual = os.path.abspath(nome_arquivo)
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro no salvamento incremental: {str(e)}")
            return False
    
    def _mascarar_data_nascimento(self, data):
        """Aplica mascaramento básico na data de nascimento (LGPD)"""
        try:
            if data and data != "Não encontrado" and data != "Erro na extração":
                # Mostrar apenas ano para preservar privacidade
                if "/" in data:
                    partes = data.split("/")
                    if len(partes) == 3:
                        return f"XX/XX/{partes[2]}"
            return data
        except:
            return data
    
    def executar_aprovacao_completa(self):
        """Executa o processo completo de aprovação de parecer do analista"""
        try:
            logger.info("[EXEC] === INICIANDO AUTOMAÇÃO DE APROVAÇÃO DE PARECER DO ANALISTA ===")
            logger.info(f"[INFO] Modo de seleção: {self.modo_selecao}")
            
            # Fazer login se necessário
            if not self.fazer_login():
                logger.error("[ERRO] Falha no login - interrompendo automação")
                return False
            
            # Executar baseado no modo selecionado
            if self.modo_selecao == 'planilha':
                return self.executar_aprovacao_por_planilha()
            else:
                return self.executar_aprovacao_por_versao()
            
        except Exception as e:
            logger.error(f"[ERRO] Erro na execução da automação: {str(e)}", exc_info=True)
            return False
    
    def executar_aprovacao_por_versao(self):
        """Executa aprovação no modo de seleção por versão (modo original)"""
        try:
            logger.info("[RELOAD] Executando aprovação por versão...")
            
            # 2. Navegar para workspace
            current_url = self.driver.current_url
            if 'workspace' not in current_url.lower():
                if not self.navegar_para_workspace():
                    return False
            
            # 3. Clicar em Caixa de entrada
            if not self.clicar_caixa_entrada():
                return False
            
            # 4. Aplicar filtros na Caixa de Entrada
            if not self.aplicar_filtros_caixa_entrada():
                return False
            
            # 5. Processar todas as páginas
            pagina_atual = 1
            while True:
                logger.info(f"[DOC] Processando página {pagina_atual}...")
                
                # Processar todos os processos da página atual (com verificação múltipla)
                if not self.processar_todos_processos_pagina():
                    logger.warning(f"Falha ao processar página {pagina_atual}")
                
                # Verificar se ainda há processos novos na página atual antes de tentar próxima página
                logger.info("[RELOAD] Verificando se ainda há processos não processados na página atual...")
                
                # Aguardar um pouco para estabilizar a página
                time.sleep(3)
                
                # Obter lista atual de processos
                processos_atuais = self.obter_processos_da_tabela()
                if processos_atuais:
                    logger.info(f"[INFO] Ainda há {len(processos_atuais)} processos na página - continuando verificação...")
                    
                    # Fazer uma última verificação para ver se há processos pendentes
                    # (isso é feito dentro do próprio processar_todos_processos_pagina)
                    # Se não conseguir processar mais nenhum, vai para próxima página
                    continue_mesma_pagina = self.processar_todos_processos_pagina()
                    
                    if continue_mesma_pagina:
                        logger.info("[INFO] Mais processos foram encontrados e processados na mesma página")
                        continue  # Continua no loop sem incrementar página
                
                # Tentar navegar para próxima página
                logger.info("[RELOAD] Tentando navegar para próxima página...")
                if not self.navegar_proxima_pagina():
                    logger.info("[OK] Não há mais páginas para processar - finalizando")
                    break
                
                pagina_atual += 1
            
            # 6. Gerar planilha com resultados
            logger.info("🗂️ Gerando planilha de resultados...")
            arquivo_planilha = self.gerar_planilha_resultados()
            
            if arquivo_planilha:
                if isinstance(arquivo_planilha, dict):
                    logger.info(f"[OK] Planilha gerada: {arquivo_planilha['nome_arquivo']}")
                    logger.info(f"[DADOS] {arquivo_planilha['total_processos']} processos processados")
                    logger.info(f"[PASTA] Arquivo salvo em: {arquivo_planilha['caminho_completo']}")
                else:
                    logger.info(f"[OK] Planilha gerada: {arquivo_planilha}")
                
                logger.info("[OK] Processo de aprovação de parecer do analista concluído com sucesso!")
                return True
            else:
                # Mesmo sem planilha, o processo pode ter sido executado
                if self.resultados_processamento:
                    logger.warning("[AVISO] Processo concluído mas houve problema na geração da planilha")
                    logger.info(f"[INFO] {len(self.resultados_processamento)} processos foram processados")
                    return True
                else:
                    logger.error("[ERRO] Nenhum processo foi processado")
                    return False
            
        except Exception as e:
            logger.error(f"Erro durante execução completa: {str(e)}")
            return False
    
    def parar_execucao(self):
        """Para a execução, fecha o driver e gera planilha final"""
        try:
            logger.info("🛑 Parando execução...")
            
            # Gerar planilha final com dados processados até agora
            if self.resultados_processamento:
                arquivo_final = self.gerar_planilha_resultados()
                if arquivo_final:
                    logger.info(f"[DADOS] Planilha final gerada: {arquivo_final}")
                else:
                    logger.warning("[AVISO] Não foi possível gerar planilha final")
            else:
                logger.info("📭 Nenhum processo foi processado")
            
            # Fechar driver
            self.fechar()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao parar execução: {str(e)}")
            return False
    
    def fechar(self):
        """Fecha o driver e limpa recursos"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                logger.info("[OK] Driver fechado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao fechar driver: {str(e)}")

    # =====================
    # Funções auxiliares
    # =====================
    def _extrair_codigo_processo_de_href(self, href: str) -> str:
        """Extrai o código do processo a partir de um href conhecido.
        Suporta padrões:
          - /workspace/flow/<codigo>
          - /workspace/form-app/<codigo>/...
        Retorna string com dígitos ou None.
        """
        try:
            if not href:
                return None
            import re
            # 1) /workspace/flow/<codigo>
            m1 = re.search(r"/workspace/flow/(\d+)", href)
            if m1:
                return m1.group(1)
            # 2) /workspace/form-app/<codigo>/...
            m2 = re.search(r"/workspace/form-app/(\d+)/", href)
            if m2:
                return m2.group(1)
            return None
        except Exception:
            return None
    
    def tomar_decisao_automatica(self, status):
        """Toma decisão automática no processo se status for ENVIAR PARA CPMIG"""
        try:
            if status != 'ENVIAR PARA CPMIG':
                logger.info(f"[RELOAD] Status '{status}' - apenas registrando na planilha, sem ação automática")
                return True
            
            logger.info("[TARGET] Status 'ENVIAR PARA CPMIG' - executando decisão automática...")
            
            # 1. Abrir dropdown de decisão - múltiplas estratégias
            logger.info("[BUSCA] Tentando abrir dropdown de decisão...")
            dropdown_aberto = False
            
            seletores_trigger = [
                '#CHDNN_DEC_caret',
                '.caret.caret_search',
                '#CHDNN_DEC',
                '.select-wrapper input',
                'div[id*="CHDNN_DEC"] .caret'
            ]
            
            for i, seletor in enumerate(seletores_trigger):
                try:
                    triggers = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    logger.info(f"  Seletor {i+1} '{seletor}': {len(triggers)} elementos encontrados")
                    
                    for j, trigger in enumerate(triggers):
                        try:
                            if trigger.is_displayed():
                                trigger.click()
                                logger.info(f"[OK] Trigger clicado com seletor '{seletor}' (elemento {j+1})")
                                time.sleep(2)
                                dropdown_aberto = True
                                break
                        except Exception as e:
                            logger.debug(f"    Erro ao clicar em elemento {j+1}: {str(e)}")
                            continue
                    if dropdown_aberto:
                        break
                except Exception as e:
                    logger.debug(f"  Erro com seletor '{seletor}': {str(e)}")
                    continue
            
            if not dropdown_aberto:
                logger.warning("[ERRO] Não foi possível abrir dropdown de decisão")
                return False
            
            # 2. Aguardar lista aparecer e procurar opções
            logger.info("[BUSCA] Procurando opções no dropdown...")
            time.sleep(1)
            
            seletores_opcoes = [
                '#CHDNN_DEC_list li',
                'li.input-autocomplete__option',
                '#CHDNN_DEC_0',
                'li[id*="CHDNN_DEC_"]',
                '.input-autocomplete__list li'
            ]
            
            opcao_encontrada = False
            for i, seletor in enumerate(seletores_opcoes):
                try:
                    opcoes = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    logger.info(f"  Seletor {i+1} '{seletor}': {len(opcoes)} opções encontradas")
                    
                    for j, opcao in enumerate(opcoes):
                        try:
                            # Verificar texto da opção
                            texto_opcao = ''
                            try:
                                span = opcao.find_element(By.TAG_NAME, 'span')
                                texto_opcao = span.get_attribute('title') or span.text or opcao.text
                            except:
                                texto_opcao = opcao.text or opcao.get_attribute('textContent')
                            
                            logger.info(f"    Opção {j+1}: '{texto_opcao}'")
                            
                            if 'Enviar para CPMIG' in texto_opcao:
                                logger.info(f"[TARGET] Encontrou opção 'Enviar para CPMIG'! Clicando...")
                                opcao.click()
                                time.sleep(1)
                                opcao_encontrada = True
                                break
                                
                        except Exception as e:
                            logger.debug(f"    Erro ao processar opção {j+1}: {str(e)}")
                            continue
                    
                    if opcao_encontrada:
                        break
                        
                except Exception as e:
                    logger.debug(f"  Erro com seletor '{seletor}': {str(e)}")
                    continue
            
            if not opcao_encontrada:
                logger.warning("[ERRO] Opção 'Enviar para CPMIG' não encontrada")
                return False
            
            # 3. Verificar se seleção foi confirmada
            try:
                campo_input = self.driver.find_element(By.CSS_SELECTOR, '#CHDNN_DEC')
                valor_selecionado = campo_input.get_attribute('value') or campo_input.get_attribute('title')
                logger.info(f"[OK] Valor selecionado: '{valor_selecionado}'")
                
                if 'Enviar para CPMIG' not in valor_selecionado:
                    logger.warning(f"[AVISO] Seleção pode não ter sido confirmada. Continuando...")
            except Exception as e:
                logger.debug(f"Erro ao verificar seleção: {str(e)}")
            
            # 4. Clicar no botão de confirmação
            logger.info("[BUSCA] Procurando botão de confirmação...")
            
            seletores_botao = [
                'a.button.btn.aprovar[id="aprovar"]',
                'a#aprovar',
                'a.aprovar',
                'button[type="submit"]',
                'a[data-method="POST"]',
                'a.button.btn[id*="aprovar"]'
            ]
            
            botao_clicado = False
            for i, seletor in enumerate(seletores_botao):
                try:
                    botoes = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    logger.info(f"  Seletor {i+1} '{seletor}': {len(botoes)} botões encontrados")
                    
                    for j, botao in enumerate(botoes):
                        try:
                            texto_botao = botao.text or botao.get_attribute('textContent') or ''
                            logger.info(f"    Botão {j+1}: '{texto_botao}'")
                            
                            if botao.is_displayed() and ('Enviar para CPMIG' in texto_botao or 'aprovar' in botao.get_attribute('id')):
                                self.driver.execute_script('arguments[0].scrollIntoView({block: "center"});', botao)
                                time.sleep(0.5)
                                botao.click()
                                logger.info(f"[OK] Botão '{texto_botao}' clicado")
                                botao_clicado = True
                                break
                                
                        except Exception as e:
                            logger.debug(f"    Erro ao clicar botão {j+1}: {str(e)}")
                            continue
                    
                    if botao_clicado:
                        break
                        
                except Exception as e:
                    logger.debug(f"  Erro com seletor '{seletor}': {str(e)}")
                    continue
            
            if not botao_clicado:
                logger.warning("[ERRO] Botão de confirmação não encontrado")
                return False
            
            # 5. Aguardar confirmação (até 15 segundos)
            logger.info("[AGUARDE] Aguardando confirmação (até 15 segundos)...")
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'p[aria-label*="Próximos responsáveis"]'))
                )
                logger.info("[SUCCESS] Decisão automática executada com sucesso!")
                time.sleep(2)
                return True
            except Exception:
                logger.info("[AVISO] Confirmação visual não detectada, mas botão foi clicado")
                time.sleep(5)
                return True
            
        except Exception as e:
            logger.error(f"Erro na decisão automática: {str(e)}")
            return False

    def executar_aprovacao_por_planilha(self):
        """Executa aprovação no modo de seleção por planilha"""
        try:
            logger.info("[DADOS] Executando aprovação por planilha...")
            
            # Verificar se planilha foi informada
            if not self.caminho_planilha:
                logger.error("[ERRO] Caminho da planilha não foi informado")
                return False
            
            # Ler códigos da planilha
            codigos = self.ler_planilha_codigos(self.caminho_planilha)
            if not codigos:
                logger.error("[ERRO] Nenhum código encontrado na planilha")
                return False
                
            logger.info(f"[INFO] Processando {len(codigos)} códigos da planilha...")
            
            # Processar cada código
            for i, codigo in enumerate(codigos, 1):
                logger.info(f"\n--- Processo {i}/{len(codigos)} ---")
                if self.processar_processo_por_codigo(codigo):
                    logger.info(f"[OK] Processo {codigo} processado com sucesso")
                else:
                    logger.warning(f"[AVISO] Falha ao processar processo {codigo}")
                
                # Salvar resultados parciais
                self.salvar_resultados_parciais_planilha(i)
                
                # Pequena pausa entre processos
                time.sleep(2)
            
            # Gerar relatório final
            logger.info("🗂️ Gerando planilha final de resultados...")
            arquivo_planilha = self.gerar_planilha_resultados_final_planilha()
            
            if arquivo_planilha:
                logger.info("[OK] Processo de aprovação de parecer do analista (modo planilha) concluído com sucesso!")
                return True
            else:
                logger.warning("[AVISO] Processo concluído mas houve problema na geração da planilha final")
                return len(self.resultados_processamento) > 0
            
        except Exception as e:
            logger.error(f"[ERRO] Erro na execução por planilha: {str(e)}", exc_info=True)
            return False
    
    def ler_planilha_codigos(self, caminho_planilha, nome_coluna_codigo='codigo'):
        """Lê planilha e extrai códigos dos processos"""
        try:
            logger.info(f"[DADOS] Lendo planilha: {caminho_planilha}")
            
            # Tentar diferentes extensões
            if caminho_planilha.endswith('.xlsx'):
                df = pd.read_excel(caminho_planilha)
            elif caminho_planilha.endswith('.csv'):
                df = pd.read_csv(caminho_planilha)
            else:
                # Tentar como Excel por padrão
                df = pd.read_excel(caminho_planilha)
            
            logger.info(f"[OK] Planilha carregada com {len(df)} linhas")
            logger.info(f"Colunas disponíveis: {list(df.columns)}")
            
            # Resolver coluna de código de forma case-insensível e tolerante
            colunas_lower_map = {str(col).strip().lower(): col for col in df.columns}
            nome_buscado = (nome_coluna_codigo or 'codigo').strip().lower()
            coluna_codigo_real = None
            
            candidatos = [nome_buscado, 'codigo', 'código']
            for cand in candidatos:
                if cand in colunas_lower_map:
                    coluna_codigo_real = colunas_lower_map[cand]
                    break
            
            # Heurística: se ainda não encontrou, buscar por coluna que contenha 'codigo'
            if not coluna_codigo_real:
                for lower_name, original in colunas_lower_map.items():
                    if 'codigo' in lower_name or 'código' in lower_name:
                        coluna_codigo_real = original
                        break
            
            if not coluna_codigo_real:
                logger.error(f"[ERRO] Coluna '{nome_coluna_codigo}' não encontrada na planilha")
                logger.error(f"Colunas disponíveis: {list(df.columns)}")
                return []
            
            logger.info(f"[OK] Usando coluna: '{coluna_codigo_real}'")
            
            # Extrair códigos válidos
            codigos = []
            for valor in df[coluna_codigo_real]:
                if pd.notna(valor):
                    codigo_str = str(valor).strip()
                    if codigo_str:
                        codigos.append(codigo_str)
            
            logger.info(f"[OK] {len(codigos)} códigos válidos encontrados")
            return codigos
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao ler planilha: {str(e)}")
            return []
    
    def processar_processo_por_codigo(self, codigo_processo):
        """Processa um processo individual baseado no código - MODO PLANILHA"""
        try:
            logger.info(f"[RELOAD] Processando processo: {codigo_processo} (modo planilha)")
            
            # 1. Navegar diretamente para o processo
            if not self.navegar_diretamente_para_processo(codigo_processo):
                logger.error(f"[ERRO] Falha ao navegar diretamente para processo {codigo_processo}")
                return False
            
            # 2. Navegar para iframe
            if not self.navegar_para_iframe_planilha():
                logger.error(f"[ERRO] Falha ao navegar para iframe do processo {codigo_processo}")
                return False
            
            # 3. Extrair dados do formulário
            dados = self.extrair_dados_formulario()
            if not dados:
                logger.error(f"[ERRO] Falha ao extrair dados do processo {codigo_processo}")
                self.voltar_do_iframe_planilha()
                return False
            
            # 4. Analisar requisitos usando a data extraída da página
            data_inicio = getattr(self, 'data_inicio_processo_planilha', dados.get('data_inicio_processo'))
            resultado_analise = self.analisar_requisitos(dados, data_inicio)
            
            # 5. Registrar resultado (usar nomes de colunas compatíveis com gerar_planilha_resultados)
            resultado = {
                'processo': codigo_processo,  # Usar 'processo' em vez de 'codigo'
                'parecer_pf': dados.get('parecer_pf', ''),
                'parecer_mj': dados.get('parecer_mj', ''),
                'biometria': dados.get('biometria', ''),
                'tipo_naturalizacao': dados.get('tipo_naturalizacao', ''),
                'data_nascimento': self._mascarar_data_nascimento(dados.get('data_nascimento', '')),
                'status': resultado_analise['status'],
                'motivo_analise_manual': '; '.join(resultado_analise['motivo_analise_manual']),
                'decisao_automatica': 'Sim' if resultado_analise['pode_aprovar_automaticamente'] else 'Não',
                'timestamp_processamento': datetime.now().strftime('%d/%m/%Y %H:%M:%S')  # Usar 'timestamp_processamento'
            }
            
            # 6. Tomar decisão se for aprovação automática
            if resultado_analise['pode_aprovar_automaticamente']:
                if self.tomar_decisao_automatica(resultado_analise['status']):
                    logger.info(f"[OK] Decisão automática tomada para {codigo_processo}")
                else:
                    logger.warning(f"[AVISO] Falha ao tomar decisão automática para {codigo_processo}")
                    resultado['status'] = 'ANÁLISE MANUAL'
                    resultado['motivo_analise_manual'] = 'Falha na decisão automática'
                    resultado['decisao_automatica'] = 'Não'
            
            # 7. Salvar resultado
            self.resultados_processamento.append(resultado)
            self.salvar_planilha_incremental()
            
            # 8. Preparar para próximo processo
            self.voltar_do_iframe_planilha()
            
            logger.info(f"[OK] Processo {codigo_processo} processado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao processar processo {codigo_processo}: {str(e)}")
            try:
                self.voltar_do_iframe_planilha()
            except:
                pass
            return False
    
    def aplicar_filtros_e_buscar_processo(self, codigo_processo):
        """Aplica filtros para buscar um processo específico - APENAS para modo VERSÃO"""
        try:
            # Navegar para workspace se necessário
            current_url = self.driver.current_url
            if 'workspace' not in current_url.lower():
                if not self.navegar_para_workspace():
                    return False
            
            # Clicar em Caixa de entrada
            if not self.clicar_caixa_entrada():
                return False
            
            # Aplicar filtros básicos (atividade específica)
            if not self.aplicar_filtros_caixa_entrada():
                return False
            
            # Aqui poderia adicionar filtros específicos por código se necessário
            # Por enquanto, os filtros gerais são suficientes
            
            return True
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao aplicar filtros para processo {codigo_processo}: {str(e)}")
            return False
    
    def navegar_diretamente_para_processo(self, codigo_processo):
        """Navegação direta para processo específico - APENAS para modo PLANILHA"""
        import re as regex_module
        try:
            logger.info(f"[WEB] Navegação direta para processo: {codigo_processo}")
            
            # Extrair número limpo do processo (apenas dígitos)
            numero_limpo = regex_module.sub(r'\D', '', codigo_processo)
            
            # Navegar diretamente para a página do flow do processo
            workspace_url = f'https://justica.servicos.gov.br/workspace/flow/{numero_limpo}'
            logger.info(f"[LINK] Navegando para: {workspace_url}")
            
            self.driver.get(workspace_url)
            time.sleep(3)  # Aguardar carregamento
            
            # Armazenar número do processo limpo para uso posterior
            self.numero_processo_limpo = numero_limpo
            logger.info(f"[INFO] Número do processo: {codigo_processo} | Limpo: {numero_limpo}")
            
            # Extrair data de início do processo ANTES de entrar na atividade
            self.data_inicio_processo_planilha = self.extrair_data_inicio_processo()
            
            # Aguardar tabela carregar
            logger.info("[BUSCA] Procurando 'Aprovar Parecer do Analista' na tabela...")
            
            tabela = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-table-tbody"))
            )
            
            # Encontrar todas as linhas da tabela
            linhas = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            logger.info(f"[BUSCA] {len(linhas)} atividades encontradas")

            # Procurar pela atividade "Aprovar Parecer do Analista"
            link_escolhido = None
            for i, linha in enumerate(linhas, start=1):
                try:
                    link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    titulo = (link.get_attribute('title') or link.text or '').strip()
                    href = link.get_attribute('href') or ''
                    logger.info(f"  - Atividade {i}: '{titulo}'")
                    
                    # Procurar especificamente por "Aprovar Parecer do Analista"
                    titulo_lc = titulo.lower()
                    if ('aprovar' in titulo_lc or 'aprovação' in titulo_lc) and 'parecer' in titulo_lc and 'analista' in titulo_lc:
                        link_escolhido = link
                        logger.info(f"[OK] Encontrou 'Aprovar Parecer do Analista': {titulo}")
                        
                        # Extrair activityInstanceId da URL
                        match = regex_module.search(r'/(\d+)/\d+\?', href)
                        if match:
                            self.activity_instance_id = match.group(1)
                            logger.info(f"[SALVO] ActivityInstanceId extraído: {self.activity_instance_id}")
                        else:
                            self.activity_instance_id = "35"  # Default para "Aprovar Parecer do Analista"
                        
                        # Extrair ciclo da URL
                        match_ciclo = regex_module.search(r'/(\d+)\?', href)
                        if match_ciclo:
                            self.ciclo_processo = int(match_ciclo.group(1))
                        else:
                            self.ciclo_processo = 1  # Default
                        
                        break
                        
                except Exception as e:
                    logger.debug(f"Erro ao processar linha {i}: {str(e)}")
                    continue

            if not link_escolhido:
                logger.error("[ERRO] 'Aprovar Parecer do Analista' não encontrada na lista de atividades!")
                return False

            # Clicar na atividade escolhida
            logger.info("[CLIQUE] Clicando na atividade 'Aprovar Parecer do Analista'...")
            
            try:
                link_escolhido.click()
                logger.info("[OK] Clique normal executado")
            except Exception as e:
                logger.warning(f"[AVISO] Clique normal falhou ({e}), tentando JavaScript...")
                self.driver.execute_script("arguments[0].click();", link_escolhido)
                logger.info("[OK] Clique via JavaScript executado")

            # Aguardar navegação para form-app
            logger.info("[AGUARDE] Aguardando navegação para form-app...")
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.url_contains('/form-app/')
                )
                logger.info("[OK] Navegação detectada!")
            except Exception as e:
                logger.warning(f"[AVISO] Timeout aguardando navegação: {e}")
                time.sleep(3)
            
            current_url = self.driver.current_url
            logger.info(f"[LINK] URL após clique: {current_url}")
            
            if 'form-app' in current_url:
                logger.info("[OK] Navegação para formulário bem-sucedida!")
                
                # Extrair processInstanceId da URL atual se não temos
                match = regex_module.search(r'/form-app/(\d+)/', current_url)
                if match:
                    self.process_instance_id = match.group(1)
                    logger.info(f"[SALVO] ProcessInstanceId extraído: {self.process_instance_id}")
                else:
                    self.process_instance_id = numero_limpo  # Usar o número limpo como fallback
                
                return True
            else:
                logger.warning(f"[AVISO] URL após clique não contém form-app: {current_url}")
                return False
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao navegar diretamente para processo: {str(e)}")
            return False
    
    def navegar_para_iframe_planilha(self):
        """Navega para dentro do iframe form-app - APENAS para modo PLANILHA"""
        try:
            logger.info("[IFRAME] Navegando para iframe form-app (modo planilha)...")
            
            # MÉTODO 1: Tentar usar iframe existente primeiro
            try:
                iframe = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "iframe-form-app"))
                )
                logger.info("[OK] Iframe form-app encontrado!")
                
                # Verificar se iframe tem src válido
                iframe_src = iframe.get_attribute('src')
                logger.info(f"[LINK] Iframe src atual: {iframe_src}")
                
                if iframe_src and 'form-web' in iframe_src:
                    logger.info("[OK] Iframe já tem src válido, entrando no contexto...")
                    
                    # Trocar contexto para o iframe
                    self.driver.switch_to.frame(iframe)
                    logger.info("[OK] Contexto trocado para dentro do iframe")
                    
                    # Aguardar conteúdo carregar
                    time.sleep(5)
                    
                    # Verificar se formulário carregou
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    logger.info("[OK] Formulário no iframe carregado!")
                    return True
                    
            except Exception as e:
                logger.warning(f"[AVISO] Iframe não encontrado ou sem src válido: {e}")
            
            # MÉTODO 2: Construir URL manualmente e navegar diretamente
            logger.info("[DEBUG] Construindo URL do form-web manualmente...")
            
            if not hasattr(self, 'process_instance_id') or not self.process_instance_id:
                logger.error("[ERRO] process_instance_id não disponível")
                return False
            
            if not hasattr(self, 'activity_instance_id'):
                self.activity_instance_id = "35"  # Default para "Aprovar Parecer do Analista"
            
            if not hasattr(self, 'ciclo_processo'):
                self.ciclo_processo = 1  # Default
            
            # Construir URL específica para "Aprovar Parecer do Analista"
            iframe_url = f'https://justica.servicos.gov.br/form-web?processInstanceId={self.process_instance_id}&activityInstanceId={self.activity_instance_id}&cycle={self.ciclo_processo}&newWS=true'
            
            logger.info(f"[DEBUG] URL construída para Aprovar Parecer do Analista:")
            logger.info(f"   [INFO] processInstanceId: {self.process_instance_id}")
            logger.info(f"   [TARGET] activityInstanceId: {self.activity_instance_id} (Aprovar Parecer do Analista)")
            logger.info(f"   [RELOAD] cycle: {self.ciclo_processo}")
            logger.info(f"   [WEB] URL completa: {iframe_url}")
            
            # Navegar diretamente para a URL do form-web
            logger.info("[EXEC] Navegando diretamente para form-web...")
            self.driver.get(iframe_url)
            
            # Aguardar página carregar
            logger.info("[AGUARDE] Aguardando form-web carregar...")
            time.sleep(5)
            
            # Verificar se chegamos na URL correta
            current_url = self.driver.current_url
            logger.info(f"[LINK] URL atual após navegação: {current_url}")
            
            if 'form-web' in current_url and self.process_instance_id in current_url:
                logger.info("[OK] Navegação direta para form-web bem-sucedida!")
                
                # Aguardar elementos do formulário carregarem
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    logger.info("[OK] Formulário carregado!")
                    return True
                except Exception as e:
                    logger.warning(f"[AVISO] Erro ao aguardar formulário: {e}")
                    return False
                    
            else:
                logger.warning(f"[AVISO] URL inesperada após navegação: {current_url}")
                return False
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao navegar para iframe/form-web: {str(e)}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False
    
    def voltar_do_iframe_planilha(self):
        """Volta para o contexto principal - APENAS para modo PLANILHA"""
        try:
            # Como estamos navegando diretamente, não precisamos voltar do iframe
            # Apenas aguardar um momento antes do próximo processo
            time.sleep(2)
            logger.info("[OK] Preparado para próximo processo")
            return True
        except Exception as e:
            logger.warning(f"[AVISO] Erro na preparação para próximo processo: {e}")
            return False
    
    def extrair_data_inicio_processo(self):
        """Extrai a data de início do processo da página atual"""
        try:
            logger.info("[DATA] Extraindo data de início do processo...")
            
            # Procurar pelo elemento que contém a data
            # Exemplo: "Em andamento - aberto por Cidadão 7 de Nov de 2024 às 11:20"
            seletores_data = [
                ".subtitle",
                ".ant-tag + span",
                "[class*='subtitle']",
                "span:contains('aberto por')",
                "span:contains('Em andamento')"
            ]
            
            for seletor in seletores_data:
                try:
                    if 'contains' in seletor:
                        # Usar XPath para seletores com :contains
                        xpath = f"//span[contains(text(), 'aberto por') or contains(text(), 'Em andamento')]"
                        elementos = self.driver.find_elements(By.XPATH, xpath)
                    else:
                        elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    
                    for elemento in elementos:
                        texto = elemento.text.strip()
                        if texto and ('aberto por' in texto.lower() or 'em andamento' in texto.lower()):
                            logger.info(f"[DATA] Texto encontrado: {texto}")
                            
                            # Extrair data do texto usando regex
                            import re
                            # Padrões possíveis: "7 de Nov de 2024", "07/11/2024", etc.
                            padrao_data = r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
                            match = re.search(padrao_data, texto, re.IGNORECASE)
                            
                            if match:
                                dia = match.group(1).zfill(2)
                                mes_nome = match.group(2).lower()
                                ano = match.group(3)
                                
                                # Mapeamento de meses
                                meses = {
                                    'jan': '01', 'janeiro': '01',
                                    'fev': '02', 'fevereiro': '02',
                                    'mar': '03', 'março': '03', 'marco': '03',
                                    'abr': '04', 'abril': '04',
                                    'mai': '05', 'maio': '05',
                                    'jun': '06', 'junho': '06',
                                    'jul': '07', 'julho': '07',
                                    'ago': '08', 'agosto': '08',
                                    'set': '09', 'setembro': '09',
                                    'out': '10', 'outubro': '10',
                                    'nov': '11', 'novembro': '11',
                                    'dez': '12', 'dezembro': '12'
                                }
                                
                                mes_num = None
                                for nome_mes, numero in meses.items():
                                    if nome_mes in mes_nome:
                                        mes_num = numero
                                        break
                                
                                if mes_num:
                                    data_formatada = f"{dia}/{mes_num}/{ano}"
                                    logger.info(f"[OK] Data de início extraída: {data_formatada}")
                                    return data_formatada
                            
                            # Tentar padrão alternativo DD/MM/YYYY
                            padrao_numerico = r'(\d{1,2})/(\d{1,2})/(\d{4})'
                            match_num = re.search(padrao_numerico, texto)
                            if match_num:
                                data_formatada = f"{match_num.group(1).zfill(2)}/{match_num.group(2).zfill(2)}/{match_num.group(3)}"
                                logger.info(f"[OK] Data de início extraída (formato numérico): {data_formatada}")
                                return data_formatada
                                
                except Exception as e:
                    logger.debug(f"Erro ao processar seletor {seletor}: {str(e)}")
                    continue
            
            # Se não encontrou por seletores específicos, buscar em todo o texto da página
            try:
                logger.info("[BUSCA] Buscando data em todo o corpo da página...")
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                
                import re
                # Buscar padrão "X de MÊS de YYYY"
                padrao_completo = r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
                matches = re.findall(padrao_completo, body_text, re.IGNORECASE)
                
                if matches:
                    # Pegar a primeira data encontrada
                    dia, mes_nome, ano = matches[0]
                    mes_nome = mes_nome.lower()
                    
                    meses = {
                        'jan': '01', 'janeiro': '01',
                        'fev': '02', 'fevereiro': '02',
                        'mar': '03', 'março': '03', 'marco': '03',
                        'abr': '04', 'abril': '04',
                        'mai': '05', 'maio': '05',
                        'jun': '06', 'junho': '06',
                        'jul': '07', 'julho': '07',
                        'ago': '08', 'agosto': '08',
                        'set': '09', 'setembro': '09',
                        'out': '10', 'outubro': '10',
                        'nov': '11', 'novembro': '11',
                        'dez': '12', 'dezembro': '12'
                    }
                    
                    for nome_mes, numero in meses.items():
                        if nome_mes in mes_nome:
                            data_formatada = f"{dia.zfill(2)}/{numero}/{ano}"
                            logger.info(f"[OK] Data de início extraída do corpo da página: {data_formatada}")
                            return data_formatada
                            
            except Exception as e:
                logger.debug(f"Erro ao buscar data no corpo da página: {str(e)}")
            
            logger.warning("[AVISO] Não foi possível extrair a data de início do processo")
            # Retornar data atual como fallback
            from datetime import datetime
            data_atual = datetime.now().strftime('%d/%m/%Y')
            logger.info(f"[DATA] Usando data atual como fallback: {data_atual}")
            return data_atual
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao extrair data de início: {str(e)}")
            # Retornar data atual como fallback
            from datetime import datetime
            data_atual = datetime.now().strftime('%d/%m/%Y')
            return data_atual
    
    def clicar_processo_na_tabela(self, codigo_processo):
        """Clica no processo específico na tabela"""
        try:
            logger.info(f"[BUSCA] Procurando processo {codigo_processo} na tabela...")
            
            # Aguardar tabela carregar
            time.sleep(3)
            
            # Procurar o processo na tabela atual
            processos = self.obter_processos_da_tabela()
            
            for processo in processos:
                if codigo_processo in processo.get('codigo', ''):
                    logger.info(f"[TARGET] Processo {codigo_processo} encontrado! Clicando...")
                    
                    # Tentar clicar usando diferentes estratégias
                    if self.clicar_elemento_robusto(processo['elemento']):
                        logger.info(f"[OK] Clique realizado no processo {codigo_processo}")
                        return True
                    else:
                        logger.warning(f"[AVISO] Falha ao clicar no processo {codigo_processo}")
                        return False
            
            logger.warning(f"[AVISO] Processo {codigo_processo} não encontrado na página atual")
            return False
            
        except Exception as e:
            logger.error(f"[ERRO] Erro ao clicar no processo {codigo_processo}: {str(e)}")
            return False
    
    def salvar_resultados_parciais_planilha(self, processo_atual):
        """Salva resultados parciais durante processamento por planilha - mesmo formato do modo versão"""
        try:
            if not self.resultados_processamento:
                return
            
            # Usar o mesmo método de salvamento do modo versão
            self.salvar_planilha_incremental()
            logger.info(f"[SALVO] Resultados parciais salvos ({processo_atual} processos)")
            
        except Exception as e:
            logger.warning(f"[AVISO] Erro ao salvar resultados parciais: {e}")
    
    def gerar_planilha_resultados_final_planilha(self):
        """Gera planilha final para modo planilha - mesmo formato do modo versão"""
        try:
            logger.info("[DADOS] Gerando planilha final de resultados (modo planilha)...")
            
            # Usar o mesmo método de geração da planilha do modo versão
            arquivo_planilha = self.gerar_planilha_resultados()
            if arquivo_planilha:
                logger.info(f"[OK] Planilha final gerada: {os.path.basename(arquivo_planilha)}")
                return arquivo_planilha
            else:
                logger.error("[ERRO] Falha na geração da planilha final")
                return None
                
        except Exception as e:
            logger.error(f"[ERRO] Erro ao gerar planilha final: {str(e)}")
            return None


def executar_aprovacao_parecer_standalone(headless=False):
    """Função standalone para executar aprovação de parecer do analista"""
    aprovacao = None
    try:
        # Inicializar classe
        aprovacao = AprovacaoParecerAnalista()
        
        # Inicializar driver em modo visual por padrão
        if not aprovacao.inicializar_driver(headless=headless):
            logger.error("Falha ao inicializar driver")
            return False
        
        # Executar processo
        resultado = aprovacao.executar_aprovacao_completa()
        
        if resultado:
            logger.info("[OK] Processo de aprovação de parecer do analista executado com sucesso!")
        else:
            logger.error("[ERRO] Falha na execução do processo de aprovação de parecer do analista")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro durante execução standalone: {str(e)}")
        return False
    finally:
        if aprovacao:
            aprovacao.fechar()


if __name__ == "__main__":
    # Executar se chamado diretamente
    executar_aprovacao_parecer_standalone()
