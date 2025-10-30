"# new_ctf_Web

## MongoDB Configuration

This CTF environment uses MongoDB 4.4 with JavaScript execution disabled for security.

### Why MongoDB 4.4?

MongoDB 5.0+ changed the parameter format for disabling JavaScript:
- **MongoDB 4.4**: `--setParameter javascriptEnabled=false` ✓
- **MongoDB 5.0+**: Parameter removed, must use config file or `--noscripting`

### Alternative: Using MongoDB 5.0+

If you need MongoDB 5.0 or higher, modify docker-compose.yml:

```yaml
db:
  image: mongo:5.0
  container_name: ctf_db
  volumes:
    - mongodb_data:/data/db
    - ./mongod.conf:/etc/mongod.conf
  command: mongod --config /etc/mongod.conf
```

Create `mongod.conf`:
```yaml
security:
  javascriptEnabled: false

net:
  bindIp: 0.0.0.0
```

## Quick Start

```bash
docker compose up -d
```" 
