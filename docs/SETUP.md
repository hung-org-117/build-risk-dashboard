# Hướng Dẫn Cài Đặt và Chạy Dự Án

## 📋 Yêu Cầu Hệ Thống

- **Node.js**: 18.x trở lên
- **Python**: 3.10 trở lên
- **MongoDB**: 6.x trở lên (hoặc Docker)
- **Docker** và **Docker Compose** (khuyến nghị)

> ⚠️ Ghi chú: Tài liệu cũ còn đề cập tới PostgreSQL. Từ phiên bản hiện tại, backend sử dụng **MongoDB** với PyMongo. Nếu đang dùng Docker Compose, chỉ cần đảm bảo service `mongo` chạy trước backend.

## 🚀 Cách 1: Chạy với Docker (Khuyến Nghị)

### Bước 1: Clone repository và di chuyển vào thư mục dự án

```bash
cd /Users/hunglai/hust/20251/thesis/build-risk-ui
```

### Bước 2: Tạo file .env cho backend

```bash
cd backend
cp .env.example .env
# Chỉnh sửa .env nếu cần
cd ..
```

### Bước 3: Tạo file .env cho frontend

```bash
cd frontend
cp .env.example .env.local
# Chỉnh sửa .env.local nếu cần
cd ..
```

### Bước 4: Chạy tất cả services với Docker Compose

```bash
docker-compose up --build
```

Hệ thống sẽ khởi động:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/api/docs
- **MongoDB**: mongodb://localhost:27017

### Bước 5: Dừng services

```bash
docker-compose down
```

Để xóa cả dữ liệu database:
```bash
docker-compose down -v
```

---

## 🔧 Cách 2: Chạy Local (Không dùng Docker)

### A. Setup Backend

#### 1. Cài đặt MongoDB

**macOS:**
```bash
brew tap mongodb/brew
brew install mongodb-community@6.0
brew services start mongodb-community@6.0
```

#### 2. Khởi tạo database (tùy chọn)

MongoDB sẽ tự tạo database khi backend ghi dữ liệu. Có thể kiểm tra nhanh bằng:

```bash
mongosh --eval "db.getSiblingDB('buildguard').stats()"
```

#### 3. Setup Python environment

```bash
cd backend

# Tạo virtual environment
python3 -m venv venv

# Kích hoạt virtual environment
source venv/bin/activate  # macOS/Linux

# Cài đặt dependencies
pip install -r requirements.txt
```

#### 4. Cấu hình environment

```bash
cp .env.example .env
```

Chỉnh sửa file `.env`:
```
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=buildguard
GITHUB_TOKEN=your_github_token_here
DEBUG=True
```

#### 5. Chạy backend server

```bash
# Đảm bảo virtual environment đang active
python -m uvicorn app.main:app --reload
```

Backend sẽ chạy tại: http://localhost:8000

---

### B. Setup Frontend

#### 1. Cài đặt dependencies

```bash
cd frontend
npm install
```

#### 2. Cấu hình environment

```bash
cp .env.example .env.local
```

File `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api
```

#### 3. Chạy frontend development server

```bash
npm run dev
```

Frontend sẽ chạy tại: http://localhost:3000

---

## 🧪 Kiểm Tra Hệ Thống

### 1. Kiểm tra Backend

```bash
curl http://localhost:8000/api/health
```

Kết quả mong đợi:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-01T...",
  "service": "Build Risk Assessment API"
}
```

### 2. Kiểm tra Database Connection

```bash
curl http://localhost:8000/api/health/db
```

### 3. Xem API Documentation

Mở browser: http://localhost:8000/api/docs

---

## 📁 Cấu Trúc Dự Án

```
build-risk-ui/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── database/       # MongoDB config/helpers
│   │   ├── models/         # Pydantic schemas
│   │   ├── services/       # Business logic
│   │   ├── ml/             # ML model
│   │   └── main.py         # App entry point
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/               # Next.js Frontend
│   ├── src/
│   │   ├── app/           # Next.js 14 app directory
│   │   ├── components/    # React components
│   │   ├── lib/           # Utilities & API client
│   │   └── types/         # TypeScript types
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml      # Docker orchestration
└── README.md
```

---

## 🔑 Các Tính Năng Hiện Tại

✅ Backend API với FastAPI
✅ Database MongoDB với PyMongo
✅ Frontend Next.js 14 với TailwindCSS
✅ API Documentation tự động (Swagger)
✅ Docker containerization
✅ Health check endpoints

## 🚧 Đang Phát Triển

- [ ] Tích hợp GitHub Actions API
- [ ] Tích hợp SonarQube
- [ ] Bayesian CNN model
- [ ] Dashboard với charts
- [ ] Authentication

---

## 📝 Ghi Chú Phát Triển

### Thêm một API endpoint mới

1. Tạo router trong `backend/app/api/`
2. Định nghĩa schema trong `backend/app/models/schemas.py`
3. Thêm router vào `backend/app/main.py`

### Thêm một page mới trong Frontend

1. Tạo folder trong `frontend/src/app/`
2. Tạo `page.tsx` trong folder đó
3. Next.js sẽ tự động routing

## 🐛 Troubleshooting

### Lỗi kết nối Database

```bash
# Kiểm tra MongoDB đang chạy
brew services list  # macOS

# Kiểm tra connection string trong .env
```

### Lỗi port đã được sử dụng

```bash
# Tìm process đang dùng port
lsof -i :8000  # Backend
lsof -i :3000  # Frontend

# Kill process
kill -9 <PID>
```

### Lỗi module Python

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

---

## 📞 Hỗ Trợ

Nếu gặp vấn đề, hãy kiểm tra:
1. Logs của Docker container: `docker-compose logs -f`
2. Backend logs trong terminal
3. Browser console cho frontend errors

---

## 📚 Tài Liệu Tham Khảo

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
- [shadcn/ui Components](https://ui.shadcn.com/)
- [PyMongo Tutorial](https://pymongo.readthedocs.io/en/stable/tutorial.html)
- [Docker Compose](https://docs.docker.com/compose/)
