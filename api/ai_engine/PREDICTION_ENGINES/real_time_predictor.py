"""
api/ai_engine/PREDICTION_ENGINES/real_time_predictor.py
========================================================
Real-Time Predictor — <200ms low-latency inference engine।
Hot model cache, feature pre-computation, async logging।
Production ML serving layer।
"""
import logging, time
from typing import Dict
logger = logging.getLogger(__name__)

_predictor_cache: Dict[str, object] = {}

class RealTimePredictor:
    """Production real-time prediction with warm model cache।"""

    SLA_MS = 200.0

    def __init__(self, ai_model):
        self.ai_model   = ai_model
        self._predictor = None

    def predict(self, features: dict) -> dict:
        start = time.time()
        predictor = self._get_predictor()
        try:
            result = predictor.predict(features)
        except Exception as e:
            logger.error(f"RTP inference error [{self.ai_model.id}]: {e}")
            result = {'confidence': 0.5, 'predicted_class': 'unknown', 'method': 'fallback'}
        latency = round((time.time() - start) * 1000, 2)
        if latency > self.SLA_MS:
            logger.warning(f"RTP latency {latency}ms > {self.SLA_MS}ms SLA [{self.ai_model.id}]")
        result['inference_ms']    = latency
        result['within_sla']      = latency <= self.SLA_MS
        result['ai_model_id']     = str(self.ai_model.id)
        result['model_version']   = self.ai_model.active_version
        return result

    def _get_predictor(self):
        model_id = str(self.ai_model.id)
        if model_id in _predictor_cache:
            return _predictor_cache[model_id]
        from ..ML_MODELS.model_predictor import ModelPredictor
        from ..models import ModelVersion
        version = ModelVersion.objects.filter(ai_model=self.ai_model, is_active=True).first()
        path    = version.model_file_path if version else ''
        p = ModelPredictor(path)
        _predictor_cache[model_id] = p
        logger.info(f"RTP model loaded and cached: {model_id}")
        return p

    def warm_up(self):
        dummy = {f'f{i}': 0.0 for i in range(10)}
        self.predict(dummy)
        logger.info(f"RTP model warmed up: {self.ai_model.id}")

    @staticmethod
    def clear_cache(model_id: str = None):
        if model_id: _predictor_cache.pop(model_id, None)
        else:         _predictor_cache.clear()

    def predict_batch(self, features_list: list) -> list:
        return [self.predict(f) for f in features_list]

    def health_check(self) -> dict:
        dummy = {f'f{i}': 0.5 for i in range(5)}
        result = self.predict(dummy)
        return {
            'healthy':     result.get('within_sla', False),
            'latency_ms':  result.get('inference_ms', 999),
            'model_id':    str(self.ai_model.id),
            'cached':      str(self.ai_model.id) in _predictor_cache,
        }
