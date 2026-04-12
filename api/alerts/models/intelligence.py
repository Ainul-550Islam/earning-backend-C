"""
Alert Intelligence Models
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
import math

from .core import AlertRule, AlertLog


class AlertCorrelation(models.Model):
    """Correlation analysis between alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    CORRELATION_TYPES = [
        ('temporal', 'Temporal'),
        ('causal', 'Causal'),
        ('statistical', 'Statistical'),
        ('pattern_based', 'Pattern-Based'),
        ('ml_based', 'Machine Learning'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('analyzing', 'Analyzing'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Correlation configuration
    correlation_type = models.CharField(max_length=20, choices=CORRELATION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Alert rules involved
    primary_rules = models.ManyToManyField(
        AlertRule,
        related_name='%(app_label)s_%(class)s_primary',
        blank=True
    )
    secondary_rules = models.ManyToManyField(
        AlertRule,
        related_name='%(app_label)s_%(class)s_secondary',
        blank=True
    )
    
    # Time window for correlation
    time_window_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    
    # Correlation parameters
    correlation_threshold = models.FloatField(
        default=0.7,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )
    minimum_occurrences = models.IntegerField(
        default=3,
        validators=[MinValueValidator(2)]
    )
    
    # Statistical parameters
    correlation_coefficient = models.FloatField(null=True, blank=True)
    p_value = models.FloatField(null=True, blank=True)
    confidence_level = models.FloatField(null=True, blank=True)
    
    # Pattern parameters
    pattern_description = models.TextField(blank=True)
    pattern_regex = models.CharField(max_length=500, blank=True)
    
    # ML parameters
    model_type = models.CharField(
        max_length=20,
        choices=[
            ('linear', 'Linear'),
            ('logistic', 'Logistic'),
            ('random_forest', 'Random Forest'),
            ('neural_network', 'Neural Network'),
        ],
        blank=True
    )
    model_parameters = models.JSONField(default=dict, blank=True)
    
    # Results
    correlation_strength = models.FloatField(null=True, blank=True)
    prediction_accuracy = models.FloatField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertcorrelation_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_analyzed = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Correlation: {self.name}"
    
    def analyze_correlation(self):
        """Analyze correlation between alert rules"""
        self.status = 'analyzing'
        self.save(update_fields=['status'])
        
        if self.correlation_type == 'temporal':
            self._analyze_temporal_correlation()
        elif self.correlation_type == 'statistical':
            self._analyze_statistical_correlation()
        elif self.correlation_type == 'pattern_based':
            self._analyze_pattern_correlation()
        elif self.correlation_type == 'ml_based':
            self._analyze_ml_correlation()
        
        self.last_analyzed = timezone.now()
        self.save(update_fields=['status', 'last_analyzed'])
    
    def _analyze_temporal_correlation(self):
        """Analyze temporal correlation"""
        primary_alerts = AlertLog.objects.filter(
            rule__in=self.primary_rules.all(),
            triggered_at__gte=timezone.now() - timedelta(days=30)
        ).order_by('triggered_at')
        
        secondary_alerts = AlertLog.objects.filter(
            rule__in=self.secondary_rules.all(),
            triggered_at__gte=timezone.now() - timedelta(days=30)
        ).order_by('triggered_at')
        
        # Find temporal patterns
        correlations = []
        for primary_alert in primary_alerts:
            window_start = primary_alert.triggered_at
            window_end = window_start + timedelta(minutes=self.time_window_minutes)
            
            matching_secondary = secondary_alerts.filter(
                triggered_at__gte=window_start,
                triggered_at__lte=window_end
            )
            
            if matching_secondary.exists():
                correlations.append({
                    'primary': primary_alert,
                    'secondary': list(matching_secondary),
                    'time_diff': [(sec.triggered_at - primary_alert.triggered_at).total_seconds() 
                               for sec in matching_secondary]
                })
        
        if len(correlations) >= self.minimum_occurrences:
            # Calculate correlation strength
            total_primary = primary_alerts.count()
            correlation_rate = len(correlations) / total_primary
            
            if correlation_rate >= self.correlation_threshold:
                self.status = 'confirmed'
                self.correlation_strength = correlation_rate
                self.confidence_level = min(0.95, correlation_rate * 1.2)
            else:
                self.status = 'rejected'
                self.correlation_strength = correlation_rate
        else:
            self.status = 'rejected'
            self.correlation_strength = len(correlations) / max(1, primary_alerts.count())
    
    def _analyze_statistical_correlation(self):
        """Analyze statistical correlation"""
        # Simplified statistical correlation analysis
        primary_data = []
        secondary_data = []
        
        # Collect paired data points
        for day in range(30):
            date = timezone.now().date() - timedelta(days=day)
            
            primary_count = AlertLog.objects.filter(
                rule__in=self.primary_rules.all(),
                triggered_at__date=date
            ).count()
            
            secondary_count = AlertLog.objects.filter(
                rule__in=self.secondary_rules.all(),
                triggered_at__date=date
            ).count()
            
            primary_data.append(primary_count)
            secondary_data.append(secondary_count)
        
        # Calculate Pearson correlation coefficient
        if len(primary_data) > 1:
            correlation = self._calculate_pearson_correlation(primary_data, secondary_data)
            self.correlation_coefficient = correlation
            
            if abs(correlation) >= self.correlation_threshold:
                self.status = 'confirmed'
                self.correlation_strength = abs(correlation)
            else:
                self.status = 'rejected'
                self.correlation_strength = abs(correlation)
    
    def _calculate_pearson_correlation(self, x, y):
        """Calculate Pearson correlation coefficient"""
        n = len(x)
        if n != len(y) or n == 0:
            return 0
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_y2 = sum(yi ** 2 for yi in y)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator = math.sqrt((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2))
        
        return numerator / denominator if denominator != 0 else 0
    
    def _analyze_pattern_correlation(self):
        """Analyze pattern-based correlation"""
        # Simplified pattern analysis
        patterns = []
        
        for rule in self.primary_rules.all():
            alerts = AlertLog.objects.filter(
                rule=rule,
                triggered_at__gte=timezone.now() - timedelta(days=30)
            )
            
            for alert in alerts:
                # Look for similar patterns in secondary alerts
                similar_secondary = AlertLog.objects.filter(
                    rule__in=self.secondary_rules.all(),
                    message__icontains=alert.message[:50],  # Partial message match
                    triggered_at__range=(
                        alert.triggered_at - timedelta(minutes=self.time_window_minutes),
                        alert.triggered_at + timedelta(minutes=self.time_window_minutes)
                    )
                )
                
                if similar_secondary.exists():
                    patterns.append({
                        'primary': alert,
                        'secondary': list(similar_secondary)
                    })
        
        if len(patterns) >= self.minimum_occurrences:
            correlation_rate = len(patterns) / max(1, AlertLog.objects.filter(
                rule__in=self.primary_rules.all(),
                triggered_at__gte=timezone.now() - timedelta(days=30)
            ).count())
            
            if correlation_rate >= self.correlation_threshold:
                self.status = 'confirmed'
                self.correlation_strength = correlation_rate
            else:
                self.status = 'rejected'
                self.correlation_strength = correlation_rate
        else:
            self.status = 'rejected'
            self.correlation_strength = len(patterns) / max(1, AlertLog.objects.filter(
                rule__in=self.primary_rules.all(),
                triggered_at__gte=timezone.now() - timedelta(days=30)
            ).count())
    
    def _analyze_ml_correlation(self):
        """Analyze correlation using machine learning"""
        # Placeholder for ML-based correlation analysis
        # In a real implementation, this would use trained ML models
        self._analyze_statistical_correlation()
    
    def predict_correlation(self, alert_log):
        """Predict if this alert will correlate with others"""
        if self.status != 'confirmed':
            return False
        
        if self.correlation_type == 'temporal':
            return self._predict_temporal_correlation(alert_log)
        elif self.correlation_type == 'pattern_based':
            return self._predict_pattern_correlation(alert_log)
        
        return False
    
    def _predict_temporal_correlation(self, alert_log):
        """Predict temporal correlation"""
        if not self.primary_rules.filter(id=alert_log.rule.id).exists():
            return False
        
        # Look for recent secondary alerts
        recent_secondary = AlertLog.objects.filter(
            rule__in=self.secondary_rules.all(),
            triggered_at__range=(
                alert_log.triggered_at - timedelta(minutes=self.time_window_minutes),
                alert_log.triggered_at + timedelta(minutes=self.time_window_minutes)
            )
        ).exists()
        
        return recent_secondary
    
    def _predict_pattern_correlation(self, alert_log):
        """Predict pattern-based correlation"""
        if not self.primary_rules.filter(id=alert_log.rule.id).exists():
            return False
        
        # Look for pattern matches
        similar_secondary = AlertLog.objects.filter(
            rule__in=self.secondary_rules.all(),
            message__icontains=alert_log.message[:50],
            triggered_at__range=(
                alert_log.triggered_at - timedelta(minutes=self.time_window_minutes),
                alert_log.triggered_at + timedelta(minutes=self.time_window_minutes)
            )
        ).exists()
        
        return similar_secondary
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['correlation_type', 'status']),
            models.Index(fields=['status', 'last_analyzed']),
        ]
        db_table_comment = "Correlation analysis between alerts"
        verbose_name = "Alert Correlation"
        verbose_name_plural = "Alert Correlations"


class AlertPrediction(models.Model):
    """Predictive analytics for alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    PREDICTION_TYPES = [
        ('volume', 'Volume Prediction'),
        ('severity', 'Severity Prediction'),
        ('timing', 'Timing Prediction'),
        ('correlation', 'Correlation Prediction'),
        ('anomaly', 'Anomaly Prediction'),
    ]
    
    MODEL_TYPES = [
        ('linear_regression', 'Linear Regression'),
        ('arima', 'ARIMA'),
        ('lstm', 'LSTM'),
        ('prophet', 'Prophet'),
        ('ensemble', 'Ensemble'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Prediction configuration
    prediction_type = models.CharField(max_length=20, choices=PREDICTION_TYPES)
    model_type = models.CharField(max_length=20, choices=MODEL_TYPES)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Target rules
    target_rules = models.ManyToManyField(
        AlertRule,
        related_name='%(app_label)s_%(class)s_target',
        blank=True
    )
    
    # Training parameters
    training_days = models.IntegerField(
        default=30,
        validators=[MinValueValidator(7), MaxValueValidator(365)]
    )
    prediction_horizon_hours = models.IntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(168)]
    )
    
    # Model parameters
    model_parameters = models.JSONField(default=dict)
    feature_columns = models.JSONField(default=list)
    
    # Performance metrics
    accuracy_score = models.FloatField(null=True, blank=True)
    precision_score = models.FloatField(null=True, blank=True)
    recall_score = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    mean_absolute_error = models.FloatField(null=True, blank=True)
    
    # Training status
    last_trained = models.DateTimeField(null=True, blank=True)
    training_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('training', 'Training'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertprediction_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Prediction: {self.name}"
    
    def train_model(self):
        """Train the prediction model"""
        self.training_status = 'training'
        self.save(update_fields=['training_status'])
        
        try:
            if self.prediction_type == 'volume':
                self._train_volume_model()
            elif self.prediction_type == 'timing':
                self._train_timing_model()
            elif self.prediction_type == 'severity':
                self._train_severity_model()
            
            self.training_status = 'completed'
            self.last_trained = timezone.now()
        except Exception as e:
            self.training_status = 'failed'
            # Log error
            print(f"Training failed: {e}")
        
        self.save(update_fields=['training_status', 'last_trained'])
    
    def _train_volume_model(self):
        """Train volume prediction model"""
        # Simplified volume prediction using moving average
        target_rule_ids = list(self.target_rules.values_list('id', flat=True))
        
        # Collect training data
        training_data = []
        for day in range(self.training_days):
            date = timezone.now().date() - timedelta(days=day)
            
            daily_count = AlertLog.objects.filter(
                rule_id__in=target_rule_ids,
                triggered_at__date=date
            ).count()
            
            training_data.append(daily_count)
        
        # Calculate moving average as simple prediction
        if len(training_data) >= 7:
            recent_avg = sum(training_data[-7:]) / 7
            self.accuracy_score = max(0, 1 - (abs(training_data[-1] - recent_avg) / max(1, training_data[-1])))
    
    def _train_timing_model(self):
        """Train timing prediction model"""
        # Simplified timing prediction
        target_rule_ids = list(self.target_rules.values_list('id', flat=True))
        
        # Collect alert timing data
        timing_data = []
        for day in range(self.training_days):
            date = timezone.now().date() - timedelta(days=day)
            
            alerts = AlertLog.objects.filter(
                rule_id__in=target_rule_ids,
                triggered_at__date=date
            ).order_by('triggered_at')
            
            if alerts.exists():
                first_alert = alerts.first()
                timing_data.append(first_alert.triggered_at.hour)
        
        if len(timing_data) >= 5:
            # Predict next likely hour based on historical pattern
            from collections import Counter
            hour_counts = Counter(timing_data)
            most_common_hour = hour_counts.most_common(1)[0][0]
            
            # Store prediction parameters
            self.model_parameters['predicted_hour'] = most_common_hour
            self.accuracy_score = hour_counts[most_common_hour] / len(timing_data)
    
    def _train_severity_model(self):
        """Train severity prediction model"""
        # Simplified severity prediction
        target_rule_ids = list(self.target_rules.values_list('id', flat=True))
        
        # Collect severity distribution
        severity_counts = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        total_alerts = 0
        
        for day in range(self.training_days):
            date = timezone.now().date() - timedelta(days=day)
            
            alerts = AlertLog.objects.filter(
                rule_id__in=target_rule_ids,
                triggered_at__date=date
            ).select_related('rule')
            
            for alert in alerts:
                severity_counts[alert.rule.severity] += 1
                total_alerts += 1
        
        if total_alerts > 0:
            # Store severity distribution
            severity_distribution = {
                k: v / total_alerts for k, v in severity_counts.items()
            }
            self.model_parameters['severity_distribution'] = severity_distribution
            
            # Calculate accuracy based on most common severity
            most_common_severity = max(severity_counts, key=severity_counts.get)
            self.accuracy_score = severity_counts[most_common_severity] / total_alerts
    
    def make_prediction(self, context=None):
        """Make prediction based on trained model"""
        if self.training_status != 'completed':
            return None
        
        if self.prediction_type == 'volume':
            return self._predict_volume()
        elif self.prediction_type == 'timing':
            return self._predict_timing()
        elif self.prediction_type == 'severity':
            return self._predict_severity()
        
        return None
    
    def _predict_volume(self):
        """Predict alert volume"""
        target_rule_ids = list(self.target_rules.values_list('id', flat=True))
        
        # Get recent data for prediction
        recent_data = []
        for day in range(7):
            date = timezone.now().date() - timedelta(days=day)
            
            daily_count = AlertLog.objects.filter(
                rule_id__in=target_rule_ids,
                triggered_at__date=date
            ).count()
            
            recent_data.append(daily_count)
        
        if recent_data:
            # Simple moving average prediction
            predicted_volume = sum(recent_data) / len(recent_data)
            
            return {
                'type': 'volume',
                'predicted_value': predicted_volume,
                'confidence': self.accuracy_score or 0.5,
                'horizon_hours': self.prediction_horizon_hours,
                'prediction_time': timezone.now()
            }
        
        return None
    
    def _predict_timing(self):
        """Predict alert timing"""
        predicted_hour = self.model_parameters.get('predicted_hour')
        if predicted_hour:
            next_occurrence = timezone.now().replace(
                hour=predicted_hour,
                minute=0,
                second=0,
                microsecond=0
            )
            
            if next_occurrence <= timezone.now():
                next_occurrence += timedelta(days=1)
            
            return {
                'type': 'timing',
                'predicted_time': next_occurrence,
                'confidence': self.accuracy_score or 0.5,
                'prediction_time': timezone.now()
            }
        
        return None
    
    def _predict_severity(self):
        """Predict alert severity"""
        severity_distribution = self.model_parameters.get('severity_distribution')
        if severity_distribution:
            # Find most likely severity
            most_likely_severity = max(severity_distribution, key=severity_distribution.get)
            
            return {
                'type': 'severity',
                'predicted_severity': most_likely_severity,
                'distribution': severity_distribution,
                'confidence': severity_distribution[most_likely_severity],
                'prediction_time': timezone.now()
            }
        
        return None
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['prediction_type', 'is_active']),
            models.Index(fields=['training_status', 'last_trained']),
        ]
        db_table_comment = "Predictive analytics for alerts"
        verbose_name = "Alert Prediction"
        verbose_name_plural = "Alert Predictions"


class AnomalyDetectionModel(models.Model):
    """Anomaly detection for alert patterns"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    DETECTION_METHODS = [
        ('statistical', 'Statistical'),
        ('ml_isolation_forest', 'Isolation Forest'),
        ('ml_one_class_svm', 'One-Class SVM'),
        ('time_series', 'Time Series'),
        ('threshold_based', 'Threshold-Based'),
    ]
    
    ANOMALY_TYPES = [
        ('spike', 'Spike'),
        ('drop', 'Drop'),
        ('pattern_change', 'Pattern Change'),
        ('new_pattern', 'New Pattern'),
        ('absence', 'Absence'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Detection configuration
    detection_method = models.CharField(max_length=30, choices=DETECTION_METHODS)
    target_anomaly_types = models.JSONField(
        default=list,
        help_text="Types of anomalies to detect"
    )
    
    # Target rules
    target_rules = models.ManyToManyField(
        AlertRule,
        related_name='%(app_label)s_%(class)s_target',
        blank=True
    )
    
    # Detection parameters
    sensitivity = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.1), MaxValueValidator(1.0)]
    )
    window_size_minutes = models.IntegerField(
        default=60,
        validators=[MinValueValidator(5), MaxValueValidator(1440)]
    )
    baseline_days = models.IntegerField(
        default=14,
        validators=[MinValueValidator(7), MaxValueValidator(90)]
    )
    
    # Thresholds
    anomaly_threshold = models.FloatField(default=2.0)
    min_alert_count = models.IntegerField(default=1)
    
    # Model parameters
    model_parameters = models.JSONField(default=dict)
    
    # Status
    is_active = models.BooleanField(default=True, db_index=True)
    last_trained = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_anomalydetectionmodel_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Anomaly Detection: {self.name}"
    
    def detect_anomalies(self):
        """Detect anomalies in recent alert data"""
        if not self.is_active:
            return []
        
        anomalies = []
        target_rule_ids = list(self.target_rules.values_list('id', flat=True))
        
        if self.detection_method == 'statistical':
            anomalies = self._detect_statistical_anomalies(target_rule_ids)
        elif self.detection_method == 'threshold_based':
            anomalies = self._detect_threshold_anomalies(target_rule_ids)
        elif self.detection_method == 'time_series':
            anomalies = self._detect_time_series_anomalies(target_rule_ids)
        
        return anomalies
    
    def _detect_statistical_anomalies(self, target_rule_ids):
        """Detect statistical anomalies"""
        anomalies = []
        
        # Calculate baseline statistics
        baseline_end = timezone.now() - timedelta(minutes=self.window_size_minutes)
        baseline_start = baseline_end - timedelta(days=self.baseline_days)
        
        baseline_data = AlertLog.objects.filter(
            rule_id__in=target_rule_ids,
            triggered_at__range=(baseline_start, baseline_end)
        ).aggregate(
            avg_count=models.Avg('trigger_value'),
            std_dev=models.StdDev('trigger_value'),
            min_count=models.Min('trigger_value'),
            max_count=models.Max('trigger_value')
        )
        
        # Check recent data
        recent_start = timezone.now() - timedelta(minutes=self.window_size_minutes)
        recent_alerts = AlertLog.objects.filter(
            rule_id__in=target_rule_ids,
            triggered_at__gte=recent_start
        )
        
        for alert in recent_alerts:
            # Calculate Z-score
            if baseline_data['std_dev'] and baseline_data['std_dev'] > 0:
                z_score = abs(alert.trigger_value - baseline_data['avg_count']) / baseline_data['std_dev']
                
                if z_score > self.anomaly_threshold:
                    anomaly_type = self._classify_anomaly_type(alert.trigger_value, baseline_data)
                    
                    anomalies.append({
                        'alert': alert,
                        'type': anomaly_type,
                        'score': z_score,
                        'baseline_avg': baseline_data['avg_count'],
                        'detection_time': timezone.now()
                    })
        
        return anomalies
    
    def _detect_threshold_anomalies(self, target_rule_ids):
        """Detect threshold-based anomalies"""
        anomalies = []
        
        # Get recent alert counts
        recent_start = timezone.now() - timedelta(minutes=self.window_size_minutes)
        recent_count = AlertLog.objects.filter(
            rule_id__in=target_rule_ids,
            triggered_at__gte=recent_start
        ).count()
        
        # Get historical baseline
        baseline_end = timezone.now() - timedelta(minutes=self.window_size_minutes)
        baseline_start = baseline_end - timedelta(days=self.baseline_days)
        
        historical_counts = []
        for day in range(self.baseline_days):
            day_start = baseline_start + timedelta(days=day)
            day_end = day_start + timedelta(minutes=self.window_size_minutes)
            
            day_count = AlertLog.objects.filter(
                rule_id__in=target_rule_ids,
                triggered_at__range=(day_start, day_end)
            ).count()
            
            historical_counts.append(day_count)
        
        if historical_counts:
            # Calculate statistics
            avg_count = sum(historical_counts) / len(historical_counts)
            max_count = max(historical_counts)
            
            # Detect anomalies
            if recent_count > max_count * (1 + self.sensitivity):
                anomalies.append({
                    'type': 'spike',
                    'value': recent_count,
                    'baseline_avg': avg_count,
                    'baseline_max': max_count,
                    'score': (recent_count - max_count) / max_count if max_count > 0 else 0,
                    'detection_time': timezone.now()
                })
            elif recent_count < avg_count * (1 - self.sensitivity) and recent_count < self.min_alert_count:
                anomalies.append({
                    'type': 'drop',
                    'value': recent_count,
                    'baseline_avg': avg_count,
                    'score': (avg_count - recent_count) / avg_count if avg_count > 0 else 0,
                    'detection_time': timezone.now()
                })
        
        return anomalies
    
    def _detect_time_series_anomalies(self, target_rule_ids):
        """Detect time series anomalies"""
        # Simplified time series anomaly detection
        anomalies = []
        
        # Get time series data
        time_series_data = []
        for hour in range(24):
            hour_start = timezone.now().replace(minute=0, second=0, microsecond=0) - timedelta(hours=hour)
            hour_end = hour_start + timedelta(hours=1)
            
            hour_count = AlertLog.objects.filter(
                rule_id__in=target_rule_ids,
                triggered_at__range=(hour_start, hour_end)
            ).count()
            
            time_series_data.append({
                'time': hour_start,
                'value': hour_count
            })
        
        # Simple anomaly detection based on deviation from pattern
        if len(time_series_data) >= 24:
            # Calculate hourly averages from previous days
            hourly_patterns = {}
            for hour in range(24):
                hour_values = []
                for day in range(7):  # Last 7 days
                    check_time = timezone.now() - timedelta(days=day, hours=hour)
                    hour_start = check_time.replace(minute=0, second=0, microsecond=0)
                    hour_end = hour_start + timedelta(hours=1)
                    
                    hour_count = AlertLog.objects.filter(
                        rule_id__in=target_rule_ids,
                        triggered_at__range=(hour_start, hour_end)
                    ).count()
                    
                    hour_values.append(hour_count)
                
                if hour_values:
                    hourly_patterns[hour] = {
                        'avg': sum(hour_values) / len(hour_values),
                        'std': self._calculate_std(hour_values)
                    }
            
            # Check current hour against pattern
            current_hour = timezone.now().hour
            if current_hour in hourly_patterns:
                pattern = hourly_patterns[current_hour]
                current_data = time_series_data[-1]  # Most recent hour
                
                if pattern['std'] > 0:
                    z_score = abs(current_data['value'] - pattern['avg']) / pattern['std']
                    
                    if z_score > self.anomaly_threshold:
                        anomaly_type = 'spike' if current_data['value'] > pattern['avg'] else 'drop'
                        
                        anomalies.append({
                            'type': anomaly_type,
                            'value': current_data['value'],
                            'baseline_avg': pattern['avg'],
                            'score': z_score,
                            'detection_time': timezone.now()
                        })
        
        return anomalies
    
    def _calculate_std(self, values):
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
    
    def _classify_anomaly_type(self, value, baseline):
        """Classify anomaly type based on value and baseline"""
        if value > baseline['max_count']:
            return 'spike'
        elif value < baseline['min_count']:
            return 'drop'
        else:
            return 'pattern_change'
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['detection_method', 'is_active']),
            models.Index(fields=['last_trained']),
        ]
        db_table_comment = "Anomaly detection for alert patterns"
        verbose_name = "Anomaly Detection Model"
        verbose_name_plural = "Anomaly Detection Models"


class AlertNoise(models.Model):
    """Management of alert noise and false positives"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    NOISE_TYPES = [
        ('repeated', 'Repeated Alerts'),
        ('low_priority', 'Low Priority'),
        ('known_issue', 'Known Issue'),
        ('maintenance', 'Maintenance Related'),
        ('test_environment', 'Test Environment'),
        ('configuration_error', 'Configuration Error'),
    ]
    
    SUPPRESSION_ACTIONS = [
        ('suppress', 'Suppress'),
        ('group', 'Group'),
        ('delay', 'Delay'),
        ('escalate', 'Escalate'),
        ('filter', 'Filter'),
    ]
    
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    
    # Noise configuration
    noise_type = models.CharField(max_length=20, choices=NOISE_TYPES)
    action = models.CharField(max_length=20, choices=SUPPRESSION_ACTIONS)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Target rules
    target_rules = models.ManyToManyField(
        AlertRule,
        related_name='%(app_label)s_%(class)s_target',
        blank=True
    )
    
    # Filtering criteria
    message_patterns = models.JSONField(
        default=list,
        help_text="Regex patterns to match alert messages"
    )
    severity_filter = models.JSONField(
        default=list,
        help_text="Severities to filter"
    )
    source_filter = models.JSONField(
        default=list,
        help_text="Sources to filter"
    )
    
    # Suppression settings
    suppression_duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    max_suppressions_per_hour = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1)]
    )
    
    # Grouping settings
    group_window_minutes = models.IntegerField(
        default=15,
        validators=[MinValueValidator(1), MaxValueValidator(1440)]
    )
    max_group_size = models.IntegerField(
        default=50,
        validators=[MinValueValidator(2)]
    )
    
    # Delay settings
    delay_minutes = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(60)]
    )
    
    # Statistics
    total_processed = models.IntegerField(default=0)
    total_suppressed = models.IntegerField(default=0)
    total_grouped = models.IntegerField(default=0)
    total_delayed = models.IntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_alertnoise_created_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Noise Filter: {self.name}"
    
    def process_alert(self, alert_log):
        """Process alert through noise filter"""
        if not self.is_active:
            return None
        
        self.total_processed += 1
        
        # Check if alert matches filter criteria
        if not self._matches_criteria(alert_log):
            self.save(update_fields=['total_processed'])
            return None
        
        # Apply action
        result = None
        if self.action == 'suppress':
            result = self._suppress_alert(alert_log)
        elif self.action == 'group':
            result = self._group_alert(alert_log)
        elif self.action == 'delay':
            result = self._delay_alert(alert_log)
        elif self.action == 'filter':
            result = self._filter_alert(alert_log)
        
        self.save(update_fields=['total_processed'])
        return result
    
    def _matches_criteria(self, alert_log):
        """Check if alert matches filter criteria"""
        # Check rule match
        if self.target_rules.exists() and not self.target_rules.filter(id=alert_log.rule.id).exists():
            return False
        
        # Check severity filter
        if self.severity_filter and alert_log.rule.severity not in self.severity_filter:
            return False
        
        # Check message patterns
        if self.message_patterns:
            import re
            for pattern in self.message_patterns:
                try:
                    if re.search(pattern, alert_log.message, re.IGNORECASE):
                        return True
                except re.error:
                    continue
            return False
        
        return True
    
    def _suppress_alert(self, alert_log):
        """Suppress the alert"""
        self.total_suppressed += 1
        
        return {
            'action': 'suppress',
            'alert': alert_log,
            'reason': f'Matched noise filter: {self.name}',
            'duration': self.suppression_duration_minutes
        }
    
    def _group_alert(self, alert_log):
        """Group the alert with similar ones"""
        self.total_grouped += 1
        
        # Find similar recent alerts
        group_start = timezone.now() - timedelta(minutes=self.group_window_minutes)
        similar_alerts = AlertLog.objects.filter(
            rule=alert_log.rule,
            message__icontains=alert_log.message[:50],
            triggered_at__gte=group_start
        ).exclude(id=alert_log.id)
        
        return {
            'action': 'group',
            'alert': alert_log,
            'similar_alerts': list(similar_alerts),
            'group_size': similar_alerts.count() + 1
        }
    
    def _delay_alert(self, alert_log):
        """Delay the alert"""
        self.total_delayed += 1
        
        return {
            'action': 'delay',
            'alert': alert_log,
            'delay_minutes': self.delay_minutes,
            'send_at': alert_log.triggered_at + timedelta(minutes=self.delay_minutes)
        }
    
    def _filter_alert(self, alert_log):
        """Filter out the alert"""
        return {
            'action': 'filter',
            'alert': alert_log,
            'reason': f'Filtered by noise filter: {self.name}'
        }
    
    def get_effectiveness_score(self):
        """Calculate effectiveness score"""
        if self.total_processed == 0:
            return 0
        
        # Higher score for filters that process more alerts
        processing_rate = self.total_processed / max(1, AlertLog.objects.count())
        
        # Consider action effectiveness
        action_scores = {
            'suppress': 0.8,
            'group': 0.9,
            'delay': 0.6,
            'filter': 0.7
        }
        
        action_score = action_scores.get(self.action, 0.5)
        
        return (processing_rate * 0.3 + action_score * 0.7) * 100
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['noise_type', 'is_active']),
            models.Index(fields=['action', 'is_active']),
        ]
        db_table_comment = "Management of alert noise and false positives"
        verbose_name = "Alert Noise"
        verbose_name_plural = "Alert Noise"


class RootCauseAnalysis(models.Model):
    """Root cause analysis for incidents and alerts"""
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    ANALYSIS_METHODS = [
        ('5_whys', '5 Whys'),
        ('fishbone', 'Fishbone Diagram'),
        ('fault_tree', 'Fault Tree Analysis'),
        ('pareto', 'Pareto Analysis'),
        ('statistical', 'Statistical Analysis'),
        ('ml_based', 'ML-Based Analysis'),
    ]
    
    CONFIDENCE_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('very_high', 'Very High'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    # Analysis configuration
    analysis_method = models.CharField(max_length=20, choices=ANALYSIS_METHODS)
    confidence_level = models.CharField(max_length=20, choices=CONFIDENCE_LEVELS, default='medium')
    
    # Related alerts and incidents
    related_alerts = models.ManyToManyField(
        AlertLog,
        related_name='%(app_label)s_%(class)s_alerts',
        blank=True
    )
    related_incidents = models.JSONField(default=list)
    
    # Analysis results
    root_causes = models.JSONField(default=list)
    contributing_factors = models.JSONField(default=list)
    evidence = models.JSONField(default=list)
    
    # Timeline analysis
    timeline_events = models.JSONField(default=list)
    causal_chain = models.JSONField(default=list)
    
    # Impact assessment
    impact_assessment = models.TextField(blank=True)
    affected_systems = models.JSONField(default=list)
    business_impact = models.TextField(blank=True)
    
    # Recommendations
    immediate_actions = models.JSONField(default=list)
    preventive_actions = models.JSONField(default=list)
    long_term_improvements = models.JSONField(default=list)
    
    # Verification
    verification_method = models.TextField(blank=True)
    verification_results = models.JSONField(default=list)
    
    # Status and metadata
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('verified', 'Verified'),
            ('archived', 'Archived'),
        ],
        default='draft'
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='alerts_rootcauseanalysis_created_by'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts_rootcauseanalysis_reviewed_by'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"RCA: {self.title}"
    
    def perform_analysis(self):
        """Perform root cause analysis"""
        if self.analysis_method == '5_whys':
            self._perform_5_whys_analysis()
        elif self.analysis_method == 'fishbone':
            self._perform_fishbone_analysis()
        elif self.analysis_method == 'statistical':
            self._perform_statistical_analysis()
        
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at'])
    
    def _perform_5_whys_analysis(self):
        """Perform 5 Whys analysis"""
        # Simplified 5 Whys implementation
        if not self.related_alerts.exists():
            return
        
        # Get the most recent alert as starting point
        latest_alert = self.related_alerts.latest('triggered_at')
        
        # Generate "why" questions and answers
        whys = []
        current_issue = latest_alert.message
        
        for i in range(5):
            why_question = f"Why did {current_issue} occur?"
            # In a real implementation, this would involve more sophisticated analysis
            why_answer = f"Answer to why {i+1}: Based on analysis of alert patterns"
            
            whys.append({
                'question': why_question,
                'answer': why_answer,
                'evidence': [latest_alert.id]
            })
            
            current_issue = why_answer
        
        # Extract root cause from the last "why"
        if whys:
            self.root_causes = [{
                'cause': whys[-1]['answer'],
                'confidence': 0.7,
                'evidence': [w['evidence'] for w in whys]
            }]
    
    def _perform_fishbone_analysis(self):
        """Perform fishbone diagram analysis"""
        # Simplified fishbone analysis
        categories = {
            'People': ['Insufficient training', 'Human error'],
            'Process': ['Inadequate procedures', 'Process gaps'],
            'Equipment': ['Hardware failure', 'Configuration issues'],
            'Materials': ['Resource constraints', 'Data quality'],
            'Environment': ['External factors', 'System load'],
            'Management': ['Policy issues', 'Resource allocation']
        }
        
        potential_causes = []
        for category, causes in categories.items():
            for cause in causes:
                potential_causes.append({
                    'category': category,
                    'cause': cause,
                    'likelihood': 0.5  # Would be calculated based on evidence
                })
        
        self.contributing_factors = potential_causes
    
    def _perform_statistical_analysis(self):
        """Perform statistical analysis"""
        # Simplified statistical analysis
        if not self.related_alerts.exists():
            return
        
        alerts = list(self.related_alerts.all())
        
        # Analyze patterns
        severity_distribution = {}
        time_patterns = []
        
        for alert in alerts:
            # Severity analysis
            severity = alert.rule.severity
            severity_distribution[severity] = severity_distribution.get(severity, 0) + 1
            
            # Time pattern analysis
            time_patterns.append({
                'hour': alert.triggered_at.hour,
                'day': alert.triggered_at.weekday()
            })
        
        # Generate insights
        insights = []
        
        # Most common severity
        if severity_distribution:
            most_common_severity = max(severity_distribution, key=severity_distribution.get)
            insights.append(f"Most alerts are {most_common_severity} severity")
        
        # Time patterns
        if time_patterns:
            hours = [p['hour'] for p in time_patterns]
            peak_hour = max(set(hours), key=hours.count)
            insights.append(f"Peak alert time: {peak_hour}:00")
        
        self.evidence = [{'type': 'statistical', 'insight': insight} for insight in insights]
    
    def generate_recommendations(self):
        """Generate recommendations based on analysis"""
        recommendations = []
        
        if self.root_causes:
            for cause in self.root_causes:
                cause_text = cause.get('cause', '')
                
                # Generate immediate actions
                if 'configuration' in cause_text.lower():
                    recommendations.append({
                        'type': 'immediate',
                        'action': 'Review and fix configuration issues',
                        'priority': 'high'
                    })
                
                # Generate preventive actions
                if 'human error' in cause_text.lower():
                    recommendations.append({
                        'type': 'preventive',
                        'action': 'Implement additional training and documentation',
                        'priority': 'medium'
                    })
        
        self.immediate_actions = [r for r in recommendations if r['type'] == 'immediate']
        self.preventive_actions = [r for r in recommendations if r['type'] == 'preventive']
    
    def get_analysis_score(self):
        """Calculate analysis completeness score"""
        required_elements = [
            'root_causes', 'contributing_factors', 'evidence',
            'immediate_actions', 'preventive_actions'
        ]
        
        completed_elements = 0
        for element in required_elements:
            if getattr(self, element, None):
                completed_elements += 1
        
        return (completed_elements / len(required_elements)) * 100
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['analysis_method', 'status']),
            models.Index(fields=['completed_at']),
        ]
        db_table_comment = "Root cause analysis for incidents and alerts"
        verbose_name = "Root Cause Analysis"
        verbose_name_plural = "Root Cause Analyses"
