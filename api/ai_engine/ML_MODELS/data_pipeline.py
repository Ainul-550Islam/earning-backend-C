"""
api/ai_engine/ML_MODELS/data_pipeline.py
==========================================
Data Pipeline — end-to-end data processing pipeline।
Raw data ingestion → preprocessing → feature engineering → ML-ready।
Fraud detection, churn prediction, recommendation datasets।
"""

import logging
import os
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class DataPipeline:
    """
    End-to-end ML data processing pipeline।
    Orchestrates: load → validate → preprocess → encode → normalize → split।
    """

    def __init__(self, pipeline_name: str = 'default',
                 target_col: str = None,
                 drop_cols: List[str] = None):
        self.pipeline_name = pipeline_name
        self.target_col    = target_col
        self.drop_cols     = drop_cols or []
        self.steps_log     = []

        # Component instances
        from .data_preprocessor import DataPreprocessor
        from .data_normalizer   import DataNormalizer
        from .data_encoder      import DataEncoder
        from .data_splitter     import DataSplitter

        self.preprocessor = DataPreprocessor()
        self.normalizer   = DataNormalizer(method='standard')
        self.encoder      = DataEncoder(method='label')
        self.splitter     = DataSplitter()

    def run(self, raw_data: list,
            cat_columns: List[str] = None,
            test_size: float = 0.20,
            val_size: float = 0.10) -> dict:
        """
        Full pipeline run করো।
        Returns train/val/test splits + pipeline stats।
        """
        cat_columns = cat_columns or []
        logger.info(f"Pipeline '{self.pipeline_name}' started — {len(raw_data)} records")
        self.steps_log = []

        try:
            # Step 1: Preprocess
            self._log('preprocessing')
            processed = self.preprocessor.preprocess(raw_data, self.target_col, self.drop_cols)
            if 'error' in processed:
                return {'error': processed['error'], 'step': 'preprocessing'}
            X, y = processed['X'], processed['y']
            self._log('preprocessing', processed.get('stats', {}))

            # Step 2: Encode categoricals
            if cat_columns:
                self._log('encoding')
                X = self.encoder.fit_transform(X, cat_columns)
                self._log('encoding', {'encoded_cols': len(cat_columns)})

            # Step 3: Normalize numerics
            self._log('normalization')
            try:
                import numpy as np
                X_arr = X.values if hasattr(X, 'values') else np.array(X)
                X_arr = self.normalizer.fit_transform(X_arr)
                self._log('normalization', {'method': self.normalizer.method})
            except Exception as e:
                logger.warning(f"Normalization skipped: {e}")
                X_arr = X.values if hasattr(X, 'values') else X

            # Step 4: Split
            self._log('splitting')
            if y is not None:
                split = self.splitter.split(X_arr, y.values if hasattr(y, 'values') else y,
                                             test_size=test_size, val_size=val_size)
                self._log('splitting', split.get('sizes', {}))
            else:
                split = {'X_train': X_arr, 'y_train': None,
                         'X_val': None, 'y_val': None,
                         'X_test': None, 'y_test': None}

            logger.info(f"Pipeline '{self.pipeline_name}' complete")
            return {
                **split,
                'pipeline_name': self.pipeline_name,
                'steps':         self.steps_log,
                'feature_count': X_arr.shape[1] if hasattr(X_arr, 'shape') else 0,
                'success':       True,
            }

        except Exception as e:
            logger.error(f"Pipeline error at {self.steps_log[-1] if self.steps_log else 'start'}: {e}")
            return {'error': str(e), 'steps': self.steps_log}

    def _log(self, step: str, details: dict = None):
        self.steps_log.append({'step': step, 'details': details or {}})

    def run_from_csv(self, csv_path: str, **kwargs) -> dict:
        """CSV file থেকে pipeline run করো।"""
        try:
            import pandas as pd
            df   = pd.read_csv(csv_path)
            data = df.to_dict('records')
            logger.info(f"Loaded CSV: {csv_path} — {len(data)} rows, {len(df.columns)} cols")
            return self.run(data, **kwargs)
        except Exception as e:
            return {'error': str(e)}

    def run_from_db(self, queryset, **kwargs) -> dict:
        """Django QuerySet থেকে pipeline run করো।"""
        try:
            data = list(queryset.values())
            return self.run(data, **kwargs)
        except Exception as e:
            return {'error': str(e)}

    def run_from_json(self, json_path: str, **kwargs) -> dict:
        """JSON file থেকে pipeline run করো।"""
        try:
            import json
            with open(json_path) as f:
                data = json.load(f)
            if isinstance(data, dict):
                data = list(data.values())
            return self.run(data, **kwargs)
        except Exception as e:
            return {'error': str(e)}

    def profile_data(self, raw_data: list) -> dict:
        """Pipeline চালানোর আগে data profile করো।"""
        try:
            import pandas as pd
            df      = pd.DataFrame(raw_data)
            profile = {
                'rows':              len(df),
                'columns':           len(df.columns),
                'missing_total':     int(df.isnull().sum().sum()),
                'missing_pct':       round(df.isnull().sum().sum() / (len(df) * len(df.columns)) * 100, 2),
                'duplicate_rows':    int(df.duplicated().sum()),
                'numeric_columns':   len(df.select_dtypes(include='number').columns),
                'categorical_columns': len(df.select_dtypes(include='object').columns),
                'memory_mb':         round(df.memory_usage(deep=True).sum() / 1024 / 1024, 3),
                'pipeline_ready':    True,
                'warnings':          [],
            }

            if profile['missing_pct'] > 30:
                profile['warnings'].append(f"High missing rate: {profile['missing_pct']:.1f}%")
            if profile['duplicate_rows'] > len(df) * 0.10:
                profile['warnings'].append(f"High duplicate rate: {profile['duplicate_rows']} rows")

            return profile
        except Exception as e:
            return {'error': str(e)}

    def validate_pipeline_output(self, split: dict) -> dict:
        """Pipeline output validate করো।"""
        issues = []
        checks = {}

        X_train = split.get('X_train')
        y_train = split.get('y_train')

        if X_train is None:
            issues.append('No training features')
            checks['has_features'] = False
        else:
            checks['has_features'] = True
            checks['feature_count'] = X_train.shape[1] if hasattr(X_train, 'shape') else len(X_train[0])
            checks['train_samples'] = len(X_train)

        if y_train is None:
            checks['has_target'] = False
            issues.append('No target variable — unsupervised mode')
        else:
            checks['has_target']    = True
            checks['target_samples'] = len(y_train)

            # Class balance check
            try:
                import numpy as np
                unique, counts = np.unique(y_train, return_counts=True)
                min_class_pct  = counts.min() / len(y_train)
                if min_class_pct < 0.05:
                    issues.append(f"Severe class imbalance — minority class: {min_class_pct:.1%}")
                checks['class_distribution'] = dict(zip(unique.tolist(), counts.tolist()))
            except Exception:
                pass

        return {
            'valid':   len(issues) == 0,
            'issues':  issues,
            'checks':  checks,
        }

    def save_pipeline_config(self, path: str):
        """Pipeline configuration save করো।"""
        import json
        config = {
            'pipeline_name': self.pipeline_name,
            'target_col':    self.target_col,
            'drop_cols':     self.drop_cols,
            'normalizer':    self.normalizer.method,
            'encoder':       self.encoder.method,
        }
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Pipeline config saved: {path}")

    def get_pipeline_stats(self) -> dict:
        """Pipeline execution statistics।"""
        return {
            'pipeline_name': self.pipeline_name,
            'steps_run':     [s['step'] for s in self.steps_log],
            'step_count':    len(self.steps_log),
            'config': {
                'target_col':  self.target_col,
                'normalizer':  self.normalizer.method,
                'encoder':     self.encoder.method,
            },
        }
