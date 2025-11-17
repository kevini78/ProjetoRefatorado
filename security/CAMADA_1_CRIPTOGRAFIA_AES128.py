#!/usr/bin/env python3
"""
CAMADA 1: CRIPTOGRAFIA AES-128 PARA ARQUIVOS E DADOS SENSÍVEIS
Arquivo: security_config.py
"""

import os
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import secrets
from datetime import datetime, timedelta
import hashlib

class SecurityConfig:
    """
    Configuração centralizada de segurança para o sistema
    CAMADA 1: Criptografia AES-128
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_encryption()
        self._setup_logging()
        
    def _setup_encryption(self):
        """Configura sistema de criptografia AES-128"""
        # Gerar chave de criptografia se não existir
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if not encryption_key:
            # Gerar nova chave e salvar em variável de ambiente
            encryption_key = Fernet.generate_key().decode()
            self.logger.info("Nova chave de criptografia gerada")
        
        self.fernet = Fernet(encryption_key.encode())
        
    def _setup_logging(self):
        """Configura sistema de logging de segurança"""
        # Configurar logger de segurança
        security_logger = logging.getLogger('security')
        security_logger.setLevel(logging.INFO)
        
        # Handler para arquivo de log de segurança
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        security_handler = logging.FileHandler('logs/security.log')
        security_handler.setLevel(logging.INFO)
        
        # Formato do log
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(formatter)
        security_logger.addHandler(security_handler)
        
        self.security_logger = security_logger
    
    def encrypt_file(self, file_path: str) -> str:
        """Criptografa um arquivo usando AES-128"""
        try:
            with open(file_path, 'rb') as file:
                data = file.read()
            
            encrypted_data = self.fernet.encrypt(data)
            encrypted_path = f"{file_path}.encrypted"
            
            with open(encrypted_path, 'wb') as file:
                file.write(encrypted_data)
            
            # Log da operação
            self.security_logger.info(f"Arquivo criptografado: {file_path}")
            
            # Remover arquivo original
            os.remove(file_path)
            
            return encrypted_path
            
        except Exception as e:
            self.logger.error(f"Erro ao criptografar arquivo {file_path}: {e}")
            raise
    
    def decrypt_file(self, encrypted_file_path: str) -> str:
        """Descriptografa um arquivo usando AES-128"""
        try:
            with open(encrypted_file_path, 'rb') as file:
                encrypted_data = file.read()
            
            decrypted_data = self.fernet.decrypt(encrypted_data)
            decrypted_path = encrypted_file_path.replace('.encrypted', '')
            
            with open(decrypted_path, 'wb') as file:
                file.write(decrypted_data)
            
            # Log da operação
            self.security_logger.info(f"Arquivo descriptografado: {encrypted_file_path}")
            
            return decrypted_path
            
        except Exception as e:
            self.logger.error(f"Erro ao descriptografar arquivo {encrypted_file_path}: {e}")
            raise
    
    def encrypt_text(self, text: str) -> str:
        """Criptografa texto sensível usando AES-128"""
        try:
            encrypted = self.fernet.encrypt(text.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"Erro ao criptografar texto: {e}")
            raise
    
    def decrypt_text(self, encrypted_text: str) -> str:
        """Descriptografa texto criptografado usando AES-128"""
        try:
            encrypted = base64.b64decode(encrypted_text.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"Erro ao descriptografar texto: {e}")
            raise
    
    def hash_sensitive_data(self, data: str) -> str:
        """Cria hash SHA-256 de dados sensíveis para comparação sem exposição"""
        return hashlib.sha256(data.encode()).hexdigest()

# Instância global
security_config = SecurityConfig()
