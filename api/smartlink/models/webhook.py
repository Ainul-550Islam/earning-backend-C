"""
SmartLink Webhook System
Publishers register HTTPS endpoints; we deliver real-time event payloads.
Events: click, conversion, cap_reached, fraud_spike, ab_winner, payout_ready
"""
import uuid
import hashlib
import hmac
import json
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()

WEBHOOK_EVENTS = [
    ('click',           'Click recorded'),
    ('conversion',      'Conversion attributed'),
    ('cap_reached',     'Offer cap exhausted'),
    ('fraud_spike',     'Fraud spike detected'),
    ('ab_winner',       'A/B test winner declared'),
    ('payout_ready',    'Payout calculated and ready'),
    ('smartlink_broken','SmartLink health check failed'),
    ('domain_verified', 'Custom domain verified'),
    ('tier_changed',    'Publisher tier changed'),
]


class WebhookEndpoint(models.Model):
    """
    A publisher-configured HTTPS endpoint for receiving SmartLink events.
    Supports per-event subscription and IP filtering.
    """
    publisher      = models.ForeignKey(
        User, on_delete=models.CASCADE,
        related_name='smartlink_webhook_endpoints',
    )
    url            = models.URLField(_('Endpoint URL'), max_length=500)
    secret         = models.CharField(
        _('Signing secret'), max_length=100, blank=True,
        help_text=_('Used to sign payload with HMAC-SHA256 (X-SmartLink-Signature header).')
    )
    events         = models.JSONField(
        _('Subscribed events'), default=list,
        help_text=_('e.g. ["click","conversion","cap_reached"]. Empty = all events.')
    )
    is_active      = models.BooleanField(default=True)
    description    = models.CharField(max_length=200, blank=True)
    headers        = models.JSONField(
        _('Custom headers'), default=dict, blank=True,
        help_text=_('Extra HTTP headers to include in delivery. e.g. {"Authorization": "Bearer …"}')
    )
    timeout_seconds  = models.PositiveSmallIntegerField(default=10)
    retry_count      = models.PositiveSmallIntegerField(default=3)
    success_count    = models.PositiveBigIntegerField(default=0)
    failure_count    = models.PositiveBigIntegerField(default=0)
    last_delivery_at = models.DateTimeField(null=True, blank=True)
    last_success_at  = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'sl_webhook_endpoint'
        verbose_name = _('Webhook Endpoint')
        ordering     = ['-created_at']

    def __str__(self):
        return f"{self.publisher.username} → {self.url[:60]}"

    def subscribes_to(self, event: str) -> bool:
        """Check if this endpoint wants to receive the given event."""
        if not self.events:
            return True  # empty list = subscribe to all
        return event in self.events

    def sign_payload(self, payload_bytes: bytes) -> str:
        """
        Generate HMAC-SHA256 signature for the payload.
        Receivers verify: HMAC-SHA256(secret, body) == X-SmartLink-Signature
        """
        if not self.secret:
            return ''
        return hmac.new(
            self.secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

    def build_headers(self, payload_bytes: bytes) -> dict:
        """Build the full set of delivery headers including signature."""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'SmartLink-Webhook/1.0',
        }
        sig = self.sign_payload(payload_bytes)
        if sig:
            headers['X-SmartLink-Signature'] = f'sha256={sig}'
        headers.update(self.headers)
        return headers


class WebhookDeliveryLog(models.Model):
    """
    Audit log of every webhook delivery attempt.
    Stores request + response for debugging and replay.
    Auto-purged after 30 days via cleanup_tasks.py.
    """

    class Status(models.TextChoices):
        SUCCESS  = 'success',  _('Success (2xx)')
        FAILED   = 'failed',   _('Failed (non-2xx or timeout)')
        RETRYING = 'retrying', _('Retrying')
        DROPPED  = 'dropped',  _('Dropped (max retries exceeded)')

    endpoint       = models.ForeignKey(
        WebhookEndpoint, on_delete=models.CASCADE,
        related_name='deliveries',
    )
    delivery_id    = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    event          = models.CharField(max_length=50, db_index=True)
    payload        = models.JSONField()
    status         = models.CharField(
        max_length=10, choices=Status.choices, default=Status.FAILED, db_index=True
    )
    http_status    = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body  = models.TextField(blank=True)
    latency_ms     = models.FloatField(null=True, blank=True)
    attempt        = models.PositiveSmallIntegerField(default=1)
    error_message  = models.TextField(blank=True)
    next_retry_at  = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table     = 'sl_webhook_delivery_log'
        verbose_name = _('Webhook Delivery Log')
        ordering     = ['-created_at']
        indexes      = [
            models.Index(fields=['endpoint', 'status']),
            models.Index(fields=['event', 'created_at']),
        ]

    def __str__(self):
        return f"Delivery [{self.event}] → {self.endpoint.url[:40]} [{self.status}]"
