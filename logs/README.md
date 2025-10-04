# 📁 Diretório de Logs

Este diretório contém os arquivos de log da aplicação.

## Arquivos de Log

| Arquivo | Descrição | Nível |
|---------|-----------|-------|
| `app.log` | Logs gerais da aplicação | INFO+ |
| `error.log` | Apenas erros e warnings | WARNING+ |

## Rotação Automática

- **Tamanho máximo:** 10MB por arquivo
- **Backups:** 5 arquivos antigos mantidos
- **Formato:** `app.log.1`, `app.log.2`, etc.

## Formato dos Logs

```
YYYY-MM-DD HH:MM:SS - module.name - LEVEL - Message
```

**Exemplo:**
```
2025-10-03 23:15:30 - app.main - INFO - 🚀 Iniciando microserviço...
2025-10-03 23:15:45 - app.extractors.extractor - INFO - [req-123] Iniciando extração
```

## Como Visualizar

### Tempo Real (Tail)
```bash
# PowerShell (Windows)
Get-Content logs\app.log -Wait -Tail 50

# Linux/Mac
tail -f logs/app.log
```

### Últimas N Linhas
```bash
# PowerShell
Get-Content logs\app.log -Tail 20

# Linux/Mac
tail -n 20 logs/app.log
```

### Pesquisar por Padrão
```bash
# PowerShell
Select-String -Path logs\app.log -Pattern "ERROR"

# Linux/Mac
grep "ERROR" logs/app.log
```

## Níveis de Log

| Nível | Uso | Exemplo |
|-------|-----|---------|
| `DEBUG` | Informações detalhadas para debugging | Valores de variáveis, fluxo detalhado |
| `INFO` | Informações gerais do funcionamento | Requisições recebidas, operações concluídas |
| `WARNING` | Avisos que não impedem o funcionamento | Dados faltantes, tentativas de retry |
| `ERROR` | Erros que impediram uma operação | Falha na OpenAI, validação falhou |
| `CRITICAL` | Erros graves que podem derrubar o sistema | Falha fatal, recursos críticos indisponíveis |

## Estrutura Típica de Uma Requisição

```
[Início]
2025-10-03 23:15:45 - app.main - INFO - [req-abc123] POST /extract received

[Validação]
2025-10-03 23:15:45 - app.main - INFO - [req-abc123] Validação OK

[Extração]
2025-10-03 23:15:45 - app.extractors.extractor - INFO - [req-abc123] Iniciando extração
2025-10-03 23:15:50 - app.extractors.extractor - INFO - [req-abc123] LLM respondeu
2025-10-03 23:15:50 - app.extractors.extractor - INFO - [req-abc123] Validação Pydantic OK

[Fim]
2025-10-03 23:15:50 - app.extractors.extractor - INFO - [req-abc123] Extração concluída
2025-10-03 23:15:50 - app.main - INFO - [req-abc123] Response 200 OK
```

## Segurança

⚠️ **Importante:**
- Logs **NÃO devem conter PII completa** (dados pessoais)
- Transcrições são truncadas em 300 caracteres nos logs
- Emails e dados sensíveis são sanitizados

## .gitignore

Os arquivos `*.log` são ignorados pelo Git. Apenas a estrutura de diretórios é versionada.

```gitignore
# Ignorar logs
*.log
*.log.*

# Manter pasta
!.gitignore
!.gitkeep
!README.md
```

## Monitoramento

Para produção, considere integrar com:
- **ELK Stack** (Elasticsearch + Logstash + Kibana)
- **Grafana Loki**
- **CloudWatch** (AWS)
- **Azure Monitor**
- **Google Cloud Logging**

