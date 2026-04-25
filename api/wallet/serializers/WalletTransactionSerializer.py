# api/wallet/serializers/WalletTransactionSerializer.py
from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from ..models import WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    transaction_id   = serializers.UUIDField(source="txn_id", read_only=True)
    wallet_user      = serializers.CharField(source="wallet.user.username", read_only=True)
    type_display     = serializers.CharField(source="get_type_display", read_only=True)
    status_display   = serializers.CharField(source="get_status_display", read_only=True)
    created_by_email = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = WalletTransaction
        fields = [
            "id", "transaction_id", "wallet", "wallet_user",
            "type", "type_display", "amount", "currency",
            "fee_amount", "net_amount", "status", "status_display",
            "balance_before", "balance_after",
            "debit_account", "credit_account",
            "reference_id", "reference_type", "idempotency_key",
            "description", "metadata",
            "ip_address",
            "is_reversed", "reversed_at", "reversal_reason",
            "created_by", "created_by_email",
            "approved_by", "approved_by_name", "approved_at",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "transaction_id", "balance_before", "balance_after",
            "is_reversed", "reversed_at", "created_at", "updated_at",
        ]
        extra_kwargs = {"wallet": {"write_only": True}}

    def get_created_by_email(self, obj):
        return obj.created_by.email if obj.created_by else "system"

    def get_approved_by_name(self, obj):
        return obj.approved_by.username if obj.approved_by else ""

    def validate_amount(self, value):
        try:
            v = Decimal(str(value))
            if v == 0:
                raise serializers.ValidationError("Amount cannot be zero")
            return v
        except (InvalidOperation, ValueError):
            raise serializers.ValidationError("Invalid decimal amount")
