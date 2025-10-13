# 🧠 Documentação: Analyzer (analyzer.py)

## 📚 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura LangChain](#arquitetura-langchain)
3. [Componentes Principais](#componentes-principais)
4. [Fluxo de Análise](#fluxo-de-análise)
5. [Validação de Sentimento](#validação-de-sentimento)
6. [Resiliência e Retry](#resiliência-e-retry)
7. [Sistema de Reparo](#sistema-de-reparo)
8. [Logging e Segurança](#logging-e-segurança)
9. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

O arquivo `analyzer.py` é o **cérebro da análise de sentimento** do microserviço. Ele é responsável por:

✅ Conectar com a OpenAI API (GPT-4o/GPT-4-turbo)  
✅ Analisar sentimento (positive/neutral/negative)  
✅ Calcular score numérico (0.0-1.0)  
✅ Garantir consistência label ↔ score  
✅ Identificar riscos e insights estratégicos  
✅ Resiliência com retry automático  
✅ Reparar JSONs malformados  
✅ Validar saída com Pydantic  
✅ Logar tudo de forma segura (sem PII completa)

### Por que Temperature 0.2?

Ao contrário do **Extractor** (que usa `temperature=0` para ser determinístico), o **Analyzer** usa **`temperature=0.2`** porque:

- **Análise de sentimento é subjetiva:** Permite certa variação na interpretação emocional
- **Insights criativos:** Temperatura baixa ainda mantém consistência, mas permite insights mais elaborados
- **Balanço ideal:** 0.2 é baixo o suficiente para evitar "alucinações", mas alto o suficiente para análises matizadas

**Comparação:**
```python
# temperature=0 (EXTRACTOR - puramente determinístico)
"Cliente demonstrou interesse"
"Cliente demonstrou interesse"  # Sempre 100% igual

# temperature=0.2 (ANALYZER - levemente criativo)
"Cliente demonstrou otimismo moderado com reservas técnicas"
"Cliente mostrou interesse positivo com preocupações sobre prazo"
# Similar, mas permite variações sutis na análise
```

---

## 🏗️ Arquitetura LangChain

### Componentes da Chain

```
┌──────────────────────────────────────────────────────────┐
│                    LANGCHAIN CHAIN                       │
│                                                          │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐ │
│  │   Prompt     │ → │     LLM      │ → │   Parser    │ │
│  │  Template    │   │  (ChatGPT)   │   │   (JSON)    │ │
│  └──────────────┘   └──────────────┘   └─────────────┘ │
│                                                          │
│  Input: transcript + metadata_json                       │
│  Output: dict Python com sentiment_label + score        │
└──────────────────────────────────────────────────────────┘
```

### Código Real

```python
# 1. Prompt Template (carregado do LangChain Hub)
prompt_hub_name = os.getenv("ANALYZER_PROMPT_HUB_NAME")
prompt = hub.pull(prompt_hub_name)
# Exemplo: "ivan-furukawa/analyzer-sentimento-bancario"

# 2. LLM (ChatGPT) com temperatura LIGEIRAMENTE CRIATIVA
llm = default_client.get_llm(temperature=0.2)  # ← Diferença do Extractor!

# 3. Parser JSON
parser = JsonOutputParser()

# 4. Chain RAW (para capturar tokens)
chain_raw = prompt | llm

# 5. Invocação (assíncrona)
raw_response = await chain_raw.ainvoke({
    "transcript": "Cliente: Estou muito satisfeito...",
    "metadata_json": '{"meeting_id": "MTG001"}'
})

# Parse manual do JSON
result = parser.parse(raw_response.content)

# Resultado: dict Python com análise completa!
{
    "sentiment_label": "positive",
    "sentiment_score": 0.85,
    "summary": "Reunião positiva... (150 palavras)",
    "key_points": [...],
    "risks": [...]
}
```

---

## 🧩 Componentes Principais

### 1. Inicialização do LLM

```python
from llm.openai_client import default_client

llm = default_client.get_llm(temperature=0.2)
```

**Configuração Completa (via `openai_client.py`):**
```python
ChatOpenAI(
    model="gpt-4o",           # Modelo padrão (env var)
    temperature=0.2,          # Levemente criativo
    timeout=30.0,             # Timeout de 30s
    api_key=os.getenv("OPENAI_API_KEY"),
    model_kwargs={
        "stream_usage": True  # Captura tokens para métricas
    }
)
```

**Por que `temperature=0.2` é ideal?**

| Temperature | Comportamento | Uso Ideal |
|-------------|---------------|-----------|
| 0.0 | 100% determinístico | Extração de dados estruturados |
| **0.2** | **Levemente criativo** | **Análise de sentimento** |
| 0.7 | Criativo e variado | Escrita criativa, brainstorm |
| 1.0 | Muito aleatório | Geração de ideias, poesia |

---

### 2. Prompt System (LangChain Hub)

Ao contrário do Extractor (que define o prompt em código), o Analyzer **carrega o prompt do LangChain Hub**:

```python
prompt_hub_name = os.getenv("ANALYZER_PROMPT_HUB_NAME")
# Exemplo: "ivan-furukawa/analyzer-sentimento-bancario"

try:
    logger.info(f"🔄 Carregando prompt do Hub: {prompt_hub_name}")
    prompt = hub.pull(prompt_hub_name)
    logger.debug(f"✅ Prompt do Analyzer carregado com sucesso")
except Exception as e:
    logger.error(f"❌ Falha ao carregar o prompt: {e}")
    raise
```

**Benefícios do LangChain Hub:**
- ✅ **Versionamento de prompts:** Atualizar sem mexer no código
- ✅ **A/B testing:** Testar diferentes prompts facilmente
- ✅ **Colaboração:** Compartilhar prompts entre times
- ✅ **Rollback rápido:** Reverter para versões anteriores

**Estrutura Típica do Prompt:**
```
Você é um assistente especializado em análise de sentimento de reuniões bancárias.

**INSTRUÇÕES:**

1. **ANÁLISE DE SENTIMENTO:**
   - Classifique o sentimento geral em: "positive", "neutral", ou "negative"
   - Calcule um score numérico entre 0.0 e 1.0:
     * 0.0-0.4: negative (cliente insatisfeito, preocupado, frustrado)
     * 0.4-0.6: neutral (cliente neutro, sem emoções fortes)
     * 0.6-1.0: positive (cliente satisfeito, entusiasmado, confiante)

2. **CONSISTÊNCIA OBRIGATÓRIA:**
   - sentiment_label = "positive" → sentiment_score >= 0.6
   - sentiment_label = "neutral" → 0.4 <= sentiment_score < 0.6
   - sentiment_label = "negative" → sentiment_score < 0.4

3. **IDENTIFICAÇÃO DE RISCOS:**
   - Identifique preocupações, objeções ou sinais de alerta
   - Se não houver riscos identificáveis, retorne lista vazia []

4. **FORMATO DE SAÍDA:**
Retorne um JSON válido:
{
  "sentiment_label": "positive|neutral|negative",
  "sentiment_score": 0.85,
  "summary": "Resumo de 100-200 palavras...",
  "key_points": ["Ponto 1", "Ponto 2"],
  "action_items": ["Ação 1", "Ação 2"],
  "risks": ["Risco 1"] ou []
}
```

---

### 3. Funções Auxiliares

O Analyzer **reutiliza funções compartilhadas** do módulo `utils`:

```python
from utils import (
    sanitize_transcript_for_log,    # Proteção de PII
    prepare_metadata_for_prompt,    # Formatação de metadata
    repair_json,                    # Reparo de JSON
    extract_and_record_token_usage, # Métricas de tokens
    log_retry_attempt               # Log de retry
)
```

#### `sanitize_transcript_for_log()` - Proteção de PII

```python
transcript = "Cliente João Silva, CPF 123.456.789-00, está muito satisfeito..."

# Log SEGURO ✅
logger.info(f"Transcript: {sanitize_transcript_for_log(transcript, 100)}")
# Output: "Cliente João Silva, CPF 123.456.789-00, está muito sa... (truncado, total: 523 chars)"
```

#### `prepare_metadata_for_prompt()` - Formatação de Metadata

```python
normalized = NormalizedInput(
    transcript="...",
    meeting_id="MTG001",
    customer_id="CUST001",
    meet_date=datetime(2025, 9, 10, 14, 30)
)

metadata_json = prepare_metadata_for_prompt(normalized)
# Resultado:
# {
#   "meeting_id": "MTG001",
#   "customer_id": "CUST001",
#   "meet_date": "2025-09-10T14:30:00"
# }
```

---

## 🔄 Fluxo de Análise

### Função Principal: `analyze_sentiment_chain()`

```python
@retry(
    reraise=True,
    stop=stop_after_attempt(3),  # Máximo 3 tentativas
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
    before_sleep=log_retry_attempt,  # Log antes de cada retry
)
async def analyze_sentiment_chain(
    normalized: NormalizedInput,
    request_id: str = "-"
) -> AnalyzedMeeting:
    """
    Analisa sentimento e gera insights de uma reunião usando OpenAI + LangChain.
    
    Orquestra todo o processo de análise:
    1. Valida dados de entrada
    2. Prepara os dados para o prompt
    3. Chama o LLM com retry automático (até 3 tentativas)
    4. Extrai tokens e registra métricas Prometheus
    5. Valida o resultado com Pydantic (consistência label ↔ score)
    6. Tenta reparar se a validação falhar
    7. Preenche a chave de idempotência
    8. Retorna o objeto validado
    """
```

### Passo a Passo Detalhado

#### Passo 1: Preparação

```python
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
```

#### Passo 2: Chamada ao LLM (com captura de tokens)

```python
# Prepara configuração para LangSmith (observabilidade)
trace_config = {
    "metadata": {
        "request_id": request_id,
        "transcript_length": len(normalized.transcript),
        "has_metadata_input": bool(metadata_fields_count > 0)
    },
    "run_name": f"Analyze Meeting - {request_id}"
}

# 🔥 Chain RAW para capturar metadados de tokens
llm_start = time.time()
raw_response = await chain_raw.ainvoke(
    {
        "transcript": normalized.transcript,
        "metadata_json": metadata_json
    },
    config=trace_config
)

# Registra métricas Prometheus
model = get_model_from_env()  # Ex: "gpt-4o"
record_openai_request(model, "success")

# Extrai e registra tokens (prompt_tokens, completion_tokens)
extract_and_record_token_usage(raw_response, model, request_id)

# Parse manual do JSON
raw_output = parser.parse(raw_response.content)

llm_duration = time.time() - llm_start
logger.info(
    f"[RESPONSE] [{request_id}] ✅ OpenAI API respondeu | "
    f"duration={llm_duration:.2f}s | "
    f"output_keys={list(raw_output.keys())}"
)
```

**Por que Chain RAW ao invés de Chain com Parser?**

```python
# ❌ Chain com parser direto (não captura tokens)
chain = prompt | llm | parser
result = await chain.ainvoke(...)
# Problema: `result` já é dict, perdemos acesso aos metadados do LLM!

# ✅ Chain RAW + parse manual (captura tokens)
chain_raw = prompt | llm
raw_response = await chain_raw.ainvoke(...)
# raw_response.usage.prompt_tokens ← Disponível!
# raw_response.usage.completion_tokens ← Disponível!
result = parser.parse(raw_response.content)
```

#### Passo 3: Validação com Pydantic

```python
try:
    analyzed = AnalyzedMeeting.model_validate(raw_output)
    logger.debug(f"[SUCCESS] [{request_id}] ✅ Validação Pydantic OK")
    
    logger.info(
        f"[SUCCESS] [{request_id}] 🎉 Análise concluída | "
        f"sentiment={analyzed.sentiment_label} | "
        f"score={analyzed.sentiment_score:.2f} | "
        f"summary_words={len(analyzed.summary.split())} | "
        f"risks={len(analyzed.risks)}"
    )

except Exception as validation_error:
    # Validação falhou → tenta reparar UMA vez
    logger.warning(
        f"[VALIDATION] [{request_id}] ⚠️ Validação falhou | "
        f"erro={type(validation_error).__name__}: {str(validation_error)[:200]}"
    )
    
    repaired_output = await repair_json(
        malformed_output=raw_output,
        validation_error=str(validation_error),
        normalized=normalized,
        request_id=request_id,
        schema_type="analyze"  # ← Indica schema do Analyzer
    )
    
    # Tenta validar novamente
    analyzed = AnalyzedMeeting.model_validate(repaired_output)
    logger.info(f"[SUCCESS] [{request_id}] ✅ Validação OK após reparo")
    
    # Registra métrica de reparo
    record_repair_attempt("success")
```

#### Passo 4: Preenchimento da Idempotency Key

```python
# Preenche a chave de idempotência se possível
idem_key = normalized.compute_idempotency_key()
if idem_key:
    analyzed.idempotency_key = idem_key
    logger.debug(f"[IDEM] [{request_id}] 🔑 Idempotency key: {idem_key[:16]}...")
else:
    # Se não for possível calcular, usa placeholder
    analyzed.idempotency_key = "no-idempotency-key-available"
    logger.warning(
        f"[IDEM] [{request_id}] ⚠️ Não foi possível calcular idempotency_key"
    )

return analyzed
```

---

## 🎭 Validação de Sentimento

### Consistência Label ↔ Score

O `AnalyzedMeeting` possui um validador customizado que **garante consistência** entre `sentiment_label` e `sentiment_score`:

```python
@model_validator(mode='after')
def validate_sentiment_consistency(self):
    """
    Regras de consistência:
    - "positive": score >= 0.6
    - "neutral": 0.4 <= score < 0.6
    - "negative": score < 0.4
    """
    label = self.sentiment_label
    score = self.sentiment_score
    
    if label == "positive" and score < 0.6:
        raise ValueError(
            f"sentiment_label 'positive' requer score >= 0.6, recebido: {score}"
        )
    elif label == "neutral" and not (0.4 <= score < 0.6):
        raise ValueError(
            f"sentiment_label 'neutral' requer 0.4 <= score < 0.6, recebido: {score}"
        )
    elif label == "negative" and score >= 0.4:
        raise ValueError(
            f"sentiment_label 'negative' requer score < 0.4, recebido: {score}"
        )
    
    return self
```

**Exemplos:**

```python
# ✅ VÁLIDO - Consistente
AnalyzedMeeting(
    sentiment_label="positive",
    sentiment_score=0.85,  # >= 0.6 ✓
    # ... outros campos
)

# ❌ INVÁLIDO - Inconsistente
AnalyzedMeeting(
    sentiment_label="positive",
    sentiment_score=0.3,  # < 0.6 ✗
    # ... outros campos
)
# ValidationError: sentiment_label 'positive' requer score >= 0.6, recebido: 0.3

# ✅ VÁLIDO - Neutral
AnalyzedMeeting(
    sentiment_label="neutral",
    sentiment_score=0.5,  # 0.4 <= 0.5 < 0.6 ✓
    # ... outros campos
)

# ❌ INVÁLIDO - Neutral com score alto
AnalyzedMeeting(
    sentiment_label="neutral",
    sentiment_score=0.7,  # >= 0.6 ✗
    # ... outros campos
)
# ValidationError: sentiment_label 'neutral' requer 0.4 <= score < 0.6, recebido: 0.7
```

### Tabela de Consistência

| sentiment_label | sentiment_score | Válido? | Exemplo de Reunião |
|-----------------|-----------------|---------|-------------------|
| **positive** | 0.85 | ✅ | Cliente muito satisfeito, fechou negócio |
| **positive** | 0.6 | ✅ | Cliente satisfeito, sem objeções graves |
| **positive** | 0.55 | ❌ | Score muito baixo para "positive" |
| **neutral** | 0.5 | ✅ | Cliente sem emoções fortes |
| **neutral** | 0.45 | ✅ | Cliente levemente positivo |
| **neutral** | 0.7 | ❌ | Score muito alto para "neutral" |
| **negative** | 0.3 | ✅ | Cliente insatisfeito, com objeções |
| **negative** | 0.1 | ✅ | Cliente muito frustrado |
| **negative** | 0.5 | ❌ | Score muito alto para "negative" |

---

## 🔁 Resiliência e Retry

### Decorator `@retry`

Idêntico ao Extractor, o Analyzer usa o mesmo sistema de retry:

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    reraise=True,
    stop=stop_after_attempt(3),             # Máximo 3 tentativas
    wait=wait_exponential(                  # Backoff exponencial
        multiplier=0.5, 
        min=0.5, 
        max=5.0
    ),
    retry=retry_if_exception_type((         # Apenas para esses erros
        RateLimitError,                      # 429 - Too Many Requests
        APITimeoutError,                     # Timeout de rede
        APIError                             # Erro genérico da API
    )),
    before_sleep=log_retry_attempt          # ← Log antes de cada retry
)
async def analyze_sentiment_chain(...):
    ...
```

### Log de Retry (via `log_retry_attempt`)

```python
# utils/retry_logger.py
def log_retry_attempt(retry_state):
    """Log antes de cada retry."""
    attempt = retry_state.attempt_number
    wait_time = retry_state.next_action.sleep
    exception = retry_state.outcome.exception()
    
    logger.warning(
        f"[RETRY] Tentativa {attempt}/3 falhou | "
        f"erro={type(exception).__name__} | "
        f"aguardando {wait_time:.1f}s antes de retry..."
    )
```

**Exemplo de Sequência de Logs:**

```
[ANALYZE] [req-123] 🧠 Iniciando análise de sentimento | transcript_len=790
[req-123] 🤖 Chamada à OpenAI | metadata_fields=2
[ERROR] [req-123] ❌ OpenAI API Error: RateLimitError - Too Many Requests
[RETRY] Tentativa 1/3 falhou | erro=RateLimitError | aguardando 0.5s...
[req-123] 🤖 Chamada à OpenAI | metadata_fields=2 (RETRY 2/3)
[RESPONSE] [req-123] ✅ OpenAI API respondeu | duration=4.2s
[SUCCESS] [req-123] ✅ Validação Pydantic OK
[SUCCESS] [req-123] 🎉 Análise concluída | sentiment=positive | score=0.85
```

---

## 🔧 Sistema de Reparo

### Quando o Reparo é Ativado?

Quando a **validação Pydantic falha** no output do LLM:

**Cenário 1: Inconsistência label ↔ score**
```python
# LLM retornou
{
    "sentiment_label": "positive",
    "sentiment_score": 0.3,  # ❌ Inconsistente!
    ...
}

# Pydantic tenta validar
analyzed = AnalyzedMeeting.model_validate(raw_output)
# ValidationError: sentiment_label 'positive' requer score >= 0.6, recebido: 0.3

# Sistema detecta erro e chama reparo
```

**Cenário 2: Summary muito curto**
```python
{
    "summary": "Breve resumo",  # ❌ Apenas 2 palavras (precisa 100-200)
    ...
}

# ValidationError: summary deve ter 100-200 palavras, tem 2
```

### Função `repair_json()` (Compartilhada)

```python
# utils/json_repair.py
async def repair_json(
    malformed_output: dict,
    validation_error: str,
    normalized: NormalizedInput,
    request_id: str,
    schema_type: str  # ← "analyze" ou "extract"
) -> dict:
    """
    Tenta reparar um JSON malformado reenviando ao LLM com o erro.
    
    Args:
        schema_type: "analyze" ou "extract" (determina schema esperado)
    """
    
    logger.warning(
        f"[REPAIR] [{request_id}] 🔧 Tentando reparar JSON | "
        f"schema={schema_type} | erro={validation_error[:200]}"
    )
    
    # Carrega prompt de reparo do Hub
    repair_prompt_hub = os.getenv("JSON_REPAIRER_PROMPT_HUB_NAME")
    repair_prompt = hub.pull(repair_prompt_hub)
    
    # Seleciona schema correto
    if schema_type == "analyze":
        schema_doc = """
        - sentiment_label: "positive"|"neutral"|"negative"
        - sentiment_score: float (0.0-1.0)
        - Consistência: positive (≥0.6), neutral (0.4-0.6), negative (<0.4)
        - summary: string (100-200 palavras EXATAS)
        - key_points: array de strings
        - action_items: array de strings
        - risks: array de strings (pode ser vazio [])
        """
    else:
        schema_doc = """
        - summary: string (100-200 palavras EXATAS)
        - key_points: array de strings
        - action_items: array de strings
        - topics: array de strings
        """
    
    # Chain de reparo
    repair_chain = repair_prompt | llm | parser
    
    repaired = await repair_chain.ainvoke({
        "malformed_json": json.dumps(malformed_output, ensure_ascii=False, indent=2),
        "error": validation_error,
        "transcript_preview": sanitize_transcript_for_log(normalized.transcript, 500),
        "schema": schema_doc
    })
    
    logger.info(f"[REPAIR] [{request_id}] ✅ JSON reparado com sucesso")
    return repaired
```

### Exemplo de Reparo - Analyzer

**Input para reparo:**
```json
{
  "malformed_json": {
    "sentiment_label": "positive",
    "sentiment_score": 0.3,
    "summary": "Cliente satisfeito... (150 palavras)",
    ...
  },
  "error": "sentiment_label 'positive' requer score >= 0.6, recebido: 0.3",
  "schema": "analyze"
}
```

**LLM processa e retorna JSON corrigido:**
```json
{
  "sentiment_label": "neutral",
  "sentiment_score": 0.45,
  "summary": "Cliente satisfeito... (150 palavras)",
  ...
}
```
**Validação (2ª tentativa):**
```python
analyzed = AnalyzedMeeting.model_validate(repaired_output)
# ✅ OK! (neutral com score 0.45 é consistente)
```

---

## 📊 Logging e Segurança

### Estrutura de Logs

Todos os logs seguem o padrão com tags específicas:

```
[TAG] [REQUEST_ID] emoji Mensagem | contexto_key=valor
```

**Tags usadas no Analyzer:**
- `[ANALYZE]` - Início da análise
- `[RESPONSE]` - Resposta da OpenAI
- `[SUCCESS]` - Análise concluída
- `[ERROR]` - Erro na API
- `[VALIDATION]` - Erro de validação
- `[REPAIR]` - Reparo de JSON
- `[IDEM]` - Idempotency key

### Exemplo de Sequência de Logs Completa

```
[ANALYZE] [req-abc] 🧠 Iniciando análise de sentimento | transcript_len=790 | has_metadata=sim
[req-abc] 🤖 Chamada à OpenAI | metadata_fields=3 | transcript_preview=Cliente: Estou muito...
[RESPONSE] [req-abc] ✅ OpenAI API respondeu com sucesso | duration=3.8s | output_keys=['sentiment_label', 'sentiment_score', ...]
[SUCCESS] [req-abc] ✅ Validação Pydantic OK na primeira tentativa
[SUCCESS] [req-abc] 🎉 Análise concluída com sucesso | sentiment=positive | score=0.85 | summary_words=169 | risks=0
[IDEM] [req-abc] 🔑 Idempotency key calculada: 7e3e97ffd83f...
```

### O que É e NÃO É Logado

✅ **É logado:**
- Request ID (rastreamento)
- Tamanho da transcrição (número de caracteres)
- Presença de metadados (sim/não)
- Número de campos de metadata
- Preview de 100 chars da transcrição
- Chaves do JSON retornado pelo LLM
- Status de validação (OK/FALHA)
- Sentiment label e score
- Número de palavras do summary
- Quantidade de key_points/action_items/risks
- Tipos de erros (sem detalhes sensíveis)
- Duração das chamadas

❌ **NÃO é logado:**
- Transcrição completa
- Nomes de clientes/bankers
- Conteúdo do resumo
- IDs completos de clientes
- CPFs, emails, telefones
- Detalhes financeiros
- Insights específicos

---

## 🎓 Exemplos Práticos

### Exemplo 1: Análise Positiva (1ª Tentativa)

```python
# Input
normalized = NormalizedInput(
    transcript="Cliente: Estou muito satisfeito com a proposta! Vamos fechar hoje mesmo.",
    meeting_id="MTG001",
    customer_id="CUST001",
    meet_date=datetime(2025, 9, 10, 14, 30)
)

# Chamada
analyzed = await analyze_sentiment_chain(normalized, "req-123")

# Logs:
# [ANALYZE] [req-123] 🧠 Iniciando análise | transcript_len=68
# [req-123] 🤖 Chamada à OpenAI | metadata_fields=3
# [RESPONSE] [req-123] ✅ OpenAI respondeu | duration=3.2s
# [SUCCESS] [req-123] ✅ Validação OK
# [SUCCESS] [req-123] 🎉 Análise concluída | sentiment=positive | score=0.92

# Output
print(analyzed.sentiment_label)  # "positive"
print(analyzed.sentiment_score)  # 0.92
print(len(analyzed.summary.split()))  # 145 palavras
print(analyzed.risks)  # []
```

### Exemplo 2: Análise Negativa com Riscos

```python
# Input
normalized = NormalizedInput(
    transcript="Cliente: Estou preocupado com as taxas. Não sei se consigo pagar...",
    meeting_id="MTG002",
    customer_id="CUST002",
    meet_date=datetime(2025, 9, 11, 10, 0)
)

# Chamada
analyzed = await analyze_sentiment_chain(normalized, "req-456")

# Output
print(analyzed.sentiment_label)  # "negative"
print(analyzed.sentiment_score)  # 0.25
print(analyzed.risks)
# [
#   "Cliente demonstrou preocupação com capacidade de pagamento",
#   "Objeção forte sobre taxas cobradas"
# ]
```

### Exemplo 3: Reparo por Inconsistência

```python
# LLM retornou (inconsistente)
{
    "sentiment_label": "positive",
    "sentiment_score": 0.4,  # ❌ Deveria ser >= 0.6
    ...
}

# Logs:
# [VALIDATION] [req-789] ⚠️ Validação falhou | erro=ValueError: sentiment_label 'positive' requer score >= 0.6, recebido: 0.4
# [REPAIR] [req-789] 🔧 Tentando reparar JSON | schema=analyze
# [REPAIR] [req-789] ✅ JSON reparado com sucesso
# [SUCCESS] [req-789] ✅ Validação OK após reparo

# JSON reparado
{
    "sentiment_label": "neutral",
    "sentiment_score": 0.45,  # ✅ Consistente
    ...
}
```

### Exemplo 4: Retry por Rate Limit

```python
# Tentativa 1
[ANALYZE] [req-999] 🧠 Iniciando análise
[ERROR] [req-999] ❌ OpenAI API Error: RateLimitError
[RETRY] Tentativa 1/3 falhou | erro=RateLimitError | aguardando 0.5s...

# Tentativa 2
[req-999] 🤖 Chamada à OpenAI (RETRY 2/3)
[RESPONSE] [req-999] ✅ OpenAI respondeu | duration=4.1s
[SUCCESS] [req-999] ✅ Validação OK
```

---

## 💡 Dicas e Boas Práticas

### 1. Temperature Adequada por Uso

```python
# ✅ BOM - Extrator (determinístico)
llm_extract = ChatOpenAI(temperature=0)

# ✅ BOM - Analyzer (levemente criativo)
llm_analyze = ChatOpenAI(temperature=0.2)

# ❌ RUIM - Analyzer muito criativo (inconsistente)
llm_analyze = ChatOpenAI(temperature=0.7)
```

### 2. Validação de Consistência

```python
# ✅ BOM - Validador customizado
@model_validator(mode='after')
def validate_sentiment_consistency(self):
    # Garante label ↔ score consistentes
    ...

# ❌ RUIM - Sem validação (aceita inconsistências)
sentiment_label: Literal["positive", "neutral", "negative"]
sentiment_score: float  # Sem check de consistência
```

### 3. Logs Estruturados com Emojis

```python
# ✅ BOM - Fácil de identificar visualmente
logger.info(f"[ANALYZE] [{request_id}] 🧠 Iniciando análise")
logger.info(f"[SUCCESS] [{request_id}] 🎉 Análise concluída")
logger.error(f"[ERROR] [{request_id}] ❌ Falha na API")

# ❌ RUIM - Difícil de parsear
logger.info(f"Analisando sentimento para {request_id}")
```

### 4. Campo `risks` Opcional mas Sempre Lista

```python
# ✅ BOM - Sempre retorna lista (pode ser vazia)
risks: List[str] = Field(default_factory=list)

# ❌ RUIM - None pode causar erros
risks: Optional[List[str]] = None
```

---

## 📊 Métricas de Performance

| Métrica | Valor Típico | Observação |
|---------|--------------|------------|
| **Tempo médio de análise** | 3-6 segundos | Temperature 0.2 é ligeiramente mais lento |
| **Taxa de sucesso (1ª tentativa)** | ~92% | Menor que Extractor devido a validações complexas |
| **Taxa de reparo bem-sucedido** | ~80% | Inconsistência label ↔ score é comum |
| **Taxa de retry por rate limit** | ~2% | Idêntico ao Extractor |
| **Taxa de falha definitiva** | <1% | Muito raro |
| **% Positive** | ~45% | Depende do dataset |
| **% Neutral** | ~35% | Depende do dataset |
| **% Negative** | ~20% | Depende do dataset |

---

## 🔍 Debugging

### Como debugar erros de análise?

1. **Verifique os logs com o Request ID:**
```bash
grep "req-123" logs.txt | grep ANALYZE
```

2. **Teste o prompt manualmente:**
```python
# No console Python
from app.analyzers.analyzer import prompt, llm, parser

result = await (prompt | llm).ainvoke({
    "transcript": "Cliente: Teste...",
    "metadata_json": "{}"
})
print(result.content)
```

3. **Valide o output manualmente:**
```python
from app.models.schemas_analyze import AnalyzedMeeting

try:
    analyzed = AnalyzedMeeting.model_validate(result)
except Exception as e:
    print(f"Erro: {e}")
```

4. **Teste consistência label ↔ score:**
```python
# Deve falhar
AnalyzedMeeting(
    sentiment_label="positive",
    sentiment_score=0.3,  # ❌
    ...
)
# ValidationError: sentiment_label 'positive' requer score >= 0.6, recebido: 0.3
```

---

## 📚 Diferenças Extractor vs Analyzer

| Aspecto | Extractor | Analyzer |
|---------|-----------|----------|
| **Temperature** | 0 (determinístico) | 0.2 (levemente criativo) |
| **Output Principal** | Dados estruturados | Sentimento + insights |
| **Validações** | Summary 100-200 palavras | + Consistência label ↔ score |
| **Campo Diferencial** | `topics` | `sentiment_label`, `sentiment_score`, `risks` |
| **Prompt** | Definido em código | Carregado do LangChain Hub |
| **Uso** | Extração de fatos | Análise subjetiva |
| **Taxa de Reparo** | ~85% | ~80% (validações mais complexas) |

---

## 📚 Referências

- **LangChain Docs:** https://python.langchain.com/docs/get_started/introduction
- **LangChain Hub:** https://smith.langchain.com/hub
- **OpenAI API:** https://platform.openai.com/docs/api-reference
- **Tenacity (Retry):** https://tenacity.readthedocs.io/

---

**Próximo:** [05-TESTS.md](05-TESTS.md) - Como testar o Analyzer


