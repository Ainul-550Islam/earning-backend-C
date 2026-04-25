# api/wallet/serializers/LiabilityReportSerializer.py
from rest_framework import serializers
from ..models import LiabilityReport


class LiabilityReportSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.SerializerMethodField()
    liability_breakdown = serializers.SerializerMethodField()

    class Meta:
        model  = LiabilityReport
        fields = [
            "id", "report_date", "currency",
            "total_current", "total_pending", "total_frozen",
            "total_bonus", "total_reserved", "total_liability",
            "pending_wd_count", "pending_wd_amount",
            "total_wallets", "active_wallets", "locked_wallets",
            "has_anomaly", "anomaly_notes",
            "generated_at", "generated_by", "generated_by_name",
            "liability_breakdown",
        ]
        read_only_fields = fields

    def get_generated_by_name(self, obj):
        return obj.generated_by.username if obj.generated_by else "system"

    def get_liability_breakdown(self, obj):
        return {
            "current": float(obj.total_current),
            "pending": float(obj.total_pending),
            "frozen":  float(obj.total_frozen),
            "bonus":   float(obj.total_bonus),
        }
