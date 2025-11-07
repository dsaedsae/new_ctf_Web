#!/usr/bin/env python3

from flask import Flask, render_template, render_template_string, request, redirect, make_response
from flask_cors import CORS
import requests
import secrets
import os

app = Flask(__name__)
CORS(app)

# Environment variables
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8080')
INTERNAL_BASE_URL = os.environ.get('INTERNAL_BASE_URL', 'http://nginx')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/auth/callback')
def auth_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Failed</title>
    <meta charset="utf-8" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f8fafc;
            min-height: 100vh;
            padding: 2rem;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 1rem;
            padding: 3rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 {
            color: #ef4444;
            margin-bottom: 1rem;
        }
        .error-box {
            background: #fee2e2;
            border: 1px solid #fecaca;
            border-radius: 0.75rem;
            padding: 2rem;
            margin-top: 1rem;
        }
        a {
            color: #3b82f6;
            text-decoration: none;
        }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Authorization Failed</h1>
        <div class="error-box">
            <p><strong>Error:</strong> {{ error }}</p>
            <p style="margin-top: 1rem;">
                <a href="/">Return to home</a>
            </p>
        </div>
    </div>
</body>
</html>
        ''', error=error)

    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Authorization Complete</title>
    <meta charset="utf-8" />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            min-height: 100vh;
            padding: 2rem;
        }
        .navbar {
            background: rgba(255, 255, 255, 0.95);
            border-bottom: 1px solid #e2e8f0;
            padding: 1rem 2rem;
            margin-bottom: 2rem;
            border-radius: 1rem;
        }
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            color: #0f172a;
        }
        .container {
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 1rem;
            padding: 3rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        h1 {
            color: #0f172a;
            margin-bottom: 1rem;
            font-size: 2.5rem;
        }
        .success {
            color: #10b981;
            font-size: 1.1rem;
            margin-bottom: 2rem;
        }
        .code-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin: 1rem 0;
            font-family: 'Fira Code', monospace;
        }
        .label {
            color: #64748b;
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }
        .value {
            color: #0f172a;
            font-size: 1rem;
            word-break: break-all;
        }
        .next-steps {
            background: #dbeafe;
            border-left: 4px solid #3b82f6;
            padding: 1.5rem;
            margin-top: 2rem;
            border-radius: 0.5rem;
        }
        .next-steps h3 {
            color: #1e40af;
            margin-bottom: 1rem;
        }
        .next-steps ol {
            color: #1e40af;
            margin-left: 1.5rem;
        }
        .next-steps li {
            margin-bottom: 0.5rem;
        }
        code {
            background: #f1f5f9;
            padding: 0.2rem 0.4rem;
            border-radius: 0.25rem;
            font-family: 'Fira Code', monospace;
        }
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            background: #3b82f6;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            font-weight: 600;
            margin-top: 1rem;
        }
        .btn:hover {
            background: #2563eb;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <div class="logo">MSG.COM OAuth Platform</div>
    </div>

    <div class="container">
        <h1>✅ OAuth Authorization Successful</h1>
        <p class="success">Authorization code received successfully</p>

        <div class="code-box">
            <div class="label">Authorization Code</div>
            <div class="value">{{ code }}</div>
        </div>

        {% if state %}
        <div class="code-box">
            <div class="label">State</div>
            <div class="value">{{ state }}</div>
        </div>
        {% endif %}

        <div class="next-steps">
            <h3>Next Steps</h3>
            <ol>
                <li>Exchange this authorization code for an access token at <code>POST /oauth/token</code></li>
                <li>Include <code>client_id</code>, <code>client_secret</code>, and <code>code</code> in the request</li>
                <li>Use the access token to access protected resources at <code>/api/*</code></li>
            </ol>
        </div>

        <a href="/" class="btn">Return to Home</a>
    </div>
</body>
</html>
    ''', code=code, state=state)

@app.route('/auth/start')
def auth_start():
    """Start OAuth flow"""
    state = secrets.token_urlsafe(16)

    # Redirect to auth server WITHOUT client_id (user must provide it)
    auth_url = (
        f"/oauth/authorize?"
        f"redirect_uri={BASE_URL}/auth/callback&"
        f"response_type=code&"
        f"scope=read&"
        f"state={state}"
    )

    return redirect(auth_url)

if __name__ == '__main__':
    print("[START] OAuth Client Application")
    app.run(host='0.0.0.0', port=8001, debug=True)
