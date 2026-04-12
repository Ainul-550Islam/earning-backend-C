"""
Proxy Intelligence Models
=========================
সমস্ত IP ডিটেকশন, ফ্রড, থ্রেট এবং রিস্ক স্কোরিং-এর জন্য Django models।
"""

import uuid
from django.db import models
from django.db.models import JSONField
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from django.utils import timezone as tz
from core.models import TimeStampedModel
from .enums import (
    ProxyType, RiskLevel, DetectionStatus,
    ThreatType, IPVersion, BlacklistReason
)


# ==============================================================
# ১. আইপি ও ডিটেকশন কোর (IP & Detection Core)
# ==============================================================

class IPIntelligence(TimeStampedModel):
    """
    আইপি-র মূল তথ্য: ISP, ASN, রিস্ক স্কোর।
    প্রতিটি IP address-এর সম্পূর্ণ intelligence snapshot।
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='ip_intelligences', null=True, blank=True)

    # IP Info
    ip_address = models.GenericIPAddressField(db_index=True)
    ip_version = models.CharField(max_length=4, choices=IPVersion.choices, default=IPVersion.IPv4, null=True, blank=True)
    asn = models.CharField(max_length=20, null=True, blank=True)
    asn_name = models.CharField(max_length=255, null=True, blank=True)
    isp = models.CharField(max_length=255, null=True, blank=True)
    organization = models.CharField(max_length=255, null=True, blank=True)

    # Geo
    country_code = models.CharField(max_length=2, null=True, blank=True)
    country_name = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    timezone = models.CharField(max_length=50, null=True, blank=True)

    # Detection flags
    is_vpn = models.BooleanField(default=False, db_index=True)
    is_proxy = models.BooleanField(default=False, db_index=True)
    is_tor = models.BooleanField(default=False, db_index=True)
    is_datacenter = models.BooleanField(default=False, db_index=True)
    is_residential = models.BooleanField(default=False)
    is_mobile = models.BooleanField(default=False)
    is_hosting = models.BooleanField(default=False)
    is_crawler = models.BooleanField(default=False)

    # Risk
    risk_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True
    )
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.VERY_LOW, null=True, blank=True)
    fraud_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    abuse_confidence_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Meta
    last_checked = models.DateTimeField(default=tz.now)
    check_count = models.IntegerField(default=1)
    raw_data = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'IP Intelligence'
        verbose_name_plural = 'IP Intelligences'
        ordering = ['-last_checked']
        indexes = [
            models.Index(fields=['ip_address', 'tenant']),
            models.Index(fields=['risk_score']),
            models.Index(fields=['is_vpn', 'is_proxy', 'is_tor']),
        ]

    def __str__(self):
        return f"{self.ip_address} | Risk: {self.risk_score} | VPN:{self.is_vpn}"

    def update_risk_level(self):
        from .constants import (
            RISK_VERY_LOW_MAX, RISK_LOW_MAX, RISK_MEDIUM_MAX, RISK_HIGH_MAX
        )
        if self.risk_score <= RISK_VERY_LOW_MAX:
            self.risk_level = RiskLevel.VERY_LOW
        elif self.risk_score <= RISK_LOW_MAX:
            self.risk_level = RiskLevel.LOW
        elif self.risk_score <= RISK_MEDIUM_MAX:
            self.risk_level = RiskLevel.MEDIUM
        elif self.risk_score <= RISK_HIGH_MAX:
            self.risk_level = RiskLevel.HIGH
        else:
            self.risk_level = RiskLevel.CRITICAL


class VPNDetectionLog(TimeStampedModel):
    """ভিপিএন ব্যবহারের রেকর্ড।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='vpn_detection_logs', null=True, blank=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vpn_detections')

    # Detection details
    vpn_provider = models.CharField(max_length=255, null=True, blank=True)
    vpn_protocol = models.CharField(max_length=50, null=True, blank=True)  # OpenVPN, WireGuard, etc.
    confidence_score = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    detection_method = models.CharField(max_length=100, null=True, blank=True)  # ASN, header, port-scan

    is_confirmed = models.BooleanField(default=False)
    action_taken = models.CharField(max_length=50, null=True, blank=True)  # blocked, flagged, allowed

    class Meta:
        verbose_name = 'VPN Detection Log'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['ip_address', 'created_at'])]

    def __str__(self):
        return f"VPN: {self.ip_address} | {self.vpn_provider} | conf:{self.confidence_score:.2f}"


class ProxyDetectionLog(TimeStampedModel):
    """প্রক্সি ডিটেকশন ও টাইপ (Residential/Mobile)।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='proxy_detection_logs', null=True, blank=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='proxy_detections')

    proxy_type = models.CharField(max_length=30, choices=ProxyType.choices, null=True, blank=True)
    proxy_port = models.IntegerField(null=True, blank=True)
    proxy_provider = models.CharField(max_length=255, null=True, blank=True)
    confidence_score = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(1)])

    is_anonymous = models.BooleanField(default=True)
    is_elite = models.BooleanField(default=False)  # Elite proxy hides proxy headers
    headers_detected = JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'Proxy Detection Log'
        ordering = ['-created_at']

    def __str__(self):
        return f"Proxy: {self.ip_address} | {self.proxy_type}"


class TorExitNode(TimeStampedModel):
    """টর নেটওয়ার্কের আইপি লিস্ট।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ip_address = models.GenericIPAddressField(unique=True, db_index=True)
    fingerprint = models.CharField(max_length=40, null=True, blank=True)  # Tor relay fingerprint
    is_active = models.BooleanField(default=True, db_index=True)
    first_seen = models.DateTimeField(default=tz.now)
    last_seen = models.DateTimeField(default=tz.now)
    exit_policy = models.TextField(blank=True)  # Tor exit policy
    bandwidth = models.BigIntegerField(null=True, blank=True)  # bytes/sec

    class Meta:
        verbose_name = 'Tor Exit Node'
        ordering = ['-last_seen']

    def __str__(self):
        return f"Tor: {self.ip_address} | active:{self.is_active}"


class DatacenterIPRange(TimeStampedModel):
    """পরিচিত ডাটা-সেন্টার আইপি রেঞ্জ।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    cidr = models.CharField(max_length=50, unique=True, null=True, blank=True)  # e.g. 192.168.0.0/16
    provider_name = models.CharField(max_length=255, null=True, blank=True)       # AWS, GCP, Azure, etc.
    asn = models.CharField(max_length=20, null=True, blank=True)
    country_code = models.CharField(max_length=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    source = models.CharField(max_length=100, null=True, blank=True)  # Where this range was sourced from
    last_updated = models.DateTimeField(default=tz.now)

    class Meta:
        verbose_name = 'Datacenter IP Range'
        ordering = ['provider_name']

    def __str__(self):
        return f"{self.cidr} ({self.provider_name})"


# ==============================================================
# ২. ফ্রড ও আচরণ বিশ্লেষণ (Fraud & Behavior)
# ==============================================================

class FraudAttempt(TimeStampedModel):
    """প্রতিটি ফ্রড চেষ্টার বিস্তারিত লগ।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_fraud_attempts', null=True, blank=True)

    FRAUD_TYPES = [
        ('click_fraud', 'Click Fraud'),
        ('account_fraud', 'Account Fraud'),
        ('payment_fraud', 'Payment Fraud'),
        ('referral_fraud', 'Referral Fraud'),
        ('offer_fraud', 'Offer Fraud'),
        ('identity_fraud', 'Identity Fraud'),
        ('bot_activity', 'Bot Activity'),
    ]

    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('investigating', 'Under Investigation'),
        ('confirmed', 'Confirmed Fraud'),
        ('false_positive', 'False Positive'),
        ('resolved', 'Resolved'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_fraud_attempts')
    ip_address = models.GenericIPAddressField(db_index=True)
    fraud_type = models.CharField(max_length=50, choices=FRAUD_TYPES, db_index=True, null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='detected', db_index=True, null=True, blank=True)

    risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    description = models.TextField(blank=True)
    evidence = JSONField(default=dict, blank=True)
    flags = JSONField(default=list, blank=True)  # List of triggered rules

    # Resolution
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_resolved_frauds')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Fraud Attempt'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'fraud_type']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"Fraud: {self.fraud_type} | {self.ip_address} | {self.status}"


class ClickFraudRecord(TimeStampedModel):
    """অ্যাড বা লিঙ্কে অবৈধ ক্লিকের ডাটা।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='click_fraud_records', null=True, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='click_frauds')
    ip_address = models.GenericIPAddressField(db_index=True)
    target_url = models.URLField(null=True, blank=True)
    click_source = models.CharField(max_length=100, null=True, blank=True)

    # Fraud indicators
    is_bot = models.BooleanField(default=False)
    is_duplicate = models.BooleanField(default=False)
    click_frequency = models.IntegerField(default=1)  # Clicks in last N seconds
    time_on_page = models.FloatField(null=True, blank=True)  # Seconds
    conversion = models.BooleanField(default=False)

    fraud_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    user_agent = models.TextField(blank=True)
    referrer = models.URLField(null=True, blank=True)
    session_id = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        verbose_name = 'Click Fraud Record'
        ordering = ['-created_at']

    def __str__(self):
        return f"ClickFraud: {self.ip_address} | bot:{self.is_bot} | score:{self.fraud_score}"


class DeviceFingerprint(TimeStampedModel):
    """ইউজারের ডিভাইসের ইউনিক আইডি (Canvas/JS Fingerprint)।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_device_fingerprints', null=True, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_device_fingerprints')
    fingerprint_hash = models.CharField(max_length=64, db_index=True, null=True, blank=True)

    # Browser/Device info
    user_agent = models.TextField(blank=True)
    browser_name = models.CharField(max_length=50, null=True, blank=True)
    browser_version = models.CharField(max_length=20, null=True, blank=True)
    os_name = models.CharField(max_length=50, null=True, blank=True)
    os_version = models.CharField(max_length=20, null=True, blank=True)
    device_type = models.CharField(max_length=30, null=True, blank=True)  # mobile, desktop, tablet

    # Canvas/WebGL fingerprint
    canvas_hash = models.CharField(max_length=64, null=True, blank=True)
    webgl_hash = models.CharField(max_length=64, null=True, blank=True)
    audio_hash = models.CharField(max_length=64, null=True, blank=True)

    # Network
    ip_addresses = JSONField(default=list, blank=True)  # Known IPs for this fingerprint
    screen_resolution = models.CharField(max_length=20, null=True, blank=True)
    timezone = models.CharField(max_length=50, null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    plugins = JSONField(default=list, blank=True)
    fonts = JSONField(default=list, blank=True)

    first_seen = models.DateTimeField(default=tz.now)
    last_seen = models.DateTimeField(default=tz.now)
    visit_count = models.IntegerField(default=1)

    # Risk
    is_suspicious = models.BooleanField(default=False)
    spoofing_detected = models.BooleanField(default=False)
    risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    class Meta:
        verbose_name = 'Device Fingerprint'
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['fingerprint_hash', 'tenant']),
            models.Index(fields=['user', 'last_seen']),
        ]

    def __str__(self):
        return f"Device: {self.fingerprint_hash[:12]}... | {self.device_type}"


class MultiAccountLink(TimeStampedModel):
    """একই আইপি বা ডিভাইসে কয়টি অ্যাকাউন্ট আছে তার ম্যাপিং।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='multi_account_links', null=True, blank=True)

    LINK_TYPES = [
        ('same_ip', 'Same IP Address'),
        ('same_device', 'Same Device Fingerprint'),
        ('same_email_domain', 'Same Email Domain'),
        ('same_phone', 'Same Phone Number'),
        ('similar_behavior', 'Similar Behavior Pattern'),
    ]

    primary_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='primary_account_links')
    linked_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='linked_account_links')
    link_type = models.CharField(max_length=30, choices=LINK_TYPES, null=True, blank=True)
    shared_identifier = models.CharField(max_length=255, null=True, blank=True)  # Shared IP/fingerprint
    confidence_score = models.FloatField(default=0.0)
    is_confirmed = models.BooleanField(default=False)
    is_suspicious = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Multi-Account Link'
        unique_together = ['primary_user', 'linked_user', 'link_type']
        ordering = ['-created_at']

    def __str__(self):
        return f"MultiAccount: {self.primary_user} <-> {self.linked_user} [{self.link_type}]"


class VelocityMetric(TimeStampedModel):
    """নির্দিষ্ট সময়ে ইউজার কতবার রিকোয়েস্ট করছে (Rate limit)।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='velocity_metrics', null=True, blank=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='velocity_metrics')

    action_type = models.CharField(max_length=50, db_index=True, null=True, blank=True)  # login, click, api_call
    window_seconds = models.IntegerField(default=60)
    request_count = models.IntegerField(default=1)
    threshold = models.IntegerField(default=60)
    exceeded = models.BooleanField(default=False, db_index=True)
    window_start = models.DateTimeField(default=tz.now)

    class Meta:
        verbose_name = 'Velocity Metric'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'action_type', 'window_start']),
        ]

    def __str__(self):
        return f"Velocity: {self.ip_address} | {self.action_type} | {self.request_count}/{self.threshold}"


# ==============================================================
# ৩. থ্রেট ইন্টেলিজেন্স ও ব্ল্যাকলিস্ট (Threat Intel)
# ==============================================================

class IPBlacklist(TimeStampedModel):
    """স্থায়ী বা অস্থায়ীভাবে ব্লক করা আইপি।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_ip_blacklists', null=True, blank=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    cidr = models.CharField(max_length=50, null=True, blank=True)  # Block entire subnet
    reason = models.CharField(max_length=50, choices=BlacklistReason.choices, null=True, blank=True)
    description = models.TextField(blank=True)

    is_permanent = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_blacklisted_ips')
    source = models.CharField(max_length=100, null=True, blank=True)  # manual, threat_feed, auto_ban

    class Meta:
        verbose_name = 'IP Blacklist'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'is_active']),
            models.Index(fields=['tenant', 'is_active']),
        ]

    def __str__(self):
        return f"Blacklist: {self.ip_address} | {self.reason} | active:{self.is_active}"

    def is_expired(self):
        if self.is_permanent:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return True
        return False


class IPWhitelist(TimeStampedModel):
    """বিশ্বস্ত আইপি বা সার্ভিস।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_ip_whitelists', null=True, blank=True)

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    cidr = models.CharField(max_length=50, null=True, blank=True)
    label = models.CharField(max_length=255, null=True, blank=True)  # "Office IP", "Payment Gateway", etc.
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_whitelisted_ips')

    class Meta:
        verbose_name = 'IP Whitelist'
        ordering = ['label']

    def __str__(self):
        return f"Whitelist: {self.ip_address or self.cidr} | {self.label}"


class ThreatFeedProvider(TimeStampedModel):
    """বিভিন্ন থ্রেট ফিড সোর্স (AbuseIPDB, VirusTotal)।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100, unique=True, null=True, blank=True)  # 'abuseipdb', 'virustotal'
    display_name = models.CharField(max_length=255, null=True, blank=True)
    api_endpoint = models.URLField(null=True, blank=True)
    api_key_env = models.CharField(max_length=100, null=True, blank=True)  # Env var name for API key
    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(default=1)

    # Stats
    last_sync = models.DateTimeField(null=True, blank=True)
    total_entries = models.BigIntegerField(default=0)
    daily_quota = models.IntegerField(default=1000)
    used_today = models.IntegerField(default=0)

    # Config
    config = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Threat Feed Provider'
        ordering = ['priority']

    def __str__(self):
        return f"{self.display_name} | active:{self.is_active}"


class MaliciousIPDatabase(TimeStampedModel):
    """ম্যালওয়্যার বা বটনেট আক্রান্ত আইপি ডাটা।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ip_address = models.GenericIPAddressField(db_index=True)
    threat_type = models.CharField(max_length=30, choices=ThreatType.choices, null=True, blank=True)
    threat_feed = models.ForeignKey(
        ThreatFeedProvider, on_delete=models.CASCADE,
        related_name='malicious_ips')

    confidence_score = models.FloatField(default=0.0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    is_active = models.BooleanField(default=True, db_index=True)
    first_reported = models.DateTimeField(default=tz.now)
    last_reported = models.DateTimeField(default=tz.now)
    report_count = models.IntegerField(default=1)
    additional_data = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Malicious IP'
        ordering = ['-last_reported']
        unique_together = ['ip_address', 'threat_type', 'threat_feed']

    def __str__(self):
        return f"Malicious: {self.ip_address} | {self.threat_type}"


# ==============================================================
# ৪. এআই এবং রিস্ক স্কোরিং (AI & Risk Scoring)
# ==============================================================

class UserRiskProfile(TimeStampedModel):
    """ইউজারের ওভারঅল রিস্ক লেভেল।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_user_risk_profiles', null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pi_risk_profile')

    overall_risk_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.VERY_LOW, null=True, blank=True)

    # Component scores
    ip_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    behavior_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    device_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    transaction_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    identity_risk_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])

    # Flags
    is_high_risk = models.BooleanField(default=False, db_index=True)
    is_under_review = models.BooleanField(default=False)
    vpn_usage_detected = models.BooleanField(default=False)
    multi_account_detected = models.BooleanField(default=False)

    # Counters
    fraud_attempts_count = models.IntegerField(default=0)
    successful_fraud_count = models.IntegerField(default=0)
    flagged_transactions = models.IntegerField(default=0)

    last_assessed = models.DateTimeField(default=tz.now)
    assessment_notes = JSONField(default=list, blank=True)

    class Meta:
        verbose_name = 'User Risk Profile'
        ordering = ['-overall_risk_score']
        indexes = [
            models.Index(fields=['overall_risk_score', 'is_high_risk']),
        ]

    def __str__(self):
        return f"RiskProfile: {self.user} | {self.overall_risk_score} ({self.risk_level})"


class RiskScoreHistory(TimeStampedModel):
    """সময়ের সাথে ইউজারের রিস্ক স্কোর পরিবর্তনের রেকর্ড।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='risk_score_histories', null=True, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='risk_score_history')
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    previous_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    new_score = models.IntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    change_reason = models.CharField(max_length=255, null=True, blank=True)
    triggered_by = models.CharField(max_length=50, null=True, blank=True)  # 'fraud_attempt', 'vpn_detected', etc.
    score_delta = models.IntegerField(default=0)  # new_score - previous_score

    class Meta:
        verbose_name = 'Risk Score History'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'created_at'])]

    def save(self, *args, **kwargs):
        self.score_delta = self.new_score - self.previous_score
        super().save(*args, **kwargs)

    def __str__(self):
        return f"RiskHistory: {self.user} | {self.previous_score} -> {self.new_score}"


class MLModelMetadata(TimeStampedModel):
    """আপনার ট্রেইন করা এআই মডেলের ভার্সন ও পারফরম্যান্স ডাটা।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    MODEL_TYPES = [
        ('risk_scoring', 'Risk Scoring Model'),
        ('anomaly_detection', 'Anomaly Detection'),
        ('vpn_detection', 'VPN Detection'),
        ('bot_detection', 'Bot Detection'),
        ('fraud_classification', 'Fraud Classification'),
    ]

    name = models.CharField(max_length=100, null=True, blank=True)
    version = models.CharField(max_length=20, null=True, blank=True)
    model_type = models.CharField(max_length=50, choices=MODEL_TYPES, null=True, blank=True)
    is_active = models.BooleanField(default=False, db_index=True)
    is_default = models.BooleanField(default=False)

    # Performance metrics
    accuracy = models.FloatField(null=True, blank=True)
    precision = models.FloatField(null=True, blank=True)
    recall = models.FloatField(null=True, blank=True)
    f1_score = models.FloatField(null=True, blank=True)
    auc_roc = models.FloatField(null=True, blank=True)
    false_positive_rate = models.FloatField(null=True, blank=True)

    # Training info
    training_data_size = models.BigIntegerField(default=0)
    training_duration_seconds = models.FloatField(null=True, blank=True)
    trained_at = models.DateTimeField(null=True, blank=True)
    model_file_path = models.CharField(max_length=500, null=True, blank=True)

    # Feature importance
    features = JSONField(default=list, blank=True)
    hyperparameters = JSONField(default=dict, blank=True)
    metadata = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'ML Model Metadata'
        ordering = ['-trained_at']
        unique_together = ['name', 'version']

    def __str__(self):
        return f"ML Model: {self.name} v{self.version} | {self.model_type} | active:{self.is_active}"


class AnomalyDetectionLog(TimeStampedModel):
    """অস্বাভাবিক আচরণের রেকর্ড।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='anomaly_logs', null=True, blank=True)

    ANOMALY_TYPES = [
        ('velocity_spike', 'Velocity Spike'),
        ('geo_jump', 'Geographic Jump'),
        ('time_anomaly', 'Time-based Anomaly'),
        ('pattern_deviation', 'Pattern Deviation'),
        ('unusual_volume', 'Unusual Volume'),
        ('device_change', 'Device Change'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='anomaly_logs')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    anomaly_type = models.CharField(max_length=50, choices=ANOMALY_TYPES, null=True, blank=True)
    description = models.TextField(blank=True)
    anomaly_score = models.FloatField(default=0.0)
    detected_by_model = models.ForeignKey(
        MLModelMetadata, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='anomaly_detections')
    is_investigated = models.BooleanField(default=False)
    evidence = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Anomaly Detection Log'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['anomaly_type', 'anomaly_score'])]

    def __str__(self):
        return f"Anomaly: {self.anomaly_type} | score:{self.anomaly_score:.2f}"


# ==============================================================
# ৫. কনফিগারেশন ও রুলস (Config & Rules)
# ==============================================================

class FraudRule(TimeStampedModel):
    """আপনার কাস্টম ফ্রড ডিটেকশন লজিক বা রুলস।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_fraud_rules', null=True, blank=True)

    name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(blank=True)
    rule_code = models.CharField(max_length=50, unique=True, null=True, blank=True)

    CONDITIONS = [
        ('ip_risk_score_gt', 'IP Risk Score Greater Than'),
        ('vpn_detected', 'VPN Detected'),
        ('proxy_detected', 'Proxy Detected'),
        ('tor_detected', 'Tor Detected'),
        ('velocity_exceeded', 'Velocity Exceeded'),
        ('multi_account', 'Multiple Accounts Detected'),
        ('geo_mismatch', 'Geographic Mismatch'),
        ('blacklisted', 'IP Blacklisted'),
    ]

    ACTIONS = [
        ('flag', 'Flag for Review'),
        ('block', 'Block Request'),
        ('challenge', 'Issue CAPTCHA Challenge'),
        ('notify', 'Send Notification'),
        ('suspend', 'Suspend Account'),
    ]

    condition_type = models.CharField(max_length=50, choices=CONDITIONS, null=True, blank=True)
    condition_value = JSONField(default=dict, blank=True)
    action = models.CharField(max_length=30, choices=ACTIONS, null=True, blank=True)
    priority = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True, db_index=True)
    trigger_count = models.BigIntegerField(default=0)
    last_triggered = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'PI Fraud Rule'
        ordering = ['priority', 'name']

    def __str__(self):
        return f"Rule: {self.name} | {self.condition_type} -> {self.action}"


class AlertConfiguration(TimeStampedModel):
    """কখন কাকে নোটিফিকেশন পাঠানো হবে।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_alert_configs', null=True, blank=True)

    CHANNELS = [
        ('email', 'Email'),
        ('slack', 'Slack'),
        ('webhook', 'Webhook'),
        ('sms', 'SMS'),
        ('telegram', 'Telegram'),
    ]

    TRIGGERS = [
        ('high_risk_ip', 'High Risk IP Detected'),
        ('vpn_blocked', 'VPN Blocked'),
        ('fraud_detected', 'Fraud Detected'),
        ('anomaly_detected', 'Anomaly Detected'),
        ('blacklist_hit', 'Blacklist Hit'),
        ('ml_alert', 'ML Model Alert'),
    ]

    name = models.CharField(max_length=255, null=True, blank=True)
    trigger = models.CharField(max_length=50, choices=TRIGGERS, null=True, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNELS, null=True, blank=True)
    recipients = JSONField(default=list, blank=True)  # emails, slack channels, etc.
    webhook_url = models.URLField(null=True, blank=True)
    threshold_score = models.IntegerField(default=80)
    is_active = models.BooleanField(default=True)
    cooldown_minutes = models.IntegerField(default=60)
    last_sent = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Alert Configuration'
        ordering = ['name']

    def __str__(self):
        return f"Alert: {self.name} | {self.trigger} -> {self.channel}"


class IntegrationCredential(TimeStampedModel):
    """থার্ড পার্টি এপিআই (MaxMind, IPQualityScore) কি-সমূহ।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_integration_credentials', null=True, blank=True)

    SERVICES = [
        ('maxmind', 'MaxMind GeoIP2'),
        ('ipqualityscore', 'IPQualityScore'),
        ('abuseipdb', 'AbuseIPDB'),
        ('virustotal', 'VirusTotal'),
        ('shodan', 'Shodan'),
        ('alienvault', 'AlienVault OTX'),
        ('crowdsec', 'CrowdSec'),
        ('fraudlabspro', 'FraudLabsPro'),
        ('abstractapi', 'AbstractAPI'),
    ]

    service = models.CharField(max_length=50, choices=SERVICES, null=True, blank=True)
    api_key = models.CharField(max_length=500, null=True, blank=True)  # Should be encrypted in production
    account_id = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    daily_limit = models.IntegerField(default=1000)
    used_today = models.IntegerField(default=0)
    last_reset = models.DateField(null=True, blank=True)
    config = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Integration Credential'
        unique_together = ['tenant', 'service']

    def __str__(self):
        return f"Credential: {self.service} | active:{self.is_active}"


# ==============================================================
# ৬. অডিট ও পারফরম্যান্স (Audit & Logs)
# ==============================================================

class APIRequestLog(TimeStampedModel):
    """প্রতিটা এপিআই কল-এর ডিটেইলস।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_api_logs', null=True, blank=True)

    ip_address = models.GenericIPAddressField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_api_logs')

    endpoint = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    method = models.CharField(max_length=10, null=True, blank=True)
    status_code = models.IntegerField()
    response_time_ms = models.FloatField(null=True, blank=True)

    request_body = JSONField(default=dict, blank=True)
    response_summary = JSONField(default=dict, blank=True)
    user_agent = models.TextField(blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = 'API Request Log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ip_address', 'created_at']),
            models.Index(fields=['endpoint', 'status_code']),
        ]

    def __str__(self):
        return f"API: {self.method} {self.endpoint} | {self.status_code} | {self.ip_address}"


class PerformanceMetric(TimeStampedModel):
    """ডিটেকশন ইঞ্জিনের স্পিড ও রেসপন্স টাইম।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    METRIC_TYPES = [
        ('detection_latency', 'Detection Latency'),
        ('api_response_time', 'API Response Time'),
        ('cache_hit_rate', 'Cache Hit Rate'),
        ('detection_accuracy', 'Detection Accuracy'),
        ('throughput', 'Throughput (req/sec)'),
    ]

    metric_type = models.CharField(max_length=50, choices=METRIC_TYPES, null=True, blank=True)
    engine_name = models.CharField(max_length=100, null=True, blank=True)  # vpn_detector, tor_detector, etc.
    value = models.FloatField()
    unit = models.CharField(max_length=20, null=True, blank=True)  # ms, %, req/s
    recorded_at = models.DateTimeField(default=tz.now, db_index=True)
    metadata = JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Performance Metric'
        ordering = ['-recorded_at']

    def __str__(self):
        return f"Metric: {self.engine_name} | {self.metric_type}: {self.value}{self.unit}"


class SystemAuditTrail(TimeStampedModel):
    """সিস্টেমে কে কখন কী পরিবর্তন করেছে।"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.CASCADE,
        related_name='pi_audit_trails', null=True, blank=True)

    ACTIONS = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('blacklist', 'Added to Blacklist'),
        ('whitelist', 'Added to Whitelist'),
        ('rule_change', 'Rule Changed'),
        ('config_change', 'Configuration Changed'),
        ('manual_override', 'Manual Override'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pi_audit_trails')
    action = models.CharField(max_length=30, choices=ACTIONS, null=True, blank=True)
    model_name = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.CharField(max_length=100, null=True, blank=True)
    object_repr = models.CharField(max_length=500, null=True, blank=True)

    before_state = JSONField(default=dict, blank=True)
    after_state = JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = 'System Audit Trail'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'action', 'created_at']),
            models.Index(fields=['model_name', 'object_id']),
        ]

    def __str__(self):
        return f"Audit: {self.user} | {self.action} | {self.model_name}"
