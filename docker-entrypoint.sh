#!/bin/sh
# Container entrypoint script V3.0
#
# V3.0 FIXES:
# - Fixed logic error with set -e
# - Uses gevent workers for better performance

echo "=========================================="
echo "CTF Container Startup - V3.0"
echo "=========================================="

# Step 1: Initialize database
echo "[1/2] Initializing database..."

# Option 1: Let set -e handle errors automatically
python3 init_db.py || {
    echo "[ERROR] Database initialization failed"
    echo "[ERROR] Check MongoDB JavaScript configuration"
    exit 1
}

echo "[1/2] Database initialization complete ✓"

# Step 2: Start web server with gevent workers
echo "[2/2] Starting Gunicorn web server (gevent mode)..."
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --worker-class gevent \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
