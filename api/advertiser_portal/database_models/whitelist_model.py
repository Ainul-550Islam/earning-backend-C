"""Whitelist models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class TrustLevel(AdvertiserPortalBaseModel):
    name = models.CharField(max_length=100, unique=True)
    level = models.IntegerField(unique=True)
    description = models.TextField(blank=True)
    class Meta:
        ordering = ['level']
    def __str__(self):
        return f"TrustLevel {self.name} (L{self.level})"


class WhitelistEntry(AdvertiserPortalBaseModel):
    entry_type = models.CharField(max_length=20, db_index=True)
    value = models.CharField(max_length=500, db_index=True)
    trust_level = models.ForeignKey(TrustLevel, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField()
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']
        unique_together = [['entry_type', 'value']]
    def __str__(self):
        return f"Whitelist [{self.entry_type}] {self.value}"
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)


class VerificationRequest(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='verification_requests')
    request_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    submitted_documents = models.JSONField(default=list)
    reviewer_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"VerificationRequest {self.advertiser_id} [{self.status}]"
