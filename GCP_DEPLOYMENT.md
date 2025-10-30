# GCP 배포 가이드 (Google Cloud Platform)

CTF 문제를 GCP에 배포하는 가이드입니다. AWS보다 저렴하고 무료 티어가 있어 추천합니다.

---

## 💰 GCP vs AWS 가격 비교

| 항목 | AWS | GCP | 비고 |
|------|-----|-----|------|
| **무료 티어** | t2.micro (750시간/월) | e2-micro (무료 영구) | **GCP 승!** |
| **메모리** | 1GB | 1GB | 동일 |
| **네트워크** | 15GB/월 무료 | 1GB/월 무료 | AWS 승 |
| **스토리지** | 30GB | 30GB | 동일 |
| **유료 시** | ~$10/월 | ~$7/월 | **GCP 승!** |

**결론**: GCP e2-micro가 **영구 무료**라서 CTF 운영에 최적!

---

## 🚀 빠른 시작 (5분 배포)

### 1단계: GCP 프로젝트 설정

```bash
# GCP Console에서
1. https://console.cloud.google.com/ 접속
2. 프로젝트 생성: "ctf-challenge"
3. 결제 계정 연결 (무료 티어 사용 가능)
```

### 2단계: Compute Engine 인스턴스 생성

#### 방법 A: 웹 콘솔 (초보자 추천)

```
1. Compute Engine > VM 인스턴스 > 만들기
2. 설정:
   - 이름: ctf-server
   - 리전: asia-northeast3 (서울)
   - 머신 유형: e2-micro (무료!)
   - 부팅 디스크: Ubuntu 22.04 LTS (30GB)
   - 방화벽: HTTP, HTTPS 트래픽 허용
3. 만들기 클릭
```

#### 방법 B: gcloud CLI (빠름)

```bash
# gcloud CLI 설치 (로컬)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL
gcloud init

# VM 생성
gcloud compute instances create ctf-server \
    --zone=asia-northeast3-a \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --tags=http-server,https-server
```

### 3단계: 방화벽 규칙 추가

```bash
# 5000번 포트 열기 (Flask 기본 포트)
gcloud compute firewall-rules create allow-ctf \
    --allow=tcp:5000 \
    --source-ranges=0.0.0.0/0 \
    --target-tags=http-server \
    --description="CTF Challenge Port"
```

또는 웹 콘솔:
```
VPC 네트워크 > 방화벽 > 방화벽 규칙 만들기
- 이름: allow-ctf
- 대상: 네트워크의 모든 인스턴스
- 소스 IP 범위: 0.0.0.0/0
- 프로토콜 및 포트: tcp:5000
```

### 4단계: SSH 접속 및 Docker 설치

```bash
# SSH 접속
gcloud compute ssh ctf-server --zone=asia-northeast3-a

# 또는 웹 콘솔에서 "SSH" 버튼 클릭
```

서버 접속 후:

```bash
# Docker 설치
sudo apt-get update
sudo apt-get install -y docker.io docker-compose git

# Docker 권한 설정
sudo usermod -aG docker $USER
newgrp docker

# 확인
docker --version
docker-compose --version
```

### 5단계: 코드 배포

```bash
# Git에서 클론
git clone https://github.com/YOUR_USERNAME/new_ctf_Web.git
cd new_ctf_Web

# 또는 파일 업로드 (로컬에서)
gcloud compute scp --recurse ./* ctf-server:~/ctf --zone=asia-northeast3-a
```

### 6단계: 환경 설정

```bash
# .env 파일 생성
cat > .env << 'EOF'
COMPANY_SALT=insane2
FLAG=FLAG{l3g4cy_s3rv1c3s_4r3_d4ng3r0us_wh3n_f0rg0tt3n}
BLIND_RCE=true
CTF_PORT=5000
EOF
```

### 7단계: 실행!

```bash
# Docker Compose 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 상태 확인
docker-compose ps
```

### 8단계: 접속 테스트

```bash
# 외부 IP 확인
gcloud compute instances describe ctf-server \
    --zone=asia-northeast3-a \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# 또는
curl http://$(gcloud compute instances describe ctf-server --zone=asia-northeast3-a --format='get(networkInterfaces[0].accessConfigs[0].natIP)'):5000
```

브라우저에서:
```
http://YOUR_EXTERNAL_IP:5000
```

---

## 🎯 완료!

**접속 URL**: `http://YOUR_EXTERNAL_IP:5000`

**참가자에게 제공할 URL**:
```
Challenge URL: http://34.64.XXX.XXX:5000
Difficulty: DreamHack Level 8
Time Limit: 2.5 hours
```

---

## 📊 모니터링

### 로그 확인
```bash
# 실시간 로그
docker-compose logs -f

# 특정 서비스만
docker-compose logs -f web
docker-compose logs -f db
```

### 리소스 사용량
```bash
# CPU/메모리
docker stats

# 디스크
df -h
```

### 접속자 수
```bash
# Nginx 액세스 로그 (옵션)
docker-compose exec web tail -f /var/log/access.log
```

---

## 🔧 유지보수

### 재시작
```bash
docker-compose restart
```

### 업데이트
```bash
git pull
docker-compose down
docker-compose up -d --build
```

### 완전 초기화
```bash
docker-compose down -v  # 볼륨까지 삭제
docker-compose up -d
```

### 백업
```bash
# MongoDB 백업
docker-compose exec db mongodump --out /backup
docker cp ctf_db:/backup ./backup_$(date +%Y%m%d)
```

---

## 💡 성능 최적화

### e2-micro가 부족하다면?

```bash
# 인스턴스 업그레이드 (유료)
gcloud compute instances stop ctf-server --zone=asia-northeast3-a
gcloud compute instances set-machine-type ctf-server \
    --machine-type=e2-small \
    --zone=asia-northeast3-a
gcloud compute instances start ctf-server --zone=asia-northeast3-a
```

**가격**:
- e2-micro: 무료 (또는 $6.11/월)
- e2-small: $13.23/월
- e2-medium: $26.45/월

### Swap 메모리 추가 (무료)

```bash
# 1GB swap 추가
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## 🔒 보안 설정 (중요!)

### 1. SSH 키 기반 인증

```bash
# 로컬에서
ssh-keygen -t ed25519 -C "ctf-admin"
gcloud compute config-ssh

# ~/.ssh/config에 자동 추가됨
ssh ctf-server.asia-northeast3-a.ctf-challenge
```

### 2. 방화벽 강화

```bash
# 특정 IP만 SSH 허용
gcloud compute firewall-rules create allow-ssh-from-office \
    --allow=tcp:22 \
    --source-ranges=YOUR_OFFICE_IP/32 \
    --target-tags=http-server
```

### 3. 자동 업데이트

```bash
# Unattended upgrades 설치
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4. Fail2ban (선택)

```bash
sudo apt-get install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

---

## 📈 비용 관리

### 무료 티어 확인

```
GCP Console > 결제 > 보고서
```

**무료 한도**:
- e2-micro 인스턴스: 1개 (US 리전만, asia는 유료)
- 외부 IP: 1개
- 디스크: 30GB
- 송신 트래픽: 1GB/월

**참고**: **서울(asia-northeast3)은 무료 티어 대상이 아님!**
무료 사용하려면 `us-west1`, `us-central1`, `us-east1` 사용

### 비용 절약 팁

1. **리전 선택**:
   - 무료: us-west1 (오레곤)
   - 유료 저렴: asia-northeast3 (서울) - 레이턴시 좋음

2. **사용하지 않을 때 중지**:
```bash
gcloud compute instances stop ctf-server --zone=asia-northeast3-a
# 디스크 비용만 발생 (~$2/월)
```

3. **예약 할인**:
   - 1년 약정: 37% 할인
   - 3년 약정: 55% 할인

---

## 🌐 도메인 연결 (선택)

### Cloud DNS 사용

```bash
# DNS 영역 생성
gcloud dns managed-zones create ctf-zone \
    --dns-name="your-domain.com." \
    --description="CTF Challenge Domain"

# A 레코드 추가
gcloud dns record-sets transaction start --zone=ctf-zone
gcloud dns record-sets transaction add YOUR_EXTERNAL_IP \
    --name="ctf.your-domain.com." \
    --ttl=300 \
    --type=A \
    --zone=ctf-zone
gcloud dns record-sets transaction execute --zone=ctf-zone
```

### 무료 도메인 대안

- [Freenom](https://www.freenom.com/) - .tk, .ml, .ga 무료
- [No-IP](https://www.noip.com/) - 무료 DDNS

---

## 📱 자동화 스크립트

### 원클릭 배포 스크립트

```bash
#!/bin/bash
# deploy-gcp.sh

set -e

PROJECT_ID="ctf-challenge"
INSTANCE_NAME="ctf-server"
ZONE="asia-northeast3-a"

echo "🚀 GCP CTF 배포 시작..."

# 1. VM 생성
echo "📦 VM 생성 중..."
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --tags=http-server

# 2. 방화벽 규칙
echo "🔥 방화벽 설정 중..."
gcloud compute firewall-rules create allow-ctf-5000 \
    --project=$PROJECT_ID \
    --allow=tcp:5000 \
    --source-ranges=0.0.0.0/0

# 3. 30초 대기 (부팅 시간)
echo "⏳ 부팅 대기 중..."
sleep 30

# 4. 설치 스크립트 전송 및 실행
echo "📝 Docker 설치 중..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='
    sudo apt-get update && \
    sudo apt-get install -y docker.io docker-compose git && \
    sudo usermod -aG docker $USER
'

# 5. 코드 배포
echo "📤 코드 업로드 중..."
gcloud compute scp --recurse ./* $INSTANCE_NAME:~/ctf --zone=$ZONE

# 6. 실행
echo "🎯 컨테이너 시작 중..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command='
    cd ~/ctf && \
    docker-compose up -d
'

# 7. 외부 IP 출력
EXTERNAL_IP=$(gcloud compute instances describe $INSTANCE_NAME \
    --zone=$ZONE \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "✅ 배포 완료!"
echo "🌐 접속 URL: http://$EXTERNAL_IP:5000"
echo ""
```

실행:
```bash
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

---

## 🆘 트러블슈팅

### 문제: 접속이 안 됨

```bash
# 1. 컨테이너 상태 확인
docker-compose ps

# 2. 로그 확인
docker-compose logs

# 3. 방화벽 확인
gcloud compute firewall-rules list

# 4. 포트 확인
sudo netstat -tlnp | grep 5000
```

### 문제: 메모리 부족

```bash
# 메모리 사용량 확인
free -h

# Swap 추가 (위 참조)
# 또는 인스턴스 업그레이드
```

### 문제: MongoDB 연결 실패

```bash
# MongoDB 로그 확인
docker-compose logs db

# 재시작
docker-compose restart db

# 볼륨 초기화
docker-compose down -v
docker-compose up -d
```

### 문제: 디스크 공간 부족

```bash
# 디스크 사용량 확인
df -h

# Docker 정리
docker system prune -a --volumes

# 로그 정리
sudo journalctl --vacuum-time=3d
```

---

## 📞 지원

**문제 발생 시**:
1. 로그 확인: `docker-compose logs`
2. 이슈 등록: GitHub Issues
3. GCP 문서: https://cloud.google.com/compute/docs

---

## 🎓 추가 정보

### GCP 크레딧

- 신규 가입: $300 크레딧 (90일)
- 학생: Google Cloud for Students ($50/년)
- 스타트업: Google Cloud Startup Program (최대 $100,000)

### 모니터링 도구

```bash
# Cloud Monitoring 설치
curl -sSO https://dl.google.com/cloudagents/add-monitoring-agent-repo.sh
sudo bash add-monitoring-agent-repo.sh
sudo apt-get install -y stackdriver-agent
```

---

**배포 완료! 이제 CTF 참가자들에게 URL을 공유하세요!** 🎉
