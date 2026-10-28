# engagement/models/referral.py
from django.db import models
from django.conf import settings
from .base import TenantModel, UserEngagementModel


class ReferralProgram(TenantModel):
    """Configuration for a referral campaign."""

    name              = models.CharField(max_length=200)
    referrer_reward   = models.DecimalField(max_digits=10, decimal_places=2, default=50)
    referee_reward    = models.DecimalField(max_digits=10, decimal_places=2, default=25)
    referrer_xp       = models.IntegerField(default=100)
    referee_xp        = models.IntegerField(default=50)
    max_referrals     = models.IntegerField(default=0)   # 0 = unlimited
    is_active         = models.BooleanField(default=True)
    starts_at         = models.DateTimeField(null=True, blank=True)
    ends_at           = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class Referral(TenantModel):
    """One successful referral link."""

    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("confirmed", "Confirmed"),
        ("rewarded",  "Rewarded"),
        ("invalid",   "Invalid"),
    ]

    program  = models.ForeignKey(ReferralProgram, on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="referrals")
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="engagement_referrals_made")
    referee  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="engagement_referrals_received")
    code     = models.CharField(max_length=20, db_index=True)
    status   = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    rewarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["referrer", "referee"]
        ordering        = ["-created_at"]

    def __str__(self):
        return f"{self.referrer} → {self.referee} ({self.status})"
