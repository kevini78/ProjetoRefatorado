"""
Configuração avançada de segurança - Conforme Posic/MCTIC e ISO 27001/27002
"""

import os
import logging
import hashlib
import secrets
import base64
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import argon2
import ipaddress
import re
from typing import Dict, List, Optional, Tuple, Any
import time

class SecurityConfigEnhanced:
    """
    Configuração avançada de segurança implementando:
    - Posic/MCTIC (Portaria nº 4.711/2017)
    - ISO/IEC 27001/27002
    - OWASP Top 10
    - NIST Cybersecurity Framework
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.security_logger = self._setup_security_logging()
        self._setup_encryption()
        self._setup_session_security()
        self._setup_access_control()
        self._setup_audit_trail()
        
    def _setup_logging(self) -> logging.Logger:
        """Configura sistema de logging principal"""
        logger = logging.getLogger('security_enhanced')
        logger.setLevel(logging.DEBUG)
        
        if not os.path.exists('logs'):
            os.makedirs('logs', mode=0o750)
            
        handler = logging.FileHandler(
            'logs/security_enhanced.log', 
            mode='a',
            encoding='utf-8'
        )
        handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
        
    def _setup_security_logging(self) -> logging.Logger:
        """Configura sistema de logging de segurança específico"""
        security_logger = logging.getLogger('security_audit')
        security_logger.setLevel(logging.INFO)
        
        security_handler = logging.FileHandler(
            'logs/security_audit.log',
            mode='a',
            encoding='utf-8'
        )
        security_handler.setLevel(logging.INFO)
        
        security_formatter = logging.Formatter(
            '%(asctime)s - SECURITY_AUDIT - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(security_formatter)
        security_logger.addHandler(security_handler)
        
        return security_logger
        
    def _setup_encryption(self):
        """Configura sistema de criptografia multicamadas"""
        # Chave principal para Fernet (AES-128)
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            self.logger.critical("NOVA CHAVE DE CRIPTOGRAFIA GERADA - SALVE EM VARIÁVEL DE AMBIENTE")
            
        self.fernet = Fernet(encryption_key.encode())
        
        # Geração de chave RSA para dados altamente sensíveis
        self._generate_rsa_keys()
        
        # Setup Argon2 para senhas
        self.password_hasher = argon2.PasswordHasher(
            time_cost=3,
            memory_cost=65536,  # 64MB
            parallelism=1,
            hash_len=64,
            salt_len=32
        )
        
    def _generate_rsa_keys(self):
        """Gera chaves RSA-4096 para dados críticos"""
        try:
            # Verificar se já existem chaves
            if os.path.exists('keys/private_key.pem') and os.path.exists('keys/public_key.pem'):
                self._load_rsa_keys()
                return
                
            if not os.path.exists('keys'):
                os.makedirs('keys', mode=0o700)
                
            # Gerar nova chave RSA-4096
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096,
            )
            
            # Salvar chave privada
            with open('keys/private_key.pem', 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
                
            # Salvar chave pública
            public_key = private_key.public_key()
            with open('keys/public_key.pem', 'wb') as f:
                f.write(public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
                
            os.chmod('keys/private_key.pem', 0o600)
            os.chmod('keys/public_key.pem', 0o644)
            
            self.private_key = private_key
            self.public_key = public_key
            
            self.logger.info("Novas chaves RSA-4096 geradas")
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar chaves RSA: {e}")
            self.private_key = None
            self.public_key = None
            
    def _load_rsa_keys(self):
        """Carrega chaves RSA existentes"""
        try:
            with open('keys/private_key.pem', 'rb') as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                )
                
            with open('keys/public_key.pem', 'rb') as f:
                self.public_key = serialization.load_pem_public_key(f.read())
                
            self.logger.info("Chaves RSA carregadas com sucesso")
            
        except Exception as e:
            self.logger.error(f"Erro ao carregar chaves RSA: {e}")
            self.private_key = None
            self.public_key = None
            
    def _setup_session_security(self):
        """Configura controles de sessão"""
        self.session_timeout = 3600  # 1 hora
        self.max_concurrent_sessions = 3
        self.session_regeneration_interval = 900  # 15 minutos
        self.active_sessions = {}
        
    def _setup_access_control(self):
        """Configura controle de acesso baseado em papéis (RBAC)"""
        self.roles = {
            'admin': {
                'permissions': ['*'],  # Todas as permissões
                'description': 'Administrador do sistema'
            },
            'analyst': {
                'permissions': [
                    'view_processes',
                    'analyze_documents', 
                    'approve_opinions',
                    'generate_reports'
                ],
                'description': 'Analista de processos'
            },
            'viewer': {
                'permissions': [
                    'view_processes',
                    'view_reports'
                ],
                'description': 'Visualizador de dados'
            },
            'auditor': {
                'permissions': [
                    'view_audit_logs',
                    'view_security_reports',
                    'view_processes'
                ],
                'description': 'Auditor de segurança'
            }
        }
        
    def _setup_audit_trail(self):
        """Configura trilha de auditoria"""
        self.audit_events = {
            'LOGIN_SUCCESS': 'Usuario logado com sucesso',
            'LOGIN_FAILURE': 'Falha no login',
            'LOGOUT': 'Usuario deslogado',
            'FILE_ACCESS': 'Acesso a arquivo',
            'DATA_EXPORT': 'Exportacao de dados',
            'SYSTEM_CONFIG': 'Configuracao do sistema',
            'PERMISSION_DENIED': 'Acesso negado',
            'SUSPICIOUS_ACTIVITY': 'Atividade suspeita detectada'
        }
        
    def hash_password(self, password: str) -> str:
        """Cria hash seguro da senha usando Argon2"""
        try:
            return self.password_hasher.hash(password)
        except Exception as e:
            self.logger.error(f"Erro ao fazer hash da senha: {e}")
            raise
            
    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verifica senha contra hash Argon2"""
        try:
            self.password_hasher.verify(password_hash, password)
            return True
        except argon2.exceptions.VerifyMismatchError:
            return False
        except Exception as e:
            self.logger.error(f"Erro ao verificar senha: {e}")
            return False
            
    def encrypt_data_aes256(self, data: str) -> str:
        """Criptografa dados com AES-256"""
        try:
            # Gerar chave AES-256 aleatória
            key = secrets.token_bytes(32)  # 256 bits
            iv = secrets.token_bytes(16)   # 128 bits
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            encryptor = cipher.encryptor()
            
            # Padding PKCS7
            data_bytes = data.encode('utf-8')
            pad_len = 16 - (len(data_bytes) % 16)
            padded_data = data_bytes + bytes([pad_len] * pad_len)
            
            ciphertext = encryptor.update(padded_data) + encryptor.finalize()
            
            # Retornar key+iv+ciphertext codificado em base64
            result = base64.b64encode(key + iv + ciphertext).decode('utf-8')
            
            self.security_logger.info("Dados criptografados com AES-256")
            return result
            
        except Exception as e:
            self.logger.error(f"Erro ao criptografar dados AES-256: {e}")
            raise
            
    def decrypt_data_aes256(self, encrypted_data: str) -> str:
        """Descriptografa dados AES-256"""
        try:
            data = base64.b64decode(encrypted_data.encode('utf-8'))
            
            key = data[:32]
            iv = data[32:48]
            ciphertext = data[48:]
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()
            
            # Remover padding PKCS7
            pad_len = padded_data[-1]
            data_bytes = padded_data[:-pad_len]
            
            return data_bytes.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Erro ao descriptografar dados AES-256: {e}")
            raise
            
    def encrypt_sensitive_data_rsa(self, data: str) -> str:
        """Criptografa dados sensíveis com RSA-4096"""
        if not self.public_key:
            raise RuntimeError("Chave RSA não disponível")
            
        try:
            data_bytes = data.encode('utf-8')
            
            # RSA só pode criptografar dados menores que o tamanho da chave
            # Para dados maiores, usar criptografia híbrida
            if len(data_bytes) > 446:  # 4096/8 - 42 (padding)
                # Usar AES-256 para os dados e RSA para a chave AES
                aes_key = secrets.token_bytes(32)
                iv = secrets.token_bytes(16)
                
                cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
                encryptor = cipher.encryptor()
                
                # Padding PKCS7
                pad_len = 16 - (len(data_bytes) % 16)
                padded_data = data_bytes + bytes([pad_len] * pad_len)
                
                ciphertext = encryptor.update(padded_data) + encryptor.finalize()
                
                # Criptografar chave AES com RSA
                encrypted_key = self.public_key.encrypt(
                    aes_key + iv,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                # Combinar chave criptografada + dados criptografados
                result = base64.b64encode(encrypted_key + ciphertext).decode('utf-8')
                
            else:
                # Criptografia RSA direta para dados pequenos
                encrypted = self.public_key.encrypt(
                    data_bytes,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                result = base64.b64encode(encrypted).decode('utf-8')
                
            self.security_logger.info("Dados sensíveis criptografados com RSA")
            return result
            
        except Exception as e:
            self.logger.error(f"Erro ao criptografar dados RSA: {e}")
            raise
            
    def decrypt_sensitive_data_rsa(self, encrypted_data: str) -> str:
        """Descriptografa dados sensíveis RSA"""
        if not self.private_key:
            raise RuntimeError("Chave RSA privada não disponível")
            
        try:
            data = base64.b64decode(encrypted_data.encode('utf-8'))
            
            if len(data) > 512:  # Dados híbridos (RSA + AES)
                # Extrair chave criptografada (512 bytes para RSA-4096)
                encrypted_key = data[:512]
                ciphertext = data[512:]
                
                # Descriptografar chave AES
                key_iv = self.private_key.decrypt(
                    encrypted_key,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
                aes_key = key_iv[:32]
                iv = key_iv[32:48]
                
                # Descriptografar dados com AES
                cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
                decryptor = cipher.decryptor()
                
                padded_data = decryptor.update(ciphertext) + decryptor.finalize()
                
                # Remover padding
                pad_len = padded_data[-1]
                data_bytes = padded_data[:-pad_len]
                
            else:
                # Descriptografia RSA direta
                data_bytes = self.private_key.decrypt(
                    data,
                    padding.OAEP(
                        mgf=padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(),
                        label=None
                    )
                )
                
            return data_bytes.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Erro ao descriptografar dados RSA: {e}")
            raise
            
    def sanitize_input(self, data: str, context: str = 'general') -> str:
        """Sanitiza entrada do usuário conforme contexto"""
        if not isinstance(data, str):
            data = str(data)
            
        # Sanitização geral
        data = data.strip()
        
        # Contextos específicos
        if context == 'filename':
            # Para nomes de arquivo
            data = re.sub(r'[<>:"/\\|?*]', '', data)
            data = re.sub(r'\.\.', '', data)  # Prevenir path traversal
            
        elif context == 'sql':
            # Para prevenir SQL injection
            data = data.replace("'", "''")
            data = re.sub(r'[;--]', '', data)
            
        elif context == 'html':
            # Para prevenir XSS
            data = data.replace('<', '&lt;')
            data = data.replace('>', '&gt;')
            data = data.replace('"', '&quot;')
            data = data.replace("'", '&#x27;')
            
        elif context == 'process_code':
            # Para códigos de processo
            data = re.sub(r'[^0-9.\-/]', '', data)
            
        return data[:1000]  # Limitar tamanho
        
    def validate_ip_access(self, ip_address: str) -> bool:
        """Valida se IP tem permissão de acesso"""
        try:
            ip = ipaddress.ip_address(ip_address)
            
            # Redes permitidas (pode ser configurado via variável de ambiente)
            allowed_networks = [
                ipaddress.ip_network('127.0.0.0/8'),    # localhost
                ipaddress.ip_network('10.0.0.0/8'),     # rede privada
                ipaddress.ip_network('172.16.0.0/12'),  # rede privada
                ipaddress.ip_network('192.168.0.0/16'), # rede privada
            ]
            
            # Verificar se IP está em rede permitida
            for network in allowed_networks:
                if ip in network:
                    return True
                    
            return False
            
        except Exception as e:
            self.logger.error(f"Erro ao validar IP {ip_address}: {e}")
            return False
            
    def check_permission(self, user_role: str, required_permission: str) -> bool:
        """Verifica se usuário tem permissão necessária"""
        if user_role not in self.roles:
            return False
            
        user_permissions = self.roles[user_role]['permissions']
        
        # Admin tem todas as permissões
        if '*' in user_permissions:
            return True
            
        return required_permission in user_permissions
        
    def log_security_event(self, event_type: str, user_id: str, 
                          details: Dict[str, Any], ip_address: str = None):
        """Registra evento de segurança"""
        try:
            timestamp = datetime.now().isoformat()
            
            log_entry = {
                'timestamp': timestamp,
                'event_type': event_type,
                'user_id': user_id,
                'ip_address': ip_address or 'unknown',
                'details': details,
                'severity': self._get_event_severity(event_type)
            }
            
            # Log estruturado
            self.security_logger.info(json.dumps(log_entry, ensure_ascii=False))
            
            # Alertas para eventos críticos
            if log_entry['severity'] == 'CRITICAL':
                self._send_security_alert(log_entry)
                
        except Exception as e:
            self.logger.error(f"Erro ao registrar evento de segurança: {e}")
            
    def _get_event_severity(self, event_type: str) -> str:
        """Determina severidade do evento"""
        critical_events = ['LOGIN_FAILURE', 'PERMISSION_DENIED', 'SUSPICIOUS_ACTIVITY']
        high_events = ['DATA_EXPORT', 'SYSTEM_CONFIG']
        
        if event_type in critical_events:
            return 'CRITICAL'
        elif event_type in high_events:
            return 'HIGH'
        else:
            return 'INFO'
            
    def _send_security_alert(self, log_entry: Dict[str, Any]):
        """Envia alerta de segurança para administradores"""
        # Implementar notificação (email, Slack, etc.)
        self.logger.critical(f"ALERTA DE SEGURANÇA: {log_entry}")
        
    def get_security_headers(self) -> Dict[str, str]:
        """Retorna headers de segurança HTTP"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'"
            ),
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            )
        }
        
    def cleanup_old_files(self, directory: str, max_age_hours: int = 24):
        """Remove arquivos antigos com log de auditoria"""
        try:
            current_time = datetime.now()
            max_age = timedelta(hours=max_age_hours)
            files_removed = 0
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if current_time - file_time > max_age:
                        os.remove(file_path)
                        files_removed += 1
                        
                        self.log_security_event(
                            'FILE_CLEANUP',
                            'system',
                            {'file': file_path, 'age_hours': (current_time - file_time).total_seconds() / 3600}
                        )
                        
            self.logger.info(f"Limpeza concluída: {files_removed} arquivos removidos de {directory}")
            
        except Exception as e:
            self.logger.error(f"Erro na limpeza de arquivos: {e}")
            
    def generate_secure_token(self, length: int = 32) -> str:
        """Gera token seguro"""
        return secrets.token_urlsafe(length)
        
    def validate_file_upload(self, filename: str, file_content: bytes, 
                           allowed_types: List[str]) -> Tuple[bool, str]:
        """Valida upload de arquivo"""
        try:
            # Verificar extensão
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext not in allowed_types:
                return False, f"Tipo de arquivo não permitido: {file_ext}"
                
            # Verificar tamanho (16MB max)
            if len(file_content) > 16 * 1024 * 1024:
                return False, "Arquivo muito grande (máximo 16MB)"
                
            # Verificar nome do arquivo
            sanitized_name = self.sanitize_input(filename, 'filename')
            if sanitized_name != filename:
                return False, "Nome de arquivo contém caracteres inválidos"
                
            # Verificar conteúdo malicioso básico
            if b'<script' in file_content.lower():
                return False, "Conteúdo potencialmente malicioso detectado"
                
            return True, "Arquivo válido"
            
        except Exception as e:
            self.logger.error(f"Erro na validação de arquivo: {e}")
            return False, "Erro na validação"

# Instância global
enhanced_security = SecurityConfigEnhanced()
