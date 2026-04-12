"""
api/ai_engine/schemas.py
========================
AI Engine — DRF Serializers (Schemas)।
"""

from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from .models import (
    AIModel, ModelVersion, TrainingJob, ModelMetric,
    FeatureStore, UserEmbedding, ItemEmbedding,
    PredictionLog, AnomalyDetectionLog, ChurnRiskProfile,
    RecommendationResult, UserSegment, ABTestExperiment,
    TextAnalysisResult, ImageAnalysisResult, ContentModerationLog,
    ExperimentTracking, PersonalizationProfile, SegmentationModel,
    InsightModel, DataDriftLog,
)


# ── AI Model ────────────────────────────────────────────────────────────

class AIModelListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = [
            'id', 'name', 'slug', 'algorithm', 'task_type',
            'status', 'active_version', 'is_active', 'is_production',
            'created_at', 'updated_at',
        ]


class AIModelDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = '__all__'
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']

    def validate_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError(_('Model name must be at least 3 characters.'))
        return value.strip()


class AIModelCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = [
            'name', 'description', 'algorithm', 'task_type',
            'hyperparameters', 'feature_config', 'target_column',
        ]


# ── Model Version ───────────────────────────────────────────────────────

class ModelVersionSerializer(serializers.ModelSerializer):
    ai_model_name = serializers.CharField(source='ai_model.name', read_only=True)

    class Meta:
        model = ModelVersion
        fields = [
            'id', 'ai_model', 'ai_model_name', 'version', 'stage',
            'accuracy', 'precision', 'recall', 'f1_score', 'auc_roc',
            'training_rows', 'feature_count', 'trained_at',
            'training_duration_s', 'model_size_mb', 'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── Training Job ────────────────────────────────────────────────────────

class TrainingJobSerializer(serializers.ModelSerializer):
    ai_model_name = serializers.CharField(source='ai_model.name', read_only=True)
    duration_minutes = serializers.SerializerMethodField()

    class Meta:
        model = TrainingJob
        fields = [
            'id', 'job_id', 'ai_model', 'ai_model_name', 'status',
            'started_at', 'finished_at', 'duration_seconds', 'duration_minutes',
            'train_rows', 'val_rows', 'error_message', 'worker_node',
            'created_at',
        ]
        read_only_fields = ['id', 'job_id', 'created_at']

    def get_duration_minutes(self, obj):
        return round(obj.duration_seconds / 60, 2) if obj.duration_seconds else 0.0


class TrainingJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingJob
        fields = ['ai_model', 'dataset_path', 'hyperparameters']


# ── Model Metric ────────────────────────────────────────────────────────

class ModelMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelMetric
        fields = '__all__'
        read_only_fields = ['id', 'evaluated_at']


# ── Prediction Log ──────────────────────────────────────────────────────

class PredictionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionLog
        fields = [
            'id', 'prediction_type', 'user', 'entity_id',
            'confidence', 'predicted_class', 'predicted_value',
            'is_correct', 'inference_ms', 'request_id', 'created_at',
        ]
        read_only_fields = ['id', 'request_id', 'created_at']


class PredictionRequestSerializer(serializers.Serializer):
    prediction_type = serializers.ChoiceField(choices=[
        'fraud', 'churn', 'ltv', 'conversion', 'click', 'revenue', 'custom'
    ])
    user_id         = serializers.CharField(required=False, allow_blank=True)
    entity_id       = serializers.CharField(required=False, allow_blank=True)
    input_data      = serializers.DictField(default=dict)


class PredictionResponseSerializer(serializers.Serializer):
    prediction_type = serializers.CharField()
    prediction      = serializers.DictField()
    confidence      = serializers.FloatField()
    predicted_class = serializers.CharField(allow_blank=True)
    predicted_value = serializers.FloatField(allow_null=True)
    request_id      = serializers.UUIDField()
    inference_ms    = serializers.FloatField()


# ── Anomaly Detection ────────────────────────────────────────────────────

class AnomalyDetectionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnomalyDetectionLog
        fields = [
            'id', 'anomaly_type', 'severity', 'status',
            'user', 'entity_id', 'anomaly_score', 'threshold',
            'description', 'auto_action_taken', 'ip_address',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── Churn Risk ───────────────────────────────────────────────────────────

class ChurnRiskProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = ChurnRiskProfile
        fields = [
            'id', 'user', 'username', 'churn_probability', 'risk_level',
            'days_since_login', 'days_since_last_earn',
            'recent_activity_score', 'engagement_trend',
            'top_risk_factors', 'retention_actions', 'predicted_at',
        ]
        read_only_fields = ['id', 'predicted_at']


# ── Recommendation ────────────────────────────────────────────────────────

class RecommendationResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecommendationResult
        fields = [
            'id', 'user', 'engine', 'item_type',
            'recommended_items', 'item_count',
            'ctr', 'request_id', 'created_at',
        ]
        read_only_fields = ['id', 'request_id', 'created_at']


class RecommendationRequestSerializer(serializers.Serializer):
    engine      = serializers.ChoiceField(
        choices=['hybrid', 'collaborative', 'content_based', 'popularity', 'trending'],
        default='hybrid'
    )
    item_type   = serializers.ChoiceField(
        choices=['offer', 'product', 'content', 'ad', 'task'],
        default='offer'
    )
    count       = serializers.IntegerField(min_value=1, max_value=50, default=10)
    context     = serializers.DictField(default=dict)


# ── User Segment ──────────────────────────────────────────────────────────

class UserSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSegment
        fields = [
            'id', 'name', 'description', 'method',
            'user_count', 'avg_revenue', 'avg_ltv', 'churn_rate',
            'is_active', 'last_refreshed', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'last_refreshed']


# ── A/B Test ──────────────────────────────────────────────────────────────

class ABTestExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ABTestExperiment
        fields = [
            'id', 'name', 'description', 'hypothesis', 'status',
            'control_model', 'control_traffic', 'treatment_traffic',
            'started_at', 'ended_at', 'winner', 'confidence_level',
            'lift_percentage', 'total_participants', 'target_metric',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        ctrl = data.get('control_traffic', 50)
        treat = data.get('treatment_traffic', 50)
        if ctrl + treat != 100:
            raise serializers.ValidationError(_('Traffic split must sum to 100.'))
        return data


# ── NLP ───────────────────────────────────────────────────────────────────

class TextAnalysisRequestSerializer(serializers.Serializer):
    text            = serializers.CharField(min_length=3, max_length=5000)
    analysis_type   = serializers.ChoiceField(
        choices=['sentiment', 'intent', 'entity', 'spam', 'topic', 'keyword', 'profanity'],
        default='sentiment'
    )
    source_type     = serializers.CharField(required=False, default='')
    source_id       = serializers.CharField(required=False, default='')


class TextAnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextAnalysisResult
        fields = [
            'id', 'analysis_type', 'detected_language',
            'sentiment', 'sentiment_score',
            'intent', 'intent_confidence',
            'entities', 'keywords', 'topics', 'summary',
            'is_spam', 'has_profanity', 'is_flagged',
            'inference_ms', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── CV ────────────────────────────────────────────────────────────────────

class ImageAnalysisRequestSerializer(serializers.Serializer):
    image_url       = serializers.URLField(required=False)
    analysis_type   = serializers.ChoiceField(
        choices=['ocr', 'object_detect', 'face_detect', 'id_card', 'nsfw', 'quality'],
        default='ocr'
    )
    source_type     = serializers.CharField(required=False, default='')
    source_id       = serializers.CharField(required=False, default='')


class ImageAnalysisResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImageAnalysisResult
        fields = [
            'id', 'analysis_type', 'extracted_text', 'ocr_confidence',
            'detected_objects', 'detected_faces',
            'is_nsfw', 'nsfw_confidence',
            'quality_score', 'is_blurry', 'is_flagged',
            'inference_ms', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── Content Moderation ────────────────────────────────────────────────────

class ContentModerationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentModerationLog
        fields = [
            'id', 'content_type', 'content_id', 'content_preview',
            'violation_type', 'violation_score', 'action_taken',
            'is_auto_action', 'is_false_positive', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── Insight ───────────────────────────────────────────────────────────────

class InsightModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = InsightModel
        fields = [
            'id', 'title', 'description', 'insight_type', 'priority',
            'supporting_data', 'recommended_actions',
            'estimated_impact', 'confidence_score',
            'is_active', 'expires_at', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


# ── Personalization Profile ───────────────────────────────────────────────

class PersonalizationProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = PersonalizationProfile
        fields = [
            'id', 'user', 'username',
            'preferred_categories', 'preferred_offer_types',
            'preferred_time_slots', 'preferred_devices',
            'is_deal_seeker', 'is_high_engagement', 'is_mobile_first',
            'price_sensitivity', 'activity_score',
            'estimated_ltv', 'ltv_segment',
            'engagement_score', 'loyalty_score', 'risk_score',
            'ai_insights', 'recommended_actions',
            'last_refreshed',
        ]
        read_only_fields = ['id', 'last_refreshed']


# ── Data Drift ────────────────────────────────────────────────────────────

class DataDriftLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataDriftLog
        fields = [
            'id', 'ai_model', 'drift_type', 'status',
            'drift_score', 'psi_score', 'ks_statistic',
            'drifted_features', 'retrain_recommended',
            'detected_at',
        ]
        read_only_fields = ['id', 'detected_at']


# ── Experiment Tracking ───────────────────────────────────────────────────

class ExperimentTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentTracking
        fields = [
            'id', 'run_id', 'experiment_name', 'status',
            'params', 'metrics', 'tags',
            'started_at', 'ended_at', 'notes',
            'created_at',
        ]
        read_only_fields = ['id', 'run_id', 'created_at']


# ── Feature Store ─────────────────────────────────────────────────────────

class FeatureStoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureStore
        fields = [
            'id', 'name', 'feature_type', 'entity_id', 'entity_type',
            'features', 'feature_count', 'version', 'is_active', 'expires_at',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']
