# api/djoyalty/serializers/CashoutSerializer.py
"""
Djoyalty Cashout Serializers।

AUDIT FIX (v2 -- Validation):
  CashoutRequestCreateSerializer.validate() previously checked destination
  method/account pairing but did NOT validate whether the customer has a
  sufficient points balance।  Balance is checked in CashoutService but if
  the serializer is ever reused outside the viewset (admin commands, Celery
  tasks, management scripts) the balance check is silently skipped।

  FIX: Added balance check in CashoutRequestCreateSerializer.validate()。
  Uses the customer passed via serializer context।  Fails gracefully if
  context['customer'] is not provided (backward compatibility)।

  Additionally: min_points guard added -- points_to_redeem must be > 0
  (already was) AND the serializer now surfaces a clear error when the
  customer's available_balance < points_to_redeem, matching the exact
  message format used by CashoutService so clients see consistent errors।
"""
from decimal import Decimal
from rest_framework import serializers
from ..models.cashout import (
    CashoutRequest, CashoutRate,
    CustomerBankAccount, CustomerMobileWallet,
    WalletTransaction,
)


# ─── Bank Account ─────────────────────────────────────────────────────────────

class CustomerBankAccountSerializer(serializers.ModelSerializer):
    masked_account = serializers.SerializerMethodField()

    class Meta:
        model = CustomerBankAccount
        fields = [
            'id', 'customer', 'bank_name', 'masked_account',
            'account_holder_name', 'routing_number', 'branch_name',
            'is_verified', 'is_primary', 'is_active',
            'verified_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'is_verified', 'masked_account', 'verified_at',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'account_number': {'write_only': True},  # never returned raw
        }

    def get_masked_account(self, obj) -> str:
        num = obj.account_number or ''
        if len(num) > 4:
            return f'****{num[-4:]}'
        return '****'


class CustomerBankAccountCreateSerializer(serializers.ModelSerializer):
    """Used for creating a new bank account -- account_number is write-only."""

    class Meta:
        model = CustomerBankAccount
        fields = [
            'bank_name', 'account_number', 'account_holder_name',
            'routing_number', 'branch_name', 'is_primary',
        ]

    def validate_account_number(self, value):
        if not value or len(value.strip()) < 6:
            raise serializers.ValidationError('Account number must be at least 6 characters.')
        return value.strip()


# ─── Mobile Wallet ────────────────────────────────────────────────────────────

class CustomerMobileWalletSerializer(serializers.ModelSerializer):
    masked_phone = serializers.SerializerMethodField()

    class Meta:
        model = CustomerMobileWallet
        fields = [
            'id', 'customer', 'wallet_provider', 'masked_phone',
            'account_name', 'is_verified', 'is_primary', 'is_active',
            'verified_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'is_verified', 'masked_phone', 'verified_at',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'phone_number': {'write_only': True},
        }

    def get_masked_phone(self, obj) -> str:
        phone = obj.phone_number or ''
        if len(phone) > 4:
            return f'****{phone[-4:]}'
        return '****'


class CustomerMobileWalletCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerMobileWallet
        fields = ['wallet_provider', 'phone_number', 'account_name', 'is_primary']

    def validate(self, data):
        customer = self.context.get('customer')
        if customer and CustomerMobileWallet.objects.filter(
            customer=customer,
            wallet_provider=data['wallet_provider'],
            phone_number=data['phone_number'],
        ).exists():
            raise serializers.ValidationError(
                'This mobile wallet number is already registered for this provider.'
            )
        return data


# ─── Cashout Rate ──────────────────────────────────────────────────────────────

class CashoutRateSerializer(serializers.ModelSerializer):
    """Public rate info -- used to show customer how much they'll receive."""
    cash_per_100_points = serializers.SerializerMethodField()

    class Meta:
        model = CashoutRate
        fields = [
            'id', 'cashout_method',
            'points_per_unit', 'cash_per_100_points',
            'min_cashout_points', 'max_cashout_points_per_day',
            'processing_fee_percent', 'min_tier_required',
            'is_active',
        ]
        read_only_fields = fields

    def get_cash_per_100_points(self, obj) -> str:
        """Human-readable: how much cash for 100 points."""
        if obj.points_per_unit and obj.points_per_unit > 0:
            rate = Decimal('100') / obj.points_per_unit
            return f'{rate:.4f}'
        return '0'


# ─── Cashout Request ───────────────────────────────────────────────────────────

class CashoutRequestSerializer(serializers.ModelSerializer):
    """Full view -- for customer's own requests or admin."""
    customer_code = serializers.SerializerMethodField()
    bank_account_display = CustomerBankAccountSerializer(source='bank_account', read_only=True)
    mobile_wallet_display = CustomerMobileWalletSerializer(source='mobile_wallet', read_only=True)

    class Meta:
        model = CashoutRequest
        fields = [
            'id', 'customer', 'customer_code',
            'points_to_redeem', 'cash_amount', 'conversion_rate', 'currency',
            'cashout_method',
            'bank_account', 'bank_account_display',
            'mobile_wallet', 'mobile_wallet_display',
            'status', 'reference', 'payment_reference',
            'reviewed_by', 'reviewed_at', 'completed_at',
            'rejection_reason',
            'fraud_score', 'is_flagged',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'customer_code', 'cash_amount', 'conversion_rate',
            'status', 'reference', 'payment_reference',
            'reviewed_by', 'reviewed_at', 'completed_at',
            'fraud_score', 'is_flagged',
            'bank_account_display', 'mobile_wallet_display',
            'created_at', 'updated_at',
        ]

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''


class CashoutRequestCreateSerializer(serializers.Serializer):
    """
    Used for POST /cashouts/ -- initiate a cashout request।

    AUDIT FIX (v2): Added balance validation in validate()।
    Previously only destination method/account pairing was checked।
    The balance is now verified at the serializer level so all callers
    (viewsets, admin commands, Celery tasks) get the check consistently,
    not just paths that go through CashoutService (which still does its own
    select_for_update()-backed re-check as the authoritative guard)।
    """
    points_to_redeem = serializers.DecimalField(max_digits=14, decimal_places=2)
    cashout_method   = serializers.ChoiceField(choices=[
        'bank_transfer', 'mobile_wallet', 'gift_card', 'store_credit',
    ])
    bank_account_id  = serializers.IntegerField(required=False, allow_null=True)
    mobile_wallet_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_points_to_redeem(self, value):
        if value <= 0:
            raise serializers.ValidationError('Points to redeem must be positive.')
        return value

    def validate(self, data):
        # ── Destination method check ───────────────────────────────────────
        method = data.get('cashout_method')
        if method == 'bank_transfer' and not data.get('bank_account_id'):
            raise serializers.ValidationError(
                {'bank_account_id': 'Bank account required for bank transfer.'}
            )
        if method == 'mobile_wallet' and not data.get('mobile_wallet_id'):
            raise serializers.ValidationError(
                {'mobile_wallet_id': 'Mobile wallet required for mobile wallet cashout.'}
            )

        # ── Balance check (AUDIT FIX v2) ─────────────────────────────────
        # Validates that the customer has enough available points before
        # the request reaches CashoutService।  CashoutService still performs
        # the authoritative select_for_update() re-check before deduction।
        # This early check provides user-friendly errors at serializer level
        # for ALL callers, not just the viewset path।
        customer = self.context.get('customer')
        if customer is not None:
            try:
                from ..models.points import LoyaltyPoints
                lp = LoyaltyPoints.objects.filter(customer=customer).first()
                available = lp.available_balance if lp else Decimal('0')
                points_requested = data.get('points_to_redeem', Decimal('0'))
                if available < points_requested:
                    raise serializers.ValidationError({
                        'points_to_redeem': (
                            f'Insufficient balance: {available} available, '
                            f'{points_requested} required.'
                        )
                    })
            except serializers.ValidationError:
                raise
            except Exception:
                # If balance check fails for any unexpected reason, let
                # CashoutService's locked re-check be the guard।
                pass

        return data


class CashoutAdminActionSerializer(serializers.Serializer):
    """Used for approve/reject admin actions on cashout requests."""
    action            = serializers.ChoiceField(choices=['approve', 'reject', 'complete', 'cancel'])
    note              = serializers.CharField(required=False, allow_blank=True, max_length=500)
    payment_reference = serializers.CharField(required=False, allow_blank=True, max_length=200)


# ─── Wallet Transaction ────────────────────────────────────────────────────────

class WalletTransactionSerializer(serializers.ModelSerializer):
    """Customer's full wallet transaction history."""
    customer_code = serializers.SerializerMethodField()

    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'customer', 'customer_code',
            'transaction_type', 'points_delta',
            'cash_amount', 'currency',
            'balance_before', 'balance_after',
            'description', 'reference_id',
            'cashout_request',
            'created_at',
        ]
        read_only_fields = fields  # wallet transactions are never created via API

    def get_customer_code(self, obj) -> str:
        return obj.customer.code if obj.customer else ''
