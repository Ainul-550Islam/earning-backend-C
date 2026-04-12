from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import TargetingRule
from ..serializers.TargetingRuleSerializer import TargetingRuleSerializer
from ..permissions import IsPublisher


class TargetingRuleViewSet(viewsets.ModelViewSet):
    """Manage targeting rules for a SmartLink."""
    serializer_class = TargetingRuleSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return TargetingRule.objects.filter(smartlink_id=sl_pk)

    def perform_create(self, serializer):
        sl_pk = self.kwargs.get('smartlink_pk')
        serializer.save(smartlink_id=sl_pk)

    @action(detail=True, methods=['post'], url_path='test')
    def test(self, request, smartlink_pk=None, pk=None):
        """
        POST /api/smartlink/smartlinks/{id}/targeting/{rule_id}/test/
        Test a targeting rule against a simulated request context.
        Body: {"country": "BD", "device_type": "mobile", "os": "android", ...}
        """
        from ..services.targeting.TargetingEngine import TargetingEngine
        from ..models import SmartLink
        rule = self.get_object()
        context = request.data
        engine = TargetingEngine()
        try:
            sl = SmartLink.objects.get(pk=smartlink_pk)
            eligible = engine.evaluate(sl, context)
            return Response({
                'matched': len(eligible) > 0,
                'eligible_offers': len(eligible),
                'context': context,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
