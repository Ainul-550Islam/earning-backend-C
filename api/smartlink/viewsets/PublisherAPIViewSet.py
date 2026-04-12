from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import SmartLink
from ..serializers.PublisherAPISerializer import PublisherAPISerializer
from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
from ..permissions import IsPublisher


class PublisherAPIViewSet(viewsets.GenericViewSet):
    """
    Publisher-facing API for external integrations.
    Simplified endpoints for publisher dashboards and 3rd-party tools.
    """
    serializer_class = PublisherAPISerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.analytics = SmartLinkAnalyticsService()

    def get_queryset(self):
        return SmartLink.objects.filter(
            publisher=self.request.user, is_active=True, is_archived=False
        )

    @action(detail=False, methods=['get'], url_path='my-smartlinks')
    def my_smartlinks(self, request):
        """GET all active SmartLinks for authenticated publisher."""
        qs = self.get_queryset().values(
            'id', 'slug', 'name', 'type', 'total_clicks',
            'total_conversions', 'total_revenue', 'created_at'
        )
        return Response(list(qs))

    @action(detail=False, methods=['get'], url_path='my-stats')
    def my_stats(self, request):
        """GET aggregate stats for all publisher SmartLinks."""
        days = int(request.query_params.get('days', 30))
        totals = self.analytics.get_publisher_totals(request.user, days=days)
        return Response(totals)

    @action(detail=False, methods=['get'], url_path='link-url')
    def link_url(self, request):
        """GET the full redirect URL for a SmartLink slug."""
        slug = request.query_params.get('slug', '')
        if not slug:
            return Response({'error': 'slug required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sl = SmartLink.objects.get(slug=slug, publisher=request.user)
            return Response({'slug': slug, 'url': sl.full_url})
        except SmartLink.DoesNotExist:
            return Response({'error': 'not found'}, status=status.HTTP_404_NOT_FOUND)
