# 📋 Documentação: Schemas (schemas.py)

## 📚 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura de Validação](#arquitetura-de-validação)
3. [Schemas de Entrada](#schemas-de-entrada)
4. [Schema Interno](#schema-interno)
5. [Schema de Saída](#schema-de-saída)
6. [Fluxo de Conversão](#fluxo-de-conversão)
7. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

O arquivo `schemas.py` é o **coração da validação de dados** do microserviço. Ele define todas as estruturas de dados usando **Pydantic**, garantindo que:

✅ Entrada é válida (tipos corretos, campos obrigatórios presentes)  
✅ Dados são transformados/normalizados para formato interno  
✅ Saída é consistente e completa  
✅ Regras de negócio são aplicadas automaticamente

### O que é Pydantic?

Pydantic é uma biblioteca Python que:
- Valida tipos de dados automaticamente
- Serializa/deserializa JSON ↔ Python objects
- Gera documentação automática (OpenAPI/Swagger)
- Lança exceções claras quando dados são inválidos

**Exemplo simples:**
```python
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

# ✅ Válido
person = Person(name="João", age=30)

# ❌ Inválido - lança ValidationError
person = Person(name="João", age="trinta")  # age deve ser int!
```

---

## 🏗️ Arquitetura de Validação

O sistema usa **3 tipos de schemas** organizados em camadas:

```
┌─────────────────────────────────────────────────────────┐
│             SCHEMAS DE ENTRADA (REQUEST)                 │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Metadata   │  │  RawMeeting  │  │ExtractRequest│ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                          │
│  Propósito: Validar dados vindos do cliente HTTP        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ to_normalized()
                         ↓
┌─────────────────────────────────────────────────────────┐
│              SCHEMA INTERNO (PROCESSAMENTO)              │
│                                                          │
│             ┌─────────────────────────┐                 │
│             │   NormalizedInput       │                 │
│             └─────────────────────────┘                 │
│                                                          │
│  Propósito: Formato unificado para processamento        │
└────────────────────────┬─────────────────────────────────┘
                         │
                         │ extract_meeting_chain()
                         ↓
┌─────────────────────────────────────────────────────────┐
│              SCHEMA DE SAÍDA (RESPONSE)                  │
│                                                          │
│             ┌─────────────────────────┐                 │
│             │   ExtractedMeeting      │                 │
│             └─────────────────────────┘                 │
│                                                          │
│  Propósito: Formato validado retornado ao cliente       │
└─────────────────────────────────────────────────────────┘
```

---

## 📥 Schemas de Entrada

### 1. `Metadata` (Opcional)

**Propósito:** Metadados estruturados que o cliente pode fornecer junto com a transcrição.

**Quando usar:** Quando você já tem informações sobre a reunião (IDs, nomes, data, etc.) e quer garantir que a IA use esses dados como verdade absoluta.

```python
class Metadata(BaseModel):
    meeting_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    banker_id: Optional[str] = None
    banker_name: Optional[str] = None
    meet_type: Optional[str] = None
    meet_date: Optional[datetime] = None
```

**Características:**
- ✅ Todos os campos são opcionais (`Optional[...]`)
- ✅ Se fornecidos, têm **prioridade absoluta** sobre dados extraídos
- ✅ Usado para calcular `idempotency_key` (se `meeting_id`, `customer_id` e `meet_date` presentes)

**Exemplo JSON:**
```json
{
  "meeting_id": "MTG-2025-001",
  "customer_id": "CUST-456",
  "customer_name": "João Silva / ACME S.A.",
  "banker_id": "BKR-789",
  "banker_name": "Pedro Falcão",
  "meet_type": "Primeira Reunião",
  "meet_date": "2025-09-10T14:30:00Z"
}
```

---

### 2. `RawMeeting` (Formato Upstream)

**Propósito:** Formato completo de reunião vindo de sistemas upstream (ex: `transcricao.json`).

**Quando usar:** Quando você recebe um JSON completo de outro sistema e quer enviá-lo como está, sem separar transcrição e metadados.

```python
class RawMeeting(BaseModel):
    meet_id: str                    # ⚠️ Obrigatório
    customer_id: str                # ⚠️ Obrigatório
    customer_name: str              # ⚠️ Obrigatório
    customer_email: Optional[str] = None
    banker_id: str                  # ⚠️ Obrigatório
    banker_name: str                # ⚠️ Obrigatório
    meet_date: datetime             # ⚠️ Obrigatório
    meet_type: str                  # ⚠️ Obrigatório
    meet_transcription: str         # ⚠️ Obrigatório
```

**Mapeamento de campos:**
```
meet_id           → meeting_id      (normalizado)
meet_transcription → transcript     (normalizado)
Demais campos     → mantêm o nome
```

**Exemplo JSON:**
```json
{
  "meet_id": "7541064ef4a",
  "customer_id": "02ae981fbade",
  "customer_name": "Gabriel Teste",
  "customer_email": "gabriel@example.com",
  "banker_id": "1cc87e",
  "banker_name": "Ana Silva",
  "meet_date": "2025-09-22T17:00:00Z",
  "meet_type": "Acompanhamento",
  "meet_transcription": "Cliente: Olá... Banker: Bom dia..."
}
```

---

### 3. `ExtractRequest` (Schema Principal de Entrada)

**Propósito:** Schema de validação do body da requisição HTTP. Aceita **dois formatos mutuamente exclusivos**.

```python
class ExtractRequest(BaseModel):
    transcript: Optional[str] = None
    metadata: Optional[Metadata] = None
    raw_meeting: Optional[RawMeeting] = None
```

#### Formatos Aceitos

**Formato A:** `transcript` + `metadata` (opcional)
```json
{
  "transcript": "Cliente: Olá...",
  "metadata": {
    "meeting_id": "MTG001"
  }
}
```

**Formato B:** `raw_meeting` (completo)
```json
{
  "raw_meeting": {
    "meet_id": "MTG001",
    "customer_id": "CUST001",
    "meet_transcription": "Cliente: Olá..."
  }
}
```

#### Validação de Exclusividade Mútua

O `ExtractRequest` possui um **validador customizado** que garante que exatamente UM formato seja fornecido:

```python
@model_validator(mode='after')
def validate_exclusive_fields(self):
    has_transcript = self.transcript is not None
    has_raw = self.raw_meeting is not None
    
    # XOR: True apenas se exatamente um for True
    if not (has_transcript ^ has_raw):
        raise ValueError(
            "Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum"
        )
    
    return self
```

**Lógica XOR (Exclusive OR):**
```
has_transcript | has_raw  | XOR  | Resultado
---------------|----------|------|----------
False          | False    | False| ❌ ERRO (nenhum fornecido)
False          | True     | True | ✅ OK (apenas raw_meeting)
True           | False    | True | ✅ OK (apenas transcript)
True           | True     | False| ❌ ERRO (ambos fornecidos)
```

#### Método `to_normalized()`

Converte o `ExtractRequest` para `NormalizedInput`:

```python
def to_normalized(self) -> NormalizedInput:
    if self.raw_meeting:
        # Formato B → NormalizedInput
        return NormalizedInput(
            transcript=self.raw_meeting.meet_transcription,
            meeting_id=self.raw_meeting.meet_id,
            customer_id=self.raw_meeting.customer_id,
            # ... outros campos
        )
    else:
        # Formato A → NormalizedInput
        metadata = self.metadata or Metadata()
        return NormalizedInput(
            transcript=self.transcript,
            meeting_id=metadata.meeting_id,
            customer_id=metadata.customer_id,
            # ... outros campos
        )
```

**Resultado:** Independente do formato de entrada, sempre obtemos um `NormalizedInput` padronizado.

---

## 🔄 Schema Interno

### `NormalizedInput` (Formato Unificado)

**Propósito:** Unificar diferentes formatos de entrada em uma estrutura padrão para processamento.

```python
class NormalizedInput(BaseModel):
    transcript: str                   # ⚠️ Obrigatório
    meeting_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    banker_id: Optional[str] = None
    banker_name: Optional[str] = None
    meet_type: Optional[str] = None
    meet_date: Optional[datetime] = None
```

**Por que normalizar?**

Imagine que você tem **2 formatos de entrada diferentes**:

```
Formato A:           Formato B:
transcript           meet_transcription
metadata.meeting_id  meet_id
metadata.customer_id customer_id
```

Sem normalização, o código de extração teria que lidar com ambos os formatos. Com normalização, temos **um único formato interno**:

```
NormalizedInput:
  transcript
  meeting_id
  customer_id
```

**Benefícios:**
- ✅ Código de extração mais simples (só conhece 1 formato)
- ✅ Fácil adicionar novos formatos de entrada no futuro
- ✅ Separação de responsabilidades (schemas vs. extractor)

#### Método `compute_idempotency_key()`

Calcula um hash SHA-256 único para a reunião:

```python
def compute_idempotency_key(self) -> Optional[str]:
    if not (self.meeting_id and self.meet_date and self.customer_id):
        return None  # Campos obrigatórios faltando
    
    # Concatena campos únicos
    base = f"{self.meeting_id}{self.meet_date.isoformat()}{self.customer_id}"
    
    # Gera hash SHA-256 (64 caracteres hexadecimais)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()
```

**Exemplo:**
```python
normalized = NormalizedInput(
    transcript="...",
    meeting_id="MTG-2025-001",
    customer_id="CUST-456",
    meet_date=datetime(2025, 9, 10, 14, 30)
)

key = normalized.compute_idempotency_key()
# Resultado: "7e3e97ffd83f47c1556889a2b1e4d7f6..."
```

**Propriedade importante:**
```python
# Mesmos dados → Mesma chave (sempre!)
key1 = compute_key("MTG001", "2025-09-10", "CUST001")
key2 = compute_key("MTG001", "2025-09-10", "CUST001")
assert key1 == key2  # ✅ Verdadeiro!
```

---

## 📤 Schemas de Saída

### Feature 1: `ExtractedMeeting` (Resultado do Extractor)

**Propósito:** Estrutura validada do resultado da extração, retornada pelo endpoint `/extract`.

```python
class ExtractedMeeting(BaseModel):
    # Metadados da reunião (obrigatórios)
    meeting_id: str
    customer_id: str
    customer_name: str
    banker_id: str
    banker_name: str
    meet_type: str
    meet_date: datetime
    
    # Dados extraídos por IA (obrigatórios)
    summary: str  # Validado: 100-200 palavras
    key_points: List[str]
    action_items: List[str]
    topics: List[str]  # ← Campo específico do Extractor
    
    # Metadados de controle (obrigatórios)
    source: Literal["lftm-challenge"] = "lftm-challenge"
    idempotency_key: Optional[str] = None
    
    # Opcionais
    transcript_ref: Optional[str] = None
    duration_sec: Optional[int] = None
```

---

### Feature 2: `AnalyzedMeeting` (Resultado do Analyzer)

**Propósito:** Estrutura validada do resultado da análise de sentimento, retornada pelo endpoint `/analyze`.

```python
class AnalyzedMeeting(BaseModel):
    # Metadados da reunião (obrigatórios)
    meeting_id: str
    customer_id: str
    customer_name: str
    banker_id: str
    banker_name: str
    meet_type: str
    meet_date: datetime
    
    # Análise de sentimento (obrigatórios)
    sentiment_label: Literal["positive", "neutral", "negative"]
    sentiment_score: float  # Range: 0.0-1.0
    
    # Dados extraídos por IA (obrigatórios)
    summary: str  # Validado: 100-200 palavras
    key_points: List[str]
    action_items: List[str]
    
    # Insights adicionais (obrigatórios)
    risks: List[str]  # ← Campo específico do Analyzer (pode ser vazio [])
    
    # Metadados de controle (obrigatórios)
    source: Literal["lftm-challenge"] = "lftm-challenge"
    idempotency_key: Optional[str] = None
```

---

#### Validações Customizadas do Extractor

##### 1. Summary Length (ExtractedMeeting)

O campo `summary` possui um validador que garante 100-200 palavras:

```python
@field_validator("summary")
def validate_summary_length(cls, summary: str) -> str:
    # Conta palavras
    wc = len(summary.split())
    
    # Valida range
    if wc < 100 or wc > 200:
        raise ValueError(f"summary deve ter 100-200 palavras, tem {wc}")
    
    return summary
```

---

#### Validações Customizadas do Analyzer

##### 1. Summary Length (AnalyzedMeeting)

Idêntico ao Extractor - garante 100-200 palavras.

##### 2. Sentiment Score Range (AnalyzedMeeting)

```python
@field_validator("sentiment_score")
def validate_sentiment_score_range(cls, score: float) -> float:
    """
    Valida que o score de sentimento está entre 0.0 e 1.0.
    """
    if not (0.0 <= score <= 1.0):
        raise ValueError(
            f"sentiment_score deve estar entre 0.0 e 1.0, recebido: {score}"
        )
    return score
```

##### 3. **Consistência Label ↔ Score (AnalyzedMeeting)** ⚠️ VALIDAÇÃO CRÍTICA

Esta é a validação **mais importante** do Analyzer. Garante que `sentiment_label` e `sentiment_score` sejam **consistentes**:

```python
@model_validator(mode='after')
def validate_sentiment_consistency(self):
    """
    Valida consistência entre sentiment_label e sentiment_score.
    
    Regras:
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

**Tabela de Consistência:**

| sentiment_label | sentiment_score | Válido? | Exemplo |
|-----------------|-----------------|---------|---------|
| **positive** | 0.85 | ✅ | Cliente muito satisfeito |
| **positive** | 0.6 | ✅ | Cliente satisfeito |
| **positive** | 0.55 | ❌ | Score muito baixo! |
| **neutral** | 0.5 | ✅ | Cliente neutro |
| **neutral** | 0.45 | ✅ | Cliente levemente positivo |
| **neutral** | 0.7 | ❌ | Score muito alto! |
| **negative** | 0.3 | ✅ | Cliente insatisfeito |
| **negative** | 0.1 | ✅ | Cliente muito frustrado |
| **negative** | 0.5 | ❌ | Score muito alto! |

---

#### Exemplos de Validação - Extractor

```python
# ❌ Muito curto (10 palavras)
ExtractedMeeting(
    summary="Reunião breve sobre empréstimo de capital de giro para empresa.",
    # ... outros campos
)
# ValidationError: summary deve ter 100-200 palavras, tem 10

# ✅ Tamanho correto (150 palavras)
ExtractedMeeting(
    summary="Reunião detalhada focando em... (150 palavras)",
    # ... outros campos
)
# OK!

# ❌ Muito longo (250 palavras)
ExtractedMeeting(
    summary="Reunião extremamente detalhada... (250 palavras)",
    # ... outros campos
)
# ValidationError: summary deve ter 100-200 palavras, tem 250
```

---

#### Exemplos de Validação - Analyzer

```python
# ✅ VÁLIDO - Positive com score alto
AnalyzedMeeting(
    sentiment_label="positive",
    sentiment_score=0.85,
    summary="Reunião extremamente positiva... (152 palavras)",
    risks=[]
)
# OK!

# ❌ INVÁLIDO - Positive com score baixo
AnalyzedMeeting(
    sentiment_label="positive",
    sentiment_score=0.3,  # ❌ < 0.6
    summary="...",
    risks=[]
)
# ValidationError: sentiment_label 'positive' requer score >= 0.6, recebido: 0.3

# ✅ VÁLIDO - Neutral com score médio
AnalyzedMeeting(
    sentiment_label="neutral",
    sentiment_score=0.5,
    summary="Reunião neutra... (145 palavras)",
    risks=[]
)
# OK!

# ✅ VÁLIDO - Negative com riscos
AnalyzedMeeting(
    sentiment_label="negative",
    sentiment_score=0.25,
    summary="Reunião com objeções... (138 palavras)",
    risks=["Cliente preocupado com taxas", "Mencionou possível cancelamento"]
)
# OK!

# ❌ INVÁLIDO - Neutral com score muito alto
AnalyzedMeeting(
    sentiment_label="neutral",
    sentiment_score=0.75,  # ❌ >= 0.6 (deveria ser "positive")
    summary="...",
    risks=[]
)
# ValidationError: sentiment_label 'neutral' requer 0.4 <= score < 0.6, recebido: 0.75
```

#### Campo `source`

O campo `source` usa `Literal`, que significa que **só aceita um valor específico**:

```python
source: Literal["lftm-challenge"] = "lftm-challenge"
```

**Comportamento:**
```python
# ✅ OK - valor padrão
meeting = ExtractedMeeting(source="lftm-challenge", ...)

# ✅ OK - valor omitido (usa padrão)
meeting = ExtractedMeeting(...)  # source = "lftm-challenge" automaticamente

# ❌ ERRO - valor diferente
meeting = ExtractedMeeting(source="outro-valor", ...)
# ValidationError: Input should be 'lftm-challenge'
```

**Por que usar `Literal`?**
- Garante consistência de dados
- Facilita filtros em banco de dados no futuro
- Documenta valores aceitos no OpenAPI/Swagger

---

## 🔄 Fluxo de Conversão

### Exemplo Completo: Formato A (Transcript + Metadata)

```python
# 1️⃣ Cliente envia JSON
request_json = {
    "transcript": "Cliente: Olá, preciso de R$ 500 mil...",
    "metadata": {
        "meeting_id": "MTG-2025-001",
        "customer_id": "CUST-456",
        "meet_date": "2025-09-10T14:30:00Z"
    }
}

# 2️⃣ FastAPI valida contra ExtractRequest
request = ExtractRequest.model_validate(request_json)
# ✅ Validação OK!

# 3️⃣ Conversão para formato interno
normalized = request.to_normalized()
# Resultado:
# NormalizedInput(
#     transcript="Cliente: Olá, preciso de R$ 500 mil...",
#     meeting_id="MTG-2025-001",
#     customer_id="CUST-456",
#     customer_name=None,  # Será extraído pela IA
#     banker_name=None,    # Será extraído pela IA
#     meet_type=None,      # Será extraído pela IA
#     meet_date=datetime(2025, 9, 10, 14, 30, 0)
# )

# 4️⃣ Calcula idempotency key
idem_key = normalized.compute_idempotency_key()
# "7e3e97ffd83f47c1556889a2b1e4d7f6..."

# 5️⃣ Extração com IA (extractor.py)
raw_llm_output = {
    "meeting_id": "MTG-2025-001",  # Do metadata (prioridade)
    "customer_id": "CUST-456",     # Do metadata
    "customer_name": "João Silva", # Extraído da transcrição
    "banker_name": "Pedro Falcão", # Extraído da transcrição
    "meet_type": "Empréstimo",     # Inferido
    "meet_date": "2025-09-10T14:30:00Z",
    "summary": "Reunião focou em... (169 palavras)",
    "key_points": ["Cliente precisa de R$ 500k", "..."],
    "action_items": ["Preparar proposta", "..."],
    "topics": ["Empréstimo", "Capital de Giro"],
    "source": "lftm-challenge",
    "idempotency_key": None,  # Será preenchido
    "transcript_ref": None,
    "duration_sec": None
}

# 6️⃣ Validação do output
extracted = ExtractedMeeting.model_validate(raw_llm_output)
# ✅ Validação OK! (summary tem 169 palavras)

# 7️⃣ Preenche idempotency_key
extracted.idempotency_key = idem_key

# 8️⃣ Retorna ao cliente
return extracted.model_dump()
```

---

### Exemplo Completo: Formato B (Raw Meeting)

```python
# 1️⃣ Cliente envia JSON
request_json = {
    "raw_meeting": {
        "meet_id": "7541064ef4a",
        "customer_id": "02ae981fbade",
        "customer_name": "Maria Santos",
        "banker_id": "1cc87e",
        "banker_name": "Carlos Mendes",
        "meet_date": "2025-09-22T17:00:00Z",
        "meet_type": "Fechamento",
        "meet_transcription": "Carlos: Boa tarde! Maria: Olá..."
    }
}

# 2️⃣ Validação
request = ExtractRequest.model_validate(request_json)

# 3️⃣ Normalização
normalized = request.to_normalized()
# NormalizedInput(
#     transcript="Carlos: Boa tarde! Maria: Olá...",
#     meeting_id="7541064ef4a",
#     customer_id="02ae981fbade",
#     customer_name="Maria Santos",
#     banker_id="1cc87e",
#     banker_name="Carlos Mendes",
#     meet_type="Fechamento",
#     meet_date=datetime(2025, 9, 22, 17, 0, 0)
# )

# 4️⃣ Cálculo de idempotency
idem_key = normalized.compute_idempotency_key()
# "a9b8c7d6e5f4..."

# ... restante do fluxo igual ao Formato A
```

---

## 🎓 Exemplos Práticos

### Exemplo 1: Validação Bem-Sucedida

```python
# ✅ Entrada válida
data = {
    "transcript": "Cliente: Bom dia...",
    "metadata": {
        "meeting_id": "MTG001",
        "customer_id": "CUST001"
    }
}

request = ExtractRequest.model_validate(data)
# OK!
```

### Exemplo 2: Erro - Ambos os Formatos

```python
# ❌ Ambos fornecidos
data = {
    "transcript": "...",
    "raw_meeting": {
        "meet_id": "...",
        "meet_transcription": "..."
    }
}

request = ExtractRequest.model_validate(data)
# ValidationError: Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum
```

### Exemplo 3: Erro - Nenhum Formato

```python
# ❌ Nenhum fornecido
data = {}

request = ExtractRequest.model_validate(data)
# ValidationError: Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum
```

### Exemplo 4: Erro - Summary Muito Curto

```python
# ❌ Summary com apenas 50 palavras
data = {
    "meeting_id": "MTG001",
    "summary": "Breve resumo com apenas cinquenta palavras...",  # 50 palavras
    # ... outros campos
}

meeting = ExtractedMeeting.model_validate(data)
# ValidationError: summary deve ter 100-200 palavras, tem 50
```

### Exemplo 5: Idempotency Key com Campos Faltando

```python
# ⚠️ Metadados incompletos
normalized = NormalizedInput(
    transcript="...",
    meeting_id="MTG001",
    customer_id=None,  # ❌ Faltando
    meet_date=datetime.now()
)

key = normalized.compute_idempotency_key()
# Resultado: None (não pode calcular)
```

---

## 📊 Resumo dos Schemas

| Schema | Tipo | Propósito | Campos Obrigatórios | Feature |
|--------|------|-----------|---------------------|---------|
| `Metadata` | Entrada | Metadados opcionais | Nenhum (todos opcionais) | Compartilhado |
| `RawMeeting` | Entrada | Formato upstream completo | 8 campos | Compartilhado |
| `MeetingRequest` | Entrada | Schema principal da API | 1 de 2 formatos | Compartilhado |
| `NormalizedInput` | Interno | Formato unificado | Apenas `transcript` | Compartilhado |
| `ExtractedMeeting` | Saída | Resultado do Extractor | 14 campos | Extractor |
| `AnalyzedMeeting` | Saída | Resultado do Analyzer | 15 campos | Analyzer |

### Diferenças Entre Extractor e Analyzer

| Aspecto | ExtractedMeeting | AnalyzedMeeting |
|---------|------------------|-----------------|
| **Campo Específico** | `topics: List[str]` | `sentiment_label`, `sentiment_score`, `risks` |
| **Validações** | Summary 100-200 palavras | + Consistência label ↔ score |
| **Uso** | Extração de dados estruturados | Análise de sentimento |
| **Temperature LLM** | 0.0 (determinístico) | 0.2 (levemente criativo) |

---

## 🔍 Debugging de Validação

### Como ver erros de validação?

```python
from pydantic import ValidationError

try:
    request = ExtractRequest.model_validate(data)
except ValidationError as e:
    print(e.json(indent=2))
```

**Exemplo de erro:**
```json
[
  {
    "type": "value_error",
    "loc": ["body"],
    "msg": "Value error, Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum",
    "input": {...},
    "ctx": {...}
  }
]
```

---

## 💡 Dicas e Boas Práticas

### 1. Sempre use `Optional` para campos opcionais
```python
# ✅ BOM
customer_name: Optional[str] = None

# ❌ RUIM (pode causar erros)
customer_name: str = None  # Type error!
```

### 2. Use `Literal` para valores fixos
```python
# ✅ BOM - documenta valores aceitos
source: Literal["lftm-challenge"] = "lftm-challenge"

# ❌ RUIM - aceita qualquer string
source: str = "lftm-challenge"
```

### 3. Validadores customizados devem retornar o valor
```python
# ✅ BOM
@field_validator("summary")
def validate(cls, v: str) -> str:
    if len(v.split()) < 100:
        raise ValueError("...")
    return v  # ← Importante!

# ❌ RUIM - não retorna
@field_validator("summary")
def validate(cls, v: str):
    if len(v.split()) < 100:
        raise ValueError("...")
    # Faltou retornar!
```

### 4. Use `model_dump()` para serializar
```python
# ✅ BOM - converte para dict JSON-serializável
meeting_dict = meeting.model_dump()

# ❌ RUIM - pode conter objetos Python não-serializáveis
meeting_dict = meeting.__dict__
```

---

## 📚 Referências

- **Pydantic Docs:** https://docs.pydantic.dev/
- **FastAPI + Pydantic:** https://fastapi.tiangolo.com/tutorial/body/
- **Type Hints Python:** https://docs.python.org/3/library/typing.html

---

**Próximos:**
- **[03-EXTRACTOR.md](03-EXTRACTOR.md)** - Como funciona a extração com IA (Feature Extractor)
- **[04-ANALYZER.md](04-ANALYZER.md)** - Como funciona a análise de sentimento (Feature Analyzer)

