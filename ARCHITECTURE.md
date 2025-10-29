# Project Structure and File Documentation

## 📁 Complete File Structure

```
ctf-legacy-microservice/
├── Core Application
│   ├── app.py                      # Main Flask application
│   ├── init_db.py                  # Database initialization script
│   └── requirements.txt            # Python dependencies
│
├── Docker Infrastructure
│   ├── Dockerfile                  # Container image definition
│   ├── docker-compose.yml          # Multi-container orchestration
│   └── docker-entrypoint.sh        # Container startup script
│
├── Configuration Files
│   ├── .env.example               # Environment variables template
│   ├── .gitignore                 # Git exclusions
│   ├── .gitattributes             # Git line ending config
│   └── .dockerignore              # Docker build exclusions
│
├── Documentation
│   ├── README.md                   # Challenge description for participants
│   └── TESTING.md                  # Local testing checklist
│
└── Solution Files (excluded from Docker)
    ├── requirements.txt            # Exploit dependencies
    ├── exploit.py                  # Complete automated exploit
    ├── exploit_blind.py            # Blind RCE exploitation demo
    └── WRITEUP.md                  # Internal solution guide
```

---

## 🔧 Core Application Files

### 1. app.py (9.2KB)
**Purpose**: Main Flask web application with intentional vulnerabilities

**Components**:
- **Lines 1-47**: Configuration and initialization
  - Environment variable loading (COMPANY_SALT, FLAG, MONGO_URI)
  - Flask secret key derivation from COMPANY_SALT
  - MongoDB connection setup
  - Security settings (session cookies, timeouts)

- **Lines 49-124**: Stage 1 - Service Discovery
  - `/api/v2/services` - Lists available services (auth, api, legacy)
  - `/api/v2/services/<service>/endpoints` - Enumerates service endpoints
  - Purpose: Allows attackers to discover the "legacy" service

- **Lines 126-154**: Stage 2-3 - Information Disclosure
  - `/api/legacy/get_salt` - **VULNERABILITY**: Exposes COMPANY_SALT
  - `/api/legacy/system_info` - Provides hints about secret derivation
  - Purpose: Enables secret key calculation

- **Lines 156-172**: Stage 4 - Session Verification
  - `/api/auth/guest` - Creates guest session for testing
  - Purpose: Allows attackers to verify their secret key hypothesis

- **Lines 174-260**: Stage 6 - RCE Chain
  - `/api/admin/db/migrate` - Admin-only database migration endpoint
  - **VULNERABILITY 1**: NoSQL Injection via `$where` operator (line 202)
  - **VULNERABILITY 2**: Command Injection via `log_file` parameter (line 209)
  - Purpose: Final exploitation target with chained vulnerabilities

- **Lines 262-303**: Utility Endpoints
  - `/health` - Health check with MongoDB JavaScript verification
  - `/` - Root endpoint with API information

**Security Features**:
- Line 33-37: Validates COMPANY_SALT is set (prevents default value bypass)
- Line 192: Admin role check (prevents direct access)
- Line 205: Conditional RCE (requires NoSQL injection success)
- Line 216: Timeout protection (5 seconds max)
- Line 189: BLIND_RCE mode for increased difficulty

**Key Variables**:
- `COMPANY_SALT`: Secret material for session key derivation
- `FLAG`: The CTF flag to be captured
- `BLIND_RCE`: Toggles command output visibility

---

### 2. init_db.py (4.3KB)
**Purpose**: Initialize MongoDB with test data and verify JavaScript support

**Functions**:
- `wait_for_mongodb()` (Lines 17-37)
  - Waits up to 60 seconds for MongoDB to become available
  - Uses retry logic with 2-second intervals
  - Returns MongoClient instance when connected

- `verify_javascript_enabled()` (Lines 39-77)
  - **CRITICAL FUNCTION**: Tests if MongoDB JavaScript is enabled
  - Inserts test document and runs `$where` query
  - Container **fails to start** if JavaScript is disabled
  - Provides detailed error messages for debugging

- `init_database()` (Lines 79-116)
  - Clears existing data
  - Inserts 4 dummy user documents:
    - john.doe (developer)
    - jane.smith (analyst)
    - admin (admin) ← Used in NoSQL injection
    - legacy.service (deprecated)
  - Verifies insertion succeeded

- `main()` (Lines 118-151)
  - Orchestrates the initialization sequence
  - Returns exit code (0=success, 1=failure)
  - Called by docker-entrypoint.sh

**Why This Matters**:
- NoSQL injection requires MongoDB JavaScript to be enabled
- Without it, the `$where` operator won't work
- This validation ensures the CTF challenge is solvable

---

### 3. requirements.txt (5 lines)
**Purpose**: Python dependencies for the Flask application

**Packages**:
```
Flask==3.0.0          # Web framework
pymongo==4.6.1        # MongoDB driver
gunicorn==21.2.0      # Production WSGI server
gevent==23.9.1        # Async worker for Gunicorn
itsdangerous==2.1.2   # Session signing (Flask dependency)
```

**Version Pinning**:
- All versions are pinned for reproducibility
- Tested and verified to work together
- No known vulnerabilities in these specific versions

---

## 🐳 Docker Infrastructure

### 4. Dockerfile (1.5KB)
**Purpose**: Builds the container image with security best practices

**Build Stages**:
- **Lines 1-6**: Base image and metadata
  - Uses `python:3.9-slim` for small footprint
  - Labels for identification

- **Lines 8-15**: Security setup
  - Creates non-root user `ctfuser` (UID 1000)
  - Sets working directory to `/app`
  - Enables unbuffered Python output

- **Lines 17-22**: System dependencies
  - Installs gcc and python3-dev (required for gevent)
  - Cleans up apt cache to reduce image size

- **Lines 24-27**: Python dependencies
  - Copies and installs requirements.txt
  - Uses pip cache for faster rebuilds

- **Lines 29-42**: Application setup
  - Copies only necessary files (app.py, init_db.py, docker-entrypoint.sh)
  - Fixes CRLF line endings (Windows compatibility)
  - Makes entrypoint executable
  - Sets file ownership to ctfuser

- **Lines 44-52**: Final configuration
  - Switches to non-root user
  - Exposes port 5000
  - Defines health check using urllib (no external deps)
  - Health check verifies `javascript_enabled: true`

**Security Highlights**:
- Non-root execution (Line 42)
- Minimal file copying (Line 30)
- Health check validation (Line 48-52)

---

### 5. docker-compose.yml (1.3KB)
**Purpose**: Orchestrates multi-container deployment

**Services**:

#### web (Lines 5-23)
- Builds from local Dockerfile
- Exposes port (default 5000, configurable via CTF_PORT)
- Depends on MongoDB being healthy
- **Environment Variables**:
  - `MONGO_URI`: MongoDB connection string
  - `COMPANY_SALT`: **REQUIRED** (no default value)
  - `FLAG`: The CTF flag
  - `BLIND_RCE`: Difficulty toggle
- Uses Dockerfile's HEALTHCHECK (no duplicate)

#### db (Lines 25-42)
- Uses official `mongo:7.0` image
- **CRITICAL LINE 30**: Enables JavaScript with `javascriptEnabled=true`
- Persists data in named volume `mongo_data`
- Health check using mongosh/mongo commands
- Aggressive health check (5s interval, 12 retries)

**Networks & Volumes**:
- Custom bridge network `ctf_network`
- Named volume `ctf_mongodb_data` for persistence

**Why This Configuration**:
- Line 19: `${COMPANY_SALT:?...}` enforces environment variable
- Line 30: JavaScript is essential for NoSQL injection
- Health checks ensure proper startup order

---

### 6. docker-entrypoint.sh (800 bytes)
**Purpose**: Container initialization script

**Execution Flow**:
```bash
Step 1: Run init_db.py
   ├─ Connects to MongoDB
   ├─ Verifies JavaScript enabled
   ├─ Populates test data
   └─ Exits if any step fails

Step 2: Start Gunicorn
   ├─ Binds to 0.0.0.0:5000
   ├─ Uses 4 gevent workers
   ├─ 30-second timeout
   └─ Logs to stdout/stderr
```

**Key Features**:
- Line 13-17: Database initialization with error handling
- Line 21-28: Gunicorn configuration
  - `--worker-class gevent`: Async I/O support
  - `--workers 4`: Handles concurrent requests
  - `--timeout 30`: Prevents hung requests
  - `exec`: Replaces shell process (proper signal handling)

**Error Handling**:
- If init_db.py fails, container exits immediately
- Prevents running with invalid database state

---

## ⚙️ Configuration Files

### 7. .env.example (14 lines)
**Purpose**: Template for environment configuration

**Variables**:
```bash
CTF_PORT=5000                    # Host port binding
COMPANY_SALT=                    # REQUIRED: Random value
FLAG=FLAG{...}                   # CTF flag
BLIND_RCE=false                  # Difficulty toggle
```

**Usage**:
```bash
cp .env.example .env
nano .env  # Set COMPANY_SALT
docker-compose up -d
```

**Security Note**:
- Line 10: COMPANY_SALT is **intentionally empty**
- Forces operators to set a unique value
- Prevents predictable default values

---

### 8. .gitignore (23 lines)
**Purpose**: Excludes files from git repository

**Categories**:
- Python artifacts: `__pycache__/`, `*.pyc`
- Virtual environments: `venv/`, `env/`
- IDE files: `.vscode/`, `.idea/`
- Secrets: `.env` ← Most important
- OS files: `.DS_Store`, `Thumbs.db`
- Docker volumes: `mongo_data/`

**Why This Matters**:
- Prevents committing `.env` with secrets
- Keeps repository clean
- Protects sensitive configuration

---

### 9. .gitattributes (2 lines)
**Purpose**: Ensures consistent line endings

```
*.sh text eol=lf
docker-entrypoint.sh text eol=lf
```

**Why This Matters**:
- Shell scripts with CRLF (Windows) won't execute on Linux
- Forces LF line endings for `.sh` files
- Prevents "bad interpreter" errors

---

### 10. .dockerignore (35 lines)
**Purpose**: Excludes files from Docker build context

**Key Exclusions**:
- `solution/` ← Prevents exploit code in container
- `.env` ← Prevents secrets in image
- `.env.example` ← Prevents hints in image
- `.git/` ← Reduces image size
- Development files: `.vscode/`, `*.log`

**Security Impact**:
- Attackers cannot read exploit code from container
- No leaked environment variables in image layers
- Smaller attack surface

---

## 📚 Documentation Files

### 11. README.md (30 lines)
**Purpose**: Challenge description for CTF participants

**Contents**:
- Challenge scenario (legacy microservices)
- Access information (target URL)
- Hints (4 subtle clues)
- Flag format
- Difficulty rating (4/5 stars)

**Intentional Ambiguity**:
- Doesn't reveal exact vulnerabilities
- Encourages exploration and enumeration
- Provides just enough guidance

---

### 12. TESTING.md (367 lines)
**Purpose**: Comprehensive testing checklist for operators

**Sections**:
1. Pre-deployment setup
2. Build and health checks
3. Manual vulnerability testing (all 6 stages)
4. Automated exploit validation
5. Security verification (no shortcuts)
6. Performance testing
7. Troubleshooting guide
8. Success criteria

**Target Audience**: CTF organizers, not participants

---

## 🎯 Solution Files (solution/)

### 13. solution/requirements.txt (3 lines)
**Purpose**: Dependencies for exploit scripts

```
requests==2.31.0        # HTTP library
itsdangerous==2.1.2     # Flask session manipulation
colorama==0.4.6         # Cross-platform colored output
```

---

### 14. solution/exploit.py (3.2KB)
**Purpose**: Complete automated exploit

**Structure**:
- **Lines 1-60**: Imports and configuration
- **Lines 62-96**: Flask session utilities
  - `FlaskSessionManager` class replicates Flask's session handling
- **Lines 98-120**: Stage 1 - Service discovery
- **Lines 122-167**: Stage 2-3 - Intelligence gathering and secret derivation
- **Lines 169-202**: Stage 4 - Secret verification
- **Lines 204-221**: Stage 5 - Admin session forgery
- **Lines 223-290**: Stage 6 - RCE chain
  - Tests admin access
  - Performs NoSQL injection
  - Executes command injection
  - Extracts FLAG from output
- **Lines 292-341**: Main routine with error handling

**Features**:
- Colored output for readability
- Detailed progress logging
- Handles both normal and blind RCE modes
- Cross-platform compatible

---

### 15. solution/exploit_blind.py (1.8KB)
**Purpose**: Demonstrates blind RCE exploitation techniques

**Techniques**:
1. **DNS Exfiltration**: Encodes FLAG in DNS queries
2. **Time-based Extraction**: Character-by-character using sleep delays
3. **HTTP Callback**: Sends FLAG to attacker server
4. **File Write**: Attempts to write FLAG to accessible location

**Use Case**: When `BLIND_RCE=true` is set

---

### 16. solution/WRITEUP.md (2.7KB)
**Purpose**: Internal solution guide for organizers

**Contents**:
- Detailed walkthrough of all 6 stages
- Curl commands for manual exploitation
- Python code snippets
- Key learning points
- Defensive recommendations
- Difficulty notes
- Bonus: Time-based blind NoSQL injection

**Audience**: CTF organizers, solution reviewers

---

## 🔑 Key File Relationships

```
.env.example ──> .env (created by operator)
                   │
                   ├──> docker-compose.yml (reads variables)
                   │         │
                   │         └──> web service (receives env vars)
                   │                  │
                   │                  └──> app.py (validates COMPANY_SALT)
                   │
                   └──> Dockerfile (builds container)
                            │
                            └──> docker-entrypoint.sh (runs init_db.py)
                                        │
                                        └──> init_db.py (validates MongoDB)
                                                  │
                                                  └──> app.py (starts application)
```

**Exploit Flow**:
```
exploit.py ──> Stage 1: /api/v2/services
           ──> Stage 2-3: /api/legacy/get_salt, /api/legacy/system_info
           ──> Stage 4: /api/auth/guest (verify secret)
           ──> Stage 5: Forge admin cookie
           ──> Stage 6: /api/admin/db/migrate (NoSQL + Command Injection)
```

---

## 🔒 Security-Critical Files

| File | Security Role | What It Protects |
|------|--------------|------------------|
| `.dockerignore` | Prevents info leaks | Excludes solution/, .env from image |
| `.gitignore` | Protects secrets | Prevents .env from being committed |
| `app.py:33-37` | Enforces config | Requires COMPANY_SALT to be set |
| `init_db.py:39-77` | Validates setup | Ensures NoSQL injection will work |
| `docker-compose.yml:19` | Enforces config | Uses `:?` syntax to require COMPANY_SALT |
| `Dockerfile:42` | Least privilege | Runs as non-root user |

---

## 📊 File Size Summary

```
Total Project Size: ~25KB (excluding Docker images)

Core Application:     ~15KB (app.py, init_db.py, requirements.txt)
Docker Config:        ~3.5KB (Dockerfile, compose, entrypoint)
Documentation:        ~400KB (README, TESTING, this file)
Solution:             ~8KB (exploits, writeup, requirements)
Config Files:         ~1.5KB (various dotfiles)
```

**Docker Image Size**: ~180MB (Python 3.9-slim base + dependencies)

---

## 🎓 Educational Value by File

| File | Teaches | Level |
|------|---------|-------|
| `app.py` | Flask security, session management, injection | Advanced |
| `init_db.py` | MongoDB operations, error handling | Intermediate |
| `docker-compose.yml` | Container orchestration, env vars | Intermediate |
| `Dockerfile` | Image building, security practices | Intermediate |
| `exploit.py` | Python exploitation, HTTP requests | Advanced |
| `.dockerignore` | Security through obscurity prevention | Beginner |
| `TESTING.md` | Systematic testing methodology | All levels |

---

## 🚀 Quick Reference

**Must Read Before Deployment**:
1. `.env.example` - Set COMPANY_SALT
2. `TESTING.md` - Validation procedures
3. `docker-compose.yml` - Service configuration

**Must Read for Understanding**:
1. `app.py` - All vulnerabilities
2. `solution/exploit.py` - Solution approach
3. This file - Overall architecture

**Must Protect**:
1. `.env` - Contains secrets (git ignored)
2. `solution/` - Excluded from Docker
3. `COMPANY_SALT` value - Never use predictable values

---

**Last Updated**: 2025-01-XX
**Version**: 3.0 (Production Ready)
