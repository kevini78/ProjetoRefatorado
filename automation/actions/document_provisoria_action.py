# -*- coding: utf-8 -*-
"""
DocumentProvisoriaAction: lógica específica de download e validação de documentos
para Naturalização Provisória.

Diferente da Ordinária, localiza botões de download via estrutura HTML específica:
- Containers com IDs como `input__DOC_RNM`, `input__DOC_RNMREP`, etc.
- Botões com ícones <i type="cloud_download"> para download
- Botões com ícones <i type="visibility"> para visualização
"""
import os
import time
from typing import Any, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class DocumentProvisoriaAction:
    """Action para baixar e validar documentos específicos da Provisória."""
    
    # Mapeamento de nomes de documentos para IDs de containers (baseado no HTML fornecido)
    # Cada documento pode ter múltiplos IDs possíveis
    DOCUMENT_ID_MAP = {
        'Documento de identificacao do representante legal': ['input__DOC_RNMREP', 'input__DOC_REPRESEN'],
        'Carteira de Registro Nacional Migratorio': ['input__DOC_RNM', 'input__DOC_CRNM'],
        'Comprovante de tempo de residência': ['input__DOC_COMPRRESID', 'input__DOC_RESIDENCIA', 'input__DOC_RESID'],
        'Comprovante de tempo de residencia': ['input__DOC_COMPRRESID', 'input__DOC_RESIDENCIA', 'input__DOC_RESID'],
        'Documento de viagem internacional': ['input__DOC_VIAGEM', 'input__DOC_PASSAPORTE'],
    }
    
    def __init__(self, driver: Any, wait: WebDriverWait):
        self.driver = driver
        self.wait = wait
        self.download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
    def _normalizar_nome_documento(self, nome: str) -> str:
        """Normaliza o nome do documento para matching."""
        import unicodedata
        nome_lower = nome.lower().strip()
        # Remover acentos
        nome_norm = unicodedata.normalize('NFKD', nome_lower).encode('ascii', 'ignore').decode('ascii')
        return nome_norm
    
    def _get_container_ids(self, nome_documento: str) -> list[str]:
        """Retorna uma lista de IDs possíveis para o documento especificado."""
        nome_norm = self._normalizar_nome_documento(nome_documento)
        
        # Procurar no mapeamento direto
        for doc_name_key, container_ids in self.DOCUMENT_ID_MAP.items():
            doc_norm = self._normalizar_nome_documento(doc_name_key)
            if nome_norm in doc_norm or doc_norm in nome_norm:
                return container_ids if isinstance(container_ids, list) else [container_ids]
        
        # Tentativas alternativas com palavras-chave
        if 'representante' in nome_norm or 'legal' in nome_norm:
            return ['input__DOC_RNMREP', 'input__DOC_REPRESEN']
        elif 'rnm' in nome_norm or 'migratorio' in nome_norm or 'registro nacional' in nome_norm:
            return ['input__DOC_RNM', 'input__DOC_CRNM']
        elif 'residencia' in nome_norm or 'residência' in nome_norm or 'comprova' in nome_norm:
            return ['input__DOC_COMPRRESID', 'input__DOC_RESIDENCIA', 'input__DOC_RESID']
        elif 'viagem' in nome_norm or 'internacional' in nome_norm or 'passaporte' in nome_norm:
            return ['input__DOC_VIAGEM', 'input__DOC_PASSAPORTE']
        
        return []
    
    def _switch_to_form_iframe(self) -> bool:
        """Garante que estamos no iframe do form-app."""
        try:
            # Voltar ao contexto principal
            self.driver.switch_to.default_content()
            
            # Tentar entrar no iframe
            iframe = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, 'iframe-form-app'))
            )
            self.driver.switch_to.frame(iframe)
            print('[IFRAME] (DocumentProvisoriaAction) Contexto trocado para iframe-form-app')
            return True
        except TimeoutException:
            # Na Provisória, elementos podem estar no contexto principal
            print('[INFO] (DocumentProvisoriaAction) iframe não encontrado, usando contexto principal')
            return True  # Retornar True para continuar no contexto atual
    
    def _documento_existe(self, nome_documento: str) -> tuple[bool, str | None]:
        """Verifica se o documento existe no formulário.
        
        Returns:
            tuple: (existe, container_id_encontrado)
        """
        container_ids = self._get_container_ids(nome_documento)
        if not container_ids:
            print(f'[AVISO] (DocumentProvisoriaAction) IDs de container não encontrados para: {nome_documento}')
            return (False, None)
        
        # Garantir contexto correto
        self._switch_to_form_iframe()
        
        # Tentar cada ID possível
        for container_id in container_ids:
            try:
                # Procurar o container
                container = self.driver.find_element(By.ID, container_id)
                
                # Verificar se há botão de download (ícone cloud_download)
                download_button = container.find_element(
                    By.XPATH,
                    ".//a[contains(@class, 'button--icon')]//i[@type='cloud_download']"
                )
                
                if download_button:
                    print(f'[OK] (DocumentProvisoriaAction) Documento encontrado: {nome_documento} (container: {container_id})')
                    return (True, container_id)
                    
            except (NoSuchElementException, TimeoutException):
                # Tentar próximo ID
                continue
            except Exception as e:
                print(f'[DEBUG] (DocumentProvisoriaAction) Erro ao verificar container {container_id}: {e}')
                continue
        
        print(f'[AVISO] (DocumentProvisoriaAction) Container não encontrado para: {nome_documento} (IDs testados: {", ".join(container_ids)})')
        return (False, None)
    
    def _baixar_documento(self, nome_documento: str, container_id: str) -> str | None:
        """Baixa um documento específico e retorna o caminho do arquivo baixado.
        
        Args:
            nome_documento: Nome do documento
            container_id: ID do container já identificado
        """
        try:
            # Garantir contexto correto
            self._switch_to_form_iframe()
            
            # Procurar o container
            container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, container_id))
            )
            
            # Procurar o link de download (com ícone cloud_download)
            download_link = container.find_element(
                By.XPATH,
                ".//a[contains(@class, 'button--icon')]//i[@type='cloud_download']/ancestor::a"
            )
            
            # Antes de clicar, limpar downloads antigos
            self._limpar_downloads_antigos()
            
            # Clicar no botão de download
            try:
                download_link.click()
            except Exception:
                # Fallback: JavaScript click
                self.driver.execute_script("arguments[0].click();", download_link)
            
            print(f'[DOWNLOAD] (DocumentProvisoriaAction) Iniciando download de: {nome_documento}')
            
            # Aguardar o arquivo ser baixado
            arquivo_baixado = self._aguardar_download()
            
            if arquivo_baixado:
                print(f'[OK] (DocumentProvisoriaAction) Arquivo baixado: {arquivo_baixado}')
                return arquivo_baixado
            else:
                print(f'[ERRO] (DocumentProvisoriaAction) Falha ao aguardar download de: {nome_documento}')
                return None
                
        except (NoSuchElementException, TimeoutException) as e:
            print(f'[ERRO] (DocumentProvisoriaAction) Elemento não encontrado para {nome_documento}: {e}')
            return None
        except Exception as e:
            print(f'[ERRO] (DocumentProvisoriaAction) Erro ao baixar {nome_documento}: {e}')
            return None
    
    def _limpar_downloads_antigos(self):
        """Remove arquivos PDF antigos da pasta de downloads."""
        try:
            for arquivo in os.listdir(self.download_dir):
                if arquivo.endswith('.pdf') or arquivo.endswith('.crdownload'):
                    caminho = os.path.join(self.download_dir, arquivo)
                    try:
                        os.remove(caminho)
                    except Exception:
                        pass
        except Exception:
            pass
    
    def _aguardar_download(self, timeout: int = 30) -> str | None:
        """Aguarda um arquivo PDF ser baixado e retorna seu caminho."""
        inicio = time.time()
        
        while (time.time() - inicio) < timeout:
            try:
                # Listar arquivos PDF na pasta de downloads
                arquivos = [f for f in os.listdir(self.download_dir) if f.endswith('.pdf')]
                
                if arquivos:
                    # Pegar o arquivo mais recente
                    arquivos_full = [os.path.join(self.download_dir, f) for f in arquivos]
                    arquivo_mais_recente = max(arquivos_full, key=os.path.getmtime)
                    
                    # Verificar se o arquivo não está sendo baixado (.crdownload)
                    if not arquivo_mais_recente.endswith('.crdownload'):
                        # Esperar um pouco para garantir que o download finalizou
                        time.sleep(1)
                        if os.path.exists(arquivo_mais_recente):
                            return arquivo_mais_recente
                
                time.sleep(0.5)
            except Exception:
                time.sleep(0.5)
        
        print(f'[ERRO] (DocumentProvisoriaAction) Timeout ao aguardar download')
        return None
    
    def _validar_documento_com_ocr(self, caminho_arquivo: str, nome_documento: str) -> bool:
        """Valida um documento usando OCR."""
        try:
            # Importar action de Ordinária para reusar OCR
            from automation.actions.document_ordinaria_action import DocumentAction
            
            # Criar uma instância temporária apenas para usar o OCR
            doc_action_temp = DocumentAction(self.driver, self.wait)
            
            # Extrair texto do PDF usando OCR da Ordinária (método correto)
            texto_extraido = doc_action_temp._processar_arquivo_ocr(caminho_arquivo, nome_documento)
            
            if not texto_extraido or len(texto_extraido.strip()) < 10:
                print(f'[AVISO] (DocumentProvisoriaAction) Texto extraído muito curto ou vazio para: {nome_documento}')
                return False
            
            # Validação básica: verificar se contém palavras-chave relevantes
            texto_lower = texto_extraido.lower()
            nome_norm = self._normalizar_nome_documento(nome_documento)
            
            # Palavras-chave por tipo de documento
            keywords_map = {
                'representante': ['representante', 'responsável', 'legal', 'cpf', 'rg', 'identidade'],
                'rnm': ['rnm', 'registro', 'migratorio', 'migratório', 'estrangeiro', 'policia federal', 'polícia federal'],
                'residencia': ['residência', 'residencia', 'endereço', 'endereco', 'comprovante', 'moradia'],
                'residência': ['residência', 'residencia', 'endereço', 'endereco', 'comprovante', 'moradia'],
                'viagem': ['passaporte', 'viagem', 'internacional', 'passport', 'documento de viagem'],
            }
            
            # Encontrar palavras-chave relevantes
            keywords_relevantes = []
            for key_group, keywords in keywords_map.items():
                if key_group in nome_norm:
                    keywords_relevantes.extend(keywords)
            
            # Verificar se pelo menos uma palavra-chave está presente
            if keywords_relevantes:
                for keyword in keywords_relevantes:
                    if keyword in texto_lower:
                        print(f'[OK] (DocumentProvisoriaAction) Documento validado com palavra-chave "{keyword}": {nome_documento}')
                        return True
                
                print(f'[AVISO] (DocumentProvisoriaAction) Nenhuma palavra-chave encontrada para: {nome_documento}')
                print(f'[DEBUG] Texto extraído (primeiros 200 caracteres): {texto_extraido[:200]}')
                # Retornar True mesmo sem keywords específicas, se há texto suficiente
                if len(texto_extraido.strip()) > 50:
                    print(f'[OK] (DocumentProvisoriaAction) Documento validado por tamanho de texto suficiente')
                    return True
                return False
            else:
                # Sem keywords específicas, validar por tamanho de texto
                if len(texto_extraido.strip()) > 50:
                    print(f'[OK] (DocumentProvisoriaAction) Documento validado: {nome_documento}')
                    return True
                return False
                
        except Exception as e:
            print(f'[ERRO] (DocumentProvisoriaAction) Erro ao validar documento {nome_documento}: {e}')
            return False
    
    def baixar_e_validar_documento_individual(self, nome_documento: str) -> bool:
        """Baixa e valida um documento individual.
        
        Retorna True se o documento foi baixado e validado com sucesso.
        """
        print(f'[INICIO] (DocumentProvisoriaAction) Processando documento: {nome_documento}')
        
        # 1. Verificar se o documento existe
        existe, container_id = self._documento_existe(nome_documento)
        if not existe:
            print(f'[FALHA] (DocumentProvisoriaAction) Documento não encontrado: {nome_documento}')
            return False
        
        # 2. Baixar o documento
        caminho_arquivo = self._baixar_documento(nome_documento, container_id)
        if not caminho_arquivo:
            print(f'[FALHA] (DocumentProvisoriaAction) Falha ao baixar: {nome_documento}')
            return False
        
        # 3. Validar com OCR
        validado = self._validar_documento_com_ocr(caminho_arquivo, nome_documento)
        
        if validado:
            print(f'[SUCESSO] (DocumentProvisoriaAction) Documento validado: {nome_documento}')
        else:
            print(f'[FALHA] (DocumentProvisoriaAction) Documento não passou na validação: {nome_documento}')
        
        # 4. Limpar arquivo baixado
        try:
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
        except Exception:
            pass
        
        return validado
    
    def baixar_e_validar_todos_documentos(self, lista_documentos: list[str]) -> Dict[str, bool]:
        """Baixa e valida todos os documentos da lista.
        
        Retorna um dicionário mapeando nome do documento para status de validação.
        """
        resultados = {}
        
        for nome_doc in lista_documentos:
            try:
                resultado = self.baixar_e_validar_documento_individual(nome_doc)
                resultados[nome_doc] = resultado
            except Exception as e:
                print(f'[ERRO] (DocumentProvisoriaAction) Exceção ao processar {nome_doc}: {e}')
                resultados[nome_doc] = False
        
        return resultados
