"""
Funções auxiliares compartilhadas para processamento com LLMs.

Este módulo contém funções utilitárias usadas tanto pelo Extractor
quanto pelo Analyzer para manter o código DRY (Don't Repeat Yourself).

Funções disponíveis:
- log_retry_attempt: Callback para logging de tentativas de retry
- extract_and_record_token_usage: Extração de tokens da resposta LLM
- sanitize_transcript_for_log: Truncamento de transcrição para logs seguros
- prepare_metadata_for_prompt: Preparação de metadados para envio ao LLM
"""

import json
import logging
from typing import Any
from tenacity import RetryCallState

# Schemas internos
from app.models.schemas_common import NormalizedInput

# Métricas Prometheus
from app.metrics.collectors import record_openai_tokens


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Logger (configurado centralmente via app.config.logging_config)
logger = logging.getLogger(__name__)

# Constante de retry (importada dos módulos que usam)
MAX_RETRY_ATTEMPTS = 3


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def log_retry_attempt(retry_state: RetryCallState) -> None:
    """
    Callback para logar a falha de uma tentativa antes de um retry.
    
    Esta função é usada como callback no decorator @retry do Tenacity.
    Extrai informações do estado do retry e loga de forma estruturada.
    
    Args:
        retry_state: Estado do retry fornecido pelo Tenacity
    """
    attempt_number = retry_state.attempt_number
    
    # Extrai request_id dos argumentos da função que está sendo retryada
    # (primeiro argumento é normalized, segundo é request_id)
    if retry_state.args and len(retry_state.args) >= 2:
        request_id = retry_state.args[1]
    else:
        request_id = "-"
    
    # Obtém o tipo de erro que causou a falha
    error_type = "Unknown"
    if retry_state.outcome and retry_state.outcome.exception():
        error_type = type(retry_state.outcome.exception()).__name__
    
    # Log estruturado com informações da tentativa
    logger.warning(
        f"[RETRY] [{request_id}] Falha na tentativa {attempt_number}/{MAX_RETRY_ATTEMPTS}. "
        f"Tentando novamente... | erro={error_type}"
    )


def extract_and_record_token_usage(raw_response: Any, model: str, request_id: str) -> None:
    """
    Extrai informações de uso de tokens da resposta do LLM e registra nas métricas Prometheus.
    
    Esta função tenta múltiplos métodos para acessar os dados de token usage,
    já que diferentes versões do LangChain podem expor esses dados em estruturas diferentes.
    
    Args:
        raw_response: Resposta bruta do LLM (antes do parser JSON)
        model: Nome do modelo OpenAI usado (ex: "gpt-4o")
        request_id: ID de correlação para logs
    """
    try:
        # Tenta extrair tokens da resposta RAW usando múltiplos métodos
        usage = None
        
        # Método 1: response_metadata (LangChain padrão)
        if hasattr(raw_response, 'response_metadata'):
            usage = raw_response.response_metadata.get('token_usage')
        
        # Método 2: usage_metadata (versões mais recentes)
        elif hasattr(raw_response, 'usage_metadata'):
            usage = raw_response.usage_metadata
            
        if usage:
            # Extrai valores dos tokens (suporta dict ou objeto)
            if isinstance(usage, dict):
                prompt_tokens = usage.get('prompt_tokens', 0)
                completion_tokens = usage.get('completion_tokens', 0) 
                total_tokens = usage.get('total_tokens', 0)
            else:
                prompt_tokens = getattr(usage, 'prompt_tokens', 0)
                completion_tokens = getattr(usage, 'completion_tokens', 0)
                total_tokens = getattr(usage, 'total_tokens', 0)
                
            # Registra métricas se houver dados válidos
            if total_tokens > 0:
                record_openai_tokens(model, prompt_tokens, completion_tokens, total_tokens)
                logger.debug(f"[{request_id}] 💰 Tokens registrados: {total_tokens} total (prompt: {prompt_tokens}, completion: {completion_tokens})")
            else:
                logger.debug(f"[{request_id}] Token usage encontrado mas valores são zero")
        else:
            logger.debug(f"[{request_id}] Token usage não encontrado na resposta")
            
    except Exception as e:
        logger.error(f"[{request_id}] ❌ Erro ao extrair tokens: {e}")

def sanitize_transcript_for_log(transcript: str, max_chars: int = 300) -> str:
    """
    Trunca a transcrição para log seguro (sem PII completa).
    
    Esta função é usada para limitar o tamanho de transcrições nos logs,
    evitando expor dados pessoais completos e mantendo os logs legíveis.
    
    Args:
        transcript: Texto completo da transcrição
        max_chars: Número máximo de caracteres a manter (padrão: 300)
    
    Returns:
        str: Transcrição truncada com indicador de truncamento
    
    Example:
        >>> long_text = "Cliente: Bom dia..." * 100
        >>> sanitize_transcript_for_log(long_text, 50)
        "Cliente: Bom dia...Cliente: Bom dia...Cliente: Bo... (truncado, total: 1500 chars)"
    """
    if len(transcript) <= max_chars:
        return transcript
    return transcript[:max_chars] + f"... (truncado, total: {len(transcript)} chars)"


def prepare_metadata_for_prompt(normalized: NormalizedInput) -> str:
    """
    Prepara os metadados para envio ao LLM em formato JSON legível.
    
    Converte os campos de metadados do NormalizedInput em um JSON formatado,
    removendo valores None para clareza. O LLM verá apenas os dados fornecidos.
    
    Args:
        normalized: Dados normalizados da reunião
    
    Returns:
        str: JSON formatado dos metadados (excluindo transcript)
    
    Example:
        >>> normalized = NormalizedInput(
        ...     transcript="...",
        ...     meeting_id="MTG123",
        ...     customer_id="CUST456",
        ...     customer_name=None  # Será removido do JSON
        ... )
        >>> prepare_metadata_for_prompt(normalized)
        '{"meeting_id": "MTG123", "customer_id": "CUST456"}'
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
