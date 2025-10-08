"""
Schemas comuns compartilhados entre Extractor e Analyzer.

Este módulo contém as classes Pydantic que são reutilizadas por ambas
as features de extração e análise de reuniões.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, model_validator
import hashlib


# ============================================================================
# METADATA E RAW SCHEMAS
# ============================================================================


class Metadata(BaseModel):
    """
    Metadados opcionais da reunião fornecidos pelo cliente.
    
    Esta classe representa os metadados estruturados de uma reunião que podem ser
    fornecidos opcionalmente pelo cliente junto com a transcrição. Quando fornecidos,
    estes dados são considerados como "fonte da verdade" e têm prioridade sobre
    qualquer informação que possa ser extraída da transcrição por IA.
    
    Attributes:
        meeting_id (Optional[str]): Identificador único da reunião.
        customer_id (Optional[str]): Identificador único do cliente.
        customer_name (Optional[str]): Nome completo do cliente participante.
        banker_id (Optional[str]): Identificador único do banker/gerente.
        banker_name (Optional[str]): Nome completo do banker/gerente responsável.
        meet_type (Optional[str]): Tipo/categoria da reunião.
        meet_date (Optional[datetime]): Data e hora da reunião em formato ISO 8601.
    """
    meeting_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    banker_id: Optional[str] = None
    banker_name: Optional[str] = None
    meet_type: Optional[str] = None
    meet_date: Optional[datetime] = None


class RawMeeting(BaseModel):
    """
    Formato bruto de reunião vindo diretamente de sistemas upstream.
    
    Esta classe representa o schema completo de uma reunião no formato original
    utilizado por sistemas de captura/transcrição, como o arquivo transcricao.json.
    
    Attributes:
        meet_id (str): Identificador único da reunião.
        customer_id (str): Identificador único do cliente.
        customer_name (str): Nome completo do cliente.
        customer_email (Optional[str]): Email do cliente.
        banker_id (str): Identificador único do banker.
        banker_name (str): Nome completo do banker.
        meet_date (datetime): Data e hora da reunião (ISO 8601).
        meet_type (str): Tipo/categoria da reunião.
        meet_transcription (str): Texto completo da transcrição.
    """
    meet_id: str
    customer_id: str
    customer_name: str
    customer_email: Optional[str] = None
    banker_id: str
    banker_name: str
    meet_date: datetime
    meet_type: str
    meet_transcription: str



class MeetingRequest(BaseModel):
    """
    Schema de validação para requisições aos endpoints POST /extract e POST /analyze.
    
    Esta classe é compartilhada por ambos os serviços,
    pois ambos aceitam exatamente os mesmos formatos de entrada. A única diferença está
    no processamento interno e no formato da resposta.
    
    Esta classe suporta dois formatos mutuamente exclusivos para entrada:
    
    **Formato A: Transcrição + Metadados Separados**
    Ideal para quando a transcrição é texto puro e metadados vêm de outra fonte
    (ex: sistema de agendamento fornece metadados, sistema de transcrição fornece texto).
    
    Campos:
    - `transcript` (str, obrigatório): Texto completo da transcrição da reunião.
    - `metadata` (Metadata, opcional): Metadados estruturados da reunião.
      Quando fornecidos, têm prioridade absoluta sobre qualquer informação
      que possa ser extraída da transcrição por IA.
    
    Exemplo:
    ```json
    {
      "transcript": "Cliente: Bom dia... Banker: Olá...",
      "metadata": {
        "meeting_id": "MTG123",
        "customer_id": "CUST456",
        "customer_name": "ACME S.A.",
        "banker_id": "BKR789",
        "banker_name": "Pedro Falcão",
        "meet_type": "Primeira Reunião",
        "meet_date": "2025-09-10T14:30:00Z"
      }
    }
    ```
    
    **Formato B: Reunião Bruta Completa**
    Ideal para quando se possui um JSON completo da reunião vindo diretamente
    de sistemas upstream (ex: arquivo transcricao.json de sistemas de captura).
    
    Campos:
    - `raw_meeting` (RawMeeting, obrigatório): Objeto completo contendo todos
      os dados brutos da reunião, incluindo transcrição e metadados em um
      único objeto estruturado.
    
    Exemplo:
    ```json
    {
      "raw_meeting": {
        "meet_id": "MTG123",
        "customer_id": "CUST456",
        "customer_name": "ACME S.A.",
        "banker_id": "BKR789",
        "banker_name": "Pedro Falcão",
        "meet_date": "2025-09-10T14:30:00Z",
        "meet_type": "Primeira Reunião",
        "meet_transcription": "Cliente: Bom dia..."
      }
    }
    ```
    
    **Validação de Exclusividade Mútua (XOR):**
    - É obrigatório fornecer EXATAMENTE UM dos dois formatos (`transcript` OU `raw_meeting`).
    - Não é permitido enviar ambos os formatos simultaneamente.
    - Não é permitido não enviar nenhum dos formatos.
    - A validação ocorre automaticamente via `@model_validator` do Pydantic.
    
    Raises:
        ValueError: Se a condição de exclusividade (XOR) não for satisfeita.
                   Ou seja, se fornecer ambos os formatos ou nenhum dos formatos.
    
    Usage:
        O FastAPI usa este schema automaticamente para validar o corpo JSON das requisições.
        Em caso de erro de validação, o FastAPI retorna automaticamente um status
        422 (Unprocessable Entity) sem executar a função do endpoint.
    
    Example:
        >>> # Formato A - válido
        >>> request = MeetingRequest(
        ...     transcript="Cliente: Olá...",
        ...     metadata=Metadata(meeting_id="MTG123")
        ... )
        
        >>> # Formato B - válido
        >>> request = MeetingRequest(
        ...     raw_meeting=RawMeeting(
        ...         meet_id="MTG123",
        ...         customer_id="CUST456",
        ...         # ... demais campos
        ...     )
        ... )
        
        >>> # Ambos formatos - INVÁLIDO (lança ValueError)
        >>> request = MeetingRequest(
        ...     transcript="...",
        ...     raw_meeting=RawMeeting(...)
        ... )
        
        >>> # Nenhum formato - INVÁLIDO (lança ValueError)
        >>> request = MeetingRequest()
    
    Note:
        Esta classe substitui e unifica as antigas classes ExtractRequest e AnalyzeRequest,
        que eram duplicatas. ExtractRequest e AnalyzeRequest agora são aliases desta classe.
    """
    
    transcript: Optional[str] = None
    metadata: Optional[Metadata] = None
    raw_meeting: Optional[RawMeeting] = None

    @model_validator(mode='after')
    def validate_exclusive_fields(self):
        """
        Valida exclusividade mútua: exatamente um formato (transcript XOR raw_meeting).
        
        Raises:
            ValueError: Se ambos os formatos ou nenhum formato forem fornecidos.
        """
        has_transcript = self.transcript is not None
        has_raw = self.raw_meeting is not None
        
        if not (has_transcript ^ has_raw):
            raise ValueError(
                "Forneça 'transcript' OU 'raw_meeting', não ambos nem nenhum"
            )
        
        return self
    
    def to_normalized(self) -> "NormalizedInput":
        """
        Converte o MeetingRequest para NormalizedInput.
        
        Este método normaliza os dois formatos de entrada suportados
        (transcript+metadata ou raw_meeting) para um formato único
        interno (NormalizedInput) usado pelos extractors e analyzers.
        
        Lógica de conversão:
        
        **Se raw_meeting fornecido:**
        - Extrai campos diretamente do objeto raw_meeting
        - Mapeia meet_id → meeting_id
        - Mapeia meet_transcription → transcript
        - Demais campos mantêm os mesmos nomes
        
        **Se transcript fornecido:**
        - Usa transcript diretamente
        - Extrai metadados do objeto metadata (se fornecido)
        - Se metadata for None, cria um Metadata vazio (todos campos None)
        
        Returns:
            NormalizedInput: Objeto normalizado pronto para processamento
                           pelos extractors ou analyzers.
        
        Note:
            Este método é chamado automaticamente pelos endpoints /extract e /analyze
            após a validação bem-sucedida do request body pelo Pydantic.
        """
        if self.raw_meeting:
            # Formato raw_meeting → converte para NormalizedInput
            return NormalizedInput(
                transcript=self.raw_meeting.meet_transcription,
                meeting_id=self.raw_meeting.meet_id,
                customer_id=self.raw_meeting.customer_id,
                customer_name=self.raw_meeting.customer_name,
                banker_id=self.raw_meeting.banker_id,
                banker_name=self.raw_meeting.banker_name,
                meet_type=self.raw_meeting.meet_type,
                meet_date=self.raw_meeting.meet_date,
            )
        else:
            # Formato transcript + metadata → converte para NormalizedInput
            metadata = self.metadata or Metadata()
            return NormalizedInput(
                transcript=self.transcript,
                meeting_id=metadata.meeting_id,
                customer_id=metadata.customer_id,
                customer_name=metadata.customer_name,
                banker_id=metadata.banker_id,
                banker_name=metadata.banker_name,
                meet_type=metadata.meet_type,
                meet_date=metadata.meet_date,
            )





# ============================================================================
# NORMALIZED INPUT (interno, após normalização)
# ============================================================================


class NormalizedInput(BaseModel):
    """
    Modelo normalizado para dados de reunião entre cliente e banker.
    
    Esta classe unifica diferentes formatos de entrada (transcript+metadata ou raw_meeting)
    em uma estrutura padrão interna, validando os tipos de dados e facilitando o
    processamento downstream pelos extractors e analyzers.
    
    É o formato intermediário usado internamente por:
    - extract_meeting_chain() no extractor.py (Feature Extractor)
    - analyze_sentiment_chain() no analyzer.py (Feature Analyzer)
    
    Attributes:
        transcript (str): Texto completo da transcrição da reunião. Campo obrigatório.
                         Contém o diálogo completo entre cliente e banker.
        
        meeting_id (Optional[str]): Identificador único da reunião.
                                   Se fornecido, é usado no cálculo da idempotency_key.
                                   Se None, o LLM tentará extrair da transcrição.
        
        customer_id (Optional[str]): Identificador único do cliente.
                                    Crucial para cálculo da chave de idempotência.
                                    Se None, o LLM tentará extrair da transcrição.
        
        customer_name (Optional[str]): Nome completo do cliente participante da reunião.
                                      Se None, o LLM tentará extrair da transcrição.
        
        banker_id (Optional[str]): Identificador único do banker/gerente responsável.
                                  Se None, o LLM tentará extrair da transcrição.
        
        banker_name (Optional[str]): Nome completo do banker/gerente.
                                     Se None, o LLM tentará extrair da transcrição.
        
        meet_type (Optional[str]): Tipo/categoria da reunião.
                                  Exemplos: "Primeira Reunião", "Acompanhamento", "Fechamento"
                                  Se None, o LLM tentará extrair da transcrição.
        
        meet_date (Optional[datetime]): Data e hora da reunião em formato ISO 8601.
                                       Necessário para cálculo de idempotência.
                                       Se None, o LLM tentará extrair da transcrição.
    
    Note:
        Campos opcionais (meeting_id, customer_id, etc):
        - Se fornecidos: têm prioridade absoluta (são considerados "fonte da verdade")
        - Se None: o LLM tentará extrair automaticamente da transcrição
        
        Para garantir idempotência e precisão máxima, recomenda-se fornecer ao menos:
        - meeting_id
        - customer_id
        - meet_date
    
    Example:
        >>> # Criação direta (menos comum, geralmente vem do to_normalized())
        >>> normalized = NormalizedInput(
        ...     transcript="Cliente: Bom dia... Banker: Olá...",
        ...     meeting_id="MTG123",
        ...     customer_id="CUST456",
        ...     meet_date=datetime(2025, 9, 10, 14, 30)
        ... )
        
        >>> # Uso comum: criado via MeetingRequest.to_normalized()
        >>> request = MeetingRequest(transcript="...", metadata=Metadata(...))
        >>> normalized = request.to_normalized()
        
        >>> # Processamento
        >>> extracted = await extract_meeting_chain(normalized, request_id="req-123")
    """
    
    transcript: str
    meeting_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    banker_id: Optional[str] = None
    banker_name: Optional[str] = None
    meet_type: Optional[str] = None
    meet_date: Optional[datetime] = None

    @classmethod
    def from_raw_meeting(cls, raw: dict):
        """Cria uma instância a partir de um dicionário de reunião bruto."""
        return cls(
            transcript=raw.get("meet_transcription", ""),
            meeting_id=raw.get("meet_id"),
            customer_id=raw.get("customer_id"),
            customer_name=raw.get("customer_name"),
            banker_id=raw.get("banker_id"),
            banker_name=raw.get("banker_name"),
            meet_type=raw.get("meet_type"),
            meet_date=raw.get("meet_date"),
        )

    @classmethod
    def from_transcript_metadata(cls, transcript: str, metadata: dict):
        """Cria uma instância a partir de transcrição e metadados separados."""
        return cls(
            transcript=transcript,
            meeting_id=metadata.get("meeting_id"),
            customer_id=metadata.get("customer_id"),
            customer_name=metadata.get("customer_name"),
            banker_id=metadata.get("banker_id"),
            banker_name=metadata.get("banker_name"),
            meet_type=metadata.get("meet_type"),
            meet_date=metadata.get("meet_date"),
        )

    def compute_idempotency_key(self) -> Optional[str]:
        """
        Gera uma chave de idempotência única para a reunião.
        
        A chave é criada através de um hash SHA-256 da combinação de
        meeting_id + meet_date + customer_id.
        
        Returns:
            Optional[str]: String hexadecimal de 64 caracteres (SHA-256),
                          ou None se campos obrigatórios estiverem ausentes.
        """
        if not (self.meeting_id and self.meet_date and self.customer_id):
            return None
        
        base = f"{self.meeting_id}{self.meet_date.isoformat()}{self.customer_id}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()


