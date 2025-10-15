"""
Script de teste para validar funcionamento do cache de idempotência.

Este script faz requisições duplicadas ao endpoint /extract para verificar:
1. Primeira requisição: CACHE MISS → processa normalmente (lento, ~2-5s)
2. Segunda requisição: CACHE HIT → retorna do cache (rápido, <0.1s)

Uso:
    python test_cache_idempotency.py
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8000"

# Payload de teste com metadados completos (garante idempotency_key válido)
TEST_PAYLOAD = {
    "transcript": "Cliente: Bom dia! Gostaria de discutir opções de investimento. Banker: Olá! Vamos conversar sobre fundos de investimento e previdência privada.",
    "metadata": {
        "meeting_id": "TEST-CACHE-001",
        "customer_id": "CUST-CACHE-001", 
        "customer_name": "Cliente Teste Cache",
        "banker_id": "BANKER-001",
        "banker_name": "Banker Teste",
        "meet_type": "Primeira Reunião",
        "meet_date": "2025-10-15T10:00:00Z"
    }
}


def test_cache_idempotency():
    """
    Testa o funcionamento do cache de idempotência.
    """
    print("=" * 80)
    print("🧪 TESTE DE CACHE DE IDEMPOTÊNCIA")
    print("=" * 80)
    print()
    
    # Health check
    print("1️⃣ Verificando health da API...")
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=5)
        if health_response.status_code == 200:
            print("   ✅ API está saudável")
        else:
            print(f"   ❌ API retornou status {health_response.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Erro ao conectar: {e}")
        print("   💡 Certifique-se que a API está rodando: uvicorn app.main:app --reload")
        return
    
    print()
    
    # Primeira requisição (CACHE MISS)
    print("2️⃣ Fazendo PRIMEIRA requisição (deve processar com OpenAI)...")
    print(f"   📋 meeting_id: {TEST_PAYLOAD['metadata']['meeting_id']}")
    
    start_time_1 = time.time()
    try:
        response_1 = requests.post(
            f"{BASE_URL}/extract",
            json=TEST_PAYLOAD,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        duration_1 = time.time() - start_time_1
        
        if response_1.status_code == 200:
            data_1 = response_1.json()
            request_id_1 = response_1.headers.get("X-Request-ID", "N/A")
            idempotency_key_1 = data_1.get("idempotency_key", "N/A")
            
            print(f"   ✅ Sucesso (status 200)")
            print(f"   ⏱️ Duração: {duration_1:.2f}s")
            print(f"   🆔 Request ID: {request_id_1}")
            print(f"   🔑 Idempotency Key: {idempotency_key_1[:16]}...")
            print(f"   📝 Summary: {data_1['summary'][:80]}...")
        else:
            print(f"   ❌ Erro: status {response_1.status_code}")
            print(f"   📄 Response: {response_1.text[:200]}")
            return
    except Exception as e:
        print(f"   ❌ Erro na requisição: {e}")
        return
    
    print()
    
    # Aguardar 1 segundo
    print("3️⃣ Aguardando 1 segundo antes da segunda requisição...")
    time.sleep(1)
    print()
    
    # Segunda requisição (CACHE HIT esperado)
    print("4️⃣ Fazendo SEGUNDA requisição (deve retornar do CACHE)...")
    print(f"   📋 meeting_id: {TEST_PAYLOAD['metadata']['meeting_id']} (MESMO)")
    
    start_time_2 = time.time()
    try:
        response_2 = requests.post(
            f"{BASE_URL}/extract",
            json=TEST_PAYLOAD,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        duration_2 = time.time() - start_time_2
        
        if response_2.status_code == 200:
            data_2 = response_2.json()
            request_id_2 = response_2.headers.get("X-Request-ID", "N/A")
            idempotency_key_2 = data_2.get("idempotency_key", "N/A")
            
            print(f"   ✅ Sucesso (status 200)")
            print(f"   ⏱️ Duração: {duration_2:.2f}s")
            print(f"   🆔 Request ID: {request_id_2}")
            print(f"   🔑 Idempotency Key: {idempotency_key_2[:16]}...")
        else:
            print(f"   ❌ Erro: status {response_2.status_code}")
            return
    except Exception as e:
        print(f"   ❌ Erro na requisição: {e}")
        return
    
    print()
    
    # Análise dos resultados
    print("=" * 80)
    print("📊 ANÁLISE DOS RESULTADOS")
    print("=" * 80)
    
    # Comparar duração
    speedup = duration_1 / duration_2 if duration_2 > 0 else 0
    print(f"⏱️ Duração 1ª requisição: {duration_1:.3f}s")
    print(f"⏱️ Duração 2ª requisição: {duration_2:.3f}s")
    print(f"🚀 Speedup: {speedup:.1f}x mais rápido")
    
    # Verificar se segunda requisição foi significativamente mais rápida
    if duration_2 < duration_1 * 0.1:  # 10x mais rápido
        print("✅ CACHE FUNCIONANDO! Segunda requisição foi muito mais rápida.")
    elif duration_2 < duration_1 * 0.5:  # 2x mais rápido
        print("⚠️ Segunda requisição mais rápida, mas não tão significativo.")
        print("   Possível cache parcial ou rede lenta.")
    else:
        print("❌ CACHE NÃO FUNCIONANDO! Segunda requisição deveria ser instantânea.")
        print("   Verifique os logs da API para mensagens [CACHE HIT] ou [CACHE MISS]")
    
    print()
    
    # Comparar idempotency_keys
    if idempotency_key_1 == idempotency_key_2:
        print(f"✅ Idempotency keys idênticos: {idempotency_key_1[:32]}...")
    else:
        print("❌ Idempotency keys DIFERENTES!")
        print(f"   1ª: {idempotency_key_1}")
        print(f"   2ª: {idempotency_key_2}")
    
    print()
    
    # Comparar responses completos
    if data_1 == data_2:
        print("✅ Responses idênticos (idempotência garantida)")
    else:
        print("⚠️ Responses diferentes (possível problema de cache)")
        print("   Nota: Pode ser esperado se LLM retornar resultados diferentes")
    
    print()
    print("=" * 80)
    print("💡 DICAS:")
    print("   - Verifique logs da API para mensagens [CACHE HIT] e [CACHE SAVE]")
    print("   - Segunda requisição deve ter log: '[CACHE HIT] idempotency_key=...'")
    print("   - Cache TTL padrão: 24 horas (configurável via CACHE_TTL_HOURS)")
    print("=" * 80)


if __name__ == "__main__":
    test_cache_idempotency()

