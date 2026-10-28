# api/admin_panel/viewsets/AdminActivityViewSet.py
"""AdminActivityViewSet — activity log, filter, export."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from ..models.activity import AdminActivity
from ..pagination import LargeDatasetPagination
from ..filters import AdminActivityFilter


class AdminActivityViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for AdminActivity log.
    Supports filtering by actor, action, model, status, date range.
    """
    permission_classes = [IsAdminUser]
    pagination_class = LargeDatasetPagination
    filterset_class = AdminActivityFilter

    def get_serializer_class(self):
        from ..serializers.AdminActivitySerializer import AdminActivitySerializer
        return AdminActivitySerializer

    def get_queryset(self):
        return AdminActivity.objects.select_related('actor').order_by('-created_at')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Summary of activity counts grouped by action type."""
        from django.db.models import Count
        from django.utils import timezone
        from datetime import timedelta

        days = int(request.query_params.get('days', 7))
        cutoff = timezone.now() - timedelta(days=days)

        by_action = AdminActivity.objects.filter(
            created_at__gte=cutoff
        ).values('action').annotate(count=Count('id')).order_by('-count')

        by_status = AdminActivity.objects.filter(
            created_at__gte=cutoff
        ).values('status').annotate(count=Count('id'))

        by_actor = AdminActivity.objects.filter(
            created_at__gte=cutoff
        ).values(
            'actor__username'
        ).annotate(count=Count('id')).order_by('-count')[:10]

        return Response({
            'period_days': days,
            'by_action': list(by_action),
            'by_status': list(by_status),
            'top_actors': list(by_actor),
            'total': AdminActivity.objects.filter(created_at__gte=cutoff).count(),
        })

    @action(detail=False, methods=['get'])
    def export_csv(self, request):
        """Export activity log as CSV (inline download)."""
        import csv
        from django.http import StreamingHttpResponse

        queryset = self.filter_queryset(self.get_queryset())[:10_000]

        def generate():
            yield 'id,actor,action,model_name,object_id,status,ip,created_at\n'
            for activity in queryset:
                actor = activity.actor.username if activity.actor else ''
                yield (
                    f'{activity.pk},{actor},{activity.action},{activity.model_name},'
                    f'{activity.object_id},{activity.status},{activity.ip},'
                    f'{activity.created_at.isoformat()}\n'
                )

        response = StreamingHttpResponse(generate(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="admin_activity.csv"'
        return response

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get the 50 most recent activities (no pagination)."""
        activities = AdminActivity.objects.select_related('actor').order_by('-created_at')[:50]
        serializer = self.get_serializer(activities, many=True)
        return Response({'success': True, 'data': serializer.data})