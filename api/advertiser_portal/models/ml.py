"""
Machine Learning Models for Advertiser Portal

This module contains models for machine learning integration
including user journey tracking, network performance caching, and ML models.
"""

import logging
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()
logger = logging.getLogger(__name__)


class UserJourneyStep(models.Model):
    """
    Model for tracking user journey steps.
    
    Stores user behavior data for ML analysis
    and personalization optimization.
    """
    
    # Core relationships
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='journey_steps',
        verbose_name=_('User'),
        help_text=_('User this journey step belongs to')
    )
    
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='user_journey_steps',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this journey step belongs to')
    )
    
    # Journey details
    session_id = models.CharField(
        _('Session ID'),
        max_length=100,
        db_index=True,
        help_text=_('Unique session identifier')
    )
    
    step_type = models.CharField(
        _('Step Type'),
        max_length=50,
        choices=[
            ('landing', _('Landing')),
            ('click', _('Click')),
            ('view', _('View')),
            ('conversion', _('Conversion')),
            ('exit', _('Exit')),
        ],
        help_text=_('Type of journey step')
    )
    
    step_number = models.PositiveIntegerField(
        _('Step Number'),
        help_text=_('Order of this step in the journey')
    )
    
    # Context data
    url = models.URLField(
        _('URL'),
        max_length=2000,
        help_text=_('URL of the journey step')
    )
    
    referrer = models.URLField(
        _('Referrer'),
        max_length=2000,
        blank=True,
        help_text=_('Referrer URL')
    )
    
    user_agent = models.TextField(
        _('User Agent'),
        blank=True,
        help_text=_('User agent string')
    )
    
    ip_address = models.GenericIPAddressField(
        _('IP Address'),
        help_text=_('IP address of the user')
    )
    
    # Timing data
    timestamp = models.DateTimeField(
        _('Timestamp'),
        default=timezone.now,
        help_text=_('When this step occurred')
    )
    
    time_on_page = models.FloatField(
        _('Time on Page'),
        null=True,
        blank=True,
        help_text=_('Time spent on this page in seconds')
    )
    
    scroll_depth = models.FloatField(
        _('Scroll Depth'),
        null=True,
        blank=True,
        help_text=_('Scroll depth percentage')
    )
    
    # Device and location data
    device_type = models.CharField(
        _('Device Type'),
        max_length=20,
        choices=[
            ('desktop', _('Desktop')),
            ('mobile', _('Mobile')),
            ('tablet', _('Tablet')),
            ('unknown', _('Unknown')),
        ],
        default='unknown',
        help_text=_('Device type')
    )
    
    browser = models.CharField(
        _('Browser'),
        max_length=50,
        blank=True,
        help_text=_('Browser name')
    )
    
    os = models.CharField(
        _('Operating System'),
        max_length=50,
        blank=True,
        help_text=_('Operating system')
    )
    
    country = models.CharField(
        _('Country'),
        max_length=2,
        blank=True,
        help_text=_('Country code')
    )
    
    region = models.CharField(
        _('Region'),
        max_length=100,
        blank=True,
        help_text=_('Region or state')
    )
    
    city = models.CharField(
        _('City'),
        max_length=100,
        blank=True,
        help_text=_('City')
    )
    
    # Conversion data
    conversion_value = models.DecimalField(
        _('Conversion Value'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Value of conversion if applicable')
    )
    
    offer_id = models.CharField(
        _('Offer ID'),
        max_length=100,
        blank=True,
        help_text=_('Offer identifier if applicable')
    )
    
    campaign_id = models.CharField(
        _('Campaign ID'),
        max_length=100,
        blank=True,
        help_text=_('Campaign identifier if applicable')
    )
    
    # Custom parameters
    custom_data = models.JSONField(
        _('Custom Data'),
        default=dict,
        blank=True,
        help_text=_('Custom journey data')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('User Journey Step')
        verbose_name_plural = _('User Journey Steps')
        ordering = ['session_id', 'step_number']
        indexes = [
            models.Index(fields=['user', 'timestamp'], name='idx_user_timestamp_474'),
            models.Index(fields=['advertiser', 'timestamp'], name='idx_advertiser_timestamp_475'),
            models.Index(fields=['session_id', 'step_number'], name='idx_session_id_step_number_476'),
            models.Index(fields=['step_type', 'timestamp'], name='idx_step_type_timestamp_477'),
            models.Index(fields=['device_type'], name='idx_device_type_478'),
            models.Index(fields=['country'], name='idx_country_479'),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.session_id} - Step {self.step_number}"
    
    def clean(self):
        """Validate journey step data."""
        super().clean()
        
        if self.time_on_page and self.time_on_page < 0:
            raise ValidationError(_('Time on page cannot be negative'))
        
        if self.scroll_depth and (self.scroll_depth < 0 or self.scroll_depth > 100):
            raise ValidationError(_('Scroll depth must be between 0 and 100'))
        
        if self.conversion_value and self.conversion_value < 0:
            raise ValidationError(_('Conversion value cannot be negative'))
    
    @property
    def is_conversion_step(self):
        """Check if this is a conversion step."""
        return self.step_type == 'conversion'
    
    @property
    def is_exit_step(self):
        """Check if this is an exit step."""
        return self.step_type == 'exit'
    
    def get_device_info(self):
        """Get device information as dictionary."""
        return {
            'device_type': self.device_type,
            'browser': self.browser,
            'os': self.os,
        }
    
    def get_location_info(self):
        """Get location information as dictionary."""
        return {
            'country': self.country,
            'region': self.region,
            'city': self.city,
        }


class NetworkPerformanceCache(models.Model):
    """
    Model for caching network performance data.
    
    Stores performance metrics for optimization
    and ML model training.
    """
    
    # Core relationships
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='network_performance_cache',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this cache belongs to')
    )
    
    # Cache key and type
    cache_key = models.CharField(
        _('Cache Key'),
        max_length=200,
        unique=True,
        db_index=True,
        help_text=_('Unique cache key')
    )
    
    cache_type = models.CharField(
        _('Cache Type'),
        max_length=50,
        choices=[
            ('offer_performance', _('Offer Performance')),
            ('campaign_performance', _('Campaign Performance')),
            ('affiliate_performance', _('Affiliate Performance')),
            ('geo_performance', _('Geo Performance')),
            ('device_performance', _('Device Performance')),
            ('time_performance', _('Time Performance')),
        ],
        help_text=_('Type of cached data')
    )
    
    # Performance metrics
    impressions = models.PositiveIntegerField(
        _('Impressions'),
        default=0,
        help_text=_('Number of impressions')
    )
    
    clicks = models.PositiveIntegerField(
        _('Clicks'),
        default=0,
        help_text=_('Number of clicks')
    )
    
    conversions = models.PositiveIntegerField(
        _('Conversions'),
        default=0,
        help_text=_('Number of conversions')
    )
    
    revenue = models.DecimalField(
        _('Revenue'),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Total revenue')
    )
    
    cost = models.DecimalField(
        _('Cost'),
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text=_('Total cost')
    )
    
    # Calculated metrics
    ctr = models.FloatField(
        _('Click-Through Rate'),
        default=0.0,
        help_text=_('Click-through rate percentage')
    )
    
    conversion_rate = models.FloatField(
        _('Conversion Rate'),
        default=0.0,
        help_text=_('Conversion rate percentage')
    )
    
    cpc = models.DecimalField(
        _('Cost Per Click'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('Cost per click')
    )
    
    cpa = models.DecimalField(
        _('Cost Per Acquisition'),
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text=_('Cost per acquisition')
    )
    
    roi = models.FloatField(
        _('Return on Investment'),
        default=0.0,
        help_text=_('ROI percentage')
    )
    
    # Quality metrics
    quality_score = models.FloatField(
        _('Quality Score'),
        default=0.0,
        help_text=_('Quality score (0.0-1.0)')
    )
    
    fraud_score = models.FloatField(
        _('Fraud Score'),
        default=0.0,
        help_text=_('Fraud score (0.0-1.0)')
    )
    
    # Time period
    period_start = models.DateTimeField(
        _('Period Start'),
        help_text=_('Start of the time period')
    )
    
    period_end = models.DateTimeField(
        _('Period End'),
        help_text=_('End of the time period')
    )
    
    period_type = models.CharField(
        _('Period Type'),
        max_length=20,
        choices=[
            ('hourly', _('Hourly')),
            ('daily', _('Daily')),
            ('weekly', _('Weekly')),
            ('monthly', _('Monthly')),
        ],
        help_text=_('Type of time period')
    )
    
    # Additional data
    metadata = models.JSONField(
        _('Metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional metadata')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this cache entry was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this cache entry was last updated')
    )
    
    expires_at = models.DateTimeField(
        _('Expires At'),
        null=True,
        blank=True,
        help_text=_('When this cache entry expires')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('Network Performance Cache')
        verbose_name_plural = _('Network Performance Caches')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['advertiser', 'cache_type', 'period_start'], name='idx_advertiser_cache_type__81b'),
            models.Index(fields=['cache_key'], name='idx_cache_key_481'),
            models.Index(fields=['cache_type', 'period_end'], name='idx_cache_type_period_end_482'),
            models.Index(fields=['expires_at'], name='idx_expires_at_483'),
        ]
    
    def __str__(self):
        return f"{self.advertiser.company_name} - {self.cache_type} - {self.cache_key}"
    
    def clean(self):
        """Validate cache data."""
        super().clean()
        
        if self.period_start and self.period_end and self.period_start >= self.period_end:
            raise ValidationError(_('Period start must be before period end'))
        
        if self.ctr < 0 or self.ctr > 100:
            raise ValidationError(_('CTR must be between 0 and 100'))
        
        if self.conversion_rate < 0 or self.conversion_rate > 100:
            raise ValidationError(_('Conversion rate must be between 0 and 100'))
        
        if self.quality_score < 0 or self.quality_score > 1:
            raise ValidationError(_('Quality score must be between 0 and 1'))
        
        if self.fraud_score < 0 or self.fraud_score > 1:
            raise ValidationError(_('Fraud score must be between 0 and 1'))
    
    def calculate_metrics(self):
        """Calculate derived metrics."""
        if self.impressions > 0:
            self.ctr = (self.clicks / self.impressions) * 100
        
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100
            self.cpc = self.cost / self.clicks
        
        if self.conversions > 0:
            self.cpa = self.cost / self.conversions
        
        if self.cost > 0:
            self.roi = ((self.revenue - self.cost) / self.cost) * 100
    
    def is_expired(self):
        """Check if cache entry is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    def get_performance_summary(self):
        """Get performance summary as dictionary."""
        return {
            'impressions': self.impressions,
            'clicks': self.clicks,
            'conversions': self.conversions,
            'revenue': float(self.revenue),
            'cost': float(self.cost),
            'ctr': self.ctr,
            'conversion_rate': self.conversion_rate,
            'cpc': float(self.cpc),
            'cpa': float(self.cpa),
            'roi': self.roi,
            'quality_score': self.quality_score,
            'fraud_score': self.fraud_score,
        }


class MLModel(models.Model):
    """
    Model for managing ML models.
    
    Stores ML model configurations and metadata.
    """
    
    # Core fields
    name = models.CharField(
        _('Model Name'),
        max_length=100,
        unique=True,
        help_text=_('Unique model name')
    )
    
    model_type = models.CharField(
        _('Model Type'),
        max_length=50,
        choices=[
            ('classification', _('Classification')),
            ('regression', _('Regression')),
            ('clustering', _('Clustering')),
            ('recommendation', _('Recommendation')),
            ('anomaly_detection', _('Anomaly Detection')),
            ('time_series', _('Time Series')),
        ],
        help_text=_('Type of ML model')
    )
    
    version = models.CharField(
        _('Version'),
        max_length=20,
        help_text=_('Model version')
    )
    
    # Model configuration
    algorithm = models.CharField(
        _('Algorithm'),
        max_length=100,
        help_text=_('Algorithm used')
    )
    
    hyperparameters = models.JSONField(
        _('Hyperparameters'),
        default=dict,
        blank=True,
        help_text=_('Model hyperparameters')
    )
    
    # Performance metrics
    accuracy = models.FloatField(
        _('Accuracy'),
        null=True,
        blank=True,
        help_text=_('Model accuracy score')
    )
    
    precision = models.FloatField(
        _('Precision'),
        null=True,
        blank=True,
        help_text=_('Model precision score')
    )
    
    recall = models.FloatField(
        _('Recall'),
        null=True,
        blank=True,
        help_text=_('Model recall score')
    )
    
    f1_score = models.FloatField(
        _('F1 Score'),
        null=True,
        blank=True,
        help_text=_('Model F1 score')
    )
    
    # Training data
    training_data_count = models.PositiveIntegerField(
        _('Training Data Count'),
        default=0,
        help_text=_('Number of training samples')
    )
    
    validation_data_count = models.PositiveIntegerField(
        _('Validation Data Count'),
        default=0,
        help_text=_('Number of validation samples')
    )
    
    # Status
    is_active = models.BooleanField(
        _('Is Active'),
        default=True,
        help_text=_('Whether this model is active')
    )
    
    is_trained = models.BooleanField(
        _('Is Trained'),
        default=False,
        help_text=_('Whether this model is trained')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this model was created')
    )
    
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True,
        help_text=_('When this model was last updated')
    )
    
    trained_at = models.DateTimeField(
        _('Trained At'),
        null=True,
        blank=True,
        help_text=_('When this model was trained')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('ML Model')
        verbose_name_plural = _('ML Models')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model_type', 'is_active'], name='idx_model_type_is_active_484'),
            models.Index(fields=['algorithm'], name='idx_algorithm_485'),
            models.Index(fields=['is_trained'], name='idx_is_trained_486'),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version} ({self.model_type})"
    
    def clean(self):
        """Validate model data."""
        super().clean()
        
        if self.accuracy and (self.accuracy < 0 or self.accuracy > 1):
            raise ValidationError(_('Accuracy must be between 0 and 1'))
        
        if self.precision and (self.precision < 0 or self.precision > 1):
            raise ValidationError(_('Precision must be between 0 and 1'))
        
        if self.recall and (self.recall < 0 or self.recall > 1):
            raise ValidationError(_('Recall must be between 0 and 1'))
        
        if self.f1_score and (self.f1_score < 0 or self.f1_score > 1):
            raise ValidationError(_('F1 score must be between 0 and 1'))
    
    def mark_trained(self):
        """Mark model as trained."""
        self.is_trained = True
        self.trained_at = timezone.now()
        self.save()
    
    def get_performance_metrics(self):
        """Get performance metrics as dictionary."""
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
        }


class MLPrediction(models.Model):
    """
    Model for storing ML predictions.
    
    Stores prediction results and metadata.
    """
    
    # Core relationships
    model = models.ForeignKey(
        MLModel,
        on_delete=models.CASCADE,
        related_name='predictions',
        verbose_name=_('Model'),
        help_text=_('ML model that made this prediction')
    )
    
    advertiser = models.ForeignKey(
        'advertiser_portal_v2.Advertiser',
        on_delete=models.CASCADE,
        related_name='ml_predictions',
        verbose_name=_('Advertiser'),
        help_text=_('Advertiser this prediction belongs to')
    )
    
    # Prediction data
    prediction_type = models.CharField(
        _('Prediction Type'),
        max_length=50,
        help_text=_('Type of prediction')
    )
    
    input_data = models.JSONField(
        _('Input Data'),
        help_text=_('Input data for prediction')
    )
    
    prediction_result = models.JSONField(
        _('Prediction Result'),
        help_text=_('Prediction result')
    )
    
    confidence_score = models.FloatField(
        _('Confidence Score'),
        help_text=_('Confidence score (0.0-1.0)')
    )
    
    # Metadata
    prediction_id = models.CharField(
        _('Prediction ID'),
        max_length=100,
        unique=True,
        help_text=_('Unique prediction identifier')
    )
    
    session_id = models.CharField(
        _('Session ID'),
        max_length=100,
        blank=True,
        help_text=_('Session identifier')
    )
    
    user_id = models.PositiveIntegerField(
        _('User ID'),
        null=True,
        blank=True,
        help_text=_('User identifier if applicable')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True,
        help_text=_('When this prediction was made')
    )
    
    class Meta:
        app_label = 'advertiser_portal_v2'
        verbose_name = _('ML Prediction')
        verbose_name_plural = _('ML Predictions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['model', 'created_at'], name='idx_model_created_at_487'),
            models.Index(fields=['advertiser', 'created_at'], name='idx_advertiser_created_at_488'),
            models.Index(fields=['prediction_type'], name='idx_prediction_type_489'),
            models.Index(fields=['prediction_id'], name='idx_prediction_id_490'),
            models.Index(fields=['session_id'], name='idx_session_id_491'),
        ]
    
    def __str__(self):
        return f"{self.model.name} - {self.prediction_type} - {self.prediction_id}"
    
    def clean(self):
        """Validate prediction data."""
        super().clean()
        
        if self.confidence_score < 0 or self.confidence_score > 1:
            raise ValidationError(_('Confidence score must be between 0 and 1'))
    
    def get_prediction_summary(self):
        """Get prediction summary as dictionary."""
        return {
            'prediction_type': self.prediction_type,
            'confidence_score': self.confidence_score,
            'result': self.prediction_result,
            'created_at': self.created_at.isoformat(),
        }
        app_label = 'advertiser_portal_v2'
