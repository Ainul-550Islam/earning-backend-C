# api/wallet/serializers/EarningSummarySerializer.py
from rest_framework import serializers
from ..models import EarningSummary


class EarningSummarySerializer(serializers.ModelSerializer):
    wallet_user = serializers.CharField(source="wallet.user.username", read_only=True)
    top_source  = serializers.SerializerMethodField()

    class Meta:
        model  = EarningSummary
        fields = [
            "id", "wallet", "wallet_user",
            "period", "period_start", "period_end",
            "total_earned", "total_count",
            "by_source", "top_source",
            "computed_at",
        ]
        read_only_fields = fields

    def get_top_source(self, obj):
        if not obj.by_source:
            return None
        return max(obj.by_source.items(), key=lambda x: x[1], default=(None, 0))[0]
