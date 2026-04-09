# api/djoyalty/viewsets/earn/EarnRuleViewSet.py
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models.earn_rules import EarnRule
from ...serializers.EarnRuleSerializer import EarnRuleSerializer
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyTenantMixin
from ...permissions import IsLoyaltyAdmin
from ...throttles import DjoyaltyUserThrottle


class EarnRuleViewSet(DjoyaltyTenantMixin, viewsets.ModelViewSet):
    """Earn Rule CRUD — Tenant isolated, N+1 safe।"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [DjoyaltyUserThrottle]
    queryset = EarnRule.objects.all().order_by('-priority').prefetch_related(
        'conditions', 'tier_multipliers__tier'
    )
    serializer_class = EarnRuleSerializer
    pagination_class = DjoyaltyPagePagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'trigger', 'rule_type']
    ordering_fields = ['priority', 'created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        trigger = self.request.query_params.get('trigger')
        rule_type = self.request.query_params.get('rule_type')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        if trigger:
            qs = qs.filter(trigger=trigger)
        if rule_type:
            qs = qs.filter(rule_type=rule_type)
        return qs

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Currently active earn rules।"""
        qs = EarnRule.active.all()
        if hasattr(self, 'get_tenant'):
            tenant = self.get_tenant()
            if tenant:
                qs = qs.filter(tenant=tenant)
        return Response(self.get_serializer(qs, many=True).data)
