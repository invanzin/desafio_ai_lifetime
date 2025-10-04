"""
Testes unitários para extractor.py.

Testa a lógica de preparação de prompts e formatação de metadados,
sem fazer chamadas reais à OpenAI API.
"""

import pytest
import json
from datetime import datetime

from app.models.schemas import NormalizedInput
from app.extractors.extractor import _prepare_metadata_for_prompt, _sanitize_transcript_for_log


# ============================================================================
# CONFIGURAÇÃO DE LOGGING BONITO
# ============================================================================

def print_test_header(test_name: str, emoji: str = "[TEST]"):
    """Imprime um cabeçalho bonito para o teste."""
    print(f"\n{'='*70}")
    print(f"{emoji}  {test_name}")
    print(f"{'='*70}")


def print_success(message: str):
    """Imprime mensagem de sucesso."""
    print(f"  [OK] {message}")


def print_info(message: str):
    """Imprime mensagem informativa."""
    print(f"  [INFO] {message}")


def print_check(field: str, value: any):
    """Imprime verificação de campo."""
    print(f"  [CHECK] {field}: {value}")


# ============================================================================
# TESTES: _prepare_metadata_for_prompt
# ============================================================================

def test_prepare_metadata_with_all_fields():
    """
    Testa preparação de metadados quando todos os campos estão presentes.
    
    Valida que:
    - JSON está bem formatado
    - Todos os campos são incluídos
    - meet_date é convertido para ISO 8601
    - Não há campos None no output
    """
    print_test_header("Preparacao de Metadados - Todos os Campos", "[METADATA]")
    
    normalized = NormalizedInput(
        transcript="Cliente: Olá...",
        meeting_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_type="Primeira Reunião",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    print_info("Gerando JSON de metadados...")
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    print_info("Validando campos...")
    # Valida que todos os campos estão presentes
    print_check("meeting_id", metadata_dict["meeting_id"])
    assert metadata_dict["meeting_id"] == "MTG001"
    
    print_check("customer_id", metadata_dict["customer_id"])
    assert metadata_dict["customer_id"] == "CUST001"
    
    print_check("customer_name", metadata_dict["customer_name"])
    assert metadata_dict["customer_name"] == "João Silva"
    
    print_check("banker_id", metadata_dict["banker_id"])
    assert metadata_dict["banker_id"] == "BKR001"
    
    print_check("banker_name", metadata_dict["banker_name"])
    assert metadata_dict["banker_name"] == "Pedro Falcão"
    
    print_check("meet_type", metadata_dict["meet_type"])
    assert metadata_dict["meet_type"] == "Primeira Reunião"
    
    print_check("meet_date (ISO 8601)", metadata_dict["meet_date"])
    assert metadata_dict["meet_date"] == "2025-09-10T14:30:00"
    
    # Valida que não há campos None (foram removidos)
    assert None not in metadata_dict.values()
    
    print_success(f"JSON válido com {len(metadata_dict)} campos")


def test_prepare_metadata_without_optional_fields():
    """
    Testa preparação de metadados quando apenas campos obrigatórios estão presentes.
    
    Valida que:
    - Campos None são omitidos do JSON
    - JSON permanece válido
    - LLM verá apenas os campos fornecidos (não verá null/None)
    """
    normalized = NormalizedInput(
        transcript="Cliente: Olá...",
        meeting_id="MTG001",
        customer_id="CUST001",
        # Demais campos são None (opcionais)
    )
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    # Valida que apenas campos fornecidos estão no JSON
    assert "meeting_id" in metadata_dict
    assert "customer_id" in metadata_dict
    
    # Valida que campos None foram omitidos
    assert "customer_name" not in metadata_dict
    assert "banker_id" not in metadata_dict
    assert "banker_name" not in metadata_dict
    assert "meet_type" not in metadata_dict
    assert "meet_date" not in metadata_dict
    
    # Valida que não há valores None
    assert None not in metadata_dict.values()


def test_prepare_metadata_with_no_fields():
    """
    Testa preparação de metadados quando nenhum campo está presente.
    
    Valida que:
    - JSON vazio é retornado {}
    - Não quebra a função
    - LLM saberá que precisa extrair tudo da transcrição
    """
    normalized = NormalizedInput(
        transcript="Cliente: Olá...",
        # Todos os metadados são None
    )
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    # Valida que JSON está vazio (todos os campos eram None)
    assert metadata_dict == {}


def test_prepare_metadata_partial_fields():
    """
    Testa preparação de metadados com mix de campos presentes e ausentes.
    
    Cenário comum: cliente fornece apenas alguns metadados,
    o resto deve ser extraído da transcrição.
    """
    normalized = NormalizedInput(
        transcript="Cliente: Olá...",
        meeting_id="MTG001",
        customer_name="João Silva",
        meet_date=datetime(2025, 9, 10, 14, 30, 0),
        # customer_id, banker_id, banker_name, meet_type são None
    )
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    # Valida campos presentes
    assert metadata_dict["meeting_id"] == "MTG001"
    assert metadata_dict["customer_name"] == "João Silva"
    assert metadata_dict["meet_date"] == "2025-09-10T14:30:00"
    
    # Valida campos ausentes
    assert "customer_id" not in metadata_dict
    assert "banker_id" not in metadata_dict
    assert "banker_name" not in metadata_dict
    assert "meet_type" not in metadata_dict
    
    # Total de campos no JSON
    assert len(metadata_dict) == 3


def test_prepare_metadata_meet_date_formatting():
    """
    Testa que meet_date é formatado corretamente em ISO 8601.
    
    Valida diferentes formatos de datetime:
    - Com segundos
    - Com microsegundos
    - Timezone-aware (se aplicável)
    """
    # Caso 1: Data sem microsegundos
    normalized1 = NormalizedInput(
        transcript="test",
        meet_date=datetime(2025, 1, 15, 10, 30, 0)
    )
    metadata1 = json.loads(_prepare_metadata_for_prompt(normalized1))
    assert metadata1["meet_date"] == "2025-01-15T10:30:00"
    
    # Caso 2: Data com microsegundos
    normalized2 = NormalizedInput(
        transcript="test",
        meet_date=datetime(2025, 1, 15, 10, 30, 45, 123456)
    )
    metadata2 = json.loads(_prepare_metadata_for_prompt(normalized2))
    assert metadata2["meet_date"] == "2025-01-15T10:30:45.123456"


# ============================================================================
# TESTES: _sanitize_transcript_for_log
# ============================================================================

def test_sanitize_transcript_short():
    """
    Testa que transcrições curtas não são truncadas.
    """
    transcript = "Cliente: Olá, tudo bem?"
    
    sanitized = _sanitize_transcript_for_log(transcript, max_chars=300)
    
    assert sanitized == transcript
    assert "truncado" not in sanitized


def test_sanitize_transcript_long():
    """
    Testa que transcrições longas são truncadas corretamente.
    """
    transcript = "A" * 500  # 500 caracteres
    
    sanitized = _sanitize_transcript_for_log(transcript, max_chars=300)
    
    # Valida truncamento
    assert len(sanitized) > 300  # Inclui mensagem de truncamento
    assert sanitized.startswith("A" * 300)
    assert "truncado" in sanitized
    assert "total: 500 chars" in sanitized


def test_sanitize_transcript_exact_limit():
    """
    Testa comportamento quando transcrição tem exatamente o tamanho limite.
    """
    transcript = "B" * 300
    
    sanitized = _sanitize_transcript_for_log(transcript, max_chars=300)
    
    # Não deve truncar (<=)
    assert sanitized == transcript
    assert "truncado" not in sanitized


def test_sanitize_transcript_custom_max_chars():
    """
    Testa que max_chars customizado funciona corretamente.
    """
    transcript = "C" * 200
    
    sanitized = _sanitize_transcript_for_log(transcript, max_chars=100)
    
    # Truncado em 100 chars
    assert sanitized.startswith("C" * 100)
    assert "truncado" in sanitized
    assert "total: 200 chars" in sanitized


# ============================================================================
# TESTES: Validação de Estrutura do Prompt (indiretamente)
# ============================================================================

def test_metadata_json_is_valid_json():
    """
    Testa que o output de _prepare_metadata_for_prompt é sempre JSON válido.
    
    Importante porque será inserido no prompt do LLM.
    """
    test_cases = [
        # Caso 1: Todos os campos
        NormalizedInput(
            transcript="test",
            meeting_id="MTG001",
            customer_id="CUST001",
            customer_name="João Silva",
            banker_id="BKR001",
            banker_name="Pedro Falcão",
            meet_type="Primeira Reunião",
            meet_date=datetime(2025, 9, 10, 14, 30)
        ),
        # Caso 2: Sem campos
        NormalizedInput(transcript="test"),
        # Caso 3: Campos parciais
        NormalizedInput(
            transcript="test",
            customer_name="Ana Santos"
        ),
    ]
    
    for normalized in test_cases:
        metadata_json = _prepare_metadata_for_prompt(normalized)
        
        # Valida que é JSON válido
        try:
            parsed = json.loads(metadata_json)
            assert isinstance(parsed, dict)
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON inválido: {e}")


def test_metadata_json_has_proper_encoding():
    """
    Testa que caracteres especiais (acentos, ç) são tratados corretamente.
    """
    normalized = NormalizedInput(
        transcript="test",
        customer_name="João José da Silva Gonçalves",
        banker_name="María García",
        meet_type="Reunião de Acompanhamento"
    )
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    # Valida que acentos foram preservados
    assert metadata_dict["customer_name"] == "João José da Silva Gonçalves"
    assert metadata_dict["banker_name"] == "María García"
    assert metadata_dict["meet_type"] == "Reunião de Acompanhamento"

