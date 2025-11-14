import os
from dotenv import load_dotenv
# Carrega o .env da pasta atual do script
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)
print("Arquivo .env existe?", os.path.exists(env_path))
# Credenciais LECOM carregadas com sucesso
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from datetime import datetime
import time
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import re
import pytesseract
from pdf2image import convert_from_path
from preprocessing_ocr import ImagePreprocessor
from mistralai import Mistral
from ocr_utils import (
    extrair_nome_completo,
    extrair_filiação_limpa,
    extrair_pai_mae_da_filiacao_lista,
    extrair_nascimento_ajustado,
    extrair_rnm_robusto,
    extrair_cpf,
    extrair_classificacao,
    extrair_prazo_residencia,
    extrair_nacionalidade_validade_linha,
    comparar_campos,
    extrair_data_nasc_texto
)
import base64
import requests
import io
import json
import uuid
import unicodedata
from selenium.webdriver.chrome.options import Options

LECOM_URL = "https://justica.servicos.gov.br/bpm"
LECOM_USER = os.environ.get("LECOM_USER")
LECOM_PASS = os.environ.get("LECOM_PASS")

class NavegacaoOrdinaria:
    def __init__(self, driver=None):
        """
        Inicializa o automatizador do Lecom
        [FECHADO] LGPD: Mantém compatibilidade mas força conformidade
        """
        if driver:
            # Usar driver existente se fornecido (compatibilidade)
            self.driver = driver
            self.wait = WebDriverWait(self.driver, 40)
            print("[FECHADO] LGPD: Usando driver existente com conformidade")
        else:
            # Criar novo driver com configurações de segurança
            chrome_options = Options()
            
            # Configurações básicas (não muito restritivas para manter funcionalidade)
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # Argumentos adicionais para desabilitar visualizador de PDF
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-plugins-discovery")
            chrome_options.add_argument("--disable-pdf-viewer")
            
            # Configurar diretório de download padrão
            download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                # Impedir abertura automática de PDFs
                "plugins.always_open_pdf_externally": False,
                "plugins.plugins_disabled": ["Chrome PDF Viewer"],
                # Configurações adicionais para evitar abertura de PDFs
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.automatic_downloads": 1,
                "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
                # Desabilitar visualizador de PDF do Chrome
                "profile.default_content_settings.plugins": 2,
                "profile.content_settings.plugin_whitelist.adobe-flash-player": 0,
                "profile.default_content_setting_values.plugins": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 40)
            print("[FECHADO] LGPD: Novo driver criado com conformidade")
        
        # Propriedades essenciais
        self.numero_processo_limpo = None
        self.ja_logado = False
        
        # [FECHADO] CORREÇÃO LGPD: Definir documentos para naturalização ordinária
        self.documentos_para_baixar = [
            'Carteira de Registro Nacional Migratório',
            'Comprovante da situação cadastral do CPF',
            'Comprovante de tempo de residência',
            'Comprovante de comunicação em português',
            'Certidão de antecedentes criminais (Brasil)',
            'Atestado antecedentes criminais (país de origem)',
            'Documento de viagem internacional',
            'Comprovante de redução de prazo',
            'Comprovante de reabilitação'
            # Documentos específicos para naturalização ordinária
        ]
        
        # Cache para evitar reprocessamento
        self.textos_ja_extraidos = {}
        
        # [DEBUG] CORREÇÃO: Sistema de logs para rastrear falhas de download
        self.logs_download = {
            'sucessos': [],
            'falhas': [],
            'erros': []
        }
        
        # [FECHADO] LGPD: Flag para conformidade
        self.naturalizacao_confirmada_via_banco = False
        
        print("[FECHADO] LGPD: Sistema de navegação ordinária inicializado em conformidade")
        print("[OK] Documentos permitidos para análise ordinária:", len(self.documentos_para_baixar))

    def login(self):
        print('=== INÍCIO login ===')
        print('Acessando o Lecom...')
        self.driver.get(LECOM_URL)
        try:
            username_input = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, "//input[@name='username']"))
            )
            print('DEBUG: Campo de usuário carregado!')
        except Exception as e:
            print('ERRO: Campo de usuário não carregou:', e)
            print('HTML atual:', self.driver.page_source[:2000])
            raise
        # Usuário LECOM configurado
        username_input.click()
        username_input.clear()
        username_input.send_keys(LECOM_USER if LECOM_USER is not None else "")

        try:
            proxima_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and .//span[text()='Próxima']]"))
            )
            print('DEBUG: Botão Próxima carregado!')
        except Exception as e:
            print('ERRO: Botão Próxima não carregou:', e)
            print('HTML atual:', self.driver.page_source[:2000])
            raise
        proxima_btn.click()

        try:
            password_input = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, "//input[@name='password' and @type='password']"))
            )
            print('DEBUG: Campo de senha carregado!')
        except Exception as e:
            print('ERRO: Campo de senha não carregou:', e)
            print('HTML atual:', self.driver.page_source[:2000])
            raise
        password_input.clear()
        password_input.send_keys(LECOM_PASS if LECOM_PASS is not None else "")

        try:
            entrar_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and .//span[text()='Entrar']]"))
            )
            print('DEBUG: Botão Entrar carregado!')
        except Exception as e:
            print('ERRO: Botão Entrar não carregou:', e)
            print('HTML atual:', self.driver.page_source[:2000])
            raise
        entrar_btn.click()

        # Aguardar e clicar no botão "Entendi" se aparecer (aviso da mudança do LECOM)
        try:
            print('DEBUG: Verificando se aparece botão "Entendi" para mudança do LECOM...')
            botao_entendi = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and contains(@class, 'ant-btn-primary') and .//span[text()='Entendi']]"))
            )
            print('DEBUG: Botão "Entendi" encontrado! Clicando...')
            botao_entendi.click()
            time.sleep(2)
            print('DEBUG: Botão "Entendi" clicado com sucesso!')
        except TimeoutException:
            print('DEBUG: Botão "Entendi" não apareceu (normal se já foi clicado antes)')
        except Exception as e:
            print(f'DEBUG: Erro ao procurar botão "Entendi": {e}')

        # Fechar chat de "Comunique-se com a equipe" se aparecer
        try:
            print('DEBUG: Verificando se há chat de comunicação para fechar...')
            botao_fechar_chat = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//svg[contains(@class, '') and path[@d='M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z']]"))
            )
            print('DEBUG: Botão de fechar chat encontrado! Clicando...')
            botao_fechar_chat.click()
            time.sleep(1)
            print('DEBUG: Chat de comunicação fechado com sucesso!')
        except TimeoutException:
            print('DEBUG: Chat de comunicação não apareceu ou já foi fechado')
        except Exception as e:
            print(f'DEBUG: Erro ao procurar botão de fechar chat: {e}')

        print('Login realizado.')
        
        # Verificar URL após login (já deve estar na workspace)
        current_url_pos_login = self.driver.current_url
        print(f'DEBUG: URL após login: {current_url_pos_login}')
        
        # Login já direciona para a área de pesquisa correta
        if 'workspace' in current_url_pos_login:
            print('DEBUG: [OK] Já está na área de pesquisa de processos!')
        else:
            print('DEBUG: [AVISO] URL inesperada após login, mas continuando...')
        
        print('=== FIM login ===')
        time.sleep(2)


    def aplicar_filtros(self, numero_processo):
        import re as regex_module  # Importar com alias para evitar conflitos
        print('=== INÍCIO aplicar_filtros ===')
        print('Navegação direta para o processo...')
        
        try:
            # Extrair número limpo do processo (apenas dígitos)
            numero_limpo = regex_module.sub(r'\D', '', numero_processo)
            
            # PASSO 1: Navegar para a página do flow do processo
            workspace_url = f'https://justica.servicos.gov.br/workspace/flow/{numero_limpo}'
            print(f'DEBUG: Navegando para: {workspace_url}')
            
            self.driver.get(workspace_url)
            time.sleep(3)  # Aguardar carregamento
            
            # Armazenar número do processo limpo para uso posterior
            self.numero_processo_limpo = numero_limpo
            print(f"DEBUG: Número do processo: {numero_processo} | Limpo: {numero_limpo}")

            # PASSO 2: Extrair data inicial do processo
            print("[DATA] Extraindo data inicial do processo...")
            data_inicial = self.extrair_data_inicial_processo()
            if data_inicial:
                self.data_inicial_processo = data_inicial
                print(f"[OK] Data inicial: {data_inicial}")
            
            # PASSO 3: Buscar e clicar em "Efetuar Distribuição" na tabela
            print('[BUSCA] Procurando "Efetuar Distribuição" na tabela...')
            
            # Aguardar tabela carregar
            tabela = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-table-tbody"))
            )
            
            # Encontrar todas as linhas da tabela e listar atividades
            linhas = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            print(f'DEBUG: {len(linhas)} atividades encontradas')

            todos_links = []
            for i, linha in enumerate(linhas, start=1):
                try:
                    link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    titulo = (link.get_attribute('title') or link.text or '').strip()
                    href = link.get_attribute('href') or ''
                    print(f"  - Atividade {i}: '{titulo}' -> {href}")
                    todos_links.append((link, titulo, href))
                except Exception:
                    print(f"  - Atividade {i}: [sem link]")

            # Encontrar TODAS as atividades "Efetuar Distribuição" e pegar a do ciclo mais alto
            efetuar_distribuicao_links = []
            
            for link, titulo, href in todos_links:
                try:
                    titulo_lc = titulo.lower()
                    # Procurar por "Efetuar Distribuição" com /24/ no href
                    if ('/24/' in href) and ('efetuar distribui' in titulo_lc):
                        # Extrair o ciclo da URL usando regex
                        match = regex_module.search(r'/24/(\d+)', href)
                        if match:
                            ciclo = int(match.group(1))
                            efetuar_distribuicao_links.append((link, titulo, href, ciclo))
                            print(f"[BUSCA] Encontrou 'Efetuar Distribuição' ciclo {ciclo}: {href}")
                except Exception as e:
                    print(f"[AVISO] Erro ao processar link: {e}")
                    continue
            
            # Ordenar por ciclo (maior primeiro) e pegar o mais recente
            link_escolhido = None
            ciclo_escolhido = None
            
            if efetuar_distribuicao_links:
                # Mostrar todos os ciclos encontrados
                print(f"[INFO] Total de atividades 'Efetuar Distribuição' encontradas: {len(efetuar_distribuicao_links)}")
                for i, (_, titulo, href, ciclo) in enumerate(efetuar_distribuicao_links, 1):
                    print(f"   {i}. Ciclo {ciclo}: {titulo} -> {href}")
                
                # Ordenar por ciclo descendente (mais alto primeiro)
                efetuar_distribuicao_links.sort(key=lambda x: x[3], reverse=True)
                
                # Pegar o primeiro (ciclo mais alto)
                link_escolhido, titulo_escolhido, href_escolhido, ciclo_escolhido = efetuar_distribuicao_links[0]
                
                print(f"[TARGET] SELECIONADO: 'Efetuar Distribuição' com CICLO MAIS ALTO: {ciclo_escolhido}")
                print(f"   [PIN] Título: '{titulo_escolhido}'")
                print(f"   [LINK] URL: {href_escolhido}")
                
                # Armazenar o ciclo para usar na construção da URL do form-web
                self.ciclo_processo = ciclo_escolhido
                print(f"[SALVO] Ciclo {ciclo_escolhido} armazenado para construção da URL do form-web")
                
            else:
                print("[AVISO] Nenhuma atividade 'Efetuar Distribuição' com /24/ encontrada")
                # Fallback: procurar apenas pelo título
                for link, titulo, href in todos_links:
                    try:
                        if 'efetuar distribui' in titulo.lower():
                            link_escolhido = link
                            print(f"[OK] Selecionado por título (fallback): '{titulo}' -> {href}")
                            # Tentar extrair ciclo mesmo assim
                            match = regex_module.search(r'/(\d+)\?', href)
                            if match:
                                self.ciclo_processo = int(match.group(1))
                            else:
                                self.ciclo_processo = 2  # Default
                            break
                    except Exception:
                        continue

            if not link_escolhido:
                print('[ERRO] "Efetuar Distribuição" não encontrada na lista de atividades!')
                return None

            # Clicar na atividade escolhida usando JavaScript para garantir o clique
            print('[CLIQUE] Clicando na atividade "Efetuar Distribuição"...')
            
            # Tentar clique normal primeiro
            try:
                link_escolhido.click()
                print('[OK] Clique normal executado')
            except Exception as e:
                print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                # Se falhar, usar JavaScript
                self.driver.execute_script("arguments[0].click();", link_escolhido)
                print('[OK] Clique via JavaScript executado')

            # Aguardar navegação para o form-app correspondente
            print('[AGUARDE] Aguardando navegação para form-app...')
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.url_contains('/form-app/')
                )
                print('[OK] Navegação detectada!')
            except Exception as e:
                print(f'[AVISO] Timeout aguardando navegação: {e}')
                time.sleep(3)  # Aguardar um pouco mais
            
            current_url = self.driver.current_url
            print(f'DEBUG: URL após clique: {current_url}')
            
            if 'form-app' in current_url:
                print('[OK] Navegação para formulário bem-sucedida!')
                if '/24/' in current_url:
                    print('[OK] Confirmado: Atividade 24 (Efetuar Distribuição)')
                else:
                    print(f'ℹ️ Atividade diferente de 24, mas em form-app: {current_url}')
            else:
                print(f'[AVISO] URL após clique não contém form-app: {current_url}')
                print('[RELOAD] Tentando aguardar mais tempo para a navegação...')
                time.sleep(5)
                current_url = self.driver.current_url
                print(f'DEBUG: URL após espera adicional: {current_url}')

            # PASSO 4: Navegar diretamente para URL do form-web
            print('\n[WEB] PASSO 4: Navegando diretamente para form-web...')
            
            try:
                # Usar o ciclo detectado ou default para 2
                ciclo_para_usar = getattr(self, 'ciclo_processo', 2)
                
                # Construir URL direta do form-web com o ciclo correto
                form_url = f'https://justica.servicos.gov.br/form-web?processInstanceId={numero_limpo}&activityInstanceId=24&cycle={ciclo_para_usar}&newWS=true'
                print(f'DEBUG: Navegando para form-web com CICLO {ciclo_para_usar}: {form_url}')
                
                # Navegar diretamente para o formulário
                self.driver.get(form_url)
                
                # Aguardar página carregar
                print('[AGUARDE] Aguardando formulário carregar...')
                time.sleep(5)
                
                # Verificar se chegamos na URL correta
                current_url = self.driver.current_url
                print(f'DEBUG: URL atual: {current_url}')
                
                if 'form-web' in current_url and numero_limpo in current_url:
                    print('[OK] Navegação direta para form-web bem-sucedida!')
                    
                    # Aguardar elementos do formulário carregarem
                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        print('[OK] Formulário carregado!')
                    except Exception as e:
                        print(f'[AVISO] Erro ao aguardar formulário: {e}')
                        
                else:
                    print(f'[AVISO] URL inesperada após navegação: {current_url}')
                    
            except Exception as e:
                print(f'[ERRO] Erro ao navegar para form-web: {e}')
                print('[RELOAD] Tentando continuar com URL atual...')
            
            print('[OK] Acesso à atividade concluído!')
            print('=== FIM aplicar_filtros ===')
            
            # Retornar sucesso para indicar que a navegação foi concluída
            return {'status': 'navegacao_concluida', 'data_inicial': data_inicial}
        except Exception as e:
            print(f"ERRO ao extrair e abrir o processo: {e}")
            return

    def navegar_para_iframe_form_app(self):
        """
        Navega para dentro do iframe form-app para acessar o formulário
        Retorna True se bem-sucedido, False caso contrário
        """
        print('[IFRAME] Tentando navegar para iframe form-app...')
        
        try:
            # Primeiro, verificar se o iframe já existe
            try:
                iframe = self.driver.find_element(By.ID, "iframe-form-app")
                print('[OK] Iframe form-app já presente!')
            except:
                print('[AVISO] Iframe não encontrado imediatamente, aguardando...')
                iframe = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "iframe-form-app"))
                )
                print('[OK] Iframe form-app encontrado após espera!')
            
            # Verificar se iframe está visível e tem src
            iframe_src = iframe.get_attribute('src')
            iframe_display = iframe.value_of_css_property('display')
            print(f'DEBUG: Iframe src: {iframe_src}')
            print(f'DEBUG: Iframe display: {iframe_display}')
            
            if not iframe_src or 'form-web' not in iframe_src:
                print('[AVISO] Iframe sem src válido ou não é form-web')
                return False
            
            # Trocar contexto para o iframe
            print('[RELOAD] Trocando contexto para iframe...')
            self.driver.switch_to.frame(iframe)
            print('[OK] Contexto trocado para dentro do iframe')
            
            # Aguardar o conteúdo do iframe carregar
            print('[AGUARDE] Aguardando conteúdo do iframe carregar...')
            time.sleep(5)
            
            # Verificar se o formulário carregou
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                print('[OK] Body do iframe carregado!')
                
                # Tentar obter URL do iframe
                try:
                    current_url_iframe = self.driver.execute_script("return window.location.href;")
                    print(f'DEBUG: URL dentro do iframe: {current_url_iframe}')
                    
                    # Verificar se é a URL correta
                    if 'form-web' in current_url_iframe and 'processInstanceId' in current_url_iframe:
                        print('[OK] Iframe carregado com URL correta!')
                        return True
                    else:
                        print(f'[AVISO] URL do iframe inesperada: {current_url_iframe}')
                        
                except Exception as url_e:
                    print(f'[AVISO] Erro ao obter URL do iframe: {url_e}')
                
                # Mesmo com erro na URL, tentar continuar se body carregou
                print('[OK] Iframe carregado (mesmo com problemas na URL)')
                return True
                
            except Exception as e:
                print(f'[ERRO] Erro ao verificar conteúdo do iframe: {e}')
                # Voltar para contexto principal em caso de erro
                self.driver.switch_to.default_content()
                return False
                
        except Exception as e:
            print(f'[ERRO] Erro ao navegar para iframe: {e}')
            # Garantir que voltamos para contexto principal
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False

    def extrair_dados_do_formulario_form_web(self):
        """
        Extrai dados específicos da página form-web (acesso direto)
        Como data de nascimento, dados pessoais, etc.
        """
        print('[INFO] Extraindo dados da página form-web...')
        
        dados_extraidos = {}
        
        try:
            # Aguardar formulário carregar completamente
            print('[AGUARDE] Aguardando elementos do formulário carregarem...')
            time.sleep(3)
            
            # Tentar extrair data de nascimento
            print('🎂 Procurando data de nascimento...')
            
            # Seletores expandidos para data de nascimento
            seletores_data_nascimento = [
                "input[name*='data']",
                "input[name*='nascimento']",
                "input[name*='birth']",
                "input[placeholder*='nascimento']",
                "input[placeholder*='data']",
                "input[id*='data']",
                "input[id*='nascimento']",
                ".form-control[name*='data']",
                ".form-control[id*='data']",
                "[data-testid*='data']",
                "[data-testid*='nascimento']",
                "input[type='date']",
                "input[type='text'][name*='data']"
            ]
            
            data_nascimento = None
            for seletor in seletores_data_nascimento:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        valor = elemento.get_attribute('value')
                        placeholder = elemento.get_attribute('placeholder') or ''
                        name = elemento.get_attribute('name') or ''
                        
                        # Verificar se realmente é um campo de data
                        if (valor and len(valor) >= 8 and 
                            ('nasc' in name.lower() or 'data' in name.lower() or 
                             'nasc' in placeholder.lower() or 'data' in placeholder.lower())):
                            data_nascimento = valor
                            print(f'[OK] Data de nascimento encontrada: {data_nascimento} (campo: {name or placeholder})')
                            break
                    if data_nascimento:
                        break
                except:
                    continue
            
            if data_nascimento:
                dados_extraidos['data_nascimento'] = data_nascimento
            else:
                print('[AVISO] Data de nascimento não encontrada')
            
            # Tentar extrair outros dados pessoais
            print('[USER] Procurando outros dados pessoais...')
            
            # Nome completo
            seletores_nome = [
                "input[name*='nome']",
                "input[placeholder*='nome']",
                "input[id*='nome']",
                ".form-control[name*='nome']",
                ".form-control[id*='nome']",
                "input[name*='name']"
            ]
            
            for seletor in seletores_nome:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        valor = elemento.get_attribute('value')
                        if valor and len(valor) > 5:  # Nome deve ter pelo menos 5 caracteres
                            dados_extraidos['nome_completo'] = valor
                            print(f'[OK] Nome encontrado: {valor}')
                            break
                    if 'nome_completo' in dados_extraidos:
                        break
                except:
                    continue
            
            # Nacionalidade/País de origem
            seletores_nacionalidade = [
                "input[name*='nacionalidade']",
                "input[name*='pais']",
                "select[name*='nacionalidade']",
                "select[name*='pais']",
                "input[name*='country']",
                "select[name*='country']",
                "input[id*='nacionalidade']",
                "input[id*='pais']"
            ]
            
            for seletor in seletores_nacionalidade:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        if elemento.tag_name.lower() == 'select':
                            # Para select, pegar o texto da opção selecionada
                            from selenium.webdriver.support.ui import Select
                            select_obj = Select(elemento)
                            try:
                                valor = select_obj.first_selected_option.text
                            except:
                                continue
                        else:
                            valor = elemento.get_attribute('value')
                        
                        if valor and len(valor) > 2 and valor.lower() not in ['selecione', 'escolha', '']:
                            dados_extraidos['nacionalidade'] = valor
                            print(f'[OK] Nacionalidade encontrada: {valor}')
                            break
                    if 'nacionalidade' in dados_extraidos:
                        break
                except:
                    continue
            
            # Tentar extrair outros campos úteis
            print('[INFO] Procurando outros campos do formulário...')
            
            # CPF/Documento
            seletores_documento = [
                "input[name*='cpf']",
                "input[name*='documento']",
                "input[id*='cpf']",
                "input[id*='documento']"
            ]
            
            for seletor in seletores_documento:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for elemento in elementos:
                        valor = elemento.get_attribute('value')
                        if valor and len(valor) >= 10:
                            dados_extraidos['documento'] = valor
                            print(f'[OK] Documento encontrado: {valor}')
                            break
                    if 'documento' in dados_extraidos:
                        break
                except:
                    continue
            
            print(f'[DADOS] Total de dados extraídos do form-web: {len(dados_extraidos)}')
            for chave, valor in dados_extraidos.items():
                print(f'  - {chave}: {valor}')
                
        except Exception as e:
            print(f'[ERRO] Erro ao extrair dados do form-web: {e}')
        
        return dados_extraidos

    def voltar_do_iframe(self):
        """
        Volta do iframe para a janela principal
        """
        try:
            self.driver.switch_to.default_content()
            print('[OK] Contexto voltou para janela principal')
        except Exception as e:
            print(f'[AVISO] Erro ao voltar do iframe: {e}')

    def processar_processo(self, numero_processo, dados_texto=None):
        print('=== CHAMADA ÚNICA processar_processo ===')
        print('=== INÍCIO processar_processo ===')
        if dados_texto is None:
            dados_texto = {}
        
        # Marcar como já logado para evitar tentativas de relogin
        self.ja_logado = True
        print('DEBUG: Marcado como já logado - usando sessão existente do app.py')
        
        # Se já temos o número do processo armazenado, usar ele
        if not hasattr(self, 'numero_processo_limpo') or not self.numero_processo_limpo:
            # Tentar extrair o número do processo ou usar o código fornecido
            numero_extraido = self.extrair_numero_processo()
            if not numero_extraido:
                # Se não conseguir extrair, usar o código fornecido
                import re as regex_module
                self.numero_processo_limpo = regex_module.sub(r'\D', '', numero_processo)
                print(f'DEBUG: Usando código fornecido como número do processo: {self.numero_processo_limpo}')
        
        # Para navegação ordinária no contexto do app.py, apenas fazer o download e OCR
        return self.processar_documentos_ordinaria(numero_processo)
    
    def processar_documentos_ordinaria(self, numero_processo):
        """
        Método específico para processar documentos de naturalização ordinária
        Fluxo otimizado: navega para workspace flow → extrai data inicial → processa documentos no iframe
        """
        print('=== PROCESSAMENTO DE DOCUMENTOS ORDINÁRIA ===')
        
        # Garantir que temos o número do processo
        if not hasattr(self, 'numero_processo_limpo') or not self.numero_processo_limpo:
            import re as regex_module
            self.numero_processo_limpo = regex_module.sub(r'\D', '', numero_processo)
            print(f'DEBUG: Número do processo definido: {self.numero_processo_limpo}')
        
        # VERIFICAR SE ESTAMOS NA URL CORRETA (workspace/flow)
        current_url = self.driver.current_url
        print(f'DEBUG: URL atual: {current_url}')
        
        # Se não estivermos na URL do workspace flow, navegar para ela
        if 'workspace/flow/' not in current_url or self.numero_processo_limpo not in current_url:
            workspace_flow_url = f'https://justica.servicos.gov.br/workspace/flow/{self.numero_processo_limpo}'
            print(f'DEBUG: [EXEC] Navegando para URL do workspace flow: {workspace_flow_url}')
            self.driver.get(workspace_flow_url)
            time.sleep(5)
            print('[OK] Navegação para workspace flow concluída')
        
        # ETAPA 1: Extrair data inicial ANTES de qualquer navegação
        print('\n=== ETAPA 1: EXTRAÇÃO DA DATA INICIAL ===')
        if not hasattr(self, 'data_inicial_processo') or not self.data_inicial_processo:
            print('DEBUG: [DATA] Extraindo data inicial do processo...')
            data_inicial = self.extrair_data_inicial_processo()
            if data_inicial:
                self.data_inicial_processo = data_inicial
                print(f'DEBUG: [OK] Data inicial extraída: {data_inicial}')
            else:
                print('DEBUG: [AVISO] Não foi possível extrair data inicial')
        else:
            print(f'DEBUG: [OK] Data inicial já disponível: {self.data_inicial_processo}')
        
        # ETAPA 2: Navegar para o iframe do formulário e extrair dados (SEM chamar aplicar_filtros novamente)
        print('\n=== ETAPA 2: NAVEGAÇÃO PARA IFRAME E EXTRAÇÃO DE DADOS ===')
        try:
            # Já estamos na URL correta do workspace flow, vamos direto para o form-web
            print('DEBUG: [INFO] Navegando direto para form-web sem duplicar navegação...')
            
            # Usar o ciclo detectado ou default para 2
            ciclo_para_usar = getattr(self, 'ciclo_processo', 2)
            
            # Construir URL direta do form-web
            form_url = f'https://justica.servicos.gov.br/form-web?processInstanceId={self.numero_processo_limpo}&activityInstanceId=24&cycle={ciclo_para_usar}&newWS=true'
            print(f'DEBUG: Navegando para form-web: {form_url}')
            
            # Navegar diretamente para o formulário
            self.driver.get(form_url)
            time.sleep(5)  # Aguardar carregar
            
            resultado_filtros = {'status': 'navegacao_concluida', 'data_inicial': self.data_inicial_processo}
            
            if resultado_filtros and resultado_filtros.get('status') == 'navegacao_concluida':
                print('[OK] Navegação para formulário concluída')
                
                # Tentar navegar para o iframe
                if self.navegar_para_iframe_form_app():
                    print('[OK] Estamos dentro do iframe do formulário')
                    
                    # Extrair dados específicos do form-web
                    dados_form_web = self.extrair_dados_do_formulario_form_web()
                    print(f'[OK] Dados extraídos do form-web: {len(dados_form_web)} campos')
                    
                    # Extrair dados tradicionais também
                    dados_pessoais = self.extrair_dados_pessoais_formulario()
                    
                    # Mesclar dados do form-web com dados tradicionais
                    if dados_form_web:
                        dados_pessoais.update(dados_form_web)
                        print(f'[OK] Dados mesclados: {len(dados_pessoais)} campos total')
                    else:
                        print('[AVISO] Usando apenas dados tradicionais')
                else:
                    print('[AVISO] Não foi possível navegar para iframe, extraindo dados tradicionais...')
                    dados_pessoais = self.extrair_dados_pessoais_formulario()
            else:
                print('[AVISO] Falha na navegação para formulário, extraindo dados tradicionais...')
                dados_pessoais = self.extrair_dados_pessoais_formulario()
            
            self.dados_pessoais_extraidos = dados_pessoais
            print("[OK] Dados pessoais extraídos com sucesso")
            
            # VERIFICAÇÃO: Garantir que temos data de nascimento
            if not dados_pessoais.get('data_nascimento'):
                print("[AVISO] Data de nascimento não foi extraída - tentando extração alternativa...")
                # Tentar extrair novamente usando métodos alternativos
                dados_alternativos = self.extrair_dados_pessoais_formulario()
                if dados_alternativos.get('data_nascimento'):
                    dados_pessoais.update(dados_alternativos)
                    print(f"[OK] Data de nascimento encontrada via método alternativo: {dados_pessoais.get('data_nascimento')}")
                else:
                    print("[ERRO] ERRO: Não foi possível extrair data de nascimento necessária para verificação de capacidade civil")
                    return {
                        'numero_processo': numero_processo,
                        'erro': 'Data de nascimento não encontrada no formulário',
                        'status': 'Erro'
                    }
            else:
                print(f"[OK] Data de nascimento confirmada: {dados_pessoais.get('data_nascimento')}")
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair dados pessoais: {e}")
            return {
                'numero_processo': numero_processo,
                'erro': f'Erro ao extrair dados pessoais: {e}',
                'status': 'Erro'
            }
        
        # ETAPA 3: Verificar se já temos a data inicial (deve ter sido extraída antes)
        if not hasattr(self, 'data_inicial_processo') or not self.data_inicial_processo:
            print("[ERRO] ERRO: Data inicial do processo não foi extraída antes!")
            return {
                'numero_processo': numero_processo,
                'erro': 'Data inicial do processo não disponível',
                'status': 'Erro'
            }
        
        # ETAPA 4: SEGUIR FLUXO EXATO CONFORME ESPECIFICADO
        print('\n=== FLUXO COMPLETO – NATURALIZAÇÃO ORDINÁRIA ===')
        print('Art. 65 da Lei nº 13.445/2017')
        print('='*80)
        
        # REQUISITO I – Capacidade civil
        print('\n[INFO] REQUISITO I – Capacidade civil')
        print('Verificação: Data de nascimento')
        
        resultado_capacidade = self.verificar_capacidade_civil_antes_download(
            dados_pessoais, 
            self.data_inicial_processo
        )
        
        # Verificar se é indeferimento automático por idade
        if resultado_capacidade.get('indeferimento_automatico', False):
            print('[ERRO] Não possui capacidade civil (menos de 18 anos)')
            print('📖 Fundamento: Art. 65, inciso I da Lei nº 13.445/2017')
            print('📋 Continuando análise para identificar TODOS os motivos de indeferimento')
            
            # Listar todos os motivos de indeferimento do art. 65
            self.listar_todos_motivos_indeferimento_art65()
            
            # Adicionar motivo de indeferimento à lista
            motivos_indeferimento = [resultado_capacidade['fundamento_legal']]
        else:
            print('[OK] Maior de 18 anos → check')
            motivos_indeferimento = []
        
        # REQUISITO II – Residência mínima (não retornar automaticamente)
        print('\n[INFO] REQUISITO II – Residência mínima')
        resultado_residencia = self.verificar_residencia_minima_com_validacao_ocr()
        
        if not resultado_residencia.get('pode_continuar', False):
            print('[ERRO] Não comprovou residência mínima')
            print('📖 Fundamento: Art. 65, inciso II da Lei nº 13.445/2017')
            motivos_indeferimento.append('Art. 65, inciso II da Lei nº 13.445/2017')
        else:
            print('[OK] Residência mínima → check')
        
        # REQUISITO III – Comunicação em língua portuguesa (não retornar automaticamente)
        print('\n[INFO] REQUISITO III – Comunicação em língua portuguesa')
        resultado_comunicacao = self.verificar_comunicacao_portugues_com_validacao_ocr()
        
        if not resultado_comunicacao.get('pode_continuar', False):
            if 'anexou' in resultado_comunicacao.get('motivo', '').lower():
                print('[ERRO] Não anexou item 13')
            else:
                print('[ERRO] Inválido, não atende aos requisitos do art 65 inciso III')
            print('📖 Fundamento: Art. 65, inciso III da Lei nº 13.445/2017')
            motivos_indeferimento.append('Art. 65, inciso III da Lei nº 13.445/2017')
        else:
            if resultado_comunicacao.get('dispensado', False):
                print('[OK] Comunicação em português → DISPENSADO (país lusófono)')
            else:
                print('[OK] Comunicação em português → check')
        
        # Armazenar resultados das verificações preliminares
        self.resultado_capacidade_civil = resultado_capacidade
        self.resultado_residencia_minima = resultado_residencia
        self.resultado_comunicacao = resultado_comunicacao
        
        # ETAPA 5: Os documentos já foram baixados individualmente nos requisitos II e III
        print('\n=== ETAPA 5: VERIFICAÇÕES PRELIMINARES CONCLUÍDAS ===')
        print('[OK] Documentos já validados individualmente:')
        if self.resultado_residencia_minima.get('tem_reducao'):
            print('   - Comprovante de redução de prazo: VÁLIDO')
        
        # Exibir status do documento de comunicação em português
        if self.resultado_comunicacao.get('dispensado', False):
            print('   - Comprovante de comunicação em português: DISPENSADO (país lusófono)')
        else:
            print('   - Comprovante de comunicação em português: VÁLIDO')
        
        # REQUISITO IV – Antecedentes criminais (baixar e validar individualmente)
        print('\n[INFO] REQUISITO IV – Antecedentes criminais')
        print('Baixando e validando documentos individualmente:')
        print('- Certidão de antecedentes criminais (Brasil)')
        print('- Certidão de antecedentes criminais (outros países)')
        print('- Comprovante de reabilitação (se necessário)')
        
        resultado_antecedentes = self.verificar_requisito_iv_com_download_individual()
        
        # Verificar se antecedentes criminais foram atendidos
        if not resultado_antecedentes.get('pode_continuar', False):
            print('[ERRO] Não comprovou ausência de condenação criminal')
            print('📖 Fundamento: Art. 65, inciso IV da Lei nº 13.445/2017')
            
            # Adicionar motivo específico baseado no documento que teve problema
            motivos_especificos = resultado_antecedentes.get('motivos_especificos', [])
            if motivos_especificos:
                for motivo in motivos_especificos:
                    motivos_indeferimento.append(f'Art. 65, inciso IV - {motivo}')
            else:
                motivos_indeferimento.append('Art. 65, inciso IV da Lei nº 13.445/2017')
        else:
            print('[OK] Antecedentes criminais → check')
        
        # DOCUMENTOS COMPLEMENTARES (baixar e validar individualmente os restantes)
        print('\n[INFO] DOCUMENTOS COMPLEMENTARES (Anexo I da Portaria 623/2020)')
        print('Baixando e validando documentos restantes individualmente:')
        print('- Comprovante de tempo de residência → item 8')
        print('- Comprovante de situação cadastral do CPF → item 4')
        print('- CRNM → item 3')
        print('- Documento de viagem internacional → item 2')
        
        resultado_documentos = self.verificar_documentos_complementares_com_download_individual()
        
        # DECISÃO FINAL - VERIFICAR TODOS OS REQUISITOS
        print('\n[INFO] DECISÃO FINAL')
        print('[BUSCA] Verificando TODOS os requisitos antes da decisão...')
        
        # Usar a lista de motivos de indeferimento já coletados
        requisitos_nao_atendidos = motivos_indeferimento.copy()
        documentos_faltantes = []
        
        # Verificar documentos complementares
        if not resultado_documentos.get('atendido', False):
            print('[ERRO] Documentos complementares incompletos')
            # A agregação efetiva acontecerá mais abaixo para evitar duplicidade
            pass
        
        # Exibir resumo dos requisitos
        print(f"\n📋 RESUMO DOS REQUISITOS DO ART. 65:")
        
        # Verificar se cada inciso está em motivos_indeferimento (usando busca mais específica)
        # Para o Inciso I, verificar se não há indeferimento automático por idade OU se não há motivos específicos
        inciso_i_ok = (not resultado_capacidade.get('indeferimento_automatico', False) and 
                      not any('inciso I ' in motivo for motivo in motivos_indeferimento))  # Adicionar espaço após "I"
        inciso_ii_ok = not any('inciso II ' in motivo for motivo in motivos_indeferimento)  # Adicionar espaço após "II"
        inciso_iii_ok = not any('inciso III ' in motivo for motivo in motivos_indeferimento)  # Adicionar espaço após "III"
        inciso_iv_ok = not any('inciso IV ' in motivo for motivo in motivos_indeferimento)  # Adicionar espaço após "IV"
        
        print(f"   ✅ Requisito I (Capacidade Civil): {'ATENDIDO' if inciso_i_ok else 'NÃO ATENDIDO'}")
        print(f"   ✅ Requisito II (Residência): {'ATENDIDO' if inciso_ii_ok else 'NÃO ATENDIDO'}")
        print(f"   ✅ Requisito III (Português): {'ATENDIDO' if inciso_iii_ok else 'NÃO ATENDIDO'}")
        print(f"   ✅ Requisito IV (Antecedentes): {'ATENDIDO' if inciso_iv_ok else 'NÃO ATENDIDO'}")
        
        # DOCUMENTOS COMPLEMENTARES
        if not resultado_documentos.get('atendido', False):
            print('[ERRO] Documentos complementares incompletos')
            docs_problemas = resultado_documentos.get('documentos_faltantes', []) + resultado_documentos.get('documentos_invalidos', [])
            documentos_faltantes.extend(docs_problemas)
            # Remover duplicados preservando a ordem
            documentos_faltantes = list(dict.fromkeys(documentos_faltantes))
        else:
            print('[OK] Documentos complementares completos')
        
        # Compilar TODOS os motivos
        motivos_indeferimento = requisitos_nao_atendidos + documentos_faltantes
        # Remover duplicados preservando a ordem para evitar motivos repetidos no despacho
        motivos_indeferimento = list(dict.fromkeys(motivos_indeferimento))
        
        # Inicializar variável de elegibilidade (para evitar UnboundLocalError)
        eligibilidade_final = 'indeferimento'  # Padrão
        
        print("\n" + "=" * 80)
        print("🔍 ANÁLISE FINAL DE REQUISITOS")
        print("=" * 80)
        print(f"📋 Total de motivos de indeferimento encontrados: {len(motivos_indeferimento)}")
        if motivos_indeferimento:
            for i, motivo in enumerate(motivos_indeferimento, 1):
                print(f"  {i}. {motivo}")
        
        # Decisão final baseada em TODOS os requisitos
        if not motivos_indeferimento:
            print('\n✅ DECISÃO PRELIMINAR: DEFERIMENTO')
            print('✅ Todos os requisitos I a IV e documentos obrigatórios estão válidos')
            print('✅ Não há motivos de indeferimento identificados')
            eligibilidade_final = 'deferimento'
        else:
            print('\n❌ DECISÃO PRELIMINAR: INDEFERIMENTO')
            print(f'❌ Foram identificados {len(motivos_indeferimento)} motivo(s) de indeferimento')
            print('❌ Motivos encontrados:')
            for i, motivo in enumerate(motivos_indeferimento, 1):
                print(f'  {i}. {motivo}')
            
            # Se há indeferimento automático por idade, exibir todos os motivos do art. 65
            if resultado_capacidade.get('indeferimento_automatico', False):
                print(f'\n📋 MOTIVOS DE INDEFERIMENTO - ART. 65 DA LEI Nº 13.445/2017:')
                print(f'   🔸 INCISO I: Capacidade Civil - NÃO ATENDIDO (menos de 18 anos)')
                
                # Usar a mesma lógica de verificação específica
                # Para o Inciso I, sempre NÃO ATENDIDO quando há indeferimento automático por idade
                inciso_i_ok = False  # Sempre falso quando há indeferimento automático por idade
                inciso_ii_ok = not any('inciso II ' in motivo for motivo in motivos_indeferimento)  # Adicionar espaço
                inciso_iii_ok = not any('inciso III ' in motivo for motivo in motivos_indeferimento)  # Adicionar espaço
                inciso_iv_ok = not any('inciso IV ' in motivo for motivo in motivos_indeferimento)  # Adicionar espaço
                
                print(f'   🔸 INCISO II: Residência no Brasil - {"ATENDIDO" if inciso_ii_ok else "NÃO ATENDIDO"}')
                print(f'   🔸 INCISO III: Comunicação em Português - {"ATENDIDO" if inciso_iii_ok else "NÃO ATENDIDO"}')
                print(f'   🔸 INCISO IV: Ausência de Condenação Criminal - {"ATENDIDO" if inciso_iv_ok else "NÃO ATENDIDO"}')
            
            elegibilidade_final = 'indeferimento'
        
        # ETAPA 6: Análise do Parecer da Polícia Federal
        print("\n" + "=" * 80)
        print("=== ETAPA 6: ANÁLISE DO PARECER DA POLÍCIA FEDERAL ===")
        print("=" * 80)
        
        parecer_pf = self._extrair_e_analisar_parecer_pf()
        
        print(f"\n📊 Resultado do Parecer PF:")
        print(f"   - Proposta PF: {parecer_pf.get('proposta_pf', 'N/A')}")
        print(f"   - Excedeu ausência: {'SIM ❌' if parecer_pf.get('excedeu_ausencia') else 'NÃO ✅'}")
        print(f"   - Problema com português: {'SIM ❌' if parecer_pf.get('problema_portugues') else 'NÃO ✅'}")
        
        # Verificar se parecer PF indica problemas críticos
        if parecer_pf.get('ausencia_pais', False):
            print("\n🚨 INDEFERIMENTO AUTOMÁTICO APLICADO: Requerente não está no país")
            print("   ⚠️ Conforme registro no Sistema de Tráfego Internacional - STI e no passaporte")
            print("   ⚠️ O requerente não se encontra em território nacional na data da entrada do processo")
            print("   ⚠️ Impedindo a continuidade do processo")
            print("   ⚠️ Decisão preliminar foi ALTERADA para INDEFERIMENTO")
            eligibilidade_final_anterior = eligibilidade_final
            eligibilidade_final = 'indeferimento'
            motivos_indeferimento.append('Requerente não se encontra em território nacional')
            print(f"   📝 Decisão mudou de '{eligibilidade_final_anterior}' para '{eligibilidade_final}'")
        
        if parecer_pf['excedeu_ausencia']:
            print("\n❌ INDEFERIMENTO AUTOMÁTICO APLICADO: Excedeu limite de ausência do país")
            print("   ⚠️ Decisão preliminar foi ALTERADA para INDEFERIMENTO")
            eligibilidade_final_anterior = eligibilidade_final
            eligibilidade_final = 'indeferimento'
            motivos_indeferimento.append('Excedeu limite de ausência do território nacional')
            print(f"   📝 Decisão mudou de '{eligibilidade_final_anterior}' para '{eligibilidade_final}'")
        
        if parecer_pf['problema_portugues']:
            print("\n❌ INDEFERIMENTO AUTOMÁTICO APLICADO: Documento de português invalidado")
            print("   ⚠️ Documento de português existe mas foi invalidado pelo atendimento presencial da PF")
            print("   📖 A PF constatou que o requerente NÃO consegue se comunicar em português")
            print("   ⚙️ O atendimento presencial sobrepõe o documento apresentado")
            print("   ⚠️ Decisão preliminar foi ALTERADA para INDEFERIMENTO")
            
            # Atualizar resultado do requisito III
            self.resultado_comunicacao = {
                'atendido': False,
                'motivo': 'Documento de proficiência em português INVALIDADO - não comprovado no atendimento presencial (conforme parecer PF)',
                'observacao': 'Constatado pela PF que o requerente não consegue se comunicar em português durante o atendimento'
            }
            
            # Adicionar aos motivos se ainda não está
            motivo_portugues = 'Art. 65, inciso III da Lei nº 13.445/2017 - Documento de português invalidado pelo atendimento presencial'
            if motivo_portugues not in motivos_indeferimento and 'Art. 65, inciso III' not in str(motivos_indeferimento):
                eligibilidade_final_anterior = eligibilidade_final
                motivos_indeferimento.append(motivo_portugues)
                eligibilidade_final = 'indeferimento'
                print(f"   📝 Decisão mudou de '{eligibilidade_final_anterior}' para '{eligibilidade_final}'")
        
        # ETAPA 7: Gerar decisão e planilha
        print("\n=== ETAPA 7: GERAÇÃO DE DECISÃO E PLANILHA ===")
        
        try:
            from analise_decisoes_ordinaria import AnaliseDecisoesOrdinaria
            
            # Compilar resultado final de elegibilidade
            print("\n" + "=" * 80)
            print("📦 COMPILANDO RESULTADO DE ELEGIBILIDADE PARA PLANILHA")
            print("=" * 80)
            print(f"🎯 eligibilidade_final: {eligibilidade_final}")
            print(f"📋 Total de motivos_indeferimento: {len(motivos_indeferimento)}")
            if motivos_indeferimento:
                print("❌ Motivos encontrados:")
                for i, motivo in enumerate(motivos_indeferimento, 1):
                    print(f"   {i}. {motivo}")
            else:
                print("✅ Nenhum motivo de indeferimento")
            
            print(f"\n📊 Estado dos Requisitos:")
            print(f"   I - Capacidade Civil: {'✅' if self.resultado_capacidade_civil.get('atendido', False) else '❌'}")
            print(f"   II - Residência Mínima: {'✅' if self.resultado_residencia_minima.get('atendido', False) else '❌'}")
            print(f"   III - Comunicação Português: {'✅' if self.resultado_comunicacao.get('atendido', False) else '❌'}")
            print(f"   IV - Antecedentes Criminais: {'✅' if resultado_antecedentes.get('atendido', False) else '❌'}")
            print(f"   Documentos Complementares: {'✅' if resultado_documentos.get('atendido', False) else '❌'}")
            print("=" * 80)
            
            resultado_elegibilidade = {
                'requisito_i_capacidade_civil': self.resultado_capacidade_civil,
                'requisito_ii_residencia_minima': self.resultado_residencia_minima,
                'requisito_iii_comunicacao_portugues': self.resultado_comunicacao,
                'requisito_iv_antecedentes_criminais': resultado_antecedentes,
                'documentos_complementares': resultado_documentos,
                'elegibilidade_final': eligibilidade_final,
                'requisitos_nao_atendidos': motivos_indeferimento,
                'documentos_faltantes': documentos_faltantes,  # Adicionar separadamente
                'dados_pessoais': self.dados_pessoais_extraidos,
                'data_inicial_processo': self.data_inicial_processo,
                'parecer_pf': parecer_pf  # Adicionar parecer PF
            }
            
            # Gerar decisão automática
            gerador_decisao = AnaliseDecisoesOrdinaria()
            resultado_decisao = gerador_decisao.gerar_decisao_automatica(resultado_elegibilidade)
            
            print("[OK] Decisão automática gerada")
            
            # Gerar resumo executivo
            resumo_executivo = gerador_decisao.gerar_resumo_executivo(resultado_elegibilidade, resultado_decisao)
            
            print("[OK] Resumo executivo gerado")
            
            # GERAR PLANILHA (igual aos outros tipos)
            print("[DADOS] Gerando planilha de resultados...")
            # Verificar se estamos processando uma lista específica
            processos_especificos = getattr(self, 'processos_especificos_em_processamento', None)
            resultado_planilha = self.gerar_planilha_resultado_ordinaria(
                numero_processo, 
                resultado_elegibilidade, 
                resultado_decisao,
                processos_especificos
            )
            
            print("[OK] Planilha gerada")
            
            # SALVAR DADOS PARA EXPORTAÇÃO
            print("[SALVO] Salvando dados para exportação...")
            self.salvar_dados_para_exportacao(numero_processo, resultado_elegibilidade, resultado_decisao)
            
        except Exception as e:
            print(f"[ERRO] Erro na geração de decisão e planilha: {e}")
            import traceback
            traceback.print_exc()
            
        # RESULTADO FINAL
        status_final = 'Deferimento' if elegibilidade_final == 'deferimento' else 'Indeferimento'
        
        print("\n" + "=" * 80)
        print("🎯 DECISÃO FINAL DO PROCESSO")
        print("=" * 80)
        print(f"📊 Elegibilidade Final: {eligibilidade_final.upper()}")
        print(f"✅ Status: {status_final}")
        print(f"📋 Total de motivos de indeferimento: {len(motivos_indeferimento)}")
        if motivos_indeferimento:
            print("❌ Motivos de indeferimento:")
            for i, motivo in enumerate(motivos_indeferimento, 1):
                print(f"   {i}. {motivo}")
        else:
            print("✅ Nenhum motivo de indeferimento encontrado")
        print("=" * 80)
        
        resultado = {
            'numero_processo': numero_processo,
            'codigo_processo': getattr(self, 'codigo_processo', None),
            'dados_pessoais': self.dados_pessoais_extraidos,
            'data_inicial_processo': self.data_inicial_processo,
            'resultado_capacidade_civil': self.resultado_capacidade_civil,
            'resultado_residencia_minima': self.resultado_residencia_minima,
            'resultado_comunicacao': self.resultado_comunicacao,
            'resultado_antecedentes': resultado_antecedentes,
            'resultado_documentos': resultado_documentos,
            'elegibilidade_final': elegibilidade_final,
            'motivos_indeferimento': motivos_indeferimento,
            'status': status_final,  # Status reconhecido pelo sistema
            'analise_elegibilidade': resultado_elegibilidade if 'resultado_elegibilidade' in locals() else None,
            'decisao_automatica': resultado_decisao if 'resultado_decisao' in locals() else None,
            'resumo_executivo': resumo_executivo if 'resumo_executivo' in locals() else None,
            'exportado_para_planilha': True,  # Indica que foi exportado
            'sucesso': True,
            'dados_planilha': resultado_planilha.get('dados') if 'resultado_planilha' in locals() and resultado_planilha.get('sucesso') else None
            }
        
        print('=== FIM processar_processo ===')
        
        # Retornar para workspace para o próximo processo
        print('DEBUG: Retornando para workspace...')
        try:
            # Navegação direta para workspace
            self.driver.get('https://justica.servicos.gov.br/workspace/')
            time.sleep(2)
            print('DEBUG: [OK] Retornou para workspace!')
        except Exception as e:
            print(f'ERRO ao retornar para workspace: {e}')
        
        return resultado

    def verificar_requisito_iv_completo(self, todos_textos_ocr):
        """
        REQUISITO IV – Antecedentes criminais (verificação completa com OCR)
        """
        try:
            from analise_elegibilidade_ordinaria import AnaliseElegibilidadeOrdinaria
            analisador = AnaliseElegibilidadeOrdinaria(self)
            return analisador._verificar_antecedentes_criminais(todos_textos_ocr)
        except Exception as e:
            print(f"[ERRO] Erro na verificação de antecedentes criminais: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}'
            }
    
    def verificar_documentos_complementares_final(self, todos_textos_ocr):
        """
        DOCUMENTOS COMPLEMENTARES (verificação final com OCR)
        """
        try:
            from analise_elegibilidade_ordinaria import AnaliseElegibilidadeOrdinaria
            analisador = AnaliseElegibilidadeOrdinaria(self)
            return analisador._verificar_documentos_complementares(todos_textos_ocr)
        except Exception as e:
            print(f"[ERRO] Erro na verificação de documentos complementares: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'documentos_faltantes': ['Erro na validação'],
                'documentos_invalidos': []
            }
    
    def _extrair_e_analisar_parecer_pf(self):
        """
        Extrai e analisa o parecer da Polícia Federal
        Retorna dict com parecer, proposta de ação e alertas
        """
        try:
            elemento_parecer = self.driver.find_element(By.ID, "CHPF_PARECER")
            parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
            
            if not parecer_texto:
                return {
                    'parecer_texto': '',
                    'proposta_pf': 'Não encontrado',
                    'excedeu_ausencia': False,
                    'problema_portugues': False,
                    'alertas': []
                }
            
            alertas = []
            import re
            
            # Verificar se excedeu limite de ausência do país
            excedeu_ausencia = False
            
            # Primeiro verificar se NÃO excedeu (padrões negativos)
            padroes_nao_excedeu = [
                r'não\s+ausentou.*excedendo',
                r'não\s+excede',
                r'não\s+excedeu',
                r'nao\s+ausentou.*excedendo',
                r'nao\s+excede',
                r'nao\s+excedeu',
                r'não.*excedendo\s+o\s+prazo',
                r'nao.*excedendo\s+o\s+prazo'
            ]
            
            tem_negacao = False
            for padrao_neg in padroes_nao_excedeu:
                if re.search(padrao_neg, parecer_texto, re.IGNORECASE):
                    tem_negacao = True
                    print("✅ [PF] Parecer confirma que NÃO excedeu limite de ausência")
                    break
            
            # Se não tem negação, verificar padrões positivos
            if not tem_negacao:
                padroes_ausencia_positiva = [
                    r'(?<!não\s)(?<!nao\s)excedendo\s+o\s+prazo\s+máximo\s+de\s+ausência',
                    r'(?<!não\s)(?<!nao\s)excede.*prazo.*ausência',
                    r'ausentou.*superior\s+a\s+\d+\s+meses',
                    r'período\s+superior\s+a\s+12\s+meses',
                    # NOVO: Padrão específico para 90 dias
                    r'se\s+ausentou\s+do\s+território\s+nacional\s+por\s+período\s+superior\s+a\s+90\s+dias\s+em\s+12\s+meses',
                    r'ausentou.*superior\s+a\s+90\s+dias\s+em\s+12\s+meses',
                    r'excedendo\s+o\s+prazo\s+máximo\s+permitido\s+pela\s+legislação',
                    r'(?<!não\s)(?<!nao\s)excedeu\s+o\s+limite'
                ]
                
                # Verificar se há negação específica para 90 dias
                padroes_negacao_90_dias = [
                    r'não\s+se\s+ausentou.*90\s+dias',
                    r'nao\s+se\s+ausentou.*90\s+dias',
                    r'não\s+ausentou.*90\s+dias',
                    r'nao\s+ausentou.*90\s+dias'
                ]
                
                # Padrões específicos para excesso de ausências (29 meses em 4 anos, 11 meses em 12 meses)
                padroes_excesso_ausencias = [
                    r'se\s+ausentou\s+do\s+território\s+nacional\s+por\s+período\s+superior\s+a\s+29\s+meses',
                    r'se\s+ausentou\s+do\s+territorio\s+nacional\s+por\s+periodo\s+superior\s+a\s+29\s+meses',
                    r'se\s+ausentou.*superior\s+a\s+29\s+meses.*últimos\s+4\s+anos',
                    r'se\s+ausentou.*superior\s+a\s+29\s+meses.*ultimos\s+4\s+anos',
                    r'se\s+ausentou\s+do\s+território\s+nacional\s+por\s+período\s+superior\s+a\s+11\s+meses',
                    r'se\s+ausentou\s+do\s+territorio\s+nacional\s+por\s+periodo\s+superior\s+a\s+11\s+meses',
                    r'se\s+ausentou.*superior\s+a\s+11\s+meses.*últimos\s+12\s+meses',
                    r'se\s+ausentou.*superior\s+a\s+11\s+meses.*ultimos\s+12\s+meses',
                    r'excedendo\s+o\s+prazo\s+máximo\s+permitido\s+pela\s+legislação',
                    r'excedendo\s+o\s+prazo\s+maximo\s+permitido\s+pela\s+legislacao'
                ]
                
                tem_negacao_90_dias = False
                for padrao_neg in padroes_negacao_90_dias:
                    if re.search(padrao_neg, parecer_texto, re.IGNORECASE):
                        tem_negacao_90_dias = True
                        print("✅ [PF] Parecer confirma que NÃO excedeu limite de 90 dias")
                        break
                
                for padrao in padroes_ausencia_positiva:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        # Verificar se é padrão de 90 dias e se há negação específica
                        if '90\s+dias' in padrao and tem_negacao_90_dias:
                            print("✅ [PF] Padrão de 90 dias detectado, mas há negação específica - ignorando")
                            continue
                        excedeu_ausencia = True
                        alertas.append('⚠️ EXCEDEU LIMITE DE AUSÊNCIA DO PAÍS')
                        print("❌ ALERTA: Parecer PF indica que requerente EXCEDEU limite de ausência do país")
                        break
                
                # Verificar padrões específicos de excesso de ausências
                for padrao in padroes_excesso_ausencias:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        excedeu_ausencia = True
                        alertas.append('🚨 EXCEDEU LIMITE DE AUSÊNCIAS - INDEFERIMENTO AUTOMÁTICO')
                        print("🚨 ALERTA CRÍTICO: Parecer PF indica que requerente EXCEDEU limite de ausências")
                        print("   → INDEFERIMENTO AUTOMÁTICO necessário")
                        break
            
            # Verificar se documentos não foram apresentados
            documentos_nao_apresentados = False
            documentos_apresentados_integralmente = False
            nao_compareceu_pf = False
            padroes_documentos_nao_apresentados = [
                r'a\s+relação\s+de\s+documentos\s+exigidos.*não\s+foi\s+apresentada\s+integralmente',
                r'a\s+relação\s+de\s+documentos\s+exigidos.*não\s+foi\s+apresentada',
                r'documentos\s+exigidos.*não\s+foi\s+apresentada\s+integralmente',
                r'documentos\s+exigidos.*não\s+foi\s+apresentada',
                r'não\s+foi\s+apresentada\s+integralmente.*documentos',
                r'não\s+foi\s+apresentada.*documentos',
                r'não\s+anexando',
                r'não\s+apresentou',
                r'não\s+compareceu.*agendamento',
                r'não\s+compareceu.*notificação',
                r'não\s+compareceu.*coleta\s+biométrica',
                r'não\s+compareceu.*conferência\s+documental'
            ]
            
            # Padrões específicos para não comparecimento à PF
            padroes_nao_compareceu = [
                r'não\s+compareceu\s+à\s+unidade\s+para\s+apresentar\s+a\s+documentação',
                r'nao\s+compareceu\s+a\s+unidade\s+para\s+apresentar\s+a\s+documentacao',
                r'não\s+compareceu\s+à\s+unidade.*coletar.*dados\s+biométricos',
                r'nao\s+compareceu\s+a\s+unidade.*coletar.*dados\s+biometricos',
                r'requerente\s+não\s+compareceu\s+à\s+unidade',
                r'requerente\s+nao\s+compareceu\s+a\s+unidade',
                r'não\s+compareceu.*apresentar.*documentação.*coletar.*biométricos',
                r'nao\s+compareceu.*apresentar.*documentacao.*coletar.*biometricos'
            ]
            
            # Guard-rail: frase afirmando que documentos foram apresentados integralmente
            if re.search(r"\b(foi|foram)\s+apresentad[ao]s?\s+integralmente\b", parecer_texto, re.IGNORECASE):
                documentos_apresentados_integralmente = True
                print("✅ [PF] Parecer indica que documentos foram APRESENTADOS INTEGRALMENTE")

            # Primeiro detectar NÃO COMPARECEU / BIOMETRIA
            for padrao in padroes_nao_compareceu:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    nao_compareceu_pf = True
                    print("❌ [PF] Requerente não compareceu à unidade da PF (impacta biometria e conferência)")
                    break

            # Só marcar documentos não apresentados se NÃO for caso de não comparecimento
            if not nao_compareceu_pf and not documentos_apresentados_integralmente:
                for padrao in padroes_documentos_nao_apresentados:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        documentos_nao_apresentados = True
                        print("❌ [PF] Documentos não foram apresentados integralmente")
                        break
            
            # Verificar se não compareceu à PF (já detectado acima, manter idempotente)
            if not nao_compareceu_pf:
                for padrao in padroes_nao_compareceu:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        nao_compareceu_pf = True
                        print("❌ [PF] Requerente não compareceu à unidade da PF")
                        break
            
            # Adicionar alerta se documentos não foram apresentados
            if documentos_nao_apresentados:
                alertas.append('⚠️ DOCUMENTOS NÃO APRESENTADOS INTEGRALMENTE')
                print("❌ ALERTA: Parecer PF indica que documentos não foram apresentados integralmente")
            
            # Adicionar alerta se não compareceu à PF
            if nao_compareceu_pf:
                alertas.append('🚨 REQUERENTE NÃO COMPARECEU À PF - INDEFERIMENTO AUTOMÁTICO')
                print("🚨 ALERTA CRÍTICO: Requerente não compareceu à unidade da PF")
                print("   → INDEFERIMENTO AUTOMÁTICO necessário")

            # Alerta de ausência de PRAZO claro no parecer (tempo de residência não identificado)
            # Detecta menções de residência sem números ou datas que permitam cálculo de tempo
            menciona_residencia = re.search(r"resid[êe]ncia|indeterminad|permanente", parecer_texto, re.IGNORECASE)
            menciona_prazo = re.search(r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d+\s+anos?|\d+\s+meses?)\b", parecer_texto, re.IGNORECASE)
            if menciona_residencia and not menciona_prazo:
                alertas.append('⚠️ PARECER PF SEM PRAZO DE RESIDÊNCIA ESPECIFICADO')
                print("⚠️ ALERTA: Parecer PF menciona residência mas não especifica prazo/tempo")

            # Alerta de possível ausência de coleta biométrica (sem comparecimento explícito)
            padrao_biometria = r"n[ãa]o\s+compareceu.*coleta.*biom[ée]tric|deixamos\s+realizar\s+a\s+coleta.*biometr|dispensa\s+da\s+coleta.*biom[ée]rica|coleta.*biom[ée]tric[oa]s?.*n[ãa]o\s+(foi|fora)\s+(efetuada|feita)|n[ãa]o\s+(foi|fora)\s+(efetuada|feita).*coleta.*biom[ée]tric[oa]s?"
            if re.search(padrao_biometria, parecer_texto, re.IGNORECASE):
                alertas.append('⚠️ AUSÊNCIA DE COLETA BIOMÉTRICA CONSTATADA NO PARECER PF')
                print("⚠️ ALERTA: Indício de ausência de coleta biométrica no parecer da PF")

            # Padrões adicionais para excesso de ausências descritos em linguagem natural
            if not excedeu_ausencia:
                if re.search(r"limite\s+permitido\s+de\s+aus[êe]ncia.*n[ãa]o\s+foi\s+observado", parecer_texto, re.IGNORECASE):
                    excedeu_ausencia = True
                    alertas.append('⚠️ EXCEDEU LIMITE DE AUSÊNCIA DO PAÍS')
                    print("❌ ALERTA: Parecer PF indica excesso de ausências (limite não observado)")
            
            # Verificar se há problemas com faculdades no e-MEC
            faculdade_invalida = False
            padroes_faculdade_invalida = [
                r'cnpj.*consta\s+como\s+sendo\s+de\s+outra\s+instituição',
                r'cnpj.*consta.*outra\s+instituição\s+de\s+ensino',
                r'instituição\s+de\s+ensino.*não\s+funciona.*endereço',
                r'instituicao\s+de\s+ensino.*nao\s+funciona.*endereco',
                r'faculdade.*não\s+funciona.*endereço.*desde',
                r'faculdade.*nao\s+funciona.*endereco.*desde',
                r'site.*não\s+são\s+mais\s+válidos',
                r'site.*nao\s+sao\s+mais\s+validos',
                r'e-mails.*não\s+são\s+mais\s+válidos',
                r'e-mails.*nao\s+sao\s+mais\s+validos',
                r'não\s+foram\s+encontrados.*sites.*ativos',
                r'nao\s+foram\s+encontrados.*sites.*ativos',
                r'pesquisas.*não.*encontrados.*outros.*sites.*ativos',
                r'pesquisas.*nao.*encontrados.*outros.*sites.*ativos'
            ]
            
            for padrao in padroes_faculdade_invalida:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    faculdade_invalida = True
                    print("❌ [PF] Faculdade inválida detectada no e-MEC")
                    break
            
            # Adicionar alerta se faculdade é inválida
            if faculdade_invalida:
                alertas.append('⚠️ FACULDADE INVÁLIDA NO E-MEC - DOCUMENTO DE PORTUGUÊS INVÁLIDO')
                print("❌ ALERTA: Parecer PF indica que faculdade é inválida no e-MEC")
                print("   → Documento de português deve ser considerado INVÁLIDO")
            
            # Verificar se requerente está no país
            ausencia_pais = False
            
            # Padrões para detectar ausência do país
            padroes_ausencia_pais = [
                r'não\s+se\s+encontra\s+em\s+território\s+nacional',
                r'nao\s+se\s+encontra\s+em\s+territorio\s+nacional',
                r'não\s+encontra\s+em\s+território\s+nacional',
                r'nao\s+encontra\s+em\s+territorio\s+nacional',
                r'ausente\s+do\s+território\s+nacional',
                r'ausente\s+do\s+territorio\s+nacional',
                r'fora\s+do\s+território\s+nacional',
                r'fora\s+do\s+territorio\s+nacional',
                r'impedindo\s+a\s+continuidade\s+do\s+processo',
                r'impedindo\s+a\s+continuidade',
                r'não\s+se\s+encontra.*território.*nacional.*data.*entrada.*processo',
                r'nao\s+se\s+encontra.*territorio.*nacional.*data.*entrada.*processo'
            ]
            
            for padrao in padroes_ausencia_pais:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    ausencia_pais = True
                    alertas.append('🚨 REQUERENTE NÃO ESTÁ NO PAÍS - INDEFERIMENTO AUTOMÁTICO')
                    print("🚨 ALERTA CRÍTICO: Requerente não se encontra em território nacional")
                    print("   → INDEFERIMENTO AUTOMÁTICO necessário")
                    break
            
            # Verificar comunicação em português no atendimento
            problema_portugues = False
            comunicacao_comprovada = False
            
            # PRIMEIRO: Verificar se há negação explícita
            padroes_negacao = [
                r'(?:não|nao)\s+foi\s+comprovad[ao]',
                r'(?:não|nao)\s+comprovad[ao]',
                r'capacidade.*comunicar.*portugu[eê]s.*(?:não|nao)\s+foi\s+comprovad[ao]',
                r'sua\s+capacidade.*comunicar.*portugu[eê]s.*(?:não|nao)\s+foi\s+comprovad[ao]',
                r'ausência\s+de\s+apresentação\s+do\s+documento\s+respectivo',
                r'tendo\s+em\s+vista\s+a\s+ausência\s+de\s+apresentação'
            ]
            
            tem_negacao = False
            for padrao in padroes_negacao:
                if re.search(padrao, parecer_texto, re.IGNORECASE):
                    tem_negacao = True
                    problema_portugues = True
                    print("❌ [PF] Comunicação em português NÃO foi comprovada (negação detectada)")
                    break
            
            # SEGUNDO: Se não há negação, verificar se foi comprovada
            if not tem_negacao:
                padroes_doc_comprovado = [
                    r'foi\s+comprovad[ao].*atendimento\s+presencial',
                    r'comprovad[ao].*atendimento.*presencial',
                    r'confirmada\s+durante.*atendimento\s+presencial',
                    r'capacidade.*comunicar.*portugu[eê]s.*comprovad[ao]',
                    # NOVO: Casos especiais onde consegue se comunicar apesar de deficiência
                    r'apesar\s+da\s+deficiência.*consegue.*comunicar.*português.*satisfatória',
                    r'apesar.*deficiência.*consegue.*se\s+comunicar.*português',
                    r'consegue.*se\s+comunicar.*português.*maneira.*satisfatória',
                ]
                
                for padrao in padroes_doc_comprovado:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        comunicacao_comprovada = True
                        print("✅ [PF] Comunicação em português FOI COMPROVADA no atendimento presencial")
                        break
            
            # Adicionar alerta se problema com português foi detectado
            if problema_portugues:
                    alertas.append('⚠️ DOCUMENTO DE PORTUGUÊS NÃO COMPROVADO NO ATENDIMENTO PRESENCIAL')
                    print("❌ ALERTA: Documento de proficiência não foi comprovado no atendimento presencial")
            
            # Padrão 2: Não consegue se comunicar em português
            if not problema_portugues:
                padroes_portugues = [
                    r'não\s+consegue\s+se\s+comunicar\s+em\s+língua\s+portuguesa',
                    r'não.*comunicar.*português',
                    r'sem\s+comunicação\s+em\s+português',
                    r'não\s+demonstrou\s+proficiência'
                ]
                
                for padrao in padroes_portugues:
                    if re.search(padrao, parecer_texto, re.IGNORECASE):
                        problema_portugues = True
                        alertas.append('⚠️ NÃO CONSEGUE SE COMUNICAR EM PORTUGUÊS (atendimento presencial)')
                        print("❌ ALERTA: Parecer PF indica que requerente NÃO consegue se comunicar em português")
                        break
            
            # Extrair decisão/proposta de ação da PF (CHPF_ACAO)
            proposta_pf = 'Não especificado'
            
            # Tentar múltiplos métodos de extração
            try:
                # Método 1: Via label com aria-checked="true"
                elemento_acao = self.driver.find_element(By.XPATH, "//label[contains(text(), 'Propor Deferimento') and contains(@aria-checked, 'true')]")
                if elemento_acao:
                    proposta_pf = 'Propor Deferimento'
                    print("[PF] Decisão extraída (método 1): Propor Deferimento")
            except:
                try:
                    # Método 2: Procurar por Propor Indeferimento
                    elemento_acao = self.driver.find_element(By.XPATH, "//label[contains(text(), 'Propor Indeferimento') and contains(@aria-checked, 'true')]")
                    if elemento_acao:
                        proposta_pf = 'Propor Indeferimento'
                        print("[PF] Decisão extraída (método 2): Propor Indeferimento")
                except:
                    try:
                        # Método 3: Buscar pelo ID do campo CHPF_ACAO
                        elemento_acao = self.driver.find_element(By.ID, "CHPF_ACAO_0")
                        if elemento_acao.is_selected() or elemento_acao.get_attribute('aria-checked') == 'true':
                            proposta_pf = 'Propor Indeferimento'
                            print("[PF] Decisão extraída (método 3 - ID): Propor Indeferimento")
                    except:
                        try:
                            # Método 4: Buscar por qualquer label marcado
                            labels_marcados = self.driver.find_elements(By.XPATH, "//label[@role='radio' and @aria-checked='true']")
                            for label in labels_marcados:
                                texto = label.text
                                if 'Propor Deferimento' in texto:
                                    proposta_pf = 'Propor Deferimento'
                                    print("[PF] Decisão extraída (método 4): Propor Deferimento")
                                    break
                                elif 'Propor Indeferimento' in texto:
                                    proposta_pf = 'Propor Indeferimento'
                                    print("[PF] Decisão extraída (método 4): Propor Indeferimento")
                                    break
                        except:
                            print("[AVISO] Não foi possível extrair a decisão da PF")
                            pass
            
            print(f"[PF] Parecer extraído: {len(parecer_texto)} caracteres")
            print(f"[PF] Proposta PF: {proposta_pf}")
            if alertas:
                for alerta in alertas:
                    print(f"[PF] {alerta}")
            
            return {
                'parecer_texto': parecer_texto,
                'proposta_pf': proposta_pf,
                'excedeu_ausencia': excedeu_ausencia,
                'ausencia_pais': ausencia_pais,
                'problema_portugues': problema_portugues,
                'nao_compareceu_pf': nao_compareceu_pf,
                'documentos_nao_apresentados': documentos_nao_apresentados,
                'faculdade_invalida': faculdade_invalida,
                'alertas': alertas
            }
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair parecer PF: {e}")
            return {
                'parecer_texto': '',
                'proposta_pf': 'Erro ao extrair',
                'excedeu_ausencia': False,
                'problema_portugues': False,
                'nao_compareceu_pf': False,
                'documentos_nao_apresentados': False,
                'faculdade_invalida': False,
                'alertas': []
            }
    
    def _gerar_despacho_automatico(self, numero_processo, resultado_elegibilidade):
        """
        Gera texto do despacho automático para casos de DEFERIMENTO
        """
        try:
            # Extrair dados necessários
            dados_pessoais = resultado_elegibilidade.get('dados_pessoais', {})
            nome_completo = dados_pessoais.get('nome_completo', '[NOME COMPLETO]')
            data_nascimento = dados_pessoais.get('data_nascimento', '[DATA DE NASCIMENTO]')
            nacionalidade = dados_pessoais.get('nacionalidade', '[PAÍS DE NASCIMENTO]')
            rnm = dados_pessoais.get('rnm', '[RNM]')
            pai = dados_pessoais.get('pai', '[PAI]')
            mae = dados_pessoais.get('mae', '[MÃE]')
            estado = dados_pessoais.get('estado', dados_pessoais.get('uf', '[ESTADO]'))
            
            # Texto do despacho
            despacho = f"""Assunto: Deferimento do pedido
Processo: {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623, de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, RESOLVE, tendo em vista o cumprimento do Art. 65 da Lei nº 13.445/2017, e demais requisitos previstos na legislação vigente:

CONCEDER a nacionalidade brasileira, por naturalização, à pessoa abaixo relacionada, nos termos do art. 12, II, "a", da Constituição Federal, e em conformidade com o Art. 65 da Lei nº 13.445, de 24 de maio de 2017, regulamentada pelo Decreto nº 9.199, de 20 de novembro de 2017, a fim de que possa gozar dos direitos outorgados pela Constituição e leis do Brasil:

{nome_completo} – RNM {rnm}, natural do {nacionalidade}, nascido em {data_nascimento}, filho de {pai} e de {mae}, residente no estado do {estado} (Processo nº {numero_processo});"""
            
            return despacho
            
        except Exception as e:
            print(f"[ERRO] Erro ao gerar despacho automático: {e}")
            return "Erro ao gerar despacho"
    
    def gerar_planilha_resultado_ordinaria(self, numero_processo, resultado_elegibilidade, resultado_decisao, processos_especificos=None):
        """
        Consolida resultado em planilha única para todos os processos
        Se processos_especificos for fornecido, cria planilha apenas com esses processos
        """
        try:
            import pandas as pd
            from datetime import datetime
            import os
            
            # LOG: Verificar o que chegou na função
            print("\n" + "=" * 80)
            print("📊 GERANDO PLANILHA - DADOS RECEBIDOS")
            print("=" * 80)
            print(f"🆔 Processo: {numero_processo}")
            print(f"🎯 elegibilidade_final recebido: {resultado_elegibilidade.get('elegibilidade_final')}")
            print(f"📋 requisitos_nao_atendidos: {resultado_elegibilidade.get('requisitos_nao_atendidos')}")
            print(f"📄 documentos_faltantes: {resultado_elegibilidade.get('documentos_faltantes')}")
            print("=" * 80)
            
            # Determinar resultado final
            if resultado_elegibilidade.get('elegibilidade_final') == 'deferimento':
                print("✅ RESULTADO FINAL DETERMINADO: DEFERIMENTO")
                resultado_final = 'Deferimento'
                motivo_indeferimento = 'N/A'
                # Gerar despacho automático para deferimento
                despacho_automatico = self._gerar_despacho_automatico(numero_processo, resultado_elegibilidade)
            else:
                print("❌ RESULTADO FINAL DETERMINADO: INDEFERIMENTO")
                resultado_final = 'Indeferimento'
                # Combinar motivos dos requisitos e documentos faltantes
                motivos_requisitos = resultado_elegibilidade.get('requisitos_nao_atendidos', [])
                motivos_documentos = resultado_elegibilidade.get('documentos_faltantes', [])
                todos_motivos = motivos_requisitos + motivos_documentos
                print(f"📋 Motivos compilados: {len(todos_motivos)} total")
                print(f"   - Requisitos não atendidos: {len(motivos_requisitos)}")
                print(f"   - Documentos faltantes: {len(motivos_documentos)}")
                if todos_motivos:
                    print("❌ Lista de motivos:")
                    for i, motivo in enumerate(todos_motivos, 1):
                        print(f"   {i}. {motivo}")
                motivo_indeferimento = '; '.join(todos_motivos) if todos_motivos else 'Não especificado'
                despacho_automatico = 'N/A'
            
            # Calcular total de documentos validados
            documentos_complementares = resultado_elegibilidade.get('documentos_complementares', {})
            total_documentos = 4  # Requisitos I, II, III, IV
            documentos_validados = sum([
                1 if resultado_elegibilidade.get('requisito_i_capacidade_civil', {}).get('atendido', False) else 0,
                1 if resultado_elegibilidade.get('requisito_ii_residencia_minima', {}).get('atendido', False) else 0,
                1 if resultado_elegibilidade.get('requisito_iii_comunicacao_portugues', {}).get('atendido', False) else 0,
                1 if resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {}).get('atendido', False) else 0
            ])
            
            # Adicionar documentos complementares validados
            docs_complementares_validados = int((documentos_complementares.get('percentual_completude', 0) / 100) * 4)  # 4 documentos complementares
            total_documentos += 4
            documentos_validados += docs_complementares_validados
            
            # Extrair informações do parecer PF
            parecer_pf = resultado_elegibilidade.get('parecer_pf', {})
            parecer_texto = parecer_pf.get('parecer_texto', 'N/A')
            proposta_pf = parecer_pf.get('proposta_pf', 'Não especificado')
            alertas_pf = ' | '.join(parecer_pf.get('alertas', [])) if parecer_pf.get('alertas') else 'Nenhum'
            
            # Especificar qual antecedente falta (se requisito IV não atendido)
            req_iv_detalhado = '✅ ATENDIDO'
            if not resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {}).get('atendido', False):
                motivo_iv = resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {}).get('motivo', '')
                if 'brasil' in motivo_iv.lower():
                    req_iv_detalhado = '❌ NÃO ATENDIDO (BRASIL)'
                elif 'país' in motivo_iv.lower() or 'origem' in motivo_iv.lower():
                    req_iv_detalhado = '❌ NÃO ATENDIDO (PAÍS DE ORIGEM)'
                else:
                    req_iv_detalhado = '❌ NÃO ATENDIDO'
            
            # Criar dados da linha para este processo
            dados_linha = {
                'Número do Processo': numero_processo,
                'Código do Processo': getattr(self, 'codigo_processo', 'N/A'),
                'Nome': resultado_elegibilidade.get('dados_pessoais', {}).get('nome_completo', 'N/A'),
                'Data Inicial': resultado_elegibilidade.get('data_inicial_processo', 'N/A'),
                'Tipo de Análise': 'Naturalização Ordinária',
                'Resultado': resultado_final,
                'Motivo do Indeferimento': motivo_indeferimento,
                'Decisão PF': proposta_pf,
                'Alertas PF': alertas_pf,
                'Despacho Automático': despacho_automatico,
                'Requisito I (Capacidade Civil)': '✅ ATENDIDO' if resultado_elegibilidade.get('requisito_i_capacidade_civil', {}).get('atendido', False) else '❌ NÃO ATENDIDO',
                'Requisito II (Residência Mínima)': '✅ ATENDIDO' if resultado_elegibilidade.get('requisito_ii_residencia_minima', {}).get('atendido', False) else '❌ NÃO ATENDIDO',
                'Requisito III (Comunicação Português)': '✅ ATENDIDO' if resultado_elegibilidade.get('requisito_iii_comunicacao_portugues', {}).get('atendido', False) else '❌ NÃO ATENDIDO',
                'Requisito IV (Antecedentes Criminais)': req_iv_detalhado,
                'Documentos Complementares': f"✅ {documentos_complementares.get('percentual_completude', 0):.0f}% ({docs_complementares_validados}/4)",
                'Total de Documentos Validados': f"{documentos_validados}/{total_documentos}",
                'Percentual de Documentos Validados': f"{(documentos_validados/total_documentos)*100:.1f}%",
                'Data da Análise': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'Hora da Análise': datetime.now().strftime('%H:%M:%S'),
                'Parecer PF': parecer_texto[:500] + '...' if len(parecer_texto) > 500 else parecer_texto,  # Limitar tamanho
                'Observações': resultado_decisao.get('resumo', 'N/A') if resultado_decisao else 'N/A'
            }
            
            # Determinar nome do arquivo baseado se há processos específicos
            if processos_especificos:
                # Criar planilha específica para os processos fornecidos
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                nome_arquivo = f"analise_ordinaria_especifica_{timestamp}.xlsx"
                print(f"[DADOS] Criando planilha específica para {len(processos_especificos)} processos")
            else:
                # Usar planilha consolidada padrão
                nome_arquivo = "analise_ordinaria_consolidada.xlsx"
                print(f"[DADOS] Usando planilha consolidada padrão")
            
            caminho_arquivo = os.path.join(os.getcwd(), 'planilhas', nome_arquivo)
            
            # Criar diretório se não existir
            os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
            
            # Verificar se planilha já existe para adicionar nova linha
            if os.path.exists(caminho_arquivo) and not processos_especificos:
                # Carregar planilha existente (apenas para planilha consolidada)
                df_existente = pd.read_excel(caminho_arquivo)
                
                # Adicionar nova linha
                df_novo = pd.DataFrame([dados_linha])
                df = pd.concat([df_existente, df_novo], ignore_index=True)
                
                # Deduplicar por Número do Processo mantendo a última ocorrência
                if 'Número do Processo' in df.columns:
                    tamanho_antes = len(df)
                    df = df.drop_duplicates(subset=['Número do Processo'], keep='last')
                    tamanho_depois = len(df)
                    if tamanho_depois < tamanho_antes:
                        print(f"[DADOS] Removidas {tamanho_antes - tamanho_depois} duplicata(s) por Número do Processo")
                
                print(f"[DADOS] Adicionando processo à planilha consolidada existente")
            else:
                # Criar nova planilha
                df = pd.DataFrame([dados_linha])
                if processos_especificos:
                    print(f"[DADOS] Criando nova planilha específica (não consolidada)")
                else:
                    print(f"[DADOS] Criando nova planilha consolidada")
            
            # Salvar planilha
            df.to_excel(caminho_arquivo, index=False)
            
            if processos_especificos:
                print(f"[DADOS] Planilha específica criada: {caminho_arquivo}")
                print(f"[DADOS] Total de processos na planilha específica: {len(df)}")
            else:
                print(f"[DADOS] Planilha consolidada atualizada: {caminho_arquivo}")
                print(f"[DADOS] Total de processos na planilha consolidada: {len(df)}")
            
            # Log detalhado dos resultados
            print(f"\n{'='*80}")
            print(f"📊 RESUMO DA ANÁLISE - PROCESSO {numero_processo}")
            print(f"{'='*80}")
            print(f"🕐 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            print(f"👤 Nome: {resultado_elegibilidade.get('dados_pessoais', {}).get('nome_completo', 'N/A')}")
            print(f"📋 Resultado: {resultado_final}")
            print(f"📄 Total de Documentos Validados: {documentos_validados}/{total_documentos} ({(documentos_validados/total_documentos)*100:.1f}%)")
            print(f"\n📋 REQUISITOS:")
            print(f"   I - Capacidade Civil: {'✅ ATENDIDO' if resultado_elegibilidade.get('requisito_i_capacidade_civil', {}).get('atendido', False) else '❌ NÃO ATENDIDO'}")
            print(f"   II - Residência Mínima: {'✅ ATENDIDO' if resultado_elegibilidade.get('requisito_ii_residencia_minima', {}).get('atendido', False) else '❌ NÃO ATENDIDO'}")
            print(f"   III - Comunicação Português: {'✅ ATENDIDO' if resultado_elegibilidade.get('requisito_iii_comunicacao_portugues', {}).get('atendido', False) else '❌ NÃO ATENDIDO'}")
            print(f"   IV - Antecedentes Criminais: {'✅ ATENDIDO' if resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {}).get('atendido', False) else '❌ NÃO ATENDIDO'}")
            print(f"   📄 Documentos Complementares: ✅ {documentos_complementares.get('percentual_completude', 0):.0f}% ({docs_complementares_validados}/4)")
            print(f"{'='*80}")
            
            return {
                'arquivo': caminho_arquivo,
                'dados': dados_linha,
                'sucesso': True
            }
            
        except Exception as e:
            print(f"[ERRO] Erro ao gerar planilha: {e}")
            import traceback
            traceback.print_exc()
            return {
                'arquivo': None,
                'erro': str(e),
                'sucesso': False
            }

    def processar_lista_processos_ordinaria(self, lista_processos):
        """
        Processa uma lista específica de processos e gera planilha apenas com esses processos
        """
        try:
            print(f"\n{'='*100}")
            print(f"🚀 PROCESSANDO LISTA ESPECÍFICA DE PROCESSOS ORDINÁRIA")
            print(f"{'='*100}")
            print(f"📋 Total de processos a processar: {len(lista_processos)}")
            
            resultados_processados = []
            processos_com_sucesso = 0
            processos_com_erro = 0
            
            for i, numero_processo in enumerate(lista_processos, 1):
                print(f"\n{'='*80}")
                print(f"📋 PROCESSO {i}/{len(lista_processos)}: {numero_processo}")
                print(f"{'='*80}")
                
                try:
                    # Marcar que estamos processando uma lista específica
                    self.processos_especificos_em_processamento = lista_processos
                    
                    # Processar o processo individual
                    resultado = self.processar_documentos_ordinaria(numero_processo)
                    
                    if resultado.get('sucesso', False):
                        processos_com_sucesso += 1
                        print(f"✅ Processo {numero_processo} processado com sucesso")
                        resultados_processados.append(resultado)
                    else:
                        processos_com_erro += 1
                        print(f"❌ Erro ao processar processo {numero_processo}: {resultado.get('erro', 'Erro desconhecido')}")
                        
                except Exception as e:
                    processos_com_erro += 1
                    print(f"❌ Erro ao processar processo {numero_processo}: {e}")
                    continue
                finally:
                    # Limpar a variável após processar cada processo
                    if hasattr(self, 'processos_especificos_em_processamento'):
                        delattr(self, 'processos_especificos_em_processamento')
            
            # Gerar planilha consolidada apenas com os processos processados
            if resultados_processados:
                print(f"\n{'='*80}")
                print(f"📊 GERANDO PLANILHA CONSOLIDADA")
                print(f"{'='*80}")
                
                # Criar planilha específica
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                nome_arquivo = f"analise_ordinaria_lista_especifica_{timestamp}.xlsx"
                caminho_arquivo = os.path.join(os.getcwd(), 'planilhas', nome_arquivo)
                
                # Criar diretório se não existir
                os.makedirs(os.path.dirname(caminho_arquivo), exist_ok=True)
                
                # Consolidar todos os dados em uma planilha
                import pandas as pd
                dados_consolidados = []
                
                for resultado in resultados_processados:
                    if 'dados_planilha' in resultado:
                        dados_consolidados.append(resultado['dados_planilha'])
                
                if dados_consolidados:
                    df_consolidado = pd.DataFrame(dados_consolidados)
                    # Deduplicar por Número do Processo mantendo a última ocorrência
                    if 'Número do Processo' in df_consolidado.columns:
                        tamanho_antes = len(df_consolidado)
                        df_consolidado = df_consolidado.drop_duplicates(subset=['Número do Processo'], keep='last')
                        tamanho_depois = len(df_consolidado)
                        if tamanho_depois < tamanho_antes:
                            print(f"[DADOS] (Lista específica) Removidas {tamanho_antes - tamanho_depois} duplicata(s)")
                    df_consolidado.to_excel(caminho_arquivo, index=False)
                    
                    print(f"✅ Planilha consolidada gerada: {caminho_arquivo}")
                    print(f"📊 Total de processos na planilha: {len(dados_consolidados)}")
                    
                    return {
                        'sucesso': True,
                        'arquivo_planilha': caminho_arquivo,
                        'processos_processados': processos_com_sucesso,
                        'processos_com_erro': processos_com_erro,
                        'total_processos': len(lista_processos)
                    }
                else:
                    print("❌ Nenhum dado válido para gerar planilha")
                    return {
                        'sucesso': False,
                        'erro': 'Nenhum dado válido para gerar planilha',
                        'processos_processados': processos_com_sucesso,
                        'processos_com_erro': processos_com_erro,
                        'total_processos': len(lista_processos)
                    }
            else:
                print("❌ Nenhum processo foi processado com sucesso")
                return {
                    'sucesso': False,
                    'erro': 'Nenhum processo foi processado com sucesso',
                    'processos_processados': processos_com_sucesso,
                    'processos_com_erro': processos_com_erro,
                    'total_processos': len(lista_processos)
                }
                
        except Exception as e:
            print(f"❌ Erro geral ao processar lista de processos: {e}")
            import traceback
            traceback.print_exc()
            return {
                'sucesso': False,
                'erro': str(e),
                'processos_processados': processos_com_sucesso,
                'processos_com_erro': processos_com_erro,
                'total_processos': len(lista_processos)
            }

    def buscar_documento_na_tabela(self, nome_documento):
        """
        Busca um documento específico na tabela de documentos anexados
        """
        try:
            print(f"[BUSCA] Buscando '{nome_documento}' na tabela de documentos...")
            
            # Aguardar tabela carregar
            import time
            time.sleep(2)
            
            # Buscar todas as linhas da tabela
            try:
                linhas_tabela = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "tbody tr.table-row"
                )
                
                print(f"[DADOS] Encontradas {len(linhas_tabela)} linhas na tabela")
                
                for linha in linhas_tabela:
                    try:
                        # Buscar o tipo de documento na linha
                        tipo_elemento = linha.find_element(
                            By.CSS_SELECTOR, 
                            ".table-cell--DOCS_TIPO span"
                        )
                        tipo_texto = tipo_elemento.text.strip()
                        
                        # Buscar o tipo "outro" na linha
                        try:
                            tipo_outro_elemento = linha.find_element(
                                By.CSS_SELECTOR, 
                                ".table-cell--DOCS_TIPO_OUTRO span"
                            )
                            tipo_outro_texto = tipo_outro_elemento.text.strip()
                        except:
                            tipo_outro_texto = ""
                        
                        # Verificar se é o documento procurado
                        documento_encontrado = False
                        
                        # Verificações específicas por tipo de documento
                        if 'comprovante de redução de prazo' in nome_documento.lower():
                            # Buscar por termos mais específicos e amplos
                            termos_reducao = [
                                'redução', 'reduncao', 'filho brasileiro', 'nascimento', 'certidão de nascimento', 
                                'brasileiro', 'filha', 'união estável', 'uniao estavel', 'comprovem união estável',
                                'comprovem uniao estavel', 'documentos que comprovem união estável',
                                'documentos que comprovem uniao estavel', 'cônjuge', 'conjuge', 'companheiro',
                                'companheira', 'casamento', 'certidão de casamento', 'certidao de casamento'
                            ]
                            if any(term in tipo_outro_texto.lower() for term in termos_reducao) or any(term in tipo_texto.lower() for term in termos_reducao):
                                documento_encontrado = True
                        elif 'certidão de nascimento do filho brasileiro' in nome_documento.lower():
                            # Busca específica para certidão de nascimento que serve como comprovante de redução
                            termos_nascimento = ['certidão de nascimento do filho', 'nascimento', 'filho brasileiro', 'filha', 'certidao', 'certidão', 'brasileiro', 'brasileira']
                            if 'certidão de nascimento do filho' in tipo_texto.lower() or any(term in tipo_outro_texto.lower() for term in termos_nascimento) or any(term in tipo_texto.lower() for term in termos_nascimento):
                                documento_encontrado = True
                        elif 'carteira de registro nacional' in nome_documento.lower() or 'crnm' in nome_documento.lower():
                            if any(term in tipo_texto.lower() for term in ['carteira de registro', 'crnm']) or any(term in tipo_outro_texto.lower() for term in ['rnm', 'crnm']):
                                documento_encontrado = True
                        elif 'cpf' in nome_documento.lower():
                            if 'cpf' in tipo_texto.lower() or 'cpf' in tipo_outro_texto.lower():
                                documento_encontrado = True
                        elif 'antecedentes criminais (brasil)' in nome_documento.lower() or 'certidão de antecedentes criminais (brasil)' in nome_documento.lower():
                            # Buscar por termos relacionados a antecedentes criminais do Brasil
                            termos_brasil = ['antecedentes criminais emitida pela justiça federal e estadual', 'antecedencia estadua e federal', 'certidão', 'federal', 'estadual', 'antecedentes']
                            if any(term in tipo_texto.lower() for term in termos_brasil) or any(term in tipo_outro_texto.lower() for term in termos_brasil):
                                documento_encontrado = True
                        elif 'antecedentes criminais (país de origem)' in nome_documento.lower() or 'atestado antecedentes criminais' in nome_documento.lower():
                            # Verificar se é realmente do país de origem (não do Brasil)
                            # Padrões que indicam país de origem
                            padroes_pais_origem = [
                                'atestado de antecedentes criminais expedido pelo país',
                                'tradução',
                                'tradutor público juramentado',
                                'convenção sobre a eliminação',
                                'decreto nº 8.660',
                                'legalizado e traduzido'
                            ]
                            
                            # Padrões que indicam Brasil (deve ser rejeitado)
                            padroes_brasil = [
                                '2º ofício distribuidor',
                                '3º ofício distribuidor', 
                                'justiça federal',
                                'comarca de',
                                'estado do',
                                'tribunal de justiça',
                                'tj do estado',
                                'poder judiciário',
                                'foro central',
                                'certidão negativa criminal',
                                'distribuidor'
                            ]
                            
                            # Verificar se tem padrões do Brasil (rejeitar)
                            tem_padrao_brasil = any(padrao in tipo_texto.lower() for padrao in padroes_brasil) or any(padrao in tipo_outro_texto.lower() for padrao in padroes_brasil)
                            
                            # Verificar se tem padrões do país de origem (aceitar)
                            tem_padrao_pais_origem = any(padrao in tipo_texto.lower() for padrao in padroes_pais_origem) or any(padrao in tipo_outro_texto.lower() for padrao in padroes_pais_origem)
                            
                            if tem_padrao_pais_origem and not tem_padrao_brasil:
                                documento_encontrado = True
                                print(f"[FILTRO] Documento aceito como país de origem: {tipo_texto} | {tipo_outro_texto}")
                            elif tem_padrao_brasil:
                                print(f"[FILTRO] Documento rejeitado (é do Brasil): {tipo_texto} | {tipo_outro_texto}")
                            else:
                                print(f"[FILTRO] Documento não identificado claramente: {tipo_texto} | {tipo_outro_texto}")
                        elif 'comunicação em português' in nome_documento.lower():
                            # Buscar por termos mais específicos para comunicação em português
                            termos_comunicacao = ['comunicar-se em língua portuguesa', 'comunicação', 'português', 'certificado', 'histórico escolar', 'escolaridade']
                            if any(term in tipo_texto.lower() for term in termos_comunicacao) or any(term in tipo_outro_texto.lower() for term in termos_comunicacao):
                                documento_encontrado = True
                        elif 'tempo de residência' in nome_documento.lower():
                            if 'comprovante de residência, pelo prazo' in tipo_texto.lower() or 'comprovante residencia' in tipo_outro_texto.lower():
                                documento_encontrado = True
                        elif 'viagem internacional' in nome_documento.lower() or 'passaporte' in nome_documento.lower():
                            if 'passaporte' in tipo_texto.lower() or 'passaporte' in tipo_outro_texto.lower():
                                documento_encontrado = True
                        
                        if documento_encontrado:
                            # Buscar link de download
                            try:
                                link_download = linha.find_element(
                                    By.CSS_SELECTOR, 
                                    ".table-cell--DOCS_ANEXO a"
                                )
                                nome_arquivo = link_download.text.strip()
                                print(f"[OK] Documento encontrado: {nome_arquivo}")
                                print(f"[DOC] Tipo: {tipo_texto}")
                                print(f"🏷️ Tipo outro: {tipo_outro_texto}")
                                
                                return {
                                    'encontrado': True,
                                    'elemento_link': link_download,
                                    'nome_arquivo': nome_arquivo,
                                    'tipo_documento': tipo_texto,
                                    'tipo_outro': tipo_outro_texto
                                }
                            except:
                                print(f"[ERRO] Documento encontrado mas sem link de download")
                                return {
                                    'encontrado': False,
                                    'motivo': 'Sem link de download'
                                }
                    
                    except Exception as e:
                        continue  # Pular linhas com erro
                
                print(f"[ERRO] Documento '{nome_documento}' não encontrado na tabela")
                return {
                    'encontrado': False,
                    'motivo': 'Não encontrado na tabela'
                }
                
            except Exception as e:
                print(f"[ERRO] Erro ao buscar tabela: {e}")
                return {
                    'encontrado': False,
                    'motivo': f'Erro na tabela: {e}'
                }
                
        except Exception as e:
            print(f"[ERRO] Erro geral na busca: {e}")
            return {
                'encontrado': False,
                'motivo': f'Erro geral: {e}'
            }

    def buscar_documento_na_tabela_termos_amplos(self, termos_busca):
        """
        Busca um documento na tabela usando uma lista de termos alternativos
        """
        try:
            print(f"[BUSCA] Buscando com termos amplos: {termos_busca}")
            
            # Aguardar tabela carregar
            import time
            time.sleep(2)
            
            # Buscar todas as linhas da tabela
            try:
                linhas_tabela = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "tbody tr.table-row"
                )
                
                print(f"[DADOS] Encontradas {len(linhas_tabela)} linhas na tabela")
                
                for linha in linhas_tabela:
                    try:
                        # Buscar o tipo de documento na linha
                        tipo_elemento = linha.find_element(
                            By.CSS_SELECTOR, 
                            ".table-cell--DOCS_TIPO span"
                        )
                        tipo_texto = tipo_elemento.text.strip()
                        
                        # Buscar o tipo "outro" na linha
                        try:
                            tipo_outro_elemento = linha.find_element(
                                By.CSS_SELECTOR, 
                                ".table-cell--DOCS_TIPO_OUTRO span"
                            )
                            tipo_outro_texto = tipo_outro_elemento.text.strip()
                        except:
                            tipo_outro_texto = ""
                        
                        # Verificar se algum dos termos está presente
                        texto_completo = f"{tipo_texto} {tipo_outro_texto}".lower()
                        documento_encontrado = any(termo.lower() in texto_completo for termo in termos_busca)
                        
                        if documento_encontrado:
                            print(f"[OK] Documento encontrado: {tipo_texto[:50]}...")
                            print(f"[DOC] Texto encontrado: {tipo_outro_texto}")
                            
                            # Buscar o botão de download na linha
                            try:
                                botao_download = linha.find_element(
                                    By.CSS_SELECTOR, 
                                    ".table-cell--VIEWER button"
                                )
                                return {
                                    'encontrado': True,
                                    'elemento_link': botao_download,
                                    'fonte': 'tabela_termos_amplos'
                                }
                            except Exception as e:
                                print(f"[AVISO] Erro ao localizar botão de download: {e}")
                                continue
                                
                    except Exception as e:
                        print(f"[AVISO] Erro ao processar linha da tabela: {e}")
                        continue
                
                print(f"[ERRO] Nenhum documento encontrado com os termos: {termos_busca}")
                return {
                    'encontrado': False,
                    'motivo': f'Nenhum documento encontrado com os termos especificados',
                    'elemento_link': None
                }
                
            except Exception as e:
                print(f"[ERRO] Erro ao buscar linhas da tabela: {e}")
                return {
                    'encontrado': False,
                    'motivo': f'Erro ao buscar linhas: {e}',
                    'elemento_link': None
                }
                
        except Exception as e:
            print(f"[ERRO] Erro geral na busca por termos amplos: {e}")
            return {
                'encontrado': False, 
                'motivo': f'Erro na busca: {e}',
                'elemento_link': None
            }

    def buscar_documento_em_campo_especifico(self, nome_documento):
        """
        Busca documento primeiro em campos específicos antes da tabela geral
        """
        try:
            # Mapeamento de documentos para seus campos específicos baseado no HTML real
            campos_especificos = {
                'comprovante de redução de prazo': [
                    "input#DOC_REDUCAO",
                    "div#input__DOC_REDUCAO"
                ],
                'comprovante de comunicação em português': [
                    "input#DOC_PTBR",
                    "div#input__DOC_PTBR"
                ],
                'certidão de antecedentes criminais (brasil)': [
                    "input#DOC_CERTCRIME",
                    "div#input__DOC_CERTCRIME"
                ],
                'atestado antecedentes criminais (país de origem)': [
                    "input#DOC_ANTCRIME",
                    "div#input__DOC_ANTCRIME"
                ],
                'carteira de registro nacional migratório': [
                    "input#DOC_RNM",
                    "div#input__DOC_RNM"
                ],
                'comprovante da situação cadastral do cpf': [
                    "input#DOC_CPF",
                    "div#input__DOC_CPF"
                ],
                'comprovante de tempo de residência': [
                    "input#DOC_RESIDENCIA",
                    "div#input__DOC_RESIDENCIA"
                ],
                'documento de viagem internacional': [
                    "input#DOC_VIAGEM",
                    "div#input__DOC_VIAGEM"
                ]
            }
            
            nome_lower = nome_documento.lower()
            
            # Mapeamento simplificado de documentos para IDs
            mapeamento_ids = {
                'comprovante de redução de prazo': 'DOC_REDUCAO',
                'comprovante de comunicação em português': 'DOC_PTBR',
                'certidão de antecedentes criminais (brasil)': 'DOC_CERTCRIME',
                'atestado antecedentes criminais (país de origem)': 'DOC_ANTCRIME',
                'carteira de registro nacional migratório': 'DOC_RNM',
                'comprovante da situação cadastral do cpf': 'DOC_CPF',
                'comprovante de tempo de residência': 'DOC_RESIDENCIA',
                'documento de viagem internacional': 'DOC_VIAGEM'
            }
            
            # Buscar por campo específico primeiro
            for doc_key, campo_id in mapeamento_ids.items():
                if doc_key in nome_lower:
                    print(f"[BUSCA] Verificando campo específico para {doc_key}: {campo_id}")
                    
                    try:
                        # Verificar se o campo existe
                        elemento_campo = self.driver.find_element(By.ID, campo_id)
                        print(f"✅ Campo {campo_id} encontrado")
                        
                        # Verificar se há ícone de download
                        if self.verificar_icone_download_campo(campo_id):
                            print(f"✅ Ícone de download encontrado para {campo_id}")
                            
                            # Buscar o botão de download
                            if campo_id == 'DOC_RNM':
                                botao = self.buscar_elemento_clicavel_doc_rnm()
                            elif campo_id == 'DOC_VIAGEM':
                                botao = self.buscar_elemento_clicavel_doc_viagem()
                            else:
                                # Buscar botão genérico
                                xpath_botao = f"//div[@id='input__{campo_id}']//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
                                try:
                                    botao = self.driver.find_element(By.XPATH, xpath_botao)
                                    print(f"✅ Botão genérico encontrado via XPath: {xpath_botao}")
                                except Exception as e:
                                    print(f"❌ Botão genérico não encontrado: {e}")
                                    botao = elemento_campo
                            
                            if botao:
                                print(f"✅ Botão de download encontrado para {campo_id}")
                                return {
                                    'encontrado': True,
                                    'elemento_link': botao,
                                    'nome_arquivo': f'{doc_key} (campo específico)',
                                    'fonte': 'campo_especifico_direto'
                                }
                            else:
                                print(f"❌ Botão de download não encontrado para {campo_id}")
                        else:
                            print(f"❌ Ícone de download não encontrado para {campo_id}")
                    except Exception as e:
                        print(f"❌ Campo {campo_id} não encontrado: {e}")
                        continue
            
            print(f"[ERRO] Documento '{nome_documento}' não encontrado em campos específicos")
            return {
                'encontrado': False,
                'motivo': 'Documento não encontrado em campos específicos'
            }
            
        except Exception as e:
            print(f"[ERRO] Erro ao buscar em campos específicos: {e}")
            return {
                'encontrado': False,
                'motivo': f'Erro na busca: {e}'
            }

    def baixar_e_validar_documento_individual(self, nome_documento):
        """
        Baixa e valida um documento específico individualmente sem cache
        """
        try:
            import time
            print(f"[DOC] Baixando e validando: {nome_documento}")
            
            # ESPECIAL: Para antecedentes do país de origem, buscar PRIMEIRO na tabela
            if 'país de origem' in nome_documento.lower() or 'atestado antecedentes criminais' in nome_documento.lower():
                print(f"[BUSCA] Antecedentes país de origem: Buscando PRIMEIRO na tabela (maioria dos casos)...")
                resultado_busca = self.buscar_documento_na_tabela(nome_documento)
                
                # Se não encontrou na tabela, tentar busca por termos amplos
                if not resultado_busca.get('encontrado', False):
                    print(f"[BUSCA] Não encontrado na tabela, tentando busca ampla...")
                    resultado_busca = self.buscar_documento_na_tabela_termos_amplos([
                        'atestado de antecedentes criminais',
                        'antecedentes criminais',
                        'tradução juramentada',
                        'certificacion de antecedentes',
                        'país de origem'
                    ])
                
                # APENAS se não encontrou na tabela, tentar campo específico
                if not resultado_busca.get('encontrado', False):
                    print(f"[BUSCA] Não encontrado na tabela, tentando campo específico...")
                    resultado_busca = self.buscar_documento_em_campo_especifico(nome_documento)
            
            # FLUXO NORMAL: Outros documentos - buscar primeiro em campos específicos
            else:
                # 1. Primeiro: Buscar em campos específicos
                resultado_busca = self.buscar_documento_em_campo_especifico(nome_documento)
            
            # 2. Se não encontrou, buscar na tabela geral
            if not resultado_busca.get('encontrado', False):
                print(f"[BUSCA] Não encontrado em campo específico, buscando na tabela...")
                resultado_busca = self.buscar_documento_na_tabela(nome_documento)
            
            # 3. ESPECIAL PARA COMPROVANTE DE REDUÇÃO: Se ainda não encontrou, buscar na tabela por "Certidão de nascimento"
            if not resultado_busca.get('encontrado', False) and 'comprovante de redução de prazo' in nome_documento.lower():
                print(f"[BUSCA] Busca especial: Procurando 'Certidão de nascimento do filho brasileiro' como comprovante de redução...")
                # Buscar especificamente por certidão de nascimento na tabela
                resultado_busca = self.buscar_documento_na_tabela('Certidão de nascimento do filho brasileiro')
                
                # Se ainda não encontrou, tentar busca mais ampla
                if not resultado_busca.get('encontrado', False):
                    print(f"[BUSCA] Busca alternativa: Procurando termos relacionados a nascimento/filho...")
                    resultado_busca = self.buscar_documento_na_tabela_termos_amplos(['nascimento', 'filho brasileiro', 'filha', 'certidão de nascimento'])
            
            if not resultado_busca.get('encontrado', False):
                print(f"[ERRO] {nome_documento}: NÃO ANEXADO - {resultado_busca.get('motivo', 'Não encontrado')}")
                return False
            
            link_elemento = resultado_busca['elemento_link']
            
            # FORÇAR NOVOS DOWNLOADS: Sempre baixar documentos para garantir OCR correto
            print(f"[RELOAD] Iniciando download forçado de: {nome_documento}")
            
            # Baixar o documento com fallback robusto
            nome_arquivo_baixado = None
            fonte_busca = resultado_busca.get('fonte', '')
            
            # TENTATIVA 1: Executar download com lógica otimizada
            try:
                if fonte_busca == 'campo_especifico_xpath' or 'campo_especifico' in fonte_busca:
                    print(f"[TARGET] Tentativa 1: Campo específico COM ÍCONE - documento anexado (5s)")
                else:
                    print(f"[TARGET] Tentativa 1: Tabela - usando nome específico (5s)")
                
                # LÓGICA REORGANIZADA: Detectar método e executar download completo
                nome_arquivo_baixado = self.executar_download_completo(link_elemento, fonte_busca, resultado_busca, nome_documento)
                
                if nome_arquivo_baixado:
                    print(f"[OK] Download bem-sucedido: {nome_arquivo_baixado}")
                else:
                    print(f"[AVISO] Tentativa 1 falhou: arquivo não foi baixado")
                
            except Exception as e:
                print(f"[AVISO] Tentativa 1 falhou com erro: {e}")
            
            # TENTATIVA 2: Se falhou e era campo específico, tentar na tabela
            if not nome_arquivo_baixado and ('campo_especifico' in fonte_busca):
                try:
                    print(f"[RELOAD] Tentativa 2: Campo específico falhou, buscando na tabela...")
                    resultado_busca_tabela = self.buscar_documento_na_tabela(nome_documento)
                    
                    if resultado_busca_tabela.get('encontrado', False):
                        print(f"[OK] Documento encontrado na tabela, tentando download...")
                        link_tabela = resultado_busca_tabela['elemento_link']
                        nome_arquivo_tabela = resultado_busca_tabela.get('nome_arquivo', '')
                        
                        # Scroll para o elemento
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", link_tabela)
                        time.sleep(1)
                        
                        # Tentar apenas clique JavaScript (mais confiável)
                        self.driver.execute_script("arguments[0].click();", link_tabela)
                        print(f"[OK] Clique JavaScript na tabela executado")
                        
                        time.sleep(5)  # Aguardar 5 segundos
                        nome_arquivo_baixado = self.aguardar_download_documento_por_nome(nome_arquivo_tabela, nome_documento, timeout=5)
                        
                        if nome_arquivo_baixado:
                            print(f"[OK] Download bem-sucedido na tentativa 2: {nome_arquivo_baixado}")
                        else:
                            print(f"[AVISO] Tentativa 2 falhou: arquivo não foi baixado")
                    else:
                        print(f"[AVISO] Documento também não encontrado na tabela")
                    
                except Exception as e:
                    print(f"[AVISO] Erro na tentativa 2: {e}")
            
            # Para comprovante de redução, busca adicional APENAS se ainda não tentou na tabela
            elif not nome_arquivo_baixado and 'comprovante de redução de prazo' in nome_documento.lower() and 'tabela' not in fonte_busca:
                try:
                    print(f"[RELOAD] Busca adicional: Certidão de nascimento como comprovante de redução...")
                    resultado_certidao = self.buscar_documento_na_tabela('Certidão de nascimento do filho brasileiro')
                    
                    if resultado_certidao.get('encontrado', False):
                        link_certidao = resultado_certidao['elemento_link']
                        nome_arquivo_certidao = resultado_certidao.get('nome_arquivo', '')
                        
                        # Scroll e clique
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", link_certidao)
                        time.sleep(1)
                        self.driver.execute_script("arguments[0].click();", link_certidao)
                        print(f"[OK] Clique na certidão de nascimento executado")
                        
                        time.sleep(5)  # Aguardar 5 segundos
                        nome_arquivo_baixado = self.aguardar_download_documento_por_nome(nome_arquivo_certidao, nome_documento, timeout=5)
                        
                        if nome_arquivo_baixado:
                            print(f"[OK] Download bem-sucedido: {nome_arquivo_baixado}")
                        
                except Exception as e:
                    print(f"[AVISO] Busca adicional falhou: {e}")
            
            # Se ainda não conseguiu baixar
            if not nome_arquivo_baixado:
                print(f"[ERRO] {nome_documento}: DOCUMENTO NÃO ANEXADO - Nenhum arquivo específico foi baixado")
                print(f"   ➤ Isso indica que o documento não foi anexado ao processo")
                return False
            
            # Executar OCR sem cache
            try:
                print(f"[BUSCA] Executando OCR em {nome_documento}...")
                texto_extraido = self.executar_ocr_sem_cache(nome_arquivo_baixado, nome_documento)
                
                if not texto_extraido:
                    print(f"[ERRO] {nome_documento}: OCR FALHOU - Nenhum texto extraído")
                    return False
                
                if len(texto_extraido.strip()) < 10:
                    print(f"[AVISO] {nome_documento}: OCR extraiu texto muito curto ({len(texto_extraido)} chars)")
                    # Para alguns documentos como imagens ou formulários, texto curto pode ser normal
                    # Não falhar automaticamente, mas continuar com validação
                
                print(f"[OK] {nome_documento}: OCR executado - {len(texto_extraido)} caracteres")
                
                # [FECHADO] LGPD: Não exibir conteúdo do documento para proteger dados pessoais
                
            except Exception as e:
                print(f"[ERRO] {nome_documento}: ERRO NO OCR - {e}")
                return False
            
            # Validar conteúdo específico do documento
            try:
                documento_valido = self.validar_conteudo_documento_especifico(nome_documento, texto_extraido)
                
                if documento_valido:
                    print(f"[OK] {nome_documento}: VÁLIDO")
                    return True
                else:
                    print(f"[ERRO] {nome_documento}: INVÁLIDO - Conteúdo não atende aos requisitos")
                    
                    # ESPECIAL: Para antecedentes do país de origem, se não validou da tabela, tentar campo específico
                    if ('país de origem' in nome_documento.lower() or 'atestado antecedentes criminais' in nome_documento.lower()) and fonte_busca == 'tabela':
                        print(f"[TENTATIVA] Antecedentes país de origem não validou da tabela, tentando campo específico...")
                        
                        # Tentar buscar no campo específico
                        resultado_campo = self.buscar_documento_em_campo_especifico(nome_documento)
                        
                        if resultado_campo.get('encontrado', False):
                            print(f"[OK] Documento encontrado no campo específico, tentando download...")
                            
                            # Tentar baixar do campo específico
                            try:
                                link_campo = resultado_campo['elemento_link']
                                nome_arquivo_campo = self.executar_download_completo(link_campo, 'campo_especifico', resultado_campo, nome_documento)
                                
                                if nome_arquivo_campo:
                                    print(f"[OK] Download do campo específico bem-sucedido: {nome_arquivo_campo}")
                                    
                                    # Executar OCR no documento do campo específico
                                    texto_campo = self.executar_ocr_sem_cache(nome_arquivo_campo, nome_documento)
                                    
                                    if texto_campo:
                                        print(f"[OK] OCR do campo específico executado - {len(texto_campo)} caracteres")
                                        
                                        # Validar o documento do campo específico
                                        documento_valido_campo = self.validar_conteudo_documento_especifico(nome_documento, texto_campo)
                                        
                                        if documento_valido_campo:
                                            print(f"[OK] {nome_documento}: VÁLIDO (campo específico)")
                                            return True
                                        else:
                                            print(f"[ERRO] {nome_documento}: INVÁLIDO também no campo específico")
                                    else:
                                        print(f"[ERRO] OCR do campo específico falhou")
                                else:
                                    print(f"[ERRO] Download do campo específico falhou")
                                    
                            except Exception as e:
                                print(f"[ERRO] Erro ao tentar campo específico: {e}")
                        else:
                            print(f"[INFO] Documento também não encontrado no campo específico")
                    
                    return False
                    
            except Exception as e:
                print(f"[ERRO] {nome_documento}: ERRO NA VALIDAÇÃO - {e}")
                return False
                
        except Exception as e:
            print(f"[ERRO] {nome_documento}: ERRO GERAL - {e}")
            return False

    def verificar_icone_download_campo(self, campo_tipo):
        """
        Verifica se existe o ícone cloud_download próximo ao campo específico
        """
        try:
            # Buscar ícone cloud_download próximo ao campo específico
            # Baseado no HTML fornecido: <i class="material-icons" type="cloud_download">
            xpath_icone = f"//input[@id='{campo_tipo}']/ancestor::div[contains(@class, 'document-field')]//i[@type='cloud_download']"
            
            try:
                icone = self.driver.find_element(By.XPATH, xpath_icone)
                print(f"✅ Ícone cloud_download encontrado para campo {campo_tipo}")
                return True
            except:
                # Tentar busca alternativa
                xpath_alt = f"//div[@id='input__{campo_tipo}']//i[@type='cloud_download']"
                try:
                    icone = self.driver.find_element(By.XPATH, xpath_alt)
                    print(f"✅ Ícone cloud_download encontrado para campo {campo_tipo} (busca alternativa)")
                    return True
                except:
                    # Para DOC_VIAGEM, tentar busca específica
                    if campo_tipo == 'DOC_VIAGEM':
                        try:
                            # Buscar pelo ícone com aria-label específico
                            xpath_viagem = "//i[@type='cloud_download' and @aria-label='Download']"
                            icone = self.driver.find_element(By.XPATH, xpath_viagem)
                            print(f"✅ Ícone cloud_download encontrado para DOC_VIAGEM (busca específica)")
                            return True
                        except:
                            pass
                    
                    print(f"❌ Ícone cloud_download NÃO encontrado para campo {campo_tipo}")
                    return False
                
        except Exception as e:
            print(f"[ERRO] Erro ao verificar ícone de download: {e}")
            return False

    def buscar_botao_doc_viagem(self):
        """
        Busca o botão específico do DOC_VIAGEM usando o ícone fornecido
        """
        try:
            # Buscar pelo ícone específico do DOC_VIAGEM
            xpath_icone_viagem = "//i[@class='material-icons' and @type='cloud_download' and contains(@data-reactid, 'DOC_VIAGEM') and text()='cloud_download']"
            
            try:
                icone = self.driver.find_element(By.XPATH, xpath_icone_viagem)
                print(f"[OK] Ícone específico cloud_download encontrado para DOC_VIAGEM")
                return True
            except:
                # Busca alternativa mais genérica para DOC_VIAGEM
                xpath_alternativo = "//span[contains(@data-reactid, 'DOC_VIAGEM')]/ancestor::*//i[@type='cloud_download' and text()='cloud_download']"
                try:
                    icone_alt = self.driver.find_element(By.XPATH, xpath_alternativo)
                    print(f"[OK] Ícone cloud_download encontrado para DOC_VIAGEM (busca alternativa)")
                    return True
                except:
                    print(f"[ERRO] Ícone cloud_download NÃO encontrado para DOC_VIAGEM")
                    return False
                    
        except Exception as e:
            print(f"[ERRO] Erro ao verificar ícone de DOC_VIAGEM: {e}")
            return False

    def buscar_elemento_clicavel_doc_rnm(self):
        """
        Busca o elemento clicável para download do DOC_RNM (CRNM)
        """
        try:
            # MÉTODO 1: Buscar o botão de download baseado no HTML fornecido
            xpath_botao_especifico = "//div[@id='input__DOC_RNM']//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
            
            try:
                botao = self.driver.find_element(By.XPATH, xpath_botao_especifico)
                print(f"✅ Botão DOC_RNM encontrado via XPath específico")
                return botao
            except:
                pass
            
            # MÉTODO 2: Buscar pelo input e navegar para o botão
            xpath_alt = "//input[@id='DOC_RNM']/ancestor::div[contains(@class, 'document-field')]//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
            
            try:
                botao = self.driver.find_element(By.XPATH, xpath_alt)
                print(f"✅ Botão DOC_RNM encontrado via busca alternativa")
                return botao
            except:
                pass
            
            # MÉTODO 3: Buscar pelo ícone diretamente
            xpath_icone = "//i[@type='cloud_download' and @aria-label='Download']"
            
            try:
                icone = self.driver.find_element(By.XPATH, xpath_icone)
                print(f"✅ Ícone DOC_RNM encontrado diretamente")
                return icone
            except:
                pass
            
            print(f"❌ Elemento clicável DOC_RNM não encontrado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao buscar elemento clicável DOC_RNM: {e}")
            return None

    def buscar_elemento_clicavel_doc_viagem(self):
        """
        Busca o elemento clicável para download do DOC_VIAGEM
        """
        try:
            # MÉTODO 1: Buscar o botão de download baseado no HTML fornecido
            xpath_botao_especifico = "//div[@id='input__DOC_VIAGEM']//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
            
            try:
                botao = self.driver.find_element(By.XPATH, xpath_botao_especifico)
                print(f"✅ Botão DOC_VIAGEM encontrado via XPath específico")
                return botao
            except:
                pass
            
            # MÉTODO 2: Buscar pelo input e navegar para o botão
            xpath_alt = "//input[@id='DOC_VIAGEM']/ancestor::div[contains(@class, 'document-field')]//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
            
            try:
                botao = self.driver.find_element(By.XPATH, xpath_alt)
                print(f"✅ Botão DOC_VIAGEM encontrado via busca alternativa")
                return botao
            except:
                pass
            
            # MÉTODO 3: Buscar pelo ícone diretamente
            xpath_icone = "//i[@type='cloud_download' and @aria-label='Download']"
            
            try:
                icone = self.driver.find_element(By.XPATH, xpath_icone)
                print(f"✅ Ícone DOC_VIAGEM encontrado diretamente")
                return icone
            except:
                pass
            
            print(f"❌ Elemento clicável DOC_VIAGEM não encontrado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao buscar elemento clicável DOC_VIAGEM: {e}")
            return None

    def verificar_arquivo_existente(self, nome_arquivo_esperado):
        """
        Verifica se um arquivo específico já existe na pasta de downloads
        """
        try:
            import os
            
            if not nome_arquivo_esperado:
                return None
            
            diretorio_downloads = self.obter_diretorio_downloads()
            caminho_arquivo = os.path.join(diretorio_downloads, nome_arquivo_esperado)
            
            if os.path.exists(caminho_arquivo):
                return caminho_arquivo
            
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao verificar arquivo existente: {e}")
            return None

    def verificar_arquivo_existente_flexivel(self, nome_documento):
        """
        Busca arquivos existentes com base no tipo de documento de forma mais flexível
        """
        try:
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            arquivos = os.listdir(diretorio_downloads)
            
            # Definir palavras-chave para cada tipo de documento
            palavras_chave = {
                'comprovante de redução de prazo': ['nascimento', 'filho', 'brasileiro', 'certidao', 'certidão'],
                'comprovante de comunicação em português': ['certificado', 'lingua', 'português', 'escolaridade', 'historico'],
                'certidão de antecedentes criminais (brasil)': ['antecedentes', 'criminais', 'certidao', 'estadual', 'federal'],
                'atestado antecedentes criminais (país de origem)': ['atestado', 'antecedentes', 'criminal', 'origem'],
                'carteira de registro nacional migratório': ['rnm', 'crnm', 'registro', 'migratorio'],
                'comprovante da situação cadastral do cpf': ['cpf', 'cadastral', 'situacao'],
                'comprovante de tempo de residência': ['residencia', 'tempo', 'comprovante'],
                'documento de viagem internacional': ['passaporte', 'viagem', 'internacional']
            }
            
            nome_documento_lower = nome_documento.lower()
            
            # Buscar palavras-chave correspondentes
            chaves_relevantes = []
            for doc_tipo, chaves in palavras_chave.items():
                if doc_tipo in nome_documento_lower:
                    chaves_relevantes.extend(chaves)
                    break
            
            if not chaves_relevantes:
                return None
            
            # Procurar arquivos que contenham as palavras-chave de forma mais específica
            melhor_arquivo = None
            melhor_score = 0
            
            for arquivo in arquivos:
                if arquivo.lower().endswith(('.pdf', '.jpeg', '.jpg', '.png')):
                    arquivo_lower = arquivo.lower()
                    
                    # Calcular score de relevância
                    score = 0
                    for chave in chaves_relevantes:
                        if chave in arquivo_lower:
                            score += 1
                    
                    # Só considerar se tem pelo menos uma palavra-chave
                    if score > 0:
                        caminho_arquivo = os.path.join(diretorio_downloads, arquivo)
                        # Verificar se foi modificado recentemente (últimas 2 horas para ser mais restritivo)
                        import time
                        if time.time() - os.path.getmtime(caminho_arquivo) < 7200:  # 2 horas
                            if score > melhor_score:
                                melhor_score = score
                                melhor_arquivo = caminho_arquivo
                                print(f"[BUSCA] Candidato: {arquivo} (score: {score})")
            
            if melhor_arquivo:
                print(f"[TARGET] Melhor arquivo encontrado: {os.path.basename(melhor_arquivo)} (score: {melhor_score})")
                return melhor_arquivo
            
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro na busca flexível: {e}")
            return None

    def executar_download_completo(self, link_elemento, fonte_busca, resultado_busca, nome_documento):
        """
        Executa download completo: contar arquivos -> clicar -> detectar novo arquivo
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            
            # PASSO 1: Contar arquivos ANTES do clique
            arquivos_antes = []
            try:
                todos_arquivos = os.listdir(diretorio_downloads)
                for arquivo in todos_arquivos:
                    caminho = os.path.join(diretorio_downloads, arquivo)
                    if os.path.isfile(caminho):
                        extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                        if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                            arquivos_antes.append(arquivo)
                
                print(f"[ARQUIVO] {len(arquivos_antes)} arquivos válidos antes do clique")
            except Exception as e:
                print(f"[AVISO] Erro ao contar arquivos antes: {e}")
                arquivos_antes = []
            
            # PASSO 2: Executar o clique
            try:
                # Scroll até o elemento
                self.driver.execute_script("arguments[0].scrollIntoView(true);", link_elemento)
                time.sleep(1)
                
                # Tentar clique direto primeiro
                try:
                    link_elemento.click()
                    print(f"[OK] Clique direto executado")
                except:
                    # Se falhar, usar JavaScript
                    self.driver.execute_script("arguments[0].click();", link_elemento)
                    print(f"[OK] Clique JavaScript executado")
                
                # Aguardar 5 segundos para download iniciar  
                time.sleep(5)
                
            except Exception as e:
                print(f"[AVISO] Erro no clique: {e}")
                return None
            
            # PASSO 3: Detectar novo arquivo baseado na fonte
            if fonte_busca == 'campo_especifico_xpath' or 'campo_especifico' in fonte_busca:
                # Para campos específicos COM ÍCONE: pegar último arquivo adicionado (5 segundos)
                print(f"[TARGET] Campo específico com ícone - aguardando 5 segundos...")
                return self.detectar_ultimo_arquivo_adicionado(arquivos_antes, nome_documento, timeout=5)
            else:
                # Para tabela: usar nome específico se disponível
                nome_arquivo_tabela = resultado_busca.get('nome_arquivo', '')
                if nome_arquivo_tabela:
                    print(f"[TARGET] Buscando arquivo específico: {nome_arquivo_tabela}")
                    return self.detectar_arquivo_por_nome(nome_arquivo_tabela, nome_documento, timeout=5)
                else:
                    # Fallback: pegar último arquivo adicionado
                    print(f"[TARGET] Fallback: aguardando último arquivo...")
                    return self.detectar_ultimo_arquivo_adicionado(arquivos_antes, nome_documento, timeout=5)
                    
        except Exception as e:
            print(f"[ERRO] Erro no download completo: {e}")
            return None
    
    def detectar_ultimo_arquivo_adicionado(self, arquivos_antes, nome_documento, timeout=5):
        """
        Detecta o último arquivo adicionado após o clique
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            tempo_inicial = time.time()
            
            print(f"[TEMPO] Aguardando {timeout} segundos por arquivo novo...")
            
            while time.time() - tempo_inicial < timeout:
                try:
                    # Listar arquivos atuais
                    arquivos_atuais = []
                    todos_arquivos = os.listdir(diretorio_downloads)
                    
                    for arquivo in todos_arquivos:
                        caminho = os.path.join(diretorio_downloads, arquivo)
                        if os.path.isfile(caminho):
                            extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                            if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                                arquivos_atuais.append(arquivo)
                    
                    # Verificar se há mais arquivos agora
                    if len(arquivos_atuais) > len(arquivos_antes):
                        # Encontrar arquivos novos
                        arquivos_novos = []
                        for arquivo in arquivos_atuais:
                            if arquivo not in arquivos_antes:
                                arquivos_novos.append(arquivo)
                        
                        if arquivos_novos:
                            print(f"📥 {len(arquivos_novos)} arquivos novos detectados:")
                            for arquivo in arquivos_novos:
                                print(f"   [DOC] {arquivo}")
                            
                            # Pegar o primeiro arquivo novo
                            arquivo_baixado = arquivos_novos[0]
                            caminho_completo = os.path.join(diretorio_downloads, arquivo_baixado)
                            
                            # Verificar se arquivo está completo
                            if self._arquivo_esta_completo(caminho_completo):
                                print(f"[OK] Último arquivo baixado: {arquivo_baixado}")
                                return caminho_completo
                            else:
                                print(f"[AGUARDE] Arquivo ainda sendo baixado: {arquivo_baixado}")
                
                except Exception as e:
                    print(f"[AVISO] Erro ao verificar arquivos: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout de {timeout}s - nenhum arquivo novo detectado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao detectar último arquivo: {e}")
            return None
    
    def detectar_arquivo_por_nome(self, nome_arquivo_esperado, nome_documento, timeout=5):
        """
        Detecta arquivo específico por nome
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            tempo_inicial = time.time()
            
            print(f"[TARGET] Procurando especificamente por: {nome_arquivo_esperado}")
            
            while time.time() - tempo_inicial < timeout:
                try:
                    arquivos_no_diretorio = os.listdir(diretorio_downloads)
                    
                    # Procurar pelo arquivo específico
                    for arquivo in arquivos_no_diretorio:
                        # Busca exata primeiro
                        if arquivo == nome_arquivo_esperado:
                            caminho_completo = os.path.join(diretorio_downloads, arquivo)
                            
                            if not arquivo.endswith('.crdownload') and os.path.isfile(caminho_completo):
                                if self._arquivo_esta_completo(caminho_completo):
                                    print(f"[OK] Arquivo específico encontrado: {arquivo}")
                                    return caminho_completo
                        
                        # Busca flexível para caracteres especiais (ex: ? em vez de Ú)
                        elif self._arquivo_compativel(arquivo, nome_arquivo_esperado):
                            caminho_completo = os.path.join(diretorio_downloads, arquivo)
                            
                            if not arquivo.endswith('.crdownload') and os.path.isfile(caminho_completo):
                                if self._arquivo_esta_completo(caminho_completo):
                                    print(f"[OK] Arquivo compatível encontrado: {arquivo} (esperado: {nome_arquivo_esperado})")
                                    return caminho_completo
                
                except Exception as e:
                    print(f"[AVISO] Erro ao procurar arquivo: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout - arquivo '{nome_arquivo_esperado}' não encontrado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao detectar arquivo por nome: {e}")
            return None
    
    def _arquivo_compativel(self, arquivo_real, arquivo_esperado):
        """
        Verifica se o arquivo real é compatível com o esperado, considerando caracteres especiais
        """
        try:
            # Normalizar nomes removendo acentos e caracteres especiais
            import unicodedata
            import re
            
            def normalizar_nome(nome):
                # Remover acentos
                nome_normalizado = unicodedata.normalize('NFD', nome)
                nome_normalizado = ''.join(c for c in nome_normalizado if unicodedata.category(c) != 'Mn')
                
                # Substituir caracteres problemáticos (usar replace múltiplo para diferentes ?)
                nome_normalizado = nome_normalizado.replace('?', 'U')  # ? pode ser Ú
                nome_normalizado = nome_normalizado.replace('?', 'A')  # ? pode ser Á  
                nome_normalizado = nome_normalizado.replace('?', 'E')  # ? pode ser É
                nome_normalizado = nome_normalizado.replace('?', 'I')  # ? pode ser Í
                nome_normalizado = nome_normalizado.replace('?', 'O')  # ? pode ser Ó
                nome_normalizado = nome_normalizado.replace('?', 'C')  # ? pode ser Ç
                # Também substituir ? genérico por U (mais comum)
                nome_normalizado = nome_normalizado.replace('?', 'U')
                
                # Converter para minúsculas e remover espaços extras
                nome_normalizado = re.sub(r'\s+', ' ', nome_normalizado.lower().strip())
                
                return nome_normalizado
            
            arquivo_real_norm = normalizar_nome(arquivo_real)
            arquivo_esperado_norm = normalizar_nome(arquivo_esperado)
            
            # Verificar se são compatíveis
            if arquivo_real_norm == arquivo_esperado_norm:
                return True
            
            # Verificar se o arquivo real contém as palavras-chave do esperado
            palavras_esperadas = arquivo_esperado_norm.split()
            palavras_reais = arquivo_real_norm.split()
            
            # Se pelo menos 70% das palavras coincidem, considerar compatível
            palavras_coincidentes = sum(1 for palavra in palavras_esperadas if palavra in palavras_reais)
            percentual_coincidencia = palavras_coincidentes / len(palavras_esperadas) if palavras_esperadas else 0
            
            return percentual_coincidencia >= 0.7
            
        except Exception as e:
            print(f"[AVISO] Erro ao verificar compatibilidade de arquivo: {e}")
            return False
    
    def aguardar_download_ultimo_arquivo(self, nome_documento, timeout=5):
        """
        Lógica simples: conta arquivos antes -> clique -> pega último arquivo adicionado
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            
            # PASSO 1: Contar arquivos ANTES do clique
            arquivos_antes = []
            try:
                todos_arquivos = os.listdir(diretorio_downloads)
                for arquivo in todos_arquivos:
                    caminho = os.path.join(diretorio_downloads, arquivo)
                    if os.path.isfile(caminho):
                        extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                        if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                            arquivos_antes.append(arquivo)
                
                print(f"[ARQUIVO] {len(arquivos_antes)} arquivos válidos antes do clique")
            except Exception as e:
                print(f"[AVISO] Erro ao contar arquivos antes: {e}")
                arquivos_antes = []
            
            # PASSO 2: Aguardar download e detectar novo arquivo
            tempo_inicial = time.time()
            print(f"[TEMPO] Aguardando {timeout} segundos por novo arquivo...")
            
            while time.time() - tempo_inicial < timeout:
                try:
                    # Listar arquivos atuais
                    arquivos_atuais = []
                    todos_arquivos = os.listdir(diretorio_downloads)
                    
                    for arquivo in todos_arquivos:
                        caminho = os.path.join(diretorio_downloads, arquivo)
                        if os.path.isfile(caminho):
                            extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                            if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                                arquivos_atuais.append(arquivo)
                    
                    # Verificar se há mais arquivos agora
                    if len(arquivos_atuais) > len(arquivos_antes):
                        # Encontrar arquivos novos
                        arquivos_novos = []
                        for arquivo in arquivos_atuais:
                            if arquivo not in arquivos_antes:
                                arquivos_novos.append(arquivo)
                        
                        if arquivos_novos:
                            print(f"📥 {len(arquivos_novos)} arquivos novos detectados:")
                            for arquivo in arquivos_novos:
                                print(f"   [DOC] {arquivo}")
                            
                            # Pegar o primeiro arquivo novo (mais recente)
                            arquivo_baixado = arquivos_novos[0]
                            caminho_completo = os.path.join(diretorio_downloads, arquivo_baixado)
                            
                            # Verificar se arquivo está completo
                            if self._arquivo_esta_completo(caminho_completo):
                                print(f"[OK] Último arquivo baixado: {arquivo_baixado}")
                                return caminho_completo
                            else:
                                print(f"[AGUARDE] Arquivo ainda sendo baixado: {arquivo_baixado}")
                
                except Exception as e:
                    print(f"[AVISO] Erro ao verificar arquivos: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout de {timeout}s - nenhum arquivo novo detectado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao aguardar último arquivo: {e}")
            return None
    
    def aguardar_download_documento_campo_especifico(self, nome_documento, timeout=5):
        """
        Aguarda download de campo específico com ícone (aceita qualquer arquivo baixado)
        Usado quando ícone de download está presente - significa que documento foi anexado
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            tempo_inicial = time.time()
            
            # Obter informações dos arquivos antes do download
            arquivos_info_antes = {}
            try:
                for arquivo in os.listdir(diretorio_downloads):
                    caminho = os.path.join(diretorio_downloads, arquivo)
                    if os.path.isfile(caminho):
                        arquivos_info_antes[arquivo] = os.path.getmtime(caminho)
                
                print(f"[ARQUIVO] {len(arquivos_info_antes)} arquivos antes do download")
            except Exception as e:
                print(f"[AVISO] Erro ao listar arquivos: {e}")
                arquivos_info_antes = {}
            
            print(f"[TEMPO] Aguardando {timeout} segundos por download do campo específico...")
            
            # Aguardar e aceitar QUALQUER arquivo válido baixado
            while time.time() - tempo_inicial < timeout:
                try:
                    # Buscar arquivos novos ou modificados recentemente
                    arquivos_candidatos = []
                    
                    for arquivo in os.listdir(diretorio_downloads):
                        caminho_arquivo = os.path.join(diretorio_downloads, arquivo)
                        
                        if os.path.isfile(caminho_arquivo):
                            extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                            if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                                # Verificar se é novo ou foi modificado recentemente
                                timestamp_atual = os.path.getmtime(caminho_arquivo)
                                
                                # Arquivo novo (não existia antes)
                                if arquivo not in arquivos_info_antes:
                                    arquivos_candidatos.append((arquivo, caminho_arquivo, 'novo'))
                                # Arquivo modificado recentemente (depois do início da espera)
                                elif timestamp_atual > tempo_inicial:
                                    arquivos_candidatos.append((arquivo, caminho_arquivo, 'modificado'))
                    
                    if arquivos_candidatos:
                        print(f"📥 {len(arquivos_candidatos)} arquivos candidatos detectados:")
                        for arquivo, caminho, tipo in arquivos_candidatos:
                            print(f"   [DOC] {arquivo} ({tipo})")
                        
                        # Para campos específicos com ícone, aceitar QUALQUER arquivo válido
                        # Priorizar arquivos novos sobre modificados
                        arquivos_candidatos.sort(key=lambda x: x[2] == 'novo', reverse=True)
                        
                        for arquivo, caminho_arquivo, tipo in arquivos_candidatos:
                            # Verificar apenas se arquivo está completo
                            if self._arquivo_esta_completo(caminho_arquivo):
                                print(f"[OK] Campo específico - arquivo aceito ({tipo}): {arquivo}")
                                return caminho_arquivo
                
                except Exception as e:
                    print(f"[AVISO] Erro ao verificar downloads: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout de {timeout}s - nenhum arquivo detectado para campo específico")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao aguardar download: {e}")
            return None
    
    def aguardar_download_documento_por_nome(self, nome_arquivo_esperado, nome_documento, timeout=5):
        """
        Aguarda download de arquivo específico por nome exato encontrado na tabela
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            tempo_inicial = time.time()
            
            print(f"[TARGET] Procurando especificamente por: {nome_arquivo_esperado}")
            print(f"[TEMPO] Aguardando {timeout} segundos por download...")
            
            # Aguardar o arquivo específico aparecer
            while time.time() - tempo_inicial < timeout:
                try:
                    arquivos_no_diretorio = os.listdir(diretorio_downloads)
                    
                    # Procurar pelo arquivo específico
                    for arquivo in arquivos_no_diretorio:
                        if arquivo == nome_arquivo_esperado:
                            caminho_completo = os.path.join(diretorio_downloads, arquivo)
                            
                            # Verificar se não é um arquivo de download temporário
                            if not arquivo.endswith('.crdownload') and os.path.isfile(caminho_completo):
                                # Verificar se arquivo está completo
                                if self._arquivo_esta_completo(caminho_completo):
                                    print(f"[OK] Arquivo encontrado e completo: {arquivo}")
                                    return caminho_completo
                                else:
                                    print(f"[AGUARDE] Arquivo ainda sendo baixado: {arquivo}")
                    
                    # Também procurar por arquivos similares (sem a extensão ou pequenas variações)
                    nome_base = nome_arquivo_esperado.rsplit('.', 1)[0] if '.' in nome_arquivo_esperado else nome_arquivo_esperado
                    
                    for arquivo in arquivos_no_diretorio:
                        if nome_base.lower() in arquivo.lower() and not arquivo.endswith('.crdownload'):
                            caminho_completo = os.path.join(diretorio_downloads, arquivo)
                            
                            # Verificar se é um arquivo válido e foi modificado recentemente
                            if os.path.isfile(caminho_completo):
                                timestamp_arquivo = os.path.getmtime(caminho_completo)
                                if timestamp_arquivo > tempo_inicial:
                                    if self._arquivo_esta_completo(caminho_completo):
                                        print(f"[OK] Arquivo similar encontrado: {arquivo}")
                                        return caminho_completo
                
                except Exception as e:
                    print(f"[AVISO] Erro ao verificar downloads: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout de {timeout}s - arquivo '{nome_arquivo_esperado}' não encontrado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao aguardar download: {e}")
            return None
    
    def aguardar_download_documento_individual_tabela(self, nome_documento, timeout=5):
        """
        Aguarda download de documento encontrado na tabela (aceita qualquer arquivo baixado)
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            tempo_inicial = time.time()
            
            # Obter informações dos arquivos antes do download
            arquivos_info_antes = {}
            try:
                for arquivo in os.listdir(diretorio_downloads):
                    caminho = os.path.join(diretorio_downloads, arquivo)
                    if os.path.isfile(caminho):
                        arquivos_info_antes[arquivo] = os.path.getmtime(caminho)
                
                print(f"[ARQUIVO] {len(arquivos_info_antes)} arquivos antes do download")
            except Exception as e:
                print(f"[AVISO] Erro ao listar arquivos: {e}")
                arquivos_info_antes = {}
            
            print(f"[TEMPO] Aguardando {timeout} segundos por novo download...")
            
            # Aguardar e detectar qualquer arquivo baixado
            while time.time() - tempo_inicial < timeout:
                try:
                    # Buscar arquivos novos ou modificados recentemente
                    arquivos_candidatos = []
                    
                    for arquivo in os.listdir(diretorio_downloads):
                        caminho_arquivo = os.path.join(diretorio_downloads, arquivo)
                        
                        if os.path.isfile(caminho_arquivo):
                            extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                            if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                                # Verificar se é novo ou foi modificado recentemente
                                timestamp_atual = os.path.getmtime(caminho_arquivo)
                                
                                # Arquivo novo (não existia antes)
                                if arquivo not in arquivos_info_antes:
                                    arquivos_candidatos.append((arquivo, caminho_arquivo, 'novo'))
                                # Arquivo modificado recentemente (depois do início da espera)
                                elif timestamp_atual > tempo_inicial:
                                    arquivos_candidatos.append((arquivo, caminho_arquivo, 'modificado'))
                    
                    if arquivos_candidatos:
                        print(f"📥 {len(arquivos_candidatos)} arquivos candidatos detectados:")
                        for arquivo, caminho, tipo in arquivos_candidatos:
                            print(f"   [DOC] {arquivo} ({tipo})")
                        
                        # Para downloads da tabela, aceitar QUALQUER arquivo válido baixado
                        arquivos_candidatos.sort(key=lambda x: x[2] == 'novo', reverse=True)
                        
                        for arquivo, caminho_arquivo, tipo in arquivos_candidatos:
                            # Verificar apenas se arquivo está completo
                            if self._arquivo_esta_completo(caminho_arquivo):
                                print(f"[OK] Arquivo baixado da tabela aceito ({tipo}): {arquivo}")
                                return caminho_arquivo
                
                except Exception as e:
                    print(f"[AVISO] Erro ao verificar downloads: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout de {timeout}s - nenhum arquivo detectado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao aguardar download: {e}")
            return None
    
    def aguardar_download_documento_individual(self, nome_documento, timeout=5):
        """
        Aguarda o download de um documento específico (detecção por timestamp)
        """
        try:
            import time
            import os
            
            diretorio_downloads = self.obter_diretorio_downloads()
            tempo_inicial = time.time()
            
            # Obter informações dos arquivos antes do download
            arquivos_info_antes = {}
            try:
                for arquivo in os.listdir(diretorio_downloads):
                    caminho = os.path.join(diretorio_downloads, arquivo)
                    if os.path.isfile(caminho):
                        arquivos_info_antes[arquivo] = os.path.getmtime(caminho)
                
                print(f"[ARQUIVO] {len(arquivos_info_antes)} arquivos antes do download")
            except Exception as e:
                print(f"[AVISO] Erro ao listar arquivos: {e}")
                arquivos_info_antes = {}
            
            print(f"[TEMPO] Aguardando {timeout} segundos por novo download...")
            
            # Aguardar e detectar por timestamp de modificação
            while time.time() - tempo_inicial < timeout:
                try:
                    # Buscar arquivos novos ou modificados recentemente
                    arquivos_candidatos = []
                    
                    for arquivo in os.listdir(diretorio_downloads):
                        caminho_arquivo = os.path.join(diretorio_downloads, arquivo)
                        
                        if os.path.isfile(caminho_arquivo):
                            extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                            if arquivo.lower().endswith(extensoes_validas) and not arquivo.endswith('.crdownload'):
                                # Verificar se é novo ou foi modificado recentemente
                                timestamp_atual = os.path.getmtime(caminho_arquivo)
                                
                                # Arquivo novo (não existia antes)
                                if arquivo not in arquivos_info_antes:
                                    arquivos_candidatos.append((arquivo, caminho_arquivo, 'novo'))
                                # Arquivo modificado recentemente (depois do início da espera)
                                elif timestamp_atual > tempo_inicial:
                                    arquivos_candidatos.append((arquivo, caminho_arquivo, 'modificado'))
                    
                    if arquivos_candidatos:
                        print(f"📥 {len(arquivos_candidatos)} arquivos candidatos detectados:")
                        for arquivo, caminho, tipo in arquivos_candidatos:
                            print(f"   [DOC] {arquivo} ({tipo})")
                        
                        # Processar candidatos em ordem de prioridade (novos primeiro)
                        arquivos_candidatos.sort(key=lambda x: x[2] == 'novo', reverse=True)
                        
                        for arquivo, caminho_arquivo, tipo in arquivos_candidatos:
                            # Verificar se arquivo está completo
                            if self._arquivo_esta_completo(caminho_arquivo):
                                # Validar se corresponde ao documento
                                if self._validar_arquivo_para_documento(arquivo, nome_documento):
                                    print(f"[OK] Download detectado ({tipo}): {arquivo}")
                                    return caminho_arquivo
                                else:
                                    print(f"[AVISO] Arquivo não corresponde ({tipo}): {arquivo}")
                        
                        # Se nenhum correspondeu mas há candidatos válidos, usar o primeiro novo
                        for arquivo, caminho_arquivo, tipo in arquivos_candidatos:
                            if tipo == 'novo' and self._arquivo_esta_completo(caminho_arquivo):
                                print(f"[AVISO] Usando primeiro arquivo novo encontrado: {arquivo}")
                                return caminho_arquivo
                
                except Exception as e:
                    print(f"[AVISO] Erro ao verificar downloads: {e}")
                
                time.sleep(0.5)
            
            print(f"⏰ Timeout de {timeout}s - nenhum arquivo adequado detectado")
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro ao aguardar download: {e}")
            return None

    def _arquivo_esta_completo(self, caminho_arquivo, max_tentativas=3):
        """
        Verifica se um arquivo está completo (não está crescendo)
        """
        try:
            import time
            import os
            
            for tentativa in range(max_tentativas):
                try:
                    tamanho1 = os.path.getsize(caminho_arquivo)
                    time.sleep(0.5)
                    tamanho2 = os.path.getsize(caminho_arquivo)
                    
                    if tamanho1 == tamanho2 and tamanho1 > 0:
                        return True
                    elif tentativa < max_tentativas - 1:
                        time.sleep(1)  # Aguardar mais um pouco
                        
                except Exception as e:
                    if tentativa < max_tentativas - 1:
                        time.sleep(1)
                    else:
                        print(f"[AVISO] Erro ao verificar tamanho do arquivo: {e}")
                        
            return False
            
        except Exception as e:
            print(f"[AVISO] Erro ao verificar se arquivo está completo: {e}")
            return False

    def _validar_arquivo_para_documento(self, nome_arquivo, nome_documento):
        """
        Validação mais flexível para documentos específicos
        """
        try:
            nome_arquivo_lower = nome_arquivo.lower()
            nome_documento_lower = nome_documento.lower()
            
            print(f"[BUSCA] Validando arquivo '{nome_arquivo}' para documento '{nome_documento}'")
            
            # Para comprovante de redução de prazo, aceitar certidões de nascimento também
            if 'comprovante de redução de prazo' in nome_documento_lower:
                termos_aceitos = ['redução', 'reducao', 'prazo', 'nascimento', 'certidão', 'certidao', 'filho', 'filha', 'brasileiro', 'eddy']
                
                # Verificar se contém algum termo aceito
                termo_encontrado = None
                for termo in termos_aceitos:
                    if termo in nome_arquivo_lower:
                        termo_encontrado = termo
                        break
                
                if termo_encontrado:
                    print(f"[OK] Arquivo aceito para comprovante de redução (termo encontrado: '{termo_encontrado}'): {nome_arquivo}")
                    return True
                else:
                    print(f"[ERRO] Arquivo rejeitado para comprovante de redução (termos esperados: {termos_aceitos}): {nome_arquivo}")
                    return False
            
            # Para outros documentos, usar validação padrão
            resultado = self._arquivo_corresponde_documento(nome_arquivo, nome_documento)
            print(f"[INFO] Validação padrão para '{nome_arquivo}': {resultado}")
            return resultado
            
        except Exception as e:
            print(f"[AVISO] Erro na validação flexível: {e}")
            return True  # Em caso de erro, aceitar o arquivo

    def _arquivo_corresponde_documento(self, nome_arquivo, nome_documento):
        """
        Verifica se o arquivo baixado corresponde ao documento esperado
        """
        try:
            nome_arquivo_lower = nome_arquivo.lower()
            nome_documento_lower = nome_documento.lower()
            
            # Mapeamento de documentos para palavras-chave que devem estar no nome do arquivo
            mapeamento_palavras = {
                'comprovante de redução de prazo': ['redução', 'reducao', 'prazo', 'residência', 'residencia'],
                'comprovante de comunicação em português': ['comunicação', 'comunicacao', 'português', 'portugues', 'lingua', 'língua', 'certificado'],
                'certidão de antecedentes criminais (brasil)': ['antecedentes', 'criminais', 'certidão', 'certidao', 'federal', 'estadual'],
                'atestado antecedentes criminais (país de origem)': ['antecedentes', 'atestado', 'criminal', 'origem', 'país', 'pais'],
                'comprovante de tempo de residência': ['tempo', 'residência', 'residencia', 'comprovante'],
                'comprovante da situação cadastral do cpf': ['cpf', 'cadastral', 'situação', 'situacao', 'receita'],
                'carteira de registro nacional migratório': ['rnm', 'crnm', 'registro', 'migratório', 'migratorio', 'carteira'],
                'documento de viagem internacional': ['passaporte', 'viagem', 'internacional', 'documento']
            }
            
            # Buscar palavras-chave correspondentes ao documento
            palavras_esperadas = []
            for doc_tipo, palavras in mapeamento_palavras.items():
                if doc_tipo in nome_documento_lower:
                    palavras_esperadas = palavras
                    break
            
            if not palavras_esperadas:
                # Se não encontrou mapeamento específico, aceitar qualquer arquivo
                print(f"[AVISO] Documento '{nome_documento}' sem mapeamento específico - aceitando arquivo")
                return True
            
            # Verificar se pelo menos uma palavra-chave está no nome do arquivo
            tem_palavra_relevante = any(palavra in nome_arquivo_lower for palavra in palavras_esperadas)
            
            if tem_palavra_relevante:
                print(f"[OK] Arquivo '{nome_arquivo}' corresponde ao documento '{nome_documento}'")
                return True
            else:
                print(f"[ERRO] Arquivo '{nome_arquivo}' NÃO corresponde ao documento '{nome_documento}' (palavras esperadas: {palavras_esperadas})")
                return False
                
        except Exception as e:
            print(f"[AVISO] Erro ao verificar correspondência de arquivo: {e}")
            # Em caso de erro, aceitar o arquivo para não bloquear o fluxo
            return True

    def executar_ocr_sem_cache(self, caminho_arquivo, nome_documento):
        """
        Executa OCR em um arquivo específico sem usar cache
        """
        try:
            print(f"[BUSCA] Executando OCR em {nome_documento}...")
            
            # Verificar extensão do arquivo
            extensao = caminho_arquivo.lower().split('.')[-1]
            
            if extensao in ['jpg', 'jpeg', 'png']:
                # Processar arquivos de imagem diretamente
                return self._processar_imagem_ocr(caminho_arquivo, nome_documento)
            elif extensao == 'pdf':
                # Processar arquivos PDF
                return self._processar_pdf_ocr(caminho_arquivo, nome_documento)
            else:
                print(f"[AVISO] Tipo de arquivo não suportado: {extensao}")
                return ""
                
        except Exception as e:
            print(f"[ERRO] Erro no OCR: {e}")
            return ""

    def _processar_imagem_ocr(self, caminho_arquivo, nome_documento):
        """
        Processa arquivos de imagem (JPG, JPEG, PNG) com OCR Mistral + Pré-processamento
        Usa: CLAHE + Sharpening + Remoção de Ruído (Filtro Bilateral)
        """
        try:
            import cv2
            import numpy as np
            from PIL import Image
            
            print(f"[MISTRAL OCR] Processando imagem: {caminho_arquivo}")
            
            # 1. Aplicar pré-processamento otimizado para Mistral
            preprocessor = ImagePreprocessor()
            img_processada, metadata = preprocessor.preprocess_for_mistral(caminho_arquivo)
            
            print(f"[PRÉ-PROC] Etapas aplicadas: {', '.join(metadata.get('etapas_aplicadas', []))}")
            print(f"[PRÉ-PROC] Qualidade da imagem: {metadata.get('quality_score', 0):.1f}/100")
            
            # 2. Salvar imagem processada temporariamente
            temp_path = caminho_arquivo.replace('.', '_processed.')
            cv2.imwrite(temp_path, img_processada)
            
            # 3. Executar OCR com Mistral
            texto_ocr = self._executar_mistral_ocr(temp_path)
            
            # 4. Limpar arquivo temporário
            try:
                os.remove(temp_path)
            except:
                pass
            
            print(f"[MISTRAL OCR] Concluído: {len(texto_ocr)} caracteres extraídos")
            return texto_ocr.strip()
            
        except Exception as e:
            print(f"[ERRO] Erro no OCR de imagem com Mistral: {e}")
            # Fallback para Tesseract se Mistral falhar
            try:
                print(f"[FALLBACK] Tentando Tesseract...")
                img = Image.open(caminho_arquivo)
                texto_ocr = pytesseract.image_to_string(img, lang='por+eng')
                print(f"[FALLBACK] Tesseract: {len(texto_ocr)} caracteres")
                return texto_ocr.strip()
            except:
                return ""

    def _processar_pdf_ocr(self, caminho_arquivo, nome_documento):
        """
        Processa arquivos PDF com OCR Mistral + Pré-processamento
        Usa: CLAHE + Sharpening + Remoção de Ruído (Filtro Bilateral)
        """
        try:
            import fitz  # PyMuPDF
            import cv2
            import numpy as np
            
            # Configurar máximo de páginas baseado no documento
            nome_lower = nome_documento.lower()
            
            # Documentos que devem ler apenas a primeira página
            documentos_primeira_pagina = [
                'tempo de residência',
                'viagem internacional',
                'comprovante de residência',
                'residencia',
                'viagens internacionais'
            ]
            
            max_paginas = 1 if any(doc in nome_lower for doc in documentos_primeira_pagina) else None
            
            # Abrir PDF
            doc = fitz.open(caminho_arquivo)
            texto_completo = ""
            
            # Processar páginas
            paginas_a_processar = min(len(doc), max_paginas) if max_paginas else len(doc)
            
            print(f"[MISTRAL OCR] Processando PDF: {paginas_a_processar} página(s)")
            
            for num_pagina in range(paginas_a_processar):
                pagina = doc[num_pagina]
                
                # Tentar extrair texto diretamente (PDF com texto)
                texto_pagina = pagina.get_text()
                
                if texto_pagina.strip() and len(texto_pagina.strip()) > 50:
                    # PDF tem texto embutido de qualidade
                    texto_completo += texto_pagina + "\n"
                    print(f"[PDF] Página {num_pagina + 1}: Texto direto extraído ({len(texto_pagina)} chars)")
                else:
                    # PDF é imagem ou texto pobre - usar OCR com pré-processamento
                    print(f"[PDF] Página {num_pagina + 1}: Aplicando Mistral OCR...")
                    
                    # Converter página para imagem em alta resolução
                    pix = pagina.get_pixmap(matrix=fitz.Matrix(3.0, 3.0))  # Alta resolução para OCR
                    img_data = pix.tobytes("png")
                    
                    # Salvar imagem temporária
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                        tmp_img.write(img_data)
                        temp_path = tmp_img.name
                    
                    try:
                        # Aplicar pré-processamento
                        preprocessor = ImagePreprocessor()
                        img_processada, metadata = preprocessor.preprocess_for_mistral(temp_path)
                        
                        print(f"[PRÉ-PROC] Pág {num_pagina + 1}: {', '.join(metadata.get('etapas_aplicadas', []))}")
                        
                        # Salvar imagem processada
                        processed_path = temp_path.replace('.png', '_processed.png')
                        cv2.imwrite(processed_path, img_processada)
                        
                        # Executar OCR com Mistral
                        texto_ocr = self._executar_mistral_ocr(processed_path)
                        texto_completo += texto_ocr + "\n"
                        
                        print(f"[MISTRAL OCR] Pág {num_pagina + 1}: {len(texto_ocr)} caracteres")
                        
                        # Limpar arquivos temporários
                        try:
                            os.remove(temp_path)
                            os.remove(processed_path)
                        except:
                            pass
                            
                    except Exception as e_ocr:
                        print(f"[ERRO] Erro no Mistral OCR da página {num_pagina + 1}: {e_ocr}")
                        # Fallback para Tesseract
                        try:
                            from PIL import Image
                            import io
                            img = Image.open(io.BytesIO(img_data))
                            texto_ocr = pytesseract.image_to_string(img, lang='por+eng')
                            texto_completo += texto_ocr + "\n"
                            print(f"[FALLBACK] Tesseract: {len(texto_ocr)} caracteres")
                        except:
                            pass
                        # Limpar
                        try:
                            os.remove(temp_path)
                        except:
                            pass
            
            doc.close()
            
            print(f"[MISTRAL OCR] PDF concluído: {len(texto_completo)} caracteres totais")
            return texto_completo.strip()
            
        except Exception as e:
            print(f"[ERRO] Erro no OCR de PDF com Mistral: {e}")
            return ""

    def _executar_mistral_ocr(self, caminho_imagem):
        """
        Executa OCR usando Mistral Pixtral-12b (Vision API)
        """
        try:
            # Carregar API Key do Mistral
            mistral_api_key = os.environ.get("MISTRAL_API_KEY")
            
            if not mistral_api_key:
                raise ValueError("MISTRAL_API_KEY não configurada no .env")
            
            # Inicializar cliente Mistral
            client = Mistral(api_key=mistral_api_key)
            
            # Carregar e codificar imagem em base64
            with open(caminho_imagem, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Preparar prompt otimizado para extração de texto
            prompt = (
                "Extraia TODO o texto deste documento de forma precisa. "
                "Mantenha a formatação original, incluindo quebras de linha. "
                "Se houver tabelas, preserve a estrutura. "
                "Não adicione comentários, apenas retorne o texto extraído."
            )
            
            # Chamar API Mistral Vision
            response = client.chat.complete(
                model="pixtral-12b-2409",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": f"data:image/png;base64,{img_base64}"
                            }
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.0  # Determinístico para OCR
            )
            
            # Extrair texto da resposta
            texto_extraido = response.choices[0].message.content
            
            return texto_extraido.strip()
            
        except Exception as e:
            print(f"[ERRO] Falha no Mistral OCR: {e}")
            raise
    
    def validar_conteudo_documento_especifico(self, nome_documento, texto):
        """
        Valida o conteúdo específico de cada tipo de documento usando critérios atualizados
        """
        try:
            from validacao_documentos_ordinaria import (
                validar_crnm,
                validar_cpf_situacao_cadastral,
                validar_antecedentes_brasil,
                validar_antecedentes_pais_origem,
                validar_documento_portugues,
                validar_comprovante_reducao_prazo,
                validar_documento_generico
            )
            
            nome_lower = nome_documento.lower()
            
            # CRNM - pelo menos 3 termos
            if 'crnm' in nome_lower or 'registro nacional migratório' in nome_lower:
                return validar_crnm(texto)
            
            # CPF - se tiver "Situação Cadastral: Regular", validar automaticamente, senão verificar 2 termos
            elif 'cpf' in nome_lower:
                return validar_cpf_situacao_cadastral(texto)
            
            # Antecedentes criminais Brasil - modelo da análise definitiva
            elif 'antecedentes criminais (brasil)' in nome_lower or 'certidão de antecedentes criminais (brasil)' in nome_lower:
                return validar_antecedentes_brasil(texto)
            
            # Antecedentes criminais país de origem - pelo menos 1 termo
            elif 'país de origem' in nome_lower or 'atestado antecedentes criminais' in nome_lower:
                return validar_antecedentes_pais_origem(texto)
            
            # Comunicação em português - pelo menos 2-3 termos
            elif 'comunicação em português' in nome_lower or 'comprovante de comunicação' in nome_lower:
                return validar_documento_portugues(texto)
            
            # Comprovante de redução de prazo - pelo menos 2 termos
            elif 'comprovante de redução de prazo' in nome_lower:
                return validar_comprovante_reducao_prazo(texto)
            
            # Outros documentos - se não foi baixado ou sem OCR, não validar
            else:
                return validar_documento_generico(texto, nome_documento)
                
        except Exception as e:
            print(f"[ERRO] Erro na validação específica: {e}")
            return False

    def verificar_requisito_iv_com_download_individual(self):
        """
        REQUISITO IV – Antecedentes criminais com download individual
        """
        try:
            print("[BUSCA] Baixando e validando antecedentes criminais individualmente...")
            
            # Verificar se a pessoa ingressou menor (dispensa antecedentes do país de origem)
            dispensar_antecedentes_origem = False
            try:
                # Extrair dados pessoais para verificar idade de ingresso
                dados_pessoais = getattr(self, 'dados_pessoais_extraidos', {})
                data_nascimento = dados_pessoais.get('data_nascimento', '')
                data_entrada = dados_pessoais.get('data_entrada', '')
                
                if data_nascimento and data_entrada:
                    from datetime import datetime
                    try:
                        # Converter datas
                        nascimento = datetime.strptime(data_nascimento, '%d/%m/%Y')
                        entrada = datetime.strptime(data_entrada, '%d/%m/%Y')
                        
                        # Calcular idade na entrada
                        idade_entrada = (entrada - nascimento).days / 365.25
                        
                        if idade_entrada < 18:
                            dispensar_antecedentes_origem = True
                            print(f"✅ DISPENSA: Pessoa ingressou com {idade_entrada:.1f} anos (menor de idade)")
                            print("📖 Fundamento: Menores de idade não precisam de antecedentes do país de origem")
                    except Exception as e:
                        print(f"[AVISO] Erro ao calcular idade de ingresso: {e}")
                        
            except Exception as e:
                print(f"[AVISO] Erro ao verificar idade de ingresso: {e}")
            
            # Lista de documentos de antecedentes criminais
            documentos_antecedentes = [
                'Certidão de antecedentes criminais (Brasil)',
                'Atestado antecedentes criminais (país de origem)' if not dispensar_antecedentes_origem else None
            ]
            
            # Remover None da lista
            documentos_antecedentes = [doc for doc in documentos_antecedentes if doc is not None]
            
            documentos_validos = 0
            tem_condenacao = False
            documentos_com_problema = []
            documentos_nao_anexados = []
            
            for doc in documentos_antecedentes:
                print(f"\n[DOC] Processando: {doc}")
                try:
                    doc_valido = self.baixar_e_validar_documento_individual(doc)
                    
                    if doc_valido:
                        documentos_validos += 1
                        print(f"✅ {doc}: VÁLIDO")
                    else:
                        print(f"❌ {doc}: INVÁLIDO ou não anexado")
                        # Identificar se foi problema de validação ou não anexação
                        if 'não anexado' in str(doc_valido).lower() or 'não encontrado' in str(doc_valido).lower():
                            documentos_nao_anexados.append(doc)
                        else:
                            documentos_com_problema.append(doc)
                        
                except Exception as e:
                    print(f"❌ {doc}: ERRO NO PROCESSAMENTO - {e}")
                    documentos_com_problema.append(f"{doc} (erro: {e})")
                    # Continuar com o próximo documento mesmo se este falhar
            
            # Resumo de validação
            total_docs = len(documentos_antecedentes)
            print(f"\n{'='*60}")
            print(f"📊 RESUMO REQUISITO IV: {documentos_validos}/{total_docs} documentos válidos")
            print(f"{'='*60}")
            
            # Verificar se precisa de comprovante de reabilitação
            if tem_condenacao:
                print("\n[DOC] Verificando comprovante de reabilitação...")
                reabilitacao_valida = self.baixar_e_validar_documento_individual('Comprovante de reabilitação')
                if not reabilitacao_valida:
                    print("❌ Comprovante de reabilitação: NÃO ANEXADO ou INVÁLIDO")
                    return {
                        'atendido': False,
                        'motivo': 'Comprovante de reabilitação obrigatório não anexado'
                    }
            
            # Verificar se todos os documentos obrigatórios são válidos
            if documentos_validos == len(documentos_antecedentes):
                if dispensar_antecedentes_origem:
                    print("✅ REQUISITO IV: ATENDIDO - Antecedentes Brasil válido + Dispensa de antecedentes origem (ingresso menor)")
                    return {
                        'atendido': True,
                        'motivo': 'Antecedentes criminais em ordem (dispensa de origem por ingresso menor)',
                        'pode_continuar': True,
                        'dispensado_origem': True
                    }
                else:
                    print("✅ REQUISITO IV: ATENDIDO - Todos os antecedentes válidos")
                    return {
                        'atendido': True,
                        'motivo': 'Antecedentes criminais em ordem',
                        'pode_continuar': True
                    }
            else:
                print("❌ REQUISITO IV: NÃO ATENDIDO - Documentos inválidos ou faltantes")
                
                # Criar mensagem específica sobre quais documentos tiveram problema
                motivos_especificos = []
                
                if documentos_nao_anexados:
                    for doc in documentos_nao_anexados:
                        if 'Brasil' in doc:
                            motivos_especificos.append('Antecedentes criminais do Brasil não anexado')
                        elif 'país de origem' in doc:
                            motivos_especificos.append('Antecedentes criminais do país de origem não anexado')
                
                if documentos_com_problema:
                    for doc in documentos_com_problema:
                        if 'Brasil' in doc:
                            motivos_especificos.append('Antecedentes criminais do Brasil inválido')
                        elif 'país de origem' in doc:
                            motivos_especificos.append('Antecedentes criminais do país de origem inválido')
                
                motivo_detalhado = '; '.join(motivos_especificos) if motivos_especificos else 'Antecedentes criminais inválidos ou não anexados'
                
                print(f"📋 Motivos específicos: {motivo_detalhado}")
                
                return {
                    'atendido': False,
                    'motivo': motivo_detalhado,
                    'pode_continuar': False,
                    'documentos_nao_anexados': documentos_nao_anexados,
                    'documentos_com_problema': documentos_com_problema,
                    'motivos_especificos': motivos_especificos
                }
                
        except Exception as e:
            print(f"[ERRO] Erro na verificação de antecedentes: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}'
            }

    def verificar_documentos_complementares_com_download_individual(self):
        """
        DOCUMENTOS COMPLEMENTARES com download individual
        """
        try:
            print("[BUSCA] Baixando e validando documentos complementares individualmente...")
            
            # Lista de documentos complementares restantes
            documentos_complementares = [
                'Comprovante de tempo de residência',
                'Comprovante da situação cadastral do CPF', 
                'Carteira de Registro Nacional Migratório',
                'Documento de viagem internacional'
            ]
            
            documentos_validos = 0
            documentos_faltantes = []
            
            for doc in documentos_complementares:
                print(f"\n[DOC] Processando: {doc}")
                try:
                    doc_valido = self.baixar_e_validar_documento_individual(doc)
                    
                    if doc_valido:
                        documentos_validos += 1
                        print(f"[OK] {doc}: VÁLIDO")
                    else:
                        print(f"[ERRO] {doc}: INVÁLIDO ou não anexado")
                        # Mapear para item do anexo
                        if 'crnm' in doc.lower() or 'registro nacional' in doc.lower():
                            documentos_faltantes.append('Não anexou item 3')
                        elif 'cpf' in doc.lower():
                            documentos_faltantes.append('Não anexou item 4')
                        elif 'tempo de residência' in doc.lower():
                            documentos_faltantes.append('Não anexou item 8')
                        elif 'viagem internacional' in doc.lower():
                            documentos_faltantes.append('Não anexou item 2')
                            
                except Exception as e:
                    print(f"[ERRO] {doc}: ERRO NO PROCESSAMENTO - {e}")
                    # Mapear erro para item do anexo também
                    if 'crnm' in doc.lower() or 'registro nacional' in doc.lower():
                        documentos_faltantes.append('Não anexou item 3')
                    elif 'cpf' in doc.lower():
                        documentos_faltantes.append('Não anexou item 4')
                    elif 'tempo de residência' in doc.lower():
                        documentos_faltantes.append('Não anexou item 8')
                    elif 'viagem internacional' in doc.lower():
                        documentos_faltantes.append('Não anexou item 2')
                    # Continuar com o próximo documento mesmo se este falhar
            
            # Calcular percentual de completude
            total_docs = len(documentos_complementares)
            percentual_completude = (documentos_validos / total_docs) * 100
            
            # Resumo de validação
            print(f"\n{'='*60}")
            print(f"📊 RESUMO DOCUMENTOS COMPLEMENTARES: {documentos_validos}/{total_docs} documentos válidos ({percentual_completude:.0f}%)")
            print(f"{'='*60}")
            
            if documentos_validos == len(documentos_complementares):
                print(f"[OK] DOCUMENTOS COMPLEMENTARES: COMPLETOS ({percentual_completude:.0f}%)")
                return {
                    'atendido': True,
                    'percentual_completude': percentual_completude,
                    'documentos_faltantes': [],
                    'documentos_invalidos': []
                }
            else:
                print(f"[ERRO] DOCUMENTOS COMPLEMENTARES: INCOMPLETOS ({percentual_completude:.0f}%)")
                return {
                    'atendido': False,
                    'percentual_completude': percentual_completude,
                    'documentos_faltantes': documentos_faltantes,
                    'documentos_invalidos': []
                }
                
        except Exception as e:
            print(f"[ERRO] Erro na verificação de documentos complementares: {e}")
            return {
                'atendido': False,
                'percentual_completude': 0,
                'documentos_faltantes': ['Erro na validação'],
                'documentos_invalidos': []
            }

    def salvar_dados_para_exportacao(self, numero_processo, resultado_elegibilidade, resultado_decisao):
        """
        Salva dados estruturados para exportação posterior
        """
        try:
            import json
            import os
            from datetime import datetime
            
            # Criar estrutura de dados para exportação
            dados_exportacao = {
                'numero_processo': numero_processo,
                'codigo_processo': getattr(self, 'codigo_processo', None),
                'tipo_analise': 'Naturalização Ordinária',
                'data_analise': datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                'nome': resultado_elegibilidade.get('dados_pessoais', {}).get('nome', 'N/A'),
                'protocolo': resultado_elegibilidade.get('dados_pessoais', {}).get('protocolo', 'N/A'),
                'data_inicial': resultado_elegibilidade.get('data_inicial_processo', 'N/A'),
                'resultado_final': 'DEFERIMENTO' if resultado_elegibilidade.get('elegibilidade_final') == 'deferimento' else 'INDEFERIMENTO',
                'motivos_indeferimento': resultado_elegibilidade.get('requisitos_nao_atendidos', []),
                'requisitos': {
                    'capacidade_civil': resultado_elegibilidade.get('requisito_i_capacidade_civil', {}).get('atendido', False),
                    'residencia_minima': resultado_elegibilidade.get('requisito_ii_residencia_minima', {}).get('atendido', False),
                    'comunicacao_portugues': resultado_elegibilidade.get('requisito_iii_comunicacao_portugues', {}).get('atendido', False),
                    'antecedentes_criminais': resultado_elegibilidade.get('requisito_iv_antecedentes_criminais', {}).get('atendido', False)
                },
                'documentos_complementares': {
                    'percentual_completude': resultado_elegibilidade.get('documentos_complementares', {}).get('percentual_completude', 0),
                    'documentos_faltantes': resultado_elegibilidade.get('documentos_complementares', {}).get('documentos_faltantes', [])
                },
                'despacho': resultado_decisao.get('despacho', 'N/A') if resultado_decisao else 'N/A',
                'resumo': resultado_decisao.get('resumo', 'N/A') if resultado_decisao else 'N/A'
            }
            
            # Criar diretório se não existir
            diretorio_dados = os.path.join(os.getcwd(), 'dados_exportacao_ordinaria')
            os.makedirs(diretorio_dados, exist_ok=True)
            
            # Salvar arquivo JSON
            nome_arquivo = f"ordinaria_{numero_processo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            caminho_arquivo = os.path.join(diretorio_dados, nome_arquivo)
            
            with open(caminho_arquivo, 'w', encoding='utf-8') as f:
                json.dump(dados_exportacao, f, ensure_ascii=False, indent=2)
            
            print(f"[SALVO] Dados salvos: {caminho_arquivo}")
            
            # Salvar também em formato compatível com exportador
            self.salvar_para_exportador_global(dados_exportacao)
            
            return True
            
        except Exception as e:
            print(f"[ERRO] Erro ao salvar dados para exportação: {e}")
            return False
    
    def salvar_para_exportador_global(self, dados_exportacao):
        """
        Salva dados no formato do exportador global para consolidação
        """
        try:
            import json
            import os
            from datetime import datetime
            
            # Arquivo global de resultados ordinários
            arquivo_global = os.path.join(os.getcwd(), 'resultados_ordinaria_global.json')
            
            # Carregar dados existentes ou criar novo
            if os.path.exists(arquivo_global):
                with open(arquivo_global, 'r', encoding='utf-8') as f:
                    dados_existentes = json.load(f)
            else:
                dados_existentes = []
            
            # Adicionar novo resultado
            dados_existentes.append(dados_exportacao)
            
            # Salvar arquivo atualizado
            with open(arquivo_global, 'w', encoding='utf-8') as f:
                json.dump(dados_existentes, f, ensure_ascii=False, indent=2)
            
            print(f"[DADOS] Resultado adicionado ao arquivo global: {arquivo_global}")
            
        except Exception as e:
            print(f"[ERRO] Erro ao salvar no exportador global: {e}")

    def obter_diretorio_downloads(self):
        """
        Obtém o diretório de downloads padrão
        """
        import os
        import platform
        
        sistema = platform.system()
        if sistema == "Windows":
            return os.path.join(os.path.expanduser("~"), "Downloads")
        elif sistema == "Darwin":  # macOS
            return os.path.join(os.path.expanduser("~"), "Downloads")
        else:  # Linux
            return os.path.join(os.path.expanduser("~"), "Downloads")

    def close(self):
        self.driver.quit()

    def fechar(self):
        """Fecha o navegador"""
        if self.driver:
            self.driver.quit()
            print("[FECHADO] Navegador fechado com segurança")

    def baixar_todos_documentos_e_ocr(self, modo_inspecao=False, usar_ocr_generico=True):
        """
        Baixa todos os documentos e executa OCR
        [FECHADO] CONFORME LGPD: NUNCA baixa portaria de naturalização - apenas banco oficial
        """
        print("DEBUG: [EXEC] Iniciando download de todos os documentos...")
        
        # [FECHADO] CORREÇÃO LGPD: NUNCA baixar portaria de naturalização
        documentos_para_baixar = [doc for doc in self.documentos_para_baixar 
                                 if doc != 'Portaria de concessão da naturalização provisória']
        
        print(f"DEBUG: [INFO] Documentos para baixar: {len(documentos_para_baixar)}")
        print("DEBUG: [FECHADO] LGPD: Portaria de naturalização NUNCA será baixada - apenas banco oficial")
        
        resultados = {}
        for nome_documento in documentos_para_baixar:
            try:
                print(f"DEBUG: Tentando baixar {nome_documento}...")
                
                # Verificar se já foi processado (cache)
                if nome_documento in self.textos_ja_extraidos:
                    print(f"DEBUG: [OK] {nome_documento}: {len(self.textos_ja_extraidos[nome_documento])} caracteres cacheados")
                    resultados[nome_documento] = {
                        'sucesso': True,
                        'texto_extraido': self.textos_ja_extraidos[nome_documento],
                        'arquivo': 'cache',
                        'tempo_ocr': 0.0
                    }
                    continue
                
                # Baixar documento com configurações específicas
                if 'Comprovante de tempo de residência' in nome_documento:
                    print(f"DEBUG: [BUSCA] {nome_documento} - usando apenas primeira página")
                    texto_extraido = self.baixar_documento_e_ocr(nome_documento, max_paginas=1)
                else:
                    texto_extraido = self.baixar_documento_e_ocr(nome_documento)
                
                if texto_extraido:
                    # [FECHADO] MASCARAR DADOS SENSÍVEIS CONFORME LGPD
                    try:
                        from data_protection import limpar_texto_ocr
                        texto_protegido = limpar_texto_ocr(texto_extraido)
                        print(f"DEBUG: [FECHADO] Dados sensíveis mascarados em {nome_documento}")
                    except ImportError:
                        # Fallback para mascaramento básico
                        texto_protegido = texto_extraido
                        # Mascarar CPF e RG basicamente
                        import re as regex_module
                        texto_protegido = regex_module.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF MASCARADO]', texto_protegido)
                        texto_protegido = regex_module.sub(r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b', '[RG MASCARADO]', texto_protegido)
                        print(f"DEBUG: [FECHADO] Mascaramento básico aplicado em {nome_documento}")
                    
                    # Salvar no cache
                    self.textos_ja_extraidos[nome_documento] = texto_protegido
                    
                    resultados[nome_documento] = {
                        'sucesso': True,
                        'texto_extraido': texto_protegido,
                        'arquivo': 'processado',
                        'tempo_ocr': 0.0  # Será calculado se necessário
                    }
                    
                    print(f"DEBUG: [OK] {nome_documento}: {len(texto_protegido)} caracteres extraídos e protegidos")
                else:
                    resultados[nome_documento] = {
                        'sucesso': False,
                        'erro': 'Falha na extração',
                        'arquivo': None,
                        'tempo_ocr': 0.0
                    }
                    print(f"DEBUG: [ERRO] Falha ao extrair texto de {nome_documento}")
                    
            except Exception as e:
                print(f"DEBUG: [ERRO] Erro ao processar {nome_documento}: {e}")
                resultados[nome_documento] = {
                    'sucesso': False,
                    'erro': str(e),
                    'arquivo': None,
                    'tempo_ocr': 0.0
                }
        
        # [FECHADO] CORREÇÃO LGPD: Log seguro sem dados sensíveis
        total_sucessos = sum(1 for r in resultados.values() if r.get('sucesso'))
        total_erros = len(resultados) - total_sucessos
        
        print(f"DEBUG: [FECHADO] Total de documentos processados: {len(resultados)}")
        print(f"DEBUG: [FECHADO] Sucessos: {total_sucessos}, Erros: {total_erros}")
        print("DEBUG: [FECHADO] LGPD: Portaria de naturalização NUNCA foi baixada - apenas banco oficial")
        
        return resultados

    def baixar_documento_e_ocr(self, nome_documento, max_paginas=None):
        """
        Baixa um documento específico e executa OCR
        [FECHADO] CONFORME LGPD: NUNCA baixa portaria de naturalização
        
        Args:
            nome_documento: Nome do documento a ser baixado
            max_paginas: Número máximo de páginas a processar (None = todas)
        """
        # [FECHADO] LGPD: Verificação de segurança - NUNCA processar portaria
        if 'portaria' in nome_documento.lower() and 'naturalização' in nome_documento.lower():
            print(f"[FECHADO] LGPD: BLOQUEADO download de {nome_documento} - violação da LGPD")
            return None
        
        try:
            print(f"DEBUG: [FECHADO] Baixando documento permitido: {nome_documento}")
            
            # Buscar o documento na página
            xpath = f"//span[contains(text(), '{nome_documento}')]"
            span = self.wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
            
            if not span:
                print(f"DEBUG: [ERRO] Documento {nome_documento} não encontrado")
                return None
            
            print(f"DEBUG: [OK] Span '{nome_documento}' encontrado!")
            
            # Clicar para baixar
            try:
                span.click()
                print(f"DEBUG: [OK] Clique realizado no span para download de {nome_documento}!")
            except Exception as e:
                print(f"DEBUG: [AVISO] Erro no clique direto: {e}")
                # Tentar clicar no elemento pai
                try:
                    parent = span.find_element(By.XPATH, "..")
                    link = parent.find_element(By.TAG_NAME, "a")
                    link.click()
                    print(f"DEBUG: [OK] Clique realizado no link de download próximo ao span!")
                except Exception as e2:
                    print(f"DEBUG: [ERRO] Erro ao clicar no link: {e2}")
                    return None
            
            # Monitorar downloads
            download_path = os.path.join(os.path.expanduser('~'), 'Downloads')
            arquivos_antes = set(os.listdir(download_path))
            print(f'DEBUG: Aguardando novo arquivo PDF para {nome_documento}...')
            
            arquivo_baixado = None
            for _ in range(15):  # 15 segundos timeout
                time.sleep(1)
                arquivos_depois = set(os.listdir(download_path))
                novos = arquivos_depois - arquivos_antes
                extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                novos_arquivos = [f for f in novos if f.lower().endswith(extensoes_validas)]
                if novos_arquivos:
                    arquivo_baixado = os.path.join(download_path, novos_arquivos[0])
                    print(f'DEBUG: [OK] Novo PDF detectado: {arquivo_baixado}')
                    break
            
            if not arquivo_baixado:
                print(f'DEBUG: [ERRO] Timeout - nenhum PDF baixado para {nome_documento}')
                # [DEBUG] CORREÇÃO: Registrar falha de download
                self.logs_download['falhas'].append(nome_documento)
                return None
            
            # Copiar para uploads
            uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            nome_base = os.path.basename(arquivo_baixado)
            nome_unico = f"{self.numero_processo_limpo}_{nome_documento.replace(' ', '_')}_{uuid.uuid4().hex[:6]}_{nome_base}"
            pdf_dest = os.path.join(uploads_dir, nome_unico)
            
            import shutil
            shutil.copy2(arquivo_baixado, pdf_dest)
            print(f'DEBUG: [OK] PDF copiado: {pdf_dest}')
            
            # [DEBUG] CORREÇÃO CRÍTICA: Registrar sucesso de download AQUI (quando PDF é copiado)
            # Independente se OCR vai funcionar ou não
            self.logs_download['sucessos'].append(nome_documento)
            print(f'DEBUG: [OK] {nome_documento} registrado em sucessos (PDF baixado)')
            
            # Executar OCR
            try:
                from app import extrair_campos_ocr_mistral
                
                print(f"DEBUG: [EXEC] Iniciando OCR para {nome_documento}...")
                start_time = time.time()
                
                # [DEBUG] CORREÇÃO: Usar max_paginas se especificado
                if max_paginas is not None:
                    print(f"DEBUG: [BUSCA] {nome_documento} - usando apenas primeira página (max_paginas={max_paginas})")
                    campos_ocr = extrair_campos_ocr_mistral(
                        pdf_dest, 
                        modo_texto_bruto=True,
                        max_retries=1,
                        max_paginas=max_paginas  # [DEBUG] NOVO: Passar max_paginas
                    )
                else:
                    campos_ocr = extrair_campos_ocr_mistral(
                        pdf_dest, 
                        modo_texto_bruto=True,
                        max_retries=1
                    )
                
                tempo_ocr = time.time() - start_time
                print(f"DEBUG: ⚡ OCR concluído em {tempo_ocr:.1f}s")
                
                if campos_ocr and 'texto_bruto' in campos_ocr:
                    texto_extraido = campos_ocr['texto_bruto']
                    
                    # [FECHADO] MASCARAR DADOS SENSÍVEIS CONFORME LGPD
                    try:
                        from data_protection import limpar_texto_ocr
                        texto_protegido = limpar_texto_ocr(texto_extraido)
                        print(f"DEBUG: [FECHADO] Dados sensíveis mascarados em {nome_documento}")
                    except ImportError:
                        # Mascaramento básico obrigatório
                        texto_protegido = self._aplicar_mascaramento_basico_lgpd(texto_extraido)
                        print(f"DEBUG: [FECHADO] Mascaramento básico LGPD aplicado em {nome_documento}")
                    
                    print(f"DEBUG: [OK] OCR bem-sucedido - {len(texto_protegido)} caracteres extraídos")
                    
                    # [DEBUG] CORREÇÃO: Armazenar no cache para uso posterior
                    self.textos_ja_extraidos[nome_documento] = texto_protegido
                    print(f"DEBUG: [SALVO] {nome_documento} armazenado no cache: {len(texto_protegido)} caracteres")
                    
                    # [DEBUG] NOTA: Sucesso já foi registrado quando PDF foi copiado (linha 719)
                    
                    # [FECHADO] LGPD: Log seguro SEM dados sensíveis
                    print(f"=== DOCUMENTO PROCESSADO (LGPD) ===")
                    print(f"Documento: {nome_documento}")
                    print(f"Status: [OK] PROCESSADO COM SEGURANÇA")
                    print(f"Caracteres: {len(texto_protegido)}")
                    print(f"[FECHADO] Dados sensíveis: MASCARADOS")
                    print(f"=" * 50)
                    
                    return texto_protegido
                else:
                    print(f"DEBUG: [ERRO] OCR retornou resultado vazio para {nome_documento}")
                    # [DEBUG] CORREÇÃO: Para viagem/comprovante residência, OCR vazio NÃO é falha se PDF foi baixado
                    # Não adicionar a 'falhas' - manter apenas em 'sucessos' pois PDF foi copiado
                    if nome_documento not in ['Documento de viagem internacional', 'Comprovante de tempo de residência']:
                        self.logs_download['falhas'].append(nome_documento)
                    print(f"DEBUG: [AVISO] {nome_documento}: OCR vazio mas PDF foi baixado {'(não penaliza provisória)' if nome_documento in ['Documento de viagem internacional', 'Comprovante de tempo de residência'] else '(registrado como falha)'}")
                    return None
                    
            except Exception as e:
                print(f"DEBUG: [ERRO] Erro no OCR de {nome_documento}: {e}")
                # [DEBUG] CORREÇÃO: Registrar erro de OCR
                self.logs_download['erros'].append(f"{nome_documento}: {str(e)}")
                return None
                
        except Exception as e:
            print(f"DEBUG: [ERRO] Erro ao baixar {nome_documento}: {e}")
            # [DEBUG] CORREÇÃO: Registrar erro de download
            self.logs_download['erros'].append(f"{nome_documento}: {str(e)}")
            return None
    
    def _aplicar_mascaramento_basico_lgpd(self, texto):
        """
        Aplica mascaramento básico conforme LGPD
        """
        if not texto:
            return texto
        
        import re as regex_module
        texto_protegido = texto
        
        # Mascarar CPF (múltiplos formatos)
        texto_protegido = regex_module.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF MASCARADO]', texto_protegido)
        texto_protegido = regex_module.sub(r'\b\d{11}\b', '[CPF MASCARADO]', texto_protegido)
        texto_protegido = regex_module.sub(r'CPF:\s*\d{3}\.\d{3}\.\d{3}-\d{2}', 'CPF: [MASCARADO]', texto_protegido)
        
        # Mascarar RG
        texto_protegido = regex_module.sub(r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b', '[RG MASCARADO]', texto_protegido)
        texto_protegido = regex_module.sub(r'RG:\s*\d{2}\.\d{3}\.\d{3}-[0-9X]', 'RG: [MASCARADO]', texto_protegido)
        
        # Mascarar endereços completos
        texto_protegido = regex_module.sub(r'ENDEREÇO:\s*[^,\n]+', 'ENDEREÇO: [MASCARADO]', texto_protegido)
        texto_protegido = regex_module.sub(r'RUA\s+[^,\n]+\d+', 'RUA [MASCARADO]', texto_protegido)
        
        # Mascarar CEP
        texto_protegido = regex_module.sub(r'\b\d{5}-\d{3}\b', '[CEP MASCARADO]', texto_protegido)
        
        # Mascarar telefones
        texto_protegido = regex_module.sub(r'\(\d{2}\)\s*\d{4,5}-\d{4}', '[TELEFONE MASCARADO]', texto_protegido)
        
        return texto_protegido

    def baixar_documento_rnm(self, modo_inspecao=False):
        print('=== INÍCIO baixar_documento_rnm ===')
        print('Procurando documento RNM...')
        try:
            numero_processo_limpo = self.numero_processo_limpo
            print(f'DEBUG: Número do processo usado para o link do form-app: {numero_processo_limpo}')
        except AttributeError:
            print('ERRO: número do processo limpo não definido! Extraia antes de chamar baixar_documento_rnm.')
            return None

        # Busca o span pelo texto e tenta clicar para baixar
        try:
            span = self.wait.until(
                EC.visibility_of_element_located(
                    (By.XPATH, "//span[contains(text(), 'Carteira de Registro Nacional Migratório')]")
                )
            )
            print("DEBUG: Span 'Carteira de Registro Nacional Migratório' encontrado!")
            try:
                span.click()
                print("DEBUG: Clique realizado no span para download!")
            except Exception as e:
                print("DEBUG: Não foi possível clicar diretamente no span:", e)
                # Tenta encontrar um link ou botão próximo ao span
                parent = span.find_element(By.XPATH, "..")
                link = parent.find_element(By.TAG_NAME, "a")
                link.click()
                print("DEBUG: Clique realizado no link de download próximo ao span!")
        except Exception as e:
            print("ERRO ao tentar baixar o documento RNM:", e)
            return None

        # Monitorar a pasta de downloads
        try:
            download_path = os.path.join(os.path.expanduser('~'), 'Downloads')
            os.makedirs(download_path, exist_ok=True)
            arquivos_antes = set(os.listdir(download_path))
            print('Aguardando novo arquivo PDF ser baixado...')
            for _ in range(60):
                time.sleep(1)
                arquivos_depois = set(os.listdir(download_path))
                novos = arquivos_depois - arquivos_antes
                extensoes_validas = ('.pdf', '.jpg', '.jpeg', '.png')
                novos_arquivos = [f for f in novos if f.lower().endswith(extensoes_validas)]
                if novos_arquivos:
                    arquivo_baixado = os.path.join(download_path, novos_arquivos[0])
                    print(f'Novo PDF detectado: {arquivo_baixado}')
                    print('=== FIM download automático RNM ===')
                    # Copiar para a pasta uploads do projeto
                    uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
                    os.makedirs(uploads_dir, exist_ok=True)
                    nome_base = os.path.basename(arquivo_baixado)
                    nome_unico = f"{numero_processo_limpo}_{uuid.uuid4().hex[:6]}_{nome_base}"
                    pdf_dest = os.path.join(uploads_dir, nome_unico)
                    import shutil
                    shutil.copy2(arquivo_baixado, pdf_dest)
                    print(f'PDF copiado para uploads: {pdf_dest}')
                    return pdf_dest
            print('Nenhum novo PDF detectado após clique automático.')
        except Exception as e:
            print('ERRO ao monitorar a pasta de downloads:', e)
        return None

    def extrair_numero_processo(self):
        time.sleep(2)  # Garante que a tela carregou
        numero_processo = None

        # Se já temos o número do processo limpo armazenado, usar ele
        if hasattr(self, 'numero_processo_limpo') and self.numero_processo_limpo:
            print(f"DEBUG: Usando número do processo já armazenado: {self.numero_processo_limpo}")
            return self.numero_processo_limpo

        # 1. Tenta extrair da div#celula0
        try:
            div = self.driver.find_element(By.ID, "celula0")
            texto_div = div.text.strip()
            print(f"DEBUG: Texto encontrado em div#celula0 - conteúdo protegido")
            if texto_div:
                numero_processo = texto_div
        except Exception as e:
            print("DEBUG: Não encontrou div#celula0:", e)

        # 2. Se não achou, tenta pelo topo
        if not numero_processo:
            try:
                span = self.driver.find_element(By.XPATH, "//div[contains(@class, 'modulo_topo')]//span[contains(text(), 'Processo:')]")
                texto_span = span.text
                print(f"DEBUG: Texto do topo encontrado: '{texto_span}'")
                match = re.search(r'Processo:\s*([\d\. ]+)', texto_span)
                if match:
                    numero_processo = match.group(1)
            except Exception as e:
                print("DEBUG: Não encontrou span do topo:", e)

        # 3. Limpa o número e salva
        if numero_processo:
            import re as regex_module
            numero_processo_limpo = regex_module.sub(r'\D', '', numero_processo)
            self.numero_processo_limpo = numero_processo_limpo
            print(f"DEBUG: Número do processo extraído: {numero_processo} | Limpo: {numero_processo_limpo}")
            return numero_processo_limpo
        else:
            print("ERRO: Não foi possível extrair o número do processo!")
            # Se não conseguir extrair, mas temos o código original, usar ele
            print("DEBUG: Tentando usar código original do processo como fallback...")
            return None

    def extrair_dados_interessado(self, numero_processo):
        """
        Acessa o processo pelo número, entra na etapa 'Preencher dados do interessado' e extrai país, data de nascimento, estado e sexo.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        import unicodedata
        
        # Navegar diretamente para o processo usando navegação direta
        print(f"DEBUG: Navegando diretamente para processo {numero_processo}...")
        self.aplicar_filtros(numero_processo)
        try:
            self.wait.until(EC.visibility_of_element_located((By.XPATH, "//div[contains(@class,'titulo-tarefa')]")))
            titulos = self.driver.find_elements(By.XPATH, "//div[contains(@class,'titulo-tarefa')]")
            print('DEBUG: Etapas encontradas:')
            for t in titulos:
                print('-', repr(t.text))
            def normalizar(texto):
                texto = texto.replace('\xa0', ' ').replace('\u00a0', ' ')
                texto = ' '.join(texto.split())
                texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
                return texto.strip().lower()
            alvo = 'preencher dados do interessado'
            alvo_norm = normalizar(alvo)
            etapa_correta = None
            for t in titulos:
                texto_norm = normalizar(t.text)
                print(f"DEBUG: Texto original: '{t.text}' | Normalizado: '{texto_norm}'")
                if texto_norm == alvo_norm:
                    etapa_correta = t
                    break
            if etapa_correta:
                texto_norm_clicado = normalizar(etapa_correta.text)
                assert texto_norm_clicado == alvo_norm, f"Tentativa de clicar em etapa errada: '{etapa_correta.text}' (normalizado: '{texto_norm_clicado}')"
                print(f"DEBUG: Vai clicar em etapa correta: '{etapa_correta.text}' (normalizado: '{texto_norm_clicado}')")
                print(f"DEBUG: HTML do elemento clicado: {etapa_correta.get_attribute('outerHTML')}")
                self.driver.execute_script("arguments[0].click();", etapa_correta)
                time.sleep(2)
            else:
                raise Exception("Etapa 'Preencher Dados do Interessado' não encontrada. Veja os textos acima para debug.")
            btn_acessar = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class,'botao-flat') and contains(@class,'azul') and contains(.,'ACESSAR')]")))
            btn_acessar.click()
            time.sleep(2)
            handles_antes = self.driver.window_handles[:-1]
            self.wait.until(lambda d: len(d.window_handles) > len(handles_antes))
            self.driver.switch_to.window(self.driver.window_handles[-1])
            time.sleep(2)
            pais = self.driver.find_element(By.ID, 'ORD_NATU').get_attribute('value')
            data_nasc = self.driver.find_element(By.ID, 'ORD_NAS').get_attribute('value')
            estado = self.driver.find_element(By.ID, 'ORD_UF').get_attribute('value')
            sexo = ''
            try:
                input_masc = self.driver.find_element(By.ID, 'ORD_SEX_0')
                input_fem = self.driver.find_element(By.ID, 'ORD_SEX_1')
                if input_masc.get_attribute('aria-checked') == 'true':
                    sexo = 'Masculino'
                elif input_fem.get_attribute('aria-checked') == 'true':
                    sexo = 'Feminino'
            except Exception:
                sexo = ''
            aba_atual = self.driver.current_window_handle
            self.driver.close()
            self.driver.switch_to.window(self.driver.window_handles[0])
            return {
                'pais': pais,
                'data_nasc': data_nasc,
                'estado': estado,
                'sexo': sexo
            }
        except Exception as e:
            raise Exception(f'Erro ao extrair dados do interessado: {e}')

    def extrair_data_inicial_processo(self):
        """Extrai a data inicial do processo antes de efetuar distribuição (novo formato)"""
        try:
            print("DEBUG: 🕒 Extraindo data inicial do processo...")
            
            # Novo formato: buscar por span.subtitle
            try:
                subtitle_element = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//span[@class='subtitle']"))
                )
                
                texto_subtitle = subtitle_element.text.strip()
                print(f"DEBUG: Texto encontrado no subtitle: {texto_subtitle}")
                
                # Extrair data usando regex para o novo formato
                # Exemplo: "Em andamento - aberto por Cidadão 10 de Jan de 2025 às 14:55"
                import re
                match = re.search(r'aberto por .+ (\d{1,2} de \w+ de \d{4})', texto_subtitle)
                if match:
                    data_inicial = match.group(1)
                    print(f"DEBUG: [OK] Data inicial extraída: {data_inicial}")
                    self.data_inicial_processo = data_inicial
                    return data_inicial
                else:
                    print("DEBUG: [ERRO] Não foi possível extrair data do texto subtitle")
                    
            except Exception as e:
                print(f"DEBUG: [AVISO] Erro ao extrair data do subtitle: {e}")
                # Fallback para o formato antigo
                try:
                    elemento_data = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".info.data .data"))
                    )
                    
                    data_inicial = elemento_data.text.strip()
                    if data_inicial:
                        print(f"DEBUG: [OK] Data inicial extraída (formato antigo): {data_inicial}")
                        self.data_inicial_processo = data_inicial
                        return data_inicial
                except Exception as e2:
                    print(f"DEBUG: [ERRO] Erro no fallback para formato antigo: {e2}")
                    return None
            
            print("DEBUG: [AVISO] Data inicial não encontrada")
            return None
                
        except Exception as e:
            print(f"DEBUG: [ERRO] Erro ao extrair data inicial: {e}")
            return None


    def verificar_capacidade_civil_antes_download(self, dados_pessoais, data_inicial):
        """
        Verifica capacidade civil ANTES de baixar documentos
        Primeira etapa obrigatória do fluxo ordinário
        """
        try:
            print("\n" + "="*80)
            print("[INFO] REQUISITO I: CAPACIDADE CIVIL")
            print("Art. 65, inciso I da Lei nº 13.445/2017")
            print("="*80)
            
            if not data_inicial or not dados_pessoais.get('data_nascimento'):
                print("[ERRO] ERRO: Data inicial ou data de nascimento não disponível")
                return {
                    'atendido': False,
                    'motivo': 'Dados insuficientes para verificar capacidade civil',
                    'pode_continuar': False
                }
            
            from datetime import datetime
            
            # Converter datas
            try:
                data_nasc = datetime.strptime(dados_pessoais['data_nascimento'], '%d/%m/%Y')
                
                # Converter data inicial para formato padrão se necessário
                data_inicial_convertida = normalizar_data_para_ddmmaaaa(data_inicial)
                data_inicio = datetime.strptime(data_inicial_convertida, '%d/%m/%Y')
                
            except ValueError as e:
                print(f"[ERRO] ERRO: Formato de data inválido: {e}")
                print(f"DEBUG: Data inicial original: '{data_inicial}'")
                print(f"DEBUG: Data nascimento: '{dados_pessoais['data_nascimento']}'")
                return {
                    'atendido': False,
                    'motivo': 'Formato de data inválido',
                    'pode_continuar': False
                }
            
            # Calcular idade na data inicial do processo
            idade_anos = (data_inicio - data_nasc).days / 365.25
            idade_completa = int(idade_anos)
            
            print(f"[DATA] Data de nascimento: {dados_pessoais['data_nascimento']}")
            print(f"[DATA] Data inicial do processo: {data_inicial}")
            print(f"🎂 Idade na data inicial: {idade_completa} anos")
            
            if idade_completa >= 18:
                print("✅ CAPACIDADE CIVIL: ATENDIDA")
                print(f"✅ Possui {idade_completa} anos (≥ 18 anos)")
                print("✅ Pode continuar com o processamento")
                return {
                    'atendido': True,
                    'idade': idade_completa,
                    'pode_continuar': True
                }
            else:
                print("❌ CAPACIDADE CIVIL: NÃO ATENDIDA")
                print(f"❌ Possui apenas {idade_completa} anos (< 18 anos)")
                print("🚫 INDEFERIMENTO AUTOMÁTICO - Art. 65, inciso I")
                print("📋 Continuando análise para identificar TODOS os motivos de indeferimento")
                print("🚫 Fundamento: Art. 65, inciso I da Lei nº 13.445/2017")
                return {
                    'atendido': False,
                    'motivo': 'Não possui capacidade civil (menos de 18 anos)',
                    'idade': idade_completa,
                    'fundamento_legal': 'Art. 65, inciso I da Lei nº 13.445/2017',
                    'pode_continuar': True,  # MODIFICADO: Continuar análise
                    'indeferimento_automatico': True
                }
                
        except Exception as e:
            print(f"[ERRO] ERRO na verificação de capacidade civil: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False
            }

    def listar_todos_motivos_indeferimento_art65(self):
        """
        Lista todos os motivos de indeferimento conforme Art. 65 da Lei nº 13.445/2017
        """
        print("\n" + "="*100)
        print("📋 TODOS OS MOTIVOS DE INDEFERIMENTO - ART. 65 DA LEI Nº 13.445/2017")
        print("="*100)
        
        motivos_art65 = {
            "I": {
                "descricao": "Capacidade Civil",
                "requisito": "Ser maior de 18 (dezoito) anos",
                "motivo_indeferimento": "Não possui capacidade civil (menos de 18 anos)",
                "fundamento": "Art. 65, inciso I da Lei nº 13.445/2017"
            },
            "II": {
                "descricao": "Residência no Brasil",
                "requisito": "Ter residência no Brasil por prazo não inferior a 4 (quatro) anos",
                "motivo_indeferimento": "Não possui residência mínima de 4 anos no Brasil",
                "fundamento": "Art. 65, inciso II da Lei nº 13.445/2017"
            },
            "III": {
                "descricao": "Comunicação em Português",
                "requisito": "Ser capaz de comunicar-se em língua portuguesa",
                "motivo_indeferimento": "Não consegue se comunicar em língua portuguesa",
                "fundamento": "Art. 65, inciso III da Lei nº 13.445/2017"
            },
            "IV": {
                "descricao": "Ausência de Condenação Criminal",
                "requisito": "Não ter sido condenado por crime",
                "motivo_indeferimento": "Possui condenação criminal",
                "fundamento": "Art. 65, inciso IV da Lei nº 13.445/2017",
                "motivos_especificos": [
                    "Antecedentes criminais do Brasil não anexado",
                    "Antecedentes criminais do Brasil inválido",
                    "Antecedentes criminais do país de origem não anexado",
                    "Antecedentes criminais do país de origem inválido"
                ]
            }
        }
        
        print("\n📖 REQUISITOS PARA NATURALIZAÇÃO ORDINÁRIA:")
        print("   (Art. 65 da Lei nº 13.445/2017 - Lei de Migração)")
        
        for inciso, dados in motivos_art65.items():
            print(f"\n🔸 INCISO {inciso}: {dados['descricao']}")
            print(f"   📋 Requisito: {dados['requisito']}")
            print(f"   ❌ Motivo de indeferimento: {dados['motivo_indeferimento']}")
            print(f"   ⚖️ Fundamento: {dados['fundamento']}")
            
            # Exibir motivos específicos para o inciso IV
            if inciso == "IV" and 'motivos_especificos' in dados:
                print(f"   📋 Motivos específicos:")
                for motivo in dados['motivos_especificos']:
                    print(f"      • {motivo}")
        
        print(f"\n📊 Total de requisitos: {len(motivos_art65)}")
        print("="*100)
        
        return motivos_art65

    def _gerar_resultado_indeferimento_automatico(self, numero_processo, dados_pessoais, resultado_verificacao, fundamento_legal, tipo_requisito):
        """
        Gera resultado de indeferimento automático formatado
        """
        try:
            from analise_decisoes_ordinaria import AnaliseDecisoesOrdinaria
            gerador_decisao = AnaliseDecisoesOrdinaria()
            
            resultado_elegibilidade_falso = {
                f'requisito_{tipo_requisito.replace(" ", "_")}': resultado_verificacao,
                'elegibilidade_final': 'indeferimento_automatico',
                'requisitos_nao_atendidos': [fundamento_legal],
                'dados_pessoais': dados_pessoais,
                'data_inicial_processo': self.data_inicial_processo
            }
            
            resultado_decisao = gerador_decisao.gerar_decisao_automatica(resultado_elegibilidade_falso)
            resumo_executivo = gerador_decisao.gerar_resumo_executivo(resultado_elegibilidade_falso, resultado_decisao)
            
            return {
                'numero_processo': numero_processo,
                'codigo_processo': getattr(self, 'codigo_processo', None),
                'indeferimento_automatico': True,
                'motivo': resultado_verificacao['motivo'],
                'fundamento_legal': fundamento_legal,
                'dados_pessoais': dados_pessoais,
                'data_inicial_processo': self.data_inicial_processo,
                'analise_elegibilidade': resultado_elegibilidade_falso,
                'decisao_automatica': resultado_decisao,
                'resumo_executivo': resumo_executivo,
                'status': f'Indeferimento automático - {tipo_requisito}'
            }
        except Exception as e:
            print(f"[ERRO] Erro ao gerar resultado de indeferimento: {e}")
            return {
                'numero_processo': numero_processo,
                'erro': f'Erro ao gerar indeferimento: {e}',
                'status': 'Erro'
            }

    def verificar_residencia_minima_com_validacao_ocr(self):
        """
        REQUISITO II – Residência mínima com validação OCR individual
        """
        try:
            print('Passo 1 – Verificar se há redução de prazo')
            
            tem_reducao = False
            try:
                # Procurar pelo elemento que indica redução de prazo marcada como "Sim"
                elemento_reducao = self.driver.find_element(
                    By.XPATH, 
                    "//label[@for='HIP_CON_0' and contains(@aria-checked, 'true')]"
                )
                if elemento_reducao and "Sim" in elemento_reducao.text:
                    tem_reducao = True
                    print("[OK] Redução de prazo: SIM")
                    print("[INFO] Validando documento: Comprovante de redução de prazo")
                    
                    # BAIXAR E VALIDAR OCR DO COMPROVANTE DE REDUÇÃO
                    doc_reducao_valido = self.baixar_e_validar_documento_individual('Comprovante de redução de prazo')
                    
                    if not doc_reducao_valido:
                        print("[ERRO] Comprovante de redução de prazo: INVÁLIDO ou não anexado")
                        # CONTINUAR processamento mesmo se documento falhar
                        tem_reducao = False  # Tratar como se não tivesse redução
                        prazo_requerido = 4
                        print("[INFO] Sem comprovante válido: exigir 4 anos de residência")
                    else:
                        print("[OK] Comprovante de redução de prazo: VÁLIDO")
                        prazo_requerido = 1
                        print("[INFO] Exigir 1 ano de residência indeterminada")
                else:
                    tem_reducao = False
                    prazo_requerido = 4
                    print("[ERRO] Redução de prazo: NÃO")
                    print("[INFO] Exigir 4 anos de residência indeterminada ou permanente")
            except Exception as e:
                print(f"[AVISO] Erro ao verificar redução de prazo: {e}")
                tem_reducao = False
                prazo_requerido = 4
                print("[ERRO] Redução de prazo: NÃO (padrão)")
                print("[INFO] Exigir 4 anos de residência indeterminada ou permanente")
            
            print('\nPasso 2 – Validar residência')
            print('Pode ser verificado por:')
            print('- Campo CHPF_PARECER (Parecer) - PRIORIDADE')
            print('- Campo RES_DAT (Residência indeterminada) - FALLBACK')
            
            data_residencia = None
            tempo_residencia_anos = 0
            
            # ========== PRIORIDADE 1: PARECER DA PF ==========
            print("[INFO] Passo 1 – Verificar parecer da PF (PRIORIDADE)")
            try:
                elemento_parecer = self.driver.find_element(By.ID, "CHPF_PARECER")
                parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
                
                if parecer_texto:
                    print("[INFO] Analisando campo CHPF_PARECER...")
                    print(f"[DEBUG] Texto do parecer (primeiros 200 chars): {parecer_texto[:200]}...")
                    
                    # Buscar indicações de tempo no parecer - padrões mais específicos para evitar falsos positivos
                    import re
                    
                    # Padrões de busca (do mais específico ao mais geral) para capturar residência
                    # PRIORIDADE: Texto explícito de anos sobre cálculo de data
                    # Removidos padrões muito genéricos para evitar falsos positivos
                    padroes_tempo = [
                        # Padrão 1: Anos explícitos com meses (mais específico)
                        r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)\)\s+anos?\s+e\s+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte|trinta)\)\s+meses?\s+de\s+residência\s+por\s+(?:tempo|prazo)\s+indeterminado',
                        # Padrão 2: Anos explícitos sem meses
                        r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)\)\s+anos?\s+de\s+residência\s+por\s+(?:tempo|prazo)\s+indeterminado',
                        # Padrão 2.1: Anos explícitos sem "por prazo indeterminado"
                        r'possuindo[,\s]+portanto[,\s]+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)\)\s+anos?\s+de\s+residência\.?\s*$',
                        # Padrão 2.2: Anos explícitos sem "portanto" (mais flexível)
                        r'possuindo[,\s]+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)\)\s+anos?\s+de\s+residência\.?\s*$',
                        # Padrão 2.3: Anos explícitos com "portanto," (vírgula) - sem $ no final
                        r'portanto[,\s]+(\d+)\s+\((?:um|dois|três|quatro|cinco|seis|sete|oito|nove|dez|onze|doze|treze|catorze|quinze|dezesseis|dezessete|dezoito|dezenove|vinte)\)\s+anos?\s+de\s+residência',
                        # Padrão 3: Totalizando anos com meses
                        r'totalizando\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+anos?\s+e\s+(\d+)\s+\([a-z]+\)\s+meses?\s*\.?\s*$',
                        # Padrão 4: Totalizando apenas anos
                        r'totalizando\s+(\d+)\s+\([a-zúéáóíõç]+\)\s+anos?\s*\.?\s*$',
                        # Padrão 5: Possui X anos de residência
                        r'possui\s+(\d+)\s*anos?\s+de\s+residência',
                        r'possui\s+(\d+)\s*anos?\s+.*residência',
                        r'(\d+)\s*anos?\s+de\s+residência',
                        r'residência.*?(\d+)\s*anos?',
                        r'(\d+)\s*anos?\s+.*indeterminad',
                        # Padrão 6: Data de residência (menor prioridade)
                        r'residência\s+(?:no\s+brasil\s+)?por\s+prazo\s+indeterminado\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
                        r'possui\s+residência\s+no\s+brasil\s+por\s+prazo\s+indeterminado\s+desde\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})',
                        # Padrão 7: Diligência PF - "totalizando X anos e Y meses como residente por prazo indeterminado"
                        r'totalizando\s+(\d+)\s+anos?\s+e\s+(\d+)\s+meses?\s+como\s+residente\s+por\s+prazo\s+indeterminado',
                        # Padrão 8: Diligência PF - "se registrou em data como permanente, totalizando X anos"
                        r'se\s+registrou\s+em\s+(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\s+como\s+permanente[,\s]+totalizando\s+(\d+)\s+anos?\s+e\s+(\d+)\s+meses?\s+como\s+residente',
                        # Padrão 9: Último recurso (REMOVIDO para evitar falsos positivos)
                        # r'(\d+)\s*anos?'
                    ]
                    
                    tempo_encontrado = False
                    for i, padrao in enumerate(padroes_tempo, 1):
                        print(f"[DEBUG] Testando padrão {i}: {padrao[:60]}...")
                        anos_match = re.search(padrao, parecer_texto.lower())
                        if anos_match:
                            # Verificar se é padrão com anos e meses (padrões 1 e 3)
                            if len(anos_match.groups()) >= 2 and anos_match.group(2):
                                anos = float(anos_match.group(1))
                                meses = float(anos_match.group(2))
                                tempo_residencia_anos = anos + (meses / 12.0)
                                print(f"[TEMPO] Tempo extraído do parecer (padrão {i}): {anos} anos e {meses} meses = {tempo_residencia_anos:.2f} anos")
                            elif anos_match.group(1).isdigit():
                                # Apenas anos
                                tempo_residencia_anos = float(anos_match.group(1))
                                print(f"[TEMPO] Tempo extraído do parecer (padrão {i}): {tempo_residencia_anos} anos")
                            else:
                                # Pode ser uma data, calcular anos corretamente
                                data_str = anos_match.group(1)
                                print(f"[TEMPO] Data de residência indeterminada detectada: {data_str}")
                                
                                try:
                                    from datetime import datetime
                                    # Tentar diferentes formatos de data
                                    formatos_data = ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']
                                    data_residencia = None
                                    
                                    for formato in formatos_data:
                                        try:
                                            data_residencia = datetime.strptime(data_str, formato)
                                            break
                                        except ValueError:
                                            continue
                                    
                                    if data_residencia:
                                        data_atual = datetime.now()
                                        tempo_residencia_anos = (data_atual - data_residencia).days / 365.25
                                        print(f"[TEMPO] Anos calculados desde {data_str}: {tempo_residencia_anos:.1f} anos")
                                    else:
                                        print(f"[AVISO] Não foi possível interpretar a data: {data_str}")
                                        tempo_residencia_anos = 0
                                        
                                except Exception as e:
                                    print(f"[ERRO] Erro ao calcular anos da data {data_str}: {e}")
                                    tempo_residencia_anos = 0
                            tempo_encontrado = True
                            print(f"✅ [PRIORIDADE] Tempo de residência extraído do PARECER DA PF: {tempo_residencia_anos:.2f} anos")
                            break
                        else:
                            print(f"[DEBUG] ❌ Nenhum match no padrão {i}")
                    
                    if not tempo_encontrado:
                        print("[AVISO] Não foi possível extrair tempo específico do parecer")
                else:
                    print(f"[AVISO] Campo CHPF_PARECER vazio")
                    
            except Exception as e:
                print(f"[AVISO] Campo CHPF_PARECER não encontrado: {e}")
            
            # ========== PRIORIDADE 2: CAMPO RES_DAT (FALLBACK) ==========
            if tempo_residencia_anos == 0:
                print("[INFO] Passo 2 – Verificar campo RES_DAT (fallback)")
            else:
                print("[INFO] Passo 2 – PULANDO campo RES_DAT (parecer da PF já encontrado)")
            
            if tempo_residencia_anos == 0:
                try:
                    elemento_data = self.driver.find_element(By.ID, "RES_DAT")
                    data_residencia_str = elemento_data.get_attribute("value")
                    if data_residencia_str:
                        print(f"[DATA] Campo RES_DAT: {data_residencia_str}")
                        
                        from datetime import datetime
                        # Normalizar data inicial do processo para dd/mm/yyyy (ex.: "19 de Nov de 2023")
                        data_inicial_normalizada = normalizar_data_para_ddmmaaaa(self.data_inicial_processo) if self.data_inicial_processo else None
                        data_residencia = datetime.strptime(data_residencia_str.strip(), '%d/%m/%Y')
                        
                        # VERIFICAR SE DATA ESTÁ NO FUTURO
                        data_atual = datetime.now()
                        if data_residencia > data_atual:
                            print(f"⚠️ AVISO: Data de residência no futuro ({data_residencia_str}), ignorando...")
                            data_residencia = None
                            tempo_residencia_anos = 0
                        else:
                            if not data_inicial_normalizada:
                                raise ValueError("Data inicial do processo ausente ou inválida")
                            data_inicial = datetime.strptime(data_inicial_normalizada.strip(), '%d/%m/%Y')
                            tempo_residencia_anos = (data_inicial - data_residencia).days / 365.25
                            
                            print(f"[TEMPO] Tempo de residência calculado: {tempo_residencia_anos:.1f} anos")
                            print(f"✅ [FALLBACK] Tempo de residência extraído do CAMPO RES_DAT: {tempo_residencia_anos:.2f} anos")
                        
                except Exception as e:
                    print(f"[AVISO] Erro ao extrair data de residência do campo RES_DAT: {e}")
            
            # Método 3: Extrair do CRNM OCR (última tentativa)
            if tempo_residencia_anos == 0:
                try:
                    elemento_parecer = self.driver.find_element(By.ID, "CHPF_PARECER")
                    parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
                    
                    if parecer_texto:
                        print("[INFO] Analisando campo CHPF_PARECER...")
                        # Buscar indicações de tempo no parecer - padrões mais específicos para evitar falsos positivos
                        import re
                        
                        # Padrões de busca (do mais específico ao mais geral) para capturar residência
                        # Removidos padrões genéricos para evitar falsos positivos
                        padroes_tempo = [
                            r'possui\s+(\d+)\s*anos?\s+de\s+residência',
                            r'possui\s+(\d+)\s*anos?\s+.*residência',
                            r'(\d+)\s*anos?\s+de\s+residência',
                            r'residência.*?(\d+)\s*anos?',
                            r'(\d+)\s*anos?\s+.*indeterminad'
                        ]
                        
                        tempo_encontrado = False
                        for padrao in padroes_tempo:
                            anos_match = re.search(padrao, parecer_texto.lower())
                            if anos_match:
                                tempo_residencia_anos = float(anos_match.group(1))
                                print(f"[TEMPO] Tempo extraído do parecer (padrão usado: {padrao[:40]}...): {tempo_residencia_anos} anos")
                                tempo_encontrado = True
                                break
                        
                        if not tempo_encontrado:
                            print("[AVISO] Não foi possível extrair tempo específico do parecer")
                            print(f"[DEBUG] Texto do parecer (primeiros 200 chars): {parecer_texto[:200]}")
                            
                except Exception as e:
                    print(f"[AVISO] Erro ao extrair parecer: {e}")
            
            # Método 3: Extrair do CRNM OCR (última tentativa)
            if tempo_residencia_anos == 0:
                try:
                    print("[INFO] Tentando extrair data de residência do CRNM via OCR...")
                    
                    # Verificar se temos OCR do CRNM processado
                    resultado_crnm = self.resultados_validacao_ocr.get('CRNM', {})
                    texto_bruto_crnm = resultado_crnm.get('texto_bruto_ocr', '')
                    
                    if texto_bruto_crnm:
                        import re
                        from datetime import datetime
                        
                        # Verificar classificação: Residente, Permanente, Indeterminado
                        classificacao_valida = False
                        padroes_classificacao = [
                            r'residente',
                            r'permanente',
                            r'indeterminado',
                            r'prazo.*indeterminado'
                        ]
                        
                        for padrao in padroes_classificacao:
                            if re.search(padrao, texto_bruto_crnm, re.IGNORECASE):
                                classificacao_valida = True
                                print(f"[CRNM] Classificação válida encontrada: {padrao}")
                                break
                        
                        if classificacao_valida:
                            # Buscar data de emissão
                            padroes_data_emissao = [
                                r'data.*emiss[ãa]o[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
                                r'emiss[ãa]o[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})',
                                r'emitido.*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})'
                            ]
                            
                            for padrao in padroes_data_emissao:
                                match = re.search(padrao, texto_bruto_crnm, re.IGNORECASE)
                                if match:
                                    data_emissao_str = match.group(1).replace('-', '/')
                                    print(f"[CRNM] Data de emissão encontrada: {data_emissao_str}")
                                    
                                    try:
                                        data_emissao = datetime.strptime(data_emissao_str, '%d/%m/%Y')
                                        
                                        # Verificar se está no futuro
                                        if data_emissao > datetime.now():
                                            print(f"⚠️ AVISO: Data de emissão no futuro, ignorando...")
                                            break
                                        
                                        # Calcular tempo
                                        data_inicial_normalizada = normalizar_data_para_ddmmaaaa(self.data_inicial_processo)
                                        if data_inicial_normalizada:
                                            data_inicial = datetime.strptime(data_inicial_normalizada, '%d/%m/%Y')
                                            tempo_residencia_anos = (data_inicial - data_emissao).days / 365.25
                                            print(f"[CRNM] ✅ Tempo de residência calculado a partir do CRNM: {tempo_residencia_anos:.1f} anos")
                                            break
                                    except Exception as e:
                                        print(f"[CRNM] Erro ao processar data: {e}")
                        else:
                            print("[CRNM] Classificação não indica residência indeterminada/permanente")
                    else:
                        print("[CRNM] Texto OCR não disponível")
                        
                except Exception as e:
                    print(f"[AVISO] Erro ao extrair data do CRNM: {e}")
            
            # Se não encontrou tempo de residência, retornar com observação
            if tempo_residencia_anos == 0:
                print("🚨 ALERTA CRÍTICO: PRAZO DE RESIDÊNCIA NÃO ENCONTRADO!")
                print("⚠️  OBSERVAÇÃO: Prazo de residência não foi encontrado no campo RES_DAT, parecer CHPF_PARECER ou CRNM")
                print("⚠️  AÇÃO NECESSÁRIA: Verificar manualmente o tempo de residência do requerente")
                print("🚨 ATENÇÃO: Não é possível indeferir sem saber o prazo de residência por tempo indeterminado!")
                return {
                    'atendido': False,
                    'motivo': 'Prazo de residência não localizado nos campos do sistema',
                    'observacao': 'ALERTA: Verificar manualmente - Campo RES_DAT vazio, parecer CHPF_PARECER sem informação e CRNM sem data válida. NÃO É POSSÍVEL INDEFERIR SEM SABER O PRAZO DE RESIDÊNCIA POR TEMPO INDETERMINADO!',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': 0,
                    'pode_continuar': False,
                    'alerta_critico': True
                }
            
            # Verificar se atende ao prazo mínimo
            print(f"\n[DADOS] ========== VERIFICAÇÃO FINAL DE RESIDÊNCIA ==========")
            print(f"[DADOS] Prazo requerido: {prazo_requerido} ano(s)")
            print(f"[DADOS] Tempo comprovado: {tempo_residencia_anos:.2f} anos")
            print(f"[DADOS] Redução de prazo: {'SIM' if tem_reducao else 'NÃO'}")
            
            # Adicionar tolerância de 0.05 anos (~18 dias) para evitar problemas de arredondamento
            tolerancia = 0.05
            prazo_minimo_com_tolerancia = prazo_requerido - tolerancia
            print(f"[DADOS] Prazo mínimo com tolerância: {prazo_minimo_com_tolerancia:.2f} anos")
            print(f"[DADOS] Comparação: {tempo_residencia_anos:.2f} >= {prazo_minimo_com_tolerancia:.2f}?")
            
            if tempo_residencia_anos >= (prazo_requerido - tolerancia):
                print("✅ [RESULTADO] Residência mínima: ATENDIDA")
                print(f"✅ [DETALHE] {tempo_residencia_anos:.2f} anos >= {prazo_minimo_com_tolerancia:.2f} anos")
                return {
                    'atendido': True,
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': True
                }
            else:
                print("❌ [RESULTADO] Residência mínima: NÃO ATENDIDA")
                print(f"❌ [DETALHE] {tempo_residencia_anos:.2f} anos < {prazo_minimo_com_tolerancia:.2f} anos")
                return {
                    'atendido': False,
                    'motivo': 'Não comprovou residência mínima',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': False
                }
                
        except Exception as e:
            print(f"[ERRO] ERRO na verificação de residência mínima: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False
            }

    def verificar_residencia_minima_completa(self):
        """
        REQUISITO II – Residência mínima (Fluxo completo conforme especificado)
        """
        try:
            print('Passo 1 – Verificar se há redução de prazo')
            
            tem_reducao = False
            try:
                # Procurar pelo elemento que indica redução de prazo marcada como "Sim"
                elemento_reducao = self.driver.find_element(
                    By.XPATH, 
                    "//label[@for='HIP_CON_0' and contains(@aria-checked, 'true')]"
                )
                if elemento_reducao and "Sim" in elemento_reducao.text:
                    tem_reducao = True
                    print("[OK] Redução de prazo: SIM")
                    print("[INFO] Validando documento: Comprovante de redução de prazo")
                    
                    # Verificar se documento de redução foi anexado
                    try:
                        elemento_doc_reducao = self.driver.find_element(
                            By.XPATH,
                            "//span[contains(text(), 'Comprovante de redução de prazo')]"
                        )
                        if elemento_doc_reducao:
                            print("[OK] Comprovante de redução de prazo: anexado")
                        else:
                            print("[ERRO] Comprovante de redução de prazo: NÃO anexado")
                            return {
                                'atendido': False,
                                'motivo': 'Comprovante de redução de prazo não anexado',
                                'pode_continuar': False
                            }
                    except:
                        print("[ERRO] Comprovante de redução de prazo: NÃO anexado")
                        return {
                            'atendido': False,
                            'motivo': 'Comprovante de redução de prazo não anexado',
                            'pode_continuar': False
                        }
                    
                    prazo_requerido = 1
                    print("[INFO] Exigir 1 ano de residência indeterminada")
                else:
                    tem_reducao = False
                    prazo_requerido = 4
                    print("[ERRO] Redução de prazo: NÃO")
                    print("[INFO] Exigir 4 anos de residência indeterminada ou permanente")
            except Exception as e:
                print(f"[AVISO] Erro ao verificar redução de prazo: {e}")
                tem_reducao = False
                prazo_requerido = 4
                print("[ERRO] Redução de prazo: NÃO (padrão)")
                print("[INFO] Exigir 4 anos de residência indeterminada ou permanente")
            
            print('\nPasso 2 – Validar residência')
            print('Pode ser verificado por:')
            print('- Campo RES_DAT (Residência indeterminada)')
            print('- Campo CHPF_PARECER (Parecer)')
            
            data_residencia = None
            tempo_residencia_anos = 0
            
            # Método 1: Campo de data de residência indeterminada
            try:
                elemento_data = self.driver.find_element(By.ID, "RES_DAT")
                data_residencia_str = elemento_data.get_attribute("value")
                if data_residencia_str:
                    print(f"[DATA] Campo RES_DAT: {data_residencia_str}")
                    
                    from datetime import datetime
                    data_residencia = datetime.strptime(data_residencia_str, '%d/%m/%Y')
                    data_inicial = datetime.strptime(self.data_inicial_processo, '%d/%m/%Y')
                    tempo_residencia_anos = (data_inicial - data_residencia).days / 365.25
                    
                    print(f"[TEMPO] Tempo de residência calculado: {tempo_residencia_anos:.1f} anos")
                    
            except Exception as e:
                print(f"[AVISO] Erro ao extrair data de residência do campo RES_DAT: {e}")
            
            # Método 2: Parecer técnico (backup)
            if tempo_residencia_anos == 0:
                try:
                    elemento_parecer = self.driver.find_element(By.ID, "CHPF_PARECER")
                    parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
                    
                    if parecer_texto:
                        print("[INFO] Analisando campo CHPF_PARECER...")
                        # Buscar indicações de tempo no parecer - padrões mais específicos para evitar falsos positivos
                        import re
                        
                        # Padrões de busca (do mais específico ao mais geral) para capturar residência
                        padroes_tempo = [
                            r'possui\s+(\d+)\s*anos?\s+de\s+residência',  # "possui 1 ano de residência"
                            r'possui\s+(\d+)\s*anos?\s+.*residência',  # "possui 1 ano ... residência"
                            r'(\d+)\s*anos?\s+de\s+residência',  # "1 ano de residência"
                            r'residência.*?(\d+)\s*anos?',  # "residência ... 1 ano"
                            r'(\d+)\s*anos?\s+.*indeterminad',  # "1 ano ... indeterminado"
                            r'(\d+)\s*anos?'  # último padrão mais genérico
                        ]
                        
                        tempo_encontrado = False
                        for padrao in padroes_tempo:
                            anos_match = re.search(padrao, parecer_texto.lower())
                            if anos_match:
                                tempo_residencia_anos = float(anos_match.group(1))
                                print(f"[TEMPO] Tempo extraído do parecer (padrão usado: {padrao[:40]}...): {tempo_residencia_anos} anos")
                                tempo_encontrado = True
                                break
                        
                        if not tempo_encontrado:
                            print("[AVISO] Não foi possível extrair tempo específico do parecer")
                            print(f"[DEBUG] Texto do parecer (primeiros 200 chars): {parecer_texto[:200]}")
                            
                except Exception as e:
                    print(f"[AVISO] Erro ao extrair parecer: {e}")
            
            # Se não encontrou tempo de residência, retornar com observação
            if tempo_residencia_anos == 0:
                print("⚠️  OBSERVAÇÃO: Prazo de residência não foi encontrado no campo RES_DAT nem no parecer CHPF_PARECER")
                print("⚠️  AÇÃO NECESSÁRIA: Verificar manualmente o tempo de residência do requerente")
                return {
                    'atendido': False,
                    'motivo': 'Prazo de residência não localizado nos campos do sistema',
                    'observacao': 'Verificar manualmente: Campo RES_DAT vazio e parecer CHPF_PARECER sem informação de tempo',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': 0,
                    'pode_continuar': False
                }
            
            # Verificar se atende ao prazo mínimo
            print(f"\n[DADOS] VERIFICAÇÃO FINAL:")
            print(f"Prazo requerido: {prazo_requerido} ano(s)")
            print(f"Tempo comprovado: {tempo_residencia_anos:.2f} anos")
            
            # Adicionar tolerância de 0.05 anos (~18 dias) para evitar problemas de arredondamento
            tolerancia = 0.05
            if tempo_residencia_anos >= (prazo_requerido - tolerancia):
                print("[OK] Residência mínima: ATENDIDA")
                return {
                    'atendido': True,
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': True
                }
            else:
                print("[ERRO] Residência mínima: NÃO ATENDIDA")
                return {
                    'atendido': False,
                    'motivo': 'Não comprovou residência mínima',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': False
                }
                
        except Exception as e:
            print(f"[ERRO] ERRO na verificação de residência mínima: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False
            }

    def verificar_comunicacao_portugues_com_validacao_ocr(self):
        """
        REQUISITO III – Comunicação em língua portuguesa com validação OCR individual
        """
        try:
            print('Verificando: Comprovante de comunicação em português')
            
            # VERIFICAR SE É ORIGINÁRIO DE PAÍS LUSÓFONO (dispensa o documento)
            dados_pessoais = getattr(self, 'dados_pessoais_extraidos', {})
            nacionalidade_raw = dados_pessoais.get('nacionalidade', '')
            nacionalidade = nacionalidade_raw.strip() if nacionalidade_raw else ''
            
            if nacionalidade:
                print(f"[INFO] Nacionalidade do solicitante: {nacionalidade}")
                
                # Países de língua portuguesa que dispensam o documento
                paises_lusofonos = [
                    'angola', 'cabo verde', 'guiné-bissau', 'guiné equatorial', 
                    'moçambique', 'portugal', 'são tomé e príncipe', 'timor-leste',
                    'guine-bissau', 'guine equatorial', 'mocambique', 'sao tome e principe',
                    'timor leste', 'timor-leste', 'guiné bissau', 'guiné equatorial'
                ]
                
                nacionalidade_lower = nacionalidade.lower()
                eh_pais_lusofono = any(pais in nacionalidade_lower for pais in paises_lusofonos)
                
                if eh_pais_lusofono:
                    print("✅ DISPENSA: Solicitante originário de país de língua portuguesa")
                    print("📖 Fundamento: Art. 12, caput, inciso II, alínea 'a', da Constituição Federal")
                    print("   Países lusófonos: Angola, Cabo Verde, Guiné-Bissau, Guiné Equatorial,")
                    print("   Moçambique, Portugal, São Tomé e Príncipe e Timor-Leste")
                    return {
                        'atendido': True,
                        'motivo': f'Dispensado - originário de país lusófono ({nacionalidade})',
                        'pode_continuar': True,
                        'dispensado': True,
                        'fundamento_legal': 'Art. 12, caput, inciso II, alínea a, da Constituição Federal'
                    }
                else:
                    print(f"[INFO] Nacionalidade não é de país lusófono: {nacionalidade}")
            else:
                print("[AVISO] Nacionalidade não encontrada nos dados pessoais")
            
            # SE NÃO É PAÍS LUSÓFONO, VERIFICAR DOCUMENTO
            print("[INFO] Verificando documento de comunicação em português...")
            
            # BAIXAR E VALIDAR OCR DO COMPROVANTE DE COMUNICAÇÃO
            doc_comunicacao_valido = self.baixar_e_validar_documento_individual('Comprovante de comunicação em português')
            
            if doc_comunicacao_valido:
                print("✅ Comprovante de comunicação em português: VÁLIDO")
                return {
                    'atendido': True,
                    'motivo': 'Comprovante de comunicação em português válido',
                    'pode_continuar': True,
                    'dispensado': False
                }
            else:
                print("❌ Comprovante de comunicação em português: INVÁLIDO ou não anexado")
                return {
                    'atendido': False,
                    'motivo': 'Não anexou item 13',
                    'pode_continuar': True,  # CONTINUAR processamento mesmo se falhar
                    'dispensado': False
                }
                
        except Exception as e:
            print(f"[ERRO] ERRO na verificação de comunicação em português: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False,
                'dispensado': False
            }

    def verificar_comunicacao_portugues_preliminar(self):
        """
        REQUISITO III – Comunicação em língua portuguesa (verificação preliminar)
        """
        try:
            print('Verificando: Comprovante de comunicação em português')
            
            # Verificar se o documento foi anexado
            try:
                elemento_comunicacao = self.driver.find_element(
                    By.XPATH,
                    "//span[contains(text(), 'Comprovante de comunicação em português')]"
                )
                
                if elemento_comunicacao and elemento_comunicacao.is_displayed():
                    print("✅ Documento anexado")
                    return {
                        'atendido': True,
                        'motivo': 'Comprovante de comunicação em português anexado',
                        'pode_continuar': True
                    }
                else:
                    print("❌ Documento não anexado")
                    return {
                        'atendido': False,
                        'motivo': 'Não anexou item 13',
                        'pode_continuar': False
                    }
            except:
                print("❌ Documento não anexado")
                return {
                    'atendido': False,
                    'motivo': 'Não anexou item 13',
                    'pode_continuar': False
                }
                
        except Exception as e:
            print(f"[ERRO] ERRO na verificação de comunicação em português: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False
            }

    def verificar_residencia_minima_antes_download(self):
        """
        Verifica residência mínima ANTES de baixar documentos
        Segunda etapa obrigatória do fluxo ordinário
        """
        try:
            print("\n" + "="*80)
            print("[INFO] REQUISITO II: RESIDÊNCIA MÍNIMA")
            print("Art. 65, inciso II da Lei nº 13.445/2017")
            print("="*80)
            
            # PASSO 1: Verificar se há redução de prazo
            print("[BUSCA] PASSO 1: Verificando redução de prazo...")
            
            tem_reducao = False
            try:
                # Procurar pelo elemento que indica redução de prazo marcada como "Sim"
                elemento_reducao = self.driver.find_element(
                    By.XPATH, 
                    "//label[@for='HIP_CON_0' and contains(@aria-checked, 'true')]"
                )
                if elemento_reducao and "Sim" in elemento_reducao.text:
                    tem_reducao = True
                    print("[OK] Redução de prazo: SIM")
                    prazo_requerido = 1
                    print("[INFO] Prazo requerido: 1 ano de residência indeterminada")
                else:
                    print("[ERRO] Redução de prazo: NÃO")
                    prazo_requerido = 4
                    print("[INFO] Prazo requerido: 4 anos de residência indeterminada ou permanente")
            except Exception as e:
                print(f"[AVISO] Erro ao verificar redução de prazo: {e}")
                print("[ERRO] Redução de prazo: NÃO (assumindo padrão)")
                tem_reducao = False
                prazo_requerido = 4
                print("[INFO] Prazo requerido: 4 anos de residência indeterminada ou permanente")
            
            # PASSO 2: Validar residência via formulário
            print("\n[BUSCA] PASSO 2: Validando tempo de residência...")
            
            data_residencia = None
            tempo_residencia_anos = 0
            
            # Método 1: Campo de data de residência indeterminada
            try:
                elemento_data = self.driver.find_element(By.ID, "RES_DAT")
                data_residencia_str = elemento_data.get_attribute("value")
                if data_residencia_str:
                    print(f"[DATA] Data residência indeterminada (campo): {data_residencia_str}")
                    
                    from datetime import datetime
                    data_residencia = datetime.strptime(data_residencia_str, '%d/%m/%Y')
                    data_inicial = datetime.strptime(self.data_inicial_processo, '%d/%m/%Y')
                    tempo_residencia_anos = (data_inicial - data_residencia).days / 365.25
                    
                    print(f"[TEMPO] Tempo de residência calculado: {tempo_residencia_anos:.1f} anos")
                    
            except Exception as e:
                print(f"[AVISO] Erro ao extrair data de residência do campo: {e}")
            
            # Método 2: Parecer técnico (backup)
            if tempo_residencia_anos == 0:
                try:
                    elemento_parecer = self.driver.find_element(By.ID, "CHPF_PARECER")
                    parecer_texto = elemento_parecer.get_attribute("value") or elemento_parecer.text
                    
                    if parecer_texto:
                        print("[INFO] Analisando parecer técnico...")
                        # Buscar indicações de tempo no parecer - padrões mais específicos para evitar falsos positivos
                        import re
                        
                        # Padrões de busca (do mais específico ao mais geral) para capturar residência
                        padroes_tempo = [
                            r'possui\s+(\d+)\s*anos?\s+de\s+residência',  # "possui 1 ano de residência"
                            r'possui\s+(\d+)\s*anos?\s+.*residência',  # "possui 1 ano ... residência"
                            r'(\d+)\s*anos?\s+de\s+residência',  # "1 ano de residência"
                            r'residência.*?(\d+)\s*anos?',  # "residência ... 1 ano"
                            r'(\d+)\s*anos?\s+.*indeterminad',  # "1 ano ... indeterminado"
                            r'(\d+)\s*anos?'  # último padrão mais genérico
                        ]
                        
                        tempo_encontrado = False
                        for padrao in padroes_tempo:
                            anos_match = re.search(padrao, parecer_texto.lower())
                            if anos_match:
                                tempo_residencia_anos = float(anos_match.group(1))
                                print(f"[TEMPO] Tempo extraído do parecer (padrão usado: {padrao[:40]}...): {tempo_residencia_anos} anos")
                                tempo_encontrado = True
                                break
                        
                        if not tempo_encontrado:
                            print("[AVISO] Não foi possível extrair tempo específico do parecer")
                            print(f"[DEBUG] Texto do parecer (primeiros 200 chars): {parecer_texto[:200]}")
                            
                except Exception as e:
                    print(f"[AVISO] Erro ao extrair parecer: {e}")
            
            # PASSO 3: Verificar se atende ao prazo mínimo
            print(f"\n[DADOS] ========== VERIFICAÇÃO FINAL DE RESIDÊNCIA ==========")
            print(f"[DADOS] Prazo requerido: {prazo_requerido} ano(s)")
            print(f"[DADOS] Tempo comprovado: {tempo_residencia_anos:.2f} anos")
            print(f"[DADOS] Redução de prazo: {'SIM' if tem_reducao else 'NÃO'}")
            
            # Adicionar tolerância de 0.05 anos (~18 dias) para evitar problemas de arredondamento
            tolerancia = 0.05
            prazo_minimo_com_tolerancia = prazo_requerido - tolerancia
            print(f"[DADOS] Prazo mínimo com tolerância: {prazo_minimo_com_tolerancia:.2f} anos")
            print(f"[DADOS] Comparação: {tempo_residencia_anos:.2f} >= {prazo_minimo_com_tolerancia:.2f}?")
            
            if tempo_residencia_anos >= (prazo_requerido - tolerancia):
                print("[OK] RESIDÊNCIA MÍNIMA: ATENDIDA")
                print(f"[OK] Comprovou {tempo_residencia_anos:.1f} anos (≥ {prazo_requerido})")
                return {
                    'atendido': True,
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'pode_continuar': True,
                    'necessita_doc_reducao': tem_reducao  # Se tem redução, precisa validar documento
                }
            else:
                print("[ERRO] RESIDÊNCIA MÍNIMA: NÃO ATENDIDA")
                print(f"[ERRO] Comprovou apenas {tempo_residencia_anos:.1f} anos (< {prazo_requerido})")
                print("🚫 INDEFERIMENTO AUTOMÁTICO")
                print("🚫 Fundamento: Art. 65, inciso II da Lei nº 13.445/2017")
                return {
                    'atendido': False,
                    'motivo': 'Não comprovou residência mínima',
                    'tem_reducao': tem_reducao,
                    'prazo_requerido': prazo_requerido,
                    'tempo_comprovado': tempo_residencia_anos,
                    'fundamento_legal': 'Art. 65, inciso II da Lei nº 13.445/2017',
                    'pode_continuar': False
                }
                
        except Exception as e:
            print(f"[ERRO] ERRO na verificação de residência mínima: {e}")
            return {
                'atendido': False,
                'motivo': f'Erro na verificação: {e}',
                'pode_continuar': False
            }

    def extrair_dados_pessoais_formulario(self):
        """
        Extrai dados pessoais do formulário: nome, pai, mãe, data nascimento
        """
        try:
            print("[BUSCA] Extraindo dados pessoais do formulário...")
            
            dados_pessoais = {}
            
            # Nome completo
            try:
                nome_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "ORD_NOM_COMPLETO"
                )))
                dados_pessoais['nome_completo'] = nome_element.get_attribute('value').strip()
                print(f"[OK] Nome completo: {dados_pessoais['nome_completo']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair nome completo: {e}")
                dados_pessoais['nome_completo'] = None
            
            # Nome do pai
            try:
                pai_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "ORD_FI1"
                )))
                dados_pessoais['nome_pai'] = pai_element.get_attribute('value').strip()
                print(f"[OK] Nome do pai: {dados_pessoais['nome_pai']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair nome do pai: {e}")
                dados_pessoais['nome_pai'] = None
            
            # Nome da mãe
            try:
                mae_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "ORD_FI2"
                )))
                dados_pessoais['nome_mae'] = mae_element.get_attribute('value').strip()
                print(f"[OK] Nome da mãe: {dados_pessoais['nome_mae']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair nome da mãe: {e}")
                dados_pessoais['nome_mae'] = None
            
            # Data de nascimento
            try:
                nascimento_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "ORD_NAS"
                )))
                dados_pessoais['data_nascimento'] = nascimento_element.get_attribute('value').strip()
                print(f"[OK] Data de nascimento: {dados_pessoais['data_nascimento']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair data de nascimento: {e}")
                dados_pessoais['data_nascimento'] = None
            
            # RNM/RNE
            try:
                rnm_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "NUM_RNM"
                )))
                dados_pessoais['rnm'] = rnm_element.get_attribute('value').strip()
                print(f"[OK] RNM: {dados_pessoais['rnm']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair RNM: {e}")
                dados_pessoais['rnm'] = None
            
            # Nacionalidade
            try:
                nacionalidade_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "ORD_PAIS_ORIGEM"
                )))
                dados_pessoais['nacionalidade'] = nacionalidade_element.get_attribute('value').strip()
                print(f"[OK] Nacionalidade: {dados_pessoais['nacionalidade']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair nacionalidade: {e}")
                dados_pessoais['nacionalidade'] = None
            
            # Estado (UF)
            try:
                estado_element = self.wait.until(EC.visibility_of_element_located((
                    By.ID, "ORD_UF"
                )))
                dados_pessoais['estado'] = estado_element.get_attribute('value').strip()
                # Se não conseguir pelo value, tentar pelo title
                if not dados_pessoais['estado']:
                    dados_pessoais['estado'] = estado_element.get_attribute('title').strip()
                print(f"[OK] Estado (UF): {dados_pessoais['estado']}")
            except Exception as e:
                print(f"[AVISO] Erro ao extrair estado: {e}")
                dados_pessoais['estado'] = None
            
            # Mapear nomes alternativos para compatibilidade com despacho
            dados_pessoais['pai'] = dados_pessoais.get('nome_pai')
            dados_pessoais['mae'] = dados_pessoais.get('nome_mae')
            dados_pessoais['uf'] = dados_pessoais.get('estado')
            
            print(f"[OK] Dados pessoais extraídos: {dados_pessoais}")
            return dados_pessoais
            
        except Exception as e:
            print(f"[ERRO] Erro ao extrair dados pessoais: {e}")
            return {}

    def extrair_data_inicial_processo(self):
        """
        Extrai a data inicial do processo da tela de navegação (novo formato)
        """
        try:
            print("[BUSCA] Extraindo data inicial do processo...")
            
            # Novo formato: buscar por span.subtitle
            try:
                subtitle_element = self.wait.until(EC.visibility_of_element_located((
                    By.XPATH, "//span[@class='subtitle']"
                )))
                
                texto_subtitle = subtitle_element.text.strip()
                print(f"DEBUG: Texto encontrado no subtitle: {texto_subtitle}")
                
                # Extrair data usando regex para o novo formato
                # Exemplo: "Em andamento - aberto por Cidadão 10 de Jan de 2025 às 14:55"
                import re
                match = re.search(r'aberto por .+ (\d{1,2} de \w+ de \d{4})', texto_subtitle)
                if match:
                    data_inicial = match.group(1)
                    print(f"[OK] Data inicial extraída: {data_inicial}")
                    return data_inicial
                else:
                    print("[ERRO] Não foi possível extrair data do texto subtitle")
                    return None
                    
            except Exception as e:
                print(f"[AVISO] Erro ao extrair data do subtitle: {e}")
                # Fallback para o formato antigo
                try:
                    data_element = self.wait.until(EC.visibility_of_element_located((
                        By.XPATH, "//div[contains(@class,'info data')]//div[contains(@class,'label') and contains(text(),'Data inicial')]/following-sibling::div//span[contains(@class,'data')]"
                    )))
                    
                    data_inicial = data_element.text.strip()
                    print(f"[OK] Data inicial extraída (formato antigo): {data_inicial}")
                    return data_inicial
                    
                except Exception as e2:
                    print(f"[ERRO] Erro no fallback para formato antigo: {e2}")
                    return None
            
        except Exception as e:
            print(f"[ERRO] Erro geral ao extrair data inicial: {e}")
            return None

    def comparar_dados(self, dados_ocr, dados_texto, return_dict=False):
        if dados_texto is None:
            dados_texto = {}
        print('--- Comparação OCR x Texto ---')
        campos = ['nome', 'pai', 'mae', 'rnm', 'data_nasc']
        campos_comparados = {}
        divergencias = []
        if return_dict:
            resultado_dict = {
                'resultado': '',
                'campos_comparados': {},
                'divergencias': [],
                'ocr_todos_campos': dados_ocr
            }
        for campo in campos:
            val_ocr = dados_ocr.get(campo, '') or ''
            val_txt = dados_texto.get(campo, '') or ''
            ok = False
            if campo == 'nome':
                # Se o OCR trouxe uma lista (ex: [sobrenome, nome]), concatena
                if isinstance(val_ocr, list) and len(val_ocr) == 2:
                    val_ocr_concat = f"{val_ocr[1]} {val_ocr[0]}".strip()
                    ok = val_txt.strip().upper() == val_ocr_concat.strip().upper()
                else:
                    if isinstance(val_ocr, str):
                        ok = val_txt.strip().upper() == val_ocr.strip().upper()
                    else:
                        ok = False
            else:
                if isinstance(val_ocr, str):
                    ok = val_txt.strip().lower() in val_ocr.strip().lower() if val_txt else False
                else:
                    ok = False
            campos_comparados[campo] = {'texto': val_txt, 'ocr': val_ocr, 'ok': ok}
            if val_txt and not ok:
                divergencias.append(campo)
        for campo in campos:
            print(f"{campo.title()} (texto): {campos_comparados[campo]['texto']}")
            print(f"{campo.title()} (OCR): {campos_comparados[campo]['ocr']}")
        all_ok = all(v['ok'] for v in campos_comparados.values() if v['texto'])
        if all_ok:
            print('DADOS CONFEREM!')
            resultado = 'DADOS CONFEREM!'
        else:
            print('DIVERGÊNCIA ENCONTRADA!')
            resultado = 'DIVERGÊNCIA ENCONTRADA!'
        if return_dict:
            resultado_dict['resultado'] = resultado
            resultado_dict['campos_comparados'] = campos_comparados
            resultado_dict['divergencias'] = divergencias
            return resultado_dict, campos_comparados
        else:
            print('--- Fim comparação ---')

    def fechar_abas_desnecessarias(self):
        """
        Fecha todas as abas desnecessárias, mantendo apenas a aba principal de pesquisa
        """
        try:
            print("🧹 Fechando abas desnecessárias...")
            
            # Obter todas as abas abertas
            todas_abas = self.driver.window_handles
            print(f"DEBUG: {len(todas_abas)} abas encontradas")
            
            if len(todas_abas) <= 1:
                print("DEBUG: Apenas uma aba aberta, nada a fazer")
                return
            
            # Identificar a aba principal (pesquisa de processos)
            aba_principal = None
            aba_atual = self.driver.current_window_handle
            
            print("DEBUG: Verificando conteúdo de cada aba...")
            for i, aba in enumerate(todas_abas):
                try:
                    self.driver.switch_to.window(aba)
                    url_atual = self.driver.current_url
                    titulo_atual = self.driver.title
                    
                    print(f"DEBUG: Aba {i+1}: {titulo_atual[:30]}... - {url_atual[:60]}...")
                    
                    # Verificar se é a aba de pesquisa de processos
                    if ('pesquisa_processo' in url_atual or 
                        ('bpm' in url_atual and 'form-app' not in url_atual and 'process-instances' not in url_atual)):
                        aba_principal = aba
                        print(f"[OK] Aba principal identificada: {titulo_atual[:30]}...")
                        break
                        
                except Exception as e:
                    print(f"DEBUG: Erro ao verificar aba {i+1}: {e}")
                    continue
            
            # Se não encontrou aba principal, usar a primeira
            if not aba_principal:
                aba_principal = todas_abas[0]
                print("DEBUG: Usando primeira aba como principal")
            
            # Fechar todas as outras abas
            abas_fechadas = 0
            for i, aba in enumerate(todas_abas):
                if aba != aba_principal:
                    try:
                        self.driver.switch_to.window(aba)
                        url_aba = self.driver.current_url
                        titulo_aba = self.driver.title
                        print(f"DEBUG: Fechando aba {i+1}: {titulo_aba[:30]}...")
                        self.driver.close()
                        abas_fechadas += 1
                        time.sleep(0.5)  # Pequena pausa entre fechamentos
                    except Exception as e:
                        print(f"DEBUG: Erro ao fechar aba {i+1}: {e}")
            
            # Voltar para a aba principal
            try:
                self.driver.switch_to.window(aba_principal)
                print(f"[OK] {abas_fechadas} abas fechadas. Aba principal ativa: {self.driver.title[:30]}...")
            except Exception as e:
                print(f"ERRO ao voltar para aba principal: {e}")
                # Se não conseguir voltar, criar nova aba
                self.driver.execute_script("window.open('');")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                print("DEBUG: Nova aba criada como fallback")
            
            # Verificar se estamos na página de pesquisa
            if not self.verificar_se_esta_na_pesquisa():
                print("DEBUG: Não estamos na pesquisa, navegando...")
                self.driver.get('https://justica.servicos.gov.br/workspace/')
                time.sleep(3)
                print("DEBUG: Navegação para pesquisa concluída")
            
        except Exception as e:
            print(f"ERRO ao fechar abas desnecessárias: {e}")
            # Em caso de erro, tentar navegar diretamente para pesquisa
            try:
                print("DEBUG: Tentando recuperação via navegação direta...")
                self.driver.get('https://justica.servicos.gov.br/workspace/')
                time.sleep(3)
                print("DEBUG: Navegação de recuperação concluída")
            except Exception as e2:
                print(f"ERRO na navegação de recuperação: {e2}")
                # Último recurso: fechar todas as abas e abrir uma nova
                try:
                    for aba in self.driver.window_handles:
                        if aba != self.driver.current_window_handle:
                            self.driver.switch_to.window(aba)
                            self.driver.close()
                    self.driver.switch_to.window(self.driver.window_handles[0])
                    self.driver.get('https://justica.servicos.gov.br/workspace/')
                    print("DEBUG: Recuperação via fechamento total concluída")
                except Exception as e3:
                    print(f"ERRO FATAL na recuperação: {e3}")

    
    def verificar_se_esta_na_pesquisa(self):
        """Verifica se já estamos na página de pesquisa de processos"""
        try:
            # Verifica se estamos na URL correta
            current_url = self.driver.current_url
            print(f'DEBUG: URL atual: {current_url}')
            
            if 'workspace' in current_url:
                # Verifica se os elementos da página de pesquisa estão presentes
                try:
                    campo_search = self.driver.find_element(By.ID, "field-search")
                    if campo_search.is_displayed():
                        print('DEBUG: Confirmado: estamos na página de pesquisa de processos')
                        return True
                    else:
                        print('DEBUG: Campo field-search não está visível')
                except Exception as e:
                    print(f'DEBUG: Campo field-search não encontrado: {e}')
                    
                # Tentar verificar outros elementos do workspace
                try:
                    workspace_table = self.driver.find_element(By.CLASS_NAME, "ant-table-tbody")
                    if workspace_table.is_displayed():
                        print('DEBUG: Confirmado via tabela do workspace: estamos na página de pesquisa')
                        return True
                except:
                    pass
                    
                # Verificar por texto na página
                page_text = self.driver.page_source
                if 'field-search' in page_text or 'workspace' in page_text:
                    print('DEBUG: Confirmado via texto da página: estamos na pesquisa')
                    return True
                    
            print('DEBUG: Não estamos na página de pesquisa de processos')
            return False
        except Exception as e:
            print(f'DEBUG: Erro ao verificar se está na pesquisa: {e}')
            return False

    def buscar_proximo_processo(self):
        """
        Busca o próximo processo, garantindo que as abas estejam organizadas
        """
        print("[BUSCA] BUSCANDO PRÓXIMO PROCESSO...")
        print("DEBUG: Organizando abas antes da busca...")
        
        # SEMPRE fechar abas desnecessárias antes de buscar próximo processo
        self.fechar_abas_desnecessarias()
        
        # Verificar se estamos na página de pesquisa
        if not self.verificar_se_esta_na_pesquisa():
            print("DEBUG: Não estamos na pesquisa, navegando...")
            self.driver.get('https://justica.servicos.gov.br/workspace/')
            time.sleep(3)
        
        print("DEBUG: [OK] Pronto para buscar próximo processo - abas organizadas!")
        print("DEBUG: [TARGET] Sistema limpo e organizado para nova busca")

# Função utilitária para normalizar datas por extenso para dd/mm/yyyy
MESES = {
    'janeiro': '01', 'jan': '01', 'fevereiro': '02', 'fev': '02', 'março': '03', 'marco': '03', 'mar': '03',
    'abril': '04', 'abr': '04', 'maio': '05', 'mai': '05', 'junho': '06', 'jun': '06',
    'julho': '07', 'jul': '07', 'agosto': '08', 'ago': '08', 'setembro': '09', 'set': '09', 'outubro': '10', 'out': '10', 
    'novembro': '11', 'nov': '11', 'dezembro': '12', 'dez': '12'
}
def normalizar_data_para_ddmmaaaa(data_str):
    # Se já está no formato dd/mm/yyyy, retorna igual
    if re.match(r'\d{2}/\d{2}/\d{4}$', data_str.strip()):
        return data_str.strip()
    # Tenta converter de "19 de dezembro de 1992" para "19/12/1992"
    m = re.match(r'(\d{1,2}) de ([a-zç]+) de (\d{4})', data_str.strip(), re.IGNORECASE)
    if m:
        dia = m.group(1).zfill(2)
        mes_nome = m.group(2).lower()
        mes = MESES.get(mes_nome, '01')
        ano = m.group(3)
        resultado = f'{dia}/{mes}/{ano}'
        print(f"[DEBUG] Data normalizada: '{data_str}' -> '{resultado}'")
        return resultado
    print(f"[DEBUG] Data não normalizada: '{data_str}'")
    return data_str.strip()

if __name__ == "__main__":
    print('=== INÍCIO DO SCRIPT PRINCIPAL ===')
    numero_processo = "668.121"  # Exemplo
    dados_texto = {'pai': 'John Stephen Lyons', 'mae': 'Cynthia Mae Goodpaster', 'rnm': 'G064347-0'}
    navegacao = NavegacaoOrdinaria()
    try:
        resultado = navegacao.processar_processo(numero_processo, dados_texto)
        print("Resultado do processamento:", resultado)
    except Exception as e:
        print('ERRO FATAL durante o processamento:', e)
    finally:
        navegacao.close()

