#!/bin/bash
# OAuth CTF Advanced - Quick Scale Script
# 긴급 증설용 스크립트 (로컬 PC에서 실행)

ZONE="asia-northeast3-a"
IMAGE="oauth-ctf-golden-image"
INSTANCE_NAME="oauth-ctf-$1"

if [ -z "$1" ]; then
  echo "Usage: ./quick-scale.sh <instance-number>"
  echo "Example: ./quick-scale.sh 3"
  exit 1
fi

echo "=========================================="
echo "OAuth CTF - Quick Scale"
echo "=========================================="
echo ""
echo "🚀 Creating instance: $INSTANCE_NAME"
echo "Zone: $ZONE"
echo "Image: $IMAGE"
echo ""

# 인스턴스 생성
gcloud compute instances create $INSTANCE_NAME \
  --zone=$ZONE \
  --machine-type=e2-medium \
  --image=$IMAGE \
  --boot-disk-size=20GB \
  --tags=ctf-server

if [ $? -ne 0 ]; then
  echo "❌ Failed to create instance"
  exit 1
fi

echo ""
echo "⏳ Waiting for instance to start (30 seconds)..."
sleep 30

# SSH로 서비스 시작
echo ""
echo "🐳 Starting Docker containers..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="cd oauth-ctf-deploy && docker-compose up -d" 2>/dev/null

if [ $? -ne 0 ]; then
  echo "⚠️  Warning: Could not start containers automatically"
  echo "Please SSH manually and run: cd oauth-ctf-deploy && docker-compose up -d"
fi

# IP 획득
echo ""
echo "🌐 Getting IP address..."
IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "=========================================="
echo "✅ New server ready!"
echo "=========================================="
echo ""
echo "Instance: $INSTANCE_NAME"
echo "IP: $IP"
echo "Access URL: http://$IP:8080"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Copy this to Discord/Slack:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🚀 추가 서버 오픈!"
echo "서버가 느린 분들은 아래 IP로 접속하세요:"
echo "http://$IP:8080"
echo ""
echo "기존 서버도 계속 사용 가능합니다."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Verify deployment:"
echo "  curl http://$IP:8080/"
echo ""
echo "Monitor instance:"
echo "  gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo "  cd oauth-ctf-deploy && ./monitor.sh"
echo ""
