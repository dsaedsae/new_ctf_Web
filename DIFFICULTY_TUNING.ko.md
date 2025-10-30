# 난이도 조절 가이드
## 취약점 추가 없이 고급 플레이어의 풀이 시간 늘리는 방법

**대상 청중**: 난이도를 조절하고 싶은 CTF 주최자
**현재 난이도**: Level 7-8 (중급자 60-80분, 고급자 20-30분)
**목표**: 고급 플레이어의 풀이 시간을 45-60+분으로 연장

---

## 🎯 철학

**원칙**: 새로운 취약점을 추가하거나 핵심 exploit 체인을 변경하지 **말것**
**방법**: 다음을 통해 각 단계를 더 시간 소모적으로 만들기:
- 힌트 줄이기
- 난독화 증가
- 노이즈/방해 요소 추가
- 더 많은 열거 요구

---

## 📊 현재 풀이 시간 분석 (고급 플레이어)

```
Stage 1: 서비스 탐색                   2-3분
Stage 2-3: 정보 노출                  5-7분
Stage 4: Secret 검증                  3-5분
Stage 5: 세션 위조                    5-7분
Stage 6: RCE 체인                     5-8분
────────────────────────────────────────────────
총계:                                20-30분
```

**목표**: 45-60분

---

## 🔧 방법 1: 정보 노출 힌트 줄이기

### 현재 코드 (app.py:139-154)
```python
@app.route('/api/legacy/system_info', methods=['GET'])
def system_info():
    return jsonify({
        'framework': 'Flask',                    # ← 너무 명확
        'session_backend': 'SecureCookie',       # ← 접근 방법 드러냄
        'crypto': {
            'library': 'hashlib',                # ← 직접적 힌트
            'algorithm': 'sha256'                # ← 정확한 알고리즘
        },
        'notes': 'Legacy system using 32-char keys'  # ← 키 길이 힌트
    })
```

### 강화 버전 (+10분 추가)
```python
@app.route('/api/legacy/system_info', methods=['GET'])
def system_info():
    return jsonify({
        'platform': 'Python 3.9.x',
        'server': 'Gunicorn/21.2.0',
        'status': 'operational',
        'deprecated_since': '2023-Q4'
    })
```

**영향**:
- 플레이어가 Flask를 독립적으로 파악해야 함 (프레임워크 탐지)
- Flask 세션 메커니즘 연구 필요
- 다양한 해시 알고리즘 테스트 필요 (md5, sha1, sha256, sha512)
- 다양한 키 길이 시도 필요 (16, 24, 32, 64)

**예상 시간 증가**: +10-15분

---

## 🔧 방법 2: Salt 엔드포인트 난독화

### 현재 코드 (app.py:130-137)
```python
@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    """
    Legacy endpoint exposing salt value

    VULNERABILITY: Information disclosure
    """
    return jsonify({'salt': COMPANY_SALT})
```

### 옵션 A: 간접 응답 (+5분 추가)
```python
@app.route('/api/legacy/config', methods=['GET'])
def legacy_config():
    """Legacy configuration endpoint"""
    return jsonify({
        'database': {
            'host': 'internal-db-01',
            'port': 27017,
            'name': 'ctf_db'
        },
        'session': {
            'derivation_material': COMPANY_SALT,  # ← 필드명 변경
            'timeout': 86400
        },
        'features': {
            'legacy_mode': True,
            'api_version': '1.0'
        }
    })
```

**영향**: 플레이어가 중첩된 JSON 파싱 및 관련 필드 식별 필요

### 옵션 B: Base64 인코딩 (+3분 추가)
```python
import base64

@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    encoded = base64.b64encode(COMPANY_SALT.encode()).decode()
    return jsonify({'config_data': encoded})
```

**영향**: 플레이어가 base64 인식 및 디코딩 필요

### 옵션 C: 여러 엔드포인트로 분할 (+8분 추가)
```python
@app.route('/api/legacy/config/part1', methods=['GET'])
def config_part1():
    return jsonify({'data': COMPANY_SALT[:len(COMPANY_SALT)//2]})

@app.route('/api/legacy/config/part2', methods=['GET'])
def config_part2():
    return jsonify({'data': COMPANY_SALT[len(COMPANY_SALT)//2:]})
```

**영향**: 플레이어가 두 엔드포인트를 모두 발견하고 값을 연결해야 함

**예상 시간 증가**: 옵션에 따라 +3-8분

---

## 🔧 방법 3: 엔드포인트 열거 제거

### 현재 코드 (app.py:85-124)
```python
@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """Enumerate endpoints for a specific service"""
    endpoints_map = {
        'legacy': [
            {
                'path': '/api/legacy/get_salt',      # ← 모든 엔드포인트 나열
                'method': 'GET',
                'description': 'Legacy utility'
            },
            # ...
        ]
    }
    return jsonify({'service': service, 'endpoints': endpoints_map[service]})
```

### 강화 버전 (+15분 추가)
```python
@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """Enumerate endpoints for a specific service"""

    if service not in ['auth', 'api', 'legacy']:
        return jsonify({'error': 'Service not found'}), 404

    # 정확한 경로 없이 일반 정보만 반환
    return jsonify({
        'service': service,
        'status': 'deprecated' if service == 'legacy' else 'active',
        'note': 'Endpoint documentation unavailable for deprecated services'
    })
```

**영향**:
- 플레이어가 디렉토리 브루트포싱 사용 필요 (gobuster, ffuf, dirbuster)
- 일반적인 엔드포인트 패턴 추측:
  - `/api/legacy/config`
  - `/api/legacy/info`
  - `/api/legacy/status`
  - `/api/legacy/get_*`
  - `/api/legacy/system_*`

**워드리스트 제안**:
- `common.txt` (SecLists)
- `api-endpoints.txt`
- 커스텀 생성 목록

**예상 시간 증가**: +15-20분

---

## 🔧 방법 4: Secret 복잡도 증가

### 현재 구현
```python
# app.py:40
app.secret_key = hashlib.sha256(COMPANY_SALT.encode()).hexdigest()[:32]
```

### 옵션 A: 다중 해시 라운드 추가 (+5분 추가)
```python
def derive_secret(salt):
    result = salt.encode()
    for _ in range(1000):  # PBKDF2-like
        result = hashlib.sha256(result).digest()
    return result.hex()[:32]

app.secret_key = derive_secret(COMPANY_SALT)
```

**제공할 힌트**: "시스템이 키 강화를 사용합니다"

**영향**: 플레이어가 반복 횟수를 알아내야 함

### 옵션 B: 키 유도 함수 (+10분 추가)
```python
import hashlib

def custom_kdf(salt):
    # 커스텀 유도: sha256(sha256(salt) + salt)
    first = hashlib.sha256(salt.encode()).hexdigest()
    second = hashlib.sha256((first + salt).encode()).hexdigest()
    return second[:32]

app.secret_key = custom_kdf(COMPANY_SALT)
```

**system_info에 제공할 힌트**: "중첩 해시 구조 사용"

**영향**: 플레이어가 유도 방법을 역공학해야 함

**경고**: 너무 모호하게 만들면 추측 게임이 됨

**예상 시간 증가**: +5-10분

---

## 🔧 방법 5: 서비스 탐색에 노이즈 추가

### 현재 코드
```python
@app.route('/api/v2/services', methods=['GET'])
def list_services():
    return jsonify({
        'services': [
            {'name': 'auth', ...},
            {'name': 'api', ...},
            {'name': 'legacy', ...}  # ← 3개 서비스만
        ]
    })
```

### 강화 버전 (+5분 추가)
```python
@app.route('/api/v2/services', methods=['GET'])
def list_services():
    return jsonify({
        'services': [
            {'name': 'auth', 'status': 'active', ...},
            {'name': 'api', 'status': 'active', ...},
            {'name': 'billing', 'status': 'active', ...},      # ← 노이즈
            {'name': 'reporting', 'status': 'active', ...},   # ← 노이즈
            {'name': 'legacy', 'status': 'deprecated', ...},
            {'name': 'backup', 'status': 'maintenance', ...}, # ← 노이즈
            {'name': 'logs', 'status': 'active', ...},        # ← 노이즈
        ]
    })
```

**영향**: 플레이어가 취약한 서비스를 찾기 위해 여러 서비스 조사 필요

**구현**:
- 노이즈 서비스용 가짜 엔드포인트 추가 (404 또는 "Not Implemented" 반환)
- 플레이어가 막다른 길을 탐색하는 데 시간 낭비

**예상 시간 증가**: +5-7분

---

## 🔧 방법 6: NoSQL Injection 힌트 난독화

### 현재 코드 (app.py:242-253)
```python
except pymongo.errors.OperationFailure as e:
    error_msg = str(e).lower()

    if 'javascript' in error_msg or 'where' in error_msg:
        return jsonify({
            'error': 'Query execution failed',
            'hint': 'Check MongoDB JavaScript configuration'  # ← 너무 도움됨
        }), 400
```

### 강화 버전 (+5분 추가)
```python
except pymongo.errors.OperationFailure as e:
    # 힌트 없는 일반 에러
    app.logger.error(f"MongoDB error: {str(e)}")
    return jsonify({
        'error': 'Database query failed',
        'code': 'DB_ERROR_001'
    }), 400
```

**영향**: 플레이어가 힌트 없이 다양한 NoSQL injection 기법 시도 필요:
- `$where` 연산자
- `$regex` 연산자
- `$ne` 연산자
- JavaScript injection

**예상 시간 증가**: +5-8분

---

## 🔧 방법 7: Rate Limiting 우회 요구

### app.py에 추가 (+10분 추가)
```python
from functools import wraps
from time import time

# 간단한 rate limiter
request_times = {}

def rate_limit(max_requests=5, window=60):
    """Rate limit: window 초 동안 max_requests"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time()

            if ip not in request_times:
                request_times[ip] = []

            # 오래된 요청 정리
            request_times[ip] = [t for t in request_times[ip] if now - t < window]

            if len(request_times[ip]) >= max_requests:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': int(window - (now - request_times[ip][0]))
                }), 429

            request_times[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# admin 엔드포인트에 적용
@app.route('/api/admin/db/migrate', methods=['POST'])
@rate_limit(max_requests=10, window=60)  # 분당 10회 요청
def db_migrate():
    # ... 기존 코드 ...
```

**영향**: 플레이어가:
- Rate limiting 감지
- Exploit에 지연 추가
- 또는 여러 IP/프록시 사용

**참고**: 제한을 합리적으로 유지 (너무 좌절스럽게 만들지 말 것)

**예상 시간 증가**: +8-12분

---

## 🔧 방법 8: BLIND_RCE 모드 활성화

### 현재 코드
```python
# .env
BLIND_RCE=false  # 출력이 반환됨
```

### 강화 버전
```python
# .env
BLIND_RCE=true  # 출력이 반환되지 않음
```

**영향** (app.py:219-232):
- 명령어 출력이 반환되지 않음
- 플레이어가 blind exploitation 기법 사용 필요:
  - DNS exfiltration
  - 시간 기반 추출
  - HTTP 콜백
  - OOB (Out-of-Band) 기법

**참고**: 기법은 `solution/exploit_blind.py` 참조

**예상 시간 증가**: +15-25분

---

## 🔧 방법 9: 세션 쿠키 수명 단축

### 현재 코드 (app.py:52)
```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # 24시간
```

### 강화 버전
```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)  # 10분
```

**영향**:
- 플레이어가 더 빠르게 작업하거나 단계를 재시작해야 함
- 자동화/스크립팅 장려
- 시간 압박 추가

**참고**: 너무 짧게 만들지 말 것 (<5분)이면 좌절스러움

**예상 시간 증가**: +5-10분 (간접적)

---

## 🔧 방법 10: 명확한 변수명 변경

### 현재 코드
```python
query_filter = request.json.get('filter', {})     # ← 명확함
log_file = request.json.get('log_file', '/dev/null')  # ← 직접적 힌트
```

### 강화 버전
```python
query_filter = request.json.get('q', {})          # ← 덜 명확함
log_file = request.json.get('output', '/dev/null')  # ← 중립적 이름
```

**문서에서도 변경**:
```python
# 도움말 엔드포인트 (추가하는 경우)
return jsonify({
    'parameters': {
        'q': '데이터베이스용 쿼리 객체',
        'output': '출력 목적지'
    }
})
```

**영향**: 플레이어가 다음을 통해 파라미터 이름 파악 필요:
- 퍼징
- 에러 메시지 읽기
- 일반적인 이름 추측

**예상 시간 증가**: +3-5분

---

## 📋 추천 조합

### 중간 증가 (총 40-45분)
1. ✅ 방법 2 (옵션 A): 간접 salt 응답 (+5분)
2. ✅ 방법 5: 서비스 탐색에 노이즈 추가 (+5분)
3. ✅ 방법 6: NoSQL injection 힌트 제거 (+5분)
4. ✅ 방법 10: 명확한 변수명 변경 (+3분)

**총계**: +18분 → ~38-48분 풀이 시간

---

### 상당한 증가 (총 50-60분)
1. ✅ 방법 1: 정보 노출 힌트 줄이기 (+10분)
2. ✅ 방법 3: 엔드포인트 열거 제거 (+15분)
3. ✅ 방법 5: 서비스 탐색에 노이즈 추가 (+5분)
4. ✅ 방법 6: NoSQL injection 힌트 제거 (+5분)
5. ✅ 방법 8: BLIND_RCE 활성화 (+20분)

**총계**: +55분 → ~75-85분 풀이 시간

---

### 전문가 모드 (총 70-90분)
1. ✅ 방법 1: 정보 노출 힌트 줄이기 (+10분)
2. ✅ 방법 3: 엔드포인트 열거 제거 (+15분)
3. ✅ 방법 4 (옵션 B): 복잡한 키 유도 (+10분)
4. ✅ 방법 5: 서비스 탐색에 노이즈 추가 (+5분)
5. ✅ 방법 6: NoSQL injection 힌트 제거 (+5분)
6. ✅ 방법 7: Rate limiting (+10분)
7. ✅ 방법 8: BLIND_RCE 활성화 (+20분)
8. ✅ 방법 10: 명확한 변수명 변경 (+3분)

**총계**: +78분 → ~98-108분 풀이 시간

---

## ⚠️ 중요 경고

### 하지 말아야 할 것:
1. ❌ 불가능하게 만들지 말 것 (여러 레벨의 인코딩/암호화 피하기)
2. ❌ 새로운 취약점 추가하지 말 것 (의도된 솔루션 변경)
3. ❌ Exploit 체인을 깨뜨리지 말 것 (각 단계가 여전히 다음으로 이어져야 함)
4. ❌ "추측성"으로 만들지 말 것 (정확한 마법 값 요구 피하기)
5. ❌ 모든 힌트를 제거하지 말 것 (균형이 중요)

### 이 원칙들을 유지하세요:
1. ✅ 모든 단계는 여전히 열거/연구로 해결 가능해야 함
2. ✅ 힌트는 미묘하지만 존재해야 함
3. ✅ 여러 접근 방법이 가능해야 함 (예: 다른 해시 알고리즘)
4. ✅ 에러 메시지가 디버깅에 충분히 유익해야 함
5. ✅ Exploit이 자동화 가능해야 함 (스크립트 작성 가능)

---

## 🧪 변경 후 테스트

난이도 변경 구현 후 다음으로 테스트:

```bash
# 1. 수동 풀이 (시간 측정)
time manual_solve.sh

# 2. 자동화 exploit (수정과 함께 여전히 작동해야 함)
cd solution
time python3 exploit.py http://localhost:5000

# 3. 의도하지 않은 우회 경로 확인
python3 test_security.py

# 4. 좌절 지점 확인
# - 에러 메시지가 충분히 도움이 되는가?
# - 단계들이 합리적인 노력으로 해결 가능한가?
# - 명확한 진행이 있는가?
```

**목표 지표**:
- 수동 풀이: 고급 플레이어가 50-70분
- 자동화 exploit: 완료되어야 함 (업데이트 필요할 수 있음)
- 막다른 길이나 불가능한 단계 없음
- 좌절 수준: 도전적이지만 공정함

---

## 📊 난이도 매트릭스

| 방법 | 추가 시간 | 필요 기술 | 좌절 위험 | 추천 |
|------|-----------|----------|----------|------|
| 1. 힌트 줄이기 | +10분 | 연구 | 낮음 | ✅ 예 |
| 2. Salt 난독화 | +5분 | JSON 파싱 | 낮음 | ✅ 예 |
| 3. 열거 제거 | +15분 | 퍼징 도구 | 중간 | ⚠️ 고려 |
| 4. 복잡한 KDF | +10분 | 암호 지식 | 높음 | ⚠️ 위험 |
| 5. 노이즈 추가 | +5분 | 인내심 | 낮음 | ✅ 예 |
| 6. NoSQL 힌트 제거 | +5분 | NoSQL 경험 | 중간 | ✅ 예 |
| 7. Rate limiting | +10분 | 스크립팅 | 중간 | ⚠️ 고려 |
| 8. Blind RCE | +20분 | 고급 RCE | 높음 | ⚠️ 전문가만 |
| 9. 짧은 세션 | +5분 | 속도 | 높음 | ❌ 비추천 |
| 10. 변수명 변경 | +3분 | 퍼징 | 낮음 | ✅ 예 |

**범례**:
- ✅ 안전하게 구현 가능
- ⚠️ 주의해서 사용
- ❌ 전문가 청중이 아니면 피하기

---

## 🎯 빠른 구현 가이드

### 1단계: 목표 난이도 선택
```
쉬운 모드:      20-30분 (현재)
중간 모드:      40-50분 (방법 2, 5, 6, 10)
어려운 모드:    60-75분 (방법 1, 3, 5, 6, 8)
전문가 모드:    90+분 (모든 방법)
```

### 2단계: 코드 변경
```bash
# 원본 백업
cp app.py app.py.original

# 선택한 방법으로 app.py 편집
nano app.py

# 난이도를 위해 .env 업데이트
nano .env
```

### 3단계: 철저히 테스트
```bash
# 빌드 및 테스트
docker-compose up -d
python3 solution/exploit.py http://localhost:5000

# 수동 검증
curl http://localhost:5000/api/v2/services
# ... 각 단계 테스트 ...
```

### 4단계: 문서 업데이트
```bash
# 새 난이도 평가로 README.md 업데이트
# 새 절차로 TESTING.md 업데이트
# 필요시 solution/exploit.py 업데이트
```

---

## 🔄 변경 사항 되돌리기

되돌려야 하는 경우:

```bash
# 원본 복원
cp app.py.original app.py

# 환경 리셋
cp .env.example .env
# COMPANY_SALT 편집

# 재빌드
docker-compose down -v
docker-compose build
docker-compose up -d
```

---

## 📞 지원

이러한 변경을 구현하고 문제가 발생하면:
1. 트러블슈팅은 TESTING.md 확인
2. MongoDB JavaScript가 여전히 활성화되어 있는지 확인
3. 각 단계를 개별적으로 테스트
4. 로그 검토: `docker-compose logs -f web`

---

**마지막 업데이트**: 2025-01-XX
**버전**: 1.0
**적용 대상**: Legacy Microservice CTF V3.0
