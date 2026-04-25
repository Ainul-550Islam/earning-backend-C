# api/payment_gateways/schedules/views.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from core.views import BaseViewSet
from .models import PaymentSchedule, ScheduledPayout, EarlyPaymentRequest
from .serializers import (PaymentScheduleSerializer, ScheduledPayoutSerializer,
                          EarlyPaymentRequestSerializer, RequestEarlyPaymentSerializer)

class PaymentScheduleViewSet(BaseViewSet):
    queryset           = PaymentSchedule.objects.all().order_by('-created_at')
    serializer_class   = PaymentScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        schedule = self.get_object()
        schedule.calculate_next_payout()
        return self.success_response(data=PaymentScheduleSerializer(schedule).data,
                                     message='Next payout date recalculated')

class ScheduledPayoutViewSet(BaseViewSet):
    queryset           = ScheduledPayout.objects.all().order_by('-scheduled_date')
    serializer_class   = ScheduledPayoutSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend]
    filterset_fields   = ['status','payment_method']

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

class EarlyPaymentViewSet(BaseViewSet):
    queryset           = EarlyPaymentRequest.objects.all().order_by('-created_at')
    serializer_class   = EarlyPaymentRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def request_early(self, request):
        """User requests early payment (before scheduled date)."""
        s = RequestEarlyPaymentSerializer(data=request.data, context={'request': request})
        s.is_valid(raise_exception=True)
        d = s.validated_data

        # Validate balance
        balance = getattr(request.user, 'balance', 0) or 0
        if d['amount'] > balance:
            return self.error_response(message=f'Insufficient balance. Available: {balance}', status_code=400)

        req = EarlyPaymentRequest.objects.create(
            user           = request.user,
            amount         = d['amount'],
            payment_method = d['payment_method'],
            payment_account= d['payment_account'],
            reason         = d.get('reason', ''),
        )
        return self.success_response(
            data=EarlyPaymentRequestSerializer(req).data,
            message=f'Early payment request submitted. Fee: {req.early_fee} (15%). Net: {req.net_amount}. Admin will process within 24h.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Admin approves early payment request."""
        req = self.get_object()
        if req.status != 'pending':
            return self.error_response(message=f'Cannot approve: status is {req.status}', status_code=400)

        req.status       = 'approved'
        req.approved_by  = request.user
        req.admin_notes  = request.data.get('notes', '')
        req.save()

        # Process payout
        try:
            from api.payment_gateways.services.PaymentFactory import PaymentFactory
            processor = PaymentFactory.get_processor(req.payment_method)

            class _M:
                account_number = req.payment_account
                account_name   = req.user.get_full_name() or req.user.username
                gateway        = req.payment_method

            processor.process_withdrawal(user=req.user, amount=req.net_amount, payment_method=_M())
            req.status       = 'processed'
            req.processed_at = timezone.now()
            req.save()
        except Exception as e:
            return self.error_response(message=str(e), status_code=500)

        return self.success_response(
            data=EarlyPaymentRequestSerializer(req).data,
            message='Early payment approved and processed'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        req            = self.get_object()
        req.status     = 'rejected'
        req.admin_notes= request.data.get('reason', 'Rejected by admin')
        req.save()
        return self.success_response(message='Early payment rejected')
