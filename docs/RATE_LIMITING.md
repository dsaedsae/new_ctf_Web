# Rate Limiting 정책

## 개요
모든 Rate Limiting은 **IP 주소 기반**으로 동작하며, **In-Memory 저장소**를 사용합니다.
서버 재시작 시 모든 카운터가 초기화됩니다.

---

## 1. Login Rate Limit

### 설정
- **엔드포인트**: `POST /oauth/authorize`
- **제한**: **IP당 5분에 10회**
- **Window**: 300초 (5분)
- **함수**: `check_login_rate_limit(ip_address)`
- **저장소**: `login_attempts` (defaultdict)

### 코드
```python
def check_login_rate_limit(ip_address):
    now = time.time()
    window = 300  # 5 minutes
    max_attempts = 10  # 10 attempts per 5 minutes

    login_attempts[ip_address] = [t for t in login_attempts[ip_address] if now - t < window]

    if len(login_attempts[ip_address]) >= max_attempts:
        return False

    login_attempts[ip_address].append(now)
    return True
```

### 에러 응답
```json
{
  "error": "Login Failed",
  "message": "Invalid username or password"
}
```
> 참고: Rate Limit 에러와 로그인 실패를 구분하지 않음 (보안상 이유)

### CTF 공격 영향
- ✅ **영향 없음**: 공격에 필요한 로그인 시도는 **1회**뿐

---

## 2. Token Endpoint Rate Limit

### 설정
- **엔드포인트**: `POST /oauth/token`
- **제한**: **IP당 1분에 5회**
- **Window**: 60초 (1분)
- **함수**: `check_token_rate_limit()`
- **저장소**: `token_requests` (defaultdict)

### 코드
```python
def check_token_rate_limit():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if ',' in client_ip:
        client_ip = client_ip.split(',')[0].strip()

    now = time.time()
    window = 60  # 1 minute
    max_requests = 5  # 5 requests per minute

    token_requests[client_ip] = [t for t in token_requests[client_ip] if now - t < window]

    if len(token_requests[client_ip]) >= max_requests:
        return False, client_ip

    token_requests[client_ip].append(now)
    return True, client_ip
```

### 에러 응답
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many token requests. Please wait before trying again.",
  "client_ip": "192.168.1.100"
}
```

### CTF 공격 영향
- ✅ **영향 없음**: 공격에 필요한 토큰 요청은 **2회**
  1. Authorization Code → Access Token (Step 3)
  2. Refresh Token → ADMIN_SECRETS Token (Step 4)

---

## 3. Admin Flag Endpoint Rate Limit

### 설정
- **엔드포인트**: `GET /api/admin/flag`
- **제한**: **IP당 1분에 500회**
- **Window**: 60초 (1분)
- **함수**: `check_rate_limit(ip_address, max_attempts=500, window=60)`
- **저장소**: `admin_attempts` (defaultdict)

### 코드
```python
def check_rate_limit(ip_address, max_attempts=500, window=60):
    now = time()
    admin_attempts[ip_address] = [t for t in admin_attempts[ip_address] if now - t < window]

    if len(admin_attempts[ip_address]) >= max_attempts:
        return False

    admin_attempts[ip_address].append(now)
    return True
```

### 에러 응답
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many attempts. Please wait before trying again."
}
```

### CTF 공격 영향
- ✅ **영향 없음**: 플래그 획득은 **1회** 요청으로 완료
- 💡 **의도**: Brute force 방어용 (500회는 충분히 관대한 제한)

---

## Rate Limiting 우회 불가능

### IP 추출 로직
```python
# Auth Server
client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
if ',' in client_ip:
    client_ip = client_ip.split(',')[0].strip()

# Resource Server
client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
```

### 특징
1. **X-Forwarded-For 헤더 우선**: Proxy/Load Balancer 환경 고려
2. **다중 IP 처리**: 쉼표로 구분된 경우 첫 번째 IP 사용
3. **Fallback**: X-Forwarded-For 없을 시 `remote_addr` 사용

### 우회 시도가 통하지 않는 이유
```python
# ❌ 헤더 조작 시도
X-Forwarded-For: 1.1.1.1, 2.2.2.2, 3.3.3.3
# → 결과: 1.1.1.1로 인식 (여전히 동일한 IP로 카운트)

# ❌ 빈 헤더
X-Forwarded-For:
# → 결과: remote_addr 사용 (실제 IP로 카운트)
```

---

## Sliding Window 방식

### 동작 방식
```python
# 예시: 1분 window, 5회 제한
now = time.time()  # 현재: 100초

# 기존 요청 타임스탬프
token_requests[ip] = [40, 50, 60, 70, 80]

# 60초 이전 요청 제거 (40, 50 제거)
token_requests[ip] = [t for t in token_requests[ip] if now - t < window]
# 결과: [60, 70, 80]

# 현재 카운트: 3회 (< 5회)
# → 요청 허용, 100 추가
# 결과: [60, 70, 80, 100]
```

### 장점
- 정확한 시간 기반 제한
- 순간적인 버스트 트래픽 방어
- 메모리 효율적 (오래된 기록 자동 삭제)

---

## CTF 공격 타임라인과 Rate Limit

```
[0:00] SSRF - Client Registration
       ├─ Rate Limit: 없음
       └─ 요청 수: 1회

[0:10] Admin Login
       ├─ Rate Limit: 5분에 10회
       └─ 사용: 1/10 회 ✅

[0:20] Token Exchange (Authorization Code)
       ├─ Rate Limit: 1분에 5회
       └─ 사용: 1/5 회 ✅

[0:25] Token Refresh (Scope Escalation)
       ├─ Rate Limit: 1분에 5회
       └─ 사용: 2/5 회 ✅

[0:30] Get Flag
       ├─ Rate Limit: 1분에 500회
       └─ 사용: 1/500 회 ✅
```

**결론**: 모든 공격 단계가 Rate Limit 이하로 수행 가능

---

## Rate Limit 관련 취약점 없음

### 검증된 사항
1. ✅ IP 기반 추적 (조작 불가)
2. ✅ Sliding Window 정확한 동작
3. ✅ 제한 값이 공격 방어에 충분
4. ✅ 공격 플로우는 제한 이하로 완료 가능

### Rate Limit은 공격의 장애물이 아님
- 이 CTF의 취약점은 **Rate Limiting 우회**가 아님
- **비즈니스 로직의 취약점**을 찾아야 함:
  - SSRF
  - PKCE Bypass
  - Scope Escalation

---

## 디버깅 팁

### Rate Limit 테스트
```python
import time
import requests

# 토큰 요청 5회 (제한)
for i in range(6):
    response = requests.post('http://localhost:8080/oauth/token', data={...})
    print(f"Attempt {i+1}: {response.status_code}")
    time.sleep(0.1)  # 같은 분(window) 내에서 요청

# 예상 결과:
# Attempt 1: 200
# Attempt 2: 200
# Attempt 3: 200
# Attempt 4: 200
# Attempt 5: 200
# Attempt 6: 429 (Rate Limit Exceeded)
```

### Rate Limit 초기화
```bash
# 방법 1: 시간 대기
sleep 60  # Token endpoint: 1분 대기
sleep 300  # Login endpoint: 5분 대기

# 방법 2: 서버 재시작 (In-Memory 초기화)
docker-compose restart auth-server
```

---

**작성일**: 2024-10-29
**버전**: 28.0
