"""
Schemas do Desafio 1 - Extração de Informações.

Este módulo contém os schemas Pydantic específicos para o serviço
de extração de informações estruturadas de reuniões.
"""

from typing import Optional, List, Literal, Union
from datetime import datetime
from pydantic import BaseModel, field_validator

from app.models.schemas_common import Metadata, RawMeeting, NormalizedInput, MeetingRequest

# Alias para manter compatibilidade (ExtractRequest é o mesmo que MeetingRequest)
# A classe real está em schemas_common.py, pois é compartilhada entre Extract e Analyze
ExtractRequest = MeetingRequest


class ExtractedMeeting(BaseModel):
    """
    Modelo de dados para reunião processada e enriquecida por IA.
    
    Esta classe representa o resultado do processamento de uma transcrição de reunião,
    contendo tanto os metadados originais quanto as informações extraídas automaticamente
    por modelos de linguagem (LLMs). Inclui validações para garantir a qualidade dos dados.
    
    Attributes:
        meeting_id (str): Identificador único da reunião. Campo obrigatório.
        customer_id (str): Identificador único do cliente. Campo obrigatório.
        customer_name (str): Nome completo do cliente participante. Campo obrigatório.
        banker_id (str): Identificador único do banker/gerente. Campo obrigatório.
        banker_name (str): Nome completo do banker/gerente. Campo obrigatório.
        meet_type (str): Tipo/categoria da reunião (ex: vendas, onboarding, suporte). Campo obrigatório.
        meet_date (datetime): Data e hora em que a reunião ocorreu. Campo obrigatório.
        summary (str): Resumo executivo da reunião gerado por IA. 
                      Deve conter entre 100-200 palavras (validado automaticamente).
        key_points (List[str]): Lista dos pontos-chave discutidos na reunião.
                                Principais insights e decisões importantes.
        action_items (List[str]): Lista de ações/tarefas identificadas durante a reunião.
                                  Itens que requerem follow-up ou execução.
        topics (List[str]): Lista de tópicos/assuntos abordados na reunião.
                           Categorização temática do conteúdo discutido.
        source (Literal["lftm-challenge"]): Identificador da origem dos dados.
                                           Valor padrão: "lftm-challenge".
        idempotency_key (str): Chave única para garantir idempotência no processamento.
                              Evita processamento duplicado da mesma reunião.
        transcript_ref (Optional[str]): Referência ou caminho para a transcrição original.
                                       Útil para rastreabilidade. Campo opcional.
        duration_sec (Optional[int]): Duração da reunião em segundos.
                                     Campo opcional para análises de tempo.
    
    Validations:
        - O campo `summary` é validado automaticamente para conter entre 100-200 palavras.
        - Se o resumo não atender ao critério, uma ValueError é lançada.
    
    Example:
        >>> meeting = ExtractedMeeting(
        ...     meeting_id="MTG123",
        ...     customer_id="CUST456",
        ...     customer_name="João Silva",
        ...     banker_id="BNK789",
        ...     banker_name="Maria Santos",
        ...     meet_type="vendas",
        ...     meet_date=datetime(2024, 1, 15, 10, 30),
        ...     summary="Reunião de vendas focada em...",  # 100-200 palavras
        ...     key_points=["Cliente interessado em produto X", "Prazo: 30 dias"],
        ...     action_items=["Enviar proposta até sexta", "Agendar demo"],
        ...     topics=["Produtos", "Precificação", "Timeline"],
        ...     idempotency_key="abc123..."
        ... )
    """
    
    # Campos obrigatórios - Metadados da reunião
    meeting_id: str
    customer_id: str
    customer_name: str
    banker_id: str
    banker_name: str
    meet_type: str
    meet_date: datetime or str
    
    # Campos obrigatórios - Dados extraídos por IA
    summary: str  # Validado para ter 100-200 palavras
    key_points: List[str]
    action_items: List[str]
    topics: List[str]
    
    # Campos obrigatórios - Metadados de controle
    source: Literal["lftm-challenge"] = "lftm-challenge"
    idempotency_key: Optional[str] = None
    
    # Campos opcionais - Informações complementares
    transcript_ref: Optional[str] = None
    duration_sec: Optional[int] = None

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
        
        Example:
            >>> # Resumo muito curto - FALHA
            >>> ExtractedMeeting(summary="Breve resumo", ...)
            ValueError: summary deve ter 100-200 palavras, tem 2
            
            >>> # Resumo no tamanho correto - SUCESSO
            >>> ExtractedMeeting(summary="Texto com 150 palavras...", ...)
            # OK
        
        Note:
            A contagem considera palavras separadas por espaço em branco.
            Palavras compostas ou hifenizadas são contadas como uma única palavra.
        """
        # Conta o número de palavras dividindo o texto por espaços
        wc = len(summary.split())
        
        # Valida se a contagem está no intervalo permitido
        if wc < 100 or wc > 200:
            raise ValueError(f"summary deve ter 100-200 palavras, tem {wc}")
        
        # Retorna o valor validado
        return summary

