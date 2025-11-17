"""Rate Limiting para proteger APIs contra abuso.

Este módulo implementa limitação de requisições usando Flask-Limiter.

Para usar:
    1. pip install Flask-Limiter
    2. Importar e aplicar nos endpoints
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request


# ============================================================================
# Configuração do Rate Limiter
# ============================================================================

def get_user_identifier():
    """Identifica o usuário para rate limiting.
    
    Usa IP por padrão, mas pode usar API key, user_id, etc.
    """
    # Tentar pegar de header customizado (se tiver auth)
    api_key = request.headers.get('X-API-KEY')
    if api_key:
        return f"key:{api_key}"
    
    # User ID de sessão (se tiver auth)
    user_id = getattr(request, 'user_id', None)
    if user_id:
        return f"user:{user_id}"
    
    # Fallback: IP address
    return get_remote_address()


# Criar instância do limiter
limiter = Limiter(
    key_func=get_user_identifier,
    default_limits=["200 per day", "50 per hour"],  # Limites globais
    storage_uri="redis://localhost:6379",  # Usar Redis
    strategy="fixed-window",  # Estratégia de contagem
)


def init_rate_limiter(app):
    """Inicializa rate limiter na aplicação Flask."""
    limiter.init_app(app)
    
    # Configurar mensagens de erro customizadas
    @app.errorhandler(429)
    def ratelimit_handler(e):
        from modular_app.utils.api_response import error_response
        return error_response(
            message="Limite de requisições excedido",
            error_code="RATE_LIMIT_EXCEEDED",
            details={
                "retry_after": e.description,
                "limite": str(e),
            },
            status_code=429
        )


# ============================================================================
# GUIA DE USO
# ============================================================================

"""
1. LIMITES GLOBAIS (aplicados a todas as rotas):
   - Configurado em default_limits acima
   - Exemplo: "200 per day", "50 per hour"

2. LIMITES POR ROTA (decorators):
   
   from modular_app.extensions.rate_limiter import limiter
   
   @app.route('/api/endpoint')
   @limiter.limit("10 per minute")  # 10 requisições por minuto
   def meu_endpoint():
       return {"data": "..."}

3. MÚLTIPLOS LIMITES:
   
   @limiter.limit("100 per day")
   @limiter.limit("10 per minute")
   def endpoint_restrito():
       pass

4. EXCEÇÕES (whitelist):
   
   @limiter.exempt  # Sem limite
   def endpoint_publico():
       pass

5. LIMITES DINÂMICOS:
   
   def dynamic_limit():
       # Usuários premium: 1000/dia, regular: 100/dia
       if is_premium_user():
           return "1000 per day"
       return "100 per day"
   
   @limiter.limit(dynamic_limit)
   def endpoint():
       pass

6. SINTAXE DE LIMITES:
   - "N per second"  -> N requisições por segundo
   - "N per minute"  -> N requisições por minuto
   - "N per hour"    -> N requisições por hora
   - "N per day"     -> N requisições por dia
   - "N per month"   -> N requisições por mês
   - "N/second"      -> Forma curta
   - "N/minute"      -> Forma curta
"""

# ============================================================================
# EXEMPLOS PRÁTICOS
# ============================================================================

def apply_rate_limits_examples(app):
    """Exemplos de aplicação de rate limits."""
    
    from flask import Blueprint
    
    api = Blueprint('api_limited', __name__)
    
    # Exemplo 1: API pública com limite baixo
    @api.route('/public/data')
    @limiter.limit("10 per minute")
    def public_endpoint():
        return {"data": "público"}
    
    # Exemplo 2: Processamento pesado com limite mais restrito
    @api.route('/process/heavy')
    @limiter.limit("2 per minute")
    @limiter.limit("20 per hour")
    def heavy_processing():
        return {"status": "processing"}
    
    # Exemplo 3: Upload com limite de tamanho e frequência
    @api.route('/upload', methods=['POST'])
    @limiter.limit("5 per hour")
    def upload_file():
        return {"status": "uploaded"}
    
    # Exemplo 4: Busca com burst allowance
    @api.route('/search')
    @limiter.limit("30 per minute")
    def search():
        return {"results": []}
    
    # Exemplo 5: Endpoint crítico muito restrito
    @api.route('/admin/action', methods=['POST'])
    @limiter.limit("1 per minute")
    @limiter.limit("10 per day")
    def admin_action():
        return {"status": "executed"}
    
    # Exemplo 6: Health check sem limite
    @api.route('/health')
    @limiter.exempt
    def health_check():
        return {"status": "ok"}
    
    app.register_blueprint(api)


# ============================================================================
# ESTRATÉGIAS DE RATE LIMITING
# ============================================================================

"""
1. FIXED-WINDOW (padrão):
   - Janela fixa de tempo
   - Exemplo: 100 req/hora = resetado a cada hora cheia
   - Prós: Simples, previsível
   - Contras: Possível burst no início da janela

2. MOVING-WINDOW:
   - Janela deslizante
   - Exemplo: Últimas 60 requisições em 60 minutos
   - Prós: Mais justo, sem burst
   - Contras: Mais complexo, usa mais memória

3. FIXED-WINDOW-ELASTIC:
   - Combina fixed e moving
   - Prós: Equilíbrio entre simplicidade e justiça
   - Contras: Mais complexo de entender

Para mudar estratégia:
    limiter = Limiter(
        key_func=get_user_identifier,
        storage_uri="redis://localhost:6379",
        strategy="moving-window",  # ou "fixed-window-elastic"
    )
"""

# ============================================================================
# MONITORAMENTO
# ============================================================================

def get_rate_limit_status(identifier=None):
    """Consulta status de rate limit de um usuário.
    
    Returns:
        dict: Status atual dos limites
    """
    if identifier is None:
        identifier = get_user_identifier()
    
    # Consultar Redis para ver quantas requisições foram feitas
    # Implementação depende da estratégia escolhida
    return {
        "identifier": identifier,
        "limits": limiter.get_window_stats()
    }


# ============================================================================
# HEADERS DE RESPOSTA
# ============================================================================

"""
Flask-Limiter adiciona headers automaticamente:

X-RateLimit-Limit: 100       # Limite total
X-RateLimit-Remaining: 87    # Requisições restantes
X-RateLimit-Reset: 1637263200  # Timestamp do reset

Exemplo de resposta:
    HTTP/1.1 200 OK
    X-RateLimit-Limit: 10
    X-RateLimit-Remaining: 9
    X-RateLimit-Reset: 1637263260
    Content-Type: application/json
    
    {"data": "..."}

Quando limite excedido:
    HTTP/1.1 429 Too Many Requests
    Retry-After: 60
    X-RateLimit-Limit: 10
    X-RateLimit-Remaining: 0
    X-RateLimit-Reset: 1637263260
    
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
"""
