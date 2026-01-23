# HƯỚNG DẪN CÀI ĐẶT BUILD RISK DASHBOARD

**Phiên bản:** 1.0  
**Cập nhật:** Tháng 01/2026  
**Tác giả:** Build Risk Team

---

## MỤC LỤC

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Chuẩn bị môi trường](#2-chuẩn-bị-môi-trường)
3. [Cấu hình biến môi trường](#3-cấu-hình-biến-môi-trường)
4. [Triển khai ứng dụng](#4-triển-khai-ứng-dụng)
5. [Cấu hình sau triển khai](#5-cấu-hình-sau-triển-khai)
6. [Kiến trúc hệ thống](#6-kiến-trúc-hệ-thống)
7. [Các lệnh thường dùng](#7-các-lệnh-thường-dùng)
8. [Xử lý sự cố](#8-xử-lý-sự-cố)

---

## 1. YÊU CẦU HỆ THỐNG

### 1.1 Phần cứng tối thiểu

| Thành phần | Yêu cầu |
|------------|---------|
| RAM | 8GB (SonarQube cần 4GB) |
| Ổ cứng | 50GB |
| CPU | 2 cores |
| OS | Debian/Ubuntu |

### 1.2 Phần mềm cần thiết

| Phần mềm | Phiên bản |
|----------|-----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Git | 2.30+ |

---

## 2. CHUẨN BỊ MÔI TRƯỜNG

### 2.1 Cập nhật hệ thống

Chạy các lệnh sau để cập nhật và cài đặt các package cần thiết:

```
sudo apt update
sudo apt install -y git python3 python3-pip htop
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release
```

### 2.2 Cài đặt Docker

**Bước 1:** Thêm GPG key của Docker

```
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
```

**Bước 2:** Thêm Docker repository

```
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

**Bước 3:** Cài đặt Docker

```
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io
```

**Bước 4:** Thêm user vào group docker (cần logout/login lại)

```
sudo usermod -aG docker $USER
```

### 2.3 Cấu hình cho SonarQube

SonarQube yêu cầu tăng giới hạn virtual memory:

```
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

---

## 3. CẤU HÌNH BIẾN MÔI TRƯỜNG

### 3.1 Clone repository và chuẩn bị file cấu hình

```
git clone https://github.com/your-org/build-risk-dashboard.git
cd build-risk-dashboard
cp .env.prod.example .env
```

### 3.2 Tạo Secret Key

```
SECRET_KEY=$(openssl rand -hex 32)
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
```

### 3.3 Danh sách biến môi trường

Mở file `.env` và cập nhật các giá trị theo bảng dưới đây:

#### Nhóm 1: Domain và URLs (BẮT BUỘC)

| Biến | Mô tả | Ví dụ |
|------|-------|-------|
| NEXT_PUBLIC_API_URL | URL của Backend API | http://10.128.0.9:8000/api |
| NEXT_PUBLIC_WS_URL | URL WebSocket | ws://10.128.0.9:8000/ws |
| FRONTEND_BASE_URL | URL của Frontend | http://10.128.0.9:3000 |

#### Nhóm 2: GitHub Configuration (BẮT BUỘC)

| Biến | Mô tả | Cách lấy |
|------|-------|----------|
| GITHUB_APP_ID | ID của GitHub App | GitHub > Settings > Developer Settings > GitHub Apps |
| GITHUB_INSTALLATION_ID | ID cài đặt app | Sau khi install app vào org |
| GITHUB_CLIENT_ID | OAuth Client ID | GitHub App settings |
| GITHUB_CLIENT_SECRET | OAuth Client Secret | GitHub App settings |
| GITHUB_WEBHOOK_SECRET | Secret cho webhook | Tự tạo chuỗi ngẫu nhiên |
| GITHUB_ORGANIZATION | Tên organization | Ví dụ: hung-org-117 |
| GITHUB_APP_PRIVATE_KEY | Đường dẫn file .pem | /app/builddefection.2025-11-17.private-key.pem |
| GITHUB_TOKENS | Danh sách PAT tokens | ghp_token1,ghp_token2 |

#### Nhóm 3: Dịch vụ bên ngoài

| Biến | Mô tả | Giá trị mặc định |
|------|-------|------------------|
| RABBITMQ_USER | Username RabbitMQ | myuser |
| RABBITMQ_PASS | Password RabbitMQ | (đặt password mạnh) |
| GRAFANA_PASSWORD | Password admin Grafana | (đặt password mạnh) |
| CELERY_CONCURRENCY | Số worker đồng thời | 4 |

#### Nhóm 4: SonarQube (cấu hình sau khi deploy)

| Biến | Mô tả |
|------|-------|
| SONAR_DB_PASSWORD | Password PostgreSQL cho SonarQube |
| SONAR_TOKEN | Token API (tạo sau khi SonarQube chạy) |
| SONAR_WEBHOOK_SECRET | Secret cho webhook từ SonarQube |

---

## 4. TRIỂN KHAI ỨNG DỤNG

### 4.1 Đảm bảo file Private Key

Kiểm tra file GitHub App Private Key (.pem) nằm ở thư mục gốc project:

```
ls -la builddefection.2025-11-17.private-key.pem
```

### 4.2 Build Docker images

```
docker compose -f docker-compose.prod.yml build
```

### 4.3 Khởi động tất cả services

```
docker compose -f docker-compose.prod.yml up -d
```

### 4.4 Kiểm tra trạng thái

```
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
```

---

## 5. CẤU HÌNH SAU TRIỂN KHAI

### 5.1 Cấu hình SonarQube

**Bước 1:** Chờ SonarQube khởi động (2-3 phút)

```
docker compose -f docker-compose.prod.yml logs -f sonarqube
```

**Bước 2:** Truy cập SonarQube

- URL: http://YOUR_SERVER_IP:9000
- Đăng nhập: admin / admin
- ĐỔI MẬT KHẨU NGAY LẬP TỨC

**Bước 3:** Tạo API Token

```
curl -u "admin:YOUR_NEW_PASSWORD" -X POST \
  "http://localhost:9000/api/user_tokens/generate" \
  -d "name=build-risk-token" -d "type=USER_TOKEN"
```

Copy token nhận được và cập nhật vào file .env: SONAR_TOKEN=...

**Bước 4:** Tạo Webhook

```
curl -u "admin:YOUR_NEW_PASSWORD" -X POST \
  "http://localhost:9000/api/webhooks/create" \
  -d "name=Build Risk Webhook" \
  -d "url=http://backend:8000/api/integrations/webhooks/sonarqube/pipeline" \
  -d "secret=YOUR_SONAR_WEBHOOK_SECRET"
```

**Bước 5:** Restart Backend

```
docker compose -f docker-compose.prod.yml restart backend celery-worker
```

### 5.2 Xác nhận Grafana

- URL: http://YOUR_SERVER_IP:3001
- Đăng nhập: admin / (password từ GRAFANA_PASSWORD)
- Kiểm tra folder "Build Risk Dashboard"

### 5.3 Kiểm tra Trivy

```
curl http://localhost:4954/healthz
```

---

## 6. KIẾN TRÚC HỆ THỐNG

### 6.1 Danh sách Services và Ports

| Service | Port | Mô tả | URL truy cập |
|---------|------|-------|--------------|
| Frontend | 3000 | Giao diện người dùng | http://IP:3000 |
| Backend | 8000 | API Server | http://IP:8000 |
| Grafana | 3001 | Dashboard giám sát | http://IP:3001 |
| SonarQube | 9000 | Phân tích code | http://IP:9000 |
| RabbitMQ | 15672 | Message broker UI | http://IP:15672 |
| Prometheus | 9090 | Thu thập metrics | http://IP:9090 |
| MongoDB | 27017 | Database | Internal |
| Redis | 6379 | Cache | Internal |
| Trivy | 4954 | Vulnerability scanner | Internal |
| Loki | 3100 | Log aggregation | Internal |

### 6.2 Sơ đồ kiến trúc

```
+------------------+      +------------------+      +------------------+
|    Frontend      |      |     Backend      |      |   Celery Worker  |
|    (Next.js)     |----->|    (FastAPI)     |----->|   (Background)   |
|    Port: 3000    |      |    Port: 8000    |      |                  |
+------------------+      +--------+---------+      +--------+---------+
                                   |                         |
                                   v                         v
+------------------+      +------------------+      +------------------+
|     MongoDB      |      |      Redis       |      |    RabbitMQ      |
|    Database      |      |      Cache       |      |  Message Queue   |
|   Port: 27017    |      |   Port: 6379     |      |   Port: 5672     |
+------------------+      +------------------+      +------------------+
                                   
+------------------+      +------------------+      +------------------+
|    SonarQube     |      |      Trivy       |      |     Grafana      |
|   Code Analysis  |      | Vuln. Scanner    |      |   Monitoring     |
|   Port: 9000     |      |   Port: 4954     |      |   Port: 3001     |
+------------------+      +------------------+      +------------------+
```

---

## 7. CÁC LỆNH THƯỜNG DÙNG

### 7.1 Quản lý Docker

| Mục đích | Lệnh |
|----------|------|
| Dừng tất cả services | docker compose -f docker-compose.prod.yml down |
| Xem logs tất cả | docker compose -f docker-compose.prod.yml logs -f |
| Xem logs backend | docker compose -f docker-compose.prod.yml logs -f backend |
| Xem logs worker | docker compose -f docker-compose.prod.yml logs -f celery-worker |
| Restart một service | docker compose -f docker-compose.prod.yml restart [service] |
| Rebuild và restart | docker compose -f docker-compose.prod.yml up -d --build |

### 7.2 Kiểm tra hệ thống

| Mục đích | Lệnh |
|----------|------|
| Kiểm tra hàng đợi RabbitMQ | docker exec prod-rabbitmq rabbitmqctl list_queues |
| Kiểm tra health backend | curl http://localhost:8000/api/health |
| Kiểm tra health Trivy | curl http://localhost:4954/healthz |

### 7.3 Backup và Restore

| Mục đích | Lệnh |
|----------|------|
| Backup MongoDB | docker exec prod-mongo mongodump --archive=/data/backup.gz --gzip |
| Restore MongoDB | docker exec -i prod-mongo mongorestore --archive=/data/backup.gz --gzip |

---

## 8. XỬ LÝ SỰ CỐ

### 8.1 GitHub App lỗi 401/403

| Nguyên nhân | Giải pháp |
|-------------|-----------|
| Sai đường dẫn private key | Kiểm tra GITHUB_APP_PRIVATE_KEY trong .env |
| Thiếu file .pem | Kiểm tra file .pem có tồn tại ở thư mục gốc |
| Sai APP_ID hoặc INSTALLATION_ID | Kiểm tra lại các giá trị từ GitHub |

### 8.2 SonarQube Out of Memory

| Vấn đề | Giải pháp |
|--------|-----------|
| Exit code 78 hoặc 137 | Chạy lệnh: sudo sysctl -w vm.max_map_count=262144 |
| Thiếu RAM | Đảm bảo server có ít nhất 8GB RAM |

### 8.3 Celery Worker không chạy task

| Nguyên nhân | Giải pháp |
|-------------|-----------|
| Thiếu cấu hình | Đảm bảo GITHUB_ORGANIZATION đã set trong .env |
| RabbitMQ chưa sẵn sàng | Kiểm tra: docker compose logs rabbitmq |
| Lỗi task | Xem logs: docker compose logs celery-worker |

### 8.4 GitHub Webhook không nhận được

| Nguyên nhân | Giải pháp |
|-------------|-----------|
| Firewall chặn | Mở port 8000 trên GCP/AWS firewall |
| Backend không chạy | Kiểm tra: docker compose ps |
| Sai webhook secret | Đảm bảo GITHUB_WEBHOOK_SECRET khớp giữa .env và GitHub App |

### 8.5 GitHub API Rate Limit

| Nguyên nhân | Giải pháp |
|-------------|-----------|
| Dùng quá nhiều API calls | Thêm nhiều PATs vào GITHUB_TOKENS |
| Redis không chạy | Kiểm tra Redis để token pool hoạt động |
| Xem logs | docker compose logs backend \| grep "rate limit" |

---

## PHỤ LỤC A: Mở Firewall trên GCP

Nếu triển khai trên Google Cloud Platform, cần mở các port sau:

```
gcloud compute firewall-rules create allow-build-risk-dashboard \
  --allow tcp:3000,tcp:8000,tcp:3001,tcp:9000 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow Build Risk Dashboard ports"
```

Để tắt truy cập khi không cần thiết:

```
gcloud compute firewall-rules update allow-build-risk-dashboard --disabled
```

Để bật lại:

```
gcloud compute firewall-rules update allow-build-risk-dashboard --no-disabled
```

---

## PHỤ LỤC B: Cấu hình GitHub Webhook

1. Truy cập GitHub > Settings > Developer Settings > GitHub Apps > [Your App]
2. Trong phần Webhook:
   - Webhook URL: http://YOUR_GCP_EXTERNAL_IP:8000/api/webhook/github
   - Webhook secret: Cùng giá trị với GITHUB_WEBHOOK_SECRET trong .env
   - Content type: application/json
3. Subscribe events: Workflow run, Push, Pull request

---

**Hết tài liệu**
