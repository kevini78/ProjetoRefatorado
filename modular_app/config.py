import os


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))
    DEBUG = False
    TESTING = False

    # Caminhos e limites padrão
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.join(os.getcwd(), "uploads"))
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 32 * 1024 * 1024))  # 32MB

    # Segurança básica (headers)
    # Permite CSS/JS inline usados pelas páginas e fontes/imagens comuns.
    CONTENT_SECURITY_POLICY = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    )
    ALLOWED_IPS = os.environ.get("ALLOWED_IPS", "").split(",") if os.environ.get("ALLOWED_IPS") else []


class DevConfig(BaseConfig):
    DEBUG = True


class ProdConfig(BaseConfig):
    DEBUG = False


class TestConfig(BaseConfig):
    TESTING = True
    DEBUG = True
