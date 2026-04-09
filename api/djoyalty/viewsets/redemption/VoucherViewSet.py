# api/djoyalty/viewsets/redemption/VoucherViewSet.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from decimal import Decimal
from ...models.redemption import Voucher
from ...models.core import Customer
from ...serializers.VoucherSerializer import VoucherSerializer
from ...services.redemption.VoucherService import VoucherService
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsLoyaltyAdmin

class VoucherViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Voucher.objects.all().select_related('customer').order_by('-created_at')
    serializer_class = VoucherSerializer
    pagination_class = DjoyaltyPagePagination

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        v_status = self.request.query_params.get('status')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if v_status:
            qs = qs.filter(status=v_status)
        return qs

    @action(detail=False, methods=['post'], permission_classes=[IsLoyaltyAdmin])
    def generate(self, request):
        customer_id = request.data.get('customer_id')
        voucher_type = request.data.get('voucher_type', 'percent')
        discount_value = request.data.get('discount_value', 10)
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            voucher = VoucherService.generate_voucher(
                customer, voucher_type, Decimal(str(discount_value)), tenant=customer.tenant,
            )
            return Response(VoucherSerializer(voucher).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def use(self, request):
        code = request.data.get('code', '')
        customer_id = request.data.get('customer_id')
        order_ref = request.data.get('order_reference', '')
        customer = get_object_or_404(Customer, pk=customer_id)
        try:
            redemption = VoucherService.use_voucher(code, customer, order_reference=order_ref)
            return Response({'message': f'Voucher used. Discount: {redemption.discount_applied}'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def validate(self, request):
        code = request.query_params.get('code', '')
        from django.utils import timezone
        voucher = Voucher.objects.filter(code=code.upper()).first()
        if not voucher:
            return Response({'valid': False, 'reason': 'Not found'})
        if voucher.status != 'active':
            return Response({'valid': False, 'reason': f'Status: {voucher.status}'})
        if voucher.expires_at and voucher.expires_at < timezone.now():
            return Response({'valid': False, 'reason': 'Expired'})
        return Response({'valid': True, 'voucher': VoucherSerializer(voucher).data})
