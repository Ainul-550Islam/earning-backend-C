"""
api/ai_engine/ML_MODELS/feature_store.py
=========================================
Feature Store Manager — compute + store + retrieve features।
"""

import logging
logger = logging.getLogger(__name__)


class FeatureStoreManager:
    """Manage feature computation and storage।"""

    def compute_and_store(self, entity_id: str, entity_type: str,
                          feature_type: str, raw_data: dict, tenant_id=None) -> dict:
        from ..ML_MODELS.feature_engineering import FeatureEngineer
        from ..repository import FeatureRepository

        engineer = FeatureEngineer(feature_type=feature_type)
        features = engineer.extract(raw_data)

        obj, created = FeatureRepository.upsert(
            entity_id=entity_id,
            feature_type=feature_type,
            features=features,
            entity_type=entity_type,
            tenant_id=tenant_id,
        )
        return {'features': features, 'feature_count': len(features), 'created': created}

    def get_features(self, entity_id: str, feature_type: str) -> dict:
        from ..repository import FeatureRepository
        store = FeatureRepository.get_features(entity_id, feature_type)
        return store.features if store else {}


"""
api/ai_engine/ML_MODELS/feature_importance.py
=============================================
Feature Importance — model feature contribution analysis।
"""


class FeatureImportanceAnalyzer:
    """Analyze which features matter most।"""

    def analyze(self, model, feature_names: list) -> dict:
        try:
            importance = model.feature_importances_
            pairs = sorted(
                zip(feature_names, [round(float(i), 4) for i in importance]),
                key=lambda x: x[1], reverse=True
            )
            return {
                'feature_importance': dict(pairs),
                'top_5': dict(pairs[:5]),
                'bottom_5': dict(pairs[-5:]),
                'total_features': len(pairs),
            }
        except AttributeError:
            return {'error': 'Model does not have feature_importances_'}

    def select_top_features(self, model, feature_names: list, threshold: float = 0.01) -> list:
        result = self.analyze(model, feature_names)
        return [
            fname for fname, imp in result.get('feature_importance', {}).items()
            if imp >= threshold
        ]


"""
api/ai_engine/ML_MODELS/ensemble_model.py
==========================================
Ensemble Model — voting, stacking, blending।
"""


class EnsembleModel:
    """Combine multiple models for better performance।"""

    def __init__(self, models: list, method: str = 'voting'):
        self.models = models
        self.method = method
        self.meta_model = None

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        for m in self.models:
            m.fit(X_train, y_train)
        logger.info(f"Ensemble ({self.method}) fitted with {len(self.models)} models")

    def predict(self, X) -> list:
        if self.method == 'voting':
            import numpy as np
            preds = [m.predict(X) for m in self.models]
            return list(np.array(preds).T.tolist())
        return self.models[0].predict(X) if self.models else []

    def predict_proba(self, X):
        try:
            import numpy as np
            probas = [m.predict_proba(X) for m in self.models if hasattr(m, 'predict_proba')]
            if probas:
                return np.mean(probas, axis=0)
        except Exception:
            pass
        return None


"""
api/ai_engine/ML_MODELS/deep_learning_model.py
===============================================
Deep Learning Model — PyTorch/TensorFlow wrappers।
"""


class DeepLearningModel:
    """Simple MLP wrapper for tabular data।"""

    def __init__(self, input_dim: int, hidden_dims: list = None,
                 output_dim: int = 1, task: str = 'classification'):
        self.input_dim  = input_dim
        self.hidden_dims = hidden_dims or [128, 64, 32]
        self.output_dim = output_dim
        self.task       = task
        self.model      = None

    def build(self):
        try:
            import torch
            import torch.nn as nn

            layers = []
            in_dim = self.input_dim
            for h in self.hidden_dims:
                layers += [nn.Linear(in_dim, h), nn.BatchNorm1d(h), nn.ReLU(), nn.Dropout(0.2)]
                in_dim  = h
            layers.append(nn.Linear(in_dim, self.output_dim))
            if self.task == 'classification':
                layers.append(nn.Sigmoid() if self.output_dim == 1 else nn.Softmax(dim=1))

            self.model = nn.Sequential(*layers)
            return self.model
        except ImportError:
            logger.warning("PyTorch not installed. pip install torch")
            return None

    def predict(self, X) -> list:
        if self.model is None:
            return [0.5] * len(X)
        try:
            import torch
            with torch.no_grad():
                t = torch.FloatTensor(X)
                return self.model(t).numpy().flatten().tolist()
        except Exception:
            return [0.5] * len(X)


"""
api/ai_engine/ML_MODELS/data_pipeline.py
==========================================
Data Pipeline — end-to-end data processing।
"""


class DataPipeline:
    """End-to-end data processing pipeline।"""

    def __init__(self):
        from .data_preprocessor import DataPreprocessor
        from .data_normalizer import DataNormalizer
        from .data_encoder import DataEncoder
        from .data_splitter import DataSplitter
        self.preprocessor = DataPreprocessor()
        self.normalizer   = DataNormalizer()
        self.encoder      = DataEncoder()
        self.splitter     = DataSplitter()

    def run(self, raw_data: list, target_col: str,
            cat_columns: list = None) -> dict:
        cat_columns = cat_columns or []

        # Step 1: Preprocess
        processed = self.preprocessor.preprocess(raw_data, target_col)
        if 'error' in processed:
            return processed

        X, y = processed['X'], processed['y']

        # Step 2: Encode categoricals
        if cat_columns:
            X = self.encoder.fit_transform(X, cat_columns)

        # Step 3: Normalize
        import numpy as np
        X_arr = self.normalizer.fit_transform(X.values if hasattr(X, 'values') else np.array(X))

        # Step 4: Split
        return self.splitter.split(X_arr, y)


"""
api/ai_engine/ML_MODELS/model_versioning.py
============================================
Model Versioning — semantic version management।
"""

import re


class ModelVersionManager:
    """Semantic version management for AI models。"""

    @staticmethod
    def parse(version: str) -> tuple:
        """'1.2.3' → (1, 2, 3)"""
        match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?$', version)
        if not match:
            raise ValueError(f"Invalid version: {version}")
        return (int(match.group(1)), int(match.group(2)), int(match.group(3) or 0))

    @staticmethod
    def bump(version: str, bump_type: str = 'patch') -> str:
        """Bump version: major/minor/patch।"""
        major, minor, patch = ModelVersionManager.parse(version)
        if bump_type == 'major':   return f"{major + 1}.0.0"
        elif bump_type == 'minor': return f"{major}.{minor + 1}.0"
        else:                      return f"{major}.{minor}.{patch + 1}"

    @staticmethod
    def is_newer(v1: str, v2: str) -> bool:
        """v1 > v2?"""
        return ModelVersionManager.parse(v1) > ModelVersionManager.parse(v2)

    @staticmethod
    def get_next_version(ai_model_id: str) -> str:
        from api.ai_engine.models import ModelVersion
        latest = ModelVersion.objects.filter(
            ai_model_id=ai_model_id
        ).order_by('-trained_at').first()
        if not latest:
            return '1.0.0'
        try:
            return ModelVersionManager.bump(latest.version, 'minor')
        except Exception:
            return '1.0.0'
