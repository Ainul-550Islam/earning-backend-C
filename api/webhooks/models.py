# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
models.py: Core data models for the webhook infrastructure.

Models:
    WebhookEndpoint  — A registered HTTP target that receives dispatches.
    WebhookSubscription — Maps an endpoint to one or more event types.
    WebhookDeliveryLog  — Immutable record of every dispatch attempt.
"""

import uuid
import secrets
import logging

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator

from core.models import TimeStampedModel
from .constants import (
    DeliveryStatus,
    EndpointStatus,
    EventType,
    HttpMethod,
    MAX_RETRY_ATTEMPTS,
)

logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _generate_secret_key() -> str:
    """
    Ainul Enterprise Engine — Auto-generate a cryptographically secure
    HMAC signing secret.  Format: `whsec_<32-byte-hex>`.
    """
    return f"whsec_{secrets.token_hex(32)}"


def _empty_list():
    return []


def _empty_dict():
    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpoint(TimeStampedModel):
    """
    Ainul Enterprise Engine — A registered webhook target URL.

    Each user (or tenant) can register multiple endpoints. Every endpoint
    has an auto-generated HMAC secret used to sign outgoing payloads.
    Supports per-endpoint HTTP method, custom headers, and retry policy.
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Tenant"),
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="webhook_endpoints",
        verbose_name=_("Owner"),
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    label = models.CharField(
        max_length=120,
        verbose_name=_("Label"),
        help_text=_("Human-readable name for this endpoint."),
    )
    target_url = models.URLField(
        max_length=2048,
        validators=[URLValidator(schemes=["https", "http"])],
        verbose_name=_("Target URL"),
        help_text=_("The HTTPS endpoint that will receive dispatched payloads."),
    )
    http_method = models.CharField(
        max_length=8,
        choices=HttpMethod.choices,
        default=HttpMethod.POST,
        verbose_name=_("HTTP Method"),
    )

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key = models.CharField(
        max_length=128,
        default=_generate_secret_key,
        editable=False,
        verbose_name=_("Signing Secret"),
        help_text=_(
            "HMAC-SHA256 secret auto-generated per endpoint. "
            "Sent as X-Webhook-Signature on every dispatch."
        ),
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=EndpointStatus.choices,
        default=EndpointStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Status"),
    )
    custom_headers = models.JSONField(
        default=_empty_dict,
        blank=True,
        verbose_name=_("Custom Headers"),
        help_text=_("Additional HTTP headers injected into every dispatch request."),
    )
    description = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Description"),
    )
    version = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Schema Version"),
    )

    # ── Retry Policy ──────────────────────────────────────────────────────────
    max_retries = models.PositiveSmallIntegerField(
        default=MAX_RETRY_ATTEMPTS,
        verbose_name=_("Max Retries"),
    )
    verify_ssl = models.BooleanField(
        default=True,
        verbose_name=_("Verify SSL"),
    )

    # ── Stats (denormalised for fast reads) ───────────────────────────────────
    total_deliveries   = models.PositiveIntegerField(default=0)
    success_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries  = models.PositiveIntegerField(default=0)
    last_triggered_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = _("Webhook Endpoint")
        verbose_name_plural = _("Webhook Endpoints")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name='idx_owner_status_1891'),
            models.Index(fields=["tenant", "status"], name='idx_tenant_status_1892'),
        ]

    def __str__(self):
        return f"[{self.status.upper()}] {self.label} → {self.target_url}"

    def rotate_secret(self) -> str:
        """
        Ainul Enterprise Engine — Rotate the signing secret.
        Returns the new secret. Caller must save the instance.
        """
        self.secret_key = _generate_secret_key()
        logger.info("Secret rotated for endpoint %s (owner=%s)", self.pk, self.owner_id)
        return self.secret_key

    @property
    def success_rate(self) -> float:
        if self.total_deliveries == 0:
            return 0.0
        return round((self.success_deliveries / self.total_deliveries) * 100, 2)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SUBSCRIPTION  (Event Filtering)
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSubscription(TimeStampedModel):
    """
    Ainul Enterprise Engine — Event Subscription Filter.

    Binds a WebhookEndpoint to a specific EventType.  An endpoint only
    receives dispatches for event types it has active subscriptions for.
    One endpoint can subscribe to many event types independently.
    """

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("Endpoint"),
    )
    event_type = models.CharField(
        max_length=80,
        choices=EventType.choices,
        db_index=True,
        verbose_name=_("Event Type"),
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Active"),
    )
    filters = models.JSONField(
        default=_empty_dict,
        blank=True,
        verbose_name=_("Payload Filters"),
        help_text=_(
            "Optional key-value pairs to filter dispatches. "
            'Example: {"currency": "BDT", "amount_gte": 100}'
        ),
    )

    class Meta:
        verbose_name        = _("Webhook Subscription")
        verbose_name_plural = _("Webhook Subscriptions")
        unique_together     = ("endpoint", "event_type")
        ordering            = ["event_type"]
        indexes = [
            models.Index(fields=["event_type", "is_active"], name='idx_event_type_is_active_1893'),
        ]

    def __str__(self):
        state = "✓" if self.is_active else "✗"
        return f"{state} {self.event_type} → {self.endpoint.label}"


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK DELIVERY LOG
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryLog(TimeStampedModel):
    """
    Ainul Enterprise Engine — Immutable delivery attempt record.

    Every outbound dispatch (initial and retry) creates a DeliveryLog row.
    Never modified after creation except for status, response fields, and
    retry metadata which are updated in-place by the dispatch engine.
    """

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="delivery_logs",
        verbose_name=_("Endpoint"),
    )
    event_type = models.CharField(
        max_length=80,
        choices=EventType.choices,
        db_index=True,
        verbose_name=_("Event Type"),
    )

    # ── Dispatch Details ──────────────────────────────────────────────────────
    delivery_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name=_("Delivery ID"),
        help_text=_("Unique ID sent as X-Webhook-Delivery-ID header."),
    )
    payload = models.JSONField(
        default=_empty_dict,
        verbose_name=_("Dispatched Payload"),
    )
    request_headers = models.JSONField(
        default=_empty_dict,
        blank=True,
        verbose_name=_("Request Headers Sent"),
    )
    signature = models.CharField(
        max_length=256,
        blank=True,
        default="",
        verbose_name=_("HMAC Signature"),
    )

    # ── Response ──────────────────────────────────────────────────────────────
    http_status_code = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name=_("HTTP Status Code"),
    )
    response_body = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Response Body"),
        help_text=_("First 4096 chars of the response body."),
    )
    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Response Time (ms)"),
    )
    error_message = models.TextField(
        blank=True,
        default="",
        verbose_name=_("Error Message"),
    )

    # ── Status & Retry ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.PENDING,
        db_index=True,
        verbose_name=_("Delivery Status"),
    )
    attempt_number = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_("Attempt Number"),
    )
    max_attempts = models.PositiveSmallIntegerField(
        default=MAX_RETRY_ATTEMPTS,
        verbose_name=_("Max Attempts"),
    )
    next_retry_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Next Retry At"),
    )
    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Dispatched At"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Completed At"),
    )

    class Meta:
        verbose_name        = _("Webhook Delivery Log")
        verbose_name_plural = _("Webhook Delivery Logs")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["endpoint", "status"], name='idx_endpoint_status_1894'),
            models.Index(fields=["event_type", "status"], name='idx_event_type_status_1895'),
            models.Index(fields=["status", "next_retry_at"], name='idx_status_next_retry_at_1896'),
            models.Index(fields=["delivery_id"], name='idx_delivery_id_1897'),
        ]

    def __str__(self):
        return (
            f"[{self.status.upper()}] {self.event_type} "
            f"→ {self.endpoint.label} (attempt {self.attempt_number})"
        )

    @property
    def is_retryable(self) -> bool:
        """True if this log entry can be retried."""
        return (
            self.status in (DeliveryStatus.FAILED, DeliveryStatus.RETRYING)
            and self.attempt_number < self.max_attempts
        )

    @property
    def was_successful(self) -> bool:
        return (
            self.status == DeliveryStatus.SUCCESS
            and self.http_status_code is not None
            and 200 <= self.http_status_code < 300
        )
