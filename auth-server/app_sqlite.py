#!/usr/bin/env python3

import os
import json
import time
import uuid
import hashlib
import requests
import sqlite3
import ipaddress
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urlencode
from collections import defaultdict

import jwt
from flask import Flask, request, jsonify, render_template_string, redirect, session, make_response, Response
from flask_cors import CORS

app = Flask(__name__)
app.secret_key = 'oauth_ctf_advanced_2025_secret'
CORS(app)

token_requests = defaultdict(list)
login_attempts = defaultdict(list)

import secrets
JWT_SECRET = os.getenv('JWT_SECRET', secrets.token_urlsafe(64))
BASE_URL = os.getenv('BASE_URL', 'http://localhost:8080')

def init_database():
    conn = sqlite3.connect('/app/data/oauth_ctf.db')
    cursor = conn.cursor()

    admin_password = "Wh3r3_is_SSRF?!"

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password VARCHAR(100) NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            role VARCHAR(20) DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_codes (
            code VARCHAR(50) PRIMARY KEY,
            client_id VARCHAR(50) NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            redirect_uri TEXT NOT NULL,
            scope TEXT NOT NULL,
            code_challenge TEXT,
            code_challenge_method VARCHAR(10),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            token VARCHAR(100) PRIMARY KEY,
            client_id VARCHAR(50) NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            scope TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_clients (
            client_id VARCHAR(50) PRIMARY KEY,
            session_id VARCHAR(50) NOT NULL,
            client_secret VARCHAR(100) NOT NULL,
            client_name TEXT NOT NULL,
            logo_uri TEXT,
            redirect_uris TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_oauth_clients_session
        ON oauth_clients(session_id)
    ''')
    
    users_data = [
        ('alice', 'wonderland123', 'user_alice_001', 'user'),
        ('bob', 'builder456', 'user_bob_002', 'user'),
        ('demo', 'demo', 'user_demo_999', 'user'),
        ('ctf_user', 'password123', 'user_ctf_001', 'user'),
        ('test_user', 'testpass', 'user_test_001', 'user')
    ]

    cursor.executemany('''
        INSERT OR IGNORE INTO users (username, password, user_id, role)
        VALUES (?, ?, ?, ?)
    ''', users_data)

    cursor.execute('''
        INSERT OR REPLACE INTO users (username, password, user_id, role)
        VALUES (?, ?, ?, ?)
    ''', ('MSG_CTF_HACKER', admin_password, 'user_admin_001', 'admin'))

    conn.commit()
    conn.close()

# Initialize database
init_database()

def is_ssrf_blocked(url):
    """
    강화된 SSRF 필터 - 대부분의 우회 기법 차단
    하지만 IPv6 full notation은 놓침 (의도된 취약점)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return True

        hostname_lower = hostname.lower()

        # 1. localhost 변형들 차단
        localhost_variants = [
            'localhost', 'localhost.localdomain',
            '127.0.0.1', '127.1', '127.0.1', '0.0.0.0',
            '0', '0x7f000001', '0177.0.0.1', '2130706433',
            '[::1]', '[::ffff:127.0.0.1]',  # IPv6 축약형만 차단!
        ]

        if hostname_lower in localhost_variants:
            return True

        # 2. 내부망 IP 대역 차단 (IPv4)
        private_ranges = [
            '192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.',
            '172.20.', '172.21.', '172.22.', '172.23.', '172.24.', '172.25.',
            '172.26.', '172.27.', '172.28.', '172.29.', '172.30.', '172.31.',
            '169.254.',  # link-local
        ]

        for prefix in private_ranges:
            if hostname_lower.startswith(prefix):
                return True

        # 3. 127.x.x.x 대역 전체 차단
        if hostname_lower.startswith('127.'):
            return True

        # 4. IP 주소 파싱 및 검증
        try:
            # 대괄호 제거 (IPv6용)
            clean_hostname = hostname.strip('[]')
            ip = ipaddress.ip_address(clean_hostname)

            # IPv4 체크
            if isinstance(ip, ipaddress.IPv4Address):
                if ip.is_private or ip.is_loopback or ip.is_reserved:
                    return True

            # IPv6 체크 (여기가 핵심 취약점!)
            # 축약형 ::1은 위에서 문자열로 차단했지만
            # 전체 표기 0:0:0:0:0:0:0:1은 정규화 후 체크를 놓침!
            elif isinstance(ip, ipaddress.IPv6Address):
                # 축약형만 차단하고 full notation은 놓침
                if '::1' in hostname_lower or '::ffff:127' in hostname_lower:
                    return True
                # 🔥 여기가 버그! ip.is_loopback 체크를 안함!

        except ValueError:
            # IP가 아닌 도메인일 수 있음
            pass

        # 5. auth-server, resource-server 등 내부 호스트명 차단
        internal_hosts = ['auth-server', 'resource-server', 'client', 'nginx']
        if hostname_lower in internal_hosts:
            return True

        return False

    except Exception as e:
        # 파싱 실패 시 안전하게 차단
        return True

def get_db_connection():
    conn = sqlite3.connect('/app/data/oauth_ctf.db')
    conn.row_factory = sqlite3.Row
    return conn

OAUTH_CONFIG = {
    'authorization_endpoint': '/oauth/authorize',
    'token_endpoint': '/oauth/token',
    'registration_endpoint': '/oauth/register',
    'supported_scopes': ['read', 'write', 'ADMIN_SECRETS'],
    'supported_response_types': ['code'],
    'supported_grant_types': ['authorization_code', 'refresh_token'],
    'code_challenge_methods_supported': ['plain', 'S256']
}

PREREGISTERED_CLIENTS = {
    "msg_developer_portal": {
        "client_name": "MSG.COM Developer Portal",
        "client_secret": "dev_portal_secret_2024",
        "redirect_uris": [
            "http://localhost:8080/auth/callback",
            f"{BASE_URL}/auth/callback"  # ngrok URL from .env
        ],
        "logo_uri": "https://example.com/logo.png",
        "description": "Official MSG.COM Developer Portal for OAuth testing and development."
    }
}


def check_login_rate_limit(ip_address):
    now = time.time()
    window = 300  # 5 minutes
    max_attempts = 10  # 10 attempts per 5 minutes

    # Clean old attempts
    login_attempts[ip_address] = [t for t in login_attempts[ip_address] if now - t < window]

    # Check limit
    if len(login_attempts[ip_address]) >= max_attempts:
        return False

    # Record this attempt
    login_attempts[ip_address].append(now)
    return True

def is_trusted_client(client_id):
    if not client_id:
        return False

    if client_id in PREREGISTERED_CLIENTS:
        return True

    return False

def validate_user_simple(username, password, client_ip='unknown'):
    if not check_login_rate_limit(client_ip):
        return None

    if not username or not password:
        return None

    if username == 'MSG_CTF_HACKER' and password == 'Wh3r3_is_SSRF?!':
        user_data = {
            'user_id': 'user_admin_001',
            'role': 'admin'
        }
        return user_data

    return None

@app.route('/oauth/register', methods=['GET', 'POST'])
def oauth_register():
    if request.method == 'GET':
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Register OAuth Client - MSG.COM</title>
    <meta charset="utf-8" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 1rem;
            padding: 3rem;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            color: #333;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            color: #666;
            margin-bottom: 2rem;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        label {
            display: block;
            font-weight: 600;
            color: #333;
            margin-bottom: 0.5rem;
        }
        input, textarea {
            width: 100%;
            padding: 0.75rem;
            border: 1px solid #ddd;
            border-radius: 0.5rem;
            font-family: 'Inter', sans-serif;
            font-size: 1rem;
        }
        textarea {
            min-height: 100px;
            resize: vertical;
        }
        .hint {
            color: #666;
            font-size: 0.875rem;
            margin-top: 0.25rem;
        }
        .required {
            color: #e74c3c;
        }
        .btn {
            display: inline-block;
            padding: 0.75rem 2rem;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            text-decoration: none;
        }
        .btn:hover {
            background: #5568d3;
        }
        .btn-secondary {
            background: #6c757d;
            margin-left: 1rem;
        }
        .btn-secondary:hover {
            background: #5a6268;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛠️ Register OAuth Client</h1>
        <p class="subtitle">Register your application to use MSG.COM OAuth</p>

        <form method="POST">
            <div class="form-group">
                <label>Client Name <span class="required">*</span></label>
                <input type="text" name="client_name" required placeholder="My Application">
                <div class="hint">A human-readable name for your application</div>
            </div>

            <div class="form-group">
                <label>Redirect URIs <span class="required">*</span></label>
                <textarea name="redirect_uris" required placeholder="http://localhost:8080/auth/callback"></textarea>
                <div class="hint">One URI per line. These are the allowed callback URLs for OAuth.</div>
            </div>

            <div class="form-group">
                <label>Logo URI</label>
                <input type="text" name="logo_uri" placeholder="https://example.com/logo.png">
                <div class="hint">URL to your application logo (optional)</div>
            </div>

            <div class="form-group">
                <label>Description</label>
                <textarea name="description" placeholder="Describe your application..."></textarea>
                <div class="hint">A brief description of your application (optional)</div>
            </div>

            <button type="submit" class="btn">Register Client</button>
            <a href="/" class="btn btn-secondary">Cancel</a>
        </form>
    </div>
</body>
</html>
        ''')

    data = request.get_json() or request.form.to_dict()

    client_name = data.get('client_name')
    logo_uri = data.get('logo_uri', 'https://example.com/logo.png')

    # Handle redirect_uris from both JSON (list) and form (string)
    redirect_uris = data.get('redirect_uris', [])
    if isinstance(redirect_uris, str):
        redirect_uris = [uri.strip() for uri in redirect_uris.split('\n') if uri.strip()]

    description = data.get('description', '')

    if not client_name:
        return jsonify({'error': 'client_name required'}), 400

    logo_fetch_result = None
    if logo_uri:
        if not logo_uri.startswith(('http://', 'https://')):
            return jsonify({
                'error': 'invalid_logo_uri',
                'message': 'Only http:// and https:// protocols are allowed',
                'provided': logo_uri
            }), 400

        # SSRF 필터 적용
        if is_ssrf_blocked(logo_uri):
            return jsonify({
                'error': 'ssrf_blocked',
                'message': 'Access to localhost and private networks is blocked for security reasons',
                'hint': 'Make sure your logo URL points to a public server',
                'provided': logo_uri
            }), 403

        try:
            # IPv6 loopback을 IPv4로 변환 (Docker 환경에서 IPv6가 제대로 동작하지 않을 수 있음)
            actual_uri = logo_uri
            parsed = urlparse(logo_uri)
            if parsed.hostname:
                try:
                    # IPv6 주소 파싱
                    clean_hostname = parsed.hostname.strip('[]')
                    ip = ipaddress.ip_address(clean_hostname)

                    # IPv6 loopback이면 127.0.0.1로 변환
                    if isinstance(ip, ipaddress.IPv6Address) and ip.is_loopback:
                        actual_uri = logo_uri.replace(f'[{clean_hostname}]', '127.0.0.1')
                except:
                    pass

            # 리다이렉트 차단
            logo_response = requests.get(actual_uri, timeout=5, allow_redirects=False)
            logo_fetch_result = {
                'status': logo_response.status_code,
                'content': logo_response.text[:1000]
            }

        except Exception as e:
            logo_fetch_result = {'error': str(e)}

    # Session-based isolation for multi-user CTF environment
    if 'ctf_session_id' not in session:
        session['ctf_session_id'] = f"sess_{uuid.uuid4().hex[:16]}"

    session_id = session['ctf_session_id']

    # Generate client credentials
    client_id = f"client_{uuid.uuid4().hex[:16]}"
    client_secret = f"secret_{uuid.uuid4().hex[:24]}"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO oauth_clients (client_id, session_id, client_secret, client_name, logo_uri, redirect_uris, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, session_id, client_secret, client_name, logo_uri, json.dumps(redirect_uris), description, datetime.now().isoformat()))

        conn.commit()

    except sqlite3.Error as e:
        print(f"[ERROR] Failed to store client: {e}")
        return jsonify({'error': 'Failed to register client'}), 500
    finally:
        conn.close()

    response_data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'client_name': client_name,
        'logo_uri': logo_uri,
        'logo_fetch_result': logo_fetch_result,
        'redirect_uris': redirect_uris,
        'description': description,
        'session_id': session_id,
        'message': 'Client registered successfully'
    }

    return jsonify(response_data)


@app.route('/internal/admin/dev-config.json')
def internal_dev_config():
    config_data = {
        "environment": "development",
        "debug_mode": True,
        "last_updated": "2024-10-15",
        "admin_accounts": [
            {
                "username": "MSG_CTF_HACKER",
                "password": "Wh3r3_is_SSRF?!",
                "role": "admin",
                "user_id": "user_admin_001"
            }
        ],
        "trusted_clients": [
            {
                "client_id": "msg_developer_portal",
                "client_secret": "dev_portal_secret_2024",
                "redirect_uris": [f"{BASE_URL}/auth/callback"]
            }
        ]
    }
    return jsonify(config_data), 200, {'Content-Type': 'application/json'}


@app.route('/oauth/client/<client_id>')
def get_client_info(client_id):
    # Check pre-registered clients first
    if client_id in PREREGISTERED_CLIENTS:
        client_data = PREREGISTERED_CLIENTS[client_id].copy()
        client_data['created_at'] = '2024-01-01T00:00:00Z'
        return jsonify(client_data)

    # Check database for registered clients (no session filter)
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT * FROM oauth_clients
            WHERE client_id = ?
        ''', (client_id,))

        result = cursor.fetchone()

        if result:
            client_data = {
                'client_id': result['client_id'],
                'client_secret': result['client_secret'],
                'client_name': result['client_name'],
                'logo_uri': result['logo_uri'],
                'redirect_uris': json.loads(result['redirect_uris']),
                'description': result['description'],
                'created_at': result['created_at']
            }
            return jsonify(client_data)
        else:
            return jsonify({'error': 'Client not found'}), 404

    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()


@app.route('/oauth/authorize')
def oauth_authorize():
    # Extract parameters
    client_id = request.args.get('client_id')
    redirect_uri = request.args.get('redirect_uri')
    response_type = request.args.get('response_type', 'code')
    scope = request.args.get('scope', 'read')
    state = request.args.get('state')
    code_challenge = request.args.get('code_challenge')
    code_challenge_method = request.args.get('code_challenge_method', 'plain')

    if not client_id or not redirect_uri:
        return jsonify({'error': 'invalid_request'}), 400

    # Validate client (check pre-registered first)
    if client_id in PREREGISTERED_CLIENTS:
        client_data = PREREGISTERED_CLIENTS[client_id]
        registered_uris = client_data['redirect_uris']
    else:
        # Check database for registered clients
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT * FROM oauth_clients WHERE client_id = ?', (client_id,))
            result = cursor.fetchone()

            if result:
                return jsonify({
                    'error': 'unauthorized_client',
                    'message': '사전 등록된 클라이언트 id사용'
                }), 403
            else:
                return jsonify({
                    'error': 'invalid_client',
                    'message': '사전 등록된 클라이언트 id사용'
                }), 400

        except sqlite3.Error as e:
            print(f"[ERROR] Database error: {e}")
            return jsonify({'error': 'Database error'}), 500
        finally:
            conn.close()

    if redirect_uri not in registered_uris:
        return jsonify({'error': 'invalid_redirect_uri'}), 400

    # Check if user is already authenticated
    if 'user_id' not in session:
        # Show login/consent page with improved UX
        return render_template_string('''
        <!DOCTYPE html>
        <html>
        <head>
            <title>MSG.COM OAuth - Authorization</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
            <style>
                :root {
                    --bg-primary: #ffffff;
                    --bg-secondary: #f9fafb;
                    --border-color: #e5e7eb;
                    --text-primary: #111827;
                    --text-secondary: #4b5563;
                    --accent-primary: #3b82f6;
                    --accent-hover: #2563eb;
                    --error-bg: #fee2e2;
                    --error-border: #ef4444;
                    --error-text: #991b1b;
                    --info-bg: #eff6ff;
                    --info-border: #3b82f6;
                    --info-text: #1e40af;
                    --warning-bg: #fef3c7;
                    --warning-border: #f59e0b;
                    --warning-text: #92400e;
                    --success-bg: #d1fae5;
                    --success-border: #10b981;
                    --success-text: #065f46;
                }
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: 'Inter', sans-serif;
                    background-color: var(--bg-secondary);
                    color: var(--text-secondary);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .container {
                    max-width: 600px;
                    width: 100%;
                    margin: 2rem auto;
                    padding: 0 2rem;
                }
                .content {
                    background-color: var(--bg-primary);
                    border-radius: 0.75rem;
                    border: 1px solid var(--border-color);
                    padding: 2.5rem;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                }
                h2 {
                    color: var(--text-primary);
                    font-size: 1.5rem;
                    margin-bottom: 1.5rem;
                    font-weight: 700;
                }
                .app-info {
                    background: var(--info-bg);
                    border-left: 4px solid var(--info-border);
                    padding: 1.5rem;
                    border-radius: 0.5rem;
                    margin: 1.5rem 0;
                }
                .app-info h3 {
                    color: var(--text-primary);
                    margin-bottom: 0.5rem;
                    font-size: 1.1rem;
                }
                .scope-list {
                    list-style: none;
                    margin: 0.5rem 0;
                }
                .scope-list li {
                    padding: 0.25rem 0;
                    color: var(--text-secondary);
                }
                .scope-list li:before {
                    content: "✓ ";
                    color: var(--success-border);
                    font-weight: bold;
                }
                .user-convenience {
                    background: var(--success-bg);
                    border-left: 4px solid var(--success-border);
                    padding: 1rem;
                    border-radius: 0.5rem;
                    margin: 1.5rem 0;
                    color: var(--success-text);
                }
                .user-convenience h4 {
                    color: var(--success-text);
                    margin-bottom: 0.5rem;
                    font-size: 0.9rem;
                }
                .user-convenience p {
                    font-size: 0.85rem;
                    margin-bottom: 0.75rem;
                    line-height: 1.5;
                }
                .btn {
                    display: inline-block;
                    padding: 0.625rem 1.25rem;
                    border-radius: 0.5rem;
                    text-decoration: none;
                    font-weight: 600;
                    transition: all 0.2s ease-in-out;
                    border: 1px solid transparent;
                    cursor: pointer;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.9rem;
                }
                .btn-primary {
                    background-color: var(--accent-primary);
                    color: white;
                }
                .btn-primary:hover {
                    background-color: var(--accent-hover);
                }
                .btn-secondary {
                    background-color: var(--text-secondary);
                    color: white;
                    margin-right: 0.5rem;
                }
                .btn-secondary:hover {
                    background-color: var(--text-primary);
                }
                .btn-deny {
                    background-color: var(--error-border);
                    color: white;
                }
                .btn-deny:hover {
                    background-color: #dc2626;
                }
                .warning {
                    background: var(--warning-bg);
                    border-left: 4px solid var(--warning-border);
                    color: var(--warning-text);
                    padding: 1rem;
                    border-radius: 0.5rem;
                    margin: 1rem 0;
                    font-size: 0.9rem;
                }
                label {
                    display: block;
                    margin-bottom: 0.5rem;
                    font-weight: 600;
                    color: var(--text-primary);
                    font-size: 0.9rem;
                }
                input[type="text"], input[type="password"] {
                    width: 100%;
                    padding: 0.625rem;
                    border: 1px solid var(--border-color);
                    border-radius: 0.5rem;
                    margin-bottom: 1rem;
                    font-family: 'Inter', sans-serif;
                    font-size: 0.9rem;
                    transition: border-color 0.2s;
                }
                input[type="text"]:focus, input[type="password"]:focus {
                    outline: none;
                    border-color: var(--accent-primary);
                    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
                }
                p {
                    color: var(--text-secondary);
                    line-height: 1.6;
                    margin: 1rem 0;
                }
                strong { color: var(--text-primary); }
                .auth-options {
                    margin-top: 2rem;
                    display: flex;
                    gap: 0.5rem;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="content">
                    <h2>🔐 OAuth Authorization</h2>

                    <div class="app-info">
                        <h3>{{ client_data.client_name }}</h3>
                        <p>이 애플리케이션이 다음 권한을 요청합니다:</p>
                        <ul class="scope-list">
                            {% for scope_item in scope.split() %}
                            <li>{{ scope_item }}</li>
                            {% endfor %}
                        </ul>
                        <p><strong>리다이렉트 URI:</strong> {{ redirect_uri }}</p>
                    </div>

                    <p>이 애플리케이션에 계정 접근을 허용하려면 로그인하세요.</p>

                    <form method="POST" action="/oauth/authorize">
                        <input type="hidden" name="client_id" value="{{ client_id }}">
                        <input type="hidden" name="redirect_uri" value="{{ redirect_uri }}">
                        <input type="hidden" name="response_type" value="{{ response_type }}">
                        <input type="hidden" name="scope" value="{{ scope }}">
                        <input type="hidden" name="state" value="{{ state }}">
                        <input type="hidden" name="code_challenge" value="{{ code_challenge }}">
                        <input type="hidden" name="code_challenge_method" value="{{ code_challenge_method }}">

                        <div style="margin: 1.5rem 0;">
                            <label for="username">사용자명:</label>
                            <input type="text" id="username" name="username" required placeholder="사용자명을 입력하세요">

                            <label for="password">비밀번호:</label>
                            <input type="password" id="password" name="password" required placeholder="비밀번호를 입력하세요">
                        </div>

                        <div class="auth-options">
                            <button type="submit" name="action" value="login" class="btn btn-primary">
                                로그인 및 승인
                            </button>
                            <button type="submit" name="action" value="deny" class="btn btn-deny">
                                거부
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </body>
        </html>

        ''', 
        client_data=client_data, client_id=client_id, redirect_uri=redirect_uri, 
        response_type=response_type, scope=scope, state=state, 
        code_challenge=code_challenge, code_challenge_method=code_challenge_method)

    # User is authenticated, generate authorization code
    auth_code = f"code_{uuid.uuid4().hex[:20]}"
    user_id = session['user_id']
    
    grant_data = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': scope,
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': code_challenge_method,
        'user_id': user_id,
        'created_at': datetime.now().isoformat()
    }

    # Store authorization code in database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        expires_at = datetime.now() + timedelta(minutes=10)
        cursor.execute('''
            INSERT INTO oauth_codes (code, client_id, user_id, redirect_uri, scope, code_challenge, code_challenge_method, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (auth_code, client_id, user_id, redirect_uri, scope, code_challenge, code_challenge_method, expires_at))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to store auth code: {e}")
        return jsonify({'error': 'Failed to generate authorization code'}), 500
    finally:
        conn.close()

    # Redirect back to client with authorization code
    redirect_params = {
        'code': auth_code,
        'state': state
    }

    redirect_url = f"{redirect_uri}?{urlencode(redirect_params)}"
    return redirect(redirect_url)

@app.route('/oauth/authorize', methods=['POST'])
def oauth_authorize_post():
    action = request.form.get('action')

    if action == 'deny':
        return jsonify({'error': 'access_denied'}), 400

    if action == 'login':
        # Get username and password from form
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        client_id = request.form.get('client_id')  # Get client_id for trust check


        # Validate credentials
        if username and password:
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            if ',' in client_ip:
                client_ip = client_ip.split(',')[0].strip()
            user_data = validate_user_simple(username, password, client_ip)
            
            if user_data:
                # Set session with consistent user_id
                session['user_id'] = user_data['user_id']
                session['username'] = username
                session['role'] = user_data['role']

                # Redirect back to GET with same parameters
                params = request.form.to_dict()
                params.pop('action', None)  # Remove action parameter
                params.pop('username', None)  # Remove username
                params.pop('password', None)  # Remove password

                redirect_url = f"/oauth/authorize?{urlencode(params)}"
                return redirect(redirect_url)
            else:
                # Invalid credentials
                return render_template_string('''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>MSG.COM OAuth - Login Error</title>
                    <link rel="preconnect" href="https://fonts.googleapis.com">
                    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
                    <style>
                        :root {
                            --bg-primary: #ffffff;
                            --bg-secondary: #f9fafb; /* gray-50 */
                            --border-color: #e5e7eb; /* gray-200 */
                            --text-primary: #111827; /* gray-900 */
                            --text-secondary: #4b5563; /* gray-600 */
                            --accent-primary: #3b82f6; /* blue-500 */
                            --accent-hover: #2563eb; /* blue-600 */
                            --error-bg: #fee2e2; /* red-100 */
                            --error-border: #ef4444; /* red-500 */
                            --error-text: #991b1b; /* red-800 */
                            --info-bg: #eff6ff; /* blue-100 */
                            --info-border: #3b82f6; /* blue-500 */
                            --info-text: #1e40af; /* blue-800 */
                            --warning-bg: #fef3c7; /* yellow-100 */
                            --warning-border: #f59e0b; /* yellow-500 */
                            --warning-text: #92400e; /* yellow-800 */
                        }
                        * { margin: 0; padding: 0; box-sizing: border-box; }
                        body {
                            font-family: 'Inter', sans-serif;
                            background-color: var(--bg-secondary);
                            color: var(--text-secondary);
                            min-height: 100vh;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                        }
                        .container {
                            max-width: 600px;
                            width: 100%;
                            margin: 2rem auto;
                            padding: 0 2rem;
                        }
                        .content {
                            background-color: var(--bg-primary);
                            border-radius: 0.75rem;
                            border: 1px solid var(--border-color);
                            padding: 2.5rem;
                            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                        }
                        h2 {
                            color: var(--text-primary);
                            font-size: 1.5rem;
                            margin-bottom: 1.5rem;
                            font-weight: 700;
                        }
                        .error {
                            background: var(--error-bg);
                            border-left: 4px solid var(--error-border);
                            color: var(--error-text);
                            padding: 1rem;
                            border-radius: 0.5rem;
                            margin: 1rem 0;
                            font-size: 0.9rem;
                        }
                        .btn {
                            display: inline-block;
                            padding: 0.625rem 1.25rem;
                            border-radius: 0.5rem;
                            text-decoration: none;
                            font-weight: 600;
                            transition: all 0.2s ease-in-out;
                            border: 1px solid transparent;
                            cursor: pointer;
                            font-family: 'Inter', sans-serif;
                            background-color: var(--accent-primary);
                            color: white;
                        }
                        .btn:hover {
                            background-color: var(--accent-hover);
                        }
                        .hint {
                            background: var(--info-bg);
                            border-left: 4px solid var(--info-border);
                            color: var(--info-text);
                            padding: 1rem;
                            border-radius: 0.5rem;
                            margin: 1rem 0;
                            font-size: 0.9rem;
                            line-height: 1.6;
                        }
                        strong { color: var(--text-primary); }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="content">
                            <h2>Login Error</h2>
                            <div class="error">
                                <strong>Login Failed</strong><br>
                                Invalid username or password.
                            </div>
                            <div class="hint">
                                <strong>Note:</strong> Rate limit: 10 attempts per 5 minutes
                            </div>
                            <a href="javascript:history.back()" class="btn">Go Back</a>
                        </div>
                    </div>
                </body>
                </html>
                ''')
        else:
            # Empty username/password
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>MSG.COM OAuth - Login Error</title>
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
                <style>
                    :root {
                        --bg-primary: #ffffff;
                        --bg-secondary: #f9fafb; /* gray-50 */
                        --border-color: #e5e7eb; /* gray-200 */
                        --text-primary: #111827; /* gray-900 */
                        --text-secondary: #4b5563; /* gray-600 */
                        --accent-primary: #3b82f6; /* blue-500 */
                        --accent-hover: #2563eb; /* blue-600 */
                        --error-bg: #fee2e2; /* red-100 */
                        --error-border: #ef4444; /* red-500 */
                        --error-text: #991b1b; /* red-800 */
                    }
                    * { margin: 0; padding: 0; box-sizing: border-box; }
                    body {
                        font-family: 'Inter', sans-serif;
                        background-color: var(--bg-secondary);
                        color: var(--text-secondary);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }
                    .container {
                        max-width: 500px;
                        width: 100%;
                        margin: 2rem auto;
                        padding: 0 2rem;
                    }
                    .content {
                        background-color: var(--bg-primary);
                        border-radius: 0.75rem;
                        border: 1px solid var(--border-color);
                        padding: 2.5rem;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
                    }
                    h2 {
                        color: var(--text-primary);
                        font-size: 1.5rem;
                        margin-bottom: 1.5rem;
                        font-weight: 700;
                    }
                    .error {
                        background: var(--error-bg);
                        border-left: 4px solid var(--error-border);
                        color: var(--error-text);
                        padding: 1rem;
                        border-radius: 0.5rem;
                        margin: 1rem 0;
                        font-size: 0.9rem;
                    }
                    .btn {
                        display: inline-block;
                        padding: 0.625rem 1.25rem;
                        border-radius: 0.5rem;
                        text-decoration: none;
                        font-weight: 600;
                        transition: all 0.2s ease-in-out;
                        border: 1px solid transparent;
                        cursor: pointer;
                        font-family: 'Inter', sans-serif;
                        background-color: var(--accent-primary);
                        color: white;
                    }
                    .btn:hover {
                        background-color: var(--accent-hover);
                    }
                    strong { color: var(--text-primary); }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="content">
                        <h2>Login Error</h2>
                        <div class="error">
                            <strong>Login Failed</strong><br>
                            Please enter both username and password.
                        </div>
                        <a href="javascript:history.back()" class="btn">Go Back</a>
                    </div>
                </div>
            </body>
            </html>
            ''')
    
    return jsonify({'error': 'invalid_request'}), 400


def check_token_rate_limit():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    # Take first IP if multiple
    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    now = time.time()
    window = 60  # 1 minute
    max_requests = 5  # 5 requests per minute (strict)

    # Clean old requests
    token_requests[client_ip] = [t for t in token_requests[client_ip] if now - t < window]

    # Check limit
    if len(token_requests[client_ip]) >= max_requests:
        return False, client_ip

    # Record this request
    token_requests[client_ip].append(now)
    return True, client_ip

@app.route('/oauth/token', methods=['POST'])
def oauth_token():
    # Check rate limit
    allowed, client_ip = check_token_rate_limit()
    if not allowed:
        return jsonify({
            'error': 'rate_limit_exceeded',
            'message': 'Too many token requests. Please wait before trying again.',
            'client_ip': client_ip
        }), 429

    data = request.form.to_dict() or request.get_json()

    grant_type = data.get('grant_type')

    if grant_type == 'authorization_code':
        return handle_authorization_code_grant(data)
    elif grant_type == 'refresh_token':
        return handle_refresh_token_grant(data)
    else:
        return jsonify({'error': 'unsupported_grant_type'}), 400

def handle_authorization_code_grant(data):
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    code = data.get('code')
    redirect_uri = data.get('redirect_uri')
    code_verifier = data.get('code_verifier')

    if not all([client_id, client_secret, code, redirect_uri]):
        return jsonify({'error': 'invalid_request'}), 400

    # Validate client credentials (check pre-registered first)
    if client_id in PREREGISTERED_CLIENTS:
        client_data = PREREGISTERED_CLIENTS[client_id]
        expected_secret = client_data['client_secret']
    else:
        # Check database for registered clients
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT client_secret FROM oauth_clients WHERE client_id = ?', (client_id,))
            result = cursor.fetchone()

            if result:
                return jsonify({
                    'error': 'unauthorized_client',
                    'error_description': '등록 허용이 되지 않은 client_id입니다.',
                    'message': 'This client is registered but not approved for token exchange.',
                    'status': 'client_not_approved'
                }), 403
            else:
                return jsonify({'error': 'invalid_client'}), 401

        except sqlite3.Error as e:
            print(f"[ERROR] Database error: {e}")
            return jsonify({'error': 'Database error'}), 500
        finally:
            conn.close()

    if expected_secret != client_secret:
        return jsonify({'error': 'invalid_client'}), 401

    # Validate authorization code from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT client_id, user_id, redirect_uri, scope, code_challenge, code_challenge_method, expires_at
            FROM oauth_codes WHERE code = ?
        ''', (code,))
        
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'invalid_grant'}), 400
        
        # Check expiration
        expires_at = datetime.fromisoformat(result['expires_at'])
        if datetime.now() > expires_at:
            return jsonify({'error': 'invalid_grant'}), 400
        
        # Validate client and redirect URI
        if result['client_id'] != client_id or result['redirect_uri'] != redirect_uri:
            return jsonify({'error': 'invalid_grant'}), 400
        
        # Delete used authorization code
        cursor.execute('DELETE FROM oauth_codes WHERE code = ?', (code,))
        conn.commit()
        
        grant_data = {
            'client_id': result['client_id'],
            'user_id': result['user_id'],
            'redirect_uri': result['redirect_uri'],
            'scope': result['scope'],
            'code_challenge': result['code_challenge'],
            'code_challenge_method': result['code_challenge_method']
        }
        
    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()

    code_challenge = grant_data.get('code_challenge')
    if code_challenge:
        original_method = grant_data.get('code_challenge_method', 'plain')
        request_method = data.get('code_challenge_method', original_method)

        if request_method == 'none':
            return jsonify({
                'error': 'invalid_request',
                'error_description': 'code_challenge_method "none" is not supported',
                'supported_methods': ['plain', 'S256']
            }), 400

        elif request_method == 'plain':
            if code_verifier is None:
                return jsonify({
                    'error': 'invalid_request',
                    'error_description': 'code_verifier is required when code_challenge was provided'
                }), 400

            empty_values = ['', 'null', 'undefined', '0', 'false', 'none', 'empty']
            if code_verifier in empty_values:
                return jsonify({
                    'error': 'invalid_request',
                    'error_description': f'code_verifier cannot be empty or null-like value: "{code_verifier}"'
                }), 400

            if code_verifier.strip() == '':
                return jsonify({
                    'error': 'invalid_request',
                    'error_description': 'code_verifier cannot be whitespace-only'
                }), 400

            bypass_patterns = [
                ' ', '  ', '\t', '\n', '\r', '\x00', '\x20',
                '[]', '{}', '()',
                '""', "''", '``',
                'NaN', 'Infinity', '-Infinity',
                'void(0)', 'void 0',
                'null', 'undefined', 'false', 'true',
                '0', '1', '-1',
                'a', 'b', 'c', 'x', 'y', 'z'
            ]

            if code_verifier in bypass_patterns:
                return jsonify({
                    'error': 'invalid_request',
                    'error_description': f'code_verifier blocked: "{code_verifier}"'
                }), 400

            zero_width_chars = [
                '\u200B',
                '\u200C',
                '\u200D',
                '\uFEFF',
                '\u2060',
                '\u2061',
                '\u2062',
                '\u2063',
                '\u2064',
            ]

            if not (code_verifier and all(c in zero_width_chars for c in code_verifier)):
                if len(code_verifier) > 0 and len(code_verifier) < 43:
                    return jsonify({
                        'error': 'invalid_request',
                        'error_description': f'code_verifier too short: {len(code_verifier)} characters (RFC 7636 requires 43-128)',
                        'current_length': len(code_verifier)
                    }), 400

            if len(code_verifier) == 1 and code_verifier in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789':
                return jsonify({
                    'error': 'invalid_request',
                    'error_description': f'Single character code_verifier blocked: "{code_verifier}"'
                }), 400

            if code_verifier and all(c in zero_width_chars for c in code_verifier):
                pass
            elif code_verifier != code_challenge:
                return jsonify({
                    'error': 'invalid_grant',
                    'error_description': 'PKCE validation failed: code_verifier does not match code_challenge',
                    'method': 'plain'
                }), 400
            else:
                pass

        elif request_method == 'S256':
            if not code_verifier:
                return jsonify({
                    'error': 'invalid_request',
                    'error_description': 'code_verifier is required for S256 method'
                }), 400

            import hashlib
            import base64
            verifier_hash = hashlib.sha256(code_verifier.encode()).digest()
            computed_challenge = base64.urlsafe_b64encode(verifier_hash).decode().rstrip('=')

            if computed_challenge != code_challenge:
                return jsonify({
                    'error': 'invalid_grant',
                    'error_description': 'PKCE validation failed: code_verifier hash does not match code_challenge',
                    'method': 'S256'
                }), 400

        else:
            return jsonify({
                'error': 'invalid_request',
                'error_description': f'Unsupported code_challenge_method: {request_method}',
                'supported_methods': ['plain', 'S256', 'none']
            }), 400
    else:
        pass

    # Generate tokens
    requested_scope = grant_data['scope']
    user_id = grant_data['user_id']

    allowed_scopes = ['read', 'write', 'openid']
    scope_list = requested_scope.split()
    filtered_scopes = [s for s in scope_list if s in allowed_scopes]
    scope = ' '.join(filtered_scopes) if filtered_scopes else 'read'


    access_token = generate_jwt_token(user_id, client_id, scope, 'access')
    refresh_token = f"refresh_{uuid.uuid4().hex}"

    # Store refresh token in database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        expires_at = datetime.now() + timedelta(days=30)
        cursor.execute('''
            INSERT INTO refresh_tokens (token, client_id, user_id, scope, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (refresh_token, client_id, user_id, scope, expires_at))
        
        conn.commit()
    except sqlite3.Error as e:
        print(f"[ERROR] Failed to store refresh token: {e}")
        return jsonify({'error': 'Failed to generate refresh token'}), 500
    finally:
        conn.close()

    response_data = {
        'access_token': access_token,
        'token_type': 'Bearer',
        'expires_in': 3600,
        'refresh_token': refresh_token,
        'scope': scope
    }

    return jsonify(response_data)


def handle_refresh_token_grant(data):
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    refresh_token = data.get('refresh_token')
    requested_scope = data.get('scope')

    if not all([client_id, client_secret, refresh_token]):
        return jsonify({'error': 'invalid_request'}), 400

    # Validate client (check pre-registered first)
    if client_id in PREREGISTERED_CLIENTS:
        client_data = PREREGISTERED_CLIENTS[client_id]
        expected_secret = client_data['client_secret']
    else:
        # Check database for registered clients
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT client_secret FROM oauth_clients WHERE client_id = ?', (client_id,))
            result = cursor.fetchone()

            if result:
                return jsonify({
                    'error': 'unauthorized_client',
                    'error_description': '등록 허용이 되지 않은 client_id입니다.',
                    'message': 'This client is registered but not approved for token refresh.',
                    'status': 'client_not_approved'
                }), 403
            else:
                return jsonify({'error': 'invalid_client'}), 401

        except sqlite3.Error as e:
            print(f"[ERROR] Database error: {e}")
            return jsonify({'error': 'Database error'}), 500
        finally:
            conn.close()

    if expected_secret != client_secret:
        return jsonify({'error': 'invalid_client'}), 401

    # Validate refresh token from database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT client_id, user_id, scope, expires_at
            FROM refresh_tokens WHERE token = ?
        ''', (refresh_token,))
        
        result = cursor.fetchone()
        
        if not result:
            return jsonify({'error': 'invalid_grant'}), 400
        
        # Check expiration
        expires_at = datetime.fromisoformat(result['expires_at'])
        if datetime.now() > expires_at:
            return jsonify({'error': 'invalid_grant'}), 400
        
        # Validate client
        if result['client_id'] != client_id:
            return jsonify({'error': 'invalid_grant'}), 400
        
        refresh_data = {
            'client_id': result['client_id'],
            'user_id': result['user_id'],
            'scope': result['scope']
        }
        
    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()

    # Process scope request
    original_scope = refresh_data['scope']

    if requested_scope:
        # Update scope if requested
        final_scope = requested_scope
    else:
        final_scope = original_scope

    # Generate new access token with escalated scope
    user_id = refresh_data['user_id']
    new_access_token = generate_jwt_token(user_id, client_id, final_scope, 'access')

    response_data = {
        'access_token': new_access_token,
        'token_type': 'Bearer',
        'expires_in': 3600,
        'scope': final_scope
    }

    if 'ADMIN_SECRETS' in final_scope:
        response_data['admin_access'] = True

    return jsonify(response_data)


def generate_jwt_token(user_id, client_id, scope, token_type):
    now = datetime.utcnow()

    payload = {
        'iss': 'https://auth.oauth-ctf.local',
        'sub': user_id,
        'aud': 'oauth-resource-server',
        'exp': int((now + timedelta(hours=1)).timestamp()),
        'iat': int(now.timestamp()),
        'scope': scope,
        'token_type': token_type
    }

    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


@app.route('/.well-known/oauth-authorization-server')
def oauth_discovery():
    return jsonify({
        'issuer': 'https://auth.oauth-ctf.local',
        'authorization_endpoint': 'http://localhost:8000/oauth/authorize',
        'token_endpoint': 'http://localhost:8000/oauth/token',
        'registration_endpoint': 'http://localhost:8000/oauth/register',
        'scopes_supported': OAUTH_CONFIG['supported_scopes'],
        'response_types_supported': OAUTH_CONFIG['supported_response_types'],
        'grant_types_supported': OAUTH_CONFIG['supported_grant_types'],
        'code_challenge_methods_supported': OAUTH_CONFIG['code_challenge_methods_supported'],
        'token_endpoint_auth_methods_supported': ['client_secret_post', 'client_secret_basic'],
        'service_topology': {
            'auth': 'auth-server:8000',
            'api': 'resource-server:8002'
        },
        'internal_documentation': '/internal/admin/',
        'debug_mode': 'development'
    })


@app.route('/robots.txt')
def robots():
    robots_content = """User-agent: *
Disallow: /internal/admin/

# OAuth 2.0 Authorization Server
# Internal admin endpoints are restricted
# Dynamic client registration: /oauth/register
"""
    return Response(robots_content, mimetype='text/plain')

@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>MSG.COM OAuth Platform</title>
        <!-- DEV NOTE: Test credentials stored in /internal/admin/dev-config.json -->
        <!-- TODO: Remove this endpoint before production deployment! -->
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: #f9fafb;
                min-height: 100vh;
                padding: 2rem;
                color: #111827;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
            }
            h1 {
                color: #111827;
                border-bottom: 2px solid #3b82f6;
                padding-bottom: 0.75rem;
                margin-bottom: 1.5rem;
                font-size: 2rem;
                font-weight: 700;
            }
            p {
                color: #4b5563;
                line-height: 1.7;
                margin-bottom: 1rem;
            }
            .endpoint {
                background: white;
                padding: 1.5rem;
                margin: 1rem 0;
                border-left: 4px solid #3b82f6;
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .endpoint h3 {
                margin-top: 0;
                margin-bottom: 0.75rem;
                color: #1f2937;
                font-size: 1.25rem;
                font-weight: 600;
            }
            .endpoint p {
                margin-bottom: 0.5rem;
                color: #4b5563;
            }
            .warning {
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                color: #92400e;
                padding: 1.25rem;
                border-radius: 0.5rem;
                margin: 1.5rem 0;
                line-height: 1.6;
            }
            code {
                background: #e5e7eb;
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
                font-family: 'Fira Code', monospace;
                font-size: 0.9em;
                color: #1f2937;
            }
            strong {
                color: #111827;
                font-weight: 600;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>MSG.COM OAuth Platform</h1>
            <p style="font-size: 1.1rem;">OAuth 2.0 Authorization Server</p>

            <div class="endpoint">
                <h3>Client Registration</h3>
                <p><strong>POST</strong> <code>/oauth/register</code></p>
                <p>Register OAuth clients dynamically (RFC 7591)</p>
            </div>

            <div class="endpoint">
                <h3>Authorization Endpoint</h3>
                <p><strong>GET</strong> <code>/oauth/authorize</code></p>
                <p>Start OAuth 2.0 authorization code flow</p>
            </div>

            <div class="endpoint">
                <h3>Token Endpoint</h3>
                <p><strong>POST</strong> <code>/oauth/token</code></p>
                <p>Exchange authorization code for tokens</p>
            </div>

            <div class="endpoint">
                <h3>Discovery</h3>
                <p><strong>GET</strong> <code>/.well-known/oauth-authorization-server</code></p>
                <p>OAuth 2.0 metadata endpoint</p>
            </div>
        </div>
    </body>
    </html>
    ''')

if __name__ == '__main__':
    print("[START] OAuth Authorization Server")

    app.run(host='0.0.0.0', port=8000, debug=True)
