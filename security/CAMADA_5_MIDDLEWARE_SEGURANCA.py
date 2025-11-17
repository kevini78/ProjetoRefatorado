#!/usr/bin/env python3
"""
CAMADA 5: MIDDLEWARE DE SEGURANÇA COM RATE LIMITING E VALIDAÇÃO
Arquivo: security_middleware.py
"""

from flask import request, g, current_app
import time
import logging
from functools import wraps
import re
import ipaddress
from collections import defaultdict, deque
from datetime import datetime, timedelta

class SecurityMiddleware:
    """
    Middleware de segurança para interceptar requisições e aplicar medidas de proteção
    CAMADA 5: Middleware de segurança com rate limiting e validação
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.rate_limits = defaultdict(lambda: deque())
        self.blocked_ips = {}
        self.setup_middleware(app)
        
    def setup_middleware(self, app):
        """Configura os middlewares de segurança"""
        # Restrição por IP/CIDR (intranet)
        allow_ips_env = None
        allow_cidrs_env = None
        try:
            import os
            allow_ips_env = os.environ.get('ALLOW_IPS', '').strip()
            allow_cidrs_env = os.environ.get('ALLOW_CIDRS', '').strip()
        except Exception:
            pass

        allow_ips = [ip.strip() for ip in allow_ips_env.split(',') if ip.strip()] if allow_ips_env else []
        allow_cidrs = [c.strip() for c in allow_cidrs_env.split(',') if c.strip()] if allow_cidrs_env else []

        networks = []
        if allow_cidrs:
            try:
                networks = [ipaddress.ip_network(cidr, strict=False) for cidr in allow_cidrs]
            except Exception:
                networks = []

        @app.before_request
        def _restrict_by_ip():
            # Se nenhuma restrição configurada, não bloqueia
            if not allow_ips and not networks:
                return None

            try:
                client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                # Pode haver múltiplos IPs em X-Forwarded-For
                if client_ip and ',' in client_ip:
                    client_ip = client_ip.split(',')[0].strip()

                # Libera IPs exatos
                if client_ip in allow_ips:
                    return None

                # Libera por redes CIDR
                if networks:
                    ip_obj = ipaddress.ip_address(client_ip)
                    if any(ip_obj in net for net in networks):
                        return None

                # Caso contrário, bloqueia
                from flask import abort
                return abort(403)
            except Exception:
                # Em caso de falha na verificação, por segurança bloquear
                from flask import abort
                return abort(403)

        @app.before_request
        def _rate_limiting():
            """Implementa rate limiting por IP"""
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if client_ip and ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            
            # Verificar se IP está bloqueado
            if client_ip in self.blocked_ips:
                if datetime.now() < self.blocked_ips[client_ip]:
                    from flask import abort
                    return abort(429)  # Too Many Requests
                else:
                    # Remover bloqueio expirado
                    del self.blocked_ips[client_ip]
            
            # Rate limiting: máximo 60 requisições por minuto
            now = time.time()
            minute_ago = now - 60
            
            # Limpar requisições antigas
            while self.rate_limits[client_ip] and self.rate_limits[client_ip][0] < minute_ago:
                self.rate_limits[client_ip].popleft()
            
            # Verificar limite
            if len(self.rate_limits[client_ip]) >= 60:
                # Bloquear IP por 30 minutos
                self.blocked_ips[client_ip] = datetime.now() + timedelta(minutes=30)
                self.logger.warning(f"IP {client_ip} bloqueado por excesso de requisições")
                from flask import abort
                return abort(429)
            
            # Adicionar requisição atual
            self.rate_limits[client_ip].append(now)

        @app.before_request
        def _validate_request():
            """Valida requisições para detectar ataques"""
            # Verificar headers suspeitos
            suspicious_headers = [
                'X-Forwarded-Host',
                'X-Original-URL',
                'X-Rewrite-URL'
            ]
            
            for header in suspicious_headers:
                if header in request.headers:
                    self.logger.warning(f"Header suspeito detectado: {header}")
            
            # Verificar User-Agent suspeito
            user_agent = request.headers.get('User-Agent', '')
            if not user_agent or len(user_agent) < 10:
                self.logger.warning(f"User-Agent suspeito: {user_agent}")
            
            # Verificar tamanho da requisição
            content_length = request.headers.get('Content-Length')
            if content_length and int(content_length) > 16 * 1024 * 1024:  # 16MB
                self.logger.warning(f"Requisição muito grande: {content_length} bytes")
                from flask import abort
                return abort(413)  # Payload Too Large

        @app.after_request
        def _add_security_headers(response):
            """Adiciona headers de segurança às respostas"""
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            return response

def require_authentication(f):
    """Decorator para exigir autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        if not current_user.is_authenticated:
            from flask import redirect, url_for
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    """Decorator para exigir privilégios de admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        if not current_user.is_authenticated or current_user.name != 'admin':
            from flask import redirect, url_for
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def log_sensitive_operation(operation_type):
    """Decorator para registrar operações sensíveis"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log da operação
            try:
                from flask_login import current_user
                user_id = current_user.name if current_user.is_authenticated else 'anonymous'
                logger = logging.getLogger('audit')
                logger.info(f"SENSITIVE_OPERATION: {operation_type} by {user_id} at {request.path}")
            except:
                pass  # Não falhar se o log não funcionar
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_file_upload(f):
    """Decorator para validar uploads de arquivo"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar se há arquivo na requisição
        if 'file' not in request.files:
            from flask import jsonify
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        file = request.files['file']
        
        # Verificar se arquivo foi selecionado
        if file.filename == '':
            from flask import jsonify
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Verificar extensão do arquivo
        allowed_extensions = {'png', 'jpg', 'jpeg', 'pdf'}
        if not ('.' in file.filename and 
                file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            from flask import jsonify
            return jsonify({'error': 'Tipo de arquivo não permitido'}), 400
        
        # Verificar tamanho do arquivo
        file.seek(0, 2)  # Ir para o final do arquivo
        file_size = file.tell()
        file.seek(0)  # Voltar para o início
        
        if file_size > 16 * 1024 * 1024:  # 16MB
            from flask import jsonify
            return jsonify({'error': 'Arquivo muito grande'}), 400
        
        return f(*args, **kwargs)
    return decorated_function

def sanitize_input(input_data):
    """Sanitiza entrada do usuário"""
    if isinstance(input_data, str):
        # Remover caracteres perigosos
        input_data = re.sub(r'[<>"\']', '', input_data)
        # Limitar tamanho
        input_data = input_data[:1000]
    return input_data

def validate_json_input(f):
    """Decorator para validar entrada JSON"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.is_json:
            try:
                data = request.get_json()
                # Sanitizar dados JSON
                sanitized_data = {}
                for key, value in data.items():
                    sanitized_key = sanitize_input(str(key))
                    if isinstance(value, str):
                        sanitized_value = sanitize_input(value)
                    else:
                        sanitized_value = value
                    sanitized_data[sanitized_key] = sanitized_value
                
                # Substituir dados originais pelos sanitizados
                request._cached_json = sanitized_data
            except Exception as e:
                from flask import jsonify
                return jsonify({'error': 'JSON inválido'}), 400
        
        return f(*args, **kwargs)
    return decorated_function
