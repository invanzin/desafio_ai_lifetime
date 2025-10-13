"""
Testes de segurança - Proteção de PII e logging seguro.

Este módulo testa funções auxiliares que garantem segurança e privacidade:
- sanitize_transcript_for_log(): Evita logar transcrições completas (PII)
- compute_idempotency_key(): Garante determinismo e unicidade

Importância:
- Proteção de dados sensíveis (LGPD/GDPR compliance)
- Logs seguros sem vazamento de informações
- Idempotência garantida para evitar duplicações
"""

import pytest
from datetime import datetime
from app.models.schemas_common import NormalizedInput
from utils.common import sanitize_transcript_for_log


# ============================================================================
# TESTES: sanitize_transcript_for_log (Segurança de Logs)
# ============================================================================

def test_sanitize_short_transcript():
    """
    Testa que transcrições curtas NÃO são truncadas.
    
    Segurança: Se transcript < 300 chars, pode ser logado completo.
    """
    transcript = "Cliente: Olá! Banker: Bom dia!"  # 30 chars
    
    result = sanitize_transcript_for_log(transcript, max_chars=300)
    
    # Não deve truncar
    assert result == transcript
    assert "..." not in result


def test_sanitize_long_transcript():
    """
    Testa que transcrições longas SÃO truncadas para proteger logs.
    
    Segurança: Logs gigantes podem expor PII completa, causar problemas
    de performance e violar compliance (LGPD/GDPR).
    """
    # Transcrição de 500 chars
    transcript = "palavra " * 70  # ~500 chars
    original_len = len(transcript)
    
    result = sanitize_transcript_for_log(transcript, max_chars=300)
    
    # Deve truncar em 300 chars + indicador de truncamento
    assert len(result) > 300  # Tem o texto truncado + indicador
    assert "truncado" in result
    assert f"total: {original_len} chars" in result
    
    # Deve conter apenas o início da transcrição
    assert result.startswith("palavra")


def test_sanitize_preserves_beginning():
    """
    Testa que sanitize_transcript_for_log() preserva o INÍCIO da transcrição.
    
    Segurança: O início da transcrição geralmente contém contexto importante
    (identificação, propósito da reunião) que é útil para debugging.
    """
    transcript = "INÍCIO IMPORTANTE: Cliente João Silva discute investimentos. " + ("x" * 500)
    
    result = sanitize_transcript_for_log(transcript, max_chars=100)
    
    # Deve preservar o início
    assert "INÍCIO IMPORTANTE" in result
    assert "João Silva" in result
    assert "truncado" in result


# ============================================================================
# TESTES: compute_idempotency_key (Idempotência)
# ============================================================================

def test_idempotency_key_is_sha256():
    """
    Testa que idempotency_key é um hash SHA-256 válido.
    
    Regra do briefing: "Geração recomendada: sha256(meeting_id + meet_date + customer_id)"
    
    SHA-256 hash deve:
    - Ter exatamente 64 caracteres
    - Conter apenas caracteres hexadecimais (0-9, a-f)
    """
    normalized = NormalizedInput(
        transcript="Teste",
        meeting_id="MTG001",
        customer_id="CUST001",
        meet_date=datetime(2025, 10, 13, 14, 30, 0)
    )
    
    key = normalized.compute_idempotency_key()
    
    # Deve ser SHA-256 (64 chars hexadecimais)
    assert key is not None
    assert len(key) == 64
    assert all(c in '0123456789abcdef' for c in key)


def test_idempotency_key_deterministic():
    """
    Testa que a mesma entrada sempre gera a mesma chave (determinismo).
    
    Importância: Idempotência só funciona se a chave for determinística.
    Mesma reunião processada 2x deve retornar o mesmo resultado.
    """
    # Primeira chamada
    normalized1 = NormalizedInput(
        transcript="Cliente: Olá",
        meeting_id="MTG-DETERM-001",
        customer_id="CUST-DETERM-001",
        meet_date=datetime(2025, 10, 13, 10, 0, 0)
    )
    key1 = normalized1.compute_idempotency_key()
    
    # Segunda chamada com MESMOS dados
    normalized2 = NormalizedInput(
        transcript="Cliente: Olá",  # Mesmo transcript
        meeting_id="MTG-DETERM-001",  # Mesmo meeting_id
        customer_id="CUST-DETERM-001",  # Mesmo customer_id
        meet_date=datetime(2025, 10, 13, 10, 0, 0)  # Mesma data
    )
    key2 = normalized2.compute_idempotency_key()
    
    # Chaves devem ser IDÊNTICAS
    assert key1 == key2
    assert key1 is not None


def test_idempotency_key_unique():
    """
    Testa que mudanças em qualquer campo geram chaves DIFERENTES.
    
    Importância: Garante que reuniões diferentes tenham chaves diferentes,
    evitando colisões e processamento incorreto.
    """
    base_data = {
        "transcript": "Cliente: Olá",
        "meeting_id": "MTG-UNQ-001",
        "customer_id": "CUST-UNQ-001",
        "meet_date": datetime(2025, 10, 13, 10, 0, 0)
    }
    
    # Chave base
    normalized_base = NormalizedInput(**base_data)
    key_base = normalized_base.compute_idempotency_key()
    
    # Muda meeting_id → chave diferente
    data_diff_meeting = {**base_data, "meeting_id": "MTG-UNQ-002"}
    normalized_diff_meeting = NormalizedInput(**data_diff_meeting)
    key_diff_meeting = normalized_diff_meeting.compute_idempotency_key()
    assert key_diff_meeting != key_base
    
    # Muda customer_id → chave diferente
    data_diff_customer = {**base_data, "customer_id": "CUST-UNQ-002"}
    normalized_diff_customer = NormalizedInput(**data_diff_customer)
    key_diff_customer = normalized_diff_customer.compute_idempotency_key()
    assert key_diff_customer != key_base
    
    # Muda meet_date → chave diferente
    data_diff_date = {**base_data, "meet_date": datetime(2025, 10, 14, 10, 0, 0)}
    normalized_diff_date = NormalizedInput(**data_diff_date)
    key_diff_date = normalized_diff_date.compute_idempotency_key()
    assert key_diff_date != key_base
    
    # Todas as chaves devem ser únicas
    all_keys = {key_base, key_diff_meeting, key_diff_customer, key_diff_date}
    assert len(all_keys) == 4, "Todas as chaves devem ser únicas"

