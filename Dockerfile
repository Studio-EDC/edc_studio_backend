FROM python:3.11-slim

# Instala dependencias necesarias, incluyendo OpenJDK 17
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    lsb-release \
    apt-transport-https \
    docker.io \
    openjdk-17-jdk \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

# Crear carpeta para el plugin y descargar docker compose
RUN mkdir -p /usr/local/lib/docker/cli-plugins && \
    curl -SL https://github.com/docker/compose/releases/download/v2.23.3/docker-compose-linux-x86_64 \
        -o /usr/local/lib/docker/cli-plugins/docker-compose && \
    chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Verifica que esté bien instalado
RUN docker compose version && keytool -help

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
