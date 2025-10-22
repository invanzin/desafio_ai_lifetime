### Próximos Passos e Cuidados (Projeto LangChain – Extractor + Analyzer)

Este guia lista iniciativas recomendadas para evoluir o projeto com segurança, performance e valor de negócio, organizadas por tema. Cada item traz objetivos, cuidados e critérios de pronto (DoD) para implantação segura.

### Segurança
- **Sanitização de PII nos logs**
  - Objetivo: impedir vazamento de dados sensíveis.
  - Cuidados: mascarar e-mails, telefones, CPFs/CNPJs, endereços; não logar payloads brutos.
  - DoD: filtros ativos; testes de mascaramento; auditoria manual em `logs/` sem PII.

- **Gestão de segredos**
  - Objetivo: proteger chaves (OpenAI, etc.).
  - Cuidados: usar variáveis de ambiente e/ou `secrets` do orquestrador; nunca commitar `.env`.
  - DoD: `.env.example` documentado; validação em startup com erro amigável se faltarem variáveis.

- **Rate limiting e proteção básica**
  - Objetivo: evitar abuso/DoS.
  - Cuidados: limites por IP/chave; respostas 429 consistentes; backoff no cliente.
  - DoD: limites ativos; testes de carga leve confirmando 429 sob excesso.

- **Política de retenção**
  - Objetivo: minimizar risco e custo.
  - Cuidados: definir prazos de retenção de logs e dados processados; rotação de logs.
  - DoD: política descrita e aplicada (ex.: 7–14 dias em dev, 30–90 em prod com rotação).

### Cache e Idempotência
- **Revisão do cache em memória (atual)**
  - Objetivo: garantir idempotência e reduzir custo; TTL correto.
  - Cuidados: limpeza periódica; limites de memória; chaves por `idempotency_key` estável.
  - DoD: métricas de acerto/miss; testes cobrindo hit/miss/expiração.

- **Migração para Redis (próximo nível)**
  - Objetivo: cache distribuído e durável.
  - Cuidados: TTL por tipo de tarefa; namespaces (extract/analyze); fallback quando Redis indisponível.
  - DoD: `REDIS_URL`/`REDIS_TTL` configuráveis; testes de rede intermitente; monitoramento de conexões.

- **Estratégias de invalidação**
  - Objetivo: garantir consistência quando entradas mudarem (ex.: transcript atualizada).
  - Cuidados: incluir versão/hash do conteúdo e metadados no `idempotency_key`.
  - DoD: testes que garantem chave diferente quando o conteúdo muda.

### Integração com Sistemas
- **CRM/Tasks**
  - Objetivo: criar follow-ups automaticamente.
  - Cuidados: reprocessamento idempotente; mapeamento de campos; auditoria de operações.
  - DoD: conector (ex.: webhook/SDK) + retries com backoff + dead-letter para falhas persistentes.

- **Ingestão de transcrições**
  - Objetivo: aceitar múltiplas fontes (upload, webhook de meeting providers, S3/GCS).
  - Cuidados: normalização; validação de encoding; limites de tamanho.
  - DoD: rotas/documentação por fonte; testes E2E por fonte.

- **Webhooks de saída**
  - Objetivo: notificar sistemas externos com o resultado.
  - Cuidados: assinar eventos (HMAC); retries; DLQ.
  - DoD: assinatura documentada; verificação de assinatura no consumidor de teste.

### Prompts e Qualidade de Saída
- **Afinamento de prompts**
  - Objetivo: aumentar precisão de resumo, ações e riscos.
  - Cuidados: manter prompts versionados; testes de regressão textual.
  - DoD: prompt v2 com métricas melhores (ex.: redução de reparos, maior consistência label/score).

- **Avaliação sistemática (LLM-as-a-judge ou rubricas)**
  - Objetivo: medir qualidade de forma objetiva.
  - Cuidados: rubricas claras (completude, factualidade, utilidade); dataset de avaliação.
  - DoD: relatório de qualidade por versão de prompt/modelo.

- **Consistência “sentiment_label ↔ sentiment_score”**
  - Objetivo: garantir coerência.
  - Cuidados: validação pós-modelo com correção leve (ex.: mapear scores extremos para rótulos 
    esperados).
  - DoD: regra implementada + testes cobrindo bordas.

### Observabilidade e Custos
- **Métricas (Prometheus) – Amadurecimento e Adoção**
  - **Objetivo**: Evoluir de um dashboard CLI para um sistema de monitoramento completo que suporte decisões de negócio, otimização de custos e garantia de performance.
  - **Fase 1 (Atual - Visão Geral)**: Visão 360º de latência, sucessos, tokens, custo, reparos e cache.
  - **Fase 2 (Próximos Passos - Aprofundamento)**:
    - **Maior Granularidade**: Adicionar labels como `model_name`, `intent`, e `error_type` (ex: `validation_error`, `api_error`) para identificar gargalos ou fontes de custo específicas.
    - **Métricas de Qualidade**: Implementar métricas de negócio, como `sentiment_score_distribution` (histograma) para entender o tom geral das reuniões, ou `action_items_per_meeting` para medir a "acionabilidade".
    - **Dashboards em Grafana**: Migrar do dashboard CLI para painéis interativos no Grafana. Isso permite análise histórica, correlação de dados (ex: latência vs. custo) e acesso para times não-técnicos.
    - **Alertas Proativos**: Configurar alertas via Alertmanager para notificar sobre:
      - **Anomalias de Custo**: Gastos com OpenAI excedendo um limite diário/horário.
      - **Degradação de Performance**: Aumento na latência p99 ou na taxa de erros.
      - **Problemas de Qualidade**: Aumento súbito de `json_repair_attempts` (indicando problemas no prompt ou modelo).
      - **Baixa Eficiência de Cache**: Queda na taxa de `cache_hit_ratio`.
  - **DoD**: Dashboard Grafana publicado; 4+ alertas críticos configurados e testados; novas métricas com labels implementadas.

- **Correção de custos por modelo**
  - Objetivo: refletir preços reais por modelo e região.
  - Cuidados: tabela de preços por modelo/versão; fallback seguro.
  - DoD: custo por requisição alinhado com LangSmith/billing.

- **Tracing**
  - Objetivo: rastreamento por `request_id` ponta a ponta.
  - Cuidados: spans por etapa (normalize → cache → LLM → parse → validações → integração).
  - DoD: traces navegáveis; amostragem configurável.

### Testes e Qualidade
- **Cobertura ampliada**
  - Objetivo: estabilidade.
  - Cuidados: testes unit (schemas, prompts “golden”), integração (API), e2e (fluxo completo).
  - DoD: cobertura mínima acordada; suíte de regressão roda no CI.

- **Testes de carga**
  - Objetivo: entender limites (latência, custo, erro).
  - Cuidados: datasets sintéticos; limites de QPS configuráveis.
  - DoD: relatório com curvas p50/p95/p99 e recomendações.

### Performance e Escalabilidade
- **Chunking progressivo (quando necessário)**
  - Objetivo: suportar transcrições grandes com custo previsível.
  - Cuidados: janela deslizante; sumarização hierárquica; controle de tokens.
  - DoD: thresholds e testes com transcrições de tamanhos variados.

- **Concorrência controlada**
  - Objetivo: throughput sem estourar limites.
  - Cuidados: filas, workers e circuit breaker para LLM.
  - DoD: fila com visibilidade; métricas de fila; retry com jitter.

### Operação e DevEx
- **Config flags/feature toggles**
  - Objetivo: ativar/desativar Analyzer, cache Redis, rate limit, etc.
  - Cuidados: defaults seguros; documentação clara.
  - DoD: tabela de flags no README + exemplos.

- **Docker/Compose/K8s**
  - Objetivo: deploy simples e reproduzível.
  - Cuidados: healthchecks; limites de recursos; readiness/liveness probes.
  - DoD: compose atualizado; manifesto K8s opcional com probes e requests/limits.

### Dados, Privacidade e Compliance
- **Minimização e retenção**
  - Objetivo: coletar o mínimo e por tempo mínimo.
  - Cuidados: TTLs; expurgo automatizado; evitar persistir transcrição sem necessidade.
  - DoD: política publicada e aplicada em ambiente.

- **Direitos do titular**
  - Objetivo: alinhamento com LGPD/GDPR.
  - Cuidados: mecanismos para exclusão/anonimização sob demanda.
  - DoD: procedimento documentado e testado.

### Roadmap sugerido (4–6 semanas)
- Semana 1: Redis + métricas cache; revisão de custos por modelo.
- Semana 2: Webhooks de saída + conectores (CRM/tasks) com idempotência.
- Semana 3: Afinamento de prompts (v2) + avaliação de qualidade.
- Semana 4: Tracing + testes de carga + limites/buckets Prometheus.
- Semana 5–6: Chunking progressivo, flags de recursos, pacote de deploy (Compose/K8s) e política de retenção.

### Critérios de sucesso (indicativos)
- Custo médio por reunião ≤ meta definida (ex.: ≤ $0.03).
- p95 da extração ≤ 20s; taxa de sucesso ≥ 95%.
- Cache hit ≥ 30% em cenários reais repetidos.
- Zero PII em logs; 0 falhas críticas em testes de carga planejados.

Se quiser, posso criar os issues/tarefas com checklists e effort estimado para começarmos pela prioridade que você escolher (ex.: Redis + conectores CRM). 


