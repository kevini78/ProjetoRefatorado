"""Configuração de Tasks Periódicas com Celery Beat.

Este módulo configura tarefas agendadas que executam automaticamente
em intervalos definidos.

Para usar:
    1. Adicionar tasks neste arquivo
    2. Executar: celery -A celery_app beat --loglevel=info
"""
from celery.schedules import crontab


def configure_beat_schedule(celery_app):
    """Configura tarefas periódicas no Celery."""
    
    celery_app.conf.beat_schedule = {
        # ============================================================================
        # Exemplo 1: Task a cada 10 minutos
        # ============================================================================
        'limpar-arquivos-temporarios-cada-10min': {
            'task': 'modular_app.tasks.celery_tasks.task_limpar_temp',
            'schedule': 600.0,  # 600 segundos = 10 minutos
        },
        
        # ============================================================================
        # Task: Aprovação em lote todos os dias às 16h23
        # ============================================================================
        'aprovacao-lote-diaria-16h23': {
            'task': 'modular_app.tasks.aprovacao_lote',
            # Horário diário às 16:23 (timezone configurado abaixo)
            'schedule': crontab(hour=16, minute=23),
            # Args: (max_iteracoes, modo_execucao, tempo_espera_minutos)
            'args': (1, 'unico', 10),
        },
        
        # ============================================================================
        # Exemplo 2: Task todos os dias às 2h da manhã
        # ============================================================================
        'backup-diario-2am': {
            'task': 'modular_app.tasks.celery_tasks.task_backup_diario',
            'schedule': crontab(hour=2, minute=0),
        },
        
        # ============================================================================
        # Exemplo 3: Task de segunda a sexta às 9h
        # ============================================================================
        'relatorio-semanal-9am': {
            'task': 'modular_app.tasks.celery_tasks.task_relatorio_semanal',
            'schedule': crontab(hour=9, minute=0, day_of_week='mon-fri'),
        },
        
        # ============================================================================
        # Exemplo 4: Task a cada hora (verificar status do sistema)
        # ============================================================================
        'health-check-cada-hora': {
            'task': 'modular_app.tasks.celery_tasks.task_health_check',
            'schedule': crontab(minute=0),  # A cada hora cheia (XX:00)
        },
        
        # ============================================================================
        # Exemplo 5: Task no primeiro dia de cada mês às 8h
        # ============================================================================
        'relatorio-mensal': {
            'task': 'modular_app.tasks.celery_tasks.task_relatorio_mensal',
            'schedule': crontab(hour=8, minute=0, day_of_month=1),
        },
    }
    
    # Timezone para as tasks agendadas
    celery_app.conf.timezone = 'America/Sao_Paulo'


# ============================================================================
# GUIA RÁPIDO: Sintaxe de Agendamento
# ============================================================================

"""
1. INTERVALOS FIXOS (segundos):
   'schedule': 60.0        # A cada 1 minuto
   'schedule': 300.0       # A cada 5 minutos
   'schedule': 3600.0      # A cada 1 hora

2. CRONTAB (horários específicos):
   
   # A cada minuto
   crontab()
   
   # A cada hora no minuto 0 (XX:00)
   crontab(minute=0)
   
   # Todos os dias às 14:30
   crontab(hour=14, minute=30)
   
   # Segunda a sexta às 9h
   crontab(hour=9, minute=0, day_of_week='mon-fri')
   
   # Sábados e domingos às 10h
   crontab(hour=10, minute=0, day_of_week='sat,sun')
   
   # Primeiro dia do mês às 8h
   crontab(hour=8, minute=0, day_of_month=1)
   
   # Último dia do mês às 23h
   crontab(hour=23, minute=0, day_of_month='28-31')

3. PARÂMETROS CRONTAB:
   - minute: 0-59
   - hour: 0-23
   - day_of_week: 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'
   - day_of_month: 1-31
   - month_of_year: 1-12
"""

# ============================================================================
# EXEMPLOS PRÁTICOS
# ============================================================================

EXEMPLOS_AGENDAMENTO = {
    # Limpeza de cache a cada 30 minutos
    'limpar-cache': {
        'task': 'tasks.limpar_cache',
        'schedule': 1800.0,  # 30 * 60
    },
    
    # Verificar processos pendentes a cada 15 minutos durante horário comercial
    'verificar-processos-pendentes': {
        'task': 'tasks.verificar_pendentes',
        'schedule': crontab(minute='*/15', hour='8-18', day_of_week='mon-fri'),
    },
    
    # Gerar relatório de produtividade diariamente às 18h
    'relatorio-produtividade': {
        'task': 'tasks.gerar_relatorio',
        'schedule': crontab(hour=18, minute=0),
    },
    
    # Sincronizar com sistema externo a cada 5 minutos
    'sincronizar-sistema': {
        'task': 'tasks.sincronizar',
        'schedule': 300.0,
    },
    
    # Arquivar processos antigos toda segunda às 3h da manhã
    'arquivar-processos-antigos': {
        'task': 'tasks.arquivar',
        'schedule': crontab(hour=3, minute=0, day_of_week='monday'),
    },
}
