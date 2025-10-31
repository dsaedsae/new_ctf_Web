import hashlib
import subprocess
import os
import time
from datetime import timedelta
from flask import Flask, request, jsonify, session, render_template
from pymongo import MongoClient
import pymongo.errors

app = Flask(__name__)

# ============================================================
# 설정 (CONFIGURATION)
# ============================================================

SECRET_KEY = os.getenv('SECRET_KEY')

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY 환경변수가 필요합니다! "
        ".env 파일 또는 docker-compose.yml에 설정하세요"
    )

app.secret_key = SECRET_KEY

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://db:27017/')
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.ctf_db

SERVICE_NAME = 'legacy-auth-service'
SERVICE_VERSION = '2.1.0'
BUILD_DATE = '20240115'
SERVICE_SALT = 'las2024'
app.config['DEBUG'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_REFRESH_EACH_REQUEST'] = False

# ============================================================
# 서비스 API
# ============================================================

@app.route('/api/v2/services', methods=['GET'])
def list_services():
    """서비스 목록 조회 엔드포인트"""
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
                'full_name': SERVICE_NAME,
                'version': SERVICE_VERSION,
                'build': BUILD_DATE,
                'status': 'deprecated',
                'description': 'Legacy endpoints - scheduled for removal',
                'salt_prefix': SERVICE_SALT
            },
            {
                'name': 'admin',
                'version': '1.0.0',
                'status': 'restricted',
                'description': 'Administrative tools',
                'access': 'Admin authentication required'
            }
        ]
    })

@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """특정 서비스의 엔드포인트 열거"""

    endpoints_map = {
        'legacy': [
            {
                'path': '/api/legacy/config_backup',
                'method': 'GET',
                'description': 'Configuration backup utility'
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
        ],
        'admin': [
            {
                'path': '/api/admin/db/migrate',
                'method': 'POST',
                'description': 'Database migration tool',
                'access': 'Admin role and migrate permission required'
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
# 레거시 API
# ============================================================

@app.route('/api/legacy/config_backup', methods=['GET'])
def config_backup():
    """레거시 설정 백업 조회"""
    return jsonify({
        'backup_date': '2024-01-15',
        'service': SERVICE_NAME,
        'config': {
            'database': {
                'connection_string': 'mongodb://***',
                'pool_size': 10,
                'timeout': 5000
            },
            'session': {
                'algorithm': 'HMAC-SHA256',
                'key_source': 'derived from service metadata',
                'format': '32 hex chars',
                'sample_generation': 'SHA256(service-build-salt)[:32]',
                'note': 'Key is deterministically generated from service info'
            },
            'build': {
                'service_id': SERVICE_NAME,
                'version': SERVICE_VERSION,
                'build_date': BUILD_DATE,
                'environment': 'production'
            }
        },
        'warning': 'This endpoint is deprecated and will be removed'
    })

# ============================================================
# 인증 API
# ============================================================

@app.route('/api/auth/guest', methods=['POST'])
def create_guest_session():
    """
    테스트용 게스트 세션 생성
    """
    session['role'] = 'guest'
    session['user'] = 'guest_user'
    session['permissions'] = ['read']  # 권한 시스템
    session.permanent = True

    return jsonify({
        'status': 'guest session created',
        'role': 'guest',
        'permissions': ['read']
    })

# ============================================================
# 관리자 API
# ============================================================

@app.route('/api/admin/db/migrate', methods=['POST'])
def db_migrate():
    """데이터베이스 마이그레이션 도구 (관리자 전용)"""

    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin role required'}), 403

    user_perms = session.get('permissions', [])
    if 'migrate' not in user_perms:
        return jsonify({
            'error': 'Insufficient permissions',
            'required': 'migrate',
            'your_permissions': user_perms
        }), 403

    query_filter = request.json.get('filter', {})
    options = request.json.get('options', {})

    limit = options.get('limit', 10)
    include_inactive = options.get('include_inactive', False)

    try:
        base_conditions = []
        if not include_inactive:
            base_conditions.append({'active': True})

        if base_conditions:
            combined_filter = {
                '$and': [query_filter] + base_conditions
            }
        else:
            combined_filter = query_filter

        results = list(db.users.find(combined_filter).limit(limit))

        if len(results) > 0 and limit >= 100:
            log_file = request.json.get('log_file', '/dev/null')

            allowed_dirs = ['/var/log/', '/tmp/']
            if not any(log_file.startswith(d) for d in allowed_dirs):
                return jsonify({'error': 'Invalid log directory'}), 400

            if not log_file.endswith(('.log', '.txt')):
                return jsonify({'error': 'Invalid file extension'}), 400

            dangerous = ['|', '&', '`', '\n', '$']
            if any(c in log_file for c in dangerous):
                return jsonify({'error': 'Invalid characters'}), 400

            cmd = f"echo 'Migration started' && echo 'Migrated {len(results)} records' > {log_file} 2>&1 && echo 'Migration completed'"

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )

            response_data = {
                'status': 'migration complete',
                'count': len(results)
            }

            output = result.stdout + result.stderr
            if output:
                response_data['log_output'] = output
            elif result.returncode == 0:
                response_data['log_output'] = 'Command executed successfully'

            return jsonify(response_data)

        return jsonify({
            'status': 'migration complete',
            'count': len(results),
            'message': 'No records migrated' if len(results) == 0 else f'{len(results)} records processed'
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Migration timeout'}), 408

    except pymongo.errors.OperationFailure as e:
        app.logger.error(f"MongoDB error: {str(e)}")
        return jsonify({'error': 'Database query failed'}), 500

    except Exception as e:
        app.logger.error(f"Migration error: {str(e)}")
        return jsonify({'error': 'Migration failed'}), 400

# ============================================================
# 유틸리티 엔드포인트
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크"""
    try:
        mongo_client.server_info()

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'services': ['auth', 'api', 'legacy'],
            'service': SERVICE_NAME,
            'version': SERVICE_VERSION,
            'build_date': BUILD_DATE
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'database': 'disconnected',
            'error': str(e)
        }), 503

@app.after_request
def add_headers(response):
    """응답 헤더 추가"""
    response.headers['X-Service-Salt'] = SERVICE_SALT
    return response

@app.route('/', methods=['GET'])
def index():
    """메인 대시보드"""
    return render_template('index.html')

@app.route('/services', methods=['GET'])
def services_ui():
    """서비스 목록"""
    return render_template('services.html')

@app.route('/services/<service_name>', methods=['GET'])
def service_detail_ui(service_name):
    """서비스 상세"""
    return render_template('services.html')

# ============================================================
# 관리자 엔드포인트
# ============================================================

@app.route('/admin/login', methods=['GET'])
def admin_login_ui():
    """관리자 로그인 페이지"""
    return render_template('login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    """로그인 처리"""
    import time

    username = request.json.get('username', '') if request.json else ''
    password = request.json.get('password', '') if request.json else ''

    if "' OR '1'='1" in username or "' OR '1'='1" in password:
        time.sleep(1.0)
        return jsonify({
            'error': 'Invalid credentials'
        }), 401

    if isinstance(username, dict) or isinstance(password, dict):
        return jsonify({
            'error': 'Invalid input format',
            'hint': 'Use string values for authentication'
        }), 400

    time.sleep(1.5)
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/admin', methods=['GET'])
@app.route('/admin/panel', methods=['GET'])
def admin_panel_redirect():
    """관리자 페이지"""
    return jsonify({
        'error': 'Unauthorized',
        'message': 'Please login at /admin/login'
    }), 401

@app.route('/admin/users', methods=['GET'])
def fake_admin_users():
    """관리자 사용자 API"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin required'}), 403

    return jsonify({
        'users': [],
        'message': 'No users found in database',
        'hint': 'Try checking /api/admin/ endpoints instead'
    })

@app.route('/api/v2/auth/login', methods=['POST'])
def fake_api_login():
    """API 로그인"""
    import time

    username = request.json.get('username', '') if request.json else ''

    if isinstance(username, dict):
        return jsonify({
            'error': 'NoSQL injection detected',
            'hint': 'Nice try, but this endpoint is not vulnerable'
        }), 400

    time.sleep(1.0)
    return jsonify({'error': 'Authentication service disabled'}), 501

@app.route('/debug', methods=['GET'])
@app.route('/test', methods=['GET'])
def debug_endpoint():
    """디버그 엔드포인트"""
    return jsonify({'error': 'Debug mode disabled'}), 403

@app.route('/backup', methods=['GET'])
@app.route('/backup/<path:filename>', methods=['GET'])
def backup_endpoint(filename=None):
    """백업 엔드포인트"""
    return jsonify({'error': 'Access denied'}), 403

@app.route('/robots.txt', methods=['GET'])
def robots():
    """robots.txt"""
    return app.send_static_file('robots.txt')

if __name__ == '__main__':
    print("[경고] Flask 개발 서버로 실행 중")
    print("[경고] 프로덕션에서는 Gunicorn 사용")
    app.run(host='0.0.0.0', port=5000, debug=False)
