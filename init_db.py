"""데이터베이스 초기화 스크립트"""

import os
import sys
import time
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

# 설정
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://db:27017/')
MAX_RETRIES = 30
RETRY_DELAY = 2

def wait_for_mongodb():
    """MongoDB가 준비될 때까지 대기"""
    print("[*] MongoDB 연결 대기 중...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000
            )
            client.server_info()
            print(f"[+] MongoDB 연결됨 (시도 {attempt}/{MAX_RETRIES})")
            return client

        except ServerSelectionTimeoutError:
            if attempt < MAX_RETRIES:
                print(f"[*] {RETRY_DELAY}초 후 재시도... ({attempt}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[!] {MAX_RETRIES}회 시도 후 MongoDB 연결 실패")
                raise

def verify_javascript_enabled(db):
    """MongoDB JavaScript 지원 검증"""
    print("[*] MongoDB JavaScript 지원 검증 중...")

    try:
        db.test_collection.delete_many({})
        db.test_collection.insert_one({'test': True})

        test_results = list(db.test_collection.find({
            "$where": "function() { return this.test === true; }"
        }))

        db.test_collection.delete_many({})

        if len(test_results) > 0:
            print("[+] JavaScript 실행 검증 완료 ✓")
            return True
        else:
            print("[!] $where 쿼리가 결과 없이 반환됨")
            return False

    except OperationFailure as e:
        error_msg = str(e).lower()

        print("=" * 70)
        print("[!!!] 치명적 오류: MongoDB JavaScript가 비활성화됨!")
        print("=" * 70)
        print(f"[!!!] 에러: {e}")
        print()
        print("[수정] docker-compose.yml에 추가:")
        print("      db:")
        print("        command: mongod --setParameter javascriptEnabled=true")
        print("=" * 70)

        return False

    except Exception as e:
        print(f"[!] 검증 중 예상치 못한 오류: {e}")
        return False

def init_database(client):
    """데이터베이스 초기화"""
    db = client.ctf_db

    existing_count = db.users.count_documents({})
    if existing_count > 0:
        print(f"[*] 기존 문서 {existing_count}개 삭제 중...")
        db.users.delete_many({})

    dummy_users = [
        {
            'username': 'john.doe',
            'role': 'developer',
            'email': 'john.doe@company.com',
            'department': 'Engineering',
            'active': True
        },
        {
            'username': 'jane.smith',
            'role': 'analyst',
            'email': 'jane.smith@company.com',
            'department': 'Marketing',
            'active': True
        },
        {
            'username': 'admin',
            'role': 'admin',
            'email': 'admin@company.com',
            'department': 'IT Security',
            'active': True
        },
        {
            'username': 'legacy.service',
            'role': 'service',
            'email': 'legacy@internal.company.com',
            'department': 'Deprecated Services',
            'active': False
        }
    ]

    insert_result = db.users.insert_many(dummy_users)
    inserted_count = len(insert_result.inserted_ids)
    print(f"[+] 사용자 문서 {inserted_count}개 삽입됨")

    total_count = db.users.count_documents({})
    print(f"[+] 컬렉션의 총 문서 수: {total_count}")

    if total_count == 0:
        raise Exception("치명적 오류: 문서가 삽입되지 않음!")

    return total_count

def main():
    """메인 초기화 루틴"""
    print("=" * 70)
    print("데이터베이스 초기화 스크립트")
    print("=" * 70)

    try:
        client = wait_for_mongodb()

        if not verify_javascript_enabled(client.ctf_db):
            print("\n[!!!] 초기화 실패 - JavaScript 비활성화")
            print("[!!!] 컨테이너 종료")
            client.close()
            return 1

        count = init_database(client)

        print("=" * 70)
        print(f"[성공] 데이터베이스 준비 완료: {count}개 문서")
        print("[성공] JavaScript 실행 검증됨")
        print("=" * 70)

        client.close()
        return 0

    except Exception as e:
        print("=" * 70)
        print(f"[실패] 초기화 실패: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
