"""
Legacy Microservice Exploitation V3.0 - PRODUCTION READY
CTF Challenge: Chained vulnerabilities in legacy services

DIFFICULTY: DreamHack Level 7-8
SOLVE TIME: 60-80 minutes (blackbox)

V3.0 FIXES:
- Fixed bare except clauses
- Improved command injection output capture
- Better error handling throughout
- Enhanced logging
"""

import hashlib
import subprocess
import os
from datetime import timedelta
from flask import Flask, request, jsonify, session
from pymongo import MongoClient
import pymongo.errors

app = Flask(__name__)

# ============================================================
# CONFIGURATION
# ============================================================

# Secret derivation material (from environment)
COMPANY_SALT = os.getenv('COMPANY_SALT', 'CompanyName2025')

# Derive Flask secret key from salt
app.secret_key = hashlib.sha256(COMPANY_SALT.encode()).hexdigest()[:32]

# MongoDB connection
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://db:27017/')
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.ctf_db

# Security settings
app.config['DEBUG'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # HTTP only (no TLS)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_REFRESH_EACH_REQUEST'] = False

# ============================================================
# STAGE 1: SERVICE DISCOVERY
# ============================================================

@app.route('/api/v2/services', methods=['GET'])
def list_services():
    """Service discovery endpoint"""
    return jsonify({
        'services': [
            {
                'name': 'auth',
                'version': '2.1.0',
                'status': 'active',
                'description': 'Authentication service'
            },
            {
                'name': 'api',
                'version': '2.0.5',
                'status': 'active',
                'description': 'Main API gateway'
            },
            {
                'name': 'legacy',
                'version': '1.0.0',
                'status': 'deprecated',
                'description': 'Legacy endpoints - scheduled for removal'
            }
        ]
    })

@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """Enumerate endpoints for a specific service"""

    endpoints_map = {
        'legacy': [
            {
                'path': '/api/legacy/get_salt',
                'method': 'GET',
                'description': 'Legacy utility'
            },
            {
                'path': '/api/legacy/system_info',
                'method': 'GET',
                'description': 'System information'
            }
        ],
        'auth': [
            {
                'path': '/api/auth/guest',
                'method': 'POST',
                'description': 'Guest session creation'
            }
        ],
        'api': [
            {
                'path': '/api/v2/services',
                'method': 'GET',
                'description': 'Service discovery'
            }
        ]
    }

    if service not in endpoints_map:
        return jsonify({'error': 'Service not found'}), 404

    return jsonify({
        'service': service,
        'endpoints': endpoints_map[service]
    })

# ============================================================
# STAGE 2-3: LEGACY ENDPOINTS (SECRET DISCOVERY)
# ============================================================

@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    """
    Legacy endpoint exposing salt value

    VULNERABILITY: Information disclosure
    """
    return jsonify({'salt': COMPANY_SALT})

@app.route('/api/legacy/system_info', methods=['GET'])
def system_info():
    """
    System information endpoint

    Enhanced hints for secret derivation
    """
    return jsonify({
        'framework': 'Flask',
        'session_backend': 'SecureCookie',
        'crypto': {
            'library': 'hashlib',
            'algorithm': 'sha256'
        },
        'notes': 'Legacy system using 32-char keys'
    })

# ============================================================
# STAGE 4: SESSION VERIFICATION
# ============================================================

@app.route('/api/auth/guest', methods=['POST'])
def create_guest_session():
    """
    Creates guest session for testing
    """
    session['role'] = 'guest'
    session['user'] = 'guest_user'
    session.permanent = True

    return jsonify({
        'status': 'guest session created',
        'role': 'guest'
    })

# ============================================================
# STAGE 6: ADMIN-ONLY ENDPOINT WITH RCE CHAIN
# ============================================================

@app.route('/api/admin/db/migrate', methods=['POST'])
def db_migrate():
    """
    Database migration tool (Admin only)

    VULNERABILITY CHAIN:
    1. NoSQL Injection via $where operator
    2. Command Injection via log_file parameter
    """

    # Difficulty toggle
    BLIND_RCE = os.getenv('BLIND_RCE', 'false').lower() == 'true'

    # Stage 5 checkpoint: Verify admin privileges
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin required'}), 403

    # Parse request parameters
    query_filter = request.json.get('filter', {})
    log_file = request.json.get('log_file', '/dev/null')

    try:
        # VULNERABILITY 1: NoSQL Injection
        # User input passed directly to MongoDB
        results = list(db.users.find(query_filter).limit(100))

        # Conditional RCE trigger - only if NoSQL injection succeeds
        if "$where" in query_filter and len(results) > 0:

            # VULNERABILITY 2: Command Injection
            # Fixed: Better output capture
            cmd = f"echo 'Migration started' && echo 'Processing {len(results)} records' > {log_file} 2>&1 && echo 'Migration completed'"

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            response_data = {
                'status': 'migration complete',
                'count': len(results),
                'mode': 'advanced'  # Indicator that RCE path was triggered
            }

            # Difficulty-based output
            if not BLIND_RCE:
                # EASY MODE: Return command output
                output = result.stdout + result.stderr
                if output:
                    response_data['log_output'] = output
                elif result.returncode == 0:
                    response_data['log_output'] = 'Command executed successfully'

            return jsonify(response_data)

        # Normal response (NoSQL injection not triggered)
        return jsonify({
            'status': 'migration complete',
            'count': len(results)
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Migration timeout'}), 408

    except pymongo.errors.OperationFailure as e:
        # Enhanced error handling with hints
        error_msg = str(e).lower()

        if 'javascript' in error_msg or 'where' in error_msg:
            return jsonify({
                'error': 'Query execution failed',
                'hint': 'Check MongoDB JavaScript configuration'
            }), 400

        app.logger.error(f"MongoDB error: {str(e)}")
        return jsonify({'error': 'Database query failed'}), 400

    except Exception as e:
        # Generic error without details
        app.logger.error(f"Migration error: {str(e)}")
        return jsonify({'error': 'Migration failed'}), 400

# ============================================================
# UTILITY ENDPOINTS
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check for monitoring"""
    try:
        mongo_client.server_info()

        # Verify $where is enabled
        try:
            test = list(db.users.find({"$where": "function() { return true; }"}).limit(1))
            js_enabled = len(test) > 0
        except (pymongo.errors.OperationFailure, Exception):
            js_enabled = False

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'javascript_enabled': js_enabled,
            'services': ['auth', 'api', 'legacy']
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 503

@app.route('/', methods=['GET'])
def index():
    """Root endpoint"""
    return jsonify({
        'message': 'Microservice Platform API',
        'version': '2.0',
        'documentation': '/api/v2/services'
    })

# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == '__main__':
    print("[WARNING] Running with Flask development server")
    print("[WARNING] Use Gunicorn in production")
    app.run(host='0.0.0.0', port=5000, debug=False)
