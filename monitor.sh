#!/bin/bash

################################################################################
# CTF 실시간 모니터링 스크립트
# 사용법: ./monitor.sh
################################################################################

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 임계값 설정
CPU_THRESHOLD=80
MEMORY_THRESHOLD=80
DISK_THRESHOLD=85

clear
echo "========================================"
echo "  CTF 실시간 모니터링 대시보드"
echo "  (Ctrl+C로 종료)"
echo "========================================"
echo ""

# 로그 파일 설정
LOG_FILE="ctf_monitor_$(date +%Y%m%d_%H%M%S).log"

# 초기 로그
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 모니터링 시작" >> "$LOG_FILE"

while true; do
    clear
    echo -e "${CYAN}========================================"
    echo "  CTF 실시간 모니터링 ($(date '+%Y-%m-%d %H:%M:%S'))"
    echo -e "========================================${NC}"
    echo ""

    # 1. 시스템 리소스
    echo -e "${BLUE}[시스템 리소스]${NC}"

    # CPU 사용률
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
    CPU_INT=${CPU_USAGE%.*}

    if [ "$CPU_INT" -ge "$CPU_THRESHOLD" ]; then
        echo -e "  CPU 사용률: ${RED}${CPU_USAGE}%${NC} ⚠️"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: CPU ${CPU_USAGE}%" >> "$LOG_FILE"
    else
        echo -e "  CPU 사용률: ${GREEN}${CPU_USAGE}%${NC}"
    fi

    # 메모리 사용률
    MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    MEMORY_INT=${MEMORY_USAGE%.*}

    if [ "$MEMORY_INT" -ge "$MEMORY_THRESHOLD" ]; then
        echo -e "  메모리 사용률: ${RED}${MEMORY_USAGE}%${NC} ⚠️"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Memory ${MEMORY_USAGE}%" >> "$LOG_FILE"
    else
        echo -e "  메모리 사용률: ${GREEN}${MEMORY_USAGE}%${NC}"
    fi

    # 디스크 사용률
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$DISK_USAGE" -ge "$DISK_THRESHOLD" ]; then
        echo -e "  디스크 사용률: ${RED}${DISK_USAGE}%${NC} ⚠️"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Disk ${DISK_USAGE}%" >> "$LOG_FILE"
    else
        echo -e "  디스크 사용률: ${GREEN}${DISK_USAGE}%${NC}"
    fi

    echo ""

    # 2. Docker 컨테이너 상태
    echo -e "${BLUE}[Docker 컨테이너 상태]${NC}"

    if docker compose ps -q &>/dev/null; then
        # Web 컨테이너
        WEB_STATUS=$(docker compose ps web 2>/dev/null | grep -q "Up" && echo "Running" || echo "Stopped")
        if [ "$WEB_STATUS" = "Running" ]; then
            echo -e "  Web 컨테이너: ${GREEN}●${NC} Running"
        else
            echo -e "  Web 컨테이너: ${RED}●${NC} Stopped"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Web container stopped" >> "$LOG_FILE"
        fi

        # DB 컨테이너
        DB_STATUS=$(docker compose ps db 2>/dev/null | grep -q "Up" && echo "Running" || echo "Stopped")
        if [ "$DB_STATUS" = "Running" ]; then
            echo -e "  DB 컨테이너: ${GREEN}●${NC} Running"
        else
            echo -e "  DB 컨테이너: ${RED}●${NC} Stopped"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: DB container stopped" >> "$LOG_FILE"
        fi

        # 컨테이너 리소스 사용량
        echo ""
        echo -e "${BLUE}[컨테이너 리소스]${NC}"
        docker stats --no-stream --format "  {{.Name}}: CPU {{.CPUPerc}} | MEM {{.MemPerc}}" ctf_web ctf_db 2>/dev/null
    else
        echo -e "  ${RED}Docker 컨테이너가 실행되지 않았습니다!${NC}"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: No containers running" >> "$LOG_FILE"
    fi

    echo ""

    # 3. 네트워크 통계
    echo -e "${BLUE}[네트워크 통계]${NC}"

    # 현재 연결 수
    CONN_COUNT=$(ss -tan | grep -c ESTABLISHED)
    echo "  활성 연결 수: ${CONN_COUNT}"

    # 5000 포트 연결
    PORT_5000=$(ss -tan | grep ":5000" | grep -c ESTABLISHED)
    echo "  5000 포트 연결: ${PORT_5000}"

    # TIME_WAIT 상태 (과부하 지표)
    TIME_WAIT=$(ss -tan | grep -c TIME_WAIT)
    if [ "$TIME_WAIT" -gt 1000 ]; then
        echo -e "  TIME_WAIT: ${RED}${TIME_WAIT}${NC} ⚠️"
    else
        echo "  TIME_WAIT: ${TIME_WAIT}"
    fi

    echo ""

    # 4. 애플리케이션 헬스체크
    echo -e "${BLUE}[애플리케이션 상태]${NC}"

    HEALTH_CHECK=$(curl -s -w "\n%{http_code}" http://localhost:5000/health 2>/dev/null)
    HTTP_CODE=$(echo "$HEALTH_CHECK" | tail -n1)

    if [ "$HTTP_CODE" = "200" ]; then
        echo -e "  헬스체크: ${GREEN}✓ OK${NC}"

        # 응답 시간 측정
        RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}\n' http://localhost:5000/health)
        echo "  응답 시간: ${RESPONSE_TIME}초"

        if (( $(echo "$RESPONSE_TIME > 1.0" | bc -l) )); then
            echo -e "  ${YELLOW}⚠️  응답이 느립니다!${NC}"
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: Slow response ${RESPONSE_TIME}s" >> "$LOG_FILE"
        fi
    else
        echo -e "  헬스체크: ${RED}✗ FAIL${NC} (HTTP $HTTP_CODE)"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Health check failed HTTP $HTTP_CODE" >> "$LOG_FILE"
    fi

    echo ""

    # 5. 최근 로그 (에러만)
    echo -e "${BLUE}[최근 에러 로그]${NC}"
    docker compose logs --tail=5 2>/dev/null | grep -i "error\|exception\|fail" | tail -3 | sed 's/^/  /'

    echo ""
    echo -e "${CYAN}----------------------------------------${NC}"
    echo -e "다음 업데이트: 5초 후... (로그: ${LOG_FILE})"
    echo ""

    # 5초 대기
    sleep 5
done
