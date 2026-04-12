"""
Unsupervised Learning Engine  (PRODUCTION-READY — COMPLETE)
=============================================================
Anomaly detection using unsupervised ML algorithms.
No labeled training data required — the model learns what is
"normal" and flags deviations.

Algorithms:
  - Isolation Forest (primary — fast, works well with mixed features)
  - Local Outlier Factor (secondary — good for density-based anomalies)
  - One-Class SVM (tertiary — good for high-dimensional data)

Feature input matches the risk_scoring_model.py FEATURE_NAMES list
so both supervised and unsupervised models use the same pipeline.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class UnsupervisedAnomalyDetector:
    """
    Trains and runs unsupervised anomaly detection.

    Usage — training:
        detector = UnsupervisedAnomalyDetector(algorithm='isolation_forest')
        X = [[0,1,0,0,80,...], ...]   # list of feature vectors
        metrics = detector.fit(X)
        detector.save('/tmp/pi_anomaly_model.pkl')

    Usage — inference:
        detector = UnsupervisedAnomalyDetector.load('/tmp/pi_anomaly_model.pkl')
        prediction = detector.predict_one([0,1,0,0,80,...])
        # prediction: {'is_anomaly': True, 'anomaly_score': -0.15}
    """

    SUPPORTED_ALGORITHMS = ['isolation_forest', 'local_outlier_factor', 'one_class_svm']

    def __init__(self, algorithm: str = 'isolation_forest',
                 contamination: float = 0.1,
                 n_estimators: int = 100,
                 random_state: int = 42):
        """
        Args:
            algorithm:     One of: isolation_forest, local_outlier_factor, one_class_svm
            contamination: Expected fraction of anomalies (0.0 to 0.5)
            n_estimators:  Number of trees (Isolation Forest only)
            random_state:  Reproducibility seed
        """
        if algorithm not in self.SUPPORTED_ALGORITHMS:
            raise ValueError(
                f"Unsupported algorithm '{algorithm}'. "
                f"Choose from: {self.SUPPORTED_ALGORITHMS}"
            )
        self.algorithm    = algorithm
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.random_state = random_state
        self.model        = None
        self.scaler       = None
        self._is_fitted   = False

    # ── Training ───────────────────────────────────────────────────────────

    def fit(self, X: list) -> dict:
        """
        Train the anomaly detector on a dataset of feature vectors.
        All values should be numeric (0/1 for flags, 0.0-1.0 for scores).

        Args:
            X: List of feature vectors (list of lists)

        Returns:
            Training metrics dict
        """
        try:
            import numpy as np
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            return {'error': 'scikit-learn not installed. Run: pip install scikit-learn'}

        if len(X) < 10:
            return {'error': f'Insufficient data: {len(X)} samples (need ≥ 10)'}

        try:
            X_arr = np.array(X, dtype=float)

            # Standardise features
            self.scaler = StandardScaler()
            X_scaled    = self.scaler.fit_transform(X_arr)

            # Build and fit the model
            self.model = self._build_model()
            self.model.fit(X_scaled)
            self._is_fitted = True

            # Score on training data
            raw_scores = self.model.decision_function(X_scaled)
            predictions = self.model.predict(X_scaled)
            anomaly_count = int((predictions == -1).sum())

            return {
                'status':           'trained',
                'algorithm':        self.algorithm,
                'training_samples': len(X),
                'feature_count':    X_arr.shape[1],
                'contamination':    self.contamination,
                'anomalies_found':  anomaly_count,
                'anomaly_rate':     round(anomaly_count / len(X), 4),
                'mean_score':       float(raw_scores.mean()),
                'std_score':        float(raw_scores.std()),
                'min_score':        float(raw_scores.min()),
                'max_score':        float(raw_scores.max()),
            }

        except Exception as e:
            logger.error(f"Unsupervised model training failed: {e}")
            return {'error': str(e)}

    def fit_from_db(self, days: int = 30, limit: int = 10000) -> dict:
        """
        Convenience method: pull clean (non-fraud) IP intelligence records
        from the database and use them as the "normal" training distribution.
        """
        try:
            from ..models import IPIntelligence
            from django.utils import timezone
            from datetime import timedelta
            from ..ai_ml_engines.risk_scoring_model import RiskScoringModel

            since = timezone.now() - timedelta(days=days)
            records = IPIntelligence.objects.filter(
                last_checked__gte=since,
                risk_score__lt=40,   # Only "clean" IPs as normal baseline
            ).values(
                'is_vpn', 'is_proxy', 'is_tor', 'is_datacenter',
                'is_hosting', 'abuse_confidence_score', 'fraud_score', 'risk_score',
            )[:limit]

            X = []
            for r in records:
                vector = RiskScoringModel.build_feature_vector(r)
                X.append(vector)

            if not X:
                return {'error': 'No clean training data found in database'}

            return self.fit(X)

        except Exception as e:
            logger.error(f"fit_from_db failed: {e}")
            return {'error': str(e)}

    # ── Inference ──────────────────────────────────────────────────────────

    def predict(self, X: list) -> list:
        """
        Predict anomaly labels for a batch of feature vectors.

        Args:
            X: List of feature vectors

        Returns:
            List of ints: 1 = normal, -1 = anomaly
        """
        if not self._is_fitted or self.model is None:
            logger.warning("Unsupervised model not fitted. Returning all normal.")
            return [1] * len(X)
        try:
            import numpy as np
            X_arr    = np.array(X, dtype=float)
            X_scaled = self.scaler.transform(X_arr)
            return self.model.predict(X_scaled).tolist()
        except Exception as e:
            logger.error(f"Unsupervised predict failed: {e}")
            return [1] * len(X)

    def predict_one(self, x: list) -> dict:
        """
        Predict anomaly for a single feature vector.

        Returns:
            {
                'is_anomaly':    bool,
                'anomaly_score': float (lower = more anomalous),
                'label':         int (-1 = anomaly, 1 = normal)
            }
        """
        if not self._is_fitted or self.model is None:
            return {
                'is_anomaly':    False,
                'anomaly_score': 0.0,
                'label':         1,
                'model_ready':   False,
            }
        try:
            import numpy as np
            x_arr    = np.array([x], dtype=float)
            x_scaled = self.scaler.transform(x_arr)
            label    = int(self.model.predict(x_scaled)[0])
            score    = float(self.model.decision_function(x_scaled)[0])

            return {
                'is_anomaly':    label == -1,
                'anomaly_score': round(score, 6),
                'label':         label,
                'model_ready':   True,
                'algorithm':     self.algorithm,
            }
        except Exception as e:
            logger.error(f"predict_one failed: {e}")
            return {'is_anomaly': False, 'anomaly_score': 0.0, 'label': 1, 'error': str(e)}

    def predict_ip(self, ip_address: str) -> dict:
        """
        Predict anomaly for an IP by loading its features from the DB.
        """
        try:
            from ..ai_ml_engines.risk_scoring_model import RiskScoringModel
            data    = RiskScoringModel.enrich_from_intelligence(ip_address)
            if not data:
                return {'is_anomaly': False, 'error': 'IP not found in DB'}
            vector  = RiskScoringModel.build_feature_vector(data)
            result  = self.predict_one(vector)
            result['ip_address'] = ip_address
            return result
        except Exception as e:
            logger.error(f"predict_ip failed for {ip_address}: {e}")
            return {'ip_address': ip_address, 'is_anomaly': False, 'error': str(e)}

    def get_anomaly_scores(self, X: list) -> list:
        """
        Return raw anomaly scores for a batch (lower = more anomalous).
        """
        if not self._is_fitted:
            return [0.0] * len(X)
        try:
            import numpy as np
            X_arr    = np.array(X, dtype=float)
            X_scaled = self.scaler.transform(X_arr)
            return self.model.decision_function(X_scaled).tolist()
        except Exception as e:
            logger.error(f"get_anomaly_scores failed: {e}")
            return [0.0] * len(X)

    # ── Model Persistence ──────────────────────────────────────────────────

    def save(self, path: str) -> Optional[str]:
        """Save trained model and scaler to disk using joblib."""
        if not self._is_fitted:
            logger.warning("Cannot save: model not fitted yet.")
            return None
        try:
            import joblib
            os.makedirs(os.path.dirname(path), exist_ok=True)
            payload = {
                'model':        self.model,
                'scaler':       self.scaler,
                'algorithm':    self.algorithm,
                'contamination': self.contamination,
            }
            joblib.dump(payload, path)
            logger.info(f"Unsupervised model saved to {path}")
            return path
        except Exception as e:
            logger.error(f"Model save failed: {e}")
            return None

    @classmethod
    def load(cls, path: str) -> 'UnsupervisedAnomalyDetector':
        """Load a previously saved model from disk."""
        try:
            import joblib
            payload = joblib.load(path)
            instance = cls(
                algorithm=payload.get('algorithm', 'isolation_forest'),
                contamination=payload.get('contamination', 0.1),
            )
            instance.model      = payload['model']
            instance.scaler     = payload['scaler']
            instance._is_fitted = True
            logger.info(f"Unsupervised model loaded from {path}")
            return instance
        except Exception as e:
            logger.error(f"Model load failed: {e}")
            raise

    def register_in_db(self, save_path: str,
                        training_metrics: dict) -> Optional[str]:
        """
        Register the trained model in MLModelMetadata for tracking.
        Returns the model UUID string.
        """
        try:
            from ..models import MLModelMetadata
            from django.utils import timezone
            version = timezone.now().strftime('%Y%m%d%H%M')
            meta = MLModelMetadata.objects.create(
                name=f'unsupervised_{self.algorithm}',
                version=version,
                model_type='anomaly_detection',
                training_data_size=training_metrics.get('training_samples', 0),
                trained_at=timezone.now(),
                model_file_path=save_path or '',
                is_active=False,
                metadata={
                    'algorithm':     self.algorithm,
                    'contamination': self.contamination,
                    **training_metrics,
                },
            )
            logger.info(f"Unsupervised model registered: {meta.pk}")
            return str(meta.pk)
        except Exception as e:
            logger.error(f"Model DB registration failed: {e}")
            return None

    # ── Internal Model Factory ─────────────────────────────────────────────

    def _build_model(self):
        """Instantiate the scikit-learn model based on self.algorithm."""
        if self.algorithm == 'isolation_forest':
            from sklearn.ensemble import IsolationForest
            return IsolationForest(
                n_estimators=self.n_estimators,
                contamination=self.contamination,
                random_state=self.random_state,
                n_jobs=-1,
            )
        elif self.algorithm == 'local_outlier_factor':
            from sklearn.neighbors import LocalOutlierFactor
            return LocalOutlierFactor(
                n_neighbors=20,
                contamination=self.contamination,
                novelty=True,     # Must be True for predict() and decision_function()
                n_jobs=-1,
            )
        elif self.algorithm == 'one_class_svm':
            from sklearn.svm import OneClassSVM
            return OneClassSVM(
                nu=self.contamination,
                kernel='rbf',
                gamma='scale',
            )
        else:
            raise ValueError(f"Unknown algorithm: {self.algorithm}")

    @property
    def is_ready(self) -> bool:
        """True if model has been fitted and is ready for inference."""
        return self._is_fitted and self.model is not None

    def __repr__(self) -> str:
        status = 'fitted' if self._is_fitted else 'not fitted'
        return (
            f"UnsupervisedAnomalyDetector("
            f"algorithm={self.algorithm}, "
            f"contamination={self.contamination}, "
            f"status={status})"
        )
