"""
Script de exemplo para testar a API de extração de reuniões.

Este script demonstra como chamar o endpoint /extract com diferentes
formatos de entrada e como lidar com as respostas.

Uso:
    python test_api.py

Requerimentos:
    - API rodando em http://localhost:8000
    - httpx instalado (já está no requirements.txt)
"""

import asyncio
import json
from datetime import datetime
import httpx


# Configuração da API
API_BASE_URL = "http://localhost:8000"


# ============================================================================
# DADOS DE TESTE
# ============================================================================

# Formato 1: Transcrição + Metadados completos
TEST_DATA_FORMAT_1 = {
    "transcript": """
Cliente: Bom dia, meu nome é João Silva e gostaria de falar sobre empréstimos.
Banker: Olá João! Meu nome é Pedro Falcão, sou gerente aqui. Claro, vamos discutir as opções de crédito disponíveis.
Cliente: Preciso de um capital de giro de cerca de R$ 500 mil para expandir minha empresa.
Banker: Entendo. Qual é o faturamento atual da sua empresa?
Cliente: Faturamos cerca de R$ 2 milhões por ano.
Banker: Ótimo. Temos algumas linhas de crédito que podem atender sua necessidade. Vou preparar uma proposta.
Cliente: Perfeito! Qual é o próximo passo?
Banker: Vou precisar de alguns documentos financeiros. Posso enviar a lista por email?
Cliente: Sim, meu email é joao@acme.com
Banker: Excelente. Vou enviar hoje e agendamos uma segunda reunião na próxima semana para apresentar a proposta.
""",
    "metadata": {
        "meeting_id": "MTG-2025-001",
        "customer_id": "CUST-456",
        "customer_name": "João Silva / ACME S.A.",
        "banker_id": "BKR-789",
        "banker_name": "Pedro Falcão",
        "meet_type": "Primeira Reunião",
        "meet_date": "2025-09-10T14:30:00Z"
    }
}

# Formato 2: Apenas transcrição (metadados serão extraídos)
TEST_DATA_FORMAT_2 = {
    "transcript": """
Data: 22 de setembro de 2025
Participantes: Ana Silva (gerente) e Gabriel Oliveira (cliente)

Ana Silva: Bom dia Gabriel! Como tem passado?
Gabriel Oliveira: Bom dia Ana! Tudo bem, obrigado. Vim aqui para fazer um acompanhamento do meu investimento.
Ana Silva: Claro! Vamos revisar sua carteira. Desde nossa última reunião, seus investimentos tiveram um rendimento de 8% no semestre.
Gabriel Oliveira: Isso é ótimo! Estou pensando em aumentar meu aporte mensal.
Ana Silva: Excelente ideia. Quanto você está pensando em investir mensalmente?
Gabriel Oliveira: Gostaria de aumentar de R$ 5 mil para R$ 10 mil por mês.
Ana Silva: Perfeito. Vou ajustar seu plano de investimentos e enviar um resumo por email.
Gabriel Oliveira: Maravilha! Quando podemos agendar a próxima reunião?
Ana Silva: Que tal daqui a 3 meses para revisarmos novamente?
Gabriel Oliveira: Combinado!
"""
}

# Formato 3: Raw Meeting (formato upstream)
TEST_DATA_FORMAT_3 = {
    "raw_meeting": {
        "meet_id": "7541064ef4a",
        "customer_id": "02ae981fbade",
        "customer_name": "Maria Santos",
        "customer_email": "maria@example.com",
        "banker_id": "1cc87e",
        "banker_name": "Carlos Mendes",
        "meet_date": "2025-09-22T17:00:00Z",
        "meet_type": "Fechamento",
        "meet_transcription": """
Carlos Mendes: Boa tarde Maria! Estamos aqui para finalizar sua proposta de crédito.
Maria Santos: Ótimo Carlos! Estou ansiosa para fechar este negócio.
Carlos Mendes: Então, confirmando: empréstimo de R$ 300 mil, prazo de 24 meses, taxa de 1.2% ao mês.
Maria Santos: Perfeito! Concordo com todos os termos.
Carlos Mendes: Excelente. Vou precisar que você assine o contrato aqui e aqui.
Maria Santos: Pronto, assinado!
Carlos Mendes: O dinheiro estará disponível em sua conta em até 48 horas úteis.
Maria Santos: Maravilha! Muito obrigada pela agilidade.
Carlos Mendes: Por nada! Qualquer dúvida, estou à disposição.
"""
    }
}


# ============================================================================
# FUNÇÕES DE TESTE
# ============================================================================

async def test_health_check():
    """Testa o health check da API."""
    print("\n" + "="*80)
    print("🏥 TESTE: Health Check")
    print("="*80)
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health")
            print(f"✅ Status: {response.status_code}")
            print(f"📄 Resposta: {response.json()}")
        except Exception as e:
            print(f"❌ Erro: {e}")


async def test_extract_format_1():
    """Testa extração com formato 1 (transcript + metadata completos)."""
    print("\n" + "="*80)
    print("📝 TESTE: Formato 1 (Transcript + Metadata)")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/extract",
                json=TEST_DATA_FORMAT_1
            )
            
            print(f"✅ Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n📋 RESULTADO:")
                print(f"  • Meeting ID: {result.get('meeting_id')}")
                print(f"  • Customer: {result.get('customer_name')}")
                print(f"  • Banker: {result.get('banker_name')}")
                print(f"  • Type: {result.get('meet_type')}")
                print(f"  • Date: {result.get('meet_date')}")
                print(f"  • Idempotency Key: {result.get('idempotency_key')[:20]}...")
                print(f"\n  📄 Summary ({len(result.get('summary', '').split())} palavras):")
                print(f"     {result.get('summary')}")
                print(f"\n  🔑 Key Points ({len(result.get('key_points', []))}):")
                for point in result.get('key_points', []):
                    print(f"     • {point}")
                print(f"\n  ✅ Action Items ({len(result.get('action_items', []))}):")
                for action in result.get('action_items', []):
                    print(f"     • {action}")
                print(f"\n  🏷️ Topics: {', '.join(result.get('topics', []))}")
            else:
                print(f"❌ Erro: {response.json()}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")


async def test_extract_format_2():
    """Testa extração com formato 2 (apenas transcript)."""
    print("\n" + "="*80)
    print("📝 TESTE: Formato 2 (Apenas Transcript)")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/extract",
                json=TEST_DATA_FORMAT_2
            )
            
            print(f"✅ Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n📋 RESULTADO:")
                print(f"  • Meeting ID: {result.get('meeting_id')}")
                print(f"  • Customer: {result.get('customer_name')} (extraído da transcrição)")
                print(f"  • Banker: {result.get('banker_name')} (extraído da transcrição)")
                print(f"  • Type: {result.get('meet_type')}")
                print(f"  • Summary: {result.get('summary')[:100]}...")
            else:
                print(f"❌ Erro: {response.json()}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")


async def test_extract_format_3():
    """Testa extração com formato 3 (raw_meeting)."""
    print("\n" + "="*80)
    print("📝 TESTE: Formato 3 (Raw Meeting)")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/extract",
                json=TEST_DATA_FORMAT_3
            )
            
            print(f"✅ Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n📋 RESULTADO:")
                print(f"  • Meeting ID: {result.get('meeting_id')}")
                print(f"  • Customer: {result.get('customer_name')}")
                print(f"  • Type: {result.get('meet_type')}")
                print(f"  • Summary: {result.get('summary')[:100]}...")
            else:
                print(f"❌ Erro: {response.json()}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")


async def test_validation_error():
    """Testa erro de validação (envio de dados inválidos)."""
    print("\n" + "="*80)
    print("❌ TESTE: Erro de Validação")
    print("="*80)
    
    # Enviar ambos os formatos (inválido)
    invalid_data = {
        "transcript": "Teste",
        "raw_meeting": TEST_DATA_FORMAT_3["raw_meeting"]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE_URL}/extract",
                json=invalid_data
            )
            
            print(f"✅ Status: {response.status_code} (esperado: 422)")
            
            if response.status_code == 422:
                error = response.json()
                print(f"📄 Erro de validação (esperado):")
                print(f"   {error.get('message')}")
                print(f"   Request ID: {error.get('request_id')}")
            else:
                print(f"⚠️ Status inesperado: {response.json()}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Executa todos os testes."""
    print("\n" + "🚀" * 40)
    print("TESTE DA API DE EXTRAÇÃO DE REUNIÕES")
    print("🚀" * 40)
    print(f"\n🔗 API Base URL: {API_BASE_URL}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    
    # Executar testes
    await test_health_check()
    await test_extract_format_1()
    await test_extract_format_2()
    await test_extract_format_3()
    await test_validation_error()
    
    print("\n" + "="*80)
    print("✅ TESTES CONCLUÍDOS")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

