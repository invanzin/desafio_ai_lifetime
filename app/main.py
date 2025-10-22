"""
API Principal do Microserviço de Extração de Reuniões.

Este módulo implementa o endpoint FastAPI para extração estruturada de informações
de transcrições de reuniões bancárias usando OpenAI API + LangChain.

Endpoints:
    POST /extract: Extrai informações estruturadas de uma transcrição
    GET /health: Health check da aplicação

Características:
    - Validação automática com Pydantic
    - Idempotência via SHA-256
    - Logs estruturados (sem PII completa)
    - Retry automático e timeouts
    - Tratamento robusto de erros
    - Documentação automática (OpenAPI/Swagger)
"""

import uuid
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from fastapi.responses import Response

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Métricas Prometheus
from prometheus_fastapi_instrumentator import Instrumentator

# OpenAI exceptions para error handling
from openai import RateLimitError, APITimeoutError, APIError

# Schemas de validação
from app.models.schemas_common import NormalizedInput, MeetingRequest
from app.models.schemas_extract import ExtractedMeeting
from app.models.schemas_analyze import AnalyzedMeeting

# Extractor e Analyzer principais
from app.extractors.extractor import extract_meeting_chain
from app.analyzers.analyzer import analyze_sentiment_chain

# Configuração de logging centralizada
from app.config.logging_config import setup_logging, get_logger

# Importa coletores de métricas para registrá-los
from app.metrics import collectors
from app.metrics.collectors import (
    record_rate_limit_exceeded,
    record_http_request,
    record_http_duration,
    record_transcript_size,
    record_meeting_extracted,
    record_api_error,
    extraction_duration_seconds,
)


# ============================================================================
# CONFIGURAÇÃO DE LOGGING
# ============================================================================

# Inicializa logging imediatamente (importante para testes)
# O setup_logging será chamado novamente no lifespan se necessário
setup_logging(log_level="DEBUG", console_output=True)
logger = get_logger(__name__)


# ============================================================================
# CONFIGURAÇÃO DE RATE LIMITING
# ============================================================================

# Cria instância do Limiter para proteção contra abuse
# - key_func: Usa IP do cliente para rastrear requisições
# - default_limits: Sem limite global (definimos por endpoint)
# - storage_uri: Usa memória (ideal para single-instance deployments)
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # Sem limite global
    storage_uri="memory://",  # Storage em memória
)


# ============================================================================
# CACHE EM MEMÓRIA PARA IDEMPOTÊNCIA
# ============================================================================

# Cache em memória: {idempotency_key: (result_dict, timestamp)}
_cache: Dict[str, Tuple[dict, datetime]] = {}

# TTL do cache em horas (24h = 1 dia)
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))


def get_from_cache(idempotency_key: str) -> Optional[dict]:
    """
    Busca um resultado no cache se ainda válido (dentro do TTL).
    
    Args:
        idempotency_key: Chave de idempotência SHA-256
        
    Returns:
        Dict com resultado se encontrado e válido, None caso contrário
    """
    if idempotency_key in _cache:
        result, timestamp = _cache[idempotency_key]
        
        # Verifica se ainda está dentro do TTL
        if datetime.now() - timestamp < timedelta(hours=CACHE_TTL_HOURS):
            logger.info(
                f"[CACHE HIT] idempotency_key={idempotency_key[:16]}... | "
                f"age={(datetime.now() - timestamp).total_seconds():.1f}s | "
                f"cache_size={len(_cache)}"
            )
            return result
        else:
            # Cache expirado, remove
            del _cache[idempotency_key]
            logger.info(
                f"[CACHE EXPIRED] idempotency_key={idempotency_key[:16]}... | "
                f"age={(datetime.now() - timestamp).total_seconds():.1f}s"
            )
    
    logger.debug(f"[CACHE MISS] idempotency_key={idempotency_key[:16]}...")
    return None


def save_to_cache(idempotency_key: str, result: dict) -> None:
    """
    Salva um resultado no cache com timestamp atual.
    
    Args:
        idempotency_key: Chave de idempotência SHA-256
        result: Dicionário com o resultado a ser cacheado
    """
    _cache[idempotency_key] = (result, datetime.now())
    logger.info(
        f"[CACHE SAVE] idempotency_key={idempotency_key[:16]}... | "
        f"cache_size={len(_cache)} | ttl={CACHE_TTL_HOURS}h"
    )


def clear_cache() -> int:
    """
    Limpa todo o cache e retorna quantos itens foram removidos.
    
    Returns:
        Número de itens removidos do cache
    """
    count = len(_cache)
    _cache.clear()
    logger.info(f"[CACHE CLEARED] removed={count} items")
    return count


# ============================================================================
# LIFESPAN EVENTS (startup/shutdown)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida da aplicação.
    
    Executado na inicialização e shutdown do servidor.
    Útil para:
    - Inicializar conexões (DB, cache, etc)
    - Carregar modelos em memória
    - Cleanup de recursos
    """
    # Startup - Logger já foi inicializado no módulo
    logger.info("🚀 Iniciando microserviço de extração de reuniões...")
    logger.info("✅ Pronto para receber requisições")
    
    yield  # Aplicação roda aqui
    
    # Shutdown
    logger.info("🛑 Encerrando microserviço...")


# ============================================================================
# INICIALIZAÇÃO DA APLICAÇÃO
# ============================================================================

app = FastAPI(
    title="Meeting Extractor API",
    description=(
        "Microserviço para extração estruturada de informações de "
        "transcrições de reuniões bancárias usando OpenAI API + LangChain"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ============================================================================
# CONFIGURAÇÃO DE MÉTRICAS PROMETHEUS
# ============================================================================

# Inicializa o instrumentador Prometheus
instrumentator = Instrumentator(
    should_group_status_codes=False,  # Mantém códigos de status específicos
    should_ignore_untemplated=True,   # Ignora rotas não mapeadas
    should_respect_env_var=True,      # Respeita ENABLE_METRICS env var
    should_instrument_requests_inprogress=True,  # Métricas de requests em progresso
    excluded_handlers=["/metrics"],   # Não instrumenta o próprio endpoint de métricas
    env_var_name="ENABLE_METRICS",    # Nome da variável de ambiente (padrão: True)
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

print("[DEBUG] Criando instrumentador Prometheus...")

# Instrumenta a aplicação FastAPI
instrumentator.instrument(app)
print("[DEBUG] Instrumentador aplicado à FastAPI!")

# Expõe o endpoint /metrics
instrumentator.expose(app, endpoint="/metrics", tags=["Monitoring"])
print("[DEBUG] Endpoint /metrics exposto!")

# ============================================================================
# CONFIGURAÇÃO DE RATE LIMITING
# ============================================================================

# Adiciona o limiter ao estado da aplicação
app.state.limiter = limiter

# Adiciona exception handler padrão do SlowAPI
# (Será sobrescrito pelo nosso handler customizado abaixo)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============================================================================
# MIDDLEWARE PARA REQUEST_ID
# ============================================================================

@app.middleware("http")
async def add_request_id_and_metrics(request: Request, call_next):
    """
    Middleware que adiciona Request-ID e registra métricas HTTP.
    
    Usado para correlação de logs e debugging. Se o cliente já enviar
    um X-Request-ID, ele é preservado; caso contrário, um novo UUID é gerado.
    
    Args:
        request: Requisição HTTP recebida
        call_next: Próxima função na cadeia de middleware
    
    Returns:
        Response: Resposta HTTP com header X-Request-ID
    """
    import time
    
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    # Captura início da requisição
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Registra métricas de sucesso
        record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        )
        record_http_duration(
            method=request.method,
            endpoint=request.url.path,
            duration=time.time() - start_time
        )
        
        response.headers["X-Request-ID"] = request_id
        return response
        
    except Exception as e:
        # Registra métricas de erro
        record_http_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=500
        )
        record_http_duration(
            method=request.method,
            endpoint=request.url.path,
            duration=time.time() - start_time
        )
        raise


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
    ) -> JSONResponse:
    """
    Handler para erros de validação do Pydantic (422 Unprocessable Entity).
    
    Retorna mensagens de erro estruturadas e amigáveis quando a validação
    do corpo da requisição falha.
    
    Args:
        request: Requisição HTTP que causou o erro
        exc: Exceção de validação do Pydantic
    
    Returns:
        JSONResponse: Resposta 422 com detalhes dos erros de validação
    """
    request_id = getattr(request.state, "request_id", "-")
    
    # Serializa os erros de validação de forma segura
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": error.get("loc", []),
            "msg": str(error.get("msg", "")),
            "type": error.get("type", ""),
        })
    
    logger.warning(
        f"⚠️ [{request_id}] Validation error | "
        f"🔍 errors={errors}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Dados de entrada inválidos",
            "details": errors,
            "request_id": request_id,
        }
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(
    request: Request,
    exc: RateLimitExceeded
    ) -> JSONResponse:
    """
    Handler para erros de rate limiting (429 Too Many Requests).
    
    Retorna mensagem estruturada quando o cliente excede o limite de
    requisições por minuto, incluindo o header Retry-After.
    
    Args:
        request: Requisição HTTP que causou o erro
        exc: Exceção de rate limit excedido
    
    Returns:
        JSONResponse: Resposta 429 com detalhes do limite e Retry-After header
    """
    request_id = getattr(request.state, "request_id", "-")
    client_ip = get_remote_address(request)
    
    # Obtém o limite configurado (padrão: 10/minute)
    rate_limit = os.getenv("RATE_LIMIT_PER_MINUTE", "10")
    
    # Registra métrica de rate limit excedido
    endpoint = request.url.path
    record_rate_limit_exceeded(endpoint)
    
    logger.warning(
        f"🚦 [{request_id}] Rate limit exceeded | "
        f"🌐 ip={client_ip} | "
        f"⏱️ limit={rate_limit}/minute"
    )
    
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "rate_limit_exceeded",
            "message": (
                "Você excedeu o limite de requisições. "
                "Tente novamente em alguns instantes."
            ),
            "limit": f"{rate_limit} requisições por minuto",
            "request_id": request_id,
        },
        headers={
            "Retry-After": "60"  # Segundos até poder tentar novamente
        }
    )


@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request,
    exc: Exception
    ) -> JSONResponse:
    """
    Handler genérico para exceções não tratadas (500 Internal Server Error).
    
    Captura qualquer exceção não prevista e retorna uma resposta estruturada,
    evitando expor detalhes internos sensíveis ao cliente.
    
    Args:
        request: Requisição HTTP que causou o erro
        exc: Exceção não tratada
    
    Returns:
        JSONResponse: Resposta 500 com mensagem genérica
    """
    request_id = getattr(request.state, "request_id", "-")
    
    logger.error(
        f"💥 [{request_id}] Unhandled exception | "
        f"🚨 type={type(exc).__name__} | "
        f"💬 error={str(exc)[:200]}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "Erro interno do servidor",
            "request_id": request_id,
        }
    )


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint.
    
    Verifica se o serviço está funcionando corretamente.
    Útil para:
    - Load balancers
    - Kubernetes liveness/readiness probes
    - Monitoramento
    
    Returns:
        dict: Status do serviço
    
    Example:
        ```bash
        curl http://localhost:8000/health
        # {"status": "healthy", "service": "meeting-extractor"}
        ```
    """
    logger.debug("💚 Health check called")
    return {
        "status": "healthy",
        "service": "meeting-extractor",
    }


# ============================================================================
# ENDPOINT: /extract
# ============================================================================

@app.post(
    "/extract",
    response_model=ExtractedMeeting,
    status_code=status.HTTP_200_OK,
    tags=["Extraction"],
    summary="Extrai informações estruturadas de uma transcrição",
    response_description="Informações estruturadas extraídas com sucesso"
    )
@limiter.limit("10/minute")
async def extract_meeting(
    request: Request,
    body: MeetingRequest # faz a validação pelo Pydantic do body
    ) -> ExtractedMeeting:
    """
    Extrai informações estruturadas de uma transcrição de reunião.
    
    Este endpoint recebe uma transcrição de reunião bancária (em um de dois formatos)
    e retorna um JSON estruturado com informações extraídas usando OpenAI API.
    
    **Formatos de entrada aceitos:**
    
    1. **Formato explícito** (transcript + metadata opcional):
       ```json
       {
         "transcript": "Cliente: Bom dia... Banker: Olá...",
         "metadata": {
           "meeting_id": "MTG123",
           "customer_id": "CUST456",
           "customer_name": "ACME S.A.",
           "banker_id": "BKR789",
           "banker_name": "Pedro Falcão",
           "meet_type": "Primeira Reunião",
           "meet_date": "2025-09-10T14:30:00Z"
         }
       }
       ```
    
    2. **Formato bruto** (raw_meeting, vindo de sistemas upstream):
       ```json
       {
         "raw_meeting": {
           "meet_id": "MTG123",
           "customer_id": "CUST456",
           "customer_name": "ACME S.A.",
           "banker_id": "BKR789",
           "banker_name": "Pedro Falcão",
           "meet_date": "2025-09-10T14:30:00Z",
           "meet_type": "Primeira Reunião",
           "meet_transcription": "Cliente: Bom dia..."
         }
       }
       ```
    
    **Observações importantes:**
    
    - Metadados são **opcionais** no input, mas **obrigatórios** no output
    - Se metadados não forem fornecidos, o LLM tentará extraí-los da transcrição
    - Se metadados forem fornecidos, eles têm **prioridade absoluta** sobre a transcrição
    - A chave de idempotência é calculada automaticamente (SHA-256) quando possível
    
    **Resiliência:**
    
    - Timeout: 30 segundos máximo por chamada à OpenAI
    - Retries: até 3 tentativas com backoff exponencial (0.5s, 1s, 2s)
    - Repair: 1 tentativa de reparo automático se validação Pydantic falhar
    
    **Segurança:**
    
    - Logs não contêm transcrições completas (apenas primeiros 300 chars)
    - Request ID único para correlação de logs
    - Sem exposição de detalhes internos em erros
    
    Args:
        request: Objeto Request do FastAPI (injetado automaticamente)
        body: Corpo da requisição validado pelo Pydantic
    
    Returns:
        ExtractedMeeting: JSON estruturado com informações extraídas
    
    Raises:
        422: Erro de validação no input
        502: Erro na chamada à OpenAI (timeout, rate limit, etc)
        500: Erro interno não esperado
    
    Example:
        ```bash
        curl -X POST http://localhost:8000/extract \\
          -H "Content-Type: application/json" \\
          -d '{
            "transcript": "Cliente: Preciso de um empréstimo...",
            "metadata": {
              "meeting_id": "MTG001",
              "customer_id": "CUST001"
            }
          }'
        ```
    """
    import time
    start_time = time.time()
    http_start_time = time.time()  # Timer separado para métricas HTTP
    request_id = request.state.request_id
    
    # Log início - Identifica formato de entrada
    if body.raw_meeting:
        input_format = "raw_meeting"
        has_metadata = True
    elif body.metadata:
        input_format = "transcript+metadata"
        has_metadata = True
    else:
        input_format = "transcript_only"
        has_metadata = False
    
    logger.info(
        f"📥 [INCOMING] [{request_id}] POST /extract received | "
        f"format={input_format} | "
        f"has_metadata={has_metadata}"
    )
    
    try:
        # 1. Normalizar input (converte ambos os formatos para NormalizedInput)
        logger.info(f"🔄 [{request_id}] Iniciando normalização...")
        normalized = body.to_normalized()
        
        # Registra métrica do tamanho da transcrição
        transcript_size = len(normalized.transcript.encode('utf-8'))
        record_transcript_size(transcript_size)
        
        # Log detalhes da normalização
        metadata_fields = sum([
            normalized.meeting_id is not None,
            normalized.customer_id is not None,
            normalized.customer_name is not None,
            normalized.banker_id is not None,
            normalized.banker_name is not None,
            normalized.meet_type is not None,
            normalized.meet_date is not None
        ])
        
        logger.info(
            f"✅ [{request_id}] Normalização concluída | "
            f"transcript_len={len(normalized.transcript)} chars | "
            f"transcript_words={len(normalized.transcript.split())} words | "
            f"metadata_fields={metadata_fields}/7 | "
            f"meeting_id={normalized.meeting_id or 'will_extract'} | "
            f"customer_id={normalized.customer_id or 'will_extract'}"
        )
        
        # 2. Calcular idempotency_key e verificar cache
        idempotency_key = normalized.compute_idempotency_key()
        
        # Se temos uma chave válida, verificar cache
        if idempotency_key and idempotency_key != "no-idempotency-key-available":
            cached_result = get_from_cache(idempotency_key)
            
            if cached_result:
                # Cache HIT: retornar resultado cacheado sem processar
                logger.info(
                    f"🎯 [{request_id}] Retornando do cache (idempotente) | "
                    f"idempotency_key={idempotency_key[:16]}... | "
                    f"⏱️ duration={time.time() - start_time:.3f}s"
                )
                
                # Registra métrica de duração HTTP total (cache hit é rápido!)
                http_duration = time.time() - http_start_time
                record_http_duration("POST", "/extract", http_duration)
                
                return ExtractedMeeting(**cached_result)
            else:
                logger.info(
                    f"🔍 [{request_id}] Cache miss - processando normalmente | "
                    f"idempotency_key={idempotency_key[:16]}..."
                )
        else:
            logger.debug(
                f"ℹ️ [{request_id}] Sem idempotency_key válido - cache não aplicado"
            )
        
        # 3. Chamar o extractor (LangChain + OpenAI)
        # Timer para duração da extração
        extraction_start = time.time()
        
        extracted = await extract_meeting_chain(
            normalized=normalized,
            request_id=request_id
        )
        
        # Registra métrica de duração da extração
        extraction_duration = time.time() - extraction_start
        extraction_duration_seconds.observe(extraction_duration)
        
        # 4. Salvar resultado no cache (se temos idempotency_key válido)
        if idempotency_key and idempotency_key != "no-idempotency-key-available":
            save_to_cache(idempotency_key, extracted.model_dump())
        
        # 5. Log sucesso com duração
        duration = time.time() - start_time
        logger.info(
            f"🎉 [{request_id}] Extração concluída com sucesso | "
            f"⏱️ duration={duration:.2f}s | "
            f"📋 meeting_id={extracted.meeting_id} | "
            f"📝 summary_words={len(extracted.summary.split())} | "
            f"🔑 key_points={len(extracted.key_points)} | "
            f"✅ action_items={len(extracted.action_items)} | "
            f"🏷️ topics={len(extracted.topics)} | "
            f"🔐 idempotency_key={extracted.idempotency_key[:16]}..."
        )
        
        # Registra métrica de reunião extraída com sucesso
        source = "raw_meeting" if body.raw_meeting else "transcript"
        meeting_type = extracted.meet_type or "Unknown"
        record_meeting_extracted(source, meeting_type)
        
        # Registra métrica de duração HTTP total
        http_duration = time.time() - http_start_time
        record_http_duration("POST", "/extract", http_duration)
        
        return extracted
    
    except (RateLimitError, APITimeoutError, APIError) as e:
        # Erros de comunicação com OpenAI API → 502 Bad Gateway
        logger.error(
            f"❌ [{request_id}] Erro de comunicação com OpenAI API | "
            f"🚨 type={type(e).__name__} | "
            f"💬 error={str(e)[:200]}"
        )
        
        # Registra métrica de erro 502
        record_api_error("openai_communication_error", 502)
        
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "openai_communication_error",
                "message": (
                    "Erro ao comunicar com OpenAI API "
                    "(timeout, rate limit ou indisponibilidade). "
                    "Tente novamente em alguns instantes."
                ),
                "error_type": type(e).__name__,
                "request_id": request_id,
            }
        )
    
    except ValidationError as e:
        # Erro de validação: OpenAI retornou dados inválidos → 502 Bad Gateway
        # Este é um problema do serviço externo (OpenAI), não interno
        logger.error(
            f"⚠️ [{request_id}] OpenAI retornou dados inválidos após repair | "
            f"🔴 errors={e.errors()}"
        )
        
        # Registra métrica de erro 502
        record_api_error("openai_invalid_response", 502)
        
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "openai_invalid_response",
                "message": (
                    "OpenAI retornou dados inválidos ou incompletos. "
                    "Tente novamente ou verifique se a transcrição está legível."
                ),
                "request_id": request_id,
            }
        )
    
    except Exception as e:
        # Qualquer outro erro não previsto
        logger.error(
            f"💥 [{request_id}] Erro inesperado | "
            f"🚨 type={type(e).__name__} | "
            f"💬 error={str(e)[:200]}"
        )
        
        # Registra métrica de erro 500
        record_api_error("internal_error", 500)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "Erro interno ao processar a requisição",
                "request_id": request_id,
            }
        )



# ============================================================================
# ENDPOINT: /analyze
# ============================================================================

@app.post(
    "/analyze",
    response_model=AnalyzedMeeting,
    status_code=status.HTTP_200_OK,
    tags=["Analysis"],
    summary="Analisa sentimento e gera insights de uma transcrição",
    response_description="Análise de sentimento e insights gerados com sucesso"
    )
@limiter.limit("10/minute")
async def analyze_meeting(
    request: Request,
    body: MeetingRequest # faz a validação pelo Pydantic do body
    ) -> AnalyzedMeeting:
    """
    Analisa sentimento e gera insights de uma transcrição de reunião.
    
    Este endpoint recebe uma transcrição de reunião bancária (em um de dois formatos)
    e retorna um JSON estruturado com análise de sentimento e insights estratégicos.
    
    **Formatos de entrada aceitos:**
    
    1. **Formato explícito** (transcript + metadata opcional):
       ```json
       {
         "transcript": "Cliente: Estou muito satisfeito... Banker: Que bom...",
         "metadata": {
           "meeting_id": "MTG123",
           "customer_id": "CUST456",
           "customer_name": "ACME S.A.",
           "banker_id": "BKR789",
           "banker_name": "Pedro Falcão",
           "meet_type": "Segunda Reunião",
           "meet_date": "2025-09-10T14:30:00Z"
         }
       }
       ```
    
    2. **Formato bruto** (raw_meeting, vindo de sistemas upstream):
       ```json
       {
         "raw_meeting": {
           "meet_id": "MTG123",
           "customer_id": "CUST456",
           "customer_name": "ACME S.A.",
           "banker_id": "BKR789",
           "banker_name": "Pedro Falcão",
           "meet_date": "2025-09-10T14:30:00Z",
           "meet_type": "Segunda Reunião",
           "meet_transcription": "Cliente: Estou muito satisfeito..."
         }
       }
       ```
    
    **Campos de análise retornados:**
    
    - `sentiment_label`: Classificação categórica ("positive", "neutral", "negative")
    - `sentiment_score`: Score numérico (0.0 a 1.0)
    - `summary`: Resumo executivo (100-200 palavras)
    - `key_points`: Pontos-chave discutidos
    - `action_items`: Ações/tarefas identificadas
    - `risks`: Riscos ou preocupações levantados pelo cliente
    
    **Observações importantes:**
    
    - Metadados são **opcionais** no input, mas **obrigatórios** no output
    - Se metadados não forem fornecidos, o LLM tentará extraí-los da transcrição
    - Se metadados forem fornecidos, eles têm **prioridade absoluta** sobre a transcrição
    - A chave de idempotência é calculada automaticamente (SHA-256) quando possível
    
    **Resiliência:**
    
    - Timeout: 30 segundos máximo por chamada à OpenAI
    - Retries: até 3 tentativas com backoff exponencial (0.5s, 1s, 2s)
    - Repair: 1 tentativa de reparo automático se validação Pydantic falhar
    
    **Segurança:**
    
    - Logs não contêm transcrições completas (apenas primeiros 300 chars)
    - Request ID único para correlação de logs
    - Sem exposição de detalhes internos em erros
    
    Args:
        request: Objeto Request do FastAPI (injetado automaticamente)
        body: Corpo da requisição validado pelo Pydantic
    
    Returns:
        AnalyzedMeeting: JSON estruturado com análise de sentimento e insights
    
    Raises:
        422: Erro de validação no input
        502: Erro na chamada à OpenAI (timeout, rate limit, etc)
        500: Erro interno não esperado
    
    Example:
        ```bash
        curl -X POST http://localhost:8000/analyze \\
          -H "Content-Type: application/json" \\
          -d '{
            "transcript": "Cliente: Estou muito satisfeito com os resultados...",
            "metadata": {
              "meeting_id": "MTG001",
              "customer_id": "CUST001"
            }
          }'
        ```
    """
    import time
    start_time = time.time()
    http_start_time = time.time()  # Timer separado para métricas HTTP
    request_id = request.state.request_id
    
    # Log início - Identifica formato de entrada
    if body.raw_meeting:
        input_format = "raw_meeting"
        has_metadata = True
    elif body.metadata:
        input_format = "transcript+metadata"
        has_metadata = True
    else:
        input_format = "transcript_only"
        has_metadata = False
    
    logger.info(
        f"[INCOMING] [{request_id}] POST /analyze received | "
        f"format={input_format} | "
        f"has_metadata={has_metadata}"
    )
    
    try:
        # 1. Normalizar input (converte ambos os formatos para NormalizedInput)
        logger.info(f"[{request_id}] Iniciando normalização...")
        normalized = body.to_normalized()
        
        # Registra métrica do tamanho da transcrição
        transcript_size = len(normalized.transcript.encode('utf-8'))
        record_transcript_size(transcript_size)
        
        # Log detalhes da normalização
        metadata_fields = sum([
            normalized.meeting_id is not None,
            normalized.customer_id is not None,
            normalized.customer_name is not None,
            normalized.banker_id is not None,
            normalized.banker_name is not None,
            normalized.meet_type is not None,
            normalized.meet_date is not None
        ])
        
        logger.info(
            f"[{request_id}] Normalização concluída | "
            f"transcript_len={len(normalized.transcript)} chars | "
            f"transcript_words={len(normalized.transcript.split())} words | "
            f"metadata_fields={metadata_fields}/7 | "
            f"meeting_id={normalized.meeting_id or 'will_extract'} | "
            f"customer_id={normalized.customer_id or 'will_extract'}"
        )
        
        # 2. Calcular idempotency_key e verificar cache
        idempotency_key = normalized.compute_idempotency_key()
        
        # Se temos uma chave válida, verificar cache
        if idempotency_key and idempotency_key != "no-idempotency-key-available":
            cached_result = get_from_cache(idempotency_key)
            
            if cached_result:
                # Cache HIT: retornar resultado cacheado sem processar
                logger.info(
                    f"🎯 [{request_id}] Retornando do cache (idempotente) | "
                    f"idempotency_key={idempotency_key[:16]}... | "
                    f"⏱️ duration={time.time() - start_time:.3f}s"
                )
                
                # Registra métrica de duração HTTP total (cache hit é rápido!)
                http_duration = time.time() - http_start_time
                record_http_duration("POST", "/analyze", http_duration)
                
                return AnalyzedMeeting(**cached_result)
            else:
                logger.info(
                    f"🔍 [{request_id}] Cache miss - processando normalmente | "
                    f"idempotency_key={idempotency_key[:16]}..."
                )
        else:
            logger.debug(
                f"ℹ️ [{request_id}] Sem idempotency_key válido - cache não aplicado"
            )
        
        # 3. Chamar o analyzer (LangChain + OpenAI)
        # Timer para duração da análise
        analysis_start = time.time()
        
        analyzed = await analyze_sentiment_chain(
            normalized=normalized,
            request_id=request_id
        )
        
        # Registra métrica de duração da análise
        analysis_duration = time.time() - analysis_start
        extraction_duration_seconds.observe(analysis_duration)
        
        # 4. Salvar resultado no cache (se temos idempotency_key válido)
        if idempotency_key and idempotency_key != "no-idempotency-key-available":
            save_to_cache(idempotency_key, analyzed.model_dump())
        
        # 5. Log sucesso com duração
        duration = time.time() - start_time
        logger.info(
            f"[{request_id}] Análise concluída com sucesso | "
            f"duration={duration:.2f}s | "
            f"meeting_id={analyzed.meeting_id} | "
            f"sentiment={analyzed.sentiment_label} | "
            f"score={analyzed.sentiment_score:.2f} | "
            f"summary_words={len(analyzed.summary.split())} | "
            f"key_points={len(analyzed.key_points)} | "
            f"action_items={len(analyzed.action_items)} | "
            f"risks={len(analyzed.risks)} | "
            f"idempotency_key={analyzed.idempotency_key[:16]}..."
        )
        
        # Registra métrica de reunião analisada com sucesso
        source = "raw_meeting" if body.raw_meeting else "transcript"
        meeting_type = analyzed.meet_type or "Unknown"
        record_meeting_extracted(source, meeting_type)
        
        # Registra métrica de duração HTTP total
        http_duration = time.time() - http_start_time
        record_http_duration("POST", "/analyze", http_duration)
        
        return analyzed
    
    except (RateLimitError, APITimeoutError, APIError) as e:
        # Erros de comunicação com OpenAI API → 502 Bad Gateway
        logger.error(
            f"[{request_id}] Erro de comunicação com OpenAI API | "
            f"type={type(e).__name__} | "
            f"error={str(e)[:200]}"
        )
        
        # Registra métrica de erro 502
        record_api_error("openai_communication_error", 502)
        
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "openai_communication_error",
                "message": (
                    "Erro ao comunicar com OpenAI API "
                    "(timeout, rate limit ou indisponibilidade). "
                    "Tente novamente em alguns instantes."
                ),
                "error_type": type(e).__name__,
                "request_id": request_id,
            }
        )
    
    except ValidationError as e:
        # Erro de validação: OpenAI retornou dados inválidos → 502 Bad Gateway
        # Este é um problema do serviço externo (OpenAI), não interno
        logger.error(
            f"[{request_id}] OpenAI retornou dados inválidos após repair | "
            f"errors={e.errors()}"
        )
        
        # Registra métrica de erro 502
        record_api_error("openai_invalid_response", 502)
        
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "openai_invalid_response",
                "message": (
                    "OpenAI retornou dados inválidos ou incompletos. "
                    "Tente novamente ou verifique se a transcrição está legível."
                ),
                "request_id": request_id,
            }
        )
    
    except Exception as e:
        # Qualquer outro erro não previsto
        logger.error(
            f"[{request_id}] Erro inesperado | "
            f"type={type(e).__name__} | "
            f"error={str(e)[:200]}"
        )
        
        # Registra métrica de erro 500
        record_api_error("internal_error", 500)
        
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "Erro interno ao processar a requisição",
                "request_id": request_id,
            }
        )


# ============================================================================
# DEBUG E MÉTRICAS
# ============================================================================

# ENDPOINT PARA DEBUG DAS MÉTRICAS
@app.get("/metrics", tags=["Debug"])
async def debug_metrics():
    """Endpoint para testar métricas"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ============================================================================
# ENTRYPOINT (para desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Roda o servidor em modo de desenvolvimento
    # Para produção, use: uvicorn app.main:app --host 0.0.0.0 --port 8000
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Hot reload em desenvolvimento
        log_level="info",
    )

