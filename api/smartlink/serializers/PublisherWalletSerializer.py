"""
SmartLink PublisherWallet Serializer
=====================================
Dedicated serializer for PublisherWallet — previously returned as a raw
dict from BillingService. Now exposed as a proper DRF serializer.
"""
from rest_framework import serializers
from api.smartlink.models.billing import PublisherWallet


class PublisherWalletSerializer(serializers.ModelSerializer):
    """
    Read-only wallet summary for a publisher.
    Returned by: GET /api/smartlink/publisher/profile/wallet/
    """
    publisher_username = serializers.SerializerMethodField()
    total_balance      = serializers.SerializerMethodField()

    class Meta:
        model = PublisherWallet
        fields = [
            'id',
            'publisher',
            'publisher_username',
            'balance_usd',
            'pending_usd',
            'lifetime_earned',
            'lifetime_paid',
            'total_balance',
            'last_credit_at',
            'last_payout_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_publisher_username(self, obj):
        return obj.publisher.username

    def get_total_balance(self, obj):
        """balance_usd + pending_usd = total owed to publisher."""
        return obj.balance_usd + obj.pending_usd


class WalletTransactionSerializer(serializers.Serializer):
    """
    Represents a single wallet transaction (credit or debit).
    Used for the wallet transaction history endpoint.
    """
    transaction_type = serializers.ChoiceField(
        choices=['credit', 'debit', 'hold', 'release']
    )
    amount_usd       = serializers.DecimalField(max_digits=14, decimal_places=4)
    description      = serializers.CharField(max_length=500)
    reference_id     = serializers.CharField(max_length=100, allow_blank=True)
    created_at       = serializers.DateTimeField()
    balance_after    = serializers.DecimalField(max_digits=14, decimal_places=4)


class WalletSummarySerializer(serializers.Serializer):
    """
    Compact wallet summary for the publisher dashboard header.
    """
    available_usd    = serializers.DecimalField(max_digits=14, decimal_places=4)
    pending_usd      = serializers.DecimalField(max_digits=14, decimal_places=4)
    lifetime_earned  = serializers.DecimalField(max_digits=14, decimal_places=4)
    lifetime_paid    = serializers.DecimalField(max_digits=14, decimal_places=4)
    next_payout_date = serializers.DateField(allow_null=True)
    min_payout       = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency         = serializers.CharField(max_length=3)
