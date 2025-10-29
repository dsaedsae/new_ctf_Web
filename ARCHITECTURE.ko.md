# 프로젝트 구조 및 파일 문서

## 📁 전체 파일 구조

```
ctf-legacy-microservice/
├── 핵심 애플리케이션
│   ├── app.py                      # 메인 Flask 애플리케이션
│   ├── init_db.py                  # 데이터베이스 초기화 스크립트
│   └── requirements.txt            # Python 의존성
│
├── Docker 인프라
│   ├── Dockerfile                  # 컨테이너 이미지 정의
│   ├── docker-compose.yml          # 멀티 컨테이너 오케스트레이션
│   └── docker-entrypoint.sh        # 컨테이너 시작 스크립트
│
├── 설정 파일
│   ├── .env.example               # 환경변수 템플릿
│   ├── .gitignore                 # Git 제외 목록
│   ├── .gitattributes             # Git 줄바꿈 설정
│   └── .dockerignore              # Docker 빌드 제외 목록
│
├── 문서
│   ├── README.md                   # 참가자용 문제 설명
│   ├── TESTING.md                  # 로컬 테스트 체크리스트
│   ├── ARCHITECTURE.md             # 파일 구조 설명 (영문)
│   ├── ARCHITECTURE.ko.md          # 파일 구조 설명 (한글)
│   └── DIFFICULTY_TUNING.md        # 난이도 조절 가이드
│
└── 솔루션 파일 (Docker에서 제외)
    ├── requirements.txt            # Exploit 의존성
    ├── exploit.py                  # 완전 자동화 exploit
    ├── exploit_blind.py            # Blind RCE exploit 데모
    └── WRITEUP.md                  # 내부 솔루션 가이드
```

---

## 🔧 핵심 애플리케이션 파일

### 1. app.py (9.2KB)
**목적**: 의도적 취약점이 포함된 메인 Flask 웹 애플리케이션

**주요 구성요소**:
- **Lines 1-47**: 설정 및 초기화
  - 환경변수 로딩 (COMPANY_SALT, FLAG, MONGO_URI)
  - COMPANY_SALT로부터 Flask secret key 유도
  - MongoDB 연결 설정
  - 보안 설정 (세션 쿠키, 타임아웃)

- **Lines 49-124**: Stage 1 - 서비스 탐색
  - `/api/v2/services` - 사용 가능한 서비스 목록 (auth, api, legacy)
  - `/api/v2/services/<service>/endpoints` - 서비스 엔드포인트 열거
  - 목적: 공격자가 "legacy" 서비스를 발견하도록 함

- **Lines 126-154**: Stage 2-3 - 정보 노출
  - `/api/legacy/get_salt` - **취약점**: COMPANY_SALT 노출
  - `/api/legacy/system_info` - Secret 유도에 대한 힌트 제공
  - 목적: Secret key 계산 가능하게 함

- **Lines 156-172**: Stage 4 - 세션 검증
  - `/api/auth/guest` - 테스트용 게스트 세션 생성
  - 목적: 공격자가 secret key 가설을 검증하도록 함

- **Lines 174-260**: Stage 6 - RCE 체인
  - `/api/admin/db/migrate` - 관리자 전용 데이터베이스 마이그레이션 엔드포인트
  - **취약점 1**: `$where` 연산자를 통한 NoSQL Injection (line 202)
  - **취약점 2**: `log_file` 파라미터를 통한 Command Injection (line 209)
  - 목적: 체인 취약점을 통한 최종 공격 대상

- **Lines 262-303**: 유틸리티 엔드포인트
  - `/health` - MongoDB JavaScript 검증을 포함한 헬스 체크
  - `/` - API 정보가 있는 루트 엔드포인트

**보안 기능**:
- Line 33-37: COMPANY_SALT 설정 검증 (기본값 우회 방지)
- Line 192: Admin 역할 체크 (직접 접근 방지)
- Line 205: 조건부 RCE (NoSQL injection 성공 필요)
- Line 216: 타임아웃 보호 (최대 5초)
- Line 189: BLIND_RCE 모드 (난이도 증가)

**주요 변수**:
- `COMPANY_SALT`: 세션 키 유도를 위한 비밀 재료
- `FLAG`: 획득할 CTF 플래그
- `BLIND_RCE`: 명령어 출력 가시성 토글

---

### 2. init_db.py (4.3KB)
**목적**: 테스트 데이터로 MongoDB를 초기화하고 JavaScript 지원 검증

**함수들**:
- `wait_for_mongodb()` (Lines 17-37)
  - MongoDB가 사용 가능해질 때까지 최대 60초 대기
  - 2초 간격으로 재시도 로직 사용
  - 연결 시 MongoClient 인스턴스 반환

- `verify_javascript_enabled()` (Lines 39-77)
  - **중요 함수**: MongoDB JavaScript 활성화 여부 테스트
  - 테스트 문서 삽입 후 `$where` 쿼리 실행
  - JavaScript 비활성화 시 컨테이너 **시작 실패**
  - 디버깅을 위한 상세 에러 메시지 제공

- `init_database()` (Lines 79-116)
  - 기존 데이터 삭제
  - 4개의 더미 사용자 문서 삽입:
    - john.doe (developer)
    - jane.smith (analyst)
    - admin (admin) ← NoSQL injection에 사용
    - legacy.service (deprecated)
  - 삽입 성공 확인

- `main()` (Lines 118-151)
  - 초기화 시퀀스 조율
  - 종료 코드 반환 (0=성공, 1=실패)
  - docker-entrypoint.sh에서 호출됨

**중요성**:
- NoSQL injection은 MongoDB JavaScript 활성화 필요
- JavaScript 없으면 `$where` 연산자가 작동하지 않음
- 이 검증으로 CTF 문제 해결 가능성 보장

---

### 3. requirements.txt (5줄)
**목적**: Flask 애플리케이션용 Python 의존성

**패키지들**:
```
Flask==3.0.0          # 웹 프레임워크
pymongo==4.6.1        # MongoDB 드라이버
gunicorn==21.2.0      # 프로덕션 WSGI 서버
gevent==23.9.1        # Gunicorn용 비동기 worker
itsdangerous==2.1.2   # 세션 서명 (Flask 의존성)
```

**버전 고정**:
- 재현성을 위해 모든 버전 고정
- 함께 작동하도록 테스트 및 검증됨
- 이 특정 버전들에 알려진 취약점 없음

---

## 🐳 Docker 인프라

### 4. Dockerfile (1.5KB)
**목적**: 보안 모범 사례를 적용한 컨테이너 이미지 빌드

**빌드 단계**:
- **Lines 1-6**: 베이스 이미지 및 메타데이터
  - 작은 용량을 위해 `python:3.9-slim` 사용
  - 식별을 위한 레이블

- **Lines 8-15**: 보안 설정
  - 비root 사용자 `ctfuser` 생성 (UID 1000)
  - 작업 디렉토리를 `/app`로 설정
  - Python 버퍼링되지 않은 출력 활성화

- **Lines 17-22**: 시스템 의존성
  - gcc와 python3-dev 설치 (gevent 필요)
  - 이미지 크기 줄이기 위해 apt 캐시 정리

- **Lines 24-27**: Python 의존성
  - requirements.txt 복사 및 설치
  - 빠른 재빌드를 위해 pip 캐시 사용

- **Lines 29-42**: 애플리케이션 설정
  - 필요한 파일만 복사 (app.py, init_db.py, docker-entrypoint.sh)
  - CRLF 줄바꿈 수정 (Windows 호환성)
  - 진입점을 실행 가능하게 만듦
  - 파일 소유권을 ctfuser로 설정

- **Lines 44-52**: 최종 설정
  - 비root 사용자로 전환
  - 포트 5000 노출
  - urllib을 사용한 헬스 체크 정의 (외부 의존성 없음)
  - 헬스 체크가 `javascript_enabled: true` 검증

**보안 하이라이트**:
- 비root 실행 (Line 42)
- 최소 파일 복사 (Line 30)
- 헬스 체크 검증 (Line 48-52)

---

### 5. docker-compose.yml (1.3KB)
**목적**: 멀티 컨테이너 배포 오케스트레이션

**서비스들**:

#### web (Lines 5-23)
- 로컬 Dockerfile에서 빌드
- 포트 노출 (기본 5000, CTF_PORT로 설정 가능)
- MongoDB가 정상 상태일 때 의존
- **환경 변수**:
  - `MONGO_URI`: MongoDB 연결 문자열
  - `COMPANY_SALT`: **필수** (기본값 없음)
  - `FLAG`: CTF 플래그
  - `BLIND_RCE`: 난이도 토글
- Dockerfile의 HEALTHCHECK 사용 (중복 없음)

#### db (Lines 25-42)
- 공식 `mongo:7.0` 이미지 사용
- **중요 LINE 30**: `javascriptEnabled=true`로 JavaScript 활성화
- 명명된 볼륨 `mongo_data`에 데이터 저장
- mongosh/mongo 명령어를 사용한 헬스 체크
- 공격적인 헬스 체크 (5초 간격, 12회 재시도)

**네트워크 & 볼륨**:
- 커스텀 브리지 네트워크 `ctf_network`
- 지속성을 위한 명명된 볼륨 `ctf_mongodb_data`

**이 설정을 사용하는 이유**:
- Line 19: `${COMPANY_SALT:?...}` 환경변수 강제
- Line 30: JavaScript는 NoSQL injection에 필수
- 헬스 체크가 올바른 시작 순서 보장

---

### 6. docker-entrypoint.sh (800 bytes)
**목적**: 컨테이너 초기화 스크립트

**실행 흐름**:
```bash
단계 1: init_db.py 실행
   ├─ MongoDB 연결
   ├─ JavaScript 활성화 검증
   ├─ 테스트 데이터 채우기
   └─ 단계 실패 시 종료

단계 2: Gunicorn 시작
   ├─ 0.0.0.0:5000에 바인드
   ├─ 4개의 gevent worker 사용
   ├─ 30초 타임아웃
   └─ stdout/stderr로 로그 출력
```

**주요 기능**:
- Line 13-17: 에러 처리가 있는 데이터베이스 초기화
- Line 21-28: Gunicorn 설정
  - `--worker-class gevent`: 비동기 I/O 지원
  - `--workers 4`: 동시 요청 처리
  - `--timeout 30`: 중단된 요청 방지
  - `exec`: 셸 프로세스 대체 (적절한 시그널 처리)

**에러 처리**:
- init_db.py 실패 시, 컨테이너 즉시 종료
- 잘못된 데이터베이스 상태로 실행 방지

---

## ⚙️ 설정 파일

### 7. .env.example (14줄)
**목적**: 환경 설정 템플릿

**변수들**:
```bash
CTF_PORT=5000                    # 호스트 포트 바인딩
COMPANY_SALT=                    # 필수: 랜덤 값
FLAG=FLAG{...}                   # CTF 플래그
BLIND_RCE=false                  # 난이도 토글
```

**사용법**:
```bash
cp .env.example .env
nano .env  # COMPANY_SALT 설정
docker-compose up -d
```

**보안 주의사항**:
- Line 10: COMPANY_SALT **의도적으로 비워둠**
- 운영자가 고유 값 설정하도록 강제
- 예측 가능한 기본값 방지

---

### 8. .gitignore (23줄)
**목적**: git 저장소에서 파일 제외

**카테고리**:
- Python 아티팩트: `__pycache__/`, `*.pyc`
- 가상 환경: `venv/`, `env/`
- IDE 파일: `.vscode/`, `.idea/`
- 비밀: `.env` ← 가장 중요
- OS 파일: `.DS_Store`, `Thumbs.db`
- Docker 볼륨: `mongo_data/`

**중요성**:
- 비밀이 있는 `.env` 커밋 방지
- 저장소를 깨끗하게 유지
- 민감한 설정 보호

---

### 9. .gitattributes (2줄)
**목적**: 일관된 줄바꿈 보장

```
*.sh text eol=lf
docker-entrypoint.sh text eol=lf
```

**중요성**:
- CRLF (Windows)가 있는 셸 스크립트는 Linux에서 실행 안 됨
- `.sh` 파일에 LF 줄바꿈 강제
- "bad interpreter" 에러 방지

---

### 10. .dockerignore (35줄)
**목적**: Docker 빌드 컨텍스트에서 파일 제외

**주요 제외 항목**:
- `solution/` ← 컨테이너에서 exploit 코드 방지
- `.env` ← 이미지에서 비밀 방지
- `.env.example` ← 이미지에서 힌트 방지
- `.git/` ← 이미지 크기 감소
- 개발 파일: `.vscode/`, `*.log`

**보안 영향**:
- 공격자가 컨테이너에서 exploit 코드를 읽을 수 없음
- 이미지 레이어에 환경변수 유출 없음
- 공격 표면 축소

---

## 📚 문서 파일

### 11. README.md (30줄)
**목적**: CTF 참가자용 문제 설명

**내용**:
- 문제 시나리오 (레거시 마이크로서비스)
- 접속 정보 (대상 URL)
- 힌트 (4개의 미묘한 단서)
- 플래그 형식
- 난이도 평가 (5점 만점에 4점)

**의도적 모호함**:
- 정확한 취약점 드러내지 않음
- 탐색과 열거 장려
- 충분한 안내만 제공

---

### 12. TESTING.md (367줄)
**목적**: 운영자를 위한 포괄적인 테스트 체크리스트

**섹션들**:
1. 배포 전 설정
2. 빌드 및 헬스 체크
3. 수동 취약점 테스트 (6단계 모두)
4. 자동화 exploit 검증
5. 보안 검증 (우회 경로 없음)
6. 성능 테스트
7. 트러블슈팅 가이드
8. 성공 기준

**대상 청중**: CTF 주최자, 참가자 아님

---

## 🎯 솔루션 파일 (solution/)

### 13. solution/requirements.txt (3줄)
**목적**: Exploit 스크립트용 의존성

```
requests==2.31.0        # HTTP 라이브러리
itsdangerous==2.1.2     # Flask 세션 조작
colorama==0.4.6         # 크로스 플랫폼 색상 출력
```

---

### 14. solution/exploit.py (3.2KB)
**목적**: 완전 자동화 exploit

**구조**:
- **Lines 1-60**: 임포트 및 설정
- **Lines 62-96**: Flask 세션 유틸리티
  - `FlaskSessionManager` 클래스가 Flask 세션 처리 복제
- **Lines 98-120**: Stage 1 - 서비스 탐색
- **Lines 122-167**: Stage 2-3 - 정보 수집 및 secret 유도
- **Lines 169-202**: Stage 4 - Secret 검증
- **Lines 204-221**: Stage 5 - Admin 세션 위조
- **Lines 223-290**: Stage 6 - RCE 체인
  - Admin 접근 테스트
  - NoSQL injection 수행
  - Command injection 실행
  - 출력에서 FLAG 추출
- **Lines 292-341**: 에러 처리가 있는 메인 루틴

**기능**:
- 가독성을 위한 색상 출력
- 상세한 진행 로깅
- 일반 및 blind RCE 모드 모두 처리
- 크로스 플랫폼 호환

---

### 15. solution/exploit_blind.py (1.8KB)
**목적**: Blind RCE 공격 기법 시연

**기법들**:
1. **DNS Exfiltration**: DNS 쿼리에 FLAG 인코딩
2. **시간 기반 추출**: sleep 지연을 사용한 문자별 추출
3. **HTTP Callback**: 공격자 서버로 FLAG 전송
4. **파일 쓰기**: 접근 가능한 위치에 FLAG 쓰기 시도

**사용 사례**: `BLIND_RCE=true` 설정 시

---

### 16. solution/WRITEUP.md (2.7KB)
**목적**: 주최자를 위한 내부 솔루션 가이드

**내용**:
- 6단계 모두의 상세 워크스루
- 수동 공격을 위한 Curl 명령어
- Python 코드 스니펫
- 주요 학습 포인트
- 방어 권장사항
- 난이도 노트
- 보너스: 시간 기반 blind NoSQL injection

**대상**: CTF 주최자, 솔루션 검토자

---

## 🔑 주요 파일 관계

```
.env.example ──> .env (운영자가 생성)
                   │
                   ├──> docker-compose.yml (변수 읽기)
                   │         │
                   │         └──> web 서비스 (환경변수 수신)
                   │                  │
                   │                  └──> app.py (COMPANY_SALT 검증)
                   │
                   └──> Dockerfile (컨테이너 빌드)
                            │
                            └──> docker-entrypoint.sh (init_db.py 실행)
                                        │
                                        └──> init_db.py (MongoDB 검증)
                                                  │
                                                  └──> app.py (애플리케이션 시작)
```

**Exploit 흐름**:
```
exploit.py ──> Stage 1: /api/v2/services
           ──> Stage 2-3: /api/legacy/get_salt, /api/legacy/system_info
           ──> Stage 4: /api/auth/guest (secret 검증)
           ──> Stage 5: Admin 쿠키 위조
           ──> Stage 6: /api/admin/db/migrate (NoSQL + Command Injection)
```

---

## 🔒 보안 크리티컬 파일

| 파일 | 보안 역할 | 보호 대상 |
|------|-----------|----------|
| `.dockerignore` | 정보 유출 방지 | solution/, .env를 이미지에서 제외 |
| `.gitignore` | 비밀 보호 | .env를 커밋에서 방지 |
| `app.py:33-37` | 설정 강제 | COMPANY_SALT 설정 필요 |
| `init_db.py:39-77` | 설정 검증 | NoSQL injection 작동 보장 |
| `docker-compose.yml:19` | 설정 강제 | `:?` 구문으로 COMPANY_SALT 필요 |
| `Dockerfile:42` | 최소 권한 | 비root 사용자로 실행 |

---

## 📊 파일 크기 요약

```
총 프로젝트 크기: ~25KB (Docker 이미지 제외)

핵심 애플리케이션:     ~15KB (app.py, init_db.py, requirements.txt)
Docker 설정:        ~3.5KB (Dockerfile, compose, entrypoint)
문서:              ~400KB (README, TESTING, 이 파일)
솔루션:             ~8KB (exploits, writeup, requirements)
설정 파일:          ~1.5KB (다양한 dotfiles)
```

**Docker 이미지 크기**: ~180MB (Python 3.9-slim 베이스 + 의존성)

---

## 🎓 파일별 교육 가치

| 파일 | 교육 내용 | 레벨 |
|------|---------|------|
| `app.py` | Flask 보안, 세션 관리, injection | 고급 |
| `init_db.py` | MongoDB 작업, 에러 처리 | 중급 |
| `docker-compose.yml` | 컨테이너 오케스트레이션, 환경변수 | 중급 |
| `Dockerfile` | 이미지 빌드, 보안 관행 | 중급 |
| `exploit.py` | Python exploitation, HTTP 요청 | 고급 |
| `.dockerignore` | 은폐를 통한 보안 방지 | 초급 |
| `TESTING.md` | 체계적 테스트 방법론 | 모든 레벨 |

---

## 🚀 빠른 참조

**배포 전 필독**:
1. `.env.example` - COMPANY_SALT 설정
2. `TESTING.md` - 검증 절차
3. `docker-compose.yml` - 서비스 설정

**이해를 위한 필독**:
1. `app.py` - 모든 취약점
2. `solution/exploit.py` - 솔루션 접근법
3. 이 파일 - 전체 아키텍처

**보호해야 할 것**:
1. `.env` - 비밀 포함 (git ignored)
2. `solution/` - Docker에서 제외
3. `COMPANY_SALT` 값 - 절대 예측 가능한 값 사용하지 말 것

---

**마지막 업데이트**: 2025-01-XX
**버전**: 3.0 (프로덕션 준비 완료)
