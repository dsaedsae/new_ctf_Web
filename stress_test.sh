#!/bin/bash

################################################################################
# CTF 부하 테스트 스크립트
# 사용법: ./stress_test.sh [동시접속자수] [요청횟수]
# 예시: ./stress_test.sh 50 100
################################################################################

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 기본값 설정
CONCURRENT_USERS=${1:-50}
REQUESTS_PER_USER=${2:-100}
TARGET_URL=${3:-"http://localhost:5000"}

echo "========================================"
echo "  CTF 부하 테스트"
echo "========================================"
echo ""
echo "설정:"
echo "  - 동시 접속자: ${CONCURRENT_USERS}명"
echo "  - 요청/사용자: ${REQUESTS_PER_USER}회"
echo "  - 총 요청 수: $((CONCURRENT_USERS * REQUESTS_PER_USER))회"
echo "  - 대상 URL: ${TARGET_URL}"
echo ""

# Apache Bench 확인
if ! command -v ab &> /dev/null; then
    echo -e "${YELLOW}[경고]${NC} Apache Bench(ab)가 설치되지 않았습니다."
    echo "설치 방법: sudo apt-get install apache2-utils"
    echo ""
    echo "대신 curl로 간단한 테스트를 진행합니다..."
    echo ""

    # curl 기반 간단 테스트
    echo -e "${BLUE}[테스트 1/3]${NC} 메인 페이지 접근"
    for i in {1..10}; do
        curl -s -o /dev/null -w "요청 $i: %{http_code} - %{time_total}초\n" "${TARGET_URL}/"
    done

    echo ""
    echo -e "${BLUE}[테스트 2/3]${NC} API 엔드포인트"
    for i in {1..10}; do
        curl -s -o /dev/null -w "요청 $i: %{http_code} - %{time_total}초\n" "${TARGET_URL}/api/v2/services"
    done

    echo ""
    echo -e "${BLUE}[테스트 3/3]${NC} 헬스체크"
    for i in {1..10}; do
        curl -s -o /dev/null -w "요청 $i: %{http_code} - %{time_total}초\n" "${TARGET_URL}/health"
    done

    echo ""
    echo -e "${GREEN}테스트 완료!${NC}"
    echo "더 정확한 테스트를 위해 Apache Bench를 설치하세요."

    exit 0
fi

# Apache Bench 기반 정밀 테스트
echo -e "${BLUE}[테스트 시작]${NC}"
echo ""

# 테스트 결과 저장 디렉토리
RESULT_DIR="stress_test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULT_DIR"

# 1. 메인 페이지 테스트
echo -e "${BLUE}[1/4]${NC} 메인 페이지 부하 테스트..."
ab -n $((CONCURRENT_USERS * REQUESTS_PER_USER)) \
   -c "$CONCURRENT_USERS" \
   -g "${RESULT_DIR}/homepage.tsv" \
   "${TARGET_URL}/" > "${RESULT_DIR}/homepage.txt" 2>&1

if [ $? -eq 0 ]; then
    RPS=$(grep "Requests per second" "${RESULT_DIR}/homepage.txt" | awk '{print $4}')
    AVG_TIME=$(grep "Time per request" "${RESULT_DIR}/homepage.txt" | head -1 | awk '{print $4}')
    echo -e "  ${GREEN}✓${NC} 완료 - RPS: ${RPS}, 평균 응답: ${AVG_TIME}ms"
else
    echo -e "  ${RED}✗${NC} 실패"
fi

# 2. API 엔드포인트 테스트
echo -e "${BLUE}[2/4]${NC} API 엔드포인트 부하 테스트..."
ab -n $((CONCURRENT_USERS * REQUESTS_PER_USER)) \
   -c "$CONCURRENT_USERS" \
   -g "${RESULT_DIR}/api.tsv" \
   "${TARGET_URL}/api/v2/services" > "${RESULT_DIR}/api.txt" 2>&1

if [ $? -eq 0 ]; then
    RPS=$(grep "Requests per second" "${RESULT_DIR}/api.txt" | awk '{print $4}')
    AVG_TIME=$(grep "Time per request" "${RESULT_DIR}/api.txt" | head -1 | awk '{print $4}')
    echo -e "  ${GREEN}✓${NC} 완료 - RPS: ${RPS}, 평균 응답: ${AVG_TIME}ms"
else
    echo -e "  ${RED}✗${NC} 실패"
fi

# 3. 헬스체크 테스트
echo -e "${BLUE}[3/4]${NC} 헬스체크 부하 테스트..."
ab -n $((CONCURRENT_USERS * REQUESTS_PER_USER)) \
   -c "$CONCURRENT_USERS" \
   -g "${RESULT_DIR}/health.tsv" \
   "${TARGET_URL}/health" > "${RESULT_DIR}/health.txt" 2>&1

if [ $? -eq 0 ]; then
    RPS=$(grep "Requests per second" "${RESULT_DIR}/health.txt" | awk '{print $4}')
    AVG_TIME=$(grep "Time per request" "${RESULT_DIR}/health.txt" | head -1 | awk '{print $4}')
    echo -e "  ${GREEN}✓${NC} 완료 - RPS: ${RPS}, 평균 응답: ${AVG_TIME}ms"
else
    echo -e "  ${RED}✗${NC} 실패"
fi

# 4. POST 요청 테스트 (세션 검증)
echo -e "${BLUE}[4/4]${NC} POST 요청 부하 테스트..."
echo '{"username":"test","password":"test"}' > /tmp/post_data.json
ab -n 1000 \
   -c 50 \
   -p /tmp/post_data.json \
   -T "application/json" \
   -g "${RESULT_DIR}/post.tsv" \
   "${TARGET_URL}/api/v2/auth/validate" > "${RESULT_DIR}/post.txt" 2>&1

if [ $? -eq 0 ]; then
    RPS=$(grep "Requests per second" "${RESULT_DIR}/post.txt" | awk '{print $4}')
    AVG_TIME=$(grep "Time per request" "${RESULT_DIR}/post.txt" | head -1 | awk '{print $4}')
    echo -e "  ${GREEN}✓${NC} 완료 - RPS: ${RPS}, 평균 응답: ${AVG_TIME}ms"
else
    echo -e "  ${RED}✗${NC} 실패"
fi

echo ""
echo "========================================"
echo -e "${GREEN}부하 테스트 완료!${NC}"
echo "========================================"
echo ""

# 결과 요약
echo "결과 요약:"
echo "  - 테스트 결과: ${RESULT_DIR}/"
echo ""

# 상세 결과 출력
for file in "${RESULT_DIR}"/*.txt; do
    if [ -f "$file" ]; then
        TEST_NAME=$(basename "$file" .txt)
        echo -e "${BLUE}[${TEST_NAME}]${NC}"

        # 주요 지표 추출
        grep "Requests per second" "$file" | sed 's/^/  /'
        grep "Time per request" "$file" | head -1 | sed 's/^/  /'
        grep "Failed requests" "$file" | sed 's/^/  /'

        # 실패율 계산
        FAILED=$(grep "Failed requests" "$file" | awk '{print $3}')
        TOTAL=$(grep "Complete requests" "$file" | awk '{print $3}')

        if [ -n "$FAILED" ] && [ -n "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
            FAIL_RATE=$(echo "scale=2; $FAILED * 100 / $TOTAL" | bc)
            if (( $(echo "$FAIL_RATE > 1" | bc -l) )); then
                echo -e "  ${RED}실패율: ${FAIL_RATE}%${NC}"
            else
                echo -e "  ${GREEN}실패율: ${FAIL_RATE}%${NC}"
            fi
        fi

        echo ""
    fi
done

echo "권장사항:"
echo "  - 실패율 > 1%: 인스턴스 사양 업그레이드 필요"
echo "  - 평균 응답 > 500ms: 성능 최적화 필요"
echo "  - RPS < 100: 리소스 증설 검토"
echo ""

# 그래프 생성 안내
echo "그래프 생성 (gnuplot 필요):"
echo "  gnuplot -e \"set terminal png; set output '${RESULT_DIR}/graph.png'; plot '${RESULT_DIR}/homepage.tsv' using 5 with lines\""
echo ""
