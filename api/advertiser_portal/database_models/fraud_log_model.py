from django.conf import settings
"""
Fraud Log Database Model

This module contains fraud detection and logging models for tracking
fraudulent activities and security incidents.
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

from api.advertiser_portal.models_base import (
    AdvertiserPortalBaseModel, StatusModel, AuditModel,
    APIKeyModel, BudgetModel, GeoModel, TrackingModel, ConfigurationModel,
)
from ..enums import *
from ..utils import *
from ..validators import *


class FraudLog(AdvertiserPortalBaseModel, AuditModel, TrackingModel):
    """
    Main fraud log model for tracking fraudulent activities.
    
    This model stores information about detected fraud incidents,
    including severity, evidence, and resolution status.
    """
    
    advertiser = models.ForeignKey(
        'advertiser_portal.Advertiser',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='fraud_logs',
        help_text="Associated advertiser (null if not applicable)"
    )
    
    campaign = models.ForeignKey(
        'advertiser_portal.Campaign',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='fraud_logs',
        help_text="Associated campaign (null if not applicable)"
    )
    
    fraud_type = models.CharField(
        max_length=50,
        choices=FraudTypeEnum.choices(),
        help_text="Type of fraud detected"
    )
    
    severity = models.CharField(
        max_length=20,
        choices=FraudSeverityEnum.choices(),
        help_text="Severity level of the fraud incident"
    )
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address associated with the fraud incident"
    )
    
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string from the fraud incident"
    )
    
    description = models.TextField(
        help_text="Detailed description of the fraud incident"
    )
    
    evidence = models.JSONField(
        default=dict,
        blank=True,
        help_text="Evidence and metadata related to the fraud incident"
    )
    
    # Detection information
    detection_method = models.CharField(
        max_length=50,
        choices=DetectionMethodEnum.choices(),
        default=DetectionMethodEnum.AUTOMATED,
        help_text="How the fraud was detected"
    )
    
    detection_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('1.00'))],
        help_text="Confidence score for fraud detection (0-1)"
    )
    
    # Resolution information
    is_resolved = models.BooleanField(
        default=False,
        help_text="Whether the fraud incident has been resolved"
    )
    
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the fraud incident was resolved"
    )
    
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='resolved_fraud_logs',
        help_text="User who resolved the fraud incident"
    )
    
    resolution_notes = models.TextField(
        blank=True,
        help_text="Notes about the resolution of the fraud incident"
    )
    
    # Impact assessment
    financial_impact = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated financial impact of the fraud incident"
    )
    
    affected_accounts = models.IntegerField(
        default=0,
        help_text="Number of accounts affected by this fraud incident"
    )
    
    # Follow-up actions
    actions_taken = models.JSONField(
        default=list,
        blank=True,
        help_text="List of actions taken in response to the fraud incident"
    )
    
    follow_up_required = models.BooleanField(
        default=True,
        help_text="Whether follow-up actions are required"
    )
    
    follow_up_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date for follow-up review"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_fraud_logs'
        indexes = [
            models.Index(fields=['advertiser', 'fraud_type'], name='idx_advertiser_fraud_type_257'),
            models.Index(fields=['campaign', 'severity'], name='idx_campaign_severity_258'),
            models.Index(fields=['is_resolved', 'severity'], name='idx_is_resolved_severity_259'),
            models.Index(fields=['detection_method'], name='idx_detection_method_260'),
            models.Index(fields=['ip_address'], name='idx_ip_address_261'),
            models.Index(fields=['created_at'], name='idx_created_at_262'),
            models.Index(fields=['resolved_at'], name='idx_resolved_at_263'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.campaign or self.advertiser or "System"
        return f"{target} - {self.fraud_type} ({self.severity})"
    
    def clean(self):
        """Validate fraud log data."""
        super().clean()
        
        if self.follow_up_date and self.follow_up_date <= timezone.now():
            raise ValidationError("Follow-up date must be in the future")
        
        if self.resolved_at and self.resolved_at >= timezone.now():
            raise ValidationError("Resolution date cannot be in the future")
    
    def resolve(self, resolver: 'User', notes: str = '', financial_impact: Decimal = None) -> None:
        """Resolve the fraud incident."""
        self.is_resolved = True
        self.resolved_by = resolver
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        
        if financial_impact is not None:
            self.financial_impact = financial_impact
        
        self.save()
    
    def add_evidence(self, evidence_type: str, evidence_data: Dict[str, Any]) -> None:
        """Add evidence to the fraud incident."""
        if not self.evidence:
            self.evidence = {}
        
        self.evidence[evidence_type] = {
            'data': evidence_data,
            'timestamp': timezone.now().isoformat()
        }
        self.save(update_fields=['evidence'])
    
    def is_overdue_follow_up(self) -> bool:
        """Check if follow-up is overdue."""
        if not self.follow_up_required or not self.follow_up_date:
            return False
        return timezone.now() > self.follow_up_date


class FraudPattern(AdvertiserPortalBaseModel, StatusModel, AuditModel):
    """
    Fraud pattern model for storing known fraud patterns.
    
    This model stores patterns and signatures of known fraud types
    for automated detection and prevention.
    """
    
    name = models.CharField(
        max_length=255,
        help_text="Name of the fraud pattern"
    )
    
    description = models.TextField(
        help_text="Description of the fraud pattern"
    )
    
    fraud_type = models.CharField(
        max_length=50,
        choices=FraudTypeEnum.choices(),
        help_text="Type of fraud this pattern detects"
    )
    
    pattern_signature = models.JSONField(
        help_text="Pattern signature and detection rules"
    )
    
    detection_rules = models.JSONField(
        default=dict,
        blank=True,
        help_text="Specific rules for detecting this pattern"
    )
    
    confidence_threshold = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal('0.8'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('1.00'))],
        help_text="Minimum confidence threshold for pattern matching"
    )
    
    severity_level = models.CharField(
        max_length=20,
        choices=FraudSeverityEnum.choices(),
        default=FraudSeverityEnum.MEDIUM,
        help_text="Default severity level for this pattern"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this pattern is currently active"
    )
    
    match_count = models.IntegerField(
        default=0,
        help_text="Number of times this pattern has matched"
    )
    
    last_matched = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time this pattern was matched"
    )
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_fraud_patterns',
        help_text="User who created this pattern"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_fraud_patterns'
        indexes = [
            models.Index(fields=['fraud_type', 'is_active'], name='idx_fraud_type_is_active_264'),
            models.Index(fields=['severity_level'], name='idx_severity_level_265'),
            models.Index(fields=['match_count'], name='idx_match_count_266'),
            models.Index(fields=['last_matched'], name='idx_last_matched_267'),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.fraud_type})"
    
    def increment_match_count(self) -> None:
        """Increment the match count and update last matched timestamp."""
        self.match_count += 1
        self.last_matched = timezone.now()
        self.save(update_fields=['match_count', 'last_matched'])
    
    def matches_pattern(self, incident_data: Dict[str, Any]) -> bool:
        """Check if incident data matches this pattern."""
        # This would contain the actual pattern matching logic
        # For now, return a placeholder implementation
        return False


class FraudAlert(AdvertiserPortalBaseModel, AuditModel):
    """
    Fraud alert model for managing fraud notifications.
    
    This model stores alerts generated when fraud is detected,
    including notification preferences and escalation rules.
    """
    
    fraud_log = models.ForeignKey(
        FraudLog,
        on_delete=models.CASCADE,
        related_name='alerts',
        help_text="Associated fraud log entry"
    )
    
    alert_type = models.CharField(
        max_length=50,
        choices=AlertTypeEnum.choices(),
        help_text="Type of alert generated"
    )
    
    severity = models.CharField(
        max_length=20,
        choices=FraudSeverityEnum.choices(),
        help_text="Severity level of the alert"
    )
    
    message = models.TextField(
        help_text="Alert message content"
    )
    
    notification_channels = models.JSONField(
        default=list,
        help_text="List of notification channels used"
    )
    
    recipients = models.JSONField(
        default=list,
        help_text="List of alert recipients"
    )
    
    sent_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when alert was sent"
    )
    
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether the alert has been acknowledged"
    )
    
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='acknowledged_fraud_alerts',
        help_text="User who acknowledged the alert"
    )
    
    acknowledged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when alert was acknowledged"
    )
    
    escalation_level = models.IntegerField(
        default=1,
        help_text="Current escalation level"
    )
    
    max_escalation_level = models.IntegerField(
        default=3,
        help_text="Maximum escalation level"
    )
    
    next_escalation_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Time for next escalation if not acknowledged"
    )
    
    class Meta:
        app_label = 'advertiser_portal'
        db_table = 'advertiser_portal_fraud_alerts'
        indexes = [
            models.Index(fields=['fraud_log', 'alert_type'], name='idx_fraud_log_alert_type_268'),
            models.Index(fields=['severity', 'acknowledged'], name='idx_severity_acknowledged_269'),
            models.Index(fields=['sent_at'], name='idx_sent_at_270'),
            models.Index(fields=['next_escalation_at'], name='idx_next_escalation_at_271'),
        ]
        ordering = ['-sent_at']
    
    def __str__(self):
        return f"{self.fraud_log} - {self.alert_type} ({self.severity})"
    
    def acknowledge(self, user: 'User') -> None:
        """Acknowledge the alert."""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save()
    
    def escalate(self) -> None:
        """Escalate the alert to the next level."""
        if self.escalation_level < self.max_escalation_level:
            self.escalation_level += 1
            self.next_escalation_at = timezone.now() + timezone.timedelta(hours=2)
            self.save()
    
    def is_due_for_escalation(self) -> bool:
        """Check if alert is due for escalation."""
        if not self.next_escalation_at or self.acknowledged:
            return False
        return timezone.now() >= self.next_escalation_at
