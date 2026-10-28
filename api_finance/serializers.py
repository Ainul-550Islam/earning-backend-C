# api_finance/serializers.py
"""
DRF Serializers for the api_finance app.
Covers: Wallet, Transaction, PayoutRequest, ReconciliationLog
"""
from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Wallet, Transaction, PayoutRequest, ReconciliationLog

User = get_user_model()


# ── Wallet ─────────────────────────────────────────────────────────────────────

class WalletSerializer(serializers.ModelSerializer):
    """
    Full wallet serializer — used in admin and user profile endpoints.
    Balance fields are read-only; only lock/unlock operations write here.
    """
    user_display    = serializers.StringRelatedField(source='user', read_only=True)
    available_balance = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True
    )

    class Meta:
        model = Wallet
        fields = [
            'id', 'user', 'user_display',
            'balance_usd', 'balance_virtual',
            'total_earned_usd', 'total_paid_usd',
            'available_balance',
            'is_locked', 'locked_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_display',
            'balance_usd', 'balance_virtual',
            'total_earned_usd', 'total_paid_usd',
            'available_balance',
            'created_at', 'updated_at',
        ]


class WalletLockSerializer(serializers.ModelSerializer):
    """Used by admin to lock / unlock a wallet."""
    class Meta:
        model = Wallet
        fields = ['is_locked', 'locked_reason']

    def validate(self, data):
        if data.get('is_locked') and not data.get('locked_reason', '').strip():
            raise serializers.ValidationError(
                {'locked_reason': 'A reason is required when locking a wallet.'}
            )
        return data


class WalletSummarySerializer(serializers.ModelSerializer):
    """Compact read-only summary for embedding in user profile responses."""
    available_balance = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True
    )

    class Meta:
        model = Wallet
        fields = [
            'balance_usd', 'balance_virtual',
            'total_earned_usd', 'total_paid_usd',
            'available_balance', 'is_locked',
        ]
        read_only_fields = fields


# ── Transaction ────────────────────────────────────────────────────────────────

class TransactionSerializer(serializers.ModelSerializer):
    """
    Full transaction serializer.
    Original `amount` field is kept alongside canonical `amount_usd`.
    """
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'wallet', 'user', 'user_display', 'reference_id',
            'amount', 'amount_usd', 'amount_virtual',
            'currency', 'fee_usd', 'net_usd',
            'transaction_type', 'source', 'status',
            'balance_before', 'balance_after',
            'description', 'metadata', 'ip_address',
            'created_at', 'completed_at',
        ]
        read_only_fields = [
            'id', 'user_display',
            'balance_before', 'balance_after', 'net_usd',
            'created_at', 'completed_at',
        ]
        extra_kwargs = {
            'ip_address': {'write_only': True},
            'metadata':   {'write_only': False},
        }

    def validate(self, data):
        amount_usd = data.get('amount_usd', Decimal('0'))
        amount     = data.get('amount',     Decimal('0'))
        # Ensure at least one non-zero amount is provided on create
        if self.instance is None and amount_usd == 0 and amount == 0:
            raise serializers.ValidationError(
                'Either amount_usd or amount must be non-zero.'
            )
        return data


class TransactionListSerializer(serializers.ModelSerializer):
    """Compact serializer for transaction list views."""
    class Meta:
        model = Transaction
        fields = [
            'id', 'transaction_type', 'source', 'status',
            'amount_usd', 'currency', 'description', 'created_at',
        ]
        read_only_fields = fields


class TransactionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating manual transactions (admin adjustments, bonuses).
    """
    class Meta:
        model = Transaction
        fields = [
            'wallet', 'user', 'reference_id',
            'amount', 'amount_usd', 'amount_virtual',
            'currency', 'fee_usd',
            'transaction_type', 'source',
            'description', 'metadata', 'ip_address',
        ]

    def validate_amount_usd(self, value):
        if value < 0:
            raise serializers.ValidationError('amount_usd cannot be negative.')
        return value


# ── PayoutRequest ──────────────────────────────────────────────────────────────

class PayoutRequestSerializer(serializers.ModelSerializer):
    """
    Full PayoutRequest serializer — used by admin and payout management views.
    """
    user_display = serializers.StringRelatedField(source='user', read_only=True)

    class Meta:
        model = PayoutRequest
        fields = [
            'id', 'user', 'user_display', 'transaction',
            'amount_requested', 'fee', 'amount_net',
            'method', 'destination', 'status',
            'fraud_score', 'admin_notes', 'rejection_reason',
            'external_ref',
            'created_at', 'processed_at',
        ]
        read_only_fields = [
            'id', 'user_display', 'amount_net',
            'created_at', 'processed_at',
        ]

    def validate_amount_requested(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Payout amount must be greater than zero.'
            )
        return value


class PayoutRequestCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for a user submitting a new payout request.
    User-facing: destination + method + amount only.
    """
    class Meta:
        model = PayoutRequest
        fields = ['amount_requested', 'method', 'destination']

    def validate_amount_requested(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Payout amount must be greater than zero.'
            )
        return value

    def validate_method(self, value):
        allowed = [m[0] for m in PayoutRequest.METHOD_CHOICES]
        if value not in allowed:
            raise serializers.ValidationError(
                f"'{value}' is not a valid payout method. Choose from: {allowed}"
            )
        return value


class PayoutRequestListSerializer(serializers.ModelSerializer):
    """Compact serializer for payout list views."""
    class Meta:
        model = PayoutRequest
        fields = [
            'id', 'amount_requested', 'amount_net',
            'method', 'status', 'fraud_score',
            'created_at', 'processed_at',
        ]
        read_only_fields = fields


class PayoutRequestStatusSerializer(serializers.Serializer):
    """
    Used for approve / reject / paid actions on a PayoutRequest.
    """
    status = serializers.ChoiceField(
        choices=[
            (PayoutRequest.STATUS_APPROVED, 'Approved'),
            (PayoutRequest.STATUS_REJECTED, 'Rejected'),
            (PayoutRequest.STATUS_PAID,     'Paid'),
        ]
    )
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    external_ref = serializers.CharField(
        required=False, allow_blank=True, max_length=255,
        help_text='Payment gateway transaction ID (required when marking Paid)',
    )
    admin_notes = serializers.CharField(
        required=False, allow_blank=True
    )

    def validate(self, data):
        if data['status'] == PayoutRequest.STATUS_REJECTED and not data.get('rejection_reason', '').strip():
            raise serializers.ValidationError(
                {'rejection_reason': 'Required when rejecting.'}
            )
        if data['status'] == PayoutRequest.STATUS_PAID and not data.get('external_ref', '').strip():
            raise serializers.ValidationError(
                {'external_ref': 'Required when marking as Paid.'}
            )
        return data


# ── ReconciliationLog ─────────────────────────────────────────────────────────

class ReconciliationLogSerializer(serializers.ModelSerializer):
    """
    Full reconciliation log serializer — admin / internal audit use.
    """
    run_by_display = serializers.StringRelatedField(source='run_by', read_only=True)

    class Meta:
        model = ReconciliationLog
        fields = [
            'id', 'date',
            'total_credited', 'total_debited', 'total_fees', 'total_payouts',
            'transaction_count', 'payout_count',
            'discrepancy_usd', 'is_balanced',
            'notes', 'run_by', 'run_by_display',
            'created_at',
        ]
        read_only_fields = [
            'id', 'run_by_display', 'created_at',
        ]


class ReconciliationLogListSerializer(serializers.ModelSerializer):
    """Compact serializer for reconciliation list views."""
    class Meta:
        model = ReconciliationLog
        fields = [
            'id', 'date',
            'total_credited', 'total_debited', 'discrepancy_usd',
            'is_balanced', 'transaction_count', 'payout_count',
            'created_at',
        ]
        read_only_fields = fields
