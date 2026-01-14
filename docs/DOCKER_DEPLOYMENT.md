# Docker Deployment Guide

Hướng dẫn triển khai Build Risk Dashboard sử dụng Docker Compose.

## 📋 Yêu Cầu

- Debian/Ubuntu server
- 8GB RAM minimum (SonarQube requires 4GB)
- 50GB disk space

## 🔧 1. System Prerequisites

### 1.1 Update & Install Base Packages

```bash
sudo apt update
sudo apt install -y git python3 python3-pip htop
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release
```

### 1.2 Install Docker

```bash
# Add Docker GPG key
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# Add user to docker group (logout and login after)
sudo usermod -aG docker $USER
```

### 1.3 SonarQube System Requirements

```bash
# Required for Elasticsearch in SonarQube
sudo sysctl -w vm.max_map_count=262144

# Make permanent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

## 🚀 2. Quick Start

### 2.1 Clone và chuẩn bị

```bash
# Clone repository
git clone https://github.com/your-org/build-risk-dashboard.git
cd build-risk-dashboard

# Copy config production
cp .env.prod .env

# Đảm bảo file GitHub Private Key (.pem) nằm ở thư mục gốc
# Tên file phải khớp với cấu hình trong docker-compose.prod.yml:
# builddefection.2025-11-17.private-key.pem
```

### 2.2 Generate Secrets

```bash
# Generate SECRET_KEY mới và cập nhật vào .env
SECRET_KEY=$(openssl rand -hex 32)
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
```

### 2.3 Environment Variables (.env)

Mở file `.env` và cập nhật các giá trị sau:

**1. Domain & URLs**
- `DOMAIN_NAME`: IP hoặc Domain của server (VD: `10.128.0.9`). Đây là biến helper để tự điền các URL bên dưới.
- `NEXT_PUBLIC_API_URL`: `http://{DOMAIN}:8000/api`
- `NEXT_PUBLIC_WS_URL`: `ws://{DOMAIN}:8000/api/ws/events`
- `FRONTEND_BASE_URL`: `http://{DOMAIN}:3000`

**2. GitHub Configuration (BẮT BUỘC)**
- `GITHUB_APP_ID`: App ID từ GitHub App settings.
- `GITHUB_INSTALLATION_ID`: Installation ID.
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`: OAuth app credentials.
- `GITHUB_ORGANIZATION`: Tên organization (VD: `hung-org-117`).
- `GITHUB_APP_PRIVATE_KEY`: Giữ nguyên đường dẫn `/app/builddefection.2025-11-17.private-key.pem` (đã được mount tự động).

**3. External Services**
- `RABBITMQ_PASS`: Set password mạnh.
- `GRAFANA_PASS`: Set password admin Grafana.
- `GMAIL_*`: Cấu hình nếu muốn gửi email thông báo.

### 2.4 Build và khởi động

```bash
# Build images
docker compose -f docker-compose.prod.yml build

# Start all services
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f
```

## ⚙️ 3. Post-Deployment Configuration

### 3.1 Configure SonarQube (Required)

1.  **Chờ khởi động**: SonarQube mất 2-3 phút để start.
    ```bash
    docker-compose -f docker-compose.prod.yml logs -f sonarqube
    ```
2.  **Truy cập**: `http://YOUR_SERVER_IP:9000`
    - Login: `admin` / `admin`
    - Đổi password ngay lập tức.

3.  **Tạo Token & Webhook**:
    Thay `YOUR_NEW_PASSWORD` bằng password mới của bạn:

    ```bash
    # Generate Token
    curl -u "admin:admin" -X POST \
      "http://localhost:9000/api/user_tokens/generate" \
      -d "name=build-risk-token" -d "type=USER_TOKEN"
    
    # Copy token nhận được và cập nhật vào .env: SONAR_TOKEN=...
    ```

    ```bash
    # Create Webhook (để báo kết quả về backend)
    curl -u "admin:admin" -X POST \
      "http://localhost:9000/api/webhooks/create" \
      -d "name=Build Risk Webhook" \
      -d "url=http://10.128.0.3:8000/api/integrations/webhooks/sonarqube/pipeline" \
      -d "secret=change-me-to-secure-secret"
    ```

4.  **Restart Backend**:
    Sau khi cập nhật `SONAR_TOKEN` trong `.env`:
    ```bash
    docker compose -f docker-compose.prod.yml restart backend celery-worker
    ```

### 3.2 Verify Grafana

- URL: `http://YOUR_SERVER_IP:3001`
- Login: `admin` / `GRAFANA_PASS` (từ .env)
- Kiểm tra folder **Build Risk Dashboard** để thấy các dashboards.

## 🏗️ Architecture & Ports

| Service | Host Port | Internal Port | URL (Example) |
|---------|-----------|---------------|---------------|
| **Frontend** | 3000 | 3000 | `http://IP:3000` |
| **Backend** | 8000 | 8000 | `http://IP:8000` |
| **Grafana** | 3001 | 3000 | `http://IP:3001` |
| **SonarQube**| 9000 | 9000 | `http://IP:9000` |
| **RabbitMQ** | 15672 | 15672 | `http://IP:15672` |

```
Browser ──┬──→ Frontend (:3000)
          ├──→ Backend (:8000)
          └──→ Grafana (:3001)

Internal: Backend ↔ MongoDB/Redis/RabbitMQ/SonarQube
```

## 🔧 Common Commands

```bash
# Stop all
docker-compose -f docker-compose.prod.yml down

# Xem logs backend & worker
docker-compose -f docker-compose.prod.yml logs -f backend celery-worker

# Kiểm tra hàng đợi RabbitMQ
docker exec prod-rabbitmq rabbitmqctl list_queues

# Backup MongoDB
docker exec prod-mongo mongodump --archive=/data/backup.gz --gzip
```

## ⚠️ Troubleshooting

**GitHub App lỗi (401/403):**
- Kiểm tra `GITHUB_APP_PRIVATE_KEY` trong `.env` phải trỏ đúng đường dẫn `/app/...pem`.
- Kiểm tra file `.pem` có tồn tại ở thư mục gốc host không.
- Kiểm tra `GITHUB_APP_ID` và `GITHUB_INSTALLATION_ID` chính xác.

**SonarQube OOM (Exit code 78/137):**
- Chạy: `sudo sysctl -w vm.max_map_count=262144`

**Celery Worker không chạy task:**
- Kiểm tra logs: `docker-compose -f docker-compose.prod.yml logs -f celery-worker`
- Đảm bảo `GITHUB_ORGANIZATION` đã set trong `.env`.
