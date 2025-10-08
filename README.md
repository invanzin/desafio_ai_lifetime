# 📚 Documentação Completa do Microserviço de Extração

Bem-vindo à documentação completa do **Microserviço de Extração de Reuniões**!

Esta documentação foi criada para ajudá-lo a entender **cada aspecto** do sistema, desde a arquitetura geral até os detalhes de implementação de cada componente.

---

## 🚀 Quick Start

### 1️⃣ Configurar Variáveis de Ambiente

Copie o arquivo de exemplo e configure suas credenciais:

```bash
# Linux/Mac
cp env.example .env

# Windows (PowerShell)
copy env.example .env

# Windows (CMD)
copy env.example .env
```

**Edite o arquivo `.env` e preencha:**
- `OPENAI_API_KEY` - sua chave da OpenAI (obrigatório)
- `LANGCHAIN_API_KEY` - sua chave do LangSmith (opcional, para observabilidade)
- `EXTRACTOR_PROMPT_HUB_NAME` - nome do seu prompt no LangChain Hub

### 2️⃣ Instalar Dependências

```bash
# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Linux/Mac
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 3️⃣ Executar a API

```bash
# Desenvolvimento (com reload automático)
uvicorn app.main:app --reload --port 8000

# Produção
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 4️⃣ Testar

```bash
# Executar todos os testes
pytest

# Executar apenas testes unitários
pytest tests/unit/ -v

# Executar apenas testes de integração
pytest tests/integration/ -v
```

### 5️⃣ Acessar Documentação Interativa

Após iniciar a API, acesse:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Métricas Prometheus: http://localhost:8000/metrics

---

## 📖 Estrutura da Documentação

A documentação está organizada em **4 partes principais**, projetadas para serem lidas em sequência:

### 1️⃣ [Visão Geral (OVERVIEW)](documentation/01-OVERVIEW-EXTRACTOR.md)

**O que você vai aprender:**
- 🎯 O que o microserviço faz
- 🏗️ Arquitetura em 3 camadas
- 🔄 Fluxo completo de dados
- 📁 Estrutura de pastas do projeto
- 🚀 Como iniciar a aplicação
- 🛠️ Tecnologias utilizadas
- 💡 Conceitos importantes (Idempotência, Request ID, etc)

**Ideal para:**
- ✅ Entender o sistema como um todo
- ✅ Primeiro contato com o projeto
- ✅ Onboarding de novos desenvolvedores

---

### 2️⃣ [Schemas (Validação de Dados)](documentation/02-SCHEMAS.md)

**O que você vai aprender:**
- 📋 O que são schemas Pydantic
- 🏗️ Arquitetura de validação em 3 camadas
- 📥 Schemas de entrada (Metadata, RawMeeting, ExtractRequest)
- 🔄 Schema interno (NormalizedInput)
- 📤 Schema de saída (ExtractedMeeting)
- 🔄 Como funciona a conversão entre formatos
- 🎓 Exemplos práticos de cada schema

**Ideal para:**
- ✅ Entender como os dados são validados
- ✅ Adicionar novos campos
- ✅ Criar novos formatos de entrada
- ✅ Debugar erros de validação

**Arquivos relacionados:**
- `app/models/schemas_common.py` - Schemas compartilhados
- `app/models/schemas_extract.py` - Schemas do Extractor
- `app/models/schemas_analyze.py` - Schemas do Analyzer

---

### 3️⃣ [Extractor (Processamento com IA)](documentation/03-EXTRACTOR.md)

**O que você vai aprender:**
- 🤖 Como funciona o LangChain
- 🏗️ Arquitetura da chain (Prompt → LLM → Parser)
- 🧩 Componentes principais (LLM, Prompt, Auxiliares)
- 🔄 Fluxo de extração passo a passo
- 🔁 Sistema de retry com backoff exponencial
- 🔧 Sistema de reparo de JSONs malformados
- 📊 Logging estruturado e seguro
- 🎓 Exemplos práticos de cada cenário

**Ideal para:**
- ✅ Entender como a IA extrai informações
- ✅ Ajustar o prompt do LLM
- ✅ Modificar a lógica de retry
- ✅ Debugar erros de extração
- ✅ Otimizar performance

**Arquivos relacionados:**
- `app/extractors/extractor.py` (432 linhas)

---

### 4️⃣ [Main API (Endpoints FastAPI)](documentation/04-MAIN-API.md)

**O que você vai aprender:**
- 🌐 Arquitetura FastAPI em camadas
- 🔧 Como funciona o middleware (Request-ID)
- 🚨 Exception handlers (422, 500, 502)
- 📡 Endpoints (GET /health, POST /extract)
- 🔄 Fluxo completo de requisição
- 📊 Códigos de status HTTP e quando usar
- 🎓 Exemplos práticos de requisições

**Ideal para:**
- ✅ Entender como a API funciona
- ✅ Adicionar novos endpoints
- ✅ Customizar tratamento de erros
- ✅ Debugar requisições HTTP
- ✅ Testar a API

**Arquivos relacionados:**
- `app/main.py` (444 linhas)

---

### 5️⃣ [Testes (Testing)](documentation/05-TESTING.md) ✨ **NOVO!**

**O que você vai aprender:**
- 🧪 Estrutura de testes (unitários e integração)
- 📊 Cobertura de testes (44 testes, ~85%)
- 🚀 Como rodar os testes
- 📝 Boas práticas de testes
- 🔧 Troubleshooting comum
- 🎨 Logs bonitos nos testes

**Ideal para:**
- ✅ Entender o que está testado
- ✅ Adicionar novos testes
- ✅ Rodar testes específicos
- ✅ Debugar testes que falham
- ✅ Medir cobertura de código

**Arquivos relacionados:**
- `tests/unit/test_schemas.py` (20 testes)
- `tests/unit/test_extractor.py` (11 testes)
- `tests/integration/test_main_api.py` (15 testes)

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

## 🗺️ Mapa de Navegação

```
📚 README.md (você está aqui)
    │
    ├─► documentation/01-OVERVIEW-EXTRACTOR.md ◄─ Comece aqui!
    │       ↓
    ├─► documentation/02-SCHEMAS.md (Validação de dados)
    │       ↓
    ├─► documentation/03-EXTRACTOR.md (Processamento com IA)
    │       ↓
    ├─► documentation/04-MAIN-API.md (Endpoints HTTP)
    │       ↓
    └─► documentation/05-TESTING.md (Testes)
```

---

## 🎯 Guias de Leitura por Perfil

### 👨‍💼 Gerente / Product Owner

**Leia:**
1. [01-OVERVIEW-EXTRACTOR.md](documentation/01-OVERVIEW-EXTRACTOR.md) - Seções: "Visão Geral" e "Fluxo de Dados"

**Tempo estimado:** 10 minutos

**O que você vai entender:**
- O que o sistema faz
- Como os dados fluem
- Principais funcionalidades

---

### 👨‍💻 Desenvolvedor (Backend)

**Leia em ordem:**
1. [01-OVERVIEW-EXTRACTOR.md](documentation/01-OVERVIEW-EXTRACTOR.md) - Completo
2. [02-SCHEMAS.md](documentation/02-SCHEMAS.md) - Completo
3. [03-EXTRACTOR.md](documentation/03-EXTRACTOR.md) - Completo
4. [04-MAIN-API.md](documentation/04-MAIN-API.md) - Completo
5. [05-TESTING.md](documentation/05-TESTING.md) - Completo

**Tempo estimado:** 60-90 minutos

**O que você vai entender:**
- Arquitetura completa
- Como modificar/estender o código
- Como debugar problemas
- Boas práticas implementadas

---

### 🧪 QA / Tester

**Leia:**
1. [01-OVERVIEW-EXTRACTOR.md](documentation/01-OVERVIEW-EXTRACTOR.md) - Seções: "Visão Geral" e "Como Iniciar"
2. [04-MAIN-API.md](documentation/04-MAIN-API.md) - Seções: "Endpoints" e "Exemplos Práticos"
3. [05-TESTING.md](documentation/05-TESTING.md) - Como rodar os testes

**Tempo estimado:** 20 minutos

**O que você vai entender:**
- Como testar a API
- Cenários de sucesso e erro
- Códigos de status esperados

---

### 🎨 Frontend Developer

**Leia:**
1. [01-OVERVIEW-EXTRACTOR.md](documentation/01-OVERVIEW-EXTRACTOR.md) - Seção: "Visão Geral"
2. [02-SCHEMAS.md](documentation/02-SCHEMAS.md) - Seções: "Schemas de Entrada" e "Schema de Saída"
3. [04-MAIN-API.md](documentation/04-MAIN-API.md) - Seções: "Endpoints" e "Exemplos Práticos"

**Tempo estimado:** 30 minutos

**O que você vai entender:**
- Formatos de requisição aceitos
- Estrutura da resposta
- Como fazer chamadas HTTP
- Tratamento de erros

---

## 📂 Arquivos Principais

| Arquivo | Linhas | Responsabilidade | Documentação |
|---------|--------|------------------|--------------|
| `app/main.py` | ~678 | API FastAPI, endpoints | [04-MAIN-API.md](documentation/04-MAIN-API.md) |
| `app/models/schemas_common.py` | ~391 | Schemas compartilhados | [02-SCHEMAS.md](documentation/02-SCHEMAS.md) |
| `app/models/schemas_extract.py` | ~146 | Schemas do Extractor | [02-SCHEMAS.md](documentation/02-SCHEMAS.md) |
| `app/models/schemas_analyze.py` | ~136 | Schemas do Analyzer | [02-SCHEMAS.md](documentation/02-SCHEMAS.md) |
| `app/extractors/extractor.py` | ~541 | Extração com IA | [03-EXTRACTOR.md](documentation/03-EXTRACTOR.md) |
| `tests/unit/test_schemas.py` | ~344 | Testes de schemas | [05-TESTING.md](documentation/05-TESTING.md) |
| `tests/unit/test_extractor.py` | ~646 | Testes de extração | [05-TESTING.md](documentation/05-TESTING.md) |
| `tests/integration/test_main_api.py` | ~351 | Testes de API | [05-TESTING.md](documentation/05-TESTING.md) |

**Total:** ~3.233 linhas (código + testes)

---

## 🔍 Busca Rápida

### Como fazer X?

| Tarefa | Onde Encontrar |
|--------|----------------|
| Adicionar novo campo na saída | [02-SCHEMAS.md](documentation/02-SCHEMAS.md) → `ExtractedMeeting` |
| Modificar o prompt da IA | [03-EXTRACTOR.md](documentation/03-EXTRACTOR.md) → "Prompt System" |
| Adicionar novo endpoint | [04-MAIN-API.md](documentation/04-MAIN-API.md) → "Endpoints" |
| Entender erros de validação | [02-SCHEMAS.md](documentation/02-SCHEMAS.md) → "Exemplos Práticos" |
| Debugar erro de extração | [03-EXTRACTOR.md](documentation/03-EXTRACTOR.md) → "Debugging" |
| Customizar tratamento de erro | [04-MAIN-API.md](documentation/04-MAIN-API.md) → "Exception Handlers" |

---

## 📊 Métricas do Projeto

| Métrica | Valor |
|---------|-------|
| **Linhas de código** | ~1.490 |
| **Cobertura de documentação** | 100% |
| **Type hints** | 100% |
| **Docstrings** | 100% |
| **Testes** | 0% (TODO) |

---

## 🔗 Links Úteis

### Documentação Externa

- **FastAPI:** https://fastapi.tiangolo.com/
- **Pydantic:** https://docs.pydantic.dev/
- **LangChain:** https://python.langchain.com/docs/
- **OpenAI API:** https://platform.openai.com/docs/

### Arquivos do Projeto

- **README Principal:** `../README.md`
- **Conceitos:** `../CONCEPTS.md` (Request ID vs Idempotency Key)
- **Script de Teste:** `../test_api.py`
- **Requirements:** `../requirements.txt`

---

## 💬 Feedback

Encontrou algum erro ou tem sugestão de melhoria na documentação?

- 📧 Abra uma issue no repositório
- 💬 Comente com o time
- 📝 Submeta um PR com a correção

---

## 📜 Glossário

| Termo | Significado |
|-------|-------------|
| **Schema** | Estrutura de dados validada com Pydantic |
| **Extractor** | Componente que chama a IA para extrair informações |
| **Chain** | Sequência de operações no LangChain (prompt → LLM → parser) |
| **Idempotency Key** | Hash único para prevenir duplicatas |
| **Request ID** | UUID para rastrear requisições nos logs |
| **Retry** | Tentar novamente em caso de erro |
| **Backoff** | Espera progressiva entre retries |
| **PII** | Personally Identifiable Information (dados pessoais) |
| **LLM** | Large Language Model (modelo de linguagem, ex: GPT-4o) |

---

## 🎓 Próximos Passos

Após ler a documentação, você pode:

1. ✅ **Implementar testes** - Use pytest para criar testes unitários
2. ✅ **Adicionar cache** - Implemente Redis para cachear resultados
3. ✅ **Criar banco de dados** - Persista resultados com idempotency_key
4. ✅ **Dockerizar** - Crie Dockerfile e docker-compose
5. ✅ **Implementar Desafio 2** - Análise de sentimentos
6. ✅ **Criar orquestrador** - Use LangGraph para compor microserviços

---

**Boa leitura! 📚**

**Comece aqui:** [01-OVERVIEW-EXTRACTOR.md](documentation/01-OVERVIEW-EXTRACTOR.md)

