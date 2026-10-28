# api/djoyalty/schemas.py
"""
Djoyalty Schemas -- OpenAPI/Swagger schema extensions।
Custom schema classes for DRF Spectacular / drf-yasg।
"""
from rest_framework import serializers


class PointsEarnRequest(serializers.Serializer):
    customer_id = serializers.IntegerField()
    txn_id = serializers.IntegerField(required=False)
    points = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    source = serializers.ChoiceField(
        choices=['purchase', 'bonus', 'referral', 'offer', 'streak', 'badge', 'admin'],
        default='purchase',
    )
    reference_id = serializers.CharField(max_length=200, required=False)


class PointsRedeemRequest(serializers.Serializer):
    customer_id = serializers.IntegerField()
    points = serializers.DecimalField(max_digits=14, decimal_places=2)
    redemption_type = serializers.CharField(max_length=50, default='voucher')
    note = serializers.CharField(max_length=300, required=False)


class CashoutRequest(serializers.Serializer):
    customer_id = serializers.IntegerField()
    points_to_redeem = serializers.DecimalField(max_digits=14, decimal_places=2)
    cashout_method = serializers.ChoiceField(
        choices=['mobile_wallet', 'bank_transfer']
    )
    mobile_wallet_id = serializers.IntegerField(required=False)
    bank_account_id = serializers.IntegerField(required=False)


class PostbackSchema(serializers.Serializer):
    subid = serializers.CharField(help_text='Customer code or ID')
    payout = serializers.DecimalField(max_digits=10, decimal_places=4)
    offer_id = serializers.CharField(required=False)
    transaction_id = serializers.CharField()
    wall_id = serializers.IntegerField(required=False, default=1)


class CustomerLoyaltyProfile(serializers.Serializer):
    """Read-only customer loyalty summary schema।"""
    customer_id = serializers.IntegerField(read_only=True)
    code = serializers.CharField(read_only=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    tier = serializers.CharField(read_only=True)
    tier_rank = serializers.IntegerField(read_only=True)
    lifetime_earned = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    lifetime_redeemed = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    streak_days = serializers.IntegerField(read_only=True)
    badges_count = serializers.IntegerField(read_only=True)


class HealthCheckSchema(serializers.Serializer):
    status = serializers.ChoiceField(choices=['healthy', 'degraded', 'unhealthy'])
    timestamp = serializers.DateTimeField(read_only=True)
    database = serializers.CharField(read_only=True)
    redis = serializers.CharField(read_only=True)
    celery = serializers.CharField(read_only=True)
