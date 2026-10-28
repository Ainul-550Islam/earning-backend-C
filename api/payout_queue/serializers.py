"""
payout_queue/serializers.py  ← FIXED v6

CHANGES v6:
  ① locked_at added to PayoutBatchSerializer.Meta.fields + read_only_fields.
      Previously only locked_by was serialized.  Admins had no way to tell
      WHEN a batch was locked — critical for diagnosing stuck/zombie batches.
      locked_at is the timestamp set when acquire_lock() succeeds.

  ② CancelPayoutItemSerializer added.
      The cancel action in PayoutItemViewSet was accepting raw {"reason": "..."}
      without schema validation.  Added here so DRF schema generation and
      Swagger docs reflect the correct input shape.

  ③ AuditTrailQuerySerializer added.
      Used by the new GET /batches/{id}/audit-trail/ viewset action to
      validate optional query parameters (page, page_size, action_filter).

  ④ BatchWalletBalanceSerializer added.
      Used by the new GET /batches/{id}/wallet-balance/ viewset action to
      expose available wallet balance to operators before processing.

v3 changes (preserved):
  - GrossAmountValidatorMixin extracted (tech debt fix — single source of truth).
  - validate_gross_amount() removed from both PayoutItemSerializer and
    PayoutItemInputSerializer; both now inherit from the mixin.

v2 changes (preserved):
  - SetWithdrawalPrioritySerializer
  - ValidateAccountSerializer
  - SkipPayoutItemSerializer (was defined but unwired; now wired in v2+ viewsets)
  - PayoutItemSerializer: gateway_reference, retry_count, error_code, computed_net_amount
  - PayoutBatchSerializer: computed_net_amount, locked_by
"""
from __future__ import annotations

from decimal import Decimal

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .choices import (
    PaymentGateway,
    PriorityLevel,
    PayoutBatchStatus,
    WithdrawalPriorityReason,
)
from .constants import (
    MIN_PAYOUT_AMOUNT,
    MAX_PAYOUT_AMOUNT,
    MAX_BATCH_SIZE,
    DEFAULT_BATCH_SIZE,
)
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog

# ---------------------------------------------------------------------------
# v3: GrossAmountValidatorMixin
# ---------------------------------------------------------------------------

class GrossAmountValidatorMixin:
    """
    Mixin providing validate_gross_amount() for any serializer that
    accepts a gross_amount field.

    Before v3: the identical validation block was copy-pasted into both
    PayoutItemSerializer and PayoutItemInputSerializer.  Any change to the
    limits (MIN/MAX_PAYOUT_AMOUNT) had to be made in two places.

    Usage::

        class MySerializer(GrossAmountValidatorMixin, serializers.Serializer):
            gross_amount = serializers.DecimalField(...)
    """

    def validate_gross_amount(self, value: Decimal) -> Decimal:
        if value < MIN_PAYOUT_AMOUNT:
            raise serializers.ValidationError(
                _(f"Amount must be at least {MIN_PAYOUT_AMOUNT} BDT.")
            )
        if value > MAX_PAYOUT_AMOUNT:
            raise serializers.ValidationError(
                _(f"Amount cannot exceed {MAX_PAYOUT_AMOUNT} BDT.")
            )
        return value

# ---------------------------------------------------------------------------
# PayoutItem
# ---------------------------------------------------------------------------

class PayoutItemSerializer(GrossAmountValidatorMixin, serializers.ModelSerializer):
    status_display  = serializers.CharField(source="get_status_display", read_only=True)
    gateway_display = serializers.CharField(source="get_gateway_display", read_only=True)
    can_retry           = serializers.BooleanField(read_only=True)
    is_terminal         = serializers.BooleanField(read_only=True)
    computed_net_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model  = PayoutItem
        fields = [
            "id", "batch", "user", "status", "status_display",
            "gateway", "gateway_display", "account_number",
            "gross_amount", "fee_amount", "net_amount",
            "computed_net_amount",
            "gateway_reference",
            "internal_reference",
            "retry_count",
            "next_retry_at",
            "processed_at",
            "error_code",
            "error_message",
            "can_retry", "is_terminal",
            "note", "metadata", "created_at",
        ]
        read_only_fields = [
            "id", "status", "fee_amount", "net_amount", "computed_net_amount",
            "gateway_reference", "internal_reference",
            "retry_count", "next_retry_at", "processed_at",
            "error_code", "error_message", "created_at",
        ]

class PayoutItemInputSerializer(GrossAmountValidatorMixin, serializers.Serializer):
    user_id        = serializers.IntegerField()
    account_number = serializers.CharField(max_length=50)
    gross_amount   = serializers.DecimalField(max_digits=12, decimal_places=2)
    note           = serializers.CharField(max_length=2000, required=False, default="")
    metadata       = serializers.DictField(required=False, default=dict)

# ---------------------------------------------------------------------------
# BulkProcessLog
# ---------------------------------------------------------------------------

class BulkProcessLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model  = BulkProcessLog
        fields = [
            "id", "batch", "status", "status_display",
            "task_id", "items_attempted", "items_succeeded",
            "items_failed", "items_skipped",
            "total_amount_processed", "duration_ms",
            "error_summary", "created_at",
        ]
        read_only_fields = fields

# ---------------------------------------------------------------------------
# PayoutBatch
# ---------------------------------------------------------------------------

class PayoutBatchSerializer(serializers.ModelSerializer):
    status_display      = serializers.CharField(source="get_status_display", read_only=True)
    gateway_display     = serializers.CharField(source="get_gateway_display", read_only=True)
    priority_display    = serializers.CharField(source="get_priority_display", read_only=True)
    success_rate        = serializers.FloatField(read_only=True)
    is_terminal         = serializers.BooleanField(read_only=True)
    is_locked           = serializers.BooleanField(read_only=True)
    computed_net_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    process_logs = BulkProcessLogSerializer(many=True, read_only=True)

    class Meta:
        model  = PayoutBatch
        fields = [
            "id", "name", "gateway", "gateway_display",
            "status", "status_display", "priority", "priority_display",
            "total_amount", "total_fee", "net_amount", "computed_net_amount",
            "item_count", "success_count", "failure_count",
            "success_rate", "is_terminal", "is_locked",
            # FIX v6: locked_at added alongside locked_by.
            # Previously admins could see WHO locked a batch but not WHEN —
            # making it impossible to determine if a lock is stale/zombie.
            "locked_by",
            "locked_at",
            "scheduled_at", "started_at", "completed_at",
            "created_by", "note", "error_summary",
            "process_logs", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "total_amount", "total_fee", "net_amount",
            "item_count", "success_count", "failure_count",
            # v6: locked_at is also read-only (set by acquire_lock()).
            "locked_by", "locked_at",
            "started_at", "completed_at", "error_summary",
            "created_at", "updated_at",
        ]

class CreatePayoutBatchSerializer(serializers.Serializer):
    name         = serializers.CharField(max_length=255)
    gateway      = serializers.ChoiceField(choices=PaymentGateway.choices)
    priority     = serializers.ChoiceField(
        choices=PriorityLevel.choices,
        default=PriorityLevel.NORMAL,
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    note         = serializers.CharField(max_length=2000, required=False, default="")
    metadata     = serializers.DictField(required=False, default=dict)
    items        = serializers.ListField(
        child=PayoutItemInputSerializer(),
        required=False,
        default=list,
        max_length=MAX_BATCH_SIZE,
    )

    def validate_name(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("name must not be empty."))
        return value.strip()

# ---------------------------------------------------------------------------
# WithdrawalPriority
# ---------------------------------------------------------------------------

class WithdrawalPrioritySerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    reason_display   = serializers.CharField(source="get_reason_display",   read_only=True)

    class Meta:
        model  = WithdrawalPriority
        fields = [
            "id", "user", "payout_item", "priority", "priority_display",
            "previous_priority", "reason", "reason_display",
            "reason_note", "expires_at", "assigned_by", "is_active",
            "created_at",
        ]
        read_only_fields = fields

# ---------------------------------------------------------------------------
# Action-specific input serializers — state transitions
# ---------------------------------------------------------------------------

class SetWithdrawalPrioritySerializer(serializers.Serializer):
    """Input for POST /priorities/set-priority/"""
    user_id        = serializers.IntegerField()
    priority       = serializers.ChoiceField(choices=PriorityLevel.choices)
    reason         = serializers.ChoiceField(choices=WithdrawalPriorityReason.choices)
    payout_item_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    reason_note    = serializers.CharField(max_length=2000, required=False, default="")
    expires_at     = serializers.DateTimeField(required=False, allow_null=True, default=None)

    def validate_expires_at(self, value):
        if value is not None:
            from django.utils import timezone
            if value <= timezone.now():
                raise serializers.ValidationError("expires_at must be in the future.")
        return value

class ValidateAccountSerializer(serializers.Serializer):
    """Input for POST /items/validate-account/"""
    gateway        = serializers.ChoiceField(
        choices=PaymentGateway.choices,
        help_text="Payment gateway to validate against.",
    )
    account_number = serializers.CharField(
        max_length=50,
        help_text="Wallet or bank account number to validate.",
    )

class SkipPayoutItemSerializer(serializers.Serializer):
    """Input for POST /items/{id}/skip/"""
    reason = serializers.CharField(
        max_length=500,
        required=False,
        default="",
        help_text="Optional reason for skipping this payout item.",
    )

# ---------------------------------------------------------------------------
# FIX v6: New action-specific serializers
# ---------------------------------------------------------------------------

class CancelPayoutItemSerializer(serializers.Serializer):
    """
    FIX v6: Input for POST /items/{id}/cancel/

    Previously the cancel action accepted raw {"reason": "..."} without any
    schema definition, so DRF could not validate or generate API docs for it.
    """
    reason = serializers.CharField(
        max_length=1000,
        help_text="Why this payout item is being cancelled.",
    )

class AuditTrailQuerySerializer(serializers.Serializer):
    """
    FIX v6: Query parameters for GET /batches/{id}/audit-trail/

    The audit-trail action calls get_payout_audit_trail() from
    api.audit_logs.payout_integration and supports optional filtering.
    """
    page         = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size    = serializers.IntegerField(
        min_value=1, max_value=200, required=False, default=50,
        help_text="Max entries to return (cap: 200).",
    )
    action_filter = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "Optional filter by audit action code, e.g. "
            "BATCH_CREATED, ITEM_SUCCEEDED, ITEM_PERMANENTLY_FAILED."
        ),
    )

class BatchWalletBalanceSerializer(serializers.Serializer):
    """
    FIX v6: Response schema for GET /batches/{id}/wallet-balance/

    Exposes the tenant's current payout wallet balance so operators can
    confirm sufficient funds exist before triggering processing.
    Not a ModelSerializer — data is fetched live from api.wallet.
    """
    batch_id           = serializers.UUIDField(read_only=True)
    tenant_id          = serializers.CharField(read_only=True)
    batch_total_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
        help_text="Amount that will be deducted from the wallet on process.",
    )
    wallet_balance     = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
        help_text="Current available balance in the tenant payout wallet.",
    )
    is_sufficient      = serializers.BooleanField(
        read_only=True,
        help_text="True if wallet_balance >= batch_total_amount.",
    )
    shortfall          = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
        allow_null=True,
        help_text="Shortfall amount if wallet is insufficient, else null.",
    )
