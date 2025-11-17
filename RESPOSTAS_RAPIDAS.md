# ✅ Respostas Rápidas às Suas Perguntas

## 1️⃣ Como rodar a aplicação?

### **Modo Simples (como antes):**

```bash
python run.py
```

✅ Funciona exatamente igual  
⚠️ Sem Celery (usa threads manuais)

---

### **Modo Completo (com Celery - RECOMENDADO):**

#### Passo 1: Iniciar Redis

```bash
docker run -d -p 6379:6379 --name redis redis:alpine
```

#### Passo 2: Usar o script automático

```bash
start.bat
```

**OU manualmente (3 terminais):**

```bash
# Terminal 1
python run.py

# Terminal 2
celery -A celery_app worker --loglevel=info --pool=solo

# Terminal 3 (opcional - tarefas agendadas)
celery -A celery_app beat --loglevel=info
```

---

## 2️⃣ Como agendar tasks periódicas?

### **Passo 1: Editar `celery_beat_config.py`**

```python
from celery.schedules import crontab

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
}
```

### **Passo 2: Iniciar Celery Beat**

```bash
celery -A celery_app beat --loglevel=info
```

### **Exemplos Práticos:**

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

### **Tasks Prontas para Usar:**

✅ `task_limpar_temp` - Limpa arquivos temporários  
✅ `task_backup_diario` - Backup automático  
✅ `task_health_check` - Verifica saúde do sistema  
✅ `task_relatorio_semanal` - Relatório semanal  
✅ `task_relatorio_mensal` - Relatório mensal  

---

## 3️⃣ Como ver Rate Limiting?

### **Passo 1: Instalar**

```bash
pip install Flask-Limiter
```

### **Passo 2: Ativar (em `modular_app/__init__.py`)**

```python
# Adicione após register_security(app)
try:
    from .extensions.rate_limiter import init_rate_limiter
    init_rate_limiter(app)
except ImportError:
    pass
```

### **Passo 3: Aplicar em Endpoints**

```python
from modular_app.extensions.rate_limiter import limiter

@app.route('/api/endpoint')
@limiter.limit("10 per minute")  # 10 requisições por minuto
def meu_endpoint():
    return {"data": "..."}
```

### **Ver Status em Tempo Real:**

**Headers HTTP na resposta:**

```
X-RateLimit-Limit: 10        # Limite total
X-RateLimit-Remaining: 7     # Requisições restantes
X-RateLimit-Reset: 1637263260  # Quando resetará
```

**Resposta quando exceder limite:**

```json
{
  "success": false,
  "error": {
    "message": "Limite de requisições excedido",
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {
      "retry_after": "60 seconds",
      "limite": "10 per minute"
    }
  }
}
```

### **Limites Recomendados:**

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

### **Ver Estatísticas no Redis:**

```bash
redis-cli

# Dentro do Redis:
KEYS limiter:*    # Ver todas as chaves de rate limiting
GET limiter:key   # Ver contador específico
```

---

## 📊 Resumo Visual

```
┌─────────────────────────────────────┐
│  COMO RODAR A APLICAÇÃO             │
├─────────────────────────────────────┤
│                                     │
│  Simples (como antes):              │
│    python run.py                    │
│                                     │
│  Completo (recomendado):            │
│    start.bat                        │
│                                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  TASKS PERIÓDICAS                   │
├─────────────────────────────────────┤
│                                     │
│  1. Editar: celery_beat_config.py   │
│  2. Rodar:  celery beat             │
│  3. Usar sintaxe crontab            │
│                                     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  RATE LIMITING                      │
├─────────────────────────────────────┤
│                                     │
│  1. pip install Flask-Limiter       │
│  2. Ativar no __init__.py           │
│  3. @limiter.limit("10/minute")     │
│  4. Ver headers X-RateLimit-*       │
│                                     │
└─────────────────────────────────────┘
```

---

## 🎯 URLs Importantes

| URL | O Que Ver |
|-----|-----------|
| http://localhost:5000 | Aplicação |
| http://localhost:5000/api/v2/doc | **Swagger UI** (testar APIs) |
| http://localhost:5555 | **Flower** (ver tasks Celery) |

---

## 📖 Documentação Completa

- **Guia Rápido**: `GUIA_RAPIDO.md` 📘
- **Melhorias**: `MELHORIAS_IMPLEMENTADAS.md` 📗
- **Changelog**: `CHANGELOG_v2.0.md` 📙

---

## ⚡ Quick Start (Copiar e Colar)

```bash
# 1. Instalar Redis
docker run -d -p 6379:6379 --name redis redis:alpine

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Iniciar tudo
start.bat

# 4. Acessar Swagger
# http://localhost:5000/api/v2/doc
```

---

**Pronto! Sistema configurado e rodando. 🚀**
