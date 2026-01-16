# Training Scenario Pipeline - Mô Tả Chi Tiết Toàn Bộ Luồng

## 📋 Mục Lục
1. [Tổng Quan Kiến Trúc](#tổng-quan-kiến-trúc)
2. [Dashboard Statistics](#dashboard-statistics)
3. [Phase 0: Build Source Upload](#phase-0-build-source-upload)
4. [Phase 1: Filtering & Ingestion](#phase-1-filtering--ingestion)
5. [Phase 2: Processing](#phase-2-processing)
   - [2.A: Feature Extraction](#2a-feature-extraction)
   - [2.B: Scan Metrics Collection](#2b-scan-metrics-collection)
6. [Phase 3: Dataset Generation](#phase-3-dataset-generation)
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
┌──────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: PROCESSING (Parallel Workflows)                                │
│                                                                          │
│  ┌─────────────────────────────────┐   ┌─────────────────────────────────┐
│  │ 2.A: FEATURE EXTRACTION         │   │ 2.B: SCAN METRICS (Optional)   │
│  │  ✓ Create EnrichmentBuild       │   │  ✓ Dispatch scans (fire&forget)│
│  │  ✓ Hamilton DAG extraction      │   │  ✓ Trivy/SonarQube parallel    │
│  │  ✓ Sequential (temporal deps)   │   │  ✓ Backfill to FeatureVector   │
│  │                                 │   │                                 │
│  │  ⏱️ When done:                   │   │  ⏱️ Runs independently:         │
│  │  → status = PROCESSED           │   │  → scan_extraction_completed   │
│  │  → feature_extraction_completed │   │  → Metrics available gradually │
│  └─────────────────────────────────┘   └─────────────────────────────────┘
│               │                                    │                     │
│               ▼                                    │                     │
│     PROCESSED (features done)                      │                     │
│     ✅ Analysis tab available                      │ (may still running) │
│     ✅ Export tab available                        │                     │
│               │◄───────────────────────────────────┘                     │
│               │  (scans backfill to FeatureVector.scan_metrics)          │
└───────────────│──────────────────────────────────────────────────────────┘
                │
                ▼
TrainingScenario (PROCESSED) - Ready for Analysis & Export
│
├─ feature_extraction_completed = true  (required)
└─ scan_extraction_completed = true/false (optional enrichment)
       │
       ▼ (User creates TrainingDatasetExport)
┌──────────────────────────────────────────┐
│  EXPORT: DATASET GENERATION              │
│  ✓ Create TrainingDatasetExport entity   │
│  ✓ Apply splitting strategy (per-export) │
│  ✓ Generate train/val/test files         │
│  ✓ Export to parquet/csv                 │
└──────────────────────────────────────────┘
       │
       ▼
TrainingDatasetExport (COMPLETED) + Dataset Splits Ready
```

### Queue Architecture

```
┌──────────────────────────────────────────────┐
│           Celery Queue System                │
├──────────────────────────────────────────────┤
│ scenario_ingestion  │ Filtering, clone,      │
│                     │ worktree, logs         │
│ scenario_processing │ Feature extraction,    │
│                     │ dataset generation     │
│ scenario_scanning   │ Trivy/SonarQube scans  │
└──────────────────────────────────────────────┘
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
                                          PROCESSING
                                               │
                           ┌───────────────────┴───────────────────┐
                           │                                       │
                    [Feature Extraction]                   [Scan Collection]
                     (Sequential chain)                    (Fire & forget)
                           │                                       │
                           ▼                                       ▼
                  feature_extraction_completed          scan_extraction_completed
                           │                                       │
                           ▼                                       │
                       PROCESSED ◄─────────────────────────────────┘
                           │              (scans may complete later)
                           │
                           ▼
          ┌────────────────────────────────────────────┐
          │ PROCESSED = feature_extraction_completed   │
          │                                            │
          │ ✅ Analysis tab: Available immediately     │
          │ ✅ Export tab: Available immediately       │
          │                                            │
          │ 🔄 If scans still running:                 │
          │    - Show progress indicator               │
          │    - Export uses available scan_metrics    │
          │    - Refresh to get updated metrics        │
          └────────────────────────────────────────────┘

Completion Flags (independent of status):

    feature_extraction_completed: bool  # ✅ Required for PROCESSED
    scan_extraction_completed: bool     # ℹ️ Optional enrichment

TrainingDatasetExport Status Flow:

    QUEUED ──► GENERATING ──► COMPLETED
                    │
                    ▼
                  FAILED
```

---

## Dashboard Statistics

### Training Scenario Widget (Admin Only)

The **Training Scenarios Summary** widget displays real-time status metrics for the entire TRAINING SCENARIO PIPELINE:

| Metric | Meaning | Source Collection |
|--------|---------|------------------|
| **Active** | Total training scenarios created | `training_scenarios` (all records) |
| **Queued** | Scenarios waiting to start ingestion | `training_scenarios` with status=QUEUED |
| **Processing** | Scenarios currently filtering, ingesting, or extracting features | `training_scenarios` with status IN (FILTERING, INGESTING, PROCESSING) |
| **Processed** | Scenarios finished feature extraction (exports are tracked separately) | `training_scenarios` with status=PROCESSED |

These metrics help admins track dataset preparation progress and manage training workflows.

---

## Phase 0: Build Source Upload (tóm tắt)

- CSV upload → validate repos/builds → persist to RawRepository/RawBuildRun.
- Tasks: `validate_build_source` + batch validators; output stats on found/not_found/filtered.

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
| `start_scenario_ingestion` | scenario_ingestion | 180s | Orchestrator: Filter + dispatch ingestion |
| `aggregate_scenario_ingestion` | scenario_ingestion | 180s | Aggregate results, mark INGESTED |
| `handle_scenario_chord_error` | scenario_ingestion | 120s | Error callback |
| `reingest_failed_builds` | scenario_ingestion | 900s | Retry FAILED builds |

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
    languages: ["python", "java"],      # Filter by main_lang
    date_start: "2024-01-01",
    date_end: "2024-12-31",
    conclusions: ["success", "failure"],
    ci_provider: "all" | "github_actions" | "circleci",  # legacy single-provider field
    ci_providers: ["github_actions"],      # optional list override used by API
    build_source_ids: ["<build_source_id>"]  # optional: scope to uploaded sources
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

## Phase 2: Processing

**File**: [backend/app/tasks/training_processing.py](backend/app/tasks/training_processing.py)

**Mục đích**: Processing là phase song song gồm 2 sub-phases:
- **2.A Feature Extraction**: Extract features từ builds sử dụng Hamilton DAG
- **2.B Scan Metrics Collection**: Thu thập scan metrics từ Trivy/SonarQube

### 2.1 Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `start_scenario_processing` | scenario_processing | 120s | User triggers Phase 2 |
| `dispatch_scans_and_processing` | scenario_processing | 180s | Dispatch scans + feature extraction |
| `dispatch_scenario_scans` | scenario_scanning | 600s | Fire-and-forget scan dispatch |
| `process_scan_batch` | scenario_scanning | 300s | Process single batch of scan dispatches |
| `finalize_scan_dispatch` | scenario_scanning | 180s | Finalize after all scan batches complete |
| `dispatch_enrichment_batches` | scenario_processing | 240s | Create EnrichmentBuild, dispatch chain |
| `process_single_enrichment` | scenario_processing | 600s | Extract features for 1 build (max_retries=2) |
| `finalize_feature_extraction` | scenario_processing | 120s | Mark PROCESSED, notify users |
| `reprocess_failed_feature_extraction` | scenario_processing | 360s | Retry failed builds |
| `retry_failed_scenario_scans` | scenario_scanning | 600s | Retry failed scans (tool-specific, batch mode) |
| `process_retry_scan_batch` | scenario_scanning | 300s | Process single batch of scan retries |
| `handle_processing_chain_error` | scenario_processing | 120s | Error handler for chain failures |

### 2.2 Processing Flow (Progressive Availability)

> **Key Design**: Feature extraction determines PROCESSED status. Scans run independently and backfill metrics to `FeatureVector.scan_metrics` as they complete.

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
       ├────────────────────────────────────────────────────────────┐
       │                                                            │
       ▼                                                            ▼
[2.A] dispatch_enrichment_batches                    [2.B] dispatch_scenario_scans
       │                                                   (async, fire & forget)
       ├─ Create EnrichmentBuild per build                        │
       └─ chain(                                                  │
              process_single_enrichment(build_1),                 │
              process_single_enrichment(build_2),                 │
              ...,                                                │
              finalize_feature_extraction                         │
          )                                                       │
              │                                                   │
              ▼                                                   ▼
    feature_extraction_completed = true          scan_extraction_completed = true
    status = PROCESSED                           (when all scans done)
              │                                           │
              ▼                                           │
    ┌─────────────────────────────────────────────────────┤
    │  PROCESSED                                          │
    │  ✅ Analysis tab: Shows features + partial scans    │
    │  ✅ Export tab: Can export with available data      │
    │  🔄 Scans continue backfilling in background        │
    └─────────────────────────────────────────────────────┘
```

### 2.A Feature Extraction (Sequential)

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

### 2.B Scan Metrics Collection (Parallel Batches)

Scans run as fire-and-forget parallel task:

```
dispatch_scenario_scans
│
├─ Collect unique commits from ingested builds
├─ Split into batches (SCAN_COMMITS_PER_BATCH = 20)
└─ chain(
       process_scan_batch(batch_0),
       process_scan_batch(batch_1),
       ...,
       finalize_scan_dispatch
   )
       │
       └─ Each batch dispatches to scan queues:
           ├─ start_trivy_scan_for_version_commit
           └─ start_sonar_scan_for_version_commit
```

**Retry Failed Scans** (Tool-Specific):
```
retry_failed_scenario_scans (tool_type: "trivy" | "sonarqube")
│
├─ Find all FAILED scans for specified tool only
├─ Split into batches (SCAN_COMMITS_PER_BATCH = 20)
└─ chain(
       process_retry_scan_batch(batch_0),
       process_retry_scan_batch(batch_1),
       ...
   )
       │
       └─ For each scan in batch:
           ├─ Check DB status (skip if COMPLETED)
           ├─ [SonarQube only] Check server existence via API
           │   └─ Skip if project already exists on SonarQube
           ├─ Reset status → PENDING, increment retry_count
           └─ Dispatch to tool-specific task:
               ├─ start_trivy_scan_for_version_commit
               └─ start_sonar_scan_for_version_commit
```

> [!NOTE]
> SonarQube retry checks if project already exists on server via `_project_exists(component_key)` API call.
> If project exists, scan is skipped to avoid duplicate analysis.

### 2.C Feature Config

> **Note:** The UI allows selecting explicit feature names; backend expands simple wildcard patterns (e.g., `gh_*`, `tr_*`) before extraction, matching the `_expand_feature_patterns` helper in `training_processing.py`.

```python
FeatureConfig = {
    # Explicit feature names selected from UI
    dag_features: [
        "tr_build_duration",
        "tr_build_queue_time",
        "gh_commits_count",
        "gh_files_changed",
        "gh_lines_added",
        "gh_lines_deleted",
        "tr_prev_build_failed",
        "tr_success_rate_last_5",
        # ... more features as selected in UI
    ],
    scan_metrics: {
        sonarqube: ["code_smells", "bugs", "coverage"],
        trivy: ["critical", "high", "medium"],
    },
    extractor_configs: {
        "lookback_days": 90,
        "test_frameworks": ["pytest", "junit"],
    },
}
```

---

## Export: Dataset Generation

**File**: [backend/app/tasks/training_export.py](backend/app/tasks/training_export.py) (`generate_export_dataset`)

**Mục đích**: Cho phép tạo nhiều dataset exports từ một scenario đã PROCESSED

### Export Architecture

Mỗi `TrainingDatasetExport` có config riêng:
- `splitting_config`: Cấu hình split strategy
- `preprocessing_config`: Missing values, normalization
- `output_config`: Formats (parquet, csv)

### Tasks Overview

| Task | Queue | Timeout | Mô Tả |
|------|-------|---------|-------|
| `generate_export_dataset` | scenario_processing | 720s | Generate dataset for one export |

### Generation Flow

```
User creates TrainingDatasetExport via API
       │
       ▼
POST /training-scenarios/{id}/exports
│
├─ Create TrainingDatasetExport entity (PENDING)
└─ User triggers generation via POST /exports/{id}/generate
       │
       ▼
generate_export_dataset (Celery task)
│
├─ Validate scenario is PROCESSED
├─ Update export status → GENERATING
│
├─ Collect features from EnrichmentBuilds
│   ├─ Query all builds with extraction_status = COMPLETED
│   ├─ Join with FeatureVector.features
│   └─ Join with FeatureVector.scan_metrics (if available)
│
├─ Build pandas DataFrame
│   ├─ Feature columns
│   ├─ Label column (outcome: 0=success, 1=failure)
│   └─ Metadata (repo, commit, build_id)
│
├─ Apply splitting strategy (from export config):
│   ├─ stratified_within_group (default)
│   ├─ leave_one_out (L1GO) - requires ≥3 groups
│   ├─ leave_two_out (L2GO) - requires ≥4 groups
│   ├─ extreme_novelty - isolate target group+label → test
│   ├─ imbalanced_train - reduce label 1 in train only
│   ├─ time_series_split
│   └─ random_split / stratified_split
│
├─ Export files to export-specific directory:
│   ├─ train.parquet (based on ratios)
│   ├─ val.parquet
│   └─ test.parquet
│
├─ Create TrainingDatasetSplit records (linked to export_id)
│
└─ Update export status → COMPLETED
```

### ExportSplittingConfig

```python
ExportSplittingConfig = {
    strategy: "stratified_within_group" | "leave_one_out" | "leave_two_out" |
              "extreme_novelty" | "imbalanced_train" | "time_series_split" |
              "random_split" | "stratified_split",
    group_by: "repo_language" | "time_of_day" |
              "percentage_of_builds_before" | "number_of_builds_before",
    stratify_by: "outcome",
    ratios: {
        train: 0.7,
        val: 0.15,
        test: 0.15,
    },
    # Dynamic binning parameters:
    num_bins: 4,        # 2-10, for numeric features (% builds, # builds)
    time_slots: 4,      # 2-12, for time_of_day grouping

    # For leave_one_out/leave_two_out strategies:
    test_groups: ["python"],        # L1GO: 1 group, L2GO: 2 groups
    val_groups: ["java"],

    # For extreme_novelty strategy:
    novelty_group: "python",        # Target group to isolate
    novelty_label: 1,               # 0=success, 1=failure (must be 0 or 1)

    # For imbalanced_train strategy:
    imbalance_reduction_rate: 0.5,  # 0-1, percentage of label 1 to remove from train
}
```

### Splitting Strategies (app.services.strategies/)

| Strategy | Mô tả | Requirements |
|----------|-------|-------------|
| `stratified_within_group` | Split within each group with stratification | - |
| `leave_one_out` (L1GO) | 1 group → test, 1 group → val | ≥3 groups |
| `leave_two_out` (L2GO) | 2 groups → test, 1 group → val | ≥4 groups |
| `extreme_novelty` | Target group + label → test (zero-shot) | novelty_group, novelty_label |
| `imbalanced_train` | Remove X% of label 1 from train only | imbalance_reduction_rate |
| `time_series_split` | Chronological split (oldest → newest) | build_started_at column |
| `random_split` | Pure random assignment | - |
| `stratified_split` | Random split preserving label distribution | - |

### TrainingDatasetExport

```python
{
    scenario_id: ObjectId,
    name: str,
    status: "queued" | "generating" | "completed" | "failed",
    splitting_config: ExportSplittingConfig,
    preprocessing_config: PreprocessingConfig,
    output_config: OutputConfig,
    # Statistics (after completion):
    train_count: int,
    val_count: int,
    test_count: int,
    feature_count: int,
    generation_duration_seconds: float,
}
```

### TrainingDatasetSplit

```python
{
    export_id: ObjectId,      # Primary reference
    scenario_id: ObjectId,    # Denormalized for convenience
    split_type: "train" | "val" | "test",
    file_path: str,
    file_format: "parquet" | "csv",
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
└─────────────────────┘              │
         │                           ▼
         │              ┌─────────────────────┐
         │              │TrainingEnrichmentBuild│
         │              │─────────────────────│
         │              │ scenario_id         │
         │              │ ingestion_build_id  │
         │              │ feature_vector_id   │───► FeatureVector
         │              │ extraction_status   │
         │              │ outcome             │   # 0=success, 1=failure
         │              │ build_started_at    │
         │              └─────────────────────┘
         │
         ▼
┌─────────────────────┐     ┌─────────────────────┐
│TrainingDatasetExport│     │TrainingDatasetSplit │
│─────────────────────│     │─────────────────────│
│ _id                 │◄────┤ export_id           │
│ scenario_id         │     │ scenario_id         │
│ name                │     │ split_type          │
│ status              │     │ file_path           │
│ splitting_config    │     │ record_count        │
│ preprocessing_config│     │ class_distribution  │
│ output_config       │     └─────────────────────┘
│ train_count         │
│ val_count           │
│ test_count          │
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
    PROCESSED = "processed"  # Final state for scenario
    FAILED = "failed"

class ExportStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
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
| `POST` | `/training-scenarios/{id}/ingest` | Start Phase 1 (Ingestion) |
| `POST` | `/training-scenarios/{id}/process` | Start Phase 2 (Processing) |
| `POST` | `/training-scenarios/{id}/generate` | Start Phase 3 (Dataset Generation) |
| `POST` | `/training-scenarios/{id}/retry-ingestion` | Retry failed ingestion |
| `POST` | `/training-scenarios/{id}/reprocess-failed-feature-extraction` | Retry failed feature extraction |

### Filtering & Preview

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/training-scenarios/preview-builds` | Preview builds with filters |
| `GET` | `/training-scenarios/filter-options` | Get dynamic filter options |
| `GET` | `/training-scenarios/splitting-groups` | Get splitting groups for wizard |
| `GET` | `/training-scenarios/{id}/split-group-distribution` | Preview group distribution |
| `GET` | `/training-scenarios/{id}/splitting-groups` | Get scenario splitting groups |
| `GET` | `/training-scenarios/{id}/data-quality-report` | Get data quality report |
| `GET` | `/training-scenarios/{id}/data-availability` | Get data availability summary |

### Builds & Splits

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/training-scenarios/{id}/ingestion-builds` | List ingestion builds |
| `GET` | `/training-scenarios/{id}/enrichment-builds` | List enrichment builds |
| `GET` | `/training-scenarios/{id}/enrichment-builds/{build_id}` | Get enrichment build detail |

### Scan Status

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/training-scenarios/{id}/scan-status` | Get scan progress status |
| `GET` | `/training-scenarios/{id}/commit-scans` | List commit scan results |
| `GET` | `/training-scenarios/{id}/commit-scans/{commit_sha}` | Get commit scan detail |
| `POST` | `/training-scenarios/{id}/retry-scans?tool_type=trivy\|sonarqube` | Retry failed scans for specific tool (required param) |

### Exports

| Method | Endpoint | Mô Tả |
|--------|----------|-------|
| `GET` | `/training-scenarios/{id}/exports` | List exports for scenario |
| `POST` | `/training-scenarios/{id}/exports` | Create new export |
| `GET` | `/training-scenarios/{id}/exports/{export_id}` | Get export detail |
| `DELETE` | `/training-scenarios/{id}/exports/{export_id}` | Delete export |
| `POST` | `/training-scenarios/{id}/exports/{export_id}/generate` | Trigger export generation |
| `GET` | `/training-scenarios/{id}/exports/{export_id}/splits` | List splits for export |
| `GET` | `/training-scenarios/{id}/exports/{export_id}/splits/{split_id}/download` | Download single split file |
| `GET` | `/training-scenarios/{id}/exports/{export_id}/download-all` | Download all splits as zip |

---

## Frontend UI Flow

- Pages: `/scenarios` list, `/scenarios/sources` (upload/validate), `/scenarios/create` wizard, `/scenarios/[id]/overview|builds|scans|analysis|export`.
- Key actions: start ingestion, start processing, retry failed ingestion/processing/scans, trigger export generation.
- Scans page: two tabs (SonarQube, Trivy) with retry buttons when failures exist.

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
| Feature extraction failed | FAILED | Yes | `reprocess_failed_feature_extraction` |
| Hamilton DAG error | FAILED | Yes | `reprocess_failed_feature_extraction` |

### Scan Errors

| Error Type | Status | Retryable | Action |
|------------|--------|-----------|--------|
| Trivy scan timeout | FAILED | Yes | `retry_failed_scenario_scans(tool_type="trivy")` |
| Trivy CLI error | FAILED | Yes | `retry_failed_scenario_scans(tool_type="trivy")` |
| SonarQube scan timeout | FAILED | Yes | `retry_failed_scenario_scans(tool_type="sonarqube")` |
| SonarQube API error | FAILED | Yes | `retry_failed_scenario_scans(tool_type="sonarqube")` |
| Project exists on server | N/A | **Skip** | Already exists, fetch metrics instead |

---

## SSE Real-time Updates

### Event Naming Convention

Events follow the format: `{PIPELINE}.{ENTITY}.{ACTION}`

- **PIPELINE**: `SCENARIO` (Training Scenario Pipeline)
- **ENTITY**: `INGESTION`, `PROCESSING`, `SCAN`
- **ACTION**: `UPDATED`, `ERROR`

### Event Types

Scenario Pipeline publishes the following SSE events:

| Event Type | Purpose | When Published |
|------------|---------|----------------|
| `SCENARIO.UPDATED` | Scenario aggregate status | Status transitions (QUEUED → FILTERING → INGESTING → etc.) |
| `SCENARIO.INGESTION.UPDATED` | Ingestion resource progress | Git clone, worktree creation, log download |
| `SCENARIO.PROCESSING.UPDATED` | Processing/enrichment progress | Feature extraction per build |
| `SCENARIO.SCAN.UPDATED` | Scan status change | Trivy/SonarQube scan completion or errors |
| `EXPORT.UPDATED` | Export generation progress | Export status transitions (QUEUED → GENERATING → COMPLETED) |
| `SOURCE.VALIDATION.UPDATED` | Build source validation progress | Validation of CSV uploads |

### Event Payloads

```python
# SCENARIO.UPDATED - Scenario status change
{
    "type": "SCENARIO.UPDATED",
    "payload": {
        "scenario_id": "...",
        "status": "processing",
        "message": "Extracting features for 150 builds...",
        "stats": {
            "builds_total": 500,
            "builds_ingested": 450,
            "builds_processed": 150,
        }
    }
}

# SCENARIO.INGESTION.UPDATED - Ingestion progress (shared with Model pipeline)
{
    "type": "SCENARIO.INGESTION.UPDATED",
    "payload": {
        "scenario_id": "...",
        "resource": "git_worktree",  # git_history | git_worktree | build_logs
        "status": "in_progress",     # in_progress | completed | failed | completed_with_errors
        "builds_affected": 10,
        "chunk_index": 2,
        "total_chunks": 5,
        "completed_commit_shas": ["abc123", "def456"],
        "failed_commit_shas": []
    }
}

# SCENARIO.PROCESSING.UPDATED - Feature extraction progress
{
    "type": "SCENARIO.PROCESSING.UPDATED",
    "payload": {
        "scenario_id": "...",
        "build_id": "...",
        "phase": "processing",
        "status": "completed",
        "feature_count": 45,
        "expected_feature_count": 45
    }
}

# SCENARIO.SCAN.UPDATED - Scan completion
{
    "type": "SCENARIO.SCAN.UPDATED",
    "payload": {
        "scenario_id": "...",
        "build_id": "...",
        "scan_type": "trivy",  # trivy | sonarqube
        "status": "completed"
    }
}
```

### Frontend SSE Subscription with Delta Merge

Frontend uses SSE subscriptions with delta merge pattern for efficient real-time updates:

```tsx
// Subscribe to scenario events
useEffect(() => {
    const unsubIngestion = subscribe("SCENARIO.INGESTION.UPDATED", (data) => {
        if (data.scenario_id === scenarioId) {
            // Delta merge: update affected builds
            setBuilds((prev) => prev.map((build) => {
                if (data.completed_commit_shas?.includes(build.commit_sha)) {
                    return { ...build, ingestion_status: "completed" };
                }
                return build;
            }));
        }
    });

    const unsubProcessing = subscribe("SCENARIO.PROCESSING.UPDATED", (data) => {
        if (data.scenario_id === scenarioId) {
            // Delta merge: update specific build
            setBuilds((prev) => prev.map((build) =>
                build.id === data.build_id
                    ? { ...build, processing_status: data.status,
                        feature_count: data.feature_count }
                    : build
            ));
        }
    });

    return () => {
        unsubIngestion();
        unsubProcessing();
    };
}, [subscribe, scenarioId]);
```

### Backend Event Publishing

Events are published via shared utility functions in `app/tasks/shared/events.py`:

```python
from app.tasks.shared.events import (
    publish_scenario_updated,
    publish_ingestion_progress,
    publish_scenario_processing_updated,
    publish_scenario_scan_updated,
)

# Publish scenario status update
publish_scenario_updated(
    scenario_id=str(scenario.id),
    status="processing",
    message=f"Processing {count} builds...",
    stats={"builds_total": 500, "builds_ingested": 450}
)

# Publish ingestion progress (shared function for both pipelines)
publish_ingestion_progress(
    repo_id=str(scenario.id),
    resource="git_worktree",
    status="completed",
    pipeline_type="dataset",  # "dataset" for Scenario pipeline
    builds_affected=10,
    chunk_index=2,
    total_chunks=5,
    completed_commit_shas=["abc123"]
)

# Publish processing progress
publish_scenario_processing_updated(
    scenario_id=str(scenario.id),
    build_id=str(build.id),
    status="completed",
    feature_count=45,
    expected_feature_count=45
)
```

### Shared Ingestion Tasks

The ingestion tasks (git clone, worktree creation, log download) are shared between Model and Scenario pipelines. The `pipeline_type` parameter determines which event type is published:

```python
# In app/tasks/shared/events.py
def publish_ingestion_progress(
    repo_id: str,
    resource: str,
    status: str,
    pipeline_type: str = "model",  # "model" or "dataset"
    ...
) -> bool:
    # Determine event type based on pipeline
    if pipeline_type == "dataset":
        event_type = EventType.SCENARIO_INGESTION_UPDATED
        payload = {"scenario_id": repo_id, ...}
    else:
        event_type = EventType.MODEL_INGESTION_PROGRESS
        payload = {"repo_id": repo_id, ...}
    
    return publish_event(event_type, payload)
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
- **Tool-specific retry**: Retry scans theo tool (Trivy/SonarQube riêng), check server existence cho SonarQube
- **Real-time updates via SSE**: Server-Sent Events với delta merge pattern cho frontend
- **Shared ingestion tasks**: `publish_ingestion_progress(pipeline_type)` hỗ trợ cả Model và Scenario pipelines
- **Template-based expected features**: Sử dụng `DatasetTemplate.feature_names + DEFAULT_FEATURES` để tính expected_feature_count
