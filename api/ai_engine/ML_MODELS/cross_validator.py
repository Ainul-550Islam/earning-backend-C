"""
api/ai_engine/ML_MODELS/cross_validator.py
==========================================
Cross Validator — K-Fold cross-validation।
Model reliability, generalization assessment।
"""
import logging
from typing import Dict, List
logger = logging.getLogger(__name__)


class CrossValidator:
    """K-fold cross-validation engine।"""

    def validate(self, model, X, y, cv: int = 5,
                 scoring: str = 'f1_weighted') -> dict:
        """K-fold cross-validation চালাও।"""
        try:
            from sklearn.model_selection import cross_validate
            import numpy as np
            results = cross_validate(
                model, X, y, cv=cv,
                scoring=scoring,
                return_train_score=True,
                n_jobs=-1,
            )
            test_scores  = results['test_score']
            train_scores = results['train_score']
            return {
                'val_mean':    round(float(test_scores.mean()), 4),
                'val_std':     round(float(test_scores.std()), 4),
                'val_min':     round(float(test_scores.min()), 4),
                'val_max':     round(float(test_scores.max()), 4),
                'train_mean':  round(float(train_scores.mean()), 4),
                'train_std':   round(float(train_scores.std()), 4),
                'cv':          cv,
                'scoring':     scoring,
                'all_val_scores': [round(float(s), 4) for s in test_scores],
                'overfit':     bool(train_scores.mean() - test_scores.mean() > 0.15),
                'reliable':    float(test_scores.std()) < 0.10,
            }
        except Exception as e:
            logger.error(f"Cross validation error: {e}")
            return {'error': str(e)}

    def stratified_cv(self, model, X, y, cv: int = 5) -> dict:
        """Stratified K-fold — class balance maintain করে।"""
        try:
            from sklearn.model_selection import StratifiedKFold, cross_val_score
            import numpy as np
            skf    = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)
            scores = cross_val_score(model, X, y, cv=skf, scoring='f1_weighted', n_jobs=-1)
            return {
                'mean':      round(float(scores.mean()), 4),
                'std':       round(float(scores.std()), 4),
                'cv':        cv,
                'method':    'stratified_kfold',
                'scores':    [round(float(s), 4) for s in scores],
                'reliable':  float(scores.std()) < 0.08,
            }
        except Exception as e:
            return {'error': str(e)}

    def time_series_cv(self, model, X, y, n_splits: int = 5) -> dict:
        """Time-series cross-validation — no future leakage।"""
        try:
            from sklearn.model_selection import TimeSeriesSplit, cross_val_score
            import numpy as np
            tscv   = TimeSeriesSplit(n_splits=n_splits)
            scores = cross_val_score(model, X, y, cv=tscv, scoring='f1_weighted')
            return {
                'mean':      round(float(scores.mean()), 4),
                'std':       round(float(scores.std()), 4),
                'n_splits':  n_splits,
                'method':    'time_series_split',
                'scores':    [round(float(s), 4) for s in scores],
            }
        except Exception as e:
            return {'error': str(e)}

    def learning_curve(self, model, X, y,
                        train_sizes: List[float] = None) -> dict:
        """Training size vs score — underfitting/overfitting detect।"""
        try:
            from sklearn.model_selection import learning_curve
            import numpy as np
            sizes = train_sizes or [0.1, 0.25, 0.5, 0.75, 1.0]
            train_s, train_sc, val_sc = learning_curve(
                model, X, y, train_sizes=sizes, cv=3,
                scoring='f1_weighted', n_jobs=-1,
            )
            return {
                'train_sizes':  list(train_s),
                'train_scores': [round(float(s.mean()), 4) for s in train_sc],
                'val_scores':   [round(float(s.mean()), 4) for s in val_sc],
                'converged':    abs(float(train_sc[-1].mean()) - float(val_sc[-1].mean())) < 0.05,
            }
        except Exception as e:
            return {'error': str(e)}
