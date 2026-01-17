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

## 🌐 4. Exposing Web Application on GCP

### 4.1 GCP Firewall Configuration

Mở các ports cần thiết để truy cập từ bên ngoài:

```bash
# Via gcloud CLI
gcloud compute firewall-rules create allow-build-risk-dashboard \
  --allow tcp:3000,tcp:8000,tcp:3001,tcp:9000 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow Build Risk Dashboard ports"
```

Hoặc qua **GCP Console**:
1. VPC Network → Firewall → Create Firewall Rule
2. **Name**: `allow-build-risk-dashboard`
3. **Targets**: All instances (hoặc chọn specific tag)
4. **Source IP ranges**: `0.0.0.0/0`
5. **Protocols and ports**: `tcp:3000,8000,3001,9000`

### 4.2 Access URLs

Sau khi mở firewall, truy cập ứng dụng qua:

| Service | URL |
|---------|-----|
| Frontend | `http://YOUR_GCP_EXTERNAL_IP:3000` |
| Backend API | `http://YOUR_GCP_EXTERNAL_IP:8000/api/docs` |
| Grafana | `http://YOUR_GCP_EXTERNAL_IP:3001` |
| SonarQube | `http://YOUR_GCP_EXTERNAL_IP:9000` |

### 4.3 Update Environment Variables

Cập nhật `.env` với external IP của GCP server:

```env
DOMAIN_NAME=YOUR_GCP_EXTERNAL_IP
NEXT_PUBLIC_API_URL=http://YOUR_GCP_EXTERNAL_IP:8000/api
NEXT_PUBLIC_WS_URL=ws://YOUR_GCP_EXTERNAL_IP:8000/api/ws/events
FRONTEND_BASE_URL=http://YOUR_GCP_EXTERNAL_IP:3000
```

Sau đó rebuild frontend (vì NEXT_PUBLIC_* là build-time variables):

```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

---

## 🔗 5. GitHub Webhook Configuration

### 5.1 Configure GitHub App Webhook

1. Truy cập **GitHub** → Settings → Developer Settings → GitHub Apps → [Your App]
2. Trong phần **Webhook**:
   - **Webhook URL**: `http://YOUR_GCP_EXTERNAL_IP:8000/api/webhook/github`
   - **Webhook secret**: Cùng giá trị với `GITHUB_WEBHOOK_SECRET` trong `.env`
   - **Content type**: `application/json`
3. Subscribe events: `Workflow run`, `Push`, `Pull request`

### 5.2 Verify Webhook Connectivity

Sau khi cấu hình:

1. Trigger một workflow trên GitHub repository đã track
2. Kiểm tra logs backend:
   ```bash
   docker compose -f docker-compose.prod.yml logs -f backend | grep webhook
   ```
3. Hoặc kiểm tra trên GitHub App → Advanced → Recent Deliveries

### 5.3 Webhook Flow

```
GitHub (workflow_run.completed)
       │
       ▼
http://GCP_IP:8000/api/webhook/github
       │
       ├─ Verify HMAC signature (GITHUB_WEBHOOK_SECRET)
       ├─ Create/Update RawBuildRun
       └─ Dispatch ingestion task (auto-sync)
```

---

## 🔒 6. Security Recommendations (Production)

### 6.1 Use HTTPS with Domain

Đối với production, khuyến nghị sử dụng domain + SSL:

1. **Register domain** và trỏ DNS A record về GCP external IP
2. **Setup Cloudflare** (hoặc SSL certificate):
   - Proxy traffic qua Cloudflare
   - Enable SSL/TLS (Full mode)
3. **Update URLs** trong `.env`:
   ```env
   NEXT_PUBLIC_API_URL=https://yourdomain.com/api
   NEXT_PUBLIC_WS_URL=wss://yourdomain.com/api/ws/events
   ```

### 6.2 Restrict Source IPs (Optional)

Giới hạn truy cập chỉ từ GitHub webhooks:

```bash
# GitHub webhook IP ranges (check docs.github.com for current ranges)
gcloud compute firewall-rules create allow-github-webhooks \
  --allow tcp:8000 \
  --source-ranges 192.30.252.0/22,185.199.108.0/22,140.82.112.0/20 \
  --description "Allow GitHub webhook IPs only"
```

---

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

**GitHub Webhook không nhận được (timeout/connection refused):**
- Kiểm tra firewall GCP đã mở port 8000
- Kiểm tra backend đang chạy: `docker compose -f docker-compose.prod.yml ps`
- Test connectivity: `curl http://YOUR_GCP_IP:8000/api/health`
- Kiểm tra webhook secret khớp giữa GitHub App và `.env`

