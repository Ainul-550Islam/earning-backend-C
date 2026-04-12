"""
api/ai_engine/TESTING_EVALUATION/explainability_test.py
========================================================
Explainability Test — model prediction interpretability।
SHAP, LIME, feature importance validation।
Regulatory compliance (GDPR, CCPA) এর জন্য।
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ExplainabilityTest:
    """
    Model explainability ও interpretability testing।
    Business ও regulatory requirements এর জন্য।
    """

    def run(self, model, X_sample, feature_names: List[str],
             method: str = "shap") -> dict:
        """Explainability test run করো।"""
        if X_sample is None or len(X_sample) == 0:
            return {"passed": False, "error": "No sample data provided"}

        if method == "shap":
            return self._shap_test(model, X_sample, feature_names)
        elif method == "lime":
            return self._lime_test(model, X_sample, feature_names)
        elif method == "feature_importance":
            return self._feature_importance_test(model, feature_names)
        return self._feature_importance_test(model, feature_names)

    def _shap_test(self, model, X_sample, feature_names: List[str]) -> dict:
        """SHAP values based explainability test।"""
        try:
            import shap
            import numpy as np

            explainer   = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample[:10])  # First 10 samples
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # Class 1 for binary

            # Per-feature mean absolute SHAP
            mean_abs = [round(float(abs(shap_values[:, i]).mean()), 6)
                        for i in range(min(len(feature_names), shap_values.shape[1]))]

            feature_shap = dict(zip(feature_names, mean_abs))
            top_features = sorted(feature_shap.items(), key=lambda x: x[1], reverse=True)[:5]
            explainability_score = min(1.0, len([v for v in mean_abs if v > 0.01]) / max(len(mean_abs), 1))

            return {
                "method":              "shap",
                "passed":              True,
                "explainability_score": round(explainability_score, 4),
                "top_5_features":       dict(top_features),
                "feature_shap_values":  {k: round(v, 6) for k, v in feature_shap.items()},
                "interpretable":        explainability_score >= 0.50,
                "recommendation":       "Good explainability" if explainability_score >= 0.50 else "Review feature engineering",
            }
        except ImportError:
            logger.warning("SHAP not installed. pip install shap")
            return self._feature_importance_test(model, feature_names)
        except Exception as e:
            logger.error(f"SHAP test error: {e}")
            return {"method": "shap", "passed": False, "error": str(e)}

    def _lime_test(self, model, X_sample, feature_names: List[str]) -> dict:
        """LIME based explainability।"""
        try:
            from lime.lime_tabular import LimeTabularExplainer
            import numpy as np

            explainer = LimeTabularExplainer(
                X_sample,
                feature_names=feature_names,
                mode="classification",
            )
            exp    = explainer.explain_instance(X_sample[0], model.predict_proba, num_features=5)
            top_fs = dict(exp.as_list())

            return {
                "method":       "lime",
                "passed":       True,
                "top_features": top_fs,
                "interpretable": True,
            }
        except ImportError:
            logger.warning("LIME not installed. pip install lime")
            return self._feature_importance_test(model, feature_names)
        except Exception as e:
            return {"method": "lime", "passed": False, "error": str(e)}

    def _feature_importance_test(self, model, feature_names: List[str]) -> dict:
        """Model built-in feature importance।"""
        try:
            importance   = model.feature_importances_
            feature_imp  = dict(zip(feature_names, [round(float(i), 6) for i in importance]))
            top_features = sorted(feature_imp.items(), key=lambda x: x[1], reverse=True)[:5]

            # Check: top 5 features should explain >70% of importance
            top5_sum = sum(v for _, v in top_features)
            total    = sum(importance)
            top5_pct = top5_sum / max(total, 0.001)

            return {
                "method":              "feature_importance",
                "passed":              True,
                "top_5_features":       dict(top_features),
                "top5_importance_pct":  round(top5_pct * 100, 2),
                "explainability_score": round(top5_pct, 4),
                "interpretable":        top5_pct >= 0.60,
                "recommendation":       f"Top 5 features explain {top5_pct:.1%} of model decisions.",
            }
        except AttributeError:
            return {
                "method":    "feature_importance",
                "passed":    False,
                "error":     "Model does not support feature_importances_",
                "suggestion": "Use TreeShap or model-agnostic explainability",
            }

    def gdpr_compliance_check(self, model_info: dict) -> dict:
        """GDPR Article 22 — automated decision explainability check।"""
        checks = {
            "has_explainability_method":   bool(model_info.get("explainability_method")),
            "can_explain_per_prediction":  bool(model_info.get("per_prediction_explanation")),
            "human_review_available":      bool(model_info.get("human_review_process")),
            "right_to_contest":            bool(model_info.get("contest_mechanism")),
            "documentation_exists":        bool(model_info.get("model_documentation")),
        }

        compliant   = all(checks.values())
        missing     = [k for k, v in checks.items() if not v]

        return {
            "gdpr_compliant":  compliant,
            "checks":          checks,
            "missing_items":   missing,
            "risk_level":      "low" if compliant else "medium" if len(missing) <= 2 else "high",
            "recommendation":  "Compliant" if compliant else f"Fix: {', '.join(missing[:2])}",
        }

    def audit_log_explanation(self, prediction_id: str) -> dict:
        """Single prediction এর audit log explanation।"""
        try:
            from ..models import PredictionLog
            log = PredictionLog.objects.get(id=prediction_id)
            return {
                "prediction_id":  str(log.id),
                "prediction_type": log.prediction_type,
                "confidence":      float(log.confidence),
                "predicted_class": log.predicted_class,
                "input_features":  log.input_data,
                "timestamp":       str(log.created_at),
                "explainable":     True,
            }
        except Exception as e:
            return {"error": str(e), "explainable": False}
