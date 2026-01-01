# Production Deployment Guide

Hướng dẫn deploy Build Risk Dashboard lên Google VM với GitHub Actions.

## Mục lục

- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cấu hình VM](#cấu-hình-vm)
- [Cấu hình GitHub Secrets](#cấu-hình-github-secrets)
- [Thiết lập SSL](#thiết-lập-ssl)
- [Deploy lần đầu](#deploy-lần-đầu)
- [Deploy tự động](#deploy-tự-động)
- [Troubleshooting](#troubleshooting)

---

## Yêu cầu hệ thống

### Google VM

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| vCPU | 4 | 8 |
| RAM | 16 GB | 32 GB |
| Disk | 100 GB SSD | 200 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Software trên VM

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin
sudo apt install docker-compose-plugin -y

# Install Git
sudo apt install git -y

# Logout và login lại để apply docker group
```

---

## Cấu hình VM

### 1. Clone repository

```bash
cd ~
git clone https://github.com/YOUR_USERNAME/build-risk-dashboard.git
cd build-risk-dashboard
```

### 2. Tạo file environment

```bash
cp .env.prod.example .env
nano .env
```

Cập nhật các giá trị trong `.env`:

```bash
# Domain hoặc IP của bạn (không bắt buộc cho HTTP-only)
DOMAIN_NAME=your-domain-or-ip

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)
NEXTAUTH_SECRET=$(openssl rand -hex 32)

# Cập nhật URLs (HTTP-only)
NEXT_PUBLIC_API_URL=http://your-domain-or-ip/api
NEXT_PUBLIC_WS_URL=ws://your-domain-or-ip/api/ws/events
NEXTAUTH_URL=http://your-domain-or-ip
```

### 3. Cấu hình Nginx

`nginx/nginx.conf` hiện dùng `server_name _;` nên không cần chỉnh khi dùng IP.
Nếu muốn ràng buộc theo domain, hãy sửa `server_name` thủ công.

---

## Cấu hình GitHub Secrets

Vào repository → Settings → Secrets and variables → Actions → New repository secret

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `VM_HOST` | IP hoặc hostname của VM | `35.123.45.67` |
| `VM_USER` | SSH username | `your-username` |
| `VM_SSH_KEY` | Private SSH key | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `VM_SSH_PORT` | SSH port (optional) | `22` |
| `DEPLOY_PATH` | Đường dẫn project trên VM | `/home/username/build-risk-dashboard` |

### Tạo SSH key

```bash
# Trên local machine
ssh-keygen -t ed25519 -C "github-deploy" -f ~/.ssh/github_deploy

# Copy public key lên VM
ssh-copy-id -i ~/.ssh/github_deploy.pub user@VM_HOST

# Lấy private key để paste vào GitHub Secret
cat ~/.ssh/github_deploy
```

---

## Thiết lập SSL

Hiện `docker-compose.prod.yml` và `nginx/nginx.conf` chỉ cấu hình HTTP (port 80).
Nếu bạn chỉ dùng IP thì có thể bỏ qua phần này.
Nếu cần HTTPS, bạn phải bổ sung TLS termination (ví dụ: Nginx + Certbot hoặc load balancer)
và cập nhật compose/nginx tương ứng.

---

## Deploy lần đầu

```bash
cd ~/build-risk-dashboard

# Đảm bảo .env đã được cấu hình
cat .env

# Chạy deployment
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

### Kiểm tra services

```bash
# Xem containers đang chạy
docker compose -f docker-compose.prod.yml ps

# Xem logs
docker compose -f docker-compose.prod.yml logs -f

# Xem logs của service cụ thể
docker compose -f docker-compose.prod.yml logs -f backend
```

---

## Deploy tự động

### Workflow triggers

1. **Push tag**: Deploy tự động khi push tag `v*`
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Manual dispatch**: Vào Actions tab → Deploy to Google VM → Run workflow

### Theo dõi deployment

1. Vào GitHub → Actions tab
2. Click vào workflow run đang chạy
3. Xem logs real-time

---

## Rollback

Nếu deploy có lỗi, rollback về version trước:

```bash
# SSH vào VM
ssh user@VM_HOST

cd ~/build-risk-dashboard

# Xem các tags có sẵn
git tag -l

# Checkout version cũ
git checkout v1.0.0

# Chạy lại deployment
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

---

## Troubleshooting

### Container không khởi động

```bash
# Xem logs chi tiết
docker compose -f docker-compose.prod.yml logs backend

# Restart container cụ thể
docker compose -f docker-compose.prod.yml restart backend
```

### SSL không hoạt động

```bash
# Kiểm tra certificate
docker compose -f docker-compose.prod.yml exec nginx ls -la /etc/letsencrypt/live/

# Kiểm tra nginx config
docker compose -f docker-compose.prod.yml exec nginx nginx -t
```

### MongoDB không healthy

```bash
# Kiểm tra replica set
docker compose -f docker-compose.prod.yml exec mongo mongosh --eval "rs.status()"
```

### Celery worker lỗi

```bash
# Xem logs
docker compose -f docker-compose.prod.yml logs celery-worker

# Restart workers
docker compose -f docker-compose.prod.yml restart celery-worker celery-beat
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Google VM                                    │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                     Nginx (80)                               │    │
│  │              SSL Termination + Reverse Proxy                 │    │
│  └─────────────┬──────────────────────────────┬────────────────┘    │
│                │                              │                      │
│     ┌──────────▼──────────┐      ┌───────────▼───────────┐          │
│     │   Frontend (:3000)  │      │   Backend API (:8000)  │          │
│     │      Next.js        │      │       FastAPI          │          │
│     └─────────────────────┘      └───────────┬───────────┘          │
│                                              │                       │
│  ┌───────────────────────────────────────────┼───────────────────┐  │
│  │                    Message Queue          │                   │  │
│  │  ┌────────┐ ┌─────────┐ ┌───────┐        │                   │  │
│  │  │MongoDB │ │RabbitMQ │ │ Redis │        │                   │  │
│  │  └────────┘ └────┬────┘ └───────┘        │                   │  │
│  │                  │                        │                   │  │
│  │       ┌──────────▼────────────────────────▼─────────┐        │  │
│  │       │          Celery Workers + Beat               │        │  │
│  │       │   (ingestion, processing, validation, etc)   │        │  │
│  │       └──────────────────────────────────────────────┘        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Monitoring & Scanners                       │  │
│  │  ┌──────────┐ ┌────────┐ ┌───────────┐ ┌──────────────────┐   │  │
│  │  │ Grafana  │ │  Loki  │ │ SonarQube │ │      Trivy       │   │  │
│  │  └──────────┘ └────────┘ └───────────┘ └──────────────────┘   │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```
