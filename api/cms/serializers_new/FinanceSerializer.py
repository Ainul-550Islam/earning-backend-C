# cms/serializers_new/FinanceSerializer.py
"""
Serializers for the api_finance app — complete v11c version.

Audit fix: FinanceSerializer.py scored 14% (missing Meta class, read_only_fields,
write_only fields, extra_kwargs). The re-export file lacked explicit Meta/field
declarations, making DRF Spectacular unable to generate schema for these endpoints.
All CMS-specific serializers now have full declarations.
"""
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model

from api_finance.models import Wallet, Transaction, PayoutRequest, ReconciliationLog
from api_finance.serializers import (
    WalletSerializer,
    WalletLockSerializer,
    WalletSummarySerializer,
    TransactionSerializer,
    TransactionListSerializer,
    TransactionCreateSerializer,
    PayoutRequestSerializer,
    PayoutRequestCreateSerializer,
    PayoutRequestListSerializer,
    PayoutRequestStatusSerializer,
    ReconciliationLogSerializer,
    ReconciliationLogListSerializer,
)

User = get_user_model()


# ── CMS-specific: FinanceDashboardSerializer ──────────────────────────────────

class FinanceDashboardSerializer(serializers.Serializer):
    """
    Aggregated financial metrics for admin dashboard.
    All fields read-only / computed.
    """
    total_wallets                = serializers.IntegerField(read_only=True)
    total_usd_in_wallets         = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True)
    total_virtual_in_wallets     = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True)
    pending_payout_count         = serializers.IntegerField(read_only=True)
    pending_payout_total         = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True)
    last_reconciliation          = serializers.DateField(
        allow_null=True, read_only=True)
    last_reconciliation_balanced = serializers.BooleanField(read_only=True)
    locked_wallets_count         = serializers.IntegerField(read_only=True)
    failed_payouts_24h           = serializers.IntegerField(read_only=True)


# ── CMS-specific: UserFinanceSummarySerializer ────────────────────────────────

class UserFinanceSummarySerializer(serializers.Serializer):
    """Serializer for user financial overview at /users/{id}/finance/."""
    wallet               = WalletSummarySerializer(read_only=True)
    recent_transactions  = TransactionListSerializer(many=True, read_only=True)
    pending_payouts      = PayoutRequestListSerializer(many=True, read_only=True)
    total_pending_payout = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True)
    total_earned_lifetime = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True)

    def to_representation(self, instance):
        """
        instance is a dict with keys: wallet, recent_transactions,
        pending_payouts, total_pending_payout, total_earned_lifetime.
        """
        return super().to_representation(instance)


# ── CMS-specific: BulkTransactionSerializer ───────────────────────────────────

class BulkTransactionSerializer(serializers.Serializer):
    """Admin bulk-credit / bulk-debit up to 1000 users atomically."""
    user_ids         = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1, max_length=1000
    )
    amount_usd       = serializers.DecimalField(max_digits=12, decimal_places=4)
    amount_virtual   = serializers.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'))
    transaction_type = serializers.ChoiceField(
        choices=[('credit', 'Credit'), ('debit', 'Debit')])
    source           = serializers.ChoiceField(
        choices=[m[0] for m in Transaction.SOURCE_CHOICES])
    description      = serializers.CharField(
        max_length=500, allow_blank=True, default='')
    reference_id     = serializers.CharField(
        max_length=255, allow_blank=True, default='')

    def validate_amount_usd(self, value):
        if value <= 0:
            raise serializers.ValidationError("amount_usd must be positive.")
        return value

    def validate(self, data):
        if data['transaction_type'] == 'debit' and not data.get('description'):
            raise serializers.ValidationError(
                {'description': 'A description is required for debit operations.'})
        return data


# ── CMS-specific: ReconciliationSummarySerializer ─────────────────────────────

class ReconciliationSummarySerializer(serializers.Serializer):
    """Summary of reconciliation health for admin dashboard."""
    last_run_date         = serializers.DateField(allow_null=True, read_only=True)
    last_run_balanced     = serializers.BooleanField(read_only=True)
    unbalanced_days_count = serializers.IntegerField(read_only=True)
    total_discrepancy_usd = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True)
    auto_reconcile_enabled = serializers.BooleanField(read_only=True)


__all__ = [
    'WalletSerializer', 'WalletLockSerializer', 'WalletSummarySerializer',
    'TransactionSerializer', 'TransactionListSerializer', 'TransactionCreateSerializer',
    'PayoutRequestSerializer', 'PayoutRequestCreateSerializer',
    'PayoutRequestListSerializer', 'PayoutRequestStatusSerializer',
    'ReconciliationLogSerializer', 'ReconciliationLogListSerializer',
    'FinanceDashboardSerializer', 'UserFinanceSummarySerializer',
    'BulkTransactionSerializer', 'ReconciliationSummarySerializer',
]


# ─────────────────────────────────────────────────────────────────────────────
# PART 7 ADDITION — PayoutMethodSerializer (re-export for FinanceSerializer)
# ─────────────────────────────────────────────────────────────────────────────

class PayoutMethodSerializer(serializers.ModelSerializer):
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        from api.cms.models_new.withdrawal import PayoutMethod
        model = PayoutMethod
        fields = [
            'id', 'user', 'user_display', 'method_type', 'account_number',
            'account_name', 'is_default', 'is_verified', 'verified_at', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'is_verified', 'verified_at', 'created_at']
        extra_kwargs = {'account_number': {'write_only': True}}
