"""
api/ai_engine/ML_MODELS/model_predictor.py
==========================================
Model Predictor — saved model load করে inference চালাও।
"""

import logging
import pickle
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_model_cache: Dict[str, Any] = {}  # in-memory model cache


class ModelPredictor:
    """Saved model load করে prediction করো।"""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = self._load(model_path)

    def _load(self, path: str):
        if path in _model_cache:
            return _model_cache[path]
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, 'rb') as f:
                model = pickle.load(f)
            _model_cache[path] = model
            logger.info(f"Model loaded: {path}")
            return model
        except Exception as e:
            logger.error(f"Model load error [{path}]: {e}")
            return None

    def predict(self, features: dict) -> dict:
        if self.model is None:
            return {'confidence': 0.5, 'predicted_class': 'unknown', 'method': 'no_model'}

        try:
            import numpy as np
            X = np.array([list(features.values())], dtype=float)

            if hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(X)[0]
                predicted_class = str(self.model.predict(X)[0])
                confidence = float(max(proba))
            else:
                pred = self.model.predict(X)[0]
                predicted_class = str(pred)
                confidence = 0.75

            return {
                'predicted_class': predicted_class,
                'predicted_value': float(proba[1]) if hasattr(self.model, 'predict_proba') else None,
                'confidence': confidence,
                'method': 'ml_model',
            }
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return {'confidence': 0.5, 'predicted_class': 'error', 'error': str(e)}

    def predict_batch(self, features_list: list) -> list:
        return [self.predict(f) for f in features_list]

    @staticmethod
    def clear_cache():
        _model_cache.clear()
