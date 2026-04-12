# api/offer_inventory/ml_fraud/__init__.py
"""
ML Fraud — Machine Learning enhanced fraud detection.
Uses: Isolation Forest, behavioral clustering, anomaly detection.
Works without GPU — pure scikit-learn/numpy.
Upgrades fraud_detection.py rule-based system with learned patterns.
"""
from .ml_scorer       import MLFraudScorer
from .feature_builder import FraudFeatureBuilder
from .model_trainer   import FraudModelTrainer
from .anomaly_detector import AnomalyDetector

__all__ = [
    'MLFraudScorer', 'FraudFeatureBuilder',
    'FraudModelTrainer', 'AnomalyDetector',
]
