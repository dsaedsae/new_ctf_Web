#!/bin/bash

################################################################################
# CTF 자동 배포 스크립트
# 사용법: ./deploy.sh
################################################################################

set -e  # 에러 발생 시 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 로깅 함수
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 제목
echo "========================================"
echo "  CTF 자동 배포 스크립트"
echo "  Legacy Microservice Exploitation"
echo "========================================"
echo ""

# 1. 시스템 확인
log_info "시스템 확인 중..."
if ! command -v docker &> /dev/null; then
    log_error "Docker가 설치되지 않았습니다!"
    log_info "다음 명령으로 설치하세요:"
    echo "curl -fsSL https://get.docker.com -o get-docker.sh"
    echo "sudo sh get-docker.sh"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    log_error "Docker Compose가 설치되지 않았습니다!"
    log_info "다음 명령으로 설치하세요:"
    echo "sudo apt-get install docker-compose-plugin"
    exit 1
fi

log_success "Docker 및 Docker Compose 확인 완료"

# 2. .env 파일 확인
log_info ".env 파일 확인 중..."
if [ ! -f .env ]; then
    log_warning ".env 파일이 없습니다. 생성합니다..."

    if [ -f .env.example ]; then
        cp .env.example .env
        log_info ".env.example을 복사했습니다."
    else
        log_error ".env.example 파일이 없습니다!"
        exit 1
    fi

    # COMPANY_SALT 자동 생성
    RANDOM_SALT=$(openssl rand -hex 16)
    sed -i "s/^COMPANY_SALT=.*/COMPANY_SALT=${RANDOM_SALT}/" .env

    log_success "랜덤 COMPANY_SALT 생성: ${RANDOM_SALT}"
    log_warning "⚠️  .env 파일을 확인하고 FLAG를 설정하세요!"

    echo ""
    echo "계속하려면 Enter를 누르세요 (Ctrl+C로 취소)..."
    read
fi

# COMPANY_SALT 확인
if ! grep -q "COMPANY_SALT=" .env || grep -q "COMPANY_SALT=$" .env; then
    log_error "COMPANY_SALT가 설정되지 않았습니다!"
    log_info ".env 파일에서 COMPANY_SALT를 설정하세요"
    exit 1
fi

log_success ".env 파일 확인 완료"

# 3. 기존 컨테이너 정리
log_info "기존 컨테이너 확인 중..."
if docker compose ps -q | grep -q .; then
    log_warning "기존 컨테이너를 중지합니다..."
    docker compose down
    log_success "기존 컨테이너 중지 완료"
fi

# 4. Docker 이미지 빌드
log_info "Docker 이미지 빌드 중... (시간이 걸릴 수 있습니다)"
if docker compose build; then
    log_success "Docker 이미지 빌드 완료"
else
    log_error "Docker 이미지 빌드 실패!"
    exit 1
fi

# 5. 컨테이너 시작
log_info "컨테이너 시작 중..."
if docker compose up -d; then
    log_success "컨테이너 시작 완료"
else
    log_error "컨테이너 시작 실패!"
    log_info "로그를 확인하세요: docker compose logs"
    exit 1
fi

# 6. 컨테이너 상태 확인
log_info "컨테이너 상태 확인 중... (30초 대기)"
sleep 30

if ! docker compose ps | grep -q "Up"; then
    log_error "컨테이너가 정상적으로 실행되지 않았습니다!"
    log_info "로그를 확인하세요:"
    docker compose logs
    exit 1
fi

log_success "컨테이너 실행 확인 완료"

# 7. 헬스체크
log_info "애플리케이션 헬스체크 중..."
sleep 5

HEALTH_RESPONSE=$(curl -s http://localhost:5000/health)

if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    log_success "헬스체크 성공!"

    # JavaScript 활성화 확인
    if echo "$HEALTH_RESPONSE" | grep -q '"javascript_enabled":true'; then
        log_success "✓ MongoDB JavaScript 활성화 확인"
    else
        log_error "✗ MongoDB JavaScript가 비활성화되어 있습니다!"
        log_warning "이 CTF 문제는 JavaScript가 필요합니다!"
    fi

    # 데이터베이스 연결 확인
    if echo "$HEALTH_RESPONSE" | grep -q '"database":"connected"'; then
        log_success "✓ 데이터베이스 연결 확인"
    else
        log_error "✗ 데이터베이스 연결 실패"
    fi
else
    log_error "헬스체크 실패!"
    log_info "응답: $HEALTH_RESPONSE"
    exit 1
fi

# 8. 최종 정보 출력
echo ""
echo "========================================"
log_success "배포 완료!"
echo "========================================"
echo ""

# 현재 호스트 정보
HOSTNAME=$(hostname -I | awk '{print $1}')

echo "접속 정보:"
echo "  - 로컬: http://localhost:5000"
echo "  - 내부 IP: http://${HOSTNAME}:5000"
echo ""

# 퍼블릭 IP 확인 (AWS EC2)
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "N/A")
if [ "$PUBLIC_IP" != "N/A" ]; then
    echo "  - 퍼블릭 IP: http://${PUBLIC_IP}:5000"
    log_warning "⚠️  보안 그룹에서 5000번 포트를 열어야 합니다!"
fi

echo ""
echo "테스트 명령어:"
echo "  curl http://localhost:5000/health"
echo "  curl http://localhost:5000/api/v2/services"
echo ""

echo "로그 확인:"
echo "  docker compose logs -f"
echo ""

echo "컨테이너 관리:"
echo "  docker compose ps       # 상태 확인"
echo "  docker compose restart  # 재시작"
echo "  docker compose down     # 중지"
echo ""

log_info "배포 스크립트 종료"
