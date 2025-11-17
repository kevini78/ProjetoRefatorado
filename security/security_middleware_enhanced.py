"""
Middleware de Segurança Avançado - Conformidade Posic/MCTIC
"""

import time
import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from flask import request, Response, g, current_app, jsonify, abort
from functools import wraps
import ipaddress
from .security_config_enhanced import enhanced_security

class SecurityMiddlewareEnhanced:
    """
    Middleware de segurança avançado implementando:
    - Rate limiting por IP e usuário
    - Detecção de ataques (SQL Injection, XSS, etc.)
    - Análise comportamental
    - Headers de segurança HTTP
    - Proteção CSRF avançada
    - Monitoramento de anomalias
    """
    
    def __init__(self, app=None):
        self.app = app
        self.rate_limiter = RateLimiter()
        self.attack_detector = AttackDetector()
        self.behavioral_analyzer = BehavioralAnalyzer()
        self.security_headers = SecurityHeaders()
        
        if app:
            self.init_app(app)
            
    def init_app(self, app):
        """Inicializa middleware com aplicação Flask"""
        self.app = app
        
        # Registrar middlewares
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        
    def before_request(self):
        """Executa antes de cada requisição"""
        start_time = time.time()
        g.request_start_time = start_time
        
        # 1. Validar IP de origem
        if not self._validate_ip_access():
            enhanced_security.log_security_event(
                'IP_BLOCKED',
                'unknown',
                {'ip': request.remote_addr, 'reason': 'ip_not_allowed'},
                request.remote_addr
            )
            abort(403)
            
        # 2. Rate limiting
        if not self.rate_limiter.is_allowed(request.remote_addr, request.endpoint):
            enhanced_security.log_security_event(
                'RATE_LIMIT_EXCEEDED',
                getattr(g, 'current_user', {}).get('username', 'unknown'),
                {'ip': request.remote_addr, 'endpoint': request.endpoint},
                request.remote_addr
            )
            abort(429)
            
        # 3. Detecção de ataques
        attack_type = self.attack_detector.detect_attack(request)
        if attack_type:
            enhanced_security.log_security_event(
                'ATTACK_DETECTED',
                getattr(g, 'current_user', {}).get('username', 'unknown'),
                {
                    'attack_type': attack_type,
                    'ip': request.remote_addr,
                    'endpoint': request.endpoint,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'payload': str(request.get_data())[:1000]  # Limitar tamanho
                },
                request.remote_addr
            )
            abort(400)
            
        # 4. Análise comportamental
        self.behavioral_analyzer.analyze_request(request)
        
        # 5. Validação de entrada
        self._validate_request_data()
        
    def after_request(self, response: Response) -> Response:
        """Executa após cada requisição"""
        # 1. Adicionar headers de segurança
        response = self.security_headers.add_headers(response)
        
        # 2. Log da requisição
        self._log_request(response)
        
        # 3. Atualizar rate limiter
        self.rate_limiter.record_request(request.remote_addr, request.endpoint)
        
        return response
        
    def _validate_ip_access(self) -> bool:
        """Valida se IP tem permissão de acesso"""
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()
            
        return enhanced_security.validate_ip_access(client_ip)
        
    def _validate_request_data(self):
        """Valida dados da requisição"""
        try:
            # Validar tamanho da requisição
            if request.content_length and request.content_length > 50 * 1024 * 1024:  # 50MB
                enhanced_security.log_security_event(
                    'REQUEST_TOO_LARGE',
                    getattr(g, 'current_user', {}).get('username', 'unknown'),
                    {'size': request.content_length},
                    request.remote_addr
                )
                abort(413)
                
            # Validar headers suspeitos
            suspicious_headers = ['X-Forwarded-Host', 'X-Original-URL', 'X-Rewrite-URL']
            for header in suspicious_headers:
                if header in request.headers:
                    enhanced_security.log_security_event(
                        'SUSPICIOUS_HEADER',
                        getattr(g, 'current_user', {}).get('username', 'unknown'),
                        {'header': header, 'value': request.headers[header]},
                        request.remote_addr
                    )
                    
        except Exception as e:
            enhanced_security.logger.error(f"Erro na validação da requisição: {e}")
            
    def _log_request(self, response: Response):
        """Registra log da requisição"""
        try:
            duration = time.time() - g.request_start_time
            
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'method': request.method,
                'endpoint': request.endpoint,
                'path': request.path,
                'ip': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', ''),
                'status_code': response.status_code,
                'duration_ms': round(duration * 1000, 2),
                'user': getattr(g, 'current_user', {}).get('username', 'anonymous')
            }
            
            # Log adicional para operações sensíveis
            if request.endpoint in ['upload', 'download', 'delete', 'admin']:
                enhanced_security.log_security_event(
                    'SENSITIVE_OPERATION',
                    log_data['user'],
                    log_data,
                    request.remote_addr
                )
                
        except Exception as e:
            enhanced_security.logger.error(f"Erro no log da requisição: {e}")

class RateLimiter:
    """Sistema de rate limiting"""
    
    def __init__(self):
        self.requests = {}  # {ip: {endpoint: [timestamps]}}
        self.limits = {
            'default': {'requests': 100, 'window': 3600},  # 100 req/hora
            'login': {'requests': 5, 'window': 900},        # 5 req/15min
            'upload': {'requests': 10, 'window': 3600},     # 10 req/hora
            'api': {'requests': 1000, 'window': 3600}       # 1000 req/hora
        }
        
    def is_allowed(self, ip: str, endpoint: str) -> bool:
        """Verifica se requisição é permitida"""
        try:
            current_time = time.time()
            
            # Determinar limite baseado no endpoint
            limit_key = 'default'
            if endpoint:
                if 'login' in endpoint:
                    limit_key = 'login'
                elif 'upload' in endpoint:
                    limit_key = 'upload'
                elif 'api' in endpoint:
                    limit_key = 'api'
                    
            limit = self.limits[limit_key]
            
            # Inicializar se necessário
            if ip not in self.requests:
                self.requests[ip] = {}
            if endpoint not in self.requests[ip]:
                self.requests[ip][endpoint] = []
                
            # Limpar requisições antigas
            cutoff_time = current_time - limit['window']
            self.requests[ip][endpoint] = [
                t for t in self.requests[ip][endpoint] 
                if t > cutoff_time
            ]
            
            # Verificar limite
            return len(self.requests[ip][endpoint]) < limit['requests']
            
        except Exception as e:
            enhanced_security.logger.error(f"Erro no rate limiter: {e}")
            return True  # Permitir em caso de erro
            
    def record_request(self, ip: str, endpoint: str):
        """Registra requisição"""
        try:
            current_time = time.time()
            
            if ip not in self.requests:
                self.requests[ip] = {}
            if endpoint not in self.requests[ip]:
                self.requests[ip][endpoint] = []
                
            self.requests[ip][endpoint].append(current_time)
            
        except Exception as e:
            enhanced_security.logger.error(f"Erro ao registrar requisição: {e}")

class AttackDetector:
    """Detector de ataques"""
    
    def __init__(self):
        # Padrões de SQL Injection
        self.sql_patterns = [
            r"(?i)(union\s+select)",
            r"(?i)(drop\s+table)",
            r"(?i)(delete\s+from)",
            r"(?i)(insert\s+into)",
            r"(?i)(update\s+.+set)",
            r"(?i)(exec\s*\()",
            r"(?i)(\'\s*or\s*\'1\'\s*=\s*\'1)",
            r"(?i)(\'\s*or\s*1\s*=\s*1)",
            r"(?i)(--\s*$)",
            r"(?i)(/\*.*\*/)"
        ]
        
        # Padrões de XSS
        self.xss_patterns = [
            r"(?i)(<script[^>]*>)",
            r"(?i)(</script>)",
            r"(?i)(javascript:)",
            r"(?i)(on\w+\s*=)",
            r"(?i)(<iframe[^>]*>)",
            r"(?i)(<object[^>]*>)",
            r"(?i)(<embed[^>]*>)",
            r"(?i)(eval\s*\()",
            r"(?i)(alert\s*\()",
            r"(?i)(document\.cookie)",
            r"(?i)(window\.location)"
        ]
        
        # Padrões de Path Traversal
        self.path_traversal_patterns = [
            r"\.\.\/",
            r"\.\.\\\\",
            r"\/etc\/passwd",
            r"\/proc\/",
            r"\\\\windows\\\\system32",
            r"%2e%2e%2f",
            r"%2e%2e\\\\",
            r"..%c0%af",
            r"..%c1%9c"
        ]
        
        # Padrões de Command Injection
        self.command_injection_patterns = [
            r"(?i)(;\s*cat\s)",
            r"(?i)(;\s*ls\s)",
            r"(?i)(;\s*pwd\s)",
            r"(?i)(;\s*whoami)",
            r"(?i)(\|\s*cat\s)",
            r"(?i)(\&\&\s*cat\s)",
            r"(?i)(;\s*rm\s)",
            r"(?i)(;\s*chmod\s)",
            r"(?i)(;\s*wget\s)",
            r"(?i)(;\s*curl\s)"
        ]
        
    def detect_attack(self, request) -> Optional[str]:
        """Detecta tipo de ataque na requisição"""
        try:
            # Obter todos os dados da requisição
            data_sources = []
            
            # Query parameters
            if request.args:
                for key, value in request.args.items():
                    data_sources.append(str(value))
                    
            # Form data
            if request.form:
                for key, value in request.form.items():
                    data_sources.append(str(value))
                    
            # JSON data
            if request.is_json and request.get_json():
                data_sources.append(str(request.get_json()))
                
            # Headers suspeitos
            suspicious_headers = ['User-Agent', 'Referer', 'X-Forwarded-For']
            for header in suspicious_headers:
                if header in request.headers:
                    data_sources.append(request.headers[header])
                    
            # Path da URL
            data_sources.append(request.path)
            
            # Verificar cada fonte de dados
            for data in data_sources:
                if not data:
                    continue
                    
                # SQL Injection
                for pattern in self.sql_patterns:
                    if re.search(pattern, data):
                        return 'SQL_INJECTION'
                        
                # XSS
                for pattern in self.xss_patterns:
                    if re.search(pattern, data):
                        return 'XSS'
                        
                # Path Traversal
                for pattern in self.path_traversal_patterns:
                    if re.search(pattern, data):
                        return 'PATH_TRAVERSAL'
                        
                # Command Injection
                for pattern in self.command_injection_patterns:
                    if re.search(pattern, data):
                        return 'COMMAND_INJECTION'
                        
            return None
            
        except Exception as e:
            enhanced_security.logger.error(f"Erro na detecção de ataques: {e}")
            return None

class BehavioralAnalyzer:
    """Analisador de comportamento"""
    
    def __init__(self):
        self.user_patterns = {}  # {user_id: pattern_data}
        self.suspicious_threshold = 0.8
        
    def analyze_request(self, request):
        """Analisa padrão comportamental da requisição"""
        try:
            user_id = getattr(g, 'current_user', {}).get('id', request.remote_addr)
            current_time = time.time()
            
            # Inicializar padrões do usuário
            if user_id not in self.user_patterns:
                self.user_patterns[user_id] = {
                    'requests': [],
                    'endpoints': {},
                    'user_agents': set(),
                    'ips': set(),
                    'request_intervals': []
                }
                
            patterns = self.user_patterns[user_id]
            
            # Registrar requisição
            patterns['requests'].append(current_time)
            
            # Registrar endpoint
            endpoint = request.endpoint or 'unknown'
            patterns['endpoints'][endpoint] = patterns['endpoints'].get(endpoint, 0) + 1
            
            # Registrar User-Agent
            user_agent = request.headers.get('User-Agent', '')
            patterns['user_agents'].add(user_agent)
            
            # Registrar IP
            patterns['ips'].add(request.remote_addr)
            
            # Calcular intervalos entre requisições
            if len(patterns['requests']) >= 2:
                interval = patterns['requests'][-1] - patterns['requests'][-2]
                patterns['request_intervals'].append(interval)
                
            # Limpar dados antigos (últimas 24 horas)
            cutoff = current_time - 86400
            patterns['requests'] = [t for t in patterns['requests'] if t > cutoff]
            patterns['request_intervals'] = patterns['request_intervals'][-100:]
            
            # Analisar anomalias
            self._detect_anomalies(user_id, patterns, request)
            
        except Exception as e:
            enhanced_security.logger.error(f"Erro na análise comportamental: {e}")
            
    def _detect_anomalies(self, user_id: str, patterns: Dict, request):
        """Detecta anomalias comportamentais"""
        try:
            anomalies = []
            
            # 1. Múltiplos User-Agents
            if len(patterns['user_agents']) > 5:
                anomalies.append('multiple_user_agents')
                
            # 2. Múltiplos IPs
            if len(patterns['ips']) > 3:
                anomalies.append('multiple_ips')
                
            # 3. Requisições muito frequentes
            recent_requests = [t for t in patterns['requests'] if t > time.time() - 300]  # 5 min
            if len(recent_requests) > 50:
                anomalies.append('high_frequency_requests')
                
            # 4. Intervalos suspeitos (muito regulares = bot)
            if len(patterns['request_intervals']) >= 10:
                avg_interval = sum(patterns['request_intervals'][-10:]) / 10
                variance = sum((i - avg_interval) ** 2 for i in patterns['request_intervals'][-10:]) / 10
                if variance < 0.1:  # Muito regular
                    anomalies.append('regular_intervals_bot')
                    
            # 5. Acesso a endpoints sensíveis incomuns
            sensitive_endpoints = ['admin', 'config', 'debug', 'test']
            for endpoint in sensitive_endpoints:
                if endpoint in patterns['endpoints'] and patterns['endpoints'][endpoint] > 10:
                    anomalies.append(f'excessive_access_to_{endpoint}')
                    
            # Log anomalias
            if anomalies:
                enhanced_security.log_security_event(
                    'BEHAVIORAL_ANOMALY',
                    user_id,
                    {
                        'anomalies': anomalies,
                        'user_agents_count': len(patterns['user_agents']),
                        'ips_count': len(patterns['ips']),
                        'recent_requests_count': len(recent_requests)
                    },
                    request.remote_addr
                )
                
        except Exception as e:
            enhanced_security.logger.error(f"Erro na detecção de anomalias: {e}")

class SecurityHeaders:
    """Gerenciador de headers de segurança"""
    
    def add_headers(self, response: Response) -> Response:
        """Adiciona headers de segurança HTTP"""
        try:
            # Headers básicos de segurança
            security_headers = enhanced_security.get_security_headers()
            
            for header, value in security_headers.items():
                response.headers[header] = value
                
            # Headers adicionais baseados no conteúdo
            self._add_content_specific_headers(response)
            
            return response
            
        except Exception as e:
            enhanced_security.logger.error(f"Erro ao adicionar headers de segurança: {e}")
            return response
            
    def _add_content_specific_headers(self, response: Response):
        """Adiciona headers específicos baseados no tipo de conteúdo"""
        try:
            content_type = response.headers.get('Content-Type', '')
            
            # Para responses JSON
            if 'application/json' in content_type:
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'
                
            # Para downloads de arquivo
            if 'application/octet-stream' in content_type:
                response.headers['X-Download-Options'] = 'noopen'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                
        except Exception as e:
            enhanced_security.logger.error(f"Erro ao adicionar headers específicos: {e}")

# Instância global
security_middleware_enhanced = SecurityMiddlewareEnhanced()

# Decoradores adicionais
def monitor_sensitive_operation(operation_type: str):
    """Decorador para monitorar operações sensíveis"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = f(*args, **kwargs)
                duration = time.time() - start_time
                
                enhanced_security.log_security_event(
                    'SENSITIVE_OPERATION_SUCCESS',
                    getattr(g, 'current_user', {}).get('username', 'unknown'),
                    {
                        'operation': operation_type,
                        'duration_ms': round(duration * 1000, 2),
                        'endpoint': request.endpoint
                    },
                    request.remote_addr
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                enhanced_security.log_security_event(
                    'SENSITIVE_OPERATION_FAILURE',
                    getattr(g, 'current_user', {}).get('username', 'unknown'),
                    {
                        'operation': operation_type,
                        'error': str(e),
                        'duration_ms': round(duration * 1000, 2),
                        'endpoint': request.endpoint
                    },
                    request.remote_addr
                )
                
                raise
                
        return decorated_function
    return decorator
