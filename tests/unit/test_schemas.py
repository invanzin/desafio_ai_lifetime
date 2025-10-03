"""
Testes unitários para schemas.py (Pydantic models).

Testa validações, conversões e cálculo de idempotency key.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.schemas import (
    Metadata,
    RawMeeting,
    ExtractRequest,
    NormalizedInput,
    ExtractedMeeting,
)


# ============================================================================
# TESTES: Metadata
# ============================================================================

def test_metadata_all_fields_optional():
    """Testa que todos os campos de Metadata são opcionais."""
    metadata = Metadata()
    
    assert metadata.meeting_id is None
    assert metadata.customer_id is None
    assert metadata.customer_name is None
    assert metadata.banker_id is None
    assert metadata.banker_name is None
    assert metadata.meet_type is None
    assert metadata.meet_date is None


def test_metadata_with_all_fields():
    """Testa criação de Metadata com todos os campos."""
    metadata = Metadata(
        meeting_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_type="Primeira Reunião",
        meet_date=datetime(2025, 9, 10, 14, 30)
    )
    
    assert metadata.meeting_id == "MTG001"
    assert metadata.customer_id == "CUST001"
    assert metadata.meet_date == datetime(2025, 9, 10, 14, 30)


# ============================================================================
# TESTES: ExtractRequest (Validação de Exclusividade)
# ============================================================================

def test_extract_request_only_transcript():
    """Testa ExtractRequest com apenas transcript (válido)."""
    request = ExtractRequest(transcript="Cliente: Olá...")
    
    assert request.transcript == "Cliente: Olá..."
    assert request.metadata is None
    assert request.raw_meeting is None


def test_extract_request_transcript_and_metadata():
    """Testa ExtractRequest com transcript + metadata (válido)."""
    request = ExtractRequest(
        transcript="Cliente: Olá...",
        metadata=Metadata(meeting_id="MTG001")
    )
    
    assert request.transcript is not None
    assert request.metadata is not None
    assert request.raw_meeting is None


def test_extract_request_only_raw_meeting():
    """Testa ExtractRequest com apenas raw_meeting (válido)."""
    raw = RawMeeting(
        meet_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_date=datetime(2025, 9, 10, 14, 30),
        meet_type="Primeira Reunião",
        meet_transcription="Cliente: Olá..."
    )
    
    request = ExtractRequest(raw_meeting=raw)
    
    assert request.transcript is None
    assert request.metadata is None
    assert request.raw_meeting is not None


def test_extract_request_both_formats_fails():
    """Testa que fornecer ambos os formatos lança erro."""
    raw = RawMeeting(
        meet_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_date=datetime(2025, 9, 10, 14, 30),
        meet_type="Primeira Reunião",
        meet_transcription="Cliente: Olá..."
    )
    
    with pytest.raises(ValidationError) as exc_info:
        ExtractRequest(
            transcript="Cliente: Olá...",
            raw_meeting=raw
        )
    
    assert "não ambos nem nenhum" in str(exc_info.value)


def test_extract_request_neither_format_fails():
    """Testa que não fornecer nenhum formato lança erro."""
    with pytest.raises(ValidationError) as exc_info:
        ExtractRequest()
    
    assert "não ambos nem nenhum" in str(exc_info.value)


# ============================================================================
# TESTES: NormalizedInput (Idempotency Key)
# ============================================================================

def test_compute_idempotency_key_with_all_fields():
    """Testa cálculo de idempotency key com todos os campos."""
    normalized = NormalizedInput(
        transcript="test",
        meeting_id="MTG001",
        customer_id="CUST001",
        meet_date=datetime(2025, 9, 10, 14, 30)
    )
    
    key = normalized.compute_idempotency_key()
    
    # Deve ser SHA-256 (64 caracteres hexadecimais)
    assert key is not None
    assert len(key) == 64
    assert all(c in '0123456789abcdef' for c in key)


def test_compute_idempotency_key_is_deterministic():
    """Testa que a chave de idempotência é determinística."""
    normalized1 = NormalizedInput(
        transcript="test",
        meeting_id="MTG001",
        customer_id="CUST001",
        meet_date=datetime(2025, 9, 10, 14, 30)
    )
    
    normalized2 = NormalizedInput(
        transcript="different",  # Transcript diferente não afeta!
        meeting_id="MTG001",
        customer_id="CUST001",
        meet_date=datetime(2025, 9, 10, 14, 30)
    )
    
    key1 = normalized1.compute_idempotency_key()
    key2 = normalized2.compute_idempotency_key()
    
    # Mesmos metadados → mesma chave (transcript não importa!)
    assert key1 == key2


def test_compute_idempotency_key_without_meeting_id():
    """Testa que retorna None se meeting_id ausente."""
    normalized = NormalizedInput(
        transcript="test",
        customer_id="CUST001",
        meet_date=datetime(2025, 9, 10, 14, 30)
    )
    
    key = normalized.compute_idempotency_key()
    
    assert key is None


def test_compute_idempotency_key_without_customer_id():
    """Testa que retorna None se customer_id ausente."""
    normalized = NormalizedInput(
        transcript="test",
        meeting_id="MTG001",
        meet_date=datetime(2025, 9, 10, 14, 30)
    )
    
    key = normalized.compute_idempotency_key()
    
    assert key is None


def test_compute_idempotency_key_without_meet_date():
    """Testa que retorna None se meet_date ausente."""
    normalized = NormalizedInput(
        transcript="test",
        meeting_id="MTG001",
        customer_id="CUST001"
    )
    
    key = normalized.compute_idempotency_key()
    
    assert key is None


# ============================================================================
# TESTES: ExtractedMeeting (Validação de Summary)
# ============================================================================

def test_extracted_meeting_summary_valid_length():
    """Testa que summary com 100-200 palavras é aceito."""
    summary = " ".join(["palavra"] * 150)  # 150 palavras
    
    meeting = ExtractedMeeting(
        meeting_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_type="Primeira Reunião",
        meet_date=datetime(2025, 9, 10, 14, 30),
        summary=summary,
        key_points=["Ponto 1"],
        action_items=["Ação 1"],
        topics=["Tópico 1"],
        idempotency_key="abc123"
    )
    
    assert len(meeting.summary.split()) == 150


def test_extracted_meeting_summary_too_short():
    """Testa que summary com menos de 100 palavras é rejeitado."""
    summary = " ".join(["palavra"] * 50)  # 50 palavras
    
    with pytest.raises(ValidationError) as exc_info:
        ExtractedMeeting(
            meeting_id="MTG001",
            customer_id="CUST001",
            customer_name="João Silva",
            banker_id="BKR001",
            banker_name="Pedro Falcão",
            meet_type="Primeira Reunião",
            meet_date=datetime(2025, 9, 10, 14, 30),
            summary=summary,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tópico 1"],
            idempotency_key="abc123"
        )
    
    assert "100-200 palavras" in str(exc_info.value)


def test_extracted_meeting_summary_too_long():
    """Testa que summary com mais de 200 palavras é rejeitado."""
    summary = " ".join(["palavra"] * 250)  # 250 palavras
    
    with pytest.raises(ValidationError) as exc_info:
        ExtractedMeeting(
            meeting_id="MTG001",
            customer_id="CUST001",
            customer_name="João Silva",
            banker_id="BKR001",
            banker_name="Pedro Falcão",
            meet_type="Primeira Reunião",
            meet_date=datetime(2025, 9, 10, 14, 30),
            summary=summary,
            key_points=["Ponto 1"],
            action_items=["Ação 1"],
            topics=["Tópico 1"],
            idempotency_key="abc123"
        )
    
    assert "100-200 palavras" in str(exc_info.value)


def test_extracted_meeting_source_field():
    """Testa que source tem valor padrão correto."""
    meeting = ExtractedMeeting(
        meeting_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_type="Primeira Reunião",
        meet_date=datetime(2025, 9, 10, 14, 30),
        summary=" ".join(["palavra"] * 150),
        key_points=["Ponto 1"],
        action_items=["Ação 1"],
        topics=["Tópico 1"],
        idempotency_key="abc123"
    )
    
    assert meeting.source == "lftm-challenge"


# ============================================================================
# TESTES: to_normalized() (Conversão)
# ============================================================================

def test_to_normalized_from_transcript_metadata():
    """Testa conversão de transcript+metadata para NormalizedInput."""
    request = ExtractRequest(
        transcript="Cliente: Olá...",
        metadata=Metadata(
            meeting_id="MTG001",
            customer_id="CUST001",
            meet_date=datetime(2025, 9, 10, 14, 30)
        )
    )
    
    normalized = request.to_normalized()
    
    assert normalized.transcript == "Cliente: Olá..."
    assert normalized.meeting_id == "MTG001"
    assert normalized.customer_id == "CUST001"
    assert normalized.meet_date == datetime(2025, 9, 10, 14, 30)


def test_to_normalized_from_raw_meeting():
    """Testa conversão de raw_meeting para NormalizedInput."""
    raw = RawMeeting(
        meet_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_date=datetime(2025, 9, 10, 14, 30),
        meet_type="Primeira Reunião",
        meet_transcription="Cliente: Olá..."
    )
    
    request = ExtractRequest(raw_meeting=raw)
    normalized = request.to_normalized()
    
    assert normalized.transcript == "Cliente: Olá..."
    assert normalized.meeting_id == "MTG001"
    assert normalized.customer_id == "CUST001"
    assert normalized.customer_name == "João Silva"


