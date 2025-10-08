"""
Schemas da Feature Analyzer - Análise de Sentimento e Insights.

Este módulo contém os schemas Pydantic específicos para a feature de análise
de sentimento e geração de insights de reuniões (Desafio 2).
"""

from typing import List, Literal, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.schemas_common import Metadata, RawMeeting, NormalizedInput, MeetingRequest

# Alias para manter compatibilidade (AnalyzeRequest é o mesmo que MeetingRequest)
# A classe real está em schemas_common.py, pois é compartilhada entre Extract e Analyze
AnalyzeRequest = MeetingRequest


class AnalyzedMeeting(BaseModel):
    """
    Schema de saída para o endpoint /analyze.
    
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
        meet_date (datetime): Data e hora da reunião.
        
        sentiment_label (Literal): Classificação categórica do sentimento.
                                   Valores: "positive", "neutral", "negative"
        sentiment_score (float): Score numérico de sentimento (0.0 a 1.0).
                                Range: 0.0 = muito negativo, 1.0 = muito positivo
        
        summary (str): Resumo executivo da reunião (100-200 palavras).
        key_points (List[str]): Pontos-chave discutidos.
        action_items (List[str]): Ações/tarefas identificadas.
        risks (List[str]): Riscos ou preocupações levantados pelo cliente.
        
        source (Literal): Identificador da origem ("lftm-challenge").
        idempotency_key (Optional[str]): Chave única para idempotência.
    
    Validations:
        - `summary` é validado para ter entre 100 e 200 palavras.
        - `sentiment_score` é validado para estar no intervalo [0.0, 1.0].
        - `sentiment_label` e `sentiment_score` são validados para consistência.
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
    risks: List[str] = Field(default_factory=list)
    
    # Campos obrigatórios - Metadados de controle
    source: Literal["lftm-challenge"] = "lftm-challenge"
    idempotency_key: Optional[str] = None

    @field_validator("summary")
    def validate_summary_length(cls, summary: str) -> str:
        """
        Valida se o resumo possui entre 100 e 200 palavras.
        
        Este validador garante que o resumo gerado pela IA tenha uma extensão adequada:
        nem muito curto (que perderia informações importantes) nem muito longo
        (que não seria um resumo executivo eficaz).
        
        Processo de validação:
        1. Divide o texto do resumo em palavras usando split() (separação por espaços)
        2. Conta o número total de palavras
        3. Verifica se está no intervalo permitido (100-200 palavras)
        4. Se estiver fora do intervalo, lança uma exceção com mensagem detalhada
        5. Se estiver correto, retorna o valor validado
        
        Args:
            cls: Referência à classe (método de classe do Pydantic)
            v (str): O valor do campo `summary` a ser validado
        
        Returns:
            str: O valor do resumo, se válido (100-200 palavras)
        
        Raises:
            ValueError: Se o resumo tiver menos de 100 ou mais de 200 palavras.
                       A mensagem de erro inclui a contagem atual de palavras.
        
        Note:
            A contagem considera palavras separadas por espaço em branco.
            Palavras compostas ou hifenizadas são contadas como uma única palavra.
        """
        # Conta palavras dividindo por espaços em branco
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
