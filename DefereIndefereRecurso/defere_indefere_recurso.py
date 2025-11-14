import os
from dotenv import load_dotenv
# Carrega o .env da pasta atual do script
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)
print("Arquivo .env existe?", os.path.exists(env_path))

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
import pandas as pd
from selenium.webdriver.chrome.options import Options

LECOM_URL = "https://justica.servicos.gov.br/bpm"

class DefereIndefefereRecurso:
    def __init__(self, driver=None):
        """
        Inicializa o automatizador para Defere ou Indefere Recurso
        """
        print("[DEBUG] Iniciando construtor DefereIndefefereRecurso...")
        
        if driver:
            # Usar driver existente se fornecido
            self.driver = driver
            self.wait = WebDriverWait(self.driver, 40)
            print("Usando driver existente")
        else:
            # Criar novo driver com configurações
            print("[DEBUG] DEBUG: Criando novo driver Chrome...")
            chrome_options = Options()
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
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
                "plugins.always_open_pdf_externally": False,
                "plugins.plugins_disabled": ["Chrome PDF Viewer"],
                "profile.default_content_settings.popups": 0,
                "profile.default_content_setting_values.automatic_downloads": 1,
                "profile.content_settings.exceptions.automatic_downloads.*.setting": 1,
                "profile.default_content_settings.plugins": 2,
                "profile.content_settings.plugin_whitelist.adobe-flash-player": 0,
                "profile.default_content_setting_values.plugins": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 40)
            print("Novo driver criado")
            
            # Verificar se driver foi criado corretamente
            try:
                test_url = self.driver.current_url
                print(f"[DEBUG] DEBUG: Driver testado - URL inicial: {test_url}")
            except Exception as e:
                print(f"[ERRO] DEBUG: Erro ao testar driver recém-criado: {e}")
        
        # Propriedades essenciais
        self.ja_logado = False
        self.resultados = []  # Para armazenar resultados de cada processo
        self.modo_teste = False  # MODO PRODUÇÃO: Formulários serão enviados efetivamente
        
        print("[OK] DEBUG: Construtor DefereIndefefereRecurso concluído com sucesso")
        print("[EXEC] MODO PRODUÇÃO: Formulários serão enviados efetivamente!")
        
    def login(self):
        """Aguarda login manual no LECOM"""
        print('=== INÍCIO login ===')
        print('[WEB] Acessando o LECOM...')
        self.driver.get(LECOM_URL)
        
        print('[USER] AGUARDANDO LOGIN MANUAL...')
        print('[INFO] Instruções:')
        print('   1. Faça o login manualmente na página do LECOM')
        print('   2. O sistema detectará automaticamente quando o login for concluído')
        print('   3. Aguarde até aparecer "[OK] Login detectado!" antes de continuar')
        print()
        print('[AGUARDE] Monitorando... (aguardando até 300 segundos)')
        
        # Aguardar até 5 minutos pelo login manual
        timeout = 300  # 5 minutos
        tempo_inicio = time.time()
        
        while time.time() - tempo_inicio < timeout:
            try:
                # Verificar se estamos na página principal do workspace (logado)
                current_url = self.driver.current_url
                if 'workspace' in current_url or 'portal' in current_url:
                    print('[OK] Login detectado!')
                    self.ja_logado = True
                    return True
                    
                # Aguardar 2 segundos antes da próxima verificação
                time.sleep(2)
                
            except Exception as e:
                print(f'[AVISO] Erro durante monitoramento: {e}')
                time.sleep(2)
        
        print('[ERRO] Timeout: Login não foi detectado dentro do tempo limite')
        return False

    def ler_planilha_codigos(self, caminho_planilha, nome_coluna='codigo'):
        """
        Lê códigos da planilha Excel ou CSV
        """
        print(f'=== INÍCIO ler_planilha_codigos ===')
        print(f'[ARQUIVO] Lendo planilha: {caminho_planilha}')
        print(f'[DADOS] Coluna alvo: {nome_coluna}')
        
        try:
            # Verificar driver antes da leitura
            try:
                test_url = self.driver.current_url
                print(f'[DEBUG] DEBUG: Driver ativo antes da leitura - URL: {test_url}')
            except Exception as e:
                print(f'[ERRO] DEBUG: Driver perdido antes da leitura: {e}')
            
            # Determinar tipo de arquivo e ler
            if caminho_planilha.endswith('.csv'):
                df = pd.read_csv(caminho_planilha, dtype=str)
                print('[DOC] Arquivo CSV lido')
            else:
                df = pd.read_excel(caminho_planilha, dtype=str)
                print('[DADOS] Arquivo Excel lido')
            
            print(f'[INFO] Planilha carregada: {len(df)} linhas')
            print(f'[DADOS] Colunas disponíveis: {list(df.columns)}')
            
            # Verificar se a coluna existe (case-insensitive)
            colunas_df = [col.lower() for col in df.columns]
            nome_coluna_lower = nome_coluna.lower()
            
            if nome_coluna_lower in colunas_df:
                # Encontrar nome real da coluna
                nome_coluna_real = df.columns[colunas_df.index(nome_coluna_lower)]
                print(f'[OK] Coluna "{nome_coluna_real}" encontrada')
            else:
                print(f'[ERRO] Coluna "{nome_coluna}" não encontrada')
                print(f'[DADOS] Colunas disponíveis: {list(df.columns)}')
                return []
            
            # Extrair códigos (remover vazios e NaN)
            serie_codigos = df[nome_coluna_real].dropna().astype(str)
            serie_codigos = serie_codigos[serie_codigos != '']
            codigos = serie_codigos.tolist()
            print(f'[INFO] Encontrados {len(codigos)} códigos (ordem preservada)')
            
            # Verificar driver após extração
            try:
                test_url3 = self.driver.current_url
                print(f'[DEBUG] DEBUG: Driver ativo APÓS extração - URL: {test_url3}')
            except Exception as e:
                print(f'[ERRO] DEBUG: Driver perdido APÓS extração: {e}')
            
            print(f'[DEBUG] DEBUG: Retornando lista de códigos...')
            print(f'[DEBUG] DEBUG: Primeiros 3 códigos: {codigos[:3]}')
            return codigos
            
        except Exception as e:
            print(f'[ERRO] Erro ao ler planilha: {e}')
            # Verificar driver após erro
            try:
                test_url_error = self.driver.current_url
                print(f'[DEBUG] DEBUG: Driver ainda ativo após erro - URL: {test_url_error}')
            except Exception as e2:
                print(f'[ERRO] DEBUG: Driver perdido após erro: {e2}')
            return []

    def aplicar_filtros(self, numero_processo):
        """
        Aplica filtros e navega para o processo específico
        Procura pela etapa "Defere ou Indefere Recurso"
        """
        import re as regex_module  # Importar com alias para evitar conflitos
        print('=== INÍCIO aplicar_filtros ===')
        print('Navegação direta para o processo...')
        print(f'[BUSCA] Navegando para processo: {numero_processo}')
        
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
            
            # PASSO 2: Aguardar tabela carregar e buscar atividade
            print('[BUSCA] Procurando "Defere ou Indefere Recurso" na tabela...')
            
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

            # Encontrar TODAS as atividades "Defere ou Indefere Recurso" e pegar a do ciclo mais alto
            defere_indefere_links = []
            
            for link, titulo, href in todos_links:
                try:
                    titulo_lc = titulo.lower()
                    # Procurar por "Defere ou Indefere Recurso"
                    if ('defere' in titulo_lc or 'indefere' in titulo_lc) and 'recurso' in titulo_lc:
                        # Extrair o ciclo da URL usando regex
                        match = regex_module.search(r'/(\d+)\?', href)
                        if match:
                            ciclo = int(match.group(1))
                            defere_indefere_links.append((link, titulo, href, ciclo))
                            print(f"[BUSCA] Encontrou 'Defere ou Indefere Recurso' ciclo {ciclo}: {href}")
                except Exception as e:
                    print(f"[AVISO] Erro ao processar link: {e}")
                    continue
            
            # Escolher a atividade com ciclo mais alto
            link_escolhido = None
            processInstanceId_escolhido = None
            ciclo_escolhido = None
            
            if defere_indefere_links:
                # Mostrar todos os ciclos encontrados
                print(f"[INFO] Total de atividades 'Defere ou Indefere Recurso' encontradas: {len(defere_indefere_links)}")
                for i, (_, titulo, href, ciclo) in enumerate(defere_indefere_links, 1):
                    print(f"   {i}. Ciclo {ciclo}: {titulo} -> {href}")
                
                # Ordenar por ciclo descendente (mais alto primeiro)
                defere_indefere_links.sort(key=lambda x: x[3], reverse=True)
                
                # Pegar o primeiro (ciclo mais alto)
                link_escolhido, titulo_escolhido, href_escolhido, ciclo_escolhido = defere_indefere_links[0]
                
                print(f"[TARGET] SELECIONADO: 'Defere ou Indefere Recurso' com CICLO MAIS ALTO: {ciclo_escolhido}")
                print(f"   [PIN] Título: '{titulo_escolhido}'")
                print(f"   [LINK] URL: {href_escolhido}")
                
                # Armazenar o ciclo para usar na construção da URL do form-web
                self.ciclo_processo = ciclo_escolhido
                print(f"[SALVO] Ciclo {ciclo_escolhido} armazenado para construção da URL do form-web")
                
            else:
                print("[AVISO] Nenhuma atividade 'Defere ou Indefere Recurso' encontrada")
                # Fallback: procurar apenas pelo título
                for link, titulo, href in todos_links:
                    try:
                        titulo_lc = titulo.lower()
                        if ('defere' in titulo_lc or 'indefere' in titulo_lc) and 'recurso' in titulo_lc:
                            link_escolhido = link
                            print(f"[OK] Selecionado por título (fallback): '{titulo}' -> {href}")
                            
                            # Tentar extrair ciclo mesmo assim
                            match = regex_module.search(r'/(\d+)\?', href)
                            if match:
                                self.ciclo_processo = int(match.group(1))
                            else:
                                self.ciclo_processo = 1  # Default
                            break
                    except Exception:
                        continue

            if not link_escolhido:
                print('[ERRO] "Defere ou Indefere Recurso" não encontrada na lista de atividades!')
                return None

            # PASSO 3: Clicar na atividade escolhida
            print('[CLIQUE] Clicando na atividade "Defere ou Indefere Recurso"...')
            
            try:
                link_escolhido.click()
                print('[OK] Clique normal executado')
            except Exception as e:
                print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                self.driver.execute_script("arguments[0].click();", link_escolhido)
                print('[OK] Clique via JavaScript executado')

            # PASSO 4: Aguardar redirecionamento
            print('[AGUARDE] Aguardando redirecionamento...')
            time.sleep(4)
            
            # Verificar se foi redirecionado corretamente
            url_final = self.driver.current_url
            print(f'[LINK] URL final: {url_final}')
            
            if 'form-app' in url_final or 'form-web' in url_final:
                print('[OK] Redirecionamento para formulário detectado')
                return True
            else:
                print('[AVISO] URL não parece ser de formulário, mas continuando...')
                return True
            
        except Exception as e:
            print(f'[ERRO] Erro ao aplicar filtros: {e}')
            return None

    def navegar_para_iframe_form_app(self):
        """
        Navega para o iframe form-app onde está o formulário de decisão
        Implementa duas abordagens: mudança de contexto ou navegação direta para URL
        """
        print('=== INÍCIO navegar_para_iframe_form_app ===')
        
        try:
            # Abordagem 1: Tentar navegar para o iframe
            print('[AGUARDE] Tentando encontrar iframe...')
            
            # Procurar por diferentes IDs possíveis do iframe
            iframe_selectors = [
                "iframe-form-app",  # ID específico mencionado pelo usuário
                "form-app",         # ID original
                "iframe[src*='form-web']",  # Qualquer iframe com form-web na URL
                "iframe[title='form-app']"  # Iframe com title form-app
            ]
            
            iframe_encontrado = None
            iframe_src = None
            
            for selector in iframe_selectors:
                try:
                    if selector.startswith("iframe["):
                        iframe = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                    else:
                        iframe = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.ID, selector))
                        )
                    
                    iframe_src = iframe.get_attribute('src')
                    if iframe_src and 'form-web' in iframe_src:
                        iframe_encontrado = iframe
                        print(f'[OK] Iframe encontrado: {selector}')
                        print(f'[LINK] URL do iframe: {iframe_src}')
                        break
                        
                except TimeoutException:
                    continue
            
            if iframe_encontrado:
                # Abordagem 1: Navegar para dentro do iframe
                print('[INFO] Tentando abordagem 1: mudança de contexto para iframe')
                try:
                    self.driver.switch_to.frame(iframe_encontrado)
                    print('[OK] Contexto mudado para iframe')
                    
                    # Aguardar conteúdo carregar
                    time.sleep(3)
                    
                    # Verificar se conseguimos acessar elementos do formulário
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        print('[OK] Conteúdo do iframe carregado')
                        return True
                    except TimeoutException:
                        print('[AVISO] Iframe não carregou conteúdo, tentando abordagem 2')
                        self.driver.switch_to.default_content()
                        
                except Exception as e:
                    print(f'[AVISO] Falha na abordagem 1: {e}')
                    self.driver.switch_to.default_content()
            
            # Abordagem 2: Navegar diretamente para a URL do iframe
            if iframe_src and 'form-web' in iframe_src:
                print('[INFO] Tentando abordagem 2: navegação direta para URL do iframe')
                print(f'[WEB] Navegando para: {iframe_src}')
                
                # Abrir nova aba ou navegar diretamente
                self.driver.get(iframe_src)
                time.sleep(3)
                
                # Verificar se chegamos na página correta
                current_url = self.driver.current_url
                if 'form-web' in current_url:
                    print('[OK] Navegação direta bem-sucedida')
                    return True
                else:
                    print(f'[AVISO] URL inesperada: {current_url}')
            
            # Se chegou aqui, tentar buscar iframe novamente com mais tempo
            print('[INFO] Tentando buscar iframe com mais tempo...')
            iframe = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "iframe"))
            )
            iframe_src = iframe.get_attribute('src')
            print(f'[INFO] Iframe genérico encontrado: {iframe_src}')
            
            if iframe_src and ('form-web' in iframe_src or 'form-app' in iframe_src):
                self.driver.switch_to.frame(iframe)
                print('[OK] Navegação para iframe genérico concluída')
                time.sleep(3)
                return True
            
            return False
            
        except TimeoutException:
            print('[ERRO] Timeout: nenhum iframe encontrado')
            return False
        except Exception as e:
            print(f'[ERRO] Erro ao navegar para iframe: {e}')
            return False

    def extrair_valor_dnnr_dec(self):
        """
        Extrai o valor do campo DNNR_DEC para determinar a decisão
        Igual à lógica da aprovação do conteúdo de recurso
        """
        print('=== INÍCIO extrair_valor_dnnr_dec ===')
        
        try:
            # Aguardar formulário carregar
            time.sleep(2)
            
            # Procurar pelo campo DNNR_DEC
            dnnr_element = None
            selectors = [
                '#DNNR_DEC',
                'input[name="DNNR_DEC"]',
                'input[id="DNNR_DEC"]'
            ]
            
            for selector in selectors:
                try:
                    dnnr_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except TimeoutException:
                    continue
            
            if not dnnr_element:
                print('[ERRO] Campo DNNR_DEC não encontrado')
                return None
            
            # Extrair valor do campo
            valor_dnnr = dnnr_element.get_attribute('value') or dnnr_element.get_attribute('title') or ''
            valor_dnnr = valor_dnnr.strip()
            
            print(f'[OK] Campo DNNR_DEC encontrado: "{valor_dnnr}"')
            return valor_dnnr
            
        except Exception as e:
            print(f'[ERRO] Erro ao extrair DNNR_DEC: {e}')
            return None

    def determinar_decisao_por_dnnr(self, valor_dnnr):
        """
        Determina a decisão baseada no valor do campo DNNR_DEC
        Segue a mesma lógica da aprovação do conteúdo de recurso
        """
        print(f'=== INÍCIO determinar_decisao_por_dnnr ===')
        print(f'[INFO] Valor DNNR_DEC: "{valor_dnnr}"')
        
        if not valor_dnnr:
            print('[AVISO] Valor DNNR_DEC vazio - não é possível determinar decisão')
            return None
        
        valor_lower = valor_dnnr.lower()
        
        # Lógica igual à aprovação do conteúdo de recurso:
        # Se contém "indeferimento" ou "arquivamento" → Nego Provimento
        # Se contém "reconsideração" → Dou Provimento
        
        if any(palavra in valor_lower for palavra in ['indeferimento', 'arquivamento', 'manutenção']):
            decisao = 'Nego Provimento'
            print(f'[OK] Decisão determinada: {decisao} (baseado em indeferimento/arquivamento)')
            return decisao
        
        elif any(palavra in valor_lower for palavra in ['reconsideração', 'reconsidera']):
            decisao = 'Dou Provimento'
            print(f'[OK] Decisão determinada: {decisao} (baseado em reconsideração)')
            return decisao
        
        else:
            print(f'[AVISO] Não foi possível determinar decisão para: "{valor_dnnr}"')
            return None

    def processar_decisao_recurso(self):
        """
        Processa a decisão do recurso baseado no campo DNNR_DEC
        Segue a mesma lógica da aprovação do conteúdo de recurso
        """
        print('=== INÍCIO processar_decisao_recurso ===')
        
        try:
            # Aguardar formulário carregar
            time.sleep(2)
            
            # Extrair valor do campo DNNR_DEC
            valor_dnnr = self.extrair_valor_dnnr_dec()
            
            if not valor_dnnr:
                print('[ERRO] Não foi possível extrair valor do campo DNNR_DEC')
                return None
            
            # Determinar decisão baseada no DNNR_DEC
            decisao = self.determinar_decisao_por_dnnr(valor_dnnr)
            
            if not decisao:
                print('[ERRO] Não foi possível determinar decisão - processo não será processado')
                return None
            
            # Marcar radio button e clicar no botão correspondente
            # (O botão de ação já envia o formulário automaticamente)
            decisao_aplicada = self.marcar_radio_e_clicar_botao_decisao(decisao)
            
            resultado = {
                'decisao': decisao,
                'valor_dnnr': valor_dnnr,
                'radio_marcado': decisao_aplicada,
                'formulario_enviado': decisao_aplicada  # Se radio foi marcado e botão clicado, formulário foi enviado
            }
            
            print(f'[OK] Decisão processada: {resultado}')
            return resultado
            
        except Exception as e:
            print(f'[ERRO] Erro ao processar decisão: {e}')
            return None


    def marcar_radio_e_clicar_botao_decisao(self, decisao):
        """
        Marca o radio button da decisão final CGPMIG e clica no botão correspondente
        Exatamente igual à lógica da aprovação do conteúdo de recurso
        """
        print(f'=== INÍCIO marcar_radio_e_clicar_botao_decisao ===')
        print(f'[DECISAO] Processando decisão: {decisao}')
        
        try:
            if decisao == "Nego Provimento":
                print('[BUSCA] Campo indica: Nego Provimento')
                print('[TARGET] Processo: 1) Selecionar radio button "Nego Provimento" 2) Clicar no botão de ação')
                
                try:
                    # PASSO 1: Selecionar o radio button primeiro
                    print('[INFO] Passo 1: Selecionando radio button "Nego Provimento"...')
                    
                    # Tentar diferentes seletores para o radio button
                    seletores_radio_nego = [
                        "label[for='CGPMIG_DEC_1']",  # Seletor específico 
                        "input[name='CGPMIG_DEC'][value='Nego Provimento']",
                        "input[id='CGPMIG_DEC_1']"
                    ]
                    
                    radio_marcado = False
                    for seletor in seletores_radio_nego:
                        try:
                            if seletor.startswith('label'):
                                opcao_nego = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                                )
                            else:
                                opcao_nego = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                                )
                            
                            opcao_nego.click()
                            print(f'[OK] Radio button "Nego Provimento" selecionado (seletor: {seletor})')
                            radio_marcado = True
                            break
                        except:
                            continue
                    
                    if not radio_marcado:
                        print('[ERRO] Não foi possível marcar radio button "Nego Provimento"')
                        return False
                    
                    # Aguardar um momento para a interface atualizar
                    time.sleep(2)
                    
                    # PASSO 2: Procurar e clicar no botão de ação "Negar Provimento"
                    print('[BUSCA] Passo 2: Procurando botão de ação "Negar Provimento"...')
                    
                    # Múltiplas estratégias para encontrar o botão
                    seletores_botao_nego = [
                        "a.rejeitar",  # Classe específica
                        "a#rejeitar",  # ID específico
                        "a.button-danger.red",  # Por classes CSS
                        "a.button.btn.waves-effect.waves-light.button-danger.red",  # Classe completa
                        "a[id='rejeitar']"  # Por atributo ID
                    ]
                    
                    botao_acao = None
                    for seletor in seletores_botao_nego:
                        try:
                            botao_acao = self.driver.find_element(By.CSS_SELECTOR, seletor)
                            if botao_acao and botao_acao.is_displayed() and botao_acao.is_enabled():
                                texto_botao = botao_acao.text.strip()
                                print(f'[BUSCA] Botão encontrado com seletor "{seletor}": "{texto_botao}"')
                                if 'Negar Provimento' in texto_botao or 'Nego Provimento' in texto_botao:
                                    print(f'[OK] Botão de ação "Negar Provimento" confirmado!')
                                    break
                            botao_acao = None
                        except:
                            continue
                    
                    # Se não encontrou pelos seletores, buscar por texto
                    if not botao_acao:
                        print('[BUSCA] Buscando botão por texto "Negar Provimento"...')
                        xpath_textos = [
                            "//a[contains(text(), 'Negar Provimento')]",
                            "//a[contains(text(), 'Nego Provimento')]"
                        ]
                        for xpath in xpath_textos:
                            try:
                                botao_acao = self.driver.find_element(By.XPATH, xpath)
                                if botao_acao and botao_acao.is_displayed():
                                    print(f'[OK] Botão encontrado por XPath: "{xpath}"')
                                    break
                            except:
                                continue
                    
                    if not botao_acao:
                        print('[ERRO] Botão de ação "Negar Provimento" não encontrado')
                        return False
                    
                    # Clicar no botão de ação
                    print('[CLIQUE] Clicando no botão de ação "Negar Provimento"...')
                    try:
                        botao_acao.click()
                        print('[OK] Clique normal no botão de ação executado')
                    except Exception as e:
                        print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                        self.driver.execute_script("arguments[0].click();", botao_acao)
                        print('[OK] Clique via JavaScript no botão de ação executado')
                    
                    print(f'[OK] Decisão aplicada: {decisao}')
                    
                    # Aguardar o botão "Voltar" aparecer antes de continuar
                    print('[AGUARDE] Aguardando botão "Voltar" aparecer para continuar para próximo processo...')
                    if self.aguardar_botao_voltar():
                        print('[OK] Botão "Voltar" detectado - Pode continuar para próximo processo!')
                        return True
                    else:
                        print('[AVISO] Timeout ao aguardar botão "Voltar", mas decisão foi aplicada')
                        return True
                    
                except Exception as e:
                    print(f'[ERRO] Erro no processo de "Nego Provimento": {e}')
                    return False
                    
            elif decisao == "Dou Provimento":
                print('[BUSCA] Campo indica: Dou Provimento')
                print('[TARGET] Processo: 1) Selecionar radio button "Dou Provimento" 2) Clicar no botão de ação')
                
                try:
                    # PASSO 1: Selecionar o radio button primeiro
                    print('[INFO] Passo 1: Selecionando radio button "Dou Provimento"...')
                    
                    # Tentar diferentes seletores para o radio button
                    seletores_radio_dou = [
                        "label[for='CGPMIG_DEC_0']",  # Seletor específico
                        "input[name='CGPMIG_DEC'][value='Dou Provimento']",
                        "input[id='CGPMIG_DEC_0']"
                    ]
                    
                    radio_marcado = False
                    for seletor in seletores_radio_dou:
                        try:
                            if seletor.startswith('label'):
                                opcao_dou = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                                )
                            else:
                                opcao_dou = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.CSS_SELECTOR, seletor))
                                )
                            
                            opcao_dou.click()
                            print(f'[OK] Radio button "Dou Provimento" selecionado (seletor: {seletor})')
                            radio_marcado = True
                            break
                        except:
                            continue
                    
                    if not radio_marcado:
                        print('[ERRO] Não foi possível marcar radio button "Dou Provimento"')
                        return False
                    
                    # Aguardar um momento para a interface atualizar
                    time.sleep(2)
                    
                    # PASSO 2: Procurar e clicar no botão de ação "Dou Provimento"
                    print('[BUSCA] Passo 2: Procurando botão de ação "Dou Provimento"...')
                    
                    # Múltiplas estratégias para encontrar o botão (classes podem ser diferentes)
                    seletores_botao_dou = [
                        "a.button.btn:not(.rejeitar)",  # Botão que não seja rejeitar
                        "a.button.btn.waves-effect:not(.button-danger)",  # Botão que não seja danger
                        "a.button[type='submit']:not(.rejeitar)",  # Submit que não seja rejeitar
                        "a.button.btn.waves-effect.waves-light:not(.red)"  # Botão que não seja vermelho
                    ]
                    
                    botao_acao = None
                    for seletor in seletores_botao_dou:
                        try:
                            botoes = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                            for botao in botoes:
                                if botao and botao.is_displayed() and botao.is_enabled():
                                    texto_botao = botao.text.strip()
                                    print(f'[BUSCA] Botão candidato: "{texto_botao}" (seletor: {seletor})')
                                    if 'Dou Provimento' in texto_botao or 'Dar Provimento' in texto_botao:
                                        botao_acao = botao
                                        print(f'[OK] Botão de ação "Dou Provimento" confirmado!')
                                        break
                            if botao_acao:
                                break
                        except:
                            continue
                    
                    # Se não encontrou pelos seletores, buscar por texto
                    if not botao_acao:
                        print('[BUSCA] Buscando botão por texto "Dou Provimento"...')
                        xpath_textos = [
                            "//a[contains(text(), 'Dou Provimento')]",
                            "//a[contains(text(), 'Dar Provimento')]"
                        ]
                        for xpath in xpath_textos:
                            try:
                                botao_acao = self.driver.find_element(By.XPATH, xpath)
                                if botao_acao and botao_acao.is_displayed():
                                    print(f'[OK] Botão encontrado por XPath: "{xpath}"')
                                    break
                            except:
                                continue
                    
                    if not botao_acao:
                        print('[ERRO] Botão de ação "Dou Provimento" não encontrado')
                        return False
                    
                    # Clicar no botão de ação
                    print('[CLIQUE] Clicando no botão de ação "Dou Provimento"...')
                    try:
                        botao_acao.click()
                        print('[OK] Clique normal no botão de ação executado')
                    except Exception as e:
                        print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                        self.driver.execute_script("arguments[0].click();", botao_acao)
                        print('[OK] Clique via JavaScript no botão de ação executado')
                    
                    print(f'[OK] Decisão aplicada: {decisao}')
                    
                    # Aguardar o botão "Voltar" aparecer antes de continuar (igual ao "Nego Provimento")
                    print('[AGUARDE] Aguardando botão "Voltar" aparecer para continuar para próximo processo...')
                    if self.aguardar_botao_voltar():
                        print('[OK] Botão "Voltar" detectado - Pode continuar para próximo processo!')
                        return True
                    else:
                        print('[AVISO] Timeout ao aguardar botão "Voltar", mas decisão foi aplicada')
                        print('[NOTA] Tentando recuperação...')
                        
                        # Fallback: Tentar clicar no botão "Voltar" se estiver disponível
                        if self.tentar_clicar_voltar():
                            print('[OK] Botão "Voltar" clicado com sucesso na recuperação')
                            time.sleep(2)  # Aguardar navegação
                            return True
                        else:
                            print('[AVISO] Botão "Voltar" não encontrado na recuperação')
                            
                        # Se não conseguiu voltar, tentar navegar diretamente para workspace
                        if self.navegar_para_workspace():
                            print('[OK] Navegação direta para workspace realizada')
                            return True
                        else:
                            print('[AVISO] Falha na navegação para workspace')
                            print('[NOTA] Decisão foi aplicada, mas pode ser necessário intervenção manual')
                            return True
                    
                except Exception as e:
                    print(f'[ERRO] Erro no processo de "Dou Provimento": {e}')
                    return False
            else:
                print(f'[ERRO] Decisão não reconhecida: {decisao}')
                return False
            
        except Exception as e:
            print(f'[ERRO] Erro ao processar decisão: {e}')
            return False

    def aguardar_confirmacao_proxima_atividade(self):
        """
        Aguarda a confirmação da próxima atividade através de mudança no HTML
        Detecta quando aparece: "Próxima atividade: Defere ou Indefere Recurso"
        """
        try:
            print('[AGUARDE] Aguardando mudança no HTML para identificar próxima atividade...')
            print('[BUSCA] Monitorando mudanças na página por até 30 segundos...')
            
            tempo_limite = 30
            tempo_inicio = time.time()
            contador_verificacoes = 0
            
            while time.time() - tempo_inicio < tempo_limite:
                contador_verificacoes += 1
                tempo_decorrido = int(time.time() - tempo_inicio)
                
                # Log a cada 5 segundos
                if tempo_decorrido % 5 == 0 and tempo_decorrido > 0:
                    print(f'[BUSCA] Verificando HTML... {tempo_decorrido}s (verificação #{contador_verificacoes})')
                
                try:
                    # Aguardar elementos com WebDriverWait para maior precisão
                    elementos_encontrados = WebDriverWait(self.driver, 2).until(
                        lambda driver: driver.find_elements(By.XPATH, "//*[contains(text(), 'Próxima atividade') or contains(@aria-label, 'Próxima atividade')]")
                    )
                    
                    if elementos_encontrados:
                        for elemento in elementos_encontrados:
                            try:
                                # Verificar se elemento está visível
                                if not elemento.is_displayed():
                                    continue
                                    
                                # Extrair texto de múltiplas formas
                                textos_possiveis = [
                                    elemento.text,
                                    elemento.get_attribute('aria-label'),
                                    elemento.get_attribute('textContent'),
                                    elemento.get_attribute('innerText')
                                ]
                                
                                for texto in textos_possiveis:
                                    if texto and 'Próxima atividade' in texto:
                                        # Verificar se contém as palavras-chave específicas
                                        texto_limpo = texto.strip().lower()
                                        if ('defere' in texto_limpo or 'indefere' in texto_limpo) and 'recurso' in texto_limpo:
                                            print(f'[OK] Próxima atividade detectada via HTML!')
                                            print(f'[INFO] Texto encontrado: "{texto.strip()}"')
                                            print(f'[TEMPO] Tempo decorrido: {tempo_decorrido}s')
                                            return True
                                        elif 'defere' in texto_limpo or 'indefere' in texto_limpo:
                                            print(f'[BUSCA] Possível match parcial: "{texto.strip()}"')
                                            
                            except Exception as elem_e:
                                continue
                    
                    # Se não encontrou ainda, aguardar um pouco antes da próxima verificação
                    time.sleep(1)
                    
                except Exception as wait_e:
                    time.sleep(0.5)
                    continue
            
            print(f'[AVISO] Timeout após {tempo_limite}s - Próxima atividade não detectada via HTML')
            return False
            
        except Exception as e:
            print(f'[ERRO] Erro ao aguardar confirmação via HTML: {e}')
            return False

    def aguardar_botao_voltar(self, timeout=15):
        """
        Aguarda especificamente o botão "Voltar" aparecer na página
        Conforme o usuário, ele aparece após cerca de 10 segundos
        """
        try:
            print('[AGUARDE] Aguardando botão "Voltar" aparecer...')
            print(f'[TIMEOUT] Tempo limite: {timeout} segundos')
            
            tempo_inicio = time.time()
            
            # Seletores para o botão "Voltar"
            seletores_voltar = [
                "a.btn-back",  # Classe específica mencionada pelo usuário
                "a.button.btn.waves-effect.waves-light.btn-back",
                "a[class*='btn-back']",
                "//a[contains(@class, 'btn-back')]",
                "//a[contains(text(), 'Voltar')]"
            ]
            
            while time.time() - tempo_inicio < timeout:
                tempo_decorrido = int(time.time() - tempo_inicio)
                
                # Log a cada 3 segundos
                if tempo_decorrido % 3 == 0 and tempo_decorrido > 0:
                    print(f'[BUSCA] Aguardando botão "Voltar"... {tempo_decorrido}s')
                
                for seletor in seletores_voltar:
                    try:
                        if seletor.startswith('//'):
                            # XPath
                            botao_voltar = self.driver.find_element(By.XPATH, seletor)
                        else:
                            # CSS Selector
                            botao_voltar = self.driver.find_element(By.CSS_SELECTOR, seletor)
                        
                        if botao_voltar and botao_voltar.is_displayed() and botao_voltar.is_enabled():
                            tempo_real = int(time.time() - tempo_inicio)
                            print(f'[OK] Botão "Voltar" apareceu após {tempo_real}s!')
                            print(f'[ELEMENTO] Seletor usado: {seletor}')
                            print(f'[ELEMENTO] Texto do botão: "{botao_voltar.text.strip()}"')
                            return True
                    except:
                        continue
                
                # Aguardar um pouco antes da próxima verificação
                time.sleep(0.5)
            
            print(f'[TIMEOUT] Botão "Voltar" não apareceu em {timeout}s')
            return False
            
        except Exception as e:
            print(f'[ERRO] Erro ao aguardar botão "Voltar": {e}')
            return False

    def tentar_clicar_voltar(self):
        """
        Tenta clicar no botão "Voltar" se estiver disponível
        """
        try:
            print('[BUSCA] Procurando botão "Voltar"...')
            
            # Múltiplas estratégias para encontrar o botão "Voltar"
            seletores_voltar = [
                "a.btn-back",  # Classe específica
                "a.button.btn.waves-effect.waves-light.btn-back",  # Classe completa
                "a[class*='btn-back']",  # Contém btn-back
                "//a[contains(@class, 'btn-back')]",  # XPath por classe
                "//a[contains(text(), 'Voltar')]",  # XPath por texto
                "//a[contains(., 'Voltar')]"  # XPath por conteúdo
            ]
            
            for seletor in seletores_voltar:
                try:
                    if seletor.startswith('//'):
                        # XPath
                        botao_voltar = self.driver.find_element(By.XPATH, seletor)
                    else:
                        # CSS Selector
                        botao_voltar = self.driver.find_element(By.CSS_SELECTOR, seletor)
                    
                    if botao_voltar and botao_voltar.is_displayed() and botao_voltar.is_enabled():
                        texto_botao = botao_voltar.text.strip()
                        print(f'[OK] Botão "Voltar" encontrado: "{texto_botao}" (seletor: {seletor})')
                        
                        # Clicar no botão
                        try:
                            botao_voltar.click()
                            print('[OK] Clique normal no botão "Voltar" executado')
                            return True
                        except Exception as e:
                            print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                            self.driver.execute_script("arguments[0].click();", botao_voltar)
                            print('[OK] Clique via JavaScript no botão "Voltar" executado')
                            return True
                except:
                    continue
            
            print('[ERRO] Botão "Voltar" não encontrado com nenhum seletor')
            return False
            
        except Exception as e:
            print(f'[ERRO] Erro ao tentar clicar no botão "Voltar": {e}')
            return False
    
    def navegar_para_workspace(self):
        """
        Navega diretamente para o workspace principal
        """
        try:
            print('[WEB] Navegando diretamente para workspace...')
            workspace_url = 'https://justica.servicos.gov.br/workspace'
            self.driver.get(workspace_url)
            
            # Aguardar carregamento
            time.sleep(3)
            
            # Verificar se chegou no workspace
            current_url = self.driver.current_url
            if 'workspace' in current_url:
                print('[OK] Navegação para workspace concluída')
                return True
            else:
                print(f'[AVISO] URL inesperada após navegação: {current_url}')
                return False
                
        except Exception as e:
            print(f'[ERRO] Erro ao navegar para workspace: {e}')
            return False

    def enviar_formulario(self):
        """
        Envia o formulário de decisão
        """
        print('=== INÍCIO enviar_formulario ===')
        
        try:
            # Procurar por botão de envio
            seletores_botao = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:contains("Enviar")',
                'button:contains("Salvar")',
                'button:contains("Confirmar")',
                '.btn-primary',
                '.btn-success'
            ]
            
            botao_encontrado = False
            
            for seletor in seletores_botao:
                try:
                    botao = self.driver.find_element(By.CSS_SELECTOR, seletor)
                    if botao.is_enabled():
                        if not self.modo_teste:
                            botao.click()
                            print('[OK] Formulário enviado (PRODUÇÃO)')
                        else:
                            print('[TESTE] Formulário seria enviado (MODO TESTE)')
                        botao_encontrado = True
                        break
                except:
                    continue
            
            if not botao_encontrado:
                print('[AVISO] Botão de envio não encontrado')
                return False
            
            # Aguardar processamento
            time.sleep(3)
            return True
            
        except Exception as e:
            print(f'[ERRO] Erro ao enviar formulário: {e}')
            return False

    def extrair_url_iframe(self):
        """
        Extrai a URL do iframe form-web para navegação direta
        """
        try:
            print('[INFO] Extraindo URL do iframe...')
            
            # Procurar iframe com form-web
            iframe_selectors = [
                "iframe-form-app",
                "iframe[src*='form-web']",
                "iframe[title='form-app']"
            ]
            
            for selector in iframe_selectors:
                try:
                    if selector.startswith("iframe["):
                        iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                    else:
                        iframe = self.driver.find_element(By.ID, selector)
                    
                    iframe_src = iframe.get_attribute('src')
                    if iframe_src and 'form-web' in iframe_src:
                        print(f'[OK] URL do iframe extraída: {iframe_src}')
                        return iframe_src
                        
                except:
                    continue
            
            print('[AVISO] URL do iframe não encontrada')
            return None
            
        except Exception as e:
            print(f'[ERRO] Erro ao extrair URL do iframe: {e}')
            return None

    def navegar_diretamente_para_formulario(self):
        """
        Método alternativo: navega diretamente para a URL do iframe
        """
        try:
            print('[INFO] Tentando navegação direta para formulário...')
            
            # Extrair URL do iframe
            iframe_url = self.extrair_url_iframe()
            
            if iframe_url:
                print(f'[WEB] Navegando diretamente para: {iframe_url}')
                self.driver.get(iframe_url)
                time.sleep(3)
                
                # Verificar se chegamos na página correta
                current_url = self.driver.current_url
                if 'form-web' in current_url:
                    print('[OK] Navegação direta para formulário bem-sucedida')
                    return True
                else:
                    print(f'[AVISO] URL inesperada após navegação: {current_url}')
            
            return False
            
        except Exception as e:
            print(f'[ERRO] Erro na navegação direta: {e}')
            return False

    def voltar_do_iframe(self):
        """
        Volta do iframe para a página principal
        """
        try:
            self.driver.switch_to.default_content()
            print('[OK] Retorno do iframe concluído')
        except Exception as e:
            print(f'[AVISO] Erro ao voltar do iframe: {e}')

    def processar_processo_completo(self, codigo_processo):
        """
        Processa um único processo de forma completa
        """
        print(f'\n=== PROCESSANDO PROCESSO: {codigo_processo} ===')
        
        resultado = {
            'codigo': codigo_processo,
            'status': 'erro',
            'decisao': '',
            'valor_dnnr': '',
            'decisao_enviada': False,
            'erro': ''
        }
        
        try:
            # 1. Aplicar filtros e navegar para processo
            print(f'[BUSCA] Etapa 1: Aplicando filtros para processo {codigo_processo}')
            if not self.aplicar_filtros(codigo_processo):
                print(f'[ERRO] Falha na aplicação de filtros para {codigo_processo}')
                resultado['erro'] = 'Falha na aplicação de filtros'
                return resultado
            print(f'[OK] Filtros aplicados e navegação para processo concluída')
            
            # 2. Navegar para iframe (com fallback para navegação direta)
            print(f'[IFRAME] Etapa 2: Navegando para iframe form-app')
            iframe_sucesso = self.navegar_para_iframe_form_app()
            
            if not iframe_sucesso:
                print(f'[INFO] Tentando navegação direta como alternativa...')
                iframe_sucesso = self.navegar_diretamente_para_formulario()
            
            if not iframe_sucesso:
                print(f'[ERRO] Falha na navegação para formulário (iframe e direta)')
                resultado['erro'] = 'Falha na navegação para formulário'
                return resultado
            print(f'[OK] Navegação para formulário concluída')
            
            # 3. Processar decisão
            print(f'[DECISAO] Etapa 3: Processando decisão do recurso')
            resultado_decisao = self.processar_decisao_recurso()
            if resultado_decisao:
                resultado['decisao'] = resultado_decisao['decisao']
                resultado['valor_dnnr'] = resultado_decisao['valor_dnnr']
                # Decisão enviada = radio marcado E formulário enviado
                resultado['decisao_enviada'] = resultado_decisao.get('radio_marcado', False) and resultado_decisao.get('formulario_enviado', False)
                resultado['status'] = 'sucesso'
                print(f'[OK] Processo {codigo_processo} processado com sucesso: {resultado_decisao["decisao"]}')
                print(f'[INFO] Campo DNNR_DEC: "{resultado_decisao["valor_dnnr"]}"')
                print(f'[INFO] Decisão enviada: {resultado["decisao_enviada"]}')
            else:
                print(f'[ERRO] Falha no processamento da decisão para {codigo_processo}')
                resultado['erro'] = 'Falha no processamento da decisão'
            
            # 4. Voltar do iframe
            print(f'[VOLTA] Etapa 4: Voltando do iframe')
            self.voltar_do_iframe()
            print(f'[OK] Retorno do iframe concluído')
            
            # 5. Pausa entre processos (apenas se decisão foi processada com sucesso)
            if resultado['status'] == 'sucesso':
                print(f'[TEMPO] Etapa 5: Aguardando 2 segundos antes do próximo processo...')
                time.sleep(2)
                print(f'[OK] Pausa concluída - Sistema pronto para próximo processo')
            
        except Exception as e:
            resultado['erro'] = str(e)
            print(f'[ERRO] Erro no processamento do processo {codigo_processo}: {e}')
            # Garantir que volta do iframe em caso de erro
            try:
                self.voltar_do_iframe()
                print(f'[OK] Retorno do iframe (recuperação) concluído')
            except Exception as e2:
                print(f'[AVISO] Erro ao voltar do iframe na recuperação: {e2}')
        
        print(f'[DADOS] Resultado final para {codigo_processo}: {resultado["status"]}')
        return resultado

    def processar_planilha_completa(self, caminho_planilha, nome_coluna_codigo='codigo'):
        """
        Processa todos os códigos da planilha
        """
        print(f'[DADOS] Iniciando processamento da planilha: {caminho_planilha}')
        
        # Ler códigos da planilha
        codigos = self.ler_planilha_codigos(caminho_planilha, nome_coluna_codigo)
        if not codigos:
            print('[ERRO] Nenhum código encontrado na planilha')
            return
        
        print(f'[INFO] Processando {len(codigos)} códigos...')
        
        # Fazer login se necessário
        if not self.ja_logado:
            if not self.login():
                print('[ERRO] Falha no login')
                return
        
        # Processar cada código
        for i, codigo in enumerate(codigos, 1):
            print(f'\n--- Processo {i}/{len(codigos)} ---')
            resultado = self.processar_processo_completo(codigo)
            self.resultados.append(resultado)
            
            # Salvar resultado a cada processo
            self.salvar_resultados_parciais(caminho_planilha, i)
            
            # Pequena pausa entre processos
            time.sleep(2)
        
        # Salvar resultados finais
        self.salvar_resultados_finais(caminho_planilha)
        print(f'\n[OK] Processamento concluído! {len(self.resultados)} processos processados')

    def salvar_resultados_parciais(self, caminho_planilha, processo_atual):
        """
        Salva resultados parciais a cada processo
        """
        try:
            # Criar DataFrame com resultados
            df_resultados = pd.DataFrame(self.resultados)
            
            # Reordenar colunas para melhor visualização
            colunas_ordenadas = ['codigo', 'decisao', 'valor_dnnr', 'decisao_enviada', 'status', 'erro']
            colunas_existentes = [col for col in colunas_ordenadas if col in df_resultados.columns]
            if colunas_existentes:
                df_resultados = df_resultados[colunas_existentes]
            
            # Nome do arquivo de resultados
            nome_base = os.path.splitext(os.path.basename(caminho_planilha))[0]
            arquivo_resultado = f"{nome_base}_resultados_defere_indefere_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # Salvar na mesma pasta da planilha original
            pasta_planilha = os.path.dirname(caminho_planilha)
            caminho_resultado = os.path.join(pasta_planilha, arquivo_resultado)
            
            df_resultados.to_excel(caminho_resultado, index=False)
            print(f'[SALVO] Resultados parciais salvos: {caminho_resultado} ({processo_atual} processos)')
            
        except Exception as e:
            print(f'[AVISO] Erro ao salvar resultados parciais: {e}')

    def salvar_resultados_finais(self, caminho_planilha):
        """
        Salva resultados finais do processamento
        """
        try:
            # Criar DataFrame com resultados
            df_resultados = pd.DataFrame(self.resultados)
            
            # Reordenar colunas para melhor visualização
            colunas_ordenadas = ['codigo', 'decisao', 'valor_dnnr', 'decisao_enviada', 'status', 'erro']
            colunas_existentes = [col for col in colunas_ordenadas if col in df_resultados.columns]
            if colunas_existentes:
                df_resultados = df_resultados[colunas_existentes]
            
            # Nome do arquivo de resultados finais
            nome_base = os.path.splitext(os.path.basename(caminho_planilha))[0]
            arquivo_resultado = f"{nome_base}_resultados_defere_indefere_FINAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # Salvar na mesma pasta da planilha original
            pasta_planilha = os.path.dirname(caminho_planilha)
            caminho_resultado = os.path.join(pasta_planilha, arquivo_resultado)
            
            df_resultados.to_excel(caminho_resultado, index=False)
            
            # Estatísticas
            total = len(self.resultados)
            sucessos = len([r for r in self.resultados if r['status'] == 'sucesso'])
            erros = total - sucessos
            
            print(f'\n[DADOS] RELATÓRIO FINAL:')
            print(f'   [PASTA] Arquivo: {caminho_resultado}')
            print(f'   [INFO] Total de processos: {total}')
            print(f'   [OK] Sucessos: {sucessos}')
            print(f'   [ERRO] Erros: {erros}')
            print(f'   [PROGRESS] Taxa de sucesso: {(sucessos/total)*100:.1f}%')
            
        except Exception as e:
            print(f'[ERRO] Erro ao salvar resultados finais: {e}')

    def close(self):
        """
        Fecha o driver do navegador
        """
        try:
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
                print('[FECHADO] Driver fechado com sucesso')
        except Exception as e:
            print(f'[AVISO] Erro ao fechar driver: {e}')
