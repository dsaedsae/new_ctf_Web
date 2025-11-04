#!/usr/bin/env python3
"""
MSG.COM OAuth Platform - Client Application
Simple OAuth 2.0 client demo
"""

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
    """Homepage"""
    return render_template('index.html')

@app.route('/auth/callback')
def auth_callback():
    """OAuth callback endpoint"""
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

@app.route('/client/register', methods=['GET', 'POST'])
def client_register():
    """OAuth Client Registration Page"""
    if request.method == 'POST':
        # Get form data
        client_name = request.form.get('client_name')
        redirect_uris = request.form.get('redirect_uris', '').split('\n')
        redirect_uris = [uri.strip() for uri in redirect_uris if uri.strip()]
        logo_uri = request.form.get('logo_uri', '')
        description = request.form.get('description', '')

        # Register client
        registration_data = {
            'client_name': client_name,
            'redirect_uris': redirect_uris
        }

        if logo_uri:
            registration_data['logo_uri'] = logo_uri
        if description:
            registration_data['description'] = description

        try:
            response = requests.post(
                f'{INTERNAL_BASE_URL}/oauth/register',
                json=registration_data,
                timeout=10
            )

            if response.status_code == 200:
                result = response.json()
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Client Registered - MSG.COM</title>
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
            margin-bottom: 2rem;
        }
        .success {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 1rem;
            border-radius: 0.5rem;
            margin-bottom: 1.5rem;
        }
        .info-box {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 0.5rem;
            padding: 1.5rem;
            margin: 1rem 0;
        }
        .label {
            font-weight: 600;
            color: #666;
            font-size: 0.875rem;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        .value {
            color: #333;
            font-family: 'Courier New', monospace;
            word-break: break-all;
            background: white;
            padding: 0.75rem;
            border-radius: 0.25rem;
            border: 1px solid #dee2e6;
        }
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            font-weight: 600;
            margin-top: 1.5rem;
        }
        .btn:hover {
            background: #5568d3;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Client Registered Successfully</h1>

        <div class="success">
            Your OAuth client has been registered successfully!
        </div>

        <div class="info-box">
            <div class="label">Client ID</div>
            <div class="value">{{ client_id }}</div>
        </div>

        <div class="info-box">
            <div class="label">Client Secret</div>
            <div class="value">{{ client_secret }}</div>
        </div>

        <div class="info-box">
            <div class="label">Client Name</div>
            <div class="value">{{ client_name }}</div>
        </div>

        {% if logo_fetch_result %}
        <div class="info-box">
            <div class="label">Logo Fetch Result</div>
            <div class="value">{{ logo_fetch_result | tojson }}</div>
        </div>
        {% endif %}

        <a href="/" class="btn">Return to Home</a>
        <a href="/client/register" class="btn" style="background: #6c757d;">Register Another</a>
    </div>
</body>
</html>
                ''',
                client_id=result.get('client_id'),
                client_secret=result.get('client_secret'),
                client_name=result.get('client_name'),
                logo_fetch_result=result.get('logo_fetch_result')
                )
            else:
                error_msg = response.text
                return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Registration Failed - MSG.COM</title>
    <meta charset="utf-8" />
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
        }
        .error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 1rem;
            border-radius: 0.5rem;
        }
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            margin-top: 1.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Registration Failed</h1>
        <div class="error">{{ error }}</div>
        <a href="/client/register" class="btn">Try Again</a>
    </div>
</body>
</html>
                ''', error=error_msg)
        except Exception as e:
            return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Error - MSG.COM</title>
    <meta charset="utf-8" />
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
        }
        .error {
            background: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
            padding: 1rem;
            border-radius: 0.5rem;
        }
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 0.5rem;
            margin-top: 1.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Error</h1>
        <div class="error">{{ error }}</div>
        <a href="/client/register" class="btn">Try Again</a>
    </div>
</body>
</html>
            ''', error=str(e))

    # GET request - show registration form
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
                <textarea name="redirect_uris" required placeholder="http://localhost:3000/callback
http://localhost:3000/auth/callback"></textarea>
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

if __name__ == '__main__':
    print("[START] OAuth Client Application")
    app.run(host='0.0.0.0', port=8001, debug=True)
