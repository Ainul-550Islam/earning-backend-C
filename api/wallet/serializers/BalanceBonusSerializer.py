# api/wallet/serializers/BalanceBonusSerializer.py
from rest_framework import serializers
from ..models import BalanceBonus


class BalanceBonusSerializer(serializers.ModelSerializer):
    wallet_user  = serializers.CharField(source="wallet.user.username", read_only=True)
    is_expired   = serializers.BooleanField(read_only=True)
    granted_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = BalanceBonus
        fields = [
            "id", "bonus_id", "wallet", "wallet_user",
            "amount", "source", "source_id",
            "status", "description",
            "expires_at", "granted_at", "claimed_at", "revoked_at",
            "granted_by", "granted_by_name",
            "is_expired",
        ]
        read_only_fields = ["bonus_id", "granted_at", "claimed_at", "revoked_at"]

    def get_granted_by_name(self, obj):
        return obj.granted_by.username if obj.granted_by else "system"
