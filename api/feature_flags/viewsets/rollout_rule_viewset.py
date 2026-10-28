"""
Rollout Rule viewset for Feature Flags & A/B Testing.

FIX: added authentication/permissions + pagination/filtering (was missing).
NEW: `test` and `evaluate_with_stats` actions expose
`RolloutService.evaluate_rules` style logic that previously had no API
endpoint (floating-code fix).
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from ..models.rollout_rule import RolloutRule
from ..serializers.rollout_rule_serializer import RolloutRuleSerializer, RolloutRuleListSerializer
from ..permissions import IsAuthenticated, CanViewFlags, CanEditFlags


class RolloutRuleViewSet(viewsets.ModelViewSet):
    """
    Viewset for RolloutRule model.
    """

    queryset = RolloutRule.objects.all()
    serializer_class = RolloutRuleSerializer
    permission_classes = [IsAuthenticated, CanViewFlags, CanEditFlags]

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['flag', 'is_active', 'rule_type']
    ordering_fields = ['priority', 'created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return RolloutRuleListSerializer
        return RolloutRuleSerializer

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a rule."""
        rule = self.get_object()
        rule.is_active = True
        rule.save()

        return Response({'success': True, 'message': f'Rule {rule.field} activated successfully'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a rule."""
        rule = self.get_object()
        rule.is_active = False
        rule.save()

        return Response({'success': True, 'message': f'Rule {rule.field} deactivated successfully'})

    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active rules."""
        flag_id = request.query_params.get('flag_id')

        if flag_id:
            rules = self.get_queryset().filter(flag_id=flag_id, is_active=True)
        else:
            rules = self.get_queryset().filter(is_active=True)

        page = self.paginate_queryset(rules)
        serializer = self.get_serializer(page if page is not None else rules, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """NEW: test a single rule against an ad-hoc context (floating-code fix)."""
        rule = self.get_object()
        context = request.data.get('context', {})
        result = rule.evaluate(context)

        return Response({
            'rule_id': rule.id,
            'context': context,
            'matches': result,
        })

    @action(detail=True, methods=['post'])
    def evaluate_with_stats(self, request, pk=None):
        """NEW: evaluate a rule against many contexts and return a match-rate
        summary (floating-code fix)."""
        rule = self.get_object()
        contexts = request.data.get('contexts', [])

        if not contexts:
            return Response({'error': 'contexts (list) is required'}, status=400)

        results = [rule.evaluate(ctx) for ctx in contexts]
        match_count = sum(1 for r in results if r)

        return Response({
            'rule_id': rule.id,
            'total_tested': len(contexts),
            'match_count': match_count,
            'match_percentage': round(match_count / len(contexts) * 100, 2),
            'results': results,
        })
