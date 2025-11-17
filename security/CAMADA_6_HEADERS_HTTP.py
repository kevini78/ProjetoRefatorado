#!/usr/bin/env python3
"""
CAMADA 6: HEADERS HTTP DE PROTEÇÃO CONTRA ATAQUES
Implementado em security_config.py e security_middleware.py
"""

from flask import request, g, current_app
from functools import wraps

class HTTPHeadersSecurity:
    """
    Classe para implementar headers de segurança HTTP
    CAMADA 6: Headers HTTP de proteção contra ataques
    """
    
    @staticmethod
    def get_security_headers() -> dict:
        """
        Retorna headers de segurança para respostas HTTP
        
        Returns:
            Dict com headers de segurança
        """
        return {
            # Previne MIME type sniffing
            'X-Content-Type-Options': 'nosniff',
            
            # Previne clickjacking
            'X-Frame-Options': 'DENY',
            
            # Ativa proteção XSS do navegador
            'X-XSS-Protection': '1; mode=block',
            
            # Força HTTPS (HSTS)
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            
            # Política de segurança de conteúdo
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
            
            # Política de referrer
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            
            # Permissões de recursos
            'Permissions-Policy': (
                "geolocation=(), "
                "microphone=(), "
                "camera=(), "
                "payment=(), "
                "usb=(), "
                "magnetometer=(), "
                "gyroscope=(), "
                "speaker=()"
            ),
            
            # Cache control para dados sensíveis
            'Cache-Control': 'no-store, no-cache, must-revalidate, private',
            'Pragma': 'no-cache',
            'Expires': '0',
            
            # Previne vazamento de informações do servidor
            'Server': 'Secure-Server',
            
            # Política de recursos de origem cruzada
            'Cross-Origin-Embedder-Policy': 'require-corp',
            'Cross-Origin-Opener-Policy': 'same-origin',
            'Cross-Origin-Resource-Policy': 'same-origin'
        }
    
    @staticmethod
    def add_security_headers(response):
        """
        Adiciona headers de segurança a uma resposta HTTP
        
        Args:
            response: Objeto de resposta Flask
            
        Returns:
            Resposta com headers de segurança adicionados
        """
        headers = HTTPHeadersSecurity.get_security_headers()
        
        for header, value in headers.items():
            response.headers[header] = value
        
        return response
    
    @staticmethod
    def validate_request_headers(request):
        """
        Valida headers de requisição para detectar ataques
        
        Args:
            request: Objeto de requisição Flask
            
        Returns:
            Tuple (is_valid, error_message)
        """
        # Verificar headers suspeitos
        suspicious_headers = [
            'X-Forwarded-Host',
            'X-Original-URL',
            'X-Rewrite-URL',
            'X-Forwarded-Proto',
            'X-Forwarded-Port'
        ]
        
        for header in suspicious_headers:
            if header in request.headers:
                return False, f"Header suspeito detectado: {header}"
        
        # Verificar User-Agent
        user_agent = request.headers.get('User-Agent', '')
        if not user_agent or len(user_agent) < 10:
            return False, "User-Agent suspeito ou ausente"
        
        # Verificar Accept header
        accept = request.headers.get('Accept', '')
        if not accept or '*' not in accept:
            return False, "Accept header suspeito"
        
        # Verificar Content-Type para requisições POST/PUT
        if request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if not content_type:
                return False, "Content-Type ausente para requisição com corpo"
        
        return True, None
    
    @staticmethod
    def get_csp_policy(environment='production'):
        """
        Retorna política de segurança de conteúdo baseada no ambiente
        
        Args:
            environment: Ambiente ('development', 'production')
            
        Returns:
            String com política CSP
        """
        if environment == 'development':
            return (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self' ws: wss:; "
                "frame-ancestors 'none'"
            )
        else:
            return (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            )
    
    @staticmethod
    def get_hsts_header(max_age=31536000, include_subdomains=True, preload=False):
        """
        Retorna header HSTS (HTTP Strict Transport Security)
        
        Args:
            max_age: Tempo em segundos (padrão: 1 ano)
            include_subdomains: Incluir subdomínios
            preload: Incluir diretiva preload
            
        Returns:
            String com header HSTS
        """
        hsts = f"max-age={max_age}"
        
        if include_subdomains:
            hsts += "; includeSubDomains"
        
        if preload:
            hsts += "; preload"
        
        return hsts
    
    @staticmethod
    def get_cors_headers(allowed_origins=None, allow_credentials=True):
        """
        Retorna headers CORS seguros
        
        Args:
            allowed_origins: Lista de origens permitidas
            allow_credentials: Permitir credenciais
            
        Returns:
            Dict com headers CORS
        """
        if allowed_origins is None:
            allowed_origins = ['https://localhost:5000', 'https://127.0.0.1:5000']
        
        return {
            'Access-Control-Allow-Origin': ', '.join(allowed_origins),
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With',
            'Access-Control-Allow-Credentials': 'true' if allow_credentials else 'false',
            'Access-Control-Max-Age': '86400'  # 24 horas
        }

def add_security_headers_decorator(f):
    """
    Decorator para adicionar headers de segurança automaticamente
    
    Args:
        f: Função a ser decorada
        
    Returns:
        Função decorada com headers de segurança
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import make_response
        
        # Executar função original
        result = f(*args, **kwargs)
        
        # Se resultado é uma resposta, adicionar headers
        if hasattr(result, 'headers'):
            return HTTPHeadersSecurity.add_security_headers(result)
        else:
            # Criar resposta e adicionar headers
            response = make_response(result)
            return HTTPHeadersSecurity.add_security_headers(response)
    
    return decorated_function

def validate_headers_decorator(f):
    """
    Decorator para validar headers de requisição
    
    Args:
        f: Função a ser decorada
        
    Returns:
        Função decorada com validação de headers
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Validar headers da requisição
        is_valid, error_message = HTTPHeadersSecurity.validate_request_headers(request)
        
        if not is_valid:
            from flask import jsonify
            return jsonify({'error': error_message}), 400
        
        return f(*args, **kwargs)
    
    return decorated_function

# Exemplo de uso em uma aplicação Flask
def setup_security_headers(app):
    """
    Configura headers de segurança para uma aplicação Flask
    
    Args:
        app: Instância da aplicação Flask
    """
    @app.after_request
    def add_security_headers(response):
        return HTTPHeadersSecurity.add_security_headers(response)
    
    @app.before_request
    def validate_headers():
        is_valid, error_message = HTTPHeadersSecurity.validate_request_headers(request)
        if not is_valid:
            from flask import jsonify
            return jsonify({'error': error_message}), 400
        return None
