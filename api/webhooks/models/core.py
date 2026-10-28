# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Webhook Dispatch System
models/core.py: Core data models for the webhook infrastructure.

Models:
    WebhookEndpoint     — A registered HTTP target that receives dispatches.
    WebhookSubscription — Maps an endpoint to one or more event types.
    WebhookDeliveryLog  — Immutable record of every dispatch attempt.

CANONICAL MODEL — all views, serializers, and services use these classes.

FIXES APPLIED:
    [CORE-01] target_url had two separate `validators=` kwargs — Python
              silently discards the first.  validate_webhook_url was therefore
              NEVER called.  Fixed: merged into a single validators list so
              both validate_webhook_url AND URLValidator always run.
"""

import uuid
import secrets
import logging

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from ..validators import validate_webhook_url
from ..choices import WebhookStatus, DeliveryStatus
from ..crypto import EncryptedCharField

User = get_user_model()
logger = logging.getLogger("ainul.webhooks")


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _generate_secret_key() -> str:
    """Auto-generate a cryptographically secure HMAC signing secret."""
    return f"whsec_{secrets.token_hex(32)}"


def _empty_dict():
    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK ENDPOINT
# ─────────────────────────────────────────────────────────────────────────────

class WebhookEndpoint(models.Model):
    """
    Ainul Enterprise Engine — A registered webhook target URL.

    Each user can register multiple endpoints.  Every endpoint has an
    auto-generated HMAC secret used to sign outgoing payloads.  Supports
    per-endpoint HTTP method, custom headers, and retry policy.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="webhooks_owned_endpoints",
        verbose_name=_("Owner"),
    )

    # ── Identity ──────────────────────────────────────────────────────────────
    label = models.CharField(
        max_length=120,
        verbose_name=_("Label"),
        help_text=_("Human-readable name for this endpoint."),
    )

    # FIX [CORE-01]: Previously two separate `validators=` keyword arguments
    # existed on this field.  Python uses the LAST value when the same kwarg
    # appears twice, so validate_webhook_url was silently discarded and only
    # URLValidator ran.  Both validators are now combined in a single list so
    # both are guaranteed to execute on every full_clean() call.
    target_url = models.URLField(
        validators=[
            validate_webhook_url,
            URLValidator(schemes=["https", "http"]),
        ],
        max_length=2048,
        verbose_name=_("Target URL"),
        help_text=_("The HTTPS endpoint that will receive dispatched payloads."),
    )

    http_method = models.CharField(
        max_length=8,
        choices=[("POST", "POST"), ("PUT", "PUT"), ("PATCH", "PATCH")],
        default="POST",
        verbose_name=_("HTTP Method"),
    )

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key = EncryptedCharField(
        # SECURITY FIX: was a plain CharField (plaintext at rest). max_length
        # widened from 128 -> 512: a Fernet-encrypted token is longer than
        # the raw secret it wraps (base64 + IV + HMAC + our "enc:v1:" prefix).
        max_length=512,
        default=_generate_secret_key,
        editable=False,
        verbose_name=_("Signing Secret"),
        help_text=_(
            "HMAC-SHA256 secret auto-generated per endpoint. "
            "Sent as X-Webhook-Signature on every dispatch. "
            "Encrypted at rest; decrypted transparently on access."
        ),
    )

    # ── Status ────────────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=WebhookStatus.CHOICES,
        default=WebhookStatus.ACTIVE,
        db_index=True,
        verbose_name=_("Status"),
    )

    # ── Metadata ──────────────────────────────────────────────────────────────
    custom_headers = models.JSONField(
        default=_empty_dict,
        blank=True,
        verbose_name=_("Custom Headers"),
        help_text=_("Additional HTTP headers injected into every dispatch request."),
    )
    description = models.TextField(blank=True, default="", verbose_name=_("Description"))
    version     = models.PositiveSmallIntegerField(default=1, verbose_name=_("Schema Version"))

    payload_template = models.ForeignKey(
        "WebhookTemplate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="endpoints",
        verbose_name=_("Payload Template"),
        help_text=_("Optional template applied to the payload before dispatch."),
    )

    # ── Retry Policy ──────────────────────────────────────────────────────────
    max_retries = models.PositiveSmallIntegerField(default=3, verbose_name=_("Max Retries"))
    verify_ssl  = models.BooleanField(default=True, verbose_name=_("Verify SSL"))

    # ── Stats (denormalised for fast reads) ───────────────────────────────────
    total_deliveries   = models.PositiveIntegerField(default=0)
    success_deliveries = models.PositiveIntegerField(default=0)
    failed_deliveries  = models.PositiveIntegerField(default=0)
    last_triggered_at  = models.DateTimeField(null=True, blank=True)
    suspension_reason  = models.TextField(blank=True, default="")

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "webhook_endpoints"
        verbose_name        = _("Webhook Endpoint")
        verbose_name_plural = _("Webhook Endpoints")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"], name="idx_owner_status_1905"),
            models.Index(fields=["status"],           name="idx_status_1906"),
            models.Index(fields=["created_at"],       name="idx_created_at_1907"),
        ]

    def __str__(self):
        return f"[{self.status.upper()}] {self.label} -> {self.target_url}"

    def clean(self):
        super().clean()
        if self.target_url and not self.target_url.startswith(("http://", "https://")):
            raise ValidationError("Target URL must start with http:// or https://")
        if self.max_retries > 10:
            raise ValidationError("max_retries must be between 0 and 10.")

    # FIX: clean() above was defined but never called anywhere (Django
    # doesn't call it automatically on save() - only full_clean() does,
    # and nothing in the codebase called that either). Wired it in here.
    # Runs on create and on unrestricted saves; skipped for narrow
    # save(update_fields=[...]) calls (used throughout this codebase for
    # status-only transitions - see views.py, tasks/*) so an update to one
    # field is never blocked by a pre-existing bad value sitting in some
    # other, untouched field. clean_fields()/validate_unique() are skipped
    # too (exclude=all field names) since DRF's serializer layer already
    # covers per-field/uniqueness checks on the API path this model is
    # actually written through; this only adds the whole-object clean()
    # business rules above, which nothing else runs.
    def save(self, *args, **kwargs):
        if self.pk is None or not kwargs.get("update_fields"):
            self.clean()
        super().save(*args, **kwargs)

    # ── Business logic ────────────────────────────────────────────────────────

    def rotate_secret(self) -> str:
        """
        Ainul Enterprise Engine — Rotate the signing secret.
        Returns the new secret.  Caller must save the instance.
        """
        self.secret_key = _generate_secret_key()
        logger.info("Secret rotated for endpoint %s (owner=%s)", self.pk, self.owner_id)
        return self.secret_key

    @property
    def success_rate(self) -> float:
        if self.total_deliveries == 0:
            return 0.0
        return round((self.success_deliveries / self.total_deliveries) * 100, 2)

    def is_active_status(self) -> bool:
        return self.status == WebhookStatus.ACTIVE

    def is_suspended_status(self) -> bool:
        return self.status == WebhookStatus.SUSPENDED

    def get_subscription_count(self) -> int:
        return self.subscriptions.filter(is_active=True).count()

    def get_recent_deliveries(self, days: int = 7):
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return self.delivery_logs.filter(created_at__gte=since)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SUBSCRIPTION
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSubscription(models.Model):
    """
    Ainul Enterprise Engine — Event Subscription Filter.

    Binds a WebhookEndpoint to a specific event type.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("Endpoint"),
    )
    event_type = models.CharField(max_length=80, db_index=True, verbose_name=_("Event Type"))
    is_active  = models.BooleanField(default=True, db_index=True, verbose_name=_("Active"))

    # Canonical field name: filters  (aligns with serializers.py)
    filters = models.JSONField(
        default=_empty_dict,
        blank=True,
        verbose_name=_("Payload Filters"),
        help_text=_('Optional key-value pairs. Example: {"currency": "BDT"}'),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table            = "webhook_subscriptions"
        verbose_name        = _("Webhook Subscription")
        verbose_name_plural = _("Webhook Subscriptions")
        unique_together     = [["endpoint", "event_type"]]
        ordering            = ["event_type"]
        indexes = [
            models.Index(fields=["endpoint", "is_active"], name="idx_endpoint_is_active_1908"),
            models.Index(fields=["event_type"],             name="idx_event_type_1909"),
            models.Index(fields=["is_active"],              name="idx_is_active_1910"),
        ]

    def __str__(self):
        state = "active" if self.is_active else "inactive"
        return f"{self.event_type} -> {self.endpoint.label} ({state})"

    def clean(self):
        super().clean()
        if not self.event_type:
            raise ValidationError("Event type is required.")
        if self.filters and not isinstance(self.filters, dict):
            raise ValidationError("Filters must be a JSON object.")

    # FIX: same as WebhookEndpoint above - clean() was defined but never
    # called. Wired in the same way: create/full-save only, narrow
    # update_fields saves skipped.
    def save(self, *args, **kwargs):
        if self.pk is None or not kwargs.get("update_fields"):
            self.clean()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK DELIVERY LOG
# ─────────────────────────────────────────────────────────────────────────────

class WebhookDeliveryLog(models.Model):
    """
    Ainul Enterprise Engine — Immutable delivery attempt record.

    Every outbound dispatch (initial and retry) creates a DeliveryLog row.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    endpoint = models.ForeignKey(
        WebhookEndpoint,
        on_delete=models.CASCADE,
        related_name="delivery_logs",
        verbose_name=_("Endpoint"),
    )
    event_type = models.CharField(max_length=80, db_index=True, verbose_name=_("Event Type"))

    # ── Dispatch Details ──────────────────────────────────────────────────────
    delivery_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        verbose_name=_("Delivery ID"),
        help_text=_("Unique ID sent as X-Webhook-Delivery-ID header."),
    )
    payload         = models.JSONField(default=_empty_dict, verbose_name=_("Dispatched Payload"))
    request_headers = models.JSONField(
        default=_empty_dict, blank=True, verbose_name=_("Request Headers Sent")
    )
    signature = models.CharField(
        max_length=256, blank=True, default="", verbose_name=_("HMAC Signature")
    )

    # ── Response ──────────────────────────────────────────────────────────────
    http_status_code = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("HTTP Status Code")
    )
    response_body    = models.TextField(blank=True, default="", verbose_name=_("Response Body"))
    response_time_ms = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Response Time (ms)")
    )
    error_message = models.TextField(blank=True, default="", verbose_name=_("Error Message"))

    # ── Status & Retry ────────────────────────────────────────────────────────
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.CHOICES,
        default=DeliveryStatus.PENDING,
        db_index=True,
        verbose_name=_("Delivery Status"),
    )
    attempt_number = models.PositiveSmallIntegerField(default=1, verbose_name=_("Attempt Number"))
    max_attempts   = models.PositiveSmallIntegerField(default=3, verbose_name=_("Max Attempts"))
    next_retry_at  = models.DateTimeField(
        null=True, blank=True, db_index=True, verbose_name=_("Next Retry At")
    )
    dispatched_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Dispatched At"))
    completed_at  = models.DateTimeField(null=True, blank=True, verbose_name=_("Completed At"))

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(default=timezone.now)  # was auto_now_add=True; silently ignored explicit values needed for replay-eligibility-window testing/logic (same bug class as WebhookHealthLog.checked_at, fixed earlier this audit)
    updated_at = models.DateTimeField(auto_now=True)

    # ── Archival ──────────────────────────────────────────────────────────────
    # Added session 6: archive_old_data (tasks/cleanup_tasks.py) was already
    # setting log.archived / log.archived_at directly, but neither field
    # existed — Model.save() silently no-ops on unknown attributes, so the
    # task always reported success while persisting nothing.
    archived = models.BooleanField(default=False, db_index=True, verbose_name=_("Archived"))
    archived_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Archived At"))

    class Meta:
        db_table            = "webhook_delivery_logs"
        verbose_name        = _("Webhook Delivery Log")
        verbose_name_plural = _("Webhook Delivery Logs")
        ordering            = ["-created_at"]
        indexes = [
            models.Index(fields=["endpoint", "status"],  name="idx_endpoint_status_1911"),
            models.Index(fields=["event_type"],           name="idx_event_type_1912"),
            models.Index(fields=["status"],               name="idx_status_1913"),
            models.Index(fields=["dispatched_at"],        name="idx_dispatched_at_1914"),
            models.Index(fields=["next_retry_at"],        name="idx_next_retry_at_1915"),
            models.Index(fields=["delivery_id"],          name="idx_delivery_id_1916"),
        ]

    def __str__(self):
        return (
            f"[{self.status.upper()}] {self.event_type} "
            f"-> {self.endpoint.label} (attempt {self.attempt_number})"
        )

    # ── Properties ────────────────────────────────────────────────────────────

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

    # ── Helpers ───────────────────────────────────────────────────────────────

    def mark_as_successful(self, status_code=None, response_body=None, response_time_ms=None):
        self.status           = DeliveryStatus.SUCCESS
        self.http_status_code = status_code
        self.response_body    = response_body or ""
        self.response_time_ms = response_time_ms
        self.completed_at     = timezone.now()
        self.save()

    def mark_as_failed(
        self, error_message, status_code=None, response_body=None, response_time_ms=None
    ):
        self.error_message    = error_message
        self.http_status_code = status_code
        self.response_body    = response_body or ""
        self.response_time_ms = response_time_ms
        self.completed_at     = timezone.now()
        self.status = (
            DeliveryStatus.EXHAUSTED
            if self.attempt_number >= self.max_attempts
            else DeliveryStatus.FAILED
        )
        self.save()

    def mark_as_exhausted(self, error_message=""):
        self.status        = DeliveryStatus.EXHAUSTED
        self.error_message = error_message
        self.completed_at  = timezone.now()
        self.save()

    def get_retry_delay(self) -> int:
        """Exponential backoff retry delay in seconds."""
        delays = {1: 60, 2: 300}
        return delays.get(self.attempt_number, 900)

    def schedule_retry(self) -> bool:
        if not self.is_retryable:
            return False
        from datetime import timedelta
        self.next_retry_at = timezone.now() + timedelta(seconds=self.get_retry_delay())
        self.status        = DeliveryStatus.RETRYING
        self.save()
        return True
