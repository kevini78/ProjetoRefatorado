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

class NavegacaoProvisoria:
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
            
            # Configurar diretório de download padrão
            download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 40)
            print("[FECHADO] LGPD: Novo driver criado com conformidade")
        
        # Propriedades essenciais
        self.numero_processo_limpo = None
        self.ja_logado = False
        
        # [FECHADO] CORREÇÃO LGPD: Definir documentos permitidos (SEM portaria de naturalização)
        self.documentos_para_baixar = [
            'Documento oficial de identidade',
            'Certidão de antecedentes criminais',
            'Comprovante de tempo de residência'
            # [FECHADO] LGPD: Portaria de naturalização NUNCA está na lista
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
        
        print("[FECHADO] LGPD: Sistema inicializado em conformidade")
        print("[OK] Documentos permitidos:", len(self.documentos_para_baixar))

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

        # Aguardar um pouco para o login processar
        time.sleep(3)
        
        # Verificar se apareceu botão "Entendi" (nova funcionalidade do LECOM)
        try:
            print('DEBUG: Procurando botão "Entendi" para mudanças do LECOM...')
            entendi_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and contains(@class, 'ant-btn-primary') and .//span[text()='Entendi']]"))
            )
            print('DEBUG: Botão "Entendi" encontrado - clicando...')
            entendi_btn.click()
            time.sleep(2)
            print('DEBUG: Botão "Entendi" clicado com sucesso!')
        except TimeoutException:
            print('DEBUG: Botão "Entendi" não apareceu ou já foi clicado')
        except Exception as e:
            print(f'DEBUG: Erro ao procurar botão "Entendi": {e}')

        # Verificar se apareceu chat "Comunique-se com a equipe" para fechar
        try:
            print('DEBUG: Procurando chat de comunicação para fechar...')
            fechar_chat_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//svg[contains(@class, '') and path[@d='M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z']]"))
            )
            print('DEBUG: Botão de fechar chat encontrado - clicando...')
            fechar_chat_btn.click()
            time.sleep(2)
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
        print('=== INÍCIO aplicar_filtros ===')
        print('Navegação direta para o processo...')
        
        try:
            # Extrair número limpo do processo (apenas dígitos)
            numero_limpo = re.sub(r'\D', '', numero_processo)
            
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
            
            # Encontrar todas as linhas da tabela
            linhas = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            print(f'DEBUG: {len(linhas)} atividades encontradas')
            
            # Procurar por "Efetuar Distribuição"
            for linha in linhas:
                try:
                    link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    nome_atividade = link.get_attribute('title') or link.text.strip()
                    
                    if 'efetuar distribuição' in nome_atividade.lower():
                        print(f'[OK] Encontrou: {nome_atividade}')
                        print('[CLIQUE] Clicando na atividade...')
                        link.click()
                        time.sleep(3)
                        
                        current_url = self.driver.current_url
                        print(f'DEBUG: URL após clique: {current_url}')
                        
                        if 'form-app' in current_url:
                            print('[OK] Navegação para formulário bem-sucedida!')
                        break
                except:
                    continue
            else:
                print('[ERRO] "Efetuar Distribuição" não encontrada!')
                return None

            print('[OK] Acesso à atividade concluído!')
            
            # AGORA EXTRAIR DADOS PESSOAIS E VERIFICAR ELEGIBILIDADE
            print("\n[BUSCA] INICIANDO EXTRAÇÃO DE DADOS PESSOAIS E VERIFICAÇÃO DE ELEGIBILIDADE")
            print("=" * 70)
            
            # 2. Extrair dados pessoais do formulário (agora que estamos no form-app)
            print("\n[USER] ETAPA 2: Extraindo dados pessoais do formulário...")
            
            if not data_inicial:
                print("[ERRO] Não foi possível extrair a data inicial do processo")
                print("   Continuando com análise tradicional...")
            else:
                print(f"[OK] Data inicial extraída: {data_inicial}")
                
                # 2. Extrair dados pessoais do formulário
                print("\n[USER] ETAPA 2: Extraindo dados pessoais do formulário...")
                dados_pessoais = self.extrair_dados_pessoais_formulario()
                
                if dados_pessoais.get('nome_completo') and dados_pessoais.get('data_nascimento'):
                    print(f"[OK] Dados pessoais extraídos:")
                    print(f"   Nome: {dados_pessoais['nome_completo']}")
                    print(f"   Pai: {dados_pessoais['nome_pai']}")
                    print(f"   Mãe: {dados_pessoais['nome_mae']}")
                    print(f"   Nascimento: {dados_pessoais['data_nascimento']}")
                    
                    # 3. Verificar elegibilidade por idade (REMOVIDO - será feito pelo módulo de análise provisória)
                    print("\n[TARGET] ETAPA 3: Elegibilidade por idade será verificada pelo módulo de análise provisória")
                    print("   [INFO] Regra provisória: Idade ≤ 17 anos (não 18-20 anos)")
                    print("   [RELOAD] Continuando para verificação de naturalização...")
                    
                    # Variável para armazenar resultado da idade (será calculada pelo módulo de análise)
                    resultado_idade = {
                        'idade_calculada': None,
                        'elegivel_por_idade': None,
                        'motivo_idade': 'Será calculada pelo módulo de análise provisória'
                    }
                    
                    # 4. Para análise provisória, NÃO verificar se já tem naturalização
                    print("\n[INFO] ETAPA 4: Análise provisória - verificação de naturalização REMOVIDA")
                    print("   [TARGET] Para análise provisória, não verificamos se já tem naturalização")
                    print("   [TARGET] Estamos analisando se a pessoa DEVE RECEBER a naturalização provisória")
                    print("   [RELOAD] Continuando para análise completa...")
                
                else:
                    print("[AVISO] Dados pessoais incompletos")
                    print("   Continuando com análise tradicional...")
            
            print("\n[RELOAD] Continuando com fluxo tradicional de análise...")
            print('=== FIM aplicar_filtros com navegação natural para form-app na etapa Efetuar Distribuição ===')
            
            # Retornar None para indicar que deve continuar com análise tradicional
            return None
        except Exception as e:
            print(f"ERRO ao extrair e abrir o processo: {e}")
            return

    def processar_processo(self, numero_processo, dados_texto=None):
        print('=== CHAMADA ÚNICA processar_processo ===')
        print('=== INÍCIO processar_processo ===')
        if dados_texto is None:
            dados_texto = {}
        # Marcar como já logado para evitar tentativas de relogin
        self.ja_logado = True
        print('DEBUG: Marcado como já logado - usando sessão existente do app.py')
        
        # Aplicar filtros e verificar se houve indeferimento automático
        resultado_filtros = self.aplicar_filtros(numero_processo)
        print('Filtros aplicados OK')
        
        # VERIFICAR SE HOUVE INDEFERIMENTO AUTOMÁTICO
        if resultado_filtros and resultado_filtros.get('indeferimento_automatico'):
            print('🚫 INDEFERIMENTO AUTOMÁTICO DETECTADO!')
            print(f'💬 Motivo: {resultado_filtros.get("motivo")}')
            print('[TARGET] Não será executado download de documentos')
            print('[TARGET] Não será executado OCR')
            print('[TARGET] Processo finalizado com indeferimento automático')
            
            # Navegar de volta para pesquisa de processos
            print('DEBUG: Retornando para pesquisa de processos...')
            try:
                # Tentar navegação direta primeiro (mais confiável)
                self.driver.get('https://justica.servicos.gov.br/workspace/')
                time.sleep(5)
                print('DEBUG: Navegação direta para pesquisa de processos concluída!')
                
                # Verificar se chegou corretamente
                if self.verificar_se_esta_na_pesquisa():
                    print('DEBUG: [OK] Navegação para pesquisa de processos bem-sucedida!')
                else:
                    print('DEBUG: [AVISO] Navegação direta não funcionou, tentando método alternativo...')
                    self.voltar_para_pesquisa_processos()
                    
            except Exception as e:
                print(f'ERRO na navegação direta: {e}')
                try:
                    print('DEBUG: Tentando método alternativo...')
                    self.voltar_para_pesquisa_processos()
                    print('DEBUG: Navegação alternativa para pesquisa de processos concluída!')
                except Exception as e2:
                    print(f'ERRO na navegação alternativa: {e2}')
                    # Último recurso: tentar novamente a navegação direta
                    try:
                        self.driver.get('https://justica.servicos.gov.br/workspace/')
                        time.sleep(5)
                        print('DEBUG: Última tentativa de navegação direta concluída!')
                    except Exception as e3:
                        print(f'ERRO na última tentativa: {e3}')
                
            # Retornar resultado de indeferimento automático
            return {
                'numero_processo': numero_processo,
                'indeferimento_automatico': True,
                'motivo': resultado_filtros.get('motivo'),
                'dados_verificacao': resultado_filtros.get('dados_verificacao', {}),
                'status': 'Indeferimento automático'
            }
        
        # SE NÃO HOUVE INDEFERIMENTO, CONTINUAR COM DOWNLOAD E OCR
        print('DEBUG: Iniciando download de todos os documentos e OCR...')
        resultado = {}
        
        try:
            print('=== VOU CHAMAR baixar_todos_documentos_e_ocr ===')
            resultados_ocr = self.baixar_todos_documentos_e_ocr()
            print('=== FIM baixar_todos_documentos_e_ocr ===')
        except Exception as e:
            print('ERRO ao executar baixar_todos_documentos_e_ocr:', e)
            resultados_ocr = {}
        
        print('Download e OCR de todos os documentos OK')
        
        if resultados_ocr:
            # Processar resultados de todos os documentos
            todos_campos_ocr = {}
            todos_textos_ocr = {}
            
            for nome_doc, dados_doc in resultados_ocr.items():
                print(f"DEBUG: Processando resultados do documento: {nome_doc}")
                campos_ocr = dados_doc.get('campos_ocr', {})
                texto_completo = dados_doc.get('texto_completo', '')
                
                # Se houver nome_completo, use para o campo nome
                if 'nome_completo' in campos_ocr and campos_ocr['nome_completo']:
                    campos_ocr['nome'] = campos_ocr['nome_completo']
                
                todos_campos_ocr[nome_doc] = campos_ocr
                todos_textos_ocr[nome_doc] = texto_completo
                
                print(f"DEBUG: Campos extraídos de {nome_doc}:", campos_ocr)
            
            resultado = {
                'numero_processo': numero_processo,
                'todos_campos_ocr': todos_campos_ocr,
                'todos_textos_ocr': todos_textos_ocr,
                'documentos_processados': list(resultados_ocr.keys()),
                'total_documentos': len(resultados_ocr),
                'status': 'Processado com sucesso'
            }
        else:
            print('Não foi possível baixar nenhum documento.')
            resultado = {
                'numero_processo': numero_processo,
                'erro': 'Não foi possível baixar nenhum documento.',
                'status': 'Erro'
            }
        
        print('=== FIM processar_processo ===')
        
        # Retornar para a aba de pesquisa de processos para o próximo processo
        print('DEBUG: Retornando para pesquisa de processos...')
        try:
            # SEMPRE fechar abas desnecessárias antes de voltar
            print('DEBUG: 🧹 Fechando abas desnecessárias antes de voltar...')
            self.fechar_abas_desnecessarias()
            
            # Agora voltar para pesquisa
            self.voltar_para_pesquisa_processos()
            print('DEBUG: Navegação para pesquisa de processos concluída!')
        except Exception as e:
            print(f'ERRO ao retornar para pesquisa de processos: {e}')
            print('DEBUG: Tentando navegação manual...')
            try:
                # Fallback: navegação direta
                self.driver.get('https://justica.servicos.gov.br/workspace/')
                time.sleep(3)
                print('DEBUG: Navegação direta para pesquisa de processos concluída!')
            except Exception as e2:
                print(f'ERRO na navegação de fallback: {e2}')
        
        return resultado

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
                
                # Baixar documento
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
                        import re
                        texto_protegido = re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF MASCARADO]', texto_protegido)
                        texto_protegido = re.sub(r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b', '[RG MASCARADO]', texto_protegido)
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
                novos_pdfs = [f for f in novos if f.lower().endswith('.pdf')]
                if novos_pdfs:
                    arquivo_baixado = os.path.join(download_path, novos_pdfs[0])
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
                    
                    print(f"DEBUG: [OK] OCR bem-sucedido - {len(texto_protegido)} caracteres extraídos e protegidos")
                    
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
        
        import re
        texto_protegido = texto
        
        # Mascarar CPF (múltiplos formatos)
        texto_protegido = re.sub(r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b', '[CPF MASCARADO]', texto_protegido)
        texto_protegido = re.sub(r'\b\d{11}\b', '[CPF MASCARADO]', texto_protegido)
        texto_protegido = re.sub(r'CPF:\s*\d{3}\.\d{3}\.\d{3}-\d{2}', 'CPF: [MASCARADO]', texto_protegido)
        
        # Mascarar RG
        texto_protegido = re.sub(r'\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b', '[RG MASCARADO]', texto_protegido)
        texto_protegido = re.sub(r'RG:\s*\d{2}\.\d{3}\.\d{3}-[0-9X]', 'RG: [MASCARADO]', texto_protegido)
        
        # Mascarar endereços completos
        texto_protegido = re.sub(r'ENDEREÇO:\s*[^,\n]+', 'ENDEREÇO: [MASCARADO]', texto_protegido)
        texto_protegido = re.sub(r'RUA\s+[^,\n]+\d+', 'RUA [MASCARADO]', texto_protegido)
        
        # Mascarar CEP
        texto_protegido = re.sub(r'\b\d{5}-\d{3}\b', '[CEP MASCARADO]', texto_protegido)
        
        # Mascarar telefones
        texto_protegido = re.sub(r'\(\d{2}\)\s*\d{4,5}-\d{4}', '[TELEFONE MASCARADO]', texto_protegido)
        
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
                novos_pdfs = [f for f in novos if f.lower().endswith('.pdf')]
                if novos_pdfs:
                    arquivo_baixado = os.path.join(download_path, novos_pdfs[0])
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

        # 1. Tenta extrair da div#celula0
        try:
            div = self.driver.find_element(By.ID, "celula0")
            texto_div = div.text.strip()
            print(f"DEBUG: Texto encontrado em div#celula0: '{texto_div}'")
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
            numero_processo_limpo = re.sub(r'\D', '', numero_processo)
            self.numero_processo_limpo = numero_processo_limpo
            print(f"DEBUG: Número do processo extraído: {numero_processo} | Limpo: {numero_processo_limpo}")
            return numero_processo_limpo
        else:
            print("ERRO: Não foi possível extrair o número do processo!")
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

    def voltar_para_pesquisa_processos(self):
        """
        Volta para a página de pesquisa de processos, fechando abas desnecessárias
        """
        print("DEBUG: Iniciando retorno para pesquisa de processos...")
        
        # SEMPRE fechar abas desnecessárias antes de voltar
        print("DEBUG: 🧹 Fechando abas desnecessárias antes de voltar...")
        self.fechar_abas_desnecessarias()
        
        # Verificar se já estamos na página de pesquisa
        if self.verificar_se_esta_na_pesquisa():
            print("DEBUG: Já estamos na página de pesquisa de processos!")
            return
        
        # Navegar para a página de pesquisa
        print("DEBUG: Navegando diretamente para URL de pesquisa...")
        try:
            self.driver.get('https://justica.servicos.gov.br/workspace/')
            time.sleep(3)
            
            # Verificar se chegamos na página correta
            if self.verificar_se_esta_na_pesquisa():
                print("DEBUG: Navegação para pesquisa de processos concluída!")
            else:
                print("DEBUG: Navegação pode ter falhado, tentando novamente...")
                time.sleep(2)
                self.driver.get('https://justica.servicos.gov.br/workspace/')
                time.sleep(3)
                
        except Exception as e:
            print(f"ERRO na navegação para pesquisa: {e}")
            # Tentar recuperação
            try:
                self.driver.get('https://justica.servicos.gov.br/workspace/')
                time.sleep(3)
                print("DEBUG: Navegação de recuperação concluída")
            except Exception as e2:
                print(f"ERRO na navegação de recuperação: {e2}")
    
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
    'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03', 'abril': '04', 'maio': '05', 'junho': '06',
    'julho': '07', 'agosto': '08', 'setembro': '09', 'outubro': '10', 'novembro': '11', 'dezembro': '12'
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
        return f'{dia}/{mes}/{ano}'
    return data_str.strip()

if __name__ == "__main__":
    print('=== INÍCIO DO SCRIPT PRINCIPAL ===')
    numero_processo = "668.121"  # Exemplo
    dados_texto = {'pai': 'John Stephen Lyons', 'mae': 'Cynthia Mae Goodpaster', 'rnm': 'G064347-0'}
    navegacao = NavegacaoProvisoria()
    try:
        resultado = navegacao.processar_processo(numero_processo, dados_texto)
        print("Resultado do processamento:", resultado)
    except Exception as e:
        print('ERRO FATAL durante o processamento:', e)
    finally:
        navegacao.close()

