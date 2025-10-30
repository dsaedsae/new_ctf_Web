# AWS EC2 배포 가이드 - Legacy Microservice CTF

완벽한 AWS 배포 가이드입니다. CTF 대회용 프로덕션 환경 구축.

---

## 📋 목차

1. [사전 준비](#1-사전-준비)
2. [EC2 인스턴스 생성](#2-ec2-인스턴스-생성)
3. [보안 그룹 설정](#3-보안-그룹-설정)
4. [서버 초기 설정](#4-서버-초기-설정)
5. [Docker 설치](#5-docker-설치)
6. [프로젝트 배포](#6-프로젝트-배포)
7. [도메인 연결 (선택)](#7-도메인-연결-선택)
8. [SSL 인증서 (선택)](#8-ssl-인증서-선택)
9. [모니터링 및 관리](#9-모니터링-및-관리)
10. [문제 해결](#10-문제-해결)

---

## 1. 사전 준비

### 1.1 필요한 것

- [ ] AWS 계정 (https://aws.amazon.com)
- [ ] 신용카드 (프리티어 사용 시에도 필요)
- [ ] SSH 키 생성 방법 숙지
- [ ] (선택) 도메인 (예: ctf.yourdomain.com)

### 1.2 예상 비용

#### 개발/테스트 환경
| 항목 | 프리티어 | 유료 (월) |
|------|---------|----------|
| EC2 t2.micro | **무료** (750시간/월) | $8-10 |
| EC2 t3.small | - | $15-20 |
| 데이터 전송 | 15GB 무료 | $0.09/GB |
| 도메인 (선택) | - | $12/년 |

**추천**: 프리티어 t2.micro (1GB RAM, 1 vCPU) - 개발 및 소규모 테스트용

#### 블랙박스 CTF 대회 환경 (10일 운영 기준)

| 인스턴스 유형 | 사양 | 예상 참가자 | 시간당 비용 | 10일 비용 | 총 예상 비용 |
|--------------|------|------------|-----------|---------|------------|
| **t3.medium** ⭐ | 2 vCPU, 4GB | ~50명 | $0.0416 | $10 | **$15** |
| **t3.large** ⭐⭐ | 2 vCPU, 8GB | ~100-200명 | $0.0832 | $20 | **$27** |
| **c6i.large** | 2 vCPU, 4GB | ~150명 | $0.085 | $20.4 | **$28** |
| **c6i.xlarge** | 4 vCPU, 8GB | 200명+ | $0.17 | $40.8 | **$50** |

**총 예상 비용 (10일 대회)**:
- **t3.large (추천)**: 약 $27 (약 36,000원)
  - EC2 인스턴스: $20
  - 데이터 전송 (~50GB): $4
  - EBS 스토리지 (20GB gp3): $0.50
  - Elastic IP: 무료 (사용 중)
  - 예비비: $2.50

**비용 절약 팁**:
- ✅ **Spot 인스턴스** 사용 시 최대 70% 할인 (단, 중단 위험 있음)
- ✅ **예약 인스턴스** 사용 시 최대 40% 할인 (장기 사용)
- ✅ 대회 종료 즉시 인스턴스 중지 (비용 절감)
- ✅ CloudWatch 알람 설정으로 비용 초과 방지

---

## 2. EC2 인스턴스 생성

### 2.1 AWS Console 로그인

1. https://console.aws.amazon.com 접속
2. 우측 상단에서 **리전 선택**
   - 추천: `ap-northeast-2` (서울)
   - 또는: `us-east-1` (버지니아 - 가장 저렴)

### 2.2 EC2 대시보드 이동

1. 상단 검색창에 "EC2" 입력
2. "EC2" 클릭
3. "인스턴스 시작" 버튼 클릭

### 2.3 인스턴스 설정

#### Step 1: 이름 및 AMI 선택

```
이름: ctf-legacy-microservice
AMI: Ubuntu Server 22.04 LTS (64-bit x86)
```

**주의**: Amazon Linux가 아닌 **Ubuntu** 선택!

#### Step 2: 인스턴스 유형

**개발/테스트:**
```
프리티어: t2.micro (1 vCPU, 1GB RAM) - 무료
```

**블랙박스 CTF 대회 (11/9~11/18, 10일):**
```
소규모 (~50명):   t3.medium  (2 vCPU, 4GB RAM)  - $15/10일 ⭐
중규모 (~100명):  t3.large   (2 vCPU, 8GB RAM)  - $27/10일 ⭐⭐ 추천
대규모 (200명+):  c6i.xlarge (4 vCPU, 8GB RAM)  - $50/10일
```

**선택 가이드:**
- 예상 동시 접속 100명 이하 → `t3.medium`
- 예상 동시 접속 100-200명 → `t3.large` (추천)
- 예상 동시 접속 200명 이상 → `c6i.xlarge`

#### Step 3: 키 페어 생성

```
1. "새 키 페어 생성" 클릭
2. 키 페어 이름: ctf-key
3. 키 페어 유형: RSA
4. 프라이빗 키 파일 형식:
   - Windows: .ppk (PuTTY용)
   - Mac/Linux: .pem
5. "키 페어 생성" 클릭
6. ⚠️ 다운로드된 파일 안전하게 보관!
```

**중요**: 키 파일 분실 시 서버 접속 불가능!

#### Step 4: 네트워크 설정

```
VPC: (기본값)
서브넷: (기본값)
퍼블릭 IP 자동 할당: 활성화 ✓
```

#### Step 5: 스토리지 구성

```
루트 볼륨:
- 크기: 16 GB (권장) ~ 30GB (프리티어 최대)
- 볼륨 유형: gp3 (SSD)
```

#### Step 6: 고급 세부 정보 (선택)

```
사용자 데이터 (User Data):
# 아래 스크립트를 입력하면 자동으로 Docker 설치됨
```

```bash
#!/bin/bash
apt-get update
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker
```

#### Step 7: 인스턴스 시작

1. "인스턴스 시작" 버튼 클릭
2. "인스턴스 보기" 클릭
3. 상태가 "실행 중"이 될 때까지 대기 (2-3분)

---

## 3. 보안 그룹 설정

### 3.1 보안 그룹 편집

1. EC2 대시보드 → 왼쪽 메뉴 → "보안 그룹"
2. 방금 생성한 인스턴스의 보안 그룹 클릭
3. "인바운드 규칙" 탭 → "인바운드 규칙 편집"

### 3.2 규칙 추가

| 유형 | 프로토콜 | 포트 범위 | 소스 | 설명 |
|------|---------|----------|------|------|
| SSH | TCP | 22 | **내 IP** | SSH 접속 |
| HTTP | TCP | 80 | 0.0.0.0/0 | HTTP (선택) |
| 사용자 지정 TCP | TCP | 5000 | 0.0.0.0/0 | CTF 앱 |

**보안 팁**:
- ⚠️ SSH는 반드시 "내 IP"로 제한!
- 💡 5000번 포트 대신 80번 사용 권장 (아래 Nginx 설정 참조)

### 3.3 "규칙 저장" 클릭

---

## 4. 서버 초기 설정

### 4.1 SSH 접속

#### Mac/Linux:

```bash
# 키 파일 권한 설정
chmod 400 ~/Downloads/ctf-key.pem

# SSH 접속
ssh -i ~/Downloads/ctf-key.pem ubuntu@<퍼블릭-IP>
```

**퍼블릭 IP 확인**: EC2 대시보드에서 인스턴스 선택 → 하단에 표시

#### Windows (PuTTY):

```
1. PuTTY 실행
2. Host Name: ubuntu@<퍼블릭-IP>
3. Connection → SSH → Auth → Credentials
   → Private key file: ctf-key.ppk 선택
4. "Open" 클릭
```

### 4.2 시스템 업데이트

```bash
# 처음 접속하면 실행
sudo apt update
sudo apt upgrade -y
```

### 4.3 타임존 설정 (선택)

```bash
# 서울 시간으로 설정
sudo timedatectl set-timezone Asia/Seoul

# 확인
date
```

---

## 5. Docker 설치

### 5.1 Docker 설치 확인

```bash
# User Data에서 자동 설치된 경우
docker --version

# 설치 안 됐으면 수동 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
```

### 5.2 Docker Compose 설치

```bash
# Docker Compose 플러그인 확인
docker compose version

# 없으면 수동 설치
sudo apt-get install docker-compose-plugin
```

### 5.3 현재 사용자에게 Docker 권한 부여

```bash
sudo usermod -aG docker $USER

# 로그아웃 후 재접속 (중요!)
exit

# 다시 SSH 접속
ssh -i ~/Downloads/ctf-key.pem ubuntu@<퍼블릭-IP>

# 권한 확인 (sudo 없이 실행되어야 함)
docker ps
```

---

## 6. 프로젝트 배포

### 6.1 Git 설치 및 프로젝트 클론

```bash
# Git 설치
sudo apt install -y git

# 프로젝트 클론
cd ~
git clone https://github.com/dsaedsae/new_ctf_Web.git
cd new_ctf_Web

# 올바른 브랜치로 전환
git checkout claude/mongodb-44-ctf-application-011CUciUTX4HvLBd24UHPcB7
```

### 6.2 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집
nano .env
```

**중요한 설정**:

```bash
# .env 파일 내용
CTF_PORT=5000

# ⚠️ CRITICAL: 고유한 SALT 생성!
COMPANY_SALT=your_unique_random_salt_here_$(openssl rand -hex 16)

# FLAG 설정 (대회용)
FLAG=FLAG{pr0duct10n_fl4g_f0r_ctf_2025}

# 난이도 설정
BLIND_RCE=false  # 또는 true (더 어려움)
```

**자동 생성**:

```bash
# 안전한 SALT 자동 생성
echo "COMPANY_SALT=$(openssl rand -hex 16)" >> .env
```

### 6.3 Docker Compose 설정 확인

```bash
# docker-compose.yml 확인
cat docker-compose.yml

# version: '3.8' 라인 제거 (경고 방지)
sed -i "1d" docker-compose.yml
```

### 6.4 빌드 및 실행

```bash
# Docker 이미지 빌드
docker compose build

# 백그라운드 실행
docker compose up -d

# 로그 확인
docker compose logs -f web
# Ctrl+C로 종료
```

### 6.5 동작 확인

```bash
# 헬스체크
curl http://localhost:5000/health

# 서비스 목록
curl http://localhost:5000/api/v2/services

# 브라우저에서도 확인
# http://<퍼블릭-IP>:5000
```

**성공 메시지**:
```json
{
  "status": "healthy",
  "database": "connected",
  "javascript_enabled": true,
  "services": ["auth", "api", "legacy"]
}
```

---

## 7. 도메인 연결 (선택)

### 7.1 도메인 구매

- Namecheap: https://www.namecheap.com
- GoDaddy: https://www.godaddy.com
- AWS Route 53: https://console.aws.amazon.com/route53

### 7.2 DNS 설정

#### A 레코드 추가:

```
타입: A
호스트: ctf (또는 @)
값: <EC2 퍼블릭 IP>
TTL: 300
```

### 7.3 Elastic IP 할당 (권장)

**문제**: EC2 재부팅 시 IP 변경됨

**해결**: Elastic IP (고정 IP) 사용

1. EC2 대시보드 → "탄력적 IP"
2. "탄력적 IP 주소 할당"
3. 할당된 IP를 인스턴스에 연결
4. DNS A 레코드를 Elastic IP로 변경

**비용**:
- 인스턴스에 연결된 상태: **무료**
- 미사용 상태: $3.60/월

---

## 8. SSL 인증서 (선택)

### 8.1 Nginx 설치

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 8.2 Nginx 설정

```bash
sudo nano /etc/nginx/sites-available/ctf
```

**설정 파일**:

```nginx
server {
    listen 80;
    server_name ctf.yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 8.3 Nginx 활성화

```bash
# 심볼릭 링크 생성
sudo ln -s /etc/nginx/sites-available/ctf /etc/nginx/sites-enabled/

# 기본 설정 제거
sudo rm /etc/nginx/sites-enabled/default

# 설정 테스트
sudo nginx -t

# Nginx 재시작
sudo systemctl restart nginx
```

### 8.4 Let's Encrypt SSL 인증서

```bash
# SSL 인증서 자동 발급 및 설정
sudo certbot --nginx -d ctf.yourdomain.com

# 질문에 답변:
# Email: your@email.com
# Terms: Y
# Share email: N
# Redirect to HTTPS: 2 (Yes)
```

### 8.5 자동 갱신 설정

```bash
# 갱신 테스트
sudo certbot renew --dry-run

# Cron 자동 설정 (자동 갱신)
sudo systemctl enable certbot.timer
```

**결과**: https://ctf.yourdomain.com 접속 가능!

---

## 9. 모니터링 및 관리

### 9.1 컨테이너 상태 확인

```bash
# 실행 중인 컨테이너
docker compose ps

# 리소스 사용량
docker stats

# 로그 보기
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f web
docker compose logs -f db
```

### 9.2 재시작

```bash
# 전체 재시작
docker compose restart

# 특정 서비스만
docker compose restart web

# 완전 재빌드
docker compose down
docker compose build --no-cache
docker compose up -d
```

### 9.3 업데이트 배포

```bash
cd ~/new_ctf_Web

# 최신 코드 가져오기
git pull origin claude/mongodb-44-ctf-application-011CUciUTX4HvLBd24UHPcB7

# 재빌드 및 재시작
docker compose down
docker compose build
docker compose up -d
```

### 9.4 백업

```bash
# MongoDB 데이터 백업
docker compose exec db mongodump --out /tmp/backup

# 백업 파일 복사
docker cp ctf_db:/tmp/backup ./backup-$(date +%Y%m%d)

# S3로 업로드 (선택)
aws s3 cp backup-$(date +%Y%m%d) s3://your-bucket/backups/
```

### 9.5 자동 재시작 설정

```bash
# 서버 재부팅 시 자동 시작
sudo crontab -e

# 아래 라인 추가
@reboot cd /home/ubuntu/new_ctf_Web && docker compose up -d
```

### 9.6 실시간 모니터링 (블랙박스 CTF 필수) ⭐

**대회 중 실시간 모니터링 도구:**

```bash
cd ~/new_ctf_Web

# 실행 권한 부여
chmod +x monitor.sh

# 모니터링 시작 (Ctrl+C로 종료)
./monitor.sh
```

**모니터링 항목:**
- ✅ CPU/메모리/디스크 사용률 (임계값 초과 시 경고)
- ✅ Docker 컨테이너 상태 (자동 중지 감지)
- ✅ 네트워크 연결 수 (동시 접속자 추정)
- ✅ 애플리케이션 응답 시간 (성능 저하 감지)
- ✅ 에러 로그 실시간 추적
- ✅ 자동 로그 파일 생성 (`ctf_monitor_YYYYMMDD_HHMMSS.log`)

**화면 예시:**
```
========================================
  CTF 실시간 모니터링 (2024-11-09 14:32:15)
========================================

[시스템 리소스]
  CPU 사용률: 45.2%
  메모리 사용률: 62.8%
  디스크 사용률: 38%

[Docker 컨테이너 상태]
  Web 컨테이너: ● Running
  DB 컨테이너: ● Running

[컨테이너 리소스]
  ctf_web: CPU 23.5% | MEM 15.2%
  ctf_db: CPU 12.3% | MEM 8.7%

[네트워크 통계]
  활성 연결 수: 87
  5000 포트 연결: 42
  TIME_WAIT: 234

[애플리케이션 상태]
  헬스체크: ✓ OK
  응답 시간: 0.045초
```

**경고 알림:**
- CPU > 80% → 인스턴스 업그레이드 검토
- 메모리 > 80% → 메모리 부족 임박
- 응답 시간 > 1초 → 성능 저하

### 9.7 부하 테스트 (대회 전 필수) ⭐⭐

**배포 전 성능 검증:**

```bash
cd ~/new_ctf_Web

# 실행 권한 부여
chmod +x stress_test.sh

# Apache Bench 설치
sudo apt-get install -y apache2-utils

# 부하 테스트 실행
# 사용법: ./stress_test.sh [동시접속자] [요청수] [URL]
./stress_test.sh 100 200
```

**테스트 시나리오:**
1. 메인 페이지 부하 테스트
2. API 엔드포인트 테스트
3. 헬스체크 테스트
4. POST 요청 테스트 (세션 검증)

**결과 해석:**
```
[homepage]
  Requests per second:    312.45 [#/sec] (mean)
  Time per request:       320.123 [ms] (mean)
  Failed requests:        0
  실패율: 0.00%
```

**권장 기준값:**
- ✅ **RPS (초당 요청) > 100**: 정상
- ✅ **평균 응답 시간 < 500ms**: 양호
- ✅ **실패율 < 1%**: 안정적
- ⚠️ 기준 미달 시 → 인스턴스 사양 업그레이드

**예상 참가자별 테스트:**
```bash
# 소규모 (50명)
./stress_test.sh 50 100

# 중규모 (100명)
./stress_test.sh 100 200

# 대규모 (200명)
./stress_test.sh 200 500
```

**결과 파일:**
- `stress_test_results_YYYYMMDD_HHMMSS/`
  - `homepage.txt` - 메인 페이지 결과
  - `api.txt` - API 성능
  - `health.txt` - 헬스체크
  - `post.txt` - POST 요청
  - `*.tsv` - 그래프 생성용 데이터

---

## 10. 문제 해결

### 10.1 컨테이너가 시작 안됨

```bash
# 로그 확인
docker compose logs

# MongoDB JavaScript 확인
docker compose logs db | grep -i javascript

# 헬스체크 실패
docker compose logs web | grep -i error
```

**해결**:
```bash
# 완전 정리 후 재시작
docker compose down -v
docker system prune -f
docker compose up -d
```

### 10.2 포트 5000 접속 안됨

```bash
# 포트 리스닝 확인
sudo netstat -tlnp | grep 5000

# 방화벽 확인
sudo ufw status

# 보안 그룹 재확인
# AWS Console → EC2 → 보안 그룹 → 인바운드 규칙
```

### 10.3 MongoDB 연결 실패

```bash
# MongoDB 컨테이너 상태
docker compose ps db

# MongoDB 로그
docker compose logs db

# MongoDB 직접 접속 테스트
docker compose exec db mongo --eval "db.version()"
```

### 10.4 메모리 부족

```bash
# 메모리 확인
free -h

# t2.micro (1GB)는 부족할 수 있음
# → t3.small (2GB)로 업그레이드 권장
```

**임시 해결**:
```bash
# Swap 추가
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### 10.5 디스크 공간 부족

```bash
# 디스크 사용량 확인
df -h

# Docker 정리
docker system prune -a --volumes
```

---

## 📋 배포 체크리스트

배포 전 최종 확인:

- [ ] EC2 인스턴스 생성 및 실행
- [ ] 보안 그룹 설정 (SSH, 5000번 포트)
- [ ] Elastic IP 할당 (선택)
- [ ] Docker 설치 완료
- [ ] .env 파일 설정 (COMPANY_SALT, FLAG)
- [ ] docker compose up -d 실행
- [ ] http://<IP>:5000/health 확인
- [ ] javascript_enabled: true 확인
- [ ] (선택) 도메인 연결
- [ ] (선택) SSL 인증서
- [ ] (선택) Nginx 리버스 프록시

---

## 🎯 프로덕션 권장 설정

### 최소 사양 (30-50명 CTF)
```
인스턴스: t3.small
RAM: 2GB
CPU: 2 vCPU
스토리지: 20GB
예상 비용: $15-20/월
```

### 권장 사양 (100-200명 CTF)
```
인스턴스: t3.medium
RAM: 4GB
CPU: 2 vCPU
스토리지: 30GB
예상 비용: $30-40/월
```

### 대규모 (500+ 명 CTF)
```
인스턴스: t3.large + Auto Scaling
Load Balancer + CloudFront
MongoDB Atlas (관리형)
예상 비용: $100+/월
```

---

## 🔐 보안 권장사항

1. ✅ SSH 포트를 "내 IP"로 제한
2. ✅ 고유한 COMPANY_SALT 사용
3. ✅ FLAG를 대회용으로 변경
4. ✅ 정기적 업데이트 (apt update)
5. ✅ 불필요한 포트 닫기
6. ✅ fail2ban 설치 (무차별 대입 공격 방지)
7. ✅ CloudWatch 로깅 활성화
8. ⚠️ 대회 종료 후 인스턴스 중지 또는 삭제

---

## 📞 도움이 필요하면

- AWS 공식 문서: https://docs.aws.amazon.com
- Docker 문서: https://docs.docker.com
- 프로젝트 이슈: https://github.com/dsaedsae/new_ctf_Web/issues

**배포 성공을 기원합니다!** 🚀
