"""
api/ai_engine/ANOMALY_DETECTION/one_class_svm.py
================================================
One-Class SVM Anomaly Detector।
Normal behavior শিখে যেকোনো deviation detect করো।
Unsupervised anomaly detection — labeled data লাগে না।
"""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class OneClassSVMDetector:
    """
    One-Class SVM based anomaly detection।
    Training data: normal samples only।
    Detection: anything unusual = anomaly।
    """

    def __init__(self, nu: float = 0.05, kernel: str = 'rbf',
                 gamma: str = 'auto'):
        self.nu     = nu       # Expected fraction of anomalies
        self.kernel = kernel
        self.gamma  = gamma
        self.model  = None
        self.scaler = None
        self._is_fitted = False

    def fit(self, X_normal) -> dict:
        """
        Normal samples দিয়ে model train করো।
        X_normal: numpy array of normal behavior features।
        """
        try:
            from sklearn.svm import OneClassSVM
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            X = np.array(X_normal)
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            self.model = OneClassSVM(
                nu=self.nu,
                kernel=self.kernel,
                gamma=self.gamma,
            )
            self.model.fit(X_scaled)
            self._is_fitted = True

            logger.info(f"OneClassSVM fitted on {len(X)} normal samples.")
            return {
                'fitted':          True,
                'training_samples': len(X),
                'nu':              self.nu,
                'kernel':          self.kernel,
            }
        except ImportError:
            logger.warning("scikit-learn not available for OneClassSVM")
            return {'fitted': False, 'error': 'sklearn not installed'}
        except Exception as e:
            logger.error(f"OneClassSVM fit error: {e}")
            return {'fitted': False, 'error': str(e)}

    def predict(self, X) -> List[int]:
        """
        Predictions: 1 = normal, -1 = anomaly।
        """
        if not self._is_fitted:
            return [1] * len(X)
        try:
            import numpy as np
            X_arr    = np.array(X)
            X_scaled = self.scaler.transform(X_arr)
            return self.model.predict(X_scaled).tolist()
        except Exception as e:
            logger.error(f"OneClassSVM predict error: {e}")
            return [1] * len(X)

    def score_samples(self, X) -> List[float]:
        """
        Anomaly scores: lower = more anomalous।
        Normalized to 0-1 where 1 = most anomalous।
        """
        if not self._is_fitted:
            return [0.5] * len(X)
        try:
            import numpy as np
            X_arr    = np.array(X)
            X_scaled = self.scaler.transform(X_arr)
            raw_scores = self.model.score_samples(X_scaled)

            # Normalize: flip and scale to 0-1 (higher = more anomalous)
            min_s = raw_scores.min()
            max_s = raw_scores.max()
            if max_s == min_s:
                return [0.5] * len(X)
            normalized = 1.0 - (raw_scores - min_s) / (max_s - min_s)
            return [round(float(s), 4) for s in normalized]
        except Exception as e:
            logger.error(f"OneClassSVM score error: {e}")
            return [0.5] * len(X)

    def detect_single(self, features: dict,
                       feature_order: List[str] = None) -> dict:
        """Single observation anomaly detection।"""
        if feature_order:
            X = [[features.get(f, 0) for f in feature_order]]
        else:
            X = [[v for v in features.values()]]

        label  = self.predict(X)[0]
        score  = self.score_samples(X)[0]

        return {
            'is_anomaly':    label == -1,
            'anomaly_score': score,
            'prediction':    'anomaly' if label == -1 else 'normal',
            'confidence':    round(abs(score - 0.5) * 2, 4),
        }

    def get_decision_boundary_info(self) -> dict:
        """Model decision boundary information।"""
        if not self._is_fitted:
            return {'fitted': False}
        try:
            return {
                'fitted':          True,
                'nu':              self.nu,
                'kernel':          self.kernel,
                'n_support_vectors': len(self.model.support_vectors_),
            }
        except Exception:
            return {'fitted': self._is_fitted}

    def incremental_fit(self, new_normal_samples,
                         existing_X = None) -> dict:
        """New normal data দিয়ে model update করো।"""
        try:
            import numpy as np
            if existing_X is not None:
                combined = np.vstack([existing_X, new_normal_samples])
            else:
                combined = np.array(new_normal_samples)
            return self.fit(combined)
        except Exception as e:
            return {'fitted': False, 'error': str(e)}
