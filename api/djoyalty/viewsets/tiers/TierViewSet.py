# api/djoyalty/viewsets/tiers/TierViewSet.py
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models.tiers import LoyaltyTier
from ...serializers.TierSerializer import LoyaltyTierSerializer
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyTenantMixin
from ...mixins import DjoyaltyBaseViewSet
from ...permissions import IsLoyaltyAdmin


class TierViewSet(DjoyaltyBaseViewSet, DjoyaltyTenantMixin, viewsets.ModelViewSet):
    """Loyalty Tier CRUD -- Tenant isolated, N+1 safe।"""
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
    @action(detail=True, methods=['get', 'put'], url_path='config', permission_classes=[IsLoyaltyAdmin])
    def tier_config(self, request, pk=None):
        """
        FIXED: TierConfig had NO API endpoint -- tier configuration only editable in admin.
        GET/PUT tier configuration (evaluation period, auto-downgrade, grace days).
        """
        from ...models.tiers import TierConfig, LoyaltyTier
        from django.shortcuts import get_object_or_404
        tier = get_object_or_404(LoyaltyTier, pk=pk)
        config, _ = TierConfig.objects.get_or_create(tier=tier)
        if request.method == 'PUT':
            for field in ('evaluation_period_days', 'auto_downgrade', 'grace_days', 'require_spend'):
                if field in request.data:
                    setattr(config, field, request.data[field])
            config.save()
        return Response({
            'tier_id': tier.pk, 'tier_name': tier.name,
            'evaluation_period_days': config.evaluation_period_days,
            'auto_downgrade': config.auto_downgrade,
            'grace_days': config.grace_days,
            'require_spend': config.require_spend,
        })
