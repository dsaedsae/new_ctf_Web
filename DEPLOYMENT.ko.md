# 배포 가이드

## 🎯 배포 개요

### GitHub Actions의 역할 명확화
❌ **흔한 오해**: GitHub Actions로 문제를 직접 호스팅할 수 있다
✅ **정확한 이해**: GitHub Actions는 빌드/테스트 자동화만 담당, **실제 서버가 반드시 필요**

```
GitHub Actions                실제 서버 (필수!)
─────────────────            ──────────────────
✓ 코드 빌드 자동화           ✓ Docker 컨테이너 실행
✓ 테스트 실행                ✓ 24/7 서비스 운영
✓ Docker 이미지 푸시         ✓ 참가자 접속 처리
                            ✓ MongoDB 데이터 저장
```

**결론**: CTF 문제를 운영하려면 **반드시 서버가 필요**합니다!

---

## 📋 배포 옵션 비교표

| 배포 방법 | 난이도 | 월 비용 | 확장성 | 추천도 | 비고 |
|----------|-------|--------|-------|-------|------|
| **로컬 서버** | ⭐ | 무료 | ❌ | 테스트용 | 외부 접속 어려움 |
| **VPS** | ⭐⭐ | $5-20 | ⭐⭐⭐ | ✅ **강력 추천** | 가성비 최고 |
| **AWS/GCP** | ⭐⭐⭐⭐ | 변동 | ⭐⭐⭐⭐⭐ | 대규모용 | 복잡함 |
| **Heroku/Railway** | ⭐ | $5-10 | ⭐⭐ | 간편 배포 | 제한 많음 |
| **CTFd 플랫폼** | ⭐⭐⭐ | $10-50 | ⭐⭐⭐⭐ | 통합 관리 | CTFd 학습 필요 |

**초보자 추천**: VPS (DigitalOcean, Vultr 등)

---

## 🚀 방법 1: VPS 배포 (가장 추천)

### 단계 1: VPS 서버 구매

#### 추천 업체
```
1. DigitalOcean (https://digitalocean.com)
   - Droplet (서버): $6/월 (1GB RAM)
   - 사용하기 쉬운 UI
   - 한국 리전 없음 (싱가포르 추천)

2. Vultr (https://vultr.com)
   - Cloud Compute: $5/월 (1GB RAM)
   - 서울 리전 있음 ✓
   - 성능 좋음

3. Linode (https://linode.com)
   - Nanode: $5/월 (1GB RAM)
   - 안정적

4. AWS Lightsail
   - $5/월 (1GB RAM)
   - AWS 계정 있으면 편함
```

#### 서버 스펙 선택

**최소 사양** (참가자 ~30명):
```
CPU: 1 core
RAM: 1GB
디스크: 25GB SSD
OS: Ubuntu 22.04 LTS
```

**권장 사양** (참가자 50-100명):
```
CPU: 2 cores
RAM: 2GB
디스크: 50GB SSD
OS: Ubuntu 22.04 LTS
```

---

### 단계 2: 서버 초기 설정

```bash
# 1. SSH 접속 (서버 IP는 VPS 업체에서 제공)
ssh root@서버IP주소

# 예시:
# ssh root@123.45.67.89

# 2. 시스템 업데이트 (필수!)
apt update
apt upgrade -y

# 3. Docker 설치
curl -fsSL https://get.docker.com | sh

# 4. Docker Compose 설치
apt install docker-compose -y

# 5. Docker 버전 확인
docker --version
docker-compose --version

# 6. 방화벽 설정
ufw allow 22/tcp    # SSH (필수! 안 하면 접속 끊김)
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS (SSL 사용 시)
ufw enable

# 주의: ufw enable 전에 반드시 22번 포트를 먼저 열어야 합니다!

# 7. 비root 사용자 생성 (보안 강화, 선택사항)
adduser ctfadmin
usermod -aG docker ctfadmin
usermod -aG sudo ctfadmin

# 이후 ctfadmin으로 로그인
# su - ctfadmin
```

---

### 단계 3: 프로젝트 배포

```bash
# 1. 작업 디렉토리 생성
cd /opt
mkdir ctf
cd ctf

# 2. GitHub에서 프로젝트 클론
git clone https://github.com/your-username/new_ctf_Web.git
cd new_ctf_Web

# 또는 파일 직접 업로드 (scp 사용):
# 로컬에서:
# scp -r /path/to/ctf-legacy-microservice root@서버IP:/opt/ctf/

# 3. .env 파일 생성 (중요!)
cp .env.example .env
nano .env

# 4. .env 파일 편집 내용:
# ─────────────────────────────────────
# COMPANY_SALT 생성 (매우 중요!)
# 새 터미널에서 실행:
openssl rand -hex 16
# 출력 예: a3f9d8e2b1c4567890abcdef12345678

# .env 파일에 입력:
CTF_PORT=5000
COMPANY_SALT=a3f9d8e2b1c4567890abcdef12345678  # 위에서 생성한 값
FLAG=FLAG{y0ur_cust0m_fl4g_h3r3}
BLIND_RCE=false
# ─────────────────────────────────────

# 5. 빌드 (처음에만, 시간 걸림)
docker-compose build

# 6. 실행
docker-compose up -d

# -d 옵션: 백그라운드 실행

# 7. 상태 확인
docker-compose ps

# 예상 출력:
#   Name              Command          State           Ports
# ─────────────────────────────────────────────────────────
# ctf_db      mongod ...         Up      27017/tcp
# ctf_web     ./docker-...       Up      0.0.0.0:5000->5000/tcp
```

---

### 단계 4: 동작 확인

```bash
# 1. 헬스 체크 (서버 내부에서)
curl http://localhost:5000/health | jq

# 2. 예상 출력:
{
  "status": "healthy",
  "database": "connected",
  "javascript_enabled": true,  # ← 반드시 true여야 함!
  "services": ["auth", "api", "legacy"]
}

# 3. 외부에서 접속 테스트 (로컬 PC에서)
curl http://서버IP:5000/health

# 4. 브라우저에서 확인
# http://서버IP:5000
```

**javascript_enabled가 false인 경우**:
```bash
# MongoDB JavaScript가 활성화 안 됨
docker-compose logs db

# docker-compose.yml 확인:
# db 서비스에 이것이 있어야 함:
# command: mongod --setParameter javascriptEnabled=true
```

---

### 단계 5: Exploit 테스트

```bash
# 로컬 PC에서 테스트
cd solution
pip install -r requirements.txt
python3 exploit.py http://서버IP:5000

# 예상 출력:
# [Stage 1] Service Discovery
# [+] Found 3 services
# ...
# [SUCCESS] FLAG CAPTURED:
# FLAG{y0ur_cust0m_fl4g_h3r3}
```

**성공하면 배포 완료!** 🎉

---

### 단계 6: 도메인 연결 (선택사항)

도메인이 있다면 IP 대신 도메인을 사용할 수 있습니다.

```bash
# 예: ctf.your-domain.com

# 1. DNS 설정 (도메인 업체 웹사이트에서)
ctf.your-domain.com  →  A 레코드  →  서버IP

# 2. Nginx 설치 (리버스 프록시)
apt install nginx -y

# 3. Nginx 설정 파일 생성
nano /etc/nginx/sites-available/ctf

# 내용:
server {
    listen 80;
    server_name ctf.your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 타임아웃 설정
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

# 4. 설정 활성화
ln -s /etc/nginx/sites-available/ctf /etc/nginx/sites-enabled/
nginx -t  # 설정 테스트
systemctl restart nginx

# 5. 방화벽에서 5000번 포트 닫기 (보안)
ufw deny 5000/tcp

# 이제 80번 포트로만 접속 가능
# http://ctf.your-domain.com
```

#### HTTPS 설정 (SSL, 무료)

```bash
# Let's Encrypt 사용
apt install certbot python3-certbot-nginx -y
certbot --nginx -d ctf.your-domain.com

# 자동으로 HTTPS 설정됨
# https://ctf.your-domain.com
```

---

## 🚀 방법 2: Railway 간편 배포

Railway는 GUI로 쉽게 배포할 수 있지만, MongoDB JavaScript 제한이 있을 수 있습니다.

```bash
# 1. Railway CLI 설치
npm install -g @railway/cli

# 2. 로그인
railway login

# 3. 프로젝트 초기화
cd /path/to/ctf-legacy-microservice
railway init

# 4. MongoDB 추가
railway add

# MongoDB 선택

# 5. 환경변수 설정
railway variables set COMPANY_SALT=$(openssl rand -hex 16)
railway variables set FLAG="FLAG{your_flag}"
railway variables set BLIND_RCE=false

# 6. 배포
railway up

# 7. URL 확인
railway open
```

**주의**: Railway는 무료 플랜 제한이 있고, MongoDB JavaScript가 제한될 수 있습니다.

---

## 📊 리소스 사용량 및 비용

### 예상 리소스 사용

| 참가자 수 | CPU | RAM | 대역폭 | 추천 서버 |
|----------|-----|-----|--------|----------|
| 1명 (테스트) | 5% | 200MB | 1Mbps | 로컬 |
| ~30명 | 30% | 512MB | 5Mbps | VPS 512MB ($3.5/월) |
| ~50명 | 50% | 1GB | 10Mbps | VPS 1GB ($5/월) |
| 50-100명 | 70% | 2GB | 20Mbps | VPS 2GB ($12/월) |
| 100-200명 | 2 cores | 4GB | 50Mbps | VPS 4GB ($24/월) |

### 월 비용 계산

**소규모 CTF** (참가자 ~50명):
```
VPS 1GB:              $5-6
도메인 (선택):        $1
────────────────────────
총계:                $6-7/월
```

**중규모 CTF** (참가자 100-200명):
```
VPS 2-4GB:           $12-24
도메인:              $1
모니터링 (선택):     무료
────────────────────────
총계:                $13-25/월
```

**대규모 CTF** (참가자 500+명):
```
VPS 또는 클라우드:   $50-100
로드밸런서:          $20
모니터링:            $20
백업:               $10
────────────────────────
총계:                $100-150/월
```

---

## 🛠️ 주요 명령어 모음

### 일상 관리

```bash
# 상태 확인
docker-compose ps

# 로그 확인 (실시간)
docker-compose logs -f

# 로그 확인 (최근 100줄)
docker-compose logs --tail=100

# 재시작
docker-compose restart

# 중지
docker-compose stop

# 시작
docker-compose start

# 완전 종료 (데이터 삭제)
docker-compose down -v

# 리소스 사용량 확인
docker stats
```

### 업데이트

```bash
# 1. 코드 업데이트
git pull

# 2. 재빌드
docker-compose build

# 3. 재시작
docker-compose up -d

# 또는 한 번에:
git pull && docker-compose build && docker-compose up -d
```

---

## 🔒 보안 강화

### 1. SSH 키 인증 설정

```bash
# 로컬 PC에서 키 생성
ssh-keygen -t ed25519 -C "your-email@example.com"

# 공개키를 서버에 복사
ssh-copy-id root@서버IP

# 서버에서 비밀번호 로그인 비활성화
nano /etc/ssh/sshd_config

# 다음 설정:
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes

# SSH 재시작
systemctl restart sshd
```

### 2. fail2ban 설치 (무차별 대입 공격 방어)

```bash
apt install fail2ban -y
systemctl enable fail2ban
systemctl start fail2ban

# 상태 확인
fail2ban-client status
```

### 3. 자동 보안 업데이트

```bash
apt install unattended-upgrades -y
dpkg-reconfigure -plow unattended-upgrades
```

---

## 🐛 트러블슈팅

### 문제 1: 컨테이너가 시작 안 됨

```bash
# 로그 확인
docker-compose logs web
docker-compose logs db

# 일반적 원인:
# 1. COMPANY_SALT 미설정
cat .env | grep COMPANY_SALT

# 2. 포트 충돌
netstat -tlnp | grep 5000
# 다른 프로그램이 5000번 포트 사용 중이면:
# .env에서 CTF_PORT=5001로 변경

# 3. 메모리 부족
free -h

# 해결책:
docker-compose down -v
# .env 확인 및 수정
docker-compose up -d
```

### 문제 2: javascript_enabled: false

```bash
# MongoDB 설정 확인
docker-compose exec db mongosh --eval "db.adminCommand({getParameter: 1, javascriptEnabled: 1})"

# docker-compose.yml 확인
grep "javascriptEnabled" docker-compose.yml

# 없으면 추가:
# db:
#   command: mongod --setParameter javascriptEnabled=true

# 재시작
docker-compose down -v
docker-compose up -d
```

### 문제 3: 외부에서 접속 안 됨

```bash
# 1. 방화벽 확인
ufw status

# 5000번 포트가 ALLOW인지 확인

# 2. Docker가 리스닝 중인지 확인
netstat -tlnp | grep 5000

# 3. 서버에서 로컬 접속 테스트
curl http://localhost:5000/health

# 4. VPS 업체의 방화벽 설정도 확인
# (DigitalOcean, Vultr 등의 웹 콘솔에서)
```

### 문제 4: 메모리 부족

```bash
# 메모리 사용량 확인
free -h
docker stats

# Swap 추가 (임시 방편)
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# 영구 설정
echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
```

---

## 📈 모니터링

### 기본 모니터링

```bash
# 리소스 사용량 (실시간)
watch -n 2 'docker stats --no-stream'

# 디스크 사용량
df -h

# 헬스 체크 자동화
watch -n 30 'curl -s http://localhost:5000/health | jq'

# 로그 모니터링
tail -f /var/log/syslog
```

### 접속 로그 분석

```bash
# 접속 통계 확인
docker-compose logs web | grep "GET /api" | wc -l

# IP별 접속 수
docker-compose logs web | grep "GET /api" | awk '{print $1}' | sort | uniq -c | sort -nr
```

---

## 🎯 배포 체크리스트

### 배포 전 준비
```
□ VPS 서버 구매 (1GB RAM 이상)
□ Ubuntu 22.04 LTS 설치
□ SSH 접속 확인
□ 도메인 구매 (선택사항)
```

### 서버 설정
```
□ Docker 설치
□ Docker Compose 설치
□ 방화벽 설정 (22, 80, 443 포트)
□ (선택) 비root 사용자 생성
```

### 프로젝트 배포
```
□ GitHub에서 코드 클론
□ .env 파일 생성
□ COMPANY_SALT 랜덤 생성 및 설정
□ FLAG 설정
□ docker-compose build
□ docker-compose up -d
```

### 테스트
```
□ 헬스 체크 (javascript_enabled: true 확인)
□ 서비스 목록 조회 (/api/v2/services)
□ Exploit 스크립트 실행
□ 외부에서 접속 테스트
```

### 보안
```
□ SSH 키 인증 설정
□ 비밀번호 로그인 비활성화
□ fail2ban 설치
□ 방화벽 재확인
```

### 참가자 공지
```
□ URL 또는 도메인 공지
□ 문제 설명 (README.md)
□ 힌트 제공 시기 결정
□ 긴급 연락처 공유
```

---

## 💡 팁과 권장사항

### 1. 백업 설정

```bash
# 자동 백업 스크립트
cat > /opt/backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T db mongodump --archive > /opt/backups/db_$DATE.archive
# 30일 이상 된 백업 삭제
find /opt/backups -name "db_*.archive" -mtime +30 -delete
EOF

chmod +x /opt/backup.sh

# 매일 새벽 3시 백업
crontab -e
# 추가:
0 3 * * * /opt/backup.sh
```

### 2. 자동 재시작 설정

```bash
# 서버 재부팅 시 자동 시작
cat > /etc/systemd/system/ctf-challenge.service << 'EOF'
[Unit]
Description=CTF Challenge
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/ctf/new_ctf_Web
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down

[Install]
WantedBy=multi-user.target
EOF

systemctl enable ctf-challenge
```

### 3. 리소스 제한

```yaml
# docker-compose.yml에 추가
services:
  web:
    # ... 기존 설정 ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
```

---

## 📞 긴급 대응

### 서비스 다운 시

```bash
# 1단계: 빠른 재시작
docker-compose restart

# 2단계: 완전 재시작
docker-compose down
docker-compose up -d

# 3단계: 재빌드
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d

# 4단계: 로그 확인
docker-compose logs --tail=100
```

### 과부하 시

```bash
# CPU/메모리 사용량 확인
docker stats

# 로그에서 이상 패턴 찾기
docker-compose logs web | grep "ERROR"

# Rate limiting 추가 (Nginx)
# /etc/nginx/sites-available/ctf 수정:
limit_req_zone $binary_remote_addr zone=ctf:10m rate=10r/s;
limit_req zone=ctf burst=20;
```

---

## 🎓 추천 배포 순서

```
1단계: 로컬에서 테스트 ✓
   ↓ (docker-compose up -d)
   ↓ (exploit.py 실행)

2단계: VPS 구매 ✓
   ↓ (DigitalOcean/Vultr)
   ↓ (Ubuntu 22.04 LTS)

3단계: 서버 설정 ✓
   ↓ (Docker 설치)
   ↓ (방화벽 설정)

4단계: 프로젝트 배포 ✓
   ↓ (git clone)
   ↓ (.env 설정)
   ↓ (docker-compose up -d)

5단계: 테스트 ✓
   ↓ (헬스 체크)
   ↓ (Exploit 실행)

6단계: 공개 ✓
   ↓ (URL 공지)

7단계: 모니터링 ✓
   (docker stats)
   (로그 확인)
```

---

## ❓ FAQ

**Q: 꼭 돈을 내야 하나요?**
A: 외부에서 접속 가능하려면 공인 IP가 있는 서버가 필요합니다. 로컬은 테스트용으로만 사용 가능합니다.

**Q: 가장 저렴한 방법은?**
A: Vultr/DigitalOcean VPS $5/월이 가장 가성비 좋습니다.

**Q: 도메인이 꼭 필요한가요?**
A: 아니요, IP 주소로도 가능합니다. 도메인은 선택사항입니다.

**Q: SSL/HTTPS가 필요한가요?**
A: CTF 문제 자체는 HTTP로 충분하지만, 보안을 위해 HTTPS 권장합니다 (Let's Encrypt 무료).

**Q: 몇 명까지 수용 가능한가요?**
A: 1GB RAM 서버로 50명 정도, 2GB RAM으로 100명 정도 가능합니다.

**Q: Railway/Heroku는 안 되나요?**
A: MongoDB JavaScript 제한 때문에 문제가 발생할 수 있습니다. VPS 추천합니다.

**Q: GitHub Actions는 어디에 쓰나요?**
A: 코드 변경 시 자동으로 Docker 이미지를 빌드하고 테스트하는 용도입니다. 서버 배포는 별도입니다.

---

**마지막 업데이트**: 2025-01-XX
**버전**: 1.0
**작성자**: CTF 주최자 가이드
