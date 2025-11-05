# 🔐 OAuth CTF Advanced

## 문제 설명 (Problem Description)

**MSG.COM**은 최근 OAuth 2.0 기반의 새로운 개발자 포털을 출시했습니다. 보안팀은 Dynamic Client Registration과 PKCE를 적용하여 안전한 인증 시스템을 구축했다고 자신하고 있습니다.

하지만 정말 안전할까요? 🤔

당신의 목표는 **관리자 권한**을 획득하여 `/api/admin/flag` 엔드포인트에 접근하고, 숨겨진 플래그를 탈취하는 것입니다.

---

## 접근 정보 (Access Information)

- **URL**: `http://localhost:8080`
- **플래그 형식**: `MSG{...}`
- **목표 엔드포인트**: `/api/admin/flag`

---

## 시스템 구성 (System Architecture)

이 OAuth 시스템은 3개의 주요 컴포넌트로 구성되어 있습니다:

1. **Authorization Server** (`http://localhost:8080/oauth/*`)
   - OAuth 2.0 인증 서버
   - Dynamic Client Registration 지원
   - PKCE (Proof Key for Code Exchange) 구현

2. **Resource Server** (`http://localhost:8080/api/*`)
   - 보호된 리소스 제공
   - Bearer Token 기반 인증
   - Admin 전용 엔드포인트 포함

3. **Demo Client** (`http://localhost:8080`)
   - OAuth 클라이언트 데모 애플리케이션
   - Authorization Code Flow 구현

---

## 힌트 (Hints)

1. 🔍 Dynamic Client Registration은 어떤 파라미터를 받을까요?
2. 🔐 OAuth 2.0의 여러 Grant Type들을 살펴보세요
3. 🎯 일부 "신뢰받는" 클라이언트는 특별한 권한이 있을 수 있습니다
4. 🌐 내부 네트워크에는 흥미로운 정보가 숨겨져 있을지도 모릅니다

---

## 요구사항 (Requirements)

플래그를 획득하기 위해서는:
- ✅ `ADMIN_SECRETS` 스코프를 가진 유효한 Access Token
- ✅ Admin 계정으로 인증된 토큰

일반 사용자 계정으로는 충분하지 않습니다!

---

## 참고 자료 (References)

- [RFC 6749 - OAuth 2.0 Authorization Framework](https://datatracker.ietf.org/doc/html/rfc6749)
- [RFC 7636 - PKCE](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 7591 - OAuth Dynamic Client Registration](https://datatracker.ietf.org/doc/html/rfc7591)

---

## 시작하기 (Getting Started)

```bash
# 1. 서비스 시작
docker-compose up -d

# 2. 접속
http://localhost:8080

# 3. OAuth 플로우 분석
# - Client Registration
# - Authorization Request
# - Token Exchange
# - API Access
```

---

## 난이도 (Difficulty)

**중급 (Medium)**

- OAuth 2.0 프로토콜 이해 필요
- 여러 취약점을 체인으로 연결해야 함
- SSRF, 권한 상승 등 다양한 기법 활용

**예상 풀이 시간**: 2-4시간

---

## 평가 기준 (Scoring)

- 🚩 **플래그 제출**: `MSG{...}` 형식의 플래그
- 📝 **Write-up 작성** (선택): 공격 과정을 상세히 기록하면 추가 점수

---

## 주의사항 (Notice)

⚠️ **이 환경은 교육 목적으로만 사용하세요**
- 실제 운영 환경에 대한 무단 침투 테스트는 불법입니다
- 학습한 내용은 윤리적으로 사용해주세요

---

**Good luck and happy hacking!** 🚀

_"OAuth is hard. OAuth with vulnerabilities is harder."_
