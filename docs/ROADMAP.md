# Kế Hoạch Triển Khai Đồ Án Theo Tuần

## ✅ Đã Hoàn Thành - Tuần 4 (Setup Cơ Bản)

### Backend
- [x] Khởi tạo dự án FastAPI
- [x] Cấu hình database MongoDB với PyMongo
- [x] Tạo models cho Build, SonarQubeResult, RiskAssessment
- [x] API endpoints cơ bản:
  - Health check (`/api/health`, `/api/health/db`)
  - Builds management (`/api/builds/`)
  - Risk assessment (`/api/risk/{build_id}`)
- [x] API documentation tự động với Swagger

### Frontend
- [x] Khởi tạo Next.js 14 project
- [x] Cấu hình TailwindCSS
- [x] Setup shadcn/ui components (Button, Card)
- [x] Tạo homepage với giới thiệu dự án
- [x] API client với axios

### DevOps
- [x] Docker setup cho backend
- [x] Docker setup cho frontend
- [x] Docker Compose orchestration
- [x] Environment configuration

---

## 🚧 Tuần 5: Tích Hợp GitHub Actions API

### Mục tiêu
- Kết nối với GitHub API để lấy danh sách workflow runs
- Thu thập thông tin build từ GitHub Actions
- Hiển thị danh sách builds trên frontend

### Tasks Backend
- [ ] Tạo `GitHubService` trong `backend/app/services/github_service.py`
  - Authenticate với GitHub API
  - Lấy danh sách workflow runs
  - Parse dữ liệu build
- [ ] API endpoint `/api/github/sync/{owner}/{repo}` để sync builds
- [ ] Background job để tự động sync builds định kỳ
- [ ] Lưu build data vào database

### Tasks Frontend
- [ ] Tạo page `/builds` để hiển thị danh sách builds
- [ ] Components:
  - `BuildList`: Hiển thị table builds
  - `BuildCard`: Card cho mỗi build
  - `BuildFilters`: Lọc theo status, repository, branch
  - `Pagination`: Phân trang
- [ ] Kết nối với API để fetch builds

### Files cần tạo
```
backend/app/services/github_service.py
backend/app/api/github.py
frontend/src/app/builds/page.tsx
frontend/src/components/BuildList.tsx
frontend/src/components/BuildCard.tsx
frontend/src/components/BuildFilters.tsx
```

---

## 📅 Tuần 6: Tối Ưu SonarQube & Báo Cáo Rủi Ro

### Mục tiêu
- Kết nối với SonarQube API
- Lưu kết quả phân tích vào database
- Chuẩn hóa thông tin rủi ro để hiển thị dashboard

### Tasks Backend
- [ ] `SonarQubeService` - Lấy metrics từ SonarQube API
- [ ] API endpoints:
  - `/api/sonarqube/analyze/{build_id}`
- [ ] Tự động chạy scan khi có build mới
- [ ] Lưu history quality gate + mapping sang risk score

### Tasks Frontend
- [ ] Trang chi tiết build `/builds/[id]`
- [ ] Components hiển thị:
  - SonarQube metrics (bugs, code smells, coverage)
  - Risk insights & timeline
  - Charts cho metrics

### Files cần tạo
```
backend/app/services/sonarqube_service.py
backend/app/api/sonarqube.py
frontend/src/app/builds/[id]/page.tsx
frontend/src/components/SonarQubeMetrics.tsx
frontend/src/components/SecurityInsights.tsx
```

---

## 📅 Tuần 7-8: Xây Dựng ML Model

### Mục tiêu
- Thu thập và chuẩn bị dataset
- Xây dựng Bayesian CNN model
- Huấn luyện model

### Tasks
- [ ] Thu thập dữ liệu từ builds đã sync
- [ ] Feature engineering:
  - Build metrics (duration, status, test results)
  - SonarQube metrics
  - Code ownership features
- [ ] Implement Bayesian CNN với PyTorch
- [ ] Training pipeline
- [ ] Model evaluation
- [ ] Save trained model

### Files cần tạo
```
backend/app/ml/data_preprocessing.py
backend/app/ml/bayesian_cnn.py
backend/app/ml/train.py
backend/app/ml/evaluate.py
scripts/prepare_dataset.py
scripts/train_model.py
```

---

## 📅 Tuần 9: Tích Hợp ML Model vào API

### Mục tiêu
- Load trained model vào backend
- API endpoint để predict risk score
- Hiển thị risk score trên frontend

### Tasks Backend
- [ ] `MLPredictor` class để load và run model
- [ ] Update `/api/risk/{build_id}` để sử dụng model thật
- [ ] Cache predictions
- [ ] Batch prediction support

### Tasks Frontend
- [ ] RiskScoreBadge component
- [ ] Uncertainty indicator
- [ ] Risk level visualization
- [ ] Update BuildList để hiển thị risk scores

### Files cần tạo
```
backend/app/ml/predictor.py
backend/app/ml/models/ (saved models)
frontend/src/components/RiskScoreBadge.tsx
frontend/src/components/UncertaintyIndicator.tsx
```

---

## 📅 Tuần 10-11: Dashboard và Visualizations

### Mục tiêu
- Tạo dashboard tổng quan
- Biểu đồ thống kê
- Filters và search nâng cao

### Tasks Frontend
- [ ] Dashboard page `/dashboard`
- [ ] Charts:
  - Risk score trends over time
  - Build success rate
  - Vulnerability distribution
  - Quality metrics trends
- [ ] Real-time updates với polling/websockets
- [ ] Export reports

### Libraries
- [ ] Recharts cho visualizations
- [ ] date-fns cho date handling

### Files cần tạo
```
frontend/src/app/dashboard/page.tsx
frontend/src/components/charts/RiskTrendChart.tsx
frontend/src/components/charts/BuildStatusChart.tsx
frontend/src/components/charts/VulnerabilityChart.tsx
frontend/src/components/Dashboard.tsx
```

---

## 📅 Tuần 12-13: Testing và Optimization

### Tasks
- [ ] Unit tests cho backend (pytest)
- [ ] Integration tests
- [ ] Frontend tests
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Loading states
- [ ] Documentation

### Files cần tạo
```
backend/tests/test_api.py
backend/tests/test_services.py
backend/tests/test_ml.py
frontend/src/__tests__/components.test.tsx
```

---

## 🎯 Các Bước Tiếp Theo Ngay (Ưu Tiên)

### 1. Setup MongoDB và Test Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Setup database
python -m uvicorn app.main:app --reload
```

### 2. Test Frontend
```bash
cd frontend
npm install
npm run dev
```

### 3. Tạo GitHub Token
- Vào GitHub Settings > Developer settings > Personal access tokens
- Tạo token với quyền `repo`, `workflow`
- Thêm vào `backend/.env`

### 4. Bắt đầu Tuần 5 - GitHub Integration
- Tạo file `backend/app/services/github_service.py`
- Implement GitHub API calls
- Test với một repository thật

---

## 📝 Notes

### Dependencies cần thêm theo tuần

**Tuần 5 (GitHub):**
```
PyGithub==2.1.1  # Already in requirements.txt
```

**Tuần 6 (SonarQube & Risk Reports):**
```bash
# Backend
pip install requests beautifulsoup4
```

**Tuần 7-8 (ML):**
```
torch==2.1.1
torchvision==0.16.1
scikit-learn==1.3.2
matplotlib==3.8.2
seaborn==0.13.0
```

**Tuần 10 (Charts):**
```bash
# Frontend
npm install recharts date-fns
```

---

## 🎓 Learning Resources

- **Bayesian Neural Networks**: [TensorFlow Probability Guide](https://www.tensorflow.org/probability/examples/Bayesian_Neural_Networks)
- **GitHub Actions API**: [GitHub REST API Docs](https://docs.github.com/en/rest/actions)
- **SonarQube API**: [SonarQube Web API](https://docs.sonarqube.org/latest/extend/web-api/)
