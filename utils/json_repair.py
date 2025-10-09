"""
Módulo de reparo de JSON malformado usando LLM.

Este módulo contém a lógica de reparo automático de JSONs que falharam
na validação Pydantic. É usado tanto pelo Extractor quanto pelo Analyzer.

Características:
- Parametrizável por tipo de schema (extract/analyze)
- Timeout configurável (15s padrão)
- LangSmith tracing integrado
- Logging estruturado
"""

import json
import asyncio
import logging
from typing import Literal

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Schemas internos
from app.models.schemas_common import NormalizedInput

# LLM client
from llm.openai_client import default_client

# Utilitários compartilhados
from utils.common import sanitize_transcript_for_log


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Logger (configurado centralmente via app.config.logging_config)
logger = logging.getLogger(__name__)

# Timeout para operação de reparo (menor que LLM principal)
REPAIR_TIMEOUT_SECONDS = 15

# LLM e Parser
llm = default_client.get_llm()
parser = JsonOutputParser()


# ============================================================================
# SCHEMAS ESPERADOS POR TIPO
# ============================================================================

EXTRACTOR_SCHEMA = """
- meeting_id, customer_id, customer_name (strings obrigatórias)
- banker_id, banker_name (strings obrigatórias)
- meet_type (string obrigatória)
- meet_date (datetime ISO 8601 obrigatório)
- summary (string com 100-200 palavras EXATAS)
- key_points (array de strings)
- action_items (array de strings)
- topics (array de strings)
- source: "lftm-challenge"
- idempotency_key: será preenchido externamente
- transcript_ref: null
- duration_sec: null
"""

ANALYZER_SCHEMA = """
- meeting_id, customer_id, customer_name (strings obrigatórias)
- banker_id, banker_name (strings obrigatórias)
- meet_type (string obrigatória)
- meet_date (datetime ISO 8601 obrigatório)
- sentiment_label: "positive"/"neutral"/"negative" (string obrigatória)
- sentiment_score: float entre 0.0 e 1.0 (obrigatório)
- summary (string com 100-200 palavras EXATAS)
- key_points (array de strings)
- action_items (array de strings)
- risks (array de strings, pode ser vazio)
- source: "lftm-challenge"
- idempotency_key: será preenchido externamente
"""


# ============================================================================
# FUNÇÃO DE REPARO
# ============================================================================

async def repair_json(
    malformed_output: dict,
    validation_error: str,
    normalized: NormalizedInput,
    request_id: str,
    schema_type: Literal["extract", "analyze"] = "extract"
) -> dict:
    """
    Tenta reparar um JSON malformado reenviando ao LLM com o erro.
    
    Esta função é chamada quando a validação Pydantic falha na primeira tentativa.
    Envia o JSON original + mensagem de erro de volta ao LLM, pedindo correção.
    
    A função é parametrizada por `schema_type` para suportar diferentes schemas:
    - "extract": Para ExtractedMeeting (campos: topics, etc.)
    - "analyze": Para AnalyzedMeeting (campos: sentiment_label, risks, etc.)
    
    Args:
        malformed_output: O JSON original que falhou na validação
        validation_error: Mensagem de erro da validação Pydantic
        normalized: Dados normalizados da reunião (para contexto)
        request_id: ID de correlação da requisição
        schema_type: Tipo de schema a ser reparado ("extract" ou "analyze")
    
    Returns:
        dict: JSON reparado (esperançosamente válido)
    
    Raises:
        asyncio.TimeoutError: Se a operação demorar mais de REPAIR_TIMEOUT_SECONDS
        Exception: Se a chamada ao LLM falhar
    
    Example:
        >>> repaired = await repair_json(
        ...     malformed_output={"meeting_id": "MTG123", "summary": "texto curto"},
        ...     validation_error="summary deve ter 100-200 palavras",
        ...     normalized=normalized_input,
        ...     request_id="req-123",
        ...     schema_type="extract"
        ... )
    """
    logger.warning(
        f"[REPAIR] [{request_id}] 🔧 Tentando reparar JSON inválido | "
        f"schema_type={schema_type} | "
        f"erro={validation_error[:200]}"
    )
    
    # Seleciona o schema esperado baseado no tipo
    expected_schema = EXTRACTOR_SCHEMA if schema_type == "extract" else ANALYZER_SCHEMA
    
    # Cria o prompt de reparo
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
{expected_schema}

Retorne o JSON corrigido:""")
    ])
    
    # Cria a chain de reparo
    repair_chain = repair_prompt | llm | parser
    
    try:
        # Configuração para o trace do reparo no LangSmith
        repair_trace_config = {
            "metadata": {
                "request_id": request_id,
                "schema_type": schema_type,
                "operation": "repair_json"
            },
            "run_name": f"Repair JSON ({schema_type}) - {request_id}"
        }

        # Adiciona timeout para operação de reparo
        repaired = await asyncio.wait_for(
            repair_chain.ainvoke(
                {
                    "malformed_json": json.dumps(malformed_output, ensure_ascii=False, indent=2),
                    "error": str(validation_error),
                    "transcript_preview": sanitize_transcript_for_log(normalized.transcript, 500),
                    "expected_schema": expected_schema
                },
                config=repair_trace_config
            ),
            timeout=REPAIR_TIMEOUT_SECONDS
        )
        
        logger.info(
            f"[REPAIR] [{request_id}] ✅ JSON reparado com sucesso | "
            f"schema_type={schema_type}"
        )
        return repaired
        
    except asyncio.TimeoutError:
        logger.error(
            f"[REPAIR] [{request_id}] ⏱️ Timeout na operação de reparo | "
            f"timeout={REPAIR_TIMEOUT_SECONDS}s"
        )
        raise Exception(f"Timeout na operação de reparo: {REPAIR_TIMEOUT_SECONDS}s")
    
    except Exception as e:
        logger.error(
            f"[REPAIR] [{request_id}] ❌ Erro durante reparo | "
            f"erro={type(e).__name__}: {str(e)[:200]}"
        )
        raise


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
                logger.debug(
                    f"[{request_id}] Tokens registrados: {total_tokens} total "
                    f"(prompt: {prompt_tokens}, completion: {completion_tokens})"
                )
            else:
                logger.debug(f"[{request_id}] Token usage encontrado mas valores são zero")
        else:
            logger.debug(f"[{request_id}] Token usage não encontrado na resposta")
            
    except Exception as e:
        logger.error(f"[{request_id}] Erro ao extrair tokens: {e}")
        # Não falha a operação por causa de métricas


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
