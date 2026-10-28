import logging

logger = logging.getLogger(__name__)

# api/djoyalty/viewsets/points/LedgerViewSet.py
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from ...models.points import PointsLedger
from ...serializers.LedgerSerializer import LedgerSerializer
from ...pagination import LedgerCursorPagination
from ...mixins import DjoyaltyBaseViewSet

class LedgerViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = PointsLedger.objects.all().select_related('customer').order_by('-created_at')
    serializer_class = LedgerSerializer
    pagination_class = LedgerCursorPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['created_at', 'points']

    def get_queryset(self):
        try:
            qs = super().get_queryset()
            customer_id = self.request.query_params.get('customer')
            txn_type = self.request.query_params.get('txn_type')
            source = self.request.query_params.get('source')
            if customer_id:
                qs = qs.filter(customer_id=customer_id)
            if txn_type:
                qs = qs.filter(txn_type=txn_type)
            if source:
                qs = qs.filter(source=source)
            return qs
        except Exception as e:
            logger.error('LedgerViewSet.get_queryset error: %s', e)
            from ...models.points import PointsLedger
            return PointsLedger.objects.none()
