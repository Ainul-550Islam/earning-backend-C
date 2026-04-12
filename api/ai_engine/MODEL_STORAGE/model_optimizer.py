"""
api/ai_engine/MODEL_STORAGE/model_optimizer.py
===============================================
Model Optimizer — model performance optimization।
Speed optimization, memory reduction, inference acceleration।
"""
import os, logging
from typing import Any, Optional, Dict
logger = logging.getLogger(__name__)

class ModelOptimizer:
    """ML model inference optimization engine।"""

    @staticmethod
    def optimize_for_inference(model: Any, optimization_level: str = "O2") -> Any:
        """Model inference speed optimize করো।"""
        try:
            import torch
            # TorchScript compilation
            try:
                optimized = torch.jit.optimize_for_inference(
                    torch.jit.script(model)
                )
                logger.info("TorchScript inference optimization applied")
                return optimized
            except Exception:
                # Fallback: torch.compile (PyTorch 2.0+)
                try:
                    optimized = torch.compile(model, mode=optimization_level)
                    logger.info(f"torch.compile optimization applied: {optimization_level}")
                    return optimized
                except Exception:
                    pass
        except ImportError:
            pass

        # sklearn: no optimization needed
        logger.info("Model returned as-is (no torch optimization available)")
        return model

    @staticmethod
    def batch_inference_optimize(model: Any, optimal_batch_size: int = 32) -> dict:
        """Optimal batch size find করো।"""
        import time
        batch_sizes = [1, 8, 16, 32, 64, 128]
        results     = []
        for bs in batch_sizes:
            try:
                import numpy as np
                dummy = np.random.randn(bs, 10).astype(float)
                start = time.time()
                for _ in range(5):
                    model.predict(dummy)
                elapsed = (time.time() - start) / 5
                throughput = bs / elapsed
                results.append({"batch_size": bs, "time_ms": round(elapsed*1000, 2),
                                 "throughput": round(throughput, 2)})
            except Exception:
                break
        best = max(results, key=lambda x: x["throughput"]) if results else {"batch_size": 32}
        return {"results": results, "optimal_batch_size": best["batch_size"]}

    @staticmethod
    def cache_predictions(model: Any, cache_ttl: int = 300) -> dict:
        """Prediction caching setup।"""
        from django.core.cache import cache
        def cached_predict(input_key: str, input_data):
            cache_key = f"model_pred:{hash(str(input_data))}"
            cached    = cache.get(cache_key)
            if cached is not None:
                return {"prediction": cached, "cached": True}
            prediction = model.predict(input_data)
            cache.set(cache_key, prediction, cache_ttl)
            return {"prediction": prediction, "cached": False}
        return {"cached_predict_fn": cached_predict, "ttl": cache_ttl}

    @staticmethod
    def warm_up(model: Any, n_warmup: int = 10) -> dict:
        """Model warm up — cold start latency এড়াতে।"""
        import time, numpy as np
        dummy = np.random.randn(1, 10).astype(float)
        times = []
        for _ in range(n_warmup):
            start = time.time()
            try:
                model.predict(dummy)
            except Exception:
                break
            times.append((time.time() - start) * 1000)
        return {
            "warmup_requests": len(times),
            "avg_ms":          round(sum(times)/max(len(times),1), 2),
            "last_ms":         round(times[-1], 2) if times else 0,
        }

    @staticmethod
    def memory_profile(model: Any) -> dict:
        """Model memory usage profile।"""
        try:
            import tracemalloc
            tracemalloc.start()
            import numpy as np
            dummy = np.random.randn(100, 10)
            model.predict(dummy)
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            return {
                "current_mb": round(current / 1024 / 1024, 3),
                "peak_mb":    round(peak    / 1024 / 1024, 3),
            }
        except Exception as e:
            return {"error": str(e)}
