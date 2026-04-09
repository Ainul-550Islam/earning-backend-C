# api/djoyalty/viewsets/core/TxnViewSet.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from ...models.core import Txn
from ...serializers.TxnSerializer import TxnSerializer
from ...pagination import DjoyaltyPagePagination
from ...permissions import IsAuthenticatedAndActive
from ...throttles import DjoyaltyUserThrottle
from ...mixins import DjoyaltyTenantMixin, DjoyaltyAuditMixin


class TxnViewSet(DjoyaltyTenantMixin, DjoyaltyAuditMixin, viewsets.ModelViewSet):
    """
    Transaction CRUD — Tenant isolated, throttled।
    Custom managers ব্যবহার করে filtering।
    """
    permission_classes = [IsAuthenticatedAndActive]
    throttle_classes = [DjoyaltyUserThrottle]
    queryset = Txn.objects.all().order_by('-timestamp')
    serializer_class = TxnSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['customer__code', 'customer__email', 'reference']
    ordering_fields = ['timestamp', 'value']

    def get_queryset(self):
        # DjoyaltyTenantMixin handles tenant filter automatically
        qs = super().get_queryset()
        txn_type = self.request.query_params.get('type')
        customer_id = self.request.query_params.get('customer')
        is_discount = self.request.query_params.get('is_discount')

        if txn_type == 'full':
            qs = qs.filter(is_discount=False)
        elif txn_type == 'discount':
            qs = qs.filter(is_discount=True)
        elif txn_type == 'spending':
            qs = qs.filter(value__lt=0)

        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if is_discount is not None:
            qs = qs.filter(is_discount=is_discount.lower() == 'true')

        return qs.select_related('customer')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Transaction summary statistics — tenant scoped।"""
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'total_value': float(qs.filter(value__gt=0).aggregate(s=Sum('value'))['s'] or 0),
            'full_price': qs.filter(is_discount=False).count(),
            'discounted': qs.filter(is_discount=True).count(),
            'spending': qs.filter(value__lt=0).count(),
        })
