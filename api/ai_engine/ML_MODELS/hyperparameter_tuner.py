"""
api/ai_engine/ML_MODELS/hyperparameter_tuner.py
================================================
Hyperparameter Tuner — Grid/Random/Bayesian search।
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class HyperparameterTuner:
    """Automated hyperparameter optimization।"""

    def tune(self, model_class, X_train, y_train, param_grid: dict,
             method: str = 'random', n_iter: int = 20, cv: int = 3) -> dict:
        try:
            from sklearn.model_selection import RandomizedSearchCV, GridSearchCV
            from sklearn.metrics import make_scorer, f1_score

            scorer = make_scorer(f1_score, zero_division=0)
            model  = model_class()

            if method == 'random':
                search = RandomizedSearchCV(
                    model, param_grid, n_iter=n_iter,
                    cv=cv, scoring=scorer, n_jobs=-1, random_state=42
                )
            else:
                search = GridSearchCV(model, param_grid, cv=cv, scoring=scorer, n_jobs=-1)

            search.fit(X_train, y_train)

            return {
                'best_params': search.best_params_,
                'best_score':  round(search.best_score_, 4),
                'method':      method,
                'n_iter':      n_iter,
            }
        except Exception as e:
            logger.error(f"Tuning error: {e}")
            return {'best_params': {}, 'best_score': 0.0, 'error': str(e)}


"""
api/ai_engine/ML_MODELS/cross_validator.py
==========================================
Cross Validator।
"""


class CrossValidator:
    def validate(self, model, X, y, cv: int = 5, scoring: str = 'f1_weighted') -> dict:
        try:
            from sklearn.model_selection import cross_validate
            import numpy as np
            results = cross_validate(
                model, X, y, cv=cv,
                scoring=scoring, return_train_score=True
            )
            return {
                'val_mean':   round(float(results['test_score'].mean()), 4),
                'val_std':    round(float(results['test_score'].std()), 4),
                'train_mean': round(float(results['train_score'].mean()), 4),
                'cv':         cv,
                'scoring':    scoring,
                'overfit':    bool(results['train_score'].mean() - results['test_score'].mean() > 0.15),
            }
        except Exception as e:
            return {'error': str(e)}


"""
api/ai_engine/ML_MODELS/data_preprocessor.py
=============================================
Data Preprocessor — clean + prepare data for training।
"""


class DataPreprocessor:
    def preprocess(self, data: list, target_col: str = None) -> dict:
        try:
            import pandas as pd
            import numpy as np

            df = pd.DataFrame(data)

            # Drop duplicates
            before = len(df)
            df = df.drop_duplicates()
            dupes_removed = before - len(df)

            # Fill nulls
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df[numeric_cols].fillna(df[numeric_cols].median())
            cat_cols = df.select_dtypes(include=['object']).columns
            df[cat_cols] = df[cat_cols].fillna('unknown')

            X = df.drop(columns=[target_col]) if target_col and target_col in df.columns else df
            y = df[target_col] if target_col and target_col in df.columns else None

            return {
                'X':              X,
                'y':              y,
                'rows':           len(df),
                'cols':           len(df.columns),
                'dupes_removed':  dupes_removed,
            }
        except Exception as e:
            return {'error': str(e)}


"""
api/ai_engine/ML_MODELS/data_normalizer.py
==========================================
Data Normalizer — feature scaling।
"""


class DataNormalizer:
    def __init__(self, method: str = 'standard'):
        self.method = method
        self.scaler = None

    def fit_transform(self, X):
        try:
            from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
            scalers = {
                'standard': StandardScaler(),
                'minmax':   MinMaxScaler(),
                'robust':   RobustScaler(),
            }
            self.scaler = scalers.get(self.method, StandardScaler())
            return self.scaler.fit_transform(X)
        except Exception as e:
            logger.error(f"Normalize error: {e}")
            return X

    def transform(self, X):
        if self.scaler:
            return self.scaler.transform(X)
        return X


"""
api/ai_engine/ML_MODELS/data_encoder.py
=======================================
Data Encoder — categorical feature encoding।
"""


class DataEncoder:
    def __init__(self, method: str = 'label'):
        self.method   = method
        self.encoders = {}

    def fit_transform(self, df, cat_columns: list):
        try:
            import pandas as pd
            result = df.copy()
            for col in cat_columns:
                if col not in result.columns:
                    continue
                if self.method == 'onehot':
                    dummies = pd.get_dummies(result[col], prefix=col)
                    result  = pd.concat([result.drop(col, axis=1), dummies], axis=1)
                else:
                    from sklearn.preprocessing import LabelEncoder
                    le = LabelEncoder()
                    result[col]       = le.fit_transform(result[col].astype(str))
                    self.encoders[col] = le
            return result
        except Exception as e:
            logger.error(f"Encode error: {e}")
            return df


"""
api/ai_engine/ML_MODELS/data_splitter.py
=========================================
Data Splitter — train/val/test splitting।
"""


class DataSplitter:
    def split(self, X, y, test_size: float = 0.2, val_size: float = 0.1, stratify: bool = True):
        try:
            from sklearn.model_selection import train_test_split
            stratify_col = y if stratify else None

            X_temp, X_test, y_temp, y_test = train_test_split(
                X, y, test_size=test_size, random_state=42, stratify=stratify_col
            )
            X_train, X_val, y_train, y_val = train_test_split(
                X_temp, y_temp, test_size=val_size / (1 - test_size),
                random_state=42
            )
            return {
                'X_train': X_train, 'y_train': y_train,
                'X_val':   X_val,   'y_val':   y_val,
                'X_test':  X_test,  'y_test':  y_test,
                'sizes': {
                    'train': len(X_train),
                    'val':   len(X_val),
                    'test':  len(X_test),
                },
            }
        except Exception as e:
            return {'error': str(e)}
