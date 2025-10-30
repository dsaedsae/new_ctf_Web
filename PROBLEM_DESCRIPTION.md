# CTF 문제 설명 - Legacy Microservice Exploitation (Level 8)

## 📌 문제 제작 배경

기존의 단일 취약점 기반 CTF 문제는 실제 공격 시나리오를 반영하지 못한다는 한계가 있었습니다.
실제 프로덕션 환경에서는 하나의 취약점만으로 시스템을 완전히 장악하는 것이 거의 불가능하며,
여러 취약점을 **체이닝(Chaining)**하여 권한을 단계적으로 상승시키는 것이 일반적입니다.

이에 따라 **OWASP Top 10 (2021)** 웹 취약점을 바탕으로 현실적인 공격 시나리오를 반영한
다단계 취약점 체이닝 문제를 제작하게 되었습니다.

---

## 🎯 핵심 취약점 체이닝 (Attack Chain)

본 문제는 **4단계 공격 체이닝**을 통해 시스템 장악(RCE)을 달성하는 시나리오입니다.

```
[Stage 1] Information Disclosure
    ↓ Salt 힌트 획득
[Stage 2] Cryptographic Failure
    ↓ Flask Secret Key 유도
[Stage 3] Broken Access Control
    ↓ 세션 위조 → Admin 권한 획득
[Stage 4] NoSQL Injection
    ↓ $where 연산자 → JavaScript 실행
[Stage 5] Command Injection
    ↓ RCE (Remote Code Execution)
[FLAG 획득]
```

---

## 🔐 OWASP Top 10 (2021) 매핑

### **1. A05:2021 - Security Misconfiguration**

**취약점**: 레거시 엔드포인트에서 민감한 설정 정보 노출

```python
@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    # Salt 값을 힌트로 제공 (직접 노출하지 않지만 브루트포스 가능)
    return jsonify({
        'hint': {
            'format': 'dictionary_word + number',
            'length': 7,
            'md5_prefix': salt_hash[:6]
        }
    })
```

**영향**: 공격자가 Salt 값을 브루트포스하여 획득 가능

**관련 CWE**:
- **CWE-200**: Exposure of Sensitive Information to an Unauthorized Actor
- **CWE-497**: Exposure of Sensitive System Information to an Unauthorized Control Sphere

**관련 CVE 사례**:
- **CVE-2019-11043** (PHP-FPM): 설정 오류로 인한 RCE
- **CVE-2021-44228** (Log4Shell): 기본 설정의 위험성

---

### **2. A02:2021 - Cryptographic Failures**

**취약점**: 예측 가능한 방식으로 Secret Key 생성

```python
# Salt로부터 Flask secret_key 유도
app.secret_key = hashlib.sha256(COMPANY_SALT.encode()).hexdigest()[:32]
```

**영향**: Salt를 알면 Secret Key를 재구성하여 세션 위조 가능

**관련 CWE**:
- **CWE-326**: Inadequate Encryption Strength
- **CWE-330**: Use of Insufficiently Random Values
- **CWE-798**: Use of Hard-coded Credentials

**관련 CVE 사례**:
- **CVE-2015-5122** (Flask): Session Cookie 위조 취약점
- **CVE-2020-7656** (jQuery): Cryptographic weakness

**실제 공격 사례**:
- Uber 2016년 해킹: AWS 키가 GitHub에 노출되어 5,700만 명 정보 유출
- LastPass 2022년: Master Password Salt 획득 후 브루트포스 시도

---

### **3. A01:2021 - Broken Access Control**

**취약점**: 클라이언트 측 세션 기반 인증 (Flask SecureCookie)

```python
# 세션 쿠키만으로 권한 검증
if session.get('role') != 'admin':
    return jsonify({'error': 'Admin required'}), 403
```

**영향**: Secret Key를 알면 임의의 권한으로 세션 위조 가능

```python
# 공격자가 위조한 세션
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'attacker'}" \
  --secret "4e0210e179e20cd5bf97690a65df1c9e"
```

**관련 CWE**:
- **CWE-287**: Improper Authentication
- **CWE-639**: Authorization Bypass Through User-Controlled Key
- **CWE-565**: Reliance on Cookies without Validation and Integrity Checking

**관련 CVE 사례**:
- **CVE-2018-16487** (Lodash): Prototype pollution로 권한 상승
- **CVE-2021-3129** (Laravel): 세션 위조를 통한 RCE

---

### **4. A03:2021 - Injection (NoSQL Injection)**

**취약점**: 사용자 입력이 MongoDB 쿼리에 직접 전달

```python
# 취약한 코드
query_filter = request.json.get('filter', {})
results = list(db.users.find(query_filter).limit(100))
```

**공격 페이로드**:
```json
{
  "filter": {
    "$where": "function() { return true; }"
  }
}
```

**영향**: MongoDB의 $where 연산자를 통한 JavaScript 실행

**관련 CWE**:
- **CWE-89**: SQL Injection (NoSQL에도 적용)
- **CWE-943**: Improper Neutralization of Special Elements in Data Query Logic
- **CWE-94**: Improper Control of Generation of Code (Code Injection)

**관련 CVE 사례**:
- **CVE-2021-22911** (Rocket.Chat): MongoDB NoSQL Injection
- **CVE-2019-10758** (MongoDB Node.js Driver): NoSQL Injection
- **CVE-2020-7699** (Express-cart): NoSQL Injection leading to Admin Access

**실제 공격 사례**:
- 2016년: MongoDB 27,000+ 데이터베이스 랜섬웨어 공격 (NoSQL Injection 악용)

---

### **5. A03:2021 - Injection (OS Command Injection)**

**취약점**: 사용자 입력이 Shell 명령어에 직접 삽입

```python
# 취약한 코드
log_file = request.json.get('log_file', '/dev/null')
cmd = f"echo 'Processing {len(results)} records' > {log_file} 2>&1"
subprocess.run(cmd, shell=True)
```

**공격 페이로드**:
```json
{
  "log_file": "/tmp/x; cat /flag.txt"
}
```

**영향**: 임의의 시스템 명령어 실행 (RCE)

**관련 CWE**:
- **CWE-78**: OS Command Injection
- **CWE-77**: Command Injection
- **CWE-88**: Argument Injection

**관련 CVE 사례**:
- **CVE-2021-44228** (Log4Shell): Command Injection leading to RCE
- **CVE-2022-22965** (Spring4Shell): RCE via Command Injection
- **CVE-2014-6271** (Shellshock): Bash Command Injection

**실제 공격 사례**:
- 2017년 Equifax 해킹: Command Injection으로 1억 4,300만 명 정보 유출

---

## 🔗 공격 체이닝 상세 분석

### **Phase 1: 정찰 및 정보 수집 (Reconnaissance)**

**기법**:
- API Enumeration
- Directory Brute-forcing
- HTML Source Analysis
- robots.txt 분석

**획득 정보**:
- 서비스 구조 (auth, api, legacy)
- 레거시 엔드포인트 (/api/legacy/get_salt)
- 관리자 API 경로 힌트 (/api/admin/)

---

### **Phase 2: 크리덴셜 획득 (Credential Access)**

**공격 기법**: Dictionary-based Bruteforce

**MITRE ATT&CK**: T1110.001 - Brute Force: Password Guessing

**과정**:
1. Salt 힌트 획득 (format, length, md5_prefix)
2. 워드리스트 생성 (dictionary_word + number)
3. MD5 해시 계산 및 검증
4. Salt 발견: `insane2`

**도구**: Python (hashlib)

---

### **Phase 3: 세션 위조 (Privilege Escalation)**

**공격 기법**: Cryptographic Attack + Session Hijacking

**MITRE ATT&CK**:
- T1539 - Steal Web Session Cookie
- T1550.004 - Use Alternate Authentication Material: Web Session Cookie

**과정**:
1. Flask Secret Key 유도: `SHA256(salt)[:32]`
2. flask-unsign을 사용한 세션 위조
3. Admin 권한 획득

**도구**: flask-unsign, Python (hashlib)

---

### **Phase 4: 데이터베이스 침투 (Lateral Movement)**

**공격 기법**: NoSQL Injection

**MITRE ATT&CK**: T1190 - Exploit Public-Facing Application

**과정**:
1. Admin 세션으로 /api/admin/db/migrate 접근
2. MongoDB $where 연산자 악용
3. JavaScript 실행 가능 확인 ("mode: advanced")
4. RCE 경로 활성화

**페이로드**:
```json
{"filter": {"$where": "function() { return true; }"}}
```

---

### **Phase 5: 코드 실행 (Execution)**

**공격 기법**: OS Command Injection

**MITRE ATT&CK**: T1059.004 - Command and Scripting Interpreter: Unix Shell

**과정**:
1. log_file 파라미터에 명령어 삽입
2. 세미콜론(;)을 사용한 명령어 체이닝
3. 환경변수에서 FLAG 획득

**페이로드**:
```json
{"log_file": "/tmp/x; env"}
```

**결과**: Remote Code Execution (RCE)

---

## 📊 취약점 심각도 평가 (CVSS v3.1)

### **전체 체인 심각도**: Critical (CVSS 9.8)

| 취약점 | CVSS 점수 | 심각도 | 영향 |
|--------|----------|--------|------|
| Information Disclosure (Salt) | 5.3 | Medium | 정보 노출 |
| Cryptographic Failure | 7.5 | High | 세션 위조 |
| NoSQL Injection | 8.1 | High | 데이터 유출 |
| Command Injection | 9.8 | Critical | RCE |
| **Combined Chain** | **9.8** | **Critical** | **완전한 시스템 장악** |

### **CVSS Vector String**:
```
CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
```

- **AV (Attack Vector)**: Network (원격 공격 가능)
- **AC (Attack Complexity)**: Low (낮은 복잡도)
- **PR (Privileges Required)**: None (권한 불필요)
- **UI (User Interaction)**: None (사용자 상호작용 불필요)
- **S (Scope)**: Unchanged
- **C (Confidentiality)**: High (FLAG 획득)
- **I (Integrity)**: High (시스템 변조 가능)
- **A (Availability)**: High (서비스 중단 가능)

---

## 🎭 시나리오 (Realistic Attack Scenario)

### **배경**:
당신은 레드팀 침투 테스터로, 한 기업의 마이크로서비스 플랫폼에 대한 보안 평가를 수행하고 있습니다.
이 회사는 최근 v2.0으로 시스템을 업그레이드했지만, 레거시 API 엔드포인트가 제대로 폐기되지 않았다는
정보를 입수했습니다.

### **목표**:
1. 레거시 서비스의 취약점 발견
2. 관리자 권한 획득
3. 시스템 내부 데이터 접근
4. RCE를 통한 시스템 장악 증명 (FLAG 획득)

### **제약 조건**:
- 블랙박스 테스트 (소스코드 없음)
- 서비스 중단 금지 (DoS 공격 불가)
- 시간 제한: 2-2.5시간

### **공격 흐름**:

#### **Day 1 - 정찰 (30분)**
```
09:00 - 대상 URL 접속, 서비스 구조 파악
09:10 - robots.txt, HTML 소스 분석
09:15 - Red Herring 발견 (가짜 로그인 폼)
09:20 - API 발견: /api/v2/services
09:30 - Legacy 서비스 엔드포인트 발견
```

#### **Day 1 - 권한 획득 (70분)**
```
10:00 - Salt 힌트 발견, 브루트포스 스크립트 작성
10:20 - Salt 획득: "insane2"
10:30 - Flask Secret Key 유도 시도
10:40 - Secret Key 계산 성공
10:50 - 게스트 세션 생성 및 구조 분석
11:00 - Admin 세션 위조 성공
11:10 - Admin API 경로 추론: /api/admin/db/migrate
```

#### **Day 1 - 침투 및 RCE (30분)**
```
11:20 - NoSQL Injection 테스트
11:30 - $where 연산자 성공, "mode: advanced" 발견
11:35 - Command Injection 가능성 발견
11:40 - RCE 페이로드 작성
11:45 - FLAG 획득: FLAG{l3g4cy_s3rv1c3s_4r3_d4ng3r0us_wh3n_f0rg0tt3n}
```

---

## 🛡️ 방어 전략 (Mitigation)

### **1. Information Disclosure 방지**

**권장 사항**:
```python
# ❌ 나쁜 예
return jsonify({'salt': COMPANY_SALT})

# ✅ 좋은 예
# Salt를 환경변수나 Secrets Manager에서 안전하게 관리
# 레거시 엔드포인트 완전 제거
```

**도구**:
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes Secrets

---

### **2. Cryptographic Failures 방지**

**권장 사항**:
```python
# ❌ 나쁜 예
app.secret_key = hashlib.sha256(salt.encode()).hexdigest()[:32]

# ✅ 좋은 예
import secrets
app.secret_key = secrets.token_hex(32)  # 256-bit random key
# 또는
app.secret_key = os.urandom(32)
```

**추가 보안**:
- Secret Key Rotation (주기적 변경)
- 서버 측 세션 저장 (Redis, Memcached)
- JWT 사용 시 RS256 알고리즘 권장

---

### **3. Broken Access Control 방지**

**권장 사항**:
```python
# ❌ 나쁜 예
if session.get('role') != 'admin':
    return error()

# ✅ 좋은 예
@require_admin  # Decorator로 중앙 집중식 권한 검증
def admin_endpoint():
    # JWT 토큰 검증
    # RBAC (Role-Based Access Control)
    # 로그 기록
    pass
```

**추가 보안**:
- 다단계 인증 (MFA)
- IP 화이트리스트
- Rate Limiting

---

### **4. NoSQL Injection 방지**

**권장 사항**:
```python
# ❌ 나쁜 예
query_filter = request.json.get('filter', {})
results = db.users.find(query_filter)

# ✅ 좋은 예
from pymongo.errors import OperationFailure

# $where 연산자 완전 차단
BLOCKED_OPERATORS = ['$where', '$function', '$accumulator']

def sanitize_query(query):
    if not isinstance(query, dict):
        raise ValueError("Invalid query")

    for key in query.keys():
        if key in BLOCKED_OPERATORS:
            raise ValueError(f"Operator {key} is not allowed")

    return query

# 사용
query_filter = sanitize_query(request.json.get('filter', {}))
results = db.users.find(query_filter)
```

**MongoDB 설정**:
```javascript
// mongod.conf
security:
  javascriptEnabled: false  // JavaScript 완전 비활성화
```

---

### **5. Command Injection 방지**

**권장 사항**:
```python
# ❌ 나쁜 예
cmd = f"echo 'data' > {user_input}"
subprocess.run(cmd, shell=True)

# ✅ 좋은 예
import shlex
from pathlib import Path

# 1. 입력 검증
ALLOWED_PATH = Path('/var/log/app/')
log_path = ALLOWED_PATH / user_input

if not log_path.resolve().is_relative_to(ALLOWED_PATH):
    raise ValueError("Invalid path")

# 2. shell=False 사용
subprocess.run(['echo', 'data'],
               stdout=open(log_path, 'w'),
               shell=False)

# 3. 또는 Python 내장 함수 사용
with open(log_path, 'w') as f:
    f.write('data')
```

**입력 검증**:
```python
import re

def validate_log_filename(filename):
    # 알파벳, 숫자, 언더스코어, 대시만 허용
    if not re.match(r'^[a-zA-Z0-9_-]+\.log$', filename):
        raise ValueError("Invalid filename")

    # 경로 탐색 방지
    if '..' in filename or '/' in filename:
        raise ValueError("Path traversal detected")

    return filename
```

---

## 📚 학습 목표 (Learning Objectives)

본 문제를 통해 참가자는 다음을 학습합니다:

### **기술적 스킬**:
1. ✅ 웹 애플리케이션 정찰 기법
2. ✅ Dictionary-based Bruteforce 공격
3. ✅ 암호학적 추론 (Cryptographic Analysis)
4. ✅ Flask 세션 위조 기법
5. ✅ NoSQL Injection (MongoDB $where)
6. ✅ OS Command Injection
7. ✅ 취약점 체이닝 (Chaining)

### **보안 개념**:
1. ✅ OWASP Top 10 이해
2. ✅ MITRE ATT&CK Framework
3. ✅ CVSS 점수 평가
4. ✅ Defense in Depth
5. ✅ Secure Coding Practices

### **사고 방식**:
1. ✅ 블랙박스 테스트 접근법
2. ✅ 논리적 추론 능력
3. ✅ Red Herring 식별
4. ✅ 단계적 권한 상승 전략
5. ✅ 공격 체인 구성 능력

---

## 🔬 추가 연구 주제

### **심화 학습**:

1. **Flask Session Security**
   - itsdangerous 라이브러리 분석
   - Session Cookie 구조 리버싱
   - HMAC 서명 메커니즘

2. **NoSQL Security**
   - MongoDB Aggregation Pipeline 공격
   - SSJI (Server-Side JavaScript Injection)
   - NoSQL Injection in Different Databases (CouchDB, Cassandra)

3. **Blind RCE Techniques**
   - Time-based Blind Command Injection
   - Out-of-Band Data Exfiltration (DNS, HTTP)
   - File-based Blind RCE

4. **Modern Attack Techniques**
   - GraphQL Injection
   - API Rate Limiting Bypass
   - JWT Algorithm Confusion Attack

---

## 📖 참고 자료

### **OWASP 리소스**:
- [OWASP Top 10 (2021)](https://owasp.org/Top10/)
- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [OWASP NoSQL Injection](https://owasp.org/www-community/Injection_Flaws)

### **CVE 데이터베이스**:
- [NVD (National Vulnerability Database)](https://nvd.nist.gov/)
- [CVE Details](https://www.cvedetails.com/)
- [Exploit Database](https://www.exploit-db.com/)

### **MITRE ATT&CK**:
- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- [Web Application Tactics](https://attack.mitre.org/tactics/TA0001/)

### **도구**:
- [flask-unsign](https://github.com/Paradoxis/Flask-Unsign)
- [Burp Suite](https://portswigger.net/burp)
- [NoSQLMap](https://github.com/codingo/NoSQLMap)

---

## 🏆 난이도 및 평가

**난이도**: DreamHack Level 8 (Hard)
**예상 풀이 시간**: 130-150분 (2-2.5시간)
**필요 지식**:
- Python 중급
- 웹 보안 중급
- 암호학 기초
- NoSQL 기초

**평가 기준**:
- ✅ 브루트포스 전략 (25%)
- ✅ 암호학적 추론 (25%)
- ✅ NoSQL Injection (20%)
- ✅ Command Injection (20%)
- ✅ 전체 체이닝 (10%)

---

## 📝 제작 정보

**버전**: V4.0 (Level 8 Hard Mode)
**제작일**: 2025-10-30
**난이도 조정**: Level 6-7 → Level 8
**주요 변경사항**:
- Salt 직접 노출 → 힌트 기반 브루트포스
- system_info 제거 → Flask 지식 기반 추론
- NoSQL 힌트 제거 → 직접 테스트 필요
- Red Herring 강화

**테스트 환경**:
- Python 3.9+
- Flask 2.0+
- MongoDB 4.4
- Docker Compose

---

## ⚠️ 법적 고지 (Legal Disclaimer)

본 CTF 문제는 **교육 목적**으로만 제작되었습니다.

**허용되는 사용**:
- ✅ CTF 대회 출제
- ✅ 보안 교육 및 훈련
- ✅ 침투 테스트 학습
- ✅ 보안 연구

**금지되는 사용**:
- ❌ 실제 시스템에 대한 무단 공격
- ❌ 악의적 목적의 사용
- ❌ 법적 허가 없는 침투 테스트

**책임 제한**:
본 문제를 사용하여 발생하는 모든 법적 문제는 사용자의 책임입니다.
제작자는 부적절한 사용에 대해 책임을 지지 않습니다.

---

**제작자**: Claude Code Assistant
**라이선스**: MIT License
**문의**: GitHub Issues
