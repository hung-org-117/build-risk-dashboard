# ML Scenario YAML Configuration Guide

Hướng dẫn viết file YAML để cấu hình ML Dataset Scenario.

## 📋 Cấu Trúc Cơ Bản

```yaml
scenario:         # Required - Thông tin scenario
  name: "..."
  description: "..."

data_source:      # Optional - Lọc dữ liệu
  repositories: ...
  builds: ...

features:         # Optional - Chọn features
  dag_features: [...]

splitting:        # Required - Chiến lược chia tách
  strategy: "..."
  group_by: "..."
  config: ...

preprocessing:    # Optional - Tiền xử lý
  missing_values_strategy: "..."

output:           # Optional - Định dạng output
  format: "parquet"
```

---

## 📌 Section: `scenario` (Required)

| Field | Type | Required | Default | Mô tả |
|-------|------|----------|---------|-------|
| `name` | string | ✅ | - | Tên duy nhất của scenario |
| `description` | string | ❌ | null | Mô tả chi tiết |
| `version` | string | ❌ | "1.0" | Phiên bản |

```yaml
scenario:
  name: "my_experiment_v1"
  description: "Testing language generalization"
  version: "1.0"
```

---

## 📌 Section: `data_source`

Cấu hình lọc repositories và builds từ database.

### Repositories Filter

| Field | Type | Values | Mô tả |
|-------|------|--------|-------|
| `filter_by` | enum | `all`, `by_language`, `by_name`, `by_owner` | Cách lọc |
| `languages` | list | - | Ngôn ngữ (nếu `filter_by: by_language`) |
| `repo_names` | list | - | Tên repo (nếu `filter_by: by_name`) |
| `owners` | list | - | Owners (nếu `filter_by: by_owner`) |

### Builds Filter

| Field | Type | Mô tả |
|-------|------|-------|
| `date_range.start` | date | Ngày bắt đầu (YYYY-MM-DD) |
| `date_range.end` | date | Ngày kết thúc |
| `conclusions` | list | `["success", "failure"]` |
| `exclude_bots` | bool | Loại bỏ bot commits (default: true) |

```yaml
data_source:
  repositories:
    filter_by: "by_language"
    languages: ["python", "javascript", "java"]
  builds:
    date_range:
      start: "2024-01-01"
      end: "2024-12-31"
    conclusions: ["success", "failure"]
    exclude_bots: true
  ci_provider: "github_actions"  # or "all", "circleci"
```

---

## 📌 Section: `features`

| Field | Type | Mô tả |
|-------|------|-------|
| `dag_features` | list | Patterns hỗ trợ wildcard |
| `scan_metrics` | object | `{sonarqube: [...], trivy: [...]}` |
| `exclude` | list | Features cần loại bỏ |

### Feature Patterns (Wildcards)

| Pattern | Mô tả |
|---------|-------|
| `build_*` | Build metadata (ID, status, duration, timing) |
| `git_*` | Git operations (commits, branches, diffs) |
| `log_*` | Build logs (tests, frameworks) |
| `repo_*` | Repository stats (age, SLOC) |
| `pr_*` | Pull request info |
| `team_*` | Team metrics |
| `history_*` | Temporal features (prev builds, fail rates) |
| `author_*` | Author experience |
| `devops_*` | DevOps/CI config changes |

### Scan Metrics

Thu thập metrics từ công cụ quét bảo mật.

#### SonarQube Metrics (Available)

| Metric | Type | Mô tả |
|--------|------|-------|
| `bugs` | int | Số bugs phát hiện |
| `vulnerabilities` | int | Lỗ hổng bảo mật |
| `code_smells` | int | Code smells |
| `coverage` | float | % Test coverage |
| `duplicated_lines_density` | float | % Duplicate code |
| `reliability_rating` | str | A-E rating |
| `security_rating` | str | A-E rating |

#### Trivy Metrics (Available)

| Metric | Type | Mô tả |
|--------|------|-------|
| `critical` | int | Critical vulnerabilities |
| `high` | int | High severity |
| `medium` | int | Medium severity |
| `low` | int | Low severity |
| `total` | int | Total vulnerabilities |
| `has_critical` | bool | Has critical issues |

```yaml
features:
  dag_features:
    - "build_*"
    - "git_*"
    - "history_*"
  scan_metrics:
    sonarqube: 
      - "bugs"
      - "vulnerabilities"
      - "code_smells"
      - "coverage"
    trivy: 
      - "critical"
      - "high"
      - "medium"
  exclude:
    - "git_raw_*"
```

> [!NOTE]
> Scan metrics được merge từ `FeatureVector.scan_metrics`. Chúng được thu thập tự động khi builds đã có kết quả scan từ Trivy hoặc SonarQube.

---

## 📌 Section: `splitting` (Required)

### Strategies

| Strategy | Mô tả | Required Config |
|----------|-------|-----------------|
| `stratified_within_group` | Chia đều trong mỗi group | `ratios`, `stratify_by` |
| `leave_one_out` | Một group làm test | `test_groups` |
| `leave_two_out` | Hai groups làm val/test | `test_groups`, `val_groups` |
| `imbalanced_train` | Giảm samples của 1 label | `reduce_label`, `reduce_ratio` |
| `extreme_novelty` | Group+label → test only | `novelty_group`, `novelty_label` |

### Group By Dimensions

| Value | Mô tả |
|-------|-------|
| `language_group` | Groups: backend, fullstack, scripting, other |
| `time_of_day` | Theo giờ trong ngày |
| `percentage_of_builds_before` | Theo % builds trước đó |
| `number_of_builds_before` | Theo số builds trước đó |

### Examples

#### Stratified Within Group (Baseline)
```yaml
splitting:
  strategy: "stratified_within_group"
  group_by: "language_group"
  config:
    ratios:
      train: 0.70
      val: 0.15
      test: 0.15
    stratify_by: "outcome"
```

#### Leave One Out
```yaml
splitting:
  strategy: "leave_one_out"
  group_by: "language_group"
  config:
    test_groups: ["backend"]       # Python, Java, Go, Rust
    val_groups: ["fullstack"]      # JavaScript
    # Remaining groups → train
```

#### Imbalanced Train
```yaml
splitting:
  strategy: "imbalanced_train"
  group_by: "language_group"
  config:
    ratios:
      train: 0.70
      val: 0.15
      test: 0.15
    reduce_label: 1      # 0=success, 1=failure
    reduce_ratio: 0.5    # Giảm 50%
```

#### Extreme Novelty
```yaml
splitting:
  strategy: "extreme_novelty"
  group_by: "language_group"
  config:
    novelty_group: "backend"   # Group
    novelty_label: 1           # Label (failure)
    ratios:
      train: 0.85
      val: 0.15
    # (group=backend AND label=1) → Test only
```

---

## 📌 Section: `preprocessing`

| Field | Type | Values | Default |
|-------|------|--------|---------|
| `missing_values_strategy` | enum | `drop_row`, `fill`, `mean`, `skip_feature` | `drop_row` |
| `fill_value` | any | - | 0 |
| `normalization_method` | enum | `z_score`, `min_max`, `robust`, `none` | `z_score` |
| `strict_mode` | bool | - | false |

```yaml
preprocessing:
  missing_values_strategy: "fill"
  fill_value: 0
  normalization_method: "z_score"
  strict_mode: false
```

---

## 📌 Section: `output`

| Field | Type | Values | Default |
|-------|------|--------|---------|
| `format` | enum | `parquet`, `csv`, `pickle` | `parquet` |
| `include_metadata` | bool | - | true |

```yaml
output:
  format: "parquet"
  include_metadata: true
```

---

## ⚠️ Validation Rules

1. **Required sections**: `scenario`, `splitting`
2. **Ratios must sum to 1.0**: `train + val + test = 1.0`
3. **Strategy-specific requirements**:
   - `leave_one_out`: phải có `test_groups`
   - `leave_two_out`: phải có `test_groups` và `val_groups`
   - `imbalanced_train`: phải có `reduce_label`
   - `extreme_novelty`: phải có `novelty_group` và `novelty_label`
4. **Filter dependencies**:
   - `filter_by: by_language` → phải có `languages`
   - `filter_by: by_name` → phải có `repo_names`

---

## 📝 Complete Example

```yaml
# =============================================================================
# Scenario: Stratified Within Language Group (Baseline 70-15-15)
# =============================================================================

scenario:
  name: "baseline_language_stratified"
  description: "Baseline split 70-15-15 stratified by language group"
  version: "1.0"

data_source:
  repositories:
    filter_by: "all"
  builds:
    date_range:
      start: "2024-01-01"
      end: "2024-12-31"
    conclusions: ["success", "failure"]
    exclude_bots: true
  ci_provider: "github_actions"

features:
  dag_features:
    - "build_*"
    - "git_*"
    - "log_*"
    - "repo_*"
    - "history_*"

splitting:
  strategy: "stratified_within_group"
  group_by: "language_group"
  config:
    ratios:
      train: 0.70
      val: 0.15
      test: 0.15
    stratify_by: "outcome"

preprocessing:
  missing_values_strategy: "fill"
  fill_value: 0
  normalization_method: "z_score"

output:
  format: "parquet"
  include_metadata: true
```
