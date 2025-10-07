"""
Router para endpoint de análise de sentimento (Desafio 2).

Este módulo implementa o endpoint POST /analyze que analisa sentimento
e gera insights de transcrições de reuniões.

TODO: Implementar na Fase 4
"""

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Cria router
router = APIRouter()


@router.post("/")
async def analyze_endpoint(request: Request):
    """
    Analisa sentimento e gera insights de uma transcrição de reunião.
    
    Request Body:
        - transcript: str (obrigatório)
        - metadata: dict (opcional)
    
    Returns:
        AnalyzedMeeting: JSON com análise de sentimento e insights
    
    TODO: Implementar na Fase 4
    """
    logger.info("[ANALYZE] Endpoint será implementado na Fase 4")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Analyze endpoint será implementado na Fase 4"
    )

