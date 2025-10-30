# 배포 가이드 (DEPLOYMENT.md)

## 🎯 배포 개요

### GitHub Actions의 역할
❌ **잘못된 이해**: GitHub Actions로 문제를 직접 호스팅
✅ **올바른 이해**: GitHub Actions는 빌드/테스트 자동화용, 실제 호스팅은 별도 서버 필요

```
GitHub Actions        실제 서버
─────────────        ───────────
빌드 자동화    →     VPS/클라우드
테스트 자동화   →     Docker 실행
이미지 푸시     →     참가자 접속
```

---

## 📋 배포 옵션 비교

| 옵션 | 난이도 | 비용 | 확장성 | 추천 |
|-----|--------|-----|--------|------|
| **로컬 서버** | 쉬움 | 무료 | 낮음 | 테스트용 |
| **VPS (Vultr, DigitalOcean)** | 중간 | $5-20/월 | 중간 | ✅ 추천 |
| **AWS/GCP/Azure** | 어려움 | 변동 | 높음 | 대규모 |
| **Heroku/Railway** | 쉬움 | $5-10/월 | 중간 | 간단 배포 |
| **CTFd 플랫폼** | 중간 | $10-50/월 | 높음 | 통합 관리 |

---

## 🚀 방법 1: VPS 배포 (추천)

### A. 서버 준비

#### 1-1. VPS 제공업체 선택
```
추천:
- DigitalOcean ($6/월, 1GB RAM)
- Vultr ($5/월, 1GB RAM)
- Linode ($5/월, 1GB RAM)
- AWS Lightsail ($5/월)
```

#### 1-2. 서버 스펙 권장사항
```yaml
최소 사양:
  CPU: 1 core
  RAM: 1GB
  Disk: 25GB SSD
  OS: Ubuntu 22.04 LTS

권장 사양 (참가자 50명+):
  CPU: 2 cores
  RAM: 2GB
  Disk: 50GB SSD
  OS: Ubuntu 22.04 LTS
```

### B. 서버 초기 설정

```bash
# 1. SSH 접속
ssh root@your-server-ip

# 2. 시스템 업데이트
apt update && apt upgrade -y

# 3. Docker 설치
curl -fsSL https://get.docker.com | sh

# 4. Docker Compose 설치
apt install docker-compose -y

# 5. 방화벽 설정
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw enable

# 6. 비root 사용자 생성 (선택사항)
adduser ctfadmin
usermod -aG docker ctfadmin
usermod -aG sudo ctfadmin
```

### C. 코드 배포

```bash
# 1. 프로젝트 클론
cd /opt
git clone https://github.com/your-org/ctf-legacy-microservice.git
cd ctf-legacy-microservice

# 2. .env 파일 생성
cp .env.example .env
nano .env

# 3. COMPANY_SALT 설정 (필수!)
# 랜덤 값 생성:
openssl rand -hex 16

# .env 파일 편집:
COMPANY_SALT=<위에서 생성한 랜덤 값>
FLAG=FLAG{your_custom_flag_here}
CTF_PORT=5000
BLIND_RCE=false

# 4. 빌드 및 실행
docker-compose build
docker-compose up -d

# 5. 상태 확인
docker-compose ps
docker-compose logs -f
```

### D. 헬스 체크

```bash
# 로컬에서 확인
curl http://localhost:5000/health | jq

# 외부에서 확인
curl http://your-server-ip:5000/health | jq

# 예상 출력:
{
  "status": "healthy",
  "database": "connected",
  "javascript_enabled": true,  # ← 반드시 true
  "services": ["auth", "api", "legacy"]
}
```

### E. 도메인 연결 (선택사항)

```bash
# 1. DNS 레코드 설정
your-domain.com  →  A  →  your-server-ip

# 2. Nginx 설치 (리버스 프록시)
apt install nginx -y

# 3. Nginx 설정
cat > /etc/nginx/sites-available/ctf << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/ctf /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx

# 4. HTTPS 설정 (Let's Encrypt)
apt install certbot python3-certbot-nginx -y
certbot --nginx -d your-domain.com
```

---

## 🚀 방법 2: Docker Hub + 자동 배포

### A. GitHub Actions로 이미지 빌드

`.github/workflows/build.yml` 생성:
```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Login to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: your-org/ctf-legacy:latest
```

### B. 서버에서 자동 풀

```bash
# 서버에서 cron 설정
crontab -e

# 5분마다 최신 이미지 풀 및 재시작
*/5 * * * * cd /opt/ctf-legacy-microservice && docker-compose pull && docker-compose up -d
```

---

## 🚀 방법 3: Railway/Render (간단 배포)

### Railway 사용

```bash
# 1. Railway CLI 설치
npm install -g @railway/cli

# 2. 로그인
railway login

# 3. 프로젝트 생성
railway init

# 4. MongoDB 추가
railway add mongodb

# 5. 환경변수 설정
railway variables set COMPANY_SALT=$(openssl rand -hex 16)
railway variables set FLAG="FLAG{your_flag}"

# 6. 배포
railway up
```

**주의**: Railway는 MongoDB JavaScript를 제한할 수 있음 → VPS 추천

---

## 🚀 방법 4: CTFd 플랫폼 통합

### A. CTFd 설치

```bash
# 1. CTFd 클론
git clone https://github.com/CTFd/CTFd.git
cd CTFd

# 2. docker-compose 수정
# docker-compose.yml에 CTF 문제 추가:
services:
  ctfd:
    # ... 기존 설정 ...

  ctf-legacy:
    build: ../ctf-legacy-microservice
    environment:
      - COMPANY_SALT=${COMPANY_SALT}
      - FLAG=${FLAG}
    networks:
      - internal

# 3. 실행
docker-compose up -d
```

### B. CTFd에 문제 등록

```yaml
Challenge:
  이름: Legacy Microservice Exploitation
  카테고리: Web
  점수: 400
  설명: README.md 내용 복사
  URL: http://ctfd-server:5000
  플래그: FLAG{...}
```

---

## 📊 리소스 사용량 및 확장

### 예상 리소스 사용

```
1명 참가자:
  CPU: ~5%
  RAM: ~200MB

50명 동시 접속:
  CPU: ~50-70%
  RAM: ~1GB
  대역폭: ~10Mbps

100명 동시 접속:
  CPU: 2 cores 필요
  RAM: ~2GB
  대역폭: ~20Mbps
```

### 수평 확장 (대규모)

```yaml
# docker-compose.yml 수정
services:
  web:
    deploy:
      replicas: 3  # 3개 인스턴스
    environment:
      - COMPANY_SALT=${COMPANY_SALT}

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    ports:
      - "80:80"
    depends_on:
      - web
```

---

## 🔒 보안 권장사항

### 1. 방화벽 설정
```bash
# 필요한 포트만 열기
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw deny 5000/tcp   # Flask 직접 접근 차단 (Nginx 뒤로)
```

### 2. SSH 강화
```bash
# /etc/ssh/sshd_config
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

### 3. fail2ban 설치
```bash
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban
```

### 4. 로그 모니터링
```bash
# 실시간 로그 확인
docker-compose logs -f --tail=100

# 로그 저장
docker-compose logs > /var/log/ctf-challenge.log
```

---

## 🛠️ 트러블슈팅

### 문제 1: javascript_enabled: false

```bash
# MongoDB 컨테이너 확인
docker-compose exec db mongosh

# JavaScript 설정 확인
db.adminCommand({getParameter: 1, javascriptEnabled: 1})

# docker-compose.yml 확인
# db 서비스에 다음이 있어야 함:
command: mongod --setParameter javascriptEnabled=true
```

### 문제 2: 컨테이너가 시작 안 됨

```bash
# 로그 확인
docker-compose logs web

# 일반적 원인:
# 1. COMPANY_SALT 미설정
# 2. 포트 충돌 (5000 이미 사용 중)
# 3. MongoDB 연결 실패

# 해결:
docker-compose down -v
# .env 확인
docker-compose up -d
```

### 문제 3: 참가자가 접속 안 됨

```bash
# 방화벽 확인
ufw status

# 포트 리스닝 확인
netstat -tlnp | grep 5000

# Docker 네트워크 확인
docker network ls
docker network inspect ctf_network
```

---

## 📈 모니터링

### 기본 모니터링

```bash
# 리소스 사용량
docker stats

# 컨테이너 상태
watch -n 5 'docker-compose ps'

# 헬스 체크 자동화
watch -n 30 'curl -s http://localhost:5000/health | jq'
```

### Grafana + Prometheus (고급)

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

---

## 🎯 배포 체크리스트

### 배포 전
```
□ .env 파일 생성
□ COMPANY_SALT를 랜덤 값으로 설정
□ FLAG 설정
□ Docker 및 Docker Compose 설치
□ 방화벽 설정
□ 도메인/DNS 설정 (선택)
```

### 배포 시
```
□ git clone 또는 파일 업로드
□ docker-compose build
□ docker-compose up -d
□ 헬스 체크 확인 (javascript_enabled: true)
□ Exploit 테스트
```

### 배포 후
```
□ 모니터링 설정
□ 로그 확인
□ 백업 설정
□ 참가자 공지 (URL)
□ 긴급 연락처 준비
```

---

## 💰 비용 예상 (월간)

### 소규모 (참가자 ~50명)
```
VPS (1GB RAM):        $5-10
도메인 (선택):        $1/월
CDN (선택):          무료-$5
───────────────────────────
총계:                $6-16/월
```

### 중규모 (참가자 100-200명)
```
VPS (2GB RAM):        $12-20
도메인:              $1/월
CDN/로드밸런서:       $10
모니터링:            무료-$5
───────────────────────────
총계:                $23-36/월
```

### 대규모 (참가자 500+명)
```
클라우드 인스턴스:    $50-100
로드밸런서:          $20
모니터링:            $20
백업:               $10
───────────────────────────
총계:                $100-150/월
```

---

## 📞 긴급 대응

### 서비스 중단 시

```bash
# 1. 빠른 재시작
docker-compose restart

# 2. 완전 재빌드
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d

# 3. 백업에서 복원
cd /opt/ctf-backup
docker-compose up -d
```

### 부하 과다 시

```bash
# 1. 리소스 제한 추가
# docker-compose.yml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

# 2. Rate limiting 활성화 (Nginx)
limit_req_zone $binary_remote_addr zone=ctf:10m rate=10r/s;
```

---

## 🎓 추천 배포 흐름

```
1단계: 로컬 테스트
   ↓ (TESTING.md 참고)

2단계: VPS 구매 ($5/월)
   ↓ (DigitalOcean/Vultr)

3단계: Docker 설치 및 배포
   ↓ (이 가이드 따라)

4단계: 헬스 체크
   ↓ (javascript_enabled: true 확인)

5단계: Exploit 테스트
   ↓ (solution/exploit.py)

6단계: 참가자에게 공개
   ↓ (URL 공지)

7단계: 모니터링
   (docker stats, logs)
```

---

**마지막 업데이트**: 2025-01-XX
**버전**: 1.0
**문의**: CTF 주최자 전용
