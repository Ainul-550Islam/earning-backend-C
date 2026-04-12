from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from ..models import ClickHeatmap, SmartLink
from ..serializers.HeatmapSerializer import HeatmapSerializer
from ..services.analytics.HeatmapService import HeatmapService
from ..permissions import IsPublisher


class HeatmapViewSet(viewsets.ReadOnlyModelViewSet):
    """Geo heatmap data for a SmartLink."""
    serializer_class = HeatmapSerializer
    permission_classes = [IsAuthenticated, IsPublisher]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.heatmap_service = HeatmapService()

    def get_queryset(self):
        return ClickHeatmap.objects.filter(
            smartlink_id=self.kwargs.get('smartlink_pk')
        ).order_by('-date')

    @action(detail=False, methods=['get'], url_path='aggregate')
    def aggregate(self, request, smartlink_pk=None):
        """GET aggregated heatmap for map rendering."""
        days = int(request.query_params.get('days', 30))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        data = self.heatmap_service.get_heatmap(sl, days=days)
        return Response(data)

    @action(detail=False, methods=['get'], url_path='top-countries')
    def top_countries(self, request, smartlink_pk=None):
        """GET top countries by click volume."""
        limit = int(request.query_params.get('limit', 10))
        sl = SmartLink.objects.get(pk=smartlink_pk)
        data = self.heatmap_service.get_top_countries(sl, limit=limit)
        return Response(data)
