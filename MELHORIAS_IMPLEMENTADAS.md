# Melhorias Implementadas - Sistema de Naturalização

Este documento detalha as melhorias implementadas conforme análise do `STATUS_BOAS_PRATICAS.md`.

## 📋 Índice

- [Resumo das Melhorias](#resumo-das-melhorias)
- [1. Tipagem com Dataclasses](#1-tipagem-com-dataclasses)
- [2. Migração para Celery](#2-migração-para-celery)
- [3. Documentação OpenAPI/Swagger](#3-documentação-openapiswagger)
- [4. Respostas JSON Padronizadas](#4-respostas-json-padronizadas)
- [Instalação e Configuração](#instalação-e-configuração)
- [Uso](#uso)
- [Migração Gradual](#migração-gradual)

---

## Resumo das Melhorias

| Melhoria | Status | Prioridade | Arquivos |
|----------|--------|-----------|----------|
| ✅ Tipagem com dataclasses | Implementado | 🟡 Média | `modular_app/config.py` |
| ✅ Migração para Celery/RQ | Implementado | 🔴 Alta | `celery_app.py`, `modular_app/tasks/celery_tasks.py` |
| ✅ Documentação OpenAPI | Implementado | 🟡 Média | `modular_app/routes/api_v2.py` |
| ✅ Respostas JSON padronizadas | Implementado | 🟡 Média | `modular_app/utils/api_response.py` |

---

## 1. Tipagem com Dataclasses

### ✨ O que mudou

O arquivo `config.py` foi refatorado para usar **dataclasses** com **tipagem forte** e **validação automática**.

### 📦 Classes Criadas

```python
@dataclass
class SecurityConfig:
    """Configurações de segurança."""
    csp_policy: str
    allowed_ips: List[str]
    secret_key: bytes
    
    @classmethod
    def from_env(cls) -> 'SecurityConfig':
        # Carrega do .env

@dataclass
class UploadConfig:
    """Configurações de upload."""
    folder: str
    max_content_length: int
    allowed_extensions: List[str]

@dataclass
class CeleryConfig:
    """Configurações do Celery."""
    broker_url: str
    result_backend: str
    task_serializer: str
    # ...
```

### ✅ Benefícios

- ✅ **Type hints** para IDEs (autocompletar)
- ✅ **Validação automática** de tipos
- ✅ **Imutabilidade** por padrão
- ✅ **Documentação** inline
- ✅ **Fácil extensão** para novos ambientes

### 📝 Uso

As configurações continuam compatíveis com Flask:

```python
from modular_app.config import DevConfig, ProdConfig

# Desenvolvimento
config = DevConfig()

# Produção (com validação obrigatória de SECRET_KEY)
config = ProdConfig()  # Lança erro se SECRET_KEY não estiver definida
```

---

## 2. Migração para Celery

### 🚀 Por que Celery?

O sistema anterior usava **threads manuais** via `JobService`, que tem limitações:

❌ Jobs em memória (perdem-se em restart)  
❌ Sem retry automático  
❌ Difícil de escalar horizontalmente  
❌ Sem persistência de estado  

**Celery** resolve todos esses problemas:

✅ Jobs persistidos no Redis  
✅ Retry automático configurável  
✅ Escalável (múltiplos workers)  
✅ Monitoramento via Flower  
✅ Suporte a priorização de tasks  

### 📦 Arquivos Criados

1. **`celery_app.py`** - Aplicação Celery configurada
2. **`modular_app/tasks/celery_tasks.py`** - Tasks migradas

### 📋 Tasks Disponíveis

| Task | Nome | Descrição |
|------|------|-----------|
| `task_defere_indefere` | `modular_app.tasks.defere_indefere` | Defere/Indefere Recurso |
| `task_analise_ordinaria` | `modular_app.tasks.analise_ordinaria` | Análise Ordinária |
| `task_aprovacao_lote` | `modular_app.tasks.aprovacao_lote` | Aprovação em Lote |

### ⚙️ Configuração

1. **Instalar Redis** (broker do Celery):

```bash
# Windows (via WSL ou Docker)
docker run -d -p 6379:6379 redis:alpine

# Linux/Mac
sudo apt install redis-server  # Ubuntu/Debian
brew install redis             # macOS
```

2. **Configurar no `.env`**:

```env
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

3. **Executar Celery Worker**:

```bash
# Windows
celery -A celery_app worker --loglevel=info --pool=solo

# Linux/Mac
celery -A celery_app worker --loglevel=info
```

4. **Monitorar com Flower** (opcional):

```bash
pip install flower
celery -A celery_app flower

# Acesse http://localhost:5555
```

### 🔄 Migração do Código

**Antes (JobService com threads):**

```python
from modular_app.tasks.job_service import get_job_service
job_service = get_job_service(app)
job_id = job_service.enqueue(worker_analise_ordinaria, filepath, column_name)
```

**Depois (Celery):**

```python
from modular_app.tasks.celery_tasks import task_analise_ordinaria
task = task_analise_ordinaria.delay(filepath, column_name)
task_id = task.id
```

### 📊 Monitoramento de Tasks

```python
from celery.result import AsyncResult

# Consultar status
task = AsyncResult(task_id)
print(task.state)  # PENDING, STARTED, SUCCESS, FAILURE

# Resultado (se concluído)
if task.state == 'SUCCESS':
    resultado = task.result
```

### 🔧 Configurações Avançadas

O Celery está configurado com:

- **Retry automático**: 3 tentativas, 5 minutos entre elas
- **Time limit**: 1 hora por task (hard), 55 min (soft)
- **Acks late**: Tasks só removidas após conclusão
- **Reject on worker lost**: Rejeita tasks se worker cair

---

## 3. Documentação OpenAPI/Swagger

### 📖 O que mudou

Nova API v2 com **Flask-RESTX** que gera documentação **Swagger** automática.

### 🌐 Acesso à Documentação

Após iniciar o servidor:

```
http://localhost:5000/api/v2/doc
```

Você verá uma interface **Swagger UI** interativa com:

- 📋 **Lista de endpoints**
- 📝 **Schemas de request/response**
- 🧪 **Testador integrado** (Try it out!)
- 📄 **Download do schema OpenAPI**

### 🗂️ Namespaces (Agrupamentos)

| Namespace | Descrição | Endpoints |
|-----------|-----------|-----------|
| `health` | Health checks | `/health/ping`, `/health/status` |
| `ordinaria` | Análise ordinária | `/ordinaria/processar`, `/ordinaria/processar-lote` |
| `provisoria` | Análise provisória | `/provisoria/processar` |
| `definitiva` | Análise definitiva | `/definitiva/processar` |
| `tasks` | Monitoramento Celery | `/tasks/{task_id}` |

### 🧪 Exemplo de Uso

#### 1. Health Check

```bash
curl http://localhost:5000/api/v2/health/ping
```

Resposta:
```json
{
  "success": true,
  "message": "API está ativa",
  "data": {"pong": true},
  "meta": {"timestamp": "2025-11-17T18:00:00"}
}
```

#### 2. Processar Ordinária (Síncrono)

```bash
curl -X POST http://localhost:5000/api/v2/ordinaria/processar \
  -H "Content-Type: application/json" \
  -d '{"numero_processo": "123456789"}'
```

#### 3. Processar Lote (Assíncrono)

```bash
curl -X POST http://localhost:5000/api/v2/ordinaria/processar-lote \
  -F "file=@processos.xlsx" \
  -F "column_name=codigo"
```

Resposta:
```json
{
  "success": true,
  "message": "Processamento em lote iniciado",
  "data": {
    "task_id": "abc-123-def-456",
    "status": "pending",
    "status_url": "/api/v2/tasks/abc-123-def-456"
  },
  "meta": {
    "async": true,
    "timestamp": "2025-11-17T18:00:00"
  }
}
```

#### 4. Consultar Status da Task

```bash
curl http://localhost:5000/api/v2/tasks/abc-123-def-456
```

Resposta:
```json
{
  "success": true,
  "message": "Status da tarefa: SUCCESS",
  "data": {
    "task_id": "abc-123-def-456",
    "status": "SUCCESS",
    "result": {
      "total_processados": 50,
      "sucessos": 48,
      "erros": 2
    }
  }
}
```

### 📝 Modelos Documentados

Todos os modelos são documentados automaticamente:

```python
processo_input = api.model('ProcessoInput', {
    'numero_processo': fields.String(
        required=True,
        description='Número do processo',
        example='123456789'
    ),
})
```

Aparece no Swagger como:

```json
{
  "ProcessoInput": {
    "type": "object",
    "properties": {
      "numero_processo": {
        "type": "string",
        "description": "Número do processo",
        "example": "123456789"
      }
    },
    "required": ["numero_processo"]
  }
}
```

---

## 4. Respostas JSON Padronizadas

### 📦 Estrutura Padrão

Todas as respostas seguem o formato:

```json
{
  "success": true|false,
  "message": "Mensagem descritiva",
  "data": { /* dados */ },
  "meta": {
    "timestamp": "2025-11-17T18:00:00",
    /* metadados adicionais */
  }
}
```

### ✅ Resposta de Sucesso

```json
{
  "success": true,
  "message": "Operação realizada com sucesso",
  "data": {
    "id": 123,
    "nome": "Processo"
  },
  "meta": {
    "timestamp": "2025-11-17T18:00:00"
  }
}
```

### ❌ Resposta de Erro

```json
{
  "success": false,
  "error": {
    "message": "Código do processo inválido",
    "code": "INVALID_PROCESS_CODE",
    "details": "O código deve conter apenas números"
  },
  "data": null,
  "meta": {
    "timestamp": "2025-11-17T18:00:00"
  }
}
```

### 📄 Resposta Paginada

```json
{
  "success": true,
  "message": "Lista recuperada com sucesso",
  "data": [ /* itens */ ],
  "meta": {
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 150,
      "total_pages": 8,
      "has_next": true,
      "has_prev": false
    },
    "timestamp": "2025-11-17T18:00:00"
  }
}
```

### 🛠️ Funções Helper

```python
from modular_app.utils.api_response import (
    success_response,
    error_response,
    bad_request,
    not_found,
    internal_error,
    async_task_response,
    paginated_response
)

# Sucesso
return success_response(data={"id": 123}, message="Criado", status_code=201)

# Erro 400
return bad_request(message="Campo obrigatório", details={"field": "nome"})

# Erro 404
return not_found(message="Processo não encontrado")

# Task assíncrona
return async_task_response(task_id="abc-123", task_url="/tasks/abc-123")

# Paginação
return paginated_response(data=items, page=1, per_page=20, total=100)
```

---

## Instalação e Configuração

### 1. Instalar Dependências

```bash
pip install -r requirements.txt
```

Principais dependências adicionadas:

- `celery>=5.3.0` - Job queue
- `redis>=5.0.0` - Broker para Celery
- `flask-restx>=1.3.0` - OpenAPI/Swagger
- `pydantic>=2.0.0` - Validação de dados

### 2. Configurar Redis

**Windows (Docker):**

```bash
docker run -d -p 6379:6379 --name redis redis:alpine
```

**Linux/Mac:**

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

Testar conexão:

```bash
redis-cli ping
# Deve retornar: PONG
```

### 3. Configurar `.env`

```env
# Flask
SECRET_KEY=sua-chave-secreta-aqui
FLASK_ENV=development

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Credenciais LECOM
LECOM_USER=seu_usuario
LECOM_PASS=sua_senha

# API Mistral
MISTRAL_API_KEY=sua_chave_api
```

### 4. Iniciar Serviços

**Terminal 1 - Flask:**

```bash
python run.py
```

**Terminal 2 - Celery Worker:**

```bash
# Windows
celery -A celery_app worker --loglevel=info --pool=solo

# Linux/Mac
celery -A celery_app worker --loglevel=info
```

**Terminal 3 - Flower (opcional):**

```bash
celery -A celery_app flower
```

---

## Uso

### Acessar Swagger UI

```
http://localhost:5000/api/v2/doc
```

### Endpoints Principais

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/api/v2/health/ping` | GET | Verificar se API está ativa |
| `/api/v2/health/status` | GET | Status detalhado do sistema |
| `/api/v2/ordinaria/processar` | POST | Processar ordinária (síncrono) |
| `/api/v2/ordinaria/processar-lote` | POST | Processar lote (assíncrono) |
| `/api/v2/tasks/{task_id}` | GET | Consultar status de task |

---

## Migração Gradual

O sistema mantém **compatibilidade com código antigo**:

### ✅ Código Antigo (ainda funciona)

```python
from modular_app.tasks.job_service import JobService
job_service = JobService()
job_id = job_service.enqueue(worker_func, arg1, arg2)
```

### ✨ Código Novo (recomendado)

```python
from modular_app.tasks.celery_tasks import task_analise_ordinaria
task = task_analise_ordinaria.delay(arg1, arg2)
task_id = task.id
```

### 🔄 Plano de Migração

1. **Fase 1** (✅ Concluída): Criar infraestrutura Celery
2. **Fase 2** (em andamento): Migrar tasks principais
3. **Fase 3** (futura): Depreciar JobService

---

## Melhorias Futuras

Com a base implementada, próximas melhorias sugeridas:

1. ⏰ **Agendamento de tasks** (Celery Beat)
2. 📊 **Métricas e dashboards** (Prometheus + Grafana)
3. 🔐 **Autenticação API** (JWT tokens)
4. 📦 **Rate limiting** (Flask-Limiter)
5. 🧪 **Testes automatizados** (Pytest)

---

## Suporte

Para dúvidas ou problemas:

1. Consulte `STATUS_BOAS_PRATICAS.md` para análise completa
2. Verifique logs do Celery worker
3. Use Flower para debug de tasks: http://localhost:5555

---

**Implementado em:** 17/11/2025  
**Versão:** 2.0.0  
**Status:** ✅ Produção
