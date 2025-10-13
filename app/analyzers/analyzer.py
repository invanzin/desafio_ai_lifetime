"""
Módulo de análise de sentimento e insights usando OpenAI.

Este módulo implementa a lógica principal de análise de sentimento de transcrições
de reuniões bancárias, utilizando LangChain e OpenAI para processar o texto
e retornar análises estruturadas em formato JSON.

Funcionalidades principais:
- Análise de sentimento (positive/neutral/negative) com score 0.0-1.0
- Classificação automática com validação de consistência label ↔ score
- Geração de insights estratégicos e identificação de riscos
- Resumos executivos (100-200 palavras)
- Extração inteligente de metadados (com prioridade para dados fornecidos)
- Validação automática com Pydantic
- Retry com backoff exponencial para resiliência
- Tentativa de reparo automático para JSONs malformados
- Logs estruturados e seguros (sem PII completa)
- Métricas Prometheus integradas
"""

import os
import json
import time
import asyncio
from typing import Optional, Dict
from datetime import datetime
from dotenv import load_dotenv

# LLM
from langchain_core.output_parsers import JsonOutputParser
from langchain import hub

# Retry/Resiliência
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError, APIError

# Logging
import logging

# Schemas internos
from app.models.schemas_common import NormalizedInput
from app.models.schemas_analyze import AnalyzedMeeting

# Componentes compartilhados
from llm.openai_client import default_client
from app.metrics.collectors import (
    record_openai_request,
    record_openai_error,
    get_model_from_env,
    record_repair_attempt
)
from utils import (
    log_retry_attempt,
    extract_and_record_token_usage,
    sanitize_transcript_for_log,
    prepare_metadata_for_prompt,
    repair_json,
)

# ============================================================================
# CONSTANTES DE CONFIGURAÇÃO
# ============================================================================

# Configuração de retry
MAX_RETRY_ATTEMPTS = 3
RETRY_WAIT_MULTIPLIER = 0.5
RETRY_WAIT_MIN = 0.5
RETRY_WAIT_MAX = 5.0

# Timeouts
LLM_TIMEOUT_SECONDS = 30
REPAIR_TIMEOUT_SECONDS = 15

# Placeholders
IDEMPOTENCY_KEY_PLACEHOLDER = "no-idempotency-key-available"

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

load_dotenv()
logger = logging.getLogger(__name__)

# ============================================================================
# INICIALIZAÇÃO DO LLM E PROMPT
# ============================================================================

llm = default_client.get_llm()
parser = JsonOutputParser()

# Carrega o prompt do Analyzer do LangChain Hub
prompt_hub_name = os.getenv("ANALYZER_PROMPT_HUB_NAME")
if not prompt_hub_name:
    raise ValueError("ANALYZER_PROMPT_HUB_NAME não definido no arquivo .env")

try:
    logger.info(f"🔄 Carregando prompt do Hub: {prompt_hub_name}")
    prompt = hub.pull(prompt_hub_name)
    logger.debug(f"✅ Prompt do Analyzer carregado com sucesso do Hub")
except Exception as e:
    logger.error(f"❌ Falha ao carregar o prompt '{prompt_hub_name}' do Hub: {e}")
    raise

# ============================================================================
# CHAIN
# ============================================================================

chain_raw = prompt | llm

# ============================================================================
# FUNÇÃO PRINCIPAL DE ANÁLISE
# ============================================================================

@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
    before_sleep=log_retry_attempt,
)
async def analyze_sentiment_chain(
    normalized: NormalizedInput,
    request_id: str = "-"
    ) -> AnalyzedMeeting:
    """
    Analisa sentimento e gera insights de uma reunião usando OpenAI + LangChain.
    
    Esta é a função principal do módulo. Orquestra todo o processo de análise:
    1. Valida dados de entrada
    2. Prepara os dados para o prompt
    3. Chama o LLM com retry automático (até 3 tentativas)
    4. Extrai tokens e registra métricas Prometheus
    5. Valida o resultado com Pydantic (consistência label ↔ score)
    6. Tenta reparar se a validação falhar
    7. Preenche a chave de idempotência
    8. Retorna o objeto validado
    
    Resiliência:
    - Retry automático em caso de rate limit (429) ou timeout
    - Backoff exponencial: 0.5s → 1s → 2s entre tentativas
    - Timeout de 30s por chamada (configurado no LLM)
    
    Validações Especiais:
    - sentiment_label deve ser "positive", "neutral" ou "negative"
    - sentiment_score deve estar entre 0.0 e 1.0
    - Consistência: positive (≥0.6), neutral (0.4-0.6), negative (<0.4)
    - summary deve ter exatamente 100-200 palavras
    
    Args:
        normalized: Dados normalizados da reunião (transcript + metadados opcionais)
        request_id: ID de correlação para logs (padrão: "-")
    
    Returns:
        AnalyzedMeeting: Objeto validado com análise completa de sentimento e insights
    
    Raises:
        ValueError: Se dados de entrada forem inválidos
        RateLimitError: Se exceder rate limit após 3 tentativas
        APITimeoutError: Se timeout após 3 tentativas
        ValidationError: Se validação Pydantic falhar mesmo após reparo
        Exception: Outros erros inesperados
    
    Example:
        >>> normalized = NormalizedInput(
        ...     transcript="Cliente: Estou muito satisfeito... Banker: Que ótimo...",
        ...     meeting_id="MTG123",
        ...     customer_id="CUST456",
        ...     meet_date=datetime(2025, 9, 10, 14, 30)
        ... )
        >>> result = await analyze_sentiment_chain(normalized, request_id="req-123")
        >>> print(result.sentiment_label, result.sentiment_score)
        "positive" 0.85
    """
    # Log início (sem PII completa)
    logger.info(
        f"[ANALYZE] [{request_id}] 🧠 Iniciando análise de sentimento | "
        f"transcript_len={len(normalized.transcript)} | "
        f"has_metadata={'sim' if normalized.meeting_id else 'não'}"
    )

    # Prepara metadados para o prompt
    metadata_json = prepare_metadata_for_prompt(normalized)
    metadata_fields_count = len(json.loads(metadata_json)) if metadata_json != '{}' else 0
    
    logger.info(
        f"[{request_id}] 🤖 Chamada à OpenAI | "
        f"metadata_fields={metadata_fields_count} | "
        f"transcript_preview={sanitize_transcript_for_log(normalized.transcript, 100)}"
    )

    # Chama o LLM (com retry automático via decorator @retry)
    llm_start = time.time()
    
    try:
        # Prepara a configuração para o LangSmith
        trace_config = {
            "metadata": {
                "request_id": request_id,
                "transcript_length": len(normalized.transcript),
                "has_metadata_input": bool(metadata_fields_count > 0)
            },
            "run_name": f"Analyze Meeting - {request_id}"
        }

        # 🔥 PRIMEIRA CHAMADA: Chain RAW para capturar metadados
        raw_response = await chain_raw.ainvoke(
            {
                "transcript": normalized.transcript,
                "metadata_json": metadata_json
            },
            config=trace_config
        )
        
        # EXTRAI TOKENS DA RESPOSTA RAW (Prometheus)
        model = get_model_from_env()
        record_openai_request(model, "success")
        
        # Extrai e registra tokens (Prometheus)
        extract_and_record_token_usage(raw_response, model, request_id)
        
        # Parse manual do conteúdo JSON
        raw_output = parser.parse(raw_response.content)
        
        llm_duration = time.time() - llm_start
        logger.info(
            f"[RESPONSE] [{request_id}] ✅ OpenAI API respondeu com sucesso | "
            f"duration={llm_duration:.2f}s | "
            f"output_type={'dict' if isinstance(raw_output, dict) else type(raw_output).__name__} | "
            f"output_keys={list(raw_output.keys()) if isinstance(raw_output, dict) else 'N/A'}"
        )

    except (RateLimitError, APITimeoutError, APIError) as e:
        llm_duration = time.time() - llm_start
        logger.error(
            f"[ERROR] [{request_id}] ❌ FALHA após {MAX_RETRY_ATTEMPTS} tentativas de chamada à OpenAI | "
            f"total_duration={llm_duration:.2f}s | "
            f"error_type={type(e).__name__} | "
            f"error_msg={str(e)[:200]}"
        )
        
        # Registra métricas de erro da OpenAI
        model = get_model_from_env()
        record_openai_request(model, "error")
        record_openai_error(type(e).__name__)
        
        raise

    # Tenta validar com Pydantic
    try:
        analyzed = AnalyzedMeeting.model_validate(raw_output)
        logger.debug(f"[SUCCESS] [{request_id}] ✅ Validação Pydantic OK na primeira tentativa")
        
        # Log sucesso final imediatamente após validação bem-sucedida
        logger.info(
            f"[SUCCESS] [{request_id}] 🎉 Análise concluída com sucesso | "
            f"meeting_id={analyzed.meeting_id} | "
            f"sentiment={analyzed.sentiment_label} | "
            f"score={analyzed.sentiment_score:.2f} | "
            f"summary_words={len(analyzed.summary.split())} | "
            f"key_points={len(analyzed.key_points)} | "
            f"action_items={len(analyzed.action_items)} | "
            f"risks={len(analyzed.risks)}"
        )
    
    except Exception as validation_error:
        # Validação falhou → tenta reparar UMA vez
        logger.warning(
            f"[VALIDATION] [{request_id}] ⚠️ Validação Pydantic falhou | "
            f"erro={type(validation_error).__name__}: {str(validation_error)[:200]}"
        )
        try:
            repaired_output = await repair_json(
                malformed_output=raw_output,
                validation_error=str(validation_error),
                normalized=normalized,
                request_id=request_id,
                schema_type="analyze"
            )
            # Tenta validar novamente
            analyzed = AnalyzedMeeting.model_validate(repaired_output)
            logger.info(f"[SUCCESS] [{request_id}] ✅ Validação OK após reparo")
            
            # Log sucesso final imediatamente após validação bem-sucedida
            logger.info(
                f"[SUCCESS] [{request_id}] 🎉 Análise concluída com sucesso | "
                f"meeting_id={analyzed.meeting_id} | "
                f"sentiment={analyzed.sentiment_label} | "
                f"score={analyzed.sentiment_score:.2f} | "
                f"summary_words={len(analyzed.summary.split())} | "
                f"key_points={len(analyzed.key_points)} | "
                f"action_items={len(analyzed.action_items)} | "
                f"risks={len(analyzed.risks)}"
            )
            
            # Registra métrica de reparo bem-sucedido
            record_repair_attempt("success")
        
        except Exception as repair_error:
            logger.error(
                f"[ERROR] [{request_id}] ❌ Validação falhou mesmo após reparo | "
                f"erro={type(repair_error).__name__}: {str(repair_error)[:200]}"
            )
            
            # Registra métrica de reparo falhado
            record_repair_attempt("failed")
            
            raise

    # Preenche a chave de idempotência se possível
    idem_key = normalized.compute_idempotency_key()
    if idem_key:
        analyzed.idempotency_key = idem_key
        logger.debug(f"[IDEM] [{request_id}] 🔑 Idempotency key calculada: {idem_key[:16]}...")
    else:
        # Se não for possível calcular, usa placeholder
        analyzed.idempotency_key = IDEMPOTENCY_KEY_PLACEHOLDER
        logger.warning(
            f"[IDEM] [{request_id}] ⚠️ Não foi possível calcular idempotency_key "
            f"(faltam meeting_id, meet_date ou customer_id)"
        )
    
    return analyzed     