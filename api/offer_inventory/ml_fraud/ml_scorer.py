# api/offer_inventory/ml_fraud/ml_scorer.py
"""ML Fraud Scorer — Score events using trained Isolation Forest model."""
import logging
from .feature_builder import FraudFeatureBuilder

logger = logging.getLogger(__name__)


class MLFraudScorer:
    """
    ML-based fraud scorer using cached trained model.
    Combines rule-based score (60%) with ML anomaly score (40%).
    Falls back gracefully if scikit-learn not installed.
    """

    MODEL_CACHE_KEY  = 'ml_fraud:model'
    SCALER_CACHE_KEY = 'ml_fraud:scaler'

    @classmethod
    def score(cls, ip: str, user=None, user_agent: str = '',
               rule_based_score: float = 0.0) -> dict:
        """
        Compute ML fraud score.
        Returns {'ml_score': float, 'combined_score': float, 'is_anomaly': bool}
        """
        try:
            features    = FraudFeatureBuilder.extract(ip, user, user_agent)
            ml_score    = cls._score_with_model(features)
            combined    = cls._combine(rule_based_score, ml_score)
            return {
                'ml_score'      : round(ml_score, 1),
                'rule_score'    : round(rule_based_score, 1),
                'combined_score': round(combined, 1),
                'is_anomaly'    : ml_score >= 70.0,
                'features_used' : len(features),
            }
        except Exception as e:
            logger.debug(f'ML scoring error: {e}')
            return {
                'ml_score'      : 0.0,
                'rule_score'    : rule_based_score,
                'combined_score': rule_based_score,
                'is_anomaly'    : False,
                'error'         : str(e)[:100],
            }

    @classmethod
    def _score_with_model(cls, features: list) -> float:
        """Score using cached Isolation Forest model."""
        try:
            import numpy as np
            from django.core.cache import cache

            model  = cache.get(cls.MODEL_CACHE_KEY)
            scaler = cache.get(cls.SCALER_CACHE_KEY)
            if model is None or scaler is None:
                return 0.0   # Model not trained yet

            X          = scaler.transform([features])
            raw_score  = model.decision_function(X)[0]
            # Negative = anomaly, positive = normal → convert to 0-100
            fraud_pct  = max(0.0, min(100.0, (-raw_score + 0.5) * 100))
            return fraud_pct
        except ImportError:
            return 0.0   # scikit-learn not installed
        except Exception as e:
            logger.debug(f'Model score error: {e}')
            return 0.0

    @staticmethod
    def _combine(rule: float, ml: float) -> float:
        """60% rule-based + 40% ML weighted score."""
        return rule * 0.6 + ml * 0.4

    @classmethod
    def is_model_ready(cls) -> bool:
        """Check if trained model is available."""
        from django.core.cache import cache
        return (
            cache.get(cls.MODEL_CACHE_KEY) is not None and
            cache.get(cls.SCALER_CACHE_KEY) is not None
        )

    @classmethod
    def get_model_info(cls) -> dict:
        """Info about the current model."""
        ready = cls.is_model_ready()
        return {
            'model_ready'    : ready,
            'algorithm'      : 'IsolationForest',
            'features'       : FraudFeatureBuilder.FEATURE_NAMES,
            'feature_count'  : len(FraudFeatureBuilder.FEATURE_NAMES),
            'weight_rules'   : '60%',
            'weight_ml'      : '40%',
            'status'         : 'active' if ready else 'not_trained',
            'train_command'  : 'python manage.py train_fraud_model',
        }
