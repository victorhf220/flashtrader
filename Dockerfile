FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia todo o código
COPY . .

# Cria diretório de logs
RUN mkdir -p logs

# Variável de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV DRY_RUN=true

# Script de saúde (verifica se dashboard está respondendo)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/api/health || exit 1

# Inicia o bot
CMD ["python", "bot/main.py"]
