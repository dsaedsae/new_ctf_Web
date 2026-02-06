# 🔐 MSG CTF 2025 - OAuth SSRF Challenge

> **연합 동아리 CTF 웹 해킹 문제 — OAuth 2.0 인증 플로우의 다층적 취약점을 결합한 공격 시나리오**

## 📋 문제 개요

| 항목 | 내용 |
|------|------|
| **분야** | Web Exploitation |
| **난이도** | Hard |
| **핵심 취약점** | SSRF, OAuth 2.0 Scope Escalation, JWT Algorithm Confusion |
| **출제 기간** | 2025.08 ~ 2025.11 (약 3개월) |
| **운영** | 2025.11.09 연합 동아리 CTF |
| **역할** | 웹 파트 팀장 / 문제 설계 및 인프라 구축 |

가상의 OAuth 2.0 인증 플랫폼에서 **정찰 → SSRF → 권한 상승 → JWT 변조**까지 이어지는 실전형 공격 체인을 경험할 수 있도록 설계한 문제입니다.

## 🎯 학습 목표

참가자가 이 문제를 통해 다음을 학습하도록 설계했습니다:

- **OAuth 2.0 Authorization Code Grant** 플로우의 구조적 이해
- **SSRF(Server-Side Request Forgery)** 와 IPv6 Full Notation 우회 기법
- **Refresh Token을 이용한 Scope Escalation** (RFC 6749 Section 6)
- **JWT Algorithm Confusion** (RS256 → HS256 전환 공격)

## 🏗️ 아키텍처

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Attacker  │────▶│  OAuth Platform   │────▶│  Internal API   │
│  (Browser/  │     │  - /oauth/*       │     │  - /internal/*  │
│   Burp)     │◀────│  - /api/*         │◀────│  - dev-config   │
└─────────────┘     │  - /.well-known/* │     │  - admin creds  │
                    └──────────────────┘     └─────────────────┘
                           │
                    ┌──────┴───────┐
                    │   SSRF via   │
                    │   logo_uri   │
                    └──────────────┘
```

## 🔗 공격 체인 (풀이 흐름)

```
[1] 정찰 (Reconnaissance)
 │  robots.txt → /internal/admin/, /oauth/register 발견
 │  /.well-known/oauth-authorization-server → 스코프 구조, JWT 알고리즘 확인
 ▼
[2] SSRF (Server-Side Request Forgery)
 │  /oauth/register의 logo_uri 파라미터를 통한 SSRF
 │  IPv6 Full Notation (0:0:0:0:0:0:0:1) 으로 블랙리스트 우회
 │  → /internal/admin/dev-config.json에서 관리자 크리덴셜 탈취
 ▼
[3] OAuth 권한 상승 (Scope Escalation)
 │  Authorization Code 발급 → Access Token 획득
 │  Refresh Token으로 scope를 read → read write → read write ADMIN_SECRETS 확장
 ▼
[4] JWT Algorithm Confusion
 │  RS256(비대칭) 토큰을 HS256(대칭)으로 변조
 │  공개키(.well-known/public-key.pem)를 HMAC 시크릿으로 사용
 │  → /api/admin/flag에서 플래그 획득
```

## 🛠️ 기술 스택

| 구분 | 기술 |
|------|------|
| **Backend** | Python (Flask) |
| **인증** | OAuth 2.0 (Authorization Code Grant), JWT (RS256/HS256) |
| **인프라** | Docker, Docker Compose |
| **배포 환경** | GCP Compute Engine |

## 🚀 실행 방법

### 사전 요구사항
- Docker & Docker Compose

### 구동

```bash
git clone https://github.com/dsaedsae/new_ctf_Web.git
cd new_ctf_Web
git checkout Release2
docker-compose up -d
```

문제 환경이 `http://localhost:8080`에서 구동됩니다.

### 종료

```bash
docker-compose down
```

## 📖 Writeup

풀이 과정은 `writeup/` 디렉토리를 참고하세요.

**풀이 요약:**
1. `robots.txt` 및 OAuth Discovery 엔드포인트 정찰
2. `logo_uri` 파라미터를 통한 SSRF → IPv6 우회로 내부 설정 탈취
3. Refresh Token Grant를 활용한 단계적 scope 확장 (`read` → `ADMIN_SECRETS`)
4. RS256 공개키를 HS256 시크릿으로 전용하여 JWT 변조 → 플래그 획득

## 🔑 출제 의도

이 문제는 단일 취약점이 아닌 **여러 취약점의 체인**을 통해 최종 목표에 도달하도록 설계했습니다.

| 단계 | 취약점 | 설계 의도 |
|------|--------|----------|
| SSRF 필터 우회 | IPv6 Full Notation | 블랙리스트 기반 필터링의 한계 체험 |
| OAuth 스펙 악용 | Refresh Token Scope Escalation | RFC 6749 정독을 유도하여 프로토콜 자체에 대한 이해 강화 |
| JWT 알고리즘 혼동 | RS256 → HS256 | 실제 CVE에서 보고된 취약점 패턴 반영 |

## 📬 Contact

- **출제자**: 김재현
- **GitHub**: [@dsaedsae](https://github.com/dsaedsae)
