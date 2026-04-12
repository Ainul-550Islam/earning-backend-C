"""CORE_FILES/schemas.py — API request/response schema validators."""
from rest_framework import serializers
from decimal import Decimal


class DateRangeSchema(serializers.Serializer):
    start = serializers.DateField(required=False)
    end   = serializers.DateField(required=False)
    def validate(self, attrs):
        if attrs.get("start") and attrs.get("end") and attrs["end"] < attrs["start"]:
            raise serializers.ValidationError("end must be >= start")
        return attrs

class PaginationSchema(serializers.Serializer):
    page      = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)

class CampaignFilterSchema(serializers.Serializer):
    status        = serializers.CharField(required=False)
    pricing_model = serializers.CharField(required=False)
    search        = serializers.CharField(max_length=255, required=False)

class OfferFilterSchema(serializers.Serializer):
    offer_type = serializers.CharField(required=False)
    status     = serializers.CharField(required=False)
    country    = serializers.CharField(max_length=2, required=False)
    featured   = serializers.BooleanField(required=False)

class WebhookPayloadSchema(serializers.Serializer):
    txn_id    = serializers.CharField(required=True)
    offer_id  = serializers.CharField(required=False)
    user_id   = serializers.CharField(required=False)
    reward    = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    payout    = serializers.DecimalField(max_digits=12, decimal_places=6, required=False)
    signature = serializers.CharField(required=False)
    network   = serializers.CharField(required=False)

class CouponRedeemSchema(serializers.Serializer):
    code = serializers.CharField(max_length=30, min_length=4)
    def validate_code(self, v): return v.strip().upper()

class PayoutCreateSchema(serializers.Serializer):
    payout_method_id = serializers.IntegerField()
    coins            = serializers.DecimalField(max_digits=16, decimal_places=2, min_value=1)
    exchange_rate    = serializers.DecimalField(max_digits=12, decimal_places=6, default=Decimal("1.0"))

class ABTestVariantSchema(serializers.Serializer):
    name       = serializers.CharField(max_length=50)
    weight     = serializers.IntegerField(min_value=1, max_value=100)
    ad_unit_id = serializers.IntegerField(required=False)

class RevenueReportSchema(serializers.Serializer):
    start      = serializers.DateField()
    end        = serializers.DateField()
    network_id = serializers.IntegerField(required=False)
    country    = serializers.CharField(max_length=2, required=False)
    group_by   = serializers.ChoiceField(choices=["date","network","country","format"], default="date")
