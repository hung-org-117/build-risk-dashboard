"""
Bayesian LSTM Risk Model Definitions
"""

import torch
import torch.nn as nn

LSTM_HIDDEN_DIM = 96
LSTM_LAYERS = 2
LSTM_DROPOUT = 0.2
TEMPORAL_DROPOUT = 0.2
SEQ_LEN = 10
MIN_SEQ_LEN = 1


class BayesianLSTM(nn.Module):
    """
    LSTM layer with attention for temporal features.

    Supports packed sequences for variable-length inputs.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int,
        num_layers: int = 1,
        dropout: float = 0.0,
        temporal_dropout: float = 0.0,
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

    def forward(self, x, lengths=None):
        if lengths is not None:
            # Use packed sequence for variable-length inputs
            lengths_cpu = lengths.to("cpu")
            packed = nn.utils.rnn.pack_padded_sequence(
                x,
                lengths_cpu,
                batch_first=True,
                enforce_sorted=False,
            )
            packed_out, _ = self.lstm(packed)
            h, _ = nn.utils.rnn.pad_packed_sequence(
                packed_out,
                batch_first=True,
                total_length=x.size(1),
            )

            # Mask attention for padding
            max_len = h.size(1)
            mask = torch.arange(max_len, device=lengths.device).unsqueeze(0) < lengths.unsqueeze(1)
            attn_scores = self.attn(h).squeeze(-1)
            attn_scores = attn_scores.masked_fill(~mask, -1e9)
            weights = torch.softmax(attn_scores, dim=1).unsqueeze(-1)
            context = (weights * h).sum(dim=1)
        else:
            # Simple forward without packed sequence
            h, _ = self.lstm(x)
            weights = torch.softmax(self.attn(h), dim=1)
            context = (weights * h).sum(dim=1)

        return self.temporal_dropout(context)


class SynergyMLP(nn.Module):
    """Bayesian MLP for cross-artifact synergy features with MC Dropout."""

    def __init__(self, input_dim: int):
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
    Dual-branch Bayesian model for build risk prediction.

    Architecture:
    - Temporal branch: LSTM with attention for sequence features (X_code, X_test evolution)
    - Synergy branch: Bayesian MLP for cross-artifact interactions (all 4 streams)
    - Uncertainty-weighted Fusion: Combines branches using inverse variance weighting
    """

    def __init__(
        self,
        temporal_dim: int,
        static_dim: int,
        lstm_hidden_dim: int = LSTM_HIDDEN_DIM,
        lstm_layers: int = LSTM_LAYERS,
        lstm_dropout: float = LSTM_DROPOUT,
        temporal_dropout: float = TEMPORAL_DROPOUT,
    ):
        super().__init__()
        self.lstm_hidden_dim = lstm_hidden_dim

        # Temporal Branch (Risk Evolution)
        self.temporal = BayesianLSTM(
            temporal_dim,
            lstm_hidden_dim,
            num_layers=lstm_layers,
            dropout=lstm_dropout,
            temporal_dropout=temporal_dropout,
        )

        # Synergy Branch (Cross-Artifact Interaction)
        self.synergy = SynergyMLP(static_dim)

        # Branch-specific heads for uncertainty estimation
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

    def forward(self, seq, static, lengths=None):
        """
        Standard forward pass for training.

        Uses equal-weight averaging of branch logits. This method is intended
        for the training loop where a single output is needed for loss computation.
        For inference with uncertainty quantification, use forward_branches()
        combined with uncertainty_weighted_fusion() instead.

        Args:
            seq: Temporal sequence tensor (batch, seq_len, temporal_dim)
            static: Synergy features tensor (batch, static_dim)
            lengths: Actual sequence lengths for packing

        Returns:
            Averaged logits from both branches (batch, n_classes)
        """
        logits_temporal, logits_synergy, _, _ = self.forward_branches(seq, static, lengths)
        return (logits_temporal + logits_synergy) / 2

    def forward_branches(self, seq, static, lengths=None):
        """
        Forward pass with branch-specific outputs for uncertainty-aware inference.

        This method is used during MC Dropout inference to obtain separate
        predictions from Temporal and Synergy branches, enabling uncertainty
        quantification and inverse-variance weighted fusion.

        Args:
            seq: Temporal sequence tensor (batch, seq_len, temporal_dim)
            static: Synergy features tensor (batch, static_dim)
            lengths: Actual sequence lengths for packing

        Returns:
            Tuple of:
            - logits_temporal: Predictions from Temporal branch (batch, n_classes)
            - logits_synergy: Predictions from Synergy branch (batch, n_classes)
            - t_embed: Temporal embedding (batch, lstm_hidden_dim)
            - s_embed: Synergy embedding (batch, 64)
        """
        t_embed = self.temporal(seq, lengths)
        s_embed = self.synergy(static)

        # Branch-specific predictions
        logits_temporal = self.temporal_head(t_embed)
        logits_synergy = self.synergy_head(s_embed)

        return logits_temporal, logits_synergy, t_embed, s_embed

    @staticmethod
    def uncertainty_weighted_fusion(
        probs_temporal: torch.Tensor,
        probs_synergy: torch.Tensor,
        eps: float = 1e-8,
    ) -> torch.Tensor:
        """
        Uncertainty-weighted fusion of branch predictions.

        Uses inverse variance weighting to combine predictions from Temporal and Synergy branches.
        - Compute confidence as inverse of predictive variance
        - Weight each branch by its normalized confidence

        Args:
            probs_temporal: (batch, n_samples, n_classes) probability samples from temporal branch
            probs_synergy: (batch, n_samples, n_classes) probability samples from synergy branch
            eps: Small value to avoid division by zero

        Returns:
            Fused probability distribution (batch, n_classes)
        """
        var_temporal = probs_temporal.var(dim=1).mean(dim=1, keepdim=True)
        var_synergy = probs_synergy.var(dim=1).mean(dim=1, keepdim=True)

        conf_temporal = 1.0 / (var_temporal + eps)
        conf_synergy = 1.0 / (var_synergy + eps)

        # Normalize weights
        total_conf = conf_temporal + conf_synergy
        w_temporal = conf_temporal / total_conf
        w_synergy = conf_synergy / total_conf

        mean_prob_temporal = probs_temporal.mean(dim=1)
        mean_prob_synergy = probs_synergy.mean(dim=1)

        fused_prob = w_temporal * mean_prob_temporal + w_synergy * mean_prob_synergy

        return fused_prob, w_temporal.squeeze(), w_synergy.squeeze()
