"""
api/ai_engine/MODEL_STORAGE/model_converter.py
===============================================
Model Converter — format conversion।
sklearn → ONNX, PyTorch → TorchScript/ONNX।
Cross-platform deployment preparation।
"""
import os, logging
from typing import Any, Optional
logger = logging.getLogger(__name__)

class ModelConverter:
    """ML model format converter।"""

    @staticmethod
    def sklearn_to_onnx(model: Any, input_shape: tuple,
                         output_path: str,
                         feature_names: list = None) -> str:
        try:
            import skl2onnx
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType
            n_features = input_shape[1] if len(input_shape) > 1 else input_shape[0]
            initial_type = [("float_input", FloatTensorType([None, n_features]))]
            onx = convert_sklearn(model, initial_types=initial_type,
                                   options={type(model): {"zipmap": False}})
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(onx.SerializeToString())
            logger.info(f"sklearn → ONNX: {output_path}")
            return output_path
        except ImportError:
            logger.warning("skl2onnx not installed: pip install skl2onnx")
            return ""
        except Exception as e:
            logger.error(f"ONNX conversion error: {e}")
            return ""

    @staticmethod
    def pytorch_to_torchscript(model: Any, example_input: Any,
                                output_path: str) -> str:
        try:
            import torch
            model.eval()
            script = torch.jit.trace(model, example_input)
            script.save(output_path)
            logger.info(f"PyTorch → TorchScript: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"TorchScript conversion error: {e}")
            return ""

    @staticmethod
    def pytorch_to_onnx(model: Any, example_input: Any,
                         output_path: str, input_names: list = None,
                         output_names: list = None) -> str:
        try:
            import torch
            model.eval()
            torch.onnx.export(
                model, example_input, output_path,
                input_names=input_names or ["input"],
                output_names=output_names or ["output"],
                dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
                opset_version=11,
            )
            logger.info(f"PyTorch → ONNX: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"PyTorch ONNX error: {e}")
            return ""

    @staticmethod
    def onnx_to_tflite(onnx_path: str, output_path: str) -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-m", "tf2onnx.convert", "--onnx", onnx_path, "--output", output_path],
                capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                return output_path
            logger.error(f"ONNX → TFLite failed: {result.stderr}")
            return ""
        except Exception as e:
            logger.error(f"ONNX→TFLite error: {e}")
            return ""

    @staticmethod
    def get_model_info(path: str) -> dict:
        if not os.path.exists(path): return {"exists": False}
        ext  = os.path.splitext(path)[1].lower()
        info = {"path": path, "format": ext, "size_mb": round(os.path.getsize(path) / 1024 / 1024, 3)}
        if ext == ".onnx":
            try:
                import onnx
                model = onnx.load(path)
                info["onnx_version"] = model.opset_import[0].version
                info["inputs"]  = [i.name for i in model.graph.input]
                info["outputs"] = [o.name for o in model.graph.output]
            except Exception:
                pass
        return info
