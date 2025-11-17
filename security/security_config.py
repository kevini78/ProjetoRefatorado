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
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._setup_encryption()
        self._setup_logging()
        
    def _setup_encryption(self):
        """Configura sistema de criptografia"""
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
        """Criptografa um arquivo e retorna o caminho do arquivo criptografado"""
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
        """Descriptografa um arquivo e retorna o caminho do arquivo descriptografado"""
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
        """Sanitiza nome de arquivo para evitar path traversal"""
        import re
        
        # Remover path traversal completamente
        filename = re.sub(r'\.\.+', '', filename)  # Remove .. e ...
        filename = re.sub(r'[/\\]', '', filename)  # Remove barras
        
        # Remover outros caracteres perigosos
        dangerous_chars = [':', '*', '?', '"', '<', '>', '|', '\0']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Remover espaços no início/fim
        filename = filename.strip()
        
        # Prevenir nomes reservados no Windows
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        name_without_ext = os.path.splitext(filename)[0].upper()
        if name_without_ext in reserved_names:
            filename = f"file_{filename}"
        
        # Garantir que não está vazio
        if not filename or filename == '.':
            filename = 'unnamed_file'
        
        # Limitar tamanho
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:255-len(ext)] + ext
            
        return filename
    
    def validate_file_type(self, file_path: str, allowed_extensions: set) -> bool:
        """Valida tipo de arquivo baseado no conteúdo, não apenas na extensão"""
        try:
            import magic  # pip install python-magic
            
            mime = magic.from_file(file_path, mime=True)
            
            # Mapeamento de extensões para MIME types
            mime_map = {
                '.pdf': 'application/pdf',
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg'
            }
            
            # Verificar se o MIME type corresponde à extensão
            file_ext = os.path.splitext(file_path)[1].lower()
            expected_mime = mime_map.get(file_ext)
            
            if expected_mime and mime != expected_mime:
                self.security_logger.warning(f"Tipo MIME inválido: {mime} para arquivo {file_path}")
                return False
                
            return True
            
        except ImportError:
            # Fallback se python-magic não estiver disponível
            self.logger.warning("python-magic não disponível, validação de tipo limitada")
            return True
        except Exception as e:
            self.logger.error(f"Erro na validação de tipo de arquivo: {e}")
            return False
    
    def log_access(self, user_id: str, action: str, resource: str, success: bool = True):
        """Registra acesso a recursos sensíveis"""
        try:
            timestamp = datetime.now().isoformat()
            log_entry = {
                'timestamp': timestamp,
                'user_id': user_id,
                'action': action,
                'resource': resource,
                'success': success,
                'ip_address': 'N/A'  # Será preenchido pelo middleware
            }
            
            # Garantir que o logger está configurado
            if hasattr(self, 'security_logger') and self.security_logger:
                self.security_logger.info(f"ACESSO: {log_entry}")
            else:
                # Fallback para log básico
                import logging
                logging.basicConfig(level=logging.INFO)
                logger = logging.getLogger('security_fallback')
                logger.info(f"ACESSO: {log_entry}")
                
            # Também escrever diretamente no arquivo como backup
            import json
            log_line = json.dumps(log_entry, ensure_ascii=False) + '\n'
            
            # Garantir que o diretório existe
            if not os.path.exists('logs'):
                os.makedirs('logs')
                
            with open('logs/security.log', 'a', encoding='utf-8') as f:
                f.write(log_line)
                f.flush()  # Forçar escrita imediata
                
        except Exception as e:
            print(f"Erro ao escrever log de segurança: {e}")
            # Ainda assim tentar escrever um log básico
            try:
                with open('logs/security_error.log', 'a', encoding='utf-8') as f:
                    f.write(f"{timestamp}: Erro no log - {e}\n")
            except:
                pass  # Se nem isso funcionar, falhar silenciosamente
    
    def cleanup_old_files(self, directory: str, max_age_hours: int = 24):
        """Remove arquivos antigos para evitar acúmulo de dados sensíveis"""
        try:
            current_time = datetime.now()
            max_age = timedelta(hours=max_age_hours)
            
            for filename in os.listdir(directory):
                file_path = os.path.join(directory, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                    if current_time - file_time > max_age:
                        os.remove(file_path)
                        self.security_logger.info(f"Arquivo antigo removido: {file_path}")
                        
        except Exception as e:
            self.logger.error(f"Erro na limpeza de arquivos: {e}")
    
    def get_security_headers(self) -> dict:
        """Retorna headers de segurança para respostas HTTP"""
        return {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
            'Referrer-Policy': 'strict-origin-when-cross-origin'
        }

# Instância global
security_config = SecurityConfig() 