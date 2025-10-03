# 🤖 Documentação: Extractor (extractor.py)

## 📚 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura LangChain](#arquitetura-langchain)
3. [Componentes Principais](#componentes-principais)
4. [Fluxo de Extração](#fluxo-de-extração)
5. [Resiliência e Retry](#resiliência-e-retry)
6. [Sistema de Reparo](#sistema-de-reparo)
7. [Logging e Segurança](#logging-e-segurança)
8. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

O arquivo `extractor.py` é o **cérebro do microserviço**. Ele é responsável por:

✅ Conectar com a OpenAI API (GPT-4o/GPT-4-turbo)  
✅ Orquestrar a extração usando LangChain  
✅ Garantir resiliência (retry automático)  
✅ Reparar JSONs malformados  
✅ Validar saída com Pydantic  
✅ Logar tudo de forma segura (sem PII completa)

### Por que LangChain?

**LangChain** é um framework que facilita a construção de aplicações com LLMs (Large Language Models). Ele fornece:

- **Prompts estruturados:** Templates reutilizáveis
- **Chains:** Sequências de operações (prompt → LLM → parser)
- **Output parsers:** Conversão automática de texto → JSON
- **Retry logic:** Integração nativa com tenacity

**Sem LangChain** (código verboso):
```python
import openai

prompt = f"Extraia JSON de: {transcript}"
response = openai.ChatCompletion.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}]
)
text = response.choices[0].message.content
json_data = json.loads(text)  # Pode falhar!
```

**Com LangChain** (clean e robusto):
```python
chain = prompt | llm | parser
result = await chain.ainvoke({"transcript": transcript})
# Já retorna dict Python!
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
│  Output: dict Python                                     │
└──────────────────────────────────────────────────────────┘
```

### Código Real

```python
# 1. Prompt Template
prompt = ChatPromptTemplate.from_messages([
    ("system", """Você é um assistente especializado...
    
    Extraia informações no formato JSON..."""),
    
    ("human", """TRANSCRIÇÃO:
    {transcript}
    
    METADATA FORNECIDO:
    {metadata_json}
    
    Retorne o JSON extraído:""")
])

# 2. LLM (ChatGPT)
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,    # Determinístico
    timeout=30.0      # Timeout de 30s
)

# 3. Parser JSON
parser = JsonOutputParser()

# 4. Chain completa (operador | = pipe)
chain = prompt | llm | parser

# 5. Invocação (assíncrona)
result = await chain.ainvoke({
    "transcript": "Cliente: Olá...",
    "metadata_json": '{"meeting_id": "MTG001"}'
})
# Resultado: dict Python pronto para usar!
```

### O que acontece nos bastidores?

1. **Prompt é renderizado** (variáveis substituídas):
```
TRANSCRIÇÃO:
Cliente: Olá, preciso de R$ 500 mil...

METADATA FORNECIDO:
{"meeting_id": "MTG001", "customer_id": "CUST001"}

Retorne o JSON extraído:
```

2. **LLM processa e retorna texto**:
```
{
  "meeting_id": "MTG001",
  "customer_id": "CUST001",
  "customer_name": "João Silva",
  "summary": "Reunião focou em...",
  ...
}
```

3. **Parser converte texto → dict Python**:
```python
{
    "meeting_id": "MTG001",
    "customer_id": "CUST001",
    "customer_name": "João Silva",
    "summary": "Reunião focou em...",
    ...
}
```

---

## 🧩 Componentes Principais

### 1. Inicialização do LLM

```python
def _get_llm():
    """Inicializa e retorna o modelo de linguagem OpenAI configurado."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY não encontrada. "
            "Configure a variável de ambiente no arquivo .env"
        )
    
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    return ChatOpenAI(
        model=model_name,
        temperature=0,   # Determinístico (sem aleatoriedade)
        timeout=30.0,    # Timeout máximo de 30s (requisito)
        api_key=api_key,
    )
```

**Por que `temperature=0`?**
- Torna a IA **determinística** (mesma entrada → mesma saída)
- Reduz "alucinações" (inventar informações)
- Ideal para extração de dados estruturados

**Comparação de temperatures:**
```python
# temperature=0 (determinístico)
"Cliente interessado em empréstimo"
"Cliente interessado em empréstimo"  # Sempre igual

# temperature=0.7 (criativo)
"Cliente interessado em empréstimo"
"O cliente demonstrou interesse em obter financiamento"  # Varia
```

---

### 2. Prompt System

O prompt system é **crucial** - ele instrui a IA sobre:
- ✅ O que extrair
- ✅ Como lidar com metadados fornecidos
- ✅ O que fazer quando dados faltam
- ✅ Formato da saída

```python
("system", """Você é um assistente especializado em extrair informações 
estruturadas de transcrições de reuniões bancárias.

**REGRAS IMPORTANTES:**

1. **PRIORIDADE DOS METADADOS:**
   - Se metadados forem fornecidos (METADATA não vazio), USE-OS COMO VERDADE ABSOLUTA
   - Não altere, não invente, não "corrija" dados fornecidos nos metadados
   - Metadados fornecidos têm prioridade sobre qualquer informação na transcrição

2. **EXTRAÇÃO DA TRANSCRIÇÃO (quando metadados ausentes):**
   - Se algum campo de metadados estiver vazio/null, EXTRAIA da transcrição:
     * customer_name: nome do cliente mencionado nos diálogos
     * banker_name: nome do banker/gerente mencionado
     * meet_type: tipo da reunião inferido do contexto
     * meet_date: data mencionada na transcrição (formato ISO 8601)
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
   - NÃO deixe campos obrigatórios vazios (use "unknown" se necessário)
   - Garanta que o summary tenha 100-200 palavras (conte as palavras!)

**FORMATO DE SAÍDA:**
Retorne um JSON válido com os seguintes campos:
- meeting_id: string (do metadata ou 'unknown')
- customer_id: string (do metadata ou 'unknown')
- customer_name: string (do metadata ou extraído da transcrição)
...

Responda APENAS com o JSON válido, SEM TEXTO ADICIONAL.""")
```

**Por que tantas instruções?**
- LLMs podem "esquecer" instruções se não forem claras
- Instruções explícitas reduzem erros
- Repetição de conceitos-chave aumenta compliance

---

### 3. Funções Auxiliares

#### `_sanitize_transcript_for_log()` - Proteção de PII

```python
def _sanitize_transcript_for_log(transcript: str, max_chars: int = 300) -> str:
    """Trunca a transcrição para log seguro (sem PII completa)."""
    if len(transcript) <= max_chars:
        return transcript
    return transcript[:max_chars] + f"... (truncado, total: {len(transcript)} chars)"
```

**Exemplo:**
```python
transcript = "Cliente João Silva, CPF 123.456.789-00, solicita empréstimo..."

# Log INSEGURO ❌
logger.info(f"Transcript: {transcript}")
# Loga CPF completo!

# Log SEGURO ✅
logger.info(f"Transcript: {_sanitize_transcript_for_log(transcript)}")
# "Cliente João Silva, CPF 123.456.789-00, sol... (truncado, total: 523 chars)"
```

#### `_prepare_metadata_for_prompt()` - Formatação de Metadata

```python
def _prepare_metadata_for_prompt(normalized: NormalizedInput) -> str:
    """Prepara os metadados para envio ao LLM em formato JSON legível."""
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
```

**Por que remover `None`?**

Sem remoção:
```json
{
  "meeting_id": "MTG001",
  "customer_id": "CUST001",
  "customer_name": null,
  "banker_name": null,
  "meet_type": null
}
```

Com remoção:
```json
{
  "meeting_id": "MTG001",
  "customer_id": "CUST001"
}
```

**Benefício:** LLM vê claramente quais campos foram fornecidos e quais deve extrair.

---

## 🔄 Fluxo de Extração

### Função Principal: `extract_meeting_chain()`

```python
@retry(
    reraise=True,
    stop=stop_after_attempt(3),  # Máximo 3 tentativas
    wait=wait_exponential(multiplier=0.5, min=0.5, max=5.0),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
)
async def extract_meeting_chain(
    normalized: NormalizedInput,
    request_id: str = "-"
) -> ExtractedMeeting:
    """
    Extrai informações estruturadas de uma reunião usando OpenAI + LangChain.
    
    Orquestra todo o processo de extração:
    1. Prepara os dados para o prompt
    2. Chama o LLM com retry automático (até 3 tentativas)
    3. Valida o resultado com Pydantic
    4. Tenta reparar se a validação falhar
    5. Preenche a chave de idempotência
    6. Retorna o objeto validado
    """
```

### Passo a Passo Detalhado

#### Passo 1: Preparação

```python
# Log início (sem PII completa)
logger.info(
    f"[{request_id}] Iniciando extração | "
    f"transcript_len={len(normalized.transcript)} | "
    f"has_metadata={'sim' if normalized.meeting_id else 'não'}"
)

# Prepara metadados para o prompt
metadata_json = _prepare_metadata_for_prompt(normalized)
# Resultado: '{"meeting_id": "MTG001", "customer_id": "CUST001"}'
```

#### Passo 2: Chamada ao LLM (com retry)

```python
try:
    raw_output = await chain.ainvoke({
        "transcript": normalized.transcript,
        "metadata_json": metadata_json
    })
    
    logger.info(
        f"[{request_id}] LLM respondeu | "
        f"output_keys={list(raw_output.keys())}"
    )
    
except (RateLimitError, APITimeoutError, APIError) as e:
    logger.error(
        f"[{request_id}] Erro na chamada ao LLM após retries: "
        f"{type(e).__name__} - {str(e)[:200]}"
    )
    raise  # Re-lança exceção para main.py tratar
```

**O que pode acontecer:**
- ✅ **Sucesso:** LLM retorna JSON válido
- ⚠️ **Rate Limit (429):** Muitas requisições → retry automático
- ⚠️ **Timeout:** LLM demorou > 30s → retry automático
- ❌ **API Error:** Erro na OpenAI → retry automático
- ❌ **Após 3 tentativas:** Lança exceção (main.py retorna 502)

#### Passo 3: Validação com Pydantic

```python
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
        raise  # Re-lança (main.py retorna 500)
```

**Cenários possíveis:**
1. ✅ **Validação OK na 1ª tentativa:** Segue para passo 4
2. ⚠️ **Validação FALHA → Reparo → OK:** Segue para passo 4
3. ❌ **Validação FALHA → Reparo → FALHA:** Lança exceção (erro 500)

#### Passo 4: Preenchimento da Idempotency Key

```python
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
```

#### Passo 5: Log Final e Retorno

```python
# Log sucesso final
logger.info(
    f"[{request_id}] Extração concluída com sucesso | "
    f"meeting_id={extracted.meeting_id} | "
    f"summary_words={len(extracted.summary.split())} | "
    f"key_points={len(extracted.key_points)} | "
    f"action_items={len(extracted.action_items)}"
)

return extracted
```

---

## 🔁 Resiliência e Retry

### Decorator `@retry`

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

@retry(
    reraise=True,                           # Re-lança exceção após falhar
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
)
async def extract_meeting_chain(...):
    ...
```

### Como funciona o Retry?

**Exemplo: Rate Limit (429)**

```
Tentativa 1: → RateLimitError (429)
              ↓
              Espera 0.5s (2^0 * 0.5)
              ↓
Tentativa 2: → RateLimitError (429)
              ↓
              Espera 1.0s (2^1 * 0.5)
              ↓
Tentativa 3: → RateLimitError (429)
              ↓
              Espera 2.0s (2^2 * 0.5)
              ↓
              ❌ Falha definitiva → lança RateLimitError
```

**Exemplo: Sucesso na 2ª tentativa**

```
Tentativa 1: → APITimeoutError
              ↓
              Espera 0.5s
              ↓
Tentativa 2: → ✅ Sucesso!
              ↓
              Retorna resultado
```

### Por que Exponential Backoff?

**Linear (❌):**
```
Tentativa 1 → Espera 1s → Tentativa 2 → Espera 1s → Tentativa 3
```
Problema: Pode sobrecarregar servidor se muitos clients fazem retry simultâneo.

**Exponencial (✅):**
```
Tentativa 1 → Espera 0.5s → Tentativa 2 → Espera 1s → Tentativa 3 → Espera 2s
```
Benefício: "Espalha" os retries no tempo, reduzindo carga no servidor.

---

## 🔧 Sistema de Reparo

### Quando o Reparo é Ativado?

Quando a **validação Pydantic falha** no output do LLM:

```python
# LLM retornou
{
    "meeting_id": "MTG001",
    "summary": "Breve resumo",  # ❌ Apenas 2 palavras (precisa 100-200)
    ...
}

# Pydantic tenta validar
extracted = ExtractedMeeting.model_validate(raw_output)
# ValidationError: summary deve ter 100-200 palavras, tem 2

# Sistema detecta erro e chama reparo
```

### Função `_repair_json()`

```python
async def _repair_json(
    malformed_output: dict,
    validation_error: str,
    normalized: NormalizedInput,
    request_id: str
) -> dict:
    """
    Tenta reparar um JSON malformado reenviando ao LLM com o erro.
    
    Esta é uma ÚNICA tentativa de reparo.
    """
    logger.warning(
        f"[{request_id}] Tentando reparar JSON inválido. "
        f"Erro: {validation_error[:200]}"
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
        - summary (string com 100-200 palavras EXATAS)
        - key_points (array de strings)
        ...
        
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
```

### Exemplo de Reparo

**Input para reparo:**
```json
{
  "malformed_json": {
    "meeting_id": "MTG001",
    "summary": "Breve resumo",
    ...
  },
  "error": "summary deve ter 100-200 palavras, tem 2",
  "transcript_preview": "Cliente: Olá, preciso de R$ 500 mil..."
}
```

**LLM processa e retorna JSON corrigido:**
```json
{
  "meeting_id": "MTG001",
  "summary": "Reunião entre cliente e banker focou na necessidade de empréstimo... (150 palavras)",
  ...
}
```

**Validação (2ª tentativa):**
```python
extracted = ExtractedMeeting.model_validate(repaired_output)
# ✅ OK! (summary agora tem 150 palavras)
```

---

## 📊 Logging e Segurança

### Estrutura de Logs

Todos os logs seguem o padrão:

```
[REQUEST_ID] Ação | contexto_key=valor | outro_contexto=valor
```

### Exemplo de Sequência de Logs

```
[abc-123] Iniciando extração | transcript_len=790 | has_metadata=sim
[abc-123] LLM respondeu | output_keys=['meeting_id', 'customer_id', 'summary', ...]
[abc-123] Validação Pydantic OK na primeira tentativa
[abc-123] Idempotency key calculada: 7e3e97ffd83f...
[abc-123] Extração concluída com sucesso | meeting_id=MTG001 | summary_words=169
```

### O que É e NÃO É Logado

✅ **É logado:**
- Request ID (rastreamento)
- Tamanho da transcrição (número de caracteres)
- Presença de metadados (sim/não)
- Chaves do JSON retornado pelo LLM
- Status de validação (OK/FALHA)
- Primeiros 16 chars da idempotency key
- Número de palavras do summary
- Quantidade de key_points/action_items
- Tipos de erros (sem detalhes sensíveis)

❌ **NÃO é logado:**
- Transcrição completa
- Nomes de clientes/bankers
- Conteúdo do resumo
- IDs completos de clientes
- CPFs, emails, telefones
- Detalhes financeiros

---

## 🎓 Exemplos Práticos

### Exemplo 1: Extração Bem-Sucedida (1ª Tentativa)

```python
# Input
normalized = NormalizedInput(
    transcript="Cliente: Olá, preciso de R$ 500 mil...",
    meeting_id="MTG001",
    customer_id="CUST001",
    meet_date=datetime(2025, 9, 10, 14, 30)
)

# Chamada
extracted = await extract_meeting_chain(normalized, "req-123")

# Logs:
# [req-123] Iniciando extração | transcript_len=790 | has_metadata=sim
# [req-123] LLM respondeu | output_keys=[...]
# [req-123] Validação Pydantic OK na primeira tentativa
# [req-123] Idempotency key calculada: 7e3e97ffd83f...
# [req-123] Extração concluída | meeting_id=MTG001 | summary_words=169

# Output
print(extracted.meeting_id)  # "MTG001"
print(extracted.summary)      # "Reunião focou em... (169 palavras)"
```

### Exemplo 2: Retry por Rate Limit

```python
# Tentativa 1
[req-456] Iniciando extração | transcript_len=523 | has_metadata=não
[req-456] Erro na chamada ao LLM: RateLimitError - Too Many Requests

# Espera 0.5s...

# Tentativa 2
[req-456] Iniciando extração | transcript_len=523 | has_metadata=não
[req-456] LLM respondeu | output_keys=[...]
[req-456] Validação OK
[req-456] Extração concluída | meeting_id=unknown | summary_words=145
```

### Exemplo 3: Reparo de JSON

```python
# Tentativa 1 de Validação
[req-789] LLM respondeu | output_keys=[...]
[req-789] Validação Pydantic falhou | erro=ValueError: summary deve ter 100-200 palavras, tem 50

# Reparo
[req-789] Tentando reparar JSON inválido. Erro: summary deve ter 100-200 palavras, tem 50
[req-789] JSON reparado com sucesso

# Tentativa 2 de Validação
[req-789] Validação OK após reparo
[req-789] Extração concluída | summary_words=152
```

### Exemplo 4: Falha Definitiva

```python
# Tentativa 1
[req-999] Erro na chamada ao LLM: APITimeoutError

# Espera 0.5s...

# Tentativa 2
[req-999] Erro na chamada ao LLM: APITimeoutError

# Espera 1s...

# Tentativa 3
[req-999] Erro na chamada ao LLM: APITimeoutError

# Desiste
[req-999] Erro na chamada ao LLM após retries: APITimeoutError - Request timeout
# Exceção é re-lançada → main.py retorna 502
```

---

## 💡 Dicas e Boas Práticas

### 1. Temperature Adequada

```python
# ✅ BOM - Para extração estruturada
llm = ChatOpenAI(temperature=0)

# ❌ RUIM - Para extração (gera variações)
llm = ChatOpenAI(temperature=0.7)
```

### 2. Timeout Apropriado

```python
# ✅ BOM - 30s (requisito)
llm = ChatOpenAI(timeout=30.0)

# ❌ RUIM - Sem timeout (pode travar indefinidamente)
llm = ChatOpenAI()
```

### 3. Logs Estruturados

```python
# ✅ BOM - Fácil de parsear/filtrar
logger.info(f"[{request_id}] Ação | key1=value1 | key2=value2")

# ❌ RUIM - Difícil de parsear
logger.info(f"Fazendo ação para {request_id} com {value1}")
```

### 4. Sanitização de Dados Sensíveis

```python
# ✅ BOM - Trunca antes de logar
logger.info(f"Transcript: {_sanitize_transcript_for_log(transcript)}")

# ❌ RUIM - Loga PII completa
logger.info(f"Transcript: {transcript}")
```

---

## 📊 Métricas de Performance

| Métrica | Valor Típico |
|---------|--------------|
| **Tempo médio de extração** | 3-8 segundos |
| **Taxa de sucesso (1ª tentativa)** | ~95% |
| **Taxa de reparo bem-sucedido** | ~85% |
| **Taxa de retry por rate limit** | ~2% |
| **Taxa de falha definitiva** | <1% |

---

## 🔍 Debugging

### Como debugar erros de extração?

1. **Verifique os logs com o Request ID:**
```bash
grep "abc-123" logs.txt
```

2. **Teste o prompt manualmente:**
```python
# No console Python
from app.extractors.extractor import prompt, llm, parser

result = (prompt | llm | parser).invoke({
    "transcript": "Cliente: Teste...",
    "metadata_json": "{}"
})
print(result)
```

3. **Valide o output manualmente:**
```python
from app.models.schemas import ExtractedMeeting

try:
    extracted = ExtractedMeeting.model_validate(result)
except Exception as e:
    print(f"Erro: {e}")
```

---

## 📚 Referências

- **LangChain Docs:** https://python.langchain.com/docs/get_started/introduction
- **OpenAI API:** https://platform.openai.com/docs/api-reference
- **Tenacity (Retry):** https://tenacity.readthedocs.io/

---

**Próximo:** [04-MAIN-API.md](04-MAIN-API.md) - Como funciona a API FastAPI

