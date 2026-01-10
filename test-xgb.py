"""
XGBoost Test Script - Hierarchical Stage Evaluation (EXTENDED METRICS)
======================================================================
Test XGBoost models với 4 stages giống LSTM test script.
Output format đồng nhất để so sánh 2 models.

Metrics bổ sung:
- Recall @ Precision = 70%, 80%, 90%
- Precision @ Recall = 50%, 60%, 70%
"""

import os
import sys
import numpy as np
import pandas as pd
import json
import pickle
import gc
from xgboost import XGBClassifier

from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
    precision_recall_curve, precision_score, recall_score,
    f1_score, classification_report
)

# ==========================================
# 0. CẤU HÌNH & LOGGING
# ==========================================
OUTPUT_ROOT_DIR = "results_xgb_hierarchical"
LOG_FILENAME = "execution_log_xgb.txt"

def log_print(msg):
    print(msg)
    with open(LOG_FILENAME, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def log_memory():
    """Log RAM usage hiện tại"""
    try:
        import psutil
        ram_gb = psutil.Process().memory_info().rss / 1e9
        log_print(f"   [RAM] {ram_gb:.2f} GB")
    except ImportError:
        pass

# ==========================================
# 1. CONFIGURATION
# ==========================================
DEFAULT_TEST_DATA = "test_100k_normalized.csv"
DEFAULT_MODEL_ROOT = "models_xgb_number"
EXPERIMENTS = [1, 2, 3, 4, 5]
TARGET_PRECISION = 0.8
LABEL_COL = 'y_build_failed'

# ==========================================
# 2. FEATURE DEFINITIONS
# ==========================================
FEATURES_TEAM = {
    'a7_num_distinct_authors', 'a7_num_devops_contributors', 'a7_pct_devops_developers',
    'a7_pct_major_contributors', 'a7_contributor_count', 'is_missing_a7_num_distinct_authors',
    'is_missing_a7_num_devops_contributors', 'a7_pct_top_devops_contributor', 'a7_pct_minor_contributors',
    'a8_same_committer', 'a8_committer_avg_exp', 'is_missing_a8_same_committer', 'is_missing_a8_committer_avg_exp',
    'a9_number_of_devops_authors', 'a9_repo_skewness', 'a9_devops_skewness', 'a9_total_chronological_ownership',
    'is_missing_a9_number_of_devops_authors', 'is_missing_a9_repo_skewness', 'a9_num_author_intersection'
}

FEATURES_CODE = {
    'a1_git_num_all_built_commits', 'a1_commit_count', 'a1_commits_per_build', 'a1_devops_commits_per_build',
    'a1_number_of_devops_commits', 'a1_total_devops_commits', 'is_missing_a1_total_devops_commits',
    'a2_git_diff_src_churn', 'a2_gh_diff_files_added', 'a2_gh_diff_files_removed',
    'a3_num_of_devops_files', 'a3_devops_change_size', 'a3_devops_lines_changed_per_build',
    'is_missing_a3_num_of_devops_files', 'is_missing_a3_devops_change_size', 'is_missing_a3_devops_lines_changed_per_build'
}

FEATURES_TEST = {
    'a4_prev_build_failed', 'a4_recent_failure_rate_k10', 'a4_build_duration_sec', 'a4_num_jobs',
    'is_missing_a4_build_duration_sec', 'is_missing_a4_num_jobs',
    'a5_expected_success_rate', 'is_proxy_a5_expected_success_rate',
    'a6_committer_fail_history', 'a6_num_tests_failed', 'a6_failed_devops_build_rate',
    'is_missing_a6_num_tests_failed', 'is_missing_a6_committer_fail_history', 'is_proxy_a6_failed_devops_build_rate'
}

FEATURES_MONITOR = {
    'a10_stars', 'a10_forks', 'a10_project_maturity', 'a10_issue_comments',
    'is_missing_a10_stars', 'is_missing_a10_forks', 'is_proxy_a10_project_maturity', 'a10_commit_comments',
    'a12_number_of_devops_builds', 'is_missing_a12_number_of_devops_builds',
    'a12_day_week_sin', 'a12_day_week_cos', 'a13_is_pr'
}

STAGES_CONFIG = {
    1: {"name": "Stage_1_Plan", "active": ["team"]},
    2: {"name": "Stage_2_Code", "active": ["team", "code"]},
    3: {"name": "Stage_3_Build", "active": ["team", "code", "test"]},
    4: {"name": "Stage_4_Monitor", "active": ["team", "code", "test", "monitor"]},
}

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_cols_to_zero(feature_list, active_streams):
    """Xác định features cần mask (gán = 0) dựa trên stage active."""
    cols_to_zero = []
    for feat in feature_list:
        is_active = False
        if 'team' in active_streams and feat in FEATURES_TEAM: is_active = True
        elif 'code' in active_streams and feat in FEATURES_CODE: is_active = True
        elif 'test' in active_streams and feat in FEATURES_TEST: is_active = True
        elif 'monitor' in active_streams and feat in FEATURES_MONITOR: is_active = True
        if not is_active:
            cols_to_zero.append(feat)
    return cols_to_zero


def find_threshold_at_precision(y_true, y_prob, target_precision):
    """Tìm threshold để đạt target precision."""
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    precisions = precisions[:-1]
    valid_indices = np.where(precisions >= target_precision)[0]
    return thresholds[valid_indices[0]] if len(valid_indices) > 0 else 0.5


def find_threshold_at_recall(y_true, y_prob, target_recall):
    """Tìm threshold để đạt target recall."""
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_prob)
    recalls = recalls[:-1]
    valid_indices = np.where(recalls >= target_recall)[0]
    if len(valid_indices) > 0:
        return thresholds[valid_indices[-1]]
    return 0.5


def calculate_kpis(y_true, y_prob, fixed_threshold=0.5):
    """
    Tính tất cả metrics - MỞ RỘNG cho bộ tiêu chí đánh giá.
    
    Returns dict với:
    - Base metrics: PR_AUC, ROC_AUC, Brier
    - Recall@Precision: P70, P80, P90
    - Precision@Recall: R50, R60, R70
    """
    y_pred_fixed = (y_prob >= fixed_threshold).astype(int)
    
    # Base metrics
    metrics = {
        "PR_AUC": average_precision_score(y_true, y_prob),
        "ROC_AUC": roc_auc_score(y_true, y_prob),
        "Brier": brier_score_loss(y_true, y_prob),
        "Threshold_Saved": fixed_threshold,
        "F1_Saved": f1_score(y_true, y_pred_fixed, zero_division=0),
    }
    
    # Recall @ Precision = 70%, 80%, 90%
    for target_p in [0.70, 0.80, 0.90]:
        key_suffix = f"P{int(target_p*100)}"
        thresh = find_threshold_at_precision(y_true, y_prob, target_p)
        y_pred = (y_prob >= thresh).astype(int)
        metrics[f"Threshold_{key_suffix}"] = thresh
        metrics[f"Precision_at_{key_suffix}"] = precision_score(y_true, y_pred, zero_division=0)
        metrics[f"Recall_at_{key_suffix}"] = recall_score(y_true, y_pred, zero_division=0)
    
    # Precision @ Recall = 50%, 60%, 70%
    for target_r in [0.50, 0.60, 0.70]:
        key_suffix = f"R{int(target_r*100)}"
        thresh = find_threshold_at_recall(y_true, y_prob, target_r)
        y_pred = (y_prob >= thresh).astype(int)
        metrics[f"Threshold_{key_suffix}"] = thresh
        metrics[f"Precision_at_{key_suffix}"] = precision_score(y_true, y_pred, zero_division=0)
        metrics[f"Recall_at_{key_suffix}"] = recall_score(y_true, y_pred, zero_division=0)
    
    # Classification report at P80 (default target)
    thresh_p80 = metrics["Threshold_P80"]
    y_pred_p80 = (y_prob >= thresh_p80).astype(int)
    metrics["Report_Str"] = classification_report(y_true, y_pred_p80, digits=4)
    
    return metrics


# ==========================================
# 4. MAIN EXECUTION
# ==========================================
def run_evaluation():
    gc.collect()
    open(LOG_FILENAME, "w").close()
    
    log_print("=" * 60)
    log_print("=== XGBoost TEST - HIERARCHICAL STAGES (EXTENDED METRICS) ===")
    log_print("=" * 60)
    log_memory()
    
    if not os.path.exists(DEFAULT_TEST_DATA):
        log_print(f"❌ Error: File data {DEFAULT_TEST_DATA} không tồn tại!")
        return
    
    with open(DEFAULT_TEST_DATA, 'r') as f:
        n_rows = sum(1 for _ in f) - 1
    log_print(f"📂 Data has {n_rows} rows.")
    
    final_summary_list = []
    
    for exp_id in EXPERIMENTS:
        gc.collect()
        
        exp_name = f"xgb_exp{exp_id}"
        model_dir = os.path.join(DEFAULT_MODEL_ROOT, exp_name)
        
        log_print(f"\n{'='*60}")
        log_print(f"🚀 PROCESSING MODEL: {exp_name.upper()}")
        log_memory()
        
        meta_path = os.path.join(model_dir, "meta.json")
        if not os.path.exists(meta_path):
            log_print(f"⚠️  Skipping {exp_name}: meta.json not found.")
            continue
        
        calibrated_model = None
        scaler = None
        meta = None
        
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            
            with open(os.path.join(model_dir, "scaler.pkl"), "rb") as f:
                scaler = pickle.load(f)
            
            with open(os.path.join(model_dir, "calibrated_model.pkl"), "rb") as f:
                calibrated_model = pickle.load(f)
            
            feature_names = meta.get("feature_names", [])
            optimal_threshold = meta.get("optimal_threshold", 0.5)
            
            log_print(f"✅ Model loaded. Features: {len(feature_names)}")
            
        except Exception as e:
            log_print(f"❌ Error loading model: {e}")
            if calibrated_model is not None: del calibrated_model
            if scaler is not None: del scaler
            gc.collect()
            continue
        
        for stage_id, config in STAGES_CONFIG.items():
            stage_name = config["name"]
            active_streams = config["active"]
            
            current_output_dir = os.path.join(OUTPUT_ROOT_DIR, stage_name, exp_name)
            os.makedirs(current_output_dir, exist_ok=True)
            log_print(f"   ► Stage: {stage_name}")
            
            df_test = pd.read_csv(DEFAULT_TEST_DATA)
            
            missing_features = [f for f in feature_names if f not in df_test.columns]
            if missing_features:
                log_print(f"⚠️  Missing features: {missing_features[:5]}...")
                available_features = [f for f in feature_names if f in df_test.columns]
            else:
                available_features = feature_names
            
            X_test = df_test[available_features].copy()
            X_test_scaled = scaler.transform(X_test)
            X_test_scaled = pd.DataFrame(X_test_scaled, columns=available_features)
            
            cols_to_zero = get_cols_to_zero(available_features, active_streams)
            if cols_to_zero:
                for col in cols_to_zero:
                    if col in X_test_scaled.columns:
                        X_test_scaled[col] = 0.0
            
            y_true = df_test[LABEL_COL].values
            X_test_np = X_test_scaled.values.astype(np.float32)
            
            del df_test, X_test, X_test_scaled
            gc.collect()
            
            if len(y_true) == 0:
                log_print("⚠️  No samples. Skipping.")
                continue
            
            y_prob = calibrated_model.predict_proba(X_test_np)[:, 1]
            
            del X_test_np
            gc.collect()
            
            # METRICS - EXTENDED
            metrics = calculate_kpis(y_true, y_prob, fixed_threshold=optimal_threshold)
            
            # Save raw predictions
            pd.DataFrame({
                "True_Label": y_true,
                "Probability": y_prob
            }).to_csv(os.path.join(current_output_dir, "raw_predictions.csv"), index=False)
            
            # Save report - EXTENDED FORMAT
            report_file = os.path.join(current_output_dir, "metrics_report.txt")
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(f"Experiment: {exp_name}\n")
                f.write(f"Stage: {stage_name} (Active: {active_streams})\n")
                f.write("=" * 50 + "\n")
                f.write(f"PR-AUC:           {metrics['PR_AUC']:.4f}\n")
                f.write(f"ROC-AUC:          {metrics['ROC_AUC']:.4f}\n")
                f.write(f"Brier Score:      {metrics['Brier']:.4f}\n")
                f.write("-" * 50 + "\n")
                f.write("[Saved Threshold Metrics]\n")
                f.write(f"Threshold Saved:  {metrics['Threshold_Saved']:.4f}\n")
                f.write(f"F1 Saved:         {metrics['F1_Saved']:.4f}\n")
                f.write("-" * 50 + "\n")
                f.write("[Recall @ Fixed Precision]\n")
                for p in [70, 80, 90]:
                    f.write(f"  @Precision={p}%: Threshold={metrics[f'Threshold_P{p}']:.4f}, "
                            f"Precision={metrics[f'Precision_at_P{p}']:.4f}, "
                            f"Recall={metrics[f'Recall_at_P{p}']:.4f}\n")
                f.write("-" * 50 + "\n")
                f.write("[Precision @ Fixed Recall]\n")
                for r in [50, 60, 70]:
                    f.write(f"  @Recall={r}%: Threshold={metrics[f'Threshold_R{r}']:.4f}, "
                            f"Precision={metrics[f'Precision_at_R{r}']:.4f}, "
                            f"Recall={metrics[f'Recall_at_R{r}']:.4f}\n")
                f.write("\n=== Classification Report (at P80) ===\n")
                f.write(metrics['Report_Str'])
            
            # Summary - EXTENDED
            res_dict = {
                "Experiment": exp_name,
                "Stage": stage_name,
                "PR_AUC": metrics['PR_AUC'],
                "ROC_AUC": metrics['ROC_AUC'],
                "Brier": metrics['Brier'],
                # Recall @ Precision
                "Recall_at_P70": metrics['Recall_at_P70'],
                "Recall_at_P80": metrics['Recall_at_P80'],
                "Recall_at_P90": metrics['Recall_at_P90'],
                # Precision @ Recall
                "Precision_at_R50": metrics['Precision_at_R50'],
                "Precision_at_R60": metrics['Precision_at_R60'],
                "Precision_at_R70": metrics['Precision_at_R70'],
                # Thresholds
                "Threshold_P80": metrics['Threshold_P80'],
            }
            final_summary_list.append(res_dict)
            
            log_print(f"      -> PR-AUC: {metrics['PR_AUC']:.4f}, "
                      f"Recall@P80: {metrics['Recall_at_P80']:.4f}, "
                      f"Prec@R60: {metrics['Precision_at_R60']:.4f}")
            
            del y_true, y_prob
            gc.collect()
        
        # Cleanup model
        if calibrated_model is not None: del calibrated_model
        if scaler is not None: del scaler
        if meta is not None: del meta
        gc.collect()
        
        log_print(f"   [CLEANUP] Released model {exp_name}")
        log_memory()
    
    # Save global summary
    if final_summary_list:
        final_df = pd.DataFrame(final_summary_list)
        final_df = final_df.sort_values(by=["Stage", "Experiment"])
        summary_path = os.path.join(OUTPUT_ROOT_DIR, "final_summary_all.csv")
        os.makedirs(OUTPUT_ROOT_DIR, exist_ok=True)
        final_df.to_csv(summary_path, index=False)
        
        log_print(f"\n{'='*60}")
        log_print(f"✅ Đã lưu bảng tổng hợp: {summary_path}")
        log_print(f"{'='*60}")
        print("\n" + final_df.to_string(index=False))
    else:
        log_print("\n⚠️ Không có kết quả nào được tạo.")


if __name__ == "__main__":
    run_evaluation()
