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
from typing import Optional
from dotenv import load_dotenv

# LangChain imports
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Retry/Resiliência
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

# OpenAI exceptions
from openai import RateLimitError, APITimeoutError, APIError

# Logging estruturado
import logging

# Schemas internos
from app.models.schemas import NormalizedInput, ExtractedMeeting



# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração básica de logging (será substituído por structlog no futuro)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# INICIALIZAÇÃO DO LLM E PROMPT
# ============================================================================

def _get_llm():
    """
    Inicializa e retorna o modelo de linguagem OpenAI configurado.
    
    Configurações aplicadas:
    - Modelo: obtido da env var OPENAI_MODEL (padrão: gpt-4o)
    - Temperature: 0 (determinístico, sem alucinações)
    - Timeout: 30 segundos (requisito do briefing)
    
    Returns:
        ChatOpenAI: Instância configurada do modelo de linguagem
    
    Raises:
        ValueError: Se OPENAI_API_KEY não estiver definida
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY não encontrada. "
            "Configure a variável de ambiente no arquivo .env"
        )
    
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    return ChatOpenAI(
        model=model_name,
        temperature=0,  # Determinístico para evitar variações
        timeout=30.0,   # Timeout máximo de 30s (requisito do briefing)
        api_key=api_key,
    )


# Instância global do LLM (reutilizada entre chamadas)
llm = _get_llm()

# Parser para extrair JSON da resposta do LLM
parser = JsonOutputParser()

# Template do prompt principal
prompt = ChatPromptTemplate.from_messages([
    ("system", """Você é um assistente especializado em extrair informações estruturadas de transcrições de reuniões bancárias.

Sua tarefa é analisar a transcrição fornecida e os metadados (se disponíveis) e retornar um JSON válido no formato especificado abaixo.

**REGRAS IMPORTANTES:**

1. **PRIORIDADE DOS METADADOS:**
   - Se metadados forem fornecidos (METADATA não vazio), USE-OS COMO VERDADE ABSOLUTA
   - Não altere, não invente, não "corrija" dados fornecidos nos metadados
   - Metadados fornecidos têm prioridade sobre qualquer informação na transcrição

2. **EXTRAÇÃO DA TRANSCRIÇÃO (quando metadados ausentes):**
   - Se algum campo de metadados estiver vazio/null, EXTRAIA da transcrição:
     * customer_name: nome do cliente mencionado nos diálogos
     * banker_name: nome do banker/gerente mencionado
     * meet_type: tipo da reunião inferido do contexto (ex: "Primeira Reunião", "Acompanhamento", "Fechamento")
     * meet_date: data mencionada na transcrição (formato ISO 8601) ou use a data atual se não mencionada
     * customer_id: se não identificável → deixe como "unknown" 
     * banker_id: se não identificável → deixe como "unknown" 
     * meeting_id: se não identificável → deixe como "unknown" 

3. **CAMPOS SEMPRE EXTRAÍDOS DA TRANSCRIÇÃO:**
   - summary: resumo executivo com EXATAMENTE 100-200 palavras
   - key_points: lista de 3-7 pontos-chave da reunião
   - action_items: lista de ações/tarefas identificadas
   - topics: lista de 2-5 tópicos/assuntos principais

4. **VALIDAÇÕES:**
   - NÃO invente informações que não estão na transcrição
   - NÃO deixe campos obrigatórios vazios (use "unknown" se necessário para IDs)
   - Garanta que o summary tenha 100-200 palavras (conte as palavras!)
   - Listas vazias são permitidas se realmente não houver informações

**FORMATO DE SAÍDA:**
Retorne um JSON válido com os seguintes campos:
- meeting_id: string (do metadata ou 'unknown')
- customer_id: string (do metadata ou 'unknown')
- customer_name: string (do metadata ou extraído da transcrição)
- banker_id: string (do metadata ou 'unknown')
- banker_name: string (do metadata ou extraído da transcrição)
- meet_type: string (do metadata ou inferido)
- meet_date: ISO 8601 datetime string (do metadata ou extraído/atual)
- summary: string com 100-200 palavras exatas
- key_points: array de strings
- action_items: array de strings
- topics: array de strings
- source: sempre "lftm-challenge"
- idempotency_key: sempre null (será preenchido externamente)
- transcript_ref: sempre null
- duration_sec: sempre null

Responda APENAS com o JSON válido, SEM TEXTO ADICIONAL."""),
    
    ("human", """TRANSCRIÇÃO:
{transcript}

METADATA FORNECIDO (use como verdade se não for vazio):
{metadata_json}

Retorne o JSON extraído:""")
])

# Chain completa: prompt → LLM → parser JSON
chain = prompt | llm | parser


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

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
        f"[{request_id}] Tentando reparar JSON inválido. Erro: {validation_error[:200]}"
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
    
    repaired = await repair_chain.ainvoke({
        "malformed_json": json.dumps(malformed_output, ensure_ascii=False, indent=2),
        "error": str(validation_error),
        "transcript_preview": _sanitize_transcript_for_log(normalized.transcript, 500)
    })
    
    logger.info(f"[{request_id}] JSON reparado com sucesso")
    return repaired


# ============================================================================
# FUNÇÃO PRINCIPAL DE EXTRAÇÃO
# ============================================================================

@retry(
    reraise=True,
    stop=stop_after_attempt(3),  # Máximo 3 tentativas (requisito do briefing)
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),  # Backoff: 0.5s, 1s, 2s
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
)
async def extract_meeting_chain(
    normalized: NormalizedInput,
    request_id: str = "-"
) -> ExtractedMeeting:
    """
    Extrai informações estruturadas de uma reunião usando OpenAI + LangChain.
    
    Esta é a função principal do módulo. Orquestra todo o processo de extração:
    1. Prepara os dados para o prompt
    2. Chama o LLM com retry automático (até 3 tentativas)
    3. Valida o resultado com Pydantic
    4. Tenta reparar se a validação falhar
    5. Preenche a chave de idempotência
    6. Retorna o objeto validado
    
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
        f"[{request_id}] Iniciando extração | "
        f"transcript_len={len(normalized.transcript)} | "
        f"has_metadata={'sim' if normalized.meeting_id else 'não'}"
    )
    
    # Prepara metadados para o prompt
    metadata_json = _prepare_metadata_for_prompt(normalized)
    
    # Chama o LLM (com retry automático via decorator)
    try:
        raw_output = await chain.ainvoke({
            "transcript": normalized.transcript,
            "metadata_json": metadata_json
        })
        
        logger.info(
            f"[{request_id}] LLM respondeu | "
            f"output_keys={list(raw_output.keys()) if isinstance(raw_output, dict) else 'invalid'}"
        )
        
    except (RateLimitError, APITimeoutError, APIError) as e:
        logger.error(
            f"[{request_id}] Erro na chamada ao LLM após retries: {type(e).__name__} - {str(e)[:200]}"
        )
        raise
    
    # Tenta validar com Pydantic
    try:
        extracted = ExtractedMeeting.model_validate(raw_output)
        logger.info(f"[{request_id}] Validação Pydantic OK na primeira tentativa")
        
    except Exception as validation_error:
        # Validação falhou → tenta reparar UMA vez
        logger.warning(
            f"[{request_id}] Validação Pydantic falhou | "
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
            logger.info(f"[{request_id}] Validação OK após reparo")
            
        except Exception as repair_error:
            logger.error(
                f"[{request_id}] Validação falhou mesmo após reparo | "
                f"erro={type(repair_error).__name__}: {str(repair_error)[:200]}"
            )
            raise
    
    # Preenche a chave de idempotência se possível
    idem_key = normalized.compute_idempotency_key()
    if idem_key:
        extracted.idempotency_key = idem_key
        logger.info(f"[{request_id}] Idempotency key calculada: {idem_key[:16]}...")
    else:
        # Se não for possível calcular, usa placeholder
        extracted.idempotency_key = "no-idempotency-key-available"
        logger.warning(
            f"[{request_id}] Não foi possível calcular idempotency_key "
            f"(faltam meeting_id, meet_date ou customer_id)"
        )
    
    # Log sucesso final
    logger.info(
        f"[{request_id}] Extração concluída com sucesso | "
        f"meeting_id={extracted.meeting_id} | "
        f"summary_words={len(extracted.summary.split())} | "
        f"key_points={len(extracted.key_points)} | "
        f"action_items={len(extracted.action_items)}"
    )
    
    return extracted

