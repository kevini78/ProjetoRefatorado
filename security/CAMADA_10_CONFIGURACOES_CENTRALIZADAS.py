#!/usr/bin/env python3
"""
CAMADA 10: CONFIGURAÇÕES DE SEGURANÇA CENTRALIZADAS
Arquivo: generate_security_keys.py
"""

import secrets
from cryptography.fernet import Fernet
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

class SecurityConfigManager:
    """
    Gerenciador de configurações de segurança centralizadas
    CAMADA 10: Configurações de segurança centralizadas
    """
    
    def __init__(self):
        self.config_file = '.env'
        self.keys_file = 'keys/security_keys.json'
        self.backup_dir = 'keys/backups'
        
        # Criar diretórios necessários
        os.makedirs('keys', exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def generate_secret_key(self) -> str:
        """Gera chave secreta para sessões Flask"""
        return secrets.token_hex(32)
    
    def generate_encryption_key(self) -> str:
        """Gera chave de criptografia para arquivos"""
        return Fernet.generate_key().decode()
    
    def generate_password(self, length: int = 16) -> str:
        """Gera senha forte"""
        # Caracteres para senha forte
        lowercase = 'abcdefghijklmnopqrstuvwxyz'
        uppercase = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        digits = '0123456789'
        symbols = '!@#$%^&*()_+-=[]{}|;:,.<>?'
        
        # Garantir pelo menos um de cada tipo
        password = [
            secrets.choice(lowercase),
            secrets.choice(uppercase),
            secrets.choice(digits),
            secrets.choice(symbols)
        ]
        
        # Adicionar caracteres aleatórios para completar o tamanho
        all_chars = lowercase + uppercase + digits + symbols
        password.extend(secrets.choice(all_chars) for _ in range(length - 4))
        
        # Embaralhar a senha
        password_list = list(password)
        secrets.SystemRandom().shuffle(password_list)
        
        return ''.join(password_list)
    
    def generate_jwt_secret(self) -> str:
        """Gera chave secreta para JWT"""
        return secrets.token_urlsafe(64)
    
    def generate_session_secret(self) -> str:
        """Gera chave secreta para sessões"""
        return secrets.token_urlsafe(32)
    
    def create_env_file(self, overwrite: bool = False) -> Dict[str, Any]:
        """
        Cria arquivo .env com as chaves geradas
        
        Args:
            overwrite: Se deve sobrescrever arquivo existente
            
        Returns:
            Dicionário com as chaves geradas
        """
        if os.path.exists(self.config_file) and not overwrite:
            return {'error': 'Arquivo .env já existe. Use overwrite=True para sobrescrever.'}
        
        # Gerar todas as chaves
        keys = {
            'SECRET_KEY': self.generate_secret_key(),
            'ENCRYPTION_KEY': self.generate_encryption_key(),
            'USER_PASSWORD': self.generate_password(),
            'JWT_SECRET_KEY': self.generate_jwt_secret(),
            'SESSION_SECRET': self.generate_session_secret(),
            'MISTRAL_API_KEY': 'sua_chave_api_mistral_aqui',
            'SESSION_LIFETIME': '3600',
            'MAX_UPLOAD_SIZE': '16777216',
            'SECURITY_LOG_LEVEL': 'INFO',
            'TEMP_FILE_RETENTION': '24',
            'ENABLE_HTTPS': 'False',
            'MAX_REQUESTS_PER_MINUTE': '60',
            'MAX_LOGIN_ATTEMPTS_PER_HOUR': '5',
            'IP_BLOCK_DURATION': '30',
            'ALLOW_IPS': '127.0.0.1,10.0.0.5',
            'ALLOW_CIDRS': '10.0.0.0/8,192.168.0.0/16'
        }
        
        # Criar conteúdo do arquivo .env
        env_content = f"""# Configurações de Segurança do Sistema
# Arquivo gerado automaticamente - NÃO COMPARTILHE ESTE ARQUIVO!

# Chave secreta para sessões Flask
SECRET_KEY={keys['SECRET_KEY']}

# Chave de criptografia para arquivos
ENCRYPTION_KEY={keys['ENCRYPTION_KEY']}

# Senha do usuário administrador
USER_PASSWORD={keys['USER_PASSWORD']}

# Chave secreta para JWT
JWT_SECRET_KEY={keys['JWT_SECRET_KEY']}

# Chave secreta para sessões
SESSION_SECRET={keys['SESSION_SECRET']}

# Chave da API Mistral (preencha manualmente)
MISTRAL_API_KEY={keys['MISTRAL_API_KEY']}

# Configurações de Segurança Adicionais
SESSION_LIFETIME={keys['SESSION_LIFETIME']}
MAX_UPLOAD_SIZE={keys['MAX_UPLOAD_SIZE']}
SECURITY_LOG_LEVEL={keys['SECURITY_LOG_LEVEL']}
TEMP_FILE_RETENTION={keys['TEMP_FILE_RETENTION']}
ENABLE_HTTPS={keys['ENABLE_HTTPS']}
MAX_REQUESTS_PER_MINUTE={keys['MAX_REQUESTS_PER_MINUTE']}
MAX_LOGIN_ATTEMPTS_PER_HOUR={keys['MAX_LOGIN_ATTEMPTS_PER_HOUR']}
IP_BLOCK_DURATION={keys['IP_BLOCK_DURATION']}
ALLOW_IPS={keys['ALLOW_IPS']}
ALLOW_CIDRS={keys['ALLOW_CIDRS']}
"""
        
        try:
            # Salvar arquivo .env
            with open(self.config_file, 'w') as f:
                f.write(env_content)
            
            # Salvar chaves em arquivo separado para backup
            self._save_keys_backup(keys)
            
            return {
                'success': True,
                'message': 'Arquivo .env criado com sucesso!',
                'keys_generated': len(keys),
                'file_path': self.config_file
            }
            
        except Exception as e:
            return {'error': f'Erro ao criar arquivo .env: {e}'}
    
    def _save_keys_backup(self, keys: Dict[str, str]):
        """Salva backup das chaves geradas"""
        try:
            backup_data = {
                'generated_at': datetime.now().isoformat(),
                'keys': keys,
                'version': '1.0'
            }
            
            with open(self.keys_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
            
            # Criar backup com timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = os.path.join(self.backup_dir, f'security_keys_{timestamp}.json')
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)
                
        except Exception as e:
            print(f"Erro ao salvar backup das chaves: {e}")
    
    def validate_config(self) -> Dict[str, Any]:
        """
        Valida configurações de segurança
        
        Returns:
            Resultado da validação
        """
        validation_result = {
            'timestamp': datetime.now().isoformat(),
            'status': '✅ VÁLIDO',
            'checks': {},
            'warnings': [],
            'errors': []
        }
        
        try:
            # Verificar se arquivo .env existe
            if not os.path.exists(self.config_file):
                validation_result['errors'].append('Arquivo .env não encontrado')
                validation_result['status'] = '❌ INVÁLIDO'
            else:
                validation_result['checks']['env_file'] = '✅ Existe'
            
            # Verificar se chaves foram geradas
            if os.path.exists(self.keys_file):
                with open(self.keys_file, 'r') as f:
                    keys_data = json.load(f)
                
                required_keys = ['SECRET_KEY', 'ENCRYPTION_KEY', 'USER_PASSWORD', 'JWT_SECRET_KEY']
                for key in required_keys:
                    if key in keys_data.get('keys', {}):
                        validation_result['checks'][f'key_{key}'] = '✅ Gerada'
                    else:
                        validation_result['errors'].append(f'Chave {key} não encontrada')
                        validation_result['status'] = '❌ INVÁLIDO'
            
            # Verificar permissões do arquivo .env
            if os.path.exists(self.config_file):
                file_mode = oct(os.stat(self.config_file).st_mode)[-3:]
                if file_mode != '600':
                    validation_result['warnings'].append(f'Permissões do arquivo .env: {file_mode} (recomendado: 600)')
            
            # Verificar se MISTRAL_API_KEY foi configurada
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    content = f.read()
                    if 'sua_chave_api_mistral_aqui' in content:
                        validation_result['warnings'].append('MISTRAL_API_KEY não foi configurada')
            
        except Exception as e:
            validation_result['status'] = '❌ ERRO'
            validation_result['errors'].append(f'Erro na validação: {e}')
        
        return validation_result
    
    def rotate_keys(self) -> Dict[str, Any]:
        """
        Rotaciona chaves de segurança
        
        Returns:
            Resultado da rotação
        """
        try:
            # Gerar novas chaves
            new_keys = {
                'SECRET_KEY': self.generate_secret_key(),
                'ENCRYPTION_KEY': self.generate_encryption_key(),
                'JWT_SECRET_KEY': self.generate_jwt_secret(),
                'SESSION_SECRET': self.generate_session_secret()
            }
            
            # Manter senha do usuário e outras configurações
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    content = f.read()
                
                # Substituir apenas as chaves que devem ser rotacionadas
                for key, value in new_keys.items():
                    content = content.replace(f'{key}=', f'{key}={value}')
                
                # Salvar arquivo atualizado
                with open(self.config_file, 'w') as f:
                    f.write(content)
            
            # Salvar backup das novas chaves
            self._save_keys_backup(new_keys)
            
            return {
                'success': True,
                'message': 'Chaves rotacionadas com sucesso',
                'keys_rotated': list(new_keys.keys())
            }
            
        except Exception as e:
            return {'error': f'Erro ao rotacionar chaves: {e}'}
    
    def get_security_report(self) -> Dict[str, Any]:
        """
        Gera relatório de segurança das configurações
        
        Returns:
            Relatório de segurança
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'config_file_exists': os.path.exists(self.config_file),
            'keys_file_exists': os.path.exists(self.keys_file),
            'backup_count': len([f for f in os.listdir(self.backup_dir) if f.endswith('.json')]) if os.path.exists(self.backup_dir) else 0,
            'recommendations': [
                'Mantenha o arquivo .env em local seguro',
                'Nunca compartilhe as chaves de segurança',
                'Rotacione as chaves regularmente',
                'Monitore o acesso ao arquivo .env',
                'Mantenha backups das chaves em local seguro',
                'Use HTTPS em produção',
                'Configure firewall adequadamente',
                'Monitore logs de segurança regularmente'
            ]
        }
        
        return report

# Instância global
config_manager = SecurityConfigManager()

def main():
    """Função principal para gerar chaves de segurança"""
    print("🔐 Gerador de Chaves de Segurança")
    print("=" * 40)
    
    if os.path.exists('.env'):
        response = input("⚠️  Arquivo .env já existe. Deseja sobrescrever? (s/N): ")
        if response.lower() != 's':
            print("❌ Operação cancelada.")
            return
    
    try:
        result = config_manager.create_env_file(overwrite=True)
        
        if 'error' in result:
            print(f"❌ {result['error']}")
        else:
            print(f"✅ {result['message']}")
            print(f"📁 Arquivo criado: {result['file_path']}")
            print(f"🔑 Chaves geradas: {result['keys_generated']}")
            
            print("\n📋 Próximos passos:")
            print("1. Copie a senha gerada para um local seguro")
            print("2. Preencha MISTRAL_API_KEY com sua chave da API")
            print("3. Execute o sistema com: python app.py")
            
            # Validar configurações
            validation = config_manager.validate_config()
            print(f"\n🔍 Validação: {validation['status']}")
            
            if validation['warnings']:
                print("⚠️  Avisos:")
                for warning in validation['warnings']:
                    print(f"   - {warning}")
            
            if validation['errors']:
                print("❌ Erros:")
                for error in validation['errors']:
                    print(f"   - {error}")
        
    except Exception as e:
        print(f"❌ Erro ao gerar chaves: {e}")

if __name__ == "__main__":
    main()
