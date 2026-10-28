# =============================================================================
# fraud_detection/models.py
#
# Complete model definitions for the Fraud Detection & Prevention system.
# All 14 core models + ChargebackDispute + ConversionCap (from models_chargeback).
#
# Integrity chain: FraudAttempt, FraudCase, FraudCaseEvidence,
#                  FraudCaseAction, FraudWhitelist, FraudNotification
# all carry (integrity_hash, previous_hash) for tamper-evident audit logs.
# =============================================================================
from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone as _tz

try:
    from api.core.models import TimeStampedModel
except ImportError:
    try:
        from core.models import TimeStampedModel
    except ImportError:
        from django.db import models as _m
        class TimeStampedModel(_m.Model):
            created_at = _m.DateTimeField(auto_now_add=True)
            updated_at = _m.DateTimeField(auto_now=True)
            class Meta:
                abstract = True

from .choices import (
    ActionOnTrigger,
    ActionType,
    AlertPriority,
    AttemptStatus,
    AttemptType,
    CasePriority,
    CaseStatus,
    CompletionStatus,
    DetectedBy,
    EntityType,
    EvidenceType,
    FraudAlertType,
    MonitoringLevel,
    NotificationChannel,
    NotificationType,
    PatternType,
    RuleType,
    RunFrequency,
    SeverityLevel,
)

User = get_user_model()

_SCORE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


# =============================================================================
# Helpers
# =============================================================================

def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _compute_hash(obj, fields: list[str], previous_hash: str = '') -> str:
    """Build a deterministic SHA-256 hash over *fields* of *obj*."""
    parts = [str(getattr(obj, f, '')) for f in fields] + [previous_hash]
    return _sha256('|'.join(parts))


# =============================================================================
# FraudRule
# =============================================================================

class FraudRule(TimeStampedModel):
    """A configurable rule that the rule engine evaluates on each fraud check."""

    name             = models.CharField(max_length=200, unique=True)
    description      = models.TextField(blank=True)
    rule_type        = models.CharField(max_length=50, choices=RuleType.choices, default=RuleType.CUSTOM)
    severity         = models.CharField(max_length=20, choices=SeverityLevel.choices, default=SeverityLevel.MEDIUM)
    condition        = models.JSONField(default=dict, help_text='Rule condition expression as JSON')
    weight           = models.FloatField(default=1.0, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    threshold        = models.FloatField(default=0.5, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    action_on_trigger = models.CharField(max_length=20, choices=ActionOnTrigger.choices, default=ActionOnTrigger.FLAG)
    is_active        = models.BooleanField(default=True)
    run_frequency    = models.CharField(max_length=20, choices=RunFrequency.choices, default=RunFrequency.REAL_TIME)

    # Metrics
    last_triggered   = models.DateTimeField(null=True, blank=True)
    trigger_count    = models.PositiveIntegerField(default=0)
    false_positive_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-severity', 'name']
        indexes     = [
            models.Index(fields=['rule_type', 'is_active'], name='idx_rule_type_is_active_995'),
            models.Index(fields=['severity'],                name='idx_severity_996'),
        ]
        verbose_name        = 'Fraud Rule'
        verbose_name_plural = 'Fraud Rules'

    def __str__(self):
        return f'[{self.severity}] {self.name}'

    def record_trigger(self):
        self.trigger_count += 1
        self.last_triggered = _tz.now()
        self.save(update_fields=['trigger_count', 'last_triggered'])


# =============================================================================
# FraudAttempt
# =============================================================================

class FraudAttempt(TimeStampedModel):
    """Every detected (or suspected) fraud incident creates a FraudAttempt record."""

    attempt_id       = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fraud_detection_attempts')
    attempt_type     = models.CharField(max_length=50, choices=AttemptType.choices, default=AttemptType.OTHER)
    description      = models.TextField(blank=True)
    detected_by      = models.CharField(max_length=20, choices=DetectedBy.choices, default=DetectedBy.SYSTEM)
    fraud_rules      = models.ManyToManyField(FraudRule, blank=True, related_name='fraud_attempts')

    # Scores & confidence
    fraud_score      = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)
    confidence_score = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)

    # Evidence
    evidence_data    = models.JSONField(default=dict)
    metadata         = models.JSONField(default=dict)

    # Resolution
    status           = models.CharField(max_length=20, choices=AttemptStatus.choices, default=AttemptStatus.PENDING)
    is_resolved      = models.BooleanField(default=False)
    resolved_at      = models.DateTimeField(null=True, blank=True)
    resolved_by      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_attempts')
    resolution_notes = models.TextField(blank=True)

    # Financial impact
    amount_involved         = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    affected_transactions   = models.PositiveIntegerField(default=0)

    # Integrity chain
    integrity_hash   = models.CharField(max_length=64, blank=True)
    previous_hash    = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['user', 'status'],              name='idx_user_status_997'),
            models.Index(fields=['attempt_type', 'created_at'],  name='idx_attempt_type_created_a_18d'),
            models.Index(fields=['fraud_score'],                 name='idx_fraud_score_999'),
        ]
        verbose_name        = 'Fraud Attempt'
        verbose_name_plural = 'Fraud Attempts'

    def __str__(self):
        return f'FraudAttempt({self.attempt_id}) – {self.attempt_type} – score={self.fraud_score}'

    def save(self, *args, **kwargs):
        if not self.integrity_hash:
            self.integrity_hash = _compute_hash(
                self,
                ['attempt_id', 'user_id', 'attempt_type', 'fraud_score'],
                self.previous_hash,
            )
        super().save(*args, **kwargs)

    def resolve(self, resolved_by, notes: str = ''):
        self.is_resolved = True
        self.status = AttemptStatus.RESOLVED
        self.resolved_at = _tz.now()
        self.resolved_by = resolved_by
        self.resolution_notes = notes
        self.save(update_fields=['is_resolved', 'status', 'resolved_at', 'resolved_by', 'resolution_notes'])


# =============================================================================
# FraudPattern (ML-trained detection pattern)
# =============================================================================

class FraudPattern(TimeStampedModel):
    """Trained pattern used by the ML fraud scorer."""

    name             = models.CharField(max_length=200, unique=True)
    pattern_type     = models.CharField(max_length=50, choices=PatternType.choices, default=PatternType.BEHAVIORAL)
    description      = models.TextField(blank=True)
    pattern_data     = models.JSONField(default=dict)
    features         = models.JSONField(default=list, help_text='Feature vector names used by this pattern')

    # ML metrics
    occurrence_count = models.PositiveIntegerField(default=0)
    accuracy_rate    = models.FloatField(default=0.0, validators=[MinValueValidator(0.0), MaxValueValidator(1.0)])
    is_trained       = models.BooleanField(default=False)
    last_trained     = models.DateTimeField(null=True, blank=True)
    model_version    = models.CharField(max_length=20, default='1.0.0')

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-accuracy_rate']
        verbose_name        = 'Fraud Pattern'
        verbose_name_plural = 'Fraud Patterns'

    def __str__(self):
        trained = '✓' if self.is_trained else '✗'
        return f'[{trained}] {self.name} ({self.pattern_type})'


# =============================================================================
# UserRiskProfile
# =============================================================================

class UserRiskProfile(TimeStampedModel):
    """Continuously updated fraud risk profile for each user."""

    user                     = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fraud_detection_risk_profile')

    # Composite scores
    overall_risk_score       = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)
    account_risk_score       = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)
    payment_risk_score       = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)
    behavior_risk_score      = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)

    # Detail
    risk_factors             = models.JSONField(default=dict)
    warning_flags            = models.JSONField(default=list)

    # History counters
    total_fraud_attempts     = models.PositiveIntegerField(default=0)
    confirmed_fraud_attempts = models.PositiveIntegerField(default=0)
    false_positives          = models.PositiveIntegerField(default=0)

    # Status flags
    is_flagged      = models.BooleanField(default=False)
    is_restricted   = models.BooleanField(default=False)
    restrictions    = models.JSONField(default=dict)

    # Assessment schedule
    last_risk_assessment = models.DateTimeField(null=True, blank=True)
    next_assessment_due  = models.DateTimeField(null=True, blank=True)
    monitoring_level     = models.CharField(max_length=20, choices=MonitoringLevel.choices, default=MonitoringLevel.NORMAL)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-overall_risk_score']
        indexes     = [
            models.Index(fields=['overall_risk_score'],        name='idx_overall_risk_score_1000'),
            models.Index(fields=['is_flagged', 'is_restricted'], name='idx_is_flagged_is_restrict_e85'),
        ]
        verbose_name        = 'User Risk Profile'
        verbose_name_plural = 'User Risk Profiles'

    def __str__(self):
        return f'RiskProfile({self.user}) – score={self.overall_risk_score}'


# =============================================================================
# DeviceFingerprint
# =============================================================================

class DeviceFingerprint(TimeStampedModel):
    """Fingerprint data collected from a user's device."""

    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_fingerprints')
    device_id        = models.CharField(max_length=255, blank=True)
    device_hash      = models.CharField(max_length=64, db_index=True)

    # Browser / OS
    user_agent       = models.TextField(blank=True)
    platform         = models.CharField(max_length=100, blank=True)
    browser          = models.CharField(max_length=100, blank=True)
    browser_version  = models.CharField(max_length=50,  blank=True)
    os               = models.CharField(max_length=100, blank=True)
    os_version       = models.CharField(max_length=50,  blank=True)

    # Display
    screen_resolution = models.CharField(max_length=20, blank=True)

    # Locale
    language         = models.CharField(max_length=20, blank=True)
    timezone         = models.CharField(max_length=50, blank=True)

    # Hardware
    cpu_cores        = models.SmallIntegerField(null=True, blank=True)
    device_memory    = models.SmallIntegerField(null=True, blank=True, help_text='GB')
    max_touch_points = models.SmallIntegerField(null=True, blank=True)

    # Canvas / WebGL / Audio fingerprints
    canvas_fingerprint = models.CharField(max_length=128, blank=True)
    webgl_fingerprint  = models.CharField(max_length=128, blank=True)
    audio_fingerprint  = models.CharField(max_length=128, blank=True)

    # Network
    ip_address       = models.GenericIPAddressField(null=True, blank=True)
    location_data    = models.JSONField(default=dict)

    # Risk flags
    is_vpn   = models.BooleanField(default=False)
    is_proxy = models.BooleanField(default=False)
    is_tor   = models.BooleanField(default=False)
    is_mobile = models.BooleanField(default=False)
    is_bot   = models.BooleanField(default=False)

    trust_score = models.IntegerField(default=100, validators=_SCORE_VALIDATORS)
    last_seen   = models.DateTimeField(default=_tz.now)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-last_seen']
        indexes     = [
            models.Index(fields=['device_hash'],            name='idx_device_hash_1002'),
            models.Index(fields=['user', 'last_seen'],      name='idx_user_last_seen_1003'),
            models.Index(fields=['ip_address', 'created_at'], name='idx_ip_address_created_at_1004'),
        ]
        verbose_name        = 'Device Fingerprint'
        verbose_name_plural = 'Device Fingerprints'

    def __str__(self):
        return f'Device({self.device_hash[:8]}) – {self.user} – trust={self.trust_score}'


# =============================================================================
# IPReputation
# =============================================================================

class IPReputation(TimeStampedModel):
    """Aggregated reputation data for an IP address."""

    ip_address       = models.GenericIPAddressField(unique=True)

    # Scores
    fraud_score  = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)
    spam_score   = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)
    malware_score = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)

    # Activity counts
    total_requests  = models.PositiveIntegerField(default=0)
    fraud_attempts  = models.PositiveIntegerField(default=0)
    unique_users    = models.PositiveIntegerField(default=0)

    # Blacklist
    is_blacklisted  = models.BooleanField(default=False, db_index=True)
    blacklist_reason = models.TextField(blank=True)
    blacklisted_at  = models.DateTimeField(null=True, blank=True)

    # Geo
    country  = models.CharField(max_length=100, blank=True)
    region   = models.CharField(max_length=100, blank=True)
    city     = models.CharField(max_length=100, blank=True)
    isp      = models.CharField(max_length=200, blank=True)

    # Threat data
    threat_types       = models.JSONField(default=list)
    last_threat_check  = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-fraud_score']
        indexes     = [
            models.Index(fields=['ip_address', 'is_blacklisted'], name='idx_ip_address_is_blacklis_456'),
            models.Index(fields=['country', 'fraud_score'],        name='idx_country_fraud_score_1006'),
        ]
        verbose_name        = 'IP Reputation'
        verbose_name_plural = 'IP Reputations'

    def __str__(self):
        bl = ' [BL]' if self.is_blacklisted else ''
        return f'IP({self.ip_address}){bl} – fraud={self.fraud_score}'


# =============================================================================
# FraudAlert
# =============================================================================

class FraudAlert(TimeStampedModel):
    """Alert generated when a significant fraud signal is detected."""

    alert_id      = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    alert_type    = models.CharField(max_length=50, choices=FraudAlertType.choices, default=FraudAlertType.FRAUD_DETECTED)
    priority      = models.CharField(max_length=20, choices=AlertPriority.choices, default=AlertPriority.MEDIUM)
    title         = models.CharField(max_length=300)
    description   = models.TextField(blank=True)

    # Relations
    user          = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='fraud_alerts')
    fraud_attempt = models.ForeignKey('FraudAttempt', null=True, blank=True, on_delete=models.SET_NULL, related_name='alerts')
    related_rules = models.ManyToManyField(FraudRule, blank=True, related_name='alerts')

    # Payload
    data          = models.JSONField(default=dict)

    # Resolution
    is_resolved   = models.BooleanField(default=False, db_index=True)
    resolved_at   = models.DateTimeField(null=True, blank=True)
    resolved_by   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_alerts')
    resolution_notes = models.TextField(blank=True)

    # Notifications
    notified_users    = models.ManyToManyField(User, blank=True, related_name='notified_alerts')
    notification_sent = models.BooleanField(default=False)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        indexes     = [
            models.Index(fields=['alert_type', 'is_resolved'],  name='idx_alert_type_is_resolved_a40'),
            models.Index(fields=['priority', 'created_at'],     name='idx_priority_created_at_1008'),
        ]
        verbose_name        = 'Fraud Alert'
        verbose_name_plural = 'Fraud Alerts'

    def __str__(self):
        return f'Alert({self.alert_id}) [{self.priority}] {self.title}'

    def resolve(self, resolved_by, notes: str = ''):
        self.is_resolved = True
        self.resolved_at = _tz.now()
        self.resolved_by = resolved_by
        self.resolution_notes = notes
        self.save(update_fields=['is_resolved', 'resolved_at', 'resolved_by', 'resolution_notes'])


# =============================================================================
# FraudCase  (investigation case)
# =============================================================================

class FraudCase(TimeStampedModel):
    """A formal investigation case grouping one or more fraud signals."""

    case_number   = models.CharField(max_length=20, unique=True, editable=False)
    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fraud_cases')
    title         = models.CharField(max_length=300)
    description   = models.TextField(blank=True)

    # Triage
    status    = models.CharField(max_length=20, choices=CaseStatus.choices, default=CaseStatus.OPEN, db_index=True)
    priority  = models.CharField(max_length=20, choices=CasePriority.choices, default=CasePriority.MEDIUM)
    risk_score = models.IntegerField(default=0, validators=_SCORE_VALIDATORS)

    is_high_priority = models.BooleanField(default=False)
    escalation_level = models.PositiveSmallIntegerField(default=0)
    metadata         = models.JSONField(default=dict)

    # Timeline
    opened_at   = models.DateTimeField(default=_tz.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Assignment
    assigned_to      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_cases')
    resolved_by      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='resolved_cases')
    resolution_notes = models.TextField(blank=True)

    # Integrity chain
    integrity_hash = models.CharField(max_length=64, blank=True)
    previous_hash  = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-opened_at']
        indexes     = [
            models.Index(fields=['status'],   name='idx_case_status_1013'),
            models.Index(fields=['priority'], name='idx_case_priority_1014'),
        ]
        verbose_name        = 'Fraud Case'
        verbose_name_plural = 'Fraud Cases'

    def __str__(self):
        return f'Case({self.case_number}) [{self.status}] {self.title}'

    def save(self, *args, **kwargs):
        if not self.case_number:
            now = _tz.now()
            self.case_number = f'FC-{now.year}{now.month:02d}-{uuid.uuid4().hex[:6].upper()}'
        if not self.integrity_hash:
            self.integrity_hash = _compute_hash(
                self,
                ['case_number', 'user_id', 'title', 'status'],
                self.previous_hash,
            )
        super().save(*args, **kwargs)


# =============================================================================
# FraudCaseEvidence
# =============================================================================

class FraudCaseEvidence(TimeStampedModel):
    """A piece of evidence attached to a FraudCase."""

    evidence_id  = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fraud_case   = models.ForeignKey(FraudCase, on_delete=models.CASCADE)
    evidence_type = models.CharField(max_length=50, choices=EvidenceType.choices, default=EvidenceType.OTHER)
    data         = models.JSONField(default=dict)
    added_by     = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='added_evidence')

    integrity_hash = models.CharField(max_length=64, blank=True)
    previous_hash  = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        verbose_name        = 'Case Evidence'
        verbose_name_plural = 'Case Evidence'

    def __str__(self):
        return f'Evidence({self.evidence_id}) – {self.evidence_type}'

    def save(self, *args, **kwargs):
        if not self.integrity_hash:
            self.integrity_hash = _compute_hash(
                self,
                ['evidence_id', 'fraud_case_id', 'evidence_type'],
                self.previous_hash,
            )
        super().save(*args, **kwargs)


# =============================================================================
# FraudCaseAction  (audit trail of actions taken on a case)
# =============================================================================

class FraudCaseAction(TimeStampedModel):
    """One action (investigate, escalate, resolve …) taken on a FraudCase."""

    action_id    = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    fraud_case   = models.ForeignKey(FraudCase, on_delete=models.CASCADE)
    action_type  = models.CharField(max_length=30, choices=ActionType.choices, default=ActionType.NOTE_ADDED)
    performed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='case_actions')
    note         = models.TextField(blank=True)
    is_completed = models.BooleanField(default=False)

    integrity_hash = models.CharField(max_length=64, blank=True)
    previous_hash  = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        verbose_name        = 'Case Action'
        verbose_name_plural = 'Case Actions'

    def __str__(self):
        return f'Action({self.action_id}) – {self.action_type}'

    def save(self, *args, **kwargs):
        if not self.integrity_hash:
            self.integrity_hash = _compute_hash(
                self,
                ['action_id', 'fraud_case_id', 'action_type'],
                self.previous_hash,
            )
        super().save(*args, **kwargs)


# =============================================================================
# FraudWhitelist
# =============================================================================

class FraudWhitelist(TimeStampedModel):
    """Entities explicitly exempted from fraud checks."""

    whitelist_id    = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    entity_type     = models.CharField(max_length=30, choices=EntityType.choices)
    entity_value    = models.CharField(max_length=500, db_index=True)
    reason          = models.TextField()
    is_active       = models.BooleanField(default=True, db_index=True)
    whitelisted_by  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='whitelisted_entries')
    expires_at      = models.DateTimeField(null=True, blank=True)

    integrity_hash = models.CharField(max_length=64, blank=True)
    previous_hash  = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        unique_together = [('entity_type', 'entity_value')]
        verbose_name        = 'Whitelist Entry'
        verbose_name_plural = 'Whitelist Entries'

    def __str__(self):
        return f'Whitelist({self.entity_type}: {self.entity_value})'

    def save(self, *args, **kwargs):
        if not self.integrity_hash:
            self.integrity_hash = _compute_hash(
                self,
                ['whitelist_id', 'entity_type', 'entity_value'],
                self.previous_hash,
            )
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return _tz.now() > self.expires_at


# =============================================================================
# FraudNotification
# =============================================================================

class FraudNotification(TimeStampedModel):
    """Notification dispatched to a user as a result of a fraud event."""

    notification_id   = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fraud_notifications')
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices, default=NotificationType.ALERT)
    channel           = models.CharField(max_length=20, choices=NotificationChannel.choices, default=NotificationChannel.IN_APP)

    title   = models.CharField(max_length=300)
    body    = models.TextField()
    data    = models.JSONField(default=dict)

    is_sent = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    integrity_hash = models.CharField(max_length=64, blank=True)
    previous_hash  = models.CharField(max_length=64, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        verbose_name        = 'Fraud Notification'
        verbose_name_plural = 'Fraud Notifications'

    def __str__(self):
        return f'Notif({self.notification_id}) [{self.notification_type}] → {self.user}'

    def save(self, *args, **kwargs):
        if not self.integrity_hash:
            self.integrity_hash = _compute_hash(
                self,
                ['notification_id', 'user_id', 'notification_type'],
                self.previous_hash,
            )
        super().save(*args, **kwargs)

    def mark_read(self):
        if not self.read_at:
            self.read_at = _tz.now()
            self.save(update_fields=['read_at'])


# =============================================================================
# FraudSettings  (singleton-style system configuration)
# =============================================================================

class FraudSettings(TimeStampedModel):
    """System-wide fraud detection configuration. Keep to one row."""

    block_vpn              = models.BooleanField(default=False)
    global_risk_threshold  = models.IntegerField(default=70, validators=_SCORE_VALIDATORS,
                                                  help_text='Fraud score at or above which users are auto-flagged')
    updated_by             = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        app_label   = 'fraud_detection'
        verbose_name        = 'Fraud Settings'
        verbose_name_plural = 'Fraud Settings'

    def __str__(self):
        return f'FraudSettings (threshold={self.global_risk_threshold}, block_vpn={self.block_vpn})'

    @classmethod
    def get(cls) -> 'FraudSettings':
        """Return the singleton settings object, creating it if necessary."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# =============================================================================
# OfferCompletion
# =============================================================================

class OfferCompletion(TimeStampedModel):
    """
    Records a user's completion of an offerwall offer.
    Fraud flags are set here when patterns are detected.
    """

    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='offer_completions')
    # FK to offerwall app — use string reference to avoid circular imports
    offer           = models.ForeignKey('offerwall.Offer', on_delete=models.CASCADE, related_name='completions')
    status          = models.CharField(max_length=20, choices=CompletionStatus.choices, default=CompletionStatus.PENDING)
    completion_data = models.JSONField(default=dict)
    reward_amount   = models.DecimalField(max_digits=14, decimal_places=6, default=Decimal('0'))

    # Optional FK to wallet transaction
    transaction     = models.ForeignKey('wallet.WalletTransaction', null=True, blank=True, on_delete=models.SET_NULL, related_name='fraud_offer_completions')

    # Request metadata
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    user_agent    = models.TextField(blank=True)
    device_id     = models.CharField(max_length=255, blank=True)
    referral_code = models.CharField(max_length=50, blank=True)

    # Fraud
    is_fraud     = models.BooleanField(default=False, db_index=True)
    fraud_reason = models.TextField(blank=True)

    # Timeline
    tracked_at   = models.DateTimeField(default=_tz.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)
    reviewed_by  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_completions')
    notes        = models.TextField(blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-tracked_at']
        indexes     = [
            models.Index(fields=['user', 'status'],    name='idx_user_status_1009'),
            models.Index(fields=['offer', 'status'],   name='idx_offer_status_1010'),
            models.Index(fields=['tracked_at'],        name='idx_tracked_at_1011'),
            models.Index(fields=['is_fraud'],          name='idx_is_fraud_1012'),
        ]
        verbose_name        = 'Offer Completion'
        verbose_name_plural = 'Offer Completions'

    def __str__(self):
        return f'Completion(user={self.user_id}, offer={self.offer_id}, status={self.status})'


# =============================================================================
# ChargebackDispute & ConversionCap  (from models_chargeback.py)
# =============================================================================

class ChargebackDispute(TimeStampedModel):
    """Tracks payment chargebacks and disputes filed against the platform."""

    class Status(models.TextChoices):
        RECEIVED       = 'received',       'Received'
        INVESTIGATING  = 'investigating',  'Investigating'
        REPRESENTED    = 'represented',    'Represented (Fighting)'
        WON            = 'won',            'Won'
        LOST           = 'lost',           'Lost'
        REVERSED       = 'reversed',       'Reversed by Bank'
        WITHDRAWN      = 'withdrawn',      'Withdrawn by User'

    class Reason(models.TextChoices):
        UNAUTHORIZED          = 'unauthorized',      'Unauthorized Transaction'
        DUPLICATE             = 'duplicate',         'Duplicate Charge'
        ITEM_NOT_RECEIVED     = 'not_received',      'Item Not Received'
        ITEM_NOT_AS_DESCRIBED = 'not_as_described',  'Not As Described'
        FRIENDLY_FRAUD        = 'friendly_fraud',    'Friendly Fraud'
        OTHER                 = 'other',             'Other'

    dispute_id         = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user               = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chargebacks')
    amount             = models.DecimalField(max_digits=14, decimal_places=2)
    currency           = models.CharField(max_length=3, default='USD')
    status             = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    reason             = models.CharField(max_length=30, choices=Reason.choices, default=Reason.OTHER)
    payment_processor  = models.CharField(max_length=50, blank=True)
    processor_reference = models.CharField(max_length=200, blank=True)
    is_fraudulent      = models.BooleanField(default=False)
    fraud_attempt      = models.ForeignKey(FraudAttempt, null=True, blank=True, on_delete=models.SET_NULL, related_name='chargebacks')
    evidence_submitted = models.JSONField(default=dict)
    response_deadline  = models.DateTimeField(null=True, blank=True)
    resolved_at        = models.DateTimeField(null=True, blank=True)
    notes              = models.TextField(blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['-created_at']
        verbose_name        = 'Chargeback Dispute'
        verbose_name_plural = 'Chargeback Disputes'

    def __str__(self):
        return f'Chargeback({self.dispute_id}) [{self.status}] ${self.amount}'


class ConversionCap(TimeStampedModel):
    """Daily / weekly conversion caps to prevent offer abuse."""

    class CapType(models.TextChoices):
        DAILY   = 'daily',   'Daily Cap'
        WEEKLY  = 'weekly',  'Weekly Cap'
        MONTHLY = 'monthly', 'Monthly Cap'
        TOTAL   = 'total',   'Total Cap'

    class ActionOnExceed(models.TextChoices):
        BLOCK  = 'block',  'Block Completions'
        FLAG   = 'flag',   'Flag for Review'
        REDUCE = 'reduce', 'Reduce Reward'

    cap_id          = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name            = models.CharField(max_length=200)
    offer           = models.ForeignKey('offerwall.Offer', null=True, blank=True, on_delete=models.SET_NULL, related_name='conversion_caps')
    cap_type        = models.CharField(max_length=20, choices=CapType.choices, default=CapType.DAILY)
    limit           = models.PositiveIntegerField(help_text='Maximum allowed completions in the period')
    current_count   = models.PositiveIntegerField(default=0)
    action_on_exceed = models.CharField(max_length=20, choices=ActionOnExceed.choices, default=ActionOnExceed.BLOCK)
    is_active       = models.BooleanField(default=True)
    reset_at        = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label   = 'fraud_detection'
        ordering    = ['name']
        verbose_name        = 'Conversion Cap'
        verbose_name_plural = 'Conversion Caps'

    def __str__(self):
        return f'Cap({self.name}) {self.current_count}/{self.limit} [{self.cap_type}]'

    @property
    def is_exceeded(self) -> bool:
        return self.current_count >= self.limit


# Backward-compatible alias: most of the app imports this model as FraudRiskProfile
FraudRiskProfile = UserRiskProfile


# Backward-compatible alias: several modules still import this model as FraudSuspiciousIP
FraudSuspiciousIP = IPReputation


# ---------------------------------------------------------------------------
# Backward-compat alias: many call sites across interactors.py, throttling.py,
# use_cases.py, kyc_service.py, tasks.py, analytics.py etc. read/write
# .risk_score on a UserRiskProfile instance, but the real field is
# overall_risk_score. Same shape as the FraudSuspiciousIP alias.
# ---------------------------------------------------------------------------
def _user_risk_profile_risk_score_get(self):
    return self.overall_risk_score

def _user_risk_profile_risk_score_set(self, value):
    self.overall_risk_score = value

UserRiskProfile.risk_score = property(_user_risk_profile_risk_score_get, _user_risk_profile_risk_score_set)


# ---------------------------------------------------------------------------
# Backward-compat alias: throttling.py and use_cases.py read .risk_score on
# an IPReputation instance (via fraud_suspicious_ip_selector.get_suspicious_ip),
# but the real field is fraud_score.
# ---------------------------------------------------------------------------
def _ip_reputation_risk_score_get(self):
    return self.fraud_score

IPReputation.risk_score = property(_ip_reputation_risk_score_get)
