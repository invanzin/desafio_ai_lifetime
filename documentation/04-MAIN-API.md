# 🌐 Documentação: Main API (main.py)

## 📚 Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura FastAPI](#arquitetura-fastapi)
3. [Middleware](#middleware)
4. [Exception Handlers](#exception-handlers)
5. [Endpoints](#endpoints)
6. [Fluxo de Requisição](#fluxo-de-requisição)
7. [Códigos de Status](#códigos-de-status)
8. [Exemplos Práticos](#exemplos-práticos)

---

## 🎯 Visão Geral

O arquivo `main.py` é a **porta de entrada** do microserviço. Ele:

✅ Expõe endpoints HTTP (FastAPI)  
✅ Valida requisições automaticamente (Pydantic)  
✅ Adiciona Request-ID para rastreamento  
✅ Trata erros de forma robusta  
✅ Gera documentação automática (Swagger/ReDoc)  
✅ Integra schemas.py + extractor.py

### Por que FastAPI?

**FastAPI** é um framework web moderno que oferece:

- **Performance:** Baseado em Starlette (assíncrono)
- **Validação:** Integração nativa com Pydantic
- **Documentação:** OpenAPI/Swagger gerada automaticamente
- **Type Hints:** Verificação de tipos em tempo de desenvolvimento
- **Async/Await:** Suporte nativo a operações assíncronas

**Comparação com Flask (síncrono):**

```python
# Flask (síncrono - ❌ lento para I/O)
@app.route('/extract', methods=['POST'])
def extract():
    data = request.json
    result = process(data)  # Bloqueia thread
    return result

# FastAPI (assíncrono - ✅ rápido)
@app.post("/extract")
async def extract(body: ExtractRequest):
    result = await process(body)  # Não bloqueia
    return result
```

---

## 🏗️ Arquitetura FastAPI

### Estrutura de Camadas

```
┌─────────────────────────────────────────────────────┐
│                    CLIENTE HTTP                      │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│                 1. MIDDLEWARE                        │
│              (add_request_id)                        │
│  - Adiciona/preserva X-Request-ID                    │
│  - Propaga ID em request.state                       │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│           2. VALIDAÇÃO (automática)                  │
│  - FastAPI valida body com Pydantic                  │
│  - Se inválido → 422 (validation_exception_handler)  │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│              3. ENDPOINT HANDLER                     │
│              (extract_meeting)                       │
│  - Normaliza dados                                   │
│  - Chama extractor                                   │
│  - Retorna resultado                                 │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│            4. EXCEPTION HANDLERS                     │
│  - OpenAI errors → 502                               │
│  - Validation errors → 422                           │
│  - Outros erros → 500                                │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────┐
│                 RESPOSTA HTTP                        │
│  - JSON estruturado                                  │
│  - Header X-Request-ID                               │
└─────────────────────────────────────────────────────┘
```

---

## 🔧 Middleware

### `add_request_id` - Rastreamento de Requisições

```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """
    Middleware que adiciona um X-Request-ID único a cada requisição.
    
    Usado para correlação de logs e debugging. Se o cliente já enviar
    um X-Request-ID, ele é preservado; caso contrário, um novo UUID é gerado.
    """
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    
    return response
```

### Como Funciona?

**Sequência de Execução:**

```
1. Requisição chega
   ↓
2. Middleware intercepta
   ↓
3. Verifica header X-Request-ID
   ├─ Se presente: usa o ID do cliente
   └─ Se ausente: gera novo UUID v4
   ↓
4. Salva em request.state.request_id
   ↓
5. Chama próxima camada (call_next)
   ↓
6. Adiciona X-Request-ID no header de resposta
   ↓
7. Retorna resposta
```

**Exemplo de Requisição:**

```http
POST /extract HTTP/1.1
X-Request-ID: meu-id-customizado
Content-Type: application/json

{...}
```

**Resposta:**

```http
HTTP/1.1 200 OK
X-Request-ID: meu-id-customizado
Content-Type: application/json

{...}
```

**Sem X-Request-ID fornecido:**

```http
POST /extract HTTP/1.1
Content-Type: application/json

{...}
```

**Resposta (com UUID gerado):**

```http
HTTP/1.1 200 OK
X-Request-ID: a3f2c8b1-e4d7-4a2f-b1c9-8e5f6d7a9b2c
Content-Type: application/json

{...}
```

### Por que usar request.state?

```python
# ✅ BOM - request.state é thread-safe e isolado por request
request.state.request_id = "abc-123"

# ❌ RUIM - variável global pode causar race conditions
global_request_id = "abc-123"
```

---

## 🚨 Exception Handlers

FastAPI permite capturar exceções específicas e retornar respostas customizadas.

### 1. `validation_exception_handler` - Erro 422

Trata erros de validação do Pydantic quando o body da requisição é inválido:

```python
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, 
    exc: RequestValidationError
) -> JSONResponse:
    """Handler para erros de validação do Pydantic (422 Unprocessable Entity)."""
    request_id = getattr(request.state, "request_id", "-")
    
    # Serializa os erros de validação de forma segura
    errors = []
    for error in exc.errors():
        errors.append({
            "loc": error.get("loc", []),      # Localização do erro
            "msg": str(error.get("msg", "")), # Mensagem legível
            "type": error.get("type", ""),    # Tipo de erro
        })
    
    logger.warning(
        f"[{request_id}] Validation error | "
        f"errors={errors}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Dados de entrada inválidos",
            "details": errors,
            "request_id": request_id,
        }
    )
```

**Quando é ativado:**

```python
# Cliente envia JSON inválido
{
    "transcript": "...",
    "raw_meeting": {...}  # ❌ Ambos fornecidos (erro!)
}

# FastAPI valida contra ExtractRequest
# ExtractRequest.validate_exclusive_fields() lança ValueError
# Handler captura e retorna:
```

**Resposta:**

```json
{
  "error": "validation_error",
  "message": "Dados de entrada inválidos",
  "details": [
    {
      "loc": ["body"],
      "msg": "Value error, Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum",
      "type": "value_error"
    }
  ],
  "request_id": "abc-123"
}
```

### 2. `generic_exception_handler` - Erro 500

Captura **qualquer exceção não tratada** e retorna uma resposta genérica:

```python
@app.exception_handler(Exception)
async def generic_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handler genérico para exceções não tratadas (500 Internal Server Error)."""
    request_id = getattr(request.state, "request_id", "-")
    
    logger.error(
        f"[{request_id}] Unhandled exception | "
        f"type={type(exc).__name__} | "
        f"error={str(exc)[:200]}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "Erro interno do servidor",
            "request_id": request_id,
        }
    )
```

**Por que um handler genérico?**

- ✅ Evita expor detalhes internos sensíveis ao cliente
- ✅ Garante que sempre há uma resposta estruturada
- ✅ Loga erros inesperados para debugging
- ✅ Melhora a experiência do usuário (mensagem clara)

**Sem handler genérico:**

```json
{
  "detail": "AttributeError: 'NoneType' object has no attribute 'split'"
}
```

**Com handler genérico:**

```json
{
  "error": "internal_server_error",
  "message": "Erro interno do servidor",
  "request_id": "abc-123"
}
```

---

## 📡 Endpoints

### 1. `GET /health` - Health Check

**Propósito:** Verificar se o serviço está funcionando.

```python
@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, str]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "meeting-extractor",
    }
```

**Uso típico:**

- Load balancers (verificar se instância está saudável)
- Kubernetes liveness/readiness probes
- Monitoramento (Datadog, New Relic, etc)
- CI/CD pipelines (verificar deploy bem-sucedido)

**Exemplo:**

```bash
curl http://localhost:8000/health

# Resposta:
{
  "status": "healthy",
  "service": "meeting-extractor"
}
```

---

### 2. `POST /extract` - Extração de Informações

**Propósito:** Extrair informações estruturadas de uma transcrição.

```python
@app.post(
    "/extract",
    response_model=ExtractedMeeting,
    status_code=status.HTTP_200_OK,
    tags=["Extraction"],
    summary="Extrai informações estruturadas de uma transcrição",
    response_description="Informações estruturadas extraídas com sucesso"
)
async def extract_meeting(
    request: Request,
    body: ExtractRequest
) -> ExtractedMeeting:
    """Extrai informações estruturadas de uma transcrição de reunião."""
```

#### Parâmetros do Decorator

| Parâmetro | Valor | Propósito |
|-----------|-------|-----------|
| `response_model` | `ExtractedMeeting` | Define schema de resposta (validação + docs) |
| `status_code` | `200` | Código HTTP padrão de sucesso |
| `tags` | `["Extraction"]` | Agrupa endpoints na documentação |
| `summary` | "Extrai..." | Título curto no Swagger |
| `response_description` | "Informações..." | Descrição da resposta no Swagger |

#### Fluxo Interno do Endpoint

```python
request_id = request.state.request_id  # Obtido do middleware

# Log início (sem PII completa)
logger.info(
    f"[{request_id}] POST /extract | "
    f"format={'raw_meeting' if body.raw_meeting else 'transcript+metadata'}"
)

try:
    # 1️⃣ Normalizar input
    normalized = body.to_normalized()
    
    logger.info(
        f"[{request_id}] Input normalizado | "
        f"transcript_len={len(normalized.transcript)} | "
        f"has_metadata={normalized.meeting_id is not None}"
    )
    
    # 2️⃣ Chamar o extractor (LangChain + OpenAI)
    extracted = await extract_meeting_chain(
        normalized=normalized,
        request_id=request_id
    )
    
    # 3️⃣ Log sucesso
    logger.info(
        f"[{request_id}] Extração concluída com sucesso | "
        f"meeting_id={extracted.meeting_id} | "
        f"idempotency_key={extracted.idempotency_key[:16]}..."
    )
    
    return extracted
    
except (RateLimitError, APITimeoutError, APIError) as e:
    # Erros da OpenAI API → retornar 502 Bad Gateway
    logger.error(
        f"[{request_id}] Erro na OpenAI API | "
        f"type={type(e).__name__} | "
        f"error={str(e)[:200]}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": "openai_api_error",
            "message": (
                "Erro ao comunicar com OpenAI API. "
                "Tente novamente em alguns instantes."
            ),
            "error_type": type(e).__name__,
            "request_id": request_id,
        }
    )

except ValidationError as e:
    # Erro de validação Pydantic no output do LLM (após repair)
    logger.error(
        f"[{request_id}] Validação do output falhou após repair | "
        f"errors={e.errors()}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "llm_output_validation_error",
            "message": (
                "Não foi possível extrair informações válidas da transcrição. "
                "Por favor, verifique se a transcrição está legível."
            ),
            "request_id": request_id,
        }
    )

except Exception as e:
    # Qualquer outro erro não previsto
    logger.error(
        f"[{request_id}] Erro inesperado | "
        f"type={type(e).__name__} | "
        f"error={str(e)[:200]}"
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "Erro interno ao processar a requisição",
            "request_id": request_id,
        }
    )
```

---

### 🚨 Tratamento de Erros Específicos do `/extract`

O endpoint `/extract` possui **3 tipos de erro específicos** além dos handlers globais:

#### **1. OpenAI Communication Error → 502 Bad Gateway**

**Quando acontece:**
- ⏱️ **Rate limit da OpenAI atingido** - Muitas requisições em pouco tempo
- ⏰ **Timeout (>30s)** - Chamada para OpenAI demorou muito
- 🔌 **API da OpenAI fora do ar** - Indisponibilidade do serviço OpenAI

**Por que 502?** É um problema de **comunicação** com serviço externo (upstream).

**Código (linhas 369-389 do main.py):**
```python
except (RateLimitError, APITimeoutError, APIError) as e:
    logger.error(
        f"[{request_id}] Erro de comunicação com OpenAI API | "
        f"type={type(e).__name__}"
    )
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": "openai_communication_error",
            "message": "Erro ao comunicar com OpenAI API (timeout, rate limit ou indisponibilidade). "
                      "Tente novamente em alguns instantes.",
            "error_type": type(e).__name__,
            "request_id": request_id,
        }
    )
```

**Resposta:** Pede para o cliente tentar novamente mais tarde

**Exemplo de resposta:**
```json
{
  "error": "openai_communication_error",
  "message": "Erro ao comunicar com OpenAI API (timeout, rate limit ou indisponibilidade). Tente novamente em alguns instantes.",
  "error_type": "RateLimitError",
  "request_id": "abc-123"
}
```

**Log correspondente:**
```
[abc-123] Erro de comunicação com OpenAI API | type=RateLimitError | error=Rate limit exceeded...
```

---

#### **2. OpenAI Invalid Response → 502 Bad Gateway**

**Quando acontece:**
- 🤖 **OpenAI retornou dados inválidos** mesmo após tentativa de reparo automático
- 📝 **Transcrição muito confusa** - IA não conseguiu extrair informações no formato correto
- ❌ **Summary fora do padrão** - Não tem 100-200 palavras
- 🔧 **Campos obrigatórios faltando** na resposta da IA

**Por que 502?** É um problema do **conteúdo retornado** pelo serviço externo (OpenAI), não um bug interno.

**Código (linhas 391-409 do main.py):**
```python
except ValidationError as e:
    # Erro de validação: OpenAI retornou dados inválidos → 502 Bad Gateway
    # Este é um problema do serviço externo (OpenAI), não interno
    logger.error(
        f"[{request_id}] OpenAI retornou dados inválidos após repair | "
        f"errors={e.errors()}"
    )
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={
            "error": "openai_invalid_response",
            "message": "OpenAI retornou dados inválidos ou incompletos. "
                      "Tente novamente ou verifique se a transcrição está legível.",
            "request_id": request_id,
        }
    )
```

**Resposta:** Sugere tentar novamente ou verificar a transcrição

**Exemplo de resposta:**
```json
{
  "error": "openai_invalid_response",
  "message": "OpenAI retornou dados inválidos ou incompletos. Tente novamente ou verifique se a transcrição está legível.",
  "request_id": "xyz-789"
}
```

**Log correspondente:**
```
[xyz-789] OpenAI retornou dados inválidos após repair | errors=[{'loc': ['summary'], 'msg': 'summary deve ter 100-200 palavras, tem 45'}]
```

---

#### **3. Erro Genérico/Inesperado → 500 Internal Server Error**

**Quando acontece:**
- 💥 **Qualquer outro erro não previsto** no código
- 🐛 **Bug não mapeado** na aplicação
- 🔧 **Problema de infraestrutura** (memória, disco, etc)

**Por que 500?** É um problema **interno da aplicação**, não do serviço externo.

**Código (linhas 411-424 do main.py):**
```python
except Exception as e:
    logger.error(
        f"[{request_id}] Erro inesperado | "
        f"type={type(e).__name__}"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "Erro interno ao processar a requisição",
            "request_id": request_id,
        }
    )
```

**Resposta:** Mensagem genérica (não expõe detalhes internos por segurança)

**Exemplo de resposta:**
```json
{
  "error": "internal_error",
  "message": "Erro interno ao processar a requisição",
  "request_id": "def-456"
}
```

**Log correspondente:**
```
[def-456] Erro inesperado | type=AttributeError | error='NoneType' object has no attribute 'split'
```

---

### 📊 Tabela Resumo: Erros do `/extract`

| Erro | Status | Causa | Ação do Cliente | Retry? |
|------|--------|-------|-----------------|--------|
| `openai_communication_error` | **502** | Timeout/rate limit/indisponibilidade | ⏰ Tentar novamente em alguns segundos | ✅ Sim |
| `openai_invalid_response` | **502** | OpenAI retornou dados inválidos | 🔄 Tentar novamente ou verificar transcrição | ✅ Sim |
| `internal_error` | **500** | Bug ou problema de infraestrutura | 🔍 Reportar com Request-ID para debug | ❌ Não |

---

### 🎯 Por que 502 para ambos os erros da OpenAI?

**Lógica:** O código HTTP **502 (Bad Gateway)** significa "problema com serviço upstream". Ambos os casos são problemas causados pela OpenAI:

1. **Communication Error:** A conexão/rede com OpenAI falhou
2. **Invalid Response:** A OpenAI não conseguiu gerar dados válidos

**Diferenciação:** Mesmo sendo o mesmo status code (502), você consegue diferenciar pelos:
- ✅ **Logs:** Mensagens diferentes (`Erro de comunicação` vs `retornou dados inválidos`)
- ✅ **Campo `error`:** `openai_communication_error` vs `openai_invalid_response`
- ✅ **Campo `error_type`:** Presente apenas no erro de comunicação (ex: `RateLimitError`)

**Vantagens:**
- ✅ Cliente sabe que pode fazer **retry** em ambos os casos (problema externo)
- ✅ Diferencia de **500** (problema interno → não adianta retry)
- ✅ Monitoramento pode rastrear "problemas com OpenAI" vs "bugs nossos"

---

### 📊 Estrutura Completa de Status Codes

```
┌──────────────────────────────────────────────────┐
│              STATUS CODE                         │
├──────────────────────────────────────────────────┤
│  200 - Sucesso                                   │
│                                                  │
│  422 - Problema no INPUT do cliente              │
│       → validation_error                         │
│       → ❌ Não retry                             │
│                                                  │
│  502 - Problema com OpenAI (externo)             │
│       → openai_communication_error               │
│          (timeout, rate limit, indisponível)     │
│       → openai_invalid_response                  │
│          (dados inválidos/incompletos)           │
│       → ✅ Retry recomendado                     │
│                                                  │
│  500 - Problema interno da aplicação             │
│       → internal_error                           │
│          (bug, infraestrutura)                   │
│       → ❌ Não retry                             │
└──────────────────────────────────────────────────┘
```

---

### 🔍 Diferenciação Detalhada dos Erros 502

| Método | Erro de Comunicação | Erro de Resposta Inválida |
|--------|---------------------|---------------------------|
| **Status HTTP** | 502 | 502 |
| **Campo `error`** | `openai_communication_error` | `openai_invalid_response` |
| **Campo `error_type`** | `RateLimitError` / `APITimeoutError` / `APIError` | ❌ Ausente |
| **Log (início)** | `Erro de comunicação com OpenAI API` | `OpenAI retornou dados inválidos após repair` |
| **Causa raiz** | Rede, timeout, rate limit, API fora do ar | LLM gerou resposta inválida ou incompleta |
| **Ação sugerida** | Aguardar e tentar novamente | Verificar transcrição ou tentar novamente |

---

## 🔄 Fluxo de Requisição Completo

### 🏗️ Arquitetura Completa: Visão End-to-End

Este diagrama mostra o fluxo completo desde o cliente até a resposta final:

```
┌──────────────────────────────────────────────────────────┐
│                      CLIENTE                             │
│              (curl, Postman, frontend)                   │
└────────────────────┬─────────────────────────────────────┘
                     │ HTTP Request (POST /extract)
                     ↓
┌──────────────────────────────────────────────────────────┐
│                   MAIN.PY (FastAPI)                      │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Middleware: Add Request ID                        │  │
│  │  - Gera/preserva X-Request-ID                      │  │
│  │  - Salva em request.state                          │  │
│  └────────────────────────────────────────────────────┘  │
│                     ↓                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Validação: Pydantic (ExtractRequest)             │  │
│  │  - Valida formato do JSON                          │  │
│  │  - Verifica campos obrigatórios                    │  │
│  │  - Se inválido → 422 Validation Error             │  │
│  └────────────────────────────────────────────────────┘  │
│                     ↓                                    │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Endpoint: /extract                                │  │
│  │  - Normaliza input (to_normalized)                 │  │
│  │  - Chama extractor                                 │  │
│  │  - Logs estruturados                               │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────┐
│              EXTRACTOR (LangChain)                       │
│              app/extractors/extractor.py                 │
│  ┌────────────────────────────────────────────────────┐  │
│  │  - Monta prompt estruturado                        │  │
│  │  - Chama OpenAI API (com retry/timeout)            │  │
│  │  - Parse resposta JSON                             │  │
│  │  - Repair automático se JSON inválido              │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────┘
                     │
                     ↓
┌──────────────────────────────────────────────────────────┐
│                  OpenAI API                              │
│              (GPT-4, GPT-3.5, etc)                       │
│  ┌────────────────────────────────────────────────────┐  │
│  │  - Processa transcrição                            │  │
│  │  - Extrai: summary, key_points, action_items       │  │
│  │  - Retorna JSON estruturado                        │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────┘
                     │ JSON estruturado
                     ↓
┌──────────────────────────────────────────────────────────┐
│              Validação Final (Pydantic)                  │
│              ExtractedMeeting schema                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │  - Valida todos os campos obrigatórios             │  │
│  │  - Valida summary (100-200 palavras)               │  │
│  │  - Calcula idempotency_key (SHA-256)               │  │
│  │  - Se inválido → 500 após repair                   │  │
│  └────────────────────────────────────────────────────┘  │
└────────────────────┬─────────────────────────────────────┘
                     │ ✅ Validado!
                     ↓ Retorna 200 OK
┌──────────────────────────────────────────────────────────┐
│                      CLIENTE                             │
│              Recebe JSON estruturado                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │  {                                                  │  │
│  │    "meeting_id": "MTG123",                         │  │
│  │    "summary": "...",                                │  │
│  │    "key_points": [...],                            │  │
│  │    "action_items": [...],                          │  │
│  │    "topics": [...],                                │  │
│  │    "idempotency_key": "7e3e97..."                  │  │
│  │  }                                                  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 🎯 Pontos-Chave da Arquitetura

| Componente | Responsabilidade | Falha → Status |
|------------|------------------|----------------|
| **Middleware** | Rastreamento (Request-ID) | - |
| **Pydantic (entrada)** | Validação do body | → 422 |
| **Endpoint** | Orquestração do fluxo | → 500 |
| **Extractor** | Chamada OpenAI + retry | → 502 (OpenAI) / 500 (outros) |
| **Pydantic (saída)** | Validação do resultado | → 500 (após repair) |

---

### Caso de Sucesso (Happy Path)

```
1. Cliente → POST /extract
   {
     "transcript": "Cliente: Olá...",
     "metadata": {"meeting_id": "MTG001"}
   }
   ↓
   
2. Middleware: add_request_id
   - Gera UUID: "abc-123"
   - Salva em request.state.request_id
   ↓
   
3. FastAPI: Validação Automática
   - Valida body contra ExtractRequest (Pydantic)
   - ✅ OK! (formato válido)
   ↓
   
4. Endpoint: extract_meeting
   - Log: "[abc-123] POST /extract | format=transcript+metadata"
   - Normaliza: body.to_normalized()
   - Log: "[abc-123] Input normalizado | transcript_len=790"
   - Chama: extract_meeting_chain()
   ↓
   
5. Extractor: extractor.py
   - Monta prompt
   - Chama OpenAI API
   - Valida com Pydantic
   - Calcula idempotency_key
   - Retorna ExtractedMeeting
   ↓
   
6. Endpoint: extract_meeting (continuação)
   - Log: "[abc-123] Extração concluída | meeting_id=MTG001"
   - Retorna extracted
   ↓
   
7. FastAPI: Serialização
   - Converte ExtractedMeeting → JSON
   - Valida contra response_model
   ↓
   
8. Middleware: add_request_id (retorno)
   - Adiciona header: X-Request-ID: abc-123
   ↓
   
9. Cliente ← 200 OK
   {
     "meeting_id": "MTG001",
     "summary": "...",
     ...
   }
```

---

### Caso de Erro: Validação de Entrada (422)

```
1. Cliente → POST /extract
   {
     "transcript": "...",
     "raw_meeting": {...}  # ❌ Ambos fornecidos
   }
   ↓
   
2. Middleware: add_request_id
   - request_id = "xyz-789"
   ↓
   
3. FastAPI: Validação Automática
   - Tenta validar contra ExtractRequest
   - ExtractRequest.validate_exclusive_fields() lança ValueError
   - ❌ FALHA!
   ↓
   
4. Exception Handler: validation_exception_handler
   - Log: "[xyz-789] Validation error | errors=[...]"
   - Retorna JSONResponse(422, {...})
   ↓
   
5. Cliente ← 422 Unprocessable Entity
   {
     "error": "validation_error",
     "message": "Dados de entrada inválidos",
     "details": [...]
   }
```

---

### Caso de Erro: OpenAI Communication (502)

```
1. Cliente → POST /extract (válido)
   ↓
   
2-3. Validação OK
   ↓
   
4. Endpoint: extract_meeting
   - Chama extract_meeting_chain()
   ↓
   
5. Extractor: extractor.py
   - Tenta chamar OpenAI API
   - Tentativa 1: ❌ RateLimitError (429)
   - Espera 0.5s...
   - Tentativa 2: ❌ RateLimitError (429)
   - Espera 1s...
   - Tentativa 3: ❌ RateLimitError (429)
   - Lança RateLimitError
   ↓
   
6. Endpoint: extract_meeting (catch)
   - Captura RateLimitError
   - Log: "[abc-123] Erro de comunicação com OpenAI API | type=RateLimitError"
   - Retorna JSONResponse(502, {...})
   ↓
   
7. Cliente ← 502 Bad Gateway
   {
     "error": "openai_communication_error",
     "message": "Erro ao comunicar com OpenAI API (timeout, rate limit...)...",
     "error_type": "RateLimitError"
   }
```

---

### Caso de Erro: OpenAI Invalid Response (502)

```
1. Cliente → POST /extract (válido)
   ↓
   
2-3. Validação OK
   ↓
   
4. Endpoint: extract_meeting
   - Chama extract_meeting_chain()
   ↓
   
5. Extractor: extractor.py
   - Chama OpenAI API
   - ✅ OpenAI responde com JSON
   - Tenta validar com Pydantic
   - ❌ ValidationError (summary tem 45 palavras, precisa 100-200)
   - Tenta repair
   - Chama OpenAI novamente para corrigir
   - ❌ Ainda inválido
   - Lança ValidationError
   ↓
   
6. Endpoint: extract_meeting (catch)
   - Captura ValidationError
   - Log: "[xyz-789] OpenAI retornou dados inválidos após repair | errors=[...]"
   - Retorna JSONResponse(502, {...})
   ↓
   
7. Cliente ← 502 Bad Gateway
   {
     "error": "openai_invalid_response",
     "message": "OpenAI retornou dados inválidos ou incompletos...",
   }
```

---

## 📊 Códigos de Status HTTP

### Sucesso

| Código | Nome | Quando Ocorre |
|--------|------|---------------|
| **200** | OK | Extração bem-sucedida |

### Erros do Cliente

| Código | Nome | Quando Ocorre |
|--------|------|---------------|
| **422** | Unprocessable Entity | Validação de entrada falhou (body JSON inválido) |

### Erros do Servidor

| Código | Nome | Quando Ocorre |
|--------|------|---------------|
| **502** | Bad Gateway | Problema com OpenAI (comunicação ou resposta inválida) |
| **500** | Internal Server Error | Problema interno da aplicação (bug ou infraestrutura) |

### Tabela Detalhada

| Status | Erro | Causa | Solução | Retry? |
|--------|------|-------|---------|--------|
| 200 | - | - | ✅ Sucesso | - |
| 422 | `validation_error` | Body JSON mal formatado ou campos inválidos | Verificar formato da requisição | ❌ Não |
| 502 | `openai_communication_error` | Timeout, rate limit ou OpenAI indisponível | Tentar novamente em alguns segundos | ✅ Sim |
| 502 | `openai_invalid_response` | OpenAI retornou dados inválidos/incompletos | Tentar novamente ou verificar transcrição | ✅ Sim |
| 500 | `internal_error` | Bug no código ou problema de infraestrutura | Reportar com Request-ID para debug | ❌ Não |

### 🎯 Decisão de Retry por Status Code

```
┌─────────────────────────────────────────────────┐
│  Status 422 (Client Error)                      │
│  → Problema no input do cliente                 │
│  → ❌ NÃO RETRY (vai falhar de novo)            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Status 502 (Bad Gateway)                       │
│  → Problema com serviço externo (OpenAI)        │
│  → ✅ RETRY (problema pode ser temporário)      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│  Status 500 (Internal Error)                    │
│  → Problema interno da aplicação                │
│  → ❌ NÃO RETRY (vai falhar de novo)            │
└─────────────────────────────────────────────────┘
```

---

## 🎓 Exemplos Práticos

### Exemplo 1: Requisição Bem-Sucedida

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-custom-id" \
  -d '{
    "transcript": "Cliente: Olá, preciso de um empréstimo de R$ 500 mil...",
    "metadata": {
      "meeting_id": "MTG-2025-001",
      "customer_id": "CUST-456",
      "meet_date": "2025-09-10T14:30:00Z"
    }
  }'
```

**Resposta:**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: my-custom-id

{
  "meeting_id": "MTG-2025-001",
  "customer_id": "CUST-456",
  "customer_name": "João Silva",
  "banker_name": "Pedro Falcão",
  "meet_type": "Empréstimo",
  "meet_date": "2025-09-10T14:30:00Z",
  "summary": "Reunião focou em... (169 palavras)",
  "key_points": ["Cliente precisa de R$ 500k", "..."],
  "action_items": ["Preparar proposta", "..."],
  "topics": ["Empréstimo", "Capital de Giro"],
  "source": "lftm-challenge",
  "idempotency_key": "7e3e97ffd83f...",
  "transcript_ref": null,
  "duration_sec": null
}
```

---

### Exemplo 2: Erro de Validação (422)

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "...",
    "raw_meeting": {...}
  }'
```

**Resposta:**

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
X-Request-ID: a1b2c3d4-...

{
  "error": "validation_error",
  "message": "Dados de entrada inválidos",
  "details": [
    {
      "loc": ["body"],
      "msg": "Value error, Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum",
      "type": "value_error"
    }
  ],
  "request_id": "a1b2c3d4-..."
}
```

---

### Exemplo 3: Erro de Comunicação com OpenAI (502)

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "Cliente: Olá..."
  }'
```

**Resposta (se OpenAI estiver com rate limit):**

```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json
X-Request-ID: xyz-789

{
  "error": "openai_communication_error",
  "message": "Erro ao comunicar com OpenAI API (timeout, rate limit ou indisponibilidade). Tente novamente em alguns instantes.",
  "error_type": "RateLimitError",
  "request_id": "xyz-789"
}
```

---

### Exemplo 4: Erro de Resposta Inválida da OpenAI (502)

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "transcript": "aksdjfh asdkjfh lkjasdhf asdkjfh..."
  }'
```

**Resposta (se OpenAI retornar dados inválidos):**

```http
HTTP/1.1 502 Bad Gateway
Content-Type: application/json
X-Request-ID: abc-456

{
  "error": "openai_invalid_response",
  "message": "OpenAI retornou dados inválidos ou incompletos. Tente novamente ou verifique se a transcrição está legível.",
  "request_id": "abc-456"
}
```

**Nota:** Mesmo status code (502), mas o campo `error` diferencia os tipos de problema

---

## 📖 Documentação Automática

FastAPI gera documentação automática baseada nos schemas e docstrings:

### Swagger UI (Interativo)

**URL:** http://localhost:8000/docs

**Características:**
- ✅ Interface interativa ("Try it out")
- ✅ Exemplos de requisição/resposta
- ✅ Validação em tempo real
- ✅ Autenticação (se configurada)

![Swagger UI Example](https://fastapi.tiangolo.com/img/index/index-01-swagger-ui-simple.png)

### ReDoc (Navegável)

**URL:** http://localhost:8000/redoc

**Características:**
- ✅ Visão mais limpa e navegável
- ✅ Melhor para leitura/impressão
- ✅ Suporte a markdown nas descrições

---

## 🔍 Debugging

### Como debugar requisições?

1. **Obtenha o Request-ID da resposta:**

```bash
curl -i http://localhost:8000/extract ...
# Header: X-Request-ID: abc-123
```

2. **Filtre logs por Request-ID:**

```bash
grep "abc-123" logs.txt
```

3. **Analise a sequência de logs:**

```
[abc-123] POST /extract | format=transcript+metadata
[abc-123] Input normalizado | transcript_len=790
[abc-123] Iniciando extração | has_metadata=sim
[abc-123] LLM respondeu | output_keys=[...]
[abc-123] Validação OK
[abc-123] Extração concluída | meeting_id=MTG001
```

---

## 💡 Dicas e Boas Práticas

### 1. Sempre valide a entrada com Pydantic

```python
# ✅ BOM - Pydantic valida automaticamente
@app.post("/extract")
async def extract(body: ExtractRequest):
    # body já está validado aqui
    pass

# ❌ RUIM - Sem validação
@app.post("/extract")
async def extract(request: Request):
    body = await request.json()
    # body pode ter qualquer formato!
    pass
```

### 2. Use async/await para operações I/O

```python
# ✅ BOM - Assíncrono (não bloqueia)
@app.post("/extract")
async def extract(body: ExtractRequest):
    result = await extract_meeting_chain(...)
    return result

# ❌ RUIM - Síncrono (bloqueia thread)
@app.post("/extract")
def extract(body: ExtractRequest):
    result = extract_meeting_chain_sync(...)
    return result
```

### 3. Sempre logue Request-ID

```python
# ✅ BOM - Rastreável
logger.info(f"[{request_id}] Processando...")

# ❌ RUIM - Não rastreável
logger.info("Processando...")
```

### 4. Retorne códigos HTTP apropriados

```python
# ✅ BOM - Código específico
if error_da_openai:
    return JSONResponse(status_code=502, ...)

# ❌ RUIM - Sempre 500
if any_error:
    return JSONResponse(status_code=500, ...)
```

---

## 📚 Referências

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Starlette (base do FastAPI):** https://www.starlette.io/
- **HTTP Status Codes:** https://httpstatuses.com/

---

## 📝 Resumo

O `main.py` é responsável por:

1. ✅ Expor endpoints HTTP (`/health`, `/extract`)
2. ✅ Validar entrada automaticamente (Pydantic)
3. ✅ Adicionar Request-ID para rastreamento (middleware)
4. ✅ Tratar erros de forma robusta (3 tipos específicos + handlers globais)
5. ✅ Gerar documentação automática (Swagger/ReDoc)
6. ✅ Integrar todas as camadas (schemas + extractor)

### 🔗 Componentes Relacionados

- **Schemas:** [02-SCHEMAS.md](02-SCHEMAS.md) - Validação de dados (ExtractRequest, ExtractedMeeting)
- **Extractor:** [03-EXTRACTOR.md](03-EXTRACTOR.md) - Lógica de chamada à OpenAI
- **Docker:** [DOCKER.md](DOCKER.md) - Como executar a aplicação

### 📊 Diagrama de Arquitetura Completa

O diagrama **"Arquitetura Completa: Visão End-to-End"** neste documento (seção 🔄 Fluxo de Requisição Completo) mostra:
- ✅ Fluxo completo: Cliente → FastAPI → Extractor → OpenAI → Resposta
- ✅ Pontos de validação (entrada e saída)
- ✅ Tratamento de erros em cada camada
- ✅ Responsabilidades de cada componente

---

**Navegação:**
- ⬅️ **Anterior:** [03-EXTRACTOR.md](03-EXTRACTOR.md) - Lógica de extração
- ⬆️ **Índice:** [01-OVERVIEW.md](01-OVERVIEW.md) - Visão geral do sistema

