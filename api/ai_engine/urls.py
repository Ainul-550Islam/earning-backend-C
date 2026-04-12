"""
api/ai_engine/urls.py
======================
AI Engine — URL Routing।
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter as DefaultRouter

from .routes import (
    AIModelViewSet,
    TrainingJobViewSet,
    PredictionViewSet,
    RecommendationViewSet,
    AnomalyDetectionViewSet,
    NLPViewSet,
    UserSegmentViewSet,
    ABTestViewSet,
    InsightViewSet,
    PersonalizationViewSet,
    ChurnRiskViewSet,
    DataDriftViewSet,
    ExperimentTrackingViewSet,
    FeatureStoreViewSet,
)

router = DefaultRouter()

router.register(r'models',          AIModelViewSet,          basename='ai-model')
router.register(r'training',        TrainingJobViewSet,      basename='training-job')
router.register(r'predict',         PredictionViewSet,       basename='prediction')
router.register(r'recommend',       RecommendationViewSet,   basename='recommendation')
router.register(r'anomalies',       AnomalyDetectionViewSet, basename='anomaly')
router.register(r'nlp',             NLPViewSet,              basename='nlp')
router.register(r'segments',        UserSegmentViewSet,      basename='segment')
router.register(r'ab-tests',        ABTestViewSet,           basename='ab-test')
router.register(r'insights',        InsightViewSet,          basename='insight')
router.register(r'personalization', PersonalizationViewSet,  basename='personalization')
router.register(r'churn',           ChurnRiskViewSet,        basename='churn')
router.register(r'drift',           DataDriftViewSet,        basename='drift')
router.register(r'experiments',     ExperimentTrackingViewSet, basename='experiment')
router.register(r'features',        FeatureStoreViewSet,     basename='feature-store')

urlpatterns = [
    path('', include(router.urls)),
]
