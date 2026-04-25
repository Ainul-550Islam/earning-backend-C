# api/payment_gateways/refunds/serializers.py
# FILE 60 of 257 — Refund Serializers

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from .models import RefundRequest, RefundPolicy, RefundAuditLog
from .RefundFactory import RefundFactory


class RefundRequestSerializer(serializers.ModelSerializer):
    """Full refund request detail serializer"""

    status_display  = serializers.CharField(source='get_status_display',  read_only=True)
    reason_display  = serializers.CharField(source='get_reason_display',  read_only=True)
    gateway_display = serializers.CharField(source='get_gateway_display', read_only=True)

    user_username        = serializers.CharField(source='user.username',         read_only=True)
    user_email           = serializers.EmailField(source='user.email',           read_only=True)
    initiated_by_email   = serializers.SerializerMethodField()

    original_reference   = serializers.CharField(
        source='original_transaction.reference_id', read_only=True
    )
    original_amount      = serializers.DecimalField(
        source='original_transaction.amount',
        max_digits=10, decimal_places=2, read_only=True
    )
    is_partial           = serializers.BooleanField(read_only=True)
    supports_cancellation = serializers.SerializerMethodField()

    class Meta:
        model  = RefundRequest
        fields = [
            'id', 'gateway', 'gateway_display',
            'original_transaction', 'original_reference', 'original_amount',
            'user_username', 'user_email',
            'amount', 'is_partial',
            'status', 'status_display',
            'reason', 'reason_display',
            'reference_id', 'gateway_refund_id',
            'initiated_by_email',
            'completed_at', 'failed_at',
            'supports_cancellation',
            'notes', 'created_at',
        ]
        read_only_fields = [
            'status', 'reference_id', 'gateway_refund_id',
            'completed_at', 'failed_at', 'created_at',
        ]

    def get_initiated_by_email(self, obj):
        try:
            return obj.initiated_by.email if obj.initiated_by else None
        except Exception:
            return None

    def get_supports_cancellation(self, obj):
        return RefundFactory.supports_refund_cancellation(obj.gateway)


class RefundRequestListSerializer(serializers.ModelSerializer):
    """Lightweight list serializer"""
    user_name = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = RefundRequest
        fields = [
            'id', 'gateway', 'user_name',
            'amount', 'status',
            'reference_id', 'created_at',
        ]


class InitiateRefundSerializer(serializers.Serializer):
    """Validate a refund initiation request"""

    transaction_id = serializers.IntegerField(help_text='ID of the GatewayTransaction to refund')
    amount         = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        min_value=Decimal('1.00'),
        help_text='Amount to refund (can be partial)',
    )
    reason = serializers.ChoiceField(
        choices=[
            'duplicate', 'fraudulent', 'customer_request',
            'order_cancelled', 'service_not_provided',
            'partial_refund', 'other',
        ],
        default='customer_request',
    )
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        from api.payment_gateways.models import GatewayTransaction

        # 1. Verify transaction exists
        try:
            txn = GatewayTransaction.objects.get(id=data['transaction_id'])
        except GatewayTransaction.DoesNotExist:
            raise serializers.ValidationError({'transaction_id': 'Transaction not found.'})

        # 2. Only completed deposits can be refunded
        if txn.status != 'completed':
            raise serializers.ValidationError(
                f'Only completed transactions can be refunded. Current status: {txn.status}'
            )

        if txn.transaction_type != 'deposit':
            raise serializers.ValidationError('Only deposit transactions can be refunded.')

        # 3. Gateway must support refunds
        if not RefundFactory.supports_refund(txn.gateway):
            raise serializers.ValidationError(
                f'Gateway "{txn.gateway}" does not support refunds.'
            )

        # 4. Check refund policy
        try:
            policy = RefundPolicy.objects.get(gateway=txn.gateway, is_active=True)
            days_since = (timezone.now() - txn.created_at).days
            if days_since > policy.max_refund_days:
                raise serializers.ValidationError(
                    f'Refund window expired. This gateway allows refunds within {policy.max_refund_days} days. '
                    f'Transaction is {days_since} days old.'
                )
            if data['amount'] > policy.max_refund_amount:
                raise serializers.ValidationError(
                    f'Refund amount exceeds policy maximum of {policy.max_refund_amount}.'
                )
        except RefundPolicy.DoesNotExist:
            pass   # No policy configured — allow refund

        # 5. Amount vs refundable balance
        processor = RefundFactory.get_processor(txn.gateway)
        refundable = processor.get_refundable_amount(txn)
        if data['amount'] > refundable:
            raise serializers.ValidationError(
                f'Refund amount ({data["amount"]}) exceeds refundable balance ({refundable}).'
            )

        data['transaction'] = txn
        return data


class RefundStatusCheckSerializer(serializers.Serializer):
    """Used to manually trigger a status sync for a refund"""
    refund_id = serializers.IntegerField()


class RefundPolicySerializer(serializers.ModelSerializer):
    gateway_display = serializers.CharField(source='get_gateway_display', read_only=True)

    class Meta:
        model  = RefundPolicy
        fields = [
            'id', 'gateway', 'gateway_display',
            'auto_approve', 'max_refund_days', 'max_refund_amount',
            'allow_partial_refund', 'fee_refundable',
            'is_active', 'notes',
        ]


class RefundAuditLogSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.EmailField(source='changed_by.email', read_only=True, default=None)

    class Meta:
        model  = RefundAuditLog
        fields = [
            'id', 'refund_request', 'previous_status', 'new_status',
            'changed_by_email', 'note', 'created_at',
        ]
        read_only_fields = '__all__'
