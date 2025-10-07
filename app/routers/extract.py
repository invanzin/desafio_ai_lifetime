"""
Router para endpoint de extração de informações (Desafio 1).

Este módulo implementa o endpoint POST /extract que extrai informações
estruturadas de transcrições de reuniões.

TODO: Mover lógica do main.py para cá na Fase 4
"""

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Cria router
router = APIRouter()


@router.post("/")
async def extract_endpoint(request: Request):
    """
    Extrai informações estruturadas de uma transcrição de reunião.
    
    Request Body:
        - transcript: str (obrigatório)
        - metadata: dict (opcional)
    
    Returns:
        ExtractedMeeting: JSON com informações extraídas
    
    TODO: Implementar na Fase 4 (mover do main.py)
    """
    logger.info("[EXTRACT] Endpoint será implementado na Fase 4")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Extract endpoint será refatorado na Fase 4"
    )

