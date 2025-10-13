"""
Testes unitários para o analyzer.py (análise de sentimento).

Este módulo testa a validação Pydantic do AnalyzedMeeting, garantindo que:
- sentiment_label e sentiment_score sejam consistentes
- summary tenha entre 100-200 palavras
- Campos obrigatórios estejam presentes

Conforme exigido no briefing do Desafio 2:
- "Testes unitários: validar formatação do output e consistência sentiment_label ↔ sentiment_score"

Requisitos do briefing:
- sentiment_label: "positive" | "neutral" | "negative"
- sentiment_score: 0.0 a 1.0
- Consistência:
  - "positive" requer score >= 0.6
  - "neutral" requer 0.4 <= score < 0.6
  - "negative" requer score < 0.4
- summary: 100-200 palavras
"""

import pytest
from datetime import datetime
from app.models.schemas_analyze import AnalyzedMeeting


# ============================================================================
# TESTES DE CONSISTÊNCIA SENTIMENT_LABEL ↔ SENTIMENT_SCORE
# ============================================================================

def test_sentiment_positive_valid():
    """
    Testa que sentiment_label='positive' com score >= 0.6 é válido.
    
    Regra do briefing: "positive" requer score >= 0.6
    """
    meeting = AnalyzedMeeting(
        meeting_id="MTG-POS-001",
        customer_id="CUST-001",
        customer_name="João Feliz",
        banker_id="BNK-001",
        banker_name="Maria Santos",
        meet_type="presencial",
        meet_date=datetime(2025, 10, 13, 10, 0, 0),
        sentiment_label="positive",
        sentiment_score=0.85,  # >= 0.6 ✅
        summary=" ".join(["palavra"] * 150),  # 150 palavras
        key_points=["Cliente satisfeito", "Aumento de investimento"],
        action_items=["Enviar proposta"],
        risks=[]
    )
    
    assert meeting.sentiment_label == "positive"
    assert meeting.sentiment_score >= 0.6
    assert meeting.sentiment_score == 0.85


def test_sentiment_positive_invalid_low_score():
    """
    Testa que sentiment_label='positive' com score < 0.6 falha na validação.
    
    Regra do briefing: "positive" requer score >= 0.6
    """
    with pytest.raises(ValueError, match="sentiment_label 'positive' requer score >= 0.6"):
        AnalyzedMeeting(
            meeting_id="MTG-POS-002",
            customer_id="CUST-002",
            customer_name="Pedro Costa",
            banker_id="BNK-001",
            banker_name="Maria Santos",
            meet_type="online",
            meet_date=datetime(2025, 10, 13, 11, 0, 0),
            sentiment_label="positive",
            sentiment_score=0.3,  # < 0.6 ❌
            summary=" ".join(["palavra"] * 150),
            key_points=["ponto"],
            action_items=["ação"]
        )


def test_sentiment_neutral_valid():
    """
    Testa que sentiment_label='neutral' com 0.4 <= score < 0.6 é válido.
    
    Regra do briefing: "neutral" requer 0.4 <= score < 0.6
    """
    meeting = AnalyzedMeeting(
        meeting_id="MTG-NEU-001",
        customer_id="CUST-003",
        customer_name="Ana Silva",
        banker_id="BNK-002",
        banker_name="Carlos Lima",
        meet_type="híbrido",
        meet_date=datetime(2025, 10, 13, 14, 0, 0),
        sentiment_label="neutral",
        sentiment_score=0.5,  # 0.4 <= 0.5 < 0.6 ✅
        summary=" ".join(["palavra"] * 120),
        key_points=["Acompanhamento de rotina"],
        action_items=["Follow-up em 30 dias"],
        risks=[]
    )
    
    assert meeting.sentiment_label == "neutral"
    assert 0.4 <= meeting.sentiment_score < 0.6


def test_sentiment_neutral_invalid_high_score():
    """
    Testa que sentiment_label='neutral' com score >= 0.6 falha na validação.
    """
    with pytest.raises(ValueError, match="sentiment_label 'neutral' requer 0.4 <= score < 0.6"):
        AnalyzedMeeting(
            meeting_id="MTG-NEU-002",
            customer_id="CUST-004",
            customer_name="Roberto Alves",
            banker_id="BNK-002",
            banker_name="Carlos Lima",
            meet_type="presencial",
            meet_date=datetime(2025, 10, 13, 15, 0, 0),
            sentiment_label="neutral",
            sentiment_score=0.7,  # >= 0.6 ❌
            summary=" ".join(["palavra"] * 150),
            key_points=["ponto"],
            action_items=["ação"]
        )


def test_sentiment_negative_valid():
    """
    Testa que sentiment_label='negative' com score < 0.4 é válido.
    
    Regra do briefing: "negative" requer score < 0.4
    """
    meeting = AnalyzedMeeting(
        meeting_id="MTG-NEG-001",
        customer_id="CUST-005",
        customer_name="Luiza Insatisfeita",
        banker_id="BNK-003",
        banker_name="Julia Mendes",
        meet_type="online",
        meet_date=datetime(2025, 10, 13, 16, 0, 0),
        sentiment_label="negative",
        sentiment_score=0.15,  # < 0.4 ✅
        summary=" ".join(["palavra"] * 100),
        key_points=["Cliente insatisfeito", "Reclamações sobre rentabilidade"],
        action_items=["Reunião de emergência"],
        risks=["Perda de cliente", "Migração para concorrente"]
    )
    
    assert meeting.sentiment_label == "negative"
    assert meeting.sentiment_score < 0.4
    assert len(meeting.risks) > 0  # Sentimento negativo deve ter riscos


def test_sentiment_negative_invalid_high_score():
    """
    Testa que sentiment_label='negative' com score >= 0.4 falha na validação.
    """
    with pytest.raises(ValueError, match="sentiment_label 'negative' requer score < 0.4"):
        AnalyzedMeeting(
            meeting_id="MTG-NEG-002",
            customer_id="CUST-006",
            customer_name="Paulo Santos",
            banker_id="BNK-003",
            banker_name="Julia Mendes",
            meet_type="presencial",
            meet_date=datetime(2025, 10, 13, 17, 0, 0),
            sentiment_label="negative",
            sentiment_score=0.5,  # >= 0.4 ❌
            summary=" ".join(["palavra"] * 150),
            key_points=["ponto"],
            action_items=["ação"]
        )


# ============================================================================
# TESTES DE VALIDAÇÃO DE SUMMARY (100-200 PALAVRAS)
# ============================================================================

def test_summary_valid_100_words():
    """
    Testa que summary com exatamente 100 palavras é válido (limite inferior).
    
    Regra do briefing: summary deve ter 100-200 palavras
    """
    meeting = AnalyzedMeeting(
        meeting_id="MTG-SUM-001",
        customer_id="CUST-007",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="presencial",
        meet_date=datetime(2025, 10, 13, 10, 0, 0),
        sentiment_label="neutral",
        sentiment_score=0.5,
        summary=" ".join(["palavra"] * 100),  # Exatamente 100 palavras ✅
        key_points=["ponto"],
        action_items=["ação"]
    )
    
    assert len(meeting.summary.split()) == 100


def test_summary_valid_200_words():
    """
    Testa que summary com exatamente 200 palavras é válido (limite superior).
    """
    meeting = AnalyzedMeeting(
        meeting_id="MTG-SUM-002",
        customer_id="CUST-008",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="online",
        meet_date=datetime(2025, 10, 13, 11, 0, 0),
        sentiment_label="positive",
        sentiment_score=0.8,
        summary=" ".join(["palavra"] * 200),  # Exatamente 200 palavras ✅
        key_points=["ponto"],
        action_items=["ação"]
    )
    
    assert len(meeting.summary.split()) == 200


def test_summary_invalid_too_short():
    """
    Testa que summary com menos de 100 palavras falha na validação.
    """
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError, match="100-200 palavras"):
        AnalyzedMeeting(
            meeting_id="MTG-SUM-003",
            customer_id="CUST-009",
            customer_name="Cliente Teste",
            banker_id="BNK-001",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime(2025, 10, 13, 12, 0, 0),
            sentiment_label="neutral",
            sentiment_score=0.5,
            summary=" ".join(["palavra"] * 50),  # Apenas 50 palavras ❌
            key_points=["ponto"],
            action_items=["ação"]
        )


def test_summary_invalid_too_long():
    """
    Testa que summary com mais de 200 palavras falha na validação.
    """
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError, match="100-200 palavras"):
        AnalyzedMeeting(
            meeting_id="MTG-SUM-004",
            customer_id="CUST-010",
            customer_name="Cliente Teste",
            banker_id="BNK-001",
            banker_name="Banker Teste",
            meet_type="online",
            meet_date=datetime(2025, 10, 13, 13, 0, 0),
            sentiment_label="positive",
            sentiment_score=0.7,
            summary=" ".join(["palavra"] * 250),  # 250 palavras ❌
            key_points=["ponto"],
            action_items=["ação"]
        )


# ============================================================================
# TESTES DE CAMPOS OBRIGATÓRIOS
# ============================================================================

def test_required_fields_present():
    """
    Testa que todos os campos obrigatórios do briefing estão presentes.
    
    Campos obrigatórios conforme briefing:
    - Identificação: meeting_id, customer_id, customer_name, banker_id, banker_name, meet_type, meet_date
    - Análise: sentiment_label, sentiment_score, summary, key_points, action_items
    - Operacionais: source, idempotency_key
    """
    meeting = AnalyzedMeeting(
        meeting_id="MTG-REQ-001",
        customer_id="CUST-011",
        customer_name="Cliente Completo",
        banker_id="BNK-001",
        banker_name="Banker Completo",
        meet_type="Segunda Reunião",
        meet_date=datetime(2025, 10, 13, 14, 0, 0),
        sentiment_label="positive",
        sentiment_score=0.9,
        summary=" ".join(["palavra"] * 150),
        key_points=["ponto 1", "ponto 2"],
        action_items=["ação 1", "ação 2"],
        risks=["risco identificado"],
        source="lftm-challenge",
        idempotency_key="abc123def456"
    )
    
    # Campos de identificação
    assert meeting.meeting_id == "MTG-REQ-001"
    assert meeting.customer_id == "CUST-011"
    assert meeting.customer_name == "Cliente Completo"
    assert meeting.banker_id == "BNK-001"
    assert meeting.banker_name == "Banker Completo"
    assert meeting.meet_type == "Segunda Reunião"
    assert meeting.meet_date == datetime(2025, 10, 13, 14, 0, 0)
    
    # Campos de análise
    assert meeting.sentiment_label == "positive"
    assert meeting.sentiment_score == 0.9
    assert len(meeting.summary.split()) == 150
    assert len(meeting.key_points) == 2
    assert len(meeting.action_items) == 2
    
    # Campos opcionais
    assert len(meeting.risks) == 1
    
    # Campos operacionais
    assert meeting.source == "lftm-challenge"
    assert meeting.idempotency_key == "abc123def456"


def test_sentiment_score_range():
    """
    Testa que sentiment_score deve estar entre 0.0 e 1.0.
    
    Regra do briefing: sentiment_score é um número de 0 a 1
    """
    # Score = 0.0 (válido - limite inferior)
    meeting_min = AnalyzedMeeting(
        meeting_id="MTG-SCORE-001",
        customer_id="CUST-012",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="presencial",
        meet_date=datetime(2025, 10, 13, 10, 0, 0),
        sentiment_label="negative",
        sentiment_score=0.0,  # Mínimo válido ✅
        summary=" ".join(["palavra"] * 100),
        key_points=["ponto"],
        action_items=["ação"]
    )
    assert meeting_min.sentiment_score == 0.0
    
    # Score = 1.0 (válido - limite superior)
    meeting_max = AnalyzedMeeting(
        meeting_id="MTG-SCORE-002",
        customer_id="CUST-013",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="online",
        meet_date=datetime(2025, 10, 13, 11, 0, 0),
        sentiment_label="positive",
        sentiment_score=1.0,  # Máximo válido ✅
        summary=" ".join(["palavra"] * 100),
        key_points=["ponto"],
        action_items=["ação"]
    )
    assert meeting_max.sentiment_score == 1.0
    
    # Score > 1.0 (inválido)
    with pytest.raises(ValueError):
        AnalyzedMeeting(
            meeting_id="MTG-SCORE-003",
            customer_id="CUST-014",
            customer_name="Cliente Teste",
            banker_id="BNK-001",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime(2025, 10, 13, 12, 0, 0),
            sentiment_label="positive",
            sentiment_score=1.5,  # > 1.0 ❌
            summary=" ".join(["palavra"] * 100),
            key_points=["ponto"],
            action_items=["ação"]
        )
    
    # Score < 0.0 (inválido)
    with pytest.raises(ValueError):
        AnalyzedMeeting(
            meeting_id="MTG-SCORE-004",
            customer_id="CUST-015",
            customer_name="Cliente Teste",
            banker_id="BNK-001",
            banker_name="Banker Teste",
            meet_type="online",
            meet_date=datetime(2025, 10, 13, 13, 0, 0),
            sentiment_label="negative",
            sentiment_score=-0.1,  # < 0.0 ❌
            summary=" ".join(["palavra"] * 100),
            key_points=["ponto"],
            action_items=["ação"]
        )

