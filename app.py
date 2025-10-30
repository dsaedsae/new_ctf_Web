"""
Legacy Microservice Exploitation V3.0 - 프로덕션 준비 완료
CTF 문제: 레거시 서비스의 연쇄 취약점 공격

난이도: DreamHack Level 7-8
예상 풀이 시간: 60-80분 (블랙박스)

V3.0 수정 사항:
- bare except 절 수정
- Command Injection 출력 캡처 개선
- 전반적인 에러 처리 개선
- 로깅 강화
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
# STAGE 2-3: 레거시 엔드포인트 (SECRET 발견)
# ============================================================

@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    """
    Salt 값을 노출하는 레거시 엔드포인트

    취약점: 정보 노출 (Information disclosure)
    """
    return jsonify({'salt': COMPANY_SALT})

@app.route('/api/legacy/system_info', methods=['GET'])
def system_info():
    """
    시스템 정보 엔드포인트

    Secret 유도를 위한 힌트 제공
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

    try:
        # 취약점 1: NoSQL Injection
        # 사용자 입력이 MongoDB에 직접 전달됨
        results = list(db.users.find(query_filter).limit(100))

        # 조건부 RCE 트리거 - NoSQL injection 성공 시에만 실행
        if "$where" in query_filter and len(results) > 0:

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
        # 힌트가 포함된 향상된 에러 처리
        error_msg = str(e).lower()

        if 'javascript' in error_msg or 'where' in error_msg:
            return jsonify({
                'error': 'Query execution failed',
                'hint': 'Check MongoDB JavaScript configuration'
            }), 400

        app.logger.error(f"MongoDB error: {str(e)}")
        return jsonify({'error': 'Database query failed'}), 400

    except Exception as e:
        # 상세 정보 없는 일반 에러
        app.logger.error(f"Migration error: {str(e)}")
        return jsonify({'error': 'Migration failed'}), 400

# ============================================================
# 유틸리티 엔드포인트
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """모니터링용 헬스 체크"""
    try:
        mongo_client.server_info()

        # $where 연산자가 활성화되었는지 확인
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

@app.route('/legacy', methods=['GET'])
def legacy_tools_ui():
    """레거시 도구 UI"""
    return render_template('legacy_tools.html')

# ============================================================
# 애플리케이션 진입점
# ============================================================

if __name__ == '__main__':
    print("[경고] Flask 개발 서버로 실행 중")
    print("[경고] 프로덕션에서는 Gunicorn 사용")
    app.run(host='0.0.0.0', port=5000, debug=False)
