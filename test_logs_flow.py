"""
Script de teste para verificar o fluxo completo e logging da API.

Executa uma requisição de teste ao endpoint /extract e mostra os logs
sendo gerados em tempo real.

Uso:
    1. Inicie a API: uvicorn app.main:app --reload
    2. Em outro terminal: python test_logs_flow.py
    3. Verifique os logs em: logs/app.log e logs/error.log
"""

import httpx
import asyncio
import json
from datetime import datetime


# Dados de teste
TEST_DATA = {
    "transcript": """
Cliente: Bom dia, meu nome é João Silva da ACME S.A.
Banker: Olá João! Meu nome é Pedro Falcão, sou gerente aqui no banco.
Cliente: Estamos precisando de uma linha de crédito para capital de giro.
Nossa empresa está crescendo e precisamos de R$ 500 mil.
Banker: Entendo. Qual é o faturamento atual da empresa?
Cliente: Faturamos cerca de R$ 2 milhões por ano.
Banker: Ótimo! Temos linhas de crédito que podem atender.
Vou precisar analisar o fluxo de caixa e as garantias disponíveis.
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
        "meeting_id": "MTG-TEST-001",
        "customer_id": "CUST-001",
        "customer_name": "ACME S.A.",
        "banker_id": "BKR-789",
        "banker_name": "Pedro Falcao",
        "meet_type": "Primeira Reuniao",
        "meet_date": "2025-10-03T14:30:00Z"
    }
}


async def test_extract_flow():
    """
    Testa o fluxo completo de extração.
    """
    print("\n" + "="*80)
    print("🧪 TESTE DO FLUXO COMPLETO DE EXTRAÇÃO")
    print("="*80)
    print(f"\n⏰ Timestamp: {datetime.now().isoformat()}")
    print(f"📍 Endpoint: POST http://localhost:8000/extract")
    print(f"📝 Transcription length: {len(TEST_DATA['transcript'])} chars")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print("\n🚀 Enviando requisição...")
            response = await client.post(
                "http://localhost:8000/extract",
                json=TEST_DATA
            )
            
            print(f"\n✅ Status: {response.status_code}")
            print(f"📋 Headers:")
            print(f"   - X-Request-ID: {response.headers.get('X-Request-ID')}")
            print(f"   - Content-Type: {response.headers.get('Content-Type')}")
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"\n📊 RESULTADO DA EXTRAÇÃO:")
                print(f"   • Meeting ID: {result.get('meeting_id')}")
                print(f"   • Customer: {result.get('customer_name')}")
                print(f"   • Banker: {result.get('banker_name')}")
                print(f"   • Type: {result.get('meet_type')}")
                print(f"   • Date: {result.get('meet_date')}")
                print(f"   • Idempotency Key: {result.get('idempotency_key')[:20]}...")
                
                summary = result.get('summary', '')
                print(f"\n📄 Summary ({len(summary.split())} palavras):")
                print(f"   {summary[:200]}...")
                
                print(f"\n🔑 Key Points ({len(result.get('key_points', []))}):")
                for point in result.get('key_points', [])[:3]:
                    print(f"   • {point}")
                
                print(f"\n✅ Action Items ({len(result.get('action_items', []))}):")
                for action in result.get('action_items', [])[:3]:
                    print(f"   • {action}")
                
                print(f"\n🏷️ Topics: {', '.join(result.get('topics', []))}")
                
                print("\n" + "="*80)
                print("✅ TESTE CONCLUÍDO COM SUCESSO!")
                print("="*80)
                
                print("\n📁 VERIFIQUE OS LOGS:")
                print("   • logs/app.log   - Logs gerais (INFO+)")
                print("   • logs/error.log - Apenas erros (WARNING+)")
                
                print("\n💡 COMANDOS ÚTEIS:")
                print("   • Ver logs em tempo real:")
                print("     PowerShell: Get-Content logs\\app.log -Wait -Tail 50")
                print("     Linux/Mac: tail -f logs/app.log")
                
                print("\n   • Ver últimas 20 linhas:")
                print("     PowerShell: Get-Content logs\\app.log -Tail 20")
                print("     Linux/Mac: tail -n 20 logs/app.log")
                
            else:
                error = response.json()
                print(f"\n❌ ERRO:")
                print(json.dumps(error, indent=2, ensure_ascii=False))
                
        except httpx.ConnectError:
            print("\n❌ ERRO: Não foi possível conectar à API!")
            print("\n💡 SOLUÇÃO:")
            print("   1. Certifique-se que a API está rodando:")
            print("      uvicorn app.main:app --reload")
            print("   2. Execute este script novamente")
            
        except Exception as e:
            print(f"\n❌ Erro inesperado: {type(e).__name__}: {e}")


if __name__ == "__main__":
    print("\n🔧 CONFIGURAÇÃO:")
    print("   • API deve estar rodando em http://localhost:8000")
    print("   • OPENAI_API_KEY deve estar configurada no .env")
    
    asyncio.run(test_extract_flow())

