#!/bin/bash
# OAuth CTF Advanced - Deployment Script
# Run this on GCP instance

set -e

echo "=========================================="
echo "OAuth CTF Advanced - Deployment"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (sudo ./deploy.sh)"
  exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
apt-get update
apt-get install -y docker.io docker-compose curl

# Start Docker
echo "🐳 Starting Docker..."
systemctl start docker
systemctl enable docker

# Get instance external IP
echo "🌐 Getting instance IP..."
INSTANCE_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")
echo "Instance IP: $INSTANCE_IP"

# Generate JWT secret if .env doesn't exist
if [ ! -f .env ]; then
  echo "🔐 Generating JWT secret..."
  python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))" > .env
  echo "BASE_URL=http://$INSTANCE_IP:8080" >> .env
else
  echo "✅ .env file already exists"
fi

# Build and start containers
echo "🚀 Building Docker images..."
docker-compose build

echo "🚀 Starting containers..."
docker-compose up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 10

# Health check
echo "🏥 Running health check..."
if curl -s http://localhost:8080/ > /dev/null; then
  echo "✅ Service is running!"
else
  echo "❌ Service failed to start"
  docker-compose logs
  exit 1
fi

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "Access URL: http://$INSTANCE_IP:8080"
echo ""
echo "Useful commands:"
echo "  docker-compose ps          - Check status"
echo "  docker-compose logs -f     - View logs"
echo "  docker-compose restart     - Restart services"
echo "  docker-compose down        - Stop services"
echo ""
