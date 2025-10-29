# Difficulty Tuning Guide
## How to Increase Solve Time for Advanced Players (Without Adding Vulnerabilities)

**Target Audience**: CTF organizers who want to adjust difficulty
**Current Difficulty**: Level 7-8 (60-80 minutes for intermediate, 20-30 minutes for advanced)
**Goal**: Extend advanced player solve time to 45-60+ minutes

---

## 🎯 Philosophy

**Rule**: Do NOT add new vulnerabilities or change the core exploit chain
**Method**: Make each stage more time-consuming through:
- Reducing hints
- Increasing obfuscation
- Adding noise/distractions
- Requiring more enumeration

---

## 📊 Current Solve Time Breakdown (Advanced Players)

```
Stage 1: Service Discovery           2-3 minutes
Stage 2-3: Information Disclosure    5-7 minutes
Stage 4: Secret Verification         3-5 minutes
Stage 5: Session Forgery             5-7 minutes
Stage 6: RCE Chain                   5-8 minutes
────────────────────────────────────────────────
Total:                              20-30 minutes
```

**Target**: 45-60 minutes

---

## 🔧 Method 1: Reduce Information Disclosure Hints

### Current Code (app.py:139-154)
```python
@app.route('/api/legacy/system_info', methods=['GET'])
def system_info():
    return jsonify({
        'framework': 'Flask',                    # ← Too obvious
        'session_backend': 'SecureCookie',       # ← Gives away the approach
        'crypto': {
            'library': 'hashlib',                # ← Direct hint
            'algorithm': 'sha256'                # ← Exact algorithm
        },
        'notes': 'Legacy system using 32-char keys'  # ← Key length hint
    })
```

### Hardened Version (Adds +10 minutes)
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

**Impact**:
- Players must figure out Flask independently (framework detection)
- Must research Flask session mechanisms
- Must test different hash algorithms (md5, sha1, sha256, sha512)
- Must try different key lengths (16, 24, 32, 64)

**Estimated Time Increase**: +10-15 minutes

---

## 🔧 Method 2: Obfuscate Salt Endpoint

### Current Code (app.py:130-137)
```python
@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    """
    Legacy endpoint exposing salt value

    VULNERABILITY: Information disclosure
    """
    return jsonify({'salt': COMPANY_SALT})
```

### Option A: Indirect Response (Adds +5 minutes)
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
            'derivation_material': COMPANY_SALT,  # ← Renamed field
            'timeout': 86400
        },
        'features': {
            'legacy_mode': True,
            'api_version': '1.0'
        }
    })
```

**Impact**: Players must parse nested JSON and identify relevant field

### Option B: Base64 Encoded (Adds +3 minutes)
```python
import base64

@app.route('/api/legacy/get_salt', methods=['GET'])
def get_salt():
    encoded = base64.b64encode(COMPANY_SALT.encode()).decode()
    return jsonify({'config_data': encoded})
```

**Impact**: Players must recognize and decode base64

### Option C: Split Across Multiple Endpoints (Adds +8 minutes)
```python
@app.route('/api/legacy/config/part1', methods=['GET'])
def config_part1():
    return jsonify({'data': COMPANY_SALT[:len(COMPANY_SALT)//2]})

@app.route('/api/legacy/config/part2', methods=['GET'])
def config_part2():
    return jsonify({'data': COMPANY_SALT[len(COMPANY_SALT)//2:]})
```

**Impact**: Players must discover both endpoints and concatenate values

**Estimated Time Increase**: +3-8 minutes depending on option

---

## 🔧 Method 3: Remove Endpoint Enumeration

### Current Code (app.py:85-124)
```python
@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """Enumerate endpoints for a specific service"""
    endpoints_map = {
        'legacy': [
            {
                'path': '/api/legacy/get_salt',      # ← Lists all endpoints
                'method': 'GET',
                'description': 'Legacy utility'
            },
            # ...
        ]
    }
    return jsonify({'service': service, 'endpoints': endpoints_map[service]})
```

### Hardened Version (Adds +15 minutes)
```python
@app.route('/api/v2/services/<service>/endpoints', methods=['GET'])
def list_endpoints(service):
    """Enumerate endpoints for a specific service"""

    if service not in ['auth', 'api', 'legacy']:
        return jsonify({'error': 'Service not found'}), 404

    # Return generic information without exact paths
    return jsonify({
        'service': service,
        'status': 'deprecated' if service == 'legacy' else 'active',
        'note': 'Endpoint documentation unavailable for deprecated services'
    })
```

**Impact**:
- Players must use directory brute-forcing (gobuster, ffuf, dirbuster)
- Must guess common endpoint patterns:
  - `/api/legacy/config`
  - `/api/legacy/info`
  - `/api/legacy/status`
  - `/api/legacy/get_*`
  - `/api/legacy/system_*`

**Wordlist Suggestions**:
- `common.txt` (SecLists)
- `api-endpoints.txt`
- Custom generated list

**Estimated Time Increase**: +15-20 minutes

---

## 🔧 Method 4: Increase Secret Complexity

### Current Implementation
```python
# app.py:40
app.secret_key = hashlib.sha256(COMPANY_SALT.encode()).hexdigest()[:32]
```

### Option A: Add Multiple Hash Rounds (Adds +5 minutes)
```python
def derive_secret(salt):
    result = salt.encode()
    for _ in range(1000):  # PBKDF2-like
        result = hashlib.sha256(result).digest()
    return result.hex()[:32]

app.secret_key = derive_secret(COMPANY_SALT)
```

**Hint to provide**: "System uses key strengthening"

**Impact**: Players must figure out the iteration count

### Option B: Key Derivation Function (Adds +10 minutes)
```python
import hashlib

def custom_kdf(salt):
    # Custom derivation: sha256(sha256(salt) + salt)
    first = hashlib.sha256(salt.encode()).hexdigest()
    second = hashlib.sha256((first + salt).encode()).hexdigest()
    return second[:32]

app.secret_key = custom_kdf(COMPANY_SALT)
```

**Hint to provide in system_info**: "Uses nested hash construction"

**Impact**: Players must reverse engineer the derivation

**WARNING**: Don't make it too obscure or it becomes guessy

**Estimated Time Increase**: +5-10 minutes

---

## 🔧 Method 5: Add Noise to Service Discovery

### Current Code
```python
@app.route('/api/v2/services', methods=['GET'])
def list_services():
    return jsonify({
        'services': [
            {'name': 'auth', ...},
            {'name': 'api', ...},
            {'name': 'legacy', ...}  # ← Only 3 services
        ]
    })
```

### Hardened Version (Adds +5 minutes)
```python
@app.route('/api/v2/services', methods=['GET'])
def list_services():
    return jsonify({
        'services': [
            {'name': 'auth', 'status': 'active', ...},
            {'name': 'api', 'status': 'active', ...},
            {'name': 'billing', 'status': 'active', ...},      # ← Noise
            {'name': 'reporting', 'status': 'active', ...},   # ← Noise
            {'name': 'legacy', 'status': 'deprecated', ...},
            {'name': 'backup', 'status': 'maintenance', ...}, # ← Noise
            {'name': 'logs', 'status': 'active', ...},        # ← Noise
        ]
    })
```

**Impact**: Players must investigate multiple services to find vulnerable one

**Implementation**:
- Add fake endpoints for noise services that return 404 or "Not Implemented"
- Make players waste time exploring dead ends

**Estimated Time Increase**: +5-7 minutes

---

## 🔧 Method 6: Obfuscate NoSQL Injection Hints

### Current Code (app.py:242-253)
```python
except pymongo.errors.OperationFailure as e:
    error_msg = str(e).lower()

    if 'javascript' in error_msg or 'where' in error_msg:
        return jsonify({
            'error': 'Query execution failed',
            'hint': 'Check MongoDB JavaScript configuration'  # ← Too helpful
        }), 400
```

### Hardened Version (Adds +5 minutes)
```python
except pymongo.errors.OperationFailure as e:
    # Generic error without hints
    app.logger.error(f"MongoDB error: {str(e)}")
    return jsonify({
        'error': 'Database query failed',
        'code': 'DB_ERROR_001'
    }), 400
```

**Impact**: Players must try different NoSQL injection techniques without hints:
- `$where` operator
- `$regex` operator
- `$ne` operator
- JavaScript injection

**Estimated Time Increase**: +5-8 minutes

---

## 🔧 Method 7: Require Rate Limiting Bypass

### Add to app.py (Adds +10 minutes)
```python
from functools import wraps
from time import time

# Simple rate limiter
request_times = {}

def rate_limit(max_requests=5, window=60):
    """Rate limit: max_requests per window seconds"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time()

            if ip not in request_times:
                request_times[ip] = []

            # Clean old requests
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

# Apply to admin endpoint
@app.route('/api/admin/db/migrate', methods=['POST'])
@rate_limit(max_requests=10, window=60)  # 10 requests per minute
def db_migrate():
    # ... existing code ...
```

**Impact**: Players must:
- Detect rate limiting
- Add delays to their exploit
- Or use multiple IPs/proxies

**Note**: Keep limits reasonable (don't make it too frustrating)

**Estimated Time Increase**: +8-12 minutes

---

## 🔧 Method 8: Enable BLIND_RCE Mode

### Current Code
```python
# .env
BLIND_RCE=false  # Output is returned
```

### Hardened Version
```python
# .env
BLIND_RCE=true  # No output returned
```

**Impact** (app.py:219-232):
- Command output is NOT returned
- Players must use blind exploitation techniques:
  - DNS exfiltration
  - Time-based extraction
  - HTTP callbacks
  - OOB (Out-of-Band) techniques

**Reference**: See `solution/exploit_blind.py` for techniques

**Estimated Time Increase**: +15-25 minutes

---

## 🔧 Method 9: Reduce Session Cookie Lifetime

### Current Code (app.py:52)
```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)  # 24 hours
```

### Hardened Version
```python
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)  # 10 minutes
```

**Impact**:
- Players must work faster or restart stages
- Encourages automation/scripting
- Adds time pressure

**Note**: Don't make it too short (<5 minutes) or it becomes frustrating

**Estimated Time Increase**: +5-10 minutes (indirect)

---

## 🔧 Method 10: Rename Obvious Variables

### Current Code
```python
query_filter = request.json.get('filter', {})     # ← Obvious
log_file = request.json.get('log_file', '/dev/null')  # ← Direct hint
```

### Hardened Version
```python
query_filter = request.json.get('q', {})          # ← Less obvious
log_file = request.json.get('output', '/dev/null')  # ← Neutral name
```

**Also rename in documentation**:
```python
# Help endpoint (if you add one)
return jsonify({
    'parameters': {
        'q': 'Query object for database',
        'output': 'Output destination'
    }
})
```

**Impact**: Players must figure out parameter names through:
- Fuzzing
- Reading error messages
- Guessing common names

**Estimated Time Increase**: +3-5 minutes

---

## 📋 Recommended Combinations

### Moderate Increase (40-45 minutes total)
1. ✅ Method 2 (Option A): Indirect salt response (+5 min)
2. ✅ Method 5: Add noise to service discovery (+5 min)
3. ✅ Method 6: Remove NoSQL injection hints (+5 min)
4. ✅ Method 10: Rename obvious variables (+3 min)

**Total**: +18 minutes → ~38-48 minutes solve time

---

### Significant Increase (50-60 minutes total)
1. ✅ Method 1: Reduce information disclosure hints (+10 min)
2. ✅ Method 3: Remove endpoint enumeration (+15 min)
3. ✅ Method 5: Add noise to service discovery (+5 min)
4. ✅ Method 6: Remove NoSQL injection hints (+5 min)
5. ✅ Method 8: Enable BLIND_RCE (+20 min)

**Total**: +55 minutes → ~75-85 minutes solve time

---

### Expert Mode (70-90 minutes total)
1. ✅ Method 1: Reduce information disclosure hints (+10 min)
2. ✅ Method 3: Remove endpoint enumeration (+15 min)
3. ✅ Method 4 (Option B): Complex key derivation (+10 min)
4. ✅ Method 5: Add noise to service discovery (+5 min)
5. ✅ Method 6: Remove NoSQL injection hints (+5 min)
6. ✅ Method 7: Rate limiting (+10 min)
7. ✅ Method 8: Enable BLIND_RCE (+20 min)
8. ✅ Method 10: Rename obvious variables (+3 min)

**Total**: +78 minutes → ~98-108 minutes solve time

---

## ⚠️ Important Warnings

### DO NOT Do These:
1. ❌ Don't make it impossible (avoid multiple levels of encoding/encryption)
2. ❌ Don't add new vulnerabilities (changes the intended solution)
3. ❌ Don't break the exploit chain (each stage must still lead to next)
4. ❌ Don't make it "guessy" (avoid requiring exact magical values)
5. ❌ Don't remove all hints (balance is key)

### Keep These Principles:
1. ✅ Every stage should still be solvable with enumeration/research
2. ✅ Hints should be subtle but present
3. ✅ Multiple approaches should be possible (e.g., different hash algorithms)
4. ✅ Error messages should be informative enough to debug
5. ✅ Exploit should be automatable (scriptable)

---

## 🧪 Testing After Changes

After implementing difficulty changes, test with:

```bash
# 1. Manual solve (time yourself)
time manual_solve.sh

# 2. Automated exploit (should still work with modifications)
cd solution
time python3 exploit.py http://localhost:5000

# 3. Verify no unintended bypasses
python3 test_security.py

# 4. Check for frustration points
# - Are error messages helpful enough?
# - Can stages be solved with reasonable effort?
# - Is there a clear progression?
```

**Target Metrics**:
- Manual solve: 50-70 minutes for advanced players
- Automated exploit: Should complete (may need updates)
- No dead ends or impossible stages
- Frustration level: Challenging but fair

---

## 📊 Difficulty Matrix

| Method | Time Added | Skill Required | Frustration Risk | Recommended |
|--------|-----------|----------------|------------------|-------------|
| 1. Reduce hints | +10 min | Research | Low | ✅ Yes |
| 2. Obfuscate salt | +5 min | JSON parsing | Low | ✅ Yes |
| 3. Remove enum | +15 min | Fuzzing tools | Medium | ⚠️ Maybe |
| 4. Complex KDF | +10 min | Crypto knowledge | High | ⚠️ Risky |
| 5. Add noise | +5 min | Patience | Low | ✅ Yes |
| 6. Remove NoSQL hints | +5 min | NoSQL experience | Medium | ✅ Yes |
| 7. Rate limiting | +10 min | Scripting | Medium | ⚠️ Maybe |
| 8. Blind RCE | +20 min | Advanced RCE | High | ⚠️ Expert only |
| 9. Short session | +5 min | Speed | High | ❌ Not recommended |
| 10. Rename vars | +3 min | Fuzzing | Low | ✅ Yes |

**Legend**:
- ✅ Safe to implement
- ⚠️ Use with caution
- ❌ Avoid unless expert audience

---

## 🎯 Quick Implementation Guide

### Step 1: Choose Your Target Difficulty
```
Easy Mode:      20-30 minutes (current)
Medium Mode:    40-50 minutes (methods 2, 5, 6, 10)
Hard Mode:      60-75 minutes (methods 1, 3, 5, 6, 8)
Expert Mode:    90+ minutes (all methods)
```

### Step 2: Make Code Changes
```bash
# Backup original
cp app.py app.py.original

# Edit app.py with chosen methods
nano app.py

# Update .env for difficulty
nano .env
```

### Step 3: Test Thoroughly
```bash
# Build and test
docker-compose up -d
python3 solution/exploit.py http://localhost:5000

# Manual verification
curl http://localhost:5000/api/v2/services
# ... test each stage ...
```

### Step 4: Update Documentation
```bash
# Update README.md with new difficulty rating
# Update TESTING.md with new procedures
# Update solution/exploit.py if needed
```

---

## 🔄 Reverting Changes

If you need to revert:

```bash
# Restore original
cp app.py.original app.py

# Reset environment
cp .env.example .env
# Edit COMPANY_SALT

# Rebuild
docker-compose down -v
docker-compose build
docker-compose up -d
```

---

## 📞 Support

If you implement these changes and encounter issues:
1. Check TESTING.md for troubleshooting
2. Verify MongoDB JavaScript is still enabled
3. Test each stage individually
4. Review logs: `docker-compose logs -f web`

---

**Last Updated**: 2025-01-XX
**Version**: 1.0
**Applies to**: Legacy Microservice CTF V3.0
