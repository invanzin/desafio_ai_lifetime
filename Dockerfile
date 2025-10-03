# ============================================================================
# Dockerfile para Meeting Extractor Microservice
# ============================================================================
# Este Dockerfile cria uma imagem Docker otimizada para produção do
# microserviço de extração de reuniões.
#
# Características:
# - Multi-stage build para imagem menor
# - Non-root user para segurança
# - Health check integrado
# - Otimizado para Python 3.11+
# ============================================================================

# ----------------------------------------------------------------------------
# STAGE 1: Builder (instala dependências)
# ----------------------------------------------------------------------------
FROM python:3.11-slim as builder

# Metadados da imagem
LABEL maintainer="seu-email@example.com"
LABEL description="Meeting Extractor Microservice - Desafio LFTM"
LABEL version="1.0.0"

# Define diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para compilação
# gcc: Para compilar pacotes Python com extensões C
# python3-dev: Headers do Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copia apenas requirements.txt primeiro (aproveita cache do Docker)
COPY requirements.txt .

# Instala dependências Python em /app/venv
# --no-cache-dir: Não guarda cache (economia de espaço)
# --upgrade: Garante versões mais recentes
RUN python -m venv /app/venv && \
    /app/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------------------------------
# STAGE 2: Runtime (imagem final leve)
# ----------------------------------------------------------------------------
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Copia apenas o virtualenv do stage builder (não copia gcc, etc)
COPY --from=builder /app/venv /app/venv

# Copia código da aplicação
COPY app/ ./app/
COPY test_api.py ./

# Cria usuário não-root para segurança
# Por que? Root em container é má prática de segurança
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Muda para usuário não-root
USER appuser

# Define variáveis de ambiente
ENV PATH="/app/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expõe porta 8000 (padrão FastAPI)
EXPOSE 8000

# Health check (verifica se o serviço está saudável)
# A cada 30s, tenta acessar /health
# Se falhar 3 vezes consecutivas, marca como unhealthy
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Comando padrão para iniciar a aplicação
# --host 0.0.0.0: Aceita conexões de qualquer IP
# --port 8000: Porta padrão
# --workers 1: Número de workers (ajuste conforme CPU)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


