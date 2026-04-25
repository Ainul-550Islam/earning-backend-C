# viewsets/DepositRefundViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from core.views import BaseViewSet
from api.payment_gateways.models.deposit import DepositRefund, DepositRequest
from rest_framework import serializers


class DepositRefundSerializer(serializers.ModelSerializer):
    deposit_ref = serializers.CharField(source='deposit.reference_id', read_only=True)
    class Meta:
        model  = DepositRefund
        fields = ['id','deposit_ref','refund_amount','reason','reason_detail','status',
                  'gateway_refund_id','refunded_at','rejection_reason','created_at']
        read_only_fields = ['status','gateway_refund_id','refunded_at','rejection_reason']


class DepositRefundViewSet(BaseViewSet):
    queryset           = DepositRefund.objects.all().order_by('-created_at')
    serializer_class   = DepositRefundSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(deposit__user=self.request.user)

    @action(detail=False, methods=['post'])
    def request_refund(self, request):
        """Request refund for a deposit."""
        from decimal import Decimal
        deposit_id = request.data.get('deposit_id')
        amount     = Decimal(str(request.data.get('amount', '0')))
        reason     = request.data.get('reason', 'customer_request')
        detail     = request.data.get('reason_detail', '')

        try:
            deposit = DepositRequest.objects.get(id=deposit_id, user=request.user, status='completed')
        except DepositRequest.DoesNotExist:
            return self.error_response(message='Deposit not found or not refundable.', status_code=404)

        if amount <= 0 or amount > deposit.amount:
            return self.error_response(message='Invalid refund amount.', status_code=400)

        refund = DepositRefund.objects.create(
            deposit=deposit, requested_by=request.user,
            refund_amount=amount, reason=reason, reason_detail=detail
        )
        return self.success_response(
            data=DepositRefundSerializer(refund).data,
            message='Refund request submitted. Admin will review within 24 hours.'
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        from django.utils import timezone
        refund = self.get_object()
        refund.status      = 'approved'
        refund.approved_by = request.user
        refund.save()
        return self.success_response(message='Refund approved.')

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reject(self, request, pk=None):
        refund = self.get_object()
        refund.status           = 'rejected'
        refund.rejection_reason = request.data.get('reason', 'Rejected by admin')
        refund.save()
        return self.success_response(message='Refund rejected.')
