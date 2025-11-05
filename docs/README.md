# 🔐 OAuth CTF Advanced

## Quick Start

```bash
docker-compose up -d
```

Access: http://localhost:8080

## Goal

Capture the FLAG: `MSG{...}`

## Architecture

- **auth-server** (port 8000): OAuth 2.0 Authorization Server
- **resource-server** (port 8002): Protected API Gateway
- **fresh-client** (port 8001): Demo OAuth Client
- **nginx** (port 8080): Reverse Proxy (Single Entry Point)

All services accessible via nginx at `http://localhost:8080`

## References

- [RFC 6749 - OAuth 2.0 Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 7636 - PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 7591 - OAuth Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591)

## Source Code

- `auth-server/app_sqlite.py` - Authorization Server (1529 lines)
- `resource-server/app.py` - Resource Server (357 lines)
- `fresh-client/app.py` - Client Application (457 lines)

Good luck! 🚀
