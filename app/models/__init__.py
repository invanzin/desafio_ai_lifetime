"""
Módulo de schemas Pydantic para validação de dados.

Este módulo organiza os schemas em três categorias:
- schemas_common: Classes compartilhadas (Metadata, RawMeeting, NormalizedInput)
- schemas_extract: Schemas do Desafio 1 (ExtractRequest, ExtractedMeeting)
- schemas_analyze: Schemas do Desafio 2 (AnalyzeRequest, AnalyzedMeeting)
"""

# Schemas Comuns
from app.models.schemas_common import (
    Metadata,
    RawMeeting,
    NormalizedInput,
    MeetingRequest,
)

# Schemas do Desafio 1 (Extract)
from app.models.schemas_extract import (
    ExtractRequest,
    ExtractedMeeting,
)

# Schemas do Desafio 2 (Analyze)
from app.models.schemas_analyze import (
    AnalyzeRequest,
    AnalyzedMeeting,
)

__all__ = [
    # Comuns
    "Metadata",
    "RawMeeting",
    "NormalizedInput",
    "MeetingRequest",  # Request compartilhado para /extract e /analyze
    # Extract
    "ExtractRequest",  # Alias de MeetingRequest
    "ExtractedMeeting",
    # Analyze
    "AnalyzeRequest",  # Alias de MeetingRequest
    "AnalyzedMeeting",
]

