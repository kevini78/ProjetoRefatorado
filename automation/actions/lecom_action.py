"""
Camada Action - Interações com o sistema LECOM
Responsável por navegação web, login, downloads e OCR
"""

import os
import time
import base64
import requests
import io
import json
import uuid
import unicodedata
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import re
import pytesseract
from pdf2image import convert_from_path
from mistralai import Mistral

# Importar utilitários de OCR (mantém funcionalidade existente)
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from Ordinaria.preprocessing_ocr import ImagePreprocessor
from Ordinaria.ocr_utils import (
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

from dotenv import load_dotenv

# Carrega o .env
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=env_path)

LECOM_URL = "https://justica.servicos.gov.br/bpm"
LECOM_USER = os.environ.get("LECOM_USER")
LECOM_PASS = os.environ.get("LECOM_PASS")


class LecomAction:
    """
    Action responsável por todas as interações com o sistema LECOM
    """
    
    def __init__(self, driver=None):
        """
        Inicializa a action do LECOM
        
        Args:
            driver: WebDriver do Selenium (opcional)
        """
        if driver:
            self.driver = driver
            self.wait = WebDriverWait(self.driver, 40)
        else:
            self.driver = self._create_driver()
            self.wait = WebDriverWait(self.driver, 40)
        
        # Propriedades essenciais
        self.numero_processo_limpo = None
        self.ja_logado = False
        self.ciclo_processo = None
        self.data_inicial_processo = None
        
        # Cache para evitar reprocessamento
        self.textos_ja_extraidos = {}
        
        # Sistema de logs para rastrear falhas de download
        self.logs_download = {
            'sucessos': [],
            'falhas': [],
            'erros': []
        }
    
    def _create_driver(self) -> webdriver.Chrome:
        """Cria um novo driver Chrome com configurações otimizadas"""
        chrome_options = Options()
        
        # Configurações básicas
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
        
        return webdriver.Chrome(options=chrome_options)
    
    def login(self) -> bool:
        """
        Realiza login no sistema LECOM
        
        Returns:
            bool: True se login foi bem-sucedido
        """
        print('=== INÍCIO login ===')
        print('Acessando o Lecom...')
        self.driver.get(LECOM_URL)
        
        try:
            # Campo de usuário
            username_input = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, "//input[@name='username']"))
            )
            username_input.click()
            username_input.clear()
            username_input.send_keys(LECOM_USER if LECOM_USER else "")

            # Botão próxima
            proxima_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and .//span[text()='Próxima']]"))
            )
            proxima_btn.click()

            # Campo de senha
            password_input = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, "//input[@name='password' and @type='password']"))
            )
            password_input.clear()
            password_input.send_keys(LECOM_PASS if LECOM_PASS else "")

            # Botão entrar
            entrar_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and .//span[text()='Entrar']]"))
            )
            entrar_btn.click()

            # Aguardar e clicar no botão "Entendi" se aparecer
            try:
                botao_entendi = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@type='button' and contains(@class, 'ant-btn-primary') and .//span[text()='Entendi']]"))
                )
                botao_entendi.click()
                time.sleep(2)
            except TimeoutException:
                pass

            # Fechar chat se aparecer
            try:
                botao_fechar_chat = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//svg[contains(@class, '') and path[@d='M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z']]"))
                )
                botao_fechar_chat.click()
                time.sleep(1)
            except TimeoutException:
                pass

            print('Login realizado.')
            self.ja_logado = True
            time.sleep(2)
            return True
            
        except Exception as e:
            print(f'ERRO no login: {e}')
            return False
    
    def navegar_para_processo(self, numero_processo: str) -> Dict[str, Any]:
        """
        Navega para um processo específico
        
        Args:
            numero_processo: Número do processo
            
        Returns:
            Dict com resultado da navegação
        """
        print('=== INÍCIO navegar_para_processo ===')
        
        try:
            # Extrair número limpo do processo
            numero_limpo = re.sub(r'\D', '', numero_processo)
            self.numero_processo_limpo = numero_limpo
            
            # Navegar para workspace flow
            workspace_url = f'https://justica.servicos.gov.br/workspace/flow/{numero_limpo}'
            print(f'Navegando para: {workspace_url}')
            
            self.driver.get(workspace_url)
            time.sleep(3)
            
            # Extrair data inicial do processo
            data_inicial = self._extrair_data_inicial_processo()
            if data_inicial:
                self.data_inicial_processo = data_inicial
                print(f"Data inicial extraída: {data_inicial}")
            
            # Buscar atividade "Efetuar Distribuição"
            return self._buscar_efetuar_distribuicao()
            
        except Exception as e:
            print(f"ERRO ao navegar para processo: {e}")
            return {'status': 'erro', 'mensagem': str(e)}
    
    def _extrair_data_inicial_processo(self) -> Optional[str]:
        """Extrai a data inicial do processo da página atual (baseado no código original)"""
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
    
    def _buscar_efetuar_distribuicao(self) -> Dict[str, Any]:
        """Busca e acessa a atividade Efetuar Distribuição"""
        try:
            # Aguardar tabela carregar
            tabela = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-table-tbody"))
            )
            
            # Encontrar todas as linhas da tabela
            linhas = self.driver.find_elements(By.CSS_SELECTOR, ".ant-table-tbody tr")
            print(f'Encontradas {len(linhas)} atividades')

            # Buscar atividades "Efetuar Distribuição"
            efetuar_distribuicao_links = []
            
            for linha in linhas:
                try:
                    link = linha.find_element(By.CSS_SELECTOR, "a.col-with-link")
                    titulo = (link.get_attribute('title') or link.text or '').strip()
                    href = link.get_attribute('href') or ''
                    
                    if ('/24/' in href) and ('efetuar distribui' in titulo.lower()):
                        # Extrair ciclo da URL
                        match = re.search(r'/24/(\d+)', href)
                        if match:
                            ciclo = int(match.group(1))
                            efetuar_distribuicao_links.append((link, titulo, href, ciclo))
                            print(f"Encontrada atividade ciclo {ciclo}: {href}")
                except Exception:
                    continue
            
            if not efetuar_distribuicao_links:
                return {'status': 'erro', 'mensagem': 'Atividade Efetuar Distribuição não encontrada'}
            
            # Ordenar por ciclo (maior primeiro) e pegar o mais recente
            efetuar_distribuicao_links.sort(key=lambda x: x[3], reverse=True)
            link_escolhido, titulo_escolhido, href_escolhido, ciclo_escolhido = efetuar_distribuicao_links[0]
            
            self.ciclo_processo = ciclo_escolhido
            print(f"Selecionado ciclo {ciclo_escolhido}: {titulo_escolhido}")
            
            # Clicar na atividade
            try:
                link_escolhido.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", link_escolhido)
            
            # Aguardar navegação
            try:
                WebDriverWait(self.driver, 15).until(EC.url_contains('/form-app/'))
            except TimeoutException:
                time.sleep(3)
            
            # Navegar para form-web
            return self._navegar_form_web()
            
        except Exception as e:
            print(f"Erro ao buscar Efetuar Distribuição: {e}")
            return {'status': 'erro', 'mensagem': str(e)}
    
    def _navegar_form_web(self) -> Dict[str, Any]:
        """Navega para o form-web"""
        try:
            ciclo_para_usar = getattr(self, 'ciclo_processo', 2)
            
            form_url = f'https://justica.servicos.gov.br/form-web?processInstanceId={self.numero_processo_limpo}&activityInstanceId=24&cycle={ciclo_para_usar}&newWS=true'
            print(f'Navegando para form-web: {form_url}')
            
            self.driver.get(form_url)
            time.sleep(5)
            
            current_url = self.driver.current_url
            if 'form-web' in current_url and self.numero_processo_limpo in current_url:
                print('Navegação para form-web bem-sucedida!')
                return {
                    'status': 'navegacao_concluida', 
                    'data_inicial': self.data_inicial_processo
                }
            else:
                print(f'URL inesperada: {current_url}')
                return {'status': 'aviso', 'mensagem': 'URL inesperada mas continuando'}
                
        except Exception as e:
            print(f'Erro ao navegar para form-web: {e}')
            return {'status': 'erro', 'mensagem': str(e)}
    
    def navegar_para_iframe_form_app(self) -> bool:
        """
        Navega para o iframe do form-app
        
        Returns:
            bool: True se conseguiu navegar para o iframe
        """
        try:
            print('[IFRAME] Procurando iframe do form-app...')

            # Garantir que estamos no contexto principal antes de procurar o iframe
            try:
                self.driver.switch_to.default_content()
                print('[IFRAME] Contexto resetado para janela principal')
            except Exception as reset_error:
                print(f'[AVISO] Não foi possível resetar contexto automaticamente: {reset_error}')

            # Aguardar iframe aparecer
            iframe = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.ID, "iframe-form-app"))
            )

            # Mudar para o iframe
            self.driver.switch_to.frame(iframe)
            print('[OK] Navegação para iframe concluída')

            # Aguardar conteúdo carregar
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Marcar contexto atual
            self._esta_no_iframe = True

            return True

        except Exception as e:
            print(f'[ERRO] Erro ao navegar para iframe: {e}')
            return False
    
    def voltar_do_iframe(self):
        """Volta do iframe para a janela principal"""
        try:
            self.driver.switch_to.default_content()
            print('[OK] Voltou para janela principal')
            self._esta_no_iframe = False
        except Exception as e:
            print(f'[AVISO] Erro ao voltar do iframe: {e}')
    
    def fechar_driver(self):
        """Fecha o driver do navegador"""
        if self.driver:
            self.driver.quit()
            print('[OK] Driver fechado')
