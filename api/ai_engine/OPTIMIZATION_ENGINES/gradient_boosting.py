"""
api/ai_engine/OPTIMIZATION_ENGINES/gradient_boosting.py
========================================================
Gradient Boosting Engine — unified XGBoost/LightGBM/sklearn interface।
Fraud detection, churn prediction, LTV modeling এর জন্য।
Auto-tuning, cross-validation, feature importance সহ।
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GradientBoostingOptimizer:
    """
    Unified gradient boosting interface।
    Automatically picks best available library:
    XGBoost → LightGBM → sklearn GBM।
    """

    SUPPORTED_LIBRARIES = ['xgboost', 'lightgbm', 'sklearn']

    def __init__(self, library: str = 'auto', task: str = 'classification'):
        self.library  = library
        self.task     = task
        self.model    = None
        self._lib     = None

    def build(self, params: dict = None) -> Any:
        """Best available library দিয়ে model build করো।"""
        params = params or {}
        if self.library == 'auto':
            return self._auto_build(params)
        return self._build_specific(self.library, params)

    def _auto_build(self, params: dict) -> Any:
        """Available library auto-detect করো।"""
        for lib in self.SUPPORTED_LIBRARIES:
            model = self._build_specific(lib, params)
            if model is not None:
                self._lib = lib
                logger.info(f"Using {lib} for gradient boosting")
                return model
        raise ImportError("No gradient boosting library available. pip install xgboost or lightgbm")

    def _build_specific(self, library: str, params: dict) -> Optional[Any]:
        """Specific library দিয়ে model build।"""
        defaults = {
            'n_estimators':     params.get('n_estimators', 200),
            'max_depth':        params.get('max_depth', 6),
            'learning_rate':    params.get('learning_rate', 0.05),
            'subsample':        params.get('subsample', 0.8),
            'random_state':     42,
        }

        if library == 'xgboost':
            try:
                import xgboost as xgb
                if self.task == 'classification':
                    return xgb.XGBClassifier(
                        **defaults,
                        colsample_bytree=params.get('colsample_bytree', 0.8),
                        use_label_encoder=False,
                        eval_metric='logloss',
                        n_jobs=-1,
                    )
                return xgb.XGBRegressor(**defaults, n_jobs=-1)
            except ImportError:
                return None

        elif library == 'lightgbm':
            try:
                import lightgbm as lgb
                lgb_params = {
                    'n_estimators':  defaults['n_estimators'],
                    'max_depth':     defaults['max_depth'],
                    'learning_rate': defaults['learning_rate'],
                    'subsample':     defaults['subsample'],
                    'num_leaves':    params.get('num_leaves', 31),
                    'random_state':  42,
                    'verbose':       -1,
                    'n_jobs':        -1,
                }
                if self.task == 'classification':
                    return lgb.LGBMClassifier(**lgb_params)
                return lgb.LGBMRegressor(**lgb_params)
            except ImportError:
                return None

        elif library == 'sklearn':
            try:
                if self.task == 'classification':
                    from sklearn.ensemble import GradientBoostingClassifier
                    return GradientBoostingClassifier(
                        n_estimators=defaults['n_estimators'],
                        max_depth=defaults['max_depth'],
                        learning_rate=defaults['learning_rate'],
                        subsample=defaults['subsample'],
                        random_state=42,
                    )
                from sklearn.ensemble import GradientBoostingRegressor
                return GradientBoostingRegressor(
                    n_estimators=defaults['n_estimators'],
                    max_depth=defaults['max_depth'],
                    learning_rate=defaults['learning_rate'],
                    subsample=defaults['subsample'],
                    random_state=42,
                )
            except ImportError:
                return None

        return None

    def train(self, X_train, y_train, X_val=None, y_val=None,
               params: dict = None, early_stopping: int = 20) -> dict:
        """Model train করো এবং metrics return করো।"""
        self.model = self.build(params or {})
        if self.model is None:
            return {'error': 'No model built'}

        try:
            fit_params = {}
            if X_val is not None and self._lib in ('xgboost', 'lightgbm'):
                fit_params['eval_set'] = [(X_val, y_val)]
                if self._lib == 'xgboost':
                    fit_params['early_stopping_rounds'] = early_stopping
                    fit_params['verbose'] = False
                elif self._lib == 'lightgbm':
                    fit_params['callbacks'] = []

            self.model.fit(X_train, y_train, **fit_params)
            return self._compute_metrics(X_val, y_val)

        except Exception as e:
            logger.error(f"GBM training error: {e}")
            return {'error': str(e)}

    def _compute_metrics(self, X_val, y_val) -> dict:
        """Validation metrics compute করো।"""
        if X_val is None or y_val is None or self.model is None:
            return {}
        try:
            from sklearn.metrics import (
                accuracy_score, f1_score, roc_auc_score, mean_squared_error
            )
            import numpy as np

            y_pred = self.model.predict(X_val)

            if self.task == 'classification':
                y_prob = self.model.predict_proba(X_val)[:, 1] if hasattr(self.model, 'predict_proba') else y_pred
                return {
                    'accuracy': round(float(accuracy_score(y_val, y_pred)), 4),
                    'f1_score': round(float(f1_score(y_val, y_pred, zero_division=0)), 4),
                    'auc_roc':  round(float(roc_auc_score(y_val, y_prob)), 4),
                }
            rmse = float(np.sqrt(mean_squared_error(y_val, y_pred)))
            return {'rmse': round(rmse, 4)}

        except Exception as e:
            return {'metrics_error': str(e)}

    def predict(self, X) -> dict:
        """Single/batch prediction।"""
        if self.model is None:
            return {'error': 'Model not trained'}
        try:
            preds = self.model.predict(X)
            result = {'predictions': preds.tolist() if hasattr(preds, 'tolist') else list(preds)}
            if self.task == 'classification' and hasattr(self.model, 'predict_proba'):
                probs = self.model.predict_proba(X)
                result['probabilities'] = probs.tolist() if hasattr(probs, 'tolist') else list(probs)
            return result
        except Exception as e:
            return {'error': str(e)}

    def feature_importance(self, feature_names: List[str]) -> Dict[str, float]:
        """Feature importance rankings।"""
        if self.model is None:
            return {}
        try:
            importance = self.model.feature_importances_
            pairs = sorted(
                zip(feature_names, [round(float(i), 6) for i in importance]),
                key=lambda x: x[1], reverse=True
            )
            return dict(pairs)
        except AttributeError:
            return {}

    def cross_validate(self, X, y, cv: int = 5) -> dict:
        """K-fold cross-validation।"""
        model_factory = lambda: self.build()
        try:
            from sklearn.model_selection import cross_val_score
            import numpy as np
            model = model_factory()
            scoring = 'f1_weighted' if self.task == 'classification' else 'neg_root_mean_squared_error'
            scores  = cross_val_score(model, X, y, cv=cv, scoring=scoring, n_jobs=-1)
            return {
                'cv_scores': [round(float(s), 4) for s in scores],
                'mean':      round(float(scores.mean()), 4),
                'std':       round(float(scores.std()), 4),
                'cv':        cv,
            }
        except Exception as e:
            return {'error': str(e)}

    def get_params(self) -> dict:
        """Current model parameters।"""
        if self.model is None:
            return {}
        try:
            return self.model.get_params()
        except Exception:
            return {}

    def suggest_hyperparams(self, dataset_size: int, n_features: int) -> dict:
        """Dataset size অনুযায়ী hyperparameter suggestions।"""
        if dataset_size < 1000:
            return {'n_estimators': 100, 'max_depth': 4, 'learning_rate': 0.1}
        elif dataset_size < 100000:
            return {'n_estimators': 300, 'max_depth': 6, 'learning_rate': 0.05}
        else:
            return {
                'n_estimators': 500,
                'max_depth':    8,
                'learning_rate': 0.03,
                'subsample':    0.7,
                'colsample_bytree': 0.7,
            }
