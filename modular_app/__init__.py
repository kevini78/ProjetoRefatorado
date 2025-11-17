import os
from flask import Flask
from .config import DevConfig
from .routes.web import web_bp
from .routes.api import api_bp
from .security.middleware import register_security
from .tasks.job_service import JobService


def create_app(config_object: str | type = DevConfig) -> Flask:
    # Resolve caminhos absolutos normalizados para evitar problemas com UNC paths no Windows
    # Remove o prefixo \\?\ do Windows se presente
    def normalize_path(p: str) -> str:
        p = os.path.abspath(p)
        if p.startswith('\\\\?\\'):
            p = p[4:]  # Remove \\?\\ prefix
        return os.path.normpath(p)
    
    base_dir = normalize_path(os.path.dirname(os.path.dirname(__file__)))
    template_path = os.path.join(base_dir, "templates")
    static_path = os.path.join(base_dir, "static")
    
    app = Flask(
        __name__,
        template_folder=template_path,
        static_folder=static_path,
    )

    # Configuração
    if isinstance(config_object, str):
        app.config.from_object(config_object)
    else:
        app.config.from_object(config_object)

    # Helpers globais mínimos para templates que usam CSRF e datas
    try:
        from datetime import datetime
        app.jinja_env.globals.setdefault('csrf_token', lambda: '')
        app.jinja_env.globals.setdefault('current_time', lambda: datetime.now())
        app.jinja_env.globals.setdefault('app_version', os.environ.get('APP_VERSION', 'dev'))
    except Exception:
        pass

    # Segurança (headers/middlewares)
    register_security(app)

    # Extensões simples
    app.extensions['job_service'] = JobService()

    # Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    # Blueprints adicionais (uploads e automação)
    try:
        from .routes.api_uploads import api_uploads_bp
        app.register_blueprint(api_uploads_bp)
    except Exception:
        pass
    try:
        from .routes.ocr import ocr_bp
        app.register_blueprint(ocr_bp)
    except Exception:
        pass
    try:
        from .routes.automacao import automacao_bp
        app.register_blueprint(automacao_bp)
    except Exception:
        pass
    try:
        from .routes.aprovacoes import aprovacoes_bp
        app.register_blueprint(aprovacoes_bp)
    except Exception:
        pass
    try:
        from .routes.pages import pages_bp
        app.register_blueprint(pages_bp)
    except Exception:
        pass

    return app
