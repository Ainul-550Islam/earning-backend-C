"""
api/ai_engine/ML_MODELS/model_explainer.py
===========================================
Model Explainer — SHAP, LIME-based prediction explanations।
GDPR Article 22 compliance — explain AI decisions।
"""
import logging
from typing import List, Dict, Optional
logger = logging.getLogger(__name__)


class ModelExplainer:
    """Model prediction explanation engine।"""

    def explain_prediction(self, model, features: dict,
                            feature_names: list = None) -> dict:
        """Single prediction explain করো।"""
        feature_names = feature_names or list(features.keys())
        values        = list(features.values())

        try:
            return self._shap_explain(model, values, feature_names)
        except Exception:
            try:
                return self._feature_importance_explain(model, feature_names)
            except Exception:
                return self._fallback_explain(feature_names)

    def _shap_explain(self, model, values: list,
                       feature_names: List[str]) -> dict:
        """SHAP TreeExplainer।"""
        import shap
        import numpy as np
        X = np.array([values])
        explainer   = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Binary classification: class 1
        explanation = {
            fn: round(float(sv), 4)
            for fn, sv in zip(feature_names, shap_values[0])
        }
        top_features = sorted(explanation.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        return {
            'method':           'shap',
            'feature_contributions': explanation,
            'top_5_features':   dict(top_features),
        }

    def _feature_importance_explain(self, model, feature_names: List[str]) -> dict:
        """Model built-in feature importance।"""
        importance = model.feature_importances_
        pairs      = dict(zip(feature_names, [round(float(i), 6) for i in importance]))
        top        = dict(sorted(pairs.items(), key=lambda x: x[1], reverse=True)[:5])
        return {
            'method':          'feature_importance',
            'top_5_features':  top,
            'all_features':    pairs,
        }

    def _fallback_explain(self, feature_names: List[str]) -> dict:
        return {'method': 'unavailable', 'top_5_features': {},
                'message': 'Install shap for explanations: pip install shap'}

    def global_explanation(self, model, X_sample,
                            feature_names: List[str]) -> dict:
        """Global model behavior explain করো।"""
        try:
            import shap
            import numpy as np
            explainer   = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample[:100])
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            mean_abs = [round(float(abs(shap_values[:, i]).mean()), 6)
                        for i in range(len(feature_names))]
            pairs = sorted(zip(feature_names, mean_abs), key=lambda x: x[1], reverse=True)
            return {
                'method':         'global_shap',
                'feature_impact': dict(pairs),
                'top_10':         dict(pairs[:10]),
                'sample_size':    len(X_sample),
            }
        except Exception as e:
            return {'method': 'error', 'error': str(e)}

    def counterfactual(self, model, instance: dict,
                        feature_names: List[str],
                        target_class: int = 1) -> dict:
        """What needs to change for different prediction?"""
        try:
            import numpy as np
            values      = np.array([list(instance.values())])
            current_pred = int(model.predict(values)[0])
            if current_pred == target_class:
                return {'already_target': True, 'changes_needed': {}}
            importance = dict(zip(feature_names, model.feature_importances_))
            top_feature = max(importance, key=importance.get)
            return {
                'current_prediction': current_pred,
                'target_prediction':  target_class,
                'key_feature_to_change': top_feature,
                'suggestion': f"Adjust {top_feature} to potentially change prediction",
            }
        except Exception as e:
            return {'error': str(e)}
