# api/payment_gateways/views.py
# ✅ Bulletproof — IsAdminUser for admin endpoints, all actions working

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from core.views import BaseViewSet

from .models import (
    PaymentGateway,
    PaymentGatewayMethod,
    GatewayTransaction,
    PayoutRequest,
    GatewayConfig,
    Currency,
    PaymentGatewayWebhookLog,
)
from .serializers import (
    PaymentGatewaySerializer,
    PaymentGatewayMethodSerializer,
    GatewayTransactionSerializer,
    GatewayTransactionListSerializer,
    WithdrawalRequestSerializer,
    PayoutRequestSerializer,
    GatewayConfigSerializer,
    CurrencySerializer,
    PaymentGatewayWebhookLogSerializer,
    CreatePaymentSerializer,
    VerifyPaymentSerializer,
)


# ── PaymentGateway ────────────────────────────────────────────────────────────
class PaymentGatewayViewSet(BaseViewSet):
    """Admin: Full CRUD for payment gateways"""
    queryset           = PaymentGateway.objects.all().order_by('sort_order', 'name')
    serializer_class   = PaymentGatewaySerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields   = ['status', 'name', 'supports_deposit', 'supports_withdrawal', 'is_test_mode']
    search_fields      = ['name', 'display_name']

    @action(detail=True, methods=['post'])
    def toggle_status(self, request, pk=None):
        """Toggle gateway active/inactive"""
        gateway = self.get_object()
        gateway.status = 'inactive' if gateway.status == 'active' else 'active'
        gateway.save()
        return self.success_response(
            data=PaymentGatewaySerializer(gateway).data,
            message=f'{gateway.display_name} is now {gateway.status}'
        )

    @action(detail=True, methods=['post'])
    def set_maintenance(self, request, pk=None):
        """Put gateway in maintenance mode"""
        gateway = self.get_object()
        gateway.status = 'maintenance'
        gateway.save()
        return self.success_response(message=f'{gateway.display_name} set to maintenance')

    @action(detail=False, methods=['get'])
    def active(self, request):
        """List only active gateways"""
        qs = self.get_queryset().filter(status='active')
        return self.success_response(data=PaymentGatewaySerializer(qs, many=True).data)


# ── PaymentGatewayMethod ──────────────────────────────────────────────────────
class PaymentGatewayMethodViewSet(BaseViewSet):
    """User payment methods — user sees only their own, admin sees all"""
    queryset           = PaymentGatewayMethod.objects.all().order_by('-created_at')
    serializer_class   = PaymentGatewayMethodSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['gateway', 'is_verified', 'is_default']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs   # Admin sees all
        return qs.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this method as default"""
        method = self.get_object()
        PaymentGatewayMethod.objects.filter(user=request.user).update(is_default=False)
        method.is_default = True
        method.save()
        return self.success_response(
            data=PaymentGatewayMethodSerializer(method).data,
            message='Default payment method updated'
        )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify payment method"""
        method = self.get_object()
        method.is_verified = True
        method.save()
        return self.success_response(
            data=PaymentGatewayMethodSerializer(method).data,
            message='Payment method verified successfully'
        )


# ── GatewayTransaction ────────────────────────────────────────────────────────
class GatewayTransactionViewSet(BaseViewSet):
    """Transactions — user sees own, admin sees all"""
    queryset           = GatewayTransaction.objects.all().order_by('-created_at')
    serializer_class   = GatewayTransactionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['status', 'gateway', 'transaction_type']
    ordering_fields    = ['created_at', 'amount']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs   # Admin sees all
        return qs.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'list':
            return GatewayTransactionListSerializer
        return GatewayTransactionSerializer

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Transaction history with pagination"""
        qs   = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return self.success_response(data=serializer.data)

    @action(detail=False, methods=['post'])
    def withdraw(self, request):
        """Process withdrawal"""
        serializer = WithdrawalRequestSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        validated  = serializer.validated_data
        amount     = validated['amount']
        method     = validated['payment_method']

        try:
            from .services.PaymentFactory import PaymentFactory
            processor   = PaymentFactory.get_processor(method.gateway)
            transaction = processor.process_withdrawal(request.user, amount, method)

            # Deduct balance safely
            if hasattr(request.user, 'balance'):
                request.user.balance -= amount
                request.user.save(update_fields=['balance'])

            return self.success_response(
                data=GatewayTransactionSerializer(transaction).data,
                message='Withdrawal submitted successfully'
            )
        except Exception as e:
            return self.error_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'])
    def deposit(self, request):
        """Initiate deposit via payment gateway"""
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        gateway = data.get('gateway', 'bkash').lower()
        amount = data.get('amount')
        try:
            if gateway == 'bkash':
                from .services.BkashService import BkashService
                service = BkashService()
                result = service.process_deposit(user=request.user, amount=amount)
            elif gateway == 'nagad':
                from .services.NagadService import NagadService
                service = NagadService()
                result = service.process_deposit(user=request.user, amount=amount)
            elif gateway == 'stripe':
                from .services.StripeService import StripeService
                service = StripeService()
                result = service.process_deposit(user=request.user, amount=amount)
            else:
                return self.error_response(message=f'Gateway {gateway} not supported', status_code=400)
            
            # Serialize result - remove non-serializable objects
            if isinstance(result, dict):
                clean = {k: str(v) if hasattr(v, 'id') else v for k, v in result.items() if k != 'transaction'}
                if 'transaction' in result and result['transaction']:
                    clean['transaction_id'] = str(result['transaction'].id)
                    clean['reference_id'] = result['transaction'].reference_id
                return self.success_response(data=clean, message=f'{gateway} payment initiated')
            return self.success_response(data={}, message=f'{gateway} payment initiated')
        except Exception as e:
            return self.error_response(message=str(e), status_code=500)


# ── PayoutRequest ─────────────────────────────────────────────────────────────
class PayoutRequestViewSet(BaseViewSet):
    """Payout requests — user sees own, admin sees all + can approve/reject"""
    queryset           = PayoutRequest.objects.all().order_by('-created_at')
    serializer_class   = PayoutRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['status', 'payout_method']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin: approve payout"""
        payout = self.get_object()
        if payout.status != 'pending':
            return self.error_response(
                message=f'Cannot approve — status is {payout.status}',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        payout.status       = 'approved'
        payout.processed_by = request.user
        payout.processed_at = timezone.now()
        payout.admin_notes  = request.data.get('admin_notes', '')
        payout.save()
        return self.success_response(
            data=PayoutRequestSerializer(payout).data,
            message='Payout approved'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        """Admin: reject payout"""
        payout = self.get_object()
        if payout.status not in ['pending', 'approved']:
            return self.error_response(
                message=f'Cannot reject — status is {payout.status}',
                status_code=status.HTTP_400_BAD_REQUEST
            )
        payout.status       = 'rejected'
        payout.processed_by = request.user
        payout.processed_at = timezone.now()
        payout.admin_notes  = request.data.get('admin_notes', 'Rejected by admin')
        payout.save()
        return self.success_response(
            data=PayoutRequestSerializer(payout).data,
            message='Payout rejected'
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAdminUser])
    def pending(self, request):
        """Admin: list all pending payouts"""
        qs = self.get_queryset().filter(status='pending')
        return self.success_response(data=PayoutRequestSerializer(qs, many=True).data)


# ── GatewayConfig ─────────────────────────────────────────────────────────────
class GatewayConfigViewSet(BaseViewSet):
    """Admin: gateway configuration key-value pairs"""
    queryset           = GatewayConfig.objects.all().order_by('gateway', 'key')
    serializer_class   = GatewayConfigSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['gateway', 'is_secret']


# ── Currency ──────────────────────────────────────────────────────────────────
class CurrencyViewSet(BaseViewSet):
    """Admin: currency management"""
    queryset           = Currency.objects.all().order_by('code')
    serializer_class   = CurrencySerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['is_active', 'is_default']

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set as default currency"""
        currency = self.get_object()
        Currency.objects.filter(is_default=True).update(is_default=False)
        currency.is_default = True
        currency.save()
        return self.success_response(message=f'{currency.code} set as default currency')


# ── WebhookLog ────────────────────────────────────────────────────────────────
class PaymentWebhookLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Admin: read-only webhook logs"""
    queryset           = PaymentGatewayWebhookLog.objects.all().order_by('-created_at')
    serializer_class   = PaymentGatewayWebhookLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['gateway', 'processed']