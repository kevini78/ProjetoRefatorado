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
# Credenciais removidas - login será manual

class AprovacaoConteudoRecurso:
    def __init__(self, driver=None):
        """
        Inicializa o automatizador para aprovação do conteúdo de recurso
        """
        print("[DEBUG] DEBUG: Iniciando construtor AprovacaoConteudoRecurso...")
        
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
        
        print("[OK] DEBUG: Construtor AprovacaoConteudoRecurso concluído com sucesso")
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
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                current_url = self.driver.current_url
                
                # Verificar se chegou no workspace (login bem-sucedido)
                if "workspace" in current_url or "dashboard" in current_url:
                    print('[OK] Login detectado com sucesso!')
                    print(f'[LINK] URL atual: {current_url}')
                    self.ja_logado = True
                    return True
                
                # Log de progresso a cada 10 segundos
                elapsed = int(time.time() - start_time)
                if elapsed % 10 == 0 and elapsed > 0:
                    remaining = timeout - elapsed
                    print(f'[AGUARDE] Aguardando login... {elapsed}s decorridos ({remaining}s restantes)')
                    print(f'📍 URL atual: {current_url}')
                
                # Aguardar 2 segundos antes da próxima verificação
                time.sleep(2)
                
            except Exception as e:
                print(f'[AVISO] Erro durante monitoramento: {e}')
                time.sleep(2)
                continue
        
        # Timeout
        print('[ERRO] Timeout aguardando login manual!')
        print(f'[TEMPO] Tempo limite de {timeout} segundos excedido')
        print('[RELOAD] Você pode tentar novamente fazendo o login e reiniciando o processo')
        return False

    def ler_planilha_codigos(self, caminho_planilha, nome_coluna_codigo='codigo'):
        """
        Lê planilha e extrai códigos dos processos
        Retorna lista de códigos
        """
        print(f'[DADOS] Lendo planilha: {caminho_planilha}')
        
        # Verificar driver antes de iniciar leitura
        try:
            test_url = self.driver.current_url
            print(f'[DEBUG] DEBUG: Driver ativo ANTES da leitura - URL: {test_url}')
        except Exception as e:
            print(f'[ERRO] DEBUG: Driver não está ativo ANTES da leitura: {e}')
            return []
        
        try:
            # Tentar diferentes extensões
            print(f'[DEBUG] DEBUG: Iniciando leitura do arquivo...')
            if caminho_planilha.endswith('.xlsx'):
                df = pd.read_excel(caminho_planilha)
            elif caminho_planilha.endswith('.csv'):
                df = pd.read_csv(caminho_planilha)
            else:
                # Tentar como Excel por padrão
                df = pd.read_excel(caminho_planilha)
            
            print(f'[OK] Planilha carregada com {len(df)} linhas')
            print(f'Colunas disponíveis: {list(df.columns)}')

            # Se a planilha vier com a primeira coluna sem nome ('Unnamed: 0'), assumir como código
            if len(df.columns) == 1 and str(df.columns[0]).startswith('Unnamed'):
                df = df.rename(columns={df.columns[0]: 'codigo'})
                print('[INFO] Primeira coluna sem nome detectada. Renomeada para "codigo"')
            
            # Verificar driver no meio da leitura
            try:
                test_url2 = self.driver.current_url
                print(f'[DEBUG] DEBUG: Driver ativo DURANTE a leitura - URL: {test_url2}')
            except Exception as e:
                print(f'[ERRO] DEBUG: Driver perdido DURANTE a leitura: {e}')
            
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
                        print(f'ℹ️ Coluna de código detectada por heurística: {original}')
                        break
            
            if not coluna_codigo_real:
                # Fallback: usar a primeira coluna como código
                if len(df.columns) >= 1:
                    coluna_codigo_real = df.columns[0]
                    print(f'ℹ️ Usando a primeira coluna como código: {coluna_codigo_real}')
                else:
                    print(f'[ERRO] Coluna "{nome_coluna_codigo}" não encontrada (case-insensitive) e nenhuma coluna semelhante foi detectada!')
                    print(f'Colunas disponíveis: {list(df.columns)}')
                    return []
            else:
                print(f'[OK] Usando coluna de código: {coluna_codigo_real}')
            
            # Extrair códigos preservando ordem da planilha (sem unique), limpando espaços
            print(f'[DEBUG] DEBUG: Extraindo códigos na ordem da planilha...')
            serie_codigos = df[coluna_codigo_real].dropna().astype(str).map(lambda x: x.strip())
            # Normalizar números com separadores de milhar como '770.033' -> '770033'
            serie_codigos = serie_codigos.str.replace('.', '', regex=False).str.replace(',', '', regex=False)
            # Filtrar vazios após strip
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
        Baseado na navegação da NavegacaoOrdinaria, adaptado para Aprovação de Conteúdo de Recurso
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
            print('[BUSCA] Procurando "Aprovação do Conteúdo de Recurso" na tabela...')
            
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

            # Encontrar TODAS as atividades "Aprovação do Conteúdo de Recurso" e pegar a do ciclo mais alto
            aprovacao_recurso_links = []
            
            for link, titulo, href in todos_links:
                try:
                    titulo_lc = titulo.lower()
                    # Procurar por "Aprovação do Conteúdo de Recurso" com /15/ no href
                    if ('/15/' in href) and ('aprovação' in titulo_lc or 'aprovacao' in titulo_lc) and ('conteúdo' in titulo_lc or 'conteudo' in titulo_lc) and 'recurso' in titulo_lc:
                        # Extrair o ciclo da URL usando regex
                        match = regex_module.search(r'/15/(\d+)', href)
                        if match:
                            ciclo = int(match.group(1))
                            aprovacao_recurso_links.append((link, titulo, href, ciclo))
                            print(f"[BUSCA] Encontrou 'Aprovação do Conteúdo de Recurso' ciclo {ciclo}: {href}")
                except Exception as e:
                    print(f"[AVISO] Erro ao processar link: {e}")
                    continue
            
            # Escolher a atividade com ciclo mais alto
            link_escolhido = None
            processInstanceId_escolhido = None
            ciclo_escolhido = None
            
            if aprovacao_recurso_links:
                # Mostrar todos os ciclos encontrados
                print(f"[INFO] Total de atividades 'Aprovação do Conteúdo de Recurso' encontradas: {len(aprovacao_recurso_links)}")
                for i, (_, titulo, href, ciclo) in enumerate(aprovacao_recurso_links, 1):
                    print(f"   {i}. Ciclo {ciclo}: {titulo} -> {href}")
                
                # Ordenar por ciclo descendente (mais alto primeiro)
                aprovacao_recurso_links.sort(key=lambda x: x[3], reverse=True)
                
                # Pegar o primeiro (ciclo mais alto)
                link_escolhido, titulo_escolhido, href_escolhido, ciclo_escolhido = aprovacao_recurso_links[0]
                
                print(f"[TARGET] SELECIONADO: 'Aprovação do Conteúdo de Recurso' com CICLO MAIS ALTO: {ciclo_escolhido}")
                print(f"   [PIN] Título: '{titulo_escolhido}'")
                print(f"   [LINK] URL: {href_escolhido}")
                
                # Armazenar o ciclo para usar na construção da URL do form-web
                self.ciclo_processo = ciclo_escolhido
                print(f"[SALVO] Ciclo {ciclo_escolhido} armazenado para construção da URL do form-web")
                
            else:
                print("[AVISO] Nenhuma atividade 'Aprovação do Conteúdo de Recurso' com /15/ encontrada")
                # Fallback: procurar apenas pelo título
                for link, titulo, href in todos_links:
                    try:
                        titulo_lc = titulo.lower()
                        if ('aprovação' in titulo_lc or 'aprovacao' in titulo_lc) and ('conteúdo' in titulo_lc or 'conteudo' in titulo_lc) and 'recurso' in titulo_lc:
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
                print('[ERRO] "Aprovação do Conteúdo de Recurso" não encontrada na lista de atividades!')
                return None

            # PASSO 3: Clicar na atividade escolhida
            print('[CLIQUE] Clicando na atividade "Aprovação do Conteúdo de Recurso"...')
            
            try:
                link_escolhido.click()
                print('[OK] Clique normal executado')
            except Exception as e:
                print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                self.driver.execute_script("arguments[0].click();", link_escolhido)
                print('[OK] Clique via JavaScript executado')

            # PASSO 4: Aguardar navegação para form-app
            print('[AGUARDE] Aguardando navegação para form-app...')
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.url_contains('/form-app/')
                )
                print('[OK] Navegação detectada!')
            except Exception as e:
                print(f'[AVISO] Timeout aguardando navegação: {e}')
                time.sleep(3)
            
            current_url = self.driver.current_url
            print(f'DEBUG: URL após clique: {current_url}')
            
            if 'form-app' in current_url:
                print('[OK] Navegação para formulário bem-sucedida!')
                if '/15/' in current_url:
                    print('[OK] Confirmado: Atividade 15 (Aprovação do Conteúdo de Recurso)')
                    # Extrair processInstanceId da URL atual
                    match = regex_module.search(r'/form-app/(\d+)/', current_url)
                    if match:
                        self.processInstanceId = match.group(1)
                        print(f"[SALVO] ProcessInstanceId extraído: {self.processInstanceId}")
                else:
                    print(f'ℹ️ Atividade diferente de 15, mas em form-app: {current_url}')
            else:
                print(f'[AVISO] URL após clique não contém form-app: {current_url}')
                print('[RELOAD] Tentando aguardar mais tempo para a navegação...')
                time.sleep(5)
                current_url = self.driver.current_url
                print(f'DEBUG: URL após espera adicional: {current_url}')
            
            return True
            
        except Exception as e:
            print(f'[ERRO] Erro ao navegar para processo: {e}')
            return False

    def navegar_para_iframe_form_app(self):
        """
        Navega para dentro do iframe form-app com URL específica para cada processo
        """
        print('[IFRAME] Navegando para iframe form-app...')
        
        try:
            # MÉTODO 1: Tentar usar iframe existente primeiro
            try:
                iframe = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "iframe-form-app"))
                )
                print('[OK] Iframe form-app encontrado!')
                
                # Verificar se iframe tem src válido
                iframe_src = iframe.get_attribute('src')
                print(f'DEBUG: Iframe src atual: {iframe_src}')
                
                if iframe_src and 'form-web' in iframe_src:
                    print('[OK] Iframe já tem src válido, entrando no contexto...')
                    
                    # Trocar contexto para o iframe
                    self.driver.switch_to.frame(iframe)
                    print('[OK] Contexto trocado para dentro do iframe')
                    
                    # Aguardar conteúdo carregar
                    time.sleep(5)
                    
                    # Verificar se formulário carregou
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    print('[OK] Formulário no iframe carregado!')
                    return True
                    
            except Exception as e:
                print(f'[AVISO] Iframe não encontrado ou sem src válido: {e}')
            
            # MÉTODO 2: Construir URL manualmente e navegar diretamente
            print('[DEBUG] Construindo URL do form-web manualmente...')
            
            if not hasattr(self, 'processInstanceId') or not self.processInstanceId:
                print('[ERRO] processInstanceId não disponível')
                return False
            
            if not hasattr(self, 'ciclo_processo'):
                self.ciclo_processo = 1  # Default
            
            # Construir URL específica para cada processo
            # Formato: https://justica.servicos.gov.br/form-web?processInstanceId=718274&activityInstanceId=15&cycle=1&newWS=true
            iframe_url = f'https://justica.servicos.gov.br/form-web?processInstanceId={self.processInstanceId}&activityInstanceId=15&cycle={self.ciclo_processo}&newWS=true'
            
            print(f'[DEBUG] URL construída para processo específico:')
            print(f'   [INFO] processInstanceId: {self.processInstanceId}')
            print(f'   [TARGET] activityInstanceId: 15 (Aprovação do Conteúdo de Recurso)')
            print(f'   [RELOAD] cycle: {self.ciclo_processo}')
            print(f'   [WEB] URL completa: {iframe_url}')
            
            # Navegar diretamente para a URL do form-web
            print('[EXEC] Navegando diretamente para form-web...')
            self.driver.get(iframe_url)
            
            # Aguardar página carregar
            print('[AGUARDE] Aguardando form-web carregar...')
            time.sleep(5)
            
            # Verificar se chegamos na URL correta
            current_url = self.driver.current_url
            print(f'DEBUG: URL atual após navegação: {current_url}')
            
            if 'form-web' in current_url and self.processInstanceId in current_url:
                print('[OK] Navegação direta para form-web bem-sucedida!')
                
                # Aguardar elementos do formulário carregarem
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    print('[OK] Formulário carregado!')
                    return True
                except Exception as e:
                    print(f'[AVISO] Erro ao aguardar formulário: {e}')
                    return False
                    
            else:
                print(f'[AVISO] URL inesperada após navegação: {current_url}')
                return False
            
        except Exception as e:
            print(f'[ERRO] Erro ao navegar para iframe/form-web: {e}')
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False

    def processar_decisao_recurso(self):
        """
        Processa a decisão do recurso baseada no campo DNNR_DEC
        Retorna um dicionário com a decisão tomada e o valor do campo
        """
        print('[DECISAO] Processando decisão do recurso...')
        
        try:
            # Aguardar formulário carregar
            time.sleep(3)
            
            # Procurar pelo campo DNNR_DEC
            campo_dnnr = None
            try:
                campo_dnnr = self.wait.until(
                    EC.presence_of_element_located((By.ID, "DNNR_DEC"))
                )
                print('[OK] Campo DNNR_DEC encontrado!')
            except:
                print('[ERRO] Campo DNNR_DEC não encontrado')
                return None
            
            # Verificar o valor do campo
            valor_campo = campo_dnnr.get_attribute('value')
            print(f'[INFO] Valor do campo DNNR_DEC: "{valor_campo}"')
            
            decisao = None
            resultado = {
                'decisao': None,
                'valor_dnnr': valor_campo
            }
            
            if 'Propor Manutenção do Indeferimento/Arquivamento' in valor_campo:
                print('[BUSCA] Campo indica: Propor Manutenção do Indeferimento/Arquivamento')
                print('[TARGET] Processo: 1) Selecionar radio button "Nego Provimento" 2) Clicar no botão de ação')
                
                try:
                    # PASSO 1: Selecionar o radio button primeiro
                    print('[INFO] Passo 1: Selecionando radio button "Nego Provimento"...')
                    opcao_nego = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='CPMIGR_DEC_1']"))
                    )
                    opcao_nego.click()
                    print('[OK] Radio button "Nego Provimento" selecionado')
                    
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
                        return None
                    
                    # Clicar no botão de ação
                    print('[CLIQUE] Clicando no botão de ação "Negar Provimento"...')
                    try:
                        botao_acao.click()
                        print('[OK] Clique normal no botão de ação executado')
                    except Exception as e:
                        print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                        self.driver.execute_script("arguments[0].click();", botao_acao)
                        print('[OK] Clique via JavaScript no botão de ação executado')
                    
                    decisao = "Nego Provimento"
                    resultado['decisao'] = decisao
                    print(f'[OK] Decisão aplicada: {decisao}')
                    
                except Exception as e:
                    print(f'[ERRO] Erro no processo de "Nego Provimento": {e}')
                    return None
                    
            elif 'Propor Reconsideração' in valor_campo:
                print('[BUSCA] Campo indica: Propor Reconsideração')
                print('[TARGET] Processo: 1) Selecionar radio button "Dou Provimento" 2) Clicar no botão de ação')
                
                try:
                    # PASSO 1: Selecionar o radio button primeiro
                    print('[INFO] Passo 1: Selecionando radio button "Dou Provimento"...')
                    opcao_dou = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "label[for='CPMIGR_DEC_0']"))
                    )
                    opcao_dou.click()
                    print('[OK] Radio button "Dou Provimento" selecionado')
                    
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
                        return None
                    
                    # Clicar no botão de ação
                    print('[CLIQUE] Clicando no botão de ação "Dou Provimento"...')
                    try:
                        botao_acao.click()
                        print('[OK] Clique normal no botão de ação executado')
                    except Exception as e:
                        print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                        self.driver.execute_script("arguments[0].click();", botao_acao)
                        print('[OK] Clique via JavaScript no botão de ação executado')
                    
                    decisao = "Dou Provimento"
                    resultado['decisao'] = decisao
                    print(f'[OK] Decisão aplicada: {decisao}')
                    print('[AVISO] ATENÇÃO: Decisão "Dou Provimento" pode requerer clique em "Voltar" se ficar presa')
                    
                except Exception as e:
                    print(f'[ERRO] Erro no processo de "Dou Provimento": {e}')
                    return None
            else:
                print(f'[AVISO] Valor do campo não reconhecido: "{valor_campo}"')
                return None
            
            # Verificar modo de operação
            if self.modo_teste:
                print('[TESTE] MODO TESTE: Simulando clique no botão (não será clicado efetivamente)')
                print('[NOTA] Decisão registrada para monitoramento')
                return resultado
            else:
                # MODO PRODUÇÃO: Decisão já foi aplicada via clique no botão
                print('[EXEC] MODO PRODUÇÃO: Decisão aplicada efetivamente!')
                
                # Aguardar confirmação da próxima atividade via mudança do HTML
                print('[BUSCA] Aguardando mudança no HTML antes de continuar para próximo processo...')
                if self.aguardar_confirmacao_proxima_atividade():
                    print('[OK] HTML atualizado - Próxima atividade detectada! Pode continuar para próximo processo.')
                    return resultado
                else:
                    print('[AVISO] Timeout na detecção da próxima atividade via HTML')
                    print('[RELOAD] Tentando soluções de recuperação...')
                    
                    # Tentar clicar no botão "Voltar" se estiver disponível
                    if self.tentar_clicar_voltar():
                        print('[OK] Botão "Voltar" clicado com sucesso')
                        time.sleep(2)  # Aguardar navegação
                        return resultado
                    else:
                        print('[AVISO] Botão "Voltar" não encontrado')
                        
                    # Se não conseguiu voltar, tentar navegar diretamente para workspace
                    if self.navegar_para_workspace():
                        print('[OK] Navegação direta para workspace realizada')
                        return resultado
                    else:
                        print('[AVISO] Falha na navegação para workspace')
                        print('[NOTA] Decisão foi aplicada, mas pode ser necessário intervenção manual')
                        return resultado
            
        except Exception as e:
            print(f'[ERRO] Erro ao processar decisão: {e}')
            return None

    def enviar_formulario(self):
        """
        Envia o formulário após selecionar a decisão
        """
        try:
            print('[BUSCA] Procurando botão de envio...')
            
            # Possíveis seletores para o botão de envio
            seletores_envio = [
                "button[type='submit']",
                "input[type='submit']", 
                "button:contains('Enviar')",
                "button:contains('Salvar')",
                "button:contains('Confirmar')",
                ".btn-primary",
                ".submit-btn"
            ]
            
            botao_envio = None
            for seletor in seletores_envio:
                try:
                    if ':contains(' in seletor:
                        # Para seletores com :contains, usar XPath
                        texto_botao = seletor.split('(')[1].split(')')[0].strip("'")
                        xpath = f"//button[contains(text(), '{texto_botao}')]"
                        botao_envio = self.driver.find_element(By.XPATH, xpath)
                    else:
                        botao_envio = self.driver.find_element(By.CSS_SELECTOR, seletor)
                    
                    if botao_envio and botao_envio.is_enabled():
                        print(f'[OK] Botão de envio encontrado: {seletor}')
                        break
                except:
                    continue
            
            if not botao_envio:
                print('[ERRO] Botão de envio não encontrado')
                return False
            
            # Clicar no botão
            print('[CLIQUE] Clicando no botão de envio...')
            try:
                botao_envio.click()
                print('[OK] Clique normal no botão executado')
            except Exception as e:
                print(f'[AVISO] Clique normal falhou ({e}), tentando JavaScript...')
                # Se clique normal falhar, tentar JavaScript
                self.driver.execute_script("arguments[0].click();", botao_envio)
                print('[OK] Clique via JavaScript executado')
            
            print('[AGUARDE] Aguardando processamento do envio...')
            time.sleep(5)  # Aguardar mais tempo para o processamento inicial
            print('[OK] Tempo de processamento inicial concluído')
            
            return True
            
        except Exception as e:
            print(f'[ERRO] Erro ao enviar formulário: {e}')
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
            print('🏠 Navegando diretamente para workspace...')
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

    def aguardar_confirmacao_proxima_atividade(self):
        """
        Aguarda a confirmação da próxima atividade através de mudança no HTML
        Detecta quando aparece: "Próxima atividade: Defere ou Indefere Recurso"
        Reduzido para 30 segundos conforme solicitado
        """
        try:
            print('[AGUARDE] Aguardando mudança no HTML para identificar próxima atividade...')
            print('[BUSCA] Monitorando mudanças na página por até 30 segundos...')
            
            # Tempo de espera aumentado para 30 segundos conforme solicitado
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
                                            print(f'[BUSCA] Tag HTML: {elemento.tag_name}')
                                            return True
                                        elif 'defere' in texto_limpo or 'indefere' in texto_limpo:
                                            print(f'[BUSCA] Possível match parcial: "{texto.strip()}"')
                                            
                            except Exception as elem_e:
                                continue
                    
                    # Se não encontrou ainda, aguardar um pouco antes da próxima verificação
                    time.sleep(1)
                    
                except Exception as wait_e:
                    # Se WebDriverWait falhou, tentar busca direta mais rápida
                    try:
                        elementos_diretos = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Próxima atividade')]")
                        for elem in elementos_diretos:
                            texto = elem.text or elem.get_attribute('aria-label')
                            if texto and 'Defere' in texto and 'Recurso' in texto:
                                print(f'[OK] Encontrado via busca direta: {texto}')
                                return True
                    except:
                        pass
                    
                    time.sleep(0.5)
                    continue
            
            print(f'[AVISO] Timeout após {tempo_limite}s - Próxima atividade não detectada via HTML')
            print(f'[DADOS] Total de verificações realizadas: {contador_verificacoes}')
            print('[AVISO] Sistema pode estar "preso" aguardando confirmação manual')
            
            # Uma última tentativa mais ampla
            try:
                print('[BUSCA] Última tentativa com busca ampla...')
                todos_elementos = self.driver.find_elements(By.XPATH, "//*")
                elementos_com_texto = [elem for elem in todos_elementos if elem.text and 'atividade' in elem.text.lower()]
                
                if elementos_com_texto:
                    print(f'[BUSCA] Encontrados {len(elementos_com_texto)} elementos com "atividade"')
                    for elem in elementos_com_texto[:5]:  # Verificar apenas os primeiros 5
                        texto = elem.text.strip()
                        if texto:
                            print(f'[DOC] Texto encontrado: "{texto}"')
                            if 'próxima' in texto.lower() and 'defere' in texto.lower():
                                print(f'[OK] Match encontrado na busca ampla!')
                                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f'[ERRO] Erro ao aguardar confirmação via HTML: {e}')
            return False

    def voltar_do_iframe(self):
        """Volta para o contexto principal"""
        try:
            self.driver.switch_to.default_content()
            print('[OK] Voltou para contexto principal')
        except Exception as e:
            print(f'[AVISO] Erro ao voltar do iframe: {e}')

    def processar_processo_completo(self, codigo_processo):
        """
        Processa um processo completo: navegação + decisão
        """
        print(f'\n[RELOAD] Processando processo: {codigo_processo}')
        
        resultado = {
            'codigo': codigo_processo,
            'decisao': None,
            'status': 'erro',
            'erro': None
        }
        
        try:
            # Verificar se driver está ativo
            try:
                current_url = self.driver.current_url
                print(f'[OK] Driver ativo - URL atual: {current_url}')
            except Exception as e:
                print(f'[ERRO] Driver não está ativo: {e}')
                resultado['erro'] = 'Driver não está ativo'
                return resultado
            
            # 1. Aplicar filtros e navegar para o processo
            print(f'[BUSCA] Etapa 1: Aplicando filtros para processo {codigo_processo}')
            resultado_filtros = self.aplicar_filtros(codigo_processo)
            if not resultado_filtros:
                print(f'[ERRO] Falha na aplicação de filtros para o processo {codigo_processo}')
                resultado['erro'] = 'Falha na aplicação de filtros para o processo'
                return resultado
            print(f'[OK] Filtros aplicados e navegação para processo concluída')
            
            # 2. Navegar para iframe
            print(f'[IFRAME] Etapa 2: Navegando para iframe form-app')
            if not self.navegar_para_iframe_form_app():
                print(f'[ERRO] Falha na navegação para iframe')
                resultado['erro'] = 'Falha na navegação para iframe'
                return resultado
            print(f'[OK] Navegação para iframe concluída')
            
            # 3. Processar decisão
            print(f'[DECISAO] Etapa 3: Processando decisão do recurso')
            resultado_decisao = self.processar_decisao_recurso()
            if resultado_decisao:
                resultado['decisao'] = resultado_decisao['decisao']
                resultado['valor_dnnr'] = resultado_decisao['valor_dnnr']
                resultado['status'] = 'sucesso'
                print(f'[OK] Processo {codigo_processo} processado com sucesso: {resultado_decisao["decisao"]}')
                print(f'[INFO] Campo DNNR_DEC: "{resultado_decisao["valor_dnnr"]}"')
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
            # Criar DataFrame com resultados incluindo valor DNNR_DEC
            df_resultados = pd.DataFrame(self.resultados)
            
            # Renomear colunas para melhor clareza
            df_resultados = df_resultados.rename(columns={
                'valor_dnnr': 'Decisão Analista MJ',
                'decisao': 'Decisão Enviada Automaticamente',
                'codigo': 'Código do Processo',
                'status': 'Status',
                'erro': 'Erro'
            })
            
            # Reordenar colunas para melhor visualização
            colunas_ordenadas = ['Código do Processo', 'Decisão Analista MJ', 'Decisão Enviada Automaticamente', 'Status', 'Erro']
            colunas_existentes = [col for col in colunas_ordenadas if col in df_resultados.columns]
            if colunas_existentes:
                df_resultados = df_resultados[colunas_existentes]
            
            # Nome do arquivo de resultados
            nome_base = os.path.splitext(os.path.basename(caminho_planilha))[0]
            arquivo_resultado = f"{nome_base}_resultados_aprovacao_recurso_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            caminho_resultado = os.path.join(os.path.dirname(caminho_planilha), arquivo_resultado)
            
            # Salvar
            df_resultados.to_excel(caminho_resultado, index=False)
            print(f'[SALVO] Resultados parciais salvos: {arquivo_resultado} ({processo_atual} processos)')
            
        except Exception as e:
            print(f'[AVISO] Erro ao salvar resultados parciais: {e}')

    def salvar_resultados_finais(self, caminho_planilha):
        """
        Salva resultados finais
        """
        try:
            # Criar DataFrame com resultados incluindo a nova coluna
            df_resultados = pd.DataFrame(self.resultados)
            
            # Renomear colunas para melhor clareza
            df_resultados = df_resultados.rename(columns={
                'valor_dnnr': 'Decisão Analista MJ',
                'decisao': 'Decisão Enviada Automaticamente',
                'codigo': 'Código do Processo',
                'status': 'Status',
                'erro': 'Erro'
            })
            
            # Reordenar colunas para melhor visualização
            colunas_ordenadas = ['Código do Processo', 'Decisão Analista MJ', 'Decisão Enviada Automaticamente', 'Status', 'Erro']
            colunas_existentes = [col for col in colunas_ordenadas if col in df_resultados.columns]
            if colunas_existentes:
                df_resultados = df_resultados[colunas_existentes]
            
            # Nome do arquivo de resultados
            nome_base = os.path.splitext(os.path.basename(caminho_planilha))[0]
            arquivo_resultado = f"{nome_base}_resultados_finais_aprovacao_recurso_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            caminho_resultado = os.path.join(os.path.dirname(caminho_planilha), arquivo_resultado)
            
            # Salvar
            df_resultados.to_excel(caminho_resultado, index=False)
            print(f'\n{"="*80}')
            print(f'[SALVO] PLANILHA DE RESULTADOS GERADA COM SUCESSO!')
            print(f'{"="*80}')
            print(f'[PASTA] Local: {caminho_resultado}')
            print(f'[INFO] Nome do arquivo: {arquivo_resultado}')
            print(f'\n[DADOS] Colunas da planilha:')
            print(f'   1. Código do Processo')
            print(f'   2. Decisão Analista MJ (campo DNNR_DEC)')
            print(f'   3. Decisão Enviada Automaticamente (Nego Provimento / Dou Provimento)')
            print(f'   4. Status (sucesso / erro)')
            print(f'   5. Erro (se houver)')
            
            # Mostrar resumo
            sucessos = len([r for r in self.resultados if r['status'] == 'sucesso'])
            erros = len([r for r in self.resultados if r['status'] == 'erro'])
            total = len(self.resultados)
            
            print(f'\n[DADOS] RESUMO DO PROCESSAMENTO:')
            print(f'   [INFO] Total de processos: {total}')
            print(f'   [OK] Sucessos: {sucessos} ({(sucessos/total)*100:.1f}%)')
            print(f'   [ERRO] Erros: {erros} ({(erros/total)*100:.1f}%)')
            print(f'{"="*80}\n')
            
        except Exception as e:
            print(f'[ERRO] Erro ao salvar resultados finais: {e}')

    def close(self):
        """Fecha o driver"""
        # DEBUG: Comentado temporariamente para reduzir logs
        # import traceback
        # print('[FECHADO] CHAMADA PARA CLOSE() DETECTADA!')
        # print('[DEBUG] DEBUG: Stack trace da chamada para close():')
        # traceback.print_stack()
        
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()
            print('[FECHADO] Driver fechado')
            self.driver = None
        else:
            print('[FECHADO] Driver já estava fechado ou não existe')

    def ativar_modo_producao(self):
        """Ativa o modo produção (formulários serão enviados efetivamente)"""
        self.modo_teste = False
        print("[EXEC] MODO PRODUÇÃO ATIVADO: Formulários serão enviados efetivamente!")
    
    def ativar_modo_teste(self):
        """Ativa o modo teste (formulários não serão enviados)"""
        self.modo_teste = True
        print("[TESTE] MODO TESTE ATIVADO: Formulários não serão enviados (apenas simulação)")

    def fechar(self):
        """Alias para close"""
        self.close()

# Para usar esta classe:
# 1. aprovador = AprovacaoConteudoRecurso()
# 2. aprovador.login()
# 3. aprovador.processar_planilha_completa(caminho_planilha, 'codigo')
# 4. aprovador.close()
