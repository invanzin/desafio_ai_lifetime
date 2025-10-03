from typing import Optional, List, Literal, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
import hashlib


# ============================================================================
# REQUEST SCHEMAS (entrada da API)
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
            Se fornecido, será usado para cálculo de idempotência.
        customer_id (Optional[str]): Identificador único do cliente.
            Crucial para cálculo da chave de idempotência.
        customer_name (Optional[str]): Nome completo do cliente participante.
        banker_id (Optional[str]): Identificador único do banker/gerente.
        banker_name (Optional[str]): Nome completo do banker/gerente responsável.
        meet_type (Optional[str]): Tipo/categoria da reunião.
            Exemplos: "Primeira Reunião", "Acompanhamento", "Fechamento"
        meet_date (Optional[datetime]): Data e hora da reunião em formato ISO 8601.
            Necessário para cálculo de idempotência.
    
    Note:
        Todos os campos são opcionais. Se ausentes, o sistema tentará extrair
        estas informações da transcrição usando IA. No entanto, para garantir
        idempotência e precisão máxima, recomenda-se fornecer ao menos:
        - meeting_id
        - customer_id
        - meet_date
    
    Example:
        >>> metadata = Metadata(
        ...     meeting_id="MTG123",
        ...     customer_id="CUST456",
        ...     customer_name="João Silva",
        ...     banker_name="Maria Santos",
        ...     meet_type="Vendas",
        ...     meet_date=datetime(2025, 9, 10, 14, 30)
        ... )
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
    Difere do formato de metadados separados por incluir a transcrição completa
    em um único objeto estruturado.
    
    Mapeamento de campos:
    - meet_id → meeting_id (normalizado)
    - meet_transcription → transcript (normalizado)
    - Demais campos mantêm o mesmo significado
    
    Attributes:
        meet_id (str): Identificador único da reunião. Campo obrigatório.
        customer_id (str): Identificador único do cliente. Campo obrigatório.
        customer_name (str): Nome completo do cliente. Campo obrigatório.
        customer_email (Optional[str]): Email do cliente. Campo opcional.
        banker_id (str): Identificador único do banker. Campo obrigatório.
        banker_name (str): Nome completo do banker. Campo obrigatório.
        meet_date (datetime): Data e hora da reunião (ISO 8601). Campo obrigatório.
        meet_type (str): Tipo/categoria da reunião. Campo obrigatório.
        meet_transcription (str): Texto completo da transcrição. Campo obrigatório.
    
    Example:
        >>> raw = RawMeeting(
        ...     meet_id="7541064ef4a",
        ...     customer_id="02ae981fbade",
        ...     customer_name="Gabriel Teste",
        ...     customer_email="gabriel@example.com",
        ...     banker_id="1cc87e-0729-467f-a2c0",
        ...     banker_name="Ana Silva Santos",
        ...     meet_date=datetime(2025, 9, 22, 17, 0),
        ...     meet_type="Reunião de Acompanhamento de Carteira",
        ...     meet_transcription="Cliente: Olá..."
        ... )
    
    Note:
        Este formato é ideal quando você possui um arquivo JSON completo
        da reunião (ex: transcricao.json) e deseja enviá-lo como está,
        sem necessidade de separar transcrição e metadados.
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


class ExtractRequest(BaseModel):
    """
    Schema de validação para requisições ao endpoint POST /extract.
    
    Esta classe suporta dois formatos mutuamente exclusivos para entrada:
    
    **Formato A: Transcrição + Metadados Separados**
    Ideal para quando a transcrição é texto puro e metadados vêm de outra fonte.
    - `transcript` (str, obrigatório): Texto da transcrição.
    - `metadata` (Metadata, opcional): Metadados estruturados da reunião.
    
    **Formato B: Reunião Bruta Completa**
    Ideal para quando se possui um JSON completo da reunião (ex: transcricao.json).
    - `raw_meeting` (RawMeeting, obrigatório): Objeto completo com dados brutos da reunião.
    
    **Validação de Exclusividade Mútua (XOR):**
    - É obrigatório fornecer EXATAMENTE UM dos dois formatos (`transcript` OU `raw_meeting`).
    - Não é permitido enviar ambos nem nenhum dos formatos.
    - A validação ocorre automaticamente via `@model_validator`.
    
    Raises:
        ValueError: Se a condição de exclusividade (XOR) não for satisfeita.
    
    Usage:
        O FastAPI usa este schema automaticamente para validar o corpo JSON das requisições.
        Em caso de erro, o FastAPI retorna um status 422 (Unprocessable Entity).
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
        Converte o ExtractRequest para NormalizedInput.
        
        Este método normaliza os dois formatos de entrada suportados
        (transcript+metadata ou raw_meeting) para um formato único
        interno (NormalizedInput) usado pelo extractor.
        
        Lógica de conversão:
        - Se raw_meeting: extrai campos diretamente do objeto raw_meeting
        - Se transcript: usa transcript + metadados opcionais
        
        Returns:
            NormalizedInput: Objeto normalizado pronto para processamento
        
        Example:
            >>> request = ExtractRequest(transcript="...", metadata=Metadata(...))
            >>> normalized = request.to_normalized()
            >>> # Agora pode ser passado para extract_meeting_chain()
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
    
    Esta classe unifica diferentes formatos de entrada em uma estrutura padrão,
    validando os tipos de dados e facilitando o processamento downstream.
    Utiliza Pydantic para validação automática e serialização.
    
    Attributes:
        transcript (str): Texto completo da transcrição da reunião.
        meeting_id (Optional[str]): Identificador único da reunião.
        customer_id (Optional[str]): Identificador único do cliente.
        customer_name (Optional[str]): Nome completo do cliente.
        banker_id (Optional[str]): Identificador único do banker/gerente.
        banker_name (Optional[str]): Nome completo do banker/gerente.
        meet_type (Optional[str]): Tipo/categoria da reunião (ex: vendas, suporte, etc).
        meet_date (Optional[datetime]): Data e hora da reunião.
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
        """
        Cria uma instância a partir de um dicionário de reunião bruto.
        
        Este método factory converte dados brutos de uma reunião (geralmente vindos
        de uma API ou banco de dados) para o formato normalizado. Mapeia os campos
        específicos do formato bruto para os campos padronizados desta classe.
        
        Args:
            raw (dict): Dicionário contendo os dados brutos da reunião.
                Campos esperados:
                - meet_transcription: texto da transcrição
                - meet_id: ID da reunião
                - customer_id: ID do cliente
                - customer_name: nome do cliente
                - banker_id: ID do banker
                - banker_name: nome do banker
                - meet_type: tipo de reunião
                - meet_date: data da reunião
        
        Returns:
            NormalizedInput: Instância do modelo com os dados normalizados.
        
        Example:
            >>> raw_data = {
            ...     "meet_transcription": "Cliente: Olá...",
            ...     "meet_id": "MTG123",
            ...     "customer_id": "CUST456"
            ... }
            >>> normalized = NormalizedInput.from_raw_meeting(raw_data)
        """
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
        """
        Cria uma instância a partir de transcrição e metadados separados.
        
        Útil quando a transcrição vem separada dos metadados da reunião,
        por exemplo, quando o texto é processado por um serviço de transcrição
        e os metadados vêm de outra fonte.
        
        Args:
            transcript (str): Texto completo da transcrição da reunião.
            metadata (dict): Dicionário com os metadados da reunião.
                Campos esperados:
                - meeting_id: ID da reunião
                - customer_id: ID do cliente
                - customer_name: nome do cliente
                - banker_id: ID do banker
                - banker_name: nome do banker
                - meet_type: tipo de reunião
                - meet_date: data da reunião
        
        Returns:
            NormalizedInput: Instância do modelo com os dados normalizados.
        
        Example:
            >>> transcript = "Cliente: Gostaria de informações sobre..."
            >>> metadata = {"meeting_id": "MTG123", "customer_id": "CUST456"}
            >>> normalized = NormalizedInput.from_transcript_metadata(transcript, metadata)
        """
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
        
        A chave de idempotência é usada para garantir que a mesma reunião não seja
        processada múltiplas vezes. Ela é criada através de um hash SHA-256 da
        combinação de campos únicos da reunião.
        
        Processo de criação da chave:
        1. Verifica se os campos obrigatórios estão presentes (meeting_id, meet_date, customer_id)
        2. Se algum campo obrigatório estiver ausente, retorna None
        3. Concatena os campos obrigatórios em uma string base:
           "{meeting_id}{meet_date_iso}{customer_id}"
        4. Converte a string base para bytes (codificação UTF-8)
        5. Aplica o algoritmo SHA-256 para gerar um hash de 256 bits
        6. Converte o hash binário para uma string hexadecimal (64 caracteres)
        
        Returns:
            Optional[str]: String hexadecimal de 64 caracteres representando o hash SHA-256,
                          ou None se campos obrigatórios estiverem ausentes.
        
        Example:
            >>> meeting = NormalizedInput(
            ...     transcript="...",
            ...     meeting_id="MTG123",
            ...     meet_date=datetime(2024, 1, 15, 10, 30),
            ...     customer_id="CUST456"
            ... )
            >>> key = meeting.compute_idempotency_key()
            >>> # Resultado: "a1b2c3d4..." (hash SHA-256 de 64 caracteres)
        
        Note:
            A mesma combinação de meeting_id + meet_date + customer_id sempre
            gerará a mesma chave, garantindo idempotência no processamento.
        """

        if not (self.meeting_id and self.meet_date and self.customer_id):
            return None  # Retorna None se faltar algum campo obrigatório
        
        # Cria a string base concatenando os campos únicos da reunião
        base = f"{self.meeting_id}{self.meet_date.isoformat()}{self.customer_id}"
        
        # Gera o hash SHA-256:
        # 1. encode("utf-8") converte a string em bytes
        # 2. hashlib.sha256() cria o objeto hash
        # 3. hexdigest() retorna a representação hexadecimal do hash
        return hashlib.sha256(base.encode("utf-8")).hexdigest()


# ============================================================================
# RESPONSE SCHEMAS (saída da API)
# ============================================================================

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
    meet_date: datetime
    
    # Campos obrigatórios - Dados extraídos por IA
    summary: str  # Validado para ter 100-200 palavras
    key_points: List[str]
    action_items: List[str]
    topics: List[str]
    
    # Campos obrigatórios - Metadados de controle
    source: Literal["lftm-challenge"] = "lftm-challenge"
    idempotency_key: str
    
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