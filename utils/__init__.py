"""
Utilitários compartilhados para processamento com LLMs.

Este pacote contém funções auxiliares usadas tanto pelo Extractor
quanto pelo Analyzer, mantendo o código DRY e facilitando manutenção.

Módulos:
- common: Funções auxiliares genéricas (logging, sanitização, preparação)
- json_repair: Lógica de reparo de JSON malformado
"""

from utils.common import (
    log_retry_attempt,
    extract_and_record_token_usage,
    sanitize_transcript_for_log,
    prepare_metadata_for_prompt,
)

from utils.json_repair import (
    repair_json,
    EXTRACTOR_SCHEMA,
    ANALYZER_SCHEMA,
)

__all__ = [
    # Common utilities
    "log_retry_attempt",
    "extract_and_record_token_usage",
    "sanitize_transcript_for_log",
    "prepare_metadata_for_prompt",
    
    # JSON repair
    "repair_json",
    "EXTRACTOR_SCHEMA",
    "ANALYZER_SCHEMA",
]

