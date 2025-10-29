"""
Database Initialization Script V3.0
Populates MongoDB with dummy data
"""

import os
import sys
import time
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

# Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://db:27017/')
MAX_RETRIES = 30
RETRY_DELAY = 2

def wait_for_mongodb():
    """Wait for MongoDB to become available"""
    print("[*] Waiting for MongoDB connection...")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = MongoClient(
                MONGO_URI,
                serverSelectionTimeoutMS=2000,
                connectTimeoutMS=2000
            )
            client.server_info()
            print(f"[+] MongoDB connected (attempt {attempt}/{MAX_RETRIES})")
            return client

        except ServerSelectionTimeoutError:
            if attempt < MAX_RETRIES:
                print(f"[*] Retry in {RETRY_DELAY}s... ({attempt}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
            else:
                print(f"[!] MongoDB connection failed after {MAX_RETRIES} attempts")
                raise

def verify_javascript_enabled(db):
    """
    CRITICAL verification - $where must work!
    Container startup fails if JavaScript is disabled
    """
    print("[*] Verifying MongoDB JavaScript support...")

    try:
        # Insert test document
        db.test_collection.delete_many({})
        db.test_collection.insert_one({'test': True})

        # Test $where operator
        test_results = list(db.test_collection.find({
            "$where": "function() { return this.test === true; }"
        }))

        # Clean up
        db.test_collection.delete_many({})

        if len(test_results) > 0:
            print("[+] JavaScript execution verified ✓")
            return True
        else:
            print("[!] $where query returned no results")
            return False

    except OperationFailure as e:
        error_msg = str(e).lower()

        print("=" * 70)
        print("[!!!] CRITICAL ERROR: MongoDB JavaScript is DISABLED!")
        print("=" * 70)
        print(f"[!!!] Error: {e}")
        print()
        print("[!!!] This CTF challenge REQUIRES JavaScript support!")
        print("[!!!] The NoSQL injection will NOT work without it!")
        print()
        print("[FIX] Add to docker-compose.yml:")
        print("      db:")
        print("        command: mongod --setParameter javascriptEnabled=true")
        print("=" * 70)

        return False

    except Exception as e:
        print(f"[!] Unexpected error during verification: {e}")
        return False

def init_database(client):
    """Initialize database with dummy data"""
    db = client.ctf_db

    # Clear existing data
    existing_count = db.users.count_documents({})
    if existing_count > 0:
        print(f"[*] Clearing {existing_count} existing documents...")
        db.users.delete_many({})

    # Realistic dummy data
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

    # Insert documents
    insert_result = db.users.insert_many(dummy_users)
    inserted_count = len(insert_result.inserted_ids)
    print(f"[+] Inserted {inserted_count} user documents")

    # Verification
    total_count = db.users.count_documents({})
    print(f"[+] Total documents in collection: {total_count}")

    if total_count == 0:
        raise Exception("CRITICAL: No documents inserted!")

    return total_count

def main():
    """Main initialization routine"""
    print("=" * 70)
    print("CTF Challenge: Legacy Microservice Exploitation V3.0")
    print("Database Initialization Script")
    print("=" * 70)

    try:
        # Step 1: Connect to MongoDB
        client = wait_for_mongodb()

        # Step 2: CRITICAL verification
        if not verify_javascript_enabled(client.ctf_db):
            print("\n[!!!] Initialization FAILED - JavaScript disabled")
            print("[!!!] Container will exit now")
            client.close()
            return 1  # Fatal error

        # Step 3: Populate database
        count = init_database(client)

        # Step 4: Success
        print("=" * 70)
        print(f"[SUCCESS] Database ready with {count} documents")
        print("[SUCCESS] JavaScript execution verified")
        print("=" * 70)

        client.close()
        return 0

    except Exception as e:
        print("=" * 70)
        print(f"[FAILURE] Initialization failed: {str(e)}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
