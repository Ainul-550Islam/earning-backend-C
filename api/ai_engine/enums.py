"""
api/ai_engine/enums.py
======================
AI Engine — সকল Enum এবং Choice constants।
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class ModelStatus(models.TextChoices):
    DRAFT       = 'draft',      _('Draft')
    TRAINING    = 'training',   _('Training')
    TRAINED     = 'trained',    _('Trained')
    EVALUATING  = 'evaluating', _('Evaluating')
    DEPLOYED    = 'deployed',   _('Deployed')
    DEPRECATED  = 'deprecated', _('Deprecated')
    FAILED      = 'failed',     _('Failed')


class AlgorithmType(models.TextChoices):
    XGBOOST         = 'xgboost',        _('XGBoost')
    LIGHTGBM        = 'lightgbm',       _('LightGBM')
    RANDOM_FOREST   = 'random_forest',  _('Random Forest')
    LOGISTIC_REG    = 'logistic_reg',   _('Logistic Regression')
    SVM             = 'svm',            _('Support Vector Machine')
    NEURAL_NETWORK  = 'neural_network', _('Neural Network')
    LSTM            = 'lstm',           _('LSTM')
    TRANSFORMER     = 'transformer',    _('Transformer')
    BERT            = 'bert',           _('BERT')
    CNN             = 'cnn',            _('CNN')
    ENSEMBLE        = 'ensemble',       _('Ensemble')
    LLM             = 'llm',            _('LLM')
    CUSTOM          = 'custom',         _('Custom')


class TaskType(models.TextChoices):
    CLASSIFICATION  = 'classification',  _('Classification')
    REGRESSION      = 'regression',      _('Regression')
    CLUSTERING      = 'clustering',      _('Clustering')
    RECOMMENDATION  = 'recommendation',  _('Recommendation')
    NLP             = 'nlp',             _('NLP / Text')
    CV              = 'cv',              _('Computer Vision')
    ANOMALY         = 'anomaly',         _('Anomaly Detection')
    FORECASTING     = 'forecasting',     _('Forecasting')
    RL              = 'rl',              _('Reinforcement Learning')
    OPTIMIZATION    = 'optimization',    _('Optimization')


class SeverityLevel(models.TextChoices):
    LOW      = 'low',      _('Low')
    MEDIUM   = 'medium',   _('Medium')
    HIGH     = 'high',     _('High')
    CRITICAL = 'critical', _('Critical')


class AnomalyStatus(models.TextChoices):
    OPEN            = 'open',           _('Open')
    INVESTIGATING   = 'investigating',  _('Investigating')
    RESOLVED        = 'resolved',       _('Resolved')
    FALSE_POSITIVE  = 'false_positive', _('False Positive')


class PredictionType(models.TextChoices):
    FRAUD           = 'fraud',          _('Fraud Detection')
    CHURN           = 'churn',          _('Churn Prediction')
    LTV             = 'ltv',            _('Lifetime Value')
    CONVERSION      = 'conversion',     _('Conversion Probability')
    RECOMMENDATION  = 'recommendation', _('Recommendation')
    CLICK           = 'click',          _('Click Prediction')
    REVENUE         = 'revenue',        _('Revenue Forecast')
    ANOMALY_SCORE   = 'anomaly',        _('Anomaly Score')
    SENTIMENT       = 'sentiment',      _('Sentiment')
    CUSTOM          = 'custom',         _('Custom')


class RecommendationEngine(models.TextChoices):
    COLLABORATIVE   = 'collaborative',  _('Collaborative Filtering')
    CONTENT_BASED   = 'content_based',  _('Content-Based')
    HYBRID          = 'hybrid',         _('Hybrid')
    POPULARITY      = 'popularity',     _('Popularity-Based')
    CONTEXTUAL      = 'contextual',     _('Contextual')
    SESSION         = 'session',        _('Session-Based')
    TRENDING        = 'trending',       _('Trending')
    PERSONALIZED    = 'personalized',   _('Deep Personalization')


class SentimentLabel(models.TextChoices):
    POSITIVE = 'positive', _('Positive')
    NEGATIVE = 'negative', _('Negative')
    NEUTRAL  = 'neutral',  _('Neutral')
    MIXED    = 'mixed',    _('Mixed')


class RiskLevel(models.TextChoices):
    VERY_LOW  = 'very_low',  _('Very Low (0-20%)')
    LOW       = 'low',       _('Low (20-40%)')
    MEDIUM    = 'medium',    _('Medium (40-60%)')
    HIGH      = 'high',      _('High (60-80%)')
    VERY_HIGH = 'very_high', _('Very High (80-100%)')


class ExperimentStatus(models.TextChoices):
    DRAFT       = 'draft',      _('Draft')
    RUNNING     = 'running',    _('Running')
    PAUSED      = 'paused',     _('Paused')
    COMPLETED   = 'completed',  _('Completed')
    CANCELLED   = 'cancelled',  _('Cancelled')


class WinnerChoice(models.TextChoices):
    CONTROL     = 'control',     _('Control')
    TREATMENT_A = 'treatment_a', _('Treatment A')
    TREATMENT_B = 'treatment_b', _('Treatment B')
    NO_WINNER   = 'no_winner',   _('No Significant Winner')
    PENDING     = 'pending',     _('Pending')


class TrainingJobStatus(models.TextChoices):
    QUEUED      = 'queued',     _('Queued')
    RUNNING     = 'running',    _('Running')
    COMPLETED   = 'completed',  _('Completed')
    FAILED      = 'failed',     _('Failed')
    CANCELLED   = 'cancelled',  _('Cancelled')


class ContentViolationType(models.TextChoices):
    SPAM            = 'spam',           _('Spam')
    HATE_SPEECH     = 'hate_speech',    _('Hate Speech')
    HARASSMENT      = 'harassment',     _('Harassment')
    NSFW            = 'nsfw',           _('NSFW / Adult')
    VIOLENCE        = 'violence',       _('Violence')
    FRAUD           = 'fraud',          _('Fraudulent Content')
    PROFANITY       = 'profanity',      _('Profanity')
    OTHER           = 'other',          _('Other')


class ModerationAction(models.TextChoices):
    ALLOW           = 'allow',          _('Allowed')
    WARN            = 'warn',           _('Warning Issued')
    REMOVE          = 'remove',         _('Content Removed')
    SHADOW_BAN      = 'shadow_ban',     _('Shadow Banned')
    BLOCK_USER      = 'block_user',     _('User Blocked')
    REVIEW_NEEDED   = 'review_needed',  _('Manual Review Needed')


class ModelStage(models.TextChoices):
    DEVELOPMENT = 'development', _('Development')
    STAGING     = 'staging',     _('Staging')
    PRODUCTION  = 'production',  _('Production')
    ARCHIVED    = 'archived',    _('Archived')


class DriftStatus(models.TextChoices):
    NORMAL   = 'normal',   _('Normal — No Drift')
    WARNING  = 'warning',  _('Warning — Mild Drift')
    CRITICAL = 'critical', _('Critical — Significant Drift')


class InsightType(models.TextChoices):
    TREND           = 'trend',          _('Trend')
    ANOMALY         = 'anomaly',        _('Anomaly Alert')
    OPPORTUNITY     = 'opportunity',    _('Opportunity')
    RISK            = 'risk',           _('Risk Warning')
    PREDICTION      = 'prediction',     _('Prediction')
    RECOMMENDATION  = 'recommendation', _('Recommendation')
    PERFORMANCE     = 'performance',    _('Performance Summary')


class InsightPriority(models.TextChoices):
    LOW    = 'low',    _('Low')
    MEDIUM = 'medium', _('Medium')
    HIGH   = 'high',   _('High')
    URGENT = 'urgent', _('Urgent')
