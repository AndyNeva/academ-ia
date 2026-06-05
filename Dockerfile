FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos del proyecto
COPY requirements-api.txt .
COPY api.py .
COPY main.py .
COPY src/ ./src/
COPY data/ ./data/
COPY markdowns/ ./markdowns/

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements-api.txt

# Crear carpetas necesarias
RUN mkdir -p data/pdfs Obsidian_Vault

# Exposar puerto
EXPOSE 8000

# Comando para iniciar (Railway inyecta PORT automaticamente)
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
