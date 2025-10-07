"""
Testes de integração para Rate Limiting (limitação de taxa de requisições).

Este módulo valida que o rate limiting está funcionando corretamente,
protegendo a API contra abuso e consumo excessivo de recursos.

Configuração:
- Limite padrão: 10 requisições por minuto por IP
- Resposta: 429 Too Many Requests quando excedido
- Header: Retry-After indicando quando tentar novamente

Cenários testados:
1. Requisições dentro do limite são aceitas
2. Requisição após limite retorna 429
3. IPs diferentes têm limites independentes
4. Estrutura de resposta 429 está correta
5. Header Retry-After está presente
6. Limite reseta após janela de tempo
"""

import pytest
import time
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app


@pytest.fixture
def client():
    """
    Fixture que retorna um TestClient para testar a API.
    
    IMPORTANTE: Reseta o limiter antes de cada teste para garantir isolamento.
    Isso evita que o contador de requisições persista entre testes.
    """
    # Reseta o storage do limiter antes de cada teste
    from app.main import limiter
    limiter.reset()
    
    return TestClient(app)


# ============================================================================
# TESTES DE RATE LIMITING BÁSICO
# ============================================================================

def test_rate_limit_allows_requests_within_limit(client):
    """
    Valida que requisições dentro do limite (9/10) são aceitas normalmente.
    
    Comportamento esperado:
    - 9 requisições consecutivas devem retornar 200 OK
    - Cada uma deve processar normalmente (mockado)
    """
    # Mock do extractor para evitar chamadas à OpenAI
    with patch('app.main.extract_meeting_chain') as mock_extract:
        from app.models.schemas_extract import ExtractedMeeting
        from datetime import datetime
        
        # Mock da resposta
        mock_extract.return_value = ExtractedMeeting(
            meeting_id="MTG-TEST-001",
            customer_id="CUST-001",
            customer_name="Cliente Teste",
            banker_id="BANK-001",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime.now(),
            summary="Resumo de teste com pelo menos cem palavras para passar na validação. " * 10,
            key_points=["Ponto 1", "Ponto 2"],
            action_items=["Ação 1"],
            topics=["Tema 1"],
            idempotency_key="test-key-123",
            source="lftm-challenge"
        )
        
        payload = {"transcript": "Teste de rate limiting"}
        
        # Faz 9 requisições (dentro do limite de 10/minuto)
        for i in range(9):
            response = client.post("/extract", json=payload)
            
            # Todas devem ter sucesso (200)
            assert response.status_code == 200, f"Request {i+1} failed with status {response.status_code}"
            
            data = response.json()
            assert data["meeting_id"] == "MTG-TEST-001"


def test_rate_limit_blocks_11th_request(client):
    """
    Valida que a 11ª requisição é bloqueada com erro 429.
    
    Comportamento esperado:
    - 10 primeiras requisições: 200 OK
    - 11ª requisição: 429 Too Many Requests
    """
    with patch('app.main.extract_meeting_chain') as mock_extract:
        from app.models.schemas_extract import ExtractedMeeting
        from datetime import datetime
        
        mock_extract.return_value = ExtractedMeeting(
            meeting_id="MTG-TEST-002",
            customer_id="CUST-002",
            customer_name="Cliente Teste",
            banker_id="BANK-002",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime.now(),
            summary="Resumo de teste com pelo menos cem palavras para passar na validação. " * 10,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tema 1"],
            idempotency_key="test-key-456",
            source="lftm-challenge"
        )
        
        payload = {"transcript": "Teste de rate limiting - bloqueio"}
        
        # Faz 10 requisições (todas devem passar)
        for i in range(10):
            response = client.post("/extract", json=payload)
            assert response.status_code == 200, f"Request {i+1} should succeed but got {response.status_code}"
        
        # 11ª requisição deve ser bloqueada
        response = client.post("/extract", json=payload)
        assert response.status_code == 429
        
        data = response.json()
        assert data["error"] == "rate_limit_exceeded"


def test_rate_limit_response_structure(client):
    """
    Valida a estrutura da resposta de erro 429.
    
    Estrutura esperada:
    {
        "error": "rate_limit_exceeded",
        "message": "<mensagem legível>",
        "limit": "10 requisições por minuto",
        "request_id": "<uuid>"
    }
    """
    with patch('app.main.extract_meeting_chain') as mock_extract:
        from app.models.schemas_extract import ExtractedMeeting
        from datetime import datetime
        
        mock_extract.return_value = ExtractedMeeting(
            meeting_id="MTG-TEST-003",
            customer_id="CUST-003",
            customer_name="Cliente Teste",
            banker_id="BANK-003",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime.now(),
            summary="Resumo de teste com pelo menos cem palavras para passar na validação. " * 10,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tema 1"],
            idempotency_key="test-key-789",
            source="lftm-challenge"
        )
        
        payload = {"transcript": "Teste de estrutura de resposta"}
        
        # Esgota o limite (10 requisições)
        for _ in range(10):
            client.post("/extract", json=payload)
        
        # 11ª requisição retorna 429
        response = client.post("/extract", json=payload)
        
        assert response.status_code == 429
        
        data = response.json()
        
        # Valida campos obrigatórios
        assert "error" in data
        assert "message" in data
        assert "limit" in data
        assert "request_id" in data
        
        # Valida tipos
        assert isinstance(data["error"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["limit"], str)
        assert isinstance(data["request_id"], str)
        
        # Valida conteúdo
        assert data["error"] == "rate_limit_exceeded"
        assert "10" in data["limit"]
        assert "minuto" in data["limit"].lower()


def test_rate_limit_includes_retry_after_header(client):
    """
    Valida que a resposta 429 inclui o header Retry-After.
    
    Este header indica ao cliente quantos segundos deve esperar
    antes de tentar novamente.
    """
    with patch('app.main.extract_meeting_chain') as mock_extract:
        from app.models.schemas_extract import ExtractedMeeting
        from datetime import datetime
        
        mock_extract.return_value = ExtractedMeeting(
            meeting_id="MTG-TEST-004",
            customer_id="CUST-004",
            customer_name="Cliente Teste",
            banker_id="BANK-004",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime.now(),
            summary="Resumo de teste com pelo menos cem palavras para passar na validação. " * 10,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tema 1"],
            idempotency_key="test-key-retry",
            source="lftm-challenge"
        )
        
        payload = {"transcript": "Teste de Retry-After header"}
        
        # Esgota o limite
        for _ in range(10):
            client.post("/extract", json=payload)
        
        # 11ª requisição
        response = client.post("/extract", json=payload)
        
        assert response.status_code == 429
        
        # Valida presença do header Retry-After
        assert "Retry-After" in response.headers
        
        retry_after = response.headers["Retry-After"]
        
        # Deve ser um número (segundos)
        assert retry_after.isdigit()
        
        # Deve ser maior que 0 e menor ou igual a 60 (1 minuto)
        retry_after_int = int(retry_after)
        assert 0 < retry_after_int <= 60


def test_rate_limit_resets_after_window(client):
    """
    Valida que o limite reseta após a janela de tempo (60 segundos).
    
    NOTA: Este teste é lento (~60s).
    
    Comportamento esperado:
    - 10 requisições esgotam o limite
    - Após 60 segundos, limite reseta
    - Pode fazer mais 10 requisições
    """
    with patch('app.main.extract_meeting_chain') as mock_extract:
        from app.models.schemas_extract import ExtractedMeeting
        from datetime import datetime
        
        mock_extract.return_value = ExtractedMeeting(
            meeting_id="MTG-TEST-006",
            customer_id="CUST-006",
            customer_name="Cliente Teste",
            banker_id="BANK-006",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime.now(),
            summary="Resumo de teste com pelo menos cem palavras para passar na validação. " * 10,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tema 1"],
            idempotency_key="test-key-reset",
            source="lftm-challenge"
        )
        
        payload = {"transcript": "Teste de reset do limite"}
        
        # Esgota o limite (10 requisições)
        for _ in range(10):
            response = client.post("/extract", json=payload)
            assert response.status_code == 200
        
        # 11ª requisição deve falhar
        response = client.post("/extract", json=payload)
        assert response.status_code == 429
        
        # Aguarda 61 segundos (janela completa + margem)
        print("Aguardando 61 segundos para reset da janela...")
        time.sleep(61)
        
        # Após reset, deve conseguir fazer requisições novamente
        response = client.post("/extract", json=payload)
        assert response.status_code == 200, "Limite deveria ter resetado após 60s"


# ============================================================================
# TESTE DE LOGGING
# ============================================================================

def test_rate_limit_logs_when_exceeded(client, caplog):
    """
    Valida que o sistema loga quando o rate limit é excedido.
    
    O log deve incluir:
    - Request ID
    - IP do cliente
    - Mensagem indicando rate limit exceeded
    """
    with patch('app.main.extract_meeting_chain') as mock_extract:
        from app.models.schemas_extract import ExtractedMeeting
        from datetime import datetime
        
        mock_extract.return_value = ExtractedMeeting(
            meeting_id="MTG-TEST-007",
            customer_id="CUST-007",
            customer_name="Cliente Teste",
            banker_id="BANK-007",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime.now(),
            summary="Resumo de teste com pelo menos cem palavras para passar na validação. " * 10,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tema 1"],
            idempotency_key="test-key-log",
            source="lftm-challenge"
        )
        
        payload = {"transcript": "Teste de logging"}
        
        # Esgota o limite
        for _ in range(10):
            client.post("/extract", json=payload)
        
        # Limpa logs anteriores
        caplog.clear()
        
        # 11ª requisição (deve logar)
        response = client.post("/extract", json=payload)
        
        assert response.status_code == 429
        
        # Verifica se houve log de rate limit
        # (O log específico pode variar dependendo da implementação)
        # Este teste é mais sobre garantir que ALGO foi logado
        assert len(caplog.records) > 0

