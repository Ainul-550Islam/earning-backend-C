# api/wallet/serializers/WithdrawalFeeSerializer.py
from rest_framework import serializers
from ..models import WithdrawalFee


class WithdrawalFeeSerializer(serializers.ModelSerializer):
    example_fee_1000 = serializers.SerializerMethodField()
    example_fee_5000 = serializers.SerializerMethodField()

    class Meta:
        model  = WithdrawalFee
        fields = [
            "id", "gateway", "tier", "fee_type",
            "fee_percent", "flat_fee", "min_fee", "max_fee",
            "is_active", "example_fee_1000", "example_fee_5000",
            "created_at", "updated_at",
        ]

    def get_example_fee_1000(self, obj):
        from decimal import Decimal
        return float(obj.calculate(Decimal("1000")))

    def get_example_fee_5000(self, obj):
        from decimal import Decimal
        return float(obj.calculate(Decimal("5000")))
