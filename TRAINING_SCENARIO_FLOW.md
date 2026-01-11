# Training Scenario Pipeline - Mô Tả Chi Tiết Toàn Bộ Luồng

## 📋 Mục Lục
1. [Tổng Quan Kiến Trúc](#tổng-quan-kiến-trúc)
2. [Phase 0: Build Source Upload](#phase-0-build-source-upload)
3. [Phase 1: Filtering & Ingestion](#phase-1-filtering--ingestion)
4. [Phase 2: Processing & Feature Extraction](#phase-2-processing--feature-extraction)
5. [Phase 3: Dataset Generation](#phase-3-dataset-generation)
6. [Entities & Data Model](#entities--data-model)
7. [API Endpoints](#api-endpoints)
8. [Frontend UI Flow](#frontend-ui-flow)
9. [Error Handling & Recovery](#error-handling--recovery)
10. [WebSocket Real-time Updates](#websocket-real-time-updates)

---

## Tổng Quan Kiến Trúc

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      TRAINING SCENARIO PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────┘

Phase 0: Admin uploads CSV (Build Source)
       │
       ▼
┌──────────────────────────────────────────┐
│  BUILD SOURCE VALIDATION                  │
│  ✓ Parse CSV with build IDs               │
│  ✓ Validate repos on GitHub API           │
│  ✓ Validate builds on CI API              │
│  ✓ Cache to RawRepository & RawBuildRun   │
└──────────────────────────────────────────┘
       │
       ▼
[Build Warehouse: raw_build_runs collection]
       │
       ▼
User creates Training Scenario with filters
       │
       ▼
┌──────────────────────────────────────────┐
│  PHASE 1: FILTERING & INGESTION          │
│  ✓ Query builds from warehouse (filters) │
│  ✓ Create TrainingIngestionBuild records │
│  ✓ Clone/update git repositories         │
│  ✓ Create git worktrees cho commits      │
│  ✓ Download build logs từ CI             │
└──────────────────────────────────────────┘
       │
       ▼ (User triggers manually)
┌──────────────────────────────────────────┐
│  PHASE 2: PROCESSING                     │
│  ✓ Dispatch scans (Trivy, SonarQube)     │
│  ✓ Create TrainingEnrichmentBuild        │
│  ✓ Extract features (Hamilton DAG)       │
│  ✓ Sequential processing (temporal deps) │
└──────────────────────────────────────────┘
       │
       ▼ (User triggers manually)
┌──────────────────────────────────────────┐
│  PHASE 3: DATASET GENERATION             │
│  ✓ Collect features from EnrichmentBuilds│
│  ✓ Apply splitting strategy              │
│  ✓ Generate train/val/test files         │
│  ✓ Export to parquet/csv/pickle          │
└──────────────────────────────────────────┘
       │
       ▼
TrainingScenario (COMPLETED) + Dataset Splits Ready
```

### Queue Architecture

```
┌────────────────────────────────────────┐
│        Celery Queue System             │
├────────────────────────────────────────┤
│ validation     │ Build source validation│
│ ingestion      │ Clone, worktree, logs  │
│ processing     │ Feature extraction     │
│ trivy_scan     │ Trivy security scans   │
│ sonar_scan     │ SonarQube analysis     │
└────────────────────────────────────────┘
```

### Status Flow

```
TrainingScenario Status Flow:

    QUEUED ──► FILTERING ──► INGESTING ──► INGESTED
                  │              │             │
                  ▼              ▼             │
               FAILED ◄────── FAILED          │
                  │                            ▼
                  ▼                 (User triggers processing)
             (Retry available)                 │
                                               ▼
                                    ┌─── PROCESSING ───┐
                                    │                  │
                                    ▼                  ▼
                                PROCESSED           FAILED
                                    │
                                    ▼
                         (User triggers split/export)
                                    │
                                    ▼
                         ┌─── SPLITTING ───┐
                         │                 │
                         ▼                 ▼
                     COMPLETED          FAILED
```

---

## Phase 0: Build Source Upload

**Files**: 
- [backend/app/api/build_sources.py](backend/app/api/build_sources.py)
- [backend/app/tasks/source_validation.py](backend/app/tasks/source_validation.py)

**Mục đích**: Thu thập validated builds vào warehouse (raw_build_runs)

### 0.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `source_validation_orchestrator` | validation | 3600s | Parse CSV, dispatch validation |
| `validate_source_repos` | validation | 600s | Validate repos on GitHub |
| `validate_source_builds` | validation | 600s | Validate builds on CI |

### 0.2 Upload Flow

```
Admin uploads CSV (build_id, repo_name columns)
       │
       ▼
POST /api/build-sources/upload
│
├─ Parse CSV, create BuildSource entity
├─ Create SourceBuild records (PENDING)
└─ Dispatch source_validation_orchestrator
       │
       ▼
source_validation_orchestrator
│
├─ Group builds by repo
├─ For each repo:
│   ├─ validate_source_repos → RawRepository
│   └─ validate_source_builds → RawBuildRun
│
└─ Aggregate results
    ├─ Mark SourceBuild as FOUND/NOT_FOUND
    └─ Update BuildSource validation stats
```

### 0.3 Data Structures (Phase 0)

**BuildSource**:
```python
{
    name: str,
    description: Optional[str],
    file_name: str,
    rows: int,
    mapped_fields: Dict[str, str],  # CSV column mapping
    validation_status: str,         # pending, in_progress, completed
    validation_stats: {
        total: int,
        found: int,
        not_found: int,
        filtered: int,
    }
}
```

**SourceBuild**:
```python
{
    source_id: ObjectId,
    build_id_from_source: str,
    repo_name_from_source: str,
    status: "pending" | "found" | "not_found" | "filtered",
    raw_repo_id: Optional[ObjectId],   # Link to RawRepository
    raw_run_id: Optional[ObjectId],    # Link to RawBuildRun
}
```

---

## Phase 1: Filtering & Ingestion

**File**: [backend/app/tasks/training_ingestion.py](backend/app/tasks/training_ingestion.py)

**Mục đích**: Lọc builds từ warehouse theo config và chuẩn bị resources

### 1.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `start_scenario_ingestion` | processing | 180s | Orchestrator: Filter + dispatch ingestion |
| `aggregate_scenario_ingestion` | ingestion | 120s | Aggregate results, mark INGESTED |
| `handle_scenario_chord_error` | ingestion | 120s | Error callback |
| `reingest_failed_builds` | processing | 900s | Retry FAILED builds |

### 1.2 Filtering Flow

```
User creates Scenario via /scenarios/create wizard
       │
       ▼
POST /api/training-scenarios
│
├─ Parse config (data_source, features, splitting, preprocessing)
├─ Create TrainingScenario entity (QUEUED)
└─ User clicks "Start Ingestion" → start_scenario_ingestion
       │
       ▼
start_scenario_ingestion
│
├─ Update status → FILTERING
├─ Query RawBuildRun by filters:
│   ├─ date_start, date_end
│   ├─ languages (from RawRepository.main_lang)
│   ├─ conclusions (success, failure)
│   ├─ ci_provider
│   └─ exclude_bots
│
├─ Create TrainingIngestionBuild for each matched build
├─ Update status → INGESTING
│
└─ chord(
       group(clone_repo → worktrees → logs) × N repos,
       aggregate_scenario_ingestion
   )
```

### 1.3 Data Source Config

```python
DataSourceConfig = {
    filter_by: "all" | "by_language" | "by_name",
    languages: ["python", "java"],      # Filter by main_lang
    date_start: "2024-01-01",
    date_end: "2024-12-31",
    conclusions: ["success", "failure"],
    ci_provider: "all" | "github_actions" | "circleci",
    exclude_bots: True,
}
```

### 1.4 TrainingIngestionBuild Status

```
    PENDING ───► INGESTING ───► INGESTED
                     │              │
                     ▼              ▼
                  FAILED     (Ready for Processing)
                     │
                     ▼
              MISSING_RESOURCE
              (Not retryable)
```

---

## Phase 2: Processing & Feature Extraction

**File**: [backend/app/tasks/training_processing.py](backend/app/tasks/training_processing.py)

**Mục đích**: Extract features từ ingested builds

### 2.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `start_scenario_processing` | processing | 120s | User triggers Phase 2 |
| `dispatch_scans_and_processing` | processing | 180s | Dispatch scans + feature extraction |
| `dispatch_scenario_scans` | processing | 600s | Fire-and-forget scan dispatch |
| `dispatch_enrichment_batches` | processing | 360s | Create EnrichmentBuild, dispatch chain |
| `process_single_enrichment` | processing | 900s | Extract features for 1 build |
| `finalize_scenario_processing` | processing | 120s | Mark PROCESSED |
| `reprocess_failed_builds` | processing | 360s | Retry failed builds |

### 2.2 Processing Flow

```
User clicks "Start Processing"
       │
       ▼
start_scenario_processing
│
├─ Validate status is INGESTED
├─ Update status → PROCESSING
└─ dispatch_scans_and_processing
       │
       ├─ dispatch_scenario_scans (async, fire & forget)
       │   └─ Dispatch Trivy + SonarQube for unique commits
       │
       └─ dispatch_enrichment_batches
           │
           ├─ Create TrainingEnrichmentBuild for each INGESTED build
           └─ chain(
                  process_single_enrichment(build_1),
                  process_single_enrichment(build_2),
                  ...,
                  finalize_scenario_processing
              )
```

### 2.3 Sequential Processing (Temporal Features)

Processing MUST be sequential (oldest → newest) for temporal features:

```python
# Temporal features depend on previous builds
# tr_prev_build_duration, tr_success_rate_last_5, etc.

chain(
    process_single_enrichment(build_1),  # 2024-01-01
    process_single_enrichment(build_2),  # 2024-01-02 (references build_1)
    process_single_enrichment(build_3),  # 2024-01-03 (references build_2)
    ...,
    finalize_scenario_processing
)
```

### 2.4 Feature Config

```python
FeatureConfig = {
    dag_features: ["git_*", "build_*", "log_*"],  # Wildcard support
    scan_metrics: {
        sonarqube: ["code_smells", "bugs", "coverage"],
        trivy: ["vuln_total", "vuln_critical"],
    },
    extractor_configs: {
        "lookback_days": 90,
        "test_frameworks": ["pytest", "junit"],
    },
}
```

---

## Phase 3: Dataset Generation

**File**: [backend/app/tasks/training_processing.py](backend/app/tasks/training_processing.py) (`generate_scenario_dataset`)

**Mục đích**: Split và export dataset thành train/val/test files

### 3.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `generate_scenario_dataset` | processing | 900s | Collect features, split, export |

### 3.2 Generation Flow

```
User clicks "Generate Dataset"
       │
       ▼
generate_scenario_dataset
│
├─ Validate status is PROCESSED
├─ Update status → SPLITTING
│
├─ Collect features from EnrichmentBuilds
│   ├─ Query all builds with extraction_status = COMPLETED
│   ├─ Join with FeatureVector.features
│   └─ Join with FeatureVector.scan_metrics (if available)
│
├─ Build pandas DataFrame
│   ├─ Feature columns
│   ├─ Label column (outcome: success/failure)
│   └─ Metadata (repo, commit, build_id)
│
├─ Apply preprocessing:
│   ├─ Handle missing values (drop_row | fill | skip_feature)
│   └─ Normalize (z_score | min_max | robust | none)
│
├─ Apply splitting strategy:
│   ├─ stratified_within_group (default)
│   ├─ leave_one_out
│   ├─ time_series_split
│   └─ random_split
│
├─ Export files:
│   ├─ train.parquet (70%)
│   ├─ val.parquet (15%)
│   └─ test.parquet (15%)
│
├─ Create TrainingDatasetSplit records
│
└─ Update status → COMPLETED
```

### 3.3 Splitting Config

```python
SplittingConfig = {
    strategy: "stratified_within_group",
    group_by: "repo_name" | "language" | "ci_provider",
    stratify_by: "outcome" | "conclusion",
    ratios: {
        train: 0.7,
        val: 0.15,
        test: 0.15,
    },
    temporal_ordering: True,  # Sort by build_started_at
}
```

### 3.4 TrainingDatasetSplit

```python
{
    scenario_id: ObjectId,
    split_type: "train" | "val" | "test",
    file_path: str,
    file_format: "parquet" | "csv" | "pickle",
    file_size_bytes: int,
    record_count: int,
    feature_count: int,
    class_distribution: {"success": 500, "failure": 200},
    generated_at: datetime,
}
```

---

## Entities & Data Model

### Entity Relationship Diagram

```
┌─────────────────────┐     ┌─────────────────────┐
│   BuildSource       │     │    SourceBuild      │
│─────────────────────│     │─────────────────────│
│ _id                 │◄────┤ source_id           │
│ name                │     │ build_id_from_source│
│ validation_status   │     │ raw_run_id          │────┐
│ validation_stats    │     │ status              │    │
└─────────────────────┘     └─────────────────────┘    │
                                                        │
                         [Warehouse]                    │
                              │                         │
┌─────────────────────┐     ┌─────────────────────┐    │
│   RawRepository     │     │    RawBuildRun      │◄───┘
│─────────────────────│     │─────────────────────│
│ _id                 │◄────┤ raw_repo_id         │
│ full_name           │     │ _id                 │
│ github_repo_id      │     │ ci_run_id           │
│ main_lang           │     │ commit_sha          │
│ ci_provider         │     │ conclusion          │
└─────────────────────┘     └─────────────────────┘
                                     │
                                     │ (Filtered by config)
                                     ▼
┌─────────────────────┐     ┌─────────────────────┐
│ TrainingScenario    │     │TrainingIngestionBuild│
│─────────────────────│     │─────────────────────│
│ _id                 │◄────┤ scenario_id         │
│ name                │     │ raw_build_run_id    │
│ status              │     │ status              │
│ data_source_config  │     │ resource_status     │
│ feature_config      │     └─────────────────────┘
│ splitting_config    │              │
│ preprocessing_config│              │
└─────────────────────┘              ▼
         │              ┌─────────────────────┐
         │              │TrainingEnrichmentBuild│
         │              │─────────────────────│
         │              │ scenario_id         │
         │              │ ingestion_build_id  │
         │              │ feature_vector_id   │───► FeatureVector
         │              │ extraction_status   │
         │              └─────────────────────┘
         │
         ▼
┌─────────────────────┐
│TrainingDatasetSplit │
│─────────────────────│
│ scenario_id         │
│ split_type          │
│ file_path           │
│ record_count        │
│ class_distribution  │
└─────────────────────┘
```

### Status Enums

```python
class ScenarioStatus(str, Enum):
    QUEUED = "queued"
    FILTERING = "filtering"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    PROCESSING = "processing"
    PROCESSED = "processed"
    SPLITTING = "splitting"
    COMPLETED = "completed"
    FAILED = "failed"

class IngestionStatus(str, Enum):
    PENDING = "pending"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    MISSING_RESOURCE = "missing_resource"
    FAILED = "failed"

class ExtractionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
```

---

## API Endpoints

**File**: [backend/app/api/training_scenarios.py](backend/app/api/training_scenarios.py)

### Scenario CRUD

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `POST` | `/training-scenarios` | Create scenario |
| `GET` | `/training-scenarios` | List scenarios |
| `GET` | `/training-scenarios/{id}` | Get scenario detail |
| `PATCH` | `/training-scenarios/{id}` | Update scenario |
| `DELETE` | `/training-scenarios/{id}` | Delete scenario |

### Pipeline Control

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `POST` | `/training-scenarios/{id}/start-ingestion` | Start Phase 1 |
| `POST` | `/training-scenarios/{id}/start-processing` | Start Phase 2 |
| `POST` | `/training-scenarios/{id}/generate-dataset` | Start Phase 3 |
| `POST` | `/training-scenarios/{id}/retry-ingestion` | Retry failed ingestion |
| `POST` | `/training-scenarios/{id}/retry-processing` | Retry failed processing |

### Builds & Splits

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/training-scenarios/{id}/builds/import` | List ingestion builds |
| `GET` | `/training-scenarios/{id}/builds/enrichment` | List enrichment builds |
| `GET` | `/training-scenarios/{id}/splits` | List dataset splits |
| `GET` | `/training-scenarios/preview-builds` | Preview builds with filters |

---

## Frontend UI Flow

**Files**: [frontend/src/app/(app)/scenarios/](frontend/src/app/(app)/scenarios/)

### Page Structure

```
/scenarios
├── page.tsx                   # Scenario list
├── upload/                    # BuildSource upload wizard
│   ├── page.tsx
│   └── _components/
├── create/                    # Scenario creation wizard
│   ├── page.tsx
│   └── _components/
│       ├── StepDataSource.tsx     # Step 1: Filter config
│       ├── StepFeatures.tsx       # Step 2: Feature selection
│       ├── StepSplitting.tsx      # Step 3: Split strategy
│       ├── StepPreprocessing.tsx  # Step 4: Preprocessing
│       └── WizardContext.tsx      # Wizard state management
└── [scenarioId]/
    ├── layout.tsx             # Tabs navigation
    ├── page.tsx               # Overview
    ├── builds/                # Ingestion + Enrichment builds
    ├── analysis/              # Feature analysis
    └── export/                # Download splits
        └── page.tsx
```

### Create Wizard Flow

```
Step 1: Data Source (Filter builds from warehouse)
┌──────────────────────────────────────────────────────────────┐
│ Filters                      │  Preview                      │
│ ┌───────────────────────────┐│ ┌─────────────────────────┐  │
│ │ Languages: [Python ▼]    ││ │ Total: 5,230 builds     │  │
│ │ CI Provider: [All ▼]     ││ │ Repos: 45               │  │
│ │ Conclusions: [☑ Success] ││ │ Success: 3,800 (72%)    │  │
│ │            [☑ Failure]   ││ │ Failure: 1,430 (28%)    │  │
│ │ Date Range: [2024-01-01] ││ └─────────────────────────┘  │
│ │         to: [2024-12-31] ││                              │
│ └───────────────────────────┘│ [Apply Filters]              │
│                                                              │
│                                               [Next: Features]│
└──────────────────────────────────────────────────────────────┘

Step 2: Features (Select DAG features + scan metrics)
Step 3: Splitting (Configure train/val/test ratios)
Step 4: Preprocessing (Missing values, normalization)
Step 5: Review & Start
```

### Export Page

```
/scenarios/{id}/export
├── Dataset Summary Card
│   ├─ Total Splits: 3
│   ├─ Total Records: 4,500
│   ├─ Features: 45
│   └─ Total Size: 12.5 MB
├── Split Files Table
│   ├─ train.parquet (3,150 records, 8.7 MB) [Download]
│   ├─ val.parquet (675 records, 1.9 MB) [Download]
│   └─ test.parquet (675 records, 1.9 MB) [Download]
└── Class Distribution Chart
```

---

## Error Handling & Recovery

### Ingestion Errors

| Error Type | Status | Retryable | Action |
|------------|--------|-----------|--------|
| Clone failed (timeout) | FAILED | Yes | `reingest_failed_builds` |
| Worktree creation failed | FAILED | Yes | `reingest_failed_builds` |
| Log download timeout | FAILED | Yes | `reingest_failed_builds` |
| Logs expired (404) | MISSING_RESOURCE | No | Cannot retry |
| Commit not in repo | MISSING_RESOURCE | No | Cannot retry |

### Processing Errors

| Error Type | Status | Retryable | Action |
|------------|--------|-----------|--------|
| Feature extraction failed | FAILED | Yes | `reprocess_failed_builds` |
| Hamilton DAG error | FAILED | Yes | `reprocess_failed_builds` |
| Scan timeout | N/A | No | Scan runs async, skip backfill |

---

## WebSocket Real-time Updates

### Event Types

```python
# Scenario status update
{
    "event": "SCENARIO_UPDATE",
    "scenario_id": "...",
    "status": "processing",
    "message": "Extracting features for 150 builds...",
    "stats": {
        "builds_total": 500,
        "builds_ingested": 450,
        "builds_processed": 150,
    }
}

# Build status update
{
    "event": "SCENARIO_BUILD_UPDATE",
    "scenario_id": "...",
    "build_id": "...",
    "phase": "processing",
    "status": "completed",
}
```

---

## Summary

Training Scenario Pipeline là hệ thống 4-phase tạo dataset ML từ builds:

1. **Build Source Upload**: Admin upload CSV → validate → store to warehouse
2. **Filtering & Ingestion**: Query warehouse với filters → clone/worktree/logs
3. **Processing**: Extract features (sequential) → dispatch scans (async)
4. **Dataset Generation**: Split → export train/val/test files

**Key Design Decisions**:
- **Warehouse-first**: Builds được validate trước, lưu vào `raw_build_runs`
- **Filter-then-ingest**: User chọn builds từ warehouse, không từ CSV trực tiếp
- **3-phase user control**: User manually triggers Ingestion → Processing → Generation
- **Train/Val/Test splits**: Cấu hình splitting strategy với ratios tùy chỉnh
- **Sequential processing**: Temporal features yêu cầu xử lý tuần tự
- **Async scans**: Trivy/SonarQube chạy song song, không block feature extraction
