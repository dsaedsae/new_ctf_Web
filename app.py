"""
Legacy Microservice Exploitation V4.0 - Level 8 Hard Mode
CTF 문제: 레거시 서비스의 연쇄 취약점 공격

난이도: DreamHack Level 8
예상 풀이 시간: 120-140분 (블랙박스)

V4.0 수정 사항 (Level 8 강화):
- Salt 직접 노출 → 힌트 기반 브루트포스 필요
- system_info 엔드포인트 완전 제거
- NoSQL Injection 에러 힌트 제거
- Health check JavaScript 정보 제거
- Red Herring 엔드포인트 강화 (시간 낭비 유도)
- robots.txt 및 HTML 힌트 최소화
"""

import hashlib
import subprocess
import os
from datetime import timedelta
from flask import Flask, request, jsonify, session, render_template
from pymongo import MongoClient
import pymongo.errors

app = Flask(__name__)

# ============================================================
# 설정 (CONFIGURATION)
# ============================================================

# Secret 유도 재료 (환경변수에서 로드)
COMPANY_SALT = os.getenv('COMPANY_SALT')

# 보안: 명시적 설정 필수
if not COMPANY_SALT:
    raise RuntimeError(
        "COMPANY_SALT 환경변수가 필요합니다! "
        ".env 파일 또는 docker-compose.yml에 설정하세요"
    )

# Salt로부터 Flask secret key 유도
app.secret_key = hashlib.sha256(COMPANY_SALT.encode()).hexdigest()[:32]

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
                'version': '1.0.0',
                'status': 'deprecated',
                'description': 'Legacy endpoints - scheduled for removal'
            }
        ]
    })

@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """특정 서비스의 엔드포인트 열거"""

    endpoints_map = {
        'legacy': [
            {
                'path': '/api/legacy/get_salt',
                'method': 'GET',
                'description': 'Legacy utility'
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

@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    """
    Salt 값 힌트 제공 (간접적 정보 노출)

    취약점: 정보 노출 (Information disclosure) - 하지만 추론 필요
    """
    # Salt를 직접 주지 않고 힌트만 제공
    salt_hash = hashlib.md5(COMPANY_SALT.encode()).hexdigest()

    return jsonify({
        'message': 'Salt access restricted',
        'hint': {
            'format': 'dictionary_word + number',
            'length': len(COMPANY_SALT),
            'md5_prefix': salt_hash[:6],  # 검증용
            'example': 'company2024'
        }
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
    session.permanent = True

    return jsonify({
        'status': 'guest session created',
        'role': 'guest'
    })

# ============================================================
# STAGE 6: 관리자 전용 엔드포인트 (RCE 체인)
# ============================================================

@app.route('/api/admin/db/migrate', methods=['POST'])
def db_migrate():
    """
    데이터베이스 마이그레이션 도구 (관리자 전용)

    취약점 체인:
    1. $where 연산자를 통한 NoSQL Injection
    2. log_file 파라미터를 통한 Command Injection
    """

    # 난이도 토글
    BLIND_RCE = os.getenv('BLIND_RCE', 'false').lower() == 'true'

    # Stage 5 체크포인트: 관리자 권한 검증
    if session.get('role') != 'admin':
        return jsonify({'error': 'Admin required'}), 403

    # 요청 파라미터 파싱
    query_filter = request.json.get('filter', {})
    log_file = request.json.get('log_file', '/dev/null')

    # 간단한 입력 검증 (우회 가능)
    # 일부 위험한 문자 차단 (하지만 세미콜론은 허용)
    blocked_chars = ['|', '&', '$', '`', '\n', '(', ')']
    if any(char in log_file for char in blocked_chars):
        return jsonify({'error': 'Invalid log file path'}), 400

    try:
        # 취약점 1: NoSQL Injection
        # 사용자 입력이 MongoDB에 직접 전달됨
        results = list(db.users.find(query_filter).limit(100))

        # 조건부 RCE 트리거 - NoSQL injection 성공 시에만 실행
        # 엄격한 검증: $where가 실제로 작동하여 모든 사용자를 반환해야 함
        if "$where" in query_filter and len(results) >= 4:

            # 취약점 2: Command Injection
            # 개선됨: 출력 캡처 향상
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
                'mode': 'advanced'  # RCE 경로가 실행되었음을 나타냄
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

        # 일반 응답 (NoSQL injection이 트리거되지 않음)
        return jsonify({
            'status': 'migration complete',
            'count': len(results)
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
    """모니터링용 헬스 체크 (최소 정보만)"""
    try:
        mongo_client.server_info()

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
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

    # SQL Injection 힌트 (잘못된 방향 유도)
    if "' OR '1'='1" in username or "' OR '1'='1" in password:
        return jsonify({
            'error': 'SQL syntax detected',
            'hint': 'This is a NoSQL database'
        }), 400

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
