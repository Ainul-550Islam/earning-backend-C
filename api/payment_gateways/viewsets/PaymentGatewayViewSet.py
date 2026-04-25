# viewsets/PaymentGatewayViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from api.payment_gateways.models.core import PaymentGateway, GatewayTransaction, PayoutRequest
from rest_framework import serializers, filters
from django_filters.rest_framework import DjangoFilterBackend


class PaymentGatewaySerializer(serializers.ModelSerializer):
    is_available = serializers.BooleanField(read_only=True)
    class Meta:
        model  = PaymentGateway
        fields = ['id','name','display_name','status','is_test_mode','transaction_fee_percentage',
                  'minimum_amount','maximum_amount','supports_deposit','supports_withdrawal',
                  'supported_currencies','color_code','region','health_status',
                  'avg_response_time_ms','sort_order','is_available']

class GatewayTransactionSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    class Meta:
        model  = GatewayTransaction
        fields = ['id','user_email','transaction_type','gateway','amount','fee','net_amount',
                  'currency','status','reference_id','gateway_reference','completed_at',
                  'created_at','metadata']
        read_only_fields = ['fee','net_amount','reference_id','completed_at','created_at']

class PayoutRequestSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    class Meta:
        model  = PayoutRequest
        fields = ['id','user_email','amount','fee','net_amount','currency','payout_method',
                  'account_number','account_name','status','reference_id','admin_notes',
                  'processed_at','created_at']


class PaymentGatewayViewSet(BaseViewSet):
    """Payment gateway management."""
    queryset           = PaymentGateway.objects.all().order_by('sort_order')
    serializer_class   = PaymentGatewaySerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status', 'region']

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(status='active')

    @action(detail=False, methods=['get'])
    def deposit_gateways(self, request):
        qs = self.get_queryset().filter(supports_deposit=True, status='active')
        return self.success_response(data=PaymentGatewaySerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def withdrawal_gateways(self, request):
        qs = self.get_queryset().filter(supports_withdrawal=True, status='active')
        return self.success_response(data=PaymentGatewaySerializer(qs, many=True).data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def toggle_status(self, request, pk=None):
        gw = self.get_object()
        gw.status = 'inactive' if gw.status == 'active' else 'active'
        gw.save(update_fields=['status'])
        return self.success_response(message=f'{gw.name} status → {gw.status}')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def toggle_test_mode(self, request, pk=None):
        gw = self.get_object()
        gw.is_test_mode = not gw.is_test_mode
        gw.save(update_fields=['is_test_mode'])
        mode = 'sandbox' if gw.is_test_mode else 'LIVE'
        return self.success_response(message=f'{gw.name} → {mode} mode')


class GatewayTransactionViewSet(BaseViewSet):
    """Transaction history and management."""
    queryset           = GatewayTransaction.objects.all().order_by('-created_at')
    serializer_class   = GatewayTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['status', 'gateway', 'transaction_type', 'currency']

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def history(self, request):
        qs   = self.get_queryset().filter(user=request.user)
        page = self.paginate_queryset(qs)
        s    = GatewayTransactionSerializer(page or qs, many=True)
        return self.get_paginated_response(s.data) if page else self.success_response(data=s.data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        from django.db.models import Sum, Count
        agg = self.get_queryset().filter(
            user=request.user, status='completed'
        ).aggregate(
            total_deposits=Sum('amount', filter=__import__('django.db.models',fromlist=['Q']).Q(transaction_type='deposit')),
            total_withdrawals=Sum('amount', filter=__import__('django.db.models',fromlist=['Q']).Q(transaction_type='withdrawal')),
            count=Count('id'),
        )
        return self.success_response(data=agg)


class WithdrawalGatewayViewSet(BaseViewSet):
    """User withdrawal / payout request management."""
    queryset           = PayoutRequest.objects.all().order_by('-created_at')
    serializer_class   = PayoutRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status', 'payout_method']

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        import time
        from decimal import Decimal
        from api.payment_gateways.services.GatewayRouterService import GatewayRouterService
        amount = serializer.validated_data['amount']
        gateway = serializer.validated_data.get('payout_method', 'bkash')
        fee_pct = Decimal('0.015')
        fee     = amount * fee_pct
        serializer.save(
            user=self.request.user,
            fee=fee,
            net_amount=amount - fee,
            reference_id=f'PAY-{gateway.upper()}-{int(time.time()*1000)}',
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        payout = self.get_object()
        if payout.status != 'pending':
            return self.error_response(message=f'Cannot approve: status is {payout.status}', status_code=400)
        payout.status      = 'approved'
        payout.admin_notes = request.data.get('notes', '')
        payout.save()
        # Process immediately
        from api.payment_gateways.tasks.withdrawal_processing_tasks import retry_failed_payout
        retry_failed_payout.delay(payout.id)
        return self.success_response(message='Payout approved and queued for processing.')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        payout            = self.get_object()
        payout.status     = 'rejected'
        payout.admin_notes= request.data.get('reason', 'Rejected by admin')
        payout.save()
        return self.success_response(message='Payout rejected.')

    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        payout = self.get_object()
        try:
            from api.payment_gateways.models.withdrawal import WithdrawalReceipt
            from rest_framework import serializers as s
            class RS(s.ModelSerializer):
                class Meta:
                    model  = WithdrawalReceipt
                    fields = '__all__'
            receipt = WithdrawalReceipt.objects.get(payout_request=payout)
            return self.success_response(data=RS(receipt).data)
        except Exception:
            return self.error_response(message='Receipt not available yet.', status_code=404)
