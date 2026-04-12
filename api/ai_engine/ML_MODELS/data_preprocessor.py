"""
api/ai_engine/ML_MODELS/data_preprocessor.py
=============================================
Data Preprocessor — raw data cleaning ও preparation।
Missing values, outliers, data types, validation।
Training pipeline এর first step।
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class DataPreprocessor:
    """
    Comprehensive data preprocessing pipeline।
    Raw data → ML-ready clean data।
    """

    def preprocess(self, data: list, target_col: str = None,
                   drop_cols: List[str] = None) -> dict:
        """
        Full preprocessing pipeline:
        1. Duplicate removal
        2. Missing value imputation
        3. Type fixing
        4. Outlier detection
        """
        try:
            import pandas as pd
            import numpy as np

            df = pd.DataFrame(data)
            stats = {'original_rows': len(df), 'original_cols': len(df.columns)}

            # Step 1: Drop specified columns
            if drop_cols:
                df = df.drop(columns=[c for c in drop_cols if c in df.columns])

            # Step 2: Remove duplicates
            before_dedup = len(df)
            df = df.drop_duplicates()
            stats['duplicates_removed'] = before_dedup - len(df)

            # Step 3: Impute missing values
            missing_before = df.isnull().sum().sum()
            numeric_cols   = df.select_dtypes(include=[np.number]).columns
            cat_cols       = df.select_dtypes(include=['object', 'category']).columns

            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
            df[cat_cols]     = df[cat_cols].fillna(df[cat_cols].mode().iloc[0] if not df[cat_cols].empty else 'unknown')

            stats['missing_imputed'] = int(missing_before)

            # Step 4: Separate features and target
            X = df.drop(columns=[target_col]) if target_col and target_col in df.columns else df
            y = df[target_col]                 if target_col and target_col in df.columns else None

            stats.update({
                'final_rows': len(df),
                'final_cols': len(df.columns),
                'target_col': target_col,
                'numeric_features': list(numeric_cols),
                'categorical_features': list(cat_cols),
            })

            return {'X': X, 'y': y, 'stats': stats}
        except Exception as e:
            logger.error(f"Preprocessing error: {e}")
            return {'error': str(e)}

    def detect_outliers(self, df, method: str = 'iqr',
                         threshold: float = 3.0) -> dict:
        """
        Outlier detection।
        methods: 'iqr', 'zscore', 'isolation_forest'
        """
        try:
            import pandas as pd
            import numpy as np

            numeric_cols  = df.select_dtypes(include=[np.number]).columns
            outlier_info  = {}

            for col in numeric_cols:
                vals = df[col].dropna()
                if method == 'iqr':
                    q1, q3 = vals.quantile(0.25), vals.quantile(0.75)
                    iqr    = q3 - q1
                    lower  = q1 - 1.5 * iqr
                    upper  = q3 + 1.5 * iqr
                    mask   = (df[col] < lower) | (df[col] > upper)
                elif method == 'zscore':
                    z_scores = (vals - vals.mean()) / (vals.std() or 1)
                    mask     = abs(z_scores) > threshold
                else:
                    mask = pd.Series([False] * len(df))

                outlier_count = int(mask.sum())
                if outlier_count > 0:
                    outlier_info[col] = {
                        'count':     outlier_count,
                        'pct':       round(outlier_count / len(df) * 100, 2),
                        'method':    method,
                    }

            return {
                'outlier_columns': outlier_info,
                'total_outlier_rows': len(outlier_info),
                'recommendation': 'Cap or remove outliers before training' if outlier_info else 'No significant outliers',
            }
        except Exception as e:
            return {'error': str(e)}

    def fix_data_types(self, df, type_map: Dict[str, str] = None) -> Any:
        """
        Data types fix করো।
        type_map: {'age': 'int', 'revenue': 'float', 'date': 'datetime'}
        """
        try:
            import pandas as pd
            type_map = type_map or {}

            for col, dtype in type_map.items():
                if col not in df.columns:
                    continue
                try:
                    if dtype == 'datetime':
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                    elif dtype == 'int':
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
                    elif dtype == 'float':
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    elif dtype == 'bool':
                        df[col] = df[col].astype(bool)
                    elif dtype == 'str':
                        df[col] = df[col].astype(str)
                except Exception as e:
                    logger.warning(f"Type conversion failed for {col}: {e}")

            return df
        except Exception as e:
            logger.error(f"Type fixing error: {e}")
            return df

    def validate_schema(self, df, required_cols: List[str],
                         col_types: Dict[str, str] = None) -> dict:
        """
        Data schema validate করো।
        Required columns ও types check করো।
        """
        missing_cols    = [c for c in required_cols if c not in df.columns]
        type_mismatches = []

        if col_types:
            import numpy as np
            dtype_map = {
                'numeric': [np.number],
                'string':  ['object'],
                'bool':    ['bool'],
            }
            for col, expected_type in col_types.items():
                if col in df.columns:
                    actual = str(df[col].dtype)
                    if expected_type == 'numeric' and not df[col].dtype in [float, int]:
                        type_mismatches.append(f"{col}: expected numeric, got {actual}")

        is_valid = not missing_cols and not type_mismatches

        return {
            'is_valid':        is_valid,
            'missing_columns': missing_cols,
            'type_mismatches': type_mismatches,
            'total_columns':   len(df.columns),
            'total_rows':      len(df),
            'validation_passed': is_valid,
        }

    def generate_profile(self, df) -> dict:
        """Data profiling report তৈরি করো।"""
        try:
            import numpy as np
            import pandas as pd

            profile = {
                'shape':         {'rows': len(df), 'cols': len(df.columns)},
                'missing_pct':   round(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100, 2),
                'duplicate_rows': int(df.duplicated().sum()),
                'columns': {},
            }

            for col in df.columns:
                series  = df[col]
                is_num  = pd.api.types.is_numeric_dtype(series)
                col_info = {
                    'dtype':     str(series.dtype),
                    'missing':   int(series.isnull().sum()),
                    'unique':    int(series.nunique()),
                    'is_numeric': is_num,
                }
                if is_num:
                    col_info.update({
                        'mean':  round(float(series.mean()), 4),
                        'std':   round(float(series.std()), 4),
                        'min':   round(float(series.min()), 4),
                        'max':   round(float(series.max()), 4),
                        'p25':   round(float(series.quantile(0.25)), 4),
                        'p75':   round(float(series.quantile(0.75)), 4),
                    })
                else:
                    top_val = series.value_counts().index[0] if not series.empty else None
                    col_info['top_value'] = str(top_val)
                profile['columns'][col] = col_info

            return profile
        except Exception as e:
            return {'error': str(e)}

    def handle_missing_advanced(self, df, strategy: str = 'knn',
                                  k: int = 5) -> Any:
        """
        Advanced missing value imputation।
        strategies: 'knn', 'iterative', 'median', 'mean', 'mode'
        """
        try:
            import numpy as np
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            cat_cols     = df.select_dtypes(include=['object']).columns

            if strategy == 'knn' and len(numeric_cols) > 0:
                from sklearn.impute import KNNImputer
                imputer = KNNImputer(n_neighbors=k)
                df[numeric_cols] = imputer.fit_transform(df[numeric_cols])

            elif strategy == 'iterative' and len(numeric_cols) > 0:
                from sklearn.experimental import enable_iterative_imputer  # noqa
                from sklearn.impute import IterativeImputer
                imputer = IterativeImputer(random_state=42)
                df[numeric_cols] = imputer.fit_transform(df[numeric_cols])

            else:
                df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())

            df[cat_cols] = df[cat_cols].fillna('missing')

            return df
        except Exception as e:
            logger.error(f"Advanced imputation error: {e}")
            import pandas as pd
            return df.fillna(df.median(numeric_only=True))
