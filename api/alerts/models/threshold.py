"""
Alert Threshold Models
"""
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from datetime import timedelta
import json

from decimal import Decimal
import uuid

from .core import AlertRule, AlertLog


class ThresholdConfig(models.Model):
    """Advanced threshold configurations for alert rules"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    THRESHOLD_TYPES = [
        ('static', 'Static Threshold'),
        ('dynamic', 'Dynamic Threshold'),
        ('seasonal', 'Seasonal Threshold'),
        ('anomaly_based', 'Anomaly-Based'),
        ('machine_learning', 'Machine Learning'),
    ]
    
    COMPARISON_OPERATORS = [
        ('gt', 'Greater Than'),
        ('gte', 'Greater Than or Equal'),
        ('lt', 'Less Than'),
        ('lte', 'Less Than or Equal'),
        ('eq', 'Equal'),
        ('ne', 'Not Equal'),
        ('range', 'Within Range'),
        ('outside_range', 'Outside Range'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Basic threshold configuration
    alert_rule = models.ForeignKey(
        AlertRule,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    threshold_type = models.CharField(max_length=20, choices=THRESHOLD_TYPES, default='static')
    comparison_operator = models.CharField(max_length=15, choices=COMPARISON_OPERATORS, default='gt')
    
    # Threshold values
    primary_threshold = models.FloatField(help_text="Primary threshold value")
    secondary_threshold = models.FloatField(
        null=True, 
        blank=True,
        help_text="Secondary threshold for range-based comparisons"
    )
    
    # Dynamic threshold settings
    calculation_window_minutes = models.IntegerField(
        default=60,
        help_text="Time window for dynamic calculations",
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    percentile_value = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentile for dynamic thresholds (e.g., 95th percentile)"
    )
    standard_deviations = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.1), MaxValueValidator(5)],
        help_text="Number of standard deviations for anomaly detection"
    )
    
    # Seasonal settings
    seasonal_pattern = models.CharField(
        max_length=20,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        blank=True
    )
    seasonal_adjustment_factor = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.1), MaxValueValidator(10)],
        help_text="Factor to adjust threshold based on seasonal patterns"
    )
    
    # Machine learning settings
    model_type = models.CharField(
        max_length=20,
        choices=[
            ('linear_regression', 'Linear Regression'),
            ('arima', 'ARIMA'),
            ('lstm', 'LSTM Neural Network'),
            ('isolation_forest', 'Isolation Forest'),
            ('one_class_svm', 'One-Class SVM'),
        ],
        blank=True
    )
    model_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Parameters for ML model configuration"
    )
    
    # Status and metadata
    is_active = models.BooleanField(default=True, db_index=True)
    last_calculated = models.DateTimeField(null=True, blank=True)
    calculation_frequency_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_thresholdconfig_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_threshold_type_display()})"
    
    def clean(self):
        """Validate threshold configuration"""
        super().clean()
        
        # Validate threshold type specific requirements
        if self.threshold_type == 'range' and not self.secondary_threshold:
            raise ValidationError("Secondary threshold is required for range-based comparisons")
        
        if self.threshold_type == 'dynamic' and not self.percentile_value and not self.standard_deviations:
            raise ValidationError("Either percentile value or standard deviations must be specified for dynamic thresholds")
        
        if self.threshold_type == 'seasonal' and not self.seasonal_pattern:
            raise ValidationError("Seasonal pattern must be specified for seasonal thresholds")
        
        if self.threshold_type == 'machine_learning' and not self.model_type:
            raise ValidationError("Model type must be specified for machine learning thresholds")
    
    def calculate_threshold(self, current_value=None):
        """Calculate dynamic threshold based on configuration"""
        if self.threshold_type == 'static':
            return self.primary_threshold
        
        elif self.threshold_type == 'dynamic':
            return self._calculate_dynamic_threshold(current_value)
        
        elif self.threshold_type == 'seasonal':
            return self._calculate_seasonal_threshold(current_value)
        
        elif self.threshold_type == 'machine_learning':
            return self._calculate_ml_threshold(current_value)
        
        return self.primary_threshold
    
    def _calculate_dynamic_threshold(self, current_value=None):
        """Calculate dynamic threshold using statistical methods"""
        from django.db.models import Avg, StdDev, Count
        
        # Get historical data
        cutoff_time = timezone.now() - timedelta(minutes=self.calculation_window_minutes)
        historical_data = AlertLog.objects.filter(
            rule=self.alert_rule,
            triggered_at__gte=cutoff_time
        ).aggregate(
            avg_value=Avg('trigger_value'),
            std_dev=StdDev('trigger_value'),
            count=Count('id')
        )
        
        if historical_data['count'] < 10:  # Not enough data
            return self.primary_threshold
        
        if self.percentile_value:
            # Calculate percentile-based threshold
            values = list(AlertLog.objects.filter(
                rule=self.alert_rule,
                triggered_at__gte=cutoff_time
            ).values_list('trigger_value', flat=True))
            
            values.sort()
            index = int(len(values) * (self.percentile_value / 100))
            return values[min(index, len(values) - 1)]
        
        elif self.standard_deviations:
            # Calculate standard deviation-based threshold
            avg = historical_data['avg_value'] or 0
            std_dev = historical_data['std_dev'] or 0
            return avg + (self.standard_deviations * std_dev)
        
        return self.primary_threshold
    
    def _calculate_seasonal_threshold(self, current_value=None):
        """Calculate seasonal threshold"""
        base_threshold = self.primary_threshold
        
        if not self.seasonal_pattern:
            return base_threshold
        
        now = timezone.now()
        
        if self.seasonal_pattern == 'daily':
            # Adjust based on hour of day
            hour_factor = 1.0 + (0.2 * math.sin((now.hour - 6) * math.pi / 12))
            return base_threshold * hour_factor * self.seasonal_adjustment_factor
        
        elif self.seasonal_pattern == 'weekly':
            # Adjust based on day of week
            weekday_factor = 1.0 + (0.3 * math.sin((now.weekday() - 3) * math.pi / 3.5))
            return base_threshold * weekday_factor * self.seasonal_adjustment_factor
        
        elif self.seasonal_pattern == 'monthly':
            # Adjust based on day of month
            day_factor = 1.0 + (0.2 * math.sin((now.day - 15) * math.pi / 15))
            return base_threshold * day_factor * self.seasonal_adjustment_factor
        
        return base_threshold
    
    def _calculate_ml_threshold(self, current_value=None):
        """Calculate threshold using machine learning"""
        # This is a placeholder for ML-based threshold calculation
        # In a real implementation, this would use trained models
        return self.primary_threshold
    
    def evaluate_condition(self, current_value):
        """Evaluate if current value meets threshold condition"""
        threshold = self.calculate_threshold(current_value)
        
        if self.comparison_operator == 'gt':
            return current_value > threshold
        elif self.comparison_operator == 'gte':
            return current_value >= threshold
        elif self.comparison_operator == 'lt':
            return current_value < threshold
        elif self.comparison_operator == 'lte':
            return current_value <= threshold
        elif self.comparison_operator == 'eq':
            return abs(current_value - threshold) < 0.001
        elif self.comparison_operator == 'ne':
            return abs(current_value - threshold) >= 0.001
        elif self.comparison_operator == 'range':
            return self.secondary_threshold and (
                self.primary_threshold <= current_value <= self.secondary_threshold
            )
        elif self.comparison_operator == 'outside_range':
            return self.secondary_threshold and (
                current_value < self.primary_threshold or current_value > self.secondary_threshold
            )
        
        return False
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['alert_rule', 'is_active']),
            models.Index(fields=['threshold_type', 'is_active']),
            models.Index(fields=['last_calculated']),
        ]
        db_table_comment = "Advanced threshold configurations for alert rules"
        verbose_name = "Threshold Configuration"
        verbose_name_plural = "Threshold Configurations"


class ThresholdBreach(models.Model):
    """Record of threshold breaches for analysis"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    threshold_config = models.ForeignKey(
        ThresholdConfig,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    alert_log = models.ForeignKey(
        AlertLog,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Breach details
    breach_value = models.FloatField()
    threshold_value = models.FloatField()
    breach_percentage = models.FloatField(
        help_text="How much the value exceeded the threshold (in percentage)"
    )
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS)
    
    # Context information
    context_data = models.JSONField(
        default=dict,
        help_text="Additional context about the breach"
    )
    
    # Resolution
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_thresholdbreach_resolved_by'
    )
    resolution_notes = models.TextField(blank=True)
    
    # Metadata
    detected_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_thresholdbreach_acknowledged_by'
    )
    
    def __str__(self):
        return f"Breach: {self.threshold_config.name} at {self.detected_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def duration_minutes(self):
        """Calculate duration of breach"""
        end_time = self.resolved_at or timezone.now()
        return (end_time - self.detected_at).total_seconds() / 60
    
    @property
    def is_resolved(self):
        """Check if breach is resolved"""
        return self.resolved_at is not None
    
    def acknowledge(self, user, notes=""):
        """Acknowledge the breach"""
        self.acknowledged_at = timezone.now()
        self.acknowledged_by = user
        if notes:
            self.resolution_notes = notes
        self.save(update_fields=['acknowledged_at', 'acknowledged_by', 'resolution_notes'])
    
    def resolve(self, user, notes=""):
        """Resolve the breach"""
        self.resolved_at = timezone.now()
        self.resolved_by = user
        if notes:
            self.resolution_notes = notes
        self.save(update_fields=['resolved_at', 'resolved_by', 'resolution_notes'])
    
    class Meta:
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['threshold_config', 'detected_at']),
            models.Index(fields=['severity', 'detected_at']),
            models.Index(fields=['resolved_at']),
            models.Index(fields=['acknowledged_at']),
        ]
        db_table_comment = "Records of threshold breaches for analysis"
        verbose_name = "Threshold Breach"
        verbose_name_plural = "Threshold Breaches"


class AdaptiveThreshold(models.Model):
    """Self-adjusting thresholds based on historical patterns"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ADAPTATION_METHODS = [
        ('exponential_smoothing', 'Exponential Smoothing'),
        ('moving_average', 'Moving Average'),
        ('linear_regression', 'Linear Regression'),
        ('neural_network', 'Neural Network'),
        ('ensemble', 'Ensemble Method'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Base configuration
    base_threshold = models.FloatField()
    threshold_config = models.OneToOneField(
        ThresholdConfig,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Adaptation settings
    adaptation_method = models.CharField(max_length=50, choices=ADAPTATION_METHODS)
    learning_rate = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0.001), MaxValueValidator(1.0)],
        help_text="Rate at which threshold adapts"
    )
    adaptation_window_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1), MaxValueValidator(90)],
        help_text="Days of historical data to consider for adaptation"
    )
    
    # Constraints
    min_threshold = models.FloatField(
        validators=[MinValueValidator(0)],
        help_text="Minimum allowed threshold value"
    )
    max_threshold = models.FloatField(
        help_text="Maximum allowed threshold value"
    )
    max_adjustment_percentage = models.FloatField(
        default=50.0,
        validators=[MinValueValidator(0), MaxValueValidator(200)],
        help_text="Maximum percentage adjustment from base threshold"
    )
    
    # Current state
    current_threshold = models.FloatField()
    last_adaptation = models.DateTimeField(null=True, blank=True)
    adaptation_count = models.IntegerField(default=0)
    
    # Performance tracking
    prediction_accuracy = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Accuracy of threshold predictions"
    )
    false_positive_rate = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Rate of false positive alerts"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Adaptive: {self.name} (Current: {self.current_threshold})"
    
    def adapt_threshold(self):
        """Adapt threshold based on recent data"""
        if self.adaptation_method == 'exponential_smoothing':
            self._exponential_smoothing_adaptation()
        elif self.adaptation_method == 'moving_average':
            self._moving_average_adaptation()
        elif self.adaptation_method == 'linear_regression':
            self._linear_regression_adaptation()
        elif self.adaptation_method == 'neural_network':
            self._neural_network_adaptation()
        elif self.adaptation_method == 'ensemble':
            self._ensemble_adaptation()
        
        # Apply constraints
        self.current_threshold = max(self.min_threshold, min(self.max_threshold, self.current_threshold))
        
        # Check max adjustment
        max_adjustment = self.base_threshold * (self.max_adjustment_percentage / 100)
        if abs(self.current_threshold - self.base_threshold) > max_adjustment:
            if self.current_threshold > self.base_threshold:
                self.current_threshold = self.base_threshold + max_adjustment
            else:
                self.current_threshold = self.base_threshold - max_adjustment
        
        self.last_adaptation = timezone.now()
        self.adaptation_count += 1
        self.save(update_fields=['current_threshold', 'last_adaptation', 'adaptation_count'])
    
    def _exponential_smoothing_adaptation(self):
        """Adapt using exponential smoothing"""
        cutoff_date = timezone.now() - timedelta(days=self.adaptation_window_days)
        recent_alerts = AlertLog.objects.filter(
            rule=self.threshold_config.alert_rule,
            triggered_at__gte=cutoff_date
        ).order_by('triggered_at')
        
        if not recent_alerts.exists():
            return
        
        values = list(recent_alerts.values_list('trigger_value', flat=True))
        
        # Calculate exponential smoothing
        smoothed_value = values[0]
        for value in values[1:]:
            smoothed_value = self.learning_rate * value + (1 - self.learning_rate) * smoothed_value
        
        # Adjust threshold based on smoothed trend
        if smoothed_value > self.current_threshold:
            self.current_threshold = self.current_threshold * (1 + self.learning_rate * 0.1)
        else:
            self.current_threshold = self.current_threshold * (1 - self.learning_rate * 0.05)
    
    def _moving_average_adaptation(self):
        """Adapt using moving average"""
        cutoff_date = timezone.now() - timedelta(days=self.adaptation_window_days)
        recent_alerts = AlertLog.objects.filter(
            rule=self.threshold_config.alert_rule,
            triggered_at__gte=cutoff_date
        ).aggregate(
            avg_value=models.Avg('trigger_value')
        )
        
        if recent_alerts['avg_value']:
            # Adjust threshold towards moving average
            avg_value = recent_alerts['avg_value']
            adjustment = (avg_value - self.current_threshold) * self.learning_rate
            self.current_threshold += adjustment
    
    def _linear_regression_adaptation(self):
        """Adapt using linear regression"""
        # Simplified linear regression adaptation
        cutoff_date = timezone.now() - timedelta(days=self.adaptation_window_days)
        recent_alerts = AlertLog.objects.filter(
            rule=self.threshold_config.alert_rule,
            triggered_at__gte=cutoff_date
        ).order_by('triggered_at')
        
        if recent_alerts.count() < 10:
            return
        
        # Calculate trend
        values = list(recent_alerts.values_list('trigger_value', flat=True))
        n = len(values)
        
        # Simple linear regression
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator != 0:
            slope = numerator / denominator
            # Predict next value and adjust threshold
            predicted_next = y_mean + slope * (n - x_mean)
            adjustment = (predicted_next - self.current_threshold) * self.learning_rate
            self.current_threshold += adjustment
    
    def _neural_network_adaptation(self):
        """Adapt using neural network (placeholder)"""
        # This would implement a simple neural network for threshold adaptation
        # For now, use a simplified approach
        self._moving_average_adaptation()
    
    def _ensemble_adaptation(self):
        """Adapt using ensemble of methods"""
        methods = ['exponential_smoothing', 'moving_average', 'linear_regression']
        adaptations = []
        
        for method in methods:
            old_threshold = self.current_threshold
            self.adaptation_method = method
            self.adapt_threshold()
            adaptations.append(self.current_threshold)
            self.current_threshold = old_threshold
        
        # Average the adaptations
        self.current_threshold = sum(adaptations) / len(adaptations)
        self.adaptation_method = 'ensemble'
    
    def get_adaptation_history(self, days=30):
        """Get history of threshold adaptations"""
        return ThresholdHistory.objects.filter(
            adaptive_threshold=self,
            created_at__gte=timezone.now() - timedelta(days=days)
        ).order_by('-created_at')
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['threshold_config']),
            models.Index(fields=['last_adaptation']),
            models.Index(fields=['adaptation_method']),
        ]
        db_table_comment = "Self-adjusting thresholds based on historical patterns"
        verbose_name = "Adaptive Threshold"
        verbose_name_plural = "Adaptive Thresholds"


class ThresholdHistory(models.Model):
    """History of threshold changes and adaptations"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    CHANGE_TYPES = [
        ('manual', 'Manual Change'),
        ('automatic', 'Automatic Adaptation'),
        ('scheduled', 'Scheduled Update'),
        ('emergency', 'Emergency Adjustment'),
    ]
    
    adaptive_threshold = models.ForeignKey(
        AdaptiveThreshold,
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_tenant'
    )
    
    # Change details
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    old_threshold = models.FloatField()
    new_threshold = models.FloatField()
    change_percentage = models.FloatField()
    
    # Reason and context
    reason = models.TextField()
    context_data = models.JSONField(default=dict)
    
    # Metadata
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_thresholdhistory_changed_by'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"{self.get_change_type_display()}: {self.old_threshold} -> {self.new_threshold}"
    
    @property
    def is_increase(self):
        """Check if threshold was increased"""
        return self.new_threshold > self.old_threshold
    
    @property
    def is_decrease(self):
        """Check if threshold was decreased"""
        return self.new_threshold < self.old_threshold
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['adaptive_threshold', 'created_at']),
            models.Index(fields=['change_type', 'created_at']),
        ]
        db_table_comment = "History of threshold changes and adaptations"
        verbose_name = "Threshold History"
        verbose_name_plural = "Threshold Histories"


class ThresholdProfile(models.Model):
    """Pre-configured threshold profiles for different use cases"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    PROFILE_TYPES = [
        ('conservative', 'Conservative - Fewer false positives'),
        ('balanced', 'Balanced - Good accuracy'),
        ('aggressive', 'Aggressive - Catch more issues'),
        ('custom', 'Custom Configuration'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    profile_type = models.CharField(max_length=20, choices=PROFILE_TYPES)
    description = models.TextField()
    
    # Profile settings
    default_threshold_multiplier = models.FloatField(
        default=1.0,
        help_text="Multiplier to apply to base thresholds"
    )
    sensitivity_level = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="0 = least sensitive, 1 = most sensitive"
    )
    
    # Alert type specific settings
    alert_type_settings = models.JSONField(
        default=dict,
        help_text="Custom settings per alert type"
    )
    
    # Performance targets
    target_false_positive_rate = models.FloatField(
        default=0.05,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Target false positive rate (0-1)"
    )
    target_detection_rate = models.FloatField(
        default=0.95,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Target detection rate (0-1)"
    )
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    is_default = models.BooleanField(default=False)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_thresholdprofile_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_profile_type_display()})"
    
    def apply_to_threshold_config(self, threshold_config):
        """Apply profile settings to a threshold configuration"""
        # Apply base multiplier
        threshold_config.primary_threshold *= self.default_threshold_multiplier
        if threshold_config.secondary_threshold:
            threshold_config.secondary_threshold *= self.default_threshold_multiplier
        
        # Apply alert type specific settings
        alert_type_key = threshold_config.alert_rule.alert_type
        if alert_type_key in self.alert_type_settings:
            settings = self.alert_type_settings[alert_type_key]
            
            if 'multiplier' in settings:
                threshold_config.primary_threshold *= settings['multiplier']
                if threshold_config.secondary_threshold:
                    threshold_config.secondary_threshold *= settings['multiplier']
            
            if 'sensitivity_adjustment' in settings:
                adjustment = settings['sensitivity_adjustment'] * self.sensitivity_level
                threshold_config.primary_threshold *= (1 + adjustment)
                if threshold_config.secondary_threshold:
                    threshold_config.secondary_threshold *= (1 + adjustment)
        
        threshold_config.save()
        return threshold_config
    
    def get_effective_settings(self, alert_type):
        """Get effective settings for a specific alert type"""
        base_settings = {
            'multiplier': self.default_threshold_multiplier,
            'sensitivity': self.sensitivity_level,
        }
        
        if alert_type in self.alert_type_settings:
            base_settings.update(self.alert_type_settings[alert_type])
        
        return base_settings
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['profile_type', 'is_active']),
            models.Index(fields=['is_default']),
        ]
        db_table_comment = "Pre-configured threshold profiles for different use cases"
        verbose_name = "Threshold Profile"
        verbose_name_plural = "Threshold Profiles"
