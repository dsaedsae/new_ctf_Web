#!/bin/bash
# Prepare clean deployment package (run locally)

set -e

DEPLOY_DIR="oauth-ctf-deploy"

echo "=========================================="
echo "Preparing Deployment Package"
echo "=========================================="

# Remove old deploy directory
if [ -d "$DEPLOY_DIR" ]; then
  echo "🗑️  Removing old deployment directory..."
  rm -rf "$DEPLOY_DIR"
fi

# Create clean deployment directory
echo "📦 Creating deployment package..."
mkdir -p "$DEPLOY_DIR"

# Copy necessary files
echo "📋 Copying files..."
cp -r auth-server "$DEPLOY_DIR/"
cp -r resource-server "$DEPLOY_DIR/"
cp -r client "$DEPLOY_DIR/"
cp -r nginx "$DEPLOY_DIR/"
cp docker-compose.yml "$DEPLOY_DIR/"
cp .env.example "$DEPLOY_DIR/"
cp deploy.sh "$DEPLOY_DIR/"
cp monitor.sh "$DEPLOY_DIR/"

# Create simplified README
cat > "$DEPLOY_DIR/README.md" << 'EOF'
# OAuth CTF Challenge

## Deployment

```bash
sudo ./deploy.sh
```

## Monitoring

```bash
./monitor.sh
```

## Access

http://YOUR_INSTANCE_IP:8080

## Goal

Find the FLAG: `MSG{...}`
EOF

# Clean up
echo "🧹 Cleaning up..."
find "$DEPLOY_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$DEPLOY_DIR" -name "*.pyc" -delete 2>/dev/null || true
find "$DEPLOY_DIR" -name ".DS_Store" -delete 2>/dev/null || true

# Make scripts executable
chmod +x "$DEPLOY_DIR/deploy.sh"
chmod +x "$DEPLOY_DIR/monitor.sh"

# Show size
SIZE=$(du -sh "$DEPLOY_DIR" | cut -f1)

echo ""
echo "=========================================="
echo "✅ Deployment Package Ready!"
echo "=========================================="
echo ""
echo "Location: ./$DEPLOY_DIR"
echo "Size: $SIZE"
echo ""
echo "Next steps:"
echo "1. Upload to GCP:"
echo "   gcloud compute scp --recurse $DEPLOY_DIR INSTANCE_NAME:~/"
echo ""
echo "2. SSH to instance:"
echo "   gcloud compute ssh INSTANCE_NAME"
echo ""
echo "3. Deploy:"
echo "   cd $DEPLOY_DIR && sudo ./deploy.sh"
echo ""
