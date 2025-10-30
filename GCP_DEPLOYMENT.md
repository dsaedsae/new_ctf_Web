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

**결론**: GCP가 **더 저렴**하고 무료 티어도 있어 CTF 운영에 적합!

---

## 👥 참가자 수에 따른 인스턴스 선택 (중요!)

| 참가자 수 | 권장 인스턴스 | vCPU | RAM | 월 비용 (서울) | 비고 |
|-----------|--------------|------|-----|---------------|------|
| **10-30명** | e2-micro | 2 (버스트) | 1GB | $6-7 | 테스트/소규모 |
| **30-80명** | e2-small | 2 | 2GB | $13 | 일반 대회 |
| **100-200명** | **e2-medium** | 2 | 4GB | **$26** | **권장!** |
| **200-500명** | e2-standard-2 | 2 | 8GB | $49 | 대규모 대회 |
| **500명+** | Load Balancer | - | - | 변동 | Auto Scaling |

### ⚠️ 100명 이상 시 주의사항:

**e2-micro는 부족합니다!** 다음 부하가 예상됩니다:

```
예상 트래픽 (100명 기준, 2시간):
- 총 요청: 5,000 - 20,000 requests
- 동시 접속: 50-80명
- 피크 부하: 50-100 req/sec (초기 러시)

부하 발생 지점:
1. /admin/login: time.sleep(1.5) → 연결 고갈 위험
2. NoSQL $where 쿼리: MongoDB CPU 소모
3. subprocess (ping/traceroute): 프로세스 스폰 비용
4. MongoDB 메모리: 1GB 중 ~300MB 사용

결과:
- e2-micro (1GB RAM): Swap 발생 → 느려짐
- e2-small (2GB RAM): 가능하지만 빡빡함
- e2-medium (4GB RAM): 안정적 ✅
```

**권장: 100명 이상이면 e2-medium 사용!**

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
   - 머신 유형: e2-micro (테스트용) 또는 **e2-medium (100명 이상)**
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

# VM 생성 (테스트/소규모용)
# 참고: Ephemeral IP 자동 할당 (무료!) - Static IP 불필요
gcloud compute instances create ctf-server \
    --zone=asia-northeast3-a \
    --machine-type=e2-micro \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=30GB \
    --tags=http-server,https-server

# 100명 이상 대회용 (권장!)
# 참고: Ephemeral IP 자동 할당 (무료!) - Static IP 불필요
gcloud compute instances create ctf-server \
    --zone=asia-northeast3-a \
    --machine-type=e2-medium \
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

### 0. Rate Limiting (100명 이상 필수!)

**문제**: 참가자들이 브루트포스 시도 시 서버 과부하

**해결**: Flask-Limiter 추가 (app.py 수정)

```python
# app.py에 추가
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# 각 엔드포인트에 적용
@app.route('/admin/login', methods=['POST'])
@limiter.limit("10 per minute")  # Red Herring 공격 방지
def admin_login_post():
    # ... 기존 코드

@app.route('/api/admin/search', methods=['POST'])
@limiter.limit("30 per minute")  # NoSQL Injection 시도 제한
def admin_search():
    # ... 기존 코드

@app.route('/api/admin/tools/ping', methods=['POST'])
@limiter.limit("20 per minute")  # Command Injection 시도 제한
def admin_tools_ping():
    # ... 기존 코드
```

설치:
```bash
# requirements.txt에 추가
echo "Flask-Limiter==3.5.0" >> requirements.txt
docker-compose down
docker-compose up -d --build
```

**효과**:
- /admin/login: 분당 10회 제한 → 브루트포스 불가
- /api/admin/search: 분당 30회 제한 → NoSQL 과도한 시도 방지
- /api/admin/tools/ping: 분당 20회 제한 → subprocess 남용 방지
- 서버 부하 80% 감소 예상!

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

### 💡 Static IP vs Ephemeral IP (중요!)

**CTF 대회는 Ephemeral IP로 충분합니다!**

| 항목 | Ephemeral IP | Static IP |
|------|-------------|-----------|
| **비용** | **무료** ✅ | $3-7/월 💰 |
| **할당** | VM 시작 시 자동 | 수동 예약 필요 |
| **VM 중지 시** | IP 해제됨 | IP 유지 (비용 발생) |
| **CTF 적합성** | **적합** ✅ | 불필요 ❌ |

**Ephemeral IP 사용 플로우 (권장)**:
```bash
# 1. 대회 시작 전 (예: 1-2시간 전)
gcloud compute instances start ctf-server --zone=asia-northeast3-a

# 2. IP 확인 및 참가자에게 공유
EXTERNAL_IP=$(gcloud compute instances describe ctf-server \
    --zone=asia-northeast3-a \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo "CTF URL: http://$EXTERNAL_IP:5000"

# 3. 대회 진행 중 VM 유지 (IP 변경 안 됨)
# ...대회 진행...

# 4. 대회 종료 후 VM 중지 (IP 해제)
gcloud compute instances stop ctf-server --zone=asia-northeast3-a
```

**Static IP가 필요한 경우**:
- DNS 레코드 사전 등록 필요
- 장기간(1주일+) 운영
- IP 변경 불가능한 환경

**비용 차이 (e2-medium, 서울, 2일 대회)**:
```
Ephemeral IP:
- VM: $26/월 × (48시간/720시간) = $1.73
- 네트워크: ~$1
- 디스크: $0.13
- 총: ~$2.86 ✅

Static IP 추가 시:
- 위 비용 + Static IP: $3-7/월
- 총: ~$5.86-9.86 💰 (2배 이상!)
```

**결론**: **CTF는 Ephemeral IP 사용하세요! 50-60% 비용 절감!**

### 무료 티어 확인

```
GCP Console > 결제 > 보고서
```

**무료 한도**:
- e2-micro 인스턴스: 1개 (US 리전만, asia는 유료)
- Ephemeral 외부 IP: 무료 (VM 실행 중)
- 디스크: 30GB
- 송신 트래픽: 1GB/월

**참고**: **서울(asia-northeast3)은 무료 티어 대상이 아님!**
무료 사용하려면 `us-west1`, `us-central1`, `us-east1` 사용

### 비용 절약 팁

1. **Ephemeral IP 사용** ⭐ 최고 절약:
   - Static IP 예약 안 함 (위 참조)
   - 50-60% 비용 절감!

2. **리전 선택**:
   - 무료: us-west1 (오레곤)
   - 유료 저렴: asia-northeast3 (서울) - 레이턴시 좋음

3. **사용하지 않을 때 중지**:
```bash
gcloud compute instances stop ctf-server --zone=asia-northeast3-a
# 디스크 비용만 발생 (~$2/월)
```

4. **예약 할인**:
   - 1년 약정: 37% 할인
   - 3년 약정: 55% 할인

5. **대회 직전 시작, 직후 중지**:
```bash
# 대회 1시간 전 시작
gcloud compute instances start ctf-server --zone=asia-northeast3-a

# 대회 종료 즉시 중지 (시간당 과금이므로 빠를수록 좋음)
gcloud compute instances stop ctf-server --zone=asia-northeast3-a
```

**예시 (e2-medium, 100명, 3시간 대회)**:
```
- VM 비용: $26/월 × (3시간/720시간) = $0.11
- 네트워크: ~$0.50
- 디스크: $0.08 (항상 발생)
- 총: ~$0.69 (1달러도 안 됨!) 🎉
```

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
# 사용법: ./deploy-gcp.sh [participants]
# 예시: ./deploy-gcp.sh 150  (150명 참가자 → e2-medium 자동 선택)

set -e

PROJECT_ID="ctf-challenge"
INSTANCE_NAME="ctf-server"
ZONE="asia-northeast3-a"
PARTICIPANTS=${1:-30}  # 기본 30명

# 참가자 수에 따라 인스턴스 크기 결정
if [ $PARTICIPANTS -lt 30 ]; then
    MACHINE_TYPE="e2-micro"
    echo "📊 참가자: $PARTICIPANTS명 → e2-micro 선택"
elif [ $PARTICIPANTS -lt 100 ]; then
    MACHINE_TYPE="e2-small"
    echo "📊 참가자: $PARTICIPANTS명 → e2-small 선택"
elif [ $PARTICIPANTS -lt 200 ]; then
    MACHINE_TYPE="e2-medium"
    echo "📊 참가자: $PARTICIPANTS명 → e2-medium 선택 (권장)"
else
    MACHINE_TYPE="e2-standard-2"
    echo "📊 참가자: $PARTICIPANTS명 → e2-standard-2 선택 (대규모)"
fi

echo "🚀 GCP CTF 배포 시작..."
echo "💻 머신 타입: $MACHINE_TYPE"

# 1. VM 생성
echo "📦 VM 생성 중..."
# 참고: --address 옵션 없음 = Ephemeral IP 자동 할당 (무료!)
# Static IP 사용하려면: --address=STATIC_IP_NAME (비추천, $3-7/월 추가 비용)
gcloud compute instances create $INSTANCE_NAME \
    --project=$PROJECT_ID \
    --zone=$ZONE \
    --machine-type=$MACHINE_TYPE \
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

# 기본 (30명 소규모)
./deploy-gcp.sh

# 100명 대회 (e2-medium 자동 선택)
./deploy-gcp.sh 100

# 200명 대규모 (e2-standard-2 자동 선택)
./deploy-gcp.sh 200
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
