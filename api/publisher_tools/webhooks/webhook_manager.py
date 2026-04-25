# api/publisher_tools/webhooks/webhook_manager.py
"""
Webhook Manager — Publisher event webhooks।
Real-time event notifications to publisher endpoints।
"""
import json
import hashlib
import hmac
import uuid
from decimal import Decimal
from datetime import timedelta
from typing import Dict, List, Optional
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from core.models import TimeStampedModel


class PublisherWebhook(TimeStampedModel):
    """
    Publisher-এর webhook endpoint configuration।
    কোন events receive করবে তার settings।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_publisherwebhook_tenant', db_index=True,
    )

    EVENT_CHOICES = [
        # Earning events
        ('earning.daily_finalized',    _('Daily Earning Finalized')),
        ('earning.adjusted',           _('Earning Adjusted')),
        # Invoice events
        ('invoice.created',            _('Invoice Created')),
        ('invoice.issued',             _('Invoice Issued')),
        ('invoice.paid',               _('Invoice Paid')),
        ('invoice.failed',             _('Payment Failed')),
        # Publisher events
        ('publisher.approved',         _('Publisher Approved')),
        ('publisher.suspended',        _('Publisher Suspended')),
        ('publisher.tier_changed',     _('Tier Changed')),
        ('publisher.kyc_approved',     _('KYC Approved')),
        ('publisher.kyc_rejected',     _('KYC Rejected')),
        # Site events
        ('site.approved',              _('Site Approved')),
        ('site.rejected',              _('Site Rejected')),
        ('site.quality_alert',         _('Site Quality Alert')),
        # App events
        ('app.approved',               _('App Approved')),
        ('app.rejected',               _('App Rejected')),
        # Ad Unit events
        ('ad_unit.created',            _('Ad Unit Created')),
        ('ad_unit.paused',             _('Ad Unit Paused')),
        # Fraud events
        ('fraud.high_risk_detected',   _('High Risk IVT Detected')),
        ('fraud.publisher_warned',     _('Publisher Fraud Warning')),
        # Performance events
        ('performance.milestone',      _('Revenue Milestone Reached')),
        ('performance.ecpm_drop',      _('eCPM Significant Drop')),
        # A/B Test events
        ('ab_test.winner_declared',    _('A/B Test Winner Declared')),
    ]

    STATUS_CHOICES = [
        ('active',   _('Active')),
        ('paused',   _('Paused')),
        ('failed',   _('Failed — Too Many Errors')),
        ('disabled', _('Disabled')),
    ]

    # ── Core ──────────────────────────────────────────────────────────────────
    publisher = models.ForeignKey(
        'publisher_tools.Publisher',
        on_delete=models.CASCADE,
        related_name='webhooks',
        verbose_name=_("Publisher"),
    )
    name = models.CharField(max_length=200, verbose_name=_("Webhook Name"))
    endpoint_url = models.URLField(verbose_name=_("Endpoint URL"), help_text=_("POST requests এই URL-এ যাবে"))
    secret_key = models.CharField(
        max_length=128, blank=True,
        verbose_name=_("Secret Key"),
        help_text=_("HMAC-SHA256 signature verify করার জন্য"),
    )

    # ── Event Subscription ────────────────────────────────────────────────────
    subscribed_events = models.JSONField(
        default=list,
        verbose_name=_("Subscribed Events"),
        help_text=_("['earning.daily_finalized', 'invoice.paid', ...]"),
    )
    subscribe_all = models.BooleanField(
        default=False,
        verbose_name=_("Subscribe to All Events"),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name=_("Status"),
        db_index=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # ── Request Config ────────────────────────────────────────────────────────
    timeout_seconds = models.IntegerField(default=10, verbose_name=_("Timeout (seconds)"))
    max_retries     = models.IntegerField(default=3, verbose_name=_("Max Retries"))
    retry_backoff   = models.BooleanField(default=True, verbose_name=_("Exponential Backoff"))
    custom_headers  = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Custom Headers"),
        help_text=_("{'X-API-Key': 'value', 'X-Publisher-ID': 'PUB001'}"),
    )

    # ── Statistics ────────────────────────────────────────────────────────────
    total_deliveries    = models.IntegerField(default=0)
    successful_deliveries = models.IntegerField(default=0)
    failed_deliveries   = models.IntegerField(default=0)
    consecutive_failures= models.IntegerField(default=0)
    last_delivery_at    = models.DateTimeField(null=True, blank=True)
    last_success_at     = models.DateTimeField(null=True, blank=True)
    last_failure_at     = models.DateTimeField(null=True, blank=True)
    last_failure_reason = models.TextField(blank=True)

    description = models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_publisher_webhooks'
        verbose_name = _('Publisher Webhook')
        verbose_name_plural = _('Publisher Webhooks')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['publisher', 'is_active'], name='idx_publisher_is_active_1655'),
            models.Index(fields=['status'], name='idx_status_1656'),
        ]

    def __str__(self):
        return f"{self.publisher.publisher_id} — {self.name} [{self.status}]"

    def save(self, *args, **kwargs):
        if not self.secret_key:
            self.secret_key = uuid.uuid4().hex + uuid.uuid4().hex
        super().save(*args, **kwargs)

    @property
    def success_rate(self):
        if self.total_deliveries > 0:
            return round(self.successful_deliveries / self.total_deliveries * 100, 2)
        return 0.0

    def is_subscribed_to(self, event_type: str) -> bool:
        """Specific event-এ subscribed কিনা check করে"""
        if self.subscribe_all:
            return True
        return event_type in self.subscribed_events

    def generate_signature(self, payload: str) -> str:
        """HMAC-SHA256 signature generate করে"""
        return hmac.new(
            self.secret_key.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def build_request_headers(self, payload: str, event_type: str) -> Dict:
        """Webhook request headers build করে"""
        headers = {
            'Content-Type': 'application/json',
            'X-Publisher-Tools-Event': event_type,
            'X-Publisher-Tools-Signature': f'sha256={self.generate_signature(payload)}',
            'X-Publisher-Tools-Delivery': uuid.uuid4().hex,
            'X-Publisher-Tools-Timestamp': str(int(timezone.now().timestamp())),
            'User-Agent': 'PublisherTools-Webhooks/1.0',
        }
        headers.update(self.custom_headers)
        return headers

    @transaction.atomic
    def record_delivery(self, success: bool, response_code: int = None, reason: str = ''):
        """Delivery result record করে"""
        self.total_deliveries += 1
        self.last_delivery_at = timezone.now()

        if success:
            self.successful_deliveries += 1
            self.consecutive_failures = 0
            self.last_success_at = timezone.now()
        else:
            self.failed_deliveries += 1
            self.consecutive_failures += 1
            self.last_failure_at = timezone.now()
            self.last_failure_reason = reason

            # Auto-disable after 10 consecutive failures
            if self.consecutive_failures >= 10:
                self.status = 'failed'
                self.is_active = False

        self.save()


class WebhookDeliveryLog(TimeStampedModel):
    """
    Webhook delivery log।
    প্রতিটি delivery attempt-এর detailed record।
    """

    tenant = models.ForeignKey(
        'tenants.Tenant', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='publisher_tools_webhooklog_tenant', db_index=True,
    )

    STATUS_CHOICES = [
        ('pending',   _('Pending')),
        ('success',   _('Success')),
        ('failed',    _('Failed')),
        ('retrying',  _('Retrying')),
        ('abandoned', _('Abandoned')),
    ]

    webhook     = models.ForeignKey(PublisherWebhook, on_delete=models.CASCADE, related_name='delivery_logs')
    delivery_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    event_type  = models.CharField(max_length=100, db_index=True)
    payload     = models.JSONField(verbose_name=_("Payload Sent"))
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)

    # ── Response ──────────────────────────────────────────────────────────────
    http_status_code = models.IntegerField(null=True, blank=True)
    response_body    = models.TextField(blank=True)
    response_time_ms = models.IntegerField(default=0, verbose_name=_("Response Time (ms)"))

    # ── Retry ─────────────────────────────────────────────────────────────────
    attempt_count   = models.IntegerField(default=1)
    max_attempts    = models.IntegerField(default=3)
    next_retry_at   = models.DateTimeField(null=True, blank=True)

    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message= models.TextField(blank=True)

    class Meta:
        db_table = 'publisher_tools_webhook_delivery_logs'
        verbose_name = _('Webhook Delivery Log')
        verbose_name_plural = _('Webhook Delivery Logs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['webhook', 'event_type', 'status'], name='idx_webhook_event_type_sta_1c4'),
            models.Index(fields=['delivery_id'], name='idx_delivery_id_1658'),
            models.Index(fields=['next_retry_at'], name='idx_next_retry_at_1659'),
        ]

    def __str__(self):
        return f"{self.event_type} → {self.webhook.endpoint_url[:50]} [{self.status}]"

    def schedule_retry(self, attempt: int):
        """Exponential backoff দিয়ে retry schedule করে"""
        delays = [60, 300, 900, 3600, 7200]  # 1min, 5min, 15min, 1hr, 2hr
        delay = delays[min(attempt - 1, len(delays) - 1)]
        self.next_retry_at = timezone.now() + timedelta(seconds=delay)
        self.status = 'retrying'
        self.attempt_count = attempt
        self.save()


def send_webhook_event(publisher, event_type: str, event_data: Dict) -> List[WebhookDeliveryLog]:
    """
    Publisher-এর সব active webhooks-এ event পাঠায়।
    Returns: list of delivery logs created।
    """
    import requests as http_requests

    webhooks = PublisherWebhook.objects.filter(
        publisher=publisher,
        is_active=True,
        status='active',
    )

    delivery_logs = []
    for webhook in webhooks:
        if not webhook.is_subscribed_to(event_type):
            continue

        payload = {
            'event':      event_type,
            'timestamp':  timezone.now().isoformat(),
            'publisher_id': publisher.publisher_id,
            'data':       event_data,
        }
        payload_str = json.dumps(payload, default=str)
        headers = webhook.build_request_headers(payload_str, event_type)

        log = WebhookDeliveryLog.objects.create(
            webhook=webhook,
            event_type=event_type,
            payload=payload,
            status='pending',
            max_attempts=webhook.max_retries,
        )

        try:
            import time
            start_time = time.time()
            response = http_requests.post(
                webhook.endpoint_url,
                data=payload_str,
                headers=headers,
                timeout=webhook.timeout_seconds,
            )
            elapsed_ms = int((time.time() - start_time) * 1000)

            success = 200 <= response.status_code < 300
            log.http_status_code = response.status_code
            log.response_body    = response.text[:2000]
            log.response_time_ms = elapsed_ms
            log.status           = 'success' if success else 'failed'
            log.delivered_at     = timezone.now()

            if not success:
                log.error_message = f'HTTP {response.status_code}: {response.text[:500]}'
                if log.attempt_count < webhook.max_retries:
                    log.schedule_retry(log.attempt_count + 1)
            else:
                log.save()

            webhook.record_delivery(success=success, response_code=response.status_code)

        except Exception as e:
            log.status = 'failed'
            log.error_message = str(e)
            if log.attempt_count < webhook.max_retries:
                log.schedule_retry(log.attempt_count + 1)
            else:
                log.status = 'abandoned'
                log.save()
            webhook.record_delivery(success=False, reason=str(e))

        delivery_logs.append(log)

    return delivery_logs


def build_earning_event_payload(earning) -> Dict:
    """Earning event payload build করে"""
    return {
        'earning_id':     str(earning.id),
        'date':           str(earning.date),
        'earning_type':   earning.earning_type,
        'publisher_id':   earning.publisher.publisher_id,
        'ad_unit_id':     earning.ad_unit.unit_id if earning.ad_unit else None,
        'site_id':        earning.site.site_id if earning.site else None,
        'country':        earning.country,
        'impressions':    earning.impressions,
        'clicks':         earning.clicks,
        'publisher_revenue': float(earning.publisher_revenue),
        'ecpm':           float(earning.ecpm),
        'status':         earning.status,
    }


def build_invoice_event_payload(invoice) -> Dict:
    """Invoice event payload build করে"""
    return {
        'invoice_number': invoice.invoice_number,
        'publisher_id':   invoice.publisher.publisher_id,
        'period_start':   str(invoice.period_start),
        'period_end':     str(invoice.period_end),
        'gross_revenue':  float(invoice.gross_revenue),
        'net_payable':    float(invoice.net_payable),
        'currency':       invoice.currency,
        'status':         invoice.status,
        'paid_at':        invoice.paid_at.isoformat() if invoice.paid_at else None,
        'payment_reference': invoice.payment_reference,
    }
