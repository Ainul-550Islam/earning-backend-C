"""
api/ai_engine/ML_MODELS/data_splitter.py
=========================================
Data Splitter — train/validation/test splitting।
Stratified, time-series, group-based splits support।
Class imbalance handling, oversampling, undersampling।
"""

import logging
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)


class DataSplitter:
    """
    Comprehensive data splitting engine।
    Supports: random, stratified, time-series, group k-fold।
    """

    def split(self, X, y, test_size: float = 0.2,
              val_size: float = 0.1, stratify: bool = True,
              random_state: int = 42) -> Dict:
        """
        Train/Val/Test split করো।
        stratify=True → class distribution maintain করে।
        """
        try:
            from sklearn.model_selection import train_test_split
            stratify_col = y if stratify else None

            # First split: train+val vs test
            X_temp, X_test, y_temp, y_test = train_test_split(
                X, y,
                test_size=test_size,
                random_state=random_state,
                stratify=stratify_col,
            )

            # Second split: train vs val
            val_ratio = val_size / (1 - test_size)
            stratify_temp = y_temp if stratify else None
            X_train, X_val, y_train, y_val = train_test_split(
                X_temp, y_temp,
                test_size=val_ratio,
                random_state=random_state,
                stratify=stratify_temp,
            )

            return {
                'X_train': X_train, 'y_train': y_train,
                'X_val':   X_val,   'y_val':   y_val,
                'X_test':  X_test,  'y_test':  y_test,
                'sizes': {
                    'train': len(X_train),
                    'val':   len(X_val),
                    'test':  len(X_test),
                    'total': len(X_train) + len(X_val) + len(X_test),
                },
                'ratios': {
                    'train': round(len(X_train) / (len(X_train) + len(X_val) + len(X_test)), 3),
                    'val':   round(len(X_val)   / (len(X_train) + len(X_val) + len(X_test)), 3),
                    'test':  round(len(X_test)  / (len(X_train) + len(X_val) + len(X_test)), 3),
                },
            }
        except Exception as e:
            logger.error(f"Data split error: {e}")
            return {'error': str(e)}

    def time_series_split(self, X, y, n_splits: int = 5) -> List[Dict]:
        """
        Time-series data এর জন্য walk-forward splitting।
        Future leakage নেই — সবসময় পুরানো data train এ।
        """
        try:
            from sklearn.model_selection import TimeSeriesSplit
            tscv    = TimeSeriesSplit(n_splits=n_splits)
            splits  = []
            for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
                splits.append({
                    'fold':     fold + 1,
                    'X_train':  X[train_idx] if hasattr(X, '__getitem__') else [X[i] for i in train_idx],
                    'y_train':  y[train_idx] if hasattr(y, '__getitem__') else [y[i] for i in train_idx],
                    'X_test':   X[test_idx]  if hasattr(X, '__getitem__') else [X[i] for i in test_idx],
                    'y_test':   y[test_idx]  if hasattr(y, '__getitem__') else [y[i] for i in test_idx],
                    'train_size': len(train_idx),
                    'test_size':  len(test_idx),
                })
            return splits
        except Exception as e:
            logger.error(f"Time series split error: {e}")
            return []

    def kfold_split(self, X, y, n_folds: int = 5,
                    stratify: bool = True) -> List[Dict]:
        """K-Fold cross-validation splits।"""
        try:
            from sklearn.model_selection import StratifiedKFold, KFold
            kf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42) \
                 if stratify else KFold(n_splits=n_folds, shuffle=True, random_state=42)

            splits = []
            for fold, (train_idx, val_idx) in enumerate(kf.split(X, y if stratify else None)):
                splits.append({
                    'fold':       fold + 1,
                    'train_idx':  train_idx.tolist(),
                    'val_idx':    val_idx.tolist(),
                    'train_size': len(train_idx),
                    'val_size':   len(val_idx),
                })
            return splits
        except Exception as e:
            logger.error(f"K-fold split error: {e}")
            return []

    def handle_imbalance(self, X, y, method: str = 'oversample') -> Tuple:
        """
        Class imbalance handle করো।
        methods: 'oversample' (SMOTE), 'undersample', 'class_weight'
        """
        try:
            import numpy as np
            classes, counts = np.unique(y, return_counts=True)
            logger.info(f"Class distribution: {dict(zip(classes, counts))}")

            if method == 'oversample':
                try:
                    from imblearn.over_sampling import SMOTE
                    sm = SMOTE(random_state=42)
                    X_res, y_res = sm.fit_resample(X, y)
                    logger.info(f"SMOTE applied: {len(y)} → {len(y_res)} samples")
                    return X_res, y_res
                except ImportError:
                    logger.warning("imbalanced-learn not installed. pip install imbalanced-learn")
                    return self._simple_oversample(X, y)

            elif method == 'undersample':
                try:
                    from imblearn.under_sampling import RandomUnderSampler
                    rus = RandomUnderSampler(random_state=42)
                    X_res, y_res = rus.fit_resample(X, y)
                    return X_res, y_res
                except ImportError:
                    return X, y

            return X, y

        except Exception as e:
            logger.error(f"Imbalance handling error: {e}")
            return X, y

    def _simple_oversample(self, X, y) -> Tuple:
        """Simple random oversampling (SMOTE fallback)।"""
        import numpy as np
        classes, counts = np.unique(y, return_counts=True)
        max_count = max(counts)
        X_list, y_list = list(X), list(y)

        for cls, cnt in zip(classes, counts):
            if cnt < max_count:
                idxs   = [i for i, yi in enumerate(y_list) if yi == cls]
                needed = max_count - cnt
                extra_idxs = np.random.choice(idxs, needed, replace=True)
                for idx in extra_idxs:
                    X_list.append(X_list[idx])
                    y_list.append(cls)

        # Shuffle
        combined = list(zip(X_list, y_list))
        np.random.shuffle(combined)
        X_out, y_out = zip(*combined) if combined else ([], [])
        return np.array(X_out), np.array(y_out)

    def split_by_date(self, df, date_col: str,
                       train_end: str, test_start: str = None) -> Dict:
        """Date column দিয়ে train/test split।"""
        try:
            import pandas as pd
            df[date_col] = pd.to_datetime(df[date_col])
            train_mask   = df[date_col] <= pd.Timestamp(train_end)
            test_start   = test_start or train_end
            test_mask    = df[date_col] > pd.Timestamp(test_start)

            return {
                'train':      df[train_mask],
                'test':       df[test_mask],
                'train_size': train_mask.sum(),
                'test_size':  test_mask.sum(),
                'split_date': train_end,
            }
        except Exception as e:
            return {'error': str(e)}

    def stratified_group_split(self, X, y, groups,
                                test_size: float = 0.2) -> Dict:
        """
        Group K-Fold — same user/entity সব ফোল্ডে না থেকে।
        User-level data leakage prevent করে।
        """
        try:
            from sklearn.model_selection import GroupShuffleSplit
            gss = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
            train_idx, test_idx = next(gss.split(X, y, groups))
            return {
                'X_train': X[train_idx], 'y_train': y[train_idx],
                'X_test':  X[test_idx],  'y_test':  y[test_idx],
                'train_size': len(train_idx),
                'test_size':  len(test_idx),
                'unique_train_groups': len(set(groups[i] for i in train_idx)),
                'unique_test_groups':  len(set(groups[i] for i in test_idx)),
            }
        except Exception as e:
            logger.error(f"Group split error: {e}")
            return self.split(X, y, test_size)

    def check_data_leakage(self, train_ids, test_ids) -> dict:
        """Train ও test set এ কোনো overlap আছে কিনা check করো।"""
        train_set = set(str(i) for i in train_ids)
        test_set  = set(str(i) for i in test_ids)
        overlap   = train_set & test_set
        return {
            'has_leakage':   len(overlap) > 0,
            'overlap_count': len(overlap),
            'train_size':    len(train_set),
            'test_size':     len(test_set),
            'leaking_ids':   list(overlap)[:10],  # First 10
        }
