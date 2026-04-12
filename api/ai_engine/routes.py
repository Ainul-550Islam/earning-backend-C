"""
api/ai_engine/routes.py (views.py)
===================================
AI Engine — DRF ViewSets ও API Endpoints।
"""

import logging
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from core.views import BaseViewSet
from api.tenants.mixins import TenantMixin

from .models import (
    AIModel, ModelVersion, TrainingJob, ModelMetric,
    PredictionLog, AnomalyDetectionLog, ChurnRiskProfile,
    RecommendationResult, UserSegment, ABTestExperiment,
    TextAnalysisResult, ImageAnalysisResult, ContentModerationLog,
    InsightModel, PersonalizationProfile, DataDriftLog,
    ExperimentTracking, FeatureStore,
)
from .schemas import (
    AIModelListSerializer, AIModelDetailSerializer, AIModelCreateSerializer,
    ModelVersionSerializer, TrainingJobSerializer, TrainingJobCreateSerializer,
    ModelMetricSerializer,
    PredictionLogSerializer, PredictionRequestSerializer, PredictionResponseSerializer,
    AnomalyDetectionLogSerializer, ChurnRiskProfileSerializer,
    RecommendationResultSerializer, RecommendationRequestSerializer,
    UserSegmentSerializer, ABTestExperimentSerializer,
    TextAnalysisRequestSerializer, TextAnalysisResultSerializer,
    ImageAnalysisRequestSerializer, ImageAnalysisResultSerializer,
    ContentModerationLogSerializer, InsightModelSerializer,
    PersonalizationProfileSerializer, DataDriftLogSerializer,
    ExperimentTrackingSerializer, FeatureStoreSerializer,
)
from .services import (
    ModelManagementService, TrainingService, PredictionService,
    FraudDetectionService, ChurnPredictionService, RecommendationService,
    NLPService, AnomalyDetectionService, InsightGenerationService,
    PersonalizationService,
)
from .exceptions import ModelNotFoundError, TrainingInProgressError

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# AI MODEL VIEWSET
# ══════════════════════════════════════════════════════════════════════

class AIModelViewSet(TenantMixin, BaseViewSet):
    """
    AI Model CRUD + lifecycle management।

    GET    /ai-engine/models/           → list
    POST   /ai-engine/models/           → create
    GET    /ai-engine/models/{id}/      → detail
    PUT    /ai-engine/models/{id}/      → update
    POST   /ai-engine/models/{id}/deploy/     → deploy
    POST   /ai-engine/models/{id}/deprecate/  → deprecate
    GET    /ai-engine/models/{id}/summary/    → full summary
    """
    queryset            = AIModel.objects.all()
    permission_classes  = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create':
            return AIModelCreateSerializer
        if self.action == 'list':
            return AIModelListSerializer
        return AIModelDetailSerializer

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(tenant=tenant, created_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deploy(self, request, pk=None):
        """Model deploy করো।"""
        try:
            model = ModelManagementService.deploy_model(pk)
            return self.success_response(
                data=AIModelDetailSerializer(model).data,
                message='Model successfully deployed.'
            )
        except (ModelNotFoundError, Exception) as e:
            return self.error_response(str(e), status_code=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deprecate(self, request, pk=None):
        """Model deprecate করো।"""
        ModelManagementService.deprecate_model(pk)
        return self.success_response(message='Model deprecated.')

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        """Model এর full summary।"""
        try:
            summary = ModelManagementService.get_model_summary(pk)
            return self.success_response(data=summary)
        except ModelNotFoundError as e:
            return self.error_response(str(e), status_code=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Model এর সব versions।"""
        versions = ModelVersion.objects.filter(ai_model_id=pk).order_by('-trained_at')
        return self.success_response(data=ModelVersionSerializer(versions, many=True).data)


# ══════════════════════════════════════════════════════════════════════
# TRAINING JOB VIEWSET
# ══════════════════════════════════════════════════════════════════════

class TrainingJobViewSet(TenantMixin, BaseViewSet):
    """
    Model training job management।

    POST /ai-engine/training/           → start training
    GET  /ai-engine/training/           → list jobs
    GET  /ai-engine/training/{id}/      → job detail
    POST /ai-engine/training/{id}/cancel/ → cancel job
    """
    queryset            = TrainingJob.objects.all()
    serializer_class    = TrainingJobSerializer
    permission_classes  = [IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.action == 'create':
            return TrainingJobCreateSerializer
        return TrainingJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = TrainingJobCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        try:
            job = TrainingService.start_training(
                ai_model_id=str(d['ai_model'].id),
                dataset_path=d.get('dataset_path', ''),
                hyperparams=d.get('hyperparameters', {}),
                triggered_by=request.user,
            )
            return Response(
                {'success': True, 'message': 'Training started.', 'data': TrainingJobSerializer(job).data},
                status=status.HTTP_201_CREATED
            )
        except TrainingInProgressError as e:
            return self.error_response(str(e), status_code=status.HTTP_409_CONFLICT)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        TrainingService.fail_training(pk, 'Cancelled by user.')
        return self.success_response(message='Training job cancelled.')


# ══════════════════════════════════════════════════════════════════════
# PREDICTION VIEWSET
# ══════════════════════════════════════════════════════════════════════

class PredictionViewSet(TenantMixin, BaseViewSet):
    """
    Real-time prediction endpoints।

    POST /ai-engine/predict/            → single prediction
    POST /ai-engine/predict/batch/      → batch prediction
    POST /ai-engine/predict/fraud/      → fraud score
    POST /ai-engine/predict/churn/      → churn risk
    GET  /ai-engine/predict/history/    → user prediction history
    """
    queryset            = PredictionLog.objects.all()
    serializer_class    = PredictionLogSerializer
    permission_classes  = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Single prediction।"""
        serializer = PredictionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = PredictionService.predict(
            prediction_type=d['prediction_type'],
            input_data=d['input_data'],
            user=request.user,
            tenant_id=tenant_id,
        )
        return self.success_response(data=result)

    @action(detail=False, methods=['post'])
    def batch(self, request):
        """Batch prediction।"""
        items = request.data.get('items', [])
        prediction_type = request.data.get('prediction_type', 'fraud')
        if not items:
            return self.error_response('items list is required.')
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        results = PredictionService.batch_predict(prediction_type, items, tenant_id)
        return self.success_response(data={'results': results, 'count': len(results)})

    @action(detail=False, methods=['post'])
    def fraud(self, request):
        """Fraud score করো।"""
        user = request.user
        metadata = request.data.get('metadata', {})
        action_type = request.data.get('action_type', 'general')
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = FraudDetectionService.score_user_action(user, action_type, metadata, tenant_id)
        return self.success_response(data=result)

    @action(detail=False, methods=['post'])
    def churn(self, request):
        """Churn risk predict করো।"""
        user_id = request.data.get('user_id', str(request.user.id))
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return self.error_response('User not found.', status_code=404)
        result = ChurnPredictionService.predict_churn(user, tenant_id)
        return self.success_response(data=result)

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Current user এর prediction history।"""
        logs = PredictionLog.objects.filter(user=request.user).order_by('-created_at')[:50]
        return self.success_response(data=PredictionLogSerializer(logs, many=True).data)


# ══════════════════════════════════════════════════════════════════════
# RECOMMENDATION VIEWSET
# ══════════════════════════════════════════════════════════════════════

class RecommendationViewSet(TenantMixin, BaseViewSet):
    """
    Personalized recommendations।

    POST /ai-engine/recommend/          → get recommendations
    POST /ai-engine/recommend/click/    → track click
    POST /ai-engine/recommend/convert/  → track conversion
    """
    queryset            = RecommendationResult.objects.all()
    serializer_class    = RecommendationResultSerializer
    permission_classes  = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        """Recommendations generate করো।"""
        serializer = RecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = RecommendationService.get_recommendations(
            user=request.user,
            item_type=d['item_type'],
            engine=d['engine'],
            count=d['count'],
            context=d.get('context', {}),
            tenant_id=tenant_id,
        )
        return self.success_response(data=result)

    @action(detail=False, methods=['post'])
    def click(self, request):
        """Click track করো।"""
        request_id = request.data.get('request_id')
        item_id = request.data.get('item_id')
        if not request_id or not item_id:
            return self.error_response('request_id and item_id required.')
        RecommendationService.track_click(request_id, item_id)
        return self.success_response(message='Click tracked.')

    @action(detail=False, methods=['post'])
    def convert(self, request):
        """Conversion track করো।"""
        request_id = request.data.get('request_id')
        item_id = request.data.get('item_id')
        if not request_id or not item_id:
            return self.error_response('request_id and item_id required.')
        RecommendationService.track_conversion(request_id, item_id)
        return self.success_response(message='Conversion tracked.')


# ══════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION VIEWSET
# ══════════════════════════════════════════════════════════════════════

class AnomalyDetectionViewSet(TenantMixin, BaseViewSet):
    """
    Anomaly log management।

    GET  /ai-engine/anomalies/           → list open anomalies
    GET  /ai-engine/anomalies/{id}/      → anomaly detail
    POST /ai-engine/anomalies/{id}/resolve/ → resolve anomaly
    POST /ai-engine/anomalies/detect/    → manual detection trigger
    """
    queryset            = AnomalyDetectionLog.objects.all()
    serializer_class    = AnomalyDetectionLogSerializer
    permission_classes  = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        severity = self.request.query_params.get('severity')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if severity:
            qs = qs.filter(severity=severity)
        return qs.order_by('-created_at')

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Anomaly resolve করো।"""
        notes = request.data.get('notes', '')
        AnomalyRepository.resolve(pk, request.user.id, notes)
        return self.success_response(message='Anomaly resolved.')

    @action(detail=False, methods=['post'])
    def detect(self, request):
        """Manual anomaly detection trigger।"""
        anomaly_type = request.data.get('anomaly_type', 'general')
        entity_id = request.data.get('entity_id', '')
        data = request.data.get('data', {})
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)

        anomaly = AnomalyDetectionService.detect(
            anomaly_type=anomaly_type,
            entity_id=entity_id,
            data=data,
            user=request.user,
            tenant_id=tenant_id,
        )
        if anomaly:
            return self.success_response(
                data=AnomalyDetectionLogSerializer(anomaly).data,
                message='Anomaly detected and logged.'
            )
        return self.success_response(message='No anomaly detected. Score below threshold.')


# ══════════════════════════════════════════════════════════════════════
# NLP VIEWSET
# ══════════════════════════════════════════════════════════════════════

class NLPViewSet(TenantMixin, BaseViewSet):
    """
    NLP / Text analysis endpoints।

    POST /ai-engine/nlp/analyze/     → text analysis
    POST /ai-engine/nlp/sentiment/   → sentiment only
    POST /ai-engine/nlp/spam/        → spam detection
    POST /ai-engine/nlp/intent/      → intent classification
    POST /ai-engine/nlp/moderate/    → content moderation
    """
    queryset            = TextAnalysisResult.objects.all()
    serializer_class    = TextAnalysisResultSerializer
    permission_classes  = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = TextAnalysisRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = NLPService.analyze_text(
            text=d['text'],
            analysis_type=d['analysis_type'],
            source_type=d.get('source_type', ''),
            source_id=d.get('source_id', ''),
            user=request.user,
            tenant_id=tenant_id,
        )
        return self.success_response(data=TextAnalysisResultSerializer(result).data)

    @action(detail=False, methods=['post'])
    def sentiment(self, request):
        text = request.data.get('text', '')
        if not text:
            return self.error_response('text is required.')
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = NLPService.analyze_text(text, 'sentiment', tenant_id=tenant_id)
        return self.success_response(data=TextAnalysisResultSerializer(result).data)

    @action(detail=False, methods=['post'])
    def spam(self, request):
        text = request.data.get('text', '')
        if not text:
            return self.error_response('text is required.')
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = NLPService.analyze_text(text, 'spam', tenant_id=tenant_id)
        return self.success_response(data=TextAnalysisResultSerializer(result).data)

    @action(detail=False, methods=['post'])
    def intent(self, request):
        text = request.data.get('text', '')
        if not text:
            return self.error_response('text is required.')
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = NLPService.analyze_text(text, 'intent', tenant_id=tenant_id)
        return self.success_response(data=TextAnalysisResultSerializer(result).data)


# ══════════════════════════════════════════════════════════════════════
# USER SEGMENT VIEWSET
# ══════════════════════════════════════════════════════════════════════

class UserSegmentViewSet(TenantMixin, BaseViewSet):
    """
    AI-generated user segments।

    GET  /ai-engine/segments/            → list segments
    GET  /ai-engine/segments/{id}/       → segment detail
    POST /ai-engine/segments/refresh/    → force refresh all segments
    GET  /ai-engine/segments/my-segment/ → current user's segment
    """
    queryset            = UserSegment.objects.filter(is_active=True)
    serializer_class    = UserSegmentSerializer
    permission_classes  = [IsAuthenticated]

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def refresh(self, request):
        """Segment refresh করো।"""
        # Celery task queue করো
        return self.success_response(message='Segment refresh queued.')

    @action(detail=False, methods=['get'])
    def my_segment(self, request):
        """Current user কোন segment এ আছে।"""
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        segment = SegmentRepository.get_user_segment(str(request.user.id), tenant_id)
        if segment:
            return self.success_response(data=UserSegmentSerializer(segment).data)
        return self.success_response(data=None, message='User not yet assigned to any segment.')


# ══════════════════════════════════════════════════════════════════════
# A/B TEST VIEWSET
# ══════════════════════════════════════════════════════════════════════

class ABTestViewSet(TenantMixin, BaseViewSet):
    """
    A/B Test experiment management।
    """
    queryset            = ABTestExperiment.objects.all()
    serializer_class    = ABTestExperimentSerializer
    permission_classes  = [IsAuthenticated]

    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        serializer.save(tenant=tenant, created_by=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def start(self, request, pk=None):
        """Experiment শুরু করো।"""
        from django.utils import timezone
        ABTestExperiment.objects.filter(id=pk).update(
            status='running', started_at=timezone.now()
        )
        return self.success_response(message='Experiment started.')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def stop(self, request, pk=None):
        """Experiment বন্ধ করো।"""
        from django.utils import timezone
        ABTestExperiment.objects.filter(id=pk).update(
            status='completed', ended_at=timezone.now()
        )
        return self.success_response(message='Experiment completed.')


# ══════════════════════════════════════════════════════════════════════
# INSIGHT VIEWSET
# ══════════════════════════════════════════════════════════════════════

class InsightViewSet(TenantMixin, BaseViewSet):
    """
    AI-generated business insights।

    GET  /ai-engine/insights/           → list active insights
    POST /ai-engine/insights/{id}/dismiss/ → dismiss insight
    POST /ai-engine/insights/generate/  → force generate insights
    """
    queryset            = InsightModel.objects.filter(is_active=True, is_dismissed=False)
    serializer_class    = InsightModelSerializer
    permission_classes  = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        InsightGenerationService.dismiss_insight(pk, str(request.user.id))
        return self.success_response(message='Insight dismissed.')

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def generate(self, request):
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        insights = InsightGenerationService.generate_daily_insights(tenant_id)
        return self.success_response(
            data={'generated': len(insights)},
            message=f'{len(insights)} insights generated.'
        )


# ══════════════════════════════════════════════════════════════════════
# PERSONALIZATION VIEWSET
# ══════════════════════════════════════════════════════════════════════

class PersonalizationViewSet(TenantMixin, BaseViewSet):
    """
    User personalization profiles।

    GET  /ai-engine/personalization/me/  → my profile
    POST /ai-engine/personalization/refresh/ → force refresh
    """
    queryset            = PersonalizationProfile.objects.all()
    serializer_class    = PersonalizationProfileSerializer
    permission_classes  = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Current user এর personalization profile।"""
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        profile = PersonalizationService.get_or_build_profile(request.user, tenant_id)
        return self.success_response(data=PersonalizationProfileSerializer(profile).data)

    @action(detail=False, methods=['post'])
    def refresh(self, request):
        """Profile force refresh।"""
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        profile = PersonalizationService.get_or_build_profile(request.user, tenant_id)
        PersonalizationService.refresh_profile(request.user, profile, tenant_id)
        return self.success_response(message='Personalization profile refreshed.')


# ══════════════════════════════════════════════════════════════════════
# CHURN RISK VIEWSET
# ══════════════════════════════════════════════════════════════════════

class ChurnRiskViewSet(TenantMixin, BaseViewSet):
    """
    Churn risk profiles।
    """
    queryset            = ChurnRiskProfile.objects.all()
    serializer_class    = ChurnRiskProfileSerializer
    permission_classes  = [IsAuthenticated]

    @action(detail=False, methods=['get'])
    def high_risk(self, request):
        """High risk users।"""
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        users = ChurnRepository.get_high_risk_users(tenant_id, limit=100)
        return self.success_response(data=ChurnRiskProfileSerializer(users, many=True).data)

    @action(detail=False, methods=['post'])
    def predict_me(self, request):
        """Current user এর churn predict।"""
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', None)
        result = ChurnPredictionService.predict_churn(request.user, tenant_id)
        return self.success_response(data=result)


# ══════════════════════════════════════════════════════════════════════
# DATA DRIFT VIEWSET
# ══════════════════════════════════════════════════════════════════════

class DataDriftViewSet(TenantMixin, BaseViewSet):
    """
    Model data drift monitoring।
    """
    queryset            = DataDriftLog.objects.all()
    serializer_class    = DataDriftLogSerializer
    permission_classes  = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Critical drift logs।"""
        logs = DataDriftLog.objects.filter(status='critical').order_by('-detected_at')[:50]
        return self.success_response(data=DataDriftLogSerializer(logs, many=True).data)


# ══════════════════════════════════════════════════════════════════════
# EXPERIMENT TRACKING VIEWSET
# ══════════════════════════════════════════════════════════════════════

class ExperimentTrackingViewSet(TenantMixin, BaseViewSet):
    """
    MLflow-style experiment tracking।
    """
    queryset            = ExperimentTracking.objects.all()
    serializer_class    = ExperimentTrackingSerializer
    permission_classes  = [IsAuthenticated, IsAdminUser]


# ══════════════════════════════════════════════════════════════════════
# FEATURE STORE VIEWSET
# ══════════════════════════════════════════════════════════════════════

class FeatureStoreViewSet(TenantMixin, BaseViewSet):
    """
    Feature Store management।
    """
    queryset            = FeatureStore.objects.filter(is_active=True)
    serializer_class    = FeatureStoreSerializer
    permission_classes  = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=['get'])
    def entity_features(self, request):
        """Entity এর সব features।"""
        entity_id   = request.query_params.get('entity_id')
        entity_type = request.query_params.get('entity_type', 'user')
        if not entity_id:
            return self.error_response('entity_id is required.')
        features = FeatureStore.objects.filter(
            entity_id=entity_id, is_active=True
        ).order_by('-created_at')
        return self.success_response(data=FeatureStoreSerializer(features, many=True).data)


# ── Import fix for SegmentRepository ──────────────────────────────────
from .repository import (
    AnomalyRepository, ChurnRepository, SegmentRepository
)
