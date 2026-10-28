# api/djoyalty/viewset_cap.py
"""
Djoyalty ViewSet Capabilities -- Advanced viewset capability mixins।
Provides: export, bulk operations, analytics endpoints।
"""
import csv
import io
import logging
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse

logger = logging.getLogger(__name__)


class ExportCapabilityMixin:
    """
    Adds CSV/JSON export to any ViewSet।
    GET /api/loyalty/{resource}/export/?format=csv
    """

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export resource data as CSV or JSON।"""
        fmt = request.query_params.get('format', 'csv')
        queryset = self.get_queryset()

        if fmt == 'csv':
            return self._export_csv(queryset)
        return Response({'data': list(queryset.values())[:1000]})

    def _export_csv(self, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="djoyalty_export.csv"'

        if not queryset.exists():
            return response

        fields = [f.name for f in queryset.model._meta.fields]
        writer = csv.writer(response)
        writer.writerow(fields)

        for obj in queryset.iterator(chunk_size=500):
            writer.writerow([getattr(obj, f) for f in fields])

        return response


class BulkOperationsMixin:
    """
    Adds bulk create/update/delete to ViewSets।
    POST /api/loyalty/{resource}/bulk_create/
    """

    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Bulk create resources।"""
        items = request.data.get('items', [])
        if not items or not isinstance(items, list):
            return Response({'error': 'items list required'}, status=400)

        serializer = self.get_serializer(data=items, many=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'created': len(serializer.data)}, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete by IDs।"""
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'ids list required'}, status=400)

        deleted = self.get_queryset().filter(id__in=ids).delete()
        return Response({'deleted': deleted[0]})


class AnalyticsCapabilityMixin:
    """Adds basic analytics endpoints to ViewSets।"""

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get basic stats for this resource।"""
        from django.db.models import Count, Sum, Avg
        from django.utils import timezone
        from datetime import timedelta

        qs = self.get_queryset()
        now = timezone.now()

        return Response({
            'total': qs.count(),
            'last_7_days': qs.filter(
                created_at__gte=now - timedelta(days=7)
            ).count() if hasattr(qs.model, 'created_at') else 'N/A',
            'last_30_days': qs.filter(
                created_at__gte=now - timedelta(days=30)
            ).count() if hasattr(qs.model, 'created_at') else 'N/A',
        })
