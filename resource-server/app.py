#!/usr/bin/env python3

import os
import json
import jwt
import hmac
import hashlib
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from collections import defaultdict
from time import time

app = Flask(__name__)
CORS(app)

admin_attempts = defaultdict(list)

import secrets
JWT_SECRET = os.getenv('JWT_SECRET', secrets.token_urlsafe(64))
ADMIN_FLAG = 'MSG{0auth_2_MSG_FLAG_m4st3r}'

# jti 검증을 위한 토큰 서명 비밀키 (인증 서버와 공유)
TOKEN_SIGNING_SECRET = os.getenv('TOKEN_SIGNING_SECRET', 'default_token_signing_secret_change_in_production')

# RS256 검증용 공개키 캐시
PUBLIC_KEY_CACHE = None

def get_public_key():
    """
    인증 서버로부터 RS256 검증용 공개키를 가져옵니다.

    최초 1회만 요청하고 이후에는 캐시된 값을 재사용합니다.
    """
    global PUBLIC_KEY_CACHE

    if PUBLIC_KEY_CACHE:
        return PUBLIC_KEY_CACHE

    try:
        print("[INFO] Fetching public key from auth server...")
        response = requests.get('http://auth-server:8000/.well-known/jwks.json', timeout=3)

        if response.status_code == 200:
            jwks = response.json()
            # 간단하게 PEM 포맷 공개키를 직접 가져옴
            # 실제 운영 환경에서는 JWK를 PEM으로 변환하는 것이 좋음

            # PEM 포맷으로 직접 요청
            pem_response = requests.get('http://auth-server:8000/.well-known/public-key.pem', timeout=3)
            if pem_response.status_code == 200:
                PUBLIC_KEY_CACHE = pem_response.text
                print("[INFO] Public key cached successfully")
                return PUBLIC_KEY_CACHE

        print("[WARN] Failed to fetch public key, using fallback")
        return None

    except Exception as e:
        print(f"[ERROR] Failed to fetch public key: {e}")
        return None


def verify_token(token):
    """
    JWT 알고리즘 혼동 취약점이 있는 토큰 검증 함수

    토큰 헤더의 alg 값을 신뢰하여 검증 방식을 결정하므로,
    공격자가 RS256 토큰을 HS256으로 변조할 수 있습니다.

    공격 흐름:
    1. 정상 OAuth 플로우로 RS256 서명 토큰 획득
    2. 공개키 다운로드 (/.well-known/public-key.pem)
    3. 토큰 페이로드 복사 후 헤더를 alg=HS256으로 변경
    4. 공개키를 HMAC 비밀키로 사용하여 서명
    5. 서버가 변조된 토큰을 정상으로 인식
    """
    try:
        # 취약점: 토큰 헤더의 알고리즘을 신뢰
        header = jwt.get_unverified_header(token)
        algorithm = header.get('alg', 'RS256')

        # 보안: 위험한 알고리즘 명시적 차단
        algorithm_upper = algorithm.upper() if algorithm else ''
        if algorithm_upper in ['NONE', 'NULL', '']:
            return None, "Unsupported algorithm"

        public_key = get_public_key()

        if algorithm == 'RS256':
            # RS256: 공개키로 검증 (정상 동작)
            if not public_key:
                return None, "Public key not available for RS256 verification"

            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                options={'verify_aud': False}
            )

        elif algorithm == 'HS256':
            # 취약점: 공개키를 HMAC 비밀키로 사용
            # 알고리즘 혼동 공격의 핵심 포인트
            if not public_key:
                return None, "Public key not available for HS256 verification"

            # PyJWT는 공개키를 HMAC 키로 사용하는 것을 차단하므로 수동 검증 필요
            import hmac
            import hashlib
            import base64

            # 토큰을 헤더, 페이로드, 서명으로 분리
            parts = token.split('.')
            if len(parts) != 3:
                return None, "Invalid token format"

            header_b64, payload_b64, signature_b64 = parts

            # HMAC으로 서명 검증
            message = f"{header_b64}.{payload_b64}"
            expected_signature = hmac.new(
                public_key.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()

            # 토큰의 서명 디코딩
            # base64url 디코딩을 위한 패딩 추가
            signature_b64_padded = signature_b64 + '=' * (4 - len(signature_b64) % 4)
            actual_signature = base64.urlsafe_b64decode(signature_b64_padded)

            # 서명 비교
            if not hmac.compare_digest(expected_signature, actual_signature):
                return None, "Invalid signature"

            # 서명 검증은 이미 완료했으므로 페이로드만 디코딩
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_aud": False}
            )

            # 만료 시간 수동 검증
            import time
            exp = payload.get('exp')
            if exp and exp < time.time():
                return None, "Token has expired"

        else:
            return None, f"Unsupported algorithm: {algorithm}"

        # jti 서명 검증으로 임의 토큰 생성 방지
        jti_full = payload.get('jti', '')
        if not jti_full or '.' not in jti_full:
            return None, "Missing or invalid jti"

        # jti와 서명 분리
        jti, provided_signature = jti_full.rsplit('.', 1)

        # 예상 서명 계산
        expected_signature = hmac.new(
            TOKEN_SIGNING_SECRET.encode('utf-8'),
            jti.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()[:16]

        # 서명 검증
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None, "Token not issued by auth server"

        return payload, None

    except jwt.ExpiredSignatureError:
        return None, "Token has expired"
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {str(e)}"

@app.route('/api/userinfo')
def userinfo():
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({
            'error': 'missing_token',
            'message': 'Bearer token required'
        }), 401

    token = auth_header.split(' ')[1]
    payload, error = verify_token(token)

    if error:
        return jsonify({
            'error': 'invalid_token',
            'message': error
        }), 401

    # 유효한 액세스 토큰 처리
    token_type = payload.get('token_type', 'unknown')
    user_id = payload.get('sub')
    scope = payload.get('scope', '')

    response_data = {
        'user_id': user_id,
        'scope': scope,
        'token_type': token_type,
        'issued_at': payload.get('iat'),
        'expires_at': payload.get('exp')
    }

    if 'ADMIN_SECRETS' in scope:
        response_data['admin_access'] = True

    return jsonify(response_data)

def check_rate_limit(ip_address, max_attempts=500, window=60):
    now = time()
    admin_attempts[ip_address] = [t for t in admin_attempts[ip_address] if now - t < window]

    if len(admin_attempts[ip_address]) >= max_attempts:
        return False

    admin_attempts[ip_address].append(now)
    return True

@app.route('/api/admin/flag')
def admin_flag():
    """
    관리자 전용 엔드포인트 (알고리즘 제한 있음)

    내부 마이크로서비스와의 레거시 호환성을 위해
    HS256 알고리즘으로 서명된 토큰만 허용합니다.

    필수 조건:
    - 알고리즘: HS256
    - 스코프: ADMIN_SECRETS
    - 사용자 ID: user_admin_001
    """
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if not check_rate_limit(client_ip):
        return jsonify({
            'error': 'rate_limit_exceeded',
            'message': 'Too many attempts. Please wait before trying again.'
        }), 429

    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({
            'error': 'missing_token',
            'message': 'Admin endpoint requires Bearer token'
        }), 401

    token = auth_header.split(' ')[1]

    # 핵심: 검증 전에 알고리즘을 먼저 체크
    # 이 제약 조건이 알고리즘 혼동 공격을 유도함
    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get('alg', 'unknown')

        if algorithm != 'HS256':
            return jsonify({
                'error': 'invalid_token',
                'message': 'Token validation failed'
            }), 401

    except Exception as e:
        return jsonify({
            'error': 'invalid_token_format',
            'message': str(e)
        }), 400

    # 이제 토큰 검증 수행
    payload, error = verify_token(token)

    if error:
        return jsonify({
            'error': 'invalid_token',
            'message': error
        }), 401

    scope = payload.get('scope', '')
    user_id = payload.get('sub', '')

    scope_list = scope.split()
    if 'ADMIN_SECRETS' not in scope_list:
        return jsonify({
            'error': 'insufficient_scope',
            'message': 'ADMIN_SECRETS scope required'
        }), 403

    if user_id != 'user_admin_001':
        return jsonify({
            'error': 'forbidden',
            'message': 'Admin user account required'
        }), 403

    # 모든 검증 통과 - 관리자 데이터 반환
    return jsonify({
        'success': True,
        'message': 'Administrative access granted',
        'flag': ADMIN_FLAG,
        'user_id': payload.get('sub'),
        'algorithm_used': 'HS256',
        'admin_data': {
            'database_key': 'database_master_key_2024',
            'api_token': 'admin_api_override_token',
            'research_notes': 'jwt_algorithm_confusion_analysis'
        },
        'access_level': 'ADMIN_SECRETS',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/profile')
def profile():
    auth_header = request.headers.get('Authorization')

    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Bearer token required'}), 401

    token = auth_header.split(' ')[1]
    payload, error = verify_token(token)

    if error:
        return jsonify({'error': error}), 401

    return jsonify({
        'profile': {
            'user_id': payload.get('sub'),
            'scope': payload.get('scope'),
            'email': 'user@oauth-ctf.local',
            'name': 'CTF Participant',
            'role': 'admin' if 'ADMIN_SECRETS' in payload.get('scope', '') else 'user'
        }
    })

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>MSG.Platform API Gateway</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet" />
        <style>
            :root {
                --bg-primary: #ffffff;
                --bg-secondary: #f9fafb;
                --border-color: #e5e7eb;
                --text-primary: #111827;
                --text-secondary: #4b5563;
                --accent-primary: #3b82f6;
                --accent-hover: #2563eb;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Inter', sans-serif;
                background-color: var(--bg-secondary);
                line-height: 1.6;
                color: var(--text-secondary);
                min-height: 100vh;
            }
            .navbar {
                background-color: rgba(255, 255, 255, 0.9);
                backdrop-filter: blur(10px);
                padding: 1rem 2rem;
                border-bottom: 1px solid var(--border-color);
                position: sticky;
                top: 0;
                z-index: 50;
            }
            .navbar-content {
                max-width: 1280px;
                margin: 0 auto;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .logo {
                font-size: 1.5rem;
                font-weight: 700;
                color: var(--accent-primary);
                text-decoration: none;
            }
            .container {
                max-width: 1280px;
                margin: 2rem auto;
                padding: 0 2rem;
            }
            .content {
                background-color: var(--bg-primary);
                border-radius: 0.75rem;
                border: 1px solid var(--border-color);
                padding: 2.5rem;
            }
            h1 {
                color: var(--text-primary);
                margin-bottom: 0.5rem;
                font-weight: 700;
                font-size: 2rem;
            }
            .subtitle {
                color: var(--text-secondary);
                margin-bottom: 2rem;
                font-size: 1.1rem;
            }
            .auth-notice {
                background-color: #dbeafe;
                border-left: 4px solid var(--accent-primary);
                padding: 1rem;
                margin-bottom: 2rem;
                border-radius: 0.25rem;
                color: #1e40af;
            }
            .endpoint {
                background-color: var(--bg-primary);
                padding: 1.5rem;
                margin: 1rem 0;
                border-left: 3px solid var(--accent-primary);
                border: 1px solid var(--border-color);
                border-radius: 0.5rem;
                transition: all 0.2s;
            }
            .endpoint:hover {
                border-left-width: 4px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            }
            .protected {
                border-left-color: #10b981;
            }
            .endpoint h3 {
                margin-top: 0;
                margin-bottom: 0.5rem;
                color: var(--text-primary);
                font-weight: 600;
            }
            .endpoint p {
                margin: 0.25rem 0;
                color: var(--text-secondary);
            }
            .method {
                display: inline-block;
                font-weight: 600;
                color: var(--accent-primary);
            }
            code {
                background-color: #f3f4f6;
                padding: 0.2rem 0.5rem;
                border-radius: 0.25rem;
                font-family: 'Fira Code', monospace;
                font-size: 0.9rem;
                color: #1f2937;
            }
        </style>
    </head>
    <body>
        <div class="navbar">
            <div class="navbar-content">
                <div class="logo">MSG.Platform API</div>
            </div>
        </div>

        <div class="container">
            <div class="content">
                <h1>API Gateway</h1>
                <p class="subtitle">OAuth 2.0 Protected Resource Server</p>

                <div class="auth-notice">
                    <strong> Authentication Required:</strong> All endpoints require valid Bearer tokens
                </div>

                <div class="endpoint">
                    <h3>/api/userinfo</h3>
                    <p><span class="method">GET</span> - Returns user information and token details</p>
                    <p><strong>Requires:</strong> Access token</p>
                </div>

                <div class="endpoint">
                    <h3>/api/profile</h3>
                    <p><span class="method">GET</span> - Returns user profile data</p>
                    <p><strong>Requires:</strong> Access token</p>
                </div>

                <div class="endpoint protected">
                    <h3>/api/admin/flag</h3>
                    <p><span class="method">GET</span> - Administrative endpoint</p>
                    <p><strong>Requires:</strong> Access token with <code>ADMIN_SECRETS</code> scope</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    ''')

if __name__ == '__main__':
    print("[START] TechCorp API Gateway - Resource Server")

    app.run(host='0.0.0.0', port=8002, debug=True)