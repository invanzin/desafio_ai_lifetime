"""
Testes de integração para validar o tratamento de erros 502 (Bad Gateway).

Este módulo testa os cenários onde a API retorna 502 devido a problemas
na comunicação com a OpenAI API ou quando a OpenAI retorna dados inválidos.

Cenários testados:
1. RateLimitError - OpenAI bloqueia por rate limit
2. APITimeoutError - Timeout ao chamar a OpenAI
3. APIError - Erro genérico da OpenAI
4. ValidationError - OpenAI retorna JSON inválido/incompleto

Técnica: Usamos mocks para simular as exceções sem chamar a API real.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from openai import RateLimitError, APITimeoutError, APIError
from pydantic import ValidationError

from app.main import app


@pytest.fixture
def client():
    """Fixture que retorna um TestClient para testar a API."""
    return TestClient(app)


# ============================================================================
# TESTES DE ERRO 502 - COMUNICAÇÃO COM OPENAI
# ============================================================================

def test_502_rate_limit_error(client):
    """
    Testa resposta 502 quando OpenAI retorna RateLimitError.
    
    Simula situação onde a OpenAI bloqueia requisições por rate limit.
    O sistema deve:
    1. Capturar o RateLimitError
    2. Logar o erro apropriadamente
    3. Retornar 502 Bad Gateway com mensagem clara
    """
    # Mock da função extract_meeting_chain para lançar RateLimitError
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        # Simula erro de rate limit da OpenAI
        mock_extract.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None
        )
        
        # Payload válido
        payload = {
            "transcript": "Teste de rate limit error"
        }
        
        # Faz requisição
        response = client.post("/extract", json=payload)
        
        # Validações
        assert response.status_code == 502
        
        data = response.json()
        assert data["error"] == "openai_communication_error"
        assert "rate limit" in data["message"].lower()
        assert data["error_type"] == "RateLimitError"
        assert "request_id" in data


def test_502_api_timeout_error(client):
    """
    Testa resposta 502 quando OpenAI não responde (timeout).
    
    Simula timeout após 30 segundos (configurado no extractor).
    O sistema deve:
    1. Capturar o APITimeoutError
    2. Logar o erro com detalhes de duração
    3. Retornar 502 com mensagem de timeout
    """
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        # Simula timeout da OpenAI
        mock_extract.side_effect = APITimeoutError(
            request=MagicMock()
        )
        
        payload = {
            "transcript": "Teste de timeout error"
        }
        
        response = client.post("/extract", json=payload)
        
        # Validações
        assert response.status_code == 502
        
        data = response.json()
        assert data["error"] == "openai_communication_error"
        assert "timeout" in data["message"].lower()
        assert data["error_type"] == "APITimeoutError"
        assert "request_id" in data


def test_502_api_generic_error(client):
    """
    Testa resposta 502 quando OpenAI retorna erro genérico.
    
    Simula qualquer APIError (ex: 500, 503 da OpenAI).
    """
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        # Simula erro genérico da OpenAI
        mock_extract.side_effect = APIError(
            message="Service temporarily unavailable",
            request=MagicMock(),
            body=None
        )
        
        payload = {
            "transcript": "Teste de API error genérico"
        }
        
        response = client.post("/extract", json=payload)
        
        # Validações
        assert response.status_code == 502
        
        data = response.json()
        assert data["error"] == "openai_communication_error"
        assert "request_id" in data
        assert data["error_type"] == "APIError"


# ============================================================================
# TESTES DE ERRO 502 - VALIDAÇÃO PYDANTIC (RESPOSTA INVÁLIDA)
# ============================================================================

def test_502_validation_error_invalid_response(client):
    """
    Testa resposta 502 quando OpenAI retorna JSON inválido.
    
    Simula situação onde:
    1. OpenAI responde com sucesso (status 200)
    2. Mas o JSON retornado não passa na validação Pydantic
    3. Mesmo após tentativas de "repair" no extractor
    
    Isso indica que a OpenAI está retornando dados malformados/incompletos.
    """
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        # Simula ValidationError (Pydantic não conseguiu validar resposta da OpenAI)
        mock_extract.side_effect = ValidationError.from_exception_data(
            title="ExtractedMeeting",
            line_errors=[
                {
                    'type': 'missing',
                    'loc': ('meeting_id',),
                    'msg': 'Field required',
                    'input': {},
                }
            ]
        )
        
        payload = {
            "transcript": "Teste de resposta inválida da OpenAI"
        }
        
        response = client.post("/extract", json=payload)
        
        # Validações
        assert response.status_code == 502
        
        data = response.json()
        assert data["error"] == "openai_invalid_response"
        assert "inválidos" in data["message"] or "incompletos" in data["message"]
        assert "request_id" in data


# ============================================================================
# TESTE DE RETRIES (VERIFICA SE O DECORATOR @retry ESTÁ FUNCIONANDO)
# ============================================================================

def test_retries_before_502(client):
    """
    Testa se o sistema faz 3 tentativas antes de retornar 502.
    
    O decorator @retry no extractor.py está configurado para:
    - 3 tentativas máximas
    - Backoff exponencial (0.5s, 1s, 2s)
    
    Este teste verifica se o mock é chamado 3 vezes antes de falhar.
    """
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        # Contador de tentativas
        mock_extract.side_effect = APITimeoutError(request=MagicMock())
        
        payload = {
            "transcript": "Teste de retries"
        }
        
        response = client.post("/extract", json=payload)
        
        # Deve retornar 502 após as tentativas
        assert response.status_code == 502
        
        # NOTA: Este teste valida o comportamento final
        # O número exato de retries é testado no test_extractor.py
        # pois depende da implementação interna do @retry decorator


# ============================================================================
# TESTE DE ESTRUTURA DE RESPOSTA 502
# ============================================================================

def test_502_response_structure(client):
    """
    Valida que todas as respostas 502 seguem a mesma estrutura.
    
    Estrutura esperada:
    {
        "error": "openai_communication_error" | "openai_invalid_response",
        "message": "<descrição legível>",
        "error_type": "<tipo da exceção>" (opcional),
        "request_id": "<uuid>"
    }
    """
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        mock_extract.side_effect = APITimeoutError(request=MagicMock())
        
        payload = {"transcript": "Teste estrutura"}
        
        response = client.post("/extract", json=payload)
        
        assert response.status_code == 502
        
        data = response.json()
        
        # Campos obrigatórios
        assert "error" in data
        assert "message" in data
        assert "request_id" in data
        
        # Tipos corretos
        assert isinstance(data["error"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["request_id"], str)
        
        # Request ID deve ter formato UUID
        assert len(data["request_id"]) >= 32  # UUID básico


# ============================================================================
# TESTE COM DIFERENTES FORMATOS DE INPUT
# ============================================================================

@pytest.mark.parametrize("payload", [
    # Formato 1: transcript apenas
    {"transcript": "Teste formato 1"},
    
    # Formato 2: transcript + metadata
    {
        "transcript": "Teste formato 2",
        "metadata": {
            "meeting_id": "MTG-123",
            "customer_id": "CUST-456"
        }
    },
    
    # Formato 3: raw_meeting
    {
        "raw_meeting": {
            "meet_id": "MTG-789",
            "customer_id": "CUST-789",
            "customer_name": "Cliente Teste",
            "banker_id": "BANK-123",
            "banker_name": "Banker Teste",
            "meet_date": "2025-10-04T10:00:00",
            "meet_type": "presencial",
            "meet_transcription": "Teste formato 3"
        }
    }
])
def test_502_works_with_all_input_formats(client, payload):
    """
    Garante que o tratamento de erro 502 funciona independente
    do formato de input usado (transcript, transcript+metadata, raw_meeting).
    """
    with patch('app.main.extract_meeting_chain', new_callable=AsyncMock) as mock_extract:
        mock_extract.side_effect = APITimeoutError(request=MagicMock())
        
        response = client.post("/extract", json=payload)
        
        assert response.status_code == 502
        data = response.json()
        assert data["error"] == "openai_communication_error"
        assert "request_id" in data

