from flask import request, g, current_app
import time
import logging
from functools import wraps

try:
    from security_config_flexible import flexible_security_config as security_config
except ImportError:
    try:
        from security_config import security_config
    except ImportError:
        security_config = None

import re

class SecurityMiddleware:
    """
    Middleware de segurança para interceptar requisições e aplicar medidas de proteção
    """
    
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.setup_middleware(app)
        
    def setup_middleware(self, app):
        """Configura os middlewares de segurança"""
        # Restrição por IP/CIDR (intranet)
        # Variáveis de ambiente:
        # ALLOW_IPS: lista separada por vírgulas de IPs exatos (ex.: "127.0.0.1,10.0.0.5")
        # ALLOW_CIDRS: lista separada por vírgulas de redes CIDR (ex.: "10.0.0.0/8,192.168.0.0/16")
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
                import ipaddress
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
                    import ipaddress
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
            # Log da operação se disponível
            if security_config:
                try:
                    from flask_login import current_user
                    user_id = current_user.name if current_user.is_authenticated else 'anonymous'
                    security_config.log_access(
                        user_id=user_id,
                        action=operation_type,
                        resource=request.path,
                        success=True
                    )
                except:
                    pass  # Não falhar se o log não funcionar
            return f(*args, **kwargs)
        return decorated_function
    return decorator 