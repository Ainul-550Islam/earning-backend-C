# engagement/models/anti_cheat.py
"""
Anti-Cheat & Fraud Detection System
Monitors suspicious patterns: too-fast spins, impossible streaks,
mass referral abuse, abnormal coin accumulation.
Auto-flags accounts for review.
"""
from django.db import models
from django.conf import settings
from .base import TenantModel, UserEngagementModel


class AntiCheatRule(TenantModel):
    """A rule definition for what constitutes suspicious behaviour."""
    RULE_TYPES = [
        ("rate_limit",        "Action Rate Limit"),
        ("velocity_check",    "Coin Velocity Check"),
        ("ip_duplicate",      "Duplicate IP Check"),
        ("referral_abuse",    "Referral Abuse"),
        ("device_spoofing",   "Device Spoofing"),
        ("pattern_anomaly",   "Pattern Anomaly"),
    ]
    slug            = models.SlugField(max_length=100, unique=True)
    name            = models.CharField(max_length=200)
    rule_type       = models.CharField(max_length=20, choices=RULE_TYPES)
    description     = models.TextField(blank=True)
    threshold       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    window_seconds  = models.IntegerField(default=3600)    # observation window
    action          = models.CharField(max_length=20,
                                       choices=[("flag","Flag"),("warn","Warn"),("suspend","Suspend"),("ban","Ban")],
                                       default="flag")
    severity        = models.IntegerField(default=1)       # 1=low, 2=medium, 3=high, 4=critical
    is_active       = models.BooleanField(default=True)

    class Meta:
        ordering = ["-severity", "slug"]

    def __str__(self):
        return f"[Rule] {self.name} ({self.rule_type})"


class AntiCheatLog(UserEngagementModel):
    """A record of a rule trigger for a specific user."""
    STATUS_CHOICES = [
        ("pending",  "Pending Review"),
        ("cleared",  "Cleared – Not Suspicious"),
        ("warned",   "Warning Issued"),
        ("suspended","Account Suspended"),
        ("banned",   "Account Banned"),
    ]
    rule           = models.ForeignKey(AntiCheatRule, on_delete=models.PROTECT, related_name="logs")
    status         = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    severity       = models.IntegerField(default=1)
    details        = models.JSONField(default=dict)    # evidence payload
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    device_id      = models.CharField(max_length=200, blank=True)
    user_agent     = models.CharField(max_length=500, blank=True)
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="anticheat_reviews",
    )
    reviewed_at    = models.DateTimeField(null=True, blank=True)
    notes          = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes  = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "severity"]),
        ]

    def __str__(self):
        return f"[{self.severity}★] {self.rule.name} – {self.user} ({self.status})"


class UserRiskScore(UserEngagementModel):
    """Aggregated risk score for a user (updated by Celery task)."""
    score          = models.IntegerField(default=0)   # 0–100, higher = riskier
    flag_count     = models.IntegerField(default=0)
    last_flag_at   = models.DateTimeField(null=True, blank=True)
    is_suspended   = models.BooleanField(default=False)
    suspended_at   = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)

    class Meta:
        unique_together = []

    def __str__(self):
        return f"{self.user} risk={self.score} flags={self.flag_count}"


class IPReputation(TenantModel):
    """Known bad / good IP addresses."""
    ip_address  = models.GenericIPAddressField(unique=True)
    reputation  = models.CharField(max_length=10,
                                   choices=[("good","Good"),("neutral","Neutral"),("bad","Bad"),("blocked","Blocked")],
                                   default="neutral")
    reason      = models.CharField(max_length=200, blank=True)
    hit_count   = models.IntegerField(default=0)
    last_seen   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-hit_count"]
