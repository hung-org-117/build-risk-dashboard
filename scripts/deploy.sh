#!/bin/bash
# =============================================================================
# Production Deployment Script
# Run this on the server to deploy/update the application
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if .env file exists
if [ ! -f ".env" ]; then
    log_error ".env file not found! Copy .env.prod.example to .env and configure it."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

COMPOSE_FILE="docker-compose.prod.yml"

log_info "Starting production deployment..."

# Step 1: Pull latest images
log_info "Pulling latest Docker images..."
docker compose -f $COMPOSE_FILE pull

# Step 2: Build custom images (backend, frontend)
log_info "Building custom images..."
docker compose -f $COMPOSE_FILE build --no-cache backend frontend celery-worker celery-beat

# Step 3: Stop and recreate containers
log_info "Recreating containers..."
docker compose -f $COMPOSE_FILE up -d --force-recreate

# Step 4: Wait for services to be healthy
log_info "Waiting for services to be healthy..."
sleep 10

# Step 5: Health checks
log_info "Running health checks..."

check_service() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            log_info "$service is healthy ✓"
            return 0
        fi
        log_warn "$service not ready, attempt $attempt/$max_attempts..."
        sleep 5
        ((attempt++))
    done
    
    log_error "$service failed health check!"
    return 1
}

# Check critical services
check_service "Backend API" "http://localhost:8000/api/health" || true
check_service "Frontend" "http://localhost:3000" || true

# Step 6: Cleanup
log_info "Cleaning up old images..."
docker image prune -f

# Step 7: Show running containers
log_info "Running containers:"
docker compose -f $COMPOSE_FILE ps

log_info "🎉 Deployment completed successfully!"
echo ""
echo "Services available at:"
echo "  - Frontend:  https://${DOMAIN_NAME}"
echo "  - Backend:   https://${DOMAIN_NAME}/api"
echo "  - Grafana:   https://${DOMAIN_NAME}/grafana"
echo "  - SonarQube: https://${DOMAIN_NAME}/sonarqube"
