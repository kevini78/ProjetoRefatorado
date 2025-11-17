# Guia Rápido - Sistema v2.0

## 🚀 Início Rápido (3 passos)

### 1️⃣ Instalar Redis

**Windows (Docker - Recomendado):**
```bash
docker run -d -p 6379:6379 --name redis redis:alpine
```

**Verificar se está rodando:**
```bash
redis-cli ping
# Deve retornar: PONG
```

### 2️⃣ Instalar Dependências

```bash
pip install -r requirements.txt
```

### 3️⃣ Iniciar Sistema

**Opção A - Script Automático (Recomendado):**
```bash
start.bat
```

**Opção B - Manual:**

**Terminal 1 - Flask:**
```bash
python run.py
```

**Terminal 2 - Celery Worker:**
```bash
celery -A celery_app worker --loglevel=info --pool=solo
```

**Terminal 3 - Celery Beat (opcional - tarefas agendadas):**
```bash
celery -A celery_app beat --loglevel=info
```

---

## 📍 URLs Importantes

| URL | Descrição |
|-----|-----------|
| http://localhost:5000 | Aplicação principal |
| http://localhost:5000/api/v2/doc | **Swagger UI** (documentação interativa) |
| http://localhost:5555 | Flower (monitoramento Celery) |

---

## 📋 Comandos Úteis

### Redis

```bash
# Iniciar Redis (Docker)
docker start redis

# Parar Redis
docker stop redis

# Ver logs
docker logs redis

# Conectar ao Redis CLI
redis-cli

# Dentro do Redis CLI:
PING              # Testar conexão
KEYS *            # Ver todas as chaves
FLUSHALL          # Limpar tudo (cuidado!)
```

### Celery

```bash
# Worker (processar tasks)
celery -A celery_app worker --loglevel=info --pool=solo  # Windows
celery -A celery_app worker --loglevel=info              # Linux/Mac

# Beat (agendar tasks periódicas)
celery -A celery_app beat --loglevel=info

# Flower (interface web de monitoramento)
celery -A celery_app flower
# Acesse: http://localhost:5555

# Ver tasks ativas
celery -A celery_app inspect active

# Ver tasks agendadas
celery -A celery_app inspect scheduled

# Ver workers conectados
celery -A celery_app inspect stats

# Purgar todas as tasks da fila
celery -A celery_app purge
```

### Flask

```bash
# Modo desenvolvimento (com debug)
python run.py

# Modo produção
set APP_ENV=production  # Windows
python run.py

# Linux/Mac
export APP_ENV=production
python run.py
```

---

## 🔧 Configuração

### .env (Mínimo Necessário)

```env
# Flask
SECRET_KEY=sua-chave-secreta-aqui
FLASK_ENV=development

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# LECOM (Credenciais)
LECOM_USER=seu_usuario
LECOM_PASS=sua_senha

# Mistral API (OCR)
MISTRAL_API_KEY=sua_chave_api
```

---

## 📖 Como Usar

### 1. Processar Via API (Swagger UI)

1. Acesse: http://localhost:5000/api/v2/doc
2. Expanda o endpoint desejado
3. Clique em "Try it out"
4. Preencha os parâmetros
5. Clique em "Execute"

### 2. Processar Lote (Assíncrono)

```bash
# Via curl
curl -X POST http://localhost:5000/api/v2/ordinaria/processar-lote \
  -F "file=@sua_planilha.xlsx" \
  -F "column_name=codigo"

# Resposta:
{
  "success": true,
  "data": {
    "task_id": "abc-123-def-456",
    "status_url": "/api/v2/tasks/abc-123-def-456"
  }
}
```

### 3. Consultar Status da Task

```bash
# Via curl
curl http://localhost:5000/api/v2/tasks/abc-123-def-456

# Ou via Swagger: GET /api/v2/tasks/{task_id}
```

---

## ⏰ Agendar Tasks Periódicas

### 1. Editar Agendamento

Abra `celery_beat_config.py` e edite:

```python
celery_app.conf.beat_schedule = {
    # Limpar arquivos temporários a cada 10 minutos
    'limpar-temp': {
        'task': 'modular_app.tasks.celery_tasks.task_limpar_temp',
        'schedule': 600.0,  # 600 segundos
    },
    
    # Backup diário às 2h da manhã
    'backup-diario': {
        'task': 'modular_app.tasks.celery_tasks.task_backup_diario',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Seu agendamento customizado
    'minha-task': {
        'task': 'caminho.para.minha_task',
        'schedule': crontab(hour=9, minute=0),  # 9h todos os dias
    },
}
```

### 2. Iniciar Celery Beat

```bash
celery -A celery_app beat --loglevel=info
```

### 3. Exemplos de Agendamento

```python
# A cada 5 minutos
'schedule': 300.0

# A cada hora
'schedule': crontab(minute=0)

# Todos os dias às 14:30
'schedule': crontab(hour=14, minute=30)

# Segunda a sexta às 9h
'schedule': crontab(hour=9, minute=0, day_of_week='mon-fri')

# Primeiro dia do mês às 8h
'schedule': crontab(hour=8, minute=0, day_of_month=1)
```

---

## 🛡️ Rate Limiting (Proteção de API)

### 1. Instalar

```bash
pip install Flask-Limiter
```

### 2. Ativar no __init__.py

```python
# Em modular_app/__init__.py
try:
    from .extensions.rate_limiter import init_rate_limiter
    init_rate_limiter(app)
except ImportError:
    pass  # Flask-Limiter não instalado
```

### 3. Usar em Endpoints

```python
from modular_app.extensions.rate_limiter import limiter

@app.route('/api/endpoint')
@limiter.limit("10 per minute")  # 10 requisições por minuto
def meu_endpoint():
    return {"data": "..."}
```

### 4. Ver Status

```bash
# Headers na resposta HTTP:
X-RateLimit-Limit: 10        # Limite total
X-RateLimit-Remaining: 7     # Requisições restantes
X-RateLimit-Reset: 1637263260  # Quando resetará
```

### 5. Limites Recomendados

```python
# API pública
@limiter.limit("100 per day")
@limiter.limit("10 per minute")

# Upload de arquivos
@limiter.limit("5 per hour")

# Processamento pesado
@limiter.limit("2 per minute")

# Health check (sem limite)
@limiter.exempt
```

---

## 🔍 Monitoramento

### Flower (Celery UI)

```bash
# Instalar
pip install flower

# Executar
celery -A celery_app flower

# Acessar
http://localhost:5555
```

**O que ver no Flower:**
- ✅ Workers ativos
- ✅ Tasks em execução
- ✅ Tasks completadas
- ✅ Tasks falhadas
- ✅ Gráficos de performance
- ✅ Logs em tempo real

### Logs

```bash
# Ver logs do Flask
# (aparecem no terminal onde executou python run.py)

# Ver logs do Celery Worker
# (aparecem no terminal onde executou celery worker)

# Ver logs do Celery Beat
# (aparecem no terminal onde executou celery beat)
```

---

## 🐛 Troubleshooting

### Erro: Redis não conecta

```bash
# Verificar se Redis está rodando
redis-cli ping

# Se não estiver:
docker start redis

# Ou instalar:
docker run -d -p 6379:6379 --name redis redis:alpine
```

### Erro: Celery não encontra tasks

```bash
# Verificar se celery_app.py está correto
celery -A celery_app inspect registered

# Deve listar:
# - modular_app.tasks.celery_tasks.task_defere_indefere
# - modular_app.tasks.celery_tasks.task_analise_ordinaria
# - etc.
```

### Erro: Task não executa

```bash
# Ver se worker está rodando
celery -A celery_app inspect active

# Ver fila de tasks
celery -A celery_app inspect scheduled

# Ver tasks falhadas no Flower
http://localhost:5555
```

### Erro: Rate limit não funciona

```bash
# Verificar se Flask-Limiter está instalado
pip show Flask-Limiter

# Verificar se Redis está rodando
redis-cli ping

# Verificar se foi inicializado no __init__.py
```

---

## 📚 Documentação Completa

- **Melhorias**: `MELHORIAS_IMPLEMENTADAS.md`
- **Changelog**: `CHANGELOG_v2.0.md`
- **Status Boas Práticas**: `STATUS_BOAS_PRATICAS.md`

---

## ⚡ Comandos Quick Reference

```bash
# Iniciar tudo (Windows)
start.bat

# Redis
docker start redis
redis-cli ping

# Flask
python run.py

# Celery Worker
celery -A celery_app worker --loglevel=info --pool=solo

# Celery Beat
celery -A celery_app beat --loglevel=info

# Flower
celery -A celery_app flower

# Ver tasks ativas
celery -A celery_app inspect active

# Limpar fila
celery -A celery_app purge
```

---

## 🎯 Endpoints Principais

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v2/doc` | GET | Swagger UI |
| `/api/v2/health/ping` | GET | Health check |
| `/api/v2/health/status` | GET | Status detalhado |
| `/api/v2/ordinaria/processar` | POST | Processar ordinária (síncrono) |
| `/api/v2/ordinaria/processar-lote` | POST | Processar lote (assíncrono) |
| `/api/v2/tasks/{task_id}` | GET | Status da task |

---

**Pronto para usar! 🚀**

Para dúvidas, consulte a documentação completa ou acesse o Swagger UI.
