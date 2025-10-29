FROM python:3.9-slim

# Metadata
LABEL maintainer="ctf-admin"
LABEL description="Legacy Microservice Exploitation CTF Challenge V3.0"
LABEL version="3.0"

# Security: Create non-root user
RUN useradd -m -u 1000 -s /bin/bash ctfuser

# Set working directory
WORKDIR /app

# Environment variables (defaults, override with .env)
ENV PYTHONUNBUFFERED=1

# Install system dependencies for gevent
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py init_db.py docker-entrypoint.sh ./

# Fix potential CRLF line endings
RUN sed -i 's/\r$//' docker-entrypoint.sh || true

# Make entrypoint executable
RUN chmod +x docker-entrypoint.sh

# Set file ownership
RUN chown -R ctfuser:ctfuser /app

# Switch to non-root user
USER ctfuser

# Expose port
EXPOSE 5000

# Health check using urllib (no external dependencies)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request, json; \
    response = urllib.request.urlopen('http://localhost:5000/health'); \
    data = json.loads(response.read()); \
    exit(0 if data.get('javascript_enabled') else 1)"

# Use custom entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]
