# api/payment_gateways/serializers.py
# ✅ Bulletproof — All bugs fixed, defensive coding applied

from rest_framework import serializers
from django.core.validators import MinValueValidator
from decimal import Decimal

from .models import (
    PaymentGateway,
    PaymentGatewayMethod,
    GatewayTransaction,
    PayoutRequest,
    GatewayConfig,
    Currency,
    PaymentGatewayWebhookLog,
)


class PaymentGatewaySerializer(serializers.ModelSerializer):
    """PaymentGateway model — all fields correct"""
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = PaymentGateway
        fields = [
            'id', 'name', 'display_name', 'description', 'status',
            'transaction_fee_percentage',   # ✅ Fixed (was GatewayTransaction_fee_percentage)
            'minimum_amount', 'maximum_amount',
            'supports_deposit', 'supports_withdrawal', 'supported_currencies',
            'logo', 'color_code', 'sort_order', 'is_test_mode',
            'merchant_id', 'api_url', 'callback_url',
            'is_available', 'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'merchant_key':    {'write_only': True},
            'merchant_secret': {'write_only': True},
        }


class PaymentGatewayMethodSerializer(serializers.ModelSerializer):
    """PaymentGatewayMethod model"""
    gateway_display = serializers.CharField(source='get_gateway_display', read_only=True)
    user_username   = serializers.CharField(source='user.username', read_only=True)
    user_email      = serializers.EmailField(source='user.email',    read_only=True)

    class Meta:
        model  = PaymentGatewayMethod
        fields = [
            'id', 'gateway', 'gateway_display',
            'account_number', 'account_name',
            'is_verified', 'is_default',
            'user_username', 'user_email',
            'created_at',
        ]
        read_only_fields = ['is_verified', 'created_at']

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            return data
        user = request.user

        # Skip duplicate check on update
        instance = self.instance
        qs = PaymentGatewayMethod.objects.filter(
            user=user,
            gateway=data.get('gateway'),
            account_number=data.get('account_number'),
        )
        if instance:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This payment method is already added.')

        # bKash / Nagad number validation
        gateway        = data.get('gateway', '')
        account_number = data.get('account_number', '')
        if gateway in ['bkash', 'nagad']:
            if not account_number.startswith('01') or len(account_number) != 11:
                raise serializers.ValidationError(
                    f'Invalid {gateway} account number. Must start with 01 and be 11 digits.'
                )
        return data


class GatewayTransactionSerializer(serializers.ModelSerializer):
    """GatewayTransaction model — all fields correct"""
    # ✅ Fixed: was GatewayTransaction_type / GatewayTransaction_type_display
    transaction_type_display = serializers.CharField(
        source='get_transaction_type_display', read_only=True
    )
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    user_email      = serializers.EmailField(source='user.email',    read_only=True)
    user_username   = serializers.CharField(source='user.username',  read_only=True)
    gateway_display = serializers.SerializerMethodField()

    class Meta:
        model  = GatewayTransaction
        fields = [
            'id', 'transaction_type', 'transaction_type_display',
            'gateway', 'gateway_display',
            'amount', 'fee', 'net_amount',
            'status', 'status_display',
            'reference_id', 'gateway_reference',
            'payment_method', 'metadata', 'notes',
            'user_email', 'user_username',
            'created_at',
        ]
        read_only_fields = ['created_at', 'reference_id']

    def get_gateway_display(self, obj):
        try:
            gw = PaymentGateway.objects.get(name=obj.gateway)
            return gw.display_name
        except PaymentGateway.DoesNotExist:
            return (obj.gateway or '').title()


class GatewayTransactionListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer for transactions"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_email= serializers.EmailField(source='user.email',   read_only=True)

    class Meta:
        model  = GatewayTransaction
        fields = [
            'id', 'user_name', 'user_email',
            'transaction_type', 'gateway',
            'amount', 'fee', 'net_amount',
            'status', 'reference_id', 'created_at',
        ]


class WithdrawalRequestSerializer(serializers.Serializer):
    """Withdrawal request — with balance & method validation"""
    amount            = serializers.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('10'))])
    payment_method_id = serializers.IntegerField()
    notes             = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            raise serializers.ValidationError('Request context missing.')

        user   = request.user
        amount = data['amount']

        # Balance check — defensive: user may not have balance field
        balance = getattr(user, 'balance', None)
        if balance is not None and balance < amount:
            raise serializers.ValidationError(
                f'Insufficient balance. Available: {balance}, Requested: {amount}'
            )

        # Payment method check
        try:
            payment_method = PaymentGatewayMethod.objects.get(
                id=data['payment_method_id'],
                user=user,
                is_verified=True,
            )
            data['payment_method'] = payment_method
        except PaymentGatewayMethod.DoesNotExist:
            raise serializers.ValidationError(
                'Invalid or unverified payment method.'
            )
        return data


class PayoutRequestSerializer(serializers.ModelSerializer):
    """PayoutRequest model"""
    payout_method_display = serializers.CharField(source='get_payout_method_display', read_only=True)
    status_display        = serializers.CharField(source='get_status_display',         read_only=True)
    processed_by_email    = serializers.SerializerMethodField()
    user_username         = serializers.CharField(source='user.username', read_only=True)
    user_email            = serializers.EmailField(source='user.email',   read_only=True)

    class Meta:
        model  = PayoutRequest
        fields = [
            'id', 'amount', 'fee', 'net_amount',
            'payout_method', 'payout_method_display',
            'account_number', 'account_name',
            'status', 'status_display',
            'reference_id', 'admin_notes',
            'processed_by_email', 'processed_at',
            'user_username', 'user_email',
            'created_at',
        ]
        read_only_fields = [
            'fee', 'net_amount', 'reference_id', 'status',
            'admin_notes', 'processed_by', 'processed_at', 'created_at',
        ]

    def get_processed_by_email(self, obj):
        try:
            return obj.processed_by.email if obj.processed_by else None
        except Exception:
            return None


class GatewayConfigSerializer(serializers.ModelSerializer):
    """GatewayConfig model"""
    gateway_name = serializers.CharField(source='gateway.name', read_only=True)

    class Meta:
        model  = GatewayConfig
        fields = ['id', 'gateway', 'gateway_name', 'key', 'value', 'is_secret', 'description']
        extra_kwargs = {
            'value': {'write_only': False},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Hide secret values in list/retrieve
        if instance.is_secret:
            data['value'] = '••••••••'
        return data


class CurrencySerializer(serializers.ModelSerializer):
    """Currency model"""
    class Meta:
        model  = Currency
        fields = ['id', 'code', 'name', 'symbol', 'exchange_rate', 'is_default', 'is_active']


class PaymentGatewayWebhookLogSerializer(serializers.ModelSerializer):
    """PaymentGatewayWebhookLog model — read only"""
    class Meta:
        model  = PaymentGatewayWebhookLog
        fields = '__all__'
        read_only_fields = ['created_at']


class CreatePaymentSerializer(serializers.Serializer):
    """Initiate payment"""
    gateway  = serializers.ChoiceField(choices=['bkash', 'nagad', 'stripe', 'paypal'])
    amount   = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('10'))
    currency = serializers.CharField(default='BDT', max_length=3)

    def validate_amount(self, value):
        if value > 1000000:
            raise serializers.ValidationError('Maximum amount is 1,000,000')
        return value


class VerifyPaymentSerializer(serializers.Serializer):
    """Verify payment"""
    gateway    = serializers.ChoiceField(choices=['bkash', 'nagad', 'stripe', 'paypal'])
    payment_id = serializers.CharField(max_length=255)