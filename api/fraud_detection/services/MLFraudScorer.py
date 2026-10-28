# =============================================================================
# fraud_detection/services/MLFraudScorer.py
# =============================================================================
"""
ML-Based Fraud Scorer with Explainability.

Implements an ensemble fraud scoring model using:
  - Isolation Forest (unsupervised anomaly detection — no labels needed)
  - Statistical threshold rules (high precision, auditable)
  - Feature importance / SHAP-style contribution scores (explainability)
  - Model drift detection (alerts when score distributions shift)

Why Isolation Forest?
  It is the industry workhorse for unsupervised fraud detection because
  fraud is rare and labels are delayed. iForest flags statistical outliers
  without needing any labelled examples. Combined with rule-based thresholds
  it provides both recall (catch new patterns) and precision (known patterns).

Explainability:
  Each score comes with a feature-contribution breakdown so compliance teams
  can explain every decision (required by EU AI Act, SR 11-7, GDPR Art 22).
"""

from __future__ import annotations

import logging
import json
import hashlib
import statistics
from datetime import datetime, timezone as tz, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Feature names — order must be consistent with _build_feature_vector()
FEATURE_NAMES = [
    "transaction_velocity_1h",
    "transaction_velocity_24h",
    "login_velocity_1h",
    "risk_score_current",
    "device_age_days",
    "account_age_days",
    "ip_reputation_score",
    "geo_velocity_score",
    "hour_of_day_risk",
    "amount_zscore",
    "failed_login_count_24h",
    "device_shared_count",
    "ip_shared_count",
    "behavioral_risk_score",
    "sanctions_hit",
]

# Weights for rule-based score component (must sum to ≤ 100)
RULE_WEIGHTS: Dict[str, float] = {
    "transaction_velocity_1h":  0.15,
    "transaction_velocity_24h": 0.10,
    "login_velocity_1h":        0.10,
    "risk_score_current":       0.20,
    "device_age_days":          0.05,
    "account_age_days":         0.05,
    "ip_reputation_score":      0.10,
    "geo_velocity_score":       0.10,
    "hour_of_day_risk":         0.05,
    "amount_zscore":            0.05,
    "failed_login_count_24h":   0.05,
    "device_shared_count":      0.03,
    "ip_shared_count":          0.03,
    "behavioral_risk_score":    0.08,
    "sanctions_hit":            0.20,
}


class FeatureVector:
    """Holds a single observation's features as both dict and numpy array."""

    def __init__(self, features: Dict[str, float]):
        self.features = features
        self.array    = np.array(
            [features.get(name, 0.0) for name in FEATURE_NAMES],
            dtype=np.float64,
        )

    def __repr__(self) -> str:
        return f"FeatureVector({self.features})"


class FraudExplanation:
    """Human-readable explanation of a fraud score."""

    def __init__(
        self,
        score:         int,
        contributions: Dict[str, float],
        top_reasons:   List[str],
        model_version: str,
    ):
        self.score         = score
        self.contributions = contributions   # feature -> contribution to score (0-100)
        self.top_reasons   = top_reasons     # ranked human-readable reasons
        self.model_version = model_version
        self.generated_at  = datetime.now(tz.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score":         self.score,
            "contributions": self.contributions,
            "top_reasons":   self.top_reasons,
            "model_version": self.model_version,
            "generated_at":  self.generated_at,
        }


class IsolationForestScorer:
    """
    Pure-numpy Isolation Forest implementation.

    A lightweight, dependency-free iForest that scores anomalies without
    scikit-learn. In production you would swap this for
    sklearn.ensemble.IsolationForest trained on historical data.
    """

    def __init__(self, n_trees: int = 100, sample_size: int = 256, seed: int = 42):
        self.n_trees     = n_trees
        self.sample_size = sample_size
        self.rng         = np.random.default_rng(seed)
        self._trees:  List[Dict] = []
        self._fitted: bool       = False

    def fit(self, X: np.ndarray) -> "IsolationForestScorer":
        """Fit iForest to a 2D feature matrix X (n_samples × n_features)."""
        self._trees   = []
        self._fitted  = True
        n_samples, _ = X.shape

        for _ in range(self.n_trees):
            sample_idx = self.rng.choice(n_samples, size=min(self.sample_size, n_samples), replace=False)
            sample     = X[sample_idx]
            tree       = self._build_tree(sample, depth=0, max_depth=int(np.ceil(np.log2(max(self.sample_size, 2)))))
            self._trees.append(tree)

        return self

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """
        Return anomaly scores in [0, 1].
        Higher = more anomalous = more likely fraud.
        """
        if not self._fitted or not self._trees:
            # Fallback: return 0.5 (neutral) if not fitted
            return np.full(len(X), 0.5)

        path_lengths = np.array([
            [self._path_length(tree, x) for tree in self._trees]
            for x in X
        ])
        avg_paths = path_lengths.mean(axis=1)

        # Normalise to [0, 1] using expected path length formula
        c = self._expected_path_length(self.sample_size)
        scores = 2 ** (-avg_paths / max(c, 1e-9))
        return np.clip(scores, 0.0, 1.0)

    def _build_tree(self, X: np.ndarray, depth: int, max_depth: int) -> Dict:
        if len(X) <= 1 or depth >= max_depth:
            return {"type": "leaf", "size": len(X)}

        n_features = X.shape[1]
        feat_idx   = int(self.rng.integers(0, n_features))
        col        = X[:, feat_idx]
        col_min, col_max = col.min(), col.max()

        if col_min == col_max:
            return {"type": "leaf", "size": len(X)}

        split = float(self.rng.uniform(col_min, col_max))
        left  = X[col <= split]
        right = X[col > split]

        return {
            "type":     "split",
            "feature":  feat_idx,
            "split":    split,
            "left":     self._build_tree(left,  depth + 1, max_depth),
            "right":    self._build_tree(right, depth + 1, max_depth),
        }

    def _path_length(self, node: Dict, x: np.ndarray, depth: int = 0) -> float:
        if node["type"] == "leaf":
            return depth + self._expected_path_length(node["size"])
        feat  = node["feature"]
        if x[feat] <= node["split"]:
            return self._path_length(node["left"],  x, depth + 1)
        return self._path_length(node["right"], x, depth + 1)

    @staticmethod
    def _expected_path_length(n: int) -> float:
        """Expected path length for a BST with n nodes."""
        if n <= 1:
            return 0.0
        H = np.log(n - 1) + 0.5772156649   # Euler–Mascheroni constant
        return 2 * H - (2 * (n - 1) / n)


class ModelDriftDetector:
    """Detects distributional drift in fraud score outputs."""

    CACHE_KEY   = "ml_scorer_score_history"
    HISTORY_LEN = 1000

    def record_score(self, score: int) -> None:
        try:
            history: List[int] = cache.get(self.CACHE_KEY) or []
            history.append(score)
            if len(history) > self.HISTORY_LEN:
                history = history[-self.HISTORY_LEN:]
            cache.set(self.CACHE_KEY, history, timeout=86400 * 7)
        except Exception as e:
            logger.warning("DriftDetector record error: %s", e)

    def detect_drift(self) -> Dict[str, Any]:
        try:
            history: List[int] = cache.get(self.CACHE_KEY) or []
            if len(history) < 100:
                return {"drift_detected": False, "reason": "insufficient_history"}

            recent  = history[-50:]
            older   = history[-200:-50] if len(history) >= 200 else history[:-50]
            if not older:
                return {"drift_detected": False, "reason": "insufficient_baseline"}

            recent_mean  = statistics.mean(recent)
            baseline_mean = statistics.mean(older)
            drift_pct    = abs(recent_mean - baseline_mean) / max(baseline_mean, 1) * 100

            # KS test for distributional drift
            ks_stat, ks_p = scipy_stats.ks_2samp(recent, older)
            drift_detected = drift_pct > 20 or ks_p < 0.05

            return {
                "drift_detected":   drift_detected,
                "recent_mean":      round(recent_mean, 2),
                "baseline_mean":    round(baseline_mean, 2),
                "drift_pct":        round(drift_pct, 2),
                "ks_statistic":     round(float(ks_stat), 4),
                "ks_p_value":       round(float(ks_p), 4),
                "history_size":     len(history),
            }
        except Exception as e:
            logger.error("DriftDetector error: %s", e)
            return {"drift_detected": False, "error": str(e)}


class MLFraudScorer:
    """
    Ensemble ML fraud scorer combining:
      1. Rule-based weighted score (fast, explainable)
      2. Isolation Forest anomaly score (unsupervised, catches novel patterns)
      3. Feature-contribution explainability (regulatory compliance)
      4. Model drift monitoring

    Usage:
        scorer = MLFraudScorer()
        result = scorer.score(features)
        # result.score → 0–100
        # result.explanation.top_reasons → ['high_velocity', ...]
    """

    MODEL_VERSION = "1.0.0"
    CACHE_KEY_MODEL = "ml_fraud_scorer_iforest"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        fraud_cfg = getattr(settings, "FRAUD_DETECTION", {})
        self.enabled          = cfg.get("enabled", fraud_cfg.get("ML_SCORER_ENABLED", True))
        self.if_weight        = cfg.get("iforest_weight", 0.35)   # 35% iForest
        self.rule_weight      = 1.0 - self.if_weight              # 65% rule-based
        self.iforest          = self._load_or_init_iforest()
        self.drift_detector   = ModelDriftDetector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, features: Dict[str, float]) -> FraudExplanation:
        """
        Compute ensemble fraud score and explanation for a feature dict.

        Returns FraudExplanation with score 0–100 and top reasons.
        """
        fv = FeatureVector(features)

        # 1. Rule-based component
        rule_score, contributions = self._rule_score(fv)

        # 2. Isolation Forest component
        if_score = self._iforest_score(fv)

        # 3. Ensemble blend
        raw = self.rule_weight * rule_score + self.if_weight * if_score * 100
        final_score = int(min(max(raw, 0), 100))

        # 4. Sanctions override — always max score
        if features.get("sanctions_hit", 0) >= 1:
            final_score = 100
            contributions["sanctions_hit"] = 100.0

        # 5. Build explanation
        top_reasons = self._top_reasons(contributions, features)
        explanation = FraudExplanation(
            score=final_score,
            contributions=contributions,
            top_reasons=top_reasons,
            model_version=self.MODEL_VERSION,
        )

        # 6. Record for drift monitoring
        self.drift_detector.record_score(final_score)

        return explanation

    def batch_score(self, feature_list: List[Dict[str, float]]) -> List[FraudExplanation]:
        """Score multiple observations efficiently."""
        return [self.score(f) for f in feature_list]

    def fit(self, historical_features: List[Dict[str, float]]) -> None:
        """
        (Re-)train the Isolation Forest on historical feature data.
        Call this from a periodic management command.
        """
        if not historical_features:
            logger.warning("MLFraudScorer.fit: no data provided")
            return

        X = np.array([
            FeatureVector(f).array for f in historical_features
        ])
        self.iforest.fit(X)
        self._save_iforest()
        logger.info("MLFraudScorer: iForest retrained on %d samples", len(historical_features))

    def check_drift(self) -> Dict[str, Any]:
        """Return current model drift status."""
        return self.drift_detector.detect_drift()

    # ------------------------------------------------------------------
    # Scoring internals
    # ------------------------------------------------------------------

    def _rule_score(self, fv: FeatureVector) -> Tuple[float, Dict[str, float]]:
        """Weighted rule-based score (0–100) with per-feature contributions."""
        contributions: Dict[str, float] = {}
        total = 0.0

        for feature, weight in RULE_WEIGHTS.items():
            raw_val = fv.features.get(feature, 0.0)

            # Normalise each feature to [0, 1]
            if feature == "risk_score_current":
                normalised = raw_val / 100.0
            elif feature in ("ip_reputation_score", "geo_velocity_score", "behavioral_risk_score"):
                normalised = raw_val / 100.0
            elif feature in ("transaction_velocity_1h", "transaction_velocity_24h"):
                # Velocity is already a 0–100 ratio (vs threshold)
                normalised = min(raw_val / 100.0, 1.0)
            elif feature == "device_age_days":
                # New device = high risk (inverse)
                normalised = max(0.0, 1.0 - min(raw_val / 90.0, 1.0))
            elif feature == "account_age_days":
                normalised = max(0.0, 1.0 - min(raw_val / 180.0, 1.0))
            elif feature == "hour_of_day_risk":
                normalised = raw_val / 100.0
            elif feature == "amount_zscore":
                # Z-score: 0–3 is normal; >3 is suspicious
                normalised = min(max(raw_val - 1.5, 0.0) / 3.0, 1.0)
            elif feature == "failed_login_count_24h":
                normalised = min(raw_val / 10.0, 1.0)
            elif feature in ("device_shared_count", "ip_shared_count"):
                normalised = min(raw_val / 20.0, 1.0)
            elif feature == "login_velocity_1h":
                normalised = min(raw_val / 10.0, 1.0)
            elif feature == "sanctions_hit":
                normalised = 1.0 if raw_val >= 1 else 0.0
            else:
                normalised = min(raw_val / 100.0, 1.0)

            contribution = normalised * weight * 100
            contributions[feature] = round(contribution, 2)
            total += contribution

        return min(total, 100.0), contributions

    def _iforest_score(self, fv: FeatureVector) -> float:
        """Return iForest anomaly score in [0, 1]."""
        try:
            scores = self.iforest.score_samples(fv.array.reshape(1, -1))
            return float(scores[0])
        except Exception as e:
            logger.warning("MLFraudScorer iForest scoring error: %s", e)
            return 0.5

    @staticmethod
    def _top_reasons(contributions: Dict[str, float], features: Dict[str, float]) -> List[str]:
        """Rank features by contribution and return human-readable reasons."""
        ranked = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

        reason_templates = {
            "risk_score_current":       lambda v: f"Existing risk score is elevated ({features.get('risk_score_current', 0):.0f}/100)",
            "transaction_velocity_1h":  lambda v: f"High transaction velocity in last hour ({features.get('transaction_velocity_1h', 0):.0f}% of limit)",
            "transaction_velocity_24h": lambda v: f"High transaction velocity in last 24h ({features.get('transaction_velocity_24h', 0):.0f}% of limit)",
            "ip_reputation_score":      lambda v: f"Suspicious IP reputation score ({features.get('ip_reputation_score', 0):.0f}/100)",
            "geo_velocity_score":       lambda v: f"Impossible or suspicious travel detected ({features.get('geo_velocity_score', 0):.0f}/100)",
            "behavioral_risk_score":    lambda v: f"Behavioral biometrics anomaly ({features.get('behavioral_risk_score', 0):.0f}/100)",
            "device_age_days":          lambda v: f"New or recently registered device ({features.get('device_age_days', 0):.0f} days old)",
            "account_age_days":         lambda v: f"Recently created account ({features.get('account_age_days', 0):.0f} days old)",
            "failed_login_count_24h":   lambda v: f"Multiple failed logins in 24h ({features.get('failed_login_count_24h', 0):.0f} attempts)",
            "sanctions_hit":            lambda v: "Entity matches sanctions/watchlist",
            "device_shared_count":      lambda v: f"Device shared by {features.get('device_shared_count', 0):.0f} accounts",
            "ip_shared_count":          lambda v: f"IP shared by {features.get('ip_shared_count', 0):.0f} accounts",
            "login_velocity_1h":        lambda v: f"High login velocity ({features.get('login_velocity_1h', 0):.0f} attempts/hr)",
            "amount_zscore":            lambda v: f"Transaction amount is a statistical outlier (z={features.get('amount_zscore', 0):.1f})",
            "hour_of_day_risk":         lambda v: f"Transaction at unusual hour (risk={features.get('hour_of_day_risk', 0):.0f}/100)",
        }

        reasons = []
        for feature, contrib in ranked:
            if contrib >= 2.0 and feature in reason_templates:
                reasons.append(reason_templates[feature](contrib))
            if len(reasons) >= 5:
                break

        return reasons or ["No significant risk factors identified"]

    # ------------------------------------------------------------------
    # Model persistence
    # ------------------------------------------------------------------

    def _load_or_init_iforest(self) -> IsolationForestScorer:
        """Load persisted iForest from cache or initialise a fresh one."""
        try:
            data = cache.get(self.CACHE_KEY_MODEL)
            if data and isinstance(data, dict) and data.get("trees"):
                scorer = IsolationForestScorer()
                scorer._trees  = data["trees"]
                scorer._fitted = True
                return scorer
        except Exception as e:
            logger.warning("MLFraudScorer: iForest load error: %s", e)
        return IsolationForestScorer()

    def _save_iforest(self) -> None:
        try:
            data = {
                "trees":      self.iforest._trees,
                "saved_at":   datetime.now(tz.utc).isoformat(),
                "version":    self.MODEL_VERSION,
            }
            cache.set(self.CACHE_KEY_MODEL, data, timeout=86400 * 30)
        except Exception as e:
            logger.warning("MLFraudScorer: iForest save error: %s", e)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_ml_scorer: Optional[MLFraudScorer] = None


def get_ml_scorer() -> MLFraudScorer:
    global _ml_scorer
    if _ml_scorer is None:
        _ml_scorer = MLFraudScorer()
    return _ml_scorer
