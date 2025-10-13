"""
Testes unitários para validação do ExtractedMeeting.

Este módulo testa a validação Pydantic do ExtractedMeeting, garantindo que:
- Summary tem entre 100-200 palavras
- Campos obrigatórios estão presentes
- Campo 'topics' está correto (diferencial do Extractor vs Analyzer)
- Campo 'source' = "lftm-challenge"

Segue o mesmo padrão de test_analyzer.py para consistência.

Conforme exigido no briefing do Desafio 1:
- "Testes: validação de schemas"
- "Campos obrigatórios: summary (100-200 palavras), key_points, action_items, topics"
"""

import pytest
from datetime import datetime
from app.models.schemas_extract import ExtractedMeeting


# ============================================================================
# TESTES DE VALIDAÇÃO DE SUMMARY (100-200 PALAVRAS)
# ============================================================================

def test_summary_valid_100_words():
    """
    Testa que summary com exatamente 100 palavras é válido (limite inferior).
    
    Regra do briefing: summary deve ter 100-200 palavras
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-SUM-001",
        customer_id="CUST-001",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="presencial",
        meet_date=datetime(2025, 10, 13, 10, 0, 0),
        summary=" ".join(["palavra"] * 100),  # Exatamente 100 palavras ✅
        key_points=["ponto 1"],
        action_items=["ação 1"],
        topics=["investimentos"]
    )
    
    assert len(meeting.summary.split()) == 100


def test_summary_valid_200_words():
    """
    Testa que summary com exatamente 200 palavras é válido (limite superior).
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-SUM-002",
        customer_id="CUST-002",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="online",
        meet_date=datetime(2025, 10, 13, 11, 0, 0),
        summary=" ".join(["palavra"] * 200),  # Exatamente 200 palavras ✅
        key_points=["ponto 1"],
        action_items=["ação 1"],
        topics=["renda fixa"]
    )
    
    assert len(meeting.summary.split()) == 200


def test_summary_invalid_too_short():
    """
    Testa que summary com menos de 100 palavras falha na validação.
    """
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError, match="100-200 palavras"):
        ExtractedMeeting(
            meeting_id="MTG-SUM-003",
            customer_id="CUST-003",
            customer_name="Cliente Teste",
            banker_id="BNK-001",
            banker_name="Banker Teste",
            meet_type="híbrido",
            meet_date=datetime(2025, 10, 13, 12, 0, 0),
            summary=" ".join(["palavra"] * 50),  # Apenas 50 palavras ❌
            key_points=["ponto"],
            action_items=["ação"],
            topics=["crédito"]
        )


def test_summary_invalid_too_long():
    """
    Testa que summary com mais de 200 palavras falha na validação.
    """
    from pydantic import ValidationError
    
    with pytest.raises(ValidationError, match="100-200 palavras"):
        ExtractedMeeting(
            meeting_id="MTG-SUM-004",
            customer_id="CUST-004",
            customer_name="Cliente Teste",
            banker_id="BNK-001",
            banker_name="Banker Teste",
            meet_type="presencial",
            meet_date=datetime(2025, 10, 13, 13, 0, 0),
            summary=" ".join(["palavra"] * 250),  # 250 palavras ❌
            key_points=["ponto"],
            action_items=["ação"],
            topics=["seguros"]
        )


# ============================================================================
# TESTES DE CAMPOS OBRIGATÓRIOS
# ============================================================================

def test_required_fields_present():
    """
    Testa que todos os campos obrigatórios do briefing estão presentes.
    
    Campos obrigatórios conforme Desafio 1:
    - Identificação: meeting_id, customer_id, customer_name, banker_id, banker_name, meet_type, meet_date
    - Extraídos: summary, key_points, action_items, topics
    - Operacionais: source, idempotency_key
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-REQ-001",
        customer_id="CUST-011",
        customer_name="Cliente Completo",
        banker_id="BNK-001",
        banker_name="Banker Completo",
        meet_type="Primeira Reunião",
        meet_date=datetime(2025, 10, 13, 14, 0, 0),
        summary=" ".join(["palavra"] * 150),
        key_points=["ponto 1", "ponto 2", "ponto 3"],
        action_items=["ação 1", "ação 2"],
        topics=["investimentos", "renda fixa", "previdência"],
        source="lftm-challenge",
        idempotency_key="abc123def456"
    )
    
    # Campos de identificação
    assert meeting.meeting_id == "MTG-REQ-001"
    assert meeting.customer_id == "CUST-011"
    assert meeting.customer_name == "Cliente Completo"
    assert meeting.banker_id == "BNK-001"
    assert meeting.banker_name == "Banker Completo"
    assert meeting.meet_type == "Primeira Reunião"
    assert meeting.meet_date == datetime(2025, 10, 13, 14, 0, 0)
    
    # Campos extraídos
    assert len(meeting.summary.split()) == 150
    assert len(meeting.key_points) == 3
    assert len(meeting.action_items) == 2
    assert len(meeting.topics) == 3
    
    # Campos operacionais
    assert meeting.source == "lftm-challenge"
    assert meeting.idempotency_key == "abc123def456"


def test_topics_field_is_list():
    """
    Testa que 'topics' é uma lista de strings.
    
    Diferencial do ExtractedMeeting: tem 'topics' (AnalyzedMeeting tem 'risks')
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-TOP-001",
        customer_id="CUST-012",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="online",
        meet_date=datetime(2025, 10, 13, 15, 0, 0),
        summary=" ".join(["palavra"] * 120),
        key_points=["ponto"],
        action_items=["ação"],
        topics=["investimentos", "renda variável", "fundos"]
    )
    
    assert isinstance(meeting.topics, list)
    assert len(meeting.topics) == 3
    assert all(isinstance(topic, str) for topic in meeting.topics)


def test_source_field_is_lftm_challenge():
    """
    Testa que campo 'source' é sempre "lftm-challenge".
    
    Regra do briefing: campo 'source' identifica origem dos dados.
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-SRC-001",
        customer_id="CUST-013",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="presencial",
        meet_date=datetime(2025, 10, 13, 16, 0, 0),
        summary=" ".join(["palavra"] * 100),
        key_points=["ponto"],
        action_items=["ação"],
        topics=["empréstimos"],
        source="lftm-challenge"  # Deve ser exatamente este valor
    )
    
    assert meeting.source == "lftm-challenge"


def test_meet_type_accepts_any_string():
    """
    Testa que meet_type aceita qualquer string (é flexível).
    
    Exemplos do briefing: "Primeira Reunião", "Segunda Reunião", etc.
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-TYPE-001",
        customer_id="CUST-014",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="Reunião de Acompanhamento de Carteira Personalizada",  # String longa OK
        meet_date=datetime(2025, 10, 13, 17, 0, 0),
        summary=" ".join(["palavra"] * 150),
        key_points=["ponto"],
        action_items=["ação"],
        topics=["carteira"]
    )
    
    assert meeting.meet_type == "Reunião de Acompanhamento de Carteira Personalizada"


def test_meet_date_accepts_datetime():
    """
    Testa que meet_date aceita objeto datetime.
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-DATE-001",
        customer_id="CUST-015",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="presencial",
        meet_date=datetime(2025, 10, 13, 14, 30, 0),  # datetime object
        summary=" ".join(["palavra"] * 100),
        key_points=["ponto"],
        action_items=["ação"],
        topics=["previdência"]
    )
    
    assert isinstance(meeting.meet_date, datetime)
    assert meeting.meet_date.year == 2025
    assert meeting.meet_date.month == 10
    assert meeting.meet_date.day == 13


def test_meet_date_accepts_iso_string():
    """
    Testa que meet_date aceita string ISO 8601.
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-DATE-002",
        customer_id="CUST-016",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="online",
        meet_date="2025-10-13T14:30:00Z",  # ISO 8601 string
        summary=" ".join(["palavra"] * 120),
        key_points=["ponto"],
        action_items=["ação"],
        topics=["câmbio"]
    )
    
    # Pydantic converte string para datetime automaticamente
    assert meeting.meet_date is not None


def test_idempotency_key_optional():
    """
    Testa que idempotency_key pode ser None (opcional).
    
    Será preenchido automaticamente após extração.
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-IDEM-001",
        customer_id="CUST-017",
        customer_name="Cliente Teste",
        banker_id="BNK-001",
        banker_name="Banker Teste",
        meet_type="híbrido",
        meet_date=datetime(2025, 10, 13, 18, 0, 0),
        summary=" ".join(["palavra"] * 130),
        key_points=["ponto"],
        action_items=["ação"],
        topics=["seguros"],
        idempotency_key=None  # None é válido
    )
    
    assert meeting.idempotency_key is None


def test_all_fields_with_realistic_data():
    """
    Testa ExtractedMeeting com dados realistas completos.
    
    Valida que todos os campos juntos funcionam corretamente.
    """
    meeting = ExtractedMeeting(
        meeting_id="MTG-2025-10-13-001",
        customer_id="CUST-456-ABC",
        customer_name="João da Silva Oliveira",
        banker_id="BNK-789-XYZ",
        banker_name="Maria Santos Costa",
        meet_type="Reunião de Acompanhamento Trimestral de Investimentos",
        meet_date=datetime(2025, 10, 13, 14, 30, 0),
        summary=(
            "Reunião focou na revisão da performance dos investimentos do cliente no último trimestre. "
            "O cliente expressou satisfação com os resultados obtidos, que superaram as expectativas iniciais. "
            "Foram discutidas novas oportunidades de investimento em renda fixa e fundos multimercado. "
            "O banker apresentou três propostas de rebalanceamento de carteira visando otimizar a relação risco-retorno. "
            "O cliente demonstrou interesse especial em produtos de previdência privada para planejamento de longo prazo. "
            "Foi acordado um aporte adicional de R$ 200 mil a ser investido nos próximos 30 dias. "
            "O banco se comprometeu a enviar propostas detalhadas em até 48 horas. "
            "Próxima reunião agendada para daqui a três meses para novo acompanhamento. "
            "Cliente elogiou o atendimento personalizado e a transparência nas informações. "
            "Relacionamento considerado sólido e com potencial de crescimento futuro."
        ),  # ~150 palavras
        key_points=[
            "Performance dos investimentos superou expectativas",
            "Cliente interessado em previdência privada",
            "Aporte adicional de R$ 200 mil acordado",
            "Rebalanceamento de carteira será proposto"
        ],
        action_items=[
            "Enviar propostas detalhadas em 48h",
            "Preparar simulações de previdência privada",
            "Agendar próxima reunião em 3 meses"
        ],
        topics=[
            "revisão de carteira",
            "investimentos",
            "renda fixa",
            "fundos multimercado",
            "previdência privada",
            "rebalanceamento"
        ],
        source="lftm-challenge",
        idempotency_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2"
    )
    
    # Validações completas
    assert meeting.meeting_id == "MTG-2025-10-13-001"
    assert 100 <= len(meeting.summary.split()) <= 200
    assert len(meeting.key_points) == 4
    assert len(meeting.action_items) == 3
    assert len(meeting.topics) == 6
    assert meeting.source == "lftm-challenge"
    assert meeting.idempotency_key is not None
