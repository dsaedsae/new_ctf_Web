"""
Legacy Microservice Exploitation V6.1 - Level 7-8
CTF 문제: 레거시 서비스의 연쇄 취약점 공격

난이도: DreamHack Level 7-8
예상 풀이 시간: 90-110분 (블랙박스)

V6.1 수정 사항 (AI-Resistant & Natural):
- 분산 힌트를 통한 Secret 유추 (검증 해시 제거로 자연스러움 향상)
- Permissions 기반 권한 시스템 (auth_token 제거로 자연스러움 향상)
- include_inactive/limit 옵션 NoSQL injection (mode 제거로 자연스러움 향상)
- Path traversal + 세미콜론 우회 (현실적인 검증 실수)
- 모든 단계가 안정적이고 풀이 가능하며 자연스러움
"""

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

# Flask secret key (환경변수에서 로드)
SECRET_KEY = os.getenv('SECRET_KEY')

# 보안: 명시적 설정 필수
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY 환경변수가 필요합니다! "
        ".env 파일 또는 docker-compose.yml에 설정하세요"
    )

app.secret_key = SECRET_KEY

# MongoDB 연결
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://db:27017/')
mongo_client = MongoClient(MONGO_URI)
db = mongo_client.ctf_db

# 보안 설정
app.config['DEBUG'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # HTTP only (no TLS)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['SESSION_REFRESH_EACH_REQUEST'] = False

# Service metadata (secret 유도에 사용)
SERVICE_NAME = 'legacy-auth-service'
SERVICE_VERSION = '2.1.0'
BUILD_DATE = '20240115'
SERVICE_SALT = 'las2024'  # legacy-auth-service 2024

# ============================================================
# STAGE 1: 서비스 탐색 (SERVICE DISCOVERY)
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
                'salt_prefix': SERVICE_SALT  # 힌트: salt 정보
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
        ]
    }

    if service not in endpoints_map:
        return jsonify({'error': 'Service not found'}), 404

    return jsonify({
        'service': service,
        'endpoints': endpoints_map[service]
    })

# ============================================================
# STAGE 2-3: 레거시 엔드포인트 (SECRET 발견)
# ============================================================

@app.route('/api/legacy/config_backup', methods=['GET'])
def config_backup():
    """
    레거시 설정 백업 조회 (정보 노출)

    취약점: 정보 노출 (Information disclosure)
    실제 시나리오: 백업 API에 개발 문서가 포함됨
    """
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
                # 개발자 문서 (실수로 포함됨)
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
# STAGE 4: 세션 검증 (SESSION VERIFICATION)
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
# STAGE 6: 관리자 전용 엔드포인트 (RCE 체인)
# ============================================================

@app.route('/api/admin/db/migrate', methods=['POST'])
def db_migrate():
    """
    데이터베이스 마이그레이션 도구 (관리자 전용)

    취약점 체인:
    1. Permissions 기반 권한 검증
    2. $where 연산자를 통한 NoSQL Injection
    3. log_file 파라미터를 통한 Command Injection
    """

    # 난이도 토글
    BLIND_RCE = os.getenv('BLIND_RCE', 'false').lower() == 'true'

    # Stage 5 체크포인트: 관리자 권한 검증
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin role required'}), 403

    # Permissions 검증
    user_perms = session.get('permissions', [])
    if 'migrate' not in user_perms:
        return jsonify({
            'error': 'Insufficient permissions',
            'required': 'migrate',
            'your_permissions': user_perms
        }), 403

    # 요청 파라미터 파싱
    query_filter = request.json.get('filter', {})
    options = request.json.get('options', {})

    # 옵션 파싱
    limit = options.get('limit', 10)
    include_inactive = options.get('include_inactive', False)

    try:
        # 취약점 1: NoSQL Injection
        # 기본 조건: active 사용자만 (include_inactive로 우회 가능)
        base_conditions = []
        if not include_inactive:
            base_conditions.append({'active': True})

        # 쿼리 결합
        if base_conditions:
            combined_filter = {
                '$and': [query_filter] + base_conditions
            }
        else:
            combined_filter = query_filter

        # MongoDB 쿼리 실행
        results = list(db.users.find(combined_filter).limit(limit))

        # RCE 트리거: 결과가 있고 limit이 충분히 크면 로그 작성
        if len(results) > 0 and limit >= 100:
            log_file = request.json.get('log_file', '/dev/null')

            # 취약점 2: Command Injection
            # Path validation (하지만 취약점 존재)
            allowed_dirs = ['/var/log/', '/tmp/']
            if not any(log_file.startswith(d) for d in allowed_dirs):
                return jsonify({'error': 'Invalid log directory'}), 400

            # Extension 체크 (하지만 basename 사용 안 함)
            if not log_file.endswith(('.log', '.txt')):
                return jsonify({'error': 'Invalid file extension'}), 400

            # 위험한 문자 체크 (세미콜론은 허용 = 취약점)
            dangerous = ['|', '&', '`', '\n', '$']
            if any(c in log_file for c in dangerous):
                return jsonify({'error': 'Invalid characters'}), 400

            # Path normalization 없음 = 취약점
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

            # 난이도 기반 출력
            if not BLIND_RCE:
                # 쉬운 모드: 명령어 출력 반환
                output = result.stdout + result.stderr
                if output:
                    response_data['log_output'] = output
                elif result.returncode == 0:
                    response_data['log_output'] = 'Command executed successfully'

            return jsonify(response_data)

        # 일반 응답 (결과가 없거나 limit이 작음)
        return jsonify({
            'status': 'migration complete',
            'count': len(results),
            'message': 'No records migrated' if len(results) == 0 else f'{len(results)} records processed'
        })

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Migration timeout'}), 408

    except pymongo.errors.OperationFailure as e:
        # 일반 에러만 반환 (힌트 제거)
        app.logger.error(f"MongoDB error: {str(e)}")
        return jsonify({'error': 'Database query failed'}), 500

    except Exception as e:
        # 상세 정보 없는 일반 에러
        app.logger.error(f"Migration error: {str(e)}")
        return jsonify({'error': 'Migration failed'}), 400

# ============================================================
# 유틸리티 엔드포인트
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """모니터링용 헬스 체크 (서비스 정보 포함)"""
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

# Response header에 salt 정보 추가
@app.after_request
def add_headers(response):
    """모든 응답에 서비스 헤더 추가"""
    response.headers['X-Service-Salt'] = SERVICE_SALT
    return response

@app.route('/', methods=['GET'])
def index():
    """메인 대시보드 UI"""
    return render_template('index.html')

@app.route('/services', methods=['GET'])
def services_ui():
    """서비스 목록 UI"""
    return render_template('services.html')

@app.route('/services/<service_name>', methods=['GET'])
def service_detail_ui(service_name):
    """서비스 상세 UI (추후 구현 가능)"""
    return render_template('services.html')

# ============================================================
# Red Herring Endpoints (Misdirection)
# ============================================================

@app.route('/admin/login', methods=['GET'])
def admin_login_ui():
    """가짜 관리자 로그인 페이지 (Red Herring)"""
    return render_template('login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    """가짜 로그인 처리 - 그럴듯하게 실패 (Red Herring)"""
    import time

    username = request.json.get('username', '') if request.json else ''
    password = request.json.get('password', '') if request.json else ''

    # SQL Injection 시도 탐지 (잘못된 방향 유도)
    if "' OR '1'='1" in username or "' OR '1'='1" in password:
        # V5.0: 정답을 알려주지 않음, 그냥 실패만 시킴
        time.sleep(1.0)
        return jsonify({
            'error': 'Invalid credentials'
        }), 401

    # NoSQL Injection처럼 보이지만 실제로는 아무것도 안 함
    if isinstance(username, dict) or isinstance(password, dict):
        return jsonify({
            'error': 'Invalid input format',
            'hint': 'Use string values for authentication'
        }), 400

    # 시간 소모 유도
    time.sleep(1.5)
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/admin', methods=['GET'])
@app.route('/admin/panel', methods=['GET'])
def admin_panel_redirect():
    """가짜 관리자 페이지 - 로그인으로 리다이렉트 (Red Herring)"""
    return jsonify({
        'error': 'Unauthorized',
        'message': 'Please login at /admin/login'
    }), 401

@app.route('/admin/users', methods=['GET'])
def fake_admin_users():
    """그럴듯한 가짜 관리자 API (Red Herring)"""
    # 관리자여도 빈 목록만 반환 (미끼)
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin required'}), 403

    # Admin이어도 빈 목록 (시간 낭비)
    return jsonify({
        'users': [],
        'message': 'No users found in database',
        'hint': 'Try checking /api/admin/ endpoints instead'
    })

@app.route('/api/v2/auth/login', methods=['POST'])
def fake_api_login():
    """그럴듯한 가짜 API 로그인 (Red Herring)"""
    import time

    username = request.json.get('username', '') if request.json else ''

    # NoSQL Injection처럼 보이지만 실제로는 아무것도 안 함
    if isinstance(username, dict):
        return jsonify({
            'error': 'NoSQL injection detected',
            'hint': 'Nice try, but this endpoint is not vulnerable'
        }), 400

    # 시간 소모
    time.sleep(1.0)
    return jsonify({'error': 'Authentication service disabled'}), 501

@app.route('/debug', methods=['GET'])
@app.route('/test', methods=['GET'])
def debug_endpoint():
    """가짜 디버그 엔드포인트 (Red Herring)"""
    return jsonify({'error': 'Debug mode disabled'}), 403

@app.route('/backup', methods=['GET'])
@app.route('/backup/<path:filename>', methods=['GET'])
def backup_endpoint(filename=None):
    """가짜 백업 엔드포인트 (Red Herring)"""
    return jsonify({'error': 'Access denied'}), 403

@app.route('/robots.txt', methods=['GET'])
def robots():
    """robots.txt 제공"""
    return app.send_static_file('robots.txt')

# ============================================================
# 애플리케이션 진입점
# ============================================================

if __name__ == '__main__':
    print("[경고] Flask 개발 서버로 실행 중")
    print("[경고] 프로덕션에서는 Gunicorn 사용")
    app.run(host='0.0.0.0', port=5000, debug=False)
