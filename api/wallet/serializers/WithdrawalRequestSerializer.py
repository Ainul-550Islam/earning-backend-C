# api/wallet/serializers/WithdrawalRequestSerializer.py
from decimal import Decimal
from rest_framework import serializers
from ..models import WithdrawalRequest


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    withdrawal_id    = serializers.UUIDField(format="hex_verbose", read_only=True)
    username         = serializers.CharField(source="user.username", read_only=True)
    status_display   = serializers.CharField(source="get_status_display", read_only=True)
    method_display   = serializers.SerializerMethodField()
    fee_percent      = serializers.SerializerMethodField()
    can_cancel       = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = WithdrawalRequest
        fields = [
            "id", "withdrawal_id", "user", "username", "wallet",
            "payment_method", "method_display", "transaction",
            "amount", "fee", "net_amount", "currency",
            "status", "status_display", "priority",
            "processed_by", "processed_by_name", "processed_at",
            "rejection_reason", "rejected_at",
            "cancellation_reason", "cancelled_at",
            "gateway_reference", "gateway_status",
            "idempotency_key", "ip_address",
            "admin_note", "fee_percent", "can_cancel",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "withdrawal_id", "net_amount", "status",
            "processed_by", "processed_at",
            "rejected_at", "cancelled_at",
            "gateway_reference", "gateway_status",
            "created_at", "updated_at",
        ]

    def get_method_display(self, obj):
        if obj.payment_method:
            return (f"{obj.payment_method.get_method_type_display()} "
                    f"****{obj.payment_method.account_number[-4:]}")
        return ""

    def get_fee_percent(self, obj):
        try:
            return float(obj.fee / obj.amount * 100) if obj.amount else 0
        except Exception:
            return 0

    def get_can_cancel(self, obj):
        return obj.status in ("pending",)

    def get_processed_by_name(self, obj):
        return obj.processed_by.username if obj.processed_by else ""

    def validate_amount(self, value):
        v = Decimal(str(value))
        from ..constants import MIN_WITHDRAWAL, MAX_WITHDRAWAL
        if v < MIN_WITHDRAWAL:
            raise serializers.ValidationError(f"Minimum: {MIN_WITHDRAWAL} BDT")
        if v > MAX_WITHDRAWAL:
            raise serializers.ValidationError(f"Maximum: {MAX_WITHDRAWAL} BDT")
        return v
