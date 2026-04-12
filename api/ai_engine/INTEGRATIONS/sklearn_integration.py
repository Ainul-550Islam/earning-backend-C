"""
api/ai_engine/INTEGRATIONS/sklearn_integration.py
==================================================
Scikit-learn Integration।
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SklearnIntegration:
    """Scikit-learn model training ও inference।"""

    SUPPORTED_MODELS = {
        'random_forest':    'sklearn.ensemble.RandomForestClassifier',
        'logistic_reg':     'sklearn.linear_model.LogisticRegression',
        'svm':              'sklearn.svm.SVC',
        'knn':              'sklearn.neighbors.KNeighborsClassifier',
        'naive_bayes':      'sklearn.naive_bayes.GaussianNB',
        'gradient_boost':   'sklearn.ensemble.GradientBoostingClassifier',
        'extra_trees':      'sklearn.ensemble.ExtraTreesClassifier',
    }

    def build(self, model_type: str, params: dict = None) -> Any:
        params = params or {}
        import importlib
        module_path = self.SUPPORTED_MODELS.get(model_type)
        if not module_path:
            from sklearn.ensemble import RandomForestClassifier
            return RandomForestClassifier(**params)
        module_name, class_name = module_path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        return cls(**params)

    def cross_validate(self, model, X, y, cv: int = 5) -> dict:
        try:
            from sklearn.model_selection import cross_val_score
            import numpy as np
            scores = cross_val_score(model, X, y, cv=cv, scoring='f1_weighted')
            return {
                'mean_f1':  round(float(scores.mean()), 4),
                'std_f1':   round(float(scores.std()), 4),
                'cv_scores': [round(s, 4) for s in scores],
            }
        except Exception as e:
            logger.error(f"CV error: {e}")
            return {}

    def get_feature_importance(self, model, feature_names: list) -> Dict:
        try:
            importance = model.feature_importances_
            return dict(sorted(
                zip(feature_names, [round(float(i), 4) for i in importance]),
                key=lambda x: x[1], reverse=True
            ))
        except AttributeError:
            return {}


"""
api/ai_engine/INTEGRATIONS/xgboost_integration.py
==================================================
XGBoost Integration।
"""


class XGBoostIntegration:
    """XGBoost model training, inference, explanation।"""

    def build_classifier(self, params: dict = None) -> Any:
        try:
            import xgboost as xgb
            default_params = {
                'n_estimators': 100, 'max_depth': 6,
                'learning_rate': 0.1, 'subsample': 0.8,
                'colsample_bytree': 0.8, 'use_label_encoder': False,
                'eval_metric': 'logloss', 'random_state': 42,
            }
            default_params.update(params or {})
            return xgb.XGBClassifier(**default_params)
        except ImportError:
            logger.warning("xgboost not installed. pip install xgboost")
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier(**(params or {}))

    def build_regressor(self, params: dict = None) -> Any:
        try:
            import xgboost as xgb
            return xgb.XGBRegressor(**(params or {}))
        except ImportError:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor(**(params or {}))

    def explain_prediction(self, model, X_sample) -> dict:
        try:
            import shap
            import numpy as np
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
            return {'shap_values': shap_values.tolist()}
        except Exception:
            return {}


"""
api/ai_engine/INTEGRATIONS/lightgbm_integration.py
===================================================
LightGBM Integration।
"""


class LightGBMIntegration:
    """LightGBM fast gradient boosting।"""

    def build_classifier(self, params: dict = None) -> Any:
        try:
            import lightgbm as lgb
            default = {
                'n_estimators': 100, 'learning_rate': 0.05,
                'num_leaves': 31, 'random_state': 42, 'verbose': -1,
            }
            default.update(params or {})
            return lgb.LGBMClassifier(**default)
        except ImportError:
            logger.warning("lightgbm not installed. pip install lightgbm")
            from sklearn.ensemble import GradientBoostingClassifier
            return GradientBoostingClassifier()

    def build_regressor(self, params: dict = None) -> Any:
        try:
            import lightgbm as lgb
            return lgb.LGBMRegressor(**(params or {}))
        except ImportError:
            from sklearn.ensemble import GradientBoostingRegressor
            return GradientBoostingRegressor()


"""
api/ai_engine/INTEGRATIONS/huggingface_integration.py
======================================================
Hugging Face Integration — NLP models।
"""


class HuggingFaceIntegration:
    """Hugging Face Transformers integration।"""

    def __init__(self, model_name: str = 'distilbert-base-multilingual-cased'):
        self.model_name = model_name
        self.pipeline   = None

    def _load_pipeline(self, task: str):
        try:
            from transformers import pipeline as hf_pipeline
            self.pipeline = hf_pipeline(task, model=self.model_name)
        except ImportError:
            logger.warning("transformers not installed. pip install transformers")
        except Exception as e:
            logger.error(f"HuggingFace pipeline load error: {e}")

    def sentiment_analysis(self, text: str) -> dict:
        if not self.pipeline:
            self._load_pipeline('sentiment-analysis')
        if not self.pipeline:
            return {'label': 'NEUTRAL', 'score': 0.5}
        try:
            result = self.pipeline(text[:512])[0]
            label_map = {'POSITIVE': 'positive', 'NEGATIVE': 'negative', 'NEUTRAL': 'neutral'}
            return {
                'sentiment': label_map.get(result['label'], 'neutral'),
                'score':     round(result['score'], 4),
            }
        except Exception as e:
            logger.error(f"HF sentiment error: {e}")
            return {'sentiment': 'neutral', 'score': 0.5}

    def embed_text(self, text: str) -> list:
        """Sentence embeddings।"""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
            return model.encode(text).tolist()
        except ImportError:
            return []
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return []
