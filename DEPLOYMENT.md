# GCP Deployment Guide

## Prerequisites

- GCP account with billing enabled  
- gcloud CLI installed
- Docker installed locally (for testing)

## Step 1: Prepare Environment

```bash
# Copy environment template
cp .env.example .env

# Generate JWT secret
python3 -c "import secrets; print(secrets.token_urlsafe(64))"

# Edit .env file
nano .env
```

Set in `.env`:
```bash
JWT_SECRET=<generated-secret>
BASE_URL=http://<YOUR_GCP_IP>:8080
```

## Step 2: Create GCP VM Instance

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Create VM (Ubuntu 22.04, e2-medium)
gcloud compute instances create oauth-ctf \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,oauth-ctf

# Create firewall rule
gcloud compute firewall-rules create allow-oauth-ctf \
  --allow=tcp:8080 \
  --target-tags=oauth-ctf \
  --source-ranges=0.0.0.0/0 \
  --description="Allow OAuth CTF traffic on port 8080"
```

## Step 3: Install Docker on VM

```bash
# SSH to VM
gcloud compute ssh oauth-ctf --zone=us-central1-a

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version
```

## Step 4: Upload Files

```bash
# From your local machine
gcloud compute scp --recurse . oauth-ctf:~/oauth-ctf --zone=us-central1-a \
  --exclude=".git" --exclude="docs" --exclude="WRITEUP.md" --exclude="__pycache__"
```

## Step 5: Configure and Start

```bash
# On GCP VM
cd oauth-ctf

# Get external IP
EXTERNAL_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")
echo "External IP: $EXTERNAL_IP"

# Update .env
sed -i "s|BASE_URL=.*|BASE_URL=http://$EXTERNAL_IP:8080|g" .env

# Verify .env
cat .env

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f
```

## Step 6: Verify Deployment

```bash
# Get external IP (from local machine)
EXTERNAL_IP=$(gcloud compute instances describe oauth-ctf --zone=us-central1-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "CTF URL: http://$EXTERNAL_IP:8080"

# Test endpoints
curl http://$EXTERNAL_IP:8080
curl http://$EXTERNAL_IP:8080/robots.txt
curl http://$EXTERNAL_IP:8080/.well-known/oauth-authorization-server
```

## Monitoring

```bash
# View logs
docker-compose logs -f auth-server
docker-compose logs -f resource-server
docker-compose logs -f nginx

# Check running containers
docker-compose ps

# Restart if needed
docker-compose restart
docker-compose down && docker-compose up -d
```

## Cleanup

```bash
# Stop services
docker-compose down -v

# Delete VM (from local machine)
gcloud compute instances delete oauth-ctf --zone=us-central1-a --quiet

# Delete firewall rule
gcloud compute firewall-rules delete allow-oauth-ctf --quiet
```

## Security Checklist

- ✅ JWT_SECRET is random and strong
- ✅ .env not committed to git
- ✅ Firewall only allows port 8080
- ✅ Internal networks isolated
- ✅ No WRITEUP.md or docs/ in deployment

## Troubleshooting

**Services not accessible:**
```bash
# Check firewall
gcloud compute firewall-rules list | grep oauth

# Check docker
docker-compose ps
docker-compose logs nginx
```

**500 errors:**
```bash
# Check application logs
docker-compose logs auth-server
docker-compose logs resource-server

# Restart
docker-compose restart
```

**Port already in use:**
```bash
# Check what's using port 8080
sudo lsof -i :8080
sudo netstat -tlnp | grep 8080

# Kill process or change port
```
