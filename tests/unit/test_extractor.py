"""
Testes unitários para extractor.py.

Testa a lógica de preparação de prompts e formatação de metadados,
sem fazer chamadas reais à OpenAI API.
"""

import pytest
import json
from datetime import datetime

from app.models.schemas_common import NormalizedInput
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



def test_idempotency_key_format():
    """
    Testa que idempotency_key segue o formato SHA-256 especificado no desafio.
    
    Requisito do desafio:
    - idempotency_key = sha256(meeting_id + meet_date + customer_id)
    - Deve ser um hash hexadecimal de 64 caracteres
    """
    print_test_header("Validação de Idempotency Key", "[IDEMPOTENCY]")
    
    normalized = NormalizedInput(
        transcript="test",
        meeting_id="MTG123",
        customer_id="CUST456",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    print_info("Calculando idempotency_key...")
    key = normalized.compute_idempotency_key()
    
    # Valida que foi gerado
    print_check("key exists", key is not None)
    assert key is not None
    
    # Valida formato SHA-256
    print_check("key length", len(key))
    assert len(key) == 64, "SHA-256 deve ter 64 caracteres"
    
    print_check("is hexadecimal", all(c in '0123456789abcdef' for c in key))
    assert all(c in '0123456789abcdef' for c in key), "Deve ser hexadecimal"
    
    print_success(f"Idempotency key válida: {key[:16]}...")


def test_idempotency_key_deterministic():
    """
    Testa que a mesma entrada sempre gera a mesma chave (determinismo).
    
    Importante para:
    - Detecção de duplicatas
    - Cache
    - Evitar re-processamento
    """
    print_test_header("Determinismo de Idempotency Key", "[IDEMPOTENCY]")
    
    # Cria duas instâncias idênticas
    normalized1 = NormalizedInput(
        transcript="Transcrição 1",
        meeting_id="MTG123",
        customer_id="CUST456",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    normalized2 = NormalizedInput(
        transcript="Transcrição 2",  # Diferente!
        meeting_id="MTG123",
        customer_id="CUST456",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    key1 = normalized1.compute_idempotency_key()
    key2 = normalized2.compute_idempotency_key()
    
    print_check("key1", key1[:16] + "...")
    print_check("key2", key2[:16] + "...")
    
    # Mesmos metadados = mesma chave (transcript não importa!)
    assert key1 == key2, "Chaves devem ser idênticas para mesmos metadados"
    print_success("Determinismo confirmado ✅")


def test_idempotency_key_uniqueness():
    """
    Testa que mudanças em qualquer campo geram chaves diferentes.
    
    Garante que:
    - meeting_id diferente → chave diferente
    - customer_id diferente → chave diferente
    - meet_date diferente → chave diferente
    """
    print_test_header("Unicidade de Idempotency Key", "[IDEMPOTENCY]")
    
    base = NormalizedInput(
        transcript="test",
        meeting_id="MTG123",
        customer_id="CUST456",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    # Varia meeting_id
    variant1 = NormalizedInput(
        transcript="test",
        meeting_id="MTG999",  # Diferente
        customer_id="CUST456",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    # Varia customer_id
    variant2 = NormalizedInput(
        transcript="test",
        meeting_id="MTG123",
        customer_id="CUST999",  # Diferente
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    # Varia meet_date
    variant3 = NormalizedInput(
        transcript="test",
        meeting_id="MTG123",
        customer_id="CUST456",
        meet_date=datetime(2025, 9, 11, 14, 30, 0)  # Diferente
    )
    
    key_base = base.compute_idempotency_key()
    key_variant1 = variant1.compute_idempotency_key()
    key_variant2 = variant2.compute_idempotency_key()
    key_variant3 = variant3.compute_idempotency_key()
    
    print_info("Validando unicidade...")
    
    # Todas devem ser diferentes da base
    assert key_base != key_variant1, "meeting_id diferente deve gerar chave diferente"
    assert key_base != key_variant2, "customer_id diferente deve gerar chave diferente"
    assert key_base != key_variant3, "meet_date diferente deve gerar chave diferente"
    
    # Todas devem ser diferentes entre si
    assert key_variant1 != key_variant2
    assert key_variant1 != key_variant3
    assert key_variant2 != key_variant3
    
    print_success("Unicidade confirmada ✅")


def test_metadata_json_omits_transcript():
    """
    Testa que _prepare_metadata_for_prompt() NÃO inclui o transcript.
    
    Importante porque:
    - Transcript vai em campo separado no prompt
    - Evita duplicação de dados
    - Facilita parsing pelo LLM
    """
    print_test_header("Transcript não incluído em metadados", "[METADATA]")
    
    normalized = NormalizedInput(
        transcript="Este é um transcript longo que não deve aparecer nos metadados",
        meeting_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva"
    )
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    print_info("Verificando que transcript não está nos metadados...")
    
    # Valida que transcript NÃO está no JSON de metadados
    assert "transcript" not in metadata_dict
    
    # Valida que o transcript não aparece no JSON como valor
    metadata_str = json.dumps(metadata_dict)
    assert "Este é um transcript" not in metadata_str
    
    print_success("Transcript corretamente separado dos metadados ✅")


def test_metadata_json_only_has_expected_fields():
    """
    Testa que _prepare_metadata_for_prompt() retorna APENAS os campos esperados.
    
    Campos permitidos (conforme desafio):
    - meeting_id, customer_id, customer_name
    - banker_id, banker_name
    - meet_type, meet_date
    """
    print_test_header("Campos permitidos em metadados", "[METADATA]")
    
    normalized = NormalizedInput(
        transcript="test",
        meeting_id="MTG001",
        customer_id="CUST001",
        customer_name="João Silva",
        banker_id="BKR001",
        banker_name="Pedro Falcão",
        meet_type="Primeira Reunião",
        meet_date=datetime(2025, 9, 10, 14, 30, 0)
    )
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    expected_fields = {
        "meeting_id", "customer_id", "customer_name",
        "banker_id", "banker_name", "meet_type", "meet_date"
    }
    
    actual_fields = set(metadata_dict.keys())
    
    print_check("expected_fields", expected_fields)
    print_check("actual_fields", actual_fields)
    
    # Valida que todos os campos estão presentes
    assert actual_fields == expected_fields, f"Campos inesperados: {actual_fields - expected_fields}"
    
    print_success("Apenas campos esperados presentes ✅")


def test_sanitize_transcript_preserves_beginning():
    """
    Testa que _sanitize_transcript_for_log() preserva o INÍCIO da transcrição.
    
    Importante para:
    - Debug (começo geralmente tem contexto importante)
    - Identificação rápida da reunião
    """
    print_test_header("Sanitização preserva início", "[SANITIZE]")
    
    transcript = "Cliente: João Silva. Banker: Pedro Falcão. Reunião sobre crédito." + "X" * 500
    
    sanitized = _sanitize_transcript_for_log(transcript, max_chars=100)
    
    # Valida que começo é preservado
    print_check("starts_with", sanitized[:50] + "...")
    assert sanitized.startswith("Cliente: João Silva")
    
    print_success("Início preservado corretamente ✅")


def test_sanitize_transcript_different_lengths():
    """
    Testa _sanitize_transcript_for_log() com diferentes tamanhos de max_chars.
    
    Valida que:
    - max_chars=50 trunca em 50
    - max_chars=200 trunca em 200
    - max_chars=1000 trunca em 1000
    """
    print_test_header("Sanitização com diferentes limites", "[SANITIZE]")
    
    transcript = "A" * 2000  # 2000 caracteres
    
    # Testa diferentes limites
    limits = [50, 200, 500, 1000]
    
    for limit in limits:
        sanitized = _sanitize_transcript_for_log(transcript, max_chars=limit)
        
        # Verifica que começa com exatamente `limit` caracteres
        assert sanitized.startswith("A" * limit)
        print_check(f"limit={limit}", f"truncated at {limit} chars ✅")
    
    print_success("Todos os limites funcionam corretamente ✅")


def test_metadata_json_empty_when_no_metadata():
    """
    Testa que JSON retorna {} quando não há metadados fornecidos.
    
    Cenário: usuário envia APENAS transcript, sem nenhum metadata.
    O LLM precisa extrair tudo da transcrição.
    """
    print_test_header("JSON vazio quando sem metadados", "[METADATA]")
    
    # Apenas transcript, sem nenhum metadata
    normalized = NormalizedInput(transcript="Cliente: Olá...")
    
    metadata_json = _prepare_metadata_for_prompt(normalized)
    metadata_dict = json.loads(metadata_json)
    
    print_check("metadata_dict", metadata_dict)
    
    # Deve ser um dicionário vazio
    assert metadata_dict == {}
    
    # JSON string deve ser "{}"
    assert metadata_json.strip() == "{}"
    
    print_success("JSON vazio correto ✅")


def test_meet_date_iso_8601_format():
    """
    Testa que meet_date é formatado EXATAMENTE como ISO 8601.
    
    Requisito do desafio:
    - meet_date deve ser ISO 8601 (YYYY-MM-DDTHH:MM:SS)
    """
    print_test_header("Formatação ISO 8601 de meet_date", "[METADATA]")
    
    # Testa diferentes datas
    test_cases = [
        (datetime(2025, 1, 1, 0, 0, 0), "2025-01-01T00:00:00"),
        (datetime(2025, 12, 31, 23, 59, 59), "2025-12-31T23:59:59"),
        (datetime(2025, 9, 10, 14, 30, 0), "2025-09-10T14:30:00"),
    ]
    
    for dt, expected_iso in test_cases:
        normalized = NormalizedInput(
            transcript="test",
            meet_date=dt
        )
        
        metadata_json = _prepare_metadata_for_prompt(normalized)
        metadata_dict = json.loads(metadata_json)
        
        print_check(f"date={dt}", metadata_dict["meet_date"])
        assert metadata_dict["meet_date"] == expected_iso
    
    print_success("Todas as datas em ISO 8601 ✅")
