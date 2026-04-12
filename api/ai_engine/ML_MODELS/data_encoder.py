"""
api/ai_engine/ML_MODELS/data_encoder.py
=======================================
Data Encoder — categorical feature encoding।
Label encoding, one-hot, target encoding, frequency encoding।
High-cardinality ও ordinal features handle করো।
"""

import logging
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)


class DataEncoder:
    """
    Categorical feature encoder।
    Methods: label, onehot, ordinal, target, frequency, binary।
    """

    SUPPORTED_METHODS = ['label', 'onehot', 'ordinal', 'target', 'frequency', 'binary', 'hash']

    def __init__(self, method: str = 'label', handle_unknown: str = 'ignore'):
        self.method         = method
        self.handle_unknown = handle_unknown
        self.encoders: Dict = {}
        self.category_maps: Dict = {}
        self.target_means: Dict  = {}

    def fit_transform(self, df, cat_columns: List[str],
                       target_col: str = None) -> Any:
        """Fit ও transform categoricals।"""
        try:
            import pandas as pd

            result = df.copy()
            for col in cat_columns:
                if col not in result.columns:
                    continue
                result = self._encode_column(result, col, target_col, fit=True)
            return result

        except Exception as e:
            logger.error(f"Encoding error: {e}")
            return df

    def transform(self, df, cat_columns: List[str]) -> Any:
        """Already fitted encoders দিয়ে new data transform।"""
        try:
            result = df.copy()
            for col in cat_columns:
                if col in result.columns:
                    result = self._encode_column(result, col, fit=False)
            return result
        except Exception as e:
            logger.error(f"Transform error: {e}")
            return df

    def _encode_column(self, df, col: str, target_col: str = None,
                        fit: bool = True) -> Any:
        """Single column encode করো।"""
        if self.method == 'label':
            return self._label_encode(df, col, fit)
        elif self.method == 'onehot':
            return self._onehot_encode(df, col, fit)
        elif self.method == 'target' and target_col:
            return self._target_encode(df, col, target_col, fit)
        elif self.method == 'frequency':
            return self._frequency_encode(df, col, fit)
        elif self.method == 'binary':
            return self._binary_encode(df, col, fit)
        elif self.method == 'ordinal':
            return self._ordinal_encode(df, col, fit)
        return df

    def _label_encode(self, df, col: str, fit: bool) -> Any:
        from sklearn.preprocessing import LabelEncoder
        le = self.encoders.get(col, LabelEncoder())
        try:
            if fit:
                df[col] = le.fit_transform(df[col].astype(str))
                self.encoders[col] = le
            else:
                # Handle unknown categories
                known   = set(le.classes_)
                df[col] = df[col].astype(str).apply(
                    lambda x: x if x in known else le.classes_[0]
                )
                df[col] = le.transform(df[col])
        except Exception as e:
            logger.warning(f"Label encode error for {col}: {e}")
        return df

    def _onehot_encode(self, df, col: str, fit: bool) -> Any:
        try:
            import pandas as pd
            if fit:
                unique_vals = df[col].astype(str).unique().tolist()
                self.category_maps[col] = unique_vals

            categories = self.category_maps.get(col, df[col].astype(str).unique())
            for cat in categories:
                new_col = f"{col}_{cat}"
                df[new_col] = (df[col].astype(str) == cat).astype(int)

            df = df.drop(columns=[col])
        except Exception as e:
            logger.warning(f"OneHot encode error for {col}: {e}")
        return df

    def _target_encode(self, df, col: str, target_col: str, fit: bool) -> Any:
        """Target mean encoding (low leakage version)।"""
        try:
            if fit and target_col in df.columns:
                means = df.groupby(col)[target_col].mean()
                global_mean = df[target_col].mean()
                self.target_means[col] = means.to_dict()
                self.target_means[f"{col}_global"] = global_mean

            means       = self.target_means.get(col, {})
            global_mean = self.target_means.get(f"{col}_global", 0.5)
            df[col]     = df[col].map(means).fillna(global_mean)
        except Exception as e:
            logger.warning(f"Target encode error for {col}: {e}")
        return df

    def _frequency_encode(self, df, col: str, fit: bool) -> Any:
        """Category frequency দিয়ে replace করো।"""
        try:
            if fit:
                freq = df[col].value_counts(normalize=True).to_dict()
                self.category_maps[col] = freq
            freq    = self.category_maps.get(col, {})
            df[col] = df[col].map(freq).fillna(0.0)
        except Exception as e:
            logger.warning(f"Frequency encode error for {col}: {e}")
        return df

    def _binary_encode(self, df, col: str, fit: bool) -> Any:
        """Binary encoding for high-cardinality categories।"""
        try:
            from sklearn.preprocessing import LabelEncoder
            import numpy as np

            le = self.encoders.get(col, LabelEncoder())
            if fit:
                le.fit(df[col].astype(str))
                self.encoders[col] = le

            labels  = le.transform(df[col].astype(str))
            n_bits  = max(1, int(np.ceil(np.log2(len(le.classes_) + 1))))
            bit_df  = df.copy()

            for bit in range(n_bits):
                bit_df[f"{col}_bit{bit}"] = (labels >> bit) & 1

            bit_df = bit_df.drop(columns=[col])
            return bit_df
        except Exception as e:
            logger.warning(f"Binary encode error for {col}: {e}")
            return df

    def _ordinal_encode(self, df, col: str, fit: bool,
                         order: List = None) -> Any:
        """Ordinal encoding with custom order।"""
        try:
            if fit:
                if order is None:
                    order = sorted(df[col].dropna().unique().tolist())
                self.category_maps[col] = {val: i for i, val in enumerate(order)}

            mapping = self.category_maps.get(col, {})
            default = len(mapping)  # Unknown = last
            df[col] = df[col].map(mapping).fillna(default).astype(int)
        except Exception as e:
            logger.warning(f"Ordinal encode error for {col}: {e}")
        return df

    def encode_cyclical(self, df, col: str, period: float) -> Any:
        """
        Cyclical feature encoding (hour, day, month)।
        hour → sin(2π×hour/24), cos(2π×hour/24)
        """
        import math
        try:
            df[f"{col}_sin"] = df[col].apply(lambda x: round(math.sin(2 * math.pi * x / period), 6))
            df[f"{col}_cos"] = df[col].apply(lambda x: round(math.cos(2 * math.pi * x / period), 6))
        except Exception as e:
            logger.warning(f"Cyclical encode error for {col}: {e}")
        return df

    def auto_encode(self, df, threshold_onehot: int = 10,
                     threshold_hash: int = 100) -> Any:
        """
        Cardinality অনুযায়ী auto encoding method select করো।
        < 10 unique → onehot
        10-100 unique → target/frequency
        > 100 unique → hash/binary
        """
        try:
            import pandas as pd
            result = df.copy()
            cat_cols = result.select_dtypes(include=['object', 'category']).columns

            for col in cat_cols:
                n_unique = result[col].nunique()
                if n_unique <= 2:
                    encoder = DataEncoder('label')
                elif n_unique <= threshold_onehot:
                    encoder = DataEncoder('onehot')
                elif n_unique <= threshold_hash:
                    encoder = DataEncoder('frequency')
                else:
                    encoder = DataEncoder('binary')

                result = encoder.fit_transform(result, [col])
                self.encoders[col] = encoder

            return result
        except Exception as e:
            logger.error(f"Auto encode error: {e}")
            return df

    def get_feature_names(self, original_col: str) -> List[str]:
        """Encoding sonra কোন column names তৈরি হয়েছে।"""
        if self.method == 'onehot':
            cats = self.category_maps.get(original_col, [])
            return [f"{original_col}_{c}" for c in cats]
        elif self.method == 'binary':
            le = self.encoders.get(original_col)
            if le:
                import numpy as np
                n_bits = max(1, int(np.ceil(np.log2(len(le.classes_) + 1))))
                return [f"{original_col}_bit{b}" for b in range(n_bits)]
        return [original_col]

    def cardinality_report(self, df) -> dict:
        """Categorical columns এর cardinality report।"""
        try:
            import pandas as pd
            cat_cols = df.select_dtypes(include=['object', 'category']).columns
            report   = {}
            for col in cat_cols:
                n       = df[col].nunique()
                missing = df[col].isnull().sum()
                report[col] = {
                    'unique_values': n,
                    'missing':       int(missing),
                    'missing_pct':   round(missing / max(len(df), 1) * 100, 2),
                    'recommended_encoding': (
                        'label'     if n <= 2 else
                        'onehot'    if n <= 10 else
                        'frequency' if n <= 100 else
                        'binary'
                    ),
                }
            return report
        except Exception as e:
            return {'error': str(e)}
