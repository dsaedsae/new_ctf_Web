FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite database
RUN mkdir -p /app/data

# ========== Security Hardening ==========

# 1. Create non-root user
RUN useradd -m -u 1000 -s /bin/bash ctfuser

# 2. Set file permissions
RUN chown -R root:root /app && \
    chmod 644 /app/app_sqlite.py && \
    chmod 644 /app/requirements.txt

# Data directory: writable by ctfuser (for SQLite database)
RUN chown ctfuser:ctfuser /app/data && \
    chmod 755 /app/data

# 3. Switch to non-root user
USER ctfuser

# ========================================

# Expose port
EXPOSE 8000

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=0

# Run the application
CMD ["python", "app_sqlite.py"]