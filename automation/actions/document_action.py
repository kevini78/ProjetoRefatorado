"""
Camada Action - Download e processamento de documentos
Responsável por baixar documentos, fazer OCR e extrair dados
"""

import os
import time
import base64
import tempfile
import re
import io
from typing import Dict, Any, Optional, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import cv2
import numpy as np
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
from mistralai import Mistral

# Importar utilitários de OCR
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
    comparar_campos
)


class DocumentAction:
    """
    Action responsável por download e processamento de documentos
    """
    
    def __init__(self, driver, wait):
        """
        Inicializa a action de documentos
        
        Args:
            driver: WebDriver do Selenium
            wait: WebDriverWait instance
        """
        self.driver = driver
        self.wait = wait
        self.textos_ja_extraidos = {}
        self.logs_download = {
            'sucessos': [],
            'falhas': [],
            'erros': []
        }
        self.ultimo_texto_ocr: Dict[str, str] = {}
    
    def baixar_e_validar_documento_individual(self, nome_documento: str) -> bool:
        """
        Baixa e valida um documento específico
        
        Args:
            nome_documento: Nome do documento a ser baixado
            
        Returns:
            bool: True se documento foi baixado e validado com sucesso
        """
        try:
            print(f"[DOC] Baixando e validando: {nome_documento}")
            
            # Buscar documento na tabela ou campo específico
            resultado_busca = self._buscar_documento(nome_documento)
            
            if not resultado_busca.get('encontrado', False):
                print(f"[ERRO] {nome_documento}: NÃO ANEXADO")
                return False
            
            processamento = self._processar_documento_encontrado(
                nome_documento,
                resultado_busca,
                tentativa_fallback=False
            )
            
            if processamento.get('sucesso'):
                print(f"[OK] {nome_documento}: VÁLIDO")
                self.logs_download['sucessos'].append(nome_documento)
                return True
            else:
                motivo = processamento.get('motivo', 'INVÁLIDO')
                print(f"[ERRO] {nome_documento}: {motivo}")
                self.logs_download['falhas'].append(f"{nome_documento}: {motivo}")
                return False
                
        except Exception as e:
            print(f"[ERRO] Erro ao processar {nome_documento}: {e}")
            self.logs_download['erros'].append(f"{nome_documento}: {e}")
            return False
    
    def _buscar_documento(self, nome_documento: str) -> Dict[str, Any]:
        """
        Busca documento usando estratégias múltiplas (preserva lógica original)
        """
        # ESPECIAL: Para antecedentes do país de origem, buscar PRIMEIRO na tabela
        if 'país de origem' in nome_documento.lower() or 'atestado antecedentes criminais' in nome_documento.lower():
            print(f"[BUSCA] Antecedentes país de origem: Buscando na tabela...")
            resultado_busca = self._buscar_documento_na_tabela(nome_documento)
            
            if not resultado_busca.get('encontrado', False):
                resultado_busca = self._buscar_documento_na_tabela_termos_amplos([
                    'atestado de antecedentes criminais',
                    'antecedentes criminais',
                    'tradução juramentada',
                    'certificacion de antecedentes',
                    'país de origem'
                ])
            
            if not resultado_busca.get('encontrado', False):
                resultado_busca = self._buscar_documento_em_campo_especifico(nome_documento)
        else:
            # FLUXO NORMAL: Outros documentos
            resultado_busca = self._buscar_documento_em_campo_especifico(nome_documento)
            
            if not resultado_busca.get('encontrado', False):
                print(f"[BUSCA] Documento não encontrado em campo específico, procurando na tabela...")
                resultado_busca = self._buscar_documento_na_tabela(nome_documento)
                
                # Se não encontrou na tabela com nome exato, tentar termos amplos
                if not resultado_busca.get('encontrado', False):
                    print(f"[BUSCA] Tentando busca com termos amplos na tabela...")
                    termos_documento = self._extrair_termos_busca(nome_documento)
                    resultado_busca = self._buscar_documento_na_tabela_termos_amplos(termos_documento)
        
        # ESPECIAL PARA COMPROVANTE DE REDUÇÃO
        if not resultado_busca.get('encontrado', False) and 'comprovante de redução de prazo' in nome_documento.lower():
            print(f"[BUSCA] Busca especial: Procurando 'Certidão de nascimento do filho brasileiro'...")
            resultado_busca = self._buscar_documento_na_tabela('Certidão de nascimento do filho brasileiro')
            
            if not resultado_busca.get('encontrado', False):
                resultado_busca = self._buscar_documento_na_tabela_termos_amplos([
                    'nascimento', 'filho brasileiro', 'filha', 'certidão de nascimento'
                ])
        
        return resultado_busca
    
    def _extrair_termos_busca(self, nome_documento: str) -> List[str]:
        """Extrai termos relevantes para busca na tabela"""
        nome_lower = nome_documento.lower()

        # Mapeamento de documentos para termos de busca
        mapeamento_termos = {
            'comprovante da situação cadastral do cpf': ['cpf', 'situação cadastral', 'receita federal'],
            'carteira de registro nacional migratório': ['crnm', 'rnm', 'rne', 'registro nacional'],
            'certidão de antecedentes criminais (brasil)': ['antecedentes', 'criminais', 'certidão', 'brasil'],
            'atestado antecedentes criminais (país de origem)': ['antecedentes', 'criminais', 'atestado', 'origem'],
            'comprovante de comunicação em português': ['português', 'comunicação', 'proficiência', 'celpe'],
            'documento de viagem internacional': ['passaporte', 'viagem', 'internacional'],
            'comprovante de tempo de residência': ['residência', 'tempo', 'permanência'],
            'comprovante de redução de prazo': ['redução', 'prazo', 'nascimento', 'filho']
        }
        
        # Procurar mapeamento exato
        for doc_key, termos in mapeamento_termos.items():
            if doc_key in nome_lower:
                return termos
        
        # Fallback: extrair palavras-chave do nome
        palavras_relevantes = []
        palavras = nome_lower.split()
        
        # Filtrar palavras irrelevantes
        palavras_irrelevantes = ['de', 'da', 'do', 'em', 'para', 'com', 'por', 'a', 'o', 'e']
        
        for palavra in palavras:
            if len(palavra) > 3 and palavra not in palavras_irrelevantes:
                palavras_relevantes.append(palavra)
        
        return palavras_relevantes[:3]  # Máximo 3 termos

    def _linha_corresponde_documento(self, nome_documento: str, tipo_texto: str, tipo_outro: str) -> bool:
        nome_lower = nome_documento.lower()
        tipo_lower = (tipo_texto or '').lower()
        outro_lower = (tipo_outro or '').lower()

        def contem(termos: List[str]) -> bool:
            return any(termo in tipo_lower or termo in outro_lower for termo in termos)

        if 'carteira de registro nacional migratório' in nome_lower or 'crnm' in nome_lower:
            return contem(['carteira de registro', 'crnm', 'rnm', 'rne', 'registro migratório', 'registro migratorio'])
        if 'comprovante da situação cadastral do cpf' in nome_lower or nome_lower.strip() == 'cpf':
            return contem(['cpf', 'cadastro de pessoa', 'cadastro de pessoas', 'receita federal'])
        if 'comprovante de comunicação em português' in nome_lower:
            return contem(['portugu', 'comunicação', 'comunicacao', 'certificado', 'histórico escolar', 'historico escolar', 'celpe'])
        if 'comprovante de tempo de residência' in nome_lower:
            return contem(['tempo de residência', 'tempo de residencia', 'comprovante de residência', 'comprovante residencia'])
        if 'documento de viagem internacional' in nome_lower or 'passaporte' in nome_lower:
            return contem(['passaporte', 'viagem internacional'])
        if 'certidão de antecedentes criminais (brasil)' in nome_lower or 'antecedentes criminais (brasil)' in nome_lower:
            termos_brasil = ['antecedentes criminais', 'justiça federal', 'justica federal', 'estadual', 'tj', 'tribunal', 'poder judiciário', 'poder judiciario', 'certidão criminal', 'certidao criminal']
            return contem(termos_brasil)
        if 'atestado antecedentes criminais (país de origem)' in nome_lower or 'país de origem' in nome_lower:
            termos_origem = ['atestado de antecedentes', 'pais de origem', 'país de origem', 'legalizado', 'traduzido', 'tradução', 'traducao', 'consulado']
            termos_brasil = ['justiça federal', 'justica federal', 'tribunal de justiça', 'poder judiciário', 'estado do', 'tj']
            tem_origem = contem(termos_origem)
            tem_brasil = contem(termos_brasil)
            return tem_origem and not tem_brasil

        return nome_lower in tipo_lower or nome_lower in outro_lower

    def _obter_link_download_linha(self, linha) -> Optional[Any]:
        candidatos = [
            (By.CSS_SELECTOR, ".table-cell--DOCS_ANEXO a"),
            (By.CSS_SELECTOR, ".table-cell--VIEWER a"),
            (By.CSS_SELECTOR, ".table-cell--VIEWER button"),
            (By.XPATH, ".//a[contains(@href, 'download') or .//i[@type='cloud_download']]")
        ]

        for by, selector in candidatos:
            try:
                elemento = linha.find_element(by, selector)
                if elemento:
                    return elemento
            except Exception:
                continue
        return None

    def _buscar_documento_na_tabela(self, nome_documento: str) -> Dict[str, Any]:
        """Busca documento na tabela de anexos"""
        try:
            print(f"[BUSCA] Procurando '{nome_documento}' na tabela de documentos...")
            linhas_tabela = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr.table-row")
            print(f"[BUSCA] Encontradas {len(linhas_tabela)} linhas na tabela")

            for linha in linhas_tabela:
                try:
                    tipo_elemento = linha.find_element(By.CSS_SELECTOR, ".table-cell--DOCS_TIPO span")
                    tipo_texto = tipo_elemento.text.strip()
                except Exception:
                    continue

                try:
                    tipo_outro_elemento = linha.find_element(By.CSS_SELECTOR, ".table-cell--DOCS_TIPO_OUTRO span")
                    tipo_outro_texto = tipo_outro_elemento.text.strip()
                except Exception:
                    tipo_outro_texto = ""

                if self._linha_corresponde_documento(nome_documento, tipo_texto, tipo_outro_texto):
                    link = self._obter_link_download_linha(linha)
                    if link:
                        nome_arquivo = link.text.strip()
                        print(f"[OK] Documento encontrado na tabela: {tipo_texto} | {tipo_outro_texto}")
                        return {
                            'encontrado': True,
                            'elemento_link': link,
                            'nome_arquivo': nome_arquivo,
                            'fonte': 'tabela',
                            'tipo_documento': tipo_texto,
                            'tipo_outro': tipo_outro_texto
                        }

            print(f"[BUSCA] Documento '{nome_documento}' não encontrado na tabela")
            return {'encontrado': False, 'motivo': 'Não encontrado na tabela'}
            
        except Exception as e:
            print(f"[ERRO] Erro na busca na tabela: {e}")
            return {'encontrado': False, 'motivo': f'Erro na busca: {e}'}

    def _buscar_documento_na_tabela_termos_amplos(self, termos: List[str]) -> Dict[str, Any]:
        """Busca documento na tabela usando termos amplos"""
        try:
            print(f"[BUSCA] Procurando na tabela com termos: {termos}")
            linhas_tabela = self.driver.find_elements(By.CSS_SELECTOR, "tbody tr.table-row")
            termos_lower = [termo.lower() for termo in termos]

            for linha in linhas_tabela:
                try:
                    tipo_elemento = linha.find_element(By.CSS_SELECTOR, ".table-cell--DOCS_TIPO span")
                    tipo_texto = tipo_elemento.text.strip().lower()
                except Exception:
                    continue

                try:
                    tipo_outro_elemento = linha.find_element(By.CSS_SELECTOR, ".table-cell--DOCS_TIPO_OUTRO span")
                    tipo_outro_texto = tipo_outro_elemento.text.strip().lower()
                except Exception:
                    tipo_outro_texto = ""

                texto_completo = f"{tipo_texto} {tipo_outro_texto}"
                if any(termo in texto_completo for termo in termos_lower):
                    link = self._obter_link_download_linha(linha)
                    if link:
                        nome_arquivo = link.text.strip()
                        print(f"[OK] Documento encontrado na tabela com termos amplos: {texto_completo[:80]}...")
                        return {
                            'encontrado': True,
                            'elemento_link': link,
                            'nome_arquivo': nome_arquivo,
                            'fonte': 'tabela_termos_amplos'
                        }
            
            print(f"[BUSCA] Nenhum documento encontrado com termos: {termos}")
            return {'encontrado': False, 'motivo': 'Não encontrado com termos amplos'}
            
        except Exception as e:
            print(f"[ERRO] Erro na busca por termos amplos: {e}")
            return {'encontrado': False, 'motivo': f'Erro na busca: {e}'}
    
    def _buscar_documento_em_campo_especifico(self, nome_documento: str) -> Dict[str, Any]:
        """Busca documento em campos específicos baseado na automação original"""
        try:
            # Mapeamento baseado na automação original
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
            
            nome_lower = nome_documento.lower()
            
            # Buscar por campo específico
            for doc_key, campo_id in mapeamento_ids.items():
                if doc_key in nome_lower:
                    print(f"[BUSCA] Verificando campo específico para {doc_key}: {campo_id}")
                    
                    try:
                        # Verificar se o campo existe
                        elemento_campo = self.driver.find_element(By.ID, campo_id)
                        print(f"✅ Campo {campo_id} encontrado")
                        
                        # Verificar se há ícone de download
                        if self._verificar_icone_download_campo(campo_id):
                            print(f"✅ Ícone de download encontrado para {campo_id}")
                            
                            # Buscar o botão de download
                            botao = self._buscar_botao_download_campo(campo_id)
                            
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
            return {'encontrado': False, 'motivo': 'Documento não encontrado em campos específicos'}
            
        except Exception as e:
            print(f"[ERRO] Erro ao buscar em campos específicos: {e}")
            return {'encontrado': False, 'motivo': f'Erro na busca: {e}'}
    
    def _executar_download_completo(self, link_elemento, fonte_busca: str, resultado_busca: Dict, nome_documento: str) -> Optional[str]:
        """Executa download completo baseado na automação original"""
        try:
            print(f"[DOWNLOAD] Iniciando download de: {nome_documento}")
            
            diretorio_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            
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
            if fonte_busca == 'campo_especifico_direto' or 'campo_especifico' in fonte_busca:
                # Para campos específicos COM ÍCONE: pegar último arquivo adicionado (5 segundos)
                print(f"[TARGET] Campo específico com ícone - aguardando 5 segundos...")
                return self._detectar_ultimo_arquivo_adicionado(arquivos_antes, nome_documento, timeout=5)
            else:
                # Para tabela: usar nome específico se disponível
                nome_arquivo_tabela = resultado_busca.get('nome_arquivo', '')
                if nome_arquivo_tabela:
                    print(f"[TARGET] Buscando arquivo específico: {nome_arquivo_tabela}")
                    return self._detectar_arquivo_por_nome(nome_arquivo_tabela, nome_documento, timeout=5)
                else:
                    # Fallback: pegar último arquivo adicionado
                    print(f"[TARGET] Fallback: aguardando último arquivo...")
                    return self._detectar_ultimo_arquivo_adicionado(arquivos_antes, nome_documento, timeout=5)
                
        except Exception as e:
            print(f"[ERRO] Erro no download completo: {e}")
            return None
    
    def _download_via_href(self, href: str, nome_documento: str) -> Optional[str]:
        """Download via URL direta"""
        try:
            import requests
            
            # Obter cookies da sessão
            cookies = {cookie['name']: cookie['value'] for cookie in self.driver.get_cookies()}
            
            response = requests.get(href, cookies=cookies, stream=True)
            response.raise_for_status()
            
            # Salvar arquivo
            nome_arquivo = self._gerar_nome_arquivo(nome_documento)
            caminho_arquivo = os.path.join(os.path.expanduser('~'), 'Downloads', nome_arquivo)
            
            with open(caminho_arquivo, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"[OK] Download concluído: {nome_arquivo}")
            return caminho_arquivo
            
        except Exception as e:
            print(f"[ERRO] Erro no download via href: {e}")
            return None
    
    def _download_via_javascript(self, link_elemento, nome_documento: str) -> Optional[str]:
        """Download via JavaScript"""
        try:
            # Executar JavaScript do onclick
            self.driver.execute_script("arguments[0].click();", link_elemento)
            
            # Aguardar download
            time.sleep(3)
            
            # Procurar arquivo baixado
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            arquivos_recentes = self._obter_arquivos_recentes(downloads_dir)
            
            if arquivos_recentes:
                arquivo_baixado = arquivos_recentes[0]
                print(f"[OK] Download via JS concluído: {arquivo_baixado}")
                return arquivo_baixado
            
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro no download via JS: {e}")
            return None

    def _detectar_ultimo_arquivo_adicionado(self, arquivos_antes: list, nome_documento: str, timeout: int = 5) -> Optional[str]:
        """Detecta o último arquivo adicionado ao diretório de downloads"""
        try:
            diretorio_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            tempo_inicial = time.time()

            print(f"[TEMPO] Aguardando {timeout} segundos por arquivo novo...")

            while time.time() - tempo_inicial < timeout:
                try:
                    arquivos_atuais = [arquivo for arquivo in os.listdir(diretorio_downloads)
                                        if os.path.isfile(os.path.join(diretorio_downloads, arquivo))
                                        and not arquivo.endswith('.crdownload')]

                    arquivos_novos = [arquivo for arquivo in arquivos_atuais if arquivo not in arquivos_antes]

                    if arquivos_novos:
                        arquivos_novos.sort(key=lambda a: os.path.getmtime(os.path.join(diretorio_downloads, a)), reverse=True)
                        arquivo_escolhido = arquivos_novos[0]
                        caminho_completo = os.path.join(diretorio_downloads, arquivo_escolhido)
                        print(f"📥 1 arquivos novos detectados:")
                        print(f"   [DOC] {arquivo_escolhido}")
                        return caminho_completo

                except Exception as e:
                    print(f"[AVISO] Erro ao verificar arquivos: {e}")

                time.sleep(0.5)

            print(f"⏰ Timeout de {timeout}s - nenhum arquivo novo detectado")
            return None

        except Exception as e:
            print(f"[ERRO] Erro ao detectar último arquivo: {e}")
            return None

    def _detectar_arquivo_por_nome(self, nome_arquivo_esperado: str, nome_documento: str, timeout: int = 5) -> Optional[str]:
        """Detecta arquivo específico pelo nome esperado"""
        try:
            diretorio_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
            tempo_inicial = time.time()

            print(f"[TARGET] Procurando especificamente por: {nome_arquivo_esperado}")

            while time.time() - tempo_inicial < timeout:
                try:
                    for arquivo in os.listdir(diretorio_downloads):
                        caminho_completo = os.path.join(diretorio_downloads, arquivo)
                        if not os.path.isfile(caminho_completo) or arquivo.endswith('.crdownload'):
                            continue

                        if arquivo == nome_arquivo_esperado or self._arquivo_compativel(arquivo, nome_arquivo_esperado):
                            print(f"[OK] Arquivo encontrado: {arquivo}")
                            return caminho_completo

                except Exception as e:
                    print(f"[AVISO] Erro ao procurar arquivo: {e}")

                time.sleep(0.5)

            print(f"⏰ Timeout - arquivo '{nome_arquivo_esperado}' não encontrado")
            return None

        except Exception as e:
            print(f"[ERRO] Erro ao detectar arquivo por nome: {e}")
            return None

    def _arquivo_compativel(self, arquivo_real: str, arquivo_esperado: str) -> bool:
        """Verifica se dois nomes de arquivo são compatíveis desconsiderando acentos e caracteres especiais"""
        try:
            import unicodedata

            def normalizar(nome: str) -> str:
                nome_norm = unicodedata.normalize('NFD', nome)
                nome_norm = ''.join(c for c in nome_norm if unicodedata.category(c) != 'Mn')
                nome_norm = nome_norm.lower().replace(' ', '')
                return nome_norm

            return normalizar(arquivo_real) == normalizar(arquivo_esperado)

        except Exception:
            return False

    def _processar_documento_encontrado(self, nome_documento: str, resultado_busca: Dict[str, Any], tentativa_fallback: bool = False) -> Dict[str, Any]:
        """Executa download, OCR e validação para um resultado encontrado."""
        try:
            fonte_busca = resultado_busca.get('fonte', '') or 'tabela'
            link_elemento = resultado_busca.get('elemento_link')
            if not link_elemento:
                return {'sucesso': False, 'motivo': 'Link de download não encontrado'}

            # Download seguindo regras do fluxo antigo
            nome_arquivo_baixado = self._executar_download_completo(
                link_elemento,
                fonte_busca,
                resultado_busca,
                nome_documento
            )

            if not nome_arquivo_baixado:
                motivo = 'Falha no download'
                if 'campo_especifico' in fonte_busca and not tentativa_fallback:
                    return self._tentar_fallback_tabela(nome_documento, motivo, origem_falha='download')
                return {'sucesso': False, 'motivo': motivo}

            texto_ocr = self._processar_arquivo_ocr(nome_arquivo_baixado, nome_documento)
            if not texto_ocr or len(texto_ocr.strip()) < 10:
                motivo = 'OCR falhou ou texto insuficiente'
                if 'campo_especifico' in fonte_busca and not tentativa_fallback:
                    return self._tentar_fallback_tabela(nome_documento, motivo, origem_falha='ocr')
                return {'sucesso': False, 'motivo': motivo}

            try:
                self.ultimo_texto_ocr[nome_documento] = texto_ocr
            except Exception as e_atualizacao:
                print(f"[AVISO] Não foi possível armazenar OCR de {nome_documento}: {e_atualizacao}")

            valido = self._validar_conteudo_documento_especifico(nome_documento, texto_ocr)
            if valido:
                return {'sucesso': True}

            motivo_invalido = 'Conteúdo inválido'
            if 'campo_especifico' in fonte_busca and not tentativa_fallback:
                return self._tentar_fallback_tabela(nome_documento, motivo_invalido, origem_falha='validacao')

            return {'sucesso': False, 'motivo': motivo_invalido}

        except Exception as e:
            return {'sucesso': False, 'motivo': f'Erro geral: {e}'}

    def _tentar_fallback_tabela(self, nome_documento: str, motivo_original: str, origem_falha: str) -> Dict[str, Any]:
        """Repete o fluxo de download e validação buscando o documento diretamente na tabela."""
        print(f"[FALLBACK] {nome_documento}: {motivo_original}. Buscando na tabela (origem: {origem_falha})...")

        resultado_tabela = self._buscar_documento_na_tabela(nome_documento)

        if not resultado_tabela.get('encontrado', False):
            termos_amplos = self._extrair_termos_busca(nome_documento)
            resultado_tabela = self._buscar_documento_na_tabela_termos_amplos(termos_amplos)

        if resultado_tabela.get('encontrado', False):
            resultado_tabela.setdefault('fonte', 'tabela_fallback')
            processamento = self._processar_documento_encontrado(
                nome_documento,
                resultado_tabela,
                tentativa_fallback=True
            )

            if processamento.get('sucesso'):
                print(f"[FALLBACK] {nome_documento}: Documento válido encontrado na tabela")
            else:
                print(f"[FALLBACK] {nome_documento}: Documento encontrado na tabela, porém inválido ({processamento.get('motivo')})")

            return processamento

        print(f"[FALLBACK] {nome_documento}: Documento não localizado na tabela após falha no campo específico")
        return {'sucesso': False, 'motivo': motivo_original}

    def _download_via_clique(self, link_elemento, nome_documento: str) -> Optional[str]:
        """Download via clique direto"""
        try:
            link_elemento.click()
            time.sleep(3)
            
            downloads_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
            arquivos_recentes = self._obter_arquivos_recentes(downloads_dir)
            
            if arquivos_recentes:
                arquivo_baixado = arquivos_recentes[0]
                print(f"[OK] Download via clique concluído: {arquivo_baixado}")
                return arquivo_baixado
            
            return None
            
        except Exception as e:
            print(f"[ERRO] Erro no download via clique: {e}")
            return None
    
    def _obter_arquivos_recentes(self, diretorio: str, limite_segundos: int = 30) -> List[str]:
        """Obtém arquivos baixados recentemente"""
        try:
            arquivos = []
            agora = time.time()
            
            for arquivo in os.listdir(diretorio):
                caminho_arquivo = os.path.join(diretorio, arquivo)
                if os.path.isfile(caminho_arquivo):
                    tempo_modificacao = os.path.getmtime(caminho_arquivo)
                    if agora - tempo_modificacao <= limite_segundos:
                        arquivos.append(caminho_arquivo)
            
            # Ordenar por tempo de modificação (mais recente primeiro)
            arquivos.sort(key=os.path.getmtime, reverse=True)
            return arquivos
            
        except Exception as e:
            print(f"[ERRO] Erro ao obter arquivos recentes: {e}")
            return []
    
    def _gerar_nome_arquivo(self, nome_documento: str) -> str:
        """Gera nome de arquivo baseado no documento"""
        nome_limpo = re.sub(r'[^\w\s-]', '', nome_documento)
        nome_limpo = re.sub(r'[-\s]+', '_', nome_limpo)
        timestamp = int(time.time())
        return f"{nome_limpo}_{timestamp}.pdf"
    
    def _processar_arquivo_ocr(self, caminho_arquivo: str, nome_documento: str) -> str:
        """
        Processa arquivo com OCR (preserva lógica original)
        """
        try:
            if not os.path.exists(caminho_arquivo):
                print(f"[ERRO] Arquivo não encontrado: {caminho_arquivo}")
                return ""
            
            extensao = os.path.splitext(caminho_arquivo)[1].lower()
            
            if extensao == '.pdf':
                return self._processar_pdf_ocr(caminho_arquivo, nome_documento)
            elif extensao in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                return self._processar_imagem_ocr(caminho_arquivo, nome_documento)
            else:
                print(f"[AVISO] Tipo de arquivo não suportado: {extensao}")
                return ""
                
        except Exception as e:
            print(f"[ERRO] Erro no OCR: {e}")
            return ""
    
    def _processar_imagem_ocr(self, caminho_arquivo: str, nome_documento: str) -> str:
        """Processa imagem com OCR Mistral + Pré-processamento"""
        try:
            print(f"[MISTRAL OCR] Processando imagem: {caminho_arquivo}")
            
            # Aplicar pré-processamento
            preprocessor = ImagePreprocessor()
            img_processada, metadata = preprocessor.preprocess_for_mistral(caminho_arquivo)
            
            print(f"[PRÉ-PROC] Etapas aplicadas: {', '.join(metadata.get('etapas_aplicadas', []))}")
            
            # Salvar imagem processada temporariamente
            temp_path = caminho_arquivo.replace('.', '_processed.')
            cv2.imwrite(temp_path, img_processada)
            
            # Executar OCR com Mistral
            texto_ocr = self._executar_mistral_ocr(temp_path)
            
            # Limpar arquivo temporário
            try:
                os.remove(temp_path)
            except:
                pass
            
            print(f"[MISTRAL OCR] Concluído: {len(texto_ocr)} caracteres extraídos")
            return texto_ocr.strip()
            
        except Exception as e:
            print(f"[ERRO] Erro no OCR de imagem: {e}")
            # Fallback para Tesseract
            try:
                img = Image.open(caminho_arquivo)
                texto_ocr = pytesseract.image_to_string(img, lang='por+eng')
                return texto_ocr.strip()
            except:
                return ""
    
    def _processar_pdf_ocr(self, caminho_arquivo: str, nome_documento: str) -> str:
        """Processa PDF com OCR Mistral + Pré-processamento"""
        try:
            # Configurar máximo de páginas baseado no documento
            nome_lower = nome_documento.lower()
            
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
            
            paginas_a_processar = min(len(doc), max_paginas) if max_paginas else len(doc)
            print(f"[MISTRAL OCR] Processando PDF: {paginas_a_processar} página(s)")
            
            for num_pagina in range(paginas_a_processar):
                pagina = doc[num_pagina]
                
                # Tentar extrair texto diretamente
                texto_pagina = pagina.get_text()
                
                if texto_pagina.strip() and len(texto_pagina.strip()) > 50:
                    texto_completo += texto_pagina + "\n"
                    print(f"[PDF] Página {num_pagina + 1}: Texto direto extraído")
                else:
                    # PDF é imagem - usar OCR
                    print(f"[PDF] Página {num_pagina + 1}: Aplicando Mistral OCR...")
                    
                    # Converter página para imagem
                    pix = pagina.get_pixmap(matrix=fitz.Matrix(3.0, 3.0))
                    img_data = pix.tobytes("png")
                    
                    # Salvar imagem temporária
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp_img:
                        tmp_img.write(img_data)
                        temp_path = tmp_img.name
                    
                    try:
                        # Aplicar pré-processamento
                        preprocessor = ImagePreprocessor()
                        img_processada, metadata = preprocessor.preprocess_for_mistral(temp_path)
                        
                        # Salvar imagem processada
                        processed_path = temp_path.replace('.png', '_processed.png')
                        cv2.imwrite(processed_path, img_processada)
                        
                        # Executar OCR
                        texto_ocr = self._executar_mistral_ocr(processed_path)
                        texto_completo += texto_ocr + "\n"
                        
                        # Limpar arquivos temporários
                        try:
                            os.remove(temp_path)
                            os.remove(processed_path)
                        except:
                            pass
                            
                    except Exception as e_ocr:
                        print(f"[ERRO] Erro no Mistral OCR: {e_ocr}")
                        # Fallback para Tesseract
                        try:
                            img = Image.open(io.BytesIO(img_data))
                            texto_ocr = pytesseract.image_to_string(img, lang='por+eng')
                            texto_completo += texto_ocr + "\n"
                        except:
                            pass
                        try:
                            os.remove(temp_path)
                        except:
                            pass
            
            doc.close()
            print(f"[MISTRAL OCR] PDF concluído: {len(texto_completo)} caracteres totais")
            return texto_completo.strip()
            
        except Exception as e:
            print(f"[ERRO] Erro no OCR de PDF: {e}")
            return ""
    
    def _executar_mistral_ocr(self, caminho_imagem: str) -> str:
        """Executa OCR usando Mistral Pixtral-12b"""
        try:
            mistral_api_key = os.environ.get("MISTRAL_API_KEY")
            
            if not mistral_api_key:
                raise ValueError("MISTRAL_API_KEY não configurada")
            
            client = Mistral(api_key=mistral_api_key)
            
            # Carregar e codificar imagem
            with open(caminho_imagem, "rb") as img_file:
                img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            # Prompt otimizado
            prompt = (
                "Extraia TODO o texto deste documento de forma precisa. "
                "Mantenha a formatação original, incluindo quebras de linha. "
                "Se houver tabelas, preserve a estrutura. "
                "Não adicione comentários, apenas retorne o texto extraído."
            )
            
            # Chamar API Mistral
            response = client.chat.complete(
                model="pixtral-12b-2409",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": f"data:image/png;base64,{img_base64}"}
                        ]
                    }
                ],
                max_tokens=4096,
                temperature=0.0
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"[ERRO] Falha no Mistral OCR: {e}")
            raise
    
    def _validar_conteudo_documento_especifico(self, nome_documento: str, texto: str) -> bool:
        """
        Valida conteúdo do documento usando termos melhorados
        (preserva lógica original de validação)
        """
        try:
            # Usar validação melhorada se disponível
            try:
                from ..data.termos_validacao_melhorados import validar_documento_melhorado
                TERMOS_MELHORADOS_DISPONIVEIS = True
            except ImportError:
                TERMOS_MELHORADOS_DISPONIVEIS = False
            
            if not texto or len(texto.strip()) < 10:
                return False
            
            # Documentos que usam APENAS validação por caracteres mínimos
            documentos_apenas_caracteres = [
                'Documento de viagem internacional',
                'Comprovante de tempo de residência',
                'Comprovante de residência'
            ]
            
            # Se é documento que usa apenas caracteres mínimos, pular validação por termos
            if nome_documento in documentos_apenas_caracteres:
                print(f"[VALIDAÇÃO] Usando validação por caracteres mínimos para: {nome_documento}")
                return self._validacao_por_caracteres_minimos(nome_documento, texto)
            
            # Para outros documentos, usar validação por termos
            # Mapeamento de documentos para tipos de validação
            mapeamento_validacao = {
                'Carteira de Registro Nacional Migratório': 'CRNM',
                'Comprovante da situação cadastral do CPF': 'CPF',
                'Certidão de antecedentes criminais (Brasil)': 'Antecedentes_Brasil',
                'Atestado antecedentes criminais (país de origem)': 'Antecedentes_Origem',
                'Comprovante de comunicação em português': 'Comunicacao_Portugues',
                'Comprovante de redução de prazo': 'Reducao_Prazo',
                'Certidão de nascimento do filho brasileiro': 'Certidao_Nascimento_Filho'
            }
            
            tipo_validacao = mapeamento_validacao.get(nome_documento)
            
            if tipo_validacao and TERMOS_MELHORADOS_DISPONIVEIS:
                resultado = validar_documento_melhorado(tipo_validacao, texto, minimo_confianca=70)
                termos_encontrados = resultado.get('total_termos_encontrados', 0)
                minimo_termos = resultado.get('minimo_requerido', 0)
                termos_lista = resultado.get('termos_encontrados', [])
                termos_faltando = resultado.get('termos_faltando', [])

                print(
                    f"[VALIDAÇÃO] {nome_documento}: "
                    f"{termos_encontrados}/{minimo_termos} termos obrigatórios encontrados"
                )

                if termos_lista:
                    preview_termos = ', '.join(termos_lista[:5])
                    print(f"[VALIDAÇÃO] Termos identificados: {preview_termos}")
                if not resultado['valido'] and termos_faltando:
                    preview_faltando = ', '.join(termos_faltando[:5])
                    print(f"[VALIDAÇÃO] Termos ausentes: {preview_faltando}")

                return resultado['valido']
            else:
                # Validação básica (fallback)
                return self._validacao_basica(nome_documento, texto)
                
        except Exception as e:
            print(f"[ERRO] Erro na validação de {nome_documento}: {e}")
            return False
    
    def _validacao_por_caracteres_minimos(self, nome_documento: str, texto: str) -> bool:
        """Validação APENAS por caracteres mínimos (sem termos)"""
        try:
            texto_lower = texto.lower()
            
            # Definir mínimo de caracteres baseado no tipo de documento
            caracteres_minimos_por_documento = {
                'Documento de viagem internacional': 100,
                'Comprovante de tempo de residência': 100,
                'Comprovante de residência': 100
            }
            
            caracteres_minimos = caracteres_minimos_por_documento.get(nome_documento, 100)
            
            # Contar apenas caracteres alfanuméricos e espaços (texto útil)
            texto_limpo = ''.join(c for c in texto_lower if c.isalnum() or c.isspace())
            caracteres_validos = len(texto_limpo.strip())
            
            print(f"[VALIDAÇÃO] Caracteres encontrados: {caracteres_validos}")
            print(f"[VALIDAÇÃO] Caracteres mínimos necessários: {caracteres_minimos}")
            
            if caracteres_validos >= caracteres_minimos:
                print(f"[VALIDAÇÃO] ✅ Documento VÁLIDO: {caracteres_validos} caracteres (mínimo: {caracteres_minimos})")
                return True
            else:
                print(f"[VALIDAÇÃO] ❌ Documento INVÁLIDO: apenas {caracteres_validos} caracteres (mínimo: {caracteres_minimos})")
                return False
                
        except Exception as e:
            print(f"[ERRO] Erro na validação por caracteres: {e}")
            return False
    
    def _validacao_basica(self, nome_documento: str, texto: str) -> bool:
        """Validação básica quando termos melhorados não estão disponíveis"""
        texto_lower = texto.lower()
        
        # Termos básicos por tipo de documento
        termos_basicos = {
            'Carteira de Registro Nacional Migratório': ['rne', 'rnm', 'crnm', 'registro nacional', 'documento', 'validade'],
            'Comprovante da situação cadastral do CPF': ['cpf', 'receita federal', 'situação cadastral', 'cadastro'],
            'Certidão de antecedentes criminais (Brasil)': ['antecedentes', 'criminais', 'certidão', 'negativa'],
            'Comprovante de comunicação em português': ['portugu', 'comunicação', 'proficiência', 'celpe'],
            'Comprovante de tempo de residência': ['residência', 'tempo', 'permanência', 'indeterminado'],
            'Documento de viagem internacional': ['passaporte', 'viagem', 'internacional'],
            'Certidão de nascimento do filho brasileiro': ['certidão', 'nascimento', 'brasil', 'brasileiro']
        }

        minimo_termos_por_documento = {
            'Carteira de Registro Nacional Migratório': 2,
            'Comprovante da situação cadastral do CPF': 2,
            'Certidão de antecedentes criminais (Brasil)': 2,
            'Comprovante de comunicação em português': 2,
            'Comprovante de tempo de residência': 1,
            'Documento de viagem internacional': 1,
            'Certidão de nascimento do filho brasileiro': 2
        }

        termos = termos_basicos.get(nome_documento, [])
        termos_encontrados_lista = [termo for termo in termos if termo in texto_lower]
        encontrados = len(termos_encontrados_lista)
        minimo_requerido = minimo_termos_por_documento.get(nome_documento, 1)

        termos_log = ', '.join(termos_encontrados_lista[:5]) if termos_encontrados_lista else 'nenhum'
        print(
            f"[VALIDAÇÃO] {nome_documento}: "
            f"{encontrados}/{minimo_requerido} termos básicos encontrados ({termos_log})"
        )

        if encontrados < minimo_requerido:
            faltando = [t for t in termos if t not in termos_encontrados_lista]
            if faltando:
                print(f"[VALIDAÇÃO] Termos básicos ausentes: {', '.join(faltando[:5])}")

        return encontrados >= minimo_requerido
    
    def _verificar_icone_download_campo(self, campo_tipo: str) -> bool:
        """Verifica se existe o ícone cloud_download próximo ao campo específico"""
        try:
            # Buscar ícone cloud_download próximo ao campo específico
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
                    # Para DOC_REDUCAO, tentar busca específica
                    if campo_tipo == 'DOC_REDUCAO':
                        try:
                            # Buscar especificamente para redução de prazo
                            xpath_reducao = "//input[@id='DOC_REDUCAO']/following-sibling::*//i[@type='cloud_download']"
                            icone = self.driver.find_element(By.XPATH, xpath_reducao)
                            print(f"✅ Ícone cloud_download encontrado para DOC_REDUCAO (busca específica)")
                            return True
                        except:
                            # Busca mais ampla para DOC_REDUCAO
                            try:
                                xpath_reducao_ampla = "//i[@type='cloud_download' and contains(@data-reactid, 'DOC_REDUCAO')]"
                                icone = self.driver.find_element(By.XPATH, xpath_reducao_ampla)
                                print(f"✅ Ícone cloud_download encontrado para DOC_REDUCAO (busca ampla)")
                                return True
                            except:
                                pass
                    
                    # Para DOC_VIAGEM, tentar busca específica
                    if campo_tipo == 'DOC_VIAGEM':
                        try:
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
    
    def _buscar_botao_download_campo(self, campo_id: str):
        """Busca o botão de download específico para o campo"""
        try:
            if campo_id == 'DOC_RNM':
                return self._buscar_elemento_clicavel_doc_rnm()
            elif campo_id == 'DOC_VIAGEM':
                return self._buscar_elemento_clicavel_doc_viagem()
            elif campo_id == 'DOC_REDUCAO':
                return self._buscar_elemento_clicavel_doc_reducao()
            else:
                # Buscar botão genérico
                xpath_botao = f"//div[@id='input__{campo_id}']//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
                try:
                    botao = self.driver.find_element(By.XPATH, xpath_botao)
                    print(f"✅ Botão genérico encontrado via XPath: {xpath_botao}")
                    return botao
                except Exception as e:
                    print(f"❌ Botão genérico não encontrado: {e}")
                    # Fallback para o campo
                    elemento_campo = self.driver.find_element(By.ID, campo_id)
                    return elemento_campo
                    
        except Exception as e:
            print(f"[ERRO] Erro ao buscar botão de download: {e}")
            return None
    
    def _buscar_elemento_clicavel_doc_rnm(self):
        """Busca o elemento clicável para download do DOC_RNM (CRNM)"""
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
    
    def _buscar_elemento_clicavel_doc_reducao(self):
        """Busca o elemento clicável para download do DOC_REDUCAO (Comprovante de redução de prazo)"""
        try:
            # MÉTODO 1: Buscar o botão de download baseado no padrão padrão
            xpath_botao_especifico = "//div[@id='input__DOC_REDUCAO']//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
            
            try:
                botao = self.driver.find_element(By.XPATH, xpath_botao_especifico)
                print(f"✅ Botão DOC_REDUCAO encontrado via XPath específico")
                return botao
            except:
                pass
            
            # MÉTODO 2: Buscar pelo input e navegar para o botão
            xpath_alt = "//input[@id='DOC_REDUCAO']/ancestor::div[contains(@class, 'document-field')]//a[contains(@class, 'button') and .//i[@type='cloud_download']]"
            
            try:
                botao = self.driver.find_element(By.XPATH, xpath_alt)
                print(f"✅ Botão DOC_REDUCAO encontrado via busca alternativa")
                return botao
            except:
                pass
            
            # MÉTODO 3: Buscar pelo ícone específico do DOC_REDUCAO
            xpath_icone_reducao = "//i[@type='cloud_download' and contains(@data-reactid, 'DOC_REDUCAO')]"
            
            try:
                icone = self.driver.find_element(By.XPATH, xpath_icone_reducao)
                print(f"✅ Ícone específico cloud_download encontrado para DOC_REDUCAO")
                return icone
            except:
                pass
            
            # MÉTODO 4: Buscar por qualquer ícone de download próximo ao campo DOC_REDUCAO
            xpath_generico = "//input[@id='DOC_REDUCAO']/following-sibling::*//i[@type='cloud_download']"
            try:
                icone_generico = self.driver.find_element(By.XPATH, xpath_generico)
                print(f"✅ Ícone cloud_download genérico encontrado para DOC_REDUCAO")
                return icone_generico
            except:
                pass
            
            # MÉTODO 5: Buscar em toda a área do formulário próxima ao DOC_REDUCAO
            xpath_area = "//input[@id='DOC_REDUCAO']/ancestor::*[3]//i[@type='cloud_download']"
            try:
                icone_area = self.driver.find_element(By.XPATH, xpath_area)
                print(f"✅ Ícone cloud_download na área encontrado para DOC_REDUCAO")
                return icone_area
            except:
                pass
            
            print(f"❌ Elemento clicável DOC_REDUCAO não encontrado")
            return None
                    
        except Exception as e:
            print(f"[ERRO] Erro ao verificar ícone de DOC_REDUCAO: {e}")
            return None
    
    def _buscar_elemento_clicavel_doc_viagem(self):
        """Busca o elemento clicável para download do DOC_VIAGEM"""
        try:
            # MÉTODO 1: Buscar o botão de download baseado no padrão padrão
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
            
            # MÉTODO 3: Buscar pelo ícone específico do DOC_VIAGEM com data-reactid
            xpath_icone_viagem = "//i[@class='material-icons' and @type='cloud_download' and contains(@data-reactid, 'DOC_VIAGEM') and text()='cloud_download']"
            
            try:
                icone = self.driver.find_element(By.XPATH, xpath_icone_viagem)
                print(f"✅ Ícone específico cloud_download encontrado para DOC_VIAGEM")
                return icone
            except:
                pass
            
            # MÉTODO 4: Busca alternativa mais genérica para DOC_VIAGEM
            xpath_alternativo = "//span[contains(@data-reactid, 'DOC_VIAGEM')]/ancestor::*//i[@type='cloud_download' and text()='cloud_download']"
            try:
                icone_alt = self.driver.find_element(By.XPATH, xpath_alternativo)
                print(f"✅ Ícone cloud_download encontrado para DOC_VIAGEM (busca alternativa)")
                return icone_alt
            except:
                pass
            
            # MÉTODO 5: Buscar por qualquer ícone de download próximo ao campo DOC_VIAGEM
            xpath_generico = "//input[@id='DOC_VIAGEM']/following-sibling::*//i[@type='cloud_download']"
            try:
                icone_generico = self.driver.find_element(By.XPATH, xpath_generico)
                print(f"✅ Ícone cloud_download genérico encontrado para DOC_VIAGEM")
                return icone_generico
            except:
                pass
            
            print(f"❌ Elemento clicável DOC_VIAGEM não encontrado")
            return None
                    
        except Exception as e:
            print(f"[ERRO] Erro ao verificar ícone de DOC_VIAGEM: {e}")
            return None
    
    def _detectar_ultimo_arquivo_adicionado(self, arquivos_antes: List[str], nome_documento: str, timeout: int = 5) -> Optional[str]:
        """Detecta o último arquivo adicionado após o clique"""
        try:
            diretorio_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
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
    
    def _detectar_arquivo_por_nome(self, nome_arquivo_esperado: str, nome_documento: str, timeout: int = 5) -> Optional[str]:
        """Detecta arquivo específico por nome"""
        try:
            diretorio_downloads = os.path.join(os.path.expanduser('~'), 'Downloads')
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
                        
                        # Busca flexível para caracteres especiais
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
    
    def _arquivo_esta_completo(self, caminho_arquivo: str) -> bool:
        """Verifica se o arquivo está completamente baixado"""
        try:
            # Verificar se arquivo existe e tem tamanho > 0
            if not os.path.exists(caminho_arquivo):
                return False
            
            tamanho = os.path.getsize(caminho_arquivo)
            if tamanho == 0:
                return False
            
            # Para PDFs, verificar se não está corrompido
            if caminho_arquivo.lower().endswith('.pdf'):
                try:
                    import fitz
                    doc = fitz.open(caminho_arquivo)
                    doc.close()
                    return True
                except:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def _arquivo_compativel(self, arquivo_real: str, arquivo_esperado: str) -> bool:
        """Verifica se o arquivo real é compatível com o esperado"""
        try:
            import unicodedata
            
            def normalizar_nome(nome):
                # Remover acentos
                nome_normalizado = unicodedata.normalize('NFD', nome)
                nome_normalizado = ''.join(c for c in nome_normalizado if unicodedata.category(c) != 'Mn')
                
                # Substituir caracteres problemáticos
                nome_normalizado = nome_normalizado.replace('?', 'U')
                nome_normalizado = nome_normalizado.replace('?', 'A')
                nome_normalizado = nome_normalizado.replace('?', 'E')
                nome_normalizado = nome_normalizado.replace('?', 'I')
                nome_normalizado = nome_normalizado.replace('?', 'O')
                nome_normalizado = nome_normalizado.replace('?', 'C')
                
                return nome_normalizado.lower().strip()
            
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
