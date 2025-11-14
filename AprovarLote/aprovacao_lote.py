"""
Módulo para automação de aprovação em lote no sistema LECOM
"""

import time
import logging
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


class AprovacaoLote:
    """Classe para automação de aprovação em lote no sistema LECOM"""
    
    def __init__(self, driver=None):
        """Inicializa a classe de aprovação em lote"""
        self.driver = driver
        self.wait = WebDriverWait(self.driver, 10) if driver else None
        self.navegacao_ordinaria = NavegacaoOrdinaria(driver) if driver else None
        
        # URLs do sistema
        self.url_workspace = "https://justica.servicos.gov.br/workspace/"
        self.url_form_web = "https://justica.servicos.gov.br/form-web"
        
        # Controle de login
        self.ja_logado = False
        
        # Seletores dos elementos
        self.seletores = {
            'menu_abrir': '.menu-top .ant-menu-item',
            'aprovacao_lote': '.container-category',
            'iframe_form_app': '#iframe-form-app',
            'etapa_dropdown': '#ETAPA',
            'etapa_list': '#ETAPA_list',
            'aprovacao_conteudo': 'span[title="Aprovação do Conteúdo"]',
            'tabela_processos': '.table.striped',
            'botao_editar': '.edit-line-grid',
            'decisao_dropdown': '#NAT_DECISAO',
            'decisao_list': '#NAT_DECISAO_list',
            'botao_atualizar': '#UPDATE',
            'botao_avancar': '#aprovar',
            'paginacao': '.waves-effect',
            'pagina_2': 'a[href="#!"]:contains("2")'
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
            
            # Executar login (não retorna valor booleano)
            self.navegacao_ordinaria.login()
            
            # Aguardar um momento para garantir que a página carregou
            time.sleep(2)
            
            # Verificar se login foi bem-sucedido checando a URL atual
            current_url = self.driver.current_url
            logger.info(f"URL atual após login: {current_url}")
            
            if 'workspace' in current_url.lower():
                logger.info("[OK] Login realizado com sucesso - usuário está no workspace")
                self.ja_logado = True
                return True
            else:
                logger.warning(f"[AVISO] URL não contém 'workspace', mas pode estar correto - URL: {current_url}")
                # Verificar se está numa página do sistema justica.servicos.gov.br
                if 'justica.servicos.gov.br' in current_url:
                    logger.info("[OK] Login aparentemente bem-sucedido - está no domínio correto")
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
    
    def clicar_menu_abrir(self):
        """Clica no menu 'Abrir'"""
        try:
            logger.info("Procurando menu 'Abrir'...")
            
            # Aguardar e clicar no menu Abrir
            menu_abrir = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.seletores['menu_abrir']))
            )
            
            # Verificar se é o menu correto pelo texto
            if "Abrir" in menu_abrir.text:
                menu_abrir.click()
                logger.info("[OK] Menu 'Abrir' clicado com sucesso")
                time.sleep(1)
                return True
            else:
                logger.warning("Menu encontrado não contém texto 'Abrir'")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao clicar no menu 'Abrir': {str(e)}")
            return False
    
    def clicar_aprovacao_lote(self):
        """Clica na opção 'Naturalizar-se - Aprovação em Lote'"""
        try:
            logger.info("Procurando opção 'Aprovação em Lote'...")
            
            # Aguardar carregamento das opções
            time.sleep(2)
            
            # Buscar todas as categorias disponíveis
            categorias = self.driver.find_elements(By.CSS_SELECTOR, self.seletores['aprovacao_lote'])
            
            for categoria in categorias:
                try:
                    nome_processo = categoria.find_element(By.CSS_SELECTOR, '.name-process').text
                    if "Naturalizar-se - Aprovação em Lote" in nome_processo:
                        categoria.click()
                        logger.info("[OK] Opção 'Aprovação em Lote' clicada com sucesso")
                        time.sleep(2)
                        return True
                except:
                    continue
                    
            logger.error("Opção 'Aprovação em Lote' não encontrada")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Aprovação em Lote': {str(e)}")
            return False
    
    def aguardar_iframe_e_navegar(self):
        """Aguarda o iframe aparecer e navega para a URL do form-web"""
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
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar iframe: {str(e)}")
            return False
    
    def selecionar_etapa_aprovacao_conteudo(self):
        """Seleciona a etapa 'Aprovação do Conteúdo'"""
        try:
            logger.info("Selecionando etapa 'Aprovação do Conteúdo'...")
            
            # Clicar no dropdown de etapa
            etapa_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#ETAPA'))
            )
            etapa_dropdown.click()
            time.sleep(1)
            
            # Aguardar a lista aparecer
            etapa_list = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.seletores['etapa_list']))
            )
            
            # Procurar e clicar na opção "Aprovação do Conteúdo"
            opcoes = etapa_list.find_elements(By.CSS_SELECTOR, '.input-autocomplete__option')
            
            for opcao in opcoes:
                texto_opcao = opcao.find_element(By.TAG_NAME, 'span').get_attribute('title')
                if "Aprovação do Conteúdo" in texto_opcao:
                    opcao.click()
                    logger.info("[OK] Etapa 'Aprovação do Conteúdo' selecionada")
                    time.sleep(2)
                    return True
                    
            logger.error("Opção 'Aprovação do Conteúdo' não encontrada")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao selecionar etapa: {str(e)}")
            return False
    
    def processar_todos_processos_tabela(self):
        """Processa todos os processos da tabela atual"""
        try:
            logger.info("Iniciando processamento dos processos da tabela...")
            
            # Aguardar carregamento da tabela
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.seletores['tabela_processos']))
            )
            time.sleep(2)
            
            # Buscar todas as linhas da tabela (exceto cabeçalho)
            linhas = self.driver.find_elements(By.CSS_SELECTOR, '.table-row')
            logger.info(f"Encontradas {len(linhas)} linhas para processar")
            
            processos_processados = 0
            
            for i, linha in enumerate(linhas):
                try:
                    logger.info(f"Processando processo {i+1}/{len(linhas)}...")
                    
                    if self.processar_processo_individual(linha):
                        processos_processados += 1
                        logger.info(f"[OK] Processo {i+1} processado com sucesso")
                    else:
                        logger.warning(f"[AVISO] Falha ao processar processo {i+1}")
                    
                    time.sleep(1)  # Pausa entre processos
                    
                except Exception as e:
                    logger.error(f"Erro ao processar processo {i+1}: {str(e)}")
                    continue
            
            logger.info(f"[OK] Processamento concluído: {processos_processados}/{len(linhas)} processos")
            return processos_processados > 0
            
        except Exception as e:
            logger.error(f"Erro ao processar tabela: {str(e)}")
            return False
    
    def processar_processo_individual(self, linha):
        """Processa um processo individual da tabela"""
        try:
            # Extrair informações do processo
            numero_processo = linha.find_element(By.CSS_SELECTOR, '.table-cell--NAT_PROCESSO .table-cell__content').text
            analise_mj = linha.find_element(By.CSS_SELECTOR, '.table-cell--NAT_ANALISE_MJ .table-cell__content').text
            
            logger.info(f"Processando processo {numero_processo} com análise MJ: {analise_mj}")
            
            # Clicar no botão editar
            botao_editar = linha.find_element(By.CSS_SELECTOR, self.seletores['botao_editar'])
            botao_editar.click()
            time.sleep(1)
            
            # Determinar a decisão baseada na análise MJ
            decisao = self.determinar_decisao(analise_mj)
            
            if not decisao:
                logger.warning(f"Não foi possível determinar decisão para análise: {analise_mj}")
                return False
            
            # Selecionar a decisão
            if self.selecionar_decisao(decisao):
                # Clicar em atualizar
                if self.clicar_atualizar():
                    logger.info(f"[OK] Processo {numero_processo} atualizado com decisão: {decisao}")
                    return True
                else:
                    logger.error(f"Falha ao atualizar processo {numero_processo}")
                    return False
            else:
                logger.error(f"Falha ao selecionar decisão para processo {numero_processo}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao processar processo individual: {str(e)}")
            return False
    
    def determinar_decisao(self, analise_mj):
        """Determina a decisão baseada na análise MJ"""
        analise_mj = analise_mj.lower().strip()
        
        if "propor deferimento" in analise_mj:
            return "Aprovo o parecer pelo Deferimento"
        elif "propor indeferimento" in analise_mj:
            return "Aprovo o parecer pelo Indeferimento"
        elif "propor arquivamento" in analise_mj:
            return "Não aprovo o parecer pelo Deferimento e Arquivo (Fundamentação a seguir)"
        else:
            logger.warning(f"Análise MJ não reconhecida: {analise_mj}")
            return None
    
    def selecionar_decisao(self, decisao):
        """Seleciona a decisão no dropdown"""
        try:
            # Clicar no dropdown de decisão
            decisao_dropdown = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.seletores['decisao_dropdown']))
            )
            decisao_dropdown.click()
            time.sleep(1)
            
            # Aguardar a lista aparecer
            decisao_list = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.seletores['decisao_list']))
            )
            
            # Procurar e clicar na decisão correta
            opcoes = decisao_list.find_elements(By.CSS_SELECTOR, '.input-autocomplete__option')
            
            for opcao in opcoes:
                texto_opcao = opcao.find_element(By.TAG_NAME, 'span').get_attribute('title')
                if decisao in texto_opcao:
                    opcao.click()
                    logger.info(f"[OK] Decisão selecionada: {decisao}")
                    time.sleep(1)
                    return True
                    
            logger.error(f"Decisão não encontrada: {decisao}")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao selecionar decisão: {str(e)}")
            return False
    
    def clicar_atualizar(self):
        """Clica no botão 'Atualizar'"""
        try:
            botao_atualizar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.seletores['botao_atualizar']))
            )
            botao_atualizar.click()
            logger.info("[OK] Botão 'Atualizar' clicado")
            time.sleep(2)
            return True
            
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Atualizar': {str(e)}")
            return False
    
    def navegar_para_pagina_2(self):
        """Navega para a página 2 da tabela"""
        try:
            logger.info("Navegando para página 2...")
            
            # Buscar o link da página 2
            pagina_2 = self.driver.find_element(By.XPATH, "//a[contains(text(), '2')]")
            pagina_2.click()
            
            logger.info("[OK] Navegação para página 2 concluída")
            time.sleep(2)
            return True
            
        except NoSuchElementException:
            logger.info("Página 2 não encontrada - provavelmente só existe uma página")
            return False
        except Exception as e:
            logger.error(f"Erro ao navegar para página 2: {str(e)}")
            return False
    
    def clicar_avancar(self):
        """Clica no botão 'Avançar' para finalizar"""
        try:
            logger.info("Clicando em 'Avançar' para finalizar...")
            
            botao_avancar = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, self.seletores['botao_avancar']))
            )
            botao_avancar.click()
            
            logger.info("[OK] Botão 'Avançar' clicado - aguardando conclusão...")
            # Timeout de 10 segundos para aguardar processamento
            time.sleep(10)
            logger.info("[OK] Processo finalizado após timeout de 10 segundos")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Avançar': {str(e)}")
            return False
    
    def executar_aprovacao_completa(self):
        """Executa o processo completo de aprovação em lote"""
        try:
            logger.info("[EXEC] Iniciando processo completo de aprovação em lote...")
            
            # 1. Fazer login (apenas se necessário)
            if not self.fazer_login():
                return False
            
            # 2. Navegar para workspace (apenas se necessário)
            current_url = self.driver.current_url
            if 'workspace' not in current_url.lower():
                if not self.navegar_para_workspace():
                    return False
            else:
                logger.info("[OK] Já está no workspace - pulando navegação")
            
            # 3. Clicar no menu Abrir
            if not self.clicar_menu_abrir():
                return False
            
            # 4. Clicar em Aprovação em Lote
            if not self.clicar_aprovacao_lote():
                return False
            
            # 5. Aguardar iframe e navegar
            if not self.aguardar_iframe_e_navegar():
                return False
            
            # 6. Selecionar etapa
            if not self.selecionar_etapa_aprovacao_conteudo():
                return False
            
            # 7. Processar página 1
            logger.info("[INFO] Processando página 1...")
            if not self.processar_todos_processos_tabela():
                logger.warning("Falha ao processar página 1")
                return False
            
            # 8. Tentar navegar para página 2 e processar
            if self.navegar_para_pagina_2():
                logger.info("[INFO] Processando página 2...")
                if not self.processar_todos_processos_tabela():
                    logger.warning("Falha ao processar página 2")
                    return False
            
            # 9. Finalizar clicando em Avançar
            if not self.clicar_avancar():
                return False
            
            # 10. Voltar para o workspace para nova iteração
            if not self.navegar_para_workspace():
                return False
            
            logger.info("[OK] Processo de aprovação em lote concluído com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"Erro durante execução completa: {str(e)}")
            return False
    
    def executar_ciclo_continuo(self, max_iteracoes=10, tempo_espera_minutos=10):
        """Executa múltiplos ciclos de aprovação até não haver mais processos"""
        try:
            logger.info(f"[RELOAD] Iniciando ciclo contínuo (máx. {max_iteracoes} iterações)...")
            logger.info(f"⏰ Tempo de espera entre iterações: {tempo_espera_minutos} minutos")
            
            iteracoes_executadas = 0
            
            for i in range(max_iteracoes):
                if i == 0:
                    logger.info(f"[RELOAD] Iniciando iteração {i+1}/{max_iteracoes} (primeira execução)...")
                else:
                    logger.info(f"[RELOAD] Iniciando iteração {i+1}/{max_iteracoes} (reutilizando sessão logada)...")
                
                if self.executar_aprovacao_completa():
                    iteracoes_executadas += 1
                    logger.info(f"[OK] Iteração {i+1} concluída com sucesso")
                    
                    # Verificar se não é a última iteração
                    if i < max_iteracoes - 1:
                        logger.info(f"[AGUARDE] Aguardando {tempo_espera_minutos} minutos antes da próxima iteração...")
                        self.aguardar_tempo_entre_iteracoes(tempo_espera_minutos)
                else:
                    logger.info("[ERRO] Não há mais processos para aprovar ou ocorreu erro")
                    break
            
            logger.info(f"🏁 Ciclo contínuo finalizado. {iteracoes_executadas} iterações executadas.")
            return iteracoes_executadas > 0
            
        except Exception as e:
            logger.error(f"Erro durante ciclo contínuo: {str(e)}")
            return False
    
    def aguardar_tempo_entre_iteracoes(self, tempo_espera_minutos):
        """Aguarda o tempo especificado entre iterações com logs informativos"""
        try:
            tempo_espera_segundos = tempo_espera_minutos * 60
            logger.info(f"⏰ Iniciando espera de {tempo_espera_minutos} minutos ({tempo_espera_segundos} segundos)...")
            
            # Aguardar em intervalos de 1 minuto para mostrar progresso
            for minuto in range(tempo_espera_minutos):
                if minuto > 0:  # Não mostrar no primeiro minuto
                    tempo_restante = tempo_espera_minutos - minuto
                    logger.info(f"[AGUARDE] Tempo restante: {tempo_restante} minutos")
                
                # Aguardar 1 minuto (60 segundos)
                time.sleep(60)
            
            logger.info("[OK] Tempo de espera concluído - iniciando próxima iteração")
            
        except Exception as e:
            logger.error(f"Erro durante espera entre iterações: {str(e)}")
    
    def fechar(self):
        """Fecha o driver e limpa recursos"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                logger.info("[OK] Driver fechado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao fechar driver: {str(e)}")


def executar_aprovacao_lote_standalone(headless=False, max_iteracoes=10, tempo_espera_minutos=10):
    """Função standalone para executar aprovação em lote"""
    aprovacao = None
    try:
        # Inicializar classe
        aprovacao = AprovacaoLote()
        
        # Inicializar driver em modo visual por padrão
        if not aprovacao.inicializar_driver(headless=headless):
            logger.error("Falha ao inicializar driver")
            return False
        
        # Executar processo
        resultado = aprovacao.executar_ciclo_continuo(max_iteracoes, tempo_espera_minutos)
        
        if resultado:
            logger.info("[OK] Processo de aprovação em lote executado com sucesso!")
        else:
            logger.error("[ERRO] Falha na execução do processo de aprovação em lote")
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro durante execução standalone: {str(e)}")
        return False
    finally:
        if aprovacao:
            aprovacao.fechar()


if __name__ == "__main__":
    # Executar se chamado diretamente
    executar_aprovacao_lote_standalone()
