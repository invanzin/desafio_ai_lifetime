"""
Coletores de Métricas Prometheus para o Microserviço de Extração

Este módulo define todas as métricas customizadas que serão coletadas durante
o funcionamento da API. As métricas são organizadas por categoria e seguem
as convenções de nomenclatura do Prometheus.

Métricas Implementadas:
- OpenAI: requisições, erros, tokens, custos, reparos
- Extração: duração, reuniões extraídas, tipos de reunião
- HTTP: requisições, latência, rate limiting
- Sistema: tamanho de transcrições

Uso:
    from app.metrics.collectors import (
        openai_requests_total,
        extraction_duration_seconds,
        meetings_extracted_total
    )
    
    # Incrementar contador
    openai_requests_total.labels(model="gpt-4o", status="success").inc()
    
    # Observar duração
    extraction_duration_seconds.observe(12.5)
"""

from prometheus_client import Counter, Histogram
import os
from typing import Dict, Any

# =============================================================================
# MÉTRICAS RELACIONADAS À OPENAI API
# =============================================================================

openai_requests_total = Counter(
    'openai_requests_total',
    'Total de requisições feitas à API da OpenAI',
    ['model', 'status']  # status: success, error
)

openai_errors_total = Counter(
    'openai_errors_total', 
    'Total de erros específicos da OpenAI (timeouts, rate limits, etc.)',
    ['error_type']  # APITimeoutError, RateLimitError, APIError
)

openai_tokens_total = Counter(
    'openai_tokens_total',
    'Contagem total de tokens processados pela OpenAI',
    ['type']  # prompt, completion, total
)

openai_estimated_cost_usd = Counter(
    'openai_estimated_cost_usd',
    'Custo total estimado em USD baseado no uso de tokens',
    ['model']  # gpt-4o, gpt-3.5-turbo, etc.
)

openai_repair_attempts_total = Counter(
    'openai_repair_attempts_total',
    'Total de tentativas de reparo de JSON inválido retornado pela OpenAI',
    ['status']  # success, failed
)

# =============================================================================
# MÉTRICAS DE EXTRAÇÃO E PROCESSAMENTO
# =============================================================================

extraction_duration_seconds = Histogram(
    'extraction_duration_seconds',
    'Distribuição do tempo de duração da extração (chamada à OpenAI)',
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, float("inf")]
)

meetings_extracted_total = Counter(
    'meetings_extracted_total',
    'Número total de reuniões extraídas com sucesso',
    ['source']  # raw_meeting, transcript
)

meetings_by_type_total = Counter(
    'meetings_by_type_total',
    'Contagem de reuniões extraídas por tipo (ex: Onboarding)',
    ['meeting_type']  # Onboarding, Follow-up, etc.
)

transcript_size_bytes = Histogram(
    'transcript_size_bytes',
    'Distribuição do tamanho das transcrições processadas (em bytes)',
    buckets=[1000, 5000, 10000, 25000, 50000, 100000, 250000, float("inf")]
)

# =============================================================================
# MÉTRICAS HTTP E RATE LIMITING
# =============================================================================

rate_limit_exceeded_total = Counter(
    'rate_limit_exceeded_total',
    'Total de vezes que o rate limit da API foi atingido',
    ['endpoint']  # /extract, /health, etc.
)

api_errors_total = Counter(
    'api_errors_total',
    'Total de erros retornados pela API (502 Bad Gateway, 500 Internal Server Error)',
    ['error_type', 'status_code']  # openai_error, validation_error, 502, 500
)

http_requests_total = Counter(
    'http_requests_total',
    'Total de requisições HTTP recebidas pela API',
    ['method', 'endpoint', 'status_code']  # POST, /extract, 200
)

http_requests_duration_seconds = Histogram(
    'http_requests_duration_seconds',
    'Distribuição da latência de todas as requisições HTTP',
    ['method', 'endpoint'],  # POST, /extract
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")]
)

# =============================================================================
# FUNÇÕES AUXILIARES PARA CÁLCULO DE CUSTOS
# =============================================================================

def calculate_openai_cost(
    model: str, 
    prompt_tokens: int, 
    completion_tokens: int
    ) -> float:
    """
    Calcula o custo estimado de uma chamada à OpenAI baseado no modelo e tokens.
    
    Preços atualizados (Outubro 2025):
    - GPT-4o: $5/1M input + $15.00/1M output
    - GPT-3.5-turbo: $0.50/1M input + $1.50/1M output
    - GPT-4o-mini: $0.15/1M input + $0.60/1M output
    
    Args:
        model: Nome do modelo (ex: "gpt-4o")
        prompt_tokens: Tokens de entrada (prompt)
        completion_tokens: Tokens de saída (resposta)
        
    Returns:
        float: Custo estimado em USD
    """
    # Preços por 1M de tokens (em USD)
    pricing: Dict[str, Dict[str, float]] = {
        "gpt-4o": {
            "input": 5.00,
            "output": 15.00
        },
        "gpt-4o-mini": {
            "input": 0.15,
            "output": 0.60
        },
        "gpt-3.5-turbo": {
            "input": 0.50,
            "output": 1.50
        }
    }
    
    # Modelo padrão se não encontrado
    model_pricing = pricing.get(model, pricing["gpt-4o"])
    
    # Cálculo: (tokens / 1_000_000) * preço_por_1M
    input_cost = (prompt_tokens / 1_000_000) * model_pricing["input"]
    output_cost = (completion_tokens / 1_000_000) * model_pricing["output"]
    
    return input_cost + output_cost

def get_model_from_env() -> str:
    """
    Obtém o modelo OpenAI configurado nas variáveis de ambiente.
    
    Returns:
        str: Nome do modelo (padrão: "gpt-4o")
    """
    return os.getenv("OPENAI_MODEL", "gpt-4o")

# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA PARA INSTRUMENTAÇÃO
# =============================================================================

def record_openai_request(model: str, status: str) -> None:
    """Registra uma requisição à OpenAI."""
    openai_requests_total.labels(model=model, status=status).inc()

def record_openai_error(error_type: str) -> None:
    """Registra um erro específico da OpenAI."""
    openai_errors_total.labels(error_type=error_type).inc()

def record_openai_tokens(
    model: str,
    prompt_tokens: int, 
    completion_tokens: int, 
    total_tokens: int
) -> None:
    """Registra tokens consumidos e calcula custo."""
    # Registra tokens por tipo
    openai_tokens_total.labels(type="prompt").inc(prompt_tokens)
    openai_tokens_total.labels(type="completion").inc(completion_tokens)
    openai_tokens_total.labels(type="total").inc(total_tokens)
    
    # Calcula e registra custo
    cost = calculate_openai_cost(model, prompt_tokens, completion_tokens)
    openai_estimated_cost_usd.labels(model=model).inc(cost)

def record_repair_attempt(status: str) -> None:
    """Registra tentativa de reparo de JSON."""
    openai_repair_attempts_total.labels(status=status).inc()

def record_meeting_extracted(source: str, meeting_type: str = "Unknown") -> None:
    """Registra reunião extraída com sucesso."""
    meetings_extracted_total.labels(source=source).inc()
    meetings_by_type_total.labels(meeting_type=meeting_type).inc()

def record_transcript_size(size_bytes: int) -> None:
    """Registra tamanho da transcrição."""
    transcript_size_bytes.observe(size_bytes)

def record_rate_limit_exceeded(endpoint: str) -> None:
    """Registra rate limit excedido."""
    rate_limit_exceeded_total.labels(endpoint=endpoint).inc()

def record_api_error(error_type: str, status_code: int) -> None:
    """Registra erro retornado pela API (502, 500, etc.)."""
    api_errors_total.labels(error_type=error_type, status_code=str(status_code)).inc()

def record_http_request(method: str, endpoint: str, status_code: int) -> None:
    """Registra requisição HTTP."""
    http_requests_total.labels(
        method=method, 
        endpoint=endpoint, 
        status_code=str(status_code)
    ).inc()

def record_http_duration(method: str, endpoint: str, duration: float) -> None:
    """Registra duração de requisição HTTP."""
    http_requests_duration_seconds.labels(
        method=method, 
        endpoint=endpoint
    ).observe(duration)
