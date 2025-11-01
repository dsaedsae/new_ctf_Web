#!/bin/sh
# 컨테이너 진입점 스크립트 V3.0
#
# V3.0 수정사항:
# - set -e 로직 에러 수정
# - 성능 향상을 위해 gevent worker 사용

echo "=========================================="
echo "CTF 컨테이너 시작 - V3.0"
echo "=========================================="

# 단계 1: 데이터베이스 초기화
echo "[1/2] 데이터베이스 초기화 중..."

# set -e로 에러 자동 처리
python3 init_db.py || {
    echo "[에러] 데이터베이스 초기화 실패"
    echo "[에러] MongoDB JavaScript 설정 확인"
    exit 1
}

echo "[1/2] 데이터베이스 초기화 완료 ✓"

# 단계 1.5: FLAG 파일 생성
if [ -n "$FLAG" ]; then
    echo "$FLAG" > /flag.txt
    echo "[*] FLAG 파일 생성됨: /flag.txt"
else
    echo "[경고] FLAG 환경 변수가 설정되지 않음!"
fi

# 단계 2: gevent worker로 웹 서버 시작
echo "[2/2] Gunicorn 웹 서버 시작 중 (gevent 모드)..."
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --worker-class gevent \
    --timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
