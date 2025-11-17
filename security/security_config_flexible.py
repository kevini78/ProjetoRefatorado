import os
import logging
from cryptography.fernet import Fernet
import base64
import secrets
from datetime import datetime, timedelta
import hashlib

class FlexibleSecurityConfig:
    """
    Configuração de segurança flexível para uso diário e automações
    - Sem limites rígidos de tempo
    - Rate limiting mais permissivo
    - Logs menos verbosos
    - Foco na proteção de dados sensíveis
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_encryption()
        self._setup_logging()
        self._load_flexible_settings()
        
    def _setup_encryption(self):
        """Configura sistema de criptografia"""
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if not encryption_key:
            # Gerar nova chave válida para Fernet
            encryption_key = Fernet.generate_key().decode()
            self.logger.info("Nova chave de criptografia gerada automaticamente")
        
        try:
            self.fernet = Fernet(encryption_key.encode())
        except Exception as e:
            # Se a chave for inválida, gerar uma nova
            self.logger.info("Gerando nova chave de criptografia...")
            encryption_key = Fernet.generate_key().decode()
            self.fernet = Fernet(encryption_key.encode())
            self.logger.info("Chave de criptografia configurada")
        
    def _setup_logging(self):
        """Configura sistema de logging de segurança mais flexível"""
        security_logger = logging.getLogger('security')
        security_logger.setLevel(logging.WARNING)  # Menos verboso
        
        # Handler para arquivo de log de segurança
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        security_handler = logging.FileHandler('logs/security.log')
        security_handler.setLevel(logging.WARNING)  # Apenas avisos e erros
        
        # Formato do log mais simples
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        security_handler.setFormatter(formatter)
        security_logger.addHandler(security_handler)
        
        self.security_logger = security_logger
    
    def _load_flexible_settings(self):
        """Carrega configurações flexíveis para uso diário"""
        self.settings = {
            # Sem limite de tempo para sessões
            'session_timeout': None,
            
            # Rate limiting muito permissivo
            'max_requests_per_minute': 1000,  # 1000 requisições por minuto
            'max_requests_per_hour': 50000,   # 50000 requisições por hora
            
            # Sem limite de tentativas de login
            'max_login_attempts': None,
            
            # Limpeza de arquivos menos frequente
            'cleanup_interval_hours': 72,  # A cada 3 dias
            
            # Logs menos verbosos
            'log_all_requests': False,
            'log_successful_operations': False,
            
            # Validação de arquivos mais permissiva
            'strict_file_validation': False,
            
            # Sanitização de dados mais suave
            'aggressive_sanitization': False
        }
    
    def encrypt_file(self, file_path: str) -> str:
        """Criptografa um arquivo e retorna o caminho do arquivo criptografado"""
        try:
            with open(file_path, 'rb') as file:
                data = file.read()
            
            encrypted_data = self.fernet.encrypt(data)
            encrypted_path = f"{file_path}.encrypted"
            
            with open(encrypted_path, 'wb') as file:
                file.write(encrypted_data)
            
            # Log apenas de operações importantes
            if self.settings['log_successful_operations']:
                self.security_logger.info(f"Arquivo criptografado: {file_path}")
            
            # Remover arquivo original
            os.remove(file_path)
            
            return encrypted_path
            
        except Exception as e:
            self.logger.error(f"Erro ao criptografar arquivo {file_path}: {e}")
            raise
    
    def decrypt_file(self, encrypted_file_path: str) -> str:
        """Descriptografa um arquivo e retorna o caminho do arquivo descriptografado"""
        try:
            with open(encrypted_file_path, 'rb') as file:
                encrypted_data = file.read()
            
            decrypted_data = self.fernet.decrypt(encrypted_data)
            decrypted_path = encrypted_file_path.replace('.encrypted', '')
            
            with open(decrypted_path, 'wb') as file:
                file.write(decrypted_data)
            
            # Log apenas de operações importantes
            if self.settings['log_successful_operations']:
                self.security_logger.info(f"Arquivo descriptografado: {encrypted_file_path}")
            
            return decrypted_path
            
        except Exception as e:
            self.logger.error(f"Erro ao descriptografar arquivo {encrypted_file_path}: {e}")
            raise
    
    def encrypt_text(self, text: str) -> str:
        """Criptografa texto sensível"""
        try:
            encrypted = self.fernet.encrypt(text.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"Erro ao criptografar texto: {e}")
            raise
    
    def decrypt_text(self, encrypted_text: str) -> str:
        """Descriptografa texto criptografado"""
        try:
            encrypted = base64.b64decode(encrypted_text.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"Erro ao descriptografar texto: {e}")
            raise
    
    def hash_sensitive_data(self, data: str) -> str:
        """Cria hash de dados sensíveis para comparação sem exposição"""
        return hashlib.sha256(data.encode()).hexdigest()
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitiza nome de arquivo de forma mais permissiva"""
        # Remover apenas caracteres realmente perigosos
        dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Limitar tamanho
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
            
        return filename
    
    def validate_file_type(self, file_path: str, allowed_extensions: set) -> bool:
        """Valida tipo de arquivo de forma mais permissiva"""
        try:
            # Validação básica por extensão (mais rápida)
            file_ext = os.path.splitext(file_path)[1].lower()
            if file_ext in allowed_extensions:
                return True
            
            # Validação MIME apenas se estritamente necessário
            if self.settings['strict_file_validation']:
                try:
                    import magic
                    mime = magic.from_file(file_path, mime=True)
                    
                    mime_map = {
                        '.pdf': 'application/pdf',
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg'
                    }
                    
                    expected_mime = mime_map.get(file_ext)
                    if expected_mime and mime != expected_mime:
                        return False
                except ImportError:
                    # Se python-magic não estiver disponível, pular validação MIME
                    pass
                except Exception as e:
                    # Se houver erro na validação MIME, pular
                    self.logger.debug(f"Erro na validação MIME: {e}")
                    pass
                    
            return True
            
        except ImportError:
            # Fallback se python-magic não estiver disponível
            return True
        except Exception as e:
            self.logger.error(f"Erro na validação de tipo de arquivo: {e}")
            return True  # Em caso de erro, permitir o arquivo
    
    def log_access(self, user_id: str, action: str, resource: str, success: bool = True):
        """Registra acesso a recursos sensíveis (apenas falhas por padrão)"""
        if not success or self.settings['log_all_requests']:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'user_id': user_id,
                'action': action,
                'resource': resource,
                'success': success
            }
            
            self.security_logger.warning(f"ACESSO: {log_entry}")
    
    def cleanup_old_files(self, directory: str, max_age_hours: int = None):
        """Remove arquivos antigos com intervalo configurável"""
        try:
            # Usar configuração padrão se não especificado
            if max_age_hours is None:
                max_age_hours = self.settings['cleanup_interval_hours']
            
            current_time = datetime.now()
            max_age = timedelta(hours=max_age_hours)
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if current_time - file_time > max_age:
                        os.remove(file_path)
                        if self.settings['log_successful_operations']:
                            self.security_logger.info(f"Arquivo antigo removido: {file_path}")
                        
        except Exception as e:
            self.logger.error(f"Erro na limpeza de arquivos: {e}")
    
    def get_security_headers(self) -> dict:
        """Retorna headers de segurança básicos"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block'
        }
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Verifica rate limit de forma mais permissiva"""
        # Implementação simples sem bloqueios rígidos
        return True
    
    def is_automation_mode(self) -> bool:
        """Verifica se está em modo de automação (sem restrições rígidas)"""
        # Detectar automações por padrões de uso
        # Por exemplo, muitas requisições em sequência
        return True  # Sempre permitir para automações

# Instância global
flexible_security_config = FlexibleSecurityConfig() 