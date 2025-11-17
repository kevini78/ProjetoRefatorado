"""
Módulos de Segurança do Sistema de Automação MJSP
Pacote contendo todas as 10 camadas de segurança implementadas
"""

# Importar módulos principais
from .security_config import security_config
from .security_middleware import SecurityMiddleware, require_authentication, require_admin, log_sensitive_operation
from .data_sanitizer import data_sanitizer

# Importar módulos de conformidade LGPD
try:
    from .lgpd_compliance import lgpd_system
except ImportError:
    lgpd_system = None

# Importar módulos de segurança avançada
try:
    from .security_config_enhanced import enhanced_security
except ImportError:
    enhanced_security = None

try:
    from .security_config_flexible import flexible_security_config
except ImportError:
    flexible_security_config = None

# Lista de módulos disponíveis
__all__ = [
    'security_config',
    'SecurityMiddleware',
    'require_authentication',
    'require_admin',
    'log_sensitive_operation',
    'data_sanitizer',
    'lgpd_system',
    'enhanced_security',
    'flexible_security_config'
]

# Informações do pacote
__version__ = '1.0.0'
__author__ = 'Sistema de Automação MJSP'
__description__ = 'Módulos de segurança enterprise-grade para análise de processos migratórios'
