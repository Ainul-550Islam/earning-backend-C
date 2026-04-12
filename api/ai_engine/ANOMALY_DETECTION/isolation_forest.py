"""
api/ai_engine/ANOMALY_DETECTION/isolation_forest.py
====================================================
Isolation Forest Anomaly Detector।
"""

import logging
logger = logging.getLogger(__name__)


class IsolationForestDetector:
    """Isolation Forest for unsupervised anomaly detection।"""

    def __init__(self, contamination: float = 0.05, n_estimators: int = 100):
        self.contamination = contamination
        self.n_estimators  = n_estimators
        self.model         = None

    def fit(self, X):
        try:
            from sklearn.ensemble import IsolationForest
            self.model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=42, n_jobs=-1
            )
            self.model.fit(X)
            logger.info("IsolationForest fitted.")
        except Exception as e:
            logger.error(f"IsolationForest fit error: {e}")

    def predict(self, X) -> list:
        if not self.model:
            return [-1 if False else 1 for _ in X]
        try:
            return self.model.predict(X).tolist()  # 1=normal, -1=anomaly
        except Exception:
            return [1] * len(X)

    def score_samples(self, X) -> list:
        if not self.model:
            return [0.5] * len(X)
        try:
            scores = self.model.score_samples(X)
            # Convert to 0-1 anomaly score (higher = more anomalous)
            import numpy as np
            normalized = 1 - (scores - scores.min()) / (scores.max() - scores.min() + 1e-9)
            return [round(float(s), 4) for s in normalized]
        except Exception:
            return [0.5] * len(X)


"""
api/ai_engine/ANOMALY_DETECTION/autoencoder_anomaly.py
=======================================================
Autoencoder-based Anomaly Detection।
"""


class AutoencoderAnomalyDetector:
    """Reconstruction error based anomaly detection।"""

    def __init__(self, input_dim: int, encoding_dim: int = 32, threshold: float = None):
        self.input_dim    = input_dim
        self.encoding_dim = encoding_dim
        self.threshold    = threshold
        self.model        = None

    def build(self):
        try:
            import torch
            import torch.nn as nn
            self.model = nn.Sequential(
                nn.Linear(self.input_dim, 64), nn.ReLU(),
                nn.Linear(64, self.encoding_dim), nn.ReLU(),
                nn.Linear(self.encoding_dim, 64), nn.ReLU(),
                nn.Linear(64, self.input_dim),
            )
        except ImportError:
            logger.warning("PyTorch not installed for autoencoder.")

    def reconstruction_error(self, X) -> list:
        if not self.model:
            return [0.05] * len(X)
        try:
            import torch
            t = torch.FloatTensor(X)
            with torch.no_grad():
                reconstructed = self.model(t)
                errors = ((t - reconstructed) ** 2).mean(dim=1)
            return [round(float(e), 6) for e in errors]
        except Exception:
            return [0.05] * len(X)


"""
api/ai_engine/ANOMALY_DETECTION/fraud_anomaly_detector.py
==========================================================
Fraud-specific Anomaly Detector।
"""


class FraudAnomalyDetector:
    """Comprehensive fraud anomaly detection।"""

    def detect(self, event_data: dict, user=None) -> dict:
        from .real_time_anomaly import RealTimeAnomalyDetector

        anomaly_types = ['fraud_click', 'bulk_request', 'unusual_login']
        results       = {}

        for atype in anomaly_types:
            detector = RealTimeAnomalyDetector(atype)
            score    = detector.score(event_data)
            results[atype] = {'score': round(score, 4), 'is_anomaly': score >= 0.75}

        max_score = max(r['score'] for r in results.values())
        return {
            'overall_fraud_score': round(max_score, 4),
            'is_fraud':            max_score >= 0.75,
            'details':             results,
        }


"""
api/ai_engine/ANOMALY_DETECTION/system_anomaly_detector.py
===========================================================
System-level Anomaly Detector — API errors, latency spikes।
"""


class SystemAnomalyDetector:
    def detect(self, metrics: dict) -> dict:
        score = 0.0
        flags = []

        error_rate   = metrics.get('error_rate_pct', 0)
        latency_ms   = metrics.get('avg_latency_ms', 0)
        cpu_pct      = metrics.get('cpu_pct', 0)
        memory_pct   = metrics.get('memory_pct', 0)

        if error_rate > 10:    score += 0.5; flags.append('high_error_rate')
        if latency_ms > 2000:  score += 0.3; flags.append('high_latency')
        if cpu_pct > 90:       score += 0.3; flags.append('cpu_spike')
        if memory_pct > 90:    score += 0.2; flags.append('memory_pressure')

        return {
            'anomaly_score': round(min(1.0, score), 4),
            'is_anomaly':    score >= 0.5,
            'flags':         flags,
            'metrics':       metrics,
        }


"""
api/ai_engine/ANOMALY_DETECTION/network_anomaly_detector.py
============================================================
Network Traffic Anomaly Detector।
"""


class NetworkAnomalyDetector:
    def detect(self, traffic_data: dict) -> dict:
        score = 0.0
        rps   = traffic_data.get('requests_per_second', 0)
        unique_ips = traffic_data.get('unique_ips', 1)
        bot_score  = traffic_data.get('bot_score', 0.0)

        if rps > 1000: score += 0.5
        elif rps > 500: score += 0.3
        if bot_score > 0.7: score += 0.4
        if unique_ips < 5 and rps > 100: score += 0.3

        return {
            'anomaly_score': round(min(1.0, score), 4),
            'is_ddos':       score >= 0.7,
            'is_bot':        bot_score >= 0.7,
            'rps':           rps,
        }


"""
api/ai_engine/ANOMALY_DETECTION/user_behavior_anomaly.py
=========================================================
User Behavior Anomaly Detector।
"""


class UserBehaviorAnomalyDetector:
    def detect(self, user, behavior_data: dict) -> dict:
        from .real_time_anomaly import RealTimeAnomalyDetector
        detector = RealTimeAnomalyDetector('user_behavior')
        score    = detector.score(behavior_data)
        return {
            'anomaly_score': round(score, 4),
            'is_anomaly':    score >= 0.80,
            'user_id':       str(user.id) if user else None,
        }


"""
api/ai_engine/ANOMALY_DETECTION/conversion_anomaly.py
======================================================
Conversion Rate Anomaly Detector।
"""


class ConversionAnomalyDetector:
    def detect(self, conversion_data: dict) -> dict:
        cvr       = conversion_data.get('conversion_rate', 0)
        avg_cvr   = conversion_data.get('avg_cvr', 0.10)
        volume    = conversion_data.get('volume', 0)

        score = 0.0
        flags = []

        if avg_cvr > 0:
            ratio = cvr / avg_cvr
            if ratio > 5:  score += 0.6; flags.append('cvr_spike_5x')
            elif ratio > 3: score += 0.4; flags.append('cvr_spike_3x')
            elif ratio < 0.2: score += 0.3; flags.append('cvr_drop_80pct')

        if volume > 10000 and cvr > 0.8: score += 0.4; flags.append('mass_conversion')

        return {
            'anomaly_score': round(min(1.0, score), 4),
            'is_anomaly':    score >= 0.6,
            'flags':         flags,
            'cvr':           cvr,
        }


"""
api/ai_engine/ANOMALY_DETECTION/one_class_svm.py
================================================
One-Class SVM Anomaly Detector।
"""


class OneClassSVMDetector:
    def __init__(self, nu: float = 0.05, kernel: str = 'rbf'):
        self.nu     = nu
        self.kernel = kernel
        self.model  = None

    def fit(self, X):
        try:
            from sklearn.svm import OneClassSVM
            self.model = OneClassSVM(nu=self.nu, kernel=self.kernel)
            self.model.fit(X)
        except Exception as e:
            logger.error(f"One-Class SVM fit error: {e}")

    def predict(self, X) -> list:
        if not self.model:
            return [1] * len(X)
        return self.model.predict(X).tolist()
