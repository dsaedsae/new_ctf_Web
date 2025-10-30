# CTF Challenge - Legacy Microservice Exploitation V6.1

MongoDB + Flask 기반 웹 취약점 CTF 문제입니다.

**난이도:** DreamHack Level 7-8
**예상 풀이 시간:** 90-110분 (블랙박스)

## 🆕 V6.1 변경사항 (AI-Resistant & Natural)

- **분산 힌트를 통한 Secret 유추**: 검증 해시 제거로 자연스러움 향상
- **Permissions 기반 권한 시스템**: auth_token 제거로 자연스러움 향상
- **include_inactive/limit 옵션**: mode 파라미터 제거로 자연스러움 향상
- **Path traversal + 세미콜론 우회**: 현실적인 검증 실수 패턴
- **완전한 안정성**: 네트워크/시간 의존성 제거

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

1. **Service Discovery** → 레거시 서비스 발견
2. **Information Gathering** → 분산된 힌트 수집 (config_backup, health, headers)
3. **Secret Key Derivation** → Service metadata로부터 secret 유추
4. **Session Forgery** → Guest → Admin 권한 상승 (Permissions 추가)
5. **NoSQL Injection** → MongoDB $where + include_inactive/limit 우회
6. **Command Injection** → Path traversal + 세미콜론 우회
7. **RCE** → Flag 획득

**특징:**
- 모든 힌트가 명시적으로 제공됨
- 네트워크/시간 의존성 없음 (완전 안정적)
- AI 저항성 높음 (논리적 추론 필요)
- 자연스러운 실수 패턴 (CTF스럽지 않음)

---

**CTF 대회 운영자를 위한 간단한 배포 가이드**
