# 🐳 Guia Docker - Meeting Extractor

## 📋 Pré-requisitos

- Docker instalado: https://docs.docker.com/get-docker/
- Docker Compose instalado (geralmente vem com Docker Desktop)
- Arquivo `.env` configurado com `OPENAI_API_KEY`

---

## 🚀 Quick Start

### Opção 1: Docker Compose (Recomendado)

```bash
# 1. Configure o .env
echo "OPENAI_API_KEY=sk-proj-xxxxxxxx" > .env
echo "OPENAI_MODEL=gpt-4o" >> .env

# 2. Build e inicia o serviço
docker-compose up --build

# Ou em background (detached)
docker-compose up -d --build

# 3. Testa
curl http://localhost:8000/health
```

### Opção 2: Docker CLI Manual

```bash
# 1. Build da imagem
docker build -t meeting-extractor:latest .

# 2. Roda o container
docker run -d \
  --name meeting-extractor \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-proj-xxxxxxxx \
  -e OPENAI_MODEL=gpt-4o \
  meeting-extractor:latest

# 3. Verifica logs
docker logs -f meeting-extractor

# 4. Testa
curl http://localhost:8000/health
```

---

## 🛠️ Comandos Úteis

### Build

```bash
# Build da imagem
docker build -t meeting-extractor:latest .

# Build sem cache (força rebuild completo)
docker build --no-cache -t meeting-extractor:latest .

# Build com tag específica
docker build -t meeting-extractor:v1.0.0 .
```

### Run

```bash
# Rodar em foreground (vê logs em tempo real)
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  meeting-extractor:latest

# Rodar em background
docker run -d \
  --name meeting-extractor \
  -p 8000:8000 \
  -e OPENAI_API_KEY=sk-xxx \
  meeting-extractor:latest

# Rodar com volume (persistir logs)
docker run -d \
  --name meeting-extractor \
  -p 8000:8000 \
  -v $(pwd)/logs:/app/logs \
  -e OPENAI_API_KEY=sk-xxx \
  meeting-extractor:latest
```

### Logs

```bash
# Ver logs
docker logs meeting-extractor

# Seguir logs em tempo real
docker logs -f meeting-extractor

# Últimas 100 linhas
docker logs --tail 100 meeting-extractor
```

### Gerenciamento

```bash
# Listar containers rodando
docker ps

# Listar todos os containers
docker ps -a

# Parar container
docker stop meeting-extractor

# Iniciar container parado
docker start meeting-extractor

# Reiniciar container
docker restart meeting-extractor

# Remover container
docker rm meeting-extractor

# Remover container forçado (mesmo rodando)
docker rm -f meeting-extractor
```

### Inspeção

```bash
# Ver detalhes do container
docker inspect meeting-extractor

# Ver health status
docker inspect --format='{{.State.Health.Status}}' meeting-extractor

# Entrar no container (bash)
docker exec -it meeting-extractor /bin/bash

# Executar comando no container
docker exec meeting-extractor python --version
```

### Limpeza

```bash
# Remover imagens não usadas
docker image prune

# Remover containers parados
docker container prune

# Limpeza geral (cuidado!)
docker system prune -a
```

---

## 🔧 Docker Compose

### Comandos Principais

```bash
# Build e inicia
docker-compose up --build

# Inicia em background
docker-compose up -d

# Para os serviços
docker-compose down

# Para e remove volumes
docker-compose down -v

# Ver logs
docker-compose logs -f

# Ver logs de um serviço específico
docker-compose logs -f meeting-extractor

# Reiniciar serviço
docker-compose restart meeting-extractor

# Ver status
docker-compose ps

# Executar comando em serviço
docker-compose exec meeting-extractor python --version
```

### Escalar (múltiplas instâncias)

```bash
# 3 instâncias do serviço
docker-compose up -d --scale meeting-extractor=3
```

---

## 📊 Health Check

O container tem health check integrado:

```bash
# Ver status de saúde
docker inspect --format='{{.State.Health.Status}}' meeting-extractor

# Estados possíveis:
# - starting: Iniciando (período de graça)
# - healthy: Saudável
# - unhealthy: Com problemas
```

**O que o health check faz:**
- A cada 30s, tenta acessar `GET /health`
- Se falhar 3 vezes consecutivas → marca como `unhealthy`
- Após 40s de start, começa a verificar

---

## 🌐 Acessar a API

### Dentro do container:
```bash
http://localhost:8000
```

### Documentação Swagger:
```bash
http://localhost:8000/docs
```

### Teste:
```bash
curl http://localhost:8000/health
```

---

## 🔐 Segurança

### ✅ Boas práticas implementadas:

1. **Multi-stage build**: Imagem final não tem ferramentas de compilação
2. **Non-root user**: Container roda como `appuser` (não root)
3. **Minimal image**: Usa `python:3.11-slim` (menor e mais segura)
4. **No secrets in image**: API key via env var, não hardcoded
5. **Health checks**: Detecta problemas automaticamente

### ⚠️ Nunca faça:

```bash
# ❌ NUNCA commitar .env com API keys
# ❌ NUNCA hardcodar secrets no Dockerfile
# ❌ NUNCA rodar como root em produção
```

---

## 📦 Tamanho da Imagem

```bash
# Ver tamanho da imagem
docker images meeting-extractor

# Esperado: ~800MB - 1.2GB
# (Python 3.11 + FastAPI + LangChain + OpenAI)
```

Para reduzir tamanho:
- Use `python:3.11-alpine` (menor, mas pode ter problemas de compatibilidade)
- Remova dependências de desenvolvimento do `requirements.txt`

---

## 🐛 Troubleshooting

### Problema: "Cannot connect to Docker daemon"
```bash
# Solução: Inicie o Docker Desktop
```

### Problema: "Port 8000 already in use"
```bash
# Solução 1: Mude a porta
docker run -p 8001:8000 ...

# Solução 2: Mate o processo usando 8000
netstat -ano | findstr :8000  # Windows
lsof -i :8000                 # Linux/Mac
```

### Problema: "OPENAI_API_KEY não encontrada"
```bash
# Solução: Certifique-se que o .env existe e tem a chave
cat .env
docker-compose config  # Ver variáveis carregadas
```

### Problema: Container não inicia
```bash
# Ver logs de erro
docker logs meeting-extractor

# Entrar no container para debug
docker run -it --rm meeting-extractor:latest /bin/bash
```

---

## 🚀 Deploy em Produção

### AWS ECS / Fargate

```bash
# 1. Tag da imagem
docker tag meeting-extractor:latest \
  <account>.dkr.ecr.<region>.amazonaws.com/meeting-extractor:latest

# 2. Push para ECR
docker push <account>.dkr.ecr.<region>.amazonaws.com/meeting-extractor:latest

# 3. Deploy via ECS Task Definition
```

### Google Cloud Run

```bash
# 1. Tag da imagem
docker tag meeting-extractor:latest \
  gcr.io/<project-id>/meeting-extractor:latest

# 2. Push para GCR
docker push gcr.io/<project-id>/meeting-extractor:latest

# 3. Deploy
gcloud run deploy meeting-extractor \
  --image gcr.io/<project-id>/meeting-extractor:latest \
  --platform managed
```

### Azure Container Instances

```bash
# 1. Tag da imagem
docker tag meeting-extractor:latest \
  <registry>.azurecr.io/meeting-extractor:latest

# 2. Push para ACR
docker push <registry>.azurecr.io/meeting-extractor:latest

# 3. Deploy
az container create \
  --resource-group <rg> \
  --name meeting-extractor \
  --image <registry>.azurecr.io/meeting-extractor:latest
```

---

## 📚 Referências

- **Docker Docs:** https://docs.docker.com/
- **Docker Compose:** https://docs.docker.com/compose/
- **Best Practices:** https://docs.docker.com/develop/dev-best-practices/

---

**Criado com ❤️ para o Desafio LFTM**

