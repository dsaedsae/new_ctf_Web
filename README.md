# CTF Challenge - Legacy Microservice Exploitation V5.0

MongoDB + Flask 기반 웹 취약점 CTF 문제입니다.

**난이도:** DreamHack Level 7-8
**예상 풀이 시간:** 90-120분 (블랙박스)

## 🆕 V5.0 변경사항

- **Salt 브루트포스 제거**: Config backup을 통한 직접 secret 노출로 변경
- **체이닝 자연스러움 개선**: 인위적인 조건들 제거
- **Red Herring 개선**: 더 효과적인 미끼 엔드포인트
- **Command Injection 검증 개선**: 더 현실적인 path validation

## 🚀 빠른 배포

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (필수!)
nano .env
```

**.env 설정 항목:**
- `SECRET_KEY`: Flask secret key (32 hex chars, 필수)
- `FLAG`: 커스텀 플래그 설정 (필수)
- `BLIND_RCE`: 난이도 설정 (false/true)

**SECRET_KEY 생성 예시:**
```bash
openssl rand -hex 16
```

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
| `SECRET_KEY` | ✅ | Flask secret key (32 hex chars) |
| `FLAG` | ✅ | CTF 플래그 |
| `CTF_PORT` | ❌ | 포트 (기본: 5000) |
| `BLIND_RCE` | ❌ | Blind RCE 모드 (기본: false) |

## 🔒 보안 주의사항

⚠️ **절대 공개하지 마세요:**
- `.env` 파일
- `SECRET_KEY` 값
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

- `BLIND_RCE=false`: 일반 모드 (RCE 출력 표시)
- `BLIND_RCE=true`: Hard 모드 (RCE 출력 차단)

## 🎯 취약점 체인 개요

1. **Service Discovery** → 레거시 엔드포인트 발견
2. **Information Disclosure** → Config backup에서 secret 일부 노출
3. **Secret Key Recovery** → 브루트포스로 나머지 복구
4. **Session Forgery** → Guest → Admin 권한 상승
5. **NoSQL Injection** → MongoDB $where 연산자 악용
6. **Command Injection** → Log file 파라미터 악용
7. **RCE** → Flag 획득

---

**CTF 대회 운영자를 위한 간단한 배포 가이드**
