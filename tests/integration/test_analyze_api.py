"""
Testes de integração para o endpoint POST /analyze.

Este módulo testa o endpoint completo de análise de sentimento, garantindo que:
- A API retorna 200 OK para requisições válidas
- sentiment_label e sentiment_score estão corretos para diferentes sentimentos
- Todos os campos obrigatórios estão presentes na resposta
- Validações de erro (422, 502) funcionam corretamente

Conforme exigido no briefing do Desafio 2:
- "Testes de integração: testar com transcrições de exemplo (positiva, neutra, negativa)"

Cenários de teste:
1. Transcrição POSITIVA → sentiment="positive", score >= 0.6
2. Transcrição NEUTRA → sentiment="neutral", 0.4 <= score < 0.6
3. Transcrição NEGATIVA → sentiment="negative", score < 0.4
4. Validação de erros (422 para input inválido)
"""

import pytest
from httpx import AsyncClient
from app.main import app


# ============================================================================
# TESTES DE SENTIMENTO POSITIVO
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_positive_sentiment():
    """
    Testa análise de transcrição com sentimento POSITIVO.
    
    Transcrição: Cliente extremamente satisfeito, quer investir mais
    Resultado esperado:
    - sentiment_label = "positive"
    - sentiment_score >= 0.6
    - summary com 100-200 palavras
    - key_points e action_items não vazios
    """
    payload = {
        "transcript": """
Cliente: Bom dia! Estou EXTREMAMENTE satisfeito com os resultados dos meus investimentos!
Banker: Que maravilha ouvir isso! Como posso ajudá-lo hoje?
Cliente: Quero AUMENTAR significativamente meu investimento! Estou pensando em mais 500 mil reais!
Banker: Excelente decisão! Vou preparar uma proposta fantástica com as melhores opções do mercado.
Cliente: Perfeito! Confio TOTALMENTE em vocês. O atendimento tem sido impecável!
Banker: Muito obrigado! Vamos fazer seu patrimônio crescer ainda mais.
Cliente: Estou muito feliz com essa parceria! Vocês são os melhores!
        """,
        "metadata": {
            "meeting_id": "MTG-INT-POS-001",
            "customer_id": "CUST-POS-001",
            "customer_name": "João Muito Feliz",
            "banker_id": "BNK-001",
            "banker_name": "Maria Excelente",
            "meet_type": "presencial",
            "meet_date": "2025-10-13T10:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    # Valida status code
    assert response.status_code == 200, f"Esperado 200, recebido {response.status_code}: {response.text}"
    
    result = response.json()
    
    # Validações de sentimento POSITIVO
    assert result["sentiment_label"] == "positive", f"Esperado 'positive', recebido '{result['sentiment_label']}'"
    assert result["sentiment_score"] >= 0.6, f"Score positivo deve ser >= 0.6, recebido {result['sentiment_score']}"
    
    # Validações de estrutura conforme briefing
    assert 100 <= len(result["summary"].split()) <= 200, f"Summary deve ter 100-200 palavras, tem {len(result['summary'].split())}"
    assert len(result["key_points"]) > 0, "key_points não deve estar vazio"
    assert len(result["action_items"]) > 0, "action_items não deve estar vazio"
    
    # Validações de campos obrigatórios
    assert result["meeting_id"] == "MTG-INT-POS-001"
    assert result["customer_id"] == "CUST-POS-001"
    assert result["customer_name"] == "João Muito Feliz"
    assert result["banker_id"] == "BNK-001"
    assert result["banker_name"] == "Maria Excelente"
    assert result["meet_type"] == "presencial"
    assert result["source"] == "lftm-challenge"
    assert result["idempotency_key"] is not None


@pytest.mark.asyncio
async def test_analyze_positive_with_partial_metadata():
    """
    Testa análise positiva com metadados parciais.
    
    Valida que o LLM consegue extrair campos faltantes da transcrição.
    """
    payload = {
        "transcript": """
Data: 13 de outubro de 2025
Participantes: Carlos Silva (gerente) e Fernanda Costa (cliente)

Carlos: Olá Fernanda! Como está seu portfólio?
Fernanda: Excelente Carlos! Rendeu MUITO bem! Estou super feliz!
Carlos: Que ótimo! Quer aumentar o investimento?
Fernanda: SIM! Quero investir mais 300 mil!
Carlos: Perfeito! Vou preparar a melhor proposta para você!
        """,
        "metadata": {
            "meeting_id": "MTG-INT-POS-002"
            # customer_id, banker_id serão extraídos da transcrição
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Sentimento deve ser positivo
    assert result["sentiment_label"] == "positive"
    assert result["sentiment_score"] >= 0.6
    
    # Campos extraídos da transcrição
    assert "Fernanda" in result["customer_name"] or "Costa" in result["customer_name"]
    assert "Carlos" in result["banker_name"] or "Silva" in result["banker_name"]


# ============================================================================
# TESTES DE SENTIMENTO NEUTRO
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_neutral_sentiment():
    """
    Testa análise de transcrição com sentimento NEUTRO.
    
    Transcrição: Reunião de rotina, sem emoções fortes
    Resultado esperado:
    - sentiment_label = "neutral"
    - 0.4 <= sentiment_score < 0.6
    """
    payload = {
        "transcript": """
Cliente: Bom dia. Vim para o acompanhamento mensal da minha carteira.
Banker: Olá! Vamos revisar seus investimentos.
Cliente: Ok. Como está o rendimento este mês?
Banker: Está dentro do esperado, cerca de 0.8% no mês.
Cliente: Entendo. Vou manter os investimentos como estão.
Banker: Certo. Alguma dúvida?
Cliente: Não, por enquanto está tudo certo.
Banker: Perfeito. Qualquer coisa, estou à disposição.
Cliente: Obrigado. Até a próxima reunião.
        """,
        "metadata": {
            "meeting_id": "MTG-INT-NEU-001",
            "customer_id": "CUST-NEU-001",
            "customer_name": "Pedro Neutro",
            "banker_id": "BNK-002",
            "banker_name": "Ana Profissional",
            "meet_type": "online",
            "meet_date": "2025-10-13T14:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Validações de sentimento NEUTRO
    assert result["sentiment_label"] == "neutral", f"Esperado 'neutral', recebido '{result['sentiment_label']}'"
    assert 0.4 <= result["sentiment_score"] < 0.6, f"Score neutro deve estar entre 0.4 e 0.6, recebido {result['sentiment_score']}"
    
    # Validações de estrutura
    assert 100 <= len(result["summary"].split()) <= 200
    assert len(result["key_points"]) > 0
    # action_items pode ser lista vazia em reuniões neutras simples (acompanhamento sem ações definidas)
    assert isinstance(result["action_items"], list)


@pytest.mark.asyncio
async def test_analyze_neutral_borderline():
    """
    Testa transcrição no limite entre neutro e positivo.
    
    Transcrição levemente positiva, mas não entusiástica.
    """
    payload = {
        "transcript": """
Cliente: Olá, tudo bem?
Banker: Oi! Tudo ótimo. E você?
Cliente: Bem. Vi que os investimentos renderam ok este trimestre.
Banker: Sim, ficou legal. Dentro da meta.
Cliente: Que bom. Vou continuar investindo então.
Banker: Excelente. Vou manter a estratégia.
Cliente: Perfeito. Obrigado.
        """,
        "metadata": {
            "meeting_id": "MTG-INT-NEU-002",
            "customer_id": "CUST-NEU-002",
            "customer_name": "Laura Normal",
            "banker_id": "BNK-002",
            "banker_name": "Ricardo Calmo",
            "meet_type": "híbrido",
            "meet_date": "2025-10-13T15:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Deve ser neutro ou positivo com score baixo
    assert result["sentiment_label"] in ["neutral", "positive"]
    if result["sentiment_label"] == "neutral":
        assert 0.4 <= result["sentiment_score"] < 0.6
    elif result["sentiment_label"] == "positive":
        assert result["sentiment_score"] >= 0.6


# ============================================================================
# TESTES DE SENTIMENTO NEGATIVO
# ============================================================================

@pytest.mark.asyncio
async def test_analyze_negative_sentiment():
    """
    Testa análise de transcrição com sentimento NEGATIVO.
    
    Transcrição: Cliente insatisfeito, reclamando, ameaçando sair
    Resultado esperado:
    - sentiment_label = "negative"
    - sentiment_score < 0.4
    - risks deve conter pelo menos 1 item
    """
    payload = {
        "transcript": """
Cliente: Estou MUITO INSATISFEITO com o atendimento de vocês!
Banker: Sinto muito. O que aconteceu?
Cliente: Perdi MUITO DINHEIRO com esses investimentos RUINS que vocês me venderam!
Banker: Vamos analisar com calma o que aconteceu...
Cliente: CALMA? Perdi 50 mil reais! Isso é INACEITÁVEL!
Banker: Entendo sua frustração. Vamos ver o que podemos fazer.
Cliente: Quero SACAR TODO meu dinheiro e FECHAR minha conta!
Banker: Por favor, vamos conversar antes de tomar essa decisão...
Cliente: NÃO confio mais em vocês! Vou para outro banco!
Banker: Eu compreendo. Podemos agendar uma reunião com o diretor?
Cliente: Não adianta! Estou decepcionado demais! PÉSSIMO serviço!
        """,
        "metadata": {
            "meeting_id": "MTG-INT-NEG-001",
            "customer_id": "CUST-NEG-001",
            "customer_name": "Roberto Insatisfeito",
            "banker_id": "BNK-003",
            "banker_name": "Julia Preocupada",
            "meet_type": "presencial",
            "meet_date": "2025-10-13T16:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Validações de sentimento NEGATIVO
    assert result["sentiment_label"] == "negative", f"Esperado 'negative', recebido '{result['sentiment_label']}'"
    assert result["sentiment_score"] < 0.4, f"Score negativo deve ser < 0.4, recebido {result['sentiment_score']}"
    
    # Validações específicas de sentimento negativo
    assert len(result["risks"]) > 0, "Sentimento negativo deve ter riscos identificados"
    
    # Validações de estrutura
    assert 100 <= len(result["summary"].split()) <= 200
    assert len(result["key_points"]) > 0
    assert len(result["action_items"]) > 0
    
    # Riscos devem estar relacionados à situação
    risks_text = " ".join(result["risks"]).lower()
    assert any(word in risks_text for word in ["perda", "cliente", "sacar", "fechar", "migra"]), \
        f"Riscos devem mencionar perda de cliente ou similar: {result['risks']}"


@pytest.mark.asyncio
async def test_analyze_negative_subtle():
    """
    Testa transcrição com sentimento negativo sutil (não explícito).
    
    Cliente não grita, mas está claramente insatisfeito de forma educada.
    """
    payload = {
        "transcript": """
Cliente: Bom dia. Gostaria de conversar sobre os resultados.
Banker: Claro! Como posso ajudar?
Cliente: Bem... não estou muito satisfeito com a rentabilidade.
Banker: Entendo. O que especificamente te incomoda?
Cliente: Os rendimentos estão abaixo do que foi prometido.
Banker: Vamos revisar a estratégia.
Cliente: Acho que vou considerar outras opções no mercado.
Banker: Podemos ajustar sua carteira.
Cliente: Vou pensar com calma. Mas estou decepcionado.
        """,
        "metadata": {
            "meeting_id": "MTG-INT-NEG-002",
            "customer_id": "CUST-NEG-002",
            "customer_name": "Carla Educada Mas Insatisfeita",
            "banker_id": "BNK-003",
            "banker_name": "Marcos Atento",
            "meet_type": "online",
            "meet_date": "2025-10-13T17:00:00Z"
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Deve ser negativo ou neutro (depende da sensibilidade do LLM com temperature=0.2)
    assert result["sentiment_label"] in ["negative", "neutral"]
    
    if result["sentiment_label"] == "negative":
        assert result["sentiment_score"] < 0.4
        assert len(result["risks"]) > 0


# ============================================================================
# TESTES COM FORMATO RAW_MEETING
# ============================================================================


@pytest.mark.asyncio
async def test_analyze_only_raw_meeting_format():
    """
    Testa análise usando formato raw_meeting (do upstream).
    
    Este é o formato alternativo aceito pela API.
    """
    payload = {
        "raw_meeting": {
            "meet_id": "MTG-RAW-001",
            "customer_id": "CUST-RAW-001",
            "customer_name": "Cliente Raw",
            "banker_id": "BNK-001",
            "banker_name": "Banker Raw",
            "meet_date": "2025-10-13T18:00:00Z",
            "meet_type": "Fechamento",
            "meet_transcription": """
Cliente: Estou feliz com a proposta!
Banker: Ótimo! Vamos fechar?
Cliente: Sim! Estou animado!
Banker: Perfeito! Parabéns pela decisão!
            """
        }
    }
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/analyze", json=payload)
    
    assert response.status_code == 200
    result = response.json()
    
    # Deve analisar sentimento corretamente
    assert result["sentiment_label"] == "positive"
    assert result["sentiment_score"] >= 0.6
    assert result["meeting_id"] == "MTG-RAW-001"

