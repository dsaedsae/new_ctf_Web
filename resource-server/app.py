#!/usr/bin/env python3

import os
import json
import jwt
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

def verify_token(token):
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=['HS256'],
            options={'verify_aud': False}
        )
        
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

    # Valid access token processing
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
            'message': 'ADMIN_SECRETS scope required',
            'current_scope': scope,
            'required_scope': 'ADMIN_SECRETS'
        }), 403

    if user_id != 'user_admin_001':
        return jsonify({
            'error': 'forbidden',
            'message': 'Admin user account required',
            'user_id': user_id
        }), 403

    # Success! Return administrative data
    return jsonify({
        'success': True,
        'message': 'Administrative access granted',
        'flag': ADMIN_FLAG,
        'user_id': payload.get('sub'),
        'admin_data': {
            'database_key': 'database_master_key_2024',
            'api_token': 'admin_api_override_token',
            'research_notes': 'prototype_pollution_research_notes'
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
                    <strong>🔒 Authentication Required:</strong> All endpoints require valid Bearer tokens
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