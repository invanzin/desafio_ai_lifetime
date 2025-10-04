# 🧪 Documentação de Testes

## 📚 Índice

1. [Visão Geral](#visão-geral)
2. [Estrutura de Testes](#estrutura-de-testes)
3. [Testes Unitários](#testes-unitários)
4. [Testes de Integração](#testes-de-integração)
5. [Como Rodar](#como-rodar)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 Visão Geral

Este projeto possui **44 testes automatizados** organizados em 5 arquivos:

| Arquivo | Tipo | Testes | Tempo | Status |
|---------|------|--------|-------|--------|
| `test_schemas.py` | Unitário | 18 | ~0.5s | ✅ |
| `test_extractor.py` | Unitário | 11 | ~4s | ✅ |
| `test_main_api.py` | Integração | 15 | ~3s | ✅ |
| `test_api.py` | E2E | - | - | ⏭️ Skipped |
| `test_challenge_audit.py` | Auditoria | - | - | Manual |

**Total:** 44 testes | ~8s | ✅ 100% passando

### Ferramentas
- `pytest` - Framework de testes
- `pytest-asyncio` - Testes assíncronos
- `TestClient` - Cliente HTTP (FastAPI)

---

## 📁 Estrutura de Testes

```
projeto/tests/
├── unit/
│   ├── test_schemas.py          # Validação Pydantic (18 testes)
│   └── test_extractor.py        # Funções auxiliares (11 testes)
└── integration/
    ├── test_main_api.py         # Endpoints HTTP (15 testes)
    ├── test_api.py              # E2E com OpenAI (skipped)
    └── test_challenge_audit.py  # Auditoria do briefing
```

---

## 🔬 Testes Unitários

### 1. `test_schemas.py` - Validação Pydantic (18 testes)

**Localização:** `tests/unit/test_schemas.py`  
**Tempo de execução:** ~0.5s

#### Propósito
Testa validação de schemas Pydantic, conversão entre formatos e cálculo de idempotency key.

#### Lista de Testes

| # | Nome do Teste | O que Testa |
|---|---------------|-------------|
| 1 | `test_metadata_all_fields_optional` | Todos os campos de Metadata são opcionais |
| 2 | `test_metadata_with_all_fields` | Criação de Metadata com todos os campos preenchidos |
| 3 | `test_extract_request_only_transcript` | ExtractRequest válido com apenas transcript |
| 4 | `test_extract_request_transcript_and_metadata` | ExtractRequest válido com transcript + metadata |
| 5 | `test_extract_request_only_raw_meeting` | ExtractRequest válido com apenas raw_meeting |
| 6 | `test_extract_request_both_formats_fails` | Erro ao fornecer transcript E raw_meeting (XOR) |
| 7 | `test_extract_request_neither_format_fails` | Erro ao não fornecer nenhum formato |
| 8 | `test_compute_idempotency_key_with_all_fields` | Cálculo correto de idempotency_key (SHA-256) |
| 9 | `test_compute_idempotency_key_is_deterministic` | Mesmos dados geram mesma chave sempre |
| 10 | `test_compute_idempotency_key_without_meeting_id` | Retorna None se faltar meeting_id |
| 11 | `test_compute_idempotency_key_without_customer_id` | Retorna None se faltar customer_id |
| 12 | `test_compute_idempotency_key_without_meet_date` | Retorna None se faltar meet_date |
| 13 | `test_extracted_meeting_summary_valid_length` | Summary com 100-200 palavras é aceito |
| 14 | `test_extracted_meeting_summary_too_short` | Erro se summary < 100 palavras |
| 15 | `test_extracted_meeting_summary_too_long` | Erro se summary > 200 palavras |
| 16 | `test_extracted_meeting_source_field` | Campo source tem valor "lftm-challenge" |
| 17 | `test_to_normalized_from_transcript_metadata` | Conversão de transcript+metadata para NormalizedInput |
| 18 | `test_to_normalized_from_raw_meeting` | Conversão de raw_meeting para NormalizedInput |

#### Rodar testes
```bash
pytest tests/unit/test_schemas.py -v
```

---

### 2. `test_extractor.py` - Funções Auxiliares (11 testes)

**Localização:** `tests/unit/test_extractor.py`  
**Tempo de execução:** ~4s

#### Propósito
Testa funções auxiliares de preparação de dados e sanitização para logs.

#### Lista de Testes

| # | Nome do Teste | O que Testa |
|---|---------------|-------------|
| 1 | `test_prepare_metadata_with_all_fields` | Formatação JSON com todos os campos |
| 2 | `test_prepare_metadata_without_optional_fields` | JSON omite campos None |
| 3 | `test_prepare_metadata_with_no_fields` | JSON vazio {} quando não há metadados |
| 4 | `test_prepare_metadata_partial_fields` | Mix de campos presentes e ausentes |
| 5 | `test_prepare_metadata_meet_date_formatting` | Data formatada em ISO 8601 |
| 6 | `test_sanitize_transcript_short` | Transcrições curtas não são truncadas |
| 7 | `test_sanitize_transcript_long` | Transcrições longas truncam em 300 chars |
| 8 | `test_sanitize_transcript_exact_limit` | Transcrição com exatamente 300 chars não trunca |
| 9 | `test_sanitize_transcript_custom_max_chars` | max_chars customizado funciona |
| 10 | `test_metadata_json_is_valid_json` | Output sempre é JSON válido |
| 11 | `test_metadata_json_has_proper_encoding` | Caracteres especiais (ç, ã) preservados |

#### Rodar testes
```bash
pytest tests/unit/test_extractor.py -v
```

---

## 🌐 Testes de Integração

### 1. `test_main_api.py` - Endpoints HTTP (15 testes)

**Localização:** `tests/integration/test_main_api.py`  
**Tempo de execução:** ~3s

#### Propósito
Testa endpoints HTTP, validação de entrada, error handling e documentação da API.

#### Lista de Testes

| # | Nome do Teste | O que Testa |
|---|---------------|-------------|
| 1 | `test_health_endpoint` | GET /health retorna status 200 |
| 2 | `test_extract_validation_error_422_no_input` | Erro 422 quando body vazio (sem transcript/raw_meeting) |
| 3 | `test_extract_validation_error_422_both_formats` | Erro 422 ao enviar transcript E raw_meeting |
| 4 | `test_extract_validation_error_422_invalid_types` | Erro 422 com tipos de campo inválidos |
| 5 | `test_extract_validation_error_422_invalid_datetime` | Erro 422 com datetime não-ISO 8601 |
| 6 | `test_extract_response_has_request_id_header` | Response tem header X-Request-ID |
| 7 | `test_extract_preserves_custom_request_id` | Request-ID customizado é preservado |
| 8 | `test_extract_generates_request_id_if_not_provided` | Request-ID gerado automaticamente (UUID v4) |
| 9 | `test_error_response_structure_422` | Estrutura de erro tem campos obrigatórios |
| 10 | `test_error_details_structure` | Campo details contém informações do erro |
| 11 | `test_extract_requires_json_content_type` | Erro 415 se Content-Type não for JSON |
| 12 | `test_extract_accepts_json_content_type` | Aceita application/json corretamente |
| 13 | `test_openapi_docs_available` | GET /docs retorna Swagger UI |
| 14 | `test_redoc_available` | GET /redoc retorna ReDoc |
| 15 | `test_openapi_json_available` | GET /openapi.json retorna schema OpenAPI |

#### Rodar testes
```bash
pytest tests/integration/test_main_api.py -v
```

---

### 2. `test_api.py` - Testes End-to-End (Skipped)

**Localização:** `tests/integration/test_api.py`  
**Tempo de execução:** ~60s (quando habilitado)

#### Propósito
Testes end-to-end que fazem chamadas REAIS à API OpenAI. São skipped por padrão para evitar custos.

#### Conteúdo
- Teste com formato `transcript + metadata`
- Teste com formato `raw_meeting`
- Teste com apenas `transcript` (IA extrai metadados)
- Validação de campos obrigatórios no response

#### Como habilitar
```bash
# Remover @pytest.mark.skip dos testes
# Configurar OPENAI_API_KEY no .env
pytest tests/integration/test_api.py -v
```

---

### 3. `test_challenge_audit.py` - Auditoria do Briefing (Script)

**Localização:** `tests/integration/test_challenge_audit.py`  
**Tipo:** Script manual (não roda com pytest)

#### Propósito
Valida se a API atende TODOS os requisitos do briefing do Desafio 1.

#### O que valida
1. **Health Check** - Serviço está online
2. **Campos Obrigatórios** - Todos os campos do briefing presentes
3. **Tipos de Dados** - Validação de tipos (str, datetime, list)
4. **Summary** - Entre 100-200 palavras
5. **Idempotency Key** - SHA-256 com 64 caracteres
6. **Source** - Valor "lftm-challenge"
7. **Formato de Data** - ISO 8601
8. **Arrays** - key_points, action_items, topics são listas

#### Como executar
```bash
# API deve estar rodando em localhost:8000
python tests/integration/test_challenge_audit.py
```

---

## 🚀 Como Rodar

### Pré-requisitos
```bash
# Ativar ambiente virtual
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

### Comandos Principais

```bash
# Rodar TODOS os testes
pytest tests/unit/ tests/integration/test_main_api.py -v

# Rodar apenas unitários
pytest tests/unit/ -v

# Rodar apenas integração
pytest tests/integration/test_main_api.py -v

# Rodar arquivo específico
pytest tests/unit/test_schemas.py -v

# Rodar teste específico
pytest tests/unit/test_schemas.py::test_extract_request_both_formats_fails -v

# Por palavra-chave
pytest -k "422" -v                    # Todos com "422"
pytest -k "metadata" -v               # Todos com "metadata"

# Com logs detalhados
pytest tests/unit/test_extractor.py -v -s

# Parar no primeiro erro
pytest tests/ -x

# Ver duração dos testes
pytest tests/ -v --durations=10
```

### Opções Úteis

| Opção | Descrição |
|-------|-----------|
| `-v` | Verboso (mostra nome de cada teste) |
| `-s` | Mostra print statements |
| `-x` | Para no primeiro erro |
| `-k PATTERN` | Roda testes que correspondem ao padrão |
| `--tb=short` | Traceback curto |
| `--tb=line` | Traceback de 1 linha |
| `-q` | Modo quiet (menos output) |
| `--durations=N` | Mostra N testes mais lentos |

---

## 🔧 Troubleshooting

### ❌ Erro: "No module named 'app'"

**Causa:** pytest não encontra o módulo `app`

**Solução:**
```bash
# Sempre rodar da raiz do projeto
cd projeto/
pytest tests/
```

---

### ❌ Erro: "pytest: command not found"

**Causa:** Ambiente virtual não ativado

**Solução:**
```bash
.\venv\Scripts\activate      # Windows
source venv/bin/activate     # Linux/Mac

# Verificar instalação
pip list | grep pytest
```

---

### ❌ Encoding error (Windows)

**Sintoma:** `UnicodeEncodeError: 'charmap' codec can't encode character`

**Solução:** Já resolvido! Usamos tags ASCII `[TAG]` ao invés de emojis.

---

### ⚠️ Testes lentos

**Diagnóstico:**
```bash
pytest tests/ -v --durations=10
```

**Causa comum:** Chamadas de I/O (rede, disco)  
**Solução:** Usar mocks para dependências externas

---

### ⚠️ Testes falham aleatoriamente

**Causa:** Dependência de ordem entre testes

**Teste:**
```bash
pytest tests/ --random-order
```

**Solução:** Garantir que cada teste seja independente

---

## 📝 Resumo

### Status dos Testes

| Métrica | Valor |
|---------|-------|
| **Total de Testes** | 44 |
| **Testes Passando** | ✅ 44 (100%) |
| **Tempo Total** | ~8s |
| **Cobertura** | ~85% |

### Arquivos de Teste

| Arquivo | Tipo | Testes | Descrição |
|---------|------|--------|-----------|
| `test_schemas.py` | Unitário | 18 | Validação Pydantic |
| `test_extractor.py` | Unitário | 11 | Funções auxiliares |
| `test_main_api.py` | Integração | 15 | Endpoints HTTP |
| `test_api.py` | E2E | - | Skipped (OpenAI) |
| `test_challenge_audit.py` | Script | - | Auditoria manual |

### Comandos Rápidos

```bash
# Rodar tudo
pytest tests/unit/ tests/integration/test_main_api.py -v

# Apenas unitários
pytest tests/unit/ -v

# Teste específico
pytest tests/unit/test_schemas.py::test_extract_request_both_formats_fails -v

# Por palavra-chave
pytest -k "422" -v
```

---

**Navegação:**
- ⬅️ **Anterior:** [04-MAIN-API.md](04-MAIN-API.md) - Documentação da API
- ⬆️ **Índice:** [01-OVERVIEW.md](01-OVERVIEW.md) - Visão geral do sistema
