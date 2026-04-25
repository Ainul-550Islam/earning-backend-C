# api/wallet/serializers/EarningRecordSerializer.py
from rest_framework import serializers
from ..models import EarningRecord


class EarningRecordSerializer(serializers.ModelSerializer):
    wallet_user       = serializers.CharField(source="wallet.user.username", read_only=True)
    source_type_display = serializers.CharField(source="get_source_type_display", read_only=True)
    source_name       = serializers.SerializerMethodField()

    class Meta:
        model  = EarningRecord
        fields = [
            "id", "wallet", "wallet_user",
            "source", "source_name",
            "transaction",
            "source_type", "source_type_display", "source_ref_id",
            "amount", "original_amount", "bonus_percent",
            "country_code", "device_type",
            "metadata", "earned_at",
        ]
        read_only_fields = fields

    def get_source_name(self, obj):
        return obj.source.name if obj.source else ""
