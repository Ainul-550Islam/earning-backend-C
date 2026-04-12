from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import ABTestResult, SmartLink
from ..serializers.ABTestSerializer import ABTestSerializer
from ..serializers.ABTestResultSerializer import ABTestResultSerializer
from ..services.rotation.ABTestService import ABTestService
from ..permissions import IsPublisher


class ABTestViewSet(viewsets.ModelViewSet):
    """Manage A/B tests for a SmartLink."""
    serializer_class = ABTestResultSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ab_service = ABTestService()

    def get_queryset(self):
        sl_pk = self.kwargs.get('smartlink_pk')
        return ABTestResult.objects.filter(smartlink_id=sl_pk).select_related(
            'winner_version', 'control_version'
        )

    @action(detail=False, methods=['post'], url_path='setup')
    def setup(self, request, smartlink_pk=None):
        """POST setup a new A/B test with variants."""
        sl = SmartLink.objects.get(pk=smartlink_pk)
        variants = request.data.get('variants', [])
        versions = self.ab_service.create_test(sl, variants)
        return Response({
            'status': 'created',
            'variant_count': len(versions),
            'variants': [{'id': v.pk, 'name': v.name, 'split': v.traffic_split} for v in versions],
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='evaluate')
    def evaluate(self, request, smartlink_pk=None, pk=None):
        """POST manually trigger statistical significance evaluation."""
        result = self.get_object()
        eval_result = self.ab_service.evaluate_significance(result)
        return Response(eval_result)

    @action(detail=True, methods=['post'], url_path='apply-winner')
    def apply_winner(self, request, smartlink_pk=None, pk=None):
        """POST apply the winner variant to the SmartLink."""
        result = self.get_object()
        self.ab_service.apply_winner(result)
        return Response({'status': 'winner_applied', 'winner_id': result.winner_version_id})
