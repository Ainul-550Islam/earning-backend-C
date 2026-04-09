# api/djoyalty/viewsets/tiers/TierViewSet.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models.tiers import LoyaltyTier
from ...serializers.TierSerializer import LoyaltyTierSerializer
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyTenantMixin


class TierViewSet(DjoyaltyTenantMixin, viewsets.ModelViewSet):
    """Loyalty Tier CRUD — Tenant isolated, N+1 safe।"""
    permission_classes = [IsAuthenticated]
    queryset = LoyaltyTier.objects.all().order_by('rank').prefetch_related('benefits')
    serializer_class = LoyaltyTierSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'label']
    ordering_fields = ['rank', 'min_points']

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Only active tiers।"""
        qs = self.get_queryset().filter(is_active=True)
        return Response(self.get_serializer(qs, many=True).data)
