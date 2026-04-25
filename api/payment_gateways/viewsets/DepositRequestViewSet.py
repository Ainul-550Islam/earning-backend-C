# viewsets/DepositRequestViewSet.py
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from core.views import BaseViewSet
from api.payment_gateways.models.deposit import DepositRequest, DepositRefund
from rest_framework import serializers


class DepositRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DepositRequest
        fields = ['id','gateway','amount','fee','net_amount','currency','status',
                  'reference_id','payment_url','initiated_at','completed_at','metadata']
        read_only_fields = ['fee','net_amount','reference_id','payment_url','initiated_at']


class DepositRequestViewSet(BaseViewSet):
    """Deposit request management. Initiate, verify, list."""
    queryset           = DepositRequest.objects.all().order_by('-initiated_at')
    serializer_class   = DepositRequestSerializer
    permission_classes = [IsAuthenticated]
    filter_backends    = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields   = ['gateway', 'status', 'currency']

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """Initiate a new deposit."""
        from api.payment_gateways.services.DepositService import DepositService
        from decimal import Decimal
        data    = request.data
        gateway = data.get('gateway', 'bkash')
        amount  = Decimal(str(data.get('amount', '0')))
        currency= data.get('currency', 'BDT')

        if amount <= 0:
            return self.error_response(message='Invalid amount', status_code=400)
        svc = DepositService()
        try:
            result = svc.initiate(
                user=request.user, amount=amount, gateway=gateway,
                currency=currency,
                ip=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
            )
            return self.success_response(data=result, message='Deposit initiated')
        except PermissionError as e:
            return self.error_response(message=str(e), status_code=403)
        except Exception as e:
            return self.error_response(message=str(e), status_code=400)

    @action(detail=True, methods=['get'])
    def verify(self, request, pk=None):
        """Re-verify a pending deposit via gateway API."""
        deposit = self.get_object()
        from api.payment_gateways.services.PaymentFactory import PaymentFactory
        try:
            processor = PaymentFactory.get_processor(deposit.gateway)
            result    = processor.verify_payment(deposit.session_key or deposit.gateway_ref)
            return self.success_response(data={'verified': result is not None})
        except Exception as e:
            return self.error_response(message=str(e))

    @action(detail=False, methods=['get'])
    def my_deposits(self, request):
        """Current user's deposit history."""
        qs   = self.get_queryset().filter(user=request.user)
        page = self.paginate_queryset(qs)
        s    = DepositRequestSerializer(page or qs, many=True)
        return self.get_paginated_response(s.data) if page else self.success_response(data=s.data)
