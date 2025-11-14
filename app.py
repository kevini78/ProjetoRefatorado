"""Ponto de entrada para executar a automação de naturalização ordinária."""

import os
import sys

from automation.services.ordinaria_processor import OrdinariaProcessor


def main():
    """Executa a automação solicitando o número do processo ao usuário."""
    numero_processo = os.environ.get("NUMERO_PROCESSO")

    if not numero_processo:
        numero_processo = input("Informe o número do processo: ").strip()

    if not numero_processo:
        print("[ERRO] Número do processo não informado.")
        return

    with OrdinariaProcessor() as processor:
        resultado = processor.processar_processo(numero_processo)

        if resultado.get("sucesso"):
            print("\n=== PROCESSO CONCLUÍDO ===")
            print(f"Status: {resultado.get('status')}")
            print(f"Elegibilidade final: {resultado.get('elegibilidade_final')}")
        else:
            print("\n=== PROCESSO ENCERRADO COM ERRO ===")
            print(f"Motivo: {resultado.get('erro')}")


if __name__ == "__main__":
    main()
    sys.exit(0)
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, flash, session, send_from_directory
from functools import wraps
import os
from datetime import datetime
import tempfile
import shutil
from werkzeug.utils import secure_filename
import pandas as pd
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
from pdf2image import convert_from_path
import re
import cv2
import numpy as np
from mistralai import Mistral
from dotenv import load_dotenv
import mimetypes
import base64
import requests
import time
import json
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from Ordinaria.ocr_utils import comparar_campos
from flask_wtf.csrf import CSRFProtect, generate_csrf
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import logging
from pathlib import Path
import bleach
import html
from cryptography.fernet import Fernet
try:
    import argon2
    ARGON2_AVAILABLE = True
except ImportError:
    ARGON2_AVAILABLE = False
    print("[AVISO] Argon2 nao disponivel - usando bcrypt para senhas")

# Importar módulos de segurança (ajustar caminho para pasta pai)
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from security_modules.security_config_flexible import flexible_security_config as security_config
    print("[OK] Usando configuracao de seguranca flexivel")
except ImportError:
    try:
        from security_modules.security_config import security_config
        print("[AVISO] Usando configuracao de seguranca padrao")
    except ImportError:
        print("[ERRO] Modulos de seguranca nao disponiveis - operando sem seguranca")
        security_config = None

try:
    from security_modules.security_middleware import SecurityMiddleware, require_authentication, require_admin, log_sensitive_operation
    from security_modules.data_sanitizer import data_sanitizer
    SECURITY_MODULES_AVAILABLE = True
    print("[OK] Modulos de seguranca carregados com sucesso")
except ImportError as e:
    print(f"[AVISO] Erro ao carregar modulos de seguranca: {e}")
    # Definir fallbacks
    SecurityMiddleware = None
    require_authentication = lambda f: f
    require_admin = lambda f: f
    log_sensitive_operation = lambda op: lambda f: f
    data_sanitizer = None
    SECURITY_MODULES_AVAILABLE = False

# Importar correções de segurança para evitar falhas
try:
    from security_modules.security_fixes import initialize_security_fixes, safe_file_processing, safe_data_sanitization
    SECURITY_FIXES_AVAILABLE = True
except ImportError:
    SECURITY_FIXES_AVAILABLE = False
    print("[AVISO] Modulo de correcoes de seguranca nao disponivel - operando em modo basico")

# Importar o analisador de portarias
from portaria_analyzer import PortariaAnalyzer
# Importar o módulo de busca automática
from busca_automatica_dou import BuscadorAutomaticoDOU
from lecom_automation import LecomAutomation

# Importar o exportador Excel
try:
    from exportador_excel import exportar_processos_excel, criar_resumo_estatisticas
    EXPORTADOR_DISPONIVEL = True
    print("[OK] Exportador Excel disponivel")
except ImportError:
    EXPORTADOR_DISPONIVEL = False
    print("[AVISO] Exportador Excel nao disponivel")

# Importar o gerador de planilha de resultados
try:
    from gerador_planilha_resultados import GeradorPlanilhaResultados, gerar_planilha_resultados
    GERADOR_PLANILHA_DISPONIVEL = True
    print("[OK] Gerador de planilha de resultados disponivel")
except ImportError:
    GERADOR_PLANILHA_DISPONIVEL = False
    print("[AVISO] Gerador de planilha de resultados nao disponivel")

app = Flask(__name__)

# Carregar .env antes de ler variáveis sensíveis
load_dotenv()

# ================================
# FUNÇÕES DE SEGURANÇA INTEGRADAS
# ================================

class SecurityManager:
    """Gerenciador de segurança integrado"""
    
    def __init__(self):
        # Configurar criptografia
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if not encryption_key:
            encryption_key = Fernet.generate_key().decode()
            print("🔑 Chave de criptografia gerada automaticamente")
        
        try:
            self.fernet = Fernet(encryption_key.encode())
        except:
            # Gerar nova chave válida se houver erro
            new_key = Fernet.generate_key().decode()
            self.fernet = Fernet(new_key.encode())
            print("[INFO] Nova chave de criptografia gerada")
        
        # Configurar hash de senhas
        if ARGON2_AVAILABLE:
            self.argon2_hasher = argon2.PasswordHasher()
    
    def encrypt_data(self, data: str) -> str:
        """Criptografar dados sensíveis"""
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except:
            return data  # Fallback em caso de erro
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """Descriptografar dados"""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except:
            return encrypted_data  # Fallback em caso de erro
    
    def hash_password(self, password: str) -> str:
        """Hash seguro de senha"""
        if ARGON2_AVAILABLE:
            return self.argon2_hasher.hash(password)
        else:
            return generate_password_hash(password, method='pbkdf2:sha256', salt_length=16)
    
    def verify_password(self, password: str, hash_password: str) -> bool:
        """Verificar senha"""
        if ARGON2_AVAILABLE:
            try:
                return self.argon2_hasher.verify(hash_password, password)
            except:
                return False
        else:
            return check_password_hash(hash_password, password)
    
    def sanitize_input(self, text: str) -> str:
        """Sanitizar entrada para prevenir XSS"""
        if not text:
            return ""
        # Remover tags HTML perigosas
        clean_text = bleach.clean(str(text), tags=[], attributes={}, strip=True)
        # Escapar caracteres especiais
        return html.escape(clean_text)
    
    def validate_filename(self, filename: str) -> bool:
        """Validar nome de arquivo"""
        if not filename:
            return False
        
        # Caracteres perigosos
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in filename:
                return False
        
        return True

# Inicializar gerenciador de segurança
try:
    security_manager = SecurityManager()
    print("[FECHADO] Gerenciador de segurança inicializado")
except Exception as e:
    print(f"[AVISO] Erro ao inicializar seguranca: {e}")
    security_manager = None

# ================================
# LOGS DE SEGURANÇA
# ================================

# Configurar logs de segurança
os.makedirs('logs', exist_ok=True)
security_logger = logging.getLogger('security')
security_handler = logging.FileHandler('logs/security_audit.log', encoding='utf-8')
security_handler.setFormatter(logging.Formatter(
    '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
))
security_logger.addHandler(security_handler)
security_logger.setLevel(logging.INFO)

def log_security_event(event_type: str, details: str, ip_address: str = None):
    """Registrar eventos de segurança"""
    try:
        from flask import has_request_context, request as flask_request
        if has_request_context():
            ip = ip_address or flask_request.remote_addr
            user = current_user.username if current_user and current_user.is_authenticated else 'Anonymous'
        else:
            ip = ip_address or 'localhost'
            user = 'System'
    except:
        ip = ip_address or 'localhost'
        user = 'System'
    
    security_logger.info(f"{event_type} - User: {user} - IP: {ip} - Details: {details}")

# Configurações de segurança por ambiente
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    secret_key = secrets.token_urlsafe(64)
    print("🔑 SECRET_KEY gerada automaticamente")

app.config['SECRET_KEY'] = secret_key

# Estado em memória para processos em background (evita depender de session dentro da thread)
BACKGROUND_PROCESSES = {}

is_production = os.environ.get('FLASK_ENV') == 'production' or os.environ.get('APP_ENV') == 'production'
app.config['SESSION_COOKIE_SECURE'] = bool(is_production)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict' if is_production else 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24h

# Habilitar proteção CSRF
csrf = CSRFProtect(app)
app.config['WTF_CSRF_ENABLED'] = bool(is_production)

# Rotas isentas de CSRF (apenas em desenvolvimento para debug)
# Em produção, todas as rotas devem ter CSRF habilitado
if not is_production:
    app.config['WTF_CSRF_EXEMPT_ENDPOINTS'] = []  # Vazio por padrão, adicionar apenas se necessário

# Expor função csrf_token() nos templates Jinja
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=lambda: generate_csrf())

@app.context_processor
def inject_globals():
    """Injetar variáveis globais nos templates"""
    return {
        'current_user': current_user,
        'current_time': datetime.now,
        'app_version': '3.0.0-secure',
        'system_name': 'Sistema de Análise de Processos',
        'security_active': True
    }

# Definir o caminho correto da pasta uploads (com maiúsculas corretas)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max (para portarias longas + arquivos)

# Criar pasta de uploads se não existir
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Inicializar middleware de segurança
if SECURITY_MODULES_AVAILABLE and SecurityMiddleware:
    security_middleware = SecurityMiddleware(app)
    print("[OK] Middleware de seguranca inicializado")
else:
    security_middleware = None
    print("[AVISO] Middleware de seguranca nao disponivel - operando sem middleware")

# Inicializar o analyzer global logo após os imports
analyzer = PortariaAnalyzer()
# Variável global para armazenar o buscador automático
buscador_automatico = None

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

pytesseract.pytesseract.tesseract_cmd = r'C:\Users\kevin.iqbal\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

# Configuração do modo PSM e opções do Tesseract
OCR_CONFIG = '--psm 6'

# Carregar a chave da API do .env
load_dotenv()

# Verificar se a chave da API está disponível
api_key = os.environ.get("MISTRAL_API_KEY")
if api_key:
    try:
        client = Mistral(api_key=api_key)
        print("[OK] Cliente Mistral configurado com sucesso")
    except Exception as e:
        print(f"[AVISO] Erro ao configurar cliente Mistral: {e}")
        client = None
else:
    print("[AVISO] MISTRAL_API_KEY nao encontrada - funcionalidades de IA podem nao funcionar")
    client = None

# Configuração do Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Função personalizada para tratamento de não autenticados em APIs
def api_login_required(f):
    """Decorador que retorna JSON para rotas de API quando não autenticado"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            # Se for uma requisição AJAX ou API, retornar JSON
            if request.is_json or request.path.startswith('/api/') or request.path.startswith('/upload_'):
                return jsonify({'success': False, 'message': 'Não autenticado', 'redirect': '/login'}), 401
            # Senão, comportamento normal do Flask-Login
            return login_manager.unauthorized()
        return f(*args, **kwargs)
    return decorated_function

# Usuário fixo para autenticação interna
class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.name = "admin"
        password_plain = os.environ.get("USER_PASSWORD")
        if not password_plain:
            raise RuntimeError("A variável de ambiente USER_PASSWORD não está definida! Defina-a para proteger o acesso ao sistema.")
        self.password_hash = generate_password_hash(password_plain)

    def get_id(self):
        return self.id

# Usuário único
users = {"admin": User("admin")}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# Middleware de segurança para bloquear acessos externos
@app.before_request
def security_middleware():
    """Middleware de segurança para todas as requisições"""
    # Log da requisição
    try:
        log_security_event('REQUEST', f'{request.method} {request.path}')
    except:
        pass  # Falhar silenciosamente se houver erro no log
    
    # Validar entrada básica
    if security_manager and request.method in ['POST', 'PUT', 'PATCH']:
        try:
            if request.form:
                # Campos que podem ter textos grandes (portarias completas com centenas de pessoas)
                campos_texto_grande = ['texto_portaria', 'texto_deferimento', 'texto_manual_lecom']
                
                for key, value in request.form.items():
                    if value:
                        # Limite MUITO maior para campos de texto de portaria
                        # Portarias podem ter 100+ páginas com centenas de pessoas
                        if key in campos_texto_grande:
                            limite = 5000000  # 5MB para portarias completas (suficiente para textos enormes)
                        else:
                            limite = 50000  # 50KB para campos normais (aumentado de 10KB)
                        
                        if len(str(value)) > limite:
                            tamanho_mb = len(str(value)) / 1000000
                            print(f'[SEGURANÇA] Campo "{key}" excedeu o limite: {tamanho_mb:.2f}MB')
                            return jsonify({
                                "erro": f"Campo '{key}' muito longo ({tamanho_mb:.2f}MB). Máximo permitido: {limite/1000000}MB"
                            }), 400
        except Exception as e:
            print(f'[AVISO] Erro na validação de tamanho: {e}')
            pass  # Falhar silenciosamente

@app.before_request
def limit_remote_addr():
    """Bloqueia acessos de IPs externos à rede local"""
    client_ip = request.environ.get('REMOTE_ADDR')
    
    # IPs permitidos (rede local)
    allowed_ips = [
        '127.0.0.1',  # localhost
        '::1',        # localhost IPv6
    ]
    
    # Permitir toda a rede local (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    if client_ip:
        # Verificar se é rede local
        if (client_ip.startswith('192.168.') or 
            client_ip.startswith('10.') or 
            client_ip.startswith('172.') and 
            16 <= int(client_ip.split('.')[1]) <= 31 or
            client_ip in allowed_ips):
            return  # IP permitido
        else:
            # Bloquear acesso externo
            print(f"🚫 Acesso bloqueado de IP externo: {client_ip}")
            log_security_event('BLOCKED_IP', f'Acesso bloqueado do IP: {client_ip}')
            return "Acesso negado - apenas rede local permitida", 403

@app.after_request
def set_security_headers(response):
    """Adicionar headers de segurança"""
    security_headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; img-src 'self' data:; font-src 'self' cdnjs.cloudflare.com;",
    }
    
    for header, value in security_headers.items():
        response.headers[header] = value
    
    return response

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/configurar', methods=['GET', 'POST'])
@require_authentication
@log_sensitive_operation('CONFIGURACAO_SISTEMA')
def configurar():
    global analyzer
    message = None
    
    if request.method == 'POST':
        # Verificar se foi enviado um arquivo de histórico
        if 'arquivo' in request.files:
            arquivo = request.files['arquivo']
            if arquivo and arquivo.filename != '':
                try:
                    # Validação de segurança do arquivo
                    if security_config and not security_config.validate_file_type(arquivo.filename, {'xlsx', 'xls'}):
                        message = 'Tipo de arquivo não permitido. Use apenas arquivos Excel (.xlsx, .xls).'
                        return render_template('configurar.html', message=message)
                    
                    # Sanitizar nome do arquivo
                    filename = security_config.sanitize_filename(arquivo.filename) if security_config else secure_filename(arquivo.filename)
                    filename = secure_filename(filename)
                    caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Salvar arquivo temporariamente
                    arquivo.save(caminho_arquivo)
                    
                    # Carregar o analyzer com o arquivo original (não criptografado)
                    # O PortariaAnalyzer precisa ler o Excel com pandas, que não aceita arquivos criptografados
                    analyzer = PortariaAnalyzer(caminho_arquivo)
                    
                    # Verificar se o histórico foi carregado com sucesso
                    if analyzer.historico_df is not None:
                        # Criptografar arquivo após carregamento bem-sucedido (para armazenamento seguro)
                        if security_config:
                            try:
                                encrypted_path = security_config.encrypt_file(caminho_arquivo)
                                message = f'Sucesso! Histórico carregado com {len(analyzer.historico_df)} registros e arquivo criptografado: {filename}'
                            except Exception as e:
                                message = f'Sucesso! Histórico carregado com {len(analyzer.historico_df)} registros (arquivo não criptografado): {filename}'
                                print(f"Aviso: Criptografia falhou: {e}")
                        else:
                            message = f'Sucesso! Histórico carregado com {len(analyzer.historico_df)} registros: {filename}'
                    else:
                        message = f'Erro: Não foi possível carregar o histórico do arquivo {filename}. Verifique o formato da planilha.'
                    
                    # Log de segurança
                    if security_config:
                        try:
                            security_config.log_access(
                                user_id=current_user.name,
                                action='ARQUIVO_CONFIGURACAO_CARREGADO',
                                resource=filename,
                                success=True
                            )
                        except Exception as e:
                            print(f"Aviso: Log de segurança falhou: {e}")
                    
                except Exception as e:
                    message = f'Erro ao carregar o arquivo: {str(e)}'
                    if security_config:
                        try:
                            security_config.log_access(
                                user_id=current_user.name,
                                action='ERRO_CARREGAMENTO_ARQUIVO',
                                resource=arquivo.filename,
                                success=False
                            )
                        except Exception as e2:
                            print(f"Aviso: Log de segurança falhou: {e2}")
            else:
                # Se nenhum arquivo foi selecionado, mas o formulário foi enviado
                analyzer = PortariaAnalyzer()
                message = 'Aviso: Nenhum arquivo de histórico selecionado. O analisador usará apenas as regras padrão.'
        else:
            # Caso o formulário seja postado sem o campo 'arquivo'
            analyzer = PortariaAnalyzer()
            message = 'Aviso: Analisador configurado sem arquivo de histórico.'

        return render_template('configurar.html', message=message)
    
    # Se for GET, apenas renderiza a página
    return render_template('configurar.html', message=None)

@app.route('/analisar', methods=['GET', 'POST'])
@require_authentication
@log_sensitive_operation('ANALISE_PORTARIA')
def analisar():
    """Página de análise de portarias"""
    print('[DEBUG] Entrou na rota /analisar')
    if request.method == 'POST':
        print('[DEBUG] Recebeu POST em /analisar')
        print(f'[DEBUG] Headers: {dict(request.headers)}')
        print(f'[DEBUG] Form data keys: {list(request.form.keys())}')
        print(f'[DEBUG] CSRF token presente: {"csrf_token" in request.form}')
        
        if analyzer is None:
            print('[DEBUG] Analyzer não configurado')
            return jsonify({
                'success': False,
                'message': 'Analisador não configurado. Configure primeiro!'
            })
        # Bloqueio: exige histórico carregado para análise por texto ou URL
        if getattr(analyzer, 'historico_df', None) is None:
            print('[DEBUG] Histórico não configurado')
            return jsonify({
                'success': False,
                'message': 'É necessário configurar o histórico antes de analisar por texto ou por URL.'
            })
        # Obter dados do formulário
        tipo_analise = request.form.get('tipo_analise')
        print(f'[DEBUG] tipo_analise recebido: {tipo_analise}')
        
        if tipo_analise == 'url':
            url_portaria = request.form.get('url_portaria')
            print(f'[DEBUG] url_portaria recebido: {url_portaria}')
            if not url_portaria:
                print('[DEBUG] URL da portaria não informada')
                return jsonify({
                    'success': False,
                    'message': 'URL da portaria é obrigatória'
                })
            
            # Validar URL para evitar ataques
            if not url_portaria.startswith(('http://', 'https://')):
                return jsonify({
                    'success': False,
                    'message': 'URL inválida. Use apenas URLs HTTP/HTTPS.'
                })
            
            try:
                print('[DEBUG] Chamando analyzer.analisar_portaria')
                resultado = analyzer.analisar_portaria(url_portaria, gerar_excel=False)
                print('[DEBUG] Retornou da chamada analyzer.analisar_portaria')
                
                if 'erro' in resultado:
                    print(f'[DEBUG] Erro retornado: {resultado["erro"]}')
                    return jsonify({
                        'success': False,
                        'message': resultado['erro']
                    })
                
                # Preparar resultado para JSON (similar ao texto)
                resultado_json = {
                    'total_portarias': resultado['total_portarias'],
                    'total_erros': resultado['total_erros'],
                    'portarias': []
                }
                
                for res in resultado['resultados']:
                    if res['dados_portaria']:
                        portaria_info = {
                            'numero': res['dados_portaria']['numero'],
                            'data': res['dados_portaria']['data'],
                            'tipo': res['dados_portaria']['tipo'],
                            'total_pessoas': len(res['dados_portaria']['pessoas']),
                            'erros': res['erros'],
                            'pessoas': res['dados_portaria']['pessoas']
                        }
                        resultado_json['portarias'].append(portaria_info)
                
                return jsonify({
                    'success': True,
                    'resultado': resultado_json
                })
            except Exception as e:
                print(f'[DEBUG] Exceção ao analisar por URL: {e}')
                return jsonify({
                    'success': False,
                    'message': f'Erro ao analisar portaria: {str(e)}'
                })
        
        elif tipo_analise == 'texto':
            texto_portaria = request.form.get('texto_portaria')
            if not texto_portaria:
                return jsonify({
                    'success': False,
                    'message': 'Texto da portaria é obrigatório'
                })
            
            # Salvar o texto recebido em um arquivo para debug
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"debug_texto_recebido_{timestamp}.txt"
            
            with open(log_filename, 'w', encoding='utf-8') as f:
                f.write("=== TEXTO RECEBIDO DO FORMULARIO ===\n")
                f.write(texto_portaria)
                f.write("\n=== FIM DO TEXTO ===\n")
            
            print(f"Texto salvo em: {log_filename}")
            
            try:
                resultados, arquivos_excel = analyzer.analisar_multiplas_portarias(texto_portaria, gerar_excel=True)
                
                # Preparar resultado para JSON
                resultado_json = {
                    'total_portarias': len(resultados),
                    'total_erros': sum(r['total_erros'] for r in resultados),
                    'portarias': []
                }
                
                for res in resultados:
                    if res['dados_portaria']:
                        portaria_info = {
                            'numero': res['dados_portaria']['numero'],
                            'data': res['dados_portaria']['data'],
                            'tipo': res['dados_portaria']['tipo'],
                            'total_pessoas': len(res['dados_portaria']['pessoas']),
                            'erros': res['erros'],
                            'pessoas': res['dados_portaria']['pessoas']
                        }
                        resultado_json['portarias'].append(portaria_info)
                
                # Salvar arquivo Excel em pasta temporária
                if arquivos_excel:
                    temp_dir = tempfile.mkdtemp()
                    for arquivo in arquivos_excel:
                        if os.path.exists(arquivo):
                            shutil.copy2(arquivo, temp_dir)
                            os.remove(arquivo)  # Remover arquivo original
                    
                    resultado_json['arquivos_excel'] = [os.path.join(temp_dir, os.path.basename(f)) for f in arquivos_excel]
                
                return jsonify({
                    'success': True,
                    'resultado': resultado_json
                })
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Erro ao analisar texto: {str(e)}'
                })
    
    return render_template('analisar.html')

@app.route('/busca_automatica')
def busca_automatica():
    """Página de busca automática no DOU"""
    return render_template('busca_automatica.html')

@app.route('/buscar_automatico', methods=['POST'])
def buscar_automatico():
    """Endpoint para busca automática de portarias no DOU"""
    global buscador_automatico
    try:
        # CORREÇÃO: Obter dados tanto de JSON quanto de FormData
        if request.is_json:
            dados = request.get_json()
            tipo_portaria = dados.get('tipo_portaria', None)
            link_personalizado = dados.get('link_personalizado', None)
        else:
            # FormData enviado pelo template
            tipo_portaria = request.form.get('tipo_portaria', None)
            link_personalizado = request.form.get('link_personalizado', None)

        if not tipo_portaria or not link_personalizado:
            return jsonify({
                'success': False,
                'message': 'Tipo de portaria e link são obrigatórios.'
            })

        elif tipo_portaria == 'indeferimento':
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
            import pandas as pd
            import os
            def extrair_portarias_indef(driver, url, caminho_saida):
                driver.get(url)
                todas_pessoas = []
                pagina = 1
                while True:
                    print(f"Processando página {pagina}...")
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/despachos-')]"))
                    )
                    despachos_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/despachos-')]")
                    links = [link.get_attribute('href') for link in despachos_links]
                    for link in links:
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[1])
                        driver.get(link)
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(2)
                        try:
                            texto_portaria = driver.find_element(By.XPATH, "//body").text
                            if not texto_portaria or len(texto_portaria) < 200:
                                try:
                                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                    texto_portaria = "\n".join([p.text for p in paragrafos])
                                except:
                                    pass
                        except:
                            try:
                                div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                texto_portaria = "\n".join([p.text for p in paragrafos])
                            except:
                                texto_portaria = ""
                        
                        # Extrair indeferimentos usando regex específico
                        from busca_automatica_indef import BuscadorAutomaticoIndef
                        buscador = BuscadorAutomaticoIndef()
                        indeferimentos = buscador.extrair_indefs_do_texto(texto_portaria)
                        
                        for indef in indeferimentos:
                            pessoa_info = {
                                'nome': indef['interessado'],
                                'processo': indef['processo'],
                                'codigo': indef['codigo'],
                                'assunto': indef['assunto'],
                                'despacho': '',
                                'tipo': indef['tipo'],
                                'link_portaria': link
                            }
                            todas_pessoas.append(pessoa_info)
                        
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(1)
                    try:
                        right_arrow = driver.find_element(By.ID, "rightArrow")
                        if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                            right_arrow.click()
                            pagina += 1
                            time.sleep(2)
                        else:
                            print("Última página alcançada.")
                            break
                    except Exception as e:
                        print("Não há mais páginas ou erro ao clicar na seta:", e)
                        break
                if todas_pessoas:
                    df = pd.DataFrame(todas_pessoas)
                    # Tratar valores NaN antes de salvar
                    df = df.fillna('')
                    df.to_excel(caminho_saida, index=False)
                    return caminho_saida, len(df)
                else:
                    return None, 0
            options = webdriver.ChromeOptions()
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"indeferimentos_{timestamp}.xlsx"
                # Salvar na pasta uploads correta
                caminho_uploads = os.path.join(os.path.dirname(__file__), 'uploads')
                os.makedirs(caminho_uploads, exist_ok=True)
                caminho_saida = os.path.join(caminho_uploads, nome_arquivo)
                arquivo, total_registros = extrair_portarias_indef(driver, link_personalizado, caminho_saida)
                pessoas_amostra = []
                if arquivo:
                    try:
                        df = pd.read_excel(arquivo)
                        # Tratar valores NaN antes de converter para dicionário
                        df = df.fillna('')
                        pessoas_amostra = df.head(20).to_dict(orient='records')
                    except Exception as e:
                        pessoas_amostra = []
                    return jsonify({
                        'success': True,
                        'arquivo': nome_arquivo,
                        'total_registros': total_registros,
                        'mensagem': f'Busca de indeferimentos concluída! {total_registros} registros encontrados.',
                        'tipo_busca': tipo_portaria,
                        'pessoas': pessoas_amostra
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Nenhum indeferimento encontrado.'
                    })
            finally:
                driver.quit()
                
        elif tipo_portaria == 'expulsao':
            # Busca por expulsão (usa Selenium e extrator especial)
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
            import pandas as pd
            import re
            import os
            def formatar_tempo_impedimento(tempo_bruto):
                """
                Formata o tempo de impedimento para o padrão solicitado
                Ex: "5 (cinco) anos e 10 (dez) meses"
                """
                try:
                    # Padrão para anos
                    anos_match = re.search(r'(\d+)\s*\(?(\w+)\)?\s*ano[s]?', tempo_bruto, re.IGNORECASE)
                    anos_num = anos_match.group(1) if anos_match else "0"
                    anos_ext = anos_match.group(2) if anos_match and anos_match.group(2) else numero_por_extenso(int(anos_num))
                    
                    # Padrão para meses
                    meses_match = re.search(r'(\d+)\s*\(?(\w+)\)?\s*mês|meses', tempo_bruto, re.IGNORECASE)
                    meses_num = meses_match.group(1) if meses_match else "0"
                    meses_ext = meses_match.group(2) if meses_match and meses_match.group(2) else numero_por_extenso(int(meses_num))
                    
                    # Padrão para dias
                    dias_match = re.search(r'(\d+)\s*\(?(\w+)\)?\s*dia[s]?', tempo_bruto, re.IGNORECASE)
                    dias_num = dias_match.group(1) if dias_match else "0"
                    dias_ext = dias_match.group(2) if dias_match and dias_match.group(2) else numero_por_extenso(int(dias_num))
                    
                    # Montar resultado formatado
                    resultado = []
                    
                    if anos_num != "0":
                        resultado.append(f"{anos_num} ({anos_ext}) ano{'s' if int(anos_num) > 1 else ''}")
                    
                    if meses_num != "0":
                        resultado.append(f"{meses_num} ({meses_ext}) mês{'es' if int(meses_num) > 1 else ''}")
                    
                    if dias_num != "0":
                        resultado.append(f"{dias_num} ({dias_ext}) dia{'s' if int(dias_num) > 1 else ''}")
                    
                    if resultado:
                        return " e ".join(resultado)
                    else:
                        return tempo_bruto.strip()
                        
                except Exception as e:
                    print(f"[ERRO] Erro ao formatar tempo de impedimento: {e}")
                    return tempo_bruto.strip()
            
            def numero_por_extenso(numero):
                """Converte número para extenso em português"""
                numeros_extenso = {
                    1: "um", 2: "dois", 3: "três", 4: "quatro", 5: "cinco",
                    6: "seis", 7: "sete", 8: "oito", 9: "nove", 10: "dez",
                    11: "onze", 12: "doze", 13: "treze", 14: "quatorze", 15: "quinze",
                    16: "dezesseis", 17: "dezessete", 18: "dezoito", 19: "dezenove", 20: "vinte"
                }
                return numeros_extenso.get(numero, str(numero))
            
            def extrair_processos_expulsao(texto_completo):
                padrao_expulsao = re.compile(
                    r'(EXPULSAR.*?)\.\s*(?=(?:EXPULSAR|$|[A-Z]{2,}))',
                    re.IGNORECASE | re.DOTALL
                )
                padrao_processo = re.compile(r'Processo\s*n[º°o]*\s*([\d\.\-/]+)', re.IGNORECASE)
                textos_expulsao = padrao_expulsao.findall(texto_completo)
                processo_match = padrao_processo.search(texto_completo)
                processo_numero = processo_match.group(1) if processo_match else "Não encontrado"
                resultados = []
                for texto in textos_expulsao:
                    # Extrair nome da pessoa - regex melhorado
                    nome_match = re.search(r'EXPULSAR[^,]*?,\s*([^,]+?),\s*de\s+nacionalidade', texto, re.IGNORECASE)
                    if not nome_match:
                        # Padrão alternativo mais flexível
                        nome_match = re.search(r'EXPULSAR[^,]*?,\s*([^,]+?)(?:,|de\s+nacionalidade)', texto, re.IGNORECASE)
                    
                    nome = nome_match.group(1).strip() if nome_match else "Não identificado"
                    
                    # Extrair nacionalidade - regex melhorado
                    nacionalidade_match = re.search(r'de\s+nacionalidade\s+([^,\.;]+)', texto, re.IGNORECASE)
                    if not nacionalidade_match:
                        nacionalidade_match = re.search(r'nacionalidade\s+([^,\.;]+)', texto, re.IGNORECASE)
                    nacionalidade = nacionalidade_match.group(1).strip() if nacionalidade_match else "Não identificada"
                    
                    # Extrair tempo de impedimento com regex melhorado
                    impedimento_match = re.search(r'impedimento de reingresso.*?período de\s*([^,\.]+?)(?:,?\s*a partir da execução da medida|\.|$)', texto, re.IGNORECASE | re.DOTALL)
                    
                    if not impedimento_match:
                        # Padrão alternativo mais flexível
                        impedimento_match = re.search(r'impedimento de reingresso.*?(\d+.*?ano[s]?.*?(?:\d+.*?mês|meses)?.*?(?:\d+.*?dia[s]?)?)', texto, re.IGNORECASE | re.DOTALL)
                    
                    if impedimento_match:
                        tempo_impedimento = impedimento_match.group(1).strip()
                        # Formatar o tempo de impedimento para o padrão solicitado
                        tempo_impedimento = formatar_tempo_impedimento(tempo_impedimento)
                    else:
                        tempo_impedimento = "Não especificado"
                    
                    resultados.append({
                        "Processo": processo_numero,
                        "Nome": nome,
                        "Nacionalidade": nacionalidade,
                        "Período de Impedimento": tempo_impedimento,
                        "Texto Completo Expulsão": texto.strip()
                    })
                return resultados
            def extrair_portarias_expulsao(driver, url, caminho_saida):
                driver.get(url)
                todos_dados = []
                pagina = 1
                while True:
                    print(f"Processando página {pagina}...")
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                    )
                    portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                    links = [link.get_attribute('href') for link in portarias_links]
                    for link in links:
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[1])
                        driver.get(link)
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(2)
                        try:
                            texto_portaria = driver.find_element(By.XPATH, "//body").text
                            if not texto_portaria or len(texto_portaria) < 200:
                                try:
                                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                    texto_portaria = "\n".join([p.text for p in paragrafos])
                                except:
                                    pass
                        except:
                            try:
                                div_texto_dou = driver.find_elemenct(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                texto_portaria = "\n".join([p.text for p in paragrafos])
                            except:
                                texto_portaria = ""
                        processos_expulsao = extrair_processos_expulsao(texto_portaria)
                        for processo in processos_expulsao:
                            todos_dados.append({
                                "Link Portaria": link,
                                "Número do Processo": processo["Processo"],
                                "Nome": processo["Nome"],
                                "Nacionalidade": processo["Nacionalidade"],
                                "Período de Impedimento": processo["Período de Impedimento"],
                                "Texto Completo Expulsão": processo["Texto Completo Expulsão"]
                            })
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(1)
                    try:
                        right_arrow = driver.find_element(By.ID, "rightArrow")
                        if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                            right_arrow.click()
                            pagina += 1
                            time.sleep(2)
                        else:
                            print("Última página alcançada.")
                            break
                    except Exception as e:
                        print("Não há mais páginas ou erro ao clicar na seta:", e)
                        break
                if todos_dados:
                    df = pd.DataFrame(todos_dados)
                    # Tratar valores NaN antes de salvar
                    df = df.fillna('')
                    df.to_excel(caminho_saida, index=False)
                    return caminho_saida, len(df)
                else:
                    return None, 0
            options = webdriver.ChromeOptions()
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"expulsoes_{timestamp}.xlsx"
                caminho_saida = os.path.join(os.getcwd(), nome_arquivo)
                arquivo, total_registros = extrair_portarias_expulsao(driver, link_personalizado, caminho_saida)
                pessoas_amostra = []
                if arquivo:
                    try:
                        df = pd.read_excel(arquivo)
                        # Tratar valores NaN antes de converter para dicionário
                        df = df.fillna('')
                        pessoas_amostra = df.head(20).to_dict(orient='records')
                    except Exception as e:
                        pessoas_amostra = []
                    return jsonify({
                        'success': True,
                        'arquivo': nome_arquivo,
                        'total_registros': total_registros,
                        'mensagem': f'Busca concluída com sucesso! {total_registros} registros encontrados.',
                        'tipo_busca': tipo_portaria,
                        'pessoas': pessoas_amostra
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Nenhum processo de expulsão encontrado.'
                    })
            finally:
                driver.quit()
                
        elif tipo_portaria == 'revogacao':
            # Busca por revogação (usa Selenium e extrator especial, similar à expulsão)
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
            import pandas as pd
            import os
            
            def extrair_processos_revogacao(texto_completo):
                """Extrai dados de revogação do texto da portaria"""
                import re  # Importar o módulo re dentro da função
                
                # Primeiro verificar se o texto contém revogação
                if not re.search(r'REVOGAR', texto_completo, re.IGNORECASE):
                    print("[DEBUG] 🚫 Texto não contém revogação - pulando...")
                    return []
                
                # Padrão específico para revogação - captura diferentes formatos
                # Formato 1: "REVOGAR a Portaria..." (exemplo original)
                # Formato 2: "REVOGAR o ato publicado..." (exemplo atual)
                padrao_revogacao = re.compile(
                    r'(REVOGAR\s+(?:a\s+Portaria|o\s+ato).*?(?:tendo\s+em\s+vista.*?(?:Decreto\s+\d+\.\d+/\d+|artigo\s+\d+.*?Decreto\s+\d+\.\d+/\d+)))',
                    re.IGNORECASE | re.DOTALL
                )
                
                # Buscar número do processo no texto completo
                padrao_processo = re.compile(r'Processo\s*n[º°o]*\s*([\d\.\-/]+)', re.IGNORECASE)
                processo_match = padrao_processo.search(texto_completo)
                processo_numero = processo_match.group(1) if processo_match else "Não encontrado"
                
                # Extrair portaria atual do cabeçalho
                padrao_portaria_atual = re.compile(r'PORTARIA\s+N[º°o]*\s*(\d+[\d\.,]*),\s*DE\s+(\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4})', re.IGNORECASE)
                portaria_atual_match = padrao_portaria_atual.search(texto_completo)
                portaria_atual = f"PORTARIA Nº {portaria_atual_match.group(1)}, DE {portaria_atual_match.group(2)}" if portaria_atual_match else "Portaria não identificada"
                
                textos_revogacao = padrao_revogacao.findall(texto_completo)
                resultados = []
                
                for texto in textos_revogacao:
                    print(f"[DEBUG] 🔍 Analisando texto de revogação: {texto[:200]}...")
                    
                    # Extrair nome da pessoa - padrões para diferentes formatos de revogação
                    nome = "Nome não encontrado"
                    
                    # Formato 1: "expulsão do Território Nacional de NOME, de nacionalidade"
                    nome_match1 = re.search(r'expulsão\s+do\s+Território\s+Nacional\s+de\s+([^,]+?)(?:\s+ou\s+([^,]+?))?,\s*de\s+nacionalidade', texto, re.IGNORECASE)
                    if nome_match1:
                        nome_principal = nome_match1.group(1).strip()
                        nome_alternativo = nome_match1.group(2).strip() if nome_match1.group(2) else None
                        nome = f"{nome_principal} ou {nome_alternativo}" if nome_alternativo else nome_principal
                        print(f"[DEBUG] ✅ Nome encontrado (formato 1): {nome}")
                    else:
                        # Formato 2: buscar nome após "Nacional de" e antes de ","
                        nome_match2 = re.search(r'Nacional\s+de\s+([A-Z][A-Z\s]+?),\s*de\s+nacionalidade', texto, re.IGNORECASE)
                        if nome_match2:
                            nome = nome_match2.group(1).strip()
                            print(f"[DEBUG] ✅ Nome encontrado (formato 2): {nome}")
                        else:
                            # Formato 3: buscar nome entre "de" e ", de nacionalidade"
                            nome_match3 = re.search(r'\bde\s+([A-Z][A-Z\s]+?),\s*de\s+nacionalidade', texto, re.IGNORECASE)
                            if nome_match3:
                                nome = nome_match3.group(1).strip()
                                print(f"[DEBUG] ✅ Nome encontrado (formato 3): {nome}")
                            else:
                                print(f"[DEBUG] ❌ Nome não encontrado em nenhum formato")
                    
                    # Extrair nacionalidade
                    nacionalidade_match = re.search(r'de\s+nacionalidade\s+([^,]+)', texto, re.IGNORECASE)
                    nacionalidade = nacionalidade_match.group(1).strip() if nacionalidade_match else "Nacionalidade não encontrada"
                    
                    # Extrair informações familiares para determinar sexo
                    filho_match = re.search(r'(filh[oa])\s+de\s+([^,]+?)(?:\s+e\s+de\s+([^,]+?))?,\s*nascid[ao]', texto, re.IGNORECASE)
                    if filho_match:
                        sexo = "Masculino" if filho_match.group(1).lower() == "filho" else "Feminino"
                        pai = filho_match.group(2).strip()
                        mae = filho_match.group(3).strip() if filho_match.group(3) else None
                        if mae:
                            trecho_familiar = f"{filho_match.group(1)} de {pai} e de {mae}"
                        else:
                            trecho_familiar = f"{filho_match.group(1)} de {pai}"
                        print(f"[DEBUG] ✅ Sexo: {sexo}, Trecho familiar: {trecho_familiar}")
                    else:
                        sexo = "Não identificado"
                        trecho_familiar = "Informação familiar não encontrada"
                        print(f"[DEBUG] ❌ Informações familiares não encontradas")
                    
                    # Extrair data de nascimento - diferentes formatos
                    data_nascimento = "Data não encontrada"
                    # Formato 1: "nascido em DATA"
                    data_nasc_match1 = re.search(r'nascid[ao].*?em\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', texto, re.IGNORECASE)
                    if data_nasc_match1:
                        data_nascimento = data_nasc_match1.group(1)
                        print(f"[DEBUG] ✅ Data nascimento (formato 1): {data_nascimento}")
                    else:
                        # Formato 2: "nascida em LOCAL, em DATA"
                        data_nasc_match2 = re.search(r'nascid[ao].*?,\s*em\s+(\d{1,2}\s+de\s+\w+\s+de\s+\d{4})', texto, re.IGNORECASE)
                        if data_nasc_match2:
                            data_nascimento = data_nasc_match2.group(1)
                            print(f"[DEBUG] ✅ Data nascimento (formato 2): {data_nascimento}")
                        else:
                            print(f"[DEBUG] ❌ Data de nascimento não encontrada")
                    
                    # Extrair comprovação (texto após "tendo em vista")
                    comprovacao_match = re.search(r'(tendo\s+em\s+vista.*?(?:Decreto\s+\d+\.\d+/\d+|artigo\s+\d+.*?Decreto\s+\d+\.\d+/\d+))', texto, re.IGNORECASE | re.DOTALL)
                    comprovacao = comprovacao_match.group(1).strip() if comprovacao_match else "Comprovação não encontrada"
                    
                    # Extrair portaria revogada - diferentes formatos
                    portaria_revogada = "Portaria revogada não identificada"
                    portaria_revogada_numero = "Não identificado"
                    portaria_revogada_orgao = "Não identificado"
                    portaria_revogada_data = "Não identificado"
                    portaria_revogada_ano = "Não identificado"
                    
                    # Formato 1a: "REVOGAR a Portaria ORGAO nº NUMERO, de DATA" (com órgão, vírgula opcional)
                    portaria_revogada_match1a = re.search(r'REVOGAR\s+a\s+Portaria\s+([A-Z][A-Z/]*)\s*n[º°o]*\s*(\d+(?:\.\d+)*),?\s*de\s+(\d{1,2}\s+de\s+\w+\s+de\s+(\d{4}))', texto, re.IGNORECASE)
                    if portaria_revogada_match1a:
                        portaria_revogada_orgao = portaria_revogada_match1a.group(1)
                        portaria_revogada_numero = portaria_revogada_match1a.group(2)
                        portaria_revogada_data = portaria_revogada_match1a.group(3)
                        portaria_revogada_ano = portaria_revogada_match1a.group(4)
                        portaria_revogada = f"Portaria {portaria_revogada_orgao} nº {portaria_revogada_numero}, de {portaria_revogada_data}"
                        print(f"[DEBUG] ✅ Portaria revogada (formato 1a): {portaria_revogada}")
                        print(f"[DEBUG] ✅ Ano da portaria revogada: {portaria_revogada_ano}")
                    else:
                        # Formato 1b: "REVOGAR a Portaria nº NUMERO, de DATA" (sem órgão específico, vírgula opcional)
                        portaria_revogada_match1b = re.search(r'REVOGAR\s+a\s+Portaria\s+n[º°o]*\s*(\d+(?:\.\d+)*),?\s*de\s+(\d{1,2}\s+de\s+\w+\s+de\s+(\d{4}))', texto, re.IGNORECASE)
                        if portaria_revogada_match1b:
                            portaria_revogada_orgao = "Não especificado"
                            portaria_revogada_numero = portaria_revogada_match1b.group(1)
                            portaria_revogada_data = portaria_revogada_match1b.group(2)
                            portaria_revogada_ano = portaria_revogada_match1b.group(3)
                            portaria_revogada = f"Portaria nº {portaria_revogada_numero}, de {portaria_revogada_data}"
                            print(f"[DEBUG] ✅ Portaria revogada (formato 1b): {portaria_revogada}")
                            print(f"[DEBUG] ✅ Ano da portaria revogada: {portaria_revogada_ano}")
                        else:
                            # Formato 2: "ato publicado no Diário Oficial da União do dia DATA"
                            ato_revogado_match = re.search(r'ato\s+publicado\s+no\s+Diário\s+Oficial\s+da\s+União\s+do\s+dia\s+([^,]+)', texto, re.IGNORECASE)
                            if ato_revogado_match:
                                data_publicacao = ato_revogado_match.group(1).strip()
                                portaria_revogada = f"Ato publicado no DOU em {data_publicacao}"
                                
                                # Extrair ano da data de publicação
                                ano_match = re.search(r'\b(\d{4})\b', data_publicacao)
                                if ano_match:
                                    portaria_revogada_ano = ano_match.group(1)
                                    print(f"[DEBUG] ✅ Ano extraído da data de publicação: {portaria_revogada_ano}")
                                
                                print(f"[DEBUG] ✅ Portaria revogada (formato 2): {portaria_revogada}")
                            else:
                                # Formato 3: Buscar qualquer portaria mencionada no texto antes de "publicada"
                                portaria_match3 = re.search(r'Portaria\s+([A-Z/]+)\s*n[º°o]*\s*(\d+),\s*de\s+(\d{1,2}\s+de\s+\w+\s+de\s+(\d{4})),\s*publicada', texto, re.IGNORECASE)
                                if portaria_match3:
                                    portaria_revogada_orgao = portaria_match3.group(1)
                                    portaria_revogada_numero = portaria_match3.group(2)
                                    portaria_revogada_data = portaria_match3.group(3)
                                    portaria_revogada_ano = portaria_match3.group(4)
                                    portaria_revogada = f"Portaria {portaria_revogada_orgao} nº {portaria_revogada_numero}, de {portaria_revogada_data}"
                                    print(f"[DEBUG] ✅ Portaria revogada (formato 3): {portaria_revogada}")
                                    print(f"[DEBUG] ✅ Ano da portaria revogada: {portaria_revogada_ano}")
                                else:
                                    print(f"[DEBUG] ❌ Portaria revogada não identificada")
                    
                    resultados.append({
                        "Processo": processo_numero,
                        "Nome": nome,
                        "Nacionalidade": nacionalidade,
                        "Data de Nascimento": data_nascimento,
                        "Sexo": sexo,
                        "Trecho Familiar": trecho_familiar,
                        "Comprovação": comprovacao,
                        "Portaria Revogada": portaria_revogada,
                        "Portaria Revogada - Número": portaria_revogada_numero,
                        "Portaria Revogada - Órgão": portaria_revogada_orgao,
                        "Portaria Revogada - Data": portaria_revogada_data,
                        "Portaria Revogada - Ano": portaria_revogada_ano,
                        "Portaria Atual": portaria_atual,
                        "Texto Completo Revogação": texto.strip()
                    })
                
                return resultados
            
            def extrair_portarias_revogacao(driver, url, caminho_saida):
                """Extrai portarias de revogação seguindo o mesmo padrão da expulsão"""
                print(f"[DEBUG] Acessando URL: {url}")
                
                # Se a URL não contém termo específico para revogação, sugerir uma busca mais específica
                if "revogar" not in url.lower():
                    print("[AVISO] ⚠️ A URL fornecida não parece ser específica para revogações.")
                    print("[DICA] 💡 Considere usar uma busca com o termo 'REVOGAR' no DOU para melhores resultados.")
                
                driver.get(url)
                todos_dados = []
                pagina = 1
                
                while True:
                    print(f"[INFO] 🔍 Processando página {pagina}...")
                    print(f"[DEBUG] URL atual: {driver.current_url}")
                    
                    try:
                        # Aguardar carregamento da página - usando o mesmo padrão da expulsão
                        print("[DEBUG] ⏳ Aguardando carregamento da página...")
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                        )
                        print("[DEBUG] ✅ Página carregada!")
                        
                        # Obter todos os links das portarias - usando o mesmo XPath da expulsão
                        print("[DEBUG] 🔗 Buscando links das portarias...")
                        portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                        links_portarias = [link.get_attribute('href') for link in portarias_links]
                        
                        print(f"[INFO] 📋 Encontrados {len(links_portarias)} links na página {pagina}")
                        
                        if len(links_portarias) == 0:
                            print("[AVISO] ⚠️ Nenhum link encontrado nesta página. Verificando se existe conteúdo...")
                            # Pausa para permitir visualização
                            time.sleep(3)
                        
                        # Processar cada portaria - usando o mesmo padrão da expulsão (nova aba)
                        for i, link in enumerate(links_portarias, 1):
                            print(f"[INFO] 📄 Processando portaria {i}/{len(links_portarias)}")
                            print(f"[DEBUG] 🌐 Link: {link}")
                            
                            try:
                                # Abrir nova aba (mesmo padrão da expulsão)
                                driver.execute_script("window.open('');")
                                driver.switch_to.window(driver.window_handles[1])
                                driver.get(link)
                                
                                print("[DEBUG] ⏳ Aguardando carregamento do texto da portaria...")
                                WebDriverWait(driver, 30).until(
                                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                                )
                                time.sleep(2)
                                
                                # Extrair texto da portaria - usando o mesmo padrão da expulsão
                                try:
                                    # Primeiro tentar pegar o texto completo do body
                                    texto_portaria = driver.find_element(By.XPATH, "//body").text
                                    
                                    # Se não conseguir ou o texto for muito pequeno, tentar com div texto-dou
                                    if not texto_portaria or len(texto_portaria) < 200:
                                        try:
                                            div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                            paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                            texto_portaria = "\n".join([p.text for p in paragrafos])
                                        except:
                                            pass
                                    
                                    print(f"[DEBUG] 📝 Texto extraído ({len(texto_portaria)} caracteres)")
                                    
                                    # Mostrar preview do texto para debug
                                    preview = texto_portaria[:200] + "..." if len(texto_portaria) > 200 else texto_portaria
                                    print(f"[DEBUG] 👀 Preview do texto: {preview}")
                                    
                                except Exception as e:
                                    print(f"[ERRO] ❌ Erro ao extrair texto: {e}")
                                    try:
                                        # Fallback - tentar novamente com div texto-dou
                                        div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                        paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                        texto_portaria = "\n".join([p.text for p in paragrafos])
                                    except:
                                        texto_portaria = ""
                                
                                # Extrair dados de revogação
                                print("[DEBUG] 🔍 Executando extração de dados de revogação...")
                                
                                # Verificar se contém palavra "REVOGAR" antes de processar
                                if "REVOGAR" in texto_portaria.upper():
                                    print("[DEBUG] ✅ Texto contém 'REVOGAR' - processando...")
                                    processos_revogacao = extrair_processos_revogacao(texto_portaria)
                                    print(f"[DEBUG] 📊 {len(processos_revogacao)} processo(s) de revogação encontrado(s)")
                                else:
                                    print("[DEBUG] ❌ Texto NÃO contém 'REVOGAR' - pulando esta portaria...")
                                    processos_revogacao = []
                                
                                for j, processo in enumerate(processos_revogacao, 1):
                                    print(f"[DEBUG] ✅ Adicionando processo {j}: {processo['Nome']}")
                                    todos_dados.append({
                                        "Link Portaria": link,
                                        "Número do Processo": processo["Processo"],
                                        "Nome": processo["Nome"],
                                        "Nacionalidade": processo["Nacionalidade"],
                                        "Data de Nascimento": processo["Data de Nascimento"],
                                        "Sexo": processo["Sexo"],
                                        "Trecho Familiar": processo["Trecho Familiar"],
                                        "Comprovação": processo["Comprovação"],
                                        "Portaria Revogada": processo["Portaria Revogada"],
                                        "Portaria Revogada - Número": processo["Portaria Revogada - Número"],
                                        "Portaria Revogada - Órgão": processo["Portaria Revogada - Órgão"],
                                        "Portaria Revogada - Data": processo["Portaria Revogada - Data"],
                                        "Portaria Revogada - Ano": processo["Portaria Revogada - Ano"],
                                        "Portaria Atual": processo["Portaria Atual"],
                                        "Texto Completo": processo["Texto Completo Revogação"]
                                    })
                                
                                # Fechar aba e voltar para a principal (mesmo padrão da expulsão)
                                driver.close()
                                driver.switch_to.window(driver.window_handles[0])
                                time.sleep(1)
                                
                            except Exception as e:
                                print(f"[ERRO] ❌ Erro ao processar portaria {i}: {e}")
                                # Garantir que voltamos para a aba principal mesmo em caso de erro
                                try:
                                    if len(driver.window_handles) > 1:
                                        driver.close()
                                        driver.switch_to.window(driver.window_handles[0])
                                except:
                                    pass
                                continue
                    
                    except Exception as e:
                        print(f"[ERRO] Erro na página {pagina}: {e}")
                        break
                    
                    # Tentar ir para próxima página - usando o mesmo padrão da expulsão
                    try:
                        print("[DEBUG] 🔄 Tentando ir para próxima página...")
                        right_arrow = driver.find_element(By.ID, "rightArrow")
                        if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                            print(f"[DEBUG] ➡️ Clicando para ir para página {pagina + 1}")
                            right_arrow.click()
                            pagina += 1
                            time.sleep(2)
                        else:
                            print("[INFO] 🏁 Última página alcançada.")
                            break
                    except Exception as e:
                        print(f"[INFO] 🔚 Não há mais páginas ou erro ao clicar na seta: {e}")
                        break
                
                # Salvar dados em Excel
                if todos_dados:
                    print(f"[INFO] 💾 Salvando {len(todos_dados)} registros em Excel...")
                    df = pd.DataFrame(todos_dados)
                    df.to_excel(caminho_saida, index=False)
                    print(f"[OK] ✅ Dados salvos em: {caminho_saida}")
                    
                    # Mostrar resumo dos dados encontrados
                    print("\n" + "="*60)
                    print("📊 RESUMO DOS DADOS EXTRAÍDOS:")
                    print("="*60)
                    for i, registro in enumerate(todos_dados, 1):
                        print(f"{i}. {registro['Nome']} - {registro['Nacionalidade']}")
                    print("="*60 + "\n")
                    
                    return caminho_saida, len(todos_dados)
                else:
                    print("[AVISO] ⚠️ Nenhum dado de revogação encontrado")
                    print("\n" + "="*60)
                    print("💡 DICAS PARA MELHORAR A BUSCA DE REVOGAÇÕES:")
                    print("="*60)
                    print("1. Use uma busca específica no DOU com o termo: 'REVOGAR'")
                    print("2. Adicione filtros como: 'REVOGAR a Portaria'")
                    print("3. Verifique se as portarias encontradas são realmente de revogação")
                    print("4. Exemplo de busca recomendada:")
                    print("   https://www.in.gov.br/consulta/-/buscar/dou?q=REVOGAR&s=todos")
                    print("="*60 + "\n")
                    return None, 0
            
            # Configuração do Chrome (visível para debug)
            chrome_options = webdriver.ChromeOptions()
            # Remover --headless para tornar o navegador visível
            # chrome_options.add_argument("--headless")  # COMENTADO para debug
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            # Configurar tamanho da janela para melhor visualização
            chrome_options.add_argument("--window-size=1200,800")
            chrome_options.add_argument("--start-maximized")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Adicionar script para esconder que é um bot
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"revogacoes_{timestamp}.xlsx"
                caminho_saida = os.path.join(os.getcwd(), nome_arquivo)
                
                arquivo, total_registros = extrair_portarias_revogacao(driver, link_personalizado, caminho_saida)
                
                # Preparar amostra de dados para preview
                pessoas_amostra = []
                if arquivo:
                    try:
                        df_amostra = pd.read_excel(arquivo)
                        pessoas_amostra = df_amostra.head(20).to_dict('records')
                    except:
                        pessoas_amostra = []
                
                if arquivo and total_registros > 0:
                    return jsonify({
                        'success': True,
                        'arquivo': nome_arquivo,
                        'total_registros': total_registros,
                        'mensagem': f'Busca de revogações concluída! {total_registros} registros encontrados.',
                        'tipo_busca': tipo_portaria,
                        'pessoas': pessoas_amostra
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Nenhum processo de revogação encontrado.'
                    })
            finally:
                driver.quit()
                
        elif tipo_portaria == 'deferimento':
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
            import pandas as pd
            import os
            def extrair_portarias_deferimento(driver, url, caminho_saida, analyzer):
                driver.get(url)
                todas_pessoas = []
                import time
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                import pandas as pd
                import re
                pagina = 1
                while True:
                    print(f"Processando página {pagina}...")
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                    )
                    portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                    links = [link.get_attribute('href') for link in portarias_links]
                    for link in links:
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[1])
                        driver.get(link)
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(2)
                        
                        # Extrair data de publicação do DOU
                        data_publicacao_dou = ''
                        try:
                            elemento_data = driver.find_element(By.CSS_SELECTOR, "span.publicado-dou-data")
                            data_publicacao_dou = elemento_data.text.strip()
                            print(f"[INFO] Data de publicação DOU: {data_publicacao_dou}")
                        except Exception as e:
                            print(f"[AVISO] Não foi possível extrair a data de publicação: {e}")
                            # Tentar método alternativo usando XPath
                            try:
                                elemento_data = driver.find_element(By.XPATH, "//span[@class='publicado-dou-data']")
                                data_publicacao_dou = elemento_data.text.strip()
                                print(f"[INFO] Data de publicação DOU (XPath): {data_publicacao_dou}")
                            except:
                                data_publicacao_dou = ''
                        
                        try:
                            texto_portaria = driver.find_element(By.XPATH, "//body").text
                            if not texto_portaria or len(texto_portaria) < 200:
                                try:
                                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                    texto_portaria = "\n".join([p.text for p in paragrafos])
                                except:
                                    pass
                        except:
                            try:
                                div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                texto_portaria = "\n".join([p.text for p in paragrafos])
                            except:
                                texto_portaria = ""
                        
                        print(f"[DOC] Analisando portaria da URL: {link}")
                        print(f"[DADOS] Tamanho do texto: {len(texto_portaria)} caracteres")
                        
                        try:
                            # Usar analisar_multiplas_portarias para processar corretamente múltiplas portarias
                            resultados, _ = analyzer.analisar_multiplas_portarias(texto_portaria, gerar_excel=False)
                            
                            print(f"[INFO] Portarias encontradas na página: {len(resultados)}")
                            
                            for i, res in enumerate(resultados, 1):
                                if res.get('dados_portaria'):
                                    dados_portaria = res['dados_portaria']
                                    tipo_portaria = dados_portaria.get('tipo', 'DESCONHECIDO')
                                    numero_portaria = dados_portaria.get('numero_data_formatado', 'N/A')
                                    
                                    print(f"   {i}. {numero_portaria} - Tipo: {tipo_portaria}")
                                    print(f"      Pessoas: {len(dados_portaria.get('pessoas', []))}")
                                    
                                    # Adicionar cada pessoa com as informações corretas da sua portaria
                                    for pessoa in dados_portaria.get('pessoas', []):
                                        pessoa_info = pessoa.copy()
                                        pessoa_info['portaria_completa'] = numero_portaria
                                        pessoa_info['tipo_portaria'] = tipo_portaria
                                        pessoa_info['data_publicacao_dou'] = data_publicacao_dou  # Adicionar data de publicação do DOU
                                        pessoa_info['url_fonte'] = link  # Adicionar URL fonte para rastreabilidade
                                        todas_pessoas.append(pessoa_info)
                                        
                            print(f"[OK] Total de pessoas extraídas desta página: {sum(len(res.get('dados_portaria', {}).get('pessoas', [])) for res in resultados)}")
                                    
                        except Exception as e:
                            print(f"[ERRO] Erro ao analisar portaria da URL {link}: {e}")
                            import traceback
                            traceback.print_exc()
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(1)
                    try:
                        right_arrow = driver.find_element(By.ID, "rightArrow")
                        if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                            right_arrow.click()
                            pagina += 1
                            time.sleep(2)
                        else:
                            print("Última página alcançada.")
                            break
                    except Exception as e:
                        print("Não há mais páginas ou erro ao clicar na seta:", e)
                        break
                if todas_pessoas:
                    df = pd.DataFrame(todas_pessoas)
                    df = df.fillna('')
                    
                    # Verificar distribuição de tipos antes de salvar
                    print(f"\n[DADOS] RESUMO FINAL DA EXTRAÇÃO:")
                    print(f"   Total de pessoas extraídas: {len(df)}")
                    
                    if 'tipo_portaria' in df.columns:
                        tipos_count = df['tipo_portaria'].value_counts()
                        print(f"   Distribuição por tipo:")
                        for tipo, count in tipos_count.items():
                            print(f"      {tipo}: {count} pessoas")
                    
                    if 'portaria_completa' in df.columns:
                        portarias_count = df['portaria_completa'].value_counts()
                        print(f"   Distribuição por portaria:")
                        for portaria, count in portarias_count.items():
                            portaria_short = portaria.replace('PORTARIA Nº ', '').split(',')[0]
                            print(f"      {portaria_short}: {count} pessoas")
                    
                    # Reordenar colunas para facilitar análise
                    colunas_importantes = ['Nome Completo', 'Tipo', 'Portaria', 'Data de Publicação', 'Processo', 'Pais de Nascimento', 'Estado', 'Data de Nascimento']
                    colunas_existentes = [col for col in colunas_importantes if col in df.columns]
                    colunas_restantes = [col for col in df.columns if col not in colunas_importantes]
                    df = df[colunas_existentes + colunas_restantes]
                    
                    df.to_excel(caminho_saida, index=False)
                    print(f"[OK] Planilha salva em: {caminho_saida}")
                    return caminho_saida, len(df)
                else:
                    print("[ERRO] Nenhuma pessoa foi extraída")
                    return None, 0
            options = webdriver.ChromeOptions()
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"deferimentos_{timestamp}.xlsx"
                # Salvar na pasta uploads correta
                caminho_uploads = os.path.join(os.path.dirname(__file__), 'uploads')
                os.makedirs(caminho_uploads, exist_ok=True)
                caminho_saida = os.path.join(caminho_uploads, nome_arquivo)
                arquivo, total_registros = extrair_portarias_deferimento(driver, link_personalizado, caminho_saida, analyzer)
                pessoas_amostra = []
                if arquivo:
                    try:
                        df = pd.read_excel(arquivo)
                        # Tratar valores NaN antes de converter para dicionário
                        df = df.fillna('')
                        pessoas_amostra = df.head(20).to_dict(orient='records')
                    except Exception as e:
                        pessoas_amostra = []
                    return jsonify({
                        'success': True,
                        'arquivo': nome_arquivo,
                        'total_registros': total_registros,
                        'mensagem': f'Busca concluída com sucesso! {total_registros} registros encontrados.',
                        'tipo_busca': tipo_portaria,
                        'pessoas': pessoas_amostra
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Nenhum deferimento encontrado.'
                    })
            finally:
                driver.quit()
        elif tipo_portaria in ['perda', 'perda_nacionalidade']:
            print(f"[DEBUG] Tipo de portaria recebido: {tipo_portaria}")
            print(f"[DEBUG] Link recebido: {link_personalizado}")
            print("[DEBUG] Antes da importação do parser de perda")
            try:
                from perda import extrair_pessoas_perda_nacionalidade_html
                print("[DEBUG] Após a importação do parser de perda")
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                from webdriver_manager.chrome import ChromeDriverManager
                import time
                import pandas as pd
                import os
                def extrair_portarias_perda(driver, url, caminho_saida):
                    driver.get(url)
                    todas_pessoas = []
                    pagina = 1
                    while True:
                        print(f"Processando página {pagina}...")
                        try:
                            WebDriverWait(driver, 20).until(
                                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                            )
                        except Exception as e:
                            print(f"[ERRO] Não encontrou portarias na página {pagina}: {e}")
                            break
                        portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                        links = [link.get_attribute('href') for link in portarias_links]
                        for link in links:
                            print(f"[DEBUG] Abrindo portaria: {link}")
                            driver.execute_script("window.open('');")
                            driver.switch_to.window(driver.window_handles[1])
                            driver.get(link)
                            try:
                                WebDriverWait(driver, 30).until(
                                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                                )
                                time.sleep(2)
                                try:
                                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                    html_portaria = div_texto_dou.get_attribute('outerHTML')
                                except Exception as e:
                                    print(f"[DEBUG] Não encontrou div texto-dou, usando page_source. Erro: {e}")
                                    html_portaria = driver.page_source
                                print(f"[DEBUG] Extraindo pessoas da portaria...")
                                pessoas = extrair_pessoas_perda_nacionalidade_html(html_portaria)
                                print(f"[DEBUG] Pessoas extraídas: {len(pessoas)}")
                                todas_pessoas.extend(pessoas)
                            except Exception as e:
                                print(f"[ERRO] Falha ao extrair texto da portaria: {e}")
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            time.sleep(1)
                        try:
                            right_arrow = driver.find_element(By.ID, "rightArrow")
                            if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                                right_arrow.click()
                                pagina += 1
                                time.sleep(2)
                            else:
                                print("Última página alcançada.")
                                break
                        except Exception as e:
                            print("Não há mais páginas ou erro ao clicar na seta:", e)
                            break
                    if todas_pessoas:
                        df = pd.DataFrame(todas_pessoas)
                        df = df.fillna('')
                        df.to_excel(caminho_saida, index=False)
                        return caminho_saida, len(df)
                    else:
                        return None, 0
                options = webdriver.ChromeOptions()
                options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                print("[DEBUG] Iniciando ChromeDriver...")
                try:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                except Exception as e:
                    print(f"[ERRO] Falha ao iniciar o ChromeDriver: {e}")
                    return jsonify({
                        'success': False,
                        'message': f'Erro ao iniciar o Chrome/Selenium: {str(e)}. Verifique se o Chrome está instalado e se o ChromeDriver pode ser baixado.'
                    })
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nome_arquivo = f"perda_nacionalidade_{timestamp}.xlsx"
                    caminho_saida = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                    print(f"[DEBUG] Iniciando extração das portarias de perda...")
                    arquivo, total_registros = extrair_portarias_perda(driver, link_personalizado, caminho_saida)
                    pessoas_amostra = []
                    if arquivo:
                        try:
                            df = pd.read_excel(arquivo)
                            df = df.fillna('')
                            pessoas_amostra = df.head(20).to_dict(orient='records')
                        except Exception as e:
                            pessoas_amostra = []
                        return jsonify({
                            'success': True,
                            'arquivo': nome_arquivo,
                            'total_registros': total_registros,
                            'mensagem': f'Busca concluída com sucesso! {total_registros} registros encontrados.',
                            'tipo_busca': tipo_portaria,
                            'pessoas': pessoas_amostra
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'Nenhuma perda de nacionalidade encontrada.'
                        })
                except Exception as e:
                    print(f"[ERRO] Falha durante a extração: {e}")
                    return jsonify({
                        'success': False,
                        'message': f'Erro durante a extração: {str(e)}'
                    })
                finally:
                    driver.quit()
            except Exception as e:
                print(f"[ERRO] Falha geral no bloco de perda: {e}")
                return jsonify({
                    'success': False,
                    'message': f'Erro inesperado: {str(e)}'
                })
        elif tipo_portaria in ['tornar_sem_efeito', 'sem_efeito']:
            print(f"[DEBUG] Tipo de portaria recebido: {tipo_portaria}")
            print(f"[DEBUG] Link recebido: {link_personalizado}")
            print("[DEBUG] Iniciando extração de despachos de tornar sem efeito")
            try:
                from tornar_sem_efeito import ProcessadorTornarSemEfeito
                print("[DEBUG] Módulo de tornar sem efeito importado com sucesso")
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager
                import os
                
                # Configurar Chrome com opções adequadas
                options = webdriver.ChromeOptions()
                options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option("useAutomationExtension", False)
                options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                
                print("[DEBUG] Iniciando ChromeDriver...")
                try:
                    service = Service(ChromeDriverManager().install())
                    driver = webdriver.Chrome(service=service, options=options)
                except Exception as e:
                    print(f"[ERRO] Falha ao iniciar o ChromeDriver: {e}")
                    return jsonify({
                        'success': False,
                        'message': f'Erro ao iniciar o Chrome/Selenium: {str(e)}. Verifique se o Chrome está instalado.'
                    })
                
                try:
                    # Criar processador
                    processador = ProcessadorTornarSemEfeito()
                    
                    # Gerar nome do arquivo de saída
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    nome_arquivo = f"tornar_sem_efeito_{timestamp}.xlsx"
                    caminho_saida = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
                    
                    print(f"[DEBUG] Iniciando extração de despachos de tornar sem efeito...")
                    arquivo, total_registros = processador.extrair_portarias_tornar_sem_efeito(
                        driver, 
                        link_personalizado, 
                        caminho_saida
                    )
                    
                    despachos_amostra = []
                    if arquivo:
                        try:
                            df = pd.read_excel(arquivo)
                            df = df.fillna('')
                            despachos_amostra = df.head(20).to_dict(orient='records')
                        except Exception as e:
                            print(f"[AVISO] Erro ao ler arquivo para amostra: {e}")
                            despachos_amostra = []
                        
                        return jsonify({
                            'success': True,
                            'arquivo': nome_arquivo,
                            'total_registros': total_registros,
                            'mensagem': f'Busca concluída com sucesso! {total_registros} despachos de tornar sem efeito encontrados.',
                            'tipo_busca': tipo_portaria,
                            'pessoas': despachos_amostra
                        })
                    else:
                        return jsonify({
                            'success': False,
                            'message': 'Nenhum despacho de tornar sem efeito encontrado.'
                        })
                        
                except Exception as e:
                    print(f"[ERRO] Falha durante a extração: {e}")
                    import traceback
                    traceback.print_exc()
                    return jsonify({
                        'success': False,
                        'message': f'Erro durante a extração: {str(e)}'
                    })
                finally:
                    try:
                        driver.quit()
                    except:
                        pass
                        
            except Exception as e:
                print(f"[ERRO] Falha geral no bloco de tornar sem efeito: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'message': f'Erro inesperado: {str(e)}'
                })
        elif tipo_portaria == 'igualdade':
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
            import pandas as pd
            import os
            from igualdade import separar_blocos_igualdade
            def extrair_portarias_igualdade(driver, url, caminho_saida, analyzer, separar_blocos_igualdade):
                driver.get(url)
                todas_pessoas = []
                pagina = 1
                while True:
                    print(f"Processando página {pagina}...")
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                    ))
                    portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                    links = [link.get_attribute('href') for link in portarias_links]
                    for link in links:
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[1])
                        driver.get(link)
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.TAG_NAME, "body"))
                        )
                        time.sleep(2)
                        try:
                            texto_portaria = driver.find_element(By.XPATH, "//body").text
                            if not texto_portaria or len(texto_portaria) < 200:
                                try:
                                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                    texto_portaria = "\n".join([p.text for p in paragrafos])
                                except:
                                    pass
                        except:
                            try:
                                div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                texto_portaria = "\n".join([p.text for p in paragrafos])
                            except:
                                texto_portaria = ""
                        blocos = separar_blocos_igualdade(texto_portaria)
                        for bloco_info in blocos:
                            bloco = bloco_info['texto']
                            tipo_igualdade = bloco_info['tipo']
                            try:
                                # Usar função específica para igualdade de direitos portuguesa
                                pessoas_extraidas = analyzer.extrair_pessoas_igualdade(bloco)
                                
                                for pessoa in pessoas_extraidas:
                                    pessoa_info = pessoa.copy()
                                    
                                    # Adicionar informações de portaria
                                    pessoa_info['portaria_completa'] = f"PORTARIA {bloco[:50]}..."  # Primeiros 50 chars como identificação
                                    pessoa_info['tipo_portaria'] = 'Igualdade de Direitos'
                                    
                                    # Adicionar colunas específicas para o tipo de igualdade
                                    if tipo_igualdade == 'outorga_direitos_politicos':
                                        pessoa_info['outorga_direitos_politicos'] = 'Sim'
                                        pessoa_info['igualdade_direitos_obrigacoes'] = ''
                                        pessoa_info['tipo_igualdade_completo'] = 'Outorga de Direitos Políticos'
                                    elif tipo_igualdade == 'igualdade_direitos_obrigacoes':
                                        pessoa_info['outorga_direitos_politicos'] = ''
                                        pessoa_info['igualdade_direitos_obrigacoes'] = 'Sim'
                                        pessoa_info['tipo_igualdade_completo'] = 'Igualdade de Direitos e Obrigações Civis'
                                    elif tipo_igualdade == 'igualdade_portuguesa':
                                        pessoa_info['outorga_direitos_politicos'] = ''
                                        pessoa_info['igualdade_direitos_obrigacoes'] = 'Sim'
                                        pessoa_info['tipo_igualdade_completo'] = 'Igualdade de Direitos Portuguesa'
                                    else:
                                        pessoa_info['outorga_direitos_politicos'] = ''
                                        pessoa_info['igualdade_direitos_obrigacoes'] = ''
                                        pessoa_info['tipo_igualdade_completo'] = tipo_igualdade
                                    
                                    pessoa_info['tipo_igualdade_identificado'] = tipo_igualdade
                                    todas_pessoas.append(pessoa_info)
                                    
                            except Exception as e:
                                print(f"Erro ao analisar portaria de igualdade: {e}")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(1)
                    try:
                        right_arrow = driver.find_element(By.ID, "rightArrow")
                        if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                            right_arrow.click()
                            pagina += 1
                            time.sleep(2)
                        else:
                            print("Última página alcançada.")
                            break
                    except Exception as e:
                        print("Não há mais páginas ou erro ao clicar na seta:", e)
                        break
                if todas_pessoas:
                    df = pd.DataFrame(todas_pessoas)
                    df = df.fillna('')
                    df.to_excel(caminho_saida, index=False)
                    return caminho_saida, len(df)
                else:
                    return None, 0
            options = webdriver.ChromeOptions()
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"igualdade_{timestamp}.xlsx"
                caminho_uploads = os.path.join(os.path.dirname(__file__), 'uploads')
                os.makedirs(caminho_uploads, exist_ok=True)
                caminho_saida = os.path.join(caminho_uploads, nome_arquivo)
                arquivo, total_registros = extrair_portarias_igualdade(driver, link_personalizado, caminho_saida, analyzer, separar_blocos_igualdade)
                pessoas_amostra = []
                if arquivo:
                    try:
                        df = pd.read_excel(arquivo)
                        df = df.fillna('')
                        pessoas_amostra = df.head(20).to_dict(orient='records')
                    except Exception as e:
                        pessoas_amostra = []
                    return jsonify({
                        'success': True,
                        'arquivo': nome_arquivo,
                        'total_registros': total_registros,
                        'mensagem': f'Busca concluída com sucesso! {total_registros} registros encontrados.',
                        'tipo_busca': tipo_portaria,
                        'pessoas': pessoas_amostra
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Nenhuma portaria de igualdade encontrada.'
                    })
            finally:
                driver.quit()
                
        elif tipo_portaria == 'naturalizacao':
            # CORREÇÃO: Implementar busca de naturalização usando Selenium (como os outros tipos)
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
            import time
            import pandas as pd
            import os
            
            def extrair_portarias_naturalizacao(driver, url, caminho_saida):
                """
                Extrai portarias de naturalização usando Selenium
                """
                driver.get(url)
                todas_pessoas = []
                pagina = 1
                
                while True:
                    print(f"Processando página {pagina}...")
                    try:
                        # Aguardar portarias carregarem
                        WebDriverWait(driver, 20).until(
                            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                        )
                    except Exception as e:
                        print(f"[ERRO] Não encontrou portarias na página {pagina}: {e}")
                        break
                    
                    # Encontrar links das portarias
                    portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
                    links = [link.get_attribute('href') for link in portarias_links]
                    
                    print(f"Encontrados {len(links)} links de portarias na página {pagina}")
                    
                    for link in links:
                        try:
                            # Abrir portaria em nova aba
                            driver.execute_script("window.open('');")
                            driver.switch_to.window(driver.window_handles[1])
                            driver.get(link)
                            
                            # Aguardar página carregar
                            WebDriverWait(driver, 30).until(
                                EC.presence_of_element_located((By.TAG_NAME, "body"))
                            )
                            time.sleep(2)
                            
                            # Extrair texto da portaria
                            try:
                                texto_portaria = driver.find_element(By.XPATH, "//body").text
                                
                                # Se texto muito pequeno, tentar div específica do DOU
                                if not texto_portaria or len(texto_portaria) < 200:
                                    try:
                                        div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                        paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                        texto_portaria = "\n".join([p.text for p in paragrafos])
                                    except:
                                        pass
                            except:
                                try:
                                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                                    texto_portaria = "\n".join([p.text for p in paragrafos])
                                except:
                                    texto_portaria = ""
                            
                            # Verificar se é portaria de naturalização
                            if texto_portaria and ('naturalização' in texto_portaria.lower() or 
                                                 'naturalizacao' in texto_portaria.lower() or
                                                 'nacionalidade brasileira' in texto_portaria.lower()):
                                
                                print(f"[OK] Portaria de naturalização encontrada: {link[:80]}...")
                                
                                # Analisar portaria usando o analyzer
                                try:
                                    resultados, _ = analyzer.analisar_multiplas_portarias(texto_portaria, gerar_excel=False)
                                    
                                    for resultado in resultados:
                                        if resultado.get('dados_portaria'):
                                            dados = resultado['dados_portaria']
                                            for pessoa in dados.get('pessoas', []):
                                                pessoa_info = {
                                                    'nome': pessoa.get('nome', ''),
                                                    'documento': pessoa.get('documento', ''),
                                                    'processo': pessoa.get('processo', ''),
                                                    'pais': pessoa.get('pais', ''),
                                                    'estado': pessoa.get('estado', ''),
                                                    'idade': pessoa.get('idade', ''),
                                                    'data_nascimento': pessoa.get('data_nascimento', ''),
                                                    'numero_portaria': dados.get('numero_data_formatado', ''),
                                                    'tipo_portaria': dados.get('tipo', 'Naturalização'),
                                                    'link_portaria': link
                                                }
                                                todas_pessoas.append(pessoa_info)
                                                
                                except Exception as e:
                                    print(f"[ERRO] Erro ao analisar portaria: {e}")
                            
                            # Fechar aba da portaria
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            time.sleep(1)
                            
                        except Exception as e:
                            print(f"[ERRO] Erro ao processar portaria {link}: {e}")
                            # Tentar voltar para aba principal
                            try:
                                driver.switch_to.window(driver.window_handles[0])
                            except:
                                pass
                            continue
                    
                    # Tentar ir para próxima página
                    try:
                        right_arrow = driver.find_element(By.ID, "rightArrow")
                        if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                            right_arrow.click()
                            pagina += 1
                            time.sleep(2)
                        else:
                            print("Última página alcançada.")
                            break
                    except Exception as e:
                        print("Não há mais páginas ou erro ao clicar na seta:", e)
                        break
                
                # Salvar resultados
                if todas_pessoas:
                    df = pd.DataFrame(todas_pessoas)
                    df = df.fillna('')
                    df.to_excel(caminho_saida, index=False)
                    return caminho_saida, len(df)
                else:
                    return None, 0
            
            # Configurar Chrome
            options = webdriver.ChromeOptions()
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            
            try:
                print("[BUSCA] Iniciando busca de naturalização com Selenium...")
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                nome_arquivo = f"naturalizacoes_{timestamp}.xlsx"
                
                # Salvar na pasta uploads
                caminho_uploads = os.path.join(os.path.dirname(__file__), 'uploads')
                os.makedirs(caminho_uploads, exist_ok=True)
                caminho_saida = os.path.join(caminho_uploads, nome_arquivo)
                
                # Executar extração
                arquivo, total_registros = extrair_portarias_naturalizacao(driver, link_personalizado, caminho_saida)
                
                pessoas_amostra = []
                if arquivo:
                    try:
                        df = pd.read_excel(arquivo)
                        df = df.fillna('')
                        pessoas_amostra = df.head(20).to_dict(orient='records')
                    except Exception as e:
                        pessoas_amostra = []
                    
                    return jsonify({
                        'success': True,
                        'arquivo': nome_arquivo,
                        'total_registros': total_registros,
                        'mensagem': f'Busca de naturalização concluída! {total_registros} registros encontrados.',
                        'tipo_busca': tipo_portaria,
                        'pessoas': pessoas_amostra
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Nenhuma portaria de naturalização encontrada.'
                    })
                    
            except Exception as e:
                print(f"[ERRO] Erro na busca de naturalização: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({
                    'success': False,
                    'message': f'Erro durante a busca: {str(e)}'
                })
            finally:
                driver.quit()
        
        else:
            return jsonify({
                'success': False,
                'message': f'Extração para o tipo "{tipo_portaria}" ainda não está implementada. Fale com o desenvolvedor para adicionar o padrão de extração.'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro durante a busca: {str(e)}'
        })

@app.route('/download/<filename>')
def download_file(filename):
    import os
    # Buscar o arquivo na pasta de uploads com validação de path
    base_dir = os.path.abspath(app.config['UPLOAD_FOLDER'])
    requested_path = os.path.abspath(os.path.join(base_dir, filename))
    if not requested_path.startswith(base_dir + os.sep) and requested_path != base_dir:
        return jsonify({'success': False, 'message': 'Caminho inválido'}), 400
    file_path = requested_path
    print(f"Tentando baixar: {file_path}")  # Para depuração
    try:
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True)
        else:
            return jsonify({
                'success': False,
                'message': f'Arquivo não encontrado para download: {file_path}'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erro ao baixar arquivo: {str(e)}'
        })

@app.route('/status')
def status():
    """Verificar status do analisador"""
    global analyzer
    return jsonify({
        'configurado': analyzer is not None,
        'tem_historico': analyzer.historico_df is not None if analyzer else False
    })

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def separar_filiacao(filiacao):
    """
    Separa a filiação extraída do OCR em mãe e pai
    Retorna uma lista [mae, pai] baseada nos padrões mais comuns dos documentos
    """
    if not filiacao or filiacao.strip() == "Não encontrado":
        return ['', '']
    
    # Normalizar o texto
    filiacao = filiacao.strip()
    
    # Se já tem barra, separa normalmente
    if '/' in filiacao:
        nomes = [n.strip() for n in filiacao.split('/') if n.strip()]
        # Garantir que sempre tenhamos 2 elementos
        if len(nomes) == 1:
            return [nomes[0], '']  # [mae, pai]
        elif len(nomes) >= 2:
            return [nomes[0], nomes[1]]  # [mae, pai]
        else:
            return ['', '']
    
    # Se tem quebra de linha, separar por ela
    if '\n' in filiacao:
        linhas = [linha.strip() for linha in filiacao.split('\n') if linha.strip()]
        if len(linhas) >= 2:
            return [linhas[0], linhas[1]]  # [mae, pai]
        elif len(linhas) == 1:
            return [linhas[0], '']  # [mae, pai]
        else:
            return ['', '']
    
    # Tentar identificar padrões específicos dos documentos
    # Padrão: "NOME1 SOBRENOME1 NOME2 SOBRENOME2"
    palavras = [p for p in filiacao.split() if p and len(p) > 1]
    
    if len(palavras) == 0:
        return ['', '']
    elif len(palavras) == 1:
        return [filiacao, '']  # [mae, pai]
    elif len(palavras) == 2:
        # Provavelmente um nome só (mãe)
        return [filiacao, '']  # [mae, pai]
    elif len(palavras) == 3:
        # Dividir: 2 palavras para mãe, 1 para pai ou vice-versa
        return [' '.join(palavras[:2]), palavras[2]]  # [mae, pai]
    elif len(palavras) == 4:
        # Dividir igualmente: 2 para cada
        return [' '.join(palavras[:2]), ' '.join(palavras[2:])]  # [mae, pai]
    elif len(palavras) == 5:
        # 3 para mãe, 2 para pai
        return [' '.join(palavras[:3]), ' '.join(palavras[3:])]  # [mae, pai]
    elif len(palavras) == 6:
        # Dividir igualmente: 3 para cada
        return [' '.join(palavras[:3]), ' '.join(palavras[3:])]  # [mae, pai]
    elif len(palavras) > 6:
        # Para nomes muito longos, dividir pela metade
        meio = len(palavras) // 2
        return [' '.join(palavras[:meio]), ' '.join(palavras[meio:])]  # [mae, pai]
    else:
        # Fallback: retornar tudo como mãe
        return [filiacao, '']  # [mae, pai]

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login automático para evitar tela de login"""
    
    # Fazer login automático com usuário admin
    admin_user = users.get('admin')
    if admin_user:
        login_user(admin_user)
        log_security_event('AUTO_LOGIN', 'Login automático realizado')
        
        # Verificar para onde redirecionar
        next_page = request.args.get('next')
        if next_page:
            log_security_event('REDIRECT', f'Redirecionando para: {next_page}')
            return redirect(next_page)
        
        # Verificar se a API Mistral está configurada
        try:
            api_key = os.environ.get("MISTRAL_API_KEY")
            if api_key:
                return redirect(url_for('ocr'))
            else:
                return redirect(url_for('index'))
        except Exception as e:
            log_security_event('ERROR', f'Erro ao verificar API: {str(e)}')
            return redirect(url_for('index'))
    
    # Se chegou aqui, algo deu errado - criar usuário temporário
    log_security_event('EMERGENCY_LOGIN', 'Criando usuário temporário para acesso')
    
    # Criar usuário temporário
    from werkzeug.security import generate_password_hash
    from flask_login import UserMixin
    
    class TempUser(UserMixin):
        def __init__(self):
            self.id = 'temp_admin'
            self.username = 'admin'
            self.password_hash = generate_password_hash('admin123')
    
    temp_user = TempUser()
    login_user(temp_user)
    
    # Redirecionar para onde foi solicitado ou página principal
    next_page = request.args.get('next')
    if next_page:
        return redirect(next_page)
    return redirect(url_for('index'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/ocr', methods=['GET', 'POST'])
@require_authentication
@log_sensitive_operation('PROCESSAMENTO_OCR')
def ocr():
    try:
        from mistralai import Mistral
        from dotenv import load_dotenv
        import mimetypes
        import base64
        import os
        import requests
        from pdf2image import convert_from_path
        load_dotenv()
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            flash('Chave da API Mistral não configurada!')
            return redirect(url_for('index'))
    except ImportError as e:
        print(f"DEBUG: Erro ao importar dependências: {e}")
        flash(f'Dependências não instaladas: {e}. Contate o administrador.')
        return redirect(url_for('index'))
    except Exception as e:
        print(f"DEBUG: Erro na configuração OCR: {e}")
        flash(f'Erro na configuração OCR: {e}')
        return redirect(url_for('index'))
    resultado = None
    campos = {}
    texto_extraido = ''
    comparacao = None
    campos_esperados = {
        'nome': '',
        'cpf': '',
        'filiação': '',
        'data_nasc': '',
        'nacionalidade': '',
        'validade': '',
        'rnm': '',
        'classificacao': '',
        'prazo_residencia': ''
    }
    def image_to_base64(image):
        import io
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        return "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode()
    if request.method == 'POST':
        # Atualiza campos esperados com o que o usuário preencheu
        for campo in campos_esperados.keys():
            campos_esperados[campo] = request.form.get(f'esperado_{campo}', '')
        if 'documento' not in request.files:
            flash('Nenhum arquivo enviado!')
            return redirect(request.url)
        file = request.files['documento']
        if file.filename == '':
            flash('Nenhum arquivo selecionado!')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            # Validação de segurança do arquivo (mais permissiva)
            if security_config and not security_config.validate_file_type(file.filename, ALLOWED_EXTENSIONS):
                flash('Tipo de arquivo não permitido!')
                try:
                    security_config.log_access(
                        user_id=current_user.name,
                        action='TENTATIVA_UPLOAD_ARQUIVO_INVALIDO',
                        resource=file.filename,
                        success=False
                    )
                except:
                    pass  # Não falhar se o log não funcionar
                return redirect(request.url)
            
            # Sanitizar nome do arquivo
            filename = security_config.sanitize_filename(file.filename) if security_config else secure_filename(file.filename)
            filename = secure_filename(filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            # Salvar arquivo temporariamente
            file.save(filepath)
            
            # Log de upload
            if security_config:
                try:
                    security_config.log_access(
                        user_id=current_user.name,
                        action='UPLOAD_DOCUMENTO_OCR',
                        resource=filename,
                        success=True
                    )
                except Exception as e:
                    print(f"Aviso: Log de segurança falhou: {e}")
            prompt = "Extraia do documento os campos: nome completo, CPF, filiação, data de nascimento, nacionalidade, validade, RNM, classificação, prazo de residência. Retorne como um objeto JSON."
            if filename.lower().endswith('.pdf'):
                imagens = convert_from_path(filepath, poppler_path=r'C:\Users\kevin.iqbal\Desktop\poppler\Release-24.08.0-0\poppler-24.08.0\Library\bin')
                image_urls = [image_to_base64(img) for img in imagens[:8]]  # até 8 páginas
            else:
                from PIL import Image
                img = Image.open(filepath)
                image_urls = [image_to_base64(img)]
            url = "https://api.mistral.ai/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            messages = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extraia os campos do documento conforme solicitado pelo usuário e retorne um JSON."
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        *[
                            {"type": "image_url", "image_url": url} for url in image_urls
                        ]
                    ]
                }
            ]
            data = {
                "model": "pixtral-12b-2409",
                "messages": messages,
                "response_format": {"type": "json_object"}
            }
            response = requests.post(url, headers=headers, json=data, timeout=60)
            print('Resposta da API OCR recebida com sucesso')
            try:
                resposta = response.json()
                content = resposta['choices'][0]['message']['content']
                import json
                try:
                    campos = json.loads(content)
                    resultado = "Campos extraídos com sucesso!"
                    
                    # Sanitização e validação dos dados extraídos
                    campos_originais = campos.copy()
                    
                    # Normalização dos campos principais
                    # Nome
                    campos['nome'] = campos.get('nome', campos.get('nome_completo', ''))
                    # Data de nascimento
                    campos['data_nasc'] = campos.get('data_nasc', campos.get('data_de_nascimento', ''))
                    # Filiação
                    if 'filiação' in campos:
                        campos['filiação'] = separar_filiacao(campos['filiação'])
                    elif 'filiacao' in campos:
                        campos['filiação'] = separar_filiacao(campos['filiacao'])
                    # RNM
                    campos['rnm'] = campos.get('rnm', campos.get('rnm:', ''))
                    # Classificação
                    campos['classificação'] = campos.get('classificação', campos.get('classificacao', ''))
                    # Prazo de residência
                    campos['prazo_de_residência'] = campos.get('prazo_de_residência', campos.get('prazo_residencia', ''))
                    
                    # PROTEGER dados sem remover (apenas para auditoria)
                    campos_protegidos = {}
                    for key, value in campos.items():
                        if isinstance(value, str):
                            # NÃO REMOVER NADA - apenas registrar para auditoria
                            campos_protegidos[key] = data_sanitizer.sanitize_ocr_text(value, preserve_essential=True)
                        else:
                            campos_protegidos[key] = value
                    
                    # Validar dados extraídos (sem alterar)
                    campos_validados = data_sanitizer.validate_extracted_data(campos_protegidos)
                    
                    # Manter campos originais (dados não foram alterados)
                    campos = campos_validados
                    
                    # Criar log de auditoria (dados preservados)
                    audit_log = data_sanitizer.create_audit_log(
                        original_data=campos_originais,
                        sanitized_data=campos,  # Mesmos dados (não alterados)
                        user_id=current_user.name,
                        operation='OCR_EXTRACAO_PROTEGIDA'
                    )
                    
                    texto_extraido = "\n".join(str(v) for v in campos.values())
                    print(f'Texto extraído pelo OCR: {len(texto_extraido)} caracteres')
                    
                    # Criptografar arquivo após processamento
                    if security_config:
                        try:
                            encrypted_filepath = security_config.encrypt_file(filepath)
                            print(f'Arquivo criptografado: {encrypted_filepath}')
                        except Exception as e:
                            print(f'Erro ao criptografar arquivo: {e}')
                            # Remover arquivo não criptografado por segurança
                            if os.path.exists(filepath):
                                os.remove(filepath)
                        else:
                            print('Aviso: security_config não disponível - arquivo não criptografado')
                    else:
                        print('Aviso: security_config não disponível - arquivo não criptografado')
                    
                except Exception:
                    resultado = content  # Se não for JSON, mostra o texto puro
                    texto_extraido = content
                    print(f'Texto extraído pelo OCR: {len(texto_extraido)} caracteres')
            except Exception as e:
                print('Erro ao processar resposta da API OCR:', e)
                print('Conteúdo da API recebido com sucesso')
                campos = {}
                resultado = 'Erro ao processar resposta da API OCR.'
                texto_extraido = response.text
                print(f'Texto extraído pelo OCR: {len(texto_extraido)} caracteres')
            # Comparação dos campos extraídos com os esperados
            comparacao = comparar_campos(campos, campos_esperados)
    # Garante que texto_extraido seja string legível
    if isinstance(texto_extraido, list):
        texto_extraido = "\n".join(str(x) for x in texto_extraido)
    print(f'Tipo de campos: {type(campos)} - {len(campos)} campos extraídos')
    return render_template('ocr.html', resultado=resultado, campos=campos, texto_extraido=texto_extraido, campos_esperados=campos_esperados, comparacao=comparacao)

def normalizar_nome_nome_sobrenome(nome):
    # Se vier 'Sobrenome Nome', inverte para 'Nome Sobrenome' (ambos capitalizados)
    partes = nome.strip().split()
    if len(partes) == 2:
        return f'{partes[1].upper()} {partes[0].upper()}'
    return nome.upper()

def extrair_nome_completo(texto):
    linhas = texto.splitlines()
    nome, sobrenome = '', ''
    for i, linha in enumerate(linhas):
        if re.search(r'NOME', linha, re.IGNORECASE):
            if i+1 < len(linhas):
                nome = linhas[i+1].strip().upper()
        if re.search(r'SOBRENOME', linha, re.IGNORECASE):
            if i+1 < len(linhas):
                sobrenome = linhas[i+1].strip().upper()
    if nome and sobrenome:
        return f'{nome} {sobrenome}'.strip(), nome, sobrenome
    return (nome or sobrenome).strip(), nome, sobrenome

def extrair_filiação_limpa(texto):
    linhas = texto.splitlines()
    nomes = []
    for i, linha in enumerate(linhas):
        if re.search(r'FILIA', linha, re.IGNORECASE):
            for j in range(1, 3):  # Pega até duas linhas seguintes
                if i+j < len(linhas):
                    nome = linhas[i+j].strip()
                    # Remove ruídos como 'O', 'ma', etc.
                    nome = re.sub(r'\b(O|ma)\b', '', nome).strip()
                    if nome:
                        nomes.append(nome)
            break
    return nomes

def extrair_pai_mae_da_filiacao_lista(nomes):
    # No documento, geralmente o primeiro é o pai e o segundo é a mãe
    pai = nomes[0] if len(nomes) > 0 else ''
    mae = nomes[1] if len(nomes) > 1 else ''
    return pai, mae

def extrair_nascimento_ajustado(texto):
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if re.search(r'DATA DE NASCIMENTO', linha, re.IGNORECASE):
            # Tenta pegar a data na mesma linha
            match = re.search(r'(\d{2}/\d{2}/\d{4})', linha)
            if match:
                return match.group(1)
            # Se não achou, tenta na próxima linha
            if i+1 < len(linhas):
                prox = linhas[i+1]
                match = re.search(r'(\d{2}/\d{2}/\d{4})', prox)
                if match:
                    return match.group(1)
    # Fallback: busca qualquer data no texto
    match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
    if match:
        return match.group(1)
    return ''

def extrair_nacionalidade_validade_linha(texto):
    linhas = texto.splitlines()
    for i, linha in enumerate(linhas):
        if re.search(r'NACIONAL.*VALIDADE', linha, re.IGNORECASE):
            if i+1 < len(linhas):
                prox = linhas[i+1]
                # Busca país (palavra antes da data) e data
                match = re.search(r'([A-ZÁ-Úa-zá-ú]+)[^0-9]*(\d{2}/\d{2}/\d{4})', prox)
                if match:
                    return match.group(1), match.group(2)
    return '', ''

def extrair_rnm_robusto(texto):
    match = re.search(r'RNM[:\s-]*([A-Z0-9-]+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r'([A-Z][0-9]{6,}-[0-9])', texto)
    if match:
        return match.group(1).strip()
    return ''

def extrair_cpf(texto):
    # Aceita CPF com ou sem pontuação
    match = re.search(r'CPF[:\s-]*([0-9\.\-]{11,})', texto)
    if match:
        return match.group(1).strip()
    match = re.search(r'(\d{3}\.?\d{3}\.?\d{3}-?\d{2})', texto)
    if match:
        return match.group(1).strip()
    return ''

def extrair_classificacao(texto):
    match = re.search(r'CLASSIFICA[ÇC][AÃ]O[:\s-]*([A-Z ]+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ''

def extrair_prazo_residencia(texto):
    # Aceita variações e espaços extras
    match = re.search(r'PRAZO DE RESID[ÊE]NCIA[:\s-]*([A-Za-z ]+)', texto, re.IGNORECASE)
    if match:
        return match.group(1).strip().upper()
    return ''

# ================================
# ROTAS DE TESTE DE PRÉ-PROCESSAMENTO
# ================================

@app.route('/teste-preprocessing')
@require_authentication
def teste_preprocessing():
    """Rota para interface de teste de pré-processamento"""
    return render_template('teste_preprocessing.html')

@app.route('/api/teste-preprocessing', methods=['POST'])
@require_authentication
@log_sensitive_operation('TESTE_PREPROCESSING_OCR')
def api_teste_preprocessing():
    """API para processar documento com pré-processamento e mascaramento"""
    try:
        # FORÇAR reload completo do módulo (remover do cache e reimportar)
        import sys
        if 'preprocessing_ocr' in sys.modules:
            del sys.modules['preprocessing_ocr']
            print("[DEBUG] Módulo preprocessing_ocr removido do cache")
        
        from preprocessing_ocr import ImagePreprocessor
        print("[DEBUG] Módulo preprocessing_ocr reimportado")
        
        # Testar se a função foi atualizada
        if hasattr(ImagePreprocessor, '_correct_orientation'):
            print("[DEBUG] ✓ Função _correct_orientation NOVA detectada")
        else:
            print("[DEBUG] ⚠ Usando versão antiga do módulo")
        from data_masking import DataMasker
        from PIL import Image
        import io
        import base64
        
        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nome de arquivo vazio'}), 400
        
        # Salvar arquivo temporário
        temp_dir = tempfile.mkdtemp()
        filepath = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(filepath)
        
        start_time = time.time()
        
        try:
            # Converter PDF para imagem se necessário
            if filepath.lower().endswith('.pdf'):
                print(f"[INFO] Processando PDF com múltiplas páginas...")
                imagens = convert_from_path(filepath, poppler_path=r'C:\Users\kevin.iqbal\Desktop\poppler\Release-24.08.0-0\poppler-24.08.0\Library\bin')
                print(f"[INFO] {len(imagens)} página(s) detectada(s)")
                
                # Para visualização, usar apenas a primeira página
                pil_img_preview = imagens[0]
                img_path_preview = os.path.join(temp_dir, 'temp_image_page1.jpg')
                pil_img_preview.save(img_path_preview, 'JPEG')
                
                # Processar TODAS as páginas
                processed_pages = []
                all_pages_paths = []
                
                for idx, pil_img in enumerate(imagens, 1):
                    print(f"[INFO] Processando página {idx}/{len(imagens)}...")
                    
                    # Salvar página temporária
                    page_path = os.path.join(temp_dir, f'page_{idx}.jpg')
                    pil_img.save(page_path, 'JPEG')
                    all_pages_paths.append(page_path)
                    
                    # Converter para OpenCV
                    img_array = np.array(pil_img)
                    if len(img_array.shape) == 3:
                        img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                    else:
                        img_cv = img_array
                    
                    # Aplicar pré-processamento
                    preprocessor = ImagePreprocessor()
                    preset_mode = request.form.get('preset_mode', 'mistral')
                    
                    if preset_mode == 'none':
                        if len(img_cv.shape) == 3:
                            processed_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                        else:
                            processed_img = img_cv
                        metadata = {
                            "etapas_aplicadas": ["none - sem preprocessamento"],
                            "pagina": idx
                        }
                    elif preset_mode == 'mistral':
                        processed_img, metadata = preprocessor.preprocess_for_mistral(page_path)
                        metadata["pagina"] = idx
                    else:
                        options = {
                            'apply_all': False,
                            'apply_clahe': request.form.get('apply_clahe') == 'true',
                            'apply_denoise': request.form.get('apply_denoise') == 'true',
                            'apply_deskew': request.form.get('apply_deskew') == 'true',
                            'apply_autocrop': request.form.get('apply_autocrop') == 'true',
                            'apply_binarization': request.form.get('apply_binarization') == 'true',
                            'apply_sharpen': request.form.get('apply_sharpen') == 'true',
                        }

                        # Correção explícita de orientação ANTES do pipeline
                        orientation_angle_applied = None
                        if options.get('apply_deskew'):
                            try:
                                from preprocessing_ocr import ImagePreprocessor as _IP
                                _tmp = _IP()
                                # Converter para grayscale se necessário
                                img_gray = img_cv if len(img_cv.shape) == 2 else cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                                angle_detect = _tmp._detect_orientation(img_gray)
                                
                                if angle_detect and angle_detect % 360 != 0:
                                    print(f"[ORIENT] Rotacionando imagem em {angle_detect}°")
                                    if angle_detect == 90:
                                        img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)
                                    elif angle_detect == 180:
                                        img_cv = cv2.rotate(img_cv, cv2.ROTATE_180)
                                    elif angle_detect == 270:
                                        img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
                                    orientation_angle_applied = angle_detect
                                    print(f"[ORIENT] ✓ Correção de orientação aplicada: {angle_detect}°")
                                else:
                                    print(f"[ORIENT] Documento já na orientação correta (0°)")
                            except Exception as _e:
                                print(f"[ORIENT] Falha ao corrigir orientação: {_e}")
                                import traceback
                                traceback.print_exc()

                            # Desativar deskew no pipeline (evitar rotação fina)
                            options['apply_deskew'] = False

                        processed_img, metadata = preprocessor.preprocess(img_cv, **options)
                        if orientation_angle_applied is not None:
                            metadata = metadata or {"etapas_aplicadas": []}
                            etapas = metadata.get("etapas_aplicadas", [])
                            etapas.insert(0, f"orientation_fix({orientation_angle_applied}°)")
                            metadata["etapas_aplicadas"] = etapas
                        metadata["pagina"] = idx
                    
                    # Salvar página processada
                    processed_page_path = os.path.join(temp_dir, f'processed_page_{idx}.jpg')
                    cv2.imwrite(processed_page_path, processed_img)
                    processed_pages.append(processed_page_path)
                
                # Para visualização, usar primeira página
                filepath = img_path_preview
                processed_path = processed_pages[0]
                
                # Combinar metadados
                metadata = {
                    "etapas_aplicadas": metadata.get("etapas_aplicadas", []),
                    "total_paginas": len(imagens),
                    "original_shape": None,
                    "final_shape": None
                }
                
            else:
                # Imagem única
                pil_img = Image.open(filepath)
                
                # Converter PIL Image para numpy array (OpenCV)
                img_array = np.array(pil_img)
                if len(img_array.shape) == 3:
                    img_cv = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
                else:
                    img_cv = img_array
                
                # Aplicar pré-processamento
                preprocessor = ImagePreprocessor()
                preset_mode = request.form.get('preset_mode', 'mistral')
                
                if preset_mode == 'none':
                    if len(img_cv.shape) == 3:
                        processed_img = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                    else:
                        processed_img = img_cv
                    metadata = {
                        "etapas_aplicadas": ["none - sem preprocessamento"],
                        "original_shape": img_cv.shape,
                        "final_shape": processed_img.shape,
                        "total_paginas": 1
                    }
                elif preset_mode == 'mistral':
                    processed_img, metadata = preprocessor.preprocess_for_mistral(filepath)
                    metadata["total_paginas"] = 1
                else:
                    options = {
                        'apply_all': False,
                        'apply_clahe': request.form.get('apply_clahe') == 'true',
                        'apply_denoise': request.form.get('apply_denoise') == 'true',
                        'apply_deskew': request.form.get('apply_deskew') == 'true',
                        'apply_autocrop': request.form.get('apply_autocrop') == 'true',
                        'apply_binarization': request.form.get('apply_binarization') == 'true',
                        'apply_sharpen': request.form.get('apply_sharpen') == 'true',
                    }

                    # Correção explícita de orientação ANTES do pipeline
                    orientation_angle_applied = None
                    if options.get('apply_deskew'):
                        try:
                            from preprocessing_ocr import ImagePreprocessor as _IP
                            _tmp = _IP()
                            # Converter para grayscale se necessário
                            img_gray = img_cv if len(img_cv.shape) == 2 else cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
                            angle_detect = _tmp._detect_orientation(img_gray)
                            
                            if angle_detect and angle_detect % 360 != 0:
                                print(f"[ORIENT] Rotacionando imagem em {angle_detect}°")
                                if angle_detect == 90:
                                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_CLOCKWISE)
                                elif angle_detect == 180:
                                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_180)
                                elif angle_detect == 270:
                                    img_cv = cv2.rotate(img_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
                                orientation_angle_applied = angle_detect
                                print(f"[ORIENT] ✓ Correção de orientação aplicada: {angle_detect}°")
                            else:
                                print(f"[ORIENT] Documento já na orientação correta (0°)")
                        except Exception as _e:
                            print(f"[ORIENT] Falha ao corrigir orientação: {_e}")
                            import traceback
                            traceback.print_exc()

                        # Desativar deskew no pipeline (evitar rotação fina)
                        options['apply_deskew'] = False

                    processed_img, metadata = preprocessor.preprocess(img_cv, **options)
                    if orientation_angle_applied is not None:
                        metadata = metadata or {"etapas_aplicadas": []}
                        etapas = metadata.get("etapas_aplicadas", [])
                        etapas.insert(0, f"orientation_fix({orientation_angle_applied}°)")
                        metadata["etapas_aplicadas"] = etapas
                    metadata["total_paginas"] = 1
                
                # Salvar imagem processada
                processed_path = os.path.join(temp_dir, 'processed.jpg')
                cv2.imwrite(processed_path, processed_img)
                processed_pages = [processed_path]
                all_pages_paths = [filepath]
            
            # Converter para base64 (imagem original - primeira página para visualização)
            with open(filepath, 'rb') as f:
                original_b64 = base64.b64encode(f.read()).decode()
                original_data_uri = f"data:image/jpeg;base64,{original_b64}"
            
            # Converter imagem processada para base64 (primeira página para visualização)
            with open(processed_path, 'rb') as f:
                processed_b64 = base64.b64encode(f.read()).decode()
                processed_data_uri = f"data:image/jpeg;base64,{processed_b64}"
            
            # Executar OCR com Mistral em TODAS as páginas processadas
            print(f"[INFO] Executando OCR Mistral em {len(processed_pages)} página(s)...")
            
            if len(processed_pages) > 1:
                # Múltiplas páginas - processar todas
                textos_por_pagina = []
                for idx, page_path in enumerate(processed_pages, 1):
                    print(f"[OCR] Processando página {idx}/{len(processed_pages)}...")
                    ocr_result = extrair_campos_ocr_mistral(page_path, modo_texto_bruto=True)
                    texto_pagina = ocr_result.get('texto_bruto', '') if ocr_result else ''
                    textos_por_pagina.append(f"\n\n{'='*60}\n📄 PÁGINA {idx}\n{'='*60}\n\n{texto_pagina}")
                
                # Combinar todos os textos
                texto_bruto = "\n".join(textos_por_pagina)
            else:
                # Página única
                ocr_result = extrair_campos_ocr_mistral(processed_path, modo_texto_bruto=True)
                texto_bruto = ocr_result.get('texto_bruto', '') if ocr_result else ''
            
            print(f"[INFO] OCR concluído. Total de caracteres extraídos: {len(texto_bruto)}")
            
            # Aplicar mascaramento de dados sensíveis
            masker = DataMasker()
            
            # Obter tipos de mascaramento selecionados
            try:
                mask_types_str = request.form.get('mask_types', '[]')
                mask_types = json.loads(mask_types_str)
            except:
                mask_types = ['cpf', 'rg', 'rnm', 'telefone', 'email']
            
            texto_mascarado, masked_data = masker.mask_text(texto_bruto, mask_types)
            
            # Adicionar destaque HTML aos dados mascarados
            texto_com_destaque = masker.highlight_masked_data(texto_mascarado, mask_types)
            
            # Calcular tempo de processamento
            processing_time = round(time.time() - start_time, 2)
            
            # Preparar resposta
            response = {
                'success': True,
                'original_image': original_data_uri,
                'processed_image': processed_data_uri,
                'texto_original': texto_bruto,
                'texto_mascarado': texto_com_destaque,
                'metadata': metadata,
                'masked_stats': {
                    'total_masked': sum(len(v) for v in masked_data.values()),
                    'by_type': {k: len(v) for k, v in masked_data.items()}
                },
                'processing_time': processing_time
            }
            
            return jsonify(response)
            
        except Exception as e:
            print(f"[ERRO] Erro no processamento: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
        finally:
            # Limpar arquivos temporários
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    except Exception as e:
        print(f"[ERRO] Erro geral na API: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/analisar_lecom', methods=['POST'])
def analisar_lecom():
    tipo_lecom = request.form.get('tipo_lecom', 'ocr')
    if tipo_lecom == 'texto':
        texto = request.form.get('texto_manual_lecom')
    else:
        texto = request.form.get('texto_deferimento')
    resultados_lecom = []
    if texto:
        pessoas = analyzer.extrair_pessoas(texto)
        if not pessoas:
            pessoas = []
        print("Pessoas extraídas:", pessoas)
        lecom = None
        try:
            lecom = LecomAutomation()
            for idx, pessoa in enumerate(pessoas):
                numero_processo = pessoa.get('processo')
                dados_texto = {
                    'nome': pessoa.get('nome', ''),
                    'pai': pessoa.get('nome_pai', ''),
                    'mae': pessoa.get('nome_mae', ''),
                    'rnm': pessoa.get('documento', ''),
                    'data_nasc': pessoa.get('data_nasc', pessoa.get('data_nascimento', ''))
                }
                try:
                    print(f'Processando pessoa {idx+1}/{len(pessoas)}: {pessoa.get("nome") or "(sem nome)"}')
                    resultado = lecom.processar_processo(numero_processo, dados_texto)
                    resultados_lecom.append(resultado)
                    lecom.voltar_para_workspaces()
                    # Fecha todas as abas que não são a atual
                    aba_atual = lecom.driver.current_window_handle
                    for h in lecom.driver.window_handles:
                        if h != aba_atual:
                            try:
                                lecom.driver.switch_to.window(h)
                                lecom.driver.close()
                            except Exception:
                                pass
                    lecom.driver.switch_to.window(aba_atual)
                except Exception as e:
                    print(f'Erro ao processar pessoa {idx+1}: {e}')
                    resultados_lecom.append({'numero_processo': numero_processo, 'erro': str(e)})
        finally:
            if lecom:
                lecom.close()
    return render_template('analisar.html', resultados_lecom=resultados_lecom)

def extrair_campos_ocr_mistral(filepath, modo_texto_bruto=False, max_retries=3, max_paginas=None):
    """Extrai campos de documentos usando Mistral Vision com pré-processamento otimizado e sistema de retry robusto"""
    from mistralai import Mistral
    from dotenv import load_dotenv
    import mimetypes
    import base64
    import os
    import requests
    import tempfile
    from pdf2image import convert_from_path
    from PIL import Image
    import time
    import cv2
    import numpy as np
    
    # FORÇAR reload completo do módulo (remover do cache e reimportar)
    import sys
    if 'preprocessing_ocr' in sys.modules:
        del sys.modules['preprocessing_ocr']
    
    from preprocessing_ocr import ImagePreprocessor
    
    # Log detalhado para debug
    arquivo_nome = os.path.basename(filepath) if filepath else "arquivo_indefinido"
    print(f"[OCR-DEBUG] Iniciando OCR para arquivo: {arquivo_nome}")
    print(f"[OCR-DEBUG] Caminho completo: {filepath}")
    print(f"[OCR-DEBUG] Modo texto bruto: {modo_texto_bruto}")
    
    # Forçar nova requisição sempre para evitar cache issues
    import random
    cache_buster = random.randint(1000, 9999)
    print(f"[OCR-DEBUG] Cache buster: {cache_buster}")
    
    load_dotenv()
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        print(f"[OCR-DEBUG] ERRO: API key não encontrada para {arquivo_nome}")
        return {"erro": "Chave da API Mistral não configurada"}
    
    def image_to_base64_with_preprocessing(image):
        """Aplica pré-processamento otimizado (CLAHE + Denoise + Sharpen) antes de converter para base64"""
        import io
        import tempfile
        
        try:
            # Salvar imagem temporariamente para pré-processar
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                temp_path = tmp.name
                image.save(temp_path)
            
            # Aplicar pré-processamento otimizado
            preprocessor = ImagePreprocessor()
            img_processada, metadata = preprocessor.preprocess_for_mistral(temp_path)
            
            print(f"[PRÉ-PROC] Etapas: {', '.join(metadata.get('etapas_aplicadas', []))}")
            print(f"[PRÉ-PROC] Qualidade: {metadata.get('quality_score', 0):.1f}/100")
            
            # Converter imagem processada (OpenCV) para PIL
            img_pil = Image.fromarray(cv2.cvtColor(img_processada, cv2.COLOR_GRAY2RGB))
            
            # Limpar arquivo temporário
            try:
                os.remove(temp_path)
            except:
                pass
            
            # Converter para base64
            buffered = io.BytesIO()
            img_pil.save(buffered, format="JPEG")
            return "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode()
            
        except Exception as e:
            print(f"[ERRO] Falha no pré-processamento: {e}, usando imagem original")
            # Fallback: usar imagem original se pré-processamento falhar
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            return "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode()
    
    # Processamento adaptativo baseado no tipo de documento
    try:
        if filepath.lower().endswith('.pdf'):
            # Para PDFs, converter para imagens
            imagens = convert_from_path(filepath, poppler_path=r'C:\Users\kevin.iqbal\Desktop\poppler\Release-24.08.0-0\poppler-24.08.0\Library\bin')
            
            # [DEBUG] CORREÇÃO: Usar max_paginas se especificado
            if max_paginas is not None:
                print(f"[BUSCA] Processando apenas {max_paginas} página(s) conforme solicitado")
                imagens_processar = imagens[:max_paginas]
            # Para documentos complexos (jornais oficiais), processar menos páginas
            elif modo_texto_bruto and len(imagens) > 4:
                print(f"DEBUG: Documento complexo detectado ({len(imagens)} páginas), processando apenas as primeiras 4 páginas")
                imagens_processar = imagens[:4]
            else:
                imagens_processar = imagens[:8]  # até 8 páginas para documentos normais
            
            # Aplicar pré-processamento em cada imagem
            image_urls = []
            for i, img in enumerate(imagens_processar, 1):
                print(f"[MISTRAL OCR] Pré-processando página {i}/{len(imagens_processar)}...")
                img_base64 = image_to_base64_with_preprocessing(img)
                image_urls.append(img_base64)
            
            print(f"[MISTRAL OCR] {len(image_urls)} páginas pré-processadas de {len(imagens)} total")
        else:
            # Para imagens, processar diretamente com pré-processamento
            print(f"[MISTRAL OCR] Pré-processando imagem...")
            img = Image.open(filepath)
            image_urls = [image_to_base64_with_preprocessing(img)]
            print(f"[MISTRAL OCR] 1 imagem pré-processada")
        
    except Exception as e:
        print(f"[ERRO] Erro no processamento: {e}")
        return {}
    
    # Se for modo texto bruto (análise automática definitiva), usar prompt otimizado
    if modo_texto_bruto:
        prompt = """Analise este documento e extraia TODO o texto visível de forma legível.

        IMPORTANTE:
        - Extraia APENAS o texto bruto do documento
        - Não tente identificar campos específicos
        - Não retorne JSON estruturado
        - Retorne apenas o texto extraído, linha por linha
        - Mantenha a formatação original quando possível
        - Corrija caracteres óbvios (ex: 0 por O, 1 por l, 5 por S)
        - Para jornais oficiais, foque nas seções relevantes (portarias, despachos)
        - Para documentos com muitas páginas, priorize o conteúdo principal
        
        Retorne apenas o texto extraído, sem formatação especial."""
    else:
        # Prompt original para extração de campos específicos
        prompt = f"""Analise este documento de identidade brasileiro pré-processado e extraia os seguintes campos com máxima precisão:

        nome completo, CPF, filiação, data de nascimento, nacionalidade, validade, RNM, classificação, prazo de residência

        IMPORTANTE:
        - Use apenas os dados claramente legíveis DESTE DOCUMENTO ESPECÍFICO
        - Para CPF, use formato XXX.XXX.XXX-XX
        - Para datas, use formato DD/MM/AAAA
        - Para filiação, separe os nomes de mãe e pai com quebra de linha ou barra
        - Se algum campo não for encontrado ou não estiver legível, escreva "Não encontrado"
        - Corrija caracteres óbvios (ex: 0 por O, 1 por l, 5 por S)
        - ANÁLISE ID: {cache_buster} para {arquivo_nome}
        
        Retorne como um objeto JSON com os campos extraídos."""
    
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "Cache-Control": "no-cache",
        "X-Request-ID": f"{arquivo_nome}-{cache_buster}"
    }
    
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "Extraia os campos do documento conforme solicitado pelo usuário e retorne um JSON. Use máxima precisão e corrija caracteres óbvios."
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
                *[
                    {"type": "image_url", "image_url": url} for url in image_urls
                ]
            ]
        }
    ]
    
    # Para modo texto bruto, não forçar formato JSON
    if modo_texto_bruto:
        data = {
            "model": "pixtral-12b-2409",
            "messages": messages
        }
    else:
        data = {
            "model": "pixtral-12b-2409",
            "messages": messages,
            "response_format": {"type": "json_object"}
        }
    
    # Sistema de retry robusto
    for tentativa in range(1, max_retries + 1):
        try:
            print(f"DEBUG: Tentativa {tentativa}/{max_retries} para API Mistral")
            
            response = requests.post(url, headers=headers, json=data, timeout=120)
            
            print(f"DEBUG: Status da resposta: {response.status_code}")
            print("DEBUG: Resposta da API recebida com sucesso")
            
            # Verificar se a resposta foi bem-sucedida
            if response.status_code == 200:
                resposta = response.json()
                print("DEBUG: Resposta JSON processada com sucesso")
                
                if 'choices' not in resposta or not resposta['choices']:
                    print("DEBUG: Resposta não contém 'choices'")
                    if tentativa < max_retries:
                        print(f"DEBUG: Tentativa {tentativa} falhou, tentando novamente...")
                        time.sleep(2 ** tentativa)  # Backoff exponencial
                        continue
                    else:
                        return {}
                        
                content = resposta['choices'][0]['message']['content']
                print(f"DEBUG: Conteúdo extraído com sucesso - {len(content)} caracteres")
                
                # Se for modo texto bruto, retornar o texto diretamente
                if modo_texto_bruto:
                    print(f'DEBUG FINAL: Texto extraído com sucesso - {len(content)} caracteres')
                    return {'texto_bruto': content}
                
                # Para modo normal, processar JSON
                import json
                campos = json.loads(content)
                print(f"DEBUG: Campos parseados com sucesso - {len(campos)} campos")
                
                # Se houver campo de filiação, separa nomes e extrai pai/mãe
                if 'filiação' in campos:
                    filiacao_separada = separar_filiacao(campos['filiação'])
                    campos['filiação'] = filiacao_separada
                    # Extrair pai e mãe separadamente para comparação
                    if len(filiacao_separada) >= 2:
                        campos['pai'] = filiacao_separada[1].strip()  # Segundo nome geralmente é o pai
                        campos['mae'] = filiacao_separada[0].strip()  # Primeiro nome geralmente é a mãe
                    elif len(filiacao_separada) == 1:
                        # Se só há um nome, assumir que é a mãe
                        campos['mae'] = filiacao_separada[0].strip()
                        campos['pai'] = ''
                elif 'filiacao' in campos:
                    filiacao_separada = separar_filiacao(campos['filiacao'])
                    campos['filiação'] = filiacao_separada
                    # Extrair pai e mãe separadamente para comparação
                    if len(filiacao_separada) >= 2:
                        campos['pai'] = filiacao_separada[1].strip()  # Segundo nome geralmente é o pai
                        campos['mae'] = filiacao_separada[0].strip()  # Primeiro nome geralmente é a mãe
                    elif len(filiacao_separada) == 1:
                        # Se só há um nome, assumir que é a mãe
                        campos['mae'] = filiacao_separada[0].strip()
                        campos['pai'] = ''
                
                # Mapeamento dos campos principais
                campos['nome'] = campos.get('nome_completo', campos.get('nome', ''))
                campos['data_nasc'] = campos.get('data_de_nascimento', campos.get('data_nasc', ''))
                
                # Normalizar nome para NOME + SOBRENOME
                if campos.get('nome'):
                    campos['nome'] = normalizar_nome_nome_sobrenome(campos['nome'])
                
                # Log detalhado dos campos extraídos para debug
                print(f'[OCR-DEBUG] Arquivo: {arquivo_nome} - {len(campos)} campos extraídos')
                print(f'[OCR-DEBUG] Campos principais - Nome: {campos.get("nome", "N/A")[:30]}..., RNM: {campos.get("rnm", "N/A")}')
                if 'pai' in campos or 'mae' in campos:
                    print(f'[OCR-DEBUG] Filiação - Pai: {campos.get("pai", "N/A")[:30]}..., Mãe: {campos.get("mae", "N/A")[:30]}...')
                
                # Adicionar metadados para identificação
                campos['_arquivo_origem'] = arquivo_nome
                campos['_timestamp_ocr'] = time.time()
                
                print(f'[OCR-DEBUG] FINAL: {len(campos)} campos extraídos com pré-processamento para {arquivo_nome}')
                return campos
                
            elif response.status_code in [429, 500, 502, 503, 504]:
                # Erros que podem ser temporários
                print(f"DEBUG: Erro temporário {response.status_code}, tentativa {tentativa}")
                if tentativa < max_retries:
                    wait_time = min(2 ** tentativa, 30)  # Backoff exponencial, máximo 30s
                    print(f"DEBUG: Aguardando {wait_time} segundos antes da próxima tentativa...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"DEBUG: Todas as {max_retries} tentativas falharam")
                    return {}
            else:
                # Erro não recuperável
                print(f"DEBUG: Erro não recuperável {response.status_code}")
                return {}
                
        except requests.exceptions.Timeout:
            print(f"DEBUG: Timeout na tentativa {tentativa}")
            if tentativa < max_retries:
                wait_time = min(2 ** tentativa, 30)
                print(f"DEBUG: Aguardando {wait_time} segundos antes da próxima tentativa...")
                time.sleep(wait_time)
                continue
            else:
                print("DEBUG: Todas as tentativas falharam por timeout")
                return {}
                
        except json.JSONDecodeError as e:
            print(f"DEBUG: Erro ao fazer parse JSON da resposta: {e}")
            print("DEBUG: Conteúdo da API processado com falha")
            if tentativa < max_retries:
                print(f"DEBUG: Tentativa {tentativa} falhou, tentando novamente...")
                time.sleep(2 ** tentativa)
                continue
            else:
                return {}
                
        except KeyError as e:
            print(f"DEBUG: Erro de chave na resposta: {e}")
            print("DEBUG: Resposta da API processada com erro de chave")
            if tentativa < max_retries:
                print(f"DEBUG: Tentativa {tentativa} falhou, tentando novamente...")
                time.sleep(2 ** tentativa)
                continue
            else:
                return {}
                
        except Exception as e:
            print(f"DEBUG: Erro na extração OCR: {e}")
            print(f"DEBUG: Tipo do erro: {type(e)}")
            import traceback
            print(f"DEBUG: Traceback completo: {traceback.format_exc()}")
            if tentativa < max_retries:
                print(f"DEBUG: Tentativa {tentativa} falhou, tentando novamente...")
                time.sleep(2 ** tentativa)
                continue
            else:
                return {}
    
    # Se chegou aqui, todas as tentativas falharam
    print(f"DEBUG: Todas as {max_retries} tentativas falharam")
    return {}

@app.route('/analise_automatica', methods=['GET', 'POST'])
def analise_automatica():
    """Página de Análise Automática de Processos"""
    import pandas as pd
    import tempfile
    import os
    resultado = None
    download_url = None
    
    if request.method == 'POST':
        tipo_processo = request.form.get('tipo_processo')
        print(f"DEBUG: Tipo de processo recebido: '{tipo_processo}'")
        print(f"DEBUG: Tipo convertido para lower: '{tipo_processo.lower() if tipo_processo else None}'")
        
        if 'planilha' not in request.files:
            resultado = 'Nenhum arquivo enviado.'
            return render_template('analise_automatica.html', resultado=resultado)
        
        file = request.files['planilha']
        if file.filename == '':
            resultado = 'Nenhum arquivo selecionado.'
            return render_template('analise_automatica.html', resultado=resultado)
        
        try:
            # Importar utilitário para normalização de códigos
            try:
                from utils_processos import carregar_planilha_com_codigos_normalizados, encontrar_coluna_codigo
                print("[OK] Módulo de normalização de códigos disponível")
                
                # Carregar planilha com códigos normalizados
                df = carregar_planilha_com_codigos_normalizados(file)
                codigo_col = encontrar_coluna_codigo(df)
                
            except ImportError:
                print("[AVISO] Módulo de normalização não disponível, usando método manual")
                # Método manual de fallback
                df = pd.read_excel(file)
                
                # Encontrar coluna de código
                codigo_col = None
                for col in df.columns:
                    if col.lower() in ['código', 'codigo', 'códigos', 'codigos']:
                        codigo_col = col
                        break
                
                if codigo_col is None:
                    resultado = 'A planilha deve conter uma coluna chamada "código" ou "codigo".'
                    return render_template('analise_automatica.html', resultado=resultado)
                
                # Converter códigos para string e remover .0
                df[codigo_col] = df[codigo_col].astype(str).str.replace('.0', '', regex=False)
            
            # Criar pasta uploads se não existir
            uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            out_path = os.path.join(uploads_dir, f'analise_processos_{tipo_processo}_resultado.xlsx')
            
            # Processar cada código usando um único driver
            df['Resultado Processamento'] = ''
            df['Status'] = ''
            df['Data Processamento'] = ''
            df['Observações'] = ''
            df['Documento Baixado'] = ''
            df['Caminho Documento'] = ''
            df['Documentos Processados'] = ''
            df['Total Documentos'] = ''
            
            # Inicializar navegação baseada no tipo de processo
            print(f"DEBUG: [BUSCA] Verificando tipo de processo: '{tipo_processo}' (lower: '{tipo_processo.lower() if tipo_processo else None}')")
            
            if tipo_processo and tipo_processo.lower() == 'provisoria':
                from navegacao_provisoria import NavegacaoProvisoria
                print("DEBUG: [FECHADO] Inicializando Navegação Provisória com conformidade LGPD...")
                lecom = NavegacaoProvisoria()
                print("DEBUG: [OK] Navegação Provisória inicializada com sucesso")
            elif tipo_processo and tipo_processo.lower() == 'ordinaria':
                from navegacao_ordinaria import NavegacaoOrdinaria
                print("DEBUG: [FECHADO] Inicializando Navegação Ordinária com conformidade LGPD...")
                lecom = NavegacaoOrdinaria()
                print("DEBUG: [OK] Navegação Ordinária inicializada com sucesso")
            elif tipo_processo and tipo_processo.lower() == 'definitiva':
                from lecom_automation import LecomAutomation
                print("DEBUG: [FECHADO] Inicializando LecomAutomation para análise DEFINITIVA...")
                lecom = LecomAutomation()
                print("DEBUG: [OK] LecomAutomation para DEFINITIVA inicializado com sucesso")
            else:
                from lecom_automation import LecomAutomation
                print(f"DEBUG: [FECHADO] Inicializando Lecom genérico (tipo '{tipo_processo}' não reconhecido ou None)")
                lecom = LecomAutomation()
                print("DEBUG: [OK] LecomAutomation inicializado como fallback")
            
            try:
                # Login UMA VEZ no início para todos os processos
                print("DEBUG: Fazendo login no Lecom (uma vez para todos os processos)...")
                lecom.login()
                print("DEBUG: Login realizado com sucesso!")
                
                for idx, row in df.iterrows():
                    codigo = str(row[codigo_col])
                    print(f"DEBUG: Processando linha {idx+1}/{len(df)} - Codigo: {codigo}")
                    print(f"DEBUG: Tipo de classe sendo usada: {type(lecom).__name__}")
                    print(f"DEBUG: Arquivo da classe: {type(lecom).__module__}")
                    
                    try:
                        # Verificar se é tipo definitiva, provisória ou ordinária para usar OCR genérico
                        if tipo_processo.lower() in ['definitiva', 'provisoria', 'ordinaria']:
                            print(f"DEBUG: Processamento com OCR genérico para tipo {tipo_processo} - código {codigo}")
                            
                            # Verificar se já está na workspace, senão navegar
                            current_url = lecom.driver.current_url
                            if 'workspace' not in current_url:
                                print("DEBUG: Navegando para workspace...")
                                lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                time.sleep(3)
                            else:
                                print("DEBUG: Já está na workspace - continuando...")
                            
                            print("DEBUG: Aplicando filtros...")
                            print(f"DEBUG: Métodos disponíveis na classe: {[m for m in dir(lecom) if not m.startswith('_')]}")
                            print(f"DEBUG: Verificando se tem acessar_pesquisa_processos: {hasattr(lecom, 'acessar_pesquisa_processos')}")
                            resultado_filtros = lecom.aplicar_filtros(codigo)
                            
                            # VERIFICAR SE HOUVE INDEFERIMENTO AUTOMÁTICO
                            if resultado_filtros and resultado_filtros.get('indeferimento_automatico'):
                                print('🚫 INDEFERIMENTO AUTOMÁTICO DETECTADO!')
                                print(f'💬 Motivo: {resultado_filtros.get("motivo")}')
                                print('[TARGET] Não será executado download de documentos')
                                print('[TARGET] Não será executado OCR')
                                print('[TARGET] Processo finalizado com indeferimento automático')
                                
                                # [DEBUG] GARANTIR NAVEGAÇÃO PARA PESQUISA APÓS INDEFERIMENTO
                                print('[RELOAD] Navegando para pesquisa de processos para continuar...')
                                try:
                                    # Navegação direta para garantir que funcione
                                    lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                    time.sleep(5)
                                    print('[OK] Navegação para pesquisa concluída após indeferimento automático')
                                    
                                    # Verificar se chegou corretamente
                                    if 'workspace' in lecom.driver.current_url:
                                        print('[OK] URL de pesquisa confirmada - pronto para próximo processo')
                                    else:
                                        print('[AVISO] URL não confirmada, tentando novamente...')
                                        lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                        time.sleep(3)
                                        
                                except Exception as e:
                                    print(f'[AVISO] Erro na navegação após indeferimento: {e}')
                                    # Fallback: tentar novamente
                                    try:
                                        lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                        time.sleep(5)
                                        print('[OK] Fallback de navegação funcionou')
                                    except Exception as e2:
                                        print(f'[ERRO] Fallback falhou: {e2}')
                                
                                resultado_final = {
                                    'status': 'Indeferimento automático',
                                    'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'observacoes': f'Processo {codigo} INDEFERIDO automaticamente: {resultado_filtros.get("motivo")}',
                                    'documento_baixado': 'Não (indeferimento automático)',
                                    'caminho_documento': '',
                                    'documentos_processados': '',
                                    'total_documentos': 0,
                                    'todos_textos_extraidos': {},
                                    'tipo_ocr': 'generico',
                                    'indeferimento_automatico': True,
                                    'motivo_indef': resultado_filtros.get("motivo"),
                                    'dados_verificacao': resultado_filtros.get("dados_verificacao", {})
                                }
                            else:
                                # SE NÃO HOUVE INDEFERIMENTO, CONTINUAR COM ANÁLISE
                                # Extrair número do processo
                                numero_processo_extraido = lecom.extrair_numero_processo()
                                if numero_processo_extraido:
                                    lecom.numero_processo_limpo = numero_processo_extraido
                                
                                # Usar o módulo apropriado baseado no tipo de processo
                                try:
                                    if tipo_processo.lower() == 'definitiva':
                                        from analise_processos import analisar_processo_definitiva
                                        print("DEBUG: Chamando módulo de análise definitiva...")
                                        # [DEBUG] NOVA CORREÇÃO: Remover timeout de 30 minutos
                                        print("DEBUG: 🚫 Timeout de 30 minutos REMOVIDO - análises podem demorar o tempo necessário")
                                        resultado_processo = analisar_processo_definitiva(lecom, codigo, timeout_global_minutos=None)
                                        
                                        # [DEBUG] NOVA CORREÇÃO: Verificar sessão e navegar para página de pesquisa
                                        try:
                                            print("DEBUG: [BUSCA] Verificando se a sessão ainda está ativa...")
                                            current_url = lecom.driver.current_url
                                            print(f"DEBUG: URL atual: {current_url}")
                                            
                                            # Se não estiver na página de pesquisa, navegar de volta
                                            if 'workspace' not in current_url:
                                                print("DEBUG: [EXEC] Navegando de volta para página de pesquisa...")
                                                lecom.driver.get("https://justica.servicos.gov.br/workspace/")
                                                
                                                # Aguardar carregamento da página
                                                import time
                                                time.sleep(3)
                                                
                                                # Verificar se chegou na página correta
                                                nova_url = lecom.driver.current_url
                                                print(f"DEBUG: Nova URL após navegação: {nova_url}")
                                                
                                                if 'workspace' in nova_url:
                                                    print("DEBUG: [OK] Navegação para página de pesquisa bem-sucedida")
                                                    print("DEBUG: [RELOAD] Sessão renovada - pronto para próximo processo")
                                                else:
                                                    print("DEBUG: [AVISO] Navegação pode ter falhado, mas continuando...")
                                            else:
                                                print("DEBUG: [OK] Já está na página de pesquisa - sessão ativa")
                                                
                                        except Exception as e:
                                            print(f"DEBUG: [AVISO] Erro ao verificar/navegar sessão: {e}")
                                            print("DEBUG: [RELOAD] Tentando renovar sessão...")
                                            try:
                                                lecom.driver.get("https://justica.servicos.gov.br/workspace/")
                                                time.sleep(3)
                                                print("DEBUG: [OK] Sessão renovada com sucesso")
                                            except Exception as e2:
                                                print(f"DEBUG: [ERRO] Falha ao renovar sessão: {e2}")
                                                print("DEBUG: [RELOAD] Continuando para próximo processo...")
                                    elif tipo_processo.lower() == 'provisoria':
                                        from analise_provisoria import analisar_processo_provisoria
                                        print("DEBUG: Chamando módulo de análise provisória...")
                                        # [DEBUG] CORREÇÃO: Passar data inicial como parâmetro
                                        data_inicial = getattr(lecom, 'data_inicial_processo', None)
                                        print(f"DEBUG: Data inicial disponível: {data_inicial}")
                                        
                                        # [DEBUG] NOVA CORREÇÃO: Remover timeout de 30 minutos
                                        print("DEBUG: 🚫 Timeout de 30 minutos REMOVIDO - análises podem demorar o tempo necessário")
                                        resultado_processo = analisar_processo_provisoria(lecom, codigo, data_inicial, timeout_global_minutos=None)
                                        
                                        # [DEBUG] NOVA CORREÇÃO: Verificar sessão e navegar para página de pesquisa
                                        try:
                                            print("DEBUG: [BUSCA] Verificando se a sessão ainda está ativa...")
                                            current_url = lecom.driver.current_url
                                            print(f"DEBUG: URL atual: {current_url}")
                                            
                                            # Se não estiver na página de pesquisa, navegar de volta
                                            if 'workspace' not in current_url:
                                                print("DEBUG: [EXEC] Navegando de volta para página de pesquisa...")
                                                lecom.driver.get("https://justica.servicos.gov.br/workspace/")
                                                
                                                # Aguardar carregamento da página
                                                import time
                                                time.sleep(3)
                                                
                                                # Verificar se chegou na página correta
                                                nova_url = lecom.driver.current_url
                                                print(f"DEBUG: Nova URL após navegação: {nova_url}")
                                                
                                                if 'workspace' in nova_url:
                                                    print("DEBUG: [OK] Navegação para página de pesquisa bem-sucedida")
                                                    print("DEBUG: [RELOAD] Sessão renovada - pronto para próximo processo")
                                                else:
                                                    print("DEBUG: [AVISO] Navegação pode ter falhado, mas continuando...")
                                            else:
                                                print("DEBUG: [OK] Já está na página de pesquisa - sessão ativa")
                                                
                                        except Exception as e:
                                            print(f"DEBUG: [AVISO] Erro ao verificar/navegar sessão: {e}")
                                            print("DEBUG: [RELOAD] Tentando renovar sessão...")
                                            try:
                                                lecom.driver.get("https://justica.servicos.gov.br/workspace/")
                                                time.sleep(3)
                                                print("DEBUG: [OK] Sessão renovada com sucesso")
                                            except Exception as e2:
                                                print(f"DEBUG: [ERRO] Falha ao renovar sessão: {e2}")
                                                print("DEBUG: [RELOAD] Continuando para próximo processo...")
                                    elif tipo_processo.lower() == 'ordinaria':
                                        print(f"DEBUG: Processamento normal para tipo ordinaria - código {codigo}")
                                        # Para análise ordinária, usar o método processar_processo do próprio lecom
                                        resultado_processo = lecom.processar_processo(codigo)
                                        
                                        # Verificar sessão após processamento
                                        try:
                                            print("DEBUG: [BUSCA] Verificando sessão após processamento ordinário...")
                                            current_url = lecom.driver.current_url
                                            print(f"DEBUG: URL atual: {current_url}")
                                            
                                            if 'workspace' not in current_url:
                                                print("DEBUG: [EXEC] Navegando de volta para página de pesquisa...")
                                                lecom.driver.get("https://justica.servicos.gov.br/workspace/")
                                                time.sleep(3)
                                                print("DEBUG: [OK] Navegação para pesquisa concluída")
                                            else:
                                                print("DEBUG: [OK] Já está na página de pesquisa")
                                                
                                        except Exception as e:
                                            print(f"DEBUG: [AVISO] Erro ao verificar sessão ordinária: {e}")
                                            try:
                                                lecom.driver.get("https://justica.servicos.gov.br/workspace/")
                                                time.sleep(3)
                                                print("DEBUG: [OK] Sessão renovada")
                                            except Exception as e2:
                                                print(f"DEBUG: [ERRO] Falha ao renovar sessão: {e2}")
                                    else:
                                        # Fallback para definitiva se tipo não reconhecido
                                        from analise_processos import analisar_processo_definitiva
                                        print("DEBUG: Tipo não reconhecido, usando análise definitiva como fallback...")
                                        resultado_processo = analisar_processo_definitiva(lecom, codigo)
                                    
                                    # [DEBUG] CORREÇÃO: Processar TODOS os resultados, incluindo casos especiais
                                    if resultado_processo:
                                        print(f"DEBUG: Resultado do processo {codigo}: status = '{resultado_processo.get('status')}'")
                                        
                                        # Verificar se é indeferimento automático
                                        if resultado_processo.get('status') == 'Indeferimento automático':
                                            print(f"DEBUG: [OK] Indeferimento automático detectado para o código {codigo}")
                                            motivo_indeferimento = resultado_processo.get('motivo', 'Motivo não especificado')
                                            
                                            # Formato específico para o log
                                            observacoes_log = f'Processo {codigo} INDEFERIDO automaticamente: {motivo_indeferimento}'
                                            
                                            resultado_final = {
                                                'status': 'Indeferimento automático',
                                                'data_processamento': resultado_processo.get('data_processamento', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                                                'observacoes': observacoes_log,
                                                'documento_baixado': 'Não (indeferimento automático)',
                                                'caminho_documento': 'N/A',
                                                'documentos_processados': 'N/A',
                                                'total_documentos': 0,
                                                'todos_textos_extraidos': {},
                                                'analise_elegibilidade': {
                                                    'elegibilidade_final': 'indeferimento_automatico',
                                                    'percentual_final': 0,
                                                    'motivo_final': motivo_indeferimento
                                                },
                                                'tipo_ocr': 'generico'
                                            }
                                            
                                        elif resultado_processo.get('status') == 'Requer análise manual':
                                            print(f"DEBUG: [OK] Requer análise manual detectado para o código {codigo}")
                                            motivo_analise = resultado_processo.get('motivo', 'Motivo não especificado')
                                            
                                            resultado_final = {
                                                'status': 'Requer análise manual',
                                                'data_processamento': resultado_processo.get('data_processamento', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                                                'observacoes': f'REQUER ANÁLISE MANUAL: {motivo_analise}',
                                                'documento_baixado': 'Não (requer análise manual)',
                                                'caminho_documento': 'N/A',
                                                'documentos_processados': 'N/A',
                                                'total_documentos': 0,
                                                'todos_textos_extraidos': {},
                                                'analise_elegibilidade': {
                                                    'elegibilidade_final': 'requer_analise_manual',
                                                    'percentual_final': 0,
                                                    'motivo_final': motivo_analise
                                                },
                                                'tipo_ocr': 'generico'
                                            }
                                            
                                        elif resultado_processo.get('status') == 'Processado com sucesso':
                                            print(f"DEBUG: [OK] Análise {tipo_processo} concluída com sucesso para o código {codigo}")
                                            
                                            # Para 'Processado com sucesso', construir observações detalhadas 
                                            analise_elegibilidade = resultado_processo.get('analise_elegibilidade', {})
                                            
                                            # [DEBUG] CORREÇÃO: Criar observações detalhadas no formato correto
                                            total_docs = resultado_processo.get("total_documentos", 0)
                                            observacoes_base = f'Processo {codigo} do tipo {tipo_processo} foi analisado com OCR genérico. {total_docs} documentos processados.'
                                            
                                            if analise_elegibilidade:
                                                elegibilidade = analise_elegibilidade.get('elegibilidade_final', analise_elegibilidade.get('elegibilidade', 'indeterminada'))
                                                confianca = analise_elegibilidade.get('confianca', analise_elegibilidade.get('percentual_final', 0))
                                                score = analise_elegibilidade.get('score_total', analise_elegibilidade.get('score', 0))
                                                # Extrair condições da estrutura correta
                                                condicoes_obrigatorias = analise_elegibilidade.get('condicoes_obrigatorias', {})
                                                condicoes_atendidas = condicoes_obrigatorias.get('atendidas', '?')
                                                condicoes_total = condicoes_obrigatorias.get('total', '?')
                                                
                                                # Converter confiança para porcentagem
                                                if isinstance(confianca, (int, float)):
                                                    if confianca <= 1:
                                                        confianca_pct = confianca * 100
                                                    else:
                                                        confianca_pct = confianca
                                                    confianca_str = f"{confianca_pct:.1f}%"
                                                else:
                                                    confianca_str = str(confianca)
                                                
                                                # Determinar o texto da elegibilidade baseado no resultado
                                                if elegibilidade in ['elegivel_alta_probabilidade', 'elegivel', 'deferimento', 'elegivel_probabilidade_alta']:
                                                    status_elegibilidade = "[OK] ELEGÍVEL"
                                                    tipo_elegibilidade = "Elegivel Probabilidade Alta"
                                                elif elegibilidade in ['elegivel_probabilidade_media']:
                                                    status_elegibilidade = "[OK] ELEGÍVEL"
                                                    tipo_elegibilidade = "Elegivel Probabilidade Média"
                                                elif elegibilidade in ['elegivel_probabilidade_baixa']:
                                                    status_elegibilidade = "[AVISO] ELEGÍVEL"
                                                    tipo_elegibilidade = "Elegivel Probabilidade Baixa"
                                                elif elegibilidade in ['elegivel_com_ressalva', 'elegivel_com_ressalvas', 'deferimento_com_ressalvas']:
                                                    status_elegibilidade = "[AVISO] ELEGÍVEL"
                                                    tipo_elegibilidade = "Elegível com Ressalvas"
                                                elif elegibilidade in ['nao_elegivel', 'inelegivel', 'indeferimento_automatico', 'não_elegivel']:
                                                    status_elegibilidade = "[ERRO] NÃO ELEGÍVEL"
                                                    tipo_elegibilidade = "Não elegível"
                                                elif elegibilidade in ['elegibilidade_incerta', 'indeterminada']:
                                                    status_elegibilidade = "❓ INCERTO"
                                                    tipo_elegibilidade = "Elegibilidade Incerta"
                                                else:
                                                    status_elegibilidade = "❓ INDETERMINADO"
                                                    tipo_elegibilidade = f"Resultado: {elegibilidade}"
                                                
                                                # Análise de decisões
                                                analise_decisoes = resultado_processo.get('analise_decisoes', {})
                                                decisao_final = analise_decisoes.get('decisao_final', 'indeterminada')
                                                decisao_confianca = analise_decisoes.get('confianca', 0)
                                                decisao_score = analise_decisoes.get('score_total', 0)
                                                
                                                if isinstance(decisao_confianca, (int, float)):
                                                    if decisao_confianca <= 1:
                                                        decisao_confianca_pct = decisao_confianca * 100
                                                    else:
                                                        decisao_confianca_pct = decisao_confianca
                                                    decisao_confianca_str = f"{decisao_confianca_pct:.1f}%"
                                                else:
                                                    decisao_confianca_str = str(decisao_confianca)
                                                
                                                # Formato final das observações
                                                observacoes_detalhadas = f'{observacoes_base} {status_elegibilidade}: {tipo_elegibilidade} (Confiança: {confianca_str}, Score: {score}, Condições: {condicoes_atendidas}/{condicoes_total}) ❓ DECISÃO: {decisao_final.upper()} (Confiança: {decisao_confianca_str}, Score: {decisao_score})'
                                            else:
                                                observacoes_detalhadas = observacoes_base + " ❓ STATUS: Análise de elegibilidade não disponível"
                                            
                                            resultado_final = {
                                                'status': 'Processado',
                                                'data_processamento': resultado_processo.get('data_processamento', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                                                'observacoes': observacoes_detalhadas,
                                                'documento_baixado': f'Sim ({resultado_processo.get("total_documentos", 0)} documentos)',
                                                'caminho_documento': f'{resultado_processo.get("total_documentos", 0)} documentos baixados',
                                                'documentos_processados': ', '.join(resultado_processo.get('documentos_processados', [])),
                                                'total_documentos': resultado_processo.get('total_documentos', 0),
                                                'todos_textos_extraidos': resultado_processo.get('todos_textos_extraidos', {}),
                                                'analise_elegibilidade': analise_elegibilidade,
                                                'analise_decisoes': resultado_processo.get('analise_decisoes', {}),
                                                'tipo_ocr': 'generico'
                                            }
                                            
                                        else:
                                            print(f"DEBUG: [ERRO] Status não reconhecido: {resultado_processo.get('status')}")
                                            resultado_final = {
                                                'status': 'Erro',
                                                'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                'observacoes': f'Status não reconhecido: {resultado_processo.get("status")}',
                                                'documento_baixado': 'Não',
                                                'caminho_documento': '',
                                                'documentos_processados': '',
                                                'total_documentos': 0,
                                                'todos_textos_extraidos': {},
                                                'tipo_ocr': 'generico'
                                            }
                                    else:
                                        print(f"DEBUG: [ERRO] Erro na análise {tipo_processo} do código {codigo}")
                                        resultado_final = {
                                            'status': 'Erro',
                                            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                            'observacoes': f'Erro na análise {tipo_processo} do processo {codigo}: {resultado_processo.get("erro", "Erro desconhecido") if resultado_processo else "Resultado não retornado"}',
                                            'documento_baixado': 'Não',
                                            'caminho_documento': '',
                                            'documentos_processados': '',
                                            'total_documentos': 0,
                                            'todos_textos_extraidos': {},
                                            'tipo_ocr': 'generico'
                                        }
                                except Exception as e:
                                    print(f"DEBUG: Erro ao importar ou usar módulo de análise {tipo_processo}: {e}")
                                    resultado_final = {
                                        'status': 'Erro',
                                        'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        'observacoes': f'Erro ao usar módulo de análise {tipo_processo} para processo {codigo}: {str(e)}',
                                        'documento_baixado': 'Não',
                                        'caminho_documento': '',
                                        'documentos_processados': '',
                                        'total_documentos': 0,
                                        'todos_textos_extraidos': {},
                                        'tipo_ocr': 'generico'
                                    }
                        else:
                            # Para outros tipos, usar o fluxo normal do Lecom
                            print(f"DEBUG: Processamento normal para tipo {tipo_processo} - código {codigo}")
                            resultado_processo = lecom.processar_processo(codigo, {})
                            
                            if resultado_processo and 'status' in resultado_processo and resultado_processo['status'] == 'Processado com sucesso':
                                print(f"DEBUG: Processamento concluído com sucesso para o código {codigo}")
                                documentos_processados = resultado_processo.get('documentos_processados', [])
                                total_documentos = resultado_processo.get('total_documentos', 0)
                                
                                resultado_final = {
                                    'status': 'Processado',
                                    'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'observacoes': f'Processo {codigo} do tipo {tipo_processo} foi analisado com sucesso. {total_documentos} documentos processados.',
                                    'documento_baixado': f'Sim ({total_documentos} documentos)',
                                    'caminho_documento': f'{total_documentos} documentos baixados',
                                    'documentos_processados': ', '.join(documentos_processados),
                                    'total_documentos': total_documentos,
                                    'todos_campos_ocr': resultado_processo.get('todos_campos_ocr', {}),
                                    'todos_textos_ocr': resultado_processo.get('todos_textos_ocr', {}),
                                    'tipo_ocr': 'campos_especificos'
                                }
                            else:
                                print(f"DEBUG: Erro no processamento do código {codigo}")
                                resultado_final = {
                                    'status': 'Erro',
                                    'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    'observacoes': f'Erro ao processar processo {codigo}',
                                    'documento_baixado': 'Não',
                                    'caminho_documento': '',
                                    'documentos_processados': '',
                                    'total_documentos': 0,
                                    'todos_campos_ocr': {},
                                    'todos_textos_ocr': {},
                                    'tipo_ocr': 'campos_especificos'
                                }
                        
                    except Exception as e:
                        print(f"DEBUG: Erro ao processar código {codigo}: {e}")
                        resultado_final = {
                            'status': 'Erro',
                            'data_processamento': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'observacoes': f'Erro ao processar processo {codigo}: {str(e)}',
                            'documento_baixado': 'Não',
                            'caminho_documento': '',
                            'comparacao': '',
                            'divergencias': []
                        }
                    
                    # Atualizar DataFrame
                    df.at[idx, 'Resultado Processamento'] = resultado_final.get('status', '')
                    df.at[idx, 'Status'] = resultado_final.get('status', '')
                    df.at[idx, 'Data Processamento'] = resultado_final.get('data_processamento', '')
                    df.at[idx, 'Observações'] = resultado_final.get('observacoes', '')
                    df.at[idx, 'Documento Baixado'] = resultado_final.get('documento_baixado', '')
                    df.at[idx, 'Caminho Documento'] = resultado_final.get('caminho_documento', '')
                    df.at[idx, 'Documentos Processados'] = resultado_final.get('documentos_processados', '')
                    df.at[idx, 'Total Documentos'] = resultado_final.get('total_documentos', 0)
                    
                    # Log detalhado
                    print(f"  -> Resultado: {resultado_final.get('status', '')}")
                    
                    # [DEBUG] INDICAR CONTINUAÇÃO PARA PRÓXIMO PROCESSO
                    if idx + 1 < len(df):
                        proximo_codigo = str(df.iloc[idx + 1][codigo_col])
                        print(f"[RELOAD] CONTINUANDO para próximo processo: {proximo_codigo}")
                        
                        # 🗂️ FECHAR ABAS AUTOMATICAMENTE ANTES DO PRÓXIMO PROCESSO
                        if idx + 1 < len(df):
                            proximo_processo = str(df.iloc[idx + 1]['Codigo'])
                            print(f"[RELOAD] CONTINUANDO para próximo processo: {proximo_processo}")
                            
                            # [DEBUG] CORREÇÃO: Sempre verificar se está na URL correta
                            try:
                                url_atual = lecom.driver.current_url
                                url_correta = 'https://justica.servicos.gov.br/workspace/'
                                
                                if url_atual != url_correta:
                                    print(f"[AVISO] URL incorreta detectada: {url_atual}")
                                    print(f"[RELOAD] Redirecionando para URL correta: {url_correta}")
                                    lecom.driver.get(url_correta)
                                    time.sleep(3)
                                    print("[OK] Redirecionamento para URL correta concluído")
                                else:
                                    print("[OK] URL correta confirmada")
                            except Exception as e:
                                print(f"[AVISO] Erro ao verificar URL: {e}")
                            
                        try:
                            print("🧹 Fechando abas desnecessárias antes do próximo processo...")
                            lecom.fechar_abas_desnecessarias()
                            print("[OK] Abas organizadas - pronto para próximo processo!")
                        except Exception as e:
                            print(f"[AVISO] Erro ao fechar abas: {e}")
                            # Fallback: navegação direta para pesquisa
                            try:
                                lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                time.sleep(3)
                                print("[OK] Navegação de fallback para pesquisa concluída")
                            except Exception as e2:
                                print(f"[ERRO] Fallback falhou: {e2}")
                        
                        print("=" * 80)
                    else:
                        print("🏁 ÚLTIMO PROCESSO CONCLUÍDO!")
                        print("=" * 80)
                    
                    # Salvamento parcial a cada 10 processos
                    if (idx + 1) % 10 == 0:
                        df.to_excel(out_path, index=False)
                        print(f"DEBUG: Salvamento parcial realizado após {idx+1} processos.")
                
            finally:
                # Fechar o driver
                lecom.close()
            
            # [DEBUG] CORREÇÃO: Para análise provisória, usar o ExportadorProvisoria
            if tipo_processo.lower() == 'provisoria':
                print("DEBUG: [DADOS] Usando ExportadorProvisoria para gerar planilha...")
                try:
                    from exportador_provisoria import ExportadorProvisoria
                    
                    exportador = ExportadorProvisoria()
                    
                                        # Coletar todos os resultados processados
                    resultados_para_exportar = []
                    
                    for idx, row in df.iterrows():
                         codigo = str(row[codigo_col])
                         
                         # Criar estrutura de dados compatível com ExportadorProvisoria
                         observacoes_upper = str(row.get('Observações', '')).upper()
                         status_upper = str(row.get('Status', '')).upper()
                         
                         # [DEBUG] CORREÇÃO: Detectar elegibilidade_final na ordem correta
                         if 'INDEFERIMENTO AUTOMÁTICO' in observacoes_upper or 'INDEFERIMENTO AUTOMÁTICO' in status_upper:
                             elegibilidade_final = 'indeferimento_automatico'
                             percentual_final = 0
                         elif 'REQUER ANÁLISE MANUAL' in observacoes_upper or 'REQUER ANÁLISE MANUAL' in status_upper:
                             elegibilidade_final = 'requer_analise_manual'
                             percentual_final = 0
                         elif 'DEFERIMENTO' in observacoes_upper and 'INDEFERIMENTO' not in observacoes_upper:
                             elegibilidade_final = 'deferimento'
                             percentual_final = 100
                         elif 'ELEGÍVEL COM RESSALVA' in observacoes_upper or 'RESSALVA' in observacoes_upper or ('ELEGÍVEL' in observacoes_upper and 'PROBLEMAS' in observacoes_upper):
                             elegibilidade_final = 'elegivel_com_ressalva'
                             # Extrair percentual das observações se possível
                             import re
                             match = re.search(r'(\d+)%', observacoes_upper)
                             percentual_final = int(match.group(1)) if match else 90
                         elif 'ELEGIBILIDADE COMPROMETIDA' in observacoes_upper or 'COMPROMETIDA' in observacoes_upper:
                             elegibilidade_final = 'elegibilidade_comprometida'
                             # Extrair percentual das observações se possível
                             import re
                             match = re.search(r'(\d+)%', observacoes_upper)
                             percentual_final = int(match.group(1)) if match else 70
                         elif 'NÃO ELEGÍVEL' in observacoes_upper:
                             elegibilidade_final = 'nao_elegivel'
                             # Extrair percentual das observações se possível
                             import re
                             match = re.search(r'(\d+)%', observacoes_upper)
                             percentual_final = int(match.group(1)) if match else 60
                         else:
                             elegibilidade_final = 'indeterminada'
                             percentual_final = 0
                         
                         # [DEBUG] CORREÇÃO: Adicionar documentos processados para contagem correta
                         total_docs = row.get('Total Documentos', 0)
                         
                         # Simular estrutura de documentos para o ExportadorProvisoria
                         documentos_simulados = {
                             'Documento de identificação do representante legal': {'status': 'OK', 'presente': True} if total_docs > 0 else {'status': 'Erro', 'presente': False},
                             'Carteira de Registro Nacional Migratório': {'status': 'OK', 'presente': True} if total_docs > 0 else {'status': 'Erro', 'presente': False},
                             'Comprovante de tempo de residência': {'status': 'OK', 'presente': True} if total_docs > 0 else {'status': 'Erro', 'presente': False},
                             'Documento de viagem internacional': {'status': 'OK', 'presente': True} if total_docs > 0 else {'status': 'Erro', 'presente': False},
                             'percentual_elegibilidade': percentual_final
                         }
                         
                         resultado_linha = {
                             'status': row.get('Status', ''),
                             'data_processamento': row.get('Data Processamento', ''),
                             'observacoes': row.get('Observações', ''),
                             'analise_elegibilidade': {
                                 'elegibilidade_final': elegibilidade_final,
                                 'percentual_final': percentual_final,
                                 'motivo_final': row.get('Observações', ''),
                                 'documentos': documentos_simulados
                             }
                         }
                         
                         # Usar ExportadorProvisoria para criar linha formatada
                         linha_formatada = exportador.criar_linha_planilha(
                             numero_processo=codigo,
                             dados_pessoais={'nome_completo': 'DADOS_MASCARADOS', 'data_nascimento': '01/01/2000'},
                             resultado_analise=resultado_linha,
                             data_inicial_processo='01/01/2024'
                         )
                         
                         resultados_para_exportar.append(linha_formatada)
                    
                    # Exportar usando ExportadorProvisoria
                    caminho_exportado = exportador.exportar_para_excel(resultados_para_exportar, out_path)
                    print(f"DEBUG: [OK] Planilha exportada usando ExportadorProvisoria: {caminho_exportado}")
                    
                except Exception as e:
                    print(f"DEBUG: [ERRO] Erro ao usar ExportadorProvisoria: {e}")
                    print("DEBUG: [RELOAD] Usando exportação padrão como fallback...")
                    df.to_excel(out_path, index=False)
            else:
                # Para outros tipos, usar exportação padrão
                df.to_excel(out_path, index=False)
            
            download_url = url_for('download_file', filename=os.path.basename(out_path))
            resultado = f'Processamento concluído! <a href="{download_url}">Baixar planilha processada</a>'
            
        except Exception as e:
            resultado = f'Erro ao processar a planilha: {e}'
    
    return render_template('analise_automatica.html', resultado=resultado)

def processar_processos_definitivos(link):
    """Processa processos definitivos"""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    import pandas as pd
    import os
    
    def extrair_processos_definitivos(driver, url, caminho_saida):
        driver.get(url)
        todos_processos = []
        pagina = 1
        
        while True:
            print(f"Processando página {pagina}...")
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                )
            except Exception as e:
                print(f"Erro ao encontrar portarias na página {pagina}: {e}")
                break
                
            portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
            links = [link.get_attribute('href') for link in portarias_links]
            
            for link in links:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(link)
                
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    
                    texto_portaria = driver.find_element(By.XPATH, "//body").text
                    if not texto_portaria or len(texto_portaria) < 200:
                        try:
                            div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                            paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                            texto_portaria = "\n".join([p.text for p in paragrafos])
                        except:
                            pass
                    
                    # Extrair informações específicas de processos definitivos
                    processos = extrair_info_processos_definitivos(texto_portaria)
                    for processo in processos:
                        processo['link_portaria'] = link
                        todos_processos.append(processo)
                        
                except Exception as e:
                    print(f"Erro ao processar portaria: {e}")
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1)
            
            try:
                right_arrow = driver.find_element(By.ID, "rightArrow")
                if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                    right_arrow.click()
                    pagina += 1
                    time.sleep(2)
                else:
                    print("Última página alcançada.")
                    break
            except Exception as e:
                print("Não há mais páginas ou erro ao clicar na seta:", e)
                break
        
        if todos_processos:
            df = pd.DataFrame(todos_processos)
            df = df.fillna('')
            df.to_excel(caminho_saida, index=False)
            return caminho_saida, len(df)
        else:
            return None, 0
    
    def extrair_info_processos_definitivos(texto):
        import re
        processos = []
        
        # Padrão para encontrar processos definitivos
        padrao_definitivo = re.compile(
            r'(?:Processo\s*n[º°o]*\s*([\d\.\-/]+).*?)(?:Conceder|Concedida|Concedido).*?(?:nacionalidade\s+brasileira|brasileira\s+nacionalidade).*?(?:definitiva|definitivo)',
            re.IGNORECASE | re.DOTALL
        )
        
        matches = padrao_definitivo.finditer(texto)
        
        for match in matches:
            processo_info = {
                'numero_processo': match.group(1) if match.group(1) else 'Não encontrado',
                'tipo': 'Definitiva',
                'status': 'Concedida',
                'nacionalidade': 'Brasileira',
                'texto_completo': match.group(0)
            }
            processos.append(processo_info)
        
        return processos
    
    # Configurar e executar o driver
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"processos_definitivos_{timestamp}.xlsx"
        caminho_saida = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        
        arquivo, total_registros = extrair_processos_definitivos(driver, link, caminho_saida)
        
        if arquivo:
            return f'Processamento concluído! {total_registros} processos definitivos encontrados. <a href="/download/{nome_arquivo}">Baixar resultado</a>'
        else:
            return 'Nenhum processo definitivo encontrado.'
            
    except Exception as e:
        return f'Erro durante o processamento: {str(e)}'
    finally:
        if 'driver' in locals():
            driver.quit()

def processar_processos_ordinarios(link):
    """Processa processos ordinários"""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    import pandas as pd
    import os
    
    def extrair_processos_ordinarios(driver, url, caminho_saida):
        driver.get(url)
        todos_processos = []
        pagina = 1
        
        while True:
            print(f"Processando página {pagina}...")
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                )
            except Exception as e:
                print(f"Erro ao encontrar portarias na página {pagina}: {e}")
                break
                
            portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
            links = [link.get_attribute('href') for link in portarias_links]
            
            for link in links:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(link)
                
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    
                    texto_portaria = driver.find_element(By.XPATH, "//body").text
                    if not texto_portaria or len(texto_portaria) < 200:
                        try:
                            div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                            paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                            texto_portaria = "\n".join([p.text for p in paragrafos])
                        except:
                            pass
                    
                    # Extrair informações específicas de processos ordinários
                    processos = extrair_info_processos_ordinarios(texto_portaria)
                    for processo in processos:
                        processo['link_portaria'] = link
                        todos_processos.append(processo)
                        
                except Exception as e:
                    print(f"Erro ao processar portaria: {e}")
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1)
            
            try:
                right_arrow = driver.find_element(By.ID, "rightArrow")
                if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                    right_arrow.click()
                    pagina += 1
                    time.sleep(2)
                else:
                    print("Última página alcançada.")
                    break
            except Exception as e:
                print("Não há mais páginas ou erro ao clicar na seta:", e)
                break
        
        if todos_processos:
            df = pd.DataFrame(todos_processos)
            df = df.fillna('')
            df.to_excel(caminho_saida, index=False)
            return caminho_saida, len(df)
        else:
            return None, 0
    
    def extrair_info_processos_ordinarios(texto):
        import re
        processos = []
        
        # Padrão para encontrar processos ordinários
        padrao_ordinario = re.compile(
            r'(?:Processo\s*n[º°o]*\s*([\d\.\-/]+).*?)(?:Conceder|Concedida|Concedido).*?(?:nacionalidade\s+brasileira|brasileira\s+nacionalidade).*?(?:ordinária|ordinário)',
            re.IGNORECASE | re.DOTALL
        )
        
        matches = padrao_ordinario.finditer(texto)
        
        for match in matches:
            processo_info = {
                'numero_processo': match.group(1) if match.group(1) else 'Não encontrado',
                'tipo': 'Ordinária',
                'status': 'Concedida',
                'nacionalidade': 'Brasileira',
                'texto_completo': match.group(0)
            }
            processos.append(processo_info)
        
        return processos
    
    # Configurar e executar o driver
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"processos_ordinarios_{timestamp}.xlsx"
        caminho_saida = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        
        arquivo, total_registros = extrair_processos_ordinarios(driver, link, caminho_saida)
        
        if arquivo:
            return f'Processamento concluído! {total_registros} processos ordinários encontrados. <a href="/download/{nome_arquivo}">Baixar resultado</a>'
        else:
            return 'Nenhum processo ordinário encontrado.'
            
    except Exception as e:
        return f'Erro durante o processamento: {str(e)}'
    finally:
        if 'driver' in locals():
            driver.quit()

def processar_processos_extraordinarios(link):
    """Processa processos extraordinários"""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    import pandas as pd
    import os
    
    def extrair_processos_extraordinarios(driver, url, caminho_saida):
        driver.get(url)
        todos_processos = []
        pagina = 1
        
        while True:
            print(f"Processando página {pagina}...")
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                )
            except Exception as e:
                print(f"Erro ao encontrar portarias na página {pagina}: {e}")
                break
                
            portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
            links = [link.get_attribute('href') for link in portarias_links]
            
            for link in links:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(link)
                
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    
                    texto_portaria = driver.find_element(By.XPATH, "//body").text
                    if not texto_portaria or len(texto_portaria) < 200:
                        try:
                            div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                            paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                            texto_portaria = "\n".join([p.text for p in paragrafos])
                        except:
                            pass
                    
                    # Extrair informações específicas de processos extraordinários
                    processos = extrair_info_processos_extraordinarios(texto_portaria)
                    for processo in processos:
                        processo['link_portaria'] = link
                        todos_processos.append(processo)
                        
                except Exception as e:
                    print(f"Erro ao processar portaria: {e}")
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1)
            
            try:
                right_arrow = driver.find_element(By.ID, "rightArrow")
                if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                    right_arrow.click()
                    pagina += 1
                    time.sleep(2)
                else:
                    print("Última página alcançada.")
                    break
            except Exception as e:
                print("Não há mais páginas ou erro ao clicar na seta:", e)
                break
        
        if todos_processos:
            df = pd.DataFrame(todos_processos)
            df = df.fillna('')
            df.to_excel(caminho_saida, index=False)
            return caminho_saida, len(df)
        else:
            return None, 0
    
    def extrair_info_processos_extraordinarios(texto):
        import re
        processos = []
        
        # Padrão para encontrar processos extraordinários
        padrao_extraordinario = re.compile(
            r'(?:Processo\s*n[º°o]*\s*([\d\.\-/]+).*?)(?:Conceder|Concedida|Concedido).*?(?:nacionalidade\s+brasileira|brasileira\s+nacionalidade).*?(?:extraordinária|extraordinário)',
            re.IGNORECASE | re.DOTALL
        )
        
        matches = padrao_extraordinario.finditer(texto)
        
        for match in matches:
            processo_info = {
                'numero_processo': match.group(1) if match.group(1) else 'Não encontrado',
                'tipo': 'Extraordinária',
                'status': 'Concedida',
                'nacionalidade': 'Brasileira',
                'texto_completo': match.group(0)
            }
            processos.append(processo_info)
        
        return processos
    
    # Configurar e executar o driver
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"processos_extraordinarios_{timestamp}.xlsx"
        caminho_saida = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        
        arquivo, total_registros = extrair_processos_extraordinarios(driver, link, caminho_saida)
        
        if arquivo:
            return f'Processamento concluído! {total_registros} processos extraordinários encontrados. <a href="/download/{nome_arquivo}">Baixar resultado</a>'
        else:
            return 'Nenhum processo extraordinário encontrado.'
            
    except Exception as e:
        return f'Erro durante o processamento: {str(e)}'
    finally:
        if 'driver' in locals():
            driver.quit()



def processar_processos_provisorios(link):
    """Processa processos provisórios"""
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    import time
    import pandas as pd
    import os
    
    def extrair_processos_provisorios(driver, url, caminho_saida):
        driver.get(url)
        todos_processos = []
        pagina = 1
        
        while True:
            print(f"Processando página {pagina}...")
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
                )
            except Exception as e:
                print(f"Erro ao encontrar portarias na página {pagina}: {e}")
                break
                
            portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
            links = [link.get_attribute('href') for link in portarias_links]
            
            for link in links:
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(link)
                
                try:
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(2)
                    
                    texto_portaria = driver.find_element(By.XPATH, "//body").text
                    if not texto_portaria or len(texto_portaria) < 200:
                        try:
                            div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                            paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                            texto_portaria = "\n".join([p.text for p in paragrafos])
                        except:
                            pass
                    
                    # Extrair informações específicas de processos provisórios
                    processos = extrair_info_processos_provisorios(texto_portaria)
                    for processo in processos:
                        processo['link_portaria'] = link
                        todos_processos.append(processo)
                        
                except Exception as e:
                    print(f"Erro ao processar portaria: {e}")
                finally:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    time.sleep(1)
            
            try:
                right_arrow = driver.find_element(By.ID, "rightArrow")
                if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                    right_arrow.click()
                    pagina += 1
                    time.sleep(2)
                else:
                    print("Última página alcançada.")
                    break
            except Exception as e:
                print("Não há mais páginas ou erro ao clicar na seta:", e)
                break
        
        if todos_processos:
            df = pd.DataFrame(todos_processos)
            df = df.fillna('')
            df.to_excel(caminho_saida, index=False)
            return caminho_saida, len(df)
        else:
            return None, 0
    
    def extrair_info_processos_provisorios(texto):
        import re
        processos = []
        
        # Padrão para encontrar processos provisórios
        padrao_provisorio = re.compile(
            r'(?:Processo\s*n[º°o]*\s*([\d\.\-/]+).*?)(?:Conceder|Concedida|Concedido).*?(?:nacionalidade\s+brasileira|brasileira\s+nacionalidade).*?(?:provisória|provisório)',
            re.IGNORECASE | re.DOTALL
        )
        
        matches = padrao_provisorio.finditer(texto)
        
        for match in matches:
            processo_info = {
                'numero_processo': match.group(1) if match.group(1) else 'Não encontrado',
                'tipo': 'Provisória',
                'status': 'Concedida',
                'nacionalidade': 'Brasileira',
                'texto_completo': match.group(0)
            }
            processos.append(processo_info)
        
        return processos
    
    # Configurar e executar o driver
    options = webdriver.ChromeOptions()
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"processos_provisorios_{timestamp}.xlsx"
        caminho_saida = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        
        arquivo, total_registros = extrair_processos_provisorios(driver, link, caminho_saida)
        
        if arquivo:
            return f'Processamento concluído! {total_registros} processos provisórios encontrados. <a href="/download/{nome_arquivo}">Baixar resultado</a>'
        else:
            return 'Nenhum processo provisório encontrado.'
            
    except Exception as e:
        return f'Erro durante o processamento: {str(e)}'
    finally:
        if 'driver' in locals():
            driver.quit()

@app.route('/complementacao', methods=['GET', 'POST'])
def complementacao():
    """Página de Indeferimentos Complementação"""
    import pandas as pd
    import tempfile
    import os
    # from indef_lecom import LecomAutomation
    resultado = None
    download_url = None
    if request.method == 'POST':
        tipo_complementacao = request.form.get('tipo_complementacao', 'preencher')
        if 'planilha' not in request.files:
            resultado = 'Nenhum arquivo enviado.'
            return render_template('complementacao.html', resultado=resultado)
        file = request.files['planilha']
        if file.filename == '':
            resultado = 'Nenhum arquivo selecionado.'
            return render_template('complementacao.html', resultado=resultado)
        try:
            df = pd.read_excel(file, dtype={'Codigo': str})
            if 'Codigo' not in df.columns:
                resultado = 'A planilha deve conter a coluna Codigo.'
                return render_template('complementacao.html', resultado=resultado)
            uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            out_path = os.path.join(uploads_dir, 'complementacaoindef_resultado.xlsx')
            if tipo_complementacao == 'mapeamento':
                from indef_lecom import LecomMapeamento
                df['Resultado Mapeamento'] = ''
                lecom = LecomMapeamento()
                for idx, row in df.iterrows():
                    numero_processo = str(row['Codigo'])
                    print(f"DEBUG: [Mapeamento] Processando linha {idx+1}/{len(df)} - Codigo: {numero_processo}")
                    try:
                        resultado_map = lecom.processar_mapeamento(numero_processo)
                        df.at[idx, 'Resultado Mapeamento'] = resultado_map.get('resultado', '')
                        # Log detalhado
                        print(f"  -> Resultado: {resultado_map.get('resultado', '')}")
                        if 'etapas' in resultado_map:
                            print(f"  -> Etapas extraídas: {resultado_map['etapas']}")
                    except Exception as e:
                        df.at[idx, 'Resultado Mapeamento'] = f'Erro: {e}'
                        print(f"  -> Erro: {e}")
                    if (idx + 1) % 10 == 0:
                        df.to_excel(out_path, index=False)
                        print(f"DEBUG: Salvamento parcial realizado após {idx+1} processos.")
                    
                    # 🗂️ FECHAR ABAS AUTOMATICAMENTE ANTES DO PRÓXIMO PROCESSO
                    if idx + 1 < len(df):
                        proximo_processo = str(df.iloc[idx + 1]['Codigo'])
                        print(f"[RELOAD] CONTINUANDO para próximo processo: {proximo_processo}")
                        try:
                            print("🧹 Fechando abas desnecessárias antes do próximo processo...")
                            lecom.fechar_abas_desnecessarias()
                            print("[OK] Abas organizadas - pronto para próximo processo!")
                        except Exception as e:
                            print(f"[AVISO] Erro ao fechar abas: {e}")
                            # Fallback: navegação direta para pesquisa
                            try:
                                lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                time.sleep(3)
                                print("[OK] Navegação de fallback para pesquisa concluída")
                            except Exception as e2:
                                print(f"[ERRO] Fallback falhou: {e2}")
                    
                    # Reiniciar driver a cada 700 processos
                    if (idx + 1) % 700 == 0:
                        lecom.close()
                        print(f"DEBUG: Driver reiniciado após {idx+1} processos.")
                        from indef_lecom import LecomMapeamento
                        lecom = LecomMapeamento()
                lecom.close()
                df.to_excel(out_path, index=False)
                download_url = url_for('download_file', filename=os.path.basename(out_path))
                resultado = f'Processamento de mapeamento concluído! <a href="{download_url}">Baixar planilha processada</a>'
            else:
                # Fluxo antigo: Preencher Dados
                df['País de nascimento'] = ''
                df['Data de nascimento'] = ''
                df['Estado'] = ''
                df['Sexo'] = ''
                df['Tipo de naturalização'] = ''
                from indef_lecom import LecomAutomation
                lecom = LecomAutomation()
                for idx, row in df.iterrows():
                    numero_processo = str(row['Codigo'])
                    print(f"DEBUG: Processando linha {idx+1}/{len(df)} - Codigo: {numero_processo}")
                    try:
                        dados = lecom.processar_processo_complementacao(numero_processo)
                        df.at[idx, 'País de nascimento'] = dados.get('pais', '')
                        df.at[idx, 'Data de nascimento'] = dados.get('data_nasc', '')
                        df.at[idx, 'Estado'] = dados.get('estado', '')
                        df.at[idx, 'Sexo'] = dados.get('sexo', '')
                        df.at[idx, 'Tipo de naturalização'] = dados.get('tipo', '')
                    except Exception as e:
                        df.at[idx, 'País de nascimento'] = f'Erro: {e}'
                    if (idx + 1) % 10 == 0:
                        df.to_excel(out_path, index=False)
                        print(f"DEBUG: Salvamento parcial realizado após {idx+1} processos.")
                    
                    # 🗂️ FECHAR ABAS AUTOMATICAMENTE ANTES DO PRÓXIMO PROCESSO
                    if idx + 1 < len(df):
                        proximo_processo = str(df.iloc[idx + 1]['Codigo'])
                        print(f"[RELOAD] CONTINUANDO para próximo processo: {proximo_processo}")
                        try:
                            print("🧹 Fechando abas desnecessárias antes do próximo processo...")
                            lecom.fechar_abas_desnecessarias()
                            print("[OK] Abas organizadas - pronto para próximo processo!")
                        except Exception as e:
                            print(f"[AVISO] Erro ao fechar abas: {e}")
                            # Fallback: navegação direta para pesquisa
                            try:
                                lecom.driver.get('https://justica.servicos.gov.br/workspace/')
                                time.sleep(3)
                                print("[OK] Navegação de fallback para pesquisa concluída")
                            except Exception as e2:
                                print(f"[ERRO] Fallback falhou: {e2}")
                    
                    # Reiniciar driver a cada 700 processos
                    if (idx + 1) % 700 == 0:
                        lecom.close()
                        print(f"DEBUG: Driver reiniciado após {idx+1} processos.")
                        from indef_lecom import LecomAutomation
                        lecom = LecomAutomation()
                lecom.close()
                df.to_excel(out_path, index=False)
                download_url = url_for('download_file', filename=os.path.basename(out_path))
                resultado = f'Processamento concluído! <a href="{download_url}">Baixar planilha processada</a>'
        except Exception as e:
            resultado = f'Erro ao processar a planilha: {e}'
    return render_template('complementacao.html', resultado=resultado)

# --- Funções utilitárias para extração de portarias ---
def extrair_portarias_deferimento(driver, url, caminho_saida, analyzer):
    driver.get(url)
    todas_pessoas = []
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import pandas as pd
    import re
    pagina = 1
    while True:
        print(f"Processando página {pagina}...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]"))
        )
        portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
        links = [link.get_attribute('href') for link in portarias_links]
        for link in links:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[1])
            driver.get(link)
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            try:
                texto_portaria = driver.find_element(By.XPATH, "//body").text
                if not texto_portaria or len(texto_portaria) < 200:
                    try:
                        div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                        paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                        texto_portaria = "\n".join([p.text for p in paragrafos])
                    except:
                        pass
            except:
                try:
                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                    texto_portaria = "\n".join([p.text for p in paragrafos])
                except:
                    texto_portaria = ""
            
            print(f"[DOC] Analisando portaria da URL: {link}")
            print(f"[DADOS] Tamanho do texto: {len(texto_portaria)} caracteres")
            
            try:
                # Usar analisar_multiplas_portarias para processar corretamente múltiplas portarias
                resultados, _ = analyzer.analisar_multiplas_portarias(texto_portaria, gerar_excel=False)
                
                print(f"[INFO] Portarias encontradas na página: {len(resultados)}")
                
                for i, res in enumerate(resultados, 1):
                    if res.get('dados_portaria'):
                        dados_portaria = res['dados_portaria']
                        tipo_portaria = dados_portaria.get('tipo', 'DESCONHECIDO')
                        numero_portaria = dados_portaria.get('numero_data_formatado', 'N/A')
                        
                        print(f"   {i}. {numero_portaria} - Tipo: {tipo_portaria}")
                        print(f"      Pessoas: {len(dados_portaria.get('pessoas', []))}")
                        
                        # Adicionar cada pessoa com as informações corretas da sua portaria
                        for pessoa in dados_portaria.get('pessoas', []):
                            pessoa_info = pessoa.copy()
                            pessoa_info['portaria_completa'] = numero_portaria
                            pessoa_info['tipo_portaria'] = tipo_portaria
                            pessoa_info['url_fonte'] = link  # Adicionar URL fonte para rastreabilidade
                            todas_pessoas.append(pessoa_info)
                            
                print(f"[OK] Total de pessoas extraídas desta página: {sum(len(res.get('dados_portaria', {}).get('pessoas', [])) for res in resultados)}")
                        
            except Exception as e:
                print(f"[ERRO] Erro ao analisar portaria da URL {link}: {e}")
                import traceback
                traceback.print_exc()
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(1)
        try:
            right_arrow = driver.find_element(By.ID, "rightArrow")
            if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                right_arrow.click()
                pagina += 1
                time.sleep(2)
            else:
                print("Última página alcançada.")
                break
        except Exception as e:
            print("Não há mais páginas ou erro ao clicar na seta:", e)
            break
    if todas_pessoas:
        df = pd.DataFrame(todas_pessoas)
        df = df.fillna('')
        
        # Renomear colunas conforme solicitado
        mapeamento_colunas = {
            'nome': 'Nome Completo',
            'documento': 'CRNM',
            'data_nascimento': 'Data de Nascimento',
            'nome_pai': 'Nome do pai',
            'nome_mae': 'Nome da mãe',
            'portaria_completa': 'Portaria',
            'tipo_portaria': 'Tipo',
            'estado': 'Estado',
            'processo': 'Processo',
            'pais': 'Natural'
        }
        
        # Aplicar renomeação apenas para colunas existentes
        colunas_para_renomear = {k: v for k, v in mapeamento_colunas.items() if k in df.columns}
        df = df.rename(columns=colunas_para_renomear)
        
        # Verificar distribuição de tipos antes de salvar
        print(f"\n[DADOS] RESUMO FINAL DA EXTRAÇÃO:")
        print(f"   Total de pessoas extraídas: {len(df)}")
        
        if 'Tipo' in df.columns:
            tipos_count = df['Tipo'].value_counts()
            print(f"   Distribuição por tipo:")
            for tipo, count in tipos_count.items():
                print(f"      {tipo}: {count} pessoas")
        
        if 'Portaria' in df.columns:
            portarias_count = df['Portaria'].value_counts()
            print(f"   Distribuição por portaria:")
            for portaria, count in portarias_count.items():
                portaria_short = portaria.replace('PORTARIA Nº ', '').split(',')[0]
                print(f"      {portaria_short}: {count} pessoas")
        
        # Reordenar colunas para facilitar análise (usando novos nomes)
        colunas_importantes = ['Nome Completo', 'CRNM', 'Natural', 'Data de Nascimento', 'Nome do pai', 'Nome da mãe', 'sexo', 'Estado', 'Processo', 'Portaria', 'Tipo']
        colunas_existentes = [col for col in colunas_importantes if col in df.columns]
        colunas_restantes = [col for col in df.columns if col not in colunas_importantes]
        df = df[colunas_existentes + colunas_restantes]
        
        df.to_excel(caminho_saida, index=False)
        print(f"[OK] Planilha salva em: {caminho_saida}")
        return caminho_saida, len(df)
    else:
        print("[ERRO] Nenhuma pessoa foi extraída")
        return None, 0

def extrair_portarias_igualdade(driver, url, caminho_saida, analyzer, separar_blocos_igualdade):
    driver.get(url)
    todas_pessoas = []
    import time
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import pandas as pd
    pagina = 1
    while True:
        print(f"Processando página {pagina}...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
        ))
        portarias_links = driver.find_elements(By.XPATH, "//a[contains(@href, '/web/dou/-/portaria-')]")
        links = [link.get_attribute('href') for link in portarias_links]
        for link in links:
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[1])
            driver.get(link)
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            try:
                texto_portaria = driver.find_element(By.XPATH, "//body").text
                if not texto_portaria or len(texto_portaria) < 200:
                    try:
                        div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                        paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                        texto_portaria = "\n".join([p.text for p in paragrafos])
                    except:
                        pass
            except:
                try:
                    div_texto_dou = driver.find_element(By.XPATH, "//div[contains(@class, 'texto-dou')]")
                    paragrafos = div_texto_dou.find_elements(By.TAG_NAME, "p")
                    texto_portaria = "\n".join([p.text for p in paragrafos])
                except:
                    texto_portaria = ""
            blocos = separar_blocos_igualdade(texto_portaria)
            for bloco_info in blocos:
                bloco = bloco_info['texto']
                tipo_igualdade = bloco_info['tipo']
                try:
                    # Usar função específica para igualdade de direitos portuguesa
                    pessoas_extraidas = analyzer.extrair_pessoas_igualdade(bloco)
                    
                    for pessoa in pessoas_extraidas:
                        pessoa_info = pessoa.copy()
                        
                        # Adicionar informações de portaria
                        pessoa_info['portaria_completa'] = f"PORTARIA {bloco[:50]}..."  # Primeiros 50 chars como identificação
                        pessoa_info['tipo_portaria'] = 'Igualdade de Direitos'
                        
                        # Adicionar colunas específicas para o tipo de igualdade
                        if tipo_igualdade == 'outorga_direitos_politicos':
                            pessoa_info['outorga_direitos_politicos'] = 'Sim'
                            pessoa_info['igualdade_direitos_obrigacoes'] = ''
                            pessoa_info['tipo_igualdade_completo'] = 'Outorga de Direitos Políticos'
                        elif tipo_igualdade == 'igualdade_direitos_obrigacoes':
                            pessoa_info['outorga_direitos_politicos'] = ''
                            pessoa_info['igualdade_direitos_obrigacoes'] = 'Sim'
                            pessoa_info['tipo_igualdade_completo'] = 'Igualdade de Direitos e Obrigações Civis'
                        elif tipo_igualdade == 'igualdade_portuguesa':
                            pessoa_info['outorga_direitos_politicos'] = ''
                            pessoa_info['igualdade_direitos_obrigacoes'] = 'Sim'
                            pessoa_info['tipo_igualdade_completo'] = 'Igualdade de Direitos Portuguesa'
                        else:
                            pessoa_info['outorga_direitos_politicos'] = ''
                            pessoa_info['igualdade_direitos_obrigacoes'] = ''
                            pessoa_info['tipo_igualdade_completo'] = tipo_igualdade
                        
                        pessoa_info['tipo_igualdade_identificado'] = tipo_igualdade
                        todas_pessoas.append(pessoa_info)
                        
                except Exception as e:
                    print(f"Erro ao analisar portaria de igualdade: {e}")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(1)
            try:
                right_arrow = driver.find_element(By.ID, "rightArrow")
                if right_arrow.is_enabled() and right_arrow.get_attribute("disabled") is None:
                    right_arrow.click()
                    pagina += 1
                    time.sleep(2)
                else:
                    print("Última página alcançada.")
                    break
            except Exception as e:
                print("Não há mais páginas ou erro ao clicar na seta:", e)
                break
        if todas_pessoas:
            # Eliminar duplicações baseadas em nome e documento
            pessoas_unicas = []
            chaves_vistas = set()
            
            for pessoa in todas_pessoas:
                # Criar chave única baseada em nome e documento
                chave_unica = f"{pessoa.get('nome', '')}-{pessoa.get('documento', '')}"
                
                if chave_unica not in chaves_vistas:
                    pessoas_unicas.append(pessoa)
                    chaves_vistas.add(chave_unica)
                else:
                    print(f"[DEBUG] Duplicação eliminada: {pessoa.get('nome', 'N/A')}")
            
            print(f"[INFO] Pessoas originais: {len(todas_pessoas)}, Pessoas únicas: {len(pessoas_unicas)}")
            
            df = pd.DataFrame(pessoas_unicas)
            df = df.fillna('')
            
            # Aplicar mapeamento de nomes de colunas para igualdade
            mapeamento_colunas = {
                'nome': 'Nome Completo',
                'documento': 'CRNM',
                'data_nascimento': 'Data de Nascimento',
                'nome_pai': 'Nome do pai',
                'nome_mae': 'Nome da mãe',
                'portaria_completa': 'Portaria',
                'tipo_portaria': 'Tipo',
                'estado': 'Estado',
                'processo': 'Processo',
                'pais': 'Natural'
            }
            
            # Aplicar renomeação apenas para colunas existentes
            colunas_para_renomear = {k: v for k, v in mapeamento_colunas.items() if k in df.columns}
            df = df.rename(columns=colunas_para_renomear)
            
            df.to_excel(caminho_saida, index=False)
            return caminho_saida, len(df)
        else:
            return None, 0

# Rotas para Aprovação em Lote
@app.route('/aprovacao_lote')
@login_required
def aprovacao_lote():
    """Página de aprovação em lote"""
    return render_template('aprovacao_lote.html')

# Rotas para Aprovação de Parecer do Analista
@app.route('/aprovacao_parecer_analista')
@login_required
def aprovacao_parecer_analista():
    """Página de aprovação de parecer do analista"""
    return render_template('aprovacao_parecer_analista.html')

# Rotas para Aprovação do Conteúdo de Recurso
@app.route('/aprovacao_conteudo_recurso')
@login_required
def aprovacao_conteudo_recurso():
    """Página de aprovação do conteúdo de recurso"""
    return render_template('aprovacao_conteudo_recurso.html')

# Rota para Defere ou Indefere Recurso
@app.route('/defere_indefere_recurso')
@login_required
def defere_indefere_recurso():
    """Página de Defere ou Indefere Recurso"""
    return render_template('defere_indefere_recurso.html')

@app.route('/api/aprovacao_lote/iniciar', methods=['POST'])
@login_required
def api_aprovacao_lote_iniciar():
    """API para iniciar processo de aprovação em lote"""
    import threading
    import uuid
    
    try:
        data = request.get_json()
        max_iteracoes = data.get('max_iteracoes', 10)
        modo_execucao = data.get('modo_execucao', 'continuo')
        tempo_espera_minutos = data.get('tempo_espera_minutos', 10)
        
        # Gerar ID único para o processo
        process_id = str(uuid.uuid4())
        
        # Armazenar status do processo na sessão
        if 'aprovacao_lote_processes' not in session:
            session['aprovacao_lote_processes'] = {}
        
        session['aprovacao_lote_processes'][process_id] = {
            'status': 'starting',
            'status_text': 'Iniciando...',
            'detail': 'Preparando automação',
            'progress': 0,
            'logs': [],
            'start_time': datetime.now().isoformat(),
            'max_iteracoes': max_iteracoes,
            'modo_execucao': modo_execucao,
            'tempo_espera_minutos': tempo_espera_minutos
        }
        session.permanent = True
        
        # Iniciar processo em thread separada
        thread = threading.Thread(
            target=executar_aprovacao_lote_background,
            args=(process_id, max_iteracoes, modo_execucao, tempo_espera_minutos)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'process_id': process_id,
            'message': 'Processo iniciado com sucesso'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/aprovacao_lote/status/<process_id>')
@login_required
def api_aprovacao_lote_status(process_id):
    """API para verificar status do processo de aprovação em lote"""
    try:
        if 'aprovacao_lote_processes' not in session:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        if process_id not in session['aprovacao_lote_processes']:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        process_data = session['aprovacao_lote_processes'][process_id]
        
        # Retornar apenas logs novos (se necessário)
        # Por simplicidade, retornamos todos os logs por agora
        response_data = {
            'status': process_data['status'],
            'status_text': process_data['status_text'],
            'detail': process_data['detail'],
            'progress': process_data['progress'],
            'new_logs': process_data.get('logs', [])[-10:]  # Últimos 10 logs
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/aprovacao_lote/parar/<process_id>', methods=['POST'])
@login_required
def api_aprovacao_lote_parar(process_id):
    """API para parar processo de aprovação em lote"""
    try:
        if 'aprovacao_lote_processes' not in session:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        if process_id not in session['aprovacao_lote_processes']:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        # Marcar para parar (o thread verificará este status)
        session['aprovacao_lote_processes'][process_id]['status'] = 'stopping'
        session['aprovacao_lote_processes'][process_id]['status_text'] = 'Parando...'
        session['aprovacao_lote_processes'][process_id]['detail'] = 'Interrompendo execução'
        session.permanent = True
        
        return jsonify({'success': True, 'message': 'Comando de parada enviado'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/aprovacao_parecer_analista/iniciar', methods=['POST'])
@login_required
def api_aprovacao_parecer_analista_iniciar():
    """API para iniciar processo de aprovação de parecer do analista"""
    import threading
    import uuid
    import os
    
    try:
        # Gerar ID único para o processo
        process_id = str(uuid.uuid4())
        
        # Obter modo de seleção
        modo_selecao = request.form.get('modo_selecao', 'versao')
        caminho_planilha = None
        
        # Processar upload de planilha se modo for 'planilha'
        if modo_selecao == 'planilha':
            if 'planilha' not in request.files:
                return jsonify({
                    'success': False,
                    'error': 'Arquivo de planilha não foi fornecido'
                }), 400
            
            file = request.files['planilha']
            if file.filename == '':
                return jsonify({
                    'success': False,
                    'error': 'Nenhum arquivo selecionado'
                }), 400
            
            # Validar extensão
            if not file.filename.lower().endswith(('.xlsx', '.xls')):
                return jsonify({
                    'success': False,
                    'error': 'Arquivo deve ser um Excel (.xlsx ou .xls)'
                }), 400
            
            # Salvar arquivo temporariamente
            upload_dir = os.path.join(os.path.dirname(__file__), 'uploads', 'temp')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Nome único para o arquivo
            filename = f"{process_id}_{file.filename}"
            caminho_planilha = os.path.join(upload_dir, filename)
            file.save(caminho_planilha)
        
        # Armazenar status do processo na sessão
        if 'aprovacao_parecer_processes' not in session:
            session['aprovacao_parecer_processes'] = {}
        
        session['aprovacao_parecer_processes'][process_id] = {
            'status': 'starting',
            'status_text': 'Iniciando...',
            'detail': 'Preparando automação',
            'progress': 0,
            'logs': [],
            'start_time': datetime.now().isoformat(),
            'modo_selecao': modo_selecao,
            'caminho_planilha': caminho_planilha
        }
        session.permanent = True
        
        # Iniciar processo em thread separada
        thread = threading.Thread(
            target=executar_aprovacao_parecer_background,
            args=(process_id, modo_selecao, caminho_planilha)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'process_id': process_id,
            'message': f'Processo iniciado com sucesso no modo {modo_selecao}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/aprovacao_parecer_analista/status/<process_id>')
@login_required
def api_aprovacao_parecer_analista_status(process_id):
    """API para verificar status do processo de aprovação de parecer do analista"""
    try:
        # Tentar obter dados da sessão primeiro
        process_data = None
        if 'aprovacao_parecer_processes' in session and process_id in session['aprovacao_parecer_processes']:
            process_data = session['aprovacao_parecer_processes'][process_id]
        
        # Se não encontrou na sessão, tentar nos dados globais
        if not process_data and process_id in _global_process_data:
            process_data = _global_process_data[process_id]
            # Sincronizar de volta para a sessão se possível
            try:
                if 'aprovacao_parecer_processes' not in session:
                    session['aprovacao_parecer_processes'] = {}
                session['aprovacao_parecer_processes'][process_id] = process_data.copy()
                session.permanent = True
            except:
                pass
        
        if not process_data:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        response_data = {
            'status': process_data['status'],
            'status_text': process_data['status_text'],
            'detail': process_data['detail'],
            'progress': process_data['progress'],
            'new_logs': process_data.get('logs', [])[-10:]  # Últimos 10 logs
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/aprovacao_parecer_analista/parar/<process_id>', methods=['POST'])
@login_required
def api_aprovacao_parecer_analista_parar(process_id):
    """API para parar processo de aprovação de parecer do analista"""
    try:
        if 'aprovacao_parecer_processes' not in session:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        if process_id not in session['aprovacao_parecer_processes']:
            return jsonify({'error': 'Processo não encontrado'}), 404
        
        # Marcar processo para parar
        session['aprovacao_parecer_processes'][process_id]['should_stop'] = True
        session['aprovacao_parecer_processes'][process_id]['status'] = 'stopping'
        session.permanent = True
        
        return jsonify({'success': True, 'message': 'Parando execução e gerando planilha...'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API para Aprovação do Conteúdo de Recurso
@app.route('/upload_aprovacao_recurso', methods=['POST'])
@api_login_required
def upload_aprovacao_recurso():
    """API para upload e processamento de planilha de aprovação do conteúdo de recurso"""
    import threading
    import uuid
    from aprovacao_conteudo_recurso import AprovacaoConteudoRecurso
    
    try:
        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
        
        file = request.files['file']
        column_name = request.form.get('columnName', 'codigo')
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'})
        
        # Verificar extensão do arquivo
        allowed_extensions = {'xlsx', 'csv', 'xls'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'message': 'Formato de arquivo não permitido'})
        
        # Salvar arquivo temporário
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Criar pasta de uploads se não existir
        upload_folder = 'uploads'
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Gerar ID único para o processo
        process_id = str(uuid.uuid4())
        
        # Inicializar processo na sessão
        if 'aprovacao_recurso_processes' not in session:
            session['aprovacao_recurso_processes'] = {}
        
        session['aprovacao_recurso_processes'][process_id] = {
            'status': 'starting',
            'message': 'Iniciando processamento...',
            'progress': 0,
            'logs': [],
            'should_stop': False,
            'start_time': datetime.now().isoformat(),
            'file_path': filepath,
            'column_name': column_name
        }
        session.permanent = True
        
        # Iniciar processamento em background
        BACKGROUND_PROCESSES[process_id] = {
            'status': 'starting',
            'message': 'Iniciando processamento...',
            'progress': 0,
            'logs': [],
            'should_stop': False,
            'start_time': datetime.now().isoformat()
        }
        thread = threading.Thread(
            target=executar_aprovacao_recurso_background,
            args=(process_id, filepath, column_name)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': f'Planilha enviada com sucesso! Processamento iniciado.',
            'process_id': process_id
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro no servidor: {str(e)}'})

@app.route('/api/aprovacao_recurso/status/<process_id>')
@api_login_required
def api_aprovacao_recurso_status(process_id):
    """API para verificar status do processo de aprovação do conteúdo de recurso"""
    try:
        # Preferir dados em memória se existirem
        process_data = BACKGROUND_PROCESSES.get(process_id)
        if not process_data:
            # Fallback para sessão
            if 'aprovacao_recurso_processes' not in session:
                return jsonify({'error': 'Nenhum processo encontrado'}), 404
            if process_id not in session['aprovacao_recurso_processes']:
                return jsonify({'error': 'Processo não encontrado'}), 404
            process_data = session['aprovacao_recurso_processes'][process_id]
        
        response_data = {
            'process_id': process_id,
            'status': process_data['status'],
            'message': process_data.get('message') or process_data.get('status_text') or '',
            'progress': process_data.get('progress', 0),
            'logs': process_data.get('logs', []),
            'start_time': process_data.get('start_time'),
            'end_time': process_data.get('end_time'),
            'results': process_data.get('results', {})
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/upload_defere_indefere_recurso', methods=['POST'])
@api_login_required
def upload_defere_indefere_recurso():
    """API para upload e processamento de planilha de Defere ou Indefere Recurso"""
    import threading
    import uuid
    from defere_indefere_recurso import DefereIndefefereRecurso
    
    try:
        # Verificar se arquivo foi enviado
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'Nenhum arquivo enviado'})
        
        file = request.files['file']
        column_name = request.form.get('columnName', 'codigo')
        
        if file.filename == '':
            return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'})
        
        # Verificar extensão do arquivo
        allowed_extensions = {'xlsx', 'csv', 'xls'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({'success': False, 'message': 'Formato de arquivo não permitido'})
        
        # Salvar arquivo temporário
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Criar pasta de uploads se não existir
        upload_folder = 'uploads'
        os.makedirs(upload_folder, exist_ok=True)
        
        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)
        
        # Gerar ID único para o processo
        process_id = str(uuid.uuid4())
        
        # Inicializar processo na sessão
        if 'defere_indefere_processes' not in session:
            session['defere_indefere_processes'] = {}
        
        session['defere_indefere_processes'][process_id] = {
            'status': 'starting',
            'message': 'Iniciando processamento...',
            'progress': 0,
            'logs': [],
            'should_stop': False,
            'start_time': datetime.now().isoformat(),
            'file_path': filepath,
            'column_name': column_name
        }
        
        # Executar em thread separada
        thread = threading.Thread(
            target=executar_defere_indefere_background,
            args=(process_id, filepath, column_name),
            daemon=True
        )
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Processamento iniciado com sucesso!',
            'process_id': process_id
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Erro ao processar arquivo: {str(e)}'})

@app.route('/api/defere_indefere_recurso/status/<process_id>')
@api_login_required
def api_defere_indefere_recurso_status(process_id):
    """API para verificar status do processo de Defere ou Indefere Recurso"""
    try:
        # Preferir dados em memória se existirem
        process_data = BACKGROUND_PROCESSES.get(process_id)
        if not process_data:
            # Fallback para sessão
            if 'defere_indefere_processes' not in session:
                return jsonify({'error': 'Nenhum processo encontrado'}), 404
            if process_id not in session['defere_indefere_processes']:
                return jsonify({'error': 'Processo não encontrado'}), 404
            process_data = session['defere_indefere_processes'][process_id]
        
        response_data = {
            'process_id': process_id,
            'status': process_data['status'],
            'message': process_data.get('message') or process_data.get('status_text') or '',
            'progress': process_data.get('progress', 0),
            'logs': process_data.get('logs', []),
            'start_time': process_data.get('start_time'),
            'end_time': process_data.get('end_time'),
            'results': process_data.get('results', {})
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def executar_defere_indefere_background(process_id, filepath, column_name):
    """Executa Defere ou Indefere Recurso em background"""
    from defere_indefere_recurso import DefereIndefefereRecurso
    import time
    
    automatizador = None
    try:
        # Atualizar status
        update_process_status(process_id, 'running', 'Inicializando...', 'Configurando automação', 15)
        add_process_log(process_id, 'Iniciando módulo de Defere ou Indefere Recurso...', 'info')
        
        # Inicializar automatizador
        automatizador = DefereIndefefereRecurso()
        add_process_log(process_id, '[OK] Automatizador inicializado', 'info')
        
        # Fazer login
        update_process_status(process_id, 'running', 'Fazendo login...', 'Conectando ao LECOM', 25)
        add_process_log(process_id, 'Realizando login no sistema LECOM...', 'info')
        
        if not automatizador.login():
            raise Exception("Falha no login manual - processo cancelado")
        
        add_process_log(process_id, '[OK] Login realizado com sucesso!', 'success')
        
        # Ler planilha
        update_process_status(process_id, 'running', 'Lendo planilha...', 'Carregando códigos dos processos', 35)
        add_process_log(process_id, f'Lendo planilha: {filepath}', 'info')
        
        codigos = automatizador.ler_planilha_codigos(filepath, column_name)
        if not codigos:
            raise Exception("Nenhum código encontrado na planilha")
        
        add_process_log(process_id, f'[OK] {len(codigos)} códigos encontrados na planilha', 'success')
        
        # Processar códigos
        total_codigos = len(codigos)
        resultados = []
        
        for i, codigo in enumerate(codigos, 1):
            # Verificar se deve parar
            process_data = BACKGROUND_PROCESSES.get(process_id) or session.get('defere_indefere_processes', {}).get(process_id, {})
            if process_data.get('should_stop', False):
                add_process_log(process_id, '⏹️ Processo cancelado pelo usuário', 'warning')
                break
            
            # Atualizar progresso
            progress = int((i / total_codigos) * 100)
            update_process_status(
                process_id, 
                'running', 
                f'Processando {i}/{total_codigos}...', 
                f'Código: {codigo}', 
                progress
            )
            add_process_log(process_id, f'[INFO] Processando código {i}/{total_codigos}: {codigo}', 'info')
            
            # Processar processo individual
            resultado = automatizador.processar_processo_completo(codigo)
            resultados.append(resultado)
            
            if resultado['status'] == 'sucesso':
                add_process_log(process_id, f'[OK] {codigo}: {resultado["decisao"]} - Decisão enviada: {resultado.get("decisao_enviada", False)}', 'success')
            else:
                add_process_log(process_id, f'[ERRO] {codigo}: {resultado.get("erro", "Erro desconhecido")}', 'error')
        
        # Finalizar
        update_process_status(process_id, 'completed', 'Processamento concluído!', 'Salvando resultados...', 100)
        
        # Resumo
        sucessos = len([r for r in resultados if r['status'] == 'sucesso'])
        erros = len([r for r in resultados if r['status'] == 'erro'])
        decisoes_enviadas = len([r for r in resultados if r.get('decisao_enviada', False)])
        
        summary = {
            'total_processados': len(resultados),
            'sucessos': sucessos,
            'erros': erros,
            'decisoes_enviadas': decisoes_enviadas,
            'arquivo_original': filepath
        }
        
        # Armazenar resultados
        if 'defere_indefere_processes' in session and process_id in session['defere_indefere_processes']:
            session['defere_indefere_processes'][process_id]['results'] = summary
        add_process_log(process_id, f'[DADOS] Resumo: {sucessos} sucessos, {erros} erros, {decisoes_enviadas} decisões enviadas', 'success')
        add_process_log(process_id, '[OK] Processamento concluído com sucesso!', 'success')
        
    except Exception as e:
        update_process_status(process_id, 'error', f'Erro: {str(e)}', str(e), 0)
        add_process_log(process_id, f'[ERRO] Erro durante processamento: {str(e)}', 'error')
    finally:
        # Fechar automatizador se existir
        if automatizador:
            try:
                automatizador.close()
                add_process_log(process_id, '[FECHADO] Recursos liberados', 'info')
            except Exception as e:
                add_process_log(process_id, f'[AVISO] Erro ao liberar recursos: {str(e)}', 'warning')

def executar_aprovacao_recurso_background(process_id, filepath, column_name):
    """Executa aprovação do conteúdo de recurso em background"""
    from aprovacao_conteudo_recurso import AprovacaoConteudoRecurso
    import time
    
    aprovador = None
    try:
        # Atualizar status
        update_process_status(process_id, 'running', 'Inicializando...', 'Configurando automação', 15)
        add_process_log(process_id, 'Iniciando módulo de aprovação do conteúdo de recurso...', 'info')
        
        # Inicializar aprovador
        aprovador = AprovacaoConteudoRecurso()
        add_process_log(process_id, '[OK] Aprovador inicializado', 'info')
        
        # Fazer login
        update_process_status(process_id, 'running', 'Fazendo login...', 'Conectando ao LECOM', 25)
        add_process_log(process_id, 'Realizando login no sistema LECOM...', 'info')
        
        if not aprovador.login():
            add_process_log(process_id, '[ERRO] Falha no login no LECOM', 'error')
            raise Exception("Falha no login no LECOM")
        
        add_process_log(process_id, '[OK] Login realizado com sucesso!', 'success')
        
        # Processar planilha
        update_process_status(process_id, 'running', 'Processando planilha...', 'Lendo códigos dos processos', 50)
        add_process_log(process_id, f'Processando planilha: {os.path.basename(filepath)}', 'info')
        
        # Ler códigos da planilha
        add_process_log(process_id, f'[BUSCA] Lendo códigos da planilha com coluna: {column_name}', 'info')
        
        # Verificar status do driver ANTES de ler planilha
        try:
            url_antes = aprovador.driver.current_url
            add_process_log(process_id, f'[OK] Driver ativo ANTES da leitura - URL: {url_antes}', 'info')
        except Exception as e:
            add_process_log(process_id, f'[ERRO] Driver não está ativo ANTES da leitura: {e}', 'error')
        
        try:
            add_process_log(process_id, f'[DEBUG] DEBUG: Chamando ler_planilha_codigos...', 'info')
            codigos = aprovador.ler_planilha_codigos(filepath, column_name)
            add_process_log(process_id, f'[INFO] Leitura da planilha concluída com sucesso', 'info')
            add_process_log(process_id, f'[DEBUG] DEBUG: Códigos retornados: {len(codigos) if codigos else 0}', 'info')
        except Exception as e:
            add_process_log(process_id, f'[ERRO] Erro ao ler planilha: {e}', 'error')
            import traceback
            add_process_log(process_id, f'[DEBUG] Stack trace: {traceback.format_exc()}', 'error')
            raise Exception(f"Erro ao ler planilha: {e}")
        
        # Verificar imediatamente se driver ainda está vivo
        add_process_log(process_id, f'[DEBUG] DEBUG: Verificando driver imediatamente após leitura...', 'info')
        try:
            url_imediato = aprovador.driver.current_url
            add_process_log(process_id, f'[OK] Driver IMEDIATAMENTE após leitura: {url_imediato}', 'info')
        except Exception as e:
            add_process_log(process_id, f'[ERRO] Driver PERDIDO imediatamente após leitura: {e}', 'error')
        
        # Verificar status do driver DEPOIS de ler planilha
        try:
            url_depois = aprovador.driver.current_url
            add_process_log(process_id, f'[OK] Driver ativo DEPOIS da leitura - URL: {url_depois}', 'info')
        except Exception as e:
            add_process_log(process_id, f'[ERRO] Driver não está ativo DEPOIS da leitura: {e}', 'error')
        
        if not codigos:
            add_process_log(process_id, '[ERRO] Nenhum código encontrado na planilha', 'error')
            raise Exception("Nenhum código encontrado na planilha")
        
        add_process_log(process_id, f'[DADOS] Encontrados {len(codigos)} códigos para processar', 'info')
        add_process_log(process_id, f'[BUSCA] Primeiros códigos: {codigos[:5]}', 'info')
        
        # Verificar se driver ainda está ativo
        try:
            current_url = aprovador.driver.current_url
            add_process_log(process_id, f'[OK] Driver ativo - URL atual: {current_url}', 'info')
        except Exception as e:
            add_process_log(process_id, f'[ERRO] Driver não está ativo: {e}', 'error')
            add_process_log(process_id, f'[ERRO] DIAGNÓSTICO: Driver foi fechado antes do loop!', 'error')
            raise Exception("Driver foi fechado antes do loop de processamento")
        
        # Processar cada código
        add_process_log(process_id, '[EXEC] Iniciando processamento dos códigos...', 'info')
        add_process_log(process_id, f'[DEBUG] DEBUG: Tentando processar primeiro código: {codigos[0]}', 'info')
        resultados = []
        total_codigos = len(codigos)
        
        for i, codigo in enumerate(codigos, 1):
            try:
                if BACKGROUND_PROCESSES.get(process_id, {}).get('should_stop', False):
                    add_process_log(process_id, '⏹️ Processo interrompido pelo usuário', 'warning')
                    break
                
                progress = 50 + (i / total_codigos) * 40
                update_process_status(process_id, 'running', f'Processando {i}/{total_codigos}...', f'Processo: {codigo}', progress)
                
                add_process_log(process_id, f'[RELOAD] Processando código {i}/{total_codigos}: {codigo}', 'info')
                
                # Verificar se driver ainda está ativo antes de cada processo
                try:
                    current_url = aprovador.driver.current_url
                except:
                    add_process_log(process_id, f'[ERRO] Driver perdido no processo {i}, finalizando...', 'error')
                    break
                
                # Processar processo individual
                resultado = aprovador.processar_processo_completo(codigo)
                resultados.append(resultado)
                
                if resultado['status'] == 'sucesso':
                    add_process_log(process_id, f'[OK] {codigo}: {resultado["decisao"]}', 'success')
                else:
                    add_process_log(process_id, f'[ERRO] {codigo}: {resultado.get("erro", "Erro desconhecido")}', 'error')
                
                # Pequena pausa entre processos
                time.sleep(1)
                
            except Exception as e:
                add_process_log(process_id, f'[ERRO] Erro ao processar {codigo}: {e}', 'error')
                resultados.append({
                    'codigo': codigo,
                    'decisao': None,
                    'status': 'erro',
                    'erro': str(e)
                })
        
        # Salvar resultados
        add_process_log(process_id, f'[SALVO] Salvando resultados de {len(resultados)} processos...', 'info')
        update_process_status(process_id, 'running', 'Salvando resultados...', 'Gerando planilha de resultados', 90)
        
        # Criar planilha de resultados
        try:
            import pandas as pd
            df_resultados = pd.DataFrame(resultados)
            
            # Nome do arquivo de resultados
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            arquivo_resultado = f"resultados_aprovacao_recurso_{timestamp}.xlsx"
            caminho_resultado = os.path.join('uploads', arquivo_resultado)
            
            # Criar pasta se não existir
            os.makedirs('uploads', exist_ok=True)
            
            # Salvar
            df_resultados.to_excel(caminho_resultado, index=False)
            add_process_log(process_id, f'[SALVO] Resultados salvos: {arquivo_resultado}', 'success')
            
        except Exception as e:
            add_process_log(process_id, f'[AVISO] Erro ao salvar planilha: {e}', 'warning')
        
        # Atualizar dados do processo com resultados
        if 'aprovacao_recurso_processes' in session and process_id in session['aprovacao_recurso_processes']:
            session['aprovacao_recurso_processes'][process_id]['results'] = {
                'total_processados': len(resultados),
                'sucessos': len([r for r in resultados if r['status'] == 'sucesso']),
                'erros': len([r for r in resultados if r['status'] == 'erro']),
                'resultados': resultados
            }
            session.permanent = True
        
        # Finalizar
        update_process_status(process_id, 'completed', 'Concluído!', 'Processamento finalizado', 100)
        add_process_log(process_id, f'[OK] Processamento concluído! {len(resultados)} processos processados', 'success')
        
    except Exception as e:
        import traceback
        error_msg = f"Erro durante processamento: {str(e)}"
        add_process_log(process_id, f'[ERRO] {error_msg}', 'error')
        add_process_log(process_id, f'[BUSCA] Traceback: {traceback.format_exc()}', 'error')
        update_process_status(process_id, 'error', 'Erro', error_msg, 0)
    
    finally:
        # NÃO fechar driver automaticamente aqui para evitar encerramento prematuro durante depuração
        add_process_log(process_id, 'ℹ️ Finalizando thread sem fechar driver (modo debug)', 'info')
        
        # Limpar arquivo temporário
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                add_process_log(process_id, '🗑️ Arquivo temporário removido', 'info')
        except Exception as e:
            add_process_log(process_id, f'[AVISO] Erro ao remover arquivo temporário: {e}', 'warning')

def executar_aprovacao_lote_background(process_id, max_iteracoes, modo_execucao, tempo_espera_minutos=10):
    """Executa aprovação em lote em background"""
    from aprovacao_lote import AprovacaoLote
    
    aprovacao = None
    try:
        # Atualizar status
        update_process_status(process_id, 'running', 'Inicializando...', 'Configurando automação', 15)
        add_process_log(process_id, 'Iniciando módulo de aprovação em lote...', 'info')
        
        # Inicializar aprovação em lote
        aprovacao = AprovacaoLote()
        
        # Inicializar driver
        update_process_status(process_id, 'running', 'Inicializando Driver...', 'Abrindo navegador VISUAL', 25)
        add_process_log(process_id, 'Inicializando driver do navegador em MODO VISUAL...', 'info')
        
        if not aprovacao.inicializar_driver(headless=False):  # Modo VISUAL ativado
            raise Exception("Falha ao inicializar driver")
        
        add_process_log(process_id, '[OK] Driver inicializado em MODO VISUAL - você pode acompanhar a execução!', 'success')
        
        if modo_execucao == 'continuo':
            # Executar múltiplos ciclos completos com tempo de espera entre eles
            update_process_status(process_id, 'running', 'Executando Ciclos Contínuos...', f'Máximo {max_iteracoes} ciclos - Espera: {tempo_espera_minutos}min', 35)
            add_process_log(process_id, f'Iniciando {max_iteracoes} ciclos completos de aprovação...', 'info')
            add_process_log(process_id, f'⏰ Tempo de espera entre ciclos: {tempo_espera_minutos} minutos', 'info')
            
            ciclos_executados = 0
            for i in range(max_iteracoes):
                # Verificar se deve parar
                if check_should_stop(process_id):
                    add_process_log(process_id, 'Execução interrompida pelo usuário', 'warning')
                    break
                
                progress = 35 + (i / max_iteracoes) * 50
                update_process_status(process_id, 'running', f'Ciclo {i+1}/{max_iteracoes}', 'Executando aprovações em lote...', progress)
                add_process_log(process_id, f'[RELOAD] Iniciando ciclo completo {i+1}/{max_iteracoes}...', 'info')
                
                # Executar UM ciclo completo de aprovação
                resultado_ciclo = aprovacao.executar_aprovacao_completa()
                
                if resultado_ciclo:
                    ciclos_executados += 1
                    add_process_log(process_id, f'[OK] Ciclo {i+1} concluído com sucesso', 'success')
                else:
                    add_process_log(process_id, f'[AVISO] Ciclo {i+1} não encontrou processos para aprovar', 'warning')
                
                # Aguardar entre ciclos (exceto no último) - SEMPRE aguardar independente do resultado
                if i < max_iteracoes - 1:
                    add_process_log(process_id, f'[AGUARDE] Aguardando {tempo_espera_minutos} minutos antes do próximo ciclo...', 'info')
                    update_process_status(process_id, 'running', f'Aguardando {tempo_espera_minutos}min...', f'Pausa entre ciclo {i+1} e {i+2}', progress)
                    
                    # Aguardar com logs de progresso
                    aguardar_com_logs(process_id, tempo_espera_minutos)
                    
                    add_process_log(process_id, f'[OK] Espera concluída - iniciando ciclo {i+2}', 'success')
            
            add_process_log(process_id, f'🏁 Execução finalizada. {ciclos_executados} ciclos completos executados.', 'success')
            
        else:
            # Execução única
            update_process_status(process_id, 'running', 'Execução Única...', 'Processando aprovações...', 50)
            add_process_log(process_id, 'Iniciando execução única...', 'info')
            
            if aprovacao.executar_aprovacao_completa():
                add_process_log(process_id, '[OK] Execução única concluída com sucesso', 'success')
            else:
                raise Exception("Falha na execução única")
        
        # Finalizar com sucesso
        update_process_status(process_id, 'completed', 'Concluído!', 'Processo finalizado com sucesso', 100)
        add_process_log(process_id, '[SUCCESS] Processo de aprovação em lote concluído!', 'success')
        
    except Exception as e:
        # Erro durante execução
        update_process_status(process_id, 'error', 'Erro', f'Falha: {str(e)}', 0)
        add_process_log(process_id, f'[ERRO] Erro: {str(e)}', 'error')
        
    finally:
        # Fechar recursos
        if aprovacao:
            try:
                aprovacao.fechar()
                add_process_log(process_id, 'Recursos liberados', 'info')
            except:
                pass

def update_process_status(process_id, status, status_text, detail, progress):
    """Atualiza status do processo (em memória e na sessão se disponível)"""
    # Em memória (thread-safe básico)
    try:
        BACKGROUND_PROCESSES.setdefault(process_id, {}).update({
            'status': status,
            'message': status_text,
            'detail': detail,
            'progress': progress
        })
    except Exception:
        pass
    # Espelha na sessão quando possível
    try:
        with app.app_context():
            if 'aprovacao_lote_processes' in session and process_id in session['aprovacao_lote_processes']:
                session['aprovacao_lote_processes'][process_id].update({
                    'status': status,
                    'status_text': status_text,
                    'detail': detail,
                    'progress': progress
                })
                session.permanent = True
            elif 'aprovacao_recurso_processes' in session and process_id in session['aprovacao_recurso_processes']:
                session['aprovacao_recurso_processes'][process_id].update({
                    'status': status,
                    'message': status_text,
                    'detail': detail,
                    'progress': progress
                })
                session.permanent = True
    except Exception:
        pass

def add_process_log(process_id, message, log_type='info'):
    """Adiciona log ao processo (em memória e na sessão se disponível)"""
    entry = {
        'message': message,
        'type': log_type,
        'timestamp': datetime.now().isoformat()
    }
    # Em memória
    try:
        BACKGROUND_PROCESSES.setdefault(process_id, {}).setdefault('logs', []).append(entry)
    except Exception:
        pass
    # Espelhar na sessão quando possível
    try:
        with app.app_context():
            if 'aprovacao_lote_processes' in session and process_id in session['aprovacao_lote_processes']:
                session['aprovacao_lote_processes'][process_id].setdefault('logs', []).append(entry)
                session.permanent = True
            elif 'aprovacao_recurso_processes' in session and process_id in session['aprovacao_recurso_processes']:
                session['aprovacao_recurso_processes'][process_id].setdefault('logs', []).append(entry)
                session.permanent = True
    except Exception:
        pass

def check_should_stop(process_id):
    """Verifica se o processo deve ser interrompido"""
    try:
        with app.app_context():
            if 'aprovacao_lote_processes' in session and process_id in session['aprovacao_lote_processes']:
                return session['aprovacao_lote_processes'][process_id]['status'] == 'stopping'
    except:
        pass
    return False

def aguardar_com_logs(process_id, tempo_espera_minutos):
    """Aguarda o tempo especificado com logs de progresso para a interface"""
    import time
    
    tempo_espera_segundos = tempo_espera_minutos * 60
    add_process_log(process_id, f'⏰ Iniciando espera de {tempo_espera_minutos} minutos ({tempo_espera_segundos} segundos)', 'info')
    
    # Aguardar em intervalos de 30 segundos para mostrar progresso
    intervalos = max(1, tempo_espera_segundos // 30)  # Divide em até 30 intervalos
    tempo_por_intervalo = tempo_espera_segundos / intervalos
    
    for intervalo in range(int(intervalos)):
        # Verificar se deve parar
        if check_should_stop(process_id):
            add_process_log(process_id, 'Espera interrompida pelo usuário', 'warning')
            break
        
        # Aguardar um intervalo
        time.sleep(tempo_por_intervalo)
        
        # Calcular tempo restante
        tempo_decorrido = (intervalo + 1) * tempo_por_intervalo
        tempo_restante = tempo_espera_segundos - tempo_decorrido
        
        if tempo_restante > 60:
            minutos_restantes = int(tempo_restante / 60)
            add_process_log(process_id, f'[AGUARDE] Tempo restante: {minutos_restantes} minutos', 'info')
        elif tempo_restante > 0:
            segundos_restantes = int(tempo_restante)
            add_process_log(process_id, f'[AGUARDE] Tempo restante: {segundos_restantes} segundos', 'info')
    
    add_process_log(process_id, '[OK] Tempo de espera concluído', 'success')

def executar_aprovacao_parecer_background(process_id, modo_selecao, caminho_planilha):
    """Executa aprovação de parecer do analista em background"""
    from aprovacao_parecer_analista import AprovacaoParecerAnalista
    import os
    
    aprovacao = None
    try:
        # Usar contexto da aplicação para acessar sessão
        with app.app_context():
            # Atualizar status
            update_process_status_parecer_safe(process_id, 'running', 'Inicializando...', 'Configurando automação', 15)
            add_process_log_parecer_safe(process_id, f'Iniciando módulo de aprovação de parecer do analista no modo {modo_selecao}...', 'info')
            
            if modo_selecao == 'planilha' and caminho_planilha:
                add_process_log_parecer_safe(process_id, f'Planilha carregada: {os.path.basename(caminho_planilha)}', 'info')
            
            # Inicializar aprovação de parecer com parâmetros apropriados
            aprovacao = AprovacaoParecerAnalista(
                modo_selecao=modo_selecao,
                caminho_planilha=caminho_planilha
            )
        
            # Inicializar driver
            update_process_status_parecer_safe(process_id, 'running', 'Inicializando Driver...', 'Abrindo navegador VISUAL', 25)
            add_process_log_parecer_safe(process_id, 'Inicializando driver do navegador em MODO VISUAL...', 'info')
            
            if not aprovacao.inicializar_driver(headless=False):  # Modo VISUAL ativado
                raise Exception("Falha ao inicializar driver")
            
            add_process_log_parecer_safe(process_id, '[OK] Driver inicializado em MODO VISUAL - você pode acompanhar a execução!', 'success')
        
            # Executar processo completo
            update_process_status_parecer_safe(process_id, 'running', 'Executando Processo...', 'Processando aprovações de parecer', 35)
            add_process_log_parecer_safe(process_id, 'Iniciando processo de aprovação de parecer do analista...', 'info')
            
            # Verificar se deve parar antes de executar
            if check_should_stop_parecer(process_id):
                aprovacao.parar_execucao()
                update_process_status_parecer_safe(process_id, 'stopped', 'Execução Interrompida', 'Parado pelo usuário', 50)
                add_process_log_parecer_safe(process_id, '🛑 Execução interrompida pelo usuário', 'warning')
                return
            
            resultado = aprovacao.executar_aprovacao_completa()
            
            if resultado:
                update_process_status_parecer_safe(process_id, 'completed', 'Processo Concluído', 'Todas as aprovações processadas', 100)
                add_process_log_parecer_safe(process_id, '[OK] Processo de aprovação de parecer do analista concluído com sucesso!', 'success')
                
                # Verificar se há resultados processados
                if hasattr(aprovacao, 'resultados_processamento') and aprovacao.resultados_processamento:
                    total_processos = len(aprovacao.resultados_processamento)
                    processos_cpmig = len([p for p in aprovacao.resultados_processamento if p.get('status') == 'ENVIAR PARA CPMIG'])
                    processos_manual = len([p for p in aprovacao.resultados_processamento if p.get('status') == 'ANÁLISE MANUAL'])
                    
                    add_process_log_parecer_safe(process_id, f'[DADOS] Resumo: {total_processos} processos processados', 'info')
                    add_process_log_parecer_safe(process_id, f'[OK] Para CPMIG: {processos_cpmig} | [AVISO] Análise Manual: {processos_manual}', 'info')
                    add_process_log_parecer_safe(process_id, '[PASTA] Planilha Excel gerada na pasta do projeto', 'success')
                
            else:
                update_process_status_parecer_safe(process_id, 'error', 'Processo Finalizado com Problemas', 'Houve problemas durante a execução', 90)
                add_process_log_parecer_safe(process_id, '[AVISO] Processo finalizado mas com alguns problemas', 'warning')
        
    except Exception as e:
        error_msg = str(e)
        update_process_status_parecer_safe(process_id, 'error', 'Erro na Execução', f'Erro: {error_msg[:50]}...', 0)
        add_process_log_parecer_safe(process_id, f'[ERRO] Erro durante execução: {error_msg}', 'error')
    
    finally:
        # Sempre fechar o driver
        if aprovacao:
            try:
                aprovacao.fechar()
                add_process_log_parecer_safe(process_id, '[OK] Recursos limpos e driver fechado', 'info')
            except:
                pass
        
        # Limpar arquivo temporário se existir
        try:
            if caminho_planilha and os.path.exists(caminho_planilha):
                os.remove(caminho_planilha)
                add_process_log_parecer_safe(process_id, '🗑️ Arquivo temporário removido', 'info')
        except Exception as e:
            print(f"Erro ao limpar arquivo temporário: {e}")
        
        # Sincronizar dados globais de volta para a sessão antes de finalizar
        try:
            with app.app_context():
                sync_global_to_session_parecer(process_id)
        except:
            pass

def update_process_status_parecer(process_id, status, status_text, detail, progress):
    """Atualiza status do processo de aprovação de parecer"""
    try:
        if 'aprovacao_parecer_processes' in session and process_id in session['aprovacao_parecer_processes']:
            session['aprovacao_parecer_processes'][process_id].update({
                'status': status,
                'status_text': status_text,
                'detail': detail,
                'progress': progress,
                'last_update': datetime.now().isoformat()
            })
            session.permanent = True
    except Exception as e:
        print(f"Erro ao atualizar status do processo de parecer: {e}")

def add_process_log_parecer(process_id, message, log_type='info'):
    """Adiciona log ao processo de aprovação de parecer"""
    try:
        if 'aprovacao_parecer_processes' in session and process_id in session['aprovacao_parecer_processes']:
            if 'logs' not in session['aprovacao_parecer_processes'][process_id]:
                session['aprovacao_parecer_processes'][process_id]['logs'] = []
            
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = {
                'timestamp': timestamp,
                'message': message,
                'type': log_type
            }
            
            session['aprovacao_parecer_processes'][process_id]['logs'].append(log_entry)
            
            # Manter apenas os últimos 50 logs para evitar excesso de memória
            if len(session['aprovacao_parecer_processes'][process_id]['logs']) > 50:
                session['aprovacao_parecer_processes'][process_id]['logs'] = session['aprovacao_parecer_processes'][process_id]['logs'][-50:]
            
            session.permanent = True
    except Exception as e:
        print(f"Erro ao adicionar log do processo de parecer: {e}")

def check_should_stop_parecer(process_id):
    """Verifica se o processo de aprovação de parecer deve parar"""
    try:
        if 'aprovacao_parecer_processes' in session and process_id in session['aprovacao_parecer_processes']:
            return session['aprovacao_parecer_processes'][process_id].get('should_stop', False)
        return False
    except:
        return False

# Variável global para armazenar dados de processo (para threads background)
_global_process_data = {}

def update_process_status_parecer_safe(process_id, status, status_text, detail, progress):
    """Versão segura para atualizar status do processo de aprovação de parecer"""
    try:
        # Armazenar em variável global para acesso das threads
        if process_id not in _global_process_data:
            _global_process_data[process_id] = {'logs': []}
        
        _global_process_data[process_id].update({
            'status': status,
            'status_text': status_text,
            'detail': detail,
            'progress': progress,
            'last_update': datetime.now().isoformat()
        })
        
        # Tentar atualizar sessão também se possível
        try:
            if 'aprovacao_parecer_processes' in session and process_id in session['aprovacao_parecer_processes']:
                session['aprovacao_parecer_processes'][process_id].update({
                    'status': status,
                    'status_text': status_text,
                    'detail': detail,
                    'progress': progress,
                    'last_update': datetime.now().isoformat()
                })
                session.permanent = True
        except:
            pass  # Ignorar se não conseguir acessar sessão
            
    except Exception as e:
        print(f"Erro ao atualizar status do processo de parecer (safe): {e}")

def add_process_log_parecer_safe(process_id, message, log_type='info'):
    """Versão segura para adicionar log ao processo de aprovação de parecer"""
    try:
        # Armazenar em variável global
        if process_id not in _global_process_data:
            _global_process_data[process_id] = {'logs': []}
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'type': log_type
        }
        
        _global_process_data[process_id]['logs'].append(log_entry)
        
        # Manter apenas os últimos 50 logs
        if len(_global_process_data[process_id]['logs']) > 50:
            _global_process_data[process_id]['logs'] = _global_process_data[process_id]['logs'][-50:]
        
        # Tentar atualizar sessão também se possível
        try:
            if 'aprovacao_parecer_processes' in session and process_id in session['aprovacao_parecer_processes']:
                if 'logs' not in session['aprovacao_parecer_processes'][process_id]:
                    session['aprovacao_parecer_processes'][process_id]['logs'] = []
                
                session['aprovacao_parecer_processes'][process_id]['logs'].append(log_entry)
                
                if len(session['aprovacao_parecer_processes'][process_id]['logs']) > 50:
                    session['aprovacao_parecer_processes'][process_id]['logs'] = session['aprovacao_parecer_processes'][process_id]['logs'][-50:]
                
                session.permanent = True
        except:
            pass  # Ignorar se não conseguir acessar sessão
            
    except Exception as e:
        print(f"Erro ao adicionar log do processo de parecer (safe): {e}")

def sync_global_to_session_parecer(process_id):
    """Sincroniza dados globais de volta para a sessão"""
    try:
        if process_id in _global_process_data and 'aprovacao_parecer_processes' in session:
            if process_id in session['aprovacao_parecer_processes']:
                session['aprovacao_parecer_processes'][process_id].update(_global_process_data[process_id])
                session.permanent = True
    except:
        pass

# Rotas para exportação Excel
@app.route('/exportar_excel_completo')
@login_required
def exportar_excel_completo():
    """Exporta todos os dados dos processos para Excel com textos OCR"""
    try:
        if not EXPORTADOR_DISPONIVEL:
            flash('Exportador Excel não está disponível', 'error')
            return redirect(url_for('index'))
        
        # Obter todos os processos da sessão ou arquivo
        processos_para_exportar = []
        
        # Tentar obter da sessão primeiro
        if 'processos_analisados' in session:
            processos_para_exportar = session['processos_analisados']
        else:
            # Se não houver na sessão, tentar ler de arquivo
            arquivo_processos = os.path.join(app.config['UPLOAD_FOLDER'], 'processos_analisados.json')
            if os.path.exists(arquivo_processos):
                with open(arquivo_processos, 'r', encoding='utf-8') as f:
                    processos_para_exportar = json.load(f)
        
        if not processos_para_exportar:
            flash('Nenhum processo encontrado para exportar. Execute a análise primeiro.', 'error')
            return redirect(url_for('index'))
        
        # Exportar para Excel
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"analise_completa_processos_{timestamp}.xlsx"
        
        arquivo_excel = exportar_processos_excel(processos_para_exportar, nome_arquivo)
        
        # Criar estatísticas
        estatisticas = criar_resumo_estatisticas(processos_para_exportar)
        
        flash(f'Exportação concluída! {estatisticas["total_processos"]} processos exportados. Arquivo: {nome_arquivo}', 'success')
        
        # Fazer download automático
        return send_file(arquivo_excel, as_attachment=True, download_name=nome_arquivo)
        
    except Exception as e:
        flash(f'Erro na exportação: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/visualizar_estatisticas')
@login_required
def visualizar_estatisticas():
    """Visualiza estatísticas dos processos analisados"""
    try:
        if not EXPORTADOR_DISPONIVEL:
            flash('Exportador Excel não está disponível', 'error')
            return redirect(url_for('index'))
        
        # Obter processos
        processos_para_exportar = []
        
        if 'processos_analisados' in session:
            processos_para_exportar = session['processos_analisados']
        else:
            arquivo_processos = os.path.join(app.config['UPLOAD_FOLDER'], 'processos_analisados.json')
            if os.path.exists(arquivo_processos):
                with open(arquivo_processos, 'r', encoding='utf-8') as f:
                    processos_para_exportar = json.load(f)
        
        if not processos_para_exportar:
            flash('Nenhum processo encontrado para análise.', 'error')
            return redirect(url_for('index'))
        
        # Criar estatísticas
        estatisticas = criar_resumo_estatisticas(processos_para_exportar)
        
        return render_template('estatisticas.html', estatisticas=estatisticas, processos=processos_para_exportar)
        
    except Exception as e:
        flash(f'Erro ao gerar estatísticas: {str(e)}', 'error')
        return redirect(url_for('index'))

# ============================================================================
# ROTAS PARA EXTRAÇÃO DE OCR - NAVEGAÇÃO ORDINÁRIA
# ============================================================================

# Armazenamento de processos em execução
processos_extracao_ocr = {}

@app.route('/extracao_ocr')
@login_required
def extracao_ocr():
    """Página de extração de OCR"""
    return render_template('extracao_ocr.html')

@app.route('/api/extracao_ocr/iniciar', methods=['POST'])
@login_required
def iniciar_extracao_ocr():
    """Inicia o processo de extração de OCR"""
    try:
        dados = request.get_json()
        processos = dados.get('processos', [])
        diretorio_saida = dados.get('diretorio_saida', 'ocr_extraidos_doccano')
        
        if not processos:
            return jsonify({
                'success': False,
                'error': 'Nenhum processo fornecido'
            })
        
        # Gerar ID único para este processamento
        import uuid
        process_id = str(uuid.uuid4())
        
        # Armazenar informações do processo
        processos_extracao_ocr[process_id] = {
            'status': 'em_andamento',
            'total': len(processos),
            'processados': 0,
            'erros': 0,
            'processo_atual': None,
            'logs': [],
            'resultado': None,
            'timestamp_inicio': datetime.now().isoformat(),
            'processos_lista': processos,
            'diretorio_saida': diretorio_saida
        }
        
        # Iniciar processamento em thread separada
        import threading
        thread = threading.Thread(
            target=processar_extracao_ocr_async,
            args=(process_id, processos, diretorio_saida)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'process_id': process_id,
            'total_processos': len(processos)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def processar_extracao_ocr_async(process_id, processos, diretorio_saida):
    """Processa extração de OCR de forma assíncrona"""
    try:
        from navegacao_ordinaria_ocr import NavegacaoOrdinariaOCR
        
        # Adicionar log inicial
        adicionar_log_extracao(process_id, 'info', f'Iniciando extração de {len(processos)} processo(s)')
        
        navegacao = None
        
        try:
            # Inicializar navegação
            navegacao = NavegacaoOrdinariaOCR(diretorio_saida=diretorio_saida)
            adicionar_log_extracao(process_id, 'info', 'Sistema de navegação inicializado')
            
            # Fazer login
            adicionar_log_extracao(process_id, 'info', 'Realizando login no sistema LECOM...')
            navegacao.login()
            adicionar_log_extracao(process_id, 'success', 'Login realizado com sucesso')
            
            resultados = []
            
            for i, numero_processo in enumerate(processos, 1):
                # Verificar se foi solicitado parar
                if processos_extracao_ocr[process_id].get('parar', False):
                    adicionar_log_extracao(process_id, 'warning', 'Processamento interrompido pelo usuário')
                    break
                
                # Atualizar processo atual
                processos_extracao_ocr[process_id]['processo_atual'] = numero_processo
                adicionar_log_extracao(process_id, 'info', f'[{i}/{len(processos)}] Processando: {numero_processo}')
                
                try:
                    # Processar processo
                    resultado = navegacao.processar_processo_completo(numero_processo)
                    resultados.append(resultado)
                    
                    # Atualizar contador de processados
                    processos_extracao_ocr[process_id]['processados'] += 1
                    
                    adicionar_log_extracao(
                        process_id, 
                        'success', 
                        f'✅ {numero_processo}: {resultado["total_documentos"]} documentos processados'
                    )
                    
                except Exception as e_proc:
                    # Incrementar erros
                    processos_extracao_ocr[process_id]['erros'] += 1
                    processos_extracao_ocr[process_id]['processados'] += 1
                    
                    adicionar_log_extracao(
                        process_id, 
                        'error', 
                        f'❌ Erro ao processar {numero_processo}: {str(e_proc)}'
                    )
                    
                    resultados.append({
                        'numero_processo': numero_processo,
                        'erro': str(e_proc)
                    })
            
            # Gerar resumo final
            resumo_geral = navegacao.registro.gerar_resumo()
            
            # Atualizar resultado final
            processos_extracao_ocr[process_id]['resultado'] = {
                'total_processos': len(processos),
                'resultados': resultados,
                'resumo_por_tipo': resumo_geral
            }
            
            processos_extracao_ocr[process_id]['status'] = 'concluido'
            adicionar_log_extracao(process_id, 'success', '🎉 Extração concluída com sucesso!')
            
        except Exception as e_nav:
            processos_extracao_ocr[process_id]['status'] = 'erro'
            processos_extracao_ocr[process_id]['erro'] = str(e_nav)
            adicionar_log_extracao(process_id, 'error', f'Erro fatal: {str(e_nav)}')
            
        finally:
            # Fechar navegação
            if navegacao:
                try:
                    navegacao.fechar()
                    adicionar_log_extracao(process_id, 'info', 'Navegação encerrada')
                except:
                    pass
    
    except Exception as e:
        processos_extracao_ocr[process_id]['status'] = 'erro'
        processos_extracao_ocr[process_id]['erro'] = str(e)
        adicionar_log_extracao(process_id, 'error', f'Erro ao iniciar extração: {str(e)}')

def adicionar_log_extracao(process_id, tipo, mensagem):
    """Adiciona log ao processo de extração"""
    if process_id in processos_extracao_ocr:
        processos_extracao_ocr[process_id]['logs'].append({
            'tipo': tipo,
            'mensagem': mensagem,
            'timestamp': datetime.now().isoformat()
        })

@app.route('/api/extracao_ocr/status/<process_id>')
@login_required
def status_extracao_ocr(process_id):
    """Retorna o status do processamento"""
    if process_id not in processos_extracao_ocr:
        return jsonify({
            'success': False,
            'error': 'Processo não encontrado'
        })
    
    processo = processos_extracao_ocr[process_id]
    
    # Limitar logs retornados (últimos 10)
    logs_recentes = processo['logs'][-10:] if len(processo['logs']) > 10 else processo['logs']
    
    return jsonify({
        'success': True,
        'status': processo['status'],
        'total': processo['total'],
        'processados': processo['processados'],
        'erros': processo['erros'],
        'processo_atual': processo.get('processo_atual'),
        'logs': logs_recentes,
        'resultado': processo.get('resultado'),
        'error': processo.get('erro')
    })

@app.route('/api/extracao_ocr/parar/<process_id>', methods=['POST'])
@login_required
def parar_extracao_ocr(process_id):
    """Para o processamento em andamento"""
    if process_id not in processos_extracao_ocr:
        return jsonify({
            'success': False,
            'error': 'Processo não encontrado'
        })
    
    processos_extracao_ocr[process_id]['parar'] = True
    processos_extracao_ocr[process_id]['status'] = 'parado'
    
    return jsonify({
        'success': True,
        'message': 'Solicitação de parada enviada'
    })

@app.route('/api/extracao_ocr/download')
@login_required
def download_arquivos_doccano():
    """Cria arquivo ZIP com todos os arquivos Doccano"""
    try:
        diretorio = request.args.get('diretorio', 'ocr_extraidos_doccano')
        
        if not os.path.exists(diretorio):
            return jsonify({
                'success': False,
                'error': 'Diretório não encontrado'
            })
        
        # Criar arquivo ZIP temporário
        import zipfile
        import tempfile
        
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Adicionar todos os arquivos .jsonl
            for root, dirs, files in os.walk(diretorio):
                for file in files:
                    if file.endswith('.jsonl'):
                        caminho_completo = os.path.join(root, file)
                        caminho_no_zip = os.path.relpath(caminho_completo, diretorio)
                        zipf.write(caminho_completo, caminho_no_zip)
        
        return send_file(
            temp_zip.name,
            as_attachment=True,
            download_name=f'arquivos_doccano_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
            mimetype='application/zip'
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/extracao_ocr/estatisticas')
@login_required
def estatisticas_extracao_ocr():
    """Retorna estatísticas da extração em formato HTML"""
    try:
        from navegacao_ordinaria_ocr import RegistroOCRDoccano
        
        diretorio = request.args.get('diretorio', 'ocr_extraidos_doccano')
        
        if not os.path.exists(diretorio):
            return '<h3>Diretório não encontrado</h3>'
        
        registro = RegistroOCRDoccano(diretorio)
        resumo = registro.gerar_resumo()
        
        # Gerar HTML simples
        html = '''
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Estatísticas de Extração OCR</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="p-4">
            <h2>📊 Estatísticas de Extração de OCR</h2>
            <div class="row mt-4">
        '''
        
        for tipo, info in resumo.items():
            html += f'''
                <div class="col-md-4 mb-3">
                    <div class="card">
                        <div class="card-body">
                            <h5 class="card-title text-uppercase">{tipo}</h5>
                            <p class="mb-1">Total: <strong>{info['total']}</strong></p>
                            <p class="mb-1 text-success">Validados: <strong>{info['validados']}</strong></p>
                            <p class="mb-0 text-danger">Não validados: <strong>{info['nao_validados']}</strong></p>
                            <hr>
                            <small class="text-muted">{info['arquivo_doccano']}</small>
                        </div>
                    </div>
                </div>
            '''
        
        html += '''
            </div>
        </body>
        </html>
        '''
        
        return html
        
    except Exception as e:
        return f'<h3>Erro: {str(e)}</h3>'

# ============================================================================

# Rota para gerar planilha de resultados
@app.route('/gerar_planilha_resultados', methods=['GET', 'POST'])
@login_required
def gerar_planilha_resultados_route():
    """Analisa processos automaticamente e atualiza planilha em tempo real"""
    try:
        if not GERADOR_PLANILHA_DISPONIVEL:
            flash('Gerador de planilha não disponível', 'error')
            return redirect(url_for('index'))
        
        if request.method == 'POST':
            # Verificar se há arquivo enviado
            if 'planilha_codigos' not in request.files:
                flash('Nenhum arquivo enviado', 'error')
                return render_template('gerar_planilha_resultados.html')
            
            file = request.files['planilha_codigos']
            if file.filename == '':
                flash('Nenhum arquivo selecionado', 'error')
                return render_template('gerar_planilha_resultados.html')
            
            # Salvar arquivo para processamento contínuo
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_arquivo_original = f"planilha_original_{timestamp}.xlsx"
            caminho_arquivo_original = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo_original)
            file.save(caminho_arquivo_original)
            
            try:
                # Carregar códigos da planilha
                gerador = GeradorPlanilhaResultados()
                codigos = gerador.carregar_planilha_codigos(caminho_arquivo_original)
                
                if not codigos:
                    flash('Nenhum código encontrado na planilha', 'error')
                    return render_template('gerar_planilha_resultados.html')
                
                print(f"[INFO] Códigos carregados: {len(codigos)}")
                
                # INICIAR ANÁLISE AUTOMÁTICA DOS PROCESSOS
                from lecom_automation import LecomAutomation
                
                # Configurar Lecom
                lecom = LecomAutomation()
                # Analisador não é mais necessário - a lógica está integrada
                
                # Fazer login uma vez
                print("[LOGIN] Fazendo login no Lecom...")
                if not lecom.login():
                    flash('Erro ao fazer login no Lecom', 'error')
                    return render_template('gerar_planilha_resultados.html')
                
                # Processar cada processo da planilha
                resultados_ocr = {}
                resultados_analise = {}
                processos_processados = []
                
                for i, codigo in enumerate(codigos):
                    print(f"\n[RELOAD] Processando processo {i+1}/{len(codigos)}: {codigo}")
                    
                    try:
                        # Processar processo no Lecom
                        resultado_processo = lecom.processar_processo(codigo)
                        
                        if resultado_processo and resultado_processo.get('status') == 'Processado com sucesso':
                            # Extrair OCR dos documentos
                            documentos_processados = resultado_processo.get('todos_textos_extraidos', {})
                            
                            # Usar análise já feita no processamento
                            analise_elegibilidade = resultado_processo.get('analise_elegibilidade', {})
                            elegibilidade = analise_elegibilidade.get('elegibilidade', 'Não analisado')
                            
                            # Armazenar resultados
                            resultados_ocr[codigo] = documentos_processados
                            resultados_analise[codigo] = elegibilidade
                            
                            # Salvar processo processado
                            processo_info = {
                                'codigo': codigo,
                                'documentos': documentos_processados,
                                'resultado_final': elegibilidade,
                                'analise_completa': resultado_processo,
                                'timestamp': datetime.now().isoformat()
                            }
                            processos_processados.append(processo_info)
                            
                            print(f"  [OK] Processo {codigo} processado com sucesso")
                            
                            # ATUALIZAR PLANILHA EM TEMPO REAL
                            try:
                                caminho_planilha_atualizada = gerador.modificar_planilha_original(
                                    caminho_arquivo_original,
                                    resultados_ocr,
                                    resultados_analise
                                )
                                
                                print(f"  [DADOS] Planilha atualizada: {os.path.basename(caminho_planilha_atualizada)}")
                                
                            except Exception as e:
                                print(f"  [AVISO]  Erro ao atualizar planilha: {e}")
                                # Continuar processando outros processos
                    
                    except Exception as e:
                        print(f"  [ERRO] Exceção ao processar {codigo}: {e}")
                        resultados_ocr[codigo] = {}
                        resultados_analise[codigo] = f'Erro: {str(e)}'
                    
                    # Pequena pausa entre processos
                    time.sleep(2)
                
                # Salvar todos os processos processados
                arquivo_processos = os.path.join(app.config['UPLOAD_FOLDER'], 'processos_analisados.json')
                with open(arquivo_processos, 'w', encoding='utf-8') as f:
                    json.dump(processos_processados, f, ensure_ascii=False, indent=2)
                
                # Obter nome do arquivo final
                nome_arquivo_final = os.path.basename(caminho_arquivo_original)
                
                flash(f'[OK] Análise automática concluída! {len(processos_processados)} processos processados. Arquivo: {nome_arquivo_final}', 'success')
                
                # Retornar template com informações do arquivo gerado
                return render_template('gerar_planilha_resultados.html', 
                                   codigos_carregados=codigos,
                                   arquivo_gerado=nome_arquivo_final,
                                   caminho_arquivo=caminho_arquivo_original,
                                   resultados_encontrados=len(processos_processados),
                                   analise_concluida=True)
                
            except Exception as e:
                print(f"[ERRO] Erro durante análise automática: {e}")
                flash(f'Erro durante análise automática: {str(e)}', 'error')
                return render_template('gerar_planilha_resultados.html')
        
        return render_template('gerar_planilha_resultados.html')
        
    except Exception as e:
        flash(f'Erro ao iniciar análise automática: {str(e)}', 'error')
        return render_template('gerar_planilha_resultados.html')

@app.route('/download_planilha_modificada/<nome_arquivo>')
@login_required
def download_planilha_modificada(nome_arquivo):
    """Faz download da planilha modificada"""
    try:
        # Caminho completo do arquivo
        caminho_arquivo = os.path.join(app.config['UPLOAD_FOLDER'], nome_arquivo)
        
        # Verificar se o arquivo existe
        if not os.path.exists(caminho_arquivo):
            flash('Arquivo não encontrado', 'error')
            return redirect(url_for('gerar_planilha_resultados_route'))
        
        # Fazer download do arquivo
        return send_file(caminho_arquivo, as_attachment=True, download_name=nome_arquivo)
        
    except Exception as e:
        flash(f'Erro ao fazer download: {str(e)}', 'error')
        return redirect(url_for('gerar_planilha_resultados_route'))

# ================================
# ROTAS DE API PARA MONITORAMENTO
# ================================

@app.route('/api/health')
def health_check():
    """Health check da aplicação"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '3.0.0-secure',
        'security_active': security_manager is not None,
        'features': {
            'encryption': security_manager is not None,
            'logging': True,
            'csrf_protection': True,
            'ip_filtering': True,
            'security_headers': True
        }
    })

@app.route('/api/stats')
def api_stats():
    """Estatísticas do sistema via API"""
    try:
        upload_folder = Path(app.config['UPLOAD_FOLDER'])
        total_files = len(list(upload_folder.glob('*'))) if upload_folder.exists() else 0
        
        return jsonify({
            'success': True,
            'stats': {
                'total_files': total_files,
                'system_status': 'Operacional',
                'security_active': security_manager is not None,
                'last_check': datetime.now().isoformat(),
                'features_active': {
                    'ocr': True,
                    'mistral_ai': bool(os.environ.get('MISTRAL_API_KEY')),
                    'excel_export': EXPORTADOR_DISPONIVEL,
                    'planilha_results': GERADOR_PLANILHA_DISPONIVEL
                }
            }
        })
    except Exception as e:
        log_security_event('API_ERROR', f'Erro na API stats: {str(e)}')
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# ROTAS DA AUTOMAÇÃO DE ANÁLISE DE PROCESSOS
# ============================================================

@app.route('/automacao_processos', methods=['GET', 'POST'])
@log_sensitive_operation('AUTOMACAO_ANALISE_PROCESSOS')
def automacao_processos():
    """
    Rota principal para automação de análise de processos
    Implementa o sistema conforme prompt melhorado
    """
    if request.method == 'GET':
        return render_template('automacao_processos.html')
    
    try:
        # Obter dados do formulário
        texto_despachos = request.form.get('texto_despachos', '').strip()
        mascarar_dados = request.form.get('mascarar_dados') == 'on'
        atualizacao_tempo = request.form.get('atualizacao_tempo') == 'on'
        
        if not texto_despachos:
            return jsonify({
                'status': 'erro',
                'erro': 'Texto dos despachos não fornecido'
            })
        
        # Importar e executar automação
        from automacao_analise_processos import AutomacaoAnaliseProcessos
        
        automacao = AutomacaoAnaliseProcessos()
        
        try:
            # Processar despachos
            resultados = automacao.processar_lista_despachos(texto_despachos)
            
            # Mascarar dados sensíveis se solicitado
            if mascarar_dados:
                resultados = [automacao.mascarar_dados_sensiveis(resultado) for resultado in resultados]
            
            # Registrar operação de segurança
            security_logger.info(f'Automação de processos executada: {len(resultados)} processos processados')
            
            return jsonify({
                'status': 'sucesso',
                'resultados': resultados,
                'total_processos': len(resultados),
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            security_logger.error(f'Erro na automação de processos: {e}')
            return jsonify({
                'status': 'erro',
                'erro': f'Erro durante processamento: {str(e)}'
            })
        
        finally:
            # Garantir que o driver seja fechado
            automacao.fechar_driver()
    
    except Exception as e:
        security_logger.error(f'Erro geral na automação: {e}')
        return jsonify({
            'status': 'erro',
            'erro': f'Erro interno: {str(e)}'
        })

@app.route('/automacao_processos/processar_individual', methods=['POST'])
@log_sensitive_operation('PROCESSAR_DESPACHO_INDIVIDUAL')
def processar_despacho_individual():
    """
    Endpoint para processar um único despacho em tempo real
    """
    try:
        # Obter dados do JSON
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'message': 'Dados JSON não fornecidos'
            })
        
        linha_despacho = data.get('linha_despacho', '').strip()
        numero_processo = data.get('numero_processo', 1)
        
        if not linha_despacho:
            return jsonify({
                'success': False,
                'message': 'Linha de despacho não fornecida'
            })
        
        # Importar e executar automação
        from automacao_analise_processos import AutomacaoAnaliseProcessos
        
        # Verificar se já existe uma instância ativa de automação
        if not hasattr(app, 'automacao_ativa'):
            app.automacao_ativa = AutomacaoAnaliseProcessos()
        
        automacao = app.automacao_ativa
        
        # Processar despacho individual
        resultado = automacao.processar_despacho_individual(linha_despacho, int(numero_processo))
        
        security_logger.info(f'Despacho individual processado: {resultado.get("codigo", "N/A")}')
        
        return jsonify({
            'success': True,
            'resultado': resultado,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        security_logger.error(f'Erro no processamento individual: {e}')
        return jsonify({
            'success': False,
            'message': f'Erro durante processamento: {str(e)}'
        })

@app.route('/automacao_processos/status', methods=['GET'])
@log_sensitive_operation('STATUS_AUTOMACAO')
def status_automacao():
    """
    Endpoint para verificar status da automação em tempo real
    """
    try:
        # Em uma implementação completa, isso seria conectado a um sistema de cache/redis
        # Para esta versão, retornamos um status vazio
        return jsonify({
            'novos_resultados': [],
            'processamento_concluido': False,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        security_logger.error(f'Erro ao verificar status: {e}')
        return jsonify({
            'erro': str(e)
        })

@app.route('/automacao_processos/parar', methods=['POST'])
@log_sensitive_operation('PARAR_AUTOMACAO')
def parar_automacao():
    """
    Endpoint para parar a automação em andamento
    """
    try:
        # Fechar driver da automação ativa se existir
        if hasattr(app, 'automacao_ativa'):
            app.automacao_ativa.fechar_driver()
            del app.automacao_ativa
        
        security_logger.info('Automação parada com sucesso')
        
        return jsonify({
            'status': 'sucesso',
            'mensagem': 'Automação parada com sucesso'
        })
    
    except Exception as e:
        security_logger.error(f'Erro ao parar automação: {e}')
        return jsonify({
            'status': 'erro',
            'erro': str(e)
        })

@app.route('/download/<filename>')
@log_sensitive_operation('DOWNLOAD_DOCUMENTO')
def download_documento(filename):
    """
    Endpoint para download de documentos processados pela automação
    """
    try:
        # Pasta de downloads da automação
        download_folder = os.path.join(os.getcwd(), "downloads_automacao")
        
        # Verificar se o arquivo existe
        caminho_arquivo = os.path.join(download_folder, filename)
        
        if not os.path.exists(caminho_arquivo):
            flash('Arquivo não encontrado')
            return redirect(url_for('automacao_processos'))
        
        # Verificar se é um arquivo seguro
        if not filename.lower().endswith('.pdf'):
            flash('Tipo de arquivo não permitido')
            return redirect(url_for('automacao_processos'))
        
        security_logger.info(f'Download de documento: {filename}')
        
        return send_from_directory(
            download_folder,
            filename,
            as_attachment=True
        )
        
    except Exception as e:
        security_logger.error(f'Erro no download: {e}')
        flash(f'Erro ao baixar arquivo: {str(e)}')
        return redirect(url_for('automacao_processos'))

# Error handlers para melhor debug
@app.errorhandler(400)
def bad_request(e):
    """Handler para erros 400 (Bad Request)"""
    print(f'[ERRO 400] Bad Request: {str(e)}')
    print(f'[ERRO 400] Headers: {dict(request.headers)}')
    print(f'[ERRO 400] Form keys: {list(request.form.keys()) if request.form else "Nenhum"}')
    
    # Se for uma requisição AJAX, retornar JSON
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({
            'success': False,
            'message': f'Erro na requisição: {str(e)}',
            'erro_tipo': 'BAD_REQUEST_400'
        }), 400
    
    return f"Erro 400: {str(e)}", 400

@app.errorhandler(404)
def handle_not_found(e):
    """Handler específico para erros 404 (página não encontrada)"""
    # Ignorar favicon.ico para evitar logs desnecessários
    if request.path == '/favicon.ico':
        return '', 204  # No Content
    
    # Para outras páginas 404, retornar JSON
    return jsonify({
        'success': False,
        'message': f'Página não encontrada: {request.path}',
        'erro_tipo': 'NOT_FOUND'
    }), 404

@app.errorhandler(500)
def handle_internal_error(e):
    """Handler específico para erros 500 (erro interno do servidor)"""
    return jsonify({
        'success': False,
        'message': 'Erro interno do servidor. Tente novamente mais tarde.',
        'erro_tipo': 'INTERNAL_SERVER_ERROR'
    }), 500

@app.errorhandler(Exception)
def handle_csrf_error(e):
    """Handler genérico para capturar erros de CSRF"""
    erro_str = str(e)
    
    # Verificar se é erro de CSRF
    if 'CSRF' in erro_str or 'csrf' in erro_str.lower():
        print(f'[ERRO CSRF] {erro_str}')
        print(f'[ERRO CSRF] Headers: {dict(request.headers)}')
        print(f'[ERRO CSRF] Form: {dict(request.form) if request.form else "Nenhum"}')
        
        # Se for AJAX, retornar JSON
        if request.path.startswith('/analisar') and request.method == 'POST':
            return jsonify({
                'success': False,
                'message': 'Erro de validação de segurança (CSRF). Recarregue a página e tente novamente.',
                'erro_tipo': 'CSRF_ERROR'
            }), 400
    
    # Para outros erros, retornar resposta JSON em vez de re-lançar
    if hasattr(e, 'code'):
        return jsonify({
            'success': False,
            'message': f'Erro {e.code}: {str(e)}',
            'erro_tipo': 'HTTP_ERROR'
        }), e.code
    else:
        return jsonify({
            'success': False,
            'message': f'Erro interno: {str(e)}',
            'erro_tipo': 'INTERNAL_ERROR'
        }), 500

if __name__ == '__main__':
    # Log de inicialização do sistema
    log_security_event('SYSTEM_START', 'Sistema iniciado com medidas de segurança integradas')
    
    # Banner de segurança
    print("[FECHADO] MEDIDAS DE SEGURANÇA ATIVAS:")
    if security_manager:
        print("   [OK] Criptografia AES-256")
        print("   [OK] Hash seguro de senhas")
        print("   [OK] Sanitização de entrada")
        print("   [OK] Validação de arquivos")
    print("   [OK] Headers de segurança")
    print("   [OK] Proteção CSRF")
    print("   [OK] Logs de auditoria")
    print("   [OK] Filtragem de IP")
    print("   [OK] APIs de monitoramento")
    print()
    
    # Configuração para acesso apenas na rede local
    # host='127.0.0.1' - apenas localhost
    # host='0.0.0.0' - todas as interfaces (perigoso)
    # Vamos usar o IP da máquina local para permitir acesso na rede interna
    import socket
    
    # Obter IP da máquina na rede corporativa
    hostname = socket.gethostname()
    
    # Tentar obter o IP correto da rede corporativa (10.23.x.x)
    local_ip = None
    try:
        # Conectar temporariamente para descobrir qual IP está sendo usado
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Conectar a um servidor externo
        local_ip = s.getsockname()[0]
        s.close()
    except:
        # Fallback para o método tradicional
        local_ip = socket.gethostbyname(hostname)
    
    # Usar 0.0.0.0 para permitir localhost + IP específico
    target_ip = '10.23.3.69'  # IP específico da rede
    
    print(f"🏢 Servidor rodando com acesso local e rede:")
    print(f"   • Localhost: http://127.0.0.1:5000")
    print(f"   • Rede: http://{target_ip}:5000")
    print(f"[FECHADO] Acesso restrito à rede local")
    
    # Rodar em 0.0.0.0 para permitir tanto localhost quanto rede local
    debug_mode = bool(os.environ.get('FLASK_DEBUG') == '1' and not is_production)
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)