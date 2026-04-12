from django.conf import settings
"""Fraud detection models (used by fraud_prevention services)."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class FraudDetection(AdvertiserPortalBaseModel):
    user_id = models.CharField(max_length=64, blank=True, db_index=True)
    session_id = models.CharField(max_length=128, blank=True)
    event_type = models.CharField(max_length=50, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    device_fingerprint = models.CharField(max_length=128, blank=True)
    risk_score = models.FloatField(default=0.0, db_index=True)
    is_fraudulent = models.BooleanField(default=False, db_index=True)
    confidence_level = models.FloatField(default=0.0)
    detected_patterns = models.JSONField(default=list)
    risk_factors = models.JSONField(default=dict)
    recommended_actions = models.JSONField(default=list)
    event_data = models.JSONField(default=dict)
    detection_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-detection_timestamp']
    def __str__(self):
        return f"FraudDetection [{self.event_type}] score={self.risk_score:.2f}"


class RiskScore(AdvertiserPortalBaseModel):
    user_id = models.CharField(max_length=64, db_index=True)
    overall_risk_score = models.FloatField(default=0.0)
    risk_level = models.CharField(max_length=20, default='low')
    risk_factors = models.JSONField(default=dict)
    temporal_risk = models.FloatField(default=0.0)
    behavioral_risk = models.FloatField(default=0.0)
    technical_risk = models.FloatField(default=0.0)
    contextual_risk = models.FloatField(default=0.0)
    confidence_interval = models.JSONField(default=list)
    assessment_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-assessment_timestamp']
    def __str__(self):
        return f"RiskScore user={self.user_id} [{self.risk_level}]"


class FraudPattern(AdvertiserPortalBaseModel):
    name = models.CharField(max_length=200, unique=True)
    pattern_type = models.CharField(max_length=50)
    detection_rules = models.JSONField(default=list)
    weight = models.FloatField(default=1.0)
    threshold = models.FloatField(default=0.5)
    is_active = models.BooleanField(default=True, db_index=True)
    class Meta:
        ordering = ['name']
    def __str__(self):
        return f"FraudPattern {self.name}"


class SecurityAlert(AdvertiserPortalBaseModel):
    alert_type = models.CharField(max_length=50, db_index=True)
    severity = models.CharField(max_length=20, default='warning')
    title = models.CharField(max_length=300)
    description = models.TextField()
    risk_score = models.FloatField(default=0.0)
    is_acknowledged = models.BooleanField(default=False)
    fired_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-fired_at']
    def __str__(self):
        return f"SecurityAlert [{self.severity}] {self.title}"


class FraudCheckLog(AdvertiserPortalBaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='fraud_check_logs')
    risk_score = models.FloatField(default=0.0)
    risk_factors = models.JSONField(default=list)
    recommendation = models.CharField(max_length=20, default='allow')
    check_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-check_timestamp']
    def __str__(self):
        return f"FraudCheckLog score={self.risk_score:.2f} → {self.recommendation}"
