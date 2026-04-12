"""ML Predictor — loads trained model and predicts fraud probability."""
import logging
from django.core.cache import cache
logger = logging.getLogger(__name__)

class MLPredictor:
    """
    Loads the active ML model from MLModelMetadata and runs prediction.
    Falls back to rule-based scoring if no model is available.
    """
    def __init__(self, model_type: str = 'risk_scoring'):
        self.model_type = model_type
        self._model = None
        self._load_model()

    def _load_model(self):
        try:
            from ..models import MLModelMetadata
            meta = MLModelMetadata.objects.filter(
                model_type=self.model_type, is_active=True
            ).first()
            if meta and meta.model_file_path:
                import joblib, os
                if os.path.exists(meta.model_file_path):
                    self._model = joblib.load(meta.model_file_path)
                    logger.info(f"Loaded ML model: {meta.name} v{meta.version}")
        except Exception as e:
            logger.debug(f"ML model load failed: {e}")

    def predict(self, features: dict) -> dict:
        if self._model is None:
            return self._rule_based_fallback(features)
        try:
            import numpy as np
            feature_vector = list(features.values())
            prob = float(self._model.predict_proba([feature_vector])[0][1])
            return {
                'fraud_probability': round(prob, 4),
                'predicted_fraud': prob >= 0.5,
                'model_used': self.model_type,
                'confidence': round(prob if prob >= 0.5 else 1 - prob, 4),
            }
        except Exception as e:
            logger.warning(f"ML prediction failed: {e}")
            return self._rule_based_fallback(features)

    @staticmethod
    def _rule_based_fallback(features: dict) -> dict:
        score = 0
        if features.get('is_vpn'):   score += 30
        if features.get('is_tor'):   score += 45
        if features.get('is_proxy'): score += 20
        score += features.get('risk_score', 0) * 0.3
        prob = min(score / 100, 1.0)
        return {
            'fraud_probability': round(prob, 4),
            'predicted_fraud': prob >= 0.5,
            'model_used': 'rule_based_fallback',
            'confidence': round(prob if prob >= 0.5 else 1 - prob, 4),
        }
