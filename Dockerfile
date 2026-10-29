# syntax=docker/dockerfile:1
FROM python:3.11-slim AS runtime

# Install curl for healthcheck and ca-certificates for outbound TLS
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root system user and group
RUN groupadd -g 10001 exabyte && \
    useradd -u 10001 -g exabyte -m -s /bin/bash exabyte

WORKDIR /app

# Install dependencies first for optimal Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and assets
COPY pyproject.toml .
COPY exabyte_bot/ exabyte_bot/
COPY scripts/ scripts/

# Prepare persistent data directory with non-root ownership
RUN mkdir -p /app/data && chown -R exabyte:exabyte /app

# Switch to non-root user
USER exabyte

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/healthz || exit 1

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "-m", "exabyte_bot.main"]
