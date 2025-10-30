# Legacy Microservice Exploitation - 문제 소개

안녕하세요! 새로운 Web 취약점 체이닝 문제를 만들어봤습니다.

## 문제 개요
기존의 단순한 단일 취약점 문제는 현실성이 부족하다고 생각해서, OWASP 웹 취약점을 바탕으로 실전형 문제를 제작했습니다.

## 핵심 공격 체이닝
**Information Disclosure** → **Cryptographic Failure** → **Session Forgery** → **NoSQL Injection** → **Command Injection** → **RCE**

총 5단계 취약점을 연결해서 최종적으로 시스템 장악(FLAG 획득)을 하는 시나리오입니다.

## 사용된 취약점 (OWASP 기준)
1. **A05:2021 - Security Misconfiguration**: 레거시 엔드포인트에서 Salt 힌트 노출
2. **A02:2021 - Cryptographic Failures**: 예측 가능한 방식으로 Secret Key 생성
3. **A01:2021 - Broken Access Control**: Flask 세션 위조를 통한 권한 상승
4. **A03:2021 - Injection (NoSQL)**: MongoDB $where 연산자 악용
5. **A03:2021 - Injection (Command)**: Shell 명령어 주입으로 RCE

## 시나리오
레드팀 침투 테스터로서 레거시 마이크로서비스 플랫폼을 평가합니다.
- Salt 힌트를 브루트포스해서 Flask Secret Key를 유도
- 관리자 세션을 위조해서 Admin API 접근
- NoSQL Injection으로 특수 기능 활성화
- Command Injection으로 최종 RCE 달성

## 관련 CVE 사례
- **CVE-2019-10758**: MongoDB NoSQL Injection
- **CVE-2021-44228**: Log4Shell (Command Injection → RCE)
- **CVE-2015-5122**: Flask Session 위조
- 실제 사례: Equifax 2017 (Command Injection으로 1억 4천만명 정보 유출)

## 난이도
**DreamHack Level 8** (Hard)
예상 풀이 시간: 2-2.5시간

## 특징
- 직접적인 힌트 최소화 (추론 능력 요구)
- Salt 브루트포스 필요
- Flask 세션 구조 지식 필요
- NoSQL + Command Injection 체이닝
- Red Herring으로 미스디렉션

한번 도전해보세요! 🔥
