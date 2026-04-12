"""Webhook models."""
from django.db import models
from django.utils import timezone
from ..models import AdvertiserPortalBaseModel


class Webhook(AdvertiserPortalBaseModel):
    advertiser = models.ForeignKey('advertiser_portal.Advertiser', on_delete=models.CASCADE, related_name='webhooks')
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    secret = models.CharField(max_length=128, blank=True)
    events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True, db_index=True)
    success_count = models.BigIntegerField(default=0)
    failure_count = models.BigIntegerField(default=0)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Webhook {self.name}"


class WebhookEvent(AdvertiserPortalBaseModel):
    event_type = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return self.event_type


class WebhookDelivery(AdvertiserPortalBaseModel):
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField(max_length=100, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    response_status_code = models.IntegerField(null=True, blank=True)
    attempt_count = models.IntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Delivery {self.webhook_id} [{self.status}]"


class WebhookRetry(AdvertiserPortalBaseModel):
    delivery = models.ForeignKey(WebhookDelivery, on_delete=models.CASCADE, related_name='retries')
    attempt_number = models.IntegerField()
    attempted_at = models.DateTimeField(default=timezone.now)
    success = models.BooleanField(default=False)
    class Meta:
        ordering = ['attempt_number']
    def __str__(self):
        return f"Retry #{self.attempt_number}"


class WebhookLog(AdvertiserPortalBaseModel):
    webhook = models.ForeignKey(Webhook, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50)
    details = models.JSONField(default=dict)
    logged_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['-logged_at']
    def __str__(self):
        return f"WebhookLog {self.action}"


class WebhookQueue(AdvertiserPortalBaseModel):
    delivery = models.OneToOneField(WebhookDelivery, on_delete=models.CASCADE)
    priority = models.IntegerField(default=5)
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True)
    class Meta:
        ordering = ['priority', 'scheduled_at']
    def __str__(self):
        return f"Queue {self.delivery_id}"


class WebhookSecurity(AdvertiserPortalBaseModel):
    webhook = models.OneToOneField(Webhook, on_delete=models.CASCADE, related_name='security')
    ip_whitelist = models.JSONField(default=list)
    require_https = models.BooleanField(default=True)
    hmac_algorithm = models.CharField(max_length=20, default='sha256')
    def __str__(self):
        return f"WebhookSecurity {self.webhook_id}"
