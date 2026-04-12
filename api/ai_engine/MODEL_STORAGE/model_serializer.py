"""
api/ai_engine/MODEL_STORAGE/model_serializer.py
===============================================
Model Serializer — model save/load in multiple formats।
pickle, joblib, ONNX, TorchScript formats।
Production deployment ও model exchange এর জন্য।
"""

import os
import logging
from typing import Any, Optional, Dict

logger = logging.getLogger(__name__)


class ModelSerializer:
    """
    ML model serialization/deserialization।
    Supports: pickle, joblib, onnx, torch।
    """

    SUPPORTED_FORMATS = ['pickle', 'joblib', 'onnx', 'torch', 'sklearn']

    @staticmethod
    def serialize(model: Any, path: str, fmt: str = 'joblib') -> str:
        """Model serialize করে file এ save করো।"""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)

        if fmt == 'joblib':
            try:
                import joblib
                joblib.dump(model, path)
                logger.info(f"Model saved (joblib): {path}")
                return path
            except ImportError:
                logger.warning("joblib not installed — using pickle")

        if fmt in ('pickle', 'joblib'):
            import pickle
            with open(path, 'wb') as f:
                pickle.dump(model, f, protocol=4)
            logger.info(f"Model saved (pickle): {path}")
            return path

        if fmt == 'torch':
            try:
                import torch
                torch.save(model.state_dict(), path)
                logger.info(f"Model saved (torch): {path}")
                return path
            except Exception as e:
                logger.error(f"Torch save error: {e}")
                return ''

        if fmt == 'onnx':
            return ModelSerializer._save_onnx(model, path)

        # Default: pickle
        import pickle
        with open(path, 'wb') as f:
            pickle.dump(model, f, protocol=4)
        return path

    @staticmethod
    def deserialize(path: str, fmt: str = 'auto') -> Optional[Any]:
        """Model file থেকে load করো।"""
        if not os.path.exists(path):
            logger.error(f"Model file not found: {path}")
            return None

        # Auto-detect format
        if fmt == 'auto':
            ext = os.path.splitext(path)[1].lower()
            fmt_map = {'.pkl': 'pickle', '.joblib': 'joblib',
                       '.pt': 'torch', '.pth': 'torch', '.onnx': 'onnx'}
            fmt = fmt_map.get(ext, 'pickle')

        if fmt == 'joblib':
            try:
                import joblib
                model = joblib.load(path)
                logger.info(f"Model loaded (joblib): {path}")
                return model
            except ImportError:
                pass

        if fmt in ('pickle', 'joblib'):
            import pickle
            with open(path, 'rb') as f:
                model = pickle.load(f)
            logger.info(f"Model loaded (pickle): {path}")
            return model

        if fmt == 'torch':
            try:
                import torch
                return torch.load(path, map_location='cpu')
            except Exception as e:
                logger.error(f"Torch load error: {e}")
                return None

        if fmt == 'onnx':
            return ModelSerializer._load_onnx(path)

        import pickle
        with open(path, 'rb') as f:
            return pickle.load(f)

    @staticmethod
    def _save_onnx(model, path: str) -> str:
        """ONNX format এ save করো।"""
        try:
            import skl2onnx
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType

            initial_type = [('float_input', FloatTensorType([None, 10]))]
            onx = convert_sklearn(model, initial_types=initial_type)
            with open(path, 'wb') as f:
                f.write(onx.SerializeToString())
            logger.info(f"ONNX model saved: {path}")
            return path
        except ImportError:
            logger.warning("skl2onnx not installed. pip install skl2onnx")
            return ModelSerializer.serialize(model, path + '.pkl', 'pickle')
        except Exception as e:
            logger.error(f"ONNX save error: {e}")
            return ''

    @staticmethod
    def _load_onnx(path: str) -> Optional[Any]:
        """ONNX model load করো।"""
        try:
            import onnxruntime as ort
            session = ort.InferenceSession(path)
            logger.info(f"ONNX model loaded: {path}")
            return session
        except ImportError:
            logger.warning("onnxruntime not installed. pip install onnxruntime")
            return None
        except Exception as e:
            logger.error(f"ONNX load error: {e}")
            return None

    @staticmethod
    def get_model_info(path: str) -> Dict:
        """Model file এর metadata।"""
        if not os.path.exists(path):
            return {'exists': False}

        stat = os.stat(path)
        ext  = os.path.splitext(path)[1].lower()

        info = {
            'exists':    True,
            'path':      path,
            'size_mb':   round(stat.st_size / 1024 / 1024, 3),
            'format':    ext.lstrip('.'),
            'modified':  str(stat.st_mtime),
        }

        # Try to get sklearn model info
        if ext in ('.pkl', '.joblib'):
            try:
                model = ModelSerializer.deserialize(path, 'auto')
                info['model_type'] = type(model).__name__
                if hasattr(model, 'n_estimators'):
                    info['n_estimators'] = model.n_estimators
                if hasattr(model, 'feature_importances_'):
                    info['n_features'] = len(model.feature_importances_)
            except Exception:
                pass

        return info

    @staticmethod
    def compress(input_path: str, output_path: str = None) -> str:
        """Model compress করো (gzip)।"""
        import gzip, shutil
        output_path = output_path or input_path + '.gz'
        with open(input_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        size_orig = os.path.getsize(input_path) / 1024 / 1024
        size_comp = os.path.getsize(output_path) / 1024 / 1024
        ratio     = round(size_comp / max(size_orig, 0.001) * 100, 2)
        logger.info(f"Compressed: {size_orig:.2f}MB → {size_comp:.2f}MB ({ratio}% ratio)")
        return output_path

    @staticmethod
    def decompress(input_path: str, output_path: str = None) -> str:
        """Compressed model decompress করো।"""
        import gzip, shutil
        output_path = output_path or input_path.replace('.gz', '')
        with gzip.open(input_path, 'rb') as f_in:
            with open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return output_path

    @staticmethod
    def validate_model_file(path: str) -> dict:
        """Model file valid ও loadable কিনা check করো।"""
        if not os.path.exists(path):
            return {'valid': False, 'reason': 'File not found'}

        if os.path.getsize(path) == 0:
            return {'valid': False, 'reason': 'Empty file'}

        try:
            model = ModelSerializer.deserialize(path, 'auto')
            if model is None:
                return {'valid': False, 'reason': 'Failed to deserialize'}
            return {
                'valid':      True,
                'model_type': type(model).__name__,
                'size_mb':    round(os.path.getsize(path) / 1024 / 1024, 3),
            }
        except Exception as e:
            return {'valid': False, 'reason': str(e)}

    @staticmethod
    def copy_model(src_path: str, dst_path: str) -> str:
        """Model file copy করো।"""
        import shutil
        os.makedirs(os.path.dirname(dst_path) or '.', exist_ok=True)
        shutil.copy2(src_path, dst_path)
        logger.info(f"Model copied: {src_path} → {dst_path}")
        return dst_path
