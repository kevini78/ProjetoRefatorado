from functools import wraps
from flask import request, jsonify, current_app

try:
    from flask_login import current_user
except Exception:
    current_user = None


def api_login_required(f):
    """API login guard. Returns JSON 401 if not authenticated. No-op if Flask-Login not configured."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # If flask-login not available, allow in dev
        if current_user is None:
            return f(*args, **kwargs)
        try:
            if not current_user.is_authenticated:
                return jsonify({
                    'success': False,
                    'message': 'Não autenticado',
                    'redirect': '/login'
                }), 401
        except Exception:
            # Be permissive if user object is not standard
            pass
        return f(*args, **kwargs)
    return wrapper


def require_authentication(f):
    """Web guard. Redirects responsibility left to caller; here we return JSON 401 for APIs."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user is None:
            return f(*args, **kwargs)
        try:
            if not current_user.is_authenticated:
                return jsonify({'success': False, 'message': 'Não autenticado'}), 401
        except Exception:
            pass
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    """Simple admin gate. Allows if user has is_admin attribute truthy; otherwise 403."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if current_user is None:
            return f(*args, **kwargs)
        try:
            if not getattr(current_user, 'is_admin', False):
                return jsonify({'success': False, 'message': 'Acesso restrito'}), 403
        except Exception:
            pass
        return f(*args, **kwargs)
    return wrapper


def log_sensitive_operation(operation: str):
    """Decorator to log sensitive operations uniformly."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                current_app.logger.info(f'SECURITY_OP {operation} path={request.path} method={request.method}')
            except Exception:
                pass
            return func(*args, **kwargs)
        return wrapper
    return decorator
