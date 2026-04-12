from django.conf import settings
"""Blacklist models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class BlacklistEntry(AdvertiserPortalBaseModel):
    entry_type = models.CharField(max_length=20, db_index=True)
    value = models.CharField(max_length=500, db_index=True)
    reason = models.TextField()
    risk_score = models.FloatField(default=0.0)
    source = models.CharField(max_length=30, default='manual')
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    blocked_count = models.BigIntegerField(default=0)
    class Meta:
        ordering = ['-created_at']
        unique_together = [['entry_type', 'value']]
    def __str__(self):
        return f"Blacklist [{self.entry_type}] {self.value}"
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)


# Alias used by signals.py
IPBlacklist = BlacklistEntry


class BlacklistViolation(AdvertiserPortalBaseModel):
    """Record of a blacklist rule being triggered."""
    entry = models.ForeignKey(BlacklistEntry, on_delete=models.CASCADE, related_name='violations')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    action_taken = models.CharField(max_length=50, default='blocked')
    violated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-violated_at']

    def __str__(self):
        return f"Violation [{self.entry.entry_type}] {self.violated_at:%Y-%m-%d %H:%M}"


class BlacklistAppeal(AdvertiserPortalBaseModel):
    """Appeal submitted to remove an entry from the blacklist."""
    entry = models.ForeignKey(BlacklistEntry, on_delete=models.CASCADE, related_name='appeals')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        default='pending', db_index=True
    )
    reviewer_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Appeal [{self.status}] for {self.entry}"
