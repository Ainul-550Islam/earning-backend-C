# api/wallet/serializers/BalanceHistorySerializer.py
from rest_framework import serializers
from ..models import BalanceHistory


class BalanceHistorySerializer(serializers.ModelSerializer):
    wallet_user     = serializers.CharField(source="wallet.user.username", read_only=True)
    balance_type_display = serializers.CharField(source="get_balance_type_display", read_only=True)
    direction       = serializers.SerializerMethodField()

    class Meta:
        model  = BalanceHistory
        fields = [
            "id", "wallet", "wallet_user", "balance_type", "balance_type_display",
            "previous", "new_value", "delta", "direction",
            "reason", "reference_id",
            "created_at",
        ]
        read_only_fields = fields

    def get_direction(self, obj):
        return "credit" if obj.delta >= 0 else "debit"
