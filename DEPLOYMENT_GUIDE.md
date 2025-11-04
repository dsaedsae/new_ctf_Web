# 🚀 GCP 배포 가이드 - OAuth CTF Advanced

## 📋 배포 파일 구조

```
oauth-ctf-deploy/
├── docker-compose.yml          ✅ 필수
├── .env                        ✅ 필수 (생성 필요)
├── README.md                   ✅ 필수 (간소화 버전)
├── auth-server/
│   ├── Dockerfile             ✅ 필수
│   ├── app_sqlite.py          ✅ 필수
│   └── requirements.txt       ✅ 필수
├── resource-server/
│   ├── Dockerfile             ✅ 필수
│   ├── app.py                 ✅ 필수
│   └── requirements.txt       ✅ 필수
├── client/
│   ├── Dockerfile             ✅ 필수
│   ├── app.py                 ✅ 필수
│   └── requirements.txt       ✅ 필수
└── nginx/
    └── nginx.conf             ✅ 필수
```

**제외할 파일:**
```
❌ docs/ (전체)
❌ .backup_docs/ (전체)
❌ .claude/
❌ .env (예제만 제공)
❌ __pycache__/
```

---

## 🖥️ GCP 인스턴스 스펙 계산

### 예상 참가자 수별 권장 사양

#### 권장 구성 (100명 기준) ⭐
```
인스턴스: 2개 (메인 1 + 백업 1)
타입: e2-medium × 2
- vCPU: 2 (Dedicated) × 2 = 4
- RAM: 4GB × 2 = 8GB
- Disk: 20GB SSD × 2
비용: 9시간 기준 약 $0.80 (₩1,000)
```

**왜 e2-medium인가?**
- ✅ **Dedicated vCPU** (e2-small은 Shared)
- ✅ **브루트포스 대응** - 참가자들이 디렉토리 브루트포스 예상
- ✅ **안정성** - CPU 60-70% 유지 (e2-small은 100% 도달)
- ✅ **비용** - e2-small 대비 ₩500 차이 (커피 1잔)

### 동시 접속자 계산 (브루트포스 고려)

#### 일반 시나리오
```
참가자 수: 100명
이 문제 시도율: 60% (60명)
동시 접속: 15-20명 (피크 시간)

1명당 리소스:
- CPU: 0.05 vCPU
- RAM: 50MB
- 요청: 10-20 req/min

총 필요 리소스: CPU 1 vCPU, RAM 1.5GB
```

#### 브루트포스 시나리오 (현실) ⚠️
```
브루트포스 사용자: 30-40명 (AI + ffuf/gobuster)
동시 브루트포스: 10-15명 (피크)

1명당 브루트포스:
- 경로 시도: 500-2000개
- 요청: 100-400 req/min
- 지속: 2-5분

피크 시 총 요청: 1000-4000 req/min
필요 리소스: CPU 2-2.5 vCPU, RAM 2-3GB

→ e2-small (Shared 2 vCPU): CPU 100% ❌
→ e2-medium (Dedicated 2 vCPU): CPU 60-70% ✅
```

**결론: 브루트포스 때문에 e2-medium 필수!**

### 기타 스펙 비교

| 타입 | vCPU | RAM | 비용/9h | 브루트포스 | 100명 |
|------|------|-----|---------|-----------|------|
| e2-small | 2 (shared) | 2GB | $0.40 | ❌ 느림 | ⚠️ |
| **e2-medium** | 2 | 4GB | **$0.80** | ✅ 안정 | ✅ |
| e2-standard-2 | 2 | 8GB | $1.60 | ✅ 오버킬 | 💰 |

---

## 🔧 배포 단계별 가이드

### Step 1: 배포 파일 준비

#### 1.1 깨끗한 배포 디렉토리 생성
```bash
# 로컬에서
mkdir oauth-ctf-deploy
cd oauth-ctf-deploy

# 필요한 파일만 복사
cp -r ../oauth-ctf-advanced/auth-server .
cp -r ../oauth-ctf-advanced/resource-server .
cp -r ../oauth-ctf-advanced/client .
cp -r ../oauth-ctf-advanced/nginx .
cp ../oauth-ctf-advanced/docker-compose.yml .
cp ../oauth-ctf-advanced/README.md .

# 불필요한 파일 제거
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
```

#### 1.2 .env 파일 생성
```bash
# 고유한 JWT_SECRET 생성
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(64))" > .env
echo "BASE_URL=http://YOUR_INSTANCE_IP:8080" >> .env
```

#### 1.3 README.md 간소화
```markdown
# OAuth CTF Challenge

## Quick Start
docker-compose up -d

## Access
http://YOUR_IP:8080

## Goal
Find the FLAG: MSG{...}
```

---

### Step 2: GCP 인스턴스 설정

#### 2.1 인스턴스 생성 (인스턴스 1)
```bash
gcloud compute instances create oauth-ctf-1 \
  --zone=asia-northeast3-a \
  --machine-type=e2-medium \
  --boot-disk-size=20GB \
  --boot-disk-type=pd-ssd \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --tags=ctf-server \
  --metadata=startup-script='#!/bin/bash
    apt-get update
    apt-get install -y docker.io docker-compose
    systemctl start docker
    systemctl enable docker
    usermod -aG docker $USER'
```

#### 2.2 방화벽 규칙 설정
```bash
# HTTP 포트 8080 오픈
gcloud compute firewall-rules create allow-ctf-http \
  --allow=tcp:8080 \
  --target-tags=ctf-server \
  --description="Allow CTF HTTP traffic"

# SSH 포트 (관리용)
gcloud compute firewall-rules create allow-ctf-ssh \
  --allow=tcp:22 \
  --target-tags=ctf-server \
  --source-ranges=YOUR_ADMIN_IP/32
```

---

### Step 3: 배포 실행

#### 3.1 파일 업로드
```bash
# 로컬에서 GCP로 전송
gcloud compute scp --recurse oauth-ctf-deploy oauth-ctf-1:~/ --zone=asia-northeast3-a
```

#### 3.2 인스턴스 접속 및 실행
```bash
# SSH 접속
gcloud compute ssh oauth-ctf-1 --zone=asia-northeast3-a

# 서버에서
cd oauth-ctf-deploy

# .env 수정 (인스턴스 IP로)
INSTANCE_IP=$(curl -s http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip -H "Metadata-Flavor: Google")
sed -i "s/YOUR_INSTANCE_IP/$INSTANCE_IP/g" .env

# Docker Compose 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f
```

#### 3.3 헬스 체크
```bash
# 서비스 상태 확인
curl http://localhost:8080/
curl http://localhost:8080/.well-known/oauth-authorization-server

# 모든 컨테이너 실행 중인지 확인
docker-compose ps
```

---

### Step 4: 인스턴스 2, 3 설정 (다중 서버)

#### 4.1 인스턴스 복제
```bash
# 인스턴스 1의 이미지 생성
gcloud compute images create oauth-ctf-image \
  --source-disk=oauth-ctf-1 \
  --source-disk-zone=asia-northeast3-a

# 인스턴스 2, 3 생성
gcloud compute instances create oauth-ctf-2 oauth-ctf-3 \
  --zone=asia-northeast3-a \
  --machine-type=e2-medium \
  --image=oauth-ctf-image \
  --tags=ctf-server
```

#### 4.2 Load Balancer 설정 (선택)
```bash
# 인스턴스 그룹 생성
gcloud compute instance-groups unmanaged create ctf-instance-group \
  --zone=asia-northeast3-a

# 인스턴스 추가
gcloud compute instance-groups unmanaged add-instances ctf-instance-group \
  --zone=asia-northeast3-a \
  --instances=oauth-ctf-1,oauth-ctf-2,oauth-ctf-3

# Health Check
gcloud compute health-checks create http ctf-health-check \
  --port=8080 \
  --request-path=/

# Backend Service
gcloud compute backend-services create ctf-backend \
  --protocol=HTTP \
  --health-checks=ctf-health-check \
  --global

# Backend에 인스턴스 그룹 추가
gcloud compute backend-services add-backend ctf-backend \
  --instance-group=ctf-instance-group \
  --instance-group-zone=asia-northeast3-a \
  --global
```

**참고:** Load Balancer는 선택사항입니다. 200명 이하면 인스턴스 2개 직접 제공도 OK.

---

## 📊 모니터링 설정

### 실시간 모니터링 스크립트

#### monitor.sh
```bash
#!/bin/bash
# GCP 인스턴스에서 실행

while true; do
  clear
  echo "=== OAuth CTF Monitor ==="
  echo "Time: $(date)"
  echo ""

  echo "=== Docker Status ==="
  docker-compose ps
  echo ""

  echo "=== System Resources ==="
  echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}')%"
  echo "RAM: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
  echo "Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
  echo ""

  echo "=== Active Connections ==="
  docker exec oauth-ctf-nginx netstat -an | grep :80 | wc -l
  echo ""

  echo "=== Recent Errors ==="
  docker-compose logs --tail=5 --since=1m | grep -i error || echo "No errors"

  sleep 5
done
```

```bash
chmod +x monitor.sh
./monitor.sh
```

---

## 🛡️ 보안 체크리스트

### 배포 전 확인

- [ ] `.env` 파일에 고유한 JWT_SECRET 설정
- [ ] `.env` 파일이 `.gitignore`에 포함됨
- [ ] docs/ 폴더 제거 (ATTACK_FLOW.md, solve.py)
- [ ] __pycache__ 제거
- [ ] docker-compose.yml의 security 설정 확인
- [ ] 방화벽 규칙: 8080만 오픈, SSH는 관리자 IP만
- [ ] Admin 비밀번호가 하드코딩됨 (의도된 것, OK)
- [ ] FLAG 값 확인: resource-server/app.py:23

### 대회 중 모니터링

- [ ] CPU 사용률 < 80%
- [ ] RAM 사용률 < 85%
- [ ] Disk 사용률 < 80%
- [ ] 컨테이너 모두 실행 중
- [ ] 에러 로그 확인

---

## 🔥 트러블슈팅

### 문제 1: 서버가 느려짐
```bash
# 리소스 확인
docker stats

# 가장 많은 리소스 사용하는 컨테이너 재시작
docker-compose restart auth-server

# 또는 전체 재시작
docker-compose restart
```

### 문제 2: 컨테이너가 죽음
```bash
# 로그 확인
docker-compose logs auth-server --tail=100

# 재시작
docker-compose up -d
```

### 문제 3: 디스크 풀
```bash
# Docker 정리
docker system prune -af

# SQLite DB 리셋
docker-compose down -v
docker-compose up -d
```

### 문제 4: 너무 많은 요청
```bash
# Rate limit 강화 (auth-server/app_sqlite.py 수정)
# login_attempts: 10 → 5
# token_requests: 5 → 3

# 재배포
docker-compose down
docker-compose up -d --build
```

---

## 💾 백업 전략

### 대회 시작 전
```bash
# 디스크 스냅샷 생성
gcloud compute disks snapshot oauth-ctf-1 \
  --snapshot-names=oauth-ctf-backup-$(date +%Y%m%d) \
  --zone=asia-northeast3-a
```

### 대회 중 정기 백업
```bash
# 15분마다 SQLite DB 백업
*/15 * * * * docker cp oauth-ctf-auth-server:/app/data/oauth_ctf.db ~/backups/oauth_ctf_$(date +\%H\%M).db
```

---

## 📈 용량 계획 요약

### 권장 구성 (200명 기준)

| 항목 | 스펙 |
|------|------|
| **인스턴스 수** | 2개 (백업 1개) |
| **타입** | e2-medium |
| **vCPU** | 2 × 2 = 4 |
| **RAM** | 4GB × 2 = 8GB |
| **Disk** | 20GB SSD × 2 |
| **비용** | $1.60/day (~₩2,000/일) |
| **예상 동시 접속** | 30-50명 |
| **여유율** | 50% |

### 인스턴스 배치 전략

```
인스턴스 1 (Primary): oauth-ctf-1
  → 메인 서버, 대회 공지에 IP 배포

인스턴스 2 (Standby): oauth-ctf-2
  → 백업 서버, 인스턴스 1 문제 시 공지

인스턴스 3 (Optional): oauth-ctf-3
  → 500명 이상 시에만 추가
```

---

## ✅ 최종 체크리스트

### D-1 (대회 하루 전)
- [ ] 인스턴스 2개 생성 완료
- [ ] Docker 이미지 빌드 완료
- [ ] 헬스 체크 통과
- [ ] 방화벽 설정 완료
- [ ] 스냅샷 백업 완료
- [ ] 모니터링 스크립트 테스트
- [ ] 인스턴스 IP 기록

### D-Day (대회 당일)
- [ ] 11:00 - 모든 컨테이너 실행 확인
- [ ] 11:30 - 헬스 체크 재확인
- [ ] 11:50 - 참가자에게 IP 공지
- [ ] 12:00 - 대회 시작
- [ ] 12:00-21:00 - 모니터링 (30분마다)
- [ ] 21:00 - 대회 종료
- [ ] 21:30 - 로그 백업

### D+1 (대회 다음날)
- [ ] 인스턴스 종료 또는 중지
- [ ] 로그 분석
- [ ] 비용 확인
- [ ] 피드백 수집

---

## 💰 비용 계산

### 9시간 대회 비용 (e2-medium × 2)

```
시간당 비용: $0.033 × 2 = $0.066
9시간 비용: $0.066 × 9 = $0.594
여유 3시간 (테스트+정리): $0.066 × 3 = $0.198
총 비용: ~$0.80 (약 ₩1,000)
```

**매우 저렴합니다!**

---

## 🎯 권장 사항

1. **인스턴스 2개** (e2-medium) ✅
   - 메인 1개 + 백업 1개
   - 비용 효율적
   - 200명까지 충분

2. **Load Balancer 불필요** ❌
   - 오버 엔지니어링
   - 비용 증가
   - 수동 전환으로 충분

3. **모니터링 필수** ⚠️
   - monitor.sh 실행
   - 30분마다 체크
   - Discord/Slack 알림 설정 권장

4. **백업 전략** 💾
   - 대회 전 스냅샷 1회
   - 대회 후 로그 백업

**준비 완료 시간**: 약 2-3시간
**예상 비용**: ₩1,000-2,000
**안정성**: 매우 높음

---

## 🚀 빠른 배포 명령어 모음

```bash
# 1. 로컬에서 파일 준비
mkdir oauth-ctf-deploy
# ... 파일 복사 ...

# 2. GCP 인스턴스 생성
gcloud compute instances create oauth-ctf-1 \
  --zone=asia-northeast3-a \
  --machine-type=e2-medium \
  --boot-disk-size=20GB \
  --tags=ctf-server

# 3. 파일 업로드
gcloud compute scp --recurse oauth-ctf-deploy oauth-ctf-1:~/ --zone=asia-northeast3-a

# 4. SSH 접속 및 실행
gcloud compute ssh oauth-ctf-1 --zone=asia-northeast3-a
cd oauth-ctf-deploy
docker-compose up -d

# 5. 헬스 체크
curl http://localhost:8080/
```

---

## 🎯 긴급 증설 가이드 (이미지 활용)

### 왜 필요한가?

대회 중 예상치 못한 상황:
- ✅ 참가자가 예상보다 많음 (100명 → 200명)
- ✅ 서버 과부하 (브루트포스 폭주)
- ✅ 인스턴스 장애 발생

→ **5분 안에 새 서버 추가 필요!**

### 전략: 이미지 생성

처음 배포한 인스턴스를 이미지로 만들어두면, 클릭 몇 번으로 동일한 서버 생성 가능.

---

## 📸 Step 1: 이미지 생성 (대회 시작 전)

### 1.1 첫 번째 인스턴스 완벽하게 준비

```bash
# 1. oauth-ctf-1 배포 완료
gcloud compute ssh oauth-ctf-1 --zone=asia-northeast3-a
cd oauth-ctf-deploy
sudo ./deploy.sh

# 2. 헬스 체크
curl http://localhost:8080/
docker-compose ps

# 3. 모든 것이 정상이면 → 이미지 생성 준비 완료
```

### 1.2 인스턴스 중지 (선택사항)

```bash
# 이미지 생성 시 인스턴스를 중지하는 것이 권장됨
gcloud compute instances stop oauth-ctf-1 --zone=asia-northeast3-a
```

**참고:** 실행 중인 인스턴스도 이미지 생성 가능하지만, 데이터 일관성을 위해 중지 권장.

### 1.3 커스텀 이미지 생성 ⭐

```bash
# 이미지 생성 (5-10분 소요)
gcloud compute images create oauth-ctf-golden-image \
  --source-disk=oauth-ctf-1 \
  --source-disk-zone=asia-northeast3-a \
  --family=oauth-ctf \
  --description="OAuth CTF Advanced - Ready to deploy"

# 생성 확인
gcloud compute images list --filter="name:oauth-ctf-golden-image"
```

**중요:** 이 이미지에는 다음이 포함됨:
- ✅ Docker 설치 완료
- ✅ Docker Compose 설치 완료
- ✅ 모든 소스 코드
- ✅ .env 파일 (JWT_SECRET 포함)
- ✅ Docker 이미지 빌드 완료

### 1.4 인스턴스 재시작

```bash
gcloud compute instances start oauth-ctf-1 --zone=asia-northeast3-a
```

---

## 🚨 Step 2: 긴급 증설 (대회 중)

### 시나리오: CPU 80% 넘어감, 서버 느려짐

#### 2.1 새 인스턴스 생성 (2분)

```bash
# 이미지로부터 새 인스턴스 생성
gcloud compute instances create oauth-ctf-3 \
  --zone=asia-northeast3-a \
  --machine-type=e2-medium \
  --image=oauth-ctf-golden-image \
  --boot-disk-size=20GB \
  --tags=ctf-server

# 또는 여러 개 동시 생성
gcloud compute instances create oauth-ctf-3 oauth-ctf-4 \
  --zone=asia-northeast3-a \
  --machine-type=e2-medium \
  --image=oauth-ctf-golden-image \
  --boot-disk-size=20GB \
  --tags=ctf-server
```

**소요 시간: 1-2분**

#### 2.2 서비스 시작 (1분)

```bash
# SSH 접속
gcloud compute ssh oauth-ctf-3 --zone=asia-northeast3-a

# Docker 컨테이너 시작 (이미 빌드되어 있음!)
cd oauth-ctf-deploy
docker-compose up -d

# 확인
curl http://localhost:8080/
```

**소요 시간: 30초-1분**

#### 2.3 참가자에게 공지 (1분)

```
Discord/Slack:
"🚀 추가 서버 오픈!
서버가 느린 분들은 아래 IP로 접속하세요:
http://NEW_IP:8080

기존 서버도 계속 사용 가능합니다."
```

**총 소요 시간: 3-5분** ✅

---

## 🔧 Alternative: 스냅샷 사용

이미지 대신 스냅샷 사용 가능 (더 빠름)

### 스냅샷 생성
```bash
# 디스크 스냅샷 생성 (3-5분)
gcloud compute disks snapshot oauth-ctf-1 \
  --snapshot-names=oauth-ctf-snapshot \
  --zone=asia-northeast3-a

# 스냅샷으로부터 새 디스크 생성
gcloud compute disks create oauth-ctf-disk-3 \
  --source-snapshot=oauth-ctf-snapshot \
  --zone=asia-northeast3-a

# 새 인스턴스에 연결
gcloud compute instances create oauth-ctf-3 \
  --zone=asia-northeast3-a \
  --machine-type=e2-medium \
  --disk=name=oauth-ctf-disk-3,boot=yes \
  --tags=ctf-server
```

**차이점:**
- **이미지**: 여러 zone에서 재사용 가능, 약간 느림 (5-10분)
- **스냅샷**: 같은 zone만 가능, 빠름 (3-5분), 증분 백업

**권장: 이미지 (더 유연함)**

---

## 📋 긴급 증설 체크리스트

### D-1 (대회 전날)
- [ ] oauth-ctf-1 완벽하게 설정
- [ ] 헬스 체크 통과
- [ ] **골든 이미지 생성** ⭐
- [ ] oauth-ctf-2 배포 (백업)
- [ ] 방화벽 규칙 확인

### 대회 중 모니터링
```bash
# CPU 70% 넘으면 주의
# CPU 80% 넘으면 즉시 증설 준비
./monitor.sh
```

### 긴급 증설 실행 (CPU 80%+)

#### 방법 1: 이미지로 즉시 생성 (권장)
```bash
gcloud compute instances create oauth-ctf-3 \
  --image=oauth-ctf-golden-image \
  --machine-type=e2-medium \
  --zone=asia-northeast3-a \
  --tags=ctf-server

# SSH 후 시작
gcloud compute ssh oauth-ctf-3
cd oauth-ctf-deploy && docker-compose up -d
```

#### 방법 2: 수동 배포 (20분)
```bash
# 처음부터 다시 (비추천)
gcloud compute instances create oauth-ctf-3 ...
gcloud compute scp --recurse oauth-ctf-deploy ...
# ... 시간 오래 걸림
```

---

## 🎮 실전 시나리오

### 시나리오 1: 예상보다 참가자 2배

```
상황:
- 예상: 100명
- 실제: 200명
- CPU: 85%, 응답 지연

행동:
1. 이미지로 oauth-ctf-3, 4 생성 (2분)
2. docker-compose up -d (각 1분)
3. IP 공지 (1분)
───────────────────
총: 5분 안에 해결 ✅
```

### 시나리오 2: 인스턴스 1 다운

```
상황:
- oauth-ctf-1 응답 없음
- 참가자 불만 폭주

행동:
1. oauth-ctf-2 IP 즉시 공지 (1분)
2. oauth-ctf-1 재시작 시도
3. 안 되면 이미지로 재생성 (5분)
```

### 시나리오 3: 브루트포스 폭주

```
상황:
- 30명이 동시 브루트포스
- CPU 95%
- 응답 10초 이상

행동:
1. oauth-ctf-3 즉시 추가 (5분)
2. Rate limit 강화 (선택)
3. 참가자들에게 2개 서버 분산 공지
```

---

## 💾 이미지 vs 스냅샷 비교

| 항목 | 커스텀 이미지 | 스냅샷 |
|------|-------------|--------|
| **생성 시간** | 5-10분 | 3-5분 |
| **복원 시간** | 1-2분 | 2-3분 |
| **Zone 제한** | 없음 (글로벌) | 동일 zone만 |
| **증분 백업** | ❌ | ✅ |
| **용도** | 증설 | 백업 |
| **비용** | 저장 비용만 | 저장 비용만 |
| **권장** | ✅ 긴급 증설용 | ✅ 백업용 |

**권장 조합:**
```
골든 이미지 1개 (증설용)
+ 스냅샷 1-2개 (백업용)
```

---

## 🔥 빠른 증설 스크립트

### quick-scale.sh (로컬 PC에서 실행)

```bash
#!/bin/bash
# OAuth CTF - Quick Scale Script

ZONE="asia-northeast3-a"
IMAGE="oauth-ctf-golden-image"
INSTANCE_NAME="oauth-ctf-$1"

if [ -z "$1" ]; then
  echo "Usage: ./quick-scale.sh <instance-number>"
  echo "Example: ./quick-scale.sh 3"
  exit 1
fi

echo "🚀 Creating instance: $INSTANCE_NAME"

# 인스턴스 생성
gcloud compute instances create $INSTANCE_NAME \
  --zone=$ZONE \
  --machine-type=e2-medium \
  --image=$IMAGE \
  --boot-disk-size=20GB \
  --tags=ctf-server

echo "⏳ Waiting for instance to start..."
sleep 30

# SSH로 서비스 시작
echo "🐳 Starting Docker containers..."
gcloud compute ssh $INSTANCE_NAME --zone=$ZONE --command="cd oauth-ctf-deploy && docker-compose up -d"

# IP 획득
IP=$(gcloud compute instances describe $INSTANCE_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "✅ New server ready!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Access URL: http://$IP:8080"
echo ""
echo "Copy this to Discord:"
echo "🚀 추가 서버 오픈: http://$IP:8080"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
```

### 사용법
```bash
chmod +x quick-scale.sh
./quick-scale.sh 3   # oauth-ctf-3 생성
./quick-scale.sh 4   # oauth-ctf-4 생성
```

---

## 📊 권장 이미지 전략

### 전략 1: 골든 이미지 (권장)

```
대회 D-1:
1. oauth-ctf-1 완벽 설정
2. 골든 이미지 생성
3. oauth-ctf-2 배포 (이미지 사용)

대회 중 필요 시:
4. oauth-ctf-3, 4, 5... 즉시 추가 (3-5분)
```

### 전략 2: 스냅샷 백업

```
대회 중:
- 매 1시간마다 자동 스냅샷
- 롤백 가능

크론잡 예시:
0 * * * * gcloud compute disks snapshot oauth-ctf-1 \
  --snapshot-names=ctf-snapshot-$(date +\%H) \
  --zone=asia-northeast3-a
```

---

## 💡 Pro Tips

### 1. 이미지 생성 타이밍
```
✅ 최적: 첫 배포 직후, 모든 테스트 완료 후
⚠️ 주의: 대회 시작 후 생성하면 10분 소요
```

### 2. 여러 Zone 활용
```bash
# 이미지는 글로벌이므로 다른 zone에서도 사용 가능
gcloud compute instances create oauth-ctf-tokyo \
  --zone=asia-northeast1-a \
  --image=oauth-ctf-golden-image

# 지역별 분산 가능
```

### 3. 인스턴스 이름 규칙
```
oauth-ctf-1  (메인)
oauth-ctf-2  (백업)
oauth-ctf-3+ (긴급 증설)
```

### 4. IP 관리
```bash
# 고정 IP 예약 (선택)
gcloud compute addresses create oauth-ctf-ip-1 --region=asia-northeast3

# 인스턴스에 할당
gcloud compute instances add-access-config oauth-ctf-1 \
  --access-config-name="external-nat" \
  --address=oauth-ctf-ip-1
```

---

## ✅ 최종 체크리스트

### 대회 D-1
- [ ] oauth-ctf-1 완벽 배포
- [ ] **골든 이미지 생성** ⭐⭐⭐
- [ ] oauth-ctf-2 백업 서버 배포
- [ ] quick-scale.sh 준비
- [ ] 방화벽 규칙 확인
- [ ] 모니터링 스크립트 테스트

### 대회 당일
- [ ] 두 서버 모두 실행
- [ ] 골든 이미지 존재 확인
- [ ] monitor.sh로 CPU 체크
- [ ] Discord/Slack 알림 준비
- [ ] 필요 시 즉시 증설

### 긴급 상황 대응
```
CPU 70%: 주의 깊게 모니터링
CPU 80%: 증설 준비 (quick-scale.sh)
CPU 90%: 즉시 증설 실행
서버 다운: 백업 서버 IP 공지
```

완료! 🎉
