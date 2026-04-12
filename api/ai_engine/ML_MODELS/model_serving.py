"""
api/ai_engine/ML_MODELS/model_serving.py
=========================================
Model Serving — production REST serving layer।
"""

import logging
import time
from typing import Dict, List, Any
from .model_predictor import ModelPredictor

logger = logging.getLogger(__name__)

# In-process model cache
_serving_cache: Dict[str, ModelPredictor] = {}


class ModelServer:
    """
    Production model serving।
    Load once, serve many requests।
    """

    def __init__(self, model_id: str):
        self.model_id  = model_id
        self.predictor = self._load_predictor()

    def _load_predictor(self) -> ModelPredictor:
        if self.model_id in _serving_cache:
            return _serving_cache[self.model_id]

        from ..models import ModelVersion
        version = ModelVersion.objects.filter(
            ai_model_id=self.model_id, is_active=True
        ).first()
        path = version.model_file_path if version else ''
        predictor = ModelPredictor(path)
        _serving_cache[self.model_id] = predictor
        return predictor

    def serve(self, features: dict) -> dict:
        start = time.time()
        result = self.predictor.predict(features)
        result['served_by'] = self.model_id
        result['latency_ms'] = round((time.time() - start) * 1000, 2)
        return result

    def serve_batch(self, features_list: List[dict]) -> List[dict]:
        return [self.serve(f) for f in features_list]

    @staticmethod
    def clear_cache():
        _serving_cache.clear()
        logger.info("Model serving cache cleared.")


"""
api/ai_engine/ML_MODELS/model_monitor.py
=========================================
Model Monitor — production performance monitoring।
"""


class ModelMonitor:
    """Monitor production model metrics।"""

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id

    def get_production_metrics(self, days: int = 7) -> dict:
        from ..repository import PredictionLogRepository
        from ..models import AnomalyDetectionLog
        from django.utils import timezone
        from datetime import timedelta

        accuracy   = PredictionLogRepository.get_accuracy_stats(self.ai_model_id, days)
        since      = timezone.now() - timedelta(days=days)
        anomalies  = AnomalyDetectionLog.objects.filter(
            ai_model_id=self.ai_model_id, created_at__gte=since
        ).count()

        health = 'healthy'
        if accuracy['accuracy'] < 0.60:
            health = 'degraded'
        if accuracy['accuracy'] < 0.40 or anomalies > 100:
            health = 'critical'

        return {
            'ai_model_id': self.ai_model_id,
            'period_days': days,
            'health':      health,
            'accuracy':    accuracy,
            'anomalies':   anomalies,
        }

    def check_latency(self, threshold_ms: float = 200) -> dict:
        from ..models import PredictionLog
        from django.db.models import Avg
        from django.utils import timezone
        from datetime import timedelta

        since = timezone.now() - timedelta(hours=1)
        result = PredictionLog.objects.filter(
            ai_model_id=self.ai_model_id, created_at__gte=since
        ).aggregate(avg_ms=Avg('inference_ms'))

        avg_ms = result.get('avg_ms') or 0
        return {
            'avg_latency_ms': round(avg_ms, 2),
            'threshold_ms':   threshold_ms,
            'within_sla':     avg_ms <= threshold_ms,
        }


"""
api/ai_engine/ML_MODELS/model_explainer.py
===========================================
Model Explainer — SHAP, LIME based explanations।
"""


class ModelExplainer:
    """
    Model prediction explanation।
    SHAP values, feature importance, LIME।
    """

    def explain_prediction(self, model, features: dict, feature_names: list = None) -> dict:
        feature_names = feature_names or list(features.keys())
        values        = list(features.values())

        try:
            import shap
            import numpy as np
            X = np.array([values])
            explainer   = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]

            explanation = {
                fn: round(float(sv), 4)
                for fn, sv in zip(feature_names, shap_values[0])
            }
            top_features = sorted(explanation.items(), key=lambda x: abs(x[1]), reverse=True)[:5]

            return {
                'method':       'shap',
                'feature_contributions': explanation,
                'top_5_features': dict(top_features),
            }
        except Exception:
            # Fallback: feature importance from model
            try:
                importance = dict(zip(feature_names, model.feature_importances_))
                top = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]
                return {'method': 'feature_importance', 'top_5_features': dict(top)}
            except Exception:
                return {'method': 'unavailable', 'top_5_features': {}}
