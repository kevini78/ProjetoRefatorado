"""Configuração da aplicação Celery para processamento assíncrono.

Este módulo configura o Celery como um job runner robusto, substituindo
o sistema de threads manuais anterior.

Para executar o worker:
    celery -A celery_app worker --loglevel=info --pool=solo  # Windows
    celery -A celery_app worker --loglevel=info               # Linux/Mac

Para monitorar:
    celery -A celery_app flower  # Web UI em http://localhost:5555
"""
from celery import Celery
from modular_app.config import DevConfig, ProdConfig
import os
import sys

# Garantir que o diretório raiz do projeto esteja no sys.path,
# para que pacotes como 'automation' possam ser importados pelo worker.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def make_celery():
    """Factory para criar instância do Celery configurada."""
    
    # Escolher configuração baseada no ambiente
    config_cls = ProdConfig if os.environ.get("APP_ENV") == "production" else DevConfig
    config = config_cls()
    
    # Criar aplicação Celery
    celery_app = Celery('modular_app')
    
    # Configurar Celery usando as configurações tipadas
    celery_app.conf.update(
        broker_url=config.CELERY_BROKER_URL,
        result_backend=config.CELERY_RESULT_BACKEND,
        task_serializer=config.CELERY_TASK_SERIALIZER,
        result_serializer=config.CELERY_RESULT_SERIALIZER,
        accept_content=config.CELERY_ACCEPT_CONTENT,
        timezone=config.CELERY_TIMEZONE,
        enable_utc=config.CELERY_ENABLE_UTC,
        task_track_started=config.CELERY_TASK_TRACK_STARTED,
        task_time_limit=config.CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=config.CELERY_TASK_SOFT_TIME_LIMIT,
        # Configurações adicionais para robustez
        task_acks_late=True,  # Tarefas só são removidas da fila após conclusão
        worker_prefetch_multiplier=1,  # Evita sobrecarga do worker
        task_reject_on_worker_lost=True,  # Rejeita tarefas se worker cair
        task_default_retry_delay=300,  # 5 minutos entre retries
        task_max_retries=3,  # Máximo de 3 tentativas
    )
    
    # Importar explicitamente o módulo onde as tasks Celery estão definidas,
    # para garantir que o worker registre todas as tasks (incluindo aprovacao_lote).
    try:
        import modular_app.tasks.celery_tasks  # noqa: F401
    except Exception as e:
        # Log simples em stdout; o worker ainda pode subir, mas sem tasks registradas.
        print(f"[AVISO] Falha ao importar modular_app.tasks.celery_tasks: {e}")

    # Auto-discover tasks nos módulos (mantido por compatibilidade)
    # Procurar pelo módulo modular_app.tasks.celery_tasks (onde as tasks estão definidas)
    celery_app.autodiscover_tasks(['modular_app.tasks'], related_name='celery_tasks')
    
    # Configurar tasks periódicas (Celery Beat)
    try:
        from celery_beat_config import configure_beat_schedule
        configure_beat_schedule(celery_app)
    except ImportError:
        pass  # celery_beat_config é opcional
    
    return celery_app


# Instância global do Celery
celery = make_celery()


if __name__ == '__main__':
    celery.start()
