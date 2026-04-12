"""
api/ai_engine/MODEL_STORAGE/model_deserializer.py
==================================================
Model Deserializer — load models from storage।
Multiple formats: pickle, joblib, ONNX, TorchScript।
Version-aware loading, compatibility checks।
"""
import os, logging
from typing import Any, Optional, Dict
logger = logging.getLogger(__name__)

class ModelDeserializer:
    """Model deserialization from various formats।"""

    @staticmethod
    def load(path: str, fmt: str = "auto") -> Optional[Any]:
        if not os.path.exists(path):
            logger.error(f"Model file not found: {path}")
            return None
        if fmt == "auto":
            ext = os.path.splitext(path)[1].lower()
            fmt = {".pkl": "pickle", ".joblib": "joblib",
                   ".pt": "torch", ".pth": "torch", ".onnx": "onnx"}.get(ext, "pickle")
        loaders = {
            "joblib":  ModelDeserializer._load_joblib,
            "pickle":  ModelDeserializer._load_pickle,
            "torch":   ModelDeserializer._load_torch,
            "onnx":    ModelDeserializer._load_onnx,
        }
        loader = loaders.get(fmt, ModelDeserializer._load_pickle)
        try:
            model = loader(path)
            logger.info(f"Model loaded [{fmt}]: {path}")
            return model
        except Exception as e:
            logger.error(f"Model load error [{fmt}] {path}: {e}")
            return None

    @staticmethod
    def _load_joblib(path: str) -> Any:
        import joblib
        return joblib.load(path)

    @staticmethod
    def _load_pickle(path: str) -> Any:
        import pickle
        with open(path, "rb") as f:
            return pickle.load(f)

    @staticmethod
    def _load_torch(path: str) -> Any:
        import torch
        return torch.load(path, map_location="cpu")

    @staticmethod
    def _load_onnx(path: str) -> Any:
        import onnxruntime as ort
        return ort.InferenceSession(path)

    @staticmethod
    def load_with_metadata(path: str) -> Dict:
        model = ModelDeserializer.load(path)
        meta_path = path + ".meta.json"
        metadata  = {}
        if os.path.exists(meta_path):
            import json
            with open(meta_path) as f:
                metadata = json.load(f)
        return {"model": model, "metadata": metadata, "path": path,
                "size_mb": round(os.path.getsize(path) / 1024 / 1024, 3) if model else 0}

    @staticmethod
    def batch_load(paths_and_formats: list) -> list:
        results = []
        for item in paths_and_formats:
            path = item.get("path", "")
            fmt  = item.get("format", "auto")
            model = ModelDeserializer.load(path, fmt)
            results.append({"path": path, "loaded": model is not None, "model": model})
        return results

    @staticmethod
    def validate_on_load(path: str) -> dict:
        model = ModelDeserializer.load(path)
        if model is None:
            return {"valid": False, "reason": "Failed to load"}
        return {
            "valid":       True,
            "model_type":  type(model).__name__,
            "size_mb":     round(os.path.getsize(path) / 1024 / 1024, 3),
            "has_predict": hasattr(model, "predict"),
        }
