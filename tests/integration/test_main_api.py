"""
Testes de integração para main.py (API endpoints).

Testa o comportamento dos endpoints HTTP, incluindo error handling
e validação de respostas para diferentes cenários.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from app.main import app


# ============================================================================
# CONFIGURAÇÃO DE LOGGING BONITO
# ============================================================================

def print_test_header(test_name: str, emoji: str = "[TEST]"):
    """Imprime um cabeçalho bonito para o teste."""
    print(f"\n{'='*70}")
    print(f"{emoji}  {test_name}")
    print(f"{'='*70}")


def print_request(method: str, endpoint: str, body: dict = None):
    """Imprime detalhes da requisição."""
    print(f"  [REQUEST] {method} {endpoint}")
    if body:
        print(f"            Body: {str(body)[:100]}...")


def print_response(status_code: int, response_data: dict = None):
    """Imprime detalhes da resposta."""
    status_emoji = "[OK]" if 200 <= status_code < 300 else "[WARN]" if 400 <= status_code < 500 else "[ERROR]"
    print(f"  [RESPONSE] {status_emoji} Status: {status_code}")
    if response_data:
        error = response_data.get("error", "")
        if error:
            print(f"             Error: {error}")


def print_success(message: str):
    """Imprime mensagem de sucesso."""
    print(f"  [SUCCESS] {message}")


def print_check(field: str, value: any):
    """Imprime verificação de campo."""
    print(f"  [CHECK] {field}: {value}")


# ============================================================================
# SETUP
# ============================================================================

@pytest.fixture
def client():
    """Fixture que retorna um TestClient para fazer requisições HTTP."""
    return TestClient(app)


# ============================================================================
# TESTES: GET /health
# ============================================================================

def test_health_endpoint(client):
    """
    Testa que endpoint /health retorna 200 OK.
    """
    print_test_header("Health Check Endpoint", "[HEALTH]")
    
    print_request("GET", "/health")
    response = client.get("/health")
    
    print_response(response.status_code, response.json())
    
    assert response.status_code == 200
    
    data = response.json()
    print_check("status", data["status"])
    print_check("service", data["service"])
    
    assert data == {
        "status": "healthy",
        "service": "meeting-extractor"
    }
    
    print_success("Health check passou!")


# ============================================================================
# TESTES: POST /extract - ERROR HANDLING
# ============================================================================

def test_extract_validation_error_422_no_input(client):
    """
    Testa que endpoint retorna 422 quando nenhum formato é fornecido.
    
    Cenário: Body vazio (nem transcript nem raw_meeting)
    Esperado: 422 Unprocessable Entity
    """
    print_test_header("Erro 422 - Body Vazio", "[ERROR-422]")
    
    body = {}
    print_request("POST", "/extract", body)
    response = client.post("/extract", json=body)
    
    print_response(response.status_code, response.json())
    
    # Valida status code
    assert response.status_code == 422
    print_check("Status Code", "422 [OK]")
    
    # Valida estrutura da resposta de erro
    error_data = response.json()
    assert "error" in error_data
    print_check("Campo 'error'", error_data["error"])
    
    assert error_data["error"] == "validation_error"
    assert "message" in error_data
    print_check("Campo 'message'", error_data["message"][:50] + "...")
    
    assert "details" in error_data
    print_check("Campo 'details'", f"{len(error_data['details'])} erro(s)")
    
    assert "request_id" in error_data
    print_check("Campo 'request_id'", error_data["request_id"][:20] + "...")
    
    # Valida que erro menciona o problema
    details_str = str(error_data["details"])
    assert "não ambos nem nenhum" in details_str.lower() or "transcript" in details_str.lower()
    
    print_success("Validação 422 passou!")


def test_extract_validation_error_422_both_formats(client):
    """
    Testa que endpoint retorna 422 quando ambos os formatos são fornecidos.
    
    Cenário: Body com transcript E raw_meeting (exclusividade violada)
    Esperado: 422 Unprocessable Entity
    """
    response = client.post(
        "/extract",
        json={
            "transcript": "Cliente: Olá...",
            "raw_meeting": {
                "meet_id": "MTG001",
                "customer_id": "CUST001",
                "customer_name": "João Silva",
                "banker_id": "BKR001",
                "banker_name": "Pedro Falcão",
                "meet_date": "2025-09-10T14:30:00Z",
                "meet_type": "Primeira Reunião",
                "meet_transcription": "Cliente: Olá..."
            }
        }
    )
    
    # Valida status code
    assert response.status_code == 422
    
    # Valida estrutura da resposta
    error_data = response.json()
    assert error_data["error"] == "validation_error"
    assert "details" in error_data
    
    # Valida mensagem de erro
    details_str = str(error_data["details"])
    assert "não ambos" in details_str.lower() or "exclusive" in details_str.lower()


def test_extract_validation_error_422_invalid_types(client):
    """
    Testa que endpoint retorna 422 quando tipos de campos são inválidos.
    
    Cenário: meeting_id como int ao invés de string
    Esperado: 422 Unprocessable Entity
    """
    response = client.post(
        "/extract",
        json={
            "transcript": "Cliente: Olá...",
            "metadata": {
                "meeting_id": 12345,  # ❌ int ao invés de string
                "customer_id": "CUST001"
            }
        }
    )
    
    # Valida status code
    assert response.status_code == 422
    
    # Valida estrutura da resposta
    error_data = response.json()
    assert error_data["error"] == "validation_error"
    assert "details" in error_data
    
    # Valida que erro menciona tipo incorreto
    details_str = str(error_data["details"])
    assert "string" in details_str.lower() or "type" in details_str.lower()


def test_extract_validation_error_422_invalid_datetime(client):
    """
    Testa que endpoint retorna 422 quando formato de datetime é inválido.
    
    Cenário: meet_date em formato não-ISO
    Esperado: 422 Unprocessable Entity
    """
    response = client.post(
        "/extract",
        json={
            "transcript": "Cliente: Olá...",
            "metadata": {
                "meet_date": "10/09/2025"  # ❌ Formato errado (não ISO 8601)
            }
        }
    )
    
    # Valida status code
    assert response.status_code == 422
    
    # Valida estrutura da resposta
    error_data = response.json()
    assert error_data["error"] == "validation_error"


# ============================================================================
# TESTES: Response Structure (Headers, Request-ID)
# ============================================================================

def test_extract_response_has_request_id_header(client):
    """
    Testa que todas as respostas incluem header X-Request-ID.
    
    Valida middleware add_request_id.
    """
    # Teste com requisição válida
    response = client.get("/health")
    
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_extract_preserves_custom_request_id(client):
    """
    Testa que Request-ID fornecido pelo cliente é preservado.
    """
    custom_id = "my-custom-request-id-123"
    
    response = client.get(
        "/health",
        headers={"X-Request-ID": custom_id}
    )
    
    assert response.headers["X-Request-ID"] == custom_id


def test_extract_generates_request_id_if_not_provided(client):
    """
    Testa que Request-ID é gerado automaticamente se não fornecido.
    """
    response = client.get("/health")
    
    request_id = response.headers["X-Request-ID"]
    
    # Valida que é um UUID válido (formato: 8-4-4-4-12)
    assert len(request_id) == 36
    assert request_id.count("-") == 4


# ============================================================================
# TESTES: Error Response Structure
# ============================================================================

def test_error_response_structure_422(client):
    """
    Testa estrutura completa da resposta de erro 422.
    
    Valida que todos os campos esperados estão presentes.
    """
    response = client.post("/extract", json={})
    
    assert response.status_code == 422
    
    error_data = response.json()
    
    # Campos obrigatórios
    assert "error" in error_data
    assert "message" in error_data
    assert "details" in error_data
    assert "request_id" in error_data
    
    # Tipos corretos
    assert isinstance(error_data["error"], str)
    assert isinstance(error_data["message"], str)
    assert isinstance(error_data["details"], list)
    assert isinstance(error_data["request_id"], str)
    
    # Valores esperados
    assert error_data["error"] == "validation_error"
    assert len(error_data["message"]) > 0
    assert len(error_data["details"]) > 0


def test_error_details_structure(client):
    """
    Testa que campo 'details' em erro 422 tem estrutura correta.
    
    Cada item em 'details' deve ter: loc, msg, type
    """
    response = client.post(
        "/extract",
        json={"transcript": 123}  # Tipo errado
    )
    
    assert response.status_code == 422
    
    error_data = response.json()
    details = error_data["details"]
    
    # Valida que há pelo menos um erro
    assert len(details) > 0
    
    # Valida estrutura de cada erro
    for error_item in details:
        assert "loc" in error_item
        assert "msg" in error_item
        assert "type" in error_item
        
        # Tipos corretos
        assert isinstance(error_item["loc"], list)
        assert isinstance(error_item["msg"], str)
        assert isinstance(error_item["type"], str)


# ============================================================================
# TESTES: Content-Type
# ============================================================================

def test_extract_requires_json_content_type(client):
    """
    Testa que endpoint requer Content-Type: application/json.
    """
    # Enviando texto plano ao invés de JSON
    response = client.post(
        "/extract",
        content="plain text body",  # Use 'content' para raw bytes/text
        headers={"Content-Type": "text/plain"}
    )
    
    # FastAPI rejeita automaticamente
    assert response.status_code in [422, 400]


def test_extract_accepts_json_content_type(client):
    """
    Testa que endpoint aceita Content-Type: application/json.
    """
    response = client.post(
        "/extract",
        json={},  # TestClient automaticamente adiciona Content-Type: application/json
    )
    
    # Deve processar (mesmo que falhe validação)
    assert response.status_code == 422  # Validação falha, mas aceita JSON


# ============================================================================
# TESTES: Endpoint Documentation
# ============================================================================

def test_openapi_docs_available(client):
    """
    Testa que documentação Swagger está disponível.
    """
    response = client.get("/docs")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc_available(client):
    """
    Testa que documentação ReDoc está disponível.
    """
    response = client.get("/redoc")
    
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_openapi_json_available(client):
    """
    Testa que schema OpenAPI (JSON) está disponível.
    """
    response = client.get("/openapi.json")
    
    assert response.status_code == 200
    
    openapi_schema = response.json()
    
    # Valida estrutura básica do OpenAPI
    assert "openapi" in openapi_schema
    assert "info" in openapi_schema
    assert "paths" in openapi_schema
    
    # Valida que nossos endpoints estão documentados
    assert "/health" in openapi_schema["paths"]
    assert "/extract" in openapi_schema["paths"]

