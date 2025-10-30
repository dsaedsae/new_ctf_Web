# AWS 배포 빠른 시작 가이드 (5분 완성)

처음부터 끝까지 5-10분이면 배포 가능합니다.

---

## 🚀 1단계: AWS EC2 인스턴스 생성 (3분)

### AWS Console에서:

1. **EC2 대시보드** 접속
   - https://console.aws.amazon.com/ec2

2. **"인스턴스 시작"** 클릭

3. **빠른 설정**:
   ```
   이름: ctf-server
   AMI: Ubuntu Server 22.04 LTS
   인스턴스 유형: t2.micro (프리티어) 또는 t3.small (권장)
   키 페어: 새로 생성 → 다운로드 (.pem 파일)
   네트워크: 퍼블릭 IP 자동 할당 ✓
   스토리지: 20 GB
   ```

4. **"인스턴스 시작"** 클릭

5. **보안 그룹 편집**:
   - EC2 대시보드 → 보안 그룹 → 인바운드 규칙 편집
   - 추가:
     - SSH (22) → 내 IP
     - 사용자 지정 TCP (5000) → 0.0.0.0/0

---

## 🔐 2단계: SSH 접속 (1분)

### Mac/Linux:

```bash
chmod 400 ~/Downloads/ctf-key.pem
ssh -i ~/Downloads/ctf-key.pem ubuntu@<퍼블릭-IP>
```

### Windows:

PuTTY 사용 (키 파일 .ppk로 변환 필요)

---

## 📦 3단계: 서버 설정 (5분)

서버에 접속한 후:

```bash
# 1. 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# 2. Docker 설치
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 3. Docker Compose 설치
sudo apt-get install -y docker-compose-plugin

# 4. 현재 사용자에게 Docker 권한
sudo usermod -aG docker $USER

# 5. 재접속 (권한 적용)
exit
ssh -i ~/Downloads/ctf-key.pem ubuntu@<퍼블릭-IP>
```

---

## 🎯 4단계: 프로젝트 배포 (2분)

```bash
# 1. Git 설치
sudo apt install -y git

# 2. 프로젝트 클론
git clone https://github.com/dsaedsae/new_ctf_Web.git
cd new_ctf_Web

# 3. 브랜치 전환
git checkout claude/mongodb-44-ctf-application-011CUciUTX4HvLBd24UHPcB7

# 4. 환경 변수 설정
cp .env.example .env
nano .env

# 아래 내용으로 수정:
# COMPANY_SALT=<랜덤값>  # openssl rand -hex 16 으로 생성
# FLAG=FLAG{your_flag_here}
# BLIND_RCE=false

# 또는 자동 생성:
echo "COMPANY_SALT=$(openssl rand -hex 16)" >> .env
echo "FLAG=FLAG{aws_deployment_success_2025}" >> .env
echo "BLIND_RCE=false" >> .env

# 5. 자동 배포 스크립트 실행
chmod +x deploy.sh
./deploy.sh
```

---

## ✅ 5단계: 확인

```bash
# 헬스체크
curl http://localhost:5000/health

# 브라우저에서:
http://<퍼블릭-IP>:5000
```

**성공!** 🎉

---

## 🔧 문제 해결

### 컨테이너가 안 뜨면?

```bash
docker compose logs
docker compose down -v
docker compose up -d
```

### 포트가 안 열리면?

AWS Console → 보안 그룹 → 인바운드 규칙 확인

### 메모리 부족?

```bash
# Swap 추가
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## 📝 다음 단계

### 도메인 연결 (선택):

1. 도메인 구매 (Namecheap, GoDaddy 등)
2. A 레코드 추가: `ctf.yourdomain.com → <EC2 IP>`
3. Nginx + SSL 설정 (상세 가이드: `AWS_DEPLOYMENT.md` 참조)

### 모니터링:

```bash
# 로그 실시간 보기
docker compose logs -f

# 리소스 사용량
docker stats

# 컨테이너 상태
docker compose ps
```

---

## 💰 비용

- **t2.micro (프리티어)**: 무료
- **t3.small**: 약 $15/월
- **데이터 전송**: 15GB까지 무료

---

## 🎓 전체 가이드

더 자세한 내용은 `AWS_DEPLOYMENT.md` 참조

**배포 완료!** 참가자들에게 URL을 공유하세요! 🚀
