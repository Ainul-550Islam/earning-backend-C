from django.conf import settings
"""
Fraud Detection Database Model

This module contains Fraud Detection model and related models
for managing fraud detection and prevention.
"""

from typing import Optional, List, Dict, Any, Union
from decimal import Decimal
from datetime import datetime, date
from uuid import UUID

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, F
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.gis.geos import Point
from django.contrib.gis.db import models as gis_models

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class FraudDetectionRule(AdvertiserPortalBaseModel, AuditModel):
    """
    Main fraud detection rule model for managing fraud detection rules.
    
    This model stores rule configurations, thresholds,
    and detection logic for identifying fraudulent activity.
    """
    
    # Basic Information
    name = models.CharField(
        max_length=255,
        help_text="Rule name"
    )
    description = models.TextField(
        blank=True,
        help_text="Rule description"
    )
    
    # Rule Configuration
    rule_type = models.CharField(
        max_length=50,
        choices=[
            ('frequency', 'Frequency Analysis'),
            ('velocity', 'Velocity Analysis'),
            ('geographic', 'Geographic Analysis'),
            ('device', 'Device Analysis'),
            ('behavioral', 'Behavioral Analysis'),
            ('ip', 'IP Analysis'),
            ('domain', 'Domain Analysis'),
            ('conversion', 'Conversion Analysis'),
            ('custom', 'Custom Rule')
        ],
        db_index=True,
        help_text="Type of fraud detection rule"
    )
    
    # Target Configuration
    target_type = models.CharField(
        max_length=50,
        choices=[
            ('impression', 'Impressions'),
            ('click', 'Clicks'),
            ('conversion', 'Conversions'),
            ('user', 'Users'),
            ('campaign', 'Campaigns'),
            ('advertiser', 'Advertisers')
        ],
        help_text="Target type for rule"
    )
    
    # Threshold Configuration
    threshold_type = models.CharField(
        max_length=50,
        choices=[
            ('absolute', 'Absolute Value'),
            ('percentage', 'Percentage'),
            ('ratio', 'Ratio'),
            ('standard_deviation', 'Standard Deviation'),
            ('z_score', 'Z-Score'),
            ('anomaly_score', 'Anomaly Score')
        ],
        help_text="Type of threshold"
    )
    threshold_value = models.DecimalField(
        max_digits=15,
        decimal_places=6,
        help_text="Threshold value"
    )
    threshold_operator = models.CharField(
        max_length=20,
        choices=[
            ('greater_than', 'Greater Than'),
            ('less_than', 'Less Than'),
            ('equals', 'Equals'),
            ('not_equals', 'Not Equals'),
            ('between', 'Between'),
            ('outside', 'Outside')
        ],
        default='greater_than',
        help_text="Threshold comparison operator"
    )
    
    # Time Window Configuration
    time_window = models.IntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Time window in minutes"
    )
    time_unit = models.CharField(
        max_length=20,
        choices=[
            ('minutes', 'Minutes'),
            ('hours', 'Hours'),
            ('days', 'Days'),
            ('weeks', 'Weeks')
        ],
        default='minutes',
        help_text="Time unit for window"
    )
    
    # Rule Logic
    rule_conditions = models.JSONField(
        default=dict,
        help_text="Rule conditions and logic"
    )
    rule_expression = models.TextField(
        blank=True,
        help_text="Custom rule expression"
    )
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rule parameters"
    )
    
    # Action Configuration
    action_type = models.CharField(
        max_length=50,
        choices=[
            ('flag', 'Flag Only'),
            ('block', 'Block'),
            ('quarantine', 'Quarantine'),
            ('alert', 'Send Alert'),
            ('reject', 'Reject'),
            ('custom', 'Custom Action')
        ],
        default='flag',
        help_text="Action to take when rule is triggered"
    )
    action_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Action parameters"
    )
    
    # Severity and Priority
    severity_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        default='medium',
        help_text="Severity level"
    )
    priority = models.IntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Rule priority (1-10)"
    )
    
    # Status and Configuration
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether rule is active"
    )
    is_system = models.BooleanField(
        default=False,
        help_text="Whether rule is system-defined"
    )
    is_muted = models.BooleanField(
        default=False,
        help_text="Whether rule is muted"
    )
    mute_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Mute rule until this time"
    )
    
    # Performance Metrics
    trigger_count = models.IntegerField(
        default=0,
        help_text="Number of times rule has been triggered"
    )
    false_positive_count = models.IntegerField(
        default=0,
        help_text="Number of false positives"
    )
    true_positive_count = models.IntegerField(
        default=0,
        help_text="Number of true positives"
    )
    accuracy_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        help_text="Rule accuracy rate (0-100)"
    )
    
    # Testing and Validation
    test_results = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rule test results"
    )
    validation_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rule validation data"
    )
    
    class Meta:
        db_table = 'fraud_detection_rules'
        verbose_name = 'Fraud Detection Rule'
        verbose_name_plural = 'Fraud Detection Rules'
        indexes = [
            models.Index(fields=['rule_type'], name='idx_rule_type_240'),
            models.Index(fields=['target_type'], name='idx_target_type_241'),
            models.Index(fields=['is_active'], name='idx_is_active_242'),
            models.Index(fields=['severity_level'], name='idx_severity_level_243'),
            models.Index(fields=['priority'], name='idx_priority_244'),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def clean(self) -> None:
        """Validate model data."""
        super().clean()
        
        # Validate threshold value
        if self.threshold_value is None:
            raise ValidationError("Threshold value is required")
        
        # Validate time window
        if self.time_window <= 0:
            raise ValidationError("Time window must be greater than 0")
        
        # Validate rule expression for custom rules
        if self.rule_type == 'custom' and not self.rule_expression:
            raise ValidationError("Rule expression is required for custom rules")
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Update accuracy rate
        total_triggers = self.false_positive_count + self.true_positive_count
        if total_triggers > 0:
            self.accuracy_rate = Decimal(str((self.true_positive_count / total_triggers) * 100))
        
        super().save(*args, **kwargs)
    
    def is_muted(self) -> bool:
        """Check if rule is currently muted."""
        if not self.is_muted:
            return False
        
        if self.mute_until and timezone.now() < self.mute_until:
            return True
        
        return False
    
    def evaluate(self, data: Dict[str, Any]) -> bool:
        """Evaluate rule against provided data."""
        if not self.is_active or self.is_muted():
            return False
        
        try:
            if self.rule_type == 'frequency':
                return self._evaluate_frequency(data)
            elif self.rule_type == 'velocity':
                return self._evaluate_velocity(data)
            elif self.rule_type == 'geographic':
                return self._evaluate_geographic(data)
            elif self.rule_type == 'device':
                return self._evaluate_device(data)
            elif self.rule_type == 'behavioral':
                return self._evaluate_behavioral(data)
            elif self.rule_type == 'ip':
                return self._evaluate_ip(data)
            elif self.rule_type == 'domain':
                return self._evaluate_domain(data)
            elif self.rule_type == 'conversion':
                return self._evaluate_conversion(data)
            elif self.rule_type == 'custom':
                return self._evaluate_custom(data)
            
            return False
        except Exception as e:
            logger.error(f"Error evaluating fraud rule {self.name}: {str(e)}")
            return False
    
    def _evaluate_frequency(self, data: Dict[str, Any]) -> bool:
        """Evaluate frequency-based rule."""
        count = data.get('count', 0)
        return self._compare_threshold(count)
    
    def _evaluate_velocity(self, data: Dict[str, Any]) -> bool:
        """Evaluate velocity-based rule."""
        velocity = data.get('velocity', 0)
        return self._compare_threshold(velocity)
    
    def _evaluate_geographic(self, data: Dict[str, Any]) -> bool:
        """Evaluate geographic-based rule."""
        # Check for impossible geographic patterns
        countries = data.get('countries', [])
        if len(set(countries)) > 10:  # Too many countries in short time
            return self._compare_threshold(len(set(countries)))
        
        return False
    
    def _evaluate_device(self, data: Dict[str, Any]) -> bool:
        """Evaluate device-based rule."""
        # Check for suspicious device patterns
        devices = data.get('devices', [])
        if len(set(devices)) > 5:  # Too many devices
            return self._compare_threshold(len(set(devices)))
        
        return False
    
    def _evaluate_behavioral(self, data: Dict[str, Any]) -> bool:
        """Evaluate behavioral-based rule."""
        # Check for suspicious behavioral patterns
        click_pattern = data.get('click_pattern', {})
        if click_pattern.get('rapid_clicks', 0) > 10:
            return self._compare_threshold(click_pattern['rapid_clicks'])
        
        return False
    
    def _evaluate_ip(self, data: Dict[str, Any]) -> bool:
        """Evaluate IP-based rule."""
        # Check for suspicious IP patterns
        ip_count = data.get('unique_ips', 0)
        return self._compare_threshold(ip_count)
    
    def _evaluate_domain(self, data: Dict[str, Any]) -> bool:
        """Evaluate domain-based rule."""
        # Check for suspicious domains
        domains = data.get('domains', [])
        suspicious_count = sum(1 for domain in domains if self._is_suspicious_domain(domain))
        return self._compare_threshold(suspicious_count)
    
    def _evaluate_conversion(self, data: Dict[str, Any]) -> bool:
        """Evaluate conversion-based rule."""
        # Check for suspicious conversion patterns
        conversion_rate = data.get('conversion_rate', 0)
        return self._compare_threshold(conversion_rate)
    
    def _evaluate_custom(self, data: Dict[str, Any]) -> bool:
        """Evaluate custom rule."""
        # This would implement custom rule evaluation logic
        # For now, return False
        return False
    
    def _compare_threshold(self, value: Union[int, float]) -> bool:
        """Compare value against threshold."""
        try:
            val = float(value)
            threshold = float(self.threshold_value)
            
            if self.threshold_operator == 'greater_than':
                return val > threshold
            elif self.threshold_operator == 'less_than':
                return val < threshold
            elif self.threshold_operator == 'equals':
                return abs(val - threshold) < 0.001
            elif self.threshold_operator == 'not_equals':
                return abs(val - threshold) >= 0.001
            elif self.threshold_operator == 'between':
                # threshold_value would be a tuple [min, max]
                if isinstance(self.threshold_value, (list, tuple)) and len(self.threshold_value) == 2:
                    min_val, max_val = self.threshold_value
                    return min_val <= val <= max_val
            elif self.threshold_operator == 'outside':
                if isinstance(self.threshold_value, (list, tuple)) and len(self.threshold_value) == 2:
                    min_val, max_val = self.threshold_value
                    return val < min_val or val > max_val
            
            return False
        except (ValueError, TypeError):
            return False
    
    def _is_suspicious_domain(self, domain: str) -> bool:
        """Check if domain is suspicious."""
        suspicious_patterns = [
            'spam', 'bot', 'fake', 'temp', 'disposable',
            'proxy', 'vpn', 'tor', 'malware'
        ]
        
        domain_lower = domain.lower()
        return any(pattern in domain_lower for pattern in suspicious_patterns)
    
    def trigger(self, data: Dict[str, Any]) -> 'FraudDetectionAlert':
        """Trigger fraud detection alert."""
        # Increment trigger count
        self.trigger_count += 1
        self.save(update_fields=['trigger_count'])
        
        # Create alert
        alert = FraudDetectionAlert.objects.create(
            rule=self,
            severity_level=self.severity_level,
            target_type=self.target_type,
            target_id=data.get('target_id'),
            alert_data=data,
            action_type=self.action_type,
            action_parameters=self.action_parameters
        )
        
        return alert


class FraudDetectionAlert(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing fraud detection alerts.
    """
    
    # Basic Information
    rule = models.ForeignKey(
        FraudDetectionRule,
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text="Associated rule"
    )
    alert_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique alert identifier"
    )
    
    # Alert Details
    severity_level = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('high', 'High'),
            ('critical', 'Critical')
        ],
        db_index=True,
        help_text="Alert severity level"
    )
    target_type = models.CharField(
        max_length=50,
        choices=[
            ('impression', 'Impression'),
            ('click', 'Click'),
            ('conversion', 'Conversion'),
            ('user', 'User'),
            ('campaign', 'Campaign'),
            ('advertiser', 'Advertiser')
        ],
        help_text="Target type"
    )
    target_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Target ID"
    )
    
    # Alert Data
    alert_data = models.JSONField(
        help_text="Alert data and context"
    )
    risk_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Risk score (0-100)"
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Confidence score (0-100)"
    )
    
    # Action Information
    action_type = models.CharField(
        max_length=50,
        choices=[
            ('flag', 'Flag Only'),
            ('block', 'Block'),
            ('quarantine', 'Quarantine'),
            ('alert', 'Send Alert'),
            ('reject', 'Reject'),
            ('custom', 'Custom Action')
        ],
        help_text="Action taken"
    )
    action_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Action parameters"
    )
    action_taken = models.BooleanField(
        default=False,
        help_text="Whether action has been taken"
    )
    action_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When action was taken"
    )
    
    # Status Information
    status = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New'),
            ('investigating', 'Investigating'),
            ('confirmed', 'Confirmed'),
            ('false_positive', 'False Positive'),
            ('resolved', 'Resolved'),
            ('dismissed', 'Dismissed')
        ],
        default='new',
        db_index=True,
        help_text="Alert status"
    )
    
    # Review Information
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_fraud_alerts'
    )
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Review timestamp"
    )
    review_notes = models.TextField(
        blank=True,
        help_text="Review notes"
    )
    
    # Resolution Information
    resolution_type = models.CharField(
        max_length=50,
        choices=[
            ('none', 'None'),
            ('blocked', 'Blocked'),
            ('flagged', 'Flagged'),
            ('whitelisted', 'Whitelisted'),
            ('monitored', 'Monitored')
        ],
        blank=True,
        help_text="Resolution type"
    )
    resolution_notes = models.TextField(
        blank=True,
        help_text="Resolution notes"
    )
    
    # External References
    external_alert_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="External alert ID"
    )
    integration_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Third-party integration data"
    )
    
    class Meta:
        db_table = 'fraud_detection_alerts'
        verbose_name = 'Fraud Detection Alert'
        verbose_name_plural = 'Fraud Detection Alerts'
        indexes = [
            models.Index(fields=['rule', 'status'], name='idx_rule_status_245'),
            models.Index(fields=['severity_level'], name='idx_severity_level_246'),
            models.Index(fields=['target_type', 'target_id'], name='idx_target_type_target_id_247'),
            models.Index(fields=['status'], name='idx_status_248'),
            models.Index(fields=['created_at'], name='idx_created_at_249'),
        ]
    
    def __str__(self) -> str:
        return f"{self.alert_id} ({self.rule.name})"
    
    def save(self, *args, **kwargs) -> None:
        """Override save to handle additional logic."""
        # Generate alert ID if not set
        if not self.alert_id:
            self.alert_id = self.generate_alert_id()
        
        # Set action timestamp if action taken and not set
        if self.action_taken and not self.action_timestamp:
            self.action_timestamp = timezone.now()
        
        super().save(*args, **kwargs)
    
    def generate_alert_id(self) -> str:
        """Generate unique alert identifier."""
        import uuid
        return f"alert_{uuid.uuid4().hex}"
    
    def take_action(self) -> bool:
        """Take the configured action."""
        if self.action_taken:
            return True
        
        try:
            if self.action_type == 'flag':
                self._flag_target()
            elif self.action_type == 'block':
                self._block_target()
            elif self.action_type == 'quarantine':
                self._quarantine_target()
            elif self.action_type == 'reject':
                self._reject_target()
            elif self.action_type == 'custom':
                self._custom_action()
            
            self.action_taken = True
            self.action_timestamp = timezone.now()
            self.save(update_fields=['action_taken', 'action_timestamp'])
            
            return True
        except Exception as e:
            logger.error(f"Error taking action for alert {self.alert_id}: {str(e)}")
            return False
    
    def _flag_target(self) -> None:
        """Flag the target as suspicious."""
        if self.target_type == 'impression':
            from .impression_model import Impression
            Impression.objects.filter(id=self.target_id).update(is_suspicious=True)
        elif self.target_type == 'click':
            from .click_model import Click
            Click.objects.filter(id=self.target_id).update(is_suspicious=True)
        elif self.target_type == 'conversion':
            from .conversion_model import Conversion
            Conversion.objects.filter(id=self.target_id).update(is_valid=False)
    
    def _block_target(self) -> None:
        """Block the target."""
        # Implementation would depend on target type
        pass
    
    def _quarantine_target(self) -> None:
        """Quarantine the target."""
        # Implementation would depend on target type
        pass
    
    def _reject_target(self) -> None:
        """Reject the target."""
        if self.target_type == 'conversion':
            from .conversion_model import Conversion
            Conversion.objects.filter(id=self.target_id).update(
                status='rejected',
                is_valid=False
            )
    
    def _custom_action(self) -> None:
        """Execute custom action."""
        # Implementation would depend on custom action parameters
        pass
    
    def mark_as_false_positive(self, reviewer: 'User', notes: str = '') -> None:
        """Mark alert as false positive."""
        self.status = 'false_positive'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        
        # Update rule statistics
        self.rule.false_positive_count += 1
        self.rule.save(update_fields=['false_positive_count'])
        
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])
    
    def mark_as_confirmed(self, reviewer: 'User', notes: str = '') -> None:
        """Mark alert as confirmed fraud."""
        self.status = 'confirmed'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = notes
        
        # Update rule statistics
        self.rule.true_positive_count += 1
        self.rule.save(update_fields=['true_positive_count'])
        
        self.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary."""
        return {
            'basic_info': {
                'alert_id': self.alert_id,
                'rule_name': self.rule.name,
                'severity_level': self.severity_level,
                'target_type': self.target_type,
                'target_id': self.target_id
            },
            'scores': {
                'risk_score': float(self.risk_score),
                'confidence_score': float(self.confidence_score)
            },
            'action': {
                'action_type': self.action_type,
                'action_taken': self.action_taken,
                'action_timestamp': self.action_timestamp.isoformat() if self.action_timestamp else None
            },
            'status': {
                'status': self.status,
                'reviewed_by': self.reviewed_by.username if self.reviewed_by else None,
                'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
                'review_notes': self.review_notes
            },
            'resolution': {
                'resolution_type': self.resolution_type,
                'resolution_notes': self.resolution_notes
            }
        }


class FraudDetectionLog(AdvertiserPortalBaseModel):
    """
    Model for logging fraud detection events.
    """
    
    # Basic Information
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('rule_triggered', 'Rule Triggered'),
            ('alert_created', 'Alert Created'),
            ('action_taken', 'Action Taken'),
            ('alert_reviewed', 'Alert Reviewed'),
            ('alert_resolved', 'Alert Resolved'),
            ('rule_updated', 'Rule Updated'),
            ('system_event', 'System Event')
        ],
        db_index=True,
        help_text="Type of event"
    )
    
    # Event Details
    rule = models.ForeignKey(
        FraudDetectionRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        help_text="Associated rule"
    )
    alert = models.ForeignKey(
        FraudDetectionAlert,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        help_text="Associated alert"
    )
    
    # Event Data
    event_data = models.JSONField(
        default=dict,
        help_text="Event data and context"
    )
    message = models.TextField(
        help_text="Event message"
    )
    details = models.TextField(
        blank=True,
        help_text="Additional event details"
    )
    
    # User Information
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fraud_detection_logs'
    )
    
    # System Information
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address if applicable"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent if applicable"
    )
    
    class Meta:
        db_table = 'ap_fraud_detection_logs'
        verbose_name = 'Fraud Detection Log'
        verbose_name_plural = 'Fraud Detection Logs'
        indexes = [
            models.Index(fields=['event_type'], name='idx_event_type_250'),
            models.Index(fields=['rule'], name='idx_rule_251'),
            models.Index(fields=['alert'], name='idx_alert_252'),
            models.Index(fields=['created_at'], name='idx_created_at_253'),
        ]
    
    def __str__(self) -> str:
        return f"{self.event_type} - {self.created_at}"


class FraudDetectionReport(AdvertiserPortalBaseModel, AuditModel):
    """
    Model for managing fraud detection reports.
    """
    
    # Basic Information
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        on_delete=models.CASCADE,
        related_name='fraud_reports',
        help_text="Associated advertiser"
    )
    report_name = models.CharField(
        max_length=255,
        help_text="Report name"
    )
    report_type = models.CharField(
        max_length=50,
        choices=[
            ('summary', 'Summary Report'),
            ('detailed', 'Detailed Report'),
            ('trend', 'Trend Analysis'),
            ('rule_performance', 'Rule Performance'),
            ('case_study', 'Case Study')
        ],
        default='summary',
        help_text="Type of report"
    )
    
    # Date Range
    start_date = models.DateField(
        help_text="Report start date"
    )
    end_date = models.DateField(
        help_text="Report end date"
    )
    
    # Report Data
    summary_data = models.JSONField(
        default=dict,
        help_text="Report summary data"
    )
    detailed_data = models.JSONField(
        default=dict,
        help_text="Report detailed data"
    )
    metrics = models.JSONField(
        default=dict,
        help_text="Report metrics"
    )
    
    # File Information
    report_file = models.FileField(
        upload_to='fraud_reports/%Y/%m/',
        null=True,
        blank=True,
        help_text="Generated report file"
    )
    file_format = models.CharField(
        max_length=20,
        choices=[
            ('pdf', 'PDF'),
            ('excel', 'Excel'),
            ('csv', 'CSV'),
            ('json', 'JSON')
        ],
        default='pdf',
        help_text="Report file format"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('generating', 'Generating'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending',
        help_text="Report generation status"
    )
    
    class Meta:
        db_table = 'fraud_detection_reports'
        verbose_name = 'Fraud Detection Report'
        verbose_name_plural = 'Fraud Detection Reports'
        indexes = [
            models.Index(fields=['advertiser', 'report_type'], name='idx_advertiser_report_type_254'),
            models.Index(fields=['start_date', 'end_date'], name='idx_start_date_end_date_255'),
            models.Index(fields=['status'], name='idx_status_256'),
        ]
    
    def __str__(self) -> str:
        return f"{self.report_name} ({self.advertiser.company_name})"
    
    def generate_report(self) -> bool:
        """Generate the fraud detection report."""
        try:
            self.status = 'generating'
            self.save(update_fields=['status'])
            
            # Generate report data based on type
            if self.report_type == 'summary':
                self._generate_summary_report()
            elif self.report_type == 'detailed':
                self._generate_detailed_report()
            elif self.report_type == 'trend':
                self._generate_trend_report()
            elif self.report_type == 'rule_performance':
                self._generate_rule_performance_report()
            elif self.report_type == 'case_study':
                self._generate_case_study_report()
            
            self.status = 'completed'
            self.save(update_fields=['status', 'summary_data', 'detailed_data', 'metrics'])
            
            return True
        except Exception as e:
            logger.error(f"Error generating fraud report {self.id}: {str(e)}")
            self.status = 'failed'
            self.save(update_fields=['status'])
            return False
    
    def _generate_summary_report(self) -> None:
        """Generate summary report data."""
        # Get summary statistics for the period
        alerts = FraudDetectionAlert.objects.filter(
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        )
        
        if self.advertiser:
            alerts = alerts.filter(rule__target_type='advertiser')
        
        summary = {
            'total_alerts': alerts.count(),
            'alerts_by_severity': dict(
                alerts.values('severity_level').annotate(count=Count('id')).values_list('severity_level', 'count')
            ),
            'alerts_by_status': dict(
                alerts.values('status').annotate(count=Count('id')).values_list('status', 'count')
            ),
            'alerts_by_type': dict(
                alerts.values('target_type').annotate(count=Count('id')).values_list('target_type', 'count')
            ),
            'average_risk_score': alerts.aggregate(avg=Avg('risk_score'))['avg'] or 0,
            'average_confidence_score': alerts.aggregate(avg=Avg('confidence_score'))['avg'] or 0
        }
        
        self.summary_data = summary
    
    def _generate_detailed_report(self) -> None:
        """Generate detailed report data."""
        # Get detailed alert information
        alerts = FraudDetectionAlert.objects.filter(
            created_at__date__gte=self.start_date,
            created_at__date__lte=self.end_date
        ).select_related('rule')
        
        if self.advertiser:
            alerts = alerts.filter(rule__target_type='advertiser')
        
        detailed = []
        for alert in alerts:
            detailed.append({
                'alert_id': alert.alert_id,
                'rule_name': alert.rule.name,
                'severity_level': alert.severity_level,
                'target_type': alert.target_type,
                'target_id': alert.target_id,
                'risk_score': float(alert.risk_score),
                'confidence_score': float(alert.confidence_score),
                'status': alert.status,
                'created_at': alert.created_at.isoformat(),
                'action_taken': alert.action_taken,
                'resolution_type': alert.resolution_type
            })
        
        self.detailed_data = {'alerts': detailed}
    
    def _generate_trend_report(self) -> None:
        """Generate trend analysis report."""
        # Implementation for trend analysis
        pass
    
    def _generate_rule_performance_report(self) -> None:
        """Generate rule performance report."""
        # Implementation for rule performance analysis
        pass
    
    def _generate_case_study_report(self) -> None:
        """Generate case study report."""
        # Implementation for case study analysis
        pass
