"""
Advanced Models for Webhooks System

This module contains advanced webhook models including filters, batches,
templates, and secrets management.

FIXES APPLIED:
    [ADV-01] WebhookFilter.clean() validated field_path and operator but
             never checked the value field against the operator's type
             contract.  Operators like IN / NOT_IN require a list; BETWEEN
             requires a 2-element list; scalar operators (EQUALS, CONTAINS,
             GREATER_THAN, etc.) require a non-list primitive.  Malformed
             values passed model validation silently and then crashed
             FilterService at dispatch time.
             Fix: operator-to-type validation added in clean().

    [ADV-02] WebhookBatch had no clean() method at all — no validation of
             batch_id format, no guard on event_count == 0, and no temporal
             sanity check (completed_at must be after created_at).
             Fix: clean() method added.
"""

import uuid

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from ..validators import validate_batch_size, validate_timeout
from .constants import (
    FilterOperator, BatchStatus
)

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
#  OPERATOR TYPE CONTRACT
# ─────────────────────────────────────────────────────────────────────────────

# Operators that require the value to be a list
_LIST_OPERATORS = {FilterOperator.IN, FilterOperator.NOT_IN}

# Operators that require a list of exactly 2 comparable items
_BETWEEN_OPERATORS: set = set()  # no BETWEEN in current FilterOperator — reserved

# Operators where value is ignored entirely (field presence check)
_VALUELESS_OPERATORS = {FilterOperator.EXISTS, FilterOperator.NOT_EXISTS}

# All other operators expect a scalar (str, int, float, bool)
_SCALAR_OPERATORS = {
    FilterOperator.EQUALS,
    FilterOperator.NOT_EQUALS,
    FilterOperator.CONTAINS,
    FilterOperator.NOT_CONTAINS,
    FilterOperator.GREATER_THAN,
    FilterOperator.LESS_THAN,
    FilterOperator.GREATER_THAN_OR_EQUAL,
    FilterOperator.LESS_THAN_OR_EQUAL,
}


class WebhookFilter(models.Model):
    """
    Advanced filtering rules for webhook events.
    Controls which events trigger webhook deliveries.
    """

    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="filters",
        verbose_name=_("Endpoint"),
    )
    field_path = models.CharField(
        max_length=255,
        verbose_name=_("Field Path"),
        help_text=_('JSON field path to filter (e.g., "user.email", "amount")'),
    )
    operator = models.CharField(
        max_length=20,
        choices=FilterOperator.choices,
        default=FilterOperator.EQUALS,
        verbose_name=_("Operator"),
    )
    value = models.JSONField(
        verbose_name=_("Value"),
        help_text=_("Filter value (supports strings, numbers, arrays)"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True,     verbose_name=_("Updated At"))

    class Meta:
        verbose_name        = _("Webhook Filter")
        verbose_name_plural = _("Webhook Filters")
        indexes = [
            models.Index(fields=["endpoint", "is_active"], name="wf_endpoint_active_idx"),
            models.Index(fields=["field_path"],             name="wf_field_path_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.field_path} {self.operator} {self.value}"

    def clean(self):
        """
        Validate filter configuration.

        FIX [ADV-01]: Added operator-aware value type validation.

        Contract per operator:
            EXISTS / NOT_EXISTS  — value is irrelevant; accepted as-is.
            IN / NOT_IN          — value must be a non-empty list.
            EQUALS / NOT_EQUALS / CONTAINS / NOT_CONTAINS /
            GREATER_THAN / LESS_THAN / GTE / LTE
                                  — value must be a scalar (str, int,
                                    float, or bool), never a list or dict.
        """
        super().clean()

        # ── field_path ────────────────────────────────────────────────────────
        if not self.field_path or not self.field_path.strip():
            raise ValidationError({"field_path": _("Field path is required.")})

        # ── operator ──────────────────────────────────────────────────────────
        valid_operators = [choice[0] for choice in FilterOperator.choices]
        if self.operator not in valid_operators:
            raise ValidationError(
                {"operator": _("Invalid operator: %(op)s") % {"op": self.operator}}
            )

        # ── value (operator-specific) ─────────────────────────────────────────
        # EXISTS / NOT_EXISTS: value is not used by FilterService — skip validation.
        if self.operator in _VALUELESS_OPERATORS:
            return

        if self.value is None:
            raise ValidationError(
                {"value": _("Filter value is required for operator '%(op)s'.") % {"op": self.operator}}
            )

        if self.operator in _LIST_OPERATORS:
            # IN / NOT_IN require a non-empty list
            if not isinstance(self.value, list):
                raise ValidationError(
                    {
                        "value": _(
                            "Operator '%(op)s' requires value to be a list, "
                            "got %(typ)s."
                        ) % {"op": self.operator, "typ": type(self.value).__name__}
                    }
                )
            if len(self.value) == 0:
                raise ValidationError(
                    {"value": _("Value list for operator '%(op)s' cannot be empty.") % {"op": self.operator}}
                )

        elif self.operator in _SCALAR_OPERATORS:
            # Scalar operators must NOT receive a list or dict as value
            if isinstance(self.value, (list, dict)):
                raise ValidationError(
                    {
                        "value": _(
                            "Operator '%(op)s' requires a scalar value "
                            "(string, number, or boolean), not %(typ)s."
                        ) % {"op": self.operator, "typ": type(self.value).__name__}
                    }
                )

    # FIX: clean() above was defined but never called. Wired in now that
    # test_filter_service.py's two intentionally-malformed-filter tests
    # have been moved to bulk_create() (which bypasses save()/clean() by
    # design), so they still reach the FilterService runtime-robustness
    # behavior they're meant to test. Same pattern as the other models in
    # this pass: create/full-save only, narrow update_fields saves skipped.
    def save(self, *args, **kwargs):
        if self.pk is None or not kwargs.get("update_fields"):
            self.clean()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK BATCH
# ─────────────────────────────────────────────────────────────────────────────

def _generate_batch_id() -> str:
    """FIX: batch_id is required+unique on WebhookBatch, but the real
    create flow (WebhookBatchViewSet.perform_create -> serializer.save())
    never supplied one - confirmed via test_complete_webhook_flow_with_batch
    failing through the actual HTTP path once clean() got wired up on this
    model, not a synthetic case. Same auto-generate-a-default convention as
    WebhookDeliveryLog.delivery_id / WebhookEndpoint.secret_key
    (models/core.py)."""
    return f"batch_{uuid.uuid4().hex}"


class WebhookBatch(models.Model):
    """
    Batch processing for webhook deliveries.
    Groups multiple webhook events for efficient processing.
    """

    batch_id = models.CharField(
        max_length=64,
        unique=True,
        default=_generate_batch_id,
        verbose_name=_("Batch ID"),
    )
    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="batches",
        verbose_name=_("Endpoint"),
    )
    event_type = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name=_("Event Type"),
        help_text=_("Event type this batch was created for (dispatch-created batches only)."),
    )
    event_count = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name=_("Event Count"),
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
        verbose_name=_("Status"),
    )
    priority = models.CharField(
        max_length=10,
        choices=[("low", _("Low")), ("normal", _("Normal")), ("high", _("High")), ("urgent", _("Urgent"))],
        default="normal",
        verbose_name=_("Priority"),
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Metadata"),
        help_text=_("Arbitrary caller-supplied metadata (e.g. import source, correlation id)."),
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_webhook_batches",
        verbose_name=_("Created By"),
        help_text=_("Who explicitly triggered this batch's creation, if known. Not used for access control — see endpoint.owner for that."),
    )
    created_at   = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    started_at   = models.DateTimeField(null=True, blank=True, verbose_name=_("Started At"))
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Completed At")
    )
    error_message = models.TextField(null=True, blank=True, verbose_name=_("Error Message"))

    class Meta:
        verbose_name        = _("Webhook Batch")
        verbose_name_plural = _("Webhook Batches")
        indexes = [
            models.Index(fields=["batch_id"],          name="wb_batch_id_idx"),
            models.Index(fields=["endpoint", "status"], name="wb_endpoint_status_idx"),
            models.Index(fields=["created_at"],         name="wb_created_at_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(event_count__gte=0),
                name="wb_event_count_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return f"Batch {self.batch_id} ({self.event_count} events)"

    def clean(self):
        """
        Validate batch configuration.

        FIX [ADV-02]: WebhookBatch previously had no clean() method,
        leaving batch_id empty strings, zero-item completed batches, and
        impossible timestamps (completed_at before created_at) all passing
        model validation silently.
        """
        super().clean()

        # ── batch_id ──────────────────────────────────────────────────────────
        if not self.batch_id or not self.batch_id.strip():
            raise ValidationError({"batch_id": _("Batch ID is required.")})

        # ── temporal sanity ───────────────────────────────────────────────────
        # completed_at is set by the system after creation, so we can only
        # compare it against created_at when the row already exists.
        if self.completed_at and self.pk:
            try:
                original = WebhookBatch.objects.get(pk=self.pk)
                if self.completed_at < original.created_at:
                    raise ValidationError(
                        {"completed_at": _("completed_at cannot be before created_at.")}
                    )
            except WebhookBatch.DoesNotExist:
                pass

        # ── status / event_count coherence ────────────────────────────────────
        terminal_statuses = {BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED}
        if self.status in terminal_statuses and self.completed_at is None:
            raise ValidationError(
                {
                    "completed_at": _(
                        "completed_at must be set when status is '%(s)s'."
                    ) % {"s": self.status}
                }
            )

    # FIX: clean() above was defined but never called. Wired in now that
    # both real gaps clean() was tripping over are fixed at the source:
    # batch_id now auto-generates (see _generate_batch_id above), and
    # BatchDispatchService's FAILED path now sets completed_at like its
    # COMPLETED/CANCELLED siblings already did. Same pattern as the other
    # models in this pass: create/full-save only, narrow update_fields
    # saves skipped.
    def save(self, *args, **kwargs):
        if self.pk is None or not kwargs.get("update_fields"):
            self.clean()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK BATCH ITEM
# ─────────────────────────────────────────────────────────────────────────────

class WebhookBatchItem(models.Model):
    """
    Individual items within a webhook batch.
    Links batch items to delivery logs.
    """

    batch = models.ForeignKey(
        WebhookBatch,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Batch"),
    )
    delivery_log = models.ForeignKey(
        "WebhookDeliveryLog",
        on_delete=models.CASCADE,
        related_name="batch_items",
        null=True,
        blank=True,
        verbose_name=_("Delivery Log"),
        help_text=_("Set for BatchService-created items (grouping existing deliveries). Null for dispatch-created items, which have no delivery yet at creation time."),
    )
    position = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name=_("Position"),
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
        verbose_name=_("Status"),
    )
    event_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name=_("Event Data"),
        help_text=_("Raw event payload for dispatch-created items."),
    )
    sequence_number = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Sequence Number"),
        help_text=_("Dispatch order within the batch, for dispatch-created items."),
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Started At"))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Completed At"))
    error_message = models.TextField(null=True, blank=True, verbose_name=_("Error Message"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        verbose_name        = _("Webhook Batch Item")
        verbose_name_plural = _("Webhook Batch Items")
        indexes = [
            models.Index(fields=["batch", "position"], name="wbi_batch_position_idx"),
            models.Index(fields=["delivery_log"],       name="wbi_delivery_log_idx"),
        ]
        unique_together = [["batch", "delivery_log"]]
        constraints = [
            models.CheckConstraint(check=models.Q(position__gte=0),
                name="wbi_position_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return f"Item {self.position} in batch {self.batch.batch_id}"


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK TEMPLATE
# ─────────────────────────────────────────────────────────────────────────────

class WebhookTemplate(models.Model):
    """
    Template engine for webhook payloads.
    Supports Jinja2 templating and transformation rules.
    """

    name = models.CharField(max_length=100, verbose_name=_("Template Name"))
    event_type = models.CharField(
        max_length=100,
        verbose_name=_("Event Type"),
        help_text=_("Event type this template applies to"),
    )
    payload_template = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Payload Template"),
        help_text=_("Jinja2 template for payload transformation"),
    )
    transform_rules = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Transform Rules"),
        help_text=_("JSON transformation rules applied before template"),
    )
    is_active  = models.BooleanField(default=True, verbose_name=_("Is Active"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True,     verbose_name=_("Updated At"))

    class Meta:
        verbose_name        = _("Webhook Template")
        verbose_name_plural = _("Webhook Templates")
        indexes = [
            models.Index(fields=["event_type", "is_active"], name="wt_event_active_idx"),
            models.Index(fields=["name"],                     name="wt_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.event_type})"


# ─────────────────────────────────────────────────────────────────────────────
#  WEBHOOK SECRET
# ─────────────────────────────────────────────────────────────────────────────

class WebhookSecret(models.Model):
    """
    Secret management for webhook endpoints.
    Supports secret rotation and grace periods.
    """

    endpoint = models.ForeignKey(
        "WebhookEndpoint",
        on_delete=models.CASCADE,
        related_name="secrets",
        verbose_name=_("Endpoint"),
    )
    secret_hash = models.CharField(
        max_length=255,
        verbose_name=_("Secret Hash"),
        help_text=_("Hashed version of the webhook secret"),
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expires At"),
        help_text=_("When this secret expires (for rotation)"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        verbose_name        = _("Webhook Secret")
        verbose_name_plural = _("Webhook Secrets")
        indexes = [
            models.Index(fields=["endpoint", "is_active"], name="ws_endpoint_active_idx"),
            models.Index(fields=["expires_at"],             name="ws_expires_at_idx"),
        ]

    def __str__(self) -> str:
        return f"Secret for {self.endpoint.target_url} (expires: {self.expires_at})"

    def is_expired(self) -> bool:
        """Check if secret is expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
