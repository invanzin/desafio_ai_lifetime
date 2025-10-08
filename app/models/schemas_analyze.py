"""
Schemas da Feature Analyzer - Análise de Sentimento e Insights.

Este módulo contém os schemas Pydantic específicos para a feature
de análise de sentimento e geração de insights de reuniões.
"""

from typing import Optional, List, Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.schemas_common import Metadata, RawMeeting, NormalizedInput, MeetingRequest

# Alias para manter compatibilidade (AnalyzeRequest é o mesmo que MeetingRequest)
# A classe real está em schemas_common.py, pois é compartilhada entre Extract e Analyze
AnalyzeRequest = MeetingRequest


class AnalyzedMeeting(BaseModel):
    """
    Modelo de dados para reunião analisada com sentimento e insights.
    
    Resultado da análise de sentimento de uma transcrição de reunião,
    incluindo classificação de sentimento, score numérico e insights
    estratégicos extraídos automaticamente por LLMs.
    
    Attributes:
        meeting_id (str): Identificador único da reunião.
        customer_id (str): Identificador único do cliente.
        customer_name (str): Nome completo do cliente.
        banker_id (str): Identificador único do banker.
        banker_name (str): Nome completo do banker.
        meet_type (str): Tipo/categoria da reunião.
        meet_date (Union[datetime, str]): Data e hora da reunião.
        
        sentiment_label (Literal): Classificação categórica do sentimento.
                                   Valores: "positive", "neutral", "negative"
        sentiment_score (float): Score numérico de sentimento (0.0 a 1.0).
                                Range: 0.0 = muito negativo, 1.0 = muito positivo
        
        summary (str): Resumo executivo (100-200 palavras).
        key_points (List[str]): Pontos-chave discutidos.
        action_items (List[str]): Ações/tarefas identificadas.
        risks (List[str]): Riscos identificados (opcional).
        
        source (Literal): Identificador da origem ("lftm-challenge").
        idempotency_key (str): Chave única para idempotência.
    
    Validations:
        - summary validado para 100-200 palavras
        - sentiment_score validado para 0.0-1.0
        - sentiment_label e sentiment_score devem ser consistentes
    """
    
    # Campos obrigatórios - Metadados da reunião
    meeting_id: str
    customer_id: str
    customer_name: str
    banker_id: str
    banker_name: str
    meet_type: str
    meet_date: Union[datetime, str]
    
    # Campos obrigatórios - Análise de sentimento
    sentiment_label: Literal["positive", "neutral", "negative"]
    sentiment_score: float = Field(..., ge=0.0, le=1.0, description="Score entre 0.0 e 1.0")
    
    # Campos obrigatórios - Dados extraídos por IA
    summary: str
    key_points: List[str]
    action_items: List[str]
    
    # Campos opcionais - Insights adicionais
    risks: Optional[List[str]] = None
    
    # Campos obrigatórios - Metadados de controle
    source: Literal["lftm-challenge"] = "lftm-challenge"
    idempotency_key: Optional[str] = None

    @field_validator("summary")
    def validate_summary_length(cls, summary: str) -> str:
        """
        Valida se o resumo possui entre 100 e 200 palavras.
        
        Raises:
            ValueError: Se o resumo tiver menos de 100 ou mais de 200 palavras.
        """
        wc = len(summary.split())
        if wc < 100 or wc > 200:
            raise ValueError(f"summary deve ter 100-200 palavras, tem {wc}")
        return summary
    
    @field_validator("sentiment_score")
    def validate_sentiment_score_range(cls, score: float) -> float:
        """
        Valida que o score de sentimento está entre 0.0 e 1.0.
        
        Raises:
            ValueError: Se o score estiver fora do intervalo.
        """
        if not (0.0 <= score <= 1.0):
            raise ValueError(f"sentiment_score deve estar entre 0.0 e 1.0, recebido: {score}")
        return score
    
    @model_validator(mode='after')
    def validate_sentiment_consistency(self):
        """
        Valida consistência entre sentiment_label e sentiment_score.
        
        Regras:
        - "positive": score >= 0.6
        - "neutral": 0.4 <= score < 0.6
        - "negative": score < 0.4
        
        Raises:
            ValueError: Se label e score forem inconsistentes.
        """
        label = self.sentiment_label
        score = self.sentiment_score
        
        if label == "positive" and score < 0.6:
            raise ValueError(
                f"sentiment_label 'positive' requer score >= 0.6, recebido: {score}"
            )
        elif label == "neutral" and not (0.4 <= score < 0.6):
            raise ValueError(
                f"sentiment_label 'neutral' requer 0.4 <= score < 0.6, recebido: {score}"
            )
        elif label == "negative" and score >= 0.4:
            raise ValueError(
                f"sentiment_label 'negative' requer score < 0.4, recebido: {score}"
            )
        
        return self

