"""
api/ai_engine/ML_MODELS/model_trainer.py
=========================================
Model Trainer — sklearn/XGBoost/LightGBM model training।
"""

import logging
import os
import pickle
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ModelTrainer:
    """
    AI Model training engine।
    sklearn, XGBoost, LightGBM support।
    """

    def __init__(self, ai_model_id: str):
        self.ai_model_id = ai_model_id
        self.model = None
        self._load_model_config()

    def _load_model_config(self):
        from ..models import AIModel
        try:
            self.ai_model = AIModel.objects.get(id=self.ai_model_id)
        except Exception:
            self.ai_model = None

    def train(self, dataset_path: str, hyperparams: dict = None) -> dict:
        """Model train করো এবং version data return করো।"""
        start = time.time()
        hyperparams = hyperparams or {}

        algorithm = self.ai_model.algorithm if self.ai_model else 'xgboost'

        logger.info(f"Training [{algorithm}] model: {self.ai_model_id}")

        # Data load
        X_train, X_val, y_train, y_val = self._load_data(dataset_path)

        # Model build
        model = self._build_model(algorithm, hyperparams)

        # Fit
        model.fit(X_train, y_train)

        # Evaluate
        metrics = self._evaluate(model, X_val, y_val)

        # Save
        model_path = self._save_model(model)

        duration = time.time() - start

        return {
            'version_data': {
                'version':          self._next_version(),
                'stage':            'staging',
                'model_file_path':  model_path,
                'accuracy':         metrics.get('accuracy', 0.0),
                'precision':        metrics.get('precision', 0.0),
                'recall':           metrics.get('recall', 0.0),
                'f1_score':         metrics.get('f1_score', 0.0),
                'auc_roc':          metrics.get('auc_roc', 0.0),
                'training_rows':    len(X_train),
                'feature_count':    X_train.shape[1] if hasattr(X_train, 'shape') else 0,
                'training_duration_s': duration,
                'trained_at':       __import__('django.utils.timezone', fromlist=['timezone']).timezone.now(),
            }
        }

    def _load_data(self, dataset_path: str) -> Tuple:
        """Dataset load করো। Production এ proper data pipeline use করো।"""
        import numpy as np
        # Placeholder — real implementation connects to data pipeline
        n = 1000
        X = np.random.randn(n, 10)
        y = np.random.randint(0, 2, n)
        split = int(n * 0.8)
        return X[:split], X[split:], y[:split], y[split:]

    def _build_model(self, algorithm: str, hyperparams: dict):
        """Algorithm অনুযায়ী model build করো।"""
        if algorithm == 'xgboost':
            try:
                import xgboost as xgb
                return xgb.XGBClassifier(
                    n_estimators=hyperparams.get('n_estimators', 100),
                    max_depth=hyperparams.get('max_depth', 6),
                    learning_rate=hyperparams.get('learning_rate', 0.1),
                    use_label_encoder=False, eval_metric='logloss',
                )
            except ImportError:
                pass

        if algorithm == 'lightgbm':
            try:
                import lightgbm as lgb
                return lgb.LGBMClassifier(
                    n_estimators=hyperparams.get('n_estimators', 100),
                    learning_rate=hyperparams.get('learning_rate', 0.05),
                )
            except ImportError:
                pass

        # Default: sklearn Random Forest
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=hyperparams.get('n_estimators', 100),
            max_depth=hyperparams.get('max_depth', None),
            random_state=42,
        )

    def _evaluate(self, model, X_val, y_val) -> dict:
        """Model evaluate করো।"""
        try:
            from sklearn.metrics import (
                accuracy_score, precision_score, recall_score,
                f1_score, roc_auc_score
            )
            y_pred = model.predict(X_val)
            y_prob = model.predict_proba(X_val)[:, 1] if hasattr(model, 'predict_proba') else y_pred

            return {
                'accuracy':  round(accuracy_score(y_val, y_pred), 4),
                'precision': round(precision_score(y_val, y_pred, zero_division=0), 4),
                'recall':    round(recall_score(y_val, y_pred, zero_division=0), 4),
                'f1_score':  round(f1_score(y_val, y_pred, zero_division=0), 4),
                'auc_roc':   round(roc_auc_score(y_val, y_prob), 4),
            }
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return {'accuracy': 0.0, 'precision': 0.0, 'recall': 0.0, 'f1_score': 0.0, 'auc_roc': 0.0}

    def _save_model(self, model) -> str:
        """Model serialize করে save করো।"""
        from ..config import ai_config
        path = os.path.join(ai_config.model_storage_path, f"{self.ai_model_id}.pkl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'wb') as f:
                pickle.dump(model, f)
        except Exception as e:
            logger.error(f"Model save error: {e}")
            path = ''
        return path

    def _next_version(self) -> str:
        from ..models import ModelVersion
        count = ModelVersion.objects.filter(ai_model_id=self.ai_model_id).count()
        return f"1.{count}.0"
