# api/ai_engine/admin.py
"""
AI Engine — Django Admin
সব models এর rich admin interface।
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    AIModel, ModelVersion, TrainingJob, ModelMetric, FeatureStore,
    UserEmbedding, ItemEmbedding, PredictionLog, AnomalyDetectionLog,
    ChurnRiskProfile, RecommendationResult, UserSegment, ABTestExperiment,
    TextAnalysisResult, ImageAnalysisResult, ContentModerationLog,
    ExperimentTracking, PersonalizationProfile, SegmentationModel,
    InsightModel, DataDriftLog,
)


# ──────────────────────────────────────────────────────────────────────────────
# INLINE CLASSES
# ──────────────────────────────────────────────────────────────────────────────

class ModelVersionInline(admin.TabularInline):
    model = ModelVersion
    extra = 0
    fields = ['version', 'stage', 'accuracy', 'f1_score', 'is_active', 'trained_at']
    readonly_fields = ['trained_at']
    show_change_link = True
    max_num = 5


class ModelMetricInline(admin.TabularInline):
    model = ModelMetric
    extra = 0
    fields = ['metric_type', 'accuracy', 'f1_score', 'auc_roc', 'rmse', 'evaluated_at']
    readonly_fields = ['evaluated_at']
    show_change_link = True
    max_num = 5


class TrainingJobInline(admin.TabularInline):
    model = TrainingJob
    extra = 0
    fields = ['job_id', 'status', 'started_at', 'finished_at', 'duration_seconds']
    readonly_fields = ['job_id', 'started_at', 'finished_at']
    show_change_link = True
    max_num = 5


# ──────────────────────────────────────────────────────────────────────────────
# AI MODEL ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'algorithm', 'task_type', 'status_badge',
        'is_active', 'is_production', 'active_version',
        'tenant', 'created_at',
    ]
    list_filter = ['status', 'algorithm', 'task_type', 'is_active', 'is_production']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ModelVersionInline, TrainingJobInline, ModelMetricInline]
    prepopulated_fields = {'slug': ('name',)}

    fieldsets = (
        ('🤖 Model Identity', {
            'fields': ('name', 'slug', 'description', 'algorithm', 'task_type', 'status', 'active_version'),
        }),
        ('⚙️ Config', {
            'fields': ('hyperparameters', 'feature_config', 'target_column'),
            'classes': ('collapse',),
        }),
        ('🚀 Deployment', {
            'fields': ('is_active', 'is_production', 'endpoint_url'),
        }),
        ('🏢 Ownership', {
            'fields': ('tenant', 'created_by'),
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'draft':       '#6b7280',
            'training':    '#f59e0b',
            'trained':     '#3b82f6',
            'evaluating':  '#8b5cf6',
            'deployed':    '#22c55e',
            'deprecated':  '#9ca3af',
            'failed':      '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


# ──────────────────────────────────────────────────────────────────────────────
# MODEL VERSION ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = [
        'ai_model', 'version', 'stage_badge',
        'accuracy', 'f1_score', 'auc_roc',
        'model_size_mb', 'is_active', 'trained_at',
    ]
    list_filter = ['stage', 'is_active', 'ai_model']
    search_fields = ['ai_model__name', 'version', 'notes']
    readonly_fields = ['trained_at']

    fieldsets = (
        ('📦 Version Info', {
            'fields': ('ai_model', 'version', 'stage', 'is_active'),
        }),
        ('💾 Storage', {
            'fields': ('model_file_path', 'artifact_uri', 'model_size_mb'),
            'classes': ('collapse',),
        }),
        ('📊 Performance', {
            'fields': ('accuracy', 'precision', 'recall', 'f1_score', 'auc_roc', 'rmse'),
        }),
        ('🏋️ Training Info', {
            'fields': ('training_rows', 'feature_count', 'trained_at', 'training_duration_s'),
        }),
        ('📝 Notes', {
            'fields': ('notes',),
            'classes': ('collapse',),
        }),
    )

    def stage_badge(self, obj):
        colors = {
            'development': '#6b7280',
            'staging':     '#f59e0b',
            'production':  '#22c55e',
            'archived':    '#9ca3af',
        }
        color = colors.get(obj.stage, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_stage_display()
        )
    stage_badge.short_description = 'Stage'


# ──────────────────────────────────────────────────────────────────────────────
# TRAINING JOB ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(TrainingJob)
class TrainingJobAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'ai_model', 'status_badge',
        'train_rows', 'val_rows', 'duration_seconds',
        'started_at', 'finished_at', 'triggered_by',
    ]
    list_filter = ['status', 'ai_model']
    search_fields = ['job_id', 'ai_model__name', 'worker_node']
    readonly_fields = ['job_id', 'started_at', 'finished_at']

    fieldsets = (
        ('🏋️ Job Info', {
            'fields': ('job_id', 'ai_model', 'model_version', 'status', 'worker_node'),
        }),
        ('📊 Data', {
            'fields': ('dataset_path', 'train_rows', 'val_rows'),
        }),
        ('⏱️ Timing', {
            'fields': ('started_at', 'finished_at', 'duration_seconds'),
        }),
        ('⚙️ Config', {
            'fields': ('hyperparameters',),
            'classes': ('collapse',),
        }),
        ('📝 Logs', {
            'fields': ('log_output', 'error_message'),
            'classes': ('collapse',),
        }),
        ('👤 Triggered By', {
            'fields': ('triggered_by', 'tenant'),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'queued':    '#6b7280',
            'running':   '#f59e0b',
            'completed': '#22c55e',
            'failed':    '#ef4444',
            'cancelled': '#9ca3af',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'


# ──────────────────────────────────────────────────────────────────────────────
# MODEL METRIC ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ModelMetric)
class ModelMetricAdmin(admin.ModelAdmin):
    list_display = [
        'ai_model', 'model_version', 'metric_type',
        'accuracy', 'precision', 'recall', 'f1_score',
        'auc_roc', 'avg_inference_ms', 'evaluated_at',
    ]
    list_filter = ['metric_type', 'ai_model']
    search_fields = ['ai_model__name']
    readonly_fields = ['evaluated_at']

    fieldsets = (
        ('📊 Info', {
            'fields': ('ai_model', 'model_version', 'metric_type'),
        }),
        ('🎯 Classification Metrics', {
            'fields': ('accuracy', 'precision', 'recall', 'f1_score', 'auc_roc', 'log_loss'),
        }),
        ('📉 Regression Metrics', {
            'fields': ('mae', 'mse', 'rmse', 'r2_score'),
        }),
        ('💼 Business Metrics', {
            'fields': ('lift_score', 'ks_statistic'),
        }),
        ('⚡ Latency', {
            'fields': ('avg_inference_ms', 'p99_latency_ms'),
        }),
        ('📝 Notes', {
            'fields': ('notes', 'confusion_matrix', 'extra_metrics'),
            'classes': ('collapse',),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# FEATURE STORE ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(FeatureStore)
class FeatureStoreAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'feature_type', 'entity_id', 'entity_type',
        'feature_count', 'version', 'is_active', 'expires_at', 'created_at',
    ]
    list_filter = ['feature_type', 'entity_type', 'is_active']
    search_fields = ['name', 'entity_id', 'pipeline_run_id']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('🗄️ Feature Set', {
            'fields': ('name', 'feature_type', 'entity_id', 'entity_type', 'tenant'),
        }),
        ('📊 Data', {
            'fields': ('features', 'feature_names', 'feature_count'),
        }),
        ('🔖 Versioning', {
            'fields': ('version', 'pipeline_run_id', 'is_active', 'expires_at'),
        }),
        ('🕐 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# USER EMBEDDING ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(UserEmbedding)
class UserEmbeddingAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'embedding_type', 'dimensions',
        'interaction_count', 'quality_score',
        'is_stale', 'model_version', 'created_at',
    ]
    list_filter = ['embedding_type', 'is_stale']
    search_fields = ['user__username', 'user__email', 'model_version']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('👤 User & Model', {
            'fields': ('user', 'ai_model', 'embedding_type', 'tenant'),
        }),
        ('🔢 Vector', {
            'fields': ('vector', 'dimensions'),
        }),
        ('📊 Metadata', {
            'fields': ('interaction_count', 'last_activity_at', 'quality_score', 'model_version', 'is_stale'),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# ITEM EMBEDDING ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ItemEmbedding)
class ItemEmbeddingAdmin(admin.ModelAdmin):
    list_display = [
        'item_id', 'item_type', 'item_name',
        'category', 'dimensions', 'popularity_score',
        'is_active', 'model_version', 'created_at',
    ]
    list_filter = ['item_type', 'is_active']
    search_fields = ['item_id', 'item_name', 'category']
    readonly_fields = ['created_at', 'updated_at']


# ──────────────────────────────────────────────────────────────────────────────
# PREDICTION LOG ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = [
        'request_id', 'prediction_type', 'user',
        'predicted_class', 'confidence_display',
        'is_correct', 'inference_ms', 'created_at',
    ]
    list_filter = ['prediction_type', 'is_correct']
    search_fields = ['user__username', 'entity_id', 'predicted_class']
    readonly_fields = ['request_id', 'created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('🎯 Prediction Info', {
            'fields': ('ai_model', 'model_version', 'prediction_type', 'request_id'),
        }),
        ('👤 Entity', {
            'fields': ('user', 'entity_id', 'entity_type', 'tenant'),
        }),
        ('📥 Input / Output', {
            'fields': ('input_data', 'prediction', 'confidence', 'predicted_class', 'predicted_value'),
        }),
        ('✅ Ground Truth', {
            'fields': ('actual_outcome', 'is_correct', 'feedback_at'),
        }),
        ('⚡ Performance', {
            'fields': ('inference_ms',),
        }),
    )

    def confidence_display(self, obj):
        color = '#22c55e' if obj.confidence >= 0.8 else '#f59e0b' if obj.confidence >= 0.5 else '#ef4444'
        return format_html('<strong style="color:{}">{:.1%}</strong>', color, obj.confidence)
    confidence_display.short_description = 'Confidence'


# ──────────────────────────────────────────────────────────────────────────────
# ANOMALY DETECTION LOG ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(AnomalyDetectionLog)
class AnomalyDetectionLogAdmin(admin.ModelAdmin):
    list_display = [
        'anomaly_type', 'severity_badge', 'status_badge',
        'user', 'anomaly_score_display',
        'auto_action_taken', 'ip_address', 'created_at',
    ]
    list_filter = ['anomaly_type', 'severity', 'status']
    search_fields = ['user__username', 'ip_address', 'entity_id']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('🚨 Anomaly Info', {
            'fields': ('anomaly_type', 'severity', 'status', 'ai_model', 'tenant'),
        }),
        ('👤 Entity', {
            'fields': ('user', 'entity_id', 'entity_type'),
        }),
        ('📊 Detection', {
            'fields': ('anomaly_score', 'threshold', 'description', 'evidence_data'),
        }),
        ('⚡ Action', {
            'fields': ('auto_action_taken', 'resolved_by', 'resolved_at', 'resolution_notes'),
        }),
        ('🌐 Context', {
            'fields': ('ip_address', 'user_agent', 'metadata'),
            'classes': ('collapse',),
        }),
    )

    def severity_badge(self, obj):
        colors = {
            'low':      '#22c55e',
            'medium':   '#f59e0b',
            'high':     '#ef4444',
            'critical': '#7f1d1d',
        }
        color = colors.get(obj.severity, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.severity.upper()
        )
    severity_badge.short_description = 'Severity'

    def status_badge(self, obj):
        colors = {
            'open':           '#ef4444',
            'investigating':  '#f59e0b',
            'resolved':       '#22c55e',
            'false_positive': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def anomaly_score_display(self, obj):
        color = '#22c55e' if obj.anomaly_score < 0.3 else '#f59e0b' if obj.anomaly_score < 0.7 else '#ef4444'
        return format_html('<strong style="color:{}">{:.2f}</strong>', color, obj.anomaly_score)
    anomaly_score_display.short_description = 'Score'


# ──────────────────────────────────────────────────────────────────────────────
# CHURN RISK PROFILE ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ChurnRiskProfile)
class ChurnRiskProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'risk_level_badge', 'churn_probability_display',
        'days_since_login', 'days_since_last_earn',
        'engagement_trend', 'predicted_at',
    ]
    list_filter = ['risk_level', 'engagement_trend']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['predicted_at']

    fieldsets = (
        ('👤 User', {
            'fields': ('user', 'tenant', 'ai_model'),
        }),
        ('📊 Risk Score', {
            'fields': ('churn_probability', 'risk_level', 'model_version', 'predicted_at'),
        }),
        ('📈 Factors', {
            'fields': (
                'days_since_login', 'days_since_last_earn',
                'recent_activity_score', 'engagement_trend',
            ),
        }),
        ('💡 Insights', {
            'fields': ('top_risk_factors', 'retention_actions'),
            'classes': ('collapse',),
        }),
    )

    def risk_level_badge(self, obj):
        colors = {
            'very_low': '#22c55e',
            'low':      '#84cc16',
            'medium':   '#f59e0b',
            'high':     '#ef4444',
            'very_high':'#7f1d1d',
        }
        color = colors.get(obj.risk_level, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_risk_level_display()
        )
    risk_level_badge.short_description = 'Risk Level'

    def churn_probability_display(self, obj):
        color = '#22c55e' if obj.churn_probability < 0.3 else '#f59e0b' if obj.churn_probability < 0.6 else '#ef4444'
        return format_html('<strong style="color:{}">{:.1%}</strong>', color, obj.churn_probability)
    churn_probability_display.short_description = 'Churn %'


# ──────────────────────────────────────────────────────────────────────────────
# RECOMMENDATION RESULT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(RecommendationResult)
class RecommendationResultAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'engine', 'item_type',
        'item_count', 'ctr_display',
        'clicked_item_id', 'converted_item_id', 'created_at',
    ]
    list_filter = ['engine', 'item_type']
    search_fields = ['user__username', 'session_id']
    readonly_fields = ['request_id', 'created_at']
    date_hierarchy = 'created_at'

    def ctr_display(self, obj):
        color = '#22c55e' if obj.ctr >= 0.05 else '#f59e0b' if obj.ctr >= 0.01 else '#ef4444'
        return format_html('<span style="color:{}">{:.2%}</span>', color, obj.ctr)
    ctr_display.short_description = 'CTR'


# ──────────────────────────────────────────────────────────────────────────────
# USER SEGMENT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(UserSegment)
class UserSegmentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'method', 'user_count',
        'avg_revenue', 'avg_ltv', 'churn_rate',
        'is_active', 'auto_refresh', 'last_refreshed',
    ]
    list_filter = ['method', 'is_active', 'auto_refresh']
    search_fields = ['name', 'description']
    readonly_fields = ['last_refreshed', 'created_at', 'updated_at']

    fieldsets = (
        ('📊 Segment Info', {
            'fields': ('name', 'description', 'method', 'tenant', 'ai_model'),
        }),
        ('🎯 Criteria', {
            'fields': ('criteria', 'features_used'),
        }),
        ('👥 Members', {
            'fields': ('user_count', 'user_ids'),
        }),
        ('💰 Business Value', {
            'fields': ('avg_revenue', 'avg_ltv', 'churn_rate'),
        }),
        ('⚙️ Settings', {
            'fields': ('is_active', 'auto_refresh', 'last_refreshed', 'model_version'),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# A/B TEST EXPERIMENT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ABTestExperiment)
class ABTestExperimentAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status_badge', 'winner_badge',
        'total_participants', 'confidence_level',
        'lift_percentage', 'started_at', 'ended_at',
    ]
    list_filter = ['status', 'winner']
    search_fields = ['name', 'description', 'hypothesis']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('🧪 Experiment Info', {
            'fields': ('name', 'description', 'hypothesis', 'status', 'tenant'),
        }),
        ('🤖 Models', {
            'fields': ('control_model', 'treatment_models'),
        }),
        ('📊 Traffic Split', {
            'fields': ('control_traffic', 'treatment_traffic', 'target_metric'),
        }),
        ('⏱️ Timing', {
            'fields': ('started_at', 'ended_at', 'planned_days'),
        }),
        ('🏆 Results', {
            'fields': (
                'control_metrics', 'treatment_metrics',
                'winner', 'confidence_level', 'lift_percentage',
                'total_participants',
            ),
        }),
        ('👤 Created By', {
            'fields': ('created_by',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'draft':     '#6b7280',
            'running':   '#22c55e',
            'paused':    '#f59e0b',
            'completed': '#3b82f6',
            'cancelled': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def winner_badge(self, obj):
        if obj.winner == 'no_winner':
            return format_html('<span style="color:#6b7280">No Winner</span>')
        if obj.winner == 'pending':
            return format_html('<span style="color:#f59e0b">Pending</span>')
        return format_html('<span style="color:#22c55e;font-weight:bold">🏆 {}</span>', obj.get_winner_display())
    winner_badge.short_description = 'Winner'


# ──────────────────────────────────────────────────────────────────────────────
# TEXT ANALYSIS RESULT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(TextAnalysisResult)
class TextAnalysisResultAdmin(admin.ModelAdmin):
    list_display = [
        'analysis_type', 'sentiment_badge', 'detected_language',
        'sentiment_score', 'intent', 'is_spam',
        'has_profanity', 'is_flagged', 'created_at',
    ]
    list_filter = ['analysis_type', 'sentiment', 'is_spam', 'has_profanity', 'is_flagged']
    search_fields = ['source_id', 'input_text', 'intent']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('📝 Analysis Info', {
            'fields': ('analysis_type', 'source_type', 'source_id', 'user', 'tenant', 'ai_model'),
        }),
        ('📥 Input', {
            'fields': ('input_text', 'detected_language'),
        }),
        ('🎯 Results', {
            'fields': (
                'sentiment', 'sentiment_score',
                'intent', 'intent_confidence',
                'entities', 'keywords', 'topics', 'summary',
            ),
        }),
        ('🚩 Flags', {
            'fields': ('is_spam', 'has_profanity', 'is_flagged', 'spam_confidence'),
        }),
        ('⚙️ Technical', {
            'fields': ('raw_output', 'inference_ms', 'model_version'),
            'classes': ('collapse',),
        }),
    )

    def sentiment_badge(self, obj):
        colors = {
            'positive': '#22c55e',
            'negative': '#ef4444',
            'neutral':  '#6b7280',
            'mixed':    '#f59e0b',
        }
        color = colors.get(obj.sentiment, '#6b7280')
        return format_html(
            '<span style="color:{};font-weight:bold">{}</span>',
            color, obj.sentiment or 'N/A'
        )
    sentiment_badge.short_description = 'Sentiment'


# ──────────────────────────────────────────────────────────────────────────────
# IMAGE ANALYSIS RESULT ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ImageAnalysisResult)
class ImageAnalysisResultAdmin(admin.ModelAdmin):
    list_display = [
        'analysis_type', 'source_type', 'source_id',
        'detected_faces', 'is_nsfw', 'is_flagged',
        'quality_score', 'is_blurry', 'created_at',
    ]
    list_filter = ['analysis_type', 'is_nsfw', 'is_flagged', 'is_blurry']
    search_fields = ['source_id', 'image_url', 'extracted_text']
    readonly_fields = ['created_at']

    fieldsets = (
        ('🖼️ Image Info', {
            'fields': ('analysis_type', 'source_type', 'source_id', 'image_url', 'image_path', 'user', 'tenant'),
        }),
        ('🔍 OCR', {
            'fields': ('extracted_text', 'ocr_confidence'),
        }),
        ('📦 Detection', {
            'fields': ('detected_objects', 'detected_faces', 'bounding_boxes', 'labels'),
        }),
        ('🚩 Safety', {
            'fields': ('is_nsfw', 'nsfw_confidence', 'is_flagged'),
        }),
        ('📊 Quality', {
            'fields': ('quality_score', 'is_blurry', 'resolution'),
        }),
        ('⚙️ Technical', {
            'fields': ('raw_output', 'inference_ms', 'model_version'),
            'classes': ('collapse',),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# CONTENT MODERATION LOG ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ContentModerationLog)
class ContentModerationLogAdmin(admin.ModelAdmin):
    list_display = [
        'content_type', 'violation_type', 'violation_score_display',
        'action_badge', 'user', 'is_auto_action',
        'is_false_positive', 'reviewed_by', 'created_at',
    ]
    list_filter = [
        'content_type', 'violation_type', 'action_taken',
        'is_auto_action', 'is_false_positive',
    ]
    search_fields = ['content_id', 'user__username', 'content_preview']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    actions = ['mark_false_positive', 'mark_reviewed']

    fieldsets = (
        ('📋 Content Info', {
            'fields': ('content_type', 'content_id', 'content_preview', 'user', 'tenant', 'ai_model'),
        }),
        ('🚨 Violation', {
            'fields': ('violation_type', 'violation_score', 'detection_reasons'),
        }),
        ('⚡ Action', {
            'fields': ('action_taken', 'is_auto_action', 'model_version'),
        }),
        ('✅ Review', {
            'fields': ('reviewed_by', 'reviewed_at', 'is_false_positive', 'review_notes'),
        }),
    )

    def violation_score_display(self, obj):
        color = '#22c55e' if obj.violation_score < 0.3 else '#f59e0b' if obj.violation_score < 0.7 else '#ef4444'
        return format_html('<strong style="color:{}">{:.2f}</strong>', color, obj.violation_score)
    violation_score_display.short_description = 'Score'

    def action_badge(self, obj):
        colors = {
            'allow':        '#22c55e',
            'warn':         '#f59e0b',
            'remove':       '#ef4444',
            'shadow_ban':   '#8b5cf6',
            'block_user':   '#7f1d1d',
            'review_needed':'#3b82f6',
        }
        color = colors.get(obj.action_taken, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_action_taken_display()
        )
    action_badge.short_description = 'Action'

    @admin.action(description='✅ Mark selected as false positive')
    def mark_false_positive(self, request, queryset):
        count = queryset.update(is_false_positive=True, action_taken='allow')
        self.message_user(request, f'{count} log(s) marked as false positive.')

    @admin.action(description='👁️ Mark selected as reviewed')
    def mark_reviewed(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f'{count} log(s) marked as reviewed.')


# ──────────────────────────────────────────────────────────────────────────────
# EXPERIMENT TRACKING ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(ExperimentTracking)
class ExperimentTrackingAdmin(admin.ModelAdmin):
    list_display = [
        'experiment_name', 'run_id', 'ai_model',
        'status_badge', 'started_at', 'ended_at',
        'source_commit', 'created_by',
    ]
    list_filter = ['status', 'ai_model']
    search_fields = ['experiment_name', 'run_id', 'source_commit']
    readonly_fields = ['run_id', 'created_at']

    fieldsets = (
        ('🧪 Experiment', {
            'fields': ('experiment_name', 'run_id', 'ai_model', 'status', 'tenant'),
        }),
        ('⚙️ Config', {
            'fields': ('params', 'tags', 'environment'),
            'classes': ('collapse',),
        }),
        ('📊 Results', {
            'fields': ('metrics', 'artifacts'),
        }),
        ('⏱️ Timing', {
            'fields': ('started_at', 'ended_at'),
        }),
        ('📝 Notes', {
            'fields': ('notes', 'source_commit', 'created_by'),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'running':  '#f59e0b',
            'finished': '#22c55e',
            'failed':   '#ef4444',
            'killed':   '#7f1d1d',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'


# ──────────────────────────────────────────────────────────────────────────────
# PERSONALIZATION PROFILE ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(PersonalizationProfile)
class PersonalizationProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'ltv_segment', 'estimated_ltv',
        'engagement_score', 'loyalty_score', 'risk_score',
        'is_deal_seeker', 'is_high_engagement',
        'is_mobile_first', 'last_refreshed',
    ]
    list_filter = ['ltv_segment', 'is_deal_seeker', 'is_high_engagement', 'is_mobile_first']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['last_refreshed', 'created_at', 'updated_at']

    fieldsets = (
        ('👤 User', {
            'fields': ('user', 'tenant'),
        }),
        ('❤️ Preferences', {
            'fields': (
                'preferred_categories', 'preferred_offer_types',
                'preferred_time_slots', 'preferred_devices', 'preferred_reward_types',
            ),
        }),
        ('🎭 Behavioral Traits', {
            'fields': (
                'is_deal_seeker', 'is_high_engagement',
                'is_mobile_first', 'price_sensitivity', 'activity_score',
            ),
        }),
        ('💰 LTV & Value', {
            'fields': ('estimated_ltv', 'ltv_segment'),
        }),
        ('📊 Scoring', {
            'fields': ('engagement_score', 'loyalty_score', 'risk_score'),
        }),
        ('💡 AI Insights', {
            'fields': ('ai_insights', 'recommended_actions'),
            'classes': ('collapse',),
        }),
        ('⚙️ Meta', {
            'fields': ('model_version', 'last_refreshed'),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# SEGMENTATION MODEL ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(SegmentationModel)
class SegmentationModelAdmin(admin.ModelAdmin):
    list_display = [
        'run_name', 'ai_model', 'algorithm',
        'n_clusters', 'total_users',
        'silhouette_score', 'inertia',
        'is_active', 'ran_at',
    ]
    list_filter = ['algorithm', 'is_active']
    search_fields = ['run_name', 'ai_model__name']
    readonly_fields = ['ran_at', 'created_at']

    fieldsets = (
        ('🔢 Segmentation Run', {
            'fields': ('run_name', 'ai_model', 'algorithm', 'tenant'),
        }),
        ('⚙️ Params', {
            'fields': ('n_clusters', 'features_used', 'params'),
        }),
        ('📊 Results', {
            'fields': ('silhouette_score', 'inertia', 'total_users', 'cluster_summary'),
        }),
        ('🚀 Status', {
            'fields': ('is_active', 'ran_at'),
        }),
    )


# ──────────────────────────────────────────────────────────────────────────────
# INSIGHT MODEL ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(InsightModel)
class InsightModelAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'insight_type', 'priority_badge',
        'confidence_score', 'is_active',
        'is_dismissed', 'expires_at', 'created_at',
    ]
    list_filter = ['insight_type', 'priority', 'is_active', 'is_dismissed']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('💡 Insight Info', {
            'fields': ('title', 'description', 'insight_type', 'priority', 'tenant', 'ai_model'),
        }),
        ('📊 Data', {
            'fields': ('supporting_data', 'chart_data', 'affected_metrics'),
            'classes': ('collapse',),
        }),
        ('💼 Business Impact', {
            'fields': ('estimated_impact', 'confidence_score', 'recommended_actions'),
        }),
        ('⚙️ Lifecycle', {
            'fields': ('is_active', 'is_dismissed', 'dismissed_by', 'dismissed_at', 'expires_at'),
        }),
    )

    def priority_badge(self, obj):
        colors = {
            'low':    '#6b7280',
            'medium': '#f59e0b',
            'high':   '#ef4444',
            'urgent': '#7f1d1d',
        }
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.priority.upper()
        )
    priority_badge.short_description = 'Priority'


# ──────────────────────────────────────────────────────────────────────────────
# DATA DRIFT LOG ADMIN
# ──────────────────────────────────────────────────────────────────────────────

@admin.register(DataDriftLog)
class DataDriftLogAdmin(admin.ModelAdmin):
    list_display = [
        'ai_model', 'drift_type', 'status_badge',
        'drift_score_display', 'psi_score', 'ks_statistic',
        'retrain_recommended', 'detected_at',
    ]
    list_filter = ['drift_type', 'status', 'retrain_recommended']
    search_fields = ['ai_model__name']
    readonly_fields = ['detected_at', 'created_at']
    date_hierarchy = 'detected_at'

    fieldsets = (
        ('📊 Drift Info', {
            'fields': ('ai_model', 'model_version', 'drift_type', 'status', 'tenant'),
        }),
        ('📉 Metrics', {
            'fields': ('drift_score', 'psi_score', 'ks_statistic', 'threshold'),
        }),
        ('🔍 Features', {
            'fields': ('drifted_features', 'feature_drift_scores'),
        }),
        ('⚡ Action', {
            'fields': ('retrain_recommended', 'notes'),
        }),
        ('⏱️ Window', {
            'fields': ('detected_at', 'window_start', 'window_end'),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'normal':   '#22c55e',
            'warning':  '#f59e0b',
            'critical': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def drift_score_display(self, obj):
        color = '#22c55e' if obj.drift_score < 0.1 else '#f59e0b' if obj.drift_score < 0.2 else '#ef4444'
        return format_html('<strong style="color:{}">{:.3f}</strong>', color, obj.drift_score)
    drift_score_display.short_description = 'Drift Score'


# ──────────────────────────────────────────────────────────────────────────────
# FORCE REGISTER TO MODERN ADMIN SITE
# ──────────────────────────────────────────────────────────────────────────────

def _force_register_ai_engine():
    try:
        from api.admin_panel.admin import admin_site as modern_site
        if modern_site is None:
            return
        pairs = [
            (AIModel, AIModelAdmin),
            (ModelVersion, ModelVersionAdmin),
            (TrainingJob, TrainingJobAdmin),
            (ModelMetric, ModelMetricAdmin),
            (FeatureStore, FeatureStoreAdmin),
            (UserEmbedding, UserEmbeddingAdmin),
            (ItemEmbedding, ItemEmbeddingAdmin),
            (PredictionLog, PredictionLogAdmin),
            (AnomalyDetectionLog, AnomalyDetectionLogAdmin),
            (ChurnRiskProfile, ChurnRiskProfileAdmin),
            (RecommendationResult, RecommendationResultAdmin),
            (UserSegment, UserSegmentAdmin),
            (ABTestExperiment, ABTestExperimentAdmin),
            (TextAnalysisResult, TextAnalysisResultAdmin),
            (ImageAnalysisResult, ImageAnalysisResultAdmin),
            (ContentModerationLog, ContentModerationLogAdmin),
            (ExperimentTracking, ExperimentTrackingAdmin),
            (PersonalizationProfile, PersonalizationProfileAdmin),
            (SegmentationModel, SegmentationModelAdmin),
            (InsightModel, InsightModelAdmin),
            (DataDriftLog, DataDriftLogAdmin),
        ]
        registered = 0
        for model, model_admin in pairs:
            try:
                if model not in modern_site._registry:
                    modern_site.register(model, model_admin)
                    registered += 1
            except Exception as ex:
                print(f"[WARN] AI Engine — {model.__name__}: {ex}")
        print(f"[OK] AI Engine registered {registered} models")
    except Exception as e:
        print(f"[WARN] AI Engine force-register failed: {e}")