"""
api/ai_engine/models.py
=======================
AI Engine - সম্পূর্ণ Django Models
Earning Backend এর AI/ML সিস্টেমের সকল ডাটাবেজ মডেল

Author  : Amir (earning-backend-C)
Pattern : TimeStampedModel (core.models) + Multi-tenant (Tenant FK)
"""

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import TimeStampedModel
import uuid
import json


# ──────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────

def default_list():
    return []

def default_dict():
    return {}

def default_metrics():
    return {
        "accuracy": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "f1_score": 0.0,
    }


# ══════════════════════════════════════════════════════════════════════
# ১. MODEL MANAGEMENT  (মডেল ম্যানেজমেন্ট)
# ══════════════════════════════════════════════════════════════════════

class AIModel(TimeStampedModel):
    """
    মেইন AI মডেল রেজিস্ট্রি।
    প্রতিটি ট্রেইনড মডেলের মেটাডেটা এখানে সেভ হয়।
    """

    ALGORITHM_CHOICES = [
        # Classical ML
        ('xgboost',         'XGBoost'),
        ('lightgbm',        'LightGBM'),
        ('random_forest',   'Random Forest'),
        ('logistic_reg',    'Logistic Regression'),
        ('svm',             'Support Vector Machine'),
        ('knn',             'K-Nearest Neighbors'),
        ('naive_bayes',     'Naive Bayes'),
        # Deep Learning
        ('neural_network',  'Neural Network'),
        ('lstm',            'LSTM'),
        ('transformer',     'Transformer'),
        ('bert',            'BERT'),
        ('cnn',             'Convolutional Neural Network'),
        # Ensemble
        ('ensemble',        'Ensemble'),
        ('stacking',        'Stacking'),
        # NLP / LLM
        ('llm',             'Large Language Model'),
        ('gpt',             'GPT-based'),
        # Other
        ('custom',          'Custom'),
    ]

    TASK_CHOICES = [
        ('classification',  'Classification'),
        ('regression',      'Regression'),
        ('clustering',      'Clustering'),
        ('recommendation',  'Recommendation'),
        ('nlp',             'NLP / Text'),
        ('cv',              'Computer Vision'),
        ('anomaly',         'Anomaly Detection'),
        ('forecasting',     'Time-Series Forecasting'),
        ('rl',              'Reinforcement Learning'),
        ('optimization',    'Optimization'),
    ]

    STATUS_CHOICES = [
        ('draft',       'Draft'),
        ('training',    'Training'),
        ('trained',     'Trained'),
        ('evaluating',  'Evaluating'),
        ('deployed',    'Deployed'),
        ('deprecated',  'Deprecated'),
        ('failed',      'Failed'),
    ]

    # Multi-tenant
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ai_models',
        db_index=True,
        verbose_name=_("Tenant"),
    )

    name            = models.CharField(max_length=200, verbose_name=_("Model Name"))
    slug            = models.SlugField(max_length=220, unique=True, verbose_name=_("Slug"))
    description     = models.TextField(blank=True, verbose_name=_("Description"))
    algorithm       = models.CharField(max_length=30, choices=ALGORITHM_CHOICES, verbose_name=_("Algorithm"))
    task_type       = models.CharField(max_length=30, choices=TASK_CHOICES, verbose_name=_("Task Type"))
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name=_("Status"))
    active_version  = models.CharField(max_length=20, blank=True, verbose_name=_("Active Version"))

    # Config & Hyperparams
    hyperparameters = models.JSONField(default=default_dict, verbose_name=_("Hyperparameters"))
    feature_config  = models.JSONField(default=default_dict, verbose_name=_("Feature Config"))
    target_column   = models.CharField(max_length=100, blank=True, verbose_name=_("Target Column"))

    # Deployment
    is_active       = models.BooleanField(default=True, verbose_name=_("Is Active"))
    is_production   = models.BooleanField(default=False, verbose_name=_("Is Production"))
    endpoint_url    = models.URLField(blank=True, verbose_name=_("Endpoint URL"))

    # Ownership
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_ai_models',
        verbose_name=_("Created By"),
    )

    class Meta:
        db_table        = 'ai_engine_model'
        verbose_name    = _('AI Model')
        verbose_name_plural = _('AI Models')
        ordering        = ['-created_at']
        indexes         = [
            models.Index(fields=['tenant', 'status'], name='idx_tenant_status_601'),
            models.Index(fields=['task_type', 'is_active'], name='idx_task_type_is_active_602'),
        ]

    def __str__(self):
        return f"{self.name} ({self.algorithm}) v{self.active_version}"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.name)
            self.slug = f"{base}-{str(self.id)[:8]}"
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────

class ModelVersion(TimeStampedModel):
    """
    একটি AIModel-এর প্রতিটি ট্রেইন করা ভার্সন।
    মডেল ফাইল পাথ, মেট্রিক্স, আর্টিফ্যাক্ট লিংক এখানে থাকে।
    """

    STAGE_CHOICES = [
        ('development', 'Development'),
        ('staging',     'Staging'),
        ('production',  'Production'),
        ('archived',    'Archived'),
    ]

    ai_model    = models.ForeignKey(
        AIModel,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name=_("AI Model"),
    )
    version     = models.CharField(max_length=20, verbose_name=_("Version"))           # e.g. "1.0.3"
    stage       = models.CharField(max_length=20, choices=STAGE_CHOICES, default='development', null=True, blank=True)

    # Storage
    model_file_path     = models.CharField(max_length=500, blank=True, verbose_name=_("Model File Path"))
    artifact_uri        = models.URLField(blank=True, verbose_name=_("Artifact URI"))
    model_size_mb       = models.FloatField(default=0.0, verbose_name=_("Model Size (MB)"))

    # Performance snapshot
    accuracy    = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    precision   = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    recall      = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    f1_score    = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    auc_roc     = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    rmse        = models.FloatField(default=0.0, verbose_name=_("RMSE"))

    # Training info
    training_rows       = models.BigIntegerField(default=0, verbose_name=_("Training Rows"))
    feature_count       = models.IntegerField(default=0, verbose_name=_("Feature Count"))
    trained_at          = models.DateTimeField(null=True, blank=True)
    training_duration_s = models.FloatField(default=0.0, verbose_name=_("Training Duration (s)"))

    # Meta
    notes       = models.TextField(blank=True)
    is_active   = models.BooleanField(default=False)

    class Meta:
        db_table            = 'ai_engine_model_version'
        verbose_name        = _('Model Version')
        verbose_name_plural = _('Model Versions')
        unique_together     = [('ai_model', 'version')]
        ordering            = ['-trained_at']

    def __str__(self):
        return f"{self.ai_model.name} v{self.version} [{self.stage}]"


# ──────────────────────────────────────────────

class TrainingJob(TimeStampedModel):
    """
    মডেল ট্রেনিংয়ের সম্পূর্ণ হিস্ট্রি ও লগ।
    """

    STATUS_CHOICES = [
        ('queued',      'Queued'),
        ('running',     'Running'),
        ('completed',   'Completed'),
        ('failed',      'Failed'),
        ('cancelled',   'Cancelled'),
    ]

    tenant      = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='training_jobs',
    )
    ai_model    = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='training_jobs', null=True, blank=True)
    model_version = models.OneToOneField(
        ModelVersion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='training_job',
    )

    job_id      = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name=_("Job ID"))
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued', null=True, blank=True)

    # Timing
    started_at  = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(default=0.0)

    # Data
    dataset_path    = models.CharField(max_length=500, null=True, blank=True)
    train_rows      = models.BigIntegerField(default=0)
    val_rows        = models.BigIntegerField(default=0)

    # Logs & errors
    log_output      = models.TextField(blank=True, verbose_name=_("Log Output"))
    error_message   = models.TextField(blank=True, verbose_name=_("Error Message"))

    # Config used
    hyperparameters = models.JSONField(default=default_dict)
    worker_node     = models.CharField(max_length=100, blank=True, verbose_name=_("Worker Node"))

    triggered_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='triggered_training_jobs',
    )

    class Meta:
        db_table    = 'ai_engine_training_job'
        verbose_name = _('Training Job')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_603'),
        ]

    def __str__(self):
        return f"Job {self.job_id} — {self.ai_model.name} [{self.status}]"


# ──────────────────────────────────────────────

class ModelMetric(TimeStampedModel):
    """
    মডেলের বিস্তারিত পারফরম্যান্স মেট্রিক্স।
    প্রতিটি evaluation সেশনের জন্য আলাদা রেকর্ড।
    """

    METRIC_TYPE_CHOICES = [
        ('train',       'Train Set'),
        ('validation',  'Validation Set'),
        ('test',        'Test Set'),
        ('production',  'Production / Live'),
        ('ab_test',     'A/B Test'),
    ]

    ai_model        = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='metrics', null=True, blank=True)
    model_version   = models.ForeignKey(ModelVersion, on_delete=models.CASCADE, related_name='detailed_metrics', null=True, blank=True)
    metric_type     = models.CharField(max_length=20, choices=METRIC_TYPE_CHOICES, default='test', null=True, blank=True)

    # Classification Metrics
    accuracy        = models.FloatField(default=0.0)
    precision       = models.FloatField(default=0.0)
    recall          = models.FloatField(default=0.0)
    f1_score        = models.FloatField(default=0.0)
    auc_roc         = models.FloatField(default=0.0)
    log_loss        = models.FloatField(default=0.0)
    confusion_matrix = models.JSONField(default=default_dict, blank=True)

    # Regression Metrics
    mae             = models.FloatField(default=0.0, verbose_name=_("MAE"))
    mse             = models.FloatField(default=0.0, verbose_name=_("MSE"))
    rmse            = models.FloatField(default=0.0, verbose_name=_("RMSE"))
    r2_score        = models.FloatField(default=0.0, verbose_name=_("R² Score"))

    # Business Metrics
    lift_score      = models.FloatField(default=0.0)
    ks_statistic    = models.FloatField(default=0.0, verbose_name=_("KS Statistic"))

    # Latency
    avg_inference_ms = models.FloatField(default=0.0, verbose_name=_("Avg Inference (ms)"))
    p99_latency_ms   = models.FloatField(default=0.0, verbose_name=_("P99 Latency (ms)"))

    # Extra metrics as JSON
    extra_metrics   = models.JSONField(default=default_dict, blank=True)

    evaluated_at    = models.DateTimeField(auto_now_add=True)
    notes           = models.TextField(blank=True)

    class Meta:
        db_table    = 'ai_engine_model_metric'
        verbose_name = _('Model Metric')
        ordering    = ['-evaluated_at']

    def __str__(self):
        return f"{self.ai_model.name} | {self.metric_type} | F1={self.f1_score:.3f}"


# ══════════════════════════════════════════════════════════════════════
# ২. FEATURE STORE & EMBEDDINGS  (ফিচার স্টোর)
# ══════════════════════════════════════════════════════════════════════

class FeatureStore(TimeStampedModel):
    """
    প্রসেস করা ফিচার ডেটা — মডেল ট্রেনিংয়ের জন্য রেডি।
    """

    FEATURE_TYPE_CHOICES = [
        ('user',        'User Features'),
        ('item',        'Item / Offer Features'),
        ('session',     'Session Features'),
        ('contextual',  'Contextual Features'),
        ('behavioral',  'Behavioral Features'),
        ('demographic', 'Demographic Features'),
        ('temporal',    'Temporal Features'),
        ('interaction', 'Interaction Features'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feature_stores',
    )
    name            = models.CharField(max_length=200, verbose_name=_("Feature Set Name"))
    feature_type    = models.CharField(max_length=20, choices=FEATURE_TYPE_CHOICES, null=True, blank=True)
    entity_id       = models.CharField(max_length=100, db_index=True, verbose_name=_("Entity ID"))
    entity_type     = models.CharField(max_length=50, default='user', verbose_name=_("Entity Type"))

    # Feature data
    features        = models.JSONField(default=default_dict, verbose_name=_("Feature Values"))
    feature_names   = models.JSONField(default=default_list, verbose_name=_("Feature Names"))
    feature_count   = models.IntegerField(default=0)

    # Versioning
    version         = models.CharField(max_length=20, default='1.0', null=True, blank=True)
    pipeline_run_id = models.CharField(max_length=100, null=True, blank=True)

    is_active       = models.BooleanField(default=True)
    expires_at      = models.DateTimeField(null=True, blank=True, verbose_name=_("Expiry Time"))

    class Meta:
        db_table    = 'ai_engine_feature_store'
        verbose_name = _('Feature Store')
        indexes     = [
            models.Index(fields=['entity_id', 'feature_type'], name='idx_entity_id_feature_type_604'),
            models.Index(fields=['tenant', 'is_active'], name='idx_tenant_is_active_605'),
        ]
        ordering    = ['-created_at']

    def __str__(self):
        return f"[{self.feature_type}] {self.entity_id} — {self.feature_count} features"


# ──────────────────────────────────────────────

class UserEmbedding(TimeStampedModel):
    """
    ইউজারের বিহেভিয়ার থেকে তৈরি ভেক্টর এমবেডিং।
    পার্সোনালাইজেশন ও কোলাবোরেটিভ ফিল্টারিংয়ে ব্যবহার।
    """

    EMBEDDING_TYPE_CHOICES = [
        ('collaborative',   'Collaborative Filtering'),
        ('content_based',   'Content-Based'),
        ('hybrid',          'Hybrid'),
        ('behavioral',      'Behavioral'),
        ('deep_learning',   'Deep Learning'),
        ('graph',           'Graph Embedding'),
    ]

    tenant      = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='user_embeddings',
    )
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='ai_embeddings', verbose_name=_("User"),
    )
    ai_model    = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='user_embeddings',
    )
    embedding_type  = models.CharField(max_length=30, choices=EMBEDDING_TYPE_CHOICES, default='behavioral', null=True, blank=True)

    # Vector (stored as JSON list of floats)
    vector          = models.JSONField(default=default_list, verbose_name=_("Embedding Vector"))
    dimensions      = models.IntegerField(default=128, verbose_name=_("Vector Dimensions"))

    # Metadata
    interaction_count   = models.IntegerField(default=0, verbose_name=_("Interaction Count"))
    last_activity_at    = models.DateTimeField(null=True, blank=True)
    quality_score       = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Quality Score"),
    )

    model_version   = models.CharField(max_length=20, null=True, blank=True)
    is_stale        = models.BooleanField(default=False, verbose_name=_("Is Stale / Needs Refresh"))

    class Meta:
        db_table    = 'ai_engine_user_embedding'
        verbose_name = _('User Embedding')
        unique_together = [('user', 'embedding_type', 'ai_model')]
        ordering    = ['-created_at']

    def __str__(self):
        return f"Embedding({self.user_id}) [{self.embedding_type}] dim={self.dimensions}"


# ──────────────────────────────────────────────

class ItemEmbedding(TimeStampedModel):
    """
    অফার / প্রোডাক্ট / কন্টেন্টের ভেক্টর রিপ্রেজেন্টেশন।
    সিমিলারিটি সার্চ ও রিকমেন্ডেশনে ব্যবহার।
    """

    ITEM_TYPE_CHOICES = [
        ('offer',       'Offer'),
        ('product',     'Product'),
        ('content',     'Content'),
        ('ad',          'Advertisement'),
        ('task',        'Task'),
        ('reward',      'Reward'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='item_embeddings',
    )
    item_id         = models.CharField(max_length=100, db_index=True, verbose_name=_("Item ID"))
    item_type       = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='offer', null=True, blank=True)
    ai_model        = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='item_embeddings',
    )

    vector          = models.JSONField(default=default_list, verbose_name=_("Embedding Vector"))
    dimensions      = models.IntegerField(default=128)

    # Content metadata
    item_name       = models.CharField(max_length=300, null=True, blank=True)
    category        = models.CharField(max_length=100, null=True, blank=True)
    tags            = models.JSONField(default=default_list)

    popularity_score    = models.FloatField(default=0.0)
    model_version       = models.CharField(max_length=20, null=True, blank=True)
    is_active           = models.BooleanField(default=True)

    class Meta:
        db_table    = 'ai_engine_item_embedding'
        verbose_name = _('Item Embedding')
        unique_together = [('item_id', 'item_type', 'ai_model')]
        ordering    = ['-created_at']

    def __str__(self):
        return f"ItemEmb({self.item_id}) [{self.item_type}] dim={self.dimensions}"


# ══════════════════════════════════════════════════════════════════════
# ৩. PREDICTION LOGS  (প্রেডিকশন লগ)
# ══════════════════════════════════════════════════════════════════════

class PredictionLog(TimeStampedModel):
    """
    AI মডেলের প্রতিটি প্রেডিকশনের বিস্তারিত লগ।
    Input → Output → Ground Truth (পরে আপডেট হয়)।
    """

    PREDICTION_TYPE_CHOICES = [
        ('fraud',           'Fraud Detection'),
        ('churn',           'Churn Prediction'),
        ('ltv',             'Lifetime Value'),
        ('conversion',      'Conversion Probability'),
        ('recommendation',  'Recommendation'),
        ('click',           'Click Prediction'),
        ('revenue',         'Revenue Forecast'),
        ('anomaly',         'Anomaly Score'),
        ('sentiment',       'Sentiment'),
        ('custom',          'Custom'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prediction_logs',
    )
    ai_model        = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, related_name='prediction_logs')
    model_version   = models.CharField(max_length=20, null=True, blank=True)
    prediction_type = models.CharField(max_length=30, choices=PREDICTION_TYPE_CHOICES, null=True, blank=True)

    # Entity
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='prediction_logs',
    )
    entity_id       = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    entity_type     = models.CharField(max_length=50, null=True, blank=True)

    # Input / Output
    input_data      = models.JSONField(default=default_dict, verbose_name=_("Input Features"))
    prediction      = models.JSONField(default=default_dict, verbose_name=_("Prediction Output"))
    confidence      = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Confidence Score"),
    )
    predicted_class = models.CharField(max_length=100, blank=True, verbose_name=_("Predicted Class"))
    predicted_value = models.FloatField(null=True, blank=True, verbose_name=_("Predicted Value"))

    # Ground truth (feedback loop)
    actual_outcome  = models.CharField(max_length=100, blank=True, verbose_name=_("Actual Outcome"))
    is_correct      = models.BooleanField(null=True, blank=True, verbose_name=_("Was Prediction Correct"))
    feedback_at     = models.DateTimeField(null=True, blank=True)

    # Performance
    inference_ms    = models.FloatField(default=0.0, verbose_name=_("Inference Time (ms)"))
    request_id      = models.UUIDField(default=uuid.uuid4, db_index=True, verbose_name=_("Request ID"))

    class Meta:
        db_table    = 'ai_engine_prediction_log'
        verbose_name = _('Prediction Log')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['tenant', 'prediction_type', 'created_at'], name='idx_tenant_prediction_type_032'),
            models.Index(fields=['user', 'prediction_type'], name='idx_user_prediction_type_607'),
        ]

    def __str__(self):
        return f"[{self.prediction_type}] user={self.user_id} conf={self.confidence:.2f}"


# ──────────────────────────────────────────────

class AnomalyDetectionLog(TimeStampedModel):
    """
    AI দ্বারা সনাক্ত করা অ্যানোমালি / সন্দেহজনক কার্যকলাপ।
    ফ্রড ক্লিক, অস্বাভাবিক ট্রানজেকশন, সিস্টেম অ্যানোমালি ইত্যাদি।
    """

    ANOMALY_TYPE_CHOICES = [
        ('fraud_click',     'Fraud Click'),
        ('fraud_conversion','Fraud Conversion'),
        ('unusual_login',   'Unusual Login'),
        ('bulk_request',    'Bulk/Bot Request'),
        ('transaction',     'Transaction Anomaly'),
        ('spending',        'Spending Pattern'),
        ('system',          'System Anomaly'),
        ('network',         'Network Anomaly'),
        ('user_behavior',   'User Behavior'),
        ('data_drift',      'Data Drift'),
    ]

    SEVERITY_CHOICES = [
        ('low',      'Low'),
        ('medium',   'Medium'),
        ('high',     'High'),
        ('critical', 'Critical'),
    ]

    STATUS_CHOICES = [
        ('open',        'Open'),
        ('investigating', 'Investigating'),
        ('resolved',    'Resolved'),
        ('false_positive', 'False Positive'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_anomaly_logs',
    )
    ai_model        = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True, related_name='anomalies')
    anomaly_type    = models.CharField(max_length=30, choices=ANOMALY_TYPE_CHOICES, db_index=True, null=True, blank=True)
    severity        = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='medium', null=True, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open', null=True, blank=True)

    # Entity
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_anomaly_logs',
    )
    entity_id       = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    entity_type     = models.CharField(max_length=50, null=True, blank=True)

    # Detection details
    anomaly_score   = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Anomaly Score"),
    )
    threshold       = models.FloatField(default=0.8, verbose_name=_("Detection Threshold"))
    evidence_data   = models.JSONField(default=default_dict, verbose_name=_("Evidence Data"))
    description     = models.TextField(blank=True)

    # Action taken
    auto_action_taken   = models.CharField(max_length=100, blank=True, verbose_name=_("Auto Action"))
    resolved_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='resolved_anomalies',
    )
    resolved_at         = models.DateTimeField(null=True, blank=True)
    resolution_notes    = models.TextField(blank=True)

    # IP & context
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.TextField(blank=True)
    metadata    = models.JSONField(default=default_dict, blank=True)

    class Meta:
        db_table    = 'ai_engine_anomaly_log'
        verbose_name = _('Anomaly Detection Log')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['tenant', 'anomaly_type', 'severity'], name='idx_tenant_anomaly_type_se_f5b'),
            models.Index(fields=['status', 'created_at'], name='idx_status_created_at_609'),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.anomaly_type} — score={self.anomaly_score:.2f}"


# ──────────────────────────────────────────────

class ChurnRiskProfile(TimeStampedModel):
    """
    ইউজার চলে যাওয়ার (Churn) রিস্ক প্রোফাইল।
    প্রতিদিন রিফ্রেশ হয়।
    """

    RISK_LEVEL_CHOICES = [
        ('very_low',    'Very Low (0-20%)'),
        ('low',         'Low (20-40%)'),
        ('medium',      'Medium (40-60%)'),
        ('high',        'High (60-80%)'),
        ('very_high',   'Very High (80-100%)'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='churn_profiles',
    )
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='churn_profile',)
    ai_model        = models.ForeignKey(AIModel, on_delete=models.SET_NULL, null=True, blank=True, related_name='churn_profiles')

    churn_probability   = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Churn Probability"),
    )
    risk_level          = models.CharField(max_length=15, choices=RISK_LEVEL_CHOICES, default='low', null=True, blank=True)

    # Contributing factors
    days_since_login        = models.IntegerField(default=0)
    days_since_last_earn    = models.IntegerField(default=0)
    recent_activity_score   = models.FloatField(default=0.0)
    engagement_trend        = models.CharField(
        max_length=15,
        choices=[('increasing','Increasing'), ('stable','Stable'), ('decreasing','Decreasing')],
        default='stable',
    )

    top_risk_factors    = models.JSONField(default=default_list, verbose_name=_("Top Risk Factors"))
    retention_actions   = models.JSONField(default=default_list, verbose_name=_("Suggested Retention Actions"))

    predicted_at        = models.DateTimeField(auto_now=True)
    model_version       = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_churn_risk'
        verbose_name = _('Churn Risk Profile')
        unique_together = [('user', 'tenant')]
        ordering    = ['-churn_probability']
        indexes     = [
            models.Index(fields=['tenant', 'risk_level'], name='idx_tenant_risk_level_610'),
        ]

    def __str__(self):
        return f"ChurnRisk({self.user_id}) — {self.churn_probability:.1%} [{self.risk_level}]"


# ══════════════════════════════════════════════════════════════════════
# ৪. PERSONALIZATION & RECOMMENDATION  (পার্সোনালাইজেশন)
# ══════════════════════════════════════════════════════════════════════

class RecommendationResult(TimeStampedModel):
    """
    ইউজারকে কোন অফার / প্রোডাক্ট রিকমেন্ড করা হয়েছে তার রেকর্ড।
    """

    ENGINE_CHOICES = [
        ('collaborative',   'Collaborative Filtering'),
        ('content_based',   'Content-Based Filtering'),
        ('hybrid',          'Hybrid'),
        ('popularity',      'Popularity-Based'),
        ('contextual',      'Contextual'),
        ('session',         'Session-Based'),
        ('trending',        'Trending'),
        ('personalized',    'Deep Personalization'),
    ]

    ITEM_TYPE_CHOICES = [
        ('offer',   'Offer'),
        ('product', 'Product'),
        ('content', 'Content'),
        ('ad',      'Ad'),
        ('task',    'Task'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recommendation_results',
    )
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='recommendations',)
    ai_model        = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='recommendation_results',
    )

    engine          = models.CharField(max_length=20, choices=ENGINE_CHOICES, default='hybrid', null=True, blank=True)
    item_type       = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES, default='offer', null=True, blank=True)

    # Recommended items (ordered list of {item_id, score, reason})
    recommended_items   = models.JSONField(default=default_list, verbose_name=_("Recommended Items"))
    item_count          = models.IntegerField(default=0)

    # Context
    context_data        = models.JSONField(default=default_dict, verbose_name=_("Context Data"))
    session_id          = models.CharField(max_length=100, null=True, blank=True)

    # Interaction tracking
    shown_at            = models.DateTimeField(null=True, blank=True)
    clicked_item_id     = models.CharField(max_length=100, null=True, blank=True)
    converted_item_id   = models.CharField(max_length=100, null=True, blank=True)
    ctr                 = models.FloatField(default=0.0, verbose_name=_("Click-Through Rate"))

    model_version       = models.CharField(max_length=20, null=True, blank=True)
    request_id          = models.UUIDField(default=uuid.uuid4, db_index=True)

    class Meta:
        db_table    = 'ai_engine_recommendation_result'
        verbose_name = _('Recommendation Result')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['user', 'item_type', 'created_at'], name='idx_user_item_type_created_764'),
            models.Index(fields=['tenant', 'engine'], name='idx_tenant_engine_612'),
        ]

    def __str__(self):
        return f"Rec({self.user_id}) via {self.engine} — {self.item_count} items"


# ──────────────────────────────────────────────

class UserSegment(TimeStampedModel):
    """
    AI দ্বারা তৈরি অটোমেটিক ইউজার সেগমেন্ট / গ্রুপ।
    e.g.: High Spenders, Dormant Users, VIP Potential
    """

    SEGMENTATION_METHOD_CHOICES = [
        ('kmeans',          'K-Means Clustering'),
        ('dbscan',          'DBSCAN'),
        ('hierarchical',    'Hierarchical Clustering'),
        ('rule_based',      'Rule-Based'),
        ('ml_classifier',   'ML Classifier'),
        ('rfm',             'RFM Analysis'),
        ('manual',          'Manual'),
    ]

    tenant      = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='user_segments',
    )
    ai_model    = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='user_segments',
    )

    name            = models.CharField(max_length=200, verbose_name=_("Segment Name"))
    description     = models.TextField(blank=True)
    method          = models.CharField(max_length=20, choices=SEGMENTATION_METHOD_CHOICES, default='kmeans', null=True, blank=True)

    # Criteria
    criteria        = models.JSONField(default=default_dict, verbose_name=_("Segment Criteria"))
    features_used   = models.JSONField(default=default_list, verbose_name=_("Features Used"))

    # Members
    user_count      = models.IntegerField(default=0, verbose_name=_("User Count"))
    user_ids        = models.JSONField(default=default_list, verbose_name=_("User IDs (sampled)"))

    # Business value
    avg_revenue     = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    avg_ltv         = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    churn_rate      = models.FloatField(default=0.0)

    is_active       = models.BooleanField(default=True)
    auto_refresh    = models.BooleanField(default=True, verbose_name=_("Auto Refresh Daily"))
    last_refreshed  = models.DateTimeField(null=True, blank=True)
    model_version   = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_user_segment'
        verbose_name = _('User Segment')
        ordering    = ['-user_count']

    def __str__(self):
        return f"Segment: {self.name} ({self.user_count} users)"


# ──────────────────────────────────────────────

class ABTestExperiment(TimeStampedModel):
    """
    AI মডেলের A/B Test / মাল্টিভেরিয়েট টেস্টিং ডেটা।
    কোন ভার্সন ভালো পারফর্ম করছে তা ট্র্যাক করে।
    """

    STATUS_CHOICES = [
        ('draft',       'Draft'),
        ('running',     'Running'),
        ('paused',      'Paused'),
        ('completed',   'Completed'),
        ('cancelled',   'Cancelled'),
    ]

    WINNER_CHOICES = [
        ('control',     'Control'),
        ('treatment_a', 'Treatment A'),
        ('treatment_b', 'Treatment B'),
        ('treatment_c', 'Treatment C'),
        ('no_winner',   'No Significant Winner'),
        ('pending',     'Pending'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ab_experiments',
    )
    name            = models.CharField(max_length=200, verbose_name=_("Experiment Name"))
    description     = models.TextField(blank=True)
    hypothesis      = models.TextField(blank=True, verbose_name=_("Hypothesis"))
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='draft', null=True, blank=True)

    # Models being compared
    control_model   = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ab_control_experiments',
    )
    treatment_models = models.JSONField(default=default_list, verbose_name=_("Treatment Model IDs"))

    # Traffic split (%)
    control_traffic     = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])
    treatment_traffic   = models.IntegerField(default=50, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Timing
    started_at      = models.DateTimeField(null=True, blank=True)
    ended_at        = models.DateTimeField(null=True, blank=True)
    planned_days    = models.IntegerField(default=14)

    # Results
    control_metrics     = models.JSONField(default=default_dict, verbose_name=_("Control Metrics"))
    treatment_metrics   = models.JSONField(default=default_dict, verbose_name=_("Treatment Metrics"))
    winner              = models.CharField(max_length=15, choices=WINNER_CHOICES, default='pending', null=True, blank=True)
    confidence_level    = models.FloatField(default=0.0, verbose_name=_("Statistical Confidence"))
    lift_percentage     = models.FloatField(default=0.0, verbose_name=_("Lift (%)"))

    # Participants
    total_participants  = models.IntegerField(default=0)
    target_metric       = models.CharField(max_length=100, default='conversion_rate', null=True, blank=True)

    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ab_experiments',
    )

    class Meta:
        db_table    = 'ai_engine_ab_experiment'
        verbose_name = _('A/B Test Experiment')
        ordering    = ['-created_at']

    def __str__(self):
        return f"A/B: {self.name} [{self.status}] winner={self.winner}"


# ══════════════════════════════════════════════════════════════════════
# ৫. NLP & COMPUTER VISION  (এনএলপি ও ইমেজ)
# ══════════════════════════════════════════════════════════════════════

class TextAnalysisResult(TimeStampedModel):
    """
    টেক্সটের সেন্টিমেন্ট, ইনটেন্ট, এনটিটি বিশ্লেষণের ফলাফল।
    রিভিউ, ফিডব্যাক, সাপোর্ট মেসেজ ইত্যাদি প্রসেসিং।
    """

    ANALYSIS_TYPE_CHOICES = [
        ('sentiment',   'Sentiment Analysis'),
        ('intent',      'Intent Classification'),
        ('entity',      'Entity Extraction'),
        ('spam',        'Spam Detection'),
        ('topic',       'Topic Modeling'),
        ('summary',     'Summarization'),
        ('keyword',     'Keyword Extraction'),
        ('profanity',   'Profanity Detection'),
        ('language',    'Language Detection'),
        ('general',     'General NLP'),
    ]

    SENTIMENT_CHOICES = [
        ('positive',    'Positive'),
        ('negative',    'Negative'),
        ('neutral',     'Neutral'),
        ('mixed',       'Mixed'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='text_analysis_results',
    )
    ai_model        = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='text_results',
    )
    analysis_type   = models.CharField(max_length=20, choices=ANALYSIS_TYPE_CHOICES, null=True, blank=True)

    # Source
    source_type     = models.CharField(max_length=50, blank=True, verbose_name=_("Source Type"))  # review, feedback, support
    source_id       = models.CharField(max_length=100, blank=True, verbose_name=_("Source ID"), db_index=True)
    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='text_analyses',
    )

    # Input
    input_text      = models.TextField(verbose_name=_("Input Text"))
    detected_language = models.CharField(max_length=10, blank=True, default='en', null=True)

    # Results
    sentiment           = models.CharField(max_length=10, choices=SENTIMENT_CHOICES, null=True, blank=True)
    sentiment_score     = models.FloatField(default=0.0, validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)])
    intent              = models.CharField(max_length=100, null=True, blank=True)
    intent_confidence   = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    entities            = models.JSONField(default=default_list, verbose_name=_("Extracted Entities"))
    keywords            = models.JSONField(default=default_list, verbose_name=_("Keywords"))
    topics              = models.JSONField(default=default_list, verbose_name=_("Topics"))
    summary             = models.TextField(blank=True, verbose_name=_("Auto Summary"))

    # Classification
    is_spam             = models.BooleanField(default=False)
    has_profanity       = models.BooleanField(default=False)
    is_flagged          = models.BooleanField(default=False)
    spam_confidence     = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])

    # Raw output
    raw_output          = models.JSONField(default=default_dict, blank=True)
    inference_ms        = models.FloatField(default=0.0)
    model_version       = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_text_analysis'
        verbose_name = _('Text Analysis Result')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['tenant', 'analysis_type', 'created_at'], name='idx_tenant_analysis_type_c_9ff'),
            models.Index(fields=['source_type', 'source_id'], name='idx_source_type_source_id_614'),
        ]

    def __str__(self):
        return f"[{self.analysis_type}] {self.detected_language} — sentiment={self.sentiment}"


# ──────────────────────────────────────────────

class ImageAnalysisResult(TimeStampedModel):
    """
    ইমেজ থেকে ডিটেক্ট করা অবজেক্ট, OCR ডেটা, ফেস ডিটেকশন ইত্যাদি।
    KYC ডকুমেন্ট যাচাই, প্রোফাইল পিকচার মডারেশন ইত্যাদিতে ব্যবহার।
    """

    ANALYSIS_TYPE_CHOICES = [
        ('ocr',             'OCR / Text Extraction'),
        ('object_detect',   'Object Detection'),
        ('face_detect',     'Face Detection'),
        ('id_card',         'ID Card Verification'),
        ('document',        'Document Validation'),
        ('nsfw',            'NSFW / Adult Content'),
        ('logo',            'Logo Detection'),
        ('quality',         'Image Quality Check'),
        ('similarity',      'Image Similarity'),
        ('classification',  'Image Classification'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='image_analysis_results',
    )
    ai_model        = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='image_results',
    )
    analysis_type   = models.CharField(max_length=20, choices=ANALYSIS_TYPE_CHOICES, null=True, blank=True)

    # Source
    source_type     = models.CharField(max_length=50, null=True, blank=True)
    source_id       = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    image_url       = models.URLField(blank=True, verbose_name=_("Image URL"))
    image_path      = models.CharField(max_length=500, blank=True, verbose_name=_("Image Path"))

    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='image_analyses',
    )

    # OCR
    extracted_text  = models.TextField(blank=True, verbose_name=_("Extracted Text"))
    ocr_confidence  = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])

    # Detection results
    detected_objects    = models.JSONField(default=default_list, verbose_name=_("Detected Objects"))
    detected_faces      = models.IntegerField(default=0, verbose_name=_("Face Count"))
    bounding_boxes      = models.JSONField(default=default_list, verbose_name=_("Bounding Boxes"))
    labels              = models.JSONField(default=default_list, verbose_name=_("Labels"))

    # Safety
    is_nsfw             = models.BooleanField(default=False, verbose_name=_("Is NSFW"))
    nsfw_confidence     = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    is_flagged          = models.BooleanField(default=False)

    # Quality
    quality_score       = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    is_blurry           = models.BooleanField(default=False)
    resolution          = models.CharField(max_length=20, null=True, blank=True)

    # Raw
    raw_output          = models.JSONField(default=default_dict, blank=True)
    inference_ms        = models.FloatField(default=0.0)
    model_version       = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_image_analysis'
        verbose_name = _('Image Analysis Result')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['tenant', 'analysis_type', 'created_at'], name='idx_tenant_analysis_type_c_4e7'),
        ]

    def __str__(self):
        return f"[{self.analysis_type}] source={self.source_id} flagged={self.is_flagged}"


# ──────────────────────────────────────────────

class ContentModerationLog(TimeStampedModel):
    """
    AI দ্বারা ফ্ল্যাগ করা আপত্তিকর কন্টেন্টের বিস্তারিত লগ।
    Text + Image উভয় মডারেশন কভার করে।
    """

    CONTENT_TYPE_CHOICES = [
        ('text',    'Text'),
        ('image',   'Image'),
        ('video',   'Video'),
        ('url',     'URL'),
        ('username','Username'),
        ('profile', 'Profile'),
    ]

    VIOLATION_CHOICES = [
        ('spam',        'Spam'),
        ('hate_speech', 'Hate Speech'),
        ('harassment',  'Harassment'),
        ('nsfw',        'NSFW / Adult'),
        ('violence',    'Violence'),
        ('fraud',       'Fraudulent Content'),
        ('misinformation', 'Misinformation'),
        ('illegal',     'Illegal Content'),
        ('profanity',   'Profanity'),
        ('other',       'Other'),
    ]

    ACTION_CHOICES = [
        ('allow',           'Allowed'),
        ('warn',            'Warning Issued'),
        ('remove',          'Content Removed'),
        ('shadow_ban',      'Shadow Banned'),
        ('block_user',      'User Blocked'),
        ('review_needed',   'Manual Review Needed'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moderation_logs',
    )
    ai_model        = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moderation_logs',
    )

    user            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='moderation_logs',
    )
    content_type    = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES, null=True, blank=True)
    content_id      = models.CharField(max_length=100, blank=True, db_index=True, null=True)
    content_preview = models.TextField(blank=True, verbose_name=_("Content Preview (truncated)"))

    # Detection
    violation_type      = models.CharField(max_length=20, choices=VIOLATION_CHOICES, null=True, blank=True)
    violation_score     = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        verbose_name=_("Violation Score"),
    )
    detection_reasons   = models.JSONField(default=default_list, verbose_name=_("Detection Reasons"))

    # Action
    action_taken        = models.CharField(max_length=20, choices=ACTION_CHOICES, default='review_needed', null=True, blank=True)
    is_auto_action      = models.BooleanField(default=True, verbose_name=_("Was Auto Action"))
    reviewed_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_moderation_logs',
    )
    reviewed_at         = models.DateTimeField(null=True, blank=True)
    is_false_positive   = models.BooleanField(default=False)
    review_notes        = models.TextField(blank=True)

    model_version       = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_content_moderation'
        verbose_name = _('Content Moderation Log')
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['tenant', 'violation_type', 'action_taken'], name='idx_tenant_violation_type__c4a'),
            models.Index(fields=['user', 'created_at'], name='idx_user_created_at_617'),
        ]

    def __str__(self):
        return f"[{self.violation_type}] {self.content_type} — action={self.action_taken} score={self.violation_score:.2f}"


# ══════════════════════════════════════════════════════════════════════
# ৬. EXPERIMENT TRACKING  (এক্সপেরিমেন্ট ট্র্যাকিং)
# ══════════════════════════════════════════════════════════════════════

class ExperimentTracking(TimeStampedModel):
    """
    MLflow-style এক্সপেরিমেন্ট ট্র্যাকিং।
    প্রতিটি ট্রেনিং রান এর প্যারামিটার, মেট্রিক্স, আর্টিফ্যাক্ট।
    """

    STATUS_CHOICES = [
        ('running',     'Running'),
        ('finished',    'Finished'),
        ('failed',      'Failed'),
        ('killed',      'Killed'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='experiments',
    )
    ai_model        = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='experiments', null=True, blank=True)
    experiment_name = models.CharField(max_length=200, null=True, blank=True)
    run_id          = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name=_("Run ID"))
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default='running', null=True, blank=True)

    # Params, metrics, tags
    params          = models.JSONField(default=default_dict, verbose_name=_("Parameters"))
    metrics         = models.JSONField(default=default_dict, verbose_name=_("Metrics"))
    tags            = models.JSONField(default=default_dict, verbose_name=_("Tags"))
    artifacts       = models.JSONField(default=default_list, verbose_name=_("Artifacts"))

    # Timing
    started_at      = models.DateTimeField(null=True, blank=True)
    ended_at        = models.DateTimeField(null=True, blank=True)

    # Notes
    notes           = models.TextField(blank=True)
    source_commit   = models.CharField(max_length=50, blank=True, verbose_name=_("Git Commit"))
    environment     = models.JSONField(default=default_dict, verbose_name=_("Environment Info"))

    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='experiments',
    )

    class Meta:
        db_table    = 'ai_engine_experiment'
        verbose_name = _('Experiment Tracking')
        ordering    = ['-created_at']

    def __str__(self):
        return f"Exp: {self.experiment_name} | run={self.run_id} [{self.status}]"


# ══════════════════════════════════════════════════════════════════════
# ৭. PERSONALIZATION PROFILE  (ব্যক্তিগতকরণ প্রোফাইল)
# ══════════════════════════════════════════════════════════════════════

class PersonalizationProfile(TimeStampedModel):
    """
    ইউজারের সম্পূর্ণ AI-ভিত্তিক পার্সোনালাইজেশন প্রোফাইল।
    রিয়েল-টাইম আপডেট হয়।
    """

    tenant      = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='personalization_profiles',
    )
    user        = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='personalization_profile',)

    # Inferred preferences
    preferred_categories    = models.JSONField(default=default_list, verbose_name=_("Preferred Categories"))
    preferred_offer_types   = models.JSONField(default=default_list, verbose_name=_("Preferred Offer Types"))
    preferred_time_slots    = models.JSONField(default=default_list, verbose_name=_("Preferred Time Slots"))
    preferred_devices       = models.JSONField(default=default_list, verbose_name=_("Preferred Devices"))
    preferred_reward_types  = models.JSONField(default=default_list, verbose_name=_("Preferred Reward Types"))

    # Behavioral traits
    is_deal_seeker          = models.BooleanField(default=False)
    is_high_engagement      = models.BooleanField(default=False)
    is_mobile_first         = models.BooleanField(default=True)
    price_sensitivity       = models.FloatField(default=0.5, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    activity_score          = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])

    # LTV & Value
    estimated_ltv           = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    ltv_segment             = models.CharField(
        max_length=20,
        choices=[('low','Low'), ('medium','Medium'), ('high','High'), ('premium','Premium')],
        default='medium',
    )

    # Scoring
    engagement_score        = models.FloatField(default=0.0)
    loyalty_score           = models.FloatField(default=0.0)
    risk_score              = models.FloatField(default=0.0)

    # AI-generated insights
    ai_insights             = models.JSONField(default=default_dict, verbose_name=_("AI Insights"))
    recommended_actions     = models.JSONField(default=default_list, verbose_name=_("Recommended Actions"))

    model_version           = models.CharField(max_length=20, null=True, blank=True)
    last_refreshed          = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Refreshed"))

    class Meta:
        db_table    = 'ai_engine_personalization_profile'
        verbose_name = _('Personalization Profile')
        ordering    = ['-activity_score']

    def __str__(self):
        return f"Profile({self.user_id}) LTV={self.estimated_ltv} engagement={self.engagement_score:.2f}"


# ══════════════════════════════════════════════════════════════════════
# ৮. SEGMENTATION MODEL  (সেগমেন্টেশন)
# ══════════════════════════════════════════════════════════════════════

class SegmentationModel(TimeStampedModel):
    """
    AI সেগমেন্টেশন রানের মেটাডেটা।
    কখন রান হয়েছে, কত ক্লাস্টার, কোন অ্যালগরিদম।
    """

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='segmentation_models',
    )
    ai_model        = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='segmentation_runs', null=True, blank=True)
    run_name        = models.CharField(max_length=200, null=True, blank=True)
    algorithm       = models.CharField(max_length=50, default='kmeans', null=True, blank=True)

    # Clustering params
    n_clusters      = models.IntegerField(default=5, verbose_name=_("Number of Clusters"))
    features_used   = models.JSONField(default=default_list)
    params          = models.JSONField(default=default_dict)

    # Results
    silhouette_score    = models.FloatField(default=0.0, verbose_name=_("Silhouette Score"))
    inertia             = models.FloatField(default=0.0, verbose_name=_("Inertia"))
    total_users         = models.IntegerField(default=0)
    cluster_summary     = models.JSONField(default=default_list, verbose_name=_("Cluster Summary"))

    # Status
    is_active       = models.BooleanField(default=False)
    ran_at          = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_segmentation_model'
        verbose_name = _('Segmentation Model')
        ordering    = ['-ran_at']

    def __str__(self):
        return f"Segmentation: {self.run_name} | k={self.n_clusters} | users={self.total_users}"


# ══════════════════════════════════════════════════════════════════════
# ৯. INSIGHT MODEL  (ইনসাইট)
# ══════════════════════════════════════════════════════════════════════

class InsightModel(TimeStampedModel):
    """
    AI দ্বারা স্বয়ংক্রিয়ভাবে জেনারেট করা বিজনেস ইনসাইট।
    ড্যাশবোর্ডে দেখানো হয়।
    """

    INSIGHT_TYPE_CHOICES = [
        ('trend',           'Trend'),
        ('anomaly',         'Anomaly Alert'),
        ('opportunity',     'Opportunity'),
        ('risk',            'Risk Warning'),
        ('prediction',      'Prediction'),
        ('recommendation',  'Recommendation'),
        ('performance',     'Performance Summary'),
        ('cohort',          'Cohort Analysis'),
        ('attribution',     'Attribution'),
    ]

    PRIORITY_CHOICES = [
        ('low',     'Low'),
        ('medium',  'Medium'),
        ('high',    'High'),
        ('urgent',  'Urgent'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ai_insights',
    )
    ai_model        = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='insights',
    )

    title           = models.CharField(max_length=300, verbose_name=_("Insight Title"))
    description     = models.TextField(verbose_name=_("Insight Description"))
    insight_type    = models.CharField(max_length=20, choices=INSIGHT_TYPE_CHOICES, null=True, blank=True)
    priority        = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium', null=True, blank=True)

    # Supporting data
    supporting_data     = models.JSONField(default=default_dict, verbose_name=_("Supporting Data"))
    chart_data          = models.JSONField(default=default_dict, verbose_name=_("Chart Data"))
    affected_metrics    = models.JSONField(default=default_list, verbose_name=_("Affected Metrics"))
    recommended_actions = models.JSONField(default=default_list, verbose_name=_("Recommended Actions"))

    # Impact
    estimated_impact    = models.CharField(max_length=200, blank=True, verbose_name=_("Estimated Impact"))
    confidence_score    = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])

    # Lifecycle
    is_active           = models.BooleanField(default=True)
    is_dismissed        = models.BooleanField(default=False)
    dismissed_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='dismissed_insights',
    )
    dismissed_at        = models.DateTimeField(null=True, blank=True)
    expires_at          = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table    = 'ai_engine_insight'
        verbose_name = _('AI Insight')
        ordering    = ['-priority', '-created_at']
        indexes     = [
            models.Index(fields=['tenant', 'insight_type', 'is_active'], name='idx_tenant_insight_type_is_12e'),
        ]

    def __str__(self):
        return f"[{self.priority.upper()}] {self.insight_type}: {self.title}"


# ══════════════════════════════════════════════════════════════════════
# ১০. DATA DRIFT MONITORING  (ড্রিফট মনিটরিং)
# ══════════════════════════════════════════════════════════════════════

class DataDriftLog(TimeStampedModel):
    """
    প্রোডাকশনে ডেটার পরিবর্তন ট্র্যাকিং।
    মডেল retraining কখন দরকার তা নির্ধারণে ব্যবহার।
    """

    DRIFT_TYPE_CHOICES = [
        ('feature',     'Feature Drift'),
        ('label',       'Label / Target Drift'),
        ('concept',     'Concept Drift'),
        ('covariate',   'Covariate Shift'),
        ('prior',       'Prior Probability Shift'),
    ]

    STATUS_CHOICES = [
        ('normal',      'Normal — No Drift'),
        ('warning',     'Warning — Mild Drift'),
        ('critical',    'Critical — Significant Drift'),
    ]

    tenant          = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='drift_logs',
    )
    ai_model        = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='drift_logs', null=True, blank=True)
    model_version   = models.ForeignKey(ModelVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name='drift_logs')

    drift_type      = models.CharField(max_length=15, choices=DRIFT_TYPE_CHOICES, null=True, blank=True)
    status          = models.CharField(max_length=10, choices=STATUS_CHOICES, default='normal', null=True, blank=True)

    # Metrics
    drift_score     = models.FloatField(default=0.0, verbose_name=_("Drift Score"))
    psi_score       = models.FloatField(default=0.0, verbose_name=_("PSI Score"))
    ks_statistic    = models.FloatField(default=0.0, verbose_name=_("KS Statistic"))
    threshold       = models.FloatField(default=0.2, verbose_name=_("Alert Threshold"))

    # Drifted features
    drifted_features    = models.JSONField(default=default_list, verbose_name=_("Drifted Features"))
    feature_drift_scores = models.JSONField(default=default_dict, verbose_name=_("Per-Feature Drift Scores"))

    # Recommendation
    retrain_recommended = models.BooleanField(default=False)
    notes               = models.TextField(blank=True)

    detected_at         = models.DateTimeField(auto_now_add=True)
    window_start        = models.DateTimeField(null=True, blank=True, verbose_name=_("Data Window Start"))
    window_end          = models.DateTimeField(null=True, blank=True, verbose_name=_("Data Window End"))

    class Meta:
        db_table    = 'ai_engine_data_drift'
        verbose_name = _('Data Drift Log')
        ordering    = ['-detected_at']
        indexes     = [
            models.Index(fields=['ai_model', 'status', 'detected_at'], name='idx_ai_model_status_detect_d11'),
        ]

    def __str__(self):
        return f"Drift [{self.status}] {self.ai_model.name} — score={self.drift_score:.3f}"
