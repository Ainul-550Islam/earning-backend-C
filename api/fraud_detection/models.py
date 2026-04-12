from django.db import models
# PostgreSQL এর বদলে এটি ব্যবহার করা হয়েছে
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from core.models import TimeStampedModel
import uuid
from django.conf import settings


class FraudSettings(TimeStampedModel):
    """Simple persistent settings for fraud detection toggles"""
    block_vpn = models.BooleanField(default=False)
    global_risk_threshold = models.IntegerField(default=70)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        verbose_name = 'Fraud Setting'
        verbose_name_plural = 'Fraud Settings'

    def __str__(self):
        return f"FraudSettings(block_vpn={self.block_vpn}, threshold={self.global_risk_threshold})"

def get_default_list():
    return []

def get_default_dict():
    return {}

class FraudRule(TimeStampedModel):
    """Fraud detection rules configuration"""
    RULE_TYPES = (
        ('account', 'Account Fraud'),
        ('payment', 'Payment Fraud'),
        ('offer', 'Offer Fraud'),
        ('referral', 'Referral Fraud'),
        ('withdrawal', 'Withdrawal Fraud'),
        ('behavior', 'Behavioral Fraud'),
    )
    
    SEVERITY_LEVELS = (
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical Risk'),
    )
    
    name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    description = models.TextField()
    rule_type = models.CharField(max_length=50, choices=RULE_TYPES, null=True, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, null=True, blank=True)
    
    # Rule configuration
    condition = models.TextField(default='{}')  # Rule conditions in JSON
    weight = models.IntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])
    threshold = models.IntegerField(default=70, validators=[MinValueValidator(1), MaxValueValidator(100)])
    
    # Actions
    action_on_trigger = models.CharField(max_length=50, choices=[
        ('flag', 'Flag User'),
        ('review', 'Mark for Review'),
        ('limit', 'Limit Actions'),
        ('suspend', 'Suspend Account'),
        ('ban', 'Ban Permanently'),
    ])
    
    # Scheduling
    is_active = models.BooleanField(default=True)
    run_frequency = models.CharField(max_length=20, choices=[
        ('realtime', 'Real-time'),
        ('hourly', 'Hourly'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
    ])
    
    # Metadata
    last_triggered = models.DateTimeField(null=True, blank=True)
    trigger_count = models.IntegerField(default=0)
    false_positive_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['rule_type', 'is_active']),
            models.Index(fields=['severity']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_severity_display()})"

class FraudAttempt(TimeStampedModel):
    """Record of detected fraud attempts"""
    ATTEMPT_TYPES = (
        ('multi_account', 'Multi-Account'),
        ('vpn_proxy', 'VPN/Proxy'),
        ('click_fraud', 'Click Fraud'),
        ('offer_abuse', 'Offer Abuse'),
        ('payment_fraud', 'Payment Fraud'),
        ('referral_fraud', 'Referral Fraud'),
        ('device_spoofing', 'Device Spoofing'),
        ('location_spoofing', 'Location Spoofing'),
    )
    
    STATUS_CHOICES = (
        ('detected', 'Detected'),
        ('reviewing', 'Under Review'),
        ('confirmed', 'Confirmed Fraud'),
        ('false_positive', 'False Positive'),
        ('resolved', 'Resolved'),
    )
    
    # Identifiers
    attempt_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='fraud_detection_attempts', null=True, blank=True)
    
    # Attempt details
    attempt_type = models.CharField(max_length=50, choices=ATTEMPT_TYPES, null=True, blank=True)
    description = models.TextField()
    detected_by = models.CharField(max_length=100, null=True, blank=True)  # Which detector caught it
    fraud_rules = models.ManyToManyField(FraudRule, related_name='fraud_detection_attempts')
    
    # Evidence and data
    evidence_data = models.TextField(default='{}')  # Raw data that triggered detection
    metadata = models.TextField(default='{}')  # Additional metadata
    
    # Risk scoring
    fraud_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    confidence_score = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Status and resolution
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected', null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_fraud_attempts')
    resolution_notes = models.TextField(blank=True)
    
    # Impact
    affected_transactions = models.ManyToManyField('wallet.WalletTransaction', related_name='fraud_detection_attempts', blank=True)
    amount_involved = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['attempt_type', 'created_at']),
            models.Index(fields=['fraud_score']),
        ]
    
    def __str__(self):
        return f"Fraud Attempt {self.attempt_id} - {self.get_attempt_type_display()}"
    
    def mark_as_confirmed(self, resolved_by=None, notes=""):
        self.status = 'confirmed'
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.resolved_by = resolved_by
        self.resolution_notes = notes
        self.save()

class FraudPattern(TimeStampedModel):
    """Known fraud patterns for ML training"""
    PATTERN_TYPES = (
        ('behavioral', 'Behavioral Pattern'),
        ('temporal', 'Temporal Pattern'),
        ('geographic', 'Geographic Pattern'),
        ('device', 'Device Pattern'),
        ('network', 'Network Pattern'),
    )
    
    name = models.CharField(max_length=255, null=True, blank=True)
    pattern_type = models.CharField(max_length=50, choices=PATTERN_TYPES, null=True, blank=True)
    description = models.TextField()
    
    # Pattern data
    pattern_data = models.TextField(default='{}')  # JSON representation of pattern
    features = ArrayField(models.CharField(max_length=100, null=True, blank=True), default=list)  # Key features of the pattern
    
    # Statistics
    occurrence_count = models.IntegerField(default=0)
    accuracy_rate = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    
    # ML metadata
    is_trained = models.BooleanField(default=False)
    last_trained = models.DateTimeField(null=True, blank=True)
    model_version = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        unique_together = ['name', 'pattern_type']
    
    def __str__(self):
        return f"{self.name} ({self.get_pattern_type_display()})"

class UserRiskProfile(TimeStampedModel):
    """Risk assessment profile for each user"""
    user = models.OneToOneField('users.User', on_delete=models.CASCADE, related_name='fraud_detection_risk_profile', null=True, blank=True)
    
    # Risk scores
    overall_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    account_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    payment_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    behavior_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Risk factors
    risk_factors = models.TextField(default='{}')  # {factor: score}
    warning_flags = ArrayField(models.CharField(max_length=50, null=True, blank=True), default=list)
    
    # Statistics
    total_fraud_attempts = models.IntegerField(default=0)
    confirmed_fraud_attempts = models.IntegerField(default=0)
    false_positives = models.IntegerField(default=0)
    
    # Restrictions
    is_flagged = models.BooleanField(default=False)
    is_restricted = models.BooleanField(default=False)
    restrictions = models.TextField(default='{}')  # {action: allowed/not_allowed}
    
    # Monitoring
    last_risk_assessment = models.DateTimeField(null=True, blank=True)
    next_assessment_due = models.DateTimeField(null=True, blank=True)
    monitoring_level = models.CharField(max_length=20, choices=[
        ('normal', 'Normal Monitoring'),
        ('enhanced', 'Enhanced Monitoring'),
        ('strict', 'Strict Monitoring'),
    ], default='normal')
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['overall_risk_score']),
            models.Index(fields=['is_flagged', 'is_restricted']),
        ]
    
    def __str__(self):
        return f"Risk Profile: {self.user.username}"
    
    def update_risk_score(self):
        """Calculate and update risk scores"""
        from .services.FraudScoreCalculator import FraudScoreCalculator
        calculator = FraudScoreCalculator(self.user)
        self.overall_risk_score = calculator.calculate_overall_risk()
        self.save()

class DeviceFingerprint(TimeStampedModel):
    """Device fingerprinting data"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='device_fingerprints', null=True, blank=True)
    
    # Device identifiers
    device_id = models.CharField(max_length=255, unique=True, null=True, blank=True, default=None)
    device_hash = models.CharField(max_length=512, db_index=True, null=True, blank=True)
    
    # Device information
    user_agent = models.TextField()
    platform = models.CharField(max_length=100, null=True, blank=True)
    browser = models.CharField(max_length=100, null=True, blank=True)
    browser_version = models.CharField(max_length=50, null=True, blank=True)
    os = models.CharField(max_length=100, null=True, blank=True)
    os_version = models.CharField(max_length=50, null=True, blank=True)
    screen_resolution = models.CharField(max_length=50, null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    timezone = models.CharField(max_length=100, null=True, blank=True)
    
    # Hardware info
    cpu_cores = models.IntegerField(null=True, blank=True)
    device_memory = models.IntegerField(null=True, blank=True)  # in MB
    max_touch_points = models.IntegerField(null=True, blank=True)
    
    # Canvas/WebGL fingerprint
    canvas_fingerprint = models.CharField(max_length=512, null=True, blank=True)
    webgl_fingerprint = models.CharField(max_length=512, null=True, blank=True)
    audio_fingerprint = models.CharField(max_length=512, null=True, blank=True)
    
    # Network info
    ip_address = models.GenericIPAddressField()
    location_data = models.TextField(default='{}')  # GeoIP data
    
    # Security flags
    is_vpn = models.BooleanField(default=False)
    is_proxy = models.BooleanField(default=False)
    is_tor = models.BooleanField(default=False)
    is_mobile = models.BooleanField(default=False)
    is_bot = models.BooleanField(default=False)
    
    # Trust score
    trust_score = models.IntegerField(default=100, validators=[MinValueValidator(0), MaxValueValidator(100)])
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['device_hash']),
            models.Index(fields=['user', 'last_seen']),
            models.Index(fields=['ip_address', 'created_at']),
        ]
    
    def __str__(self):
        return f"Device {self.device_id[:8]}... ({self.user.username})"

class IPReputation(TimeStampedModel):
    """IP address reputation tracking"""
    ip_address = models.GenericIPAddressField(unique=True)
    
    # Reputation scores
    fraud_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    spam_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    malware_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    
    # Statistics
    total_requests = models.IntegerField(default=0)
    fraud_attempts = models.IntegerField(default=0)
    unique_users = models.IntegerField(default=0)
    
    # Classification
    is_blacklisted = models.BooleanField(default=False)
    blacklist_reason = models.CharField(max_length=255, null=True, blank=True)
    blacklisted_at = models.DateTimeField(null=True, blank=True)
    
    # Geolocation
    country = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    isp = models.CharField(max_length=255, null=True, blank=True)
    
    # Threat intelligence
    threat_types = ArrayField(models.CharField(max_length=50, null=True, blank=True), default=list)
    last_threat_check = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['ip_address', 'is_blacklisted']),
            models.Index(fields=['country', 'fraud_score']),
        ]
    
    def __str__(self):
        return f"IP {self.ip_address} - Score: {self.fraud_score}"

class FraudAlert(TimeStampedModel):
    """System alerts for fraud detection"""
    ALERT_TYPES = (
        ('rule_triggered', 'Rule Triggered'),
        ('pattern_detected', 'Pattern Detected'),
        ('threshold_exceeded', 'Threshold Exceeded'),
        ('manual_review', 'Manual Review Required'),
        ('system_anomaly', 'System Anomaly'),
    )
    
    PRIORITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    # Alert details
    alert_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    alert_type = models.CharField(max_length=50, choices=ALERT_TYPES, null=True, blank=True)
    priority = models.CharField(max_length=20, choices=PRIORITY_LEVELS, null=True, blank=True)
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField()
    
    # Related objects
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    fraud_attempt = models.ForeignKey(FraudAttempt, on_delete=models.CASCADE, null=True, blank=True)
    related_rules = models.ManyToManyField(FraudRule, blank=True)
    
    # Alert data
    data = models.TextField(default='{}')
    
    # Status
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolution_notes = models.TextField(blank=True)
    
    # Notification
    notified_users = models.ManyToManyField('users.User', related_name='fraud_alerts', blank=True)
    notification_sent = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['alert_type', 'is_resolved']),
            models.Index(fields=['priority', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_priority_display()} Alert: {self.title}"
    
class OfferCompletion(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),
        ('processing', 'Processing'),
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offer_completions',
        verbose_name='User')
    
    offer = models.ForeignKey(
        'offerwall.Offer',
        on_delete=models.CASCADE,
        related_name='completions',
        verbose_name='Offer')
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Status')
    
    completion_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Completion Data'
    )
    
    reward_amount = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
        verbose_name='Reward Amount')
    
    transaction = models.ForeignKey(
        'wallet.WalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offer_completions',
        verbose_name='WalletTransaction')
    
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP Address'
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    
    device_id = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Device ID')
    
    referral_code = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Referral Code')
    
    is_fraud = models.BooleanField(
        default=False,
        verbose_name='Is Fraud'
    )
    
    fraud_reason = models.TextField(
        blank=True,
        verbose_name='Fraud Reason'
    )
    
    tracked_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Tracked At'
    )
    
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Completed At'
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Reviewed At'
    )
    
    reviewed_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_offer_completions',
        verbose_name='Reviewed By')
    
    notes = models.TextField(
        blank=True,
        verbose_name='Notes'
    )
    
    class Meta:
        ordering = ['-tracked_at']
        verbose_name = 'Offer Completion'
        verbose_name_plural = 'Offer Completions'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['offer', 'status']),
            models.Index(fields=['tracked_at']),
            models.Index(fields=['is_fraud']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.offer.title} - {self.status}"
    
    def save(self, *args, **kwargs):
        if self.status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)