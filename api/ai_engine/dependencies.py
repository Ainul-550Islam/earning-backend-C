"""
api/ai_engine/dependencies.py
==============================
AI Engine — Dependency injection helpers।
ViewSet ও service layer এ ব্যবহার।
"""

import logging
from functools import lru_cache
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist

from .models import AIModel
from .exceptions import ModelNotFoundError, ModelNotDeployedError
from .config import ai_config

logger = logging.getLogger(__name__)


def get_active_model(model_key: str) -> AIModel:
    """
    Model key দিয়ে deployed + active মডেল নিয়ে আসো।
    """
    try:
        return AIModel.objects.get(
            slug=model_key,
            status='deployed',
            is_active=True,
            is_production=True,
        )
    except ObjectDoesNotExist:
        raise ModelNotFoundError(f"Active deployed model not found: {model_key}")


def get_model_or_404(model_id: str) -> AIModel:
    """UUID দিয়ে মডেল নিয়ে আসো।"""
    try:
        return AIModel.objects.get(id=model_id)
    except ObjectDoesNotExist:
        raise ModelNotFoundError(f"Model not found: {model_id}")


def get_model_for_prediction(prediction_type: str, tenant_id=None) -> Optional[AIModel]:
    """
    Prediction type এর জন্য সঠিক মডেল বের করো।
    Tenant-specific মডেল থাকলে সেটা, নাহলে global।
    """
    qs = AIModel.objects.filter(
        task_type=prediction_type,
        status='deployed',
        is_active=True,
    ).order_by('-created_at')

    if tenant_id:
        tenant_model = qs.filter(tenant_id=tenant_id).first()
        if tenant_model:
            return tenant_model

    return qs.filter(tenant__isnull=True).first()


def get_ai_config_dep():
    """AI config singleton return।"""
    return ai_config


def get_feature_extractor(feature_type: str):
    """Feature type দিয়ে সঠিক extractor import করো।"""
    from .ML_MODELS.feature_engineering import FeatureEngineer
    return FeatureEngineer(feature_type=feature_type)


def get_recommendation_engine(engine_type: str = 'hybrid'):
    """Recommendation engine factory।"""
    from .RECOMMENDATION_ENGINES.hybrid_recommender import HybridRecommender
    from .RECOMMENDATION_ENGINES.collaborative_filtering import CollaborativeFilteringEngine
    from .RECOMMENDATION_ENGINES.content_based_filtering import ContentBasedEngine
    from .RECOMMENDATION_ENGINES.popularity_recommender import PopularityRecommender

    engines = {
        'hybrid':        HybridRecommender,
        'collaborative': CollaborativeFilteringEngine,
        'content_based': ContentBasedEngine,
        'popularity':    PopularityRecommender,
    }
    engine_cls = engines.get(engine_type, HybridRecommender)
    return engine_cls()


def get_anomaly_detector(anomaly_type: str = 'general'):
    """Anomaly detector factory।"""
    from .ANOMALY_DETECTION.real_time_anomaly import RealTimeAnomalyDetector
    return RealTimeAnomalyDetector(anomaly_type=anomaly_type)


def get_nlp_engine(task: str = 'sentiment'):
    """NLP engine factory।"""
    from .NLP_ENGINES.sentiment_analyzer import SentimentAnalyzer
    from .NLP_ENGINES.intent_classifier import IntentClassifier
    from .NLP_ENGINES.spam_detector import SpamDetector

    engines = {
        'sentiment': SentimentAnalyzer,
        'intent':    IntentClassifier,
        'spam':      SpamDetector,
    }
    return engines.get(task, SentimentAnalyzer)()
