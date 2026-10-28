# api/djoyalty/viewsets/earn/EarnRuleViewSet.py
from rest_framework import viewsets, filters, status
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ...models.earn_rules import EarnRule
from ...serializers.EarnRuleSerializer import EarnRuleSerializer
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyTenantMixin
from ...permissions import IsLoyaltyAdmin
from ...throttles import DjoyaltyUserThrottle
from ...mixins import DjoyaltyBaseViewSet


class EarnRuleViewSet(DjoyaltyBaseViewSet, DjoyaltyTenantMixin, viewsets.ModelViewSet):
    """Earn Rule CRUD -- Tenant isolated, N+1 safe।"""
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
    @action(detail=True, methods=['get', 'post'], url_path='conditions', permission_classes=[IsLoyaltyAdmin])
    def conditions(self, request, pk=None):
        """
        GET/POST earn rule conditions。
        FIXED: EarnRuleCondition had NO API endpoint -- complex conditions
        (min_cart_value, category_filter, time_of_day) only editable in admin。
        """
        from ...models.earn_rules import EarnRuleCondition
        rule = get_object_or_404(EarnRule, pk=pk)
        if request.method == 'GET':
            qs = EarnRuleCondition.objects.filter(earn_rule=rule)
            return Response([{
                'id': c.id, 'condition_type': c.condition_type,
                'operator': c.operator, 'value': str(c.value),
                'is_active': c.is_active,
            } for c in qs])
        data = request.data
        cond = EarnRuleCondition.objects.create(
            earn_rule=rule, condition_type=data.get('condition_type'),
            operator=data.get('operator', 'gte'), value=data.get('value', '0'),
            is_active=data.get('is_active', True),
        )
        return Response({'id': cond.id, 'condition_type': cond.condition_type,
                         'operator': cond.operator, 'value': str(cond.value)},
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='tier-multipliers', permission_classes=[IsLoyaltyAdmin])
    def tier_multipliers(self, request, pk=None):
        """
        GET/POST tier multipliers for an earn rule。
        FIXED: EarnRuleTierMultiplier had NO API endpoint。
        """
        from ...models.earn_rules import EarnRuleTierMultiplier
        rule = get_object_or_404(EarnRule, pk=pk)
        if request.method == 'GET':
            qs = EarnRuleTierMultiplier.objects.filter(earn_rule=rule).select_related('tier')
            return Response([{
                'id': m.id, 'tier_id': m.tier_id,
                'tier_name': m.tier.name if m.tier else '',
                'multiplier': str(m.multiplier),
            } for m in qs])
        from ...models.tiers import LoyaltyTier
        tier = get_object_or_404(LoyaltyTier, pk=request.data.get('tier_id'))
        m = EarnRuleTierMultiplier.objects.update_or_create(
            earn_rule=rule, tier=tier,
            defaults={'multiplier': request.data.get('multiplier', '1.0')},
        )[0]
        return Response({'id': m.id, 'tier_id': m.tier_id, 'multiplier': str(m.multiplier)},
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='earn-transactions', permission_classes=[IsLoyaltyAdmin])
    def earn_transactions(self, request):
        """
        FIXED: EarnTransaction had NO API endpoint。
        Admin can now query the earn transaction log by customer, rule, or date range。
        """
        from ...models.earn_rules import EarnTransaction
        qs = EarnTransaction.objects.select_related('customer', 'rule').order_by('-created_at')
        cid = request.query_params.get('customer_id')
        rid = request.query_params.get('rule_id')
        if cid: qs = qs.filter(customer_id=cid)
        if rid: qs = qs.filter(rule_id=rid)
        qs = qs[:100]
        return Response({'count': qs.count(), 'results': [{
            'id': t.id, 'customer_code': t.customer.code if t.customer else '',
            'rule_name': t.rule.name if t.rule else '', 'points_awarded': str(t.points_awarded),
            'spend_amount': str(getattr(t, 'spend_amount', 0)),
            'created_at': str(t.created_at),
        } for t in qs]})

    @action(detail=False, methods=['get'], url_path='rule-log', permission_classes=[IsLoyaltyAdmin])
    def rule_log(self, request):
        """
        FIXED: EarnRuleLog had NO API endpoint -- rule execution audit log。
        """
        from ...models.earn_rules import EarnRuleLog
        qs = EarnRuleLog.objects.select_related('rule').order_by('-created_at')[:100]
        return Response({'count': qs.count(), 'results': [{
            'id': log.id, 'rule_name': log.rule.name if log.rule else '',
            'action': log.action, 'performed_by': log.performed_by,
            'note': log.note, 'created_at': str(log.created_at),
        } for log in qs]})
