# earning_backend/api/notifications/viewsets/CampaignABTestViewSet.py
"""
CampaignABTestViewSet — manage A/B tests on campaigns.

Endpoints:
  GET    /ab-tests/             — list A/B tests
  POST   /ab-tests/             — create A/B test for a campaign
  GET    /ab-tests/{id}/        — retrieve
  PUT    /ab-tests/{id}/        — update (only while active)
  POST   /ab-tests/{id}/evaluate/   — manually trigger winner evaluation
  GET    /ab-tests/{id}/status/     — get test status with live stats
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class CampaignABTestViewSet(viewsets.ModelViewSet):
    """ViewSet for CampaignABTest model."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 100

    pagination_class = _Pagination

    def get_queryset(self):
        from api.notifications.models.campaign import CampaignABTest
        qs = CampaignABTest.objects.all().select_related(
            'campaign', 'variant_a', 'variant_b'
        )
        campaign_id = self.request.query_params.get('campaign_id')
        if campaign_id:
            qs = qs.filter(campaign_id=campaign_id)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == 'true')
        return qs.order_by('-created_at')

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.notifications.models.campaign import CampaignABTest

        class ABTestSerializer(serializers.ModelSerializer):
            class Meta:
                model = CampaignABTest
                fields = [
                    'id', 'campaign', 'variant_a', 'variant_b', 'split_pct',
                    'winning_metric', 'winner', 'variant_a_stats', 'variant_b_stats',
                    'winner_declared_at', 'is_active', 'created_at', 'updated_at',
                ]
                read_only_fields = [
                    'id', 'winner', 'variant_a_stats', 'variant_b_stats',
                    'winner_declared_at', 'created_at', 'updated_at',
                ]

        return ABTestSerializer

    @action(detail=True, methods=['post'])
    def evaluate(self, request, pk=None):
        """Manually trigger winner evaluation for this A/B test."""
        from api.notifications.services.ABTestService import ab_test_service
        ab_test = self.get_object()
        result = ab_test_service.evaluate_winner(ab_test.pk)
        return Response(result)

    @action(detail=True, methods=['get'])
    def test_status(self, request, pk=None):
        """Get full A/B test status including live stats."""
        from api.notifications.services.ABTestService import ab_test_service
        ab_test = self.get_object()
        result = ab_test_service.get_ab_test_status(ab_test.pk)
        return Response(result)
