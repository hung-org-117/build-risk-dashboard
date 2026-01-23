"""
Training Script for Dual-Branch Bayesian LSTM Risk Model.

This script matches the inference architecture in:
app/services/risk_model/inference.py and model.py

Architecture:
- Temporal Branch: LSTM + Attention → temporal_head → 3 classes
- Synergy Branch: MLP → synergy_head → 3 classes
- Fusion: 50/50 averaging of both branch logits (during training)

Usage:
    Upload to Google Colab with final_clean.csv.zip
    Run all cells to train and export model artifacts
"""

# %% [markdown]
# # 1. Setup & Imports

# %%
import io
import warnings
import zipfile

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, Dataset

warnings.filterwarnings("ignore")

# Check device
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# %% [markdown]
# # 2. Load Dataset

# %%
# Load from zip
with zipfile.ZipFile("final_clean.csv.zip", "r") as z:
    name = z.namelist()[0]
    with z.open(name) as f:
        df = pd.read_csv(f)

print(f"Dataset shape: {df.shape}")
print(f"\nLabel distribution:")
print(df["risk_label"].value_counts())

# %% [markdown]
# # 3. Feature Definitions (MUST MATCH inference.py)

# %%
# Temporal features for LSTM sequence
TEMPORAL_FEATURES = [
    "history_prev_failed",
    "history_fail_streak",
    "history_fail_rate_10",
    "history_avg_churn_5",
    "history_days_since_prev",
]

# Static/Synergy features for MLP
STATIC_FEATURES = [
    "git_diff_src_churn",
    "git_diff_files_added",
    "git_diff_files_deleted",
    "git_diff_files_modified",
    "git_diff_tests_added",
    "git_diff_tests_deleted",
    "git_diff_src_files",
    "git_diff_doc_files",
    "git_diff_other_files",
    "git_file_commit_density",
    "git_files_modified_ratio",
    "git_change_entropy",
    "git_churn_vs_avg",
    "repo_sloc",
    "repo_age_days",
    "repo_total_commits",
    "repo_test_lines_per_kloc",
    "repo_test_cases_per_kloc",
    "repo_asserts_per_kloc",
    "team_size",
    "author_ownership",
    "author_is_new",
    "author_days_since_commit",
    "log_jobs_count",
    "log_tests_run",
    "log_tests_failed",
    "log_tests_skipped",
    "log_tests_passed",
    "log_test_duration_sec",
    "log_tests_fail_rate",
    "build_duration_sec",
    "build_status_num",
    "build_hour_sin",
    "build_hour_cos",
    "build_hour_risk",
]

# Features requiring log1p transformation
LOG1P_FEATURES = [
    "git_diff_src_churn",
    "git_diff_files_added",
    "git_diff_files_deleted",
    "git_diff_files_modified",
    "git_diff_tests_added",
    "git_diff_tests_deleted",
    "git_diff_src_files",
    "git_diff_doc_files",
    "git_diff_other_files",
    "git_file_commit_density",
    "repo_sloc",
    "repo_age_days",
    "repo_total_commits",
    "log_jobs_count",
    "log_tests_run",
    "log_tests_failed",
    "log_tests_skipped",
    "log_tests_passed",
    "log_test_duration_sec",
    "build_duration_sec",
    "history_days_since_prev",
    "author_days_since_commit",
]

# Model hyperparameters
LSTM_HIDDEN_DIM = 96
LSTM_LAYERS = 2
LSTM_DROPOUT = 0.2
TEMPORAL_DROPOUT = 0.2
SEQ_LEN = 10
MIN_SEQ_LEN = 4
LABEL_SMOOTHING = 0.03

GROUP_COL = "repo_full_name"
TIME_COL = "build_started_at"
PREV_COL = "history_prev_build_id"
LABEL_COL = "risk_label_numeric"

print(f"Temporal features: {len(TEMPORAL_FEATURES)}")
print(f"Static features: {len(STATIC_FEATURES)}")

# %% [markdown]
# # 4. Data Preprocessing

# %%
# Apply log1p transformation
for col in LOG1P_FEATURES:
    if col in df.columns:
        df[col] = np.log1p(df[col].clip(lower=0))

# Create label column if not exists
if "risk_label_numeric" not in df.columns:
    label_map = {"Low": 0, "Medium": 1, "High": 2}
    df["risk_label_numeric"] = df["risk_label"].map(label_map)

# Sort by repository and time
df = df.sort_values([GROUP_COL, TIME_COL]).reset_index(drop=True)

# Train/Val split by timeline (80/20)
repos = df[GROUP_COL].unique()
train_size = int(len(repos) * 0.8)
train_repos = set(repos[:train_size])
val_repos = set(repos[train_size:])

train_df = df[df[GROUP_COL].isin(train_repos)].reset_index(drop=True)
val_df = df[df[GROUP_COL].isin(val_repos)].reset_index(drop=True)

print(f"Train: {len(train_df)} samples, Val: {len(val_df)} samples")

# Fit scalers on training data
scaler_temporal = StandardScaler()
scaler_static = StandardScaler()

scaler_temporal.fit(train_df[TEMPORAL_FEATURES])
scaler_static.fit(train_df[STATIC_FEATURES])

# Transform all data
train_temporal = scaler_temporal.transform(train_df[TEMPORAL_FEATURES])
train_static = scaler_static.transform(train_df[STATIC_FEATURES])
val_temporal = scaler_temporal.transform(val_df[TEMPORAL_FEATURES])
val_static = scaler_static.transform(val_df[STATIC_FEATURES])

print("Scalers fitted and data transformed")

# %% [markdown]
# # 5. Build Sequences


# %%
def build_sequences(
    df, temporal_arr, static_arr, seq_len=SEQ_LEN, min_seq_len=MIN_SEQ_LEN
):
    """Build LSTM sequences grouped by repository."""
    sequences = []
    statics = []
    labels = []
    lengths = []

    for repo in df[GROUP_COL].unique():
        repo_mask = df[GROUP_COL] == repo
        repo_idx = np.where(repo_mask)[0]

        for i, idx in enumerate(repo_idx):
            if i < min_seq_len - 1:
                continue

            # Get history sequence
            start = max(0, i - seq_len + 1)
            seq_indices = repo_idx[start : i + 1]
            seq = temporal_arr[seq_indices]

            # Pad if needed
            actual_len = len(seq)
            if actual_len < seq_len:
                padding = np.zeros((seq_len - actual_len, len(TEMPORAL_FEATURES)))
                seq = np.vstack([seq, padding])
            else:
                seq = seq[-seq_len:]
                actual_len = seq_len

            sequences.append(seq)
            statics.append(static_arr[idx])
            labels.append(df.iloc[idx][LABEL_COL])
            lengths.append(actual_len)

    return (
        np.array(sequences, dtype=np.float32),
        np.array(statics, dtype=np.float32),
        np.array(labels, dtype=np.int64),
        np.array(lengths, dtype=np.int64),
    )


# Build sequences
print("Building training sequences...")
train_seq, train_static_arr, train_labels, train_lengths = build_sequences(
    train_df, train_temporal, train_static
)
print("Building validation sequences...")
val_seq, val_static_arr, val_labels, val_lengths = build_sequences(
    val_df, val_temporal, val_static
)

print(f"Train sequences: {train_seq.shape}")
print(f"Val sequences: {val_seq.shape}")

# %% [markdown]
# # 6. Dataset & DataLoader


# %%
class RiskDataset(Dataset):
    def __init__(self, sequences, statics, labels, lengths):
        self.sequences = torch.tensor(sequences, dtype=torch.float32)
        self.statics = torch.tensor(statics, dtype=torch.float32)
        self.labels = torch.tensor(labels, dtype=torch.long)
        self.lengths = torch.tensor(lengths, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return (
            self.sequences[idx],
            self.statics[idx],
            self.labels[idx],
            self.lengths[idx],
        )


BATCH_SIZE = 256

train_dataset = RiskDataset(train_seq, train_static_arr, train_labels, train_lengths)
val_dataset = RiskDataset(val_seq, val_static_arr, val_labels, val_lengths)

train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)

print(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")

# Compute class weights
class_counts = np.bincount(train_labels)
class_weights = 1.0 / class_counts
class_weights = class_weights / class_weights.sum() * len(class_counts)
print(f"Class weights: {class_weights}")

# %% [markdown]
# # 7. Model Definition (Dual-Head Architecture)


# %%
class BayesianLSTM(nn.Module):
    """LSTM with Attention for temporal features."""

    def __init__(
        self, input_dim, hidden_dim, num_layers=1, dropout=0.0, temporal_dropout=0.0
    ):
        super().__init__()
        self.lstm = nn.LSTM(
            input_dim,
            hidden_dim,
            batch_first=True,
            num_layers=num_layers,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.attn = nn.Linear(hidden_dim, 1)
        self.temporal_dropout = nn.Dropout(temporal_dropout)

    def forward(self, x, lengths):
        lengths_cpu = lengths.to("cpu")
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths_cpu, batch_first=True, enforce_sorted=False
        )
        packed_out, _ = self.lstm(packed)
        h, _ = nn.utils.rnn.pad_packed_sequence(
            packed_out, batch_first=True, total_length=x.size(1)
        )

        max_len = h.size(1)
        mask = torch.arange(max_len, device=lengths.device).unsqueeze(
            0
        ) < lengths.unsqueeze(1)
        attn_scores = self.attn(h).squeeze(-1)
        attn_scores = attn_scores.masked_fill(~mask, -1e9)
        weights = torch.softmax(attn_scores, dim=1).unsqueeze(-1)
        context = (weights * h).sum(dim=1)
        return self.temporal_dropout(context)


class SynergyMLP(nn.Module):
    """Bayesian MLP with MC Dropout for synergy features."""

    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.4),
        )

    def forward(self, x):
        return self.net(x)


class BayesianRiskModel(nn.Module):
    """
    Dual-Branch Bayesian Risk Model with 50/50 Fusion.

    Architecture matches inference.py:
    - Temporal Branch: LSTM → temporal_head → 3 classes
    - Synergy Branch: MLP → synergy_head → 3 classes
    - Fusion: 50/50 averaging of branch logits
    """

    def __init__(
        self,
        temporal_dim,
        static_dim,
        lstm_hidden_dim=LSTM_HIDDEN_DIM,
        lstm_layers=LSTM_LAYERS,
        lstm_dropout=LSTM_DROPOUT,
        temporal_dropout=TEMPORAL_DROPOUT,
    ):
        super().__init__()
        self.lstm_hidden_dim = lstm_hidden_dim

        # Temporal Branch
        self.temporal = BayesianLSTM(
            temporal_dim,
            lstm_hidden_dim,
            num_layers=lstm_layers,
            dropout=lstm_dropout,
            temporal_dropout=temporal_dropout,
        )

        # Synergy Branch
        self.synergy = SynergyMLP(static_dim)

        # Branch-specific classification heads (DUAL HEADS - matches inference.py)
        self.temporal_head = nn.Sequential(
            nn.Linear(lstm_hidden_dim, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 3),
        )
        self.synergy_head = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 3),
        )

    def forward(self, seq, static, lengths):
        """
        Training forward pass with 50/50 averaging.
        """
        logits_temporal, logits_synergy, _, _ = self.forward_branches(
            seq, static, lengths
        )
        # 50/50 averaging for training
        return (logits_temporal + logits_synergy) / 2

    def forward_branches(self, seq, static, lengths):
        """
        Get separate branch outputs for MC Dropout inference.
        """
        t_embed = self.temporal(seq, lengths)
        s_embed = self.synergy(static)

        logits_temporal = self.temporal_head(t_embed)
        logits_synergy = self.synergy_head(s_embed)

        return logits_temporal, logits_synergy, t_embed, s_embed


# Initialize model
model = BayesianRiskModel(
    temporal_dim=len(TEMPORAL_FEATURES),
    static_dim=len(STATIC_FEATURES),
)
model.to(device)
print(f"Model initialized with {sum(p.numel() for p in model.parameters())} parameters")

# %% [markdown]
# # 8. Training Loop

# %%
class_weights_tensor = torch.tensor(class_weights, dtype=torch.float32, device=device)

LR = 1e-3
WEIGHT_DECAY = 1e-4
EPOCHS = 20
EARLY_STOP_PATIENCE = 5
GRAD_CLIP_NORM = 1.0

optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
criterion = nn.CrossEntropyLoss(
    weight=class_weights_tensor, label_smoothing=LABEL_SMOOTHING
)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode="max", factor=0.5, patience=2, min_lr=1e-5
)


def evaluate(model, data_loader, criterion, device, num_classes=3):
    model.eval()
    total_loss = 0.0
    all_labels = []
    all_preds = []

    with torch.no_grad():
        for seq, static, label, lengths in data_loader:
            seq, static, label, lengths = (
                seq.to(device),
                static.to(device),
                label.to(device),
                lengths.to(device),
            )
            logits = model(seq, static, lengths)
            loss = criterion(logits, label)
            total_loss += loss.item()

            preds = torch.argmax(logits, dim=1)
            all_labels.append(label.cpu().numpy())
            all_preds.append(preds.cpu().numpy())

    avg_loss = total_loss / len(data_loader)
    y_true = np.concatenate(all_labels)
    y_pred = np.concatenate(all_preds)
    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro")
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))

    return avg_loss, acc, f1, cm


# Training
best_f1 = 0.0
patience_counter = 0
best_state = None

print("\n" + "=" * 60)
print("Starting Training")
print("=" * 60)

for epoch in range(EPOCHS):
    model.train()
    total_loss = 0.0

    for seq, static, label, lengths in train_loader:
        seq, static, label, lengths = (
            seq.to(device),
            static.to(device),
            label.to(device),
            lengths.to(device),
        )

        optimizer.zero_grad()
        logits = model(seq, static, lengths)
        loss = criterion(logits, label)
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP_NORM)
        optimizer.step()
        total_loss += loss.item()

    train_loss = total_loss / len(train_loader)
    val_loss, val_acc, val_f1, val_cm = evaluate(model, val_loader, criterion, device)

    scheduler.step(val_f1)

    print(
        f"Epoch {epoch+1:2d}/{EPOCHS} | "
        f"Train Loss: {train_loss:.4f} | "
        f"Val Loss: {val_loss:.4f} | "
        f"Val Acc: {val_acc:.4f} | "
        f"Val F1: {val_f1:.4f}"
    )

    if val_f1 > best_f1:
        best_f1 = val_f1
        best_state = model.state_dict().copy()
        patience_counter = 0
        print(f"  → New best F1: {best_f1:.4f}")
    else:
        patience_counter += 1
        if patience_counter >= EARLY_STOP_PATIENCE:
            print(f"\nEarly stopping at epoch {epoch+1}")
            break

print("\n" + "=" * 60)
print(f"Training Complete. Best Val F1: {best_f1:.4f}")
print("=" * 60)

# Load best model
model.load_state_dict(best_state)

# Final evaluation
_, final_acc, final_f1, final_cm = evaluate(model, val_loader, criterion, device)
print(f"\nFinal Validation:")
print(f"  Accuracy: {final_acc:.4f}")
print(f"  F1 Score: {final_f1:.4f}")
print(f"\nConfusion Matrix:")
print(final_cm)

# %% [markdown]
# # 9. Export Artifacts

# %%
import joblib

# Save model checkpoint
checkpoint = {
    "model_state_dict": model.state_dict(),
    "temporal_dim": len(TEMPORAL_FEATURES),
    "static_dim": len(STATIC_FEATURES),
    "temporal_features": TEMPORAL_FEATURES,
    "static_features": STATIC_FEATURES,
    "log1p_features": LOG1P_FEATURES,
    "seq_len": SEQ_LEN,
    "min_seq_len": MIN_SEQ_LEN,
    "lstm_hidden_dim": LSTM_HIDDEN_DIM,
    "lstm_layers": LSTM_LAYERS,
    "lstm_dropout": LSTM_DROPOUT,
    "temporal_dropout": TEMPORAL_DROPOUT,
    "label_smoothing": LABEL_SMOOTHING,
}

torch.save(checkpoint, "bayesian_risk_model.pt")
print("✅ Saved: bayesian_risk_model.pt")

# Save scalers
joblib.dump(scaler_temporal, "scaler_temporal.pkl")
joblib.dump(scaler_static, "scaler_static.pkl")
print("✅ Saved: scaler_temporal.pkl")
print("✅ Saved: scaler_static.pkl")

print("\n" + "=" * 60)
print("ARTIFACTS READY FOR DEPLOYMENT")
print("=" * 60)
print(
    """
Copy these files to: backend/app/services/risk_model/artifacts/
  - bayesian_risk_model.pt
  - scaler_temporal.pkl
  - scaler_static.pkl
"""
)
