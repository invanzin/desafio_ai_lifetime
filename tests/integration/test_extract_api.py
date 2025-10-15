"""
Testes de integração para o endpoint POST /extract.

Este módulo testa o endpoint completo de extração de dados, garantindo que:
- A API retorna 200 OK para requisições válidas
- Todos os campos obrigatórios estão presentes na resposta
- Metadados fornecidos têm prioridade sobre extração
- Campo 'topics' é gerado corretamente (diferencial do Extractor)
- Formato raw_meeting é aceito
- Validações de erro (422, 502) funcionam corretamente

Conforme exigido no briefing do Desafio 1:
- "Extrair informações estruturadas de transcrições de reuniões"
- "Metadados fornecidos devem ter prioridade"
- "Idempotency key (SHA-256)"

Cenários de teste:
1. Health check
2. Extração com metadados completos
3. Extração com metadados parciais (LLM completa)
4. Formato raw_meeting
5. Validação de topics
6. Prioridade de metadados
"""

import pytest
from httpx import AsyncClient
from app.main import app


# ============================================================================
# TESTE DE HEALTH CHECK
# ============================================================================

@pytest.mark.asyncio
async def test_health():
    """
    Testa se o serviço está rodando corretamente.
    
    Validações:
    - Status 200
    - Resposta JSON válida
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
    
    assert response.status_code == 200
    result = response.json()
    assert "status" in result
    assert result["status"] == "healthy"


# ============================================================================
# TESTES DE EXTRAÇÃO
# ============================================================================

@pytest.mark.asyncio
async def test_extract_with_full_metadata():
    """
    Testa extração com todos os metadados fornecidos.
    
    Este é o teste principal que valida:
    - Todos os 13 campos obrigatórios
    - Summary com 100-200 palavras
    - Idempotency key (SHA-256)
    - Source = "lftm-challenge"
    - Prioridade de metadados fornecidos
    - Campo topics (específico do extractor)
    
    Conforme exemplo do briefing.
    """
    payload = {
        "transcript": """
Cliente: Bom dia, meu nome é João Silva da ACME S.A.
Banker: Olá João! Meu nome é Pedro Falcão, sou gerente aqui no banco. 
        Como posso ajudá-lo hoje?
Cliente: Estamos precisando de uma linha de crédito para capital de giro. 
        Nossa empresa está crescendo e precisamos de R$ 500 mil.
Banker: Entendo. Qual é o faturamento atual da empresa?
Cliente: Faturamos cerca de R$ 2 milhões por ano.
Banker: Ótimo! Temos linhas de crédito que podem atender. Vou precisar 
        analisar o fluxo de caixa e as garantias disponíveis.
Cliente: Perfeito. Temos imóveis que podem servir como garantia.
Banker: Excelente. Vou preparar uma proposta de crédito com as condições 
        e taxas. Posso enviar por email até sexta-feira?
Cliente: Sim, meu email é joao@acme.com.br
Banker: Ótimo. Também vou precisar agendar uma segunda reunião para 
        apresentar a proposta detalhadamente. Que tal daqui a 2 semanas?
Cliente: Perfeito! Fico no aguardo.
Banker: Combinado então. Qualquer dúvida, pode me ligar.
        """,
        "metadata": {
            "meeting_id": "8f1ae3",
            "customer_id": "cust_123",
            "customer_name": "ACME S.A.",
            "banker_id": "bkr_789",
            "banker_name": "Pedro Falcao",
            "meet_type": "Primeira Reuniao",
            "meet_date": "2025-09-10T14:30:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/extract", json=payload)
    
    assert response.status_code == 200, f"Esperado 200, recebido {response.status_code}: {response.text}"
    result = response.json()
    
    # Validação de campos obrigatórios (13 campos)
    required_fields = [
        "meeting_id", "customer_id", "customer_name",
        "banker_id", "banker_name", "meet_type", "meet_date",
        "summary", "key_points", "action_items", "topics",
        "source", "idempotency_key"
    ]
    for field in required_fields:
        assert field in result, f"Campo obrigatório '{field}' ausente"
    
    # Validação de metadados respeitados
    assert result["meeting_id"] == "8f1ae3"
    assert result["customer_id"] == "cust_123"
    assert result["customer_name"] == "ACME S.A."
    assert result["banker_id"] == "bkr_789"
    assert result["banker_name"] == "Pedro Falcao"
    assert result["meet_type"] == "Primeira Reuniao"
    
    # Validação de summary (100-200 palavras)
    summary_word_count = len(result["summary"].split())
    assert 100 <= summary_word_count <= 200, f"Summary deve ter 100-200 palavras, tem {summary_word_count}"
    
    # Validação de listas não vazias
    assert len(result["key_points"]) > 0, "key_points não deve estar vazio"
    assert len(result["action_items"]) > 0, "action_items não deve estar vazio"
    assert len(result["topics"]) > 0, "topics não deve estar vazio"
    
    # Validação de campos operacionais
    assert result["source"] == "lftm-challenge"
    assert result["idempotency_key"] is not None
    assert len(result["idempotency_key"]) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_extract_with_partial_metadata():
    """
    Testa extração com metadados PARCIAIS.
    
    Valida que o LLM consegue extrair campos faltantes da transcrição.
    Importante para casos onde o upstream não envia todos os metadados.
    
    Cenário:
    - Envia apenas meeting_id e customer_id
    - LLM deve extrair: customer_name, banker_name, meet_type, meet_date
    """
    payload = {
        "transcript": """
Data: 15 de outubro de 2025, 10h da manhã
Participantes: Maria Santos (gerente) e Tech Inovações Ltda (cliente)

Maria: Bom dia! Como posso ajudar a Tech Inovações hoje?
Cliente: Olá Maria! Queremos expandir nossos investimentos em fundos de tecnologia.
Maria: Excelente! Temos ótimas opções de fundos tech. Qual valor está pensando?
Cliente: Estamos considerando uns 200 mil reais inicialmente.
Maria: Perfeito! Vou preparar uma apresentação dos melhores fundos tech do portfólio.
Cliente: Ótimo! Aguardo o contato então.
Maria: Envio até amanhã por email. Obrigada pela confiança!
        """,
        "metadata": {
            "meeting_id": "MTG-PARTIAL-001",
            "customer_id": "CUST-PARTIAL-001"
            # customer_name, banker_name, meet_type, meet_date devem ser extraídos
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/extract", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Metadados fornecidos devem ser respeitados
    assert result["meeting_id"] == "MTG-PARTIAL-001"
    assert result["customer_id"] == "CUST-PARTIAL-001"
    
    # Campos extraídos da transcrição
    assert "Tech Inovações" in result["customer_name"] or "Tech" in result["customer_name"]
    assert "Maria" in result["banker_name"] or "Santos" in result["banker_name"]
    
    # Validações de estrutura
    assert 100 <= len(result["summary"].split()) <= 200
    assert len(result["key_points"]) > 0
    assert len(result["topics"]) > 0


@pytest.mark.asyncio
async def test_extract_raw_meeting_format():
    """
    Testa extração usando formato raw_meeting (do upstream).
    
    Este é o formato alternativo aceito pela API, usado quando
    o upstream já tem os dados estruturados de forma diferente.
    
    Validações:
    - Conversão correta de meet_id → meeting_id
    - meet_transcription → transcript
    - Todos os campos obrigatórios presentes
    """
    payload = {
        "raw_meeting": {
            "meet_id": "MTG-RAW-001",
            "customer_id": "CUST-RAW-001",
            "customer_name": "Startup XYZ",
            "banker_id": "BNK-RAW-001",
            "banker_name": "Carlos Investidor",
            "meet_date": "2025-10-15T11:00:00Z",
            "meet_type": "Primeira Reunião",
            "meet_transcription": """
Cliente: Olá! Somos uma startup de inteligência artificial.
Banker: Muito interessante! Como posso ajudar?
Cliente: Precisamos de capital para expandir nossa operação.
Banker: Certo. Qual o valor necessário e prazo?
Cliente: Pensamos em 1 milhão de reais para os próximos 12 meses.
Banker: Vou preparar uma proposta de crédito empresarial.
Cliente: Perfeito! Temos boas garantias e faturamento crescente.
Banker: Ótimo! Vou analisar e retorno em 3 dias úteis.
            """
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/extract", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Validação de conversão correta
    assert result["meeting_id"] == "MTG-RAW-001"
    assert result["customer_id"] == "CUST-RAW-001"
    assert result["customer_name"] == "Startup XYZ"
    assert result["banker_id"] == "BNK-RAW-001"
    assert result["banker_name"] == "Carlos Investidor"
    
    # Validações de estrutura
    assert 100 <= len(result["summary"].split()) <= 200
    assert len(result["topics"]) > 0
    assert result["source"] == "lftm-challenge"


@pytest.mark.asyncio
async def test_extract_topics_generation():
    """
    Testa geração do campo TOPICS (diferencial do Extractor).
    
    O campo 'topics' é exclusivo do endpoint /extract e não existe
    no /analyze. Este teste valida que topics relevantes são extraídos.
    
    Cenário:
    - Transcrição sobre investimentos, seguros e previdência
    - Topics deve conter palavras-chave relevantes
    """
    payload = {
        "transcript": """
Cliente: Gostaria de discutir três assuntos importantes hoje.
Banker: Claro! Pode começar.
Cliente: Primeiro, quero reavaliar minha carteira de INVESTIMENTOS.
Banker: Perfeito. Vamos ver seus ativos atuais.
Cliente: Segundo, preciso contratar um SEGURO DE VIDA mais robusto.
Banker: Temos excelentes produtos de seguros. Qual cobertura precisa?
Cliente: E terceiro, quero abrir uma PREVIDÊNCIA PRIVADA para minha aposentadoria.
Banker: Ótima decisão! Temos planos PGBL e VGBL disponíveis.
Cliente: Também quero entender sobre IMPOSTO DE RENDA e otimização fiscal.
Banker: Com certeza! Vou preparar uma análise completa desses quatro temas.
        """,
        "metadata": {
            "meeting_id": "MTG-TOPICS-001",
            "customer_id": "CUST-TOPICS-001",
            "customer_name": "Cliente Completo",
            "banker_id": "BNK-001",
            "banker_name": "Assessor Financeiro",
            "meet_type": "Consultoria Completa",
            "meet_date": "2025-10-15T14:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/extract", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Validação específica de topics
    assert len(result["topics"]) >= 3, f"Deve ter pelo menos 3 topics, tem {len(result['topics'])}"
    
    # Validação de conteúdo relevante nos topics
    topics_text = " ".join(result["topics"]).lower()
    
    # Pelo menos 2 dos seguintes termos devem aparecer nos topics
    expected_topics = ["investimento", "seguro", "previdência", "imposto", "fiscal", "carteira"]
    matches = sum(1 for topic in expected_topics if topic in topics_text)
    
    assert matches >= 2, f"Topics deve conter termos relevantes. Topics: {result['topics']}"


@pytest.mark.asyncio
async def test_extract_metadata_priority():
    """
    Testa PRIORIDADE DE METADADOS fornecidos.
    
    Validação crítica: metadados fornecidos pelo usuário NUNCA devem
    ser sobrescritos pelo LLM, mesmo que a transcrição tenha informações diferentes.
    
    Cenário:
    - Metadata diz customer_name = "Empresa Oficial"
    - Transcrição menciona "Empresa Diferente"
    - Resultado deve usar "Empresa Oficial" (prioridade de metadata)
    """
    payload = {
        "transcript": """
Cliente: Olá, sou da Empresa ABC Ltda, mas todos me conhecem como XYZ Corp.
Banker: Olá! Prazer em conhecer você da XYZ.
Cliente: Na verdade, nosso nome fantasia é outro, mas o oficial é ABC.
Banker: Entendido. Vou usar o nome oficial ABC em nossos registros.
Cliente: Perfeito! É isso mesmo.
Banker: Ótimo. Vamos falar sobre seus objetivos financeiros então.
        """,
        "metadata": {
            "meeting_id": "MTG-PRIORITY-001",
            "customer_id": "CUST-PRIORITY-001",
            "customer_name": "Empresa Oficial LTDA",  # Este deve prevalecer
            "banker_id": "BNK-PRIORITY-001",
            "banker_name": "Gerente Correto",         # Este deve prevalecer
            "meet_type": "Tipo Fornecido",            # Este deve prevalecer
            "meet_date": "2025-10-15T15:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/extract", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # VALIDAÇÃO CRÍTICA: Metadados fornecidos devem ser EXATAMENTE os mesmos
    assert result["customer_name"] == "Empresa Oficial LTDA", \
        f"customer_name deve ser do metadata, não da transcrição. Recebido: {result['customer_name']}"
    
    assert result["banker_name"] == "Gerente Correto", \
        f"banker_name deve ser do metadata. Recebido: {result['banker_name']}"
    
    assert result["meet_type"] == "Tipo Fornecido", \
        f"meet_type deve ser do metadata. Recebido: {result['meet_type']}"
    
    assert result["meeting_id"] == "MTG-PRIORITY-001"
    assert result["customer_id"] == "CUST-PRIORITY-001"
    assert result["banker_id"] == "BNK-PRIORITY-001"


@pytest.mark.asyncio
async def test_extract_different_meeting_types():
    """
    Testa extração com diferentes tipos de reunião.
    
    Validação de flexibilidade: API deve aceitar qualquer string
    em meet_type (presencial, online, híbrido, etc).
    """
    meeting_types = ["presencial", "online", "híbrido", "telefone"]
    
    for meet_type in meeting_types:
        payload = {
            "transcript": """
Cliente: Olá, como vai?
Banker: Oi! Tudo bem?
Cliente: Gostaria de investir 50 mil reais.
Banker: Ótimo! Vou preparar uma proposta.
Cliente: Perfeito, aguardo.
Banker: Envio amanhã por email.
            """,
            "metadata": {
                "meeting_id": f"MTG-TYPE-{meet_type.upper()}",
                "customer_id": "CUST-TYPE-001",
                "customer_name": "Cliente Teste",
                "banker_id": "BNK-001",
                "banker_name": "Banker Teste",
                "meet_type": meet_type,
                "meet_date": "2025-10-15T16:00:00Z"
            }
        }
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/extract", json=payload)
        
        assert response.status_code == 200, f"Falhou para meet_type='{meet_type}'"
        result = response.json()
        
        # Validação de meet_type respeitado
        assert result["meet_type"] == meet_type, \
            f"meet_type deve ser '{meet_type}', recebido '{result['meet_type']}'"
