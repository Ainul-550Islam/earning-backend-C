# api/referral/models/fraud.py
# Fraud detection and prevention models
# ReferralFraudRule, ReferralFraudLog, ReferralBlacklist, SuspiciousReferral
# ============================================================

from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class ReferralFraudRule(models.Model):
    """
    Configurable fraud detection rules।
    Type: self_refer, device_match, ip_match, velocity, etc.
    Action: flag, block, hold_commission
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    RULE_TYPE_CHOICES = [
        ('self_refer', 'Self-Referral Detection'),
        ('device_match', 'Same Device'),
        ('ip_match', 'Same IP Address'),
        ('ip_subnet_match', 'Same IP Subnet'),
        ('email_domain', 'Suspicious Email Domain'),
        ('velocity', 'High Velocity (too many referrals quickly)'),
        ('new_account', 'Referred User is Brand New Account'),
        ('inactive_referral', 'Referred User Never Active'),
        ('multiple_accounts', 'Multiple Accounts Same User'),
        ('blacklisted', 'Blacklisted Pattern Match'),
        ('geo_mismatch', 'Geographic Mismatch'),
    ]
    rule_type = models.CharField(
        max_length=25, choices=RULE_TYPE_CHOICES, unique=True
    )

    name = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(blank=True, default='')

    ACTION_CHOICES = [
        ('flag', 'Flag as Suspicious (allow but mark)'),
        ('block', 'Block the Referral'),
        ('hold_commission', 'Allow but Hold Commission'),
        ('notify_admin', 'Notify Admin Only'),
        ('ban_user', 'Ban Referred User'),
    ]
    action = models.CharField(
        max_length=20, choices=ACTION_CHOICES, default='flag'
    )

    # Threshold for velocity rule (e.g. 20 referrals per hour)
    threshold = models.IntegerField(
        default=0,
        help_text="Threshold for velocity/count rules (0 = N/A)"
    )

    # Time window for velocity (in minutes)
    time_window_minutes = models.IntegerField(
        default=60,
        help_text="Time window for velocity rules (in minutes)"
    )

    # Fraud score points this rule adds when triggered
    fraud_score_points = models.IntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Points added to fraud score when this rule triggers"
    )

    is_active = models.BooleanField(default=True)
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority rules evaluated first"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-priority', 'rule_type']

    def __str__(self):
        return f"FraudRule({self.rule_type}: {self.action})"


class ReferralFraudLog(models.Model):
    """
    Fraud detection event log।
    প্রতিটি fraud check এর result log করা হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referral = models.ForeignKey(
        'referral.Referral',
        on_delete=models.CASCADE,
        related_name='fraud_logs'
    )

    rule = models.ForeignKey(
        ReferralFraudRule,
        on_delete=models.CASCADE,
        related_name='rule_triggered_logs'
    )

    # Fraud score at time of detection (0-100)
    fraud_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # What action was taken
    ACTION_TAKEN_CHOICES = [
        ('flagged', 'Flagged'),
        ('blocked', 'Blocked'),
        ('commission_held', 'Commission Held'),
        ('admin_notified', 'Admin Notified'),
        ('user_banned', 'User Banned'),
        ('ignored', 'Ignored (below threshold)'),
    ]
    action_taken = models.CharField(
        max_length=20, choices=ACTION_TAKEN_CHOICES, default='flagged'
    )

    # Evidence / details
    evidence = models.JSONField(
        default=dict,
        help_text="Fraud evidence details: IPs, device fingerprints, etc."
    )

    # Human-readable explanation
    explanation = models.CharField(max_length=500, blank=True, default='')

    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['referral', '-detected_at']),
            models.Index(fields=['rule']),
            models.Index(fields=['fraud_score']),
        ]

    def __str__(self):
        return (
            f"FraudLog(referral={self.referral_id} "
            f"rule={self.rule.rule_type} "
            f"score={self.fraud_score} "
            f"action={self.action_taken})"
        )


class ReferralBlacklist(models.Model):
    """
    Blacklisted patterns — IP, email, device fingerprint, etc।
    যদি এই patterns match করে তাহলে referral block/flag করা হয়।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    PATTERN_TYPE_CHOICES = [
        ('ip', 'IP Address'),
        ('ip_range', 'IP Range/CIDR'),
        ('email', 'Email Address'),
        ('email_domain', 'Email Domain'),
        ('device_fingerprint', 'Device Fingerprint'),
        ('username', 'Username Pattern'),
        ('phone', 'Phone Number'),
        ('referral_code', 'Referral Code'),
        ('vpn_asn', 'VPN/Proxy ASN'),
    ]
    pattern_type = models.CharField(
        max_length=20, choices=PATTERN_TYPE_CHOICES
    )

    # The actual pattern value
    pattern_value = models.CharField(
        max_length=500,
        help_text="e.g. '192.168.1.1', '@tempmail.com', 'suspicious_username'"
    )

    # Case-insensitive matching
    case_sensitive = models.BooleanField(default=False)

    # Is this a regex pattern?
    is_regex = models.BooleanField(default=False)

    SEVERITY_CHOICES = [
        ('low', 'Low — Flag only'),
        ('medium', 'Medium — Hold commission'),
        ('high', 'High — Block referral'),
        ('critical', 'Critical — Ban user'),
    ]
    severity = models.CharField(
        max_length=10, choices=SEVERITY_CHOICES, default='high'
    )

    reason = models.CharField(max_length=500, blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_referral_blacklist_entries'
    )

    # Hit count
    hit_count = models.IntegerField(default=0)
    last_hit_at = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Auto-expire this blacklist entry (null = permanent)"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'referral'
        indexes = [
            models.Index(fields=['pattern_type', 'is_active']),
            models.Index(fields=['pattern_value']),
        ]

    def __str__(self):
        return (
            f"Blacklist({self.pattern_type}: "
            f"{self.pattern_value[:50]} [{self.severity}])"
        )

    def record_hit(self):
        from django.utils import timezone
        self.hit_count += 1
        self.last_hit_at = timezone.now()
        self.save(update_fields=['hit_count', 'last_hit_at'])

    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at


class SuspiciousReferral(models.Model):
    """
    Admin review queue for suspicious referrals।
    Fraud detection থেকে flagged referral এখানে আসে।
    Admin review করে cleared/fraud mark করে।
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(app_label)s_%(class)s_tenant',
        db_index=True,
    )

    referral = models.OneToOneField(
        'referral.Referral',
        on_delete=models.CASCADE,
        related_name='suspicious_referral'
    )

    # Flags JSON: list of triggered rules
    # e.g. {"ip_match": true, "device_match": false, "velocity": true}
    flags = models.JSONField(
        default=dict,
        help_text="Triggered fraud rules"
    )

    # Aggregated fraud score
    fraud_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    # Evidence collected
    evidence = models.JSONField(
        default=dict,
        help_text="IP addresses, device fingerprints, browser data, etc."
    )

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('cleared', 'Cleared — Legitimate'),
        ('fraud', 'Confirmed Fraud'),
        ('partial_fraud', 'Partial Fraud (some commission held)'),
    ]
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending'
    )

    # Admin who reviewed
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_suspicious_referrals'
    )

    review_notes = models.TextField(blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Auto-detected at
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'referral'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['status', '-detected_at']),
            models.Index(fields=['fraud_score']),
        ]

    def __str__(self):
        return (
            f"SuspiciousReferral(referral={self.referral_id} "
            f"score={self.fraud_score} [{self.status}])"
        )

    def clear(self, admin_user, notes: str = ''):
        """Legitimate বলে mark করো।"""
        from django.utils import timezone
        self.status = 'cleared'
        self.reviewed_by = admin_user
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'review_notes', 'reviewed_at'])

        # Referral এর is_suspicious flag clear করো
        self.referral.is_suspicious = False
        self.referral.save(update_fields=['is_suspicious'])

    def mark_fraud(self, admin_user, notes: str = ''):
        """Fraud বলে confirm করো।"""
        from django.utils import timezone
        self.status = 'fraud'
        self.reviewed_by = admin_user
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save(update_fields=['status', 'reviewed_by', 'review_notes', 'reviewed_at'])

    def get_flag_list(self) -> list:
        """Triggered flags এর list।"""
        return [k for k, v in self.flags.items() if v]