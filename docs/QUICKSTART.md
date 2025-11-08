# Quick Start Guide - Bắt Đầu Nhanh

## 🎯 Bước 1: Clone và Setup Môi Trường

### Chuẩn bị
Đảm bảo bạn đã cài đặt:
- Docker Desktop (khuyến nghị) HOẶC
- Node.js 18+, Python 3.10+, MongoDB 6+

### Setup với Docker (Dễ nhất)

```bash
# Di chuyển vào thư mục dự án
cd /Users/hunglai/hust/20251/thesis/build-risk-ui

# Tạo file environment cho backend
cp backend/.env.example backend/.env

# Tạo file environment cho frontend  
cp frontend/.env.example frontend/.env.local

# Chạy tất cả với Docker
docker-compose up --build
```

Đợi khoảng 2-3 phút để các services khởi động.

### Kiểm tra

Mở các URL sau trong browser:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/api/health
- API Docs: http://localhost:8000/api/docs

Bạn sẽ thấy:
- ✅ Homepage của dự án
- ✅ API response: `{"status": "healthy"}`
- ✅ Swagger API documentation

---

## 🎯 Bước 2: Test API Endpoints

### Sử dụng Swagger UI

1. Mở http://localhost:8000/api/docs
2. Thử các endpoints:
   - `GET /api/health` - Health check
   - `GET /api/health/db` - Database check
   - `GET /api/builds/` - Lấy danh sách builds

### Sử dụng curl

```bash
# Health check
curl http://localhost:8000/api/health

# Database health
curl http://localhost:8000/api/health/db

# Lấy danh sách builds
curl http://localhost:8000/api/builds/
```

### Tạo Build Mẫu

```bash
curl -X POST http://localhost:8000/api/builds/ \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "user/test-repo",
    "branch": "main",
    "commit_sha": "abc123",
    "build_number": "1",
    "status": "success"
  }'
```

---

## 🎯 Bước 3: Khám Phá Frontend

### Homepage
- Mở http://localhost:3000
- Xem giới thiệu dự án
- Click "Xem Danh sách Builds" (sẽ tạo page này ở bước tiếp theo)

### Cấu Trúc Frontend
```
frontend/src/
├── app/
│   ├── layout.tsx          # Layout chính
│   ├── page.tsx            # Homepage
│   └── globals.css         # Global styles
├── components/
│   └── ui/                 # shadcn/ui components
├── lib/
│   ├── api.ts             # API client
│   └── utils.ts           # Utilities
└── types/
    └── index.ts           # TypeScript types
```

---

## 🎯 Bước 4: Tạo GitHub Token (Quan Trọng!)

### Để tích hợp GitHub Actions, bạn cần Personal Access Token:

1. Vào GitHub: https://github.com/settings/tokens
2. Click "Generate new token" > "Generate new token (classic)"
3. Đặt tên: `Build Risk Assessment`
4. Chọn quyền:
   - ✅ `repo` (Full control of private repositories)
   - ✅ `workflow` (Update GitHub Action workflows)
5. Click "Generate token"
6. **QUAN TRỌNG**: Copy token ngay (chỉ hiện 1 lần!)

### Thêm Token vào .env

```bash
# Mở file backend/.env
# Thêm dòng:
GITHUB_TOKEN=ghp_your_token_here
```

Nếu dùng Docker, restart services:
```bash
docker-compose down
docker-compose up
```

---

## 🎯 Bước 5: Bắt Đầu Development

### Workflow Development

1. **Backend Development**:
   ```bash
   cd backend
   source venv/bin/activate
   # Sửa code trong app/
   # API tự reload khi save
   ```

2. **Frontend Development**:
   ```bash
   cd frontend
   # Sửa code trong src/
   # Browser tự reload
   ```

3. **Database Changes**:
   ```bash
   cd backend
   # Thay đổi models trong app/models/database_models.py
   # Restart backend để tạo tables mới
   ```

---

## 🎯 Bước 6: Triển Khai Tính Năng Đầu Tiên

### Tạo Page "Builds" để hiển thị danh sách builds

#### 1. Tạo file frontend/src/app/builds/page.tsx:

```typescript
'use client'

import { useEffect, useState } from 'react'
import { buildApi } from '@/lib/api'
import { Build } from '@/types'

export default function BuildsPage() {
  const [builds, setBuilds] = useState<Build[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchBuilds()
  }, [])

  const fetchBuilds = async () => {
    try {
      const data = await buildApi.getAll()
      setBuilds(data.builds || [])
    } catch (error) {
      console.error('Error fetching builds:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">Build History</h1>
      
      {loading ? (
        <p>Loading...</p>
      ) : builds.length === 0 ? (
        <p>No builds found. Create one using the API.</p>
      ) : (
        <div className="grid gap-4">
          {builds.map((build) => (
            <div key={build.id} className="border p-4 rounded">
              <h3 className="font-bold">{build.repository}</h3>
              <p>Branch: {build.branch}</p>
              <p>Status: {build.status}</p>
              <p>Build: #{build.build_number}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

#### 2. Test page mới:
- Mở http://localhost:3000/builds
- Nếu chưa có builds, tạo một build mẫu bằng API (xem Bước 2)

---

## 📚 Tài Nguyên Học Tập

### Backend (FastAPI)
- Official Docs: https://fastapi.tiangolo.com/
- Tutorial: https://fastapi.tiangolo.com/tutorial/

### Frontend (Next.js)
- Official Docs: https://nextjs.org/docs
- Learn Next.js: https://nextjs.org/learn

### UI Components (shadcn/ui)
- Components: https://ui.shadcn.com/docs/components
- Installation: https://ui.shadcn.com/docs/installation/next

### Database (MongoDB)
- MongoDB University: https://learn.mongodb.com/
- PyMongo Quickstart: https://pymongo.readthedocs.io/en/stable/tutorial.html

---

## 🐛 Troubleshooting

### Backend không chạy
```bash
# Kiểm tra logs
docker-compose logs backend

# Hoặc nếu chạy local:
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload
```

### Frontend không chạy
```bash
# Kiểm tra logs
docker-compose logs frontend

# Hoặc reinstall dependencies:
cd frontend
rm -rf node_modules .next
npm install
npm run dev
```

### Database connection error
```bash
# Kiểm tra MongoDB
docker-compose ps

# Restart database
docker-compose restart mongo
```

### Port đã được sử dụng
```bash
# Tìm process
lsof -i :3000  # Frontend
lsof -i :8000  # Backend

# Kill process
kill -9 <PID>
```

---

## 📝 Next Steps

Sau khi hoàn thành Quick Start, đọc tiếp:

1. **ROADMAP.md** - Kế hoạch chi tiết theo tuần
2. **SETUP.md** - Hướng dẫn setup chi tiết
3. Bắt đầu **Tuần 5** trong ROADMAP: Tích hợp GitHub Actions

---

## ✅ Checklist

- [ ] Docker Desktop đã cài và chạy
- [ ] `docker-compose up` thành công
- [ ] Frontend http://localhost:3000 hoạt động
- [ ] Backend http://localhost:8000/api/docs hoạt động
- [ ] Database connection OK (check /api/health/db)
- [ ] Đã tạo GitHub Personal Access Token
- [ ] Token đã thêm vào backend/.env
- [ ] Test tạo build mẫu qua API thành công
- [ ] Tạo page /builds và test thành công

Khi hoàn thành checklist này, bạn đã sẵn sàng phát triển các tính năng tiếp theo! 🚀
