# CI/CD Build Risk Assessment System

Hệ thống đánh giá rủi ro cho các lần build trong pipeline CI/CD sử dụng Bayesian CNN.

**Đồ án Tốt Nghiệp - HUST 2025**

---

## 🎯 Giới Thiệu

Hệ thống tự động giám sát, phân tích và đánh giá mức độ rủi ro của các lần build trong pipeline CI/CD. Sử dụng Machine Learning (Bayesian CNN) để dự đoán điểm rủi ro kèm độ bất định, giúp team DevOps ra quyết định deploy an toàn hơn.

### Tính Năng Chính

✅ **Giám sát Build**: Tự động thu thập dữ liệu từ GitHub Actions/CircleCI  
✅ **Phân tích Code**: Tích hợp SonarQube cho quality metrics  
✅ **AI Risk Score**: Bayesian CNN dự đoán điểm rủi ro với độ tin cậy  
✅ **Dashboard**: Visualization với charts và trends  

### Quản Lý Người Dùng & Phân Quyền

- **Administrator** – Quản trị users, repositories, cấu hình hệ thống; có thể chỉnh ngưỡng rủi ro, rescan builds và cập nhật thiết lập chung.
- **DevOps Engineer** – Import repositories, theo dõi dashboard rủi ro và nhận cảnh báo đối với builds nguy hiểm hoặc độ bất định cao.
- **Repository Member (GitHub Authenticated)** – Người dùng đăng nhập bằng GitHub, chỉ đọc dashboard/analytics và nhận cảnh báo cho các repository mà họ sở hữu hoặc cộng tác.

---

## 🚀 Quick Start (5 phút)

### Yêu Cầu
- Docker Desktop (khuyến nghị) hoặc Node.js 18+ + Python 3.10+ + MongoDB 6+

### Chạy với Docker

```bash
# Clone và di chuyển vào thư mục
cd /Users/hunglai/hust/20251/thesis/build-risk-ui

# Setup environment
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local

# Chạy tất cả services
docker-compose up --build
```

### Truy Cập

- 🌐 **Frontend**: http://localhost:3000
- ⚙️ **Backend API**: http://localhost:8000
- 📖 **API Docs**: http://localhost:8000/api/docs
- 🗄️ **MongoDB**: mongodb://localhost:27017

---

## 📚 Tài Liệu

| Tài liệu | Mô tả |
|----------|-------|
| [QUICKSTART.md](docs/QUICKSTART.md) | Hướng dẫn bắt đầu nhanh cho người mới |
| [SETUP.md](docs/SETUP.md) | Hướng dẫn cài đặt chi tiết (Docker & Local) |
| [ROADMAP.md](docs/ROADMAP.md) | Kế hoạch triển khai theo tuần |

---

## 🏗️ Kiến Trúc Hệ Thống

```
┌─────────────┐      ┌─────────────┐      ┌──────────────┐
│   Frontend  │─────▶│   Backend   │─────▶│   MongoDB     │
│  (Next.js)  │      │  (FastAPI)  │      │   Database    │
└─────────────┘      └─────────────┘      └──────────────┘
                            │
                            ├─────▶ GitHub API
                            ├─────▶ SonarQube API
                            └─────▶ Bayesian CNN Model
```

### Tech Stack

**Frontend**
- Next.js 14 (App Router)
- TailwindCSS + shadcn/ui
- TypeScript
- Axios, Recharts

**Backend**
- FastAPI (Python)
- MongoDB (PyMongo)
- PyTorch (Bayesian CNN)

**DevOps**
- Docker & Docker Compose
- GitHub Actions
- SonarQube

---

## � Cấu Trúc Dự Án

```
build-risk-ui/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/               # API endpoints
│   │   │   ├── health.py     # Health checks
│   │   │   ├── builds.py     # Build management
│   │   │   └── risk.py       # Risk assessment
│   │   ├── models/            # Data models
│   │   │   └── schemas.py          # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── database/          # DB connection helpers (Mongo)
│   │   ├── ml/                # ML model
│   │   ├── config.py          # Configuration
│   │   └── main.py            # App entry point
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── frontend/                   # Next.js Frontend
│   ├── src/
│   │   ├── app/               # Next.js 14 App Router
│   │   │   ├── layout.tsx    # Root layout
│   │   │   ├── page.tsx      # Homepage
│   │   │   └── globals.css   # Global styles
│   │   ├── components/        # React components
│   │   │   └── ui/           # shadcn/ui components
│   │   ├── lib/               # Utilities
│   │   │   ├── api.ts        # API client
│   │   │   └── utils.ts      # Helper functions
│   │   └── types/             # TypeScript types
│   ├── package.json
│   ├── Dockerfile
│   └── .env.example
│
├── docs/                       # Documentation
│   ├── QUICKSTART.md          # Quick start guide
│   ├── SETUP.md               # Detailed setup
│   └── ROADMAP.md             # Development roadmap
│
├── docker-compose.yml          # Docker orchestration
├── .gitignore
└── README.md
```

---

## 🔄 Workflow Phát Triển

### 1. Setup Lần Đầu
```bash
# Xem hướng dẫn chi tiết
cat docs/QUICKSTART.md
```

### 2. Development Mode
```bash
# Backend (uv environment)
cd backend
uv sync                    # tạo virtualenv .venv và cài dependencies
uv run uvicorn app.main:app --reload

# Frontend (terminal mới)
cd frontend
# đảm bảo Node.js >= 18 (ví dụ: export PATH="/opt/homebrew/opt/node@18/bin:$PATH")
npm run dev
```

> ℹ️ Backend mặc định sử dụng MongoDB với biến `MONGODB_URI` (xem `backend/.env.example`).
> Khởi động MongoDB (ví dụ `docker-compose up mongo`) hoặc dùng instance sẵn có trước khi chạy `uvicorn`.

### 3. Production Build
```bash
docker-compose -f docker-compose.prod.yml up --build
```

---

## 🧪 API Endpoints

### Health
- `GET /api/health` - API health check
- `GET /api/health/db` - Database health check

### Builds
- `GET /api/builds/` - List all builds (with pagination)
- `GET /api/builds/{id}` - Get build details with SonarQube & Risk data
- `POST /api/builds/` - Create new build
- `DELETE /api/builds/{id}` - Delete build

### Risk Assessment
- `GET /api/risk/{build_id}` - Get risk score for build
- `GET /api/risk/{build_id}/explanation` - Giải thích chi tiết (drivers, confidence, actions) cho build
- `POST /api/risk/{build_id}/recalculate` - Recalculate risk score

### Dashboard & Integrations
- `GET /api/dashboard/summary` - Aggregate metrics for the dashboard cards/charts
- `GET /api/pipeline/status` - Trạng thái pipeline preprocessing/normalization
- `GET /api/integrations/github` - GitHub OAuth connection status + repository stats
- `POST /api/integrations/github/login` - Generate OAuth URL (creates state token)
- `POST /api/integrations/github/revoke` - Revoke stored GitHub token
- `GET /api/integrations/github/imports` - Danh sách lịch sử repository import jobs
- `POST /api/integrations/github/imports` - Khởi tạo import job cho repository mới
- `GET /api/integrations/github/callback` - OAuth redirect handler (FastAPI)
- `GET/PUT /api/settings` - Đọc & cập nhật system/model settings
- `GET /api/logs` - Danh sách activity logs (audit trail)
- `GET /api/notifications/events` - Feed cảnh báo builds high-risk/high-uncertainty
- `GET/PUT /api/notifications/policy` - Cấu hình threshold & notification channels
- `GET /api/users/roles` - Danh sách vai trò & quyền hạn

### 🔑 GitHub OAuth cấu hình

Tạo file `backend/.env` (tham khảo `.env.example`) và bổ sung:

```
GITHUB_CLIENT_ID=<client-id-tren-github>
GITHUB_CLIENT_SECRET=<client-secret-tren-github>
GITHUB_REDIRECT_URI=http://localhost:8000/api/integrations/github/callback
FRONTEND_BASE_URL=http://localhost:3000
```

Scopes mặc định: `read:user`, `repo`, `read:org`, `workflow`. Sau khi chạy backend, mở dashboard → Integrations → GitHub để ủy quyền.

Xem đầy đủ: http://localhost:8000/api/docs

---

## 📊 Database Schema

### Tables

**builds** - Thông tin build từ CI/CD
- repository, branch, commit_sha, build_number
- status, conclusion, duration_seconds
- author_name, author_email
- started_at, completed_at

**sonarqube_results** - Kết quả phân tích SonarQube
- build_id (FK)
- bugs, vulnerabilities, code_smells
- coverage, technical_debt_minutes
- quality_gate_status



**risk_assessments** - Đánh giá rủi ro bằng ML
- build_id (FK)
- risk_score, uncertainty
- risk_level (low/medium/high/critical)
- model_version

---

## 🎯 Roadmap Phát Triển

### ✅ Đã Hoàn Thành (Tuần 4)
- Khởi tạo cấu trúc dự án
- Backend API cơ bản với FastAPI
- Frontend với Next.js + TailwindCSS
- Database models
- Docker setup
- API documentation

### 🚧 Đang Thực Hiện (Tuần 5)
- Tích hợp GitHub Actions API
- Thu thập dữ liệu builds
- Build list page

### 📅 Kế Hoạch Tiếp Theo
- Tuần 6: SonarQube integration
- Tuần 7-8: Xây dựng Bayesian CNN model
- Tuần 9: Tích hợp ML model vào API
- Tuần 10-11: Dashboard & visualizations
- Tuần 12-13: Testing & optimization

Chi tiết: [ROADMAP.md](docs/ROADMAP.md)

---

## 🤝 Đóng Góp

Đây là đồ án tốt nghiệp. Mọi góp ý xin gửi qua:
- Issues: [GitHub Issues](https://github.com/...)
- Email: [email sinh viên]

---

## 🎓 Thông Tin Đồ Án

- **Tên đề tài**: Xây dựng hệ thống đánh giá rủi ro CI/CD builds sử dụng Bayesian CNN
- **Sinh viên thực hiện**: [Tên - MSSV]
- **Giảng viên hướng dẫn**: [Tên GVHD]
- **Học kỳ**: 20251
- **Trường**: Đại học Bách Khoa Hà Nội (HUST)

---

## � License

© 2025 - Đồ án tốt nghiệp - HUST

---

## 🆘 Support & Troubleshooting

Gặp vấn đề? Xem:
1. [QUICKSTART.md](docs/QUICKSTART.md) - Troubleshooting section
2. [SETUP.md](docs/SETUP.md) - Detailed setup
3. Check logs: `docker-compose logs -f`

Common issues:
- Port already in use: `lsof -i :3000` / `lsof -i :8000`
- Database connection: đảm bảo MongoDB đang chạy (`docker-compose up mongo`)
- Module not found: `npm install` / `pip install -r requirements.txt`
