#!/usr/bin/env python3
"""
Script para gerar chaves de segurança para o sistema
Execute este script para gerar as chaves necessárias para o arquivo .env
"""

import secrets
from cryptography.fernet import Fernet
import os

def generate_secret_key():
    """Gera chave secreta para sessões Flask"""
    return secrets.token_hex(32)

def generate_encryption_key():
    """Gera chave de criptografia para arquivos"""
    return Fernet.generate_key().decode()

def generate_password():
    """Gera senha forte para o usuário administrador"""
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
    
    # Adicionar caracteres aleatórios para completar 16 caracteres
    all_chars = lowercase + uppercase + digits + symbols
    password.extend(secrets.choice(all_chars) for _ in range(12))
    
    # Embaralhar a senha
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    
    return ''.join(password_list)

def create_env_file():
    """Cria arquivo .env com as chaves geradas"""
    env_content = f"""# Configurações de Segurança do Sistema
# Arquivo gerado automaticamente - NÃO COMPARTILHE ESTE ARQUIVO!

# Chave secreta para sessões Flask
SECRET_KEY={generate_secret_key()}

# Chave de criptografia para arquivos
ENCRYPTION_KEY={generate_encryption_key()}

# Senha do usuário administrador
USER_PASSWORD={generate_password()}

# Chave da API Mistral (preencha manualmente)
MISTRAL_API_KEY=sua_chave_api_mistral_aqui

# Configurações de Segurança Adicionais
SESSION_LIFETIME=3600
MAX_UPLOAD_SIZE=16777216
SECURITY_LOG_LEVEL=INFO
TEMP_FILE_RETENTION=24
ENABLE_HTTPS=False
MAX_REQUESTS_PER_MINUTE=60
MAX_LOGIN_ATTEMPTS_PER_HOUR=5
IP_BLOCK_DURATION=30
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Arquivo .env criado com sucesso!")
    print("⚠️  IMPORTANTE: Guarde a senha do administrador em local seguro!")
    print(f"🔑 Senha gerada: {env_content.split('USER_PASSWORD="[REMOVIDO_LGPD]"\n')[0]}")

def main():
    """Função principal"""
    print("🔐 Gerador de Chaves de Segurança")
    print("=" * 40)
    
    if os.path.exists('.env'):
        response = input("⚠️  Arquivo .env já existe. Deseja sobrescrever? (s/N): ")
        if response.lower() != 's':
            print("❌ Operação cancelada.")
            return
    
    try:
        create_env_file()
        print("\n📋 Próximos passos:")
        print("1. Copie a senha gerada para um local seguro")
        print("2. Preencha MISTRAL_API_KEY com sua chave da API")
        print("3. Execute o sistema com: python app.py")
        
    except Exception as e:
        print(f"❌ Erro ao gerar chaves: {e}")

if __name__ == "__main__":
    main() 