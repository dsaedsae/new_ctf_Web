# CTF Challenge - Legacy Microservice Exploitation

MongoDB + Flask 기반 웹 취약점 CTF 문제입니다.

**난이도:** DreamHack Level 7-8
**예상 풀이 시간:** 90-110분 (블랙박스)

## 🚀 빠른 배포

### 1. 환경 설정

```bash
# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (필수!)
nano .env
```

**.env 설정 항목:**
- `SECRET_KEY`: Flask secret key (필수, 기본값 제공됨)
- `FLAG`: 커스텀 플래그 설정 (필수)
- `CTF_PORT`: 포트 번호 (선택, 기본: 5000)

**Note:** .env.example에 이미 올바른 SECRET_KEY 값이 포함되어 있습니다.

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

**Note:** SECRET_KEY는 참가자가 API 응답에서 유추할 수 있는 값이어야 합니다.

## 🔒 보안 주의사항

⚠️ **절대 공개하지 마세요:**
- `.env` 파일
- `SECRET_KEY` 값 (참가자가 유추해야 함)
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

---

## 📌 추가 정보

이 문제는 레거시 마이크로서비스 환경의 연쇄 취약점을 다룹니다.
참가자들은 서비스 탐색부터 시작하여 최종 플래그까지 도달해야 합니다.

**권장 환경:**
- 독립된 네트워크 환경에서 실행
- 방화벽 설정으로 외부 접근 제한
- 정기적인 컨테이너 재시작 권장

---

**CTF 대회 운영자를 위한 배포 가이드**
