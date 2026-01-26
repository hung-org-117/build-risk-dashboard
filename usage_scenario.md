# Kịch Bản Sử Dụng Hệ Thống

Tài liệu này mô tả các kịch bản sử dụng đơn giản của hai pipeline chính trong hệ thống: **Dataset Enrichment Pipeline** (dành cho Researcher) và **Build Risk Evaluation Pipeline** (dành cho Developer).

---

## Kịch Bản 1: Researcher Tạo Dataset Huấn Luyện

**Mục tiêu**: Một nhà nghiên cứu muốn tạo dataset để huấn luyện mô hình dự đoán rủi ro build.

### Các bước thực hiện

#### Bước 1: Upload Build Source (Admin)

1. Admin đăng nhập vào hệ thống
2. Truy cập trang **Build Sources** `/scenarios/sources`
3. Click **"Upload CSV"** để tải lên file CSV chứa danh sách build IDs

<!-- [Hình 1: Giao diện upload CSV] -->

4. Hệ thống tự động validate:
   - Kiểm tra repository có tồn tại trên GitHub
   - Kiểm tra build có tồn tại trên CI provider
   - Lưu kết quả vào Build Warehouse

#### Bước 2: Tạo Training Scenario

1. Researcher truy cập **Training Scenarios** `/scenarios`
2. Click **"Create New Scenario"** để mở wizard tạo scenario

<!-- [Hình 2: Giao diện danh sách scenarios] -->

3. **Bước 2.1: Cấu hình Data Source**
   - Chọn ngôn ngữ: `Python`, `Java`, `Ruby`
   - Chọn khoảng thời gian: `01/01/2024` - `31/12/2024`
   - Chọn kết quả build: `Success`, `Failure`
   
<!-- [Hình 3: Step Data Source trong wizard] -->

4. **Bước 2.2: Chọn Features**
   - Tick chọn các nhóm feature:
     - ✅ Git Features (commits, diff, churn)
     - ✅ Build Log Features (duration, tests)
     - ✅ Team Features (authors, collaborators)
   - Cấu hình parameters nếu cần (lookback days, etc.)

<!-- [Hình 4: Step Feature Selection với Hamilton DAG visualization] -->

5. Click **"Create Scenario"** → Scenario được tạo với status `QUEUED`

#### Bước 3: Chạy Ingestion

1. Trong trang Scenario detail, click **"Start Ingestion"**
2. Hệ thống thực hiện:
   - **Filtering**: Lọc builds từ warehouse theo config
   - **Clone/Worktree**: Clone repository và tạo worktree cho mỗi commit
   - **Download Logs**: Tải build logs từ GitHub Actions/Travis CI

<!-- [Hình 5: Progress bar Ingestion với real-time updates] -->

3. Theo dõi tiến độ qua thanh progress bar real-time
4. Khi hoàn thành → Status chuyển sang `INGESTED`

#### Bước 4: Chạy Processing

1. Click **"Start Processing"** trên giao diện
2. Hệ thống chạy song song:
   - **Feature Extraction**: Trích xuất features sử dụng Hamilton DAG (sequential theo thời gian)
   - **Scan Metrics**: Thu thập metrics từ Trivy/SonarQube (parallel)

<!-- [Hình 6: Processing phase với 2 workflows song song] -->

3. Khi Feature Extraction hoàn thành → Status = `PROCESSED`
4. Scan có thể tiếp tục chạy ở background

#### Bước 5: Phân tích Data Quality

1. Truy cập tab **"Analysis"** trong Scenario detail
2. Xem các chỉ số chất lượng:
   - **Completeness**: Tỷ lệ features có giá trị
   - **Validity**: Tỷ lệ giá trị hợp lệ
   - **Coverage**: Tỷ lệ builds được enrich thành công

<!-- [Hình 7: Dashboard Data Quality với biểu đồ phân phối] -->

3. Kiểm tra phân phối features qua histograms

#### Bước 6: Export Dataset

1. Truy cập tab **"Export"** 
2. Click **"Create New Export"**
3. Cấu hình export:
   - **Splitting Strategy**: `Stratified Random` (70/15/15)
   - **Output Format**: `Parquet`
   - **Preprocessing**: Enable normalization

<!-- [Hình 8: Export configuration wizard] -->

4. Click **"Generate"** → Hệ thống tạo files:
   - `train.parquet` (70% data)
   - `val.parquet` (15% data)
   - `test.parquet` (15% data)

5. Download dataset và sử dụng cho training model

---

## Kịch Bản 2: Developer Nhận Cảnh Báo Rủi Ro Build

**Mục tiêu**: Một developer muốn đánh giá rủi ro cho repository đang phát triển.

### Các bước thực hiện

#### Bước 1: Import Repository

1. Developer đăng nhập vào hệ thống
2. Truy cập **Repositories** `/repositories`
3. Click **"Import Repository"**

<!-- [Hình 9: Danh sách repositories] -->

4. Tìm repository bằng cách:
   - Nhập URL: `https://github.com/myorg/myrepo`
   - Hoặc chọn từ danh sách organizations đã cài đặt GitHub App

<!-- [Hình 10: Import Repository wizard] -->

5. Click **"Import"** → Hệ thống bắt đầu:
   - Verify repository trên GitHub
   - Kiểm tra ngôn ngữ được hỗ trợ (Python, Java, Ruby, etc.)
   - Fetch builds từ GitHub Actions

#### Bước 2: Chờ Ingestion Hoàn Thành

1. Hệ thống tự động chạy ingestion:
   - Clone repository
   - Tạo worktree cho mỗi commit
   - Download build logs

<!-- [Hình 11: Ingestion progress với stepper] -->

2. Theo dõi tiến độ qua **MiniStepper** hiển thị các phase:
   - `FETCHING` → `INGESTING` → `INGESTED`

#### Bước 3: Bắt Đầu Processing

1. Khi status = `INGESTED`, click **"Start Processing"**
2. Hệ thống trích xuất features:
   - Git features (diff, commits, blame)
   - Build log features (keywords, patterns)
   - Temporal features (previous build results)

<!-- [Hình 12: Processing phase] -->

3. Chờ processing hoàn thành → Status = `PROCESSED`

#### Bước 4: Xem Kết Quả Dự Đoán

1. Truy cập tab **"Builds"** trong Repository detail
2. Mỗi build hiển thị:
   - **Risk Label**: `LOW` / `MEDIUM` / `HIGH`
   - **Confidence Score**: 0% - 100%
   - **Uncertainty Level**: Low / Medium / High

<!-- [Hình 13: Unified Builds Table với risk predictions] -->

3. Click vào một build để xem chi tiết:
   - Risk prediction breakdown
   - Extracted features
   - Build metadata

<!-- [Hình 14: Build Detail page] -->

#### Bước 5: Kinh Nghiệm Analytics

1. Truy cập tab **"Analytics"**
2. Xem dashboard phân tích:
   - **Risk Distribution**: Phân bố Low/Medium/High risks
   - **Risk Over Time**: Xu hướng rủi ro theo thời gian
   - **Risk by Branch**: So sánh giữa các branches

<!-- [Hình 15: Risk Analytics Dashboard] -->

3. Sử dụng insights để:
   - Xác định hotspots cần review
   - Theo dõi impact của các changes
   - Đưa ra quyết định merge/deploy

#### Bước 6: Tự Động Nhận Updates (Webhook)

1. Repository đã được cài GitHub App sẽ tự động nhận webhook
2. Khi có build mới hoàn thành trên GitHub:
   - Webhook gửi event đến hệ thống
   - Hệ thống tự động ingest build mới
   - Developer bấm **"Start Processing"** để nhận prediction

<!-- [Hình 16: New build notification] -->

3. Prediction có sẵn trong vài phút sau khi build hoàn thành

---

## Tóm Tắt Luồng Sử Dụng

| Role | Pipeline | Mục đích |
|------|----------|----------|
| **Researcher/Admin** | Dataset Enrichment | Tạo dataset huấn luyện model với features đa chiều |
| **Developer** | Build Risk Evaluation | Nhận đánh giá rủi ro real-time cho mỗi build |

### So Sánh Hai Pipeline

| Tiêu chí | Dataset Enrichment | Build Risk Evaluation |
|----------|-------------------|----------------------|
| **Input** | CSV builds từ Build Warehouse | Repository GitHub trực tiếp |
| **Output** | Dataset files (Parquet/CSV) | Risk predictions per build |
| **Scans** | Full (Trivy + SonarQube) | Skipped (ưu tiên latency) |
| **Automation** | Manual trigger | Webhook support |
| **Use case** | Research, Training | Production, CI/CD integration |

---

## Placeholder Hình Ảnh

> **Note**: Các vị trí `<!-- [Hình X: ...] -->` cần được thay thế bằng screenshots thực tế từ hệ thống.

| Hình | Mô tả | File path gợi ý |
|------|-------|-----------------|
| Hình 1 | Giao diện upload CSV | `Figure/screenshot_upload_csv.png` |
| Hình 2 | Danh sách Training Scenarios | `Figure/screenshot_scenarios_list.png` |
| Hình 3 | Wizard - Data Source step | `Figure/screenshot_wizard_datasource.png` |
| Hình 4 | Wizard - Feature Selection | `Figure/screenshot_scenario_create_wizard.png` |
| Hình 5 | Ingestion Progress | `Figure/screenshot_ingestion_progress.png` |
| Hình 6 | Processing Phase | `Figure/screenshot_processing_phase.png` |
| Hình 7 | Data Quality Dashboard | `Figure/screenshot_scenario_analysis.png` |
| Hình 8 | Export Configuration | `Figure/screenshot_scenario_export_create.png` |
| Hình 9 | Repositories List | `Figure/screenshot_repositories_list.png` |
| Hình 10 | Import Repository Wizard | `Figure/screenshot_import_wizard.png` |
| Hình 11 | Ingestion Stepper | `Figure/screenshot_mini_stepper.png` |
| Hình 12 | Processing Phase (Model) | `Figure/screenshot_model_processing.png` |
| Hình 13 | Unified Builds Table | `Figure/screenshot_unified_builds.png` |
| Hình 14 | Build Detail Page | `Figure/screenshot_build_detail.png` |
| Hình 15 | Risk Analytics Dashboard | `Figure/screenshot_risk_analytics.png` |
| Hình 16 | New Build Notification | `Figure/screenshot_new_build.png` |
