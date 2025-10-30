# CTF Challenge - Legacy Microservice Exploitation

MongoDB + Flask 기반 웹 취약점 CTF 문제입니다.

## 🚀 빠른 배포

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (필수!)
nano .env
```

**.env 설정 항목:**
- `COMPANY_SALT`: 랜덤 값 설정 (필수)
- `FLAG`: 커스텀 플래그 설정 (필수)
- `BLIND_RCE`: 난이도 설정 (false/true)

### 2. Docker Compose로 실행

```bash
docker-compose up -d
```

### 3. 접속 확인

```
http://localhost:5000
```

## 📋 시스템 요구사항

- Docker & Docker Compose
- MongoDB 4.4 (자동 설치됨)
- 포트 5000 사용 가능

## ⚙️ 환경 변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `COMPANY_SALT` | ✅ | 세션 키 생성용 Salt |
| `FLAG` | ✅ | CTF 플래그 |
| `CTF_PORT` | ❌ | 포트 (기본: 5000) |
| `BLIND_RCE` | ❌ | Blind RCE 모드 (기본: false) |

## 🔒 보안 주의사항

⚠️ **절대 공개하지 마세요:**
- `.env` 파일
- `COMPANY_SALT` 값
- `FLAG` 값

## 📝 배포 스크립트 사용 (선택)

```bash
./deploy.sh
```

자동으로 환경을 설정하고 컨테이너를 실행합니다.

## 🛑 종료

```bash
docker-compose down
```

## 📊 난이도 설정

- `BLIND_RCE=false`: 일반 모드
- `BLIND_RCE=true`: Hard 모드 (출력 차단)

---

**CTF 대회 운영자를 위한 간단한 배포 가이드**
