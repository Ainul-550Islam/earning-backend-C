"""
api/ai_engine/MODEL_STORAGE/model_registry.py
=============================================
Model Registry — model versioning ও storage management।
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Centralized model registry।
    Save, load, list, promote, archive models।
    """

    def __init__(self, base_path: str = '/tmp/ai_models/'):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def register(self, model_id: str, version: str, model_obj: Any,
                 metadata: dict = None) -> str:
        """Model register ও save করো।"""
        path = self._model_path(model_id, version)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        import pickle
        with open(path, 'wb') as f:
            pickle.dump({'model': model_obj, 'metadata': metadata or {}}, f)

        logger.info(f"Model registered: {model_id} v{version} → {path}")
        return path

    def load(self, model_id: str, version: str = 'latest') -> Optional[Any]:
        """Model load করো।"""
        if version == 'latest':
            version = self._get_latest_version(model_id)
            if not version:
                return None

        path = self._model_path(model_id, version)
        if not os.path.exists(path):
            logger.warning(f"Model not found: {path}")
            return None

        import pickle
        with open(path, 'rb') as f:
            data = pickle.load(f)
        return data.get('model')

    def list_versions(self, model_id: str) -> list:
        model_dir = os.path.join(self.base_path, model_id)
        if not os.path.exists(model_dir):
            return []
        return sorted([
            f.replace('.pkl', '')
            for f in os.listdir(model_dir)
            if f.endswith('.pkl')
        ])

    def delete(self, model_id: str, version: str):
        path = self._model_path(model_id, version)
        if os.path.exists(path):
            os.remove(path)
            logger.info(f"Model deleted: {model_id} v{version}")

    def _model_path(self, model_id: str, version: str) -> str:
        return os.path.join(self.base_path, model_id, f"{version}.pkl")

    def _get_latest_version(self, model_id: str) -> Optional[str]:
        versions = self.list_versions(model_id)
        return versions[-1] if versions else None


"""
api/ai_engine/MODEL_STORAGE/model_serializer.py
===============================================
Model Serializer — pickle / joblib / ONNX।
"""

import logging
logger = logging.getLogger(__name__)


class ModelSerializer:
    """Model serialize/deserialize।"""

    FORMATS = ['pickle', 'joblib', 'onnx']

    @staticmethod
    def serialize(model, path: str, fmt: str = 'joblib') -> str:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        if fmt == 'joblib':
            try:
                import joblib
                joblib.dump(model, path)
                return path
            except ImportError:
                pass

        import pickle
        with open(path, 'wb') as f:
            pickle.dump(model, f)
        return path

    @staticmethod
    def deserialize(path: str, fmt: str = 'joblib'):
        if fmt == 'joblib':
            try:
                import joblib
                return joblib.load(path)
            except ImportError:
                pass

        import pickle
        with open(path, 'rb') as f:
            return pickle.load(f)


"""
api/ai_engine/MODEL_STORAGE/model_optimizer.py
===============================================
Model Optimizer — quantization, pruning for faster inference।
"""


class ModelOptimizer:
    """Model size/speed optimization।"""

    def quantize(self, model, method: str = 'dynamic') -> Any:
        """Model quantize করো (PyTorch/TensorFlow)।"""
        try:
            import torch
            if hasattr(model, 'parameters'):
                return torch.quantization.quantize_dynamic(
                    model, {torch.nn.Linear}, dtype=torch.qint8
                )
        except ImportError:
            pass
        return model  # Passthrough if not supported

    def get_model_size_mb(self, path: str) -> float:
        try:
            return round(os.path.getsize(path) / 1024 / 1024, 3)
        except Exception:
            return 0.0
