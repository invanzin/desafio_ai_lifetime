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

import os
import json
import asyncio
import logging
from typing import Literal

# LangChain imports
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Schemas internos
from app.models.schemas_common import NormalizedInput

# LLM client
from llm.openai_client import default_client

# Utilitários compartilhados (todas as funções auxiliares vêm daqui)
from utils.common import sanitize_transcript_for_log

# Métricas Prometheus
from app.metrics.collectors import record_repair_attempt


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

# Carrega o nome do prompt do ambiente
prompt_hub_name = os.getenv("JSON_REPAIRER_PROMPT_HUB_NAME")
if not prompt_hub_name:
    raise ValueError("JSON_REPAIRER_PROMPT_HUB_NAME não definido no arquivo .env")

try:
    # Puxa o prompt diretamente do LangChain Hub
    logger.info(f"🔄 Carregando prompt do Hub: {prompt_hub_name}")
    repair_prompt = hub.pull(prompt_hub_name)
    logger.debug(f"✅ Prompt carregado com sucesso do LangChain Hub")
except Exception as e:
    logger.error(f"❌ Falha ao carregar o prompt '{prompt_hub_name}' do Hub: {e}")
    raise

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
        
        # Registra sucesso nas métricas
        record_repair_attempt(status="success")
        
        return repaired
        
    except asyncio.TimeoutError:
        logger.error(
            f"[REPAIR] [{request_id}] ⏱️ Timeout na operação de reparo | "
            f"timeout={REPAIR_TIMEOUT_SECONDS}s"
        )
        # Registra falha nas métricas
        record_repair_attempt(status="failed")
        raise Exception(f"Timeout na operação de reparo: {REPAIR_TIMEOUT_SECONDS}s")
    
    except Exception as e:
        logger.error(
            f"[REPAIR] [{request_id}] ❌ Erro durante reparo | "
            f"erro={type(e).__name__}: {str(e)[:200]}"
        )
        # Registra falha nas métricas
        record_repair_attempt(status="failed")
        raise
