"""
api/ai_engine/INTEGRATIONS/lightgbm_integration.py
===================================================
LightGBM Integration — fast gradient boosting।
Large dataset এর জন্য ideal। XGBoost এর faster alternative।
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class LightGBMIntegration:
    """LightGBM model integration wrapper।"""

    def __init__(self, task: str = 'classification'):
        self.task  = task
        self.model = None

    def build_classifier(self, params: dict = None) -> Any:
        try:
            import lightgbm as lgb
            p = {
                'n_estimators':      params.get('n_estimators', 300) if params else 300,
                'num_leaves':        params.get('num_leaves', 63) if params else 63,
                'learning_rate':     params.get('learning_rate', 0.05) if params else 0.05,
                'subsample':         params.get('subsample', 0.8) if params else 0.8,
                'min_child_samples': params.get('min_child_samples', 20) if params else 20,
                'random_state':      42,
                'verbose':           -1,
                'n_jobs':            -1,
            }
            return lgb.LGBMClassifier(**p)
        except ImportError:
            logger.warning("lightgbm not installed. pip install lightgbm")
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(**(params or {}))

    def build_regressor(self, params: dict = None) -> Any:
        try:
            import lightgbm as lgb
            return lgb.LGBMRegressor(**(params or {}))
        except ImportError:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(**(params or {}))

    def train(self, model, X_train, y_train, X_val=None, y_val=None,
               early_stopping: int = 30) -> dict:
        """LightGBM model train করো।"""
        try:
            fit_kwargs = {'callbacks': []}
            if X_val is not None:
                import lightgbm as lgb
                fit_kwargs['eval_set'] = [(X_val, y_val)]
                fit_kwargs['callbacks'] = [lgb.early_stopping(early_stopping, verbose=False),
                                           lgb.log_evaluation(period=-1)]
            model.fit(X_train, y_train, **fit_kwargs)
            self.model = model
            return self._eval(model, X_val, y_val)
        except Exception as e:
            logger.error(f"LightGBM train error: {e}")
            # Retry without callbacks
            try:
                model.fit(X_train, y_train)
                return {'trained': True}
            except Exception as e2:
                return {'error': str(e2)}

    def _eval(self, model, X_val, y_val) -> dict:
        if X_val is None:
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

    def get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        try:
            imp  = model.feature_importances_
            return dict(sorted(zip(feature_names, [round(float(i), 6) for i in imp]),
                               key=lambda x: x[1], reverse=True))
        except Exception:
            return {}

    def optimize_for_speed(self, params: dict = None) -> dict:
        """Speed-optimized LightGBM config।"""
        return {
            'n_estimators':  200,
            'num_leaves':    31,
            'learning_rate': 0.1,
            'n_jobs':        -1,
            'verbose':       -1,
            'max_bin':       63,   # Faster binning
            **(params or {}),
        }

    def optimize_for_accuracy(self, params: dict = None) -> dict:
        """Accuracy-optimized LightGBM config।"""
        return {
            'n_estimators':      500,
            'num_leaves':        127,
            'learning_rate':     0.03,
            'min_child_samples': 10,
            'subsample':         0.7,
            'colsample_bytree':  0.7,
            'reg_alpha':         0.1,
            'reg_lambda':        0.1,
            **(params or {}),
        }
