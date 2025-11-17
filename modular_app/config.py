"""Configurações tipadas da aplicação usando dataclasses.

Este módulo define as configurações da aplicação com tipagem forte,
validação automática e suporte a múltiplos ambientes.
"""
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SecurityConfig:
    """Configurações de segurança da aplicação."""
    
    csp_policy: str = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    allowed_ips: List[str] = field(default_factory=list)
    secret_key: bytes = field(default_factory=lambda: os.urandom(24))
    
    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        """Cria configuração a partir de variáveis de ambiente."""
        allowed_ips_str = os.environ.get("ALLOWED_IPS", "")
        allowed_ips = [ip.strip() for ip in allowed_ips_str.split(",") if ip.strip()]
        
        secret_key = os.environ.get("SECRET_KEY")
        if secret_key:
            secret_key = secret_key.encode() if isinstance(secret_key, str) else secret_key
        else:
            secret_key = os.urandom(24)
        
        return cls(
            allowed_ips=allowed_ips,
            secret_key=secret_key
        )


@dataclass
class UploadConfig:
    """Configurações de upload de arquivos."""
    
    folder: str = field(default_factory=lambda: os.path.join(os.getcwd(), "uploads"))
    max_content_length: int = 32 * 1024 * 1024  # 32MB
    allowed_extensions: List[str] = field(default_factory=lambda: ['xlsx', 'xls', 'csv', 'pdf', 'jpg', 'jpeg', 'png'])
    
    @classmethod
    def from_env(cls) -> 'UploadConfig':
        """Cria configuração a partir de variáveis de ambiente."""
        folder = os.environ.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
        max_size = int(os.environ.get("MAX_CONTENT_LENGTH", 32 * 1024 * 1024))
        
        extensions_str = os.environ.get("ALLOWED_EXTENSIONS", "xlsx,xls,csv,pdf,jpg,jpeg,png")
        extensions = [ext.strip() for ext in extensions_str.split(",") if ext.strip()]
        
        return cls(
            folder=folder,
            max_content_length=max_size,
            allowed_extensions=extensions
        )


@dataclass
class CeleryConfig:
    """Configurações do Celery para processamento assíncrono."""
    
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"
    task_serializer: str = "json"
    result_serializer: str = "json"
    accept_content: List[str] = field(default_factory=lambda: ['json'])
    timezone: str = "America/Sao_Paulo"
    enable_utc: bool = True
    task_track_started: bool = True
    task_time_limit: int = 3600  # 1 hora
    task_soft_time_limit: int = 3300  # 55 minutos
    
    @classmethod
    def from_env(cls) -> 'CeleryConfig':
        """Cria configuração a partir de variáveis de ambiente."""
        broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
        backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
        
        return cls(
            broker_url=broker,
            result_backend=backend
        )


class BaseConfig:
    """Configuração base da aplicação Flask.
    
    Esta classe mantém compatibilidade com Flask enquanto usa dataclasses
    internamente para organização e validação.
    """
    
    def __init__(self):
        # Configurações de segurança
        security = SecurityConfig.from_env()
        self.SECRET_KEY = security.secret_key
        self.CONTENT_SECURITY_POLICY = security.csp_policy
        self.ALLOWED_IPS = security.allowed_ips
        
        # Configurações de upload
        upload = UploadConfig.from_env()
        self.UPLOAD_FOLDER = upload.folder
        self.MAX_CONTENT_LENGTH = upload.max_content_length
        self.ALLOWED_EXTENSIONS = upload.allowed_extensions
        
        # Configurações Celery
        celery = CeleryConfig.from_env()
        self.CELERY_BROKER_URL = celery.broker_url
        self.CELERY_RESULT_BACKEND = celery.result_backend
        self.CELERY_TASK_SERIALIZER = celery.task_serializer
        self.CELERY_RESULT_SERIALIZER = celery.result_serializer
        self.CELERY_ACCEPT_CONTENT = celery.accept_content
        self.CELERY_TIMEZONE = celery.timezone
        self.CELERY_ENABLE_UTC = celery.enable_utc
        self.CELERY_TASK_TRACK_STARTED = celery.task_track_started
        self.CELERY_TASK_TIME_LIMIT = celery.task_time_limit
        self.CELERY_TASK_SOFT_TIME_LIMIT = celery.task_soft_time_limit
        
        # Flags de ambiente
        self.DEBUG = False
        self.TESTING = False


class DevConfig(BaseConfig):
    """Configuração para ambiente de desenvolvimento."""
    
    def __init__(self):
        super().__init__()
        self.DEBUG = True


class ProdConfig(BaseConfig):
    """Configuração para ambiente de produção."""
    
    def __init__(self):
        super().__init__()
        self.DEBUG = False
        
        # Validar que SECRET_KEY não é o padrão em produção
        if self.SECRET_KEY == os.urandom(24) or not os.environ.get("SECRET_KEY"):
            raise ValueError(
                "SECRET_KEY deve ser definida em .env para ambiente de produção!"
            )


class TestConfig(BaseConfig):
    """Configuração para ambiente de testes."""
    
    def __init__(self):
        super().__init__()
        self.TESTING = True
        self.DEBUG = True
        self.UPLOAD_FOLDER = os.path.join(os.getcwd(), "test_uploads")
