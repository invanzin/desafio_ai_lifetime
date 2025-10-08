"""
Módulo de extração de informações estruturadas de reuniões usando OpenAI.

Este módulo implementa a lógica principal de extração de dados de transcrições
de reuniões bancárias, utilizando LangChain e OpenAI para processar o texto
e retornar informações estruturadas em formato JSON.

Funcionalidades principais:
- Extração inteligente de metadados (com prioridade para dados fornecidos)
- Geração de resumos executivos (100-200 palavras)
- Identificação de pontos-chave, ações e tópicos
- Validação automática com Pydantic
- Retry com backoff exponencial para resiliência
- Tentativa de reparo automático para JSONs malformados
- Logs estruturados e seguros (sem PII completa)
"""

import os
import json
import asyncio
from typing import Optional
from dotenv import load_dotenv

# LLM
# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain import hub

# Retry/Resiliência
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
    RetryCallState,
)

# OpenAI exceptions
from openai import RateLimitError, APITimeoutError, APIError

# Logging estruturado
import logging

# Schemas internos
from app.models.schemas_common import NormalizedInput
from app.models.schemas_extract import ExtractedMeeting

from llm.openai_client import default_client

# Métricas Prometheus
from app.metrics.collectors import (
    record_openai_request,
    record_openai_error,
    record_openai_tokens,
    record_repair_attempt,
    get_model_from_env,
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

# Placeholders e valores padrão
IDEMPOTENCY_KEY_PLACEHOLDER = "no-idempotency-key-available"
DEFAULT_SOURCE = "lftm-challenge"

# Limites de validação
MIN_SUMMARY_WORDS = 100
MAX_SUMMARY_WORDS = 200

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Logger (configurado centralmente via app.config.logging_config)
logger = logging.getLogger(__name__)


# ============================================================================
# INICIALIZAÇÃO DO LLM E PROMPT
# ============================================================================

# LLM
llm = default_client.get_llm()

# Parser para extrair JSON da resposta do LLM
parser = JsonOutputParser()

# Carrega o nome do prompt do ambiente
prompt_hub_name = os.getenv("EXTRACTOR_PROMPT_HUB_NAME")
if not prompt_hub_name:
    raise ValueError("EXTRACTOR_PROMPT_HUB_NAME não definido no arquivo .env")

try:
    # Puxa o prompt diretamente do LangChain Hub
    logger.info(f"🔄 Carregando prompt do Hub: {prompt_hub_name}")
    prompt = hub.pull(prompt_hub_name)
    logger.debug(f"✅ Prompt carregado com sucesso do LangChain Hub")
except Exception as e:
    logger.error(f"❌ Falha ao carregar o prompt '{prompt_hub_name}' do Hub: {e}")
    raise

# ============================================================================
# CHAIN
# ============================================================================

# Chain SEM parser (para capturar metadados) - Parser é feito após a captura dos metadados (tokens)
chain_raw = prompt | llm

# Chain completa: prompt → LLM → parser JSON  
#chain = prompt | llm | parser


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================




def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """Callback para logar a falha de uma tentativa antes de um retry."""
    attempt_number = retry_state.attempt_number
    
    # Extrai request_id
    if retry_state.args and len(retry_state.args) >= 2:
        request_id = retry_state.args[1]
    else:
        request_id = "-"
    
    # Obtém o tipo de erro
    error_type = "Unknown"
    if retry_state.outcome and retry_state.outcome.exception():
        error_type = type(retry_state.outcome.exception()).__name__
    
    # Mensagem de log mais clara
    logger.warning(
        f"[RETRY] [{request_id}] ⚠️ Falha na tentativa {attempt_number}/{MAX_RETRY_ATTEMPTS}. "
        f"Tentando novamente... | erro={error_type}"
    )

def _extract_and_record_token_usage(raw_response, model: str, request_id: str) -> None:
    """
    Extrai informações de uso de tokens da resposta do LLM e registra nas métricas.
    
    Args:
        raw_response: Resposta bruta do LLM
        model: Modelo usado (para métricas)
        request_id: ID de correlação para logs
    """
    try:
        # Extrai tokens da resposta RAW
        usage = None
        if hasattr(raw_response, 'response_metadata'):
            usage = raw_response.response_metadata.get('token_usage')
        elif hasattr(raw_response, 'usage_metadata'):
            usage = raw_response.usage_metadata
            
        if usage:
            # Extrai valores dos tokens
            if isinstance(usage, dict):
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0) 
                total_tokens = usage.get('total_tokens', 0)
            else:
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', 0)
                
            if total_tokens > 0:
                record_openai_tokens(model, prompt_tokens, completion_tokens, total_tokens)
                logger.debug(f"[{request_id}] 💰 Tokens registrados: {total_tokens} total (prompt: {prompt_tokens}, completion: {completion_tokens})")
            else:
                logger.debug(f"[{request_id}] Token usage encontrado mas valores são zero")
        else:
            logger.debug(f"[{request_id}] Token usage não encontrado na resposta")
            
    except Exception as e:
        logger.error(f"[{request_id}] ❌ Erro ao extrair tokens: {e}")

def _sanitize_transcript_for_log(transcript: str, max_chars: int = 300) -> str:
    """
    Trunca a transcrição para log seguro (sem PII completa).
    
    Args:
        transcript: Texto completo da transcrição
        max_chars: Número máximo de caracteres a manter (padrão: 300)
    
    Returns:
        str: Transcrição truncada com indicador de truncamento
    """
    if len(transcript) <= max_chars:
        return transcript
    return transcript[:max_chars] + f"... (truncado, total: {len(transcript)} chars)"


def _prepare_metadata_for_prompt(normalized: NormalizedInput) -> str:
    """
    Prepara os metadados para envio ao LLM em formato JSON legível.
    
    Args:
        normalized: Dados normalizados da reunião
    
    Returns:
        str: JSON formatado dos metadados (excluindo transcript)
    """
    metadata_dict = {
        "meeting_id": normalized.meeting_id,
        "customer_id": normalized.customer_id,
        "customer_name": normalized.customer_name,
        "banker_id": normalized.banker_id,
        "banker_name": normalized.banker_name,
        "meet_type": normalized.meet_type,
        "meet_date": normalized.meet_date.isoformat() if normalized.meet_date else None,
    }
    
    # Remove valores None para clareza (LLM verá apenas o que foi fornecido)
    metadata_dict = {k: v for k, v in metadata_dict.items() if v is not None}
    
    return json.dumps(metadata_dict, ensure_ascii=False, indent=2)


# ============================================================================
# FUNÇÃO DE REPARO
# ============================================================================

async def _repair_json(
    malformed_output: dict,
    validation_error: str,
    normalized: NormalizedInput,
    request_id: str
    ) -> dict:
    """
    Tenta reparar um JSON malformado reenviando ao LLM com o erro.
    
    Esta função é chamada quando a validação Pydantic falha na primeira tentativa.
    Envia o JSON original + mensagem de erro de volta ao LLM, pedindo correção.
    
    Args:
        malformed_output: O JSON original que falhou na validação
        validation_error: Mensagem de erro da validação Pydantic
        normalized: Dados normalizados da reunião (para contexto)
        request_id: ID de correlação da requisição
    
    Returns:
        dict: JSON reparado (esperançosamente válido)
    
    Raises:
        Exception: Se a chamada ao LLM falhar
    """
    logger.warning(
        f"[{request_id}] 🔧 Tentando reparar JSON inválido. Erro: {validation_error[:200]}"
    )
    
    repair_prompt = ChatPromptTemplate.from_messages([
        ("system", """Você é um corretor de JSON especializado.
        Corrija o JSON abaixo para atender ao schema especificado.
        Mantenha o máximo de informações corretas possível.
        Responda APENAS com o JSON corrigido, sem explicações."""),
                
        ("human", """JSON MALFORMADO:
        {malformed_json}

        ERRO DE VALIDAÇÃO:
        {error}

        TRANSCRIÇÃO ORIGINAL (para referência se precisar):
        {transcript_preview}

        SCHEMA ESPERADO:
        - meeting_id, customer_id, customer_name (strings obrigatórias)
        - banker_id, banker_name (strings obrigatórias)
        - meet_type (string obrigatória)
        - meet_date (datetime ISO 8601 obrigatório)
        - summary (string com 100-200 palavras EXATAS)
        - key_points (array de strings)
        - action_items (array de strings)
        - topics (array de strings)
        - source: "lftm-challenge"
        - idempotency_key: "será preenchido"
        - transcript_ref: null
        - duration_sec: null

        Retorne o JSON corrigido:""")
            ])
    
    repair_chain = repair_prompt | llm | parser
    
    try:

        # Configuração para o trace do reparo LangSmith
        repair_trace_config = {
            "metadata": {"request_id": request_id},
            "run_name": f"Repair JSON - {request_id}"
        }

        # Adiciona timeout para operação de reparo
        repaired = await asyncio.wait_for(
        repair_chain.ainvoke(
            {
                "malformed_json": json.dumps(malformed_output, ensure_ascii=False, indent=2),
                "error": str(validation_error),
                "transcript_preview": _sanitize_transcript_for_log(normalized.transcript, 500)
            },
            config=repair_trace_config # Configuração para o trace do reparo LangSmith
        ),
        timeout=REPAIR_TIMEOUT_SECONDS
    )
        
        logger.info(f"[{request_id}] ✅ JSON reparado com sucesso")
        return repaired
        
    except asyncio.TimeoutError:
        logger.error(f"[{request_id}] ❌ Timeout na operação de reparo ({REPAIR_TIMEOUT_SECONDS}s)")
        raise Exception(f"Timeout na operação de reparo: {REPAIR_TIMEOUT_SECONDS}s")
    except Exception as e:
        logger.error(f"[{request_id}] ❌ Erro durante reparo: {e}")
        raise


# ============================================================================
# FUNÇÃO PRINCIPAL DE EXTRAÇÃO
# ============================================================================

@retry(
    reraise=True,
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS), # máximo 3 tentativas
    wait=wait_exponential(multiplier=RETRY_WAIT_MULTIPLIER, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX), # backogg: 0.5s, 1s, 2s
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)), # Tenta novamente apenas se for esses erros
    before_sleep=_log_retry_attempt, # log personalizado antes de cada retry
    )
async def extract_meeting_chain(
    normalized: NormalizedInput,
    request_id: str = "-"
    ) -> ExtractedMeeting:
    """
    Extrai informações estruturadas de uma reunião usando OpenAI + LangChain.
    
    Esta é a função principal do módulo. Orquestra todo o processo de extração:
    1. Valida dados de entrada
    2. Prepara os dados para o prompt
    3. Chama o LLM com retry automático (até 3 tentativas)
    4. Valida o resultado com Pydantic
    5. Tenta reparar se a validação falhar
    6. Preenche a chave de idempotência
    7. Retorna o objeto validado
    
    Resiliência:
    - Retry automático em caso de rate limit (429) ou timeout
    - Backoff exponencial: 0.5s → 1s → 2s entre tentativas
    - Timeout de 30s por chamada (configurado no LLM)
    
    Args:
        normalized: Dados normalizados da reunião (transcript + metadados opcionais)
        request_id: ID de correlação para logs (padrão: "-")
    
    Returns:
        ExtractedMeeting: Objeto validado com todas as informações extraídas
    
    Raises:
        ValueError: Se dados de entrada forem inválidos
        RateLimitError: Se exceder rate limit após 3 tentativas
        APITimeoutError: Se timeout após 3 tentativas
        ValidationError: Se validação Pydantic falhar mesmo após reparo
        Exception: Outros erros inesperados
    
    Example:
        >>> normalized = NormalizedInput(
        ...     transcript="Cliente: Olá... Banker: Bom dia...",
        ...     meeting_id="MTG123",
        ...     customer_id="CUST456",
        ...     meet_date=datetime(2025, 9, 10, 14, 30)
        ... )
        >>> result = await extract_meeting_chain(normalized, request_id="req-123")
        >>> print(result.summary)
        "Reunião focou em..."
    """
    
    
    # Log início (sem PII completa)
    logger.info(
        f"[{request_id}] 🚀 Iniciando extração | "
        f"transcript_len={len(normalized.transcript)} | "
        f"has_metadata={'sim' if normalized.meeting_id else 'não'}"
    )
    
    # Prepara metadados para o prompt
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_fields_count = len(json.loads(metadata_json)) if metadata_json != '{}' else 0
    
    logger.info(
        f"[{request_id}] 🤖 Chamada à OpenAI | "
        f"metadata_fields={metadata_fields_count} | "
        f"transcript_preview={_sanitize_transcript_for_log(normalized.transcript, 100)}"
    )
    
    # Chama o LLM (com retry automático via decorator @retry)
    import time
    llm_start = time.time()
    
    try:

        # Prepara a configuração para o LangSmith
        trace_config = {
            "metadata": {
                "request_id": request_id,
                "transcript_length": len(normalized.transcript),
                "has_metadata_input": bool(metadata_fields_count > 0)
            },
            "run_name": f"Extract Meeting - {request_id}"
        }

        # 🔥 PRIMEIRA CHAMADA: Chain RAW para capturar metadados
        raw_response = await chain_raw.ainvoke(
            {
                "transcript": normalized.transcript,
                "metadata_json": metadata_json
            },
            config=trace_config # configuração para o LangSmith
        )
        
        # 🔥 EXTRAI TOKENS DA RESPOSTA RAW (Prometheus)
        model = get_model_from_env()    
        record_openai_request(model, "success")
        
        # Extrai e registra tokens (Prometheus)
        _extract_and_record_token_usage(raw_response, model, request_id)
        
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
        extracted = ExtractedMeeting.model_validate(raw_output)
        logger.debug(f"[SUCCESS] [{request_id}] ✅ Validação Pydantic OK na primeira tentativa")
        
        # Log sucesso final imediatamente após validação bem-sucedida
        logger.info(
            f"[SUCCESS] [{request_id}] 🎉 Extração concluída com sucesso | "
            f"meeting_id={extracted.meeting_id} | "
            f"summary_words={len(extracted.summary.split())} | "
            f"key_points={len(extracted.key_points)} | "
            f"action_items={len(extracted.action_items)}"
        )
        
    except Exception as validation_error:
        # Validação falhou → tenta reparar UMA vez
        logger.warning(
            f"[{request_id}] ⚠️ Validação Pydantic falhou | "
            f"erro={type(validation_error).__name__}: {str(validation_error)[:200]}"
        )
        
        try:
            
            repaired_output = await _repair_json(
                malformed_output=raw_output,
                validation_error=str(validation_error),
                normalized=normalized,
                request_id=request_id
            )
            
            # Tenta validar novamente
            extracted = ExtractedMeeting.model_validate(repaired_output)
            logger.info(f"[SUCCESS] [{request_id}] ✅ Validação OK após reparo")
            
            # Log sucesso final imediatamente após validação bem-sucedida
            logger.info(
                f"[SUCCESS] [{request_id}] 🎉 Extração concluída com sucesso | "
                f"meeting_id={extracted.meeting_id} | "
                f"summary_words={len(extracted.summary.split())} | "
                f"key_points={len(extracted.key_points)} | "
                f"action_items={len(extracted.action_items)}"
            )
            
            # Registra métrica de reparo bem-sucedido
            record_repair_attempt("success")
            
        except Exception as repair_error:
            logger.error(
                f"[{request_id}] ❌ Validação falhou mesmo após reparo | "
                f"erro={type(repair_error).__name__}: {str(repair_error)[:200]}"
            )
            
            # Registra métrica de reparo falhado
            record_repair_attempt("failed")
            
            raise
    
    # Preenche a chave de idempotência se possível
    idem_key = normalized.compute_idempotency_key()
    if idem_key:
        extracted.idempotency_key = idem_key
        logger.debug(f"[{request_id}] 🔑 Idempotency key calculada: {idem_key[:16]}...")
    else:
        # Se não for possível calcular, usa placeholder
        extracted.idempotency_key = IDEMPOTENCY_KEY_PLACEHOLDER
        logger.warning(
            f"[{request_id}] ⚠️ Não foi possível calcular idempotency_key "
            f"(faltam meeting_id, meet_date ou customer_id)"
        )
    
    return extracted

