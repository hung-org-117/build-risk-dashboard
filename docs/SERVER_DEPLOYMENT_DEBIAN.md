# Server Worker Deployment - Debian (Google Cloud)

Hướng dẫn triển khai Backend Services (MongoDB, Redis, RabbitMQ, Celery Workers, SonarQube, Trivy) trên Debian VM (Google Cloud).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Google Cloud VM (Debian)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │ MongoDB  │ │ RabbitMQ │ │  Redis   │ │SonarQube │ │  Trivy   │   │
│  │  :27017  │ │  :5672   │ │  :6379   │ │  :9000   │ │  :4954   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
│                           │                                          │
│              ┌────────────┴────────────┐                            │
│              │      Celery Workers      │                            │
│              └──────────────────────────┘                            │
│                                                                      │
│  Ports exposed: 27017, 5672, 15672, 6379, 9000, 4954, 3001, 3100    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                     SSH Port Forward
                              │
┌─────────────────────────────────────────────────────────────────────┐
│                       Local Machine                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐                 │
│  │   Backend API       │    │     Frontend        │                 │
│  │   uvicorn :8000     │    │   npm run dev :3000 │                 │
│  └─────────────────────┘    └─────────────────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 1. Create Google Cloud VM

### VM Specifications (Recommended)
| Setting | Value |
|---------|-------|
| Machine type | `e2-standard-4` (4 vCPU, 16GB RAM) |
| Boot disk | Debian 12, 50GB SSD |
| Firewall | Allow SSH (port 22) |

### Create VM via gcloud CLI
```bash
gcloud compute instances create build-risk-server \
    --zone=asia-southeast1-a \
    --machine-type=e2-standard-4 \
    --boot-disk-size=50GB \
    --boot-disk-type=pd-ssd \
    --image-family=debian-12 \
    --image-project=debian-cloud \
    --tags=ssh-server
```

---

## 2. SSH to Server

```bash
gcloud compute ssh build-risk-server --zone=asia-southeast1-a
```

---

## 3. Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y ca-certificates curl gnupg

# Add Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

---

## 4. Clone Repository

```bash
cd ~
git clone https://github.com/your-org/build-risk-dashboard.git
cd build-risk-dashboard
```

---

## 5. Run Setup Script

```bash
chmod +x scripts/setup-server.sh
./scripts/setup-server.sh
```

This script will:
- Configure `vm.max_map_count` for SonarQube
- Pre-download Trivy vulnerability database (~600MB)
- Pull all required Docker images

---

## 6. Configure Environment

```bash
cp .env.server.example .env.server
nano .env.server
```

### Required Variables

```bash
# RabbitMQ
RABBITMQ_USER=myuser
RABBITMQ_PASS=<secure-password>

# MongoDB
MONGODB_DB_NAME=buildguard

# GitHub App (copy from your GitHub App settings)
GITHUB_APP_ID=<your-app-id>
GITHUB_APP_PRIVATE_KEY=<path-or-content>
GITHUB_INSTALLATION_ID=<installation-id>

# SonarQube (generate after first start)
SONAR_TOKEN=
SONAR_WEBHOOK_SECRET=<secure-secret>

# Security (MUST match local API)
SECRET_KEY=<your-secret-key>

# Celery
CELERY_CONCURRENCY=4

# Container permissions
APP_UID=$(id -u)
APP_GID=$(id -g)
```

---

## 7. Start Services

```bash
docker compose -f docker-compose.server.yml --env-file .env.server up -d
```

### Check Status
```bash
docker compose -f docker-compose.server.yml ps
docker compose -f docker-compose.server.yml logs -f
```

---

## 8. Configure SonarQube

1. Wait for SonarQube to start (~2-3 minutes):
   ```bash
   docker logs -f server-sonarqube
   ```

2. Access SonarQube: `http://<server-ip>:9000`
   - Default credentials: `admin` / `admin`
   - Change password on first login

3. Generate API Token:
   - Go to **My Account → Security → Generate Token**
   - Copy token and add to `.env.server`:
     ```bash
     SONAR_TOKEN=squ_xxxxxxxxxxxxx
     ```

4. Restart Celery worker:
   ```bash
   docker compose -f docker-compose.server.yml restart celery-worker
   ```

---

## 9. Local Development Setup

### SSH Port Forwarding

On your **local machine**:

```bash
./scripts/ssh-forward-server.sh <username>@<server-ip>
```

Or with gcloud:
```bash
gcloud compute ssh build-risk-server --zone=asia-southeast1-a -- -N \
    -L 27017:localhost:27017 \
    -L 5672:localhost:5672 \
    -L 15672:localhost:15672 \
    -L 6379:localhost:6379 \
    -L 9000:localhost:9000 \
    -L 4954:localhost:4954 \
    -L 3001:localhost:3001 \
    -L 3100:localhost:3100
```

### Configure Local Backend

Edit `backend/.env`:

```bash
# Database (via SSH tunnel)
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=buildguard

# Celery (via SSH tunnel)
CELERY_BROKER_URL=amqp://myuser:<password>@localhost:5672//
REDIS_URL=redis://localhost:6379/0

# SonarQube (via SSH tunnel)
SONAR_HOST_URL=http://localhost:9000
SONAR_TOKEN=<your-token>

# Trivy (via SSH tunnel)
TRIVY_SERVER_URL=http://localhost:4954

# IMPORTANT: Must match server SECRET_KEY
SECRET_KEY=<same-as-server>
```

### Run Local Services

```bash
# Backend
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (new terminal)
cd frontend
npm run dev
```

---

## 10. Useful Commands

### View Logs
```bash
# All services
docker compose -f docker-compose.server.yml logs -f

# Specific service
docker compose -f docker-compose.server.yml logs -f celery-worker
docker compose -f docker-compose.server.yml logs -f sonarqube
```

### Restart Services
```bash
docker compose -f docker-compose.server.yml restart celery-worker
```

### Stop All
```bash
docker compose -f docker-compose.server.yml down
```

### Clean Everything (⚠️ Deletes data)
```bash
docker compose -f docker-compose.server.yml down -v
```

---

## 11. Monitoring

| Service | URL |
|---------|-----|
| RabbitMQ Management | `http://localhost:15672` |
| SonarQube | `http://localhost:9000` |
| Grafana | `http://localhost:3001` (admin/admin) |

---

## Troubleshooting

### SonarQube không start
```bash
# Check vm.max_map_count
sysctl vm.max_map_count
# Must be >= 262144

# If not, set it:
sudo sysctl -w vm.max_map_count=262144
```

### Celery worker không connect được MongoDB
```bash
# Check MongoDB replica set status
docker exec -it server-mongo mongosh --eval "rs.status()"
```

### Permission denied on volumes
```bash
# Update APP_UID/APP_GID in .env.server
id -u && id -g
```
