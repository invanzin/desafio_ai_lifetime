# 📚 Microserviço de Análise de Reuniões

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura do Sistema](#arquitetura-do-sistema)
3. [Fluxo de Dados](#fluxo-de-dados)
4. [Estrutura de Pastas](#estrutura-de-pastas)
5. [Como Iniciar](#como-iniciar)
6. [Tecnologias Utilizadas](#tecnologias-utilizadas)
7. [Conceitos Importantes](#conceitos-importantes)

---

## 🎯 Visão Geral

Este microserviço foi desenvolvido para **extrair informações estruturadas** e **analisar sentimento** de transcrições de reuniões bancárias usando Inteligência Artificial (OpenAI API + LangChain).

### O que ele faz?

O sistema oferece **duas features principais**:

#### 🔍 **Feature 1: Extractor** (Extração de Dados Estruturados)

**Entrada:** Transcrição de texto de uma reunião

**Saída:** JSON estruturado contendo:
- Metadados da reunião (IDs, nomes, data, tipo)
- Resumo executivo (100-200 palavras)
- Pontos-chave discutidos
- Ações/tarefas identificadas
- Tópicos abordados

**Endpoint:** `POST /extract`

---

#### 🧠 **Feature 2: Analyzer** (Análise de Sentimento e Insights)

**Entrada:** Transcrição de texto de uma reunião

**Saída:** JSON estruturado contendo:
- **Sentimento:** Label (positive/neutral/negative) + Score (0.0-1.0)
- Metadados da reunião
- Resumo executivo (100-200 palavras)
- Pontos-chave e ações identificadas
- **Riscos e preocupações** levantados pelo cliente

**Endpoint:** `POST /analyze`

---

### Exemplo Simplificado

```
🔍 FEATURE EXTRACTOR
────────────────────
ENTRADA:
"Cliente: Olá, preciso de R$ 500 mil para capital de giro.
Banker: Perfeito! Vou preparar uma proposta..."

↓ ↓ ↓ [PROCESSAMENTO COM IA] ↓ ↓ ↓

SAÍDA:
{
  "customer_name": "extraído da transcrição",
  "banker_name": "extraído da transcrição",
  "summary": "Reunião focada em empréstimo...",
  "key_points": ["Cliente precisa de R$ 500k", "..."],
  "action_items": ["Preparar proposta", "..."],
  "topics": ["Empréstimo", "Capital de Giro"]
}
```

```
🧠 FEATURE ANALYZER
───────────────────
ENTRADA:
"Cliente: Estou muito satisfeito com a proposta!
Banker: Que ótimo! Vamos fechar hoje."

↓ ↓ ↓ [PROCESSAMENTO COM IA] ↓ ↓ ↓

SAÍDA:
{
  "sentiment_label": "positive",
  "sentiment_score": 0.92,
  "summary": "Reunião extremamente positiva...",
  "key_points": ["Cliente satisfeito", "Fechamento confirmado"],
  "risks": []  ← Nenhum risco identificado
}
```

---

## 🏗️ Arquitetura do Sistema

O microserviço é composto por **3 camadas principais**:

```
┌─────────────────────────────────────────────────────────┐
│                    1. CAMADA DE API                      │
│                      (main.py)                           │
│  - Recebe requisições HTTP                               │
│  - Valida entrada com Pydantic                           │
│  - Retorna JSON estruturado                              │
│  - Tratamento de erros                                   │
│  - 2 endpoints: /extract e /analyze                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                2. CAMADA DE VALIDAÇÃO                    │
│         (schemas_common, schemas_extract,                │
│              schemas_analyze)                            │
│  - Define estruturas de dados (Pydantic)                 │
│  - Valida tipos e formatos                               │
│  - Normaliza diferentes formatos de entrada              │
│  - Calcula chave de idempotência                         │
│  - Valida consistência sentiment_label ↔ score           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│              3. CAMADA DE PROCESSAMENTO                  │
│              (extractor.py, analyzer.py)                 │
│  - Conecta com OpenAI API                                │
│  - Orquestra prompt + LLM + parser (LangChain)           │
│  - Retry automático em caso de erro                      │
│  - Reparo de JSON malformado                             │
│  - Logs estruturados                                     │
│  - Extractor: temperature=0 (determinístico)             │
│  - Analyzer: temperature=0.2 (levemente criativo)        │
└─────────────────────────────────────────────────────────┘
```

### Fluxo de Comunicação

```
Cliente HTTP
    │
    │ POST /extract OU POST /analyze
    │ { "transcript": "...", "metadata": {...} }
    ↓
┌─────────────────┐
│   FastAPI       │ → Middleware: adiciona Request-ID
│   (main.py)     │ → Validação: MeetingRequest (Pydantic)
└────────┬────────┘
         │
         │ to_normalized()
         ↓
┌─────────────────┐
│   Schemas       │ → Converte para NormalizedInput
│ (schemas_*.py)  │ → Unifica formatos diferentes
└────────┬────────┘
         │
         │ extract_meeting_chain() OU analyze_sentiment_chain()
         ↓
┌─────────────────┐
│   Extractor     │ → Temperature 0 (determinístico)
│  OU Analyzer    │ → Temperature 0.2 (criativo)
│                 │ → Monta prompt com contexto
│                 │ → Chama OpenAI API (com retry)
│                 │ → Parse JSON da resposta
│                 │ → Valida com Pydantic
│                 │ → Repara se necessário
└────────┬────────┘
         │
         │ ExtractedMeeting OU AnalyzedMeeting
         ↓
┌─────────────────┐
│   Response      │ → JSON estruturado (200)
│   (main.py)     │ → Com X-Request-ID no header
└─────────────────┘
```

---

## 🔄 Fluxo de Dados Detalhado

### Passo 1: Requisição Chega

**Opção A: Feature Extractor**
```http
POST /extract HTTP/1.1
Content-Type: application/json

{
  "transcript": "Cliente: Bom dia...",
  "metadata": {
    "meeting_id": "MTG001",
    "customer_id": "CUST001"
  }
}
```

**Opção B: Feature Analyzer**
```http
POST /analyze HTTP/1.1
Content-Type: application/json

{
  "transcript": "Cliente: Estou muito satisfeito...",
  "metadata": {
    "meeting_id": "MTG002",
    "customer_id": "CUST002"
  }
}
```

**O que acontece (comum a ambos):**
1. Middleware captura a requisição
2. Adiciona/preserva `X-Request-ID` para rastreamento
3. FastAPI valida o body contra `MeetingRequest` (Pydantic)

---

### Passo 2: Normalização

```python
# schemas_common.py
request.to_normalized() → NormalizedInput
```

**O que acontece:**
1. Converte formato de entrada (pode ser `transcript+metadata` ou `raw_meeting`)
2. Unifica em `NormalizedInput` (formato interno padrão)
3. Prepara dados para o extractor ou analyzer

**Estrutura após normalização:**
```python
NormalizedInput(
    transcript="Cliente: Bom dia...",
    meeting_id="MTG001",
    customer_id="CUST001",
    customer_name=None,  # Será extraído pela IA
    banker_name=None,    # Será extraído pela IA
    # ... outros campos opcionais
)
```

---

### Passo 3: Processamento com IA

#### 3A. Feature Extractor (extractor.py)

```python
# Temperature 0 = Determinístico
llm = default_client.get_llm(temperature=0)

# Chama OpenAI
raw_output = await chain.ainvoke({
    "transcript": normalized.transcript,
    "metadata_json": metadata_json
})

# Valida com Pydantic
extracted = ExtractedMeeting.model_validate(raw_output)
```

**Resultado:**
```json
{
  "meeting_id": "MTG001",
  "customer_name": "João Silva",
  "summary": "Reunião focou em... (169 palavras)",
  "key_points": [...],
  "topics": ["Empréstimo", "Capital de Giro"]
}
```

#### 3B. Feature Analyzer (analyzer.py)

```python
# Temperature 0.2 = Levemente criativo
llm = default_client.get_llm(temperature=0.2)

# Chama OpenAI
raw_output = await chain.ainvoke({
    "transcript": normalized.transcript,
    "metadata_json": metadata_json
})

# Valida com Pydantic (inclui check de consistência label ↔ score)
analyzed = AnalyzedMeeting.model_validate(raw_output)
```

**Resultado:**
```json
{
  "meeting_id": "MTG001",
  "sentiment_label": "positive",
  "sentiment_score": 0.85,
  "summary": "Reunião extremamente positiva... (152 palavras)",
  "key_points": [...],
  "risks": ["Cliente mencionou prazo apertado"]
}
```

---

### Passo 4: Resposta

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: abc-123

{
  "meeting_id": "MTG001",
  ...
  "idempotency_key": "a3f2c8b1e4d7...",
  ...
}
```

---

## 📁 Estrutura de Pastas

```
projeto/
│
├── app/                          # Código principal da aplicação
│   ├── __init__.py               # Inicialização do pacote
│   ├── main.py                   # ⭐ API FastAPI (endpoints)
│   │
│   ├── config/                   # Configurações
│   │   ├── __init__.py
│   │   └── logging_config.py     # Configuração de logging
│   │
│   ├── models/                   # Modelos de dados
│   │   ├── __init__.py
│   │   ├── schemas_common.py     # ⭐ Schemas compartilhados (Metadata, NormalizedInput, MeetingRequest)
│   │   ├── schemas_extract.py    # ⭐ Schemas do Extractor (ExtractedMeeting)
│   │   └── schemas_analyze.py    # ⭐ Schemas do Analyzer (AnalyzedMeeting)
│   │
│   ├── extractors/               # Feature 1: Extractor
│   │   ├── __init__.py
│   │   └── extractor.py          # ⭐ Extração com LangChain + OpenAI (temperature=0)
│   │
│   ├── analyzers/                # Feature 2: Analyzer
│   │   ├── __init__.py
│   │   └── analyzer.py           # ⭐ Análise de sentimento (temperature=0.2)
│   │
│   └── metrics/                  # Métricas Prometheus
│       ├── __init__.py
│       ├── collectors.py         # Coletores de métricas
│       └── dashboard.py          # Dashboard Grafana
│
├── llm/                          # Cliente OpenAI compartilhado
│   ├── __init__.py
│   └── openai_client.py          # Wrapper do OpenAI
│
├── utils/                        # Utilitários compartilhados
│   ├── __init__.py
│   ├── json_repair.py            # Reparo de JSON malformado
│   ├── retry_logger.py           # Log de tentativas de retry
│   └── security.py               # Sanitização de PII, idempotency key
│
├── tests/                        # Testes
│   ├── unit/
│   │   ├── test_schemas.py       # Testes de schemas compartilhados
│   │   ├── test_security.py      # Testes de sanitização e idempotency
│   │   ├── test_extractor.py     # Testes de ExtractedMeeting
│   │   └── test_analyzer.py      # Testes de AnalyzedMeeting
│   │
│   └── integration/
│       ├── test_extract_api.py   # Testes do endpoint /extract
│       ├── test_analyze_api.py   # Testes do endpoint /analyze
│       └── test_rate_limiting.py # Testes de rate limiting
│
├── documentation/                # Documentação completa
│   ├── 01-OVERVIEW.md            # ⭐ Este arquivo (visão geral de ambas features)
│   ├── 02-SCHEMAS.md             # Documentação dos schemas
│   ├── 03-EXTRACTOR.md           # Documentação do extractor
│   ├── 04-ANALYZER.md            # ⭐ Documentação do analyzer (NOVO)
│   ├── 04-MAIN-API.md            # Documentação da API
│   ├── 05-TESTS.md               # Documentação de testes
│   ├── 06-METRICS.md             # Métricas Prometheus
│   └── DOCKER.md                 # Deploy com Docker
│
├── logs/                         # Logs da aplicação
│   ├── info.log                  # Logs nível INFO
│   ├── debug.log                 # Logs nível DEBUG
│   └── error.log                 # Logs nível ERROR
│
├── .env                          # Variáveis de ambiente (não commitado)
├── env.example                   # Template de variáveis (commitado)
├── .gitignore                    # Arquivos ignorados pelo git
├── requirements.txt              # Dependências Python
├── pytest.ini                    # Configuração do pytest
├── Dockerfile                    # Docker build
├── docker-compose.yml            # Orquestração Docker
│
└── README.md                     # Guia rápido de uso
```

### Arquivos Principais

| Arquivo | Responsabilidade | Linhas | Temperature |
|---------|------------------|--------|-------------|
| `main.py` | API FastAPI, endpoints, error handling | ~678 | N/A |
| `schemas_common.py` | Schemas compartilhados (Extractor + Analyzer) | ~391 | N/A |
| `schemas_extract.py` | Schemas do Extractor | ~146 | N/A |
| `schemas_analyze.py` | Schemas do Analyzer | ~136 | N/A |
| `extractor.py` | Feature Extractor: LangChain, OpenAI, retry | ~541 | **0.0** |
| `analyzer.py` | Feature Analyzer: Análise de sentimento | ~322 | **0.2** |

---

## 🚀 Como Iniciar

### Pré-requisitos

- Python 3.11+
- Conta OpenAI (para API Key)
- Conta LangChain (para LangSmith - opcional)
- Virtualenv (recomendado)

### Instalação

```bash
# 1. Clone o repositório
cd projeto

# 2. Crie ambiente virtual
python -m venv venv

# 3. Ative o ambiente
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate

# 4. Instale dependências
pip install -r requirements.txt

# 5. Configure variáveis de ambiente
# Copie o arquivo de exemplo
copy env.example .env  # Windows
# cp env.example .env  # Linux/Mac

# 6. Edite o arquivo .env e preencha:
# - OPENAI_API_KEY=sk-proj-your-real-key
# - EXTRACTOR_PROMPT_HUB_NAME=ivan-furukawa/extrator-reunioes-bancarias
# - ANALYZER_PROMPT_HUB_NAME=ivan-furukawa/analyzer-sentimento-bancario
# - LANGCHAIN_API_KEY=ls__your-key (opcional para LangSmith)
```

### Executando a API

```bash
# Modo desenvolvimento (com hot reload)
uvicorn app.main:app --reload --port 8000

# Ou usando o entrypoint do Python
python -m app.main

# Modo produção (múltiplos workers)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

**API disponível em:** http://localhost:8000

### Acessando a Documentação

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Métricas Prometheus:** http://localhost:8000/metrics

### Testando

```bash
# Health check
curl http://localhost:8000/health

# Testes unitários (rápido, sem custo)
pytest tests/unit/ -v

# Testes de integração (lento, com custo ~$0.25)
pytest tests/integration/ -v

# Teste manual - Feature Extractor
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Cliente: Olá...",
    "metadata": {"meeting_id": "MTG001"}
  }'

# Teste manual - Feature Analyzer
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Cliente: Estou muito satisfeito...",
    "metadata": {"meeting_id": "MTG002"}
  }'
```

---

## 🛠️ Tecnologias Utilizadas

### Core

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Python** | 3.11+ | Linguagem principal |
| **FastAPI** | 0.115.0 | Framework web assíncrono |
| **Pydantic** | 2.9.2 | Validação de dados e serialização |
| **Uvicorn** | 0.30.6 | Servidor ASGI de alta performance |

### IA e LLMs

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **LangChain** | 0.3.2 | Orquestração de LLMs |
| **LangChain-OpenAI** | 0.2.2 | Integração com modelos OpenAI |
| **OpenAI** | 1.47.0 | SDK da OpenAI (GPT-4o/GPT-4-turbo) |

### Resiliência e Utilidades

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Tenacity** | 8.5.0 | Retry logic com backoff exponencial |
| **Python-dotenv** | 1.0.1 | Carregamento de variáveis de ambiente |
| **HTTPX** | 0.27.2 | Cliente HTTP assíncrono |

### Observabilidade

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Prometheus-client** | 0.20.0 | Métricas Prometheus |
| **Prometheus-FastAPI-Instrumentator** | 7.0.0 | Instrumentação automática |
| **SlowAPI** | 0.1.9 | Rate limiting |

### Testing

| Tecnologia | Versão | Uso |
|------------|--------|-----|
| **Pytest** | 8.3.3 | Framework de testes |
| **Pytest-asyncio** | 0.24.0 | Testes assíncronos |
| **Pytest-mock** | 3.14.0 | Mocking para testes |

---

## 💡 Conceitos Importantes

### 1. Idempotência

**O que é:** Garantia de que processar a mesma reunião múltiplas vezes resulta no mesmo output.

**Como funciona:**
```python
# SHA-256 hash dos campos únicos
idempotency_key = sha256(
    meeting_id + meet_date + customer_id
)
# Resultado: "a3f2c8b1e4d7..." (sempre o mesmo para mesmos dados)
```

**Uso prático:**
```python
# No banco de dados (exemplo futuro)
if db.exists(idempotency_key):
    return cached_result  # Já processamos antes
else:
    result = process_meeting(...)
    db.save(result, idempotency_key)
    return result
```

### 2. Request ID

**O que é:** UUID único para rastrear cada requisição HTTP.

**Diferença do Idempotency Key:**
- **Request ID:** Muda a cada chamada (rastreamento/debugging)
- **Idempotency Key:** Igual para mesmos dados (prevenção de duplicatas)

**Uso em logs:**
```
[abc-123] POST /extract | format=transcript+metadata
[abc-123] Input normalizado | transcript_len=790
[abc-123] Chamando LLM...
[abc-123] Extração concluída | meeting_id=MTG001
```

### 3. Resiliência

**Retry com backoff exponencial:**
```python
@retry(
    stop=stop_after_attempt(3),  # Máximo 3 tentativas
    wait=wait_exponential(        # Espera exponencial
        multiplier=0.5, 
        min=0.5, 
        max=5.0
    ),
    retry=retry_if_exception_type((
        RateLimitError,  # Erro 429
        APITimeoutError  # Timeout
    ))
)
```

**Sequência de retries:**
1. Tentativa 1: imediato
2. Tentativa 2: espera 0.5s
3. Tentativa 3: espera 1s
4. Se falhar: lança exceção

### 4. Temperature (LLM)

**O que é:** Parâmetro que controla a "criatividade" do LLM.

**Range:** 0.0 (determinístico) → 1.0 (muito aleatório)

**Uso no projeto:**

| Feature | Temperature | Motivo |
|---------|-------------|--------|
| **Extractor** | 0.0 | Dados estruturados precisam ser determinísticos |
| **Analyzer** | 0.2 | Análise de sentimento permite leve criatividade |

**Exemplo:**
```python
# Temperature 0.0 (EXTRACTOR)
"Cliente interessado em empréstimo"
"Cliente interessado em empréstimo"  # Sempre 100% igual

# Temperature 0.2 (ANALYZER)
"Cliente demonstrou otimismo moderado"
"Cliente mostrou interesse positivo"  # Similar, mas permite variações
```

### 5. Validação em Camadas

```
┌─────────────────────────────────────┐
│  1. Validação de Entrada (FastAPI)  │
│     - Campos obrigatórios?          │
│     - Tipos corretos?               │
│     - Formato válido?               │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  2. Validação Customizada (Pydantic)│
│     - Exclusividade mútua?          │
│     - Lógica de negócio?            │
│     - Consistência label ↔ score?   │ ← ANALYZER
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  3. Validação de Saída (Pydantic)   │
│     - Summary tem 100-200 palavras? │
│     - Todos os campos presentes?    │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│  4. Reparo (se falhar)              │
│     - Reenvia ao LLM com erro       │
│     - Tenta validar novamente       │
└─────────────────────────────────────┘
```

---

## 📊 Métricas de Qualidade

| Métrica | Valor | Observação |
|---------|-------|------------|
| **Cobertura de Código** | ~85% | Testes unitários + integração |
| **Documentação** | 100% | Todas as funções documentadas |
| **Type Hints** | 100% | Tipagem completa |
| **Validação de Dados** | 100% | Pydantic em toda entrada/saída |
| **Error Handling** | 100% | Todos os erros mapeados |
| **Logging** | 100% | Logs estruturados em todas as etapas |

---

## 🔐 Segurança

### Proteção de PII (Informações Pessoais)

✅ **O que é logado:**
- Request ID
- Tamanho da transcrição (em caracteres)
- Metadata presente? (sim/não)
- Campos extraídos (nomes, mas não valores)
- Sentiment label e score
- Número de palavras do summary

❌ **O que NÃO é logado:**
- Transcrição completa
- Nomes de clientes/bankers
- Conteúdo do resumo
- IDs de clientes
- CPFs, emails, telefones
- Detalhes financeiros

### Exemplo de Log Seguro

```
[abc-123] POST /extract | format=transcript+metadata
[abc-123] Input normalizado | transcript_len=790 | has_metadata=True
[abc-123] Chamando LLM...
[abc-123] LLM respondeu | output_keys=['meeting_id', 'summary', ...]
[abc-123] Validação OK
[abc-123] Idempotency key calculada: a3f2c8b1e4d7...
[abc-123] Extração concluída | meeting_id=MTG001 | summary_words=169
```

---

## 📈 Status de Implementação

### ✅ Funcionalidades Core (Implementadas)

- [x] **Endpoint POST /extract** - Extração de dados estruturados
- [x] **Endpoint POST /analyze** - Análise de sentimento
- [x] **Endpoint GET /health** - Health check para monitoramento
- [x] **Endpoint GET /metrics** - Métricas Prometheus
- [x] **Validação com Pydantic** - Validação automática de entrada/saída
- [x] **Retry e timeout** - Resiliência em chamadas OpenAI (3 tentativas)
- [x] **Logs estruturados** - Logging com Request-ID para rastreamento
- [x] **Exception handlers** - Tratamento robusto de erros (422/502/500)
- [x] **Rate limiting** - Proteção contra abuso (10 req/min por IP)
- [x] **Documentação completa** - 7 documentos detalhados + README

### ✅ Testes (Implementados)

- [x] **Testes unitários** - 48 testes (schemas, security, extractor, analyzer)
- [x] **Testes de integração** - 20 testes (extract API, analyze API, rate limiting)
- [x] **Cobertura** - ~85% do código

### ✅ Deploy (Implementados)

- [x] **Docker** - `Dockerfile` com multi-stage build
- [x] **Docker Compose** - Orquestração de containers
- [x] **Documentação Docker** - `documentation/DOCKER.md`

### 🚧 Melhorias Opcionais (Não Implementadas)

#### Alta Prioridade
- [ ] **Cache de resultados (Redis)** - Performance otimizada
  - Cache por idempotency_key
  - TTL configurável (ex: 24h)
  - Complexidade: 🟡 Média (~4-6h)

#### Média Prioridade
- [ ] **Persistência em banco de dados** - Histórico de extrações
  - PostgreSQL para armazenar reuniões processadas
  - Complexidade: 🔴 Alta (~8-12h)

#### Baixa Prioridade
- [ ] **CI/CD pipeline** - Deploy automático
  - GitHub Actions ou GitLab CI
  - Build → Test → Deploy
  - Complexidade: 🔴 Alta (~6-8h)

- [ ] **Autenticação/Autorização** - Segurança avançada
  - API Keys ou JWT
  - Complexidade: 🟡 Média (~4-6h)

### 📊 Cobertura Atual

| Categoria | Status | Observação |
|-----------|--------|------------|
| **Core API** | ✅ 100% | Todos os requisitos atendidos (2 features) |
| **Validação** | ✅ 100% | Pydantic + handlers + consistência |
| **Resiliência** | ✅ 100% | Retry + timeout + repair |
| **Testes** | ✅ 85% | Unit + Integration |
| **Deploy** | ✅ 100% | Docker pronto para produção |
| **Observabilidade** | ✅ 100% | Logs + Métricas Prometheus |
| **Segurança** | ✅ 90% | Rate limit + PII protection |

---

## 📞 Suporte

Para entender melhor cada componente, consulte:

- **[Schemas](02-SCHEMAS.md)** - Detalhes sobre validação de dados (schemas_common, schemas_extract, schemas_analyze)
- **[Extractor](03-EXTRACTOR.md)** - Como funciona a extração com IA
- **[Analyzer](04-ANALYZER.md)** - Como funciona a análise de sentimento (NOVO)
- **[Main API](04-MAIN-API.md)** - Documentação dos endpoints
- **[Testing](05-TESTS.md)** - Como rodar e criar testes
- **[Metrics](06-METRICS.md)** - Métricas Prometheus e observabilidade

---

**Última atualização:** 2025-10-13  
**Versão:** 2.0.0  
**Status:** ✅ Produção (2 features completas: Extractor + Analyzer)


