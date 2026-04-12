"""
api/ai_engine/MODEL_STORAGE/model_quantizer.py
===============================================
Model Quantizer — precision reduction for deployment।
INT8, FP16 quantization। 4x smaller, 2-4x faster।
Mobile, edge device deployment preparation।
"""
import os, logging
from typing import Any, Optional
logger = logging.getLogger(__name__)

class ModelQuantizer:
    """Neural network quantization engine।"""

    @staticmethod
    def quantize_pytorch(model: Any, calibration_data=None,
                          method: str = "dynamic") -> Any:
        try:
            import torch
            if method == "dynamic":
                quantized = torch.quantization.quantize_dynamic(
                    model,
                    {torch.nn.Linear, torch.nn.LSTM},
                    dtype=torch.qint8,
                )
                logger.info("Dynamic quantization applied (INT8)")
                return quantized
            elif method == "static" and calibration_data is not None:
                model.qconfig = torch.quantization.get_default_qconfig("fbgemm")
                torch.quantization.prepare(model, inplace=True)
                with torch.no_grad():
                    for batch in calibration_data:
                        model(batch)
                torch.quantization.convert(model, inplace=True)
                logger.info("Static quantization applied (INT8)")
                return model
            return model
        except Exception as e:
            logger.error(f"PyTorch quantization error: {e}")
            return model

    @staticmethod
    def quantize_onnx(input_path: str, output_path: str,
                       quantize_type: str = "int8") -> str:
        try:
            from onnxruntime.quantization import quantize_dynamic, QuantType
            qt = QuantType.QInt8 if quantize_type == "int8" else QuantType.QUInt8
            quantize_dynamic(input_path, output_path, weight_type=qt)
            orig_mb = os.path.getsize(input_path)  / 1024 / 1024
            quant_mb = os.path.getsize(output_path) / 1024 / 1024
            logger.info(f"ONNX quantized {orig_mb:.2f}MB → {quant_mb:.2f}MB")
            return output_path
        except ImportError:
            logger.warning("onnxruntime-tools not installed")
            return ""
        except Exception as e:
            logger.error(f"ONNX quantization error: {e}")
            return ""

    @staticmethod
    def fp16_convert_pytorch(model: Any) -> Any:
        """FP32 → FP16 (half precision)।"""
        try:
            return model.half()
        except Exception as e:
            logger.error(f"FP16 conversion error: {e}")
            return model

    @staticmethod
    def estimate_speedup(original_path: str, quantized_path: str) -> dict:
        if not os.path.exists(original_path) or not os.path.exists(quantized_path):
            return {}
        orig_mb  = os.path.getsize(original_path)  / 1024 / 1024
        quant_mb = os.path.getsize(quantized_path) / 1024 / 1024
        size_ratio = orig_mb / max(quant_mb, 0.001)
        return {
            "original_mb":    round(orig_mb, 3),
            "quantized_mb":   round(quant_mb, 3),
            "size_reduction": round(size_ratio, 2),
            "estimated_speedup": f"{size_ratio:.1f}x",
            "latency_reduction_pct": round((1 - 1/size_ratio) * 100, 1),
        }
