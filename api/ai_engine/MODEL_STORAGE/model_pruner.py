"""
api/ai_engine/MODEL_STORAGE/model_pruner.py
============================================
Model Pruner — neural network pruning।
Weight pruning, structured pruning, magnitude-based।
Reduce model complexity, faster inference।
"""
import logging
from typing import Any, Optional, List, Dict
logger = logging.getLogger(__name__)

class ModelPruner:
    """Neural network pruning engine।"""

    @staticmethod
    def magnitude_prune_pytorch(model: Any, sparsity: float = 0.5) -> Any:
        """Magnitude-based weight pruning।"""
        try:
            import torch
            import torch.nn.utils.prune as prune
            for name, module in model.named_modules():
                if isinstance(module, torch.nn.Linear):
                    prune.l1_unstructured(module, name="weight", amount=sparsity)
                    prune.remove(module, "weight")   # Make permanent
            logger.info(f"Magnitude pruning applied: {sparsity:.0%} sparsity")
            return model
        except Exception as e:
            logger.error(f"Pruning error: {e}")
            return model

    @staticmethod
    def structured_prune(model: Any, n_heads_to_prune: int = 2) -> Any:
        """Structured pruning (attention heads, filters)।"""
        try:
            import torch
            import torch.nn.utils.prune as prune
            for name, module in model.named_modules():
                if isinstance(module, torch.nn.Conv2d):
                    prune.ln_structured(module, name="weight",
                                         amount=n_heads_to_prune, n=2, dim=0)
            logger.info(f"Structured pruning applied: {n_heads_to_prune} filters pruned")
            return model
        except Exception as e:
            logger.error(f"Structured pruning error: {e}")
            return model

    @staticmethod
    def sklearn_feature_pruning(model: Any, feature_names: List[str],
                                 importance_threshold: float = 0.01) -> dict:
        """sklearn model এর less important features prune করো।"""
        try:
            importances = model.feature_importances_
            to_keep     = [i for i, imp in enumerate(importances) if imp >= importance_threshold]
            pruned      = [feature_names[i] for i in range(len(feature_names)) if i not in to_keep]
            return {
                "features_kept":   [feature_names[i] for i in to_keep],
                "features_pruned": pruned,
                "reduction_pct":   round(len(pruned) / max(len(feature_names), 1) * 100, 2),
                "keep_indices":    to_keep,
            }
        except AttributeError:
            return {"error": "Model does not support feature_importances_"}

    @staticmethod
    def compute_sparsity(model: Any) -> dict:
        """Model sparsity compute করো।"""
        try:
            import torch
            total    = 0
            zero     = 0
            for _, param in model.named_parameters():
                total += param.numel()
                zero  += (param.data == 0).sum().item()
            sparsity = zero / max(total, 1)
            return {
                "total_params":     total,
                "zero_params":      zero,
                "sparsity":         round(sparsity, 4),
                "density":          round(1 - sparsity, 4),
                "effective_params": total - zero,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def iterative_prune(model: Any, target_sparsity: float = 0.80,
                         n_iterations: int = 5) -> Any:
        """Progressive pruning — gradual sparsity increase।"""
        per_iter = target_sparsity / n_iterations
        for i in range(n_iterations):
            current_sparsity = per_iter * (i + 1)
            model = ModelPruner.magnitude_prune_pytorch(model, current_sparsity)
            logger.info(f"Pruning iteration {i+1}/{n_iterations}: {current_sparsity:.0%}")
        return model
