"""
api/ai_engine/ML_MODELS/data_normalizer.py
==========================================
Data Normalizer — feature scaling ও normalization।
StandardScaler, MinMaxScaler, RobustScaler, Log transform।
ML model training এর আগে features normalize করো।
"""

import logging
import math
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class DataNormalizer:
    """
    Feature normalization engine।
    Multiple scaling strategies support করে।
    """

    METHODS = ['standard', 'minmax', 'robust', 'log', 'l2', 'maxabs']

    def __init__(self, method: str = 'standard'):
        self.method  = method
        self.scaler  = None
        self._fitted = False
        self._stats: Dict = {}   # For manual implementation fallback

    def fit_transform(self, X) -> Any:
        """Fit + transform একসাথে।"""
        try:
            from sklearn.preprocessing import (
                StandardScaler, MinMaxScaler, RobustScaler,
                MaxAbsScaler, Normalizer
            )
            scalers = {
                'standard': StandardScaler(),
                'minmax':   MinMaxScaler(feature_range=(0, 1)),
                'robust':   RobustScaler(),
                'maxabs':   MaxAbsScaler(),
                'l2':       Normalizer(norm='l2'),
            }

            if self.method == 'log':
                return self._log_transform(X, fit=True)

            self.scaler  = scalers.get(self.method, StandardScaler())
            result       = self.scaler.fit_transform(X)
            self._fitted = True
            return result

        except ImportError:
            logger.warning("scikit-learn not available — using manual scaling")
            return self._manual_scale(X, fit=True)
        except Exception as e:
            logger.error(f"Normalize error: {e}")
            return X

    def transform(self, X) -> Any:
        """Already fitted scaler দিয়ে new data transform।"""
        if not self._fitted:
            logger.warning("Scaler not fitted — calling fit_transform")
            return self.fit_transform(X)

        try:
            if self.method == 'log':
                return self._log_transform(X, fit=False)
            if self.scaler:
                return self.scaler.transform(X)
            return self._manual_scale(X, fit=False)
        except Exception as e:
            logger.error(f"Transform error: {e}")
            return X

    def inverse_transform(self, X) -> Any:
        """Normalize উল্টো করো — original scale এ ফিরিয়ে আনো।"""
        try:
            if self.scaler and hasattr(self.scaler, 'inverse_transform'):
                return self.scaler.inverse_transform(X)
            logger.warning("Inverse transform not available for this method")
            return X
        except Exception as e:
            logger.error(f"Inverse transform error: {e}")
            return X

    def _log_transform(self, X, fit: bool = True) -> Any:
        """Log1p transformation (non-negative values)।"""
        try:
            import numpy as np
            arr = np.array(X, dtype=float)
            # Shift to non-negative
            if fit:
                self._stats['min_vals'] = arr.min(axis=0)
            shift = self._stats.get('min_vals', 0)
            arr   = arr - shift + 1  # Shift to ≥1
            return np.log1p(arr)
        except Exception as e:
            logger.error(f"Log transform error: {e}")
            return X

    def _manual_scale(self, X, fit: bool = True) -> Any:
        """Manual StandardScaler implementation (no sklearn)।"""
        try:
            import numpy as np
            arr = np.array(X, dtype=float)
            if fit:
                self._stats['mean'] = arr.mean(axis=0)
                self._stats['std']  = arr.std(axis=0)
                self._stats['std']  = np.where(self._stats['std'] == 0, 1, self._stats['std'])
                self._fitted = True
            mean = self._stats.get('mean', 0)
            std  = self._stats.get('std', 1)
            return (arr - mean) / std
        except Exception as e:
            return X

    def get_scaling_params(self) -> dict:
        """Fitted scaler parameters return করো।"""
        if not self._fitted:
            return {'fitted': False}
        params = {'fitted': True, 'method': self.method}
        if self.scaler:
            if hasattr(self.scaler, 'mean_'):
                params['mean'] = self.scaler.mean_.tolist()
            if hasattr(self.scaler, 'scale_'):
                params['scale'] = self.scaler.scale_.tolist()
            if hasattr(self.scaler, 'data_min_'):
                params['data_min'] = self.scaler.data_min_.tolist()
                params['data_max'] = self.scaler.data_max_.tolist()
        return params

    def detect_scaling_issues(self, X) -> dict:
        """Data scaling issues detect করো।"""
        try:
            import numpy as np
            arr = np.array(X, dtype=float)
            issues = []

            # Check for extreme values
            max_val = abs(arr).max()
            if max_val > 1e6:
                issues.append(f"Extreme values detected (max={max_val:.2e}) — log scaling recommended")

            # Check for zero variance columns
            std_vals = arr.std(axis=0)
            zero_var = (std_vals == 0).sum()
            if zero_var > 0:
                issues.append(f"{zero_var} zero-variance columns — will cause NaN after StandardScaling")

            # Check for very skewed distributions
            means = arr.mean(axis=0)
            stds  = arr.std(axis=0)
            skew_cols = sum(1 for m, s in zip(means, stds) if s > 0 and abs(m) > 10 * s)
            if skew_cols > 0:
                issues.append(f"{skew_cols} highly skewed columns — RobustScaler recommended")

            return {
                'issues':     issues,
                'has_issues': len(issues) > 0,
                'recommended_method': self._recommend_method(max_val, zero_var, skew_cols),
                'shape':      arr.shape,
            }
        except Exception as e:
            return {'error': str(e)}

    def _recommend_method(self, max_val, zero_var, skew_cols) -> str:
        if max_val > 1e6:           return 'log'
        if skew_cols > 3:           return 'robust'
        if zero_var > 0:            return 'minmax'
        return 'standard'

    def normalize_single(self, values: List[float]) -> List[float]:
        """Single feature list normalize করো (no sklearn needed)।"""
        if not values:
            return values
        mean = sum(values) / len(values)
        std  = math.sqrt(sum((v - mean) ** 2 for v in values) / max(len(values) - 1, 1)) or 1.0
        return [round((v - mean) / std, 6) for v in values]

    def minmax_single(self, values: List[float],
                       feature_range: tuple = (0, 1)) -> List[float]:
        """Single list को MinMax normalize करो।"""
        if not values:
            return values
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            return [0.5] * len(values)
        lo, hi = feature_range
        return [round(lo + (v - min_v) / (max_v - min_v) * (hi - lo), 6) for v in values]
