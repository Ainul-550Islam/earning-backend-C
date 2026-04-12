"""
api/ai_engine/INTEGRATIONS/xgboost_integration.py
==================================================
XGBoost Integration — full training, inference, explanation।
Fraud detection, churn, LTV models এর জন্য।
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class XGBoostIntegration:
    """Full XGBoost integration wrapper।"""

    def __init__(self, task: str = 'classification'):
        self.task  = task
        self.model = None

    def build_classifier(self, params: dict = None) -> Any:
        try:
            import xgboost as xgb
            p = {
                'n_estimators':     params.get('n_estimators', 200) if params else 200,
                'max_depth':        params.get('max_depth', 6) if params else 6,
                'learning_rate':    params.get('learning_rate', 0.05) if params else 0.05,
                'subsample':        params.get('subsample', 0.8) if params else 0.8,
                'colsample_bytree': params.get('colsample_bytree', 0.8) if params else 0.8,
                'use_label_encoder': False,
                'eval_metric':      'logloss',
                'random_state':     42,
                'n_jobs':           -1,
            }
            return xgb.XGBClassifier(**p)
        except ImportError:
            logger.warning("xgboost not installed. pip install xgboost")
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(**(params or {}))

    def build_regressor(self, params: dict = None) -> Any:
        try:
            import xgboost as xgb
            return xgb.XGBRegressor(**(params or {}))
        except ImportError:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(**(params or {}))

    def train(self, model, X_train, y_train, X_val=None, y_val=None,
               early_stopping: int = 20) -> dict:
        """XGBoost model train করো।"""
        try:
            fit_kwargs = {}
            if X_val is not None:
                fit_kwargs['eval_set'] = [(X_val, y_val)]
                fit_kwargs['early_stopping_rounds'] = early_stopping
                fit_kwargs['verbose'] = False
            model.fit(X_train, y_train, **fit_kwargs)
            self.model = model
            return self._eval(model, X_val, y_val)
        except Exception as e:
            return {'error': str(e)}

    def _eval(self, model, X_val, y_val) -> dict:
        if X_val is None or y_val is None:
            return {'trained': True}
        try:
            from sklearn.metrics import f1_score, roc_auc_score
            y_pred = model.predict(X_val)
            y_prob = model.predict_proba(X_val)[:, 1] if hasattr(model, 'predict_proba') else y_pred
            return {
                'f1_score': round(float(f1_score(y_val, y_pred, zero_division=0)), 4),
                'auc_roc':  round(float(roc_auc_score(y_val, y_prob)), 4),
            }
        except Exception:
            return {'trained': True}

    def explain_prediction(self, model, X_sample, feature_names: List[str]) -> dict:
        """SHAP explanation।"""
        try:
            import shap
            import numpy as np
            explainer   = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            mean_abs = abs(shap_values).mean(axis=0)
            pairs    = sorted(zip(feature_names, mean_abs), key=lambda x: x[1], reverse=True)
            return {'top_5': dict(pairs[:5]), 'method': 'shap'}
        except Exception:
            return self._feature_importance_fallback(model, feature_names)

    def _feature_importance_fallback(self, model, feature_names: List[str]) -> dict:
        try:
            imp   = model.feature_importances_
            pairs = sorted(zip(feature_names, imp), key=lambda x: x[1], reverse=True)
            return {'top_5': {k: round(float(v), 6) for k, v in pairs[:5]}, 'method': 'feature_importance'}
        except Exception:
            return {'top_5': {}, 'method': 'unavailable'}

    def get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        try:
            imp  = model.feature_importances_
            return dict(sorted(zip(feature_names, [round(float(i), 6) for i in imp]),
                               key=lambda x: x[1], reverse=True))
        except Exception:
            return {}

    def tune_hyperparams(self, X, y, n_iter: int = 20) -> dict:
        """Quick hyperparameter tuning।"""
        from ..ML_MODELS.hyperparameter_tuner import HyperparameterTuner
        param_grid = {
            'n_estimators':  [100, 200, 300],
            'max_depth':     [4, 6, 8],
            'learning_rate': [0.05, 0.1, 0.15],
        }
        return HyperparameterTuner().tune(
            self.build_classifier, X, y, param_grid, 'random', n_iter
        )
