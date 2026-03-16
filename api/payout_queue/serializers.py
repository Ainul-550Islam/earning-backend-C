"""
Payout Queue Serializers — DRF serializers with full validation.
"""

from __future__ import annotations

from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .choices import PaymentGateway, PriorityLevel, PayoutBatchStatus
from .constants import MIN_PAYOUT_AMOUNT, MAX_PAYOUT_AMOUNT, MAX_BATCH_SIZE
from .models import PayoutBatch, PayoutItem, WithdrawalPriority, BulkProcessLog


class PayoutItemSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    gateway_display = serializers.CharField(source="get_gateway_display", read_only=True)
    can_retry = serializers.BooleanField(read_only=True)
    is_terminal = serializers.BooleanField(read_only=True)

    class Meta:
        model = PayoutItem
        fields = [
            "id", "batch", "user", "status", "status_display",
            "gateway", "gateway_display", "account_number",
            "gross_amount", "fee_amount", "net_amount",
            "gateway_reference", "internal_reference",
            "retry_count", "next_retry_at", "processed_at",
            "error_code", "error_message",
            "can_retry", "is_terminal",
            "note", "metadata", "created_at",
        ]
        read_only_fields = [
            "id", "status", "fee_amount", "net_amount",
            "gateway_reference", "internal_reference",
            "retry_count", "next_retry_at", "processed_at",
            "error_code", "error_message", "created_at",
        ]

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


class PayoutItemInputSerializer(serializers.Serializer):
    """Used when adding items to a batch."""
    user_id = serializers.IntegerField()
    account_number = serializers.CharField(max_length=50)
    gross_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    note = serializers.CharField(max_length=2000, required=False, default="")
    metadata = serializers.DictField(required=False, default=dict)

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


class BulkProcessLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = BulkProcessLog
        fields = [
            "id", "batch", "status", "status_display",
            "task_id", "items_attempted", "items_succeeded",
            "items_failed", "items_skipped",
            "total_amount_processed", "duration_ms",
            "error_summary", "created_at",
        ]
        read_only_fields = fields


class PayoutBatchSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    gateway_display = serializers.CharField(source="get_gateway_display", read_only=True)
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    success_rate = serializers.FloatField(read_only=True)
    is_terminal = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    process_logs = BulkProcessLogSerializer(many=True, read_only=True)

    class Meta:
        model = PayoutBatch
        fields = [
            "id", "name", "gateway", "gateway_display",
            "status", "status_display",
            "priority", "priority_display",
            "total_amount", "total_fee", "net_amount",
            "item_count", "success_count", "failure_count",
            "success_rate", "is_terminal", "is_locked",
            "scheduled_at", "started_at", "completed_at",
            "created_by", "note", "error_summary",
            "process_logs", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "total_amount", "total_fee", "net_amount",
            "item_count", "success_count", "failure_count",
            "started_at", "completed_at", "error_summary",
            "created_at", "updated_at",
        ]

    def validate_gateway(self, value: str) -> str:
        if value not in PaymentGateway.values:
            raise serializers.ValidationError(
                _(f"Invalid gateway. Valid: {PaymentGateway.values}")
            )
        return value

    def validate_priority(self, value: str) -> str:
        if value not in PriorityLevel.values:
            raise serializers.ValidationError(
                _(f"Invalid priority. Valid: {PriorityLevel.values}")
            )
        return value


class CreatePayoutBatchSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    gateway = serializers.ChoiceField(choices=PaymentGateway.choices)
    priority = serializers.ChoiceField(
        choices=PriorityLevel.choices, default=PriorityLevel.NORMAL
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    note = serializers.CharField(max_length=2000, required=False, default="")
    metadata = serializers.DictField(required=False, default=dict)
    items = serializers.ListField(
        child=PayoutItemInputSerializer(),
        required=False,
        default=list,
        max_length=MAX_BATCH_SIZE,
    )

    def validate_name(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError(_("name must not be empty."))
        return value.strip()


class WithdrawalPrioritySerializer(serializers.ModelSerializer):
    priority_display = serializers.CharField(source="get_priority_display", read_only=True)
    reason_display = serializers.CharField(source="get_reason_display", read_only=True)

    class Meta:
        model = WithdrawalPriority
        fields = [
            "id", "user", "payout_item", "priority", "priority_display",
            "previous_priority", "reason", "reason_display",
            "reason_note", "expires_at", "assigned_by", "is_active",
            "created_at",
        ]
        read_only_fields = fields
