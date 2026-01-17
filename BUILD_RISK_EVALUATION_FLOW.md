# Build Risk Evaluation Pipeline - Technical Documentation

## Table of Contents
1. [Tổng Quan Kiến Trúc](#tổng-quan-kiến-trúc)
2. [Dashboard Statistics](#dashboard-statistics)
3. [Phase 1: Import & Fetch](#phase-1-import--fetch)
4. [Phase 2: Ingestion](#phase-2-ingestion)
5. [Phase 3: Processing & Feature Extraction](#phase-3-processing--feature-extraction)
6. [Phase 4: Prediction](#phase-4-prediction)
7. [Entities & Data Model](#entities--data-model)
8. [API Endpoints](#api-endpoints)
9. [Frontend UI Flow](#frontend-ui-flow)
10. [Error Handling & Recovery](#error-handling--recovery)
11. [SSE Real-time Updates](#sse-real-time-updates)

---

## Tổng Quan Kiến Trúc

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BUILD RISK EVALUATION PIPELINE                        │
└─────────────────────────────────────────────────────────────────────────┘

User Imports GitHub Repository
       │
       ▼
┌──────────────────────────────────────────┐
│  PHASE 1: IMPORT & FETCH                 │
│  - Verify repo exists on GitHub          │
│  - Create ModelRepoConfig                │
│  - Fetch builds from CI API              │
│  - Create RawBuildRun records            │
│  - Create ModelImportBuild records       │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  PHASE 2: INGESTION                      │
│  - Clone/update git repositories         │
│  - Create git worktrees cho commits      │
│  - Download build logs từ CI             │
│  - Per-resource status tracking          │
│  - Mark builds as INGESTED/FAILED        │
└──────────────────────────────────────────┘
       │
       ▼ (User triggers manually)
┌──────────────────────────────────────────┐
│  PHASE 3: PROCESSING                     │
│  - Create ModelTrainingBuild records     │
│  - Extract features (Hamilton DAG)       │
│  - Store features in FeatureVector       │
│  - Sequential processing (temporal deps) │
└──────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────┐
│  PHASE 4: PREDICTION                     │
│  - Batch prediction (parallel)           │
│  - Risk level classification             │
│  - Uncertainty estimation                │
│  - Store prediction results              │
└──────────────────────────────────────────┘
       │
       ▼
ModelRepoConfig (PROCESSED) + Predictions Ready
```

### Queue Architecture

```
┌──────────────────────────────────────────────┐
│           Celery Queue System                │
├──────────────────────────────────────────────┤
│ model_processing  │ Orchestration, feature   │
│                   │ extraction, finalization │
│ model_ingestion   │ Fetch, clone, worktree,  │
│                   │ build logs download      │
│ model_prediction  │ ML model predictions     │
└──────────────────────────────────────────────┘
```

### Status Flow

```
ModelRepoConfig Status Flow:

    QUEUED ──────► FETCHING ──────► INGESTING ──────► INGESTED
                      │                  │                │
                      ▼                  ▼                │
                   FAILED ◄────────── FAILED             │
                      │                                   │
                      ▼                                   ▼
                 (Retry available)          (User triggers processing)
                                                          │
                                                          ▼
                                               ┌─── PROCESSING ───┐
                                               │                  │
                                               ▼                  ▼
                                           PROCESSED           FAILED
                                               │
                                               ▼
                                     (Retry / Re-sync available)
```

---

## Dashboard Statistics

Minimal metrics shown on the admin widget:

| Metric | Meaning |
|--------|---------|
| Total | Repositories imported (`model_repo_configs`) |
| Fetching | Status=FETCHING |
| Ingesting | Status=INGESTING |
| Processing | Status=PROCESSING |
| Processed | Status=PROCESSED |

---

## Phase 1: Import & Fetch

**Files**: 
- [backend/app/api/model_repos.py](backend/app/api/model_repos.py)
- [backend/app/services/model_repository_service.py](backend/app/services/model_repository_service.py)
- [backend/app/tasks/model_ingestion.py](backend/app/tasks/model_ingestion.py)

**Mục đích**: Import repository từ GitHub và fetch builds từ CI provider

### 1.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `start_model_processing` | model_processing | 180s | Orchestrator: Bắt đầu toàn bộ pipeline |
| `ingest_model_builds` | model_ingestion | 180s | Dispatch fetch tasks (parallel or sequential) |
| `fetch_builds_batch` | model_ingestion | 360s | Fetch một page builds từ CI API |
| `fetch_builds_until_existing` | model_ingestion | 900s | Sequential fetch cho sync mode |
| `aggregate_fetch_results` | model_ingestion | 120s | Aggregate fetch results (chord callback) |
| `handle_fetch_chord_error` | model_ingestion | 120s | Error handler cho fetch chord failures |

### 1.2 Import Flow Diagram

```
User clicks "Import Repository"
       │
       ▼
bulk_import_repositories (API)
│
├─ Verify repo on GitHub API
├─ Create/Update RawRepository
├─ Create ModelRepoConfig (status=QUEUED)
└─ Dispatch start_model_processing
       │
       ▼
start_model_processing (Celery)
│
├─ Update status → INGESTING
├─ Publish WebSocket event
└─ Dispatch ingest_model_builds
       │
       ▼
ingest_model_builds
│
├─ Mode 1: sync_until_existing=True
│   └─ fetch_builds_until_existing (sequential)
│       ├─ Fetch page, check if exists in DB
│       ├─ Stop when hitting existing build
│       └─ Dispatch dispatch_ingestion
│
└─ Mode 2: Parallel fetch (chord pattern)
    └─ chord(
           group(fetch_builds_batch × N pages),
           aggregate_fetch_results
       )
       └─ Dispatch dispatch_ingestion
```

### 1.2.1 Webhook Auto-Sync Flow

**Files**: 
- [backend/app/api/webhook.py](backend/app/api/webhook.py) - API endpoint `/webhook/github`
- [backend/app/services/github/github_webhook.py](backend/app/services/github/github_webhook.py) - Event handler
- [backend/app/tasks/model_ingestion.py](backend/app/tasks/model_ingestion.py) - `ingest_webhook_build` task

**Mục đích**: Tự động nhận builds mới từ GitHub webhook khi workflow hoàn thành

| Task | Queue | Timeout (soft/hard) | Mô Tả |
|------|-------|---------------------|-------|
| `ingest_webhook_build` | model_ingestion | 300s / 360s | Ingest single build từ webhook event |

```
GitHub sends webhook (workflow_run.completed)
       │
       ▼
/webhook/github (FastAPI)
│
├─ Verify signature (GITHUB_WEBHOOK_SECRET)
├─ Filter: only action=completed, conclusion=completed
├─ Find RawRepository by full_name
│
└─ IF repo tracked in ModelRepoConfig:
       │
       ├─ Create/Update RawBuildRun
       ├─ Increment builds_fetched counter
       └─ Dispatch ingest_webhook_build
              │
              ▼
    ingest_webhook_build (Celery)
    │
    ├─ Create ModelImportBuild (status=FETCHED)
    ├─ Mark INGESTING
    └─ Dispatch dispatch_ingestion (single build)
           │
           ▼
    Build ingested (clone/worktree/logs)
           │
           ▼
    Status: INGESTED
    (User starts processing manually via UI)
```

> [!NOTE]
> Webhook chỉ thực hiện **ingestion** (clone, worktree, logs), không tự động processing.
> User phải bấm "Start Processing" trên UI để chạy feature extraction.

### 1.3 Fetch Builds Logic

```python
# Từ fetch_builds_batch
fetch_kwargs = {
    "since": since_dt,          # Only builds after this date
    "limit": batch_size,        # Builds per page (default: 100)
    "page": page,               # Pagination
    "exclude_bots": True,       # Skip bot commits
    "only_completed": True,     # Only completed builds
}

# Build filters applied:
# - status == COMPLETED
# - conclusion NOT IN (SKIPPED, ACTION_REQUIRED, STALE)
# - build_id is not null
```

### 1.4 Data Structures (Phase 1)

- RawRepository: identity + github_metadata, main_lang, default_branch
- RawBuildRun: ci_run_id, commit_sha, status, conclusion, created_at, logs_available
- ModelImportBuild: links repo_config + raw_build_run, status (fetched/ingesting/ingested/failed/missing_resource), per-resource status map

---

## Phase 2: Ingestion

**File**: [backend/app/tasks/model_ingestion.py](backend/app/tasks/model_ingestion.py)

**Mục đích**: Chuẩn bị resources cần thiết cho feature extraction

### 2.1 Tasks Overview

| Task | Queue | Timeout | Retries | Mô Tả |
|------|-------|---------|---------|-------|
| `dispatch_ingestion` | model_ingestion | 180s | N/A | Build và dispatch ingestion workflow |
| `aggregate_model_ingestion_results` | model_ingestion | 60s | N/A | Aggregate results, mark builds INGESTED |
| `handle_ingestion_chord_error` | model_ingestion | 120s | N/A | Error handler cho chord failure |
| `reingest_failed_builds` | model_ingestion | 900s | N/A | Retry FAILED builds (not MISSING_RESOURCE) |

### 2.2 Resource DAG

Resources được xác định từ template "Risk Prediction":

```
clone_repo (git bare clone)
    │
    ├── create_worktree (per commit, sequential chunks)
    │
    └── download_build_logs (parallel, independent)
```

**Required Resources từ Template**:
```python
required_resources = template_service.get_required_resources_for_template("Risk Prediction")
# Có thể bao gồm:
# - FeatureResource.GIT_HISTORY (clone)
# - FeatureResource.GIT_WORKTREE (worktree per commit)
# - FeatureResource.BUILD_LOGS (CI logs)
```

### 2.3 Ingestion Flow

```
dispatch_ingestion
│
├─ Mark all FETCHED builds as INGESTING
├─ Get required resources from template
├─ Initialize resource_status for each build
│
└─ chord(
       build_ingestion_workflow(
           clone_repo → create_worktree_chunks → download_logs_chunks
       ),
       aggregate_model_ingestion_results
   )
       │
       ▼
aggregate_model_ingestion_results
│
├─ Parse results from Redis / task arguments
├─ Update per-resource status:
│   ├─ git_history: COMPLETED/FAILED (affects ALL builds)
│   ├─ git_worktree: Per-commit status
│   └─ build_logs: Per-build status
│
├─ Determine per-build final status:
│   ├─ INGESTED: All resources ready
│   ├─ FAILED: Actual error (timeout, network) - RETRYABLE
│   └─ MISSING_RESOURCE: Expected (logs expired) - NOT RETRYABLE
│
└─ Update ModelRepoConfig → status=INGESTED
```

### 2.4 Resource Status Tracking

```python
class ResourceStatus(str, Enum):
    PENDING = "pending"       # Not started
    IN_PROGRESS = "in_progress"  # Currently fetching
    COMPLETED = "completed"   # Successfully completed
    FAILED = "failed"         # Failed with error
    SKIPPED = "skipped"       # Not required by template

class ResourceStatusEntry(BaseModel):
    status: ResourceStatus
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### 2.5 ModelImportBuild Status Flow

```
        FETCHED ───► INGESTING ───► INGESTED
                        │              │
                        ▼              ▼
                    FAILED       (Ready for Processing)
                        │
                        ▼
                MISSING_RESOURCE
                (Not retryable)
```

---

## Phase 3: Processing & Feature Extraction

**File**: [backend/app/tasks/model_processing.py](backend/app/tasks/model_processing.py)

**Mục đích**: Extract features từ resources và lưu vào FeatureVector

### 3.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `start_processing_phase` | model_processing | 120s | User triggers Phase 2, find pending builds |
| `dispatch_build_processing` | model_processing | 360s | Create ModelTrainingBuild, dispatch chain |
| `process_workflow_run` | model_processing | 900s | Extract features cho 1 build (max_retries=3) |
| `finalize_model_processing` | model_processing | 120s | Aggregate results, dispatch predictions |
| `retry_failed_builds` | model_processing | 360s | Retry FAILED builds (extraction + prediction) |
| `handle_processing_chain_error` | model_processing | 120s | Error handler for chain failures |

### 3.2 Processing Flow

```
User clicks "Start Processing"
       │
       ▼
start_processing_phase (API → Task)
│
├─ Check status is INGESTED or PROCESSED
├─ Get checkpoint (last_processed_import_build_id)
├─ Find unprocessed builds after checkpoint
│   └─ Include both INGESTED and FAILED builds
└─ Dispatch dispatch_build_processing
       │
       ▼
dispatch_build_processing
│
├─ Create ModelTrainingBuild for each build (PENDING)
│   └─ Sorted by created_at (oldest → newest)
│
├─ Update status → PROCESSING
│
└─ chain(
       process_workflow_run(build_1),
       process_workflow_run(build_2),
       ...
       process_workflow_run(build_N),
       finalize_model_processing
   ).on_error(handle_processing_chain_error)
       │
       ▼
process_workflow_run (sequential for each build)
│
├─ Find ModelTrainingBuild (PENDING)
├─ Mark extraction_status → IN_PROGRESS
├─ Get feature template (Risk Prediction)
│
├─ extract_features_for_build (Hamilton DAG)
│   ├─ Git features (commits, diff, blame)
│   ├─ Build log features (keywords, patterns)
│   ├─ Temporal features (tr_prev_build)
│   └─ Store in FeatureVector
│
├─ Update ModelTrainingBuild:
│   ├─ feature_vector_id
│   ├─ extraction_status: COMPLETED/PARTIAL/FAILED
│   └─ extraction_error (if any)
│
└─ Publish WebSocket update
       │
       ▼
finalize_model_processing
│
├─ Query DB for builds with extraction_status IN (completed, partial)
│   AND prediction_status = pending (find_builds_for_prediction)
├─ Update repo_config:
│   ├─ status → PROCESSED
│   ├─ last_processed_import_build_id (checkpoint)
│   └─ builds_processing_failed count
│
└─ Dispatch predict_builds_batch (parallel batches)
```

### 3.3 Sequential Processing Pattern

Processing PHẢI tuần tự (oldest → newest) vì:

```python
# Temporal features depend on previous builds
# Ví dụ: tr_prev_build_duration, tr_success_rate_last_5

# Build chain pattern:
chain(
    process_workflow_run(build_1),  # 2024-01-01
    process_workflow_run(build_2),  # 2024-01-02 (references build_1)
    process_workflow_run(build_3),  # 2024-01-03 (references build_2)
    ...
    finalize_model_processing
)
```

### 3.4 Checkpoint Mechanism

```python
# Trong start_processing_phase:
last_checkpoint_id = repo_config.last_processed_import_build_id

# Find builds AFTER checkpoint
pending_builds = import_build_repo.find_unprocessed_builds(
    repo_config_id,
    after_id=last_checkpoint_id,  # ObjectId comparison
    include_failed=True
)

# Sau khi processing hoàn thành (finalize):
update_data["last_processed_import_build_id"] = ObjectId(last_build_id)
```

### 3.5 Data Structures Created (Phase 3)

**ModelTrainingBuild**:
```python
{
    raw_repo_id: ObjectId,
    raw_build_run_id: ObjectId,
    model_repo_config_id: ObjectId,
    model_import_build_id: ObjectId,
    
    # Feature storage reference
    feature_vector_id: ObjectId,  # → FeatureVector collection
    
    # Denormalized metadata
    head_sha: str,
    build_number: int,
    build_created_at: datetime,
    
    # Extraction status
    extraction_status: ExtractionStatus,  # PENDING → IN_PROGRESS → COMPLETED
    extraction_error: Optional[str],
    extracted_at: Optional[datetime],
    
    # Prediction results (Phase 4)
    prediction_status: ExtractionStatus,
    predicted_label: str,           # "LOW", "MEDIUM", "HIGH"
    prediction_confidence: float,   # 0-1
    prediction_uncertainty: float,
    prediction_model_version: str,
    predicted_at: datetime,
}
```

**FeatureVector** (single source of truth for features):
```python
{
    raw_repo_id: ObjectId,
    raw_build_run_id: ObjectId,
    
    # Scoping (Context)
    scope: FeatureVectorScope,      # "model_training" | "dataset_enrichment"
    config_id: Optional[ObjectId],  # Reference to ModelRepoConfig or DatasetVersion
    
    # Version tracking
    dag_version: str,               # Version of Hamilton DAG used
    computed_at: datetime,
    
    # Temporal linking
    tr_prev_build: Optional[str],   # Previous build's ci_run_id
    
    # Extraction status
    extraction_status: ExtractionStatus,
    extraction_error: Optional[str],
    
    # Graceful degradation tracking
    is_missing_commit: bool,        # Whether commit is missing from repo
    missing_resources: List[str],   # Resources unavailable (e.g., 'git_worktree')
    skipped_features: List[str],    # Features skipped due to missing resources
    
    # Computed features
    features: {
        "git_commit_count": 5,
        "git_diff_lines_added": 120,
        "git_diff_lines_deleted": 45,
        "build_log_error_count": 2,
        "tr_prev_build_duration": 180.5,
        ...
    },
    feature_count: int,
    
    # Normalized features (for prediction)
    normalized_features: {...},
    
    # Scan metrics (backfilled asynchronously)
    scan_metrics: {
        "sonar_bugs": 2,
        "sonar_code_smells": 15,
        "trivy_vuln_total": 3,
        ...
    },
}
```

---

## Phase 4: Prediction

**File**: [backend/app/tasks/model_processing.py](backend/app/tasks/model_processing.py)

**Mục đích**: Dự đoán risk level cho mỗi build

### 4.1 Prediction Tasks

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `predict_builds_batch` | model_prediction | 360s | Batch prediction cho nhiều builds |
| `finalize_prediction` | model_prediction | 120s | Finalize: set status PROCESSED, send notifications |

### 4.2 Prediction Flow

```
finalize_model_processing
│
└─ Dispatch prediction batches
       │
       ▼
predict_builds_batch (parallel batches)
│
├─ For each build_id in batch:
│   ├─ Get ModelTrainingBuild
│   ├─ Get FeatureVector (features)
│   ├─ Walk temporal chain (5 previous builds)
│   └─ Add to prediction queue
│
├─ Mark all as prediction_status → IN_PROGRESS
│
├─ Normalize features (PredictionService.normalize_features)
│   └─ Save normalized_features to FeatureVector
│
├─ Run batch prediction:
│   ├─ LSTM temporal model (if history available)
│   └─ Fallback to simple classifier
│
└─ Update each ModelTrainingBuild:
    ├─ predicted_label: "LOW" | "MEDIUM" | "HIGH"
    ├─ prediction_confidence: 0.0 - 1.0
    ├─ prediction_uncertainty: Bayesian uncertainty
    └─ prediction_status: COMPLETED | FAILED
```

### 4.3 Prediction Result Structure

```python
class PredictionResult:
    risk_level: str      # "LOW", "MEDIUM", "HIGH"
    risk_score: float    # Confidence score (0-1)
    uncertainty: float   # Bayesian uncertainty
    model_version: str   # Model version used
    error: Optional[str] # Error message if failed
```

---

## Entities & Data Model

### Entity Relationship Diagram

```
┌─────────────────────┐     ┌─────────────────────┐
│   RawRepository     │     │    RawBuildRun      │
│─────────────────────│     │─────────────────────│
│ _id                 │◄────┤ raw_repo_id         │
│ full_name           │     │ _id                 │
│ github_repo_id      │     │ ci_run_id           │
│ default_branch      │     │ commit_sha          │
│ is_private          │     │ build_number        │
│ main_lang           │     │ status              │
│ ci_provider         │     │ conclusion          │
└─────────────────────┘     └─────────────────────┘
         │                            │
         │                            │
         ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐
│  ModelRepoConfig    │     │  ModelImportBuild   │
│─────────────────────│     │─────────────────────│
│ _id                 │◄────┤ model_repo_config_id│
│ raw_repo_id         │     │ raw_build_run_id    │────┐
│ user_id             │     │ status              │    │
│ full_name           │     │ resource_status     │    │
│ ci_provider         │     │ ci_run_id           │    │
│ status              │     │ commit_sha          │    │
│ max_builds_to_ingest│     └─────────────────────┘    │
│ since_days          │                                │
│ builds_fetched      │                                │
│ builds_ingested     │                                │
│ builds_completed    │                                │
│ last_processed_id   │                                │
└─────────────────────┘                                │
         │                                             │
         │                                             │
         ▼                                             │
┌─────────────────────┐     ┌─────────────────────┐    │
│ ModelTrainingBuild  │     │   FeatureVector     │    │
│─────────────────────│     │─────────────────────│    │
│ _id                 │     │ _id                 │    │
│ model_repo_config_id│     │ raw_repo_id         │    │
│ model_import_build_id     │ raw_build_run_id    │◄───┘
│ raw_repo_id         │     │ ci_run_id           │
│ raw_build_run_id    │     │ features            │
│ feature_vector_id   │────►│ normalized_features │
│ extraction_status   │     │ tr_prev_build       │
│ prediction_status   │     └─────────────────────┘
│ predicted_label     │
│ prediction_confidence│
└─────────────────────┘
```

### Status Enums

```python
class ModelImportStatus(str, Enum):
    """ModelRepoConfig status"""
    QUEUED = "queued"
    FETCHING = "fetching"
    INGESTING = "ingesting"
    INGESTED = "ingested"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class ModelImportBuildStatus(str, Enum):
    """ModelImportBuild status (ingestion phase)"""
    FETCHED = "fetched"             # Build info fetched from CI API
    INGESTING = "ingesting"         # Ingestion in progress
    INGESTED = "ingested"           # Resources ready for processing
    MISSING_RESOURCE = "missing_resource"  # Expected: logs expired (Not retryable)
    FAILED = "failed"                       # Actual error: timeout, network (Retryable)

class ExtractionStatus(str, Enum):
    """ModelTrainingBuild extraction/prediction status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
```

---

## API Endpoints

**File**: [backend/app/api/model_repos.py](backend/app/api/model_repos.py)

### Repository Management

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `POST` | `/repos/import/bulk` | Import multiple repositories |
| `GET` | `/repos/` | List repositories |
| `GET` | `/repos/search` | Search repositories (private installed + public) |
| `GET` | `/repos/available` | Discover available repositories |
| `GET` | `/repos/languages?full_name={owner/repo}` | Detect repository languages |
| `GET` | `/repos/{repo_id}` | Get repository detail |
| `DELETE` | `/repos/{repo_id}` | Delete repository (cascade) |

### Pipeline Control

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `POST` | `/repos/{repo_id}/sync-run` | Trigger manual sync (fetch new builds) |
| `POST` | `/repos/{repo_id}/start-processing` | Start Phase 2 (processing) |
| `POST` | `/repos/{repo_id}/reingest-failed` | Retry FAILED ingestion builds (not MISSING_RESOURCE) |
| `POST` | `/repos/{repo_id}/reprocess-failed` | Retry failed processing/prediction |

### Progress & Builds

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/repos/{repo_id}/import-progress` | Get detailed import progress by status |
| `GET` | `/repos/{repo_id}/import-progress/failed` | Get failed import builds with error details |
| `GET` | `/repos/{repo_id}/import-builds` | List ModelImportBuild records (ingestion phase) |
| `GET` | `/repos/{repo_id}/training-builds` | List ModelTrainingBuild records (processing phase) |
| `GET` | `/repos/{repo_id}/builds` | List builds (RawBuildRun enriched) |
| `GET` | `/repos/{repo_id}/builds/unified` | Unified builds (ingestion + processing + prediction) |
| `GET` | `/repos/{repo_id}/builds/{build_id}` | Get build detail |

### Export

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/repos/{repo_id}/export/preview` | Preview exportable data |
| `GET` | `/repos/{repo_id}/export` | Stream export (CSV/JSON) - for small datasets |
| `POST` | `/repos/{repo_id}/export/async` | Create async export job - for large datasets |
| `GET` | `/repos/{repo_id}/export/jobs` | List export jobs for repository |
| `GET` | `/repos/export/jobs/{job_id}` | Get export job status |
| `GET` | `/repos/export/jobs/{job_id}/download` | Download completed export file |

---

## Frontend UI Flow

- Pages: `/repositories` list, `/repositories/import` wizard, `/repositories/[id]/overview|builds|analytics`.
- Key components: MiniStepper, CollectionCard, ProcessingCard, UnifiedBuildsTable, ActionProgressBanner.
- Actions: import repos, start processing, retry failed ingestion/processing, view unified builds and analytics.

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
| Feature extraction failed | FAILED | Yes | `retry_failed_builds` |
| Hamilton DAG error | FAILED | Yes | `retry_failed_builds` |
| Prediction timeout | FAILED | Yes | `retry_failed_builds` (handles both extraction + prediction) |
| Prediction model error | FAILED | Yes | `retry_failed_builds` (skips extraction if already COMPLETED) |

### Error Callbacks

```python
# Ingestion chord error
handle_ingestion_chord_error:
  - Mark all INGESTING → FAILED
  - Update repo → INGESTED (partial success) or FAILED
  - Allow user to retry

# Processing chain error
handle_processing_chain_error:
  - Mark all IN_PROGRESS → FAILED
  - Update repo → PROCESSED or FAILED
  - Allow user to retry
```

---

## SSE Real-time Updates

- Event name format: `{PIPELINE}.{ENTITY}.{ACTION}`.
- Model events: `MODEL.REPO.UPDATED`, `MODEL.INGESTION.PROGRESS`, `MODEL.PROCESSING.UPDATED`, `MODEL.PREDICTION.UPDATED` (legacy events removed).
- Payloads carry ids, status, counts; frontend merges via delta update (see `UnifiedBuildsTable`).
- Backend uses helpers in `app/tasks/shared/events.py` to publish.

<details>
<summary>Minimal payload examples</summary>

```json
{ "type": "MODEL.REPO.UPDATED", "payload": { "repo_id": "...", "status": "processing" } }
{ "type": "MODEL.PROCESSING.UPDATED", "payload": { "repo_id": "...", "build_id": "...", "extraction_status": "completed", "feature_count": 45 } }
```

</details>

## Performance Optimization

### Batch Processing

```python
# Fetch: Parallel pages với chord
chord(
    group(fetch_builds_batch × N),
    aggregate_fetch_results
)

# Ingestion: Chunked parallel tasks
group([
    clone_repo,
    group(create_worktree_chunk × M),
    group(download_logs_chunk × K),
])

# Prediction: Parallel batches
PREDICTION_BUILDS_PER_BATCH = 50
group(predict_builds_batch × ceil(N/50))
```

### Checkpoint-based Processing

```python
# Only process builds after checkpoint
pending_builds = import_build_repo.find_unprocessed_builds(
    repo_config_id,
    after_id=last_checkpoint_id,  # ObjectId comparison is efficient
)

# Checkpoint updated AFTER processing completes
# Prevents re-processing on retry
```

### Database Optimization

- **Indexes**: `raw_build_run_id + model_repo_config_id` compound index
- **Bulk operations**: `bulk_insert`, `update_many_by_status`
- **Atomic upserts**: `upsert_by_business_key` prevents duplicates
- **ObjectId cursors**: Efficient pagination without offset

---

## Summary

Model Training Pipeline là một hệ thống 4-phase xử lý builds từ GitHub:

1. **Import & Fetch**: Verify repo, fetch builds từ CI API
2. **Ingestion**: Clone git, create worktrees, download logs
3. **Processing**: Extract features (sequential), store in FeatureVector
4. **Prediction**: Batch prediction với ML model

**Key Design Decisions**:
- Two-phase pipeline với user control (Ingestion → Processing)
- Sequential processing cho temporal features
- Checkpoint mechanism cho incremental processing
- Graceful degradation (MISSING_RESOURCE vs FAILED)
- Real-time updates via SSE (Server-Sent Events) with delta merge pattern
- Template-based expected feature count using DatasetTemplate + DEFAULT_FEATURES
