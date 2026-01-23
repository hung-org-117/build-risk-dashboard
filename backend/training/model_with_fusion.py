"""
Updated Bayesian LSTM Risk Model with Uncertainty-Weighted Fusion.

Copy this model code into your training notebook to replace the existing
BayesianRiskModel class. This version aligns with the Vu et al. paper:
"Uncertainty-Aware Prediction of Software Defect Risks"

Changes from original:
1. Branch-specific heads for temporal and synergy branches
2. forward_branches() method for separate branch predictions
3. uncertainty_weighted_fusion() static method for inverse variance weighting
4. mc_dropout_predict_with_fusion() helper function
"""

import numpy as np
import torch
import torch.nn as nn

# Hyperparameters (keep same as original)
LSTM_HIDDEN_DIM = 96
LSTM_LAYERS = 2
LSTM_DROPOUT = 0.2
TEMPORAL_DROPOUT = 0.2
LABEL_SMOOTHING = 0.03


class BayesianLSTM(nn.Module):
    """LSTM with Attention for temporal features (same as original)."""

    def __init__(self, input_dim, hidden_dim, num_layers=1, dropout=0.0, temporal_dropout=0.0):
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
        mask = torch.arange(max_len, device=lengths.device).unsqueeze(0) < lengths.unsqueeze(1)
        attn_scores = self.attn(h).squeeze(-1)
        attn_scores = attn_scores.masked_fill(~mask, -1e9)
        weights = torch.softmax(attn_scores, dim=1).unsqueeze(-1)
        context = (weights * h).sum(dim=1)
        return self.temporal_dropout(context)


class SynergyMLP(nn.Module):
    """Bayesian MLP with MC Dropout for cross-artifact synergy features."""

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
    Dual-branch Bayesian model with Uncertainty-Weighted Fusion.

    Architecture (aligned with Vu et al.):
    - Temporal Branch: LSTM + Attention for temporal evolution (X_code, X_test)
    - Synergy Branch: Bayesian MLP for cross-artifact interactions
    - Fusion: Uncertainty-weighted combination of branch predictions
    """

    def __init__(self, temporal_dim, synergy_dim):
        super().__init__()
        self.lstm_hidden_dim = LSTM_HIDDEN_DIM

        # Temporal Branch (Risk Evolution)
        self.temporal = BayesianLSTM(
            temporal_dim,
            LSTM_HIDDEN_DIM,
            num_layers=LSTM_LAYERS,
            dropout=LSTM_DROPOUT,
            temporal_dropout=TEMPORAL_DROPOUT,
        )

        # Synergy Branch (Cross-Artifact Interaction)
        self.synergy = SynergyMLP(synergy_dim)

        # Branch-specific heads for uncertainty estimation
        self.temporal_head = nn.Sequential(
            nn.Linear(LSTM_HIDDEN_DIM, 32),
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

    def forward(self, seq, synergy, lengths):
        """
        Standard forward pass for training.

        Uses equal-weight averaging of branch logits. This method is intended
        for the training loop where a single output is needed for loss computation.
        For inference with uncertainty quantification, use forward_branches()
        combined with uncertainty_weighted_fusion() instead.

        Args:
            seq: Temporal sequence tensor (batch, seq_len, temporal_dim)
            synergy: Synergy features tensor (batch, synergy_dim)
            lengths: Actual sequence lengths for packing

        Returns:
            Averaged logits from both branches (batch, n_classes)
        """
        logits_temporal, logits_synergy, _, _ = self.forward_branches(seq, synergy, lengths)
        return (logits_temporal + logits_synergy) / 2

    def forward_branches(self, seq, synergy, lengths):
        """
        Forward pass with branch-specific outputs for uncertainty-aware inference.

        This method is used during MC Dropout inference to obtain separate
        predictions from Temporal and Synergy branches, enabling uncertainty
        quantification and inverse-variance weighted fusion.

        Args:
            seq: Temporal sequence tensor (batch, seq_len, temporal_dim)
            synergy: Synergy features tensor (batch, synergy_dim)
            lengths: Actual sequence lengths for packing

        Returns:
            Tuple of:
            - logits_temporal: Predictions from Temporal branch (batch, n_classes)
            - logits_synergy: Predictions from Synergy branch (batch, n_classes)
            - t_embed: Temporal embedding (batch, lstm_hidden_dim)
            - s_embed: Synergy embedding (batch, 64)
        """
        t_embed = self.temporal(seq, lengths)
        s_embed = self.synergy(synergy)

        logits_temporal = self.temporal_head(t_embed)
        logits_synergy = self.synergy_head(s_embed)

        return logits_temporal, logits_synergy, t_embed, s_embed

    @staticmethod
    def uncertainty_weighted_fusion(probs_temporal, probs_synergy, eps=1e-8):
        """
        Uncertainty-weighted fusion as per Vu et al. paper.

        Args:
            probs_temporal: (batch, n_samples, n_classes)
            probs_synergy: (batch, n_samples, n_classes)

        Returns:
            fused_prob: (batch, n_classes)
            w_temporal: weight for temporal branch
            w_synergy: weight for synergy branch
        """
        # Variance across MC samples
        var_temporal = probs_temporal.var(dim=1).mean(dim=1, keepdim=True)
        var_synergy = probs_synergy.var(dim=1).mean(dim=1, keepdim=True)

        # Confidence = inverse variance
        conf_temporal = 1.0 / (var_temporal + eps)
        conf_synergy = 1.0 / (var_synergy + eps)

        # Normalized weights
        total_conf = conf_temporal + conf_synergy
        w_temporal = conf_temporal / total_conf
        w_synergy = conf_synergy / total_conf

        # Mean probabilities
        mean_prob_temporal = probs_temporal.mean(dim=1)
        mean_prob_synergy = probs_synergy.mean(dim=1)

        # Weighted fusion
        fused_prob = w_temporal * mean_prob_temporal + w_synergy * mean_prob_synergy

        return fused_prob, w_temporal.squeeze(), w_synergy.squeeze()


# ============================================================================
# MC Dropout Inference Functions
# ============================================================================


def mc_dropout_predict(model, seq, static, lengths, n_samples=30):
    """
    Standard MC Dropout inference (original method).
    """
    model.train()  # Keep dropout enabled

    probs = []
    for _ in range(n_samples):
        logits = model(seq, static, lengths)
        probs.append(torch.softmax(logits, dim=1).detach().cpu().numpy())

    probs = np.stack(probs)
    mean_prob = probs.mean(axis=0)
    uncertainty = probs.var(axis=0).mean(axis=1)

    return mean_prob, uncertainty


def mc_dropout_predict_with_fusion(model, seq, static, lengths, n_samples=30):
    """
    MC Dropout with Uncertainty-Weighted Fusion (aligned with Vu et al.).

    Returns:
        mean_prob: fused probability distribution (batch, n_classes)
        uncertainty: combined uncertainty score
        fusion_info: dict with branch weights and uncertainties
    """
    model.train()

    probs_temporal_list = []
    probs_synergy_list = []

    with torch.no_grad():
        for _ in range(n_samples):
            logits_t, logits_s, _, _ = model.forward_branches(seq, static, lengths)
            prob_t = torch.softmax(logits_t, dim=1)
            prob_s = torch.softmax(logits_s, dim=1)
            probs_temporal_list.append(prob_t)
            probs_synergy_list.append(prob_s)

    # Stack: (batch, n_samples, n_classes)
    probs_temporal = torch.stack(probs_temporal_list, dim=1)
    probs_synergy = torch.stack(probs_synergy_list, dim=1)

    # Uncertainty-weighted fusion
    fused_prob, w_temporal, w_synergy = BayesianRiskModel.uncertainty_weighted_fusion(
        probs_temporal, probs_synergy
    )

    # Compute uncertainty
    var_temporal = probs_temporal.var(dim=1).mean().item()
    var_synergy = probs_synergy.var(dim=1).mean().item()
    uncertainty = (var_temporal + var_synergy) / 2

    fusion_info = {
        "w_temporal": w_temporal.cpu().numpy()
        if isinstance(w_temporal, torch.Tensor)
        else w_temporal,
        "w_synergy": w_synergy.cpu().numpy() if isinstance(w_synergy, torch.Tensor) else w_synergy,
        "var_temporal": var_temporal,
        "var_synergy": var_synergy,
    }

    return fused_prob.cpu().numpy(), uncertainty, fusion_info


# ============================================================================
# Usage Example (for Colab notebook)
# ============================================================================
"""
# After training loop, to test with fusion:

print("Testing Uncertainty-Weighted Fusion...")
model.eval()

with torch.no_grad():
    seq, static, label, lengths = next(iter(val_loader))
    seq = seq.to(device)
    static = static.to(device)
    lengths = lengths.to(device)

    # Standard MC Dropout
    mean_prob_std, uncertainty_std = mc_dropout_predict(
        model, seq, static, lengths, n_samples=30
    )

    # With Uncertainty-Weighted Fusion
    mean_prob_fused, uncertainty_fused, fusion_info = mc_dropout_predict_with_fusion(
        model, seq, static, lengths, n_samples=30
    )

    print(f"Standard MC Dropout - Uncertainty: {uncertainty_std[:5]}")
    print(f"Fused MC Dropout - Uncertainty: {uncertainty_fused:.4f}")
    print(f"Fusion Weights - Temporal: {fusion_info['w_temporal'][:5]}")
    print(f"Fusion Weights - Synergy: {fusion_info['w_synergy'][:5]}")
"""
