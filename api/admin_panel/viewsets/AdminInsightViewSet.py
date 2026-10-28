# api/admin_panel/viewsets/AdminInsightViewSet.py
"""AdminInsightViewSet — AI insights: list, mark read, dismiss."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.utils import timezone

from ..models.reports import AdminInsight
from ..pagination import AdminPagination
from ..filters import AdminInsightFilter, get_filter_for_model


class AdminInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """Read admin insights. Support mark-read, dismiss, trigger regeneration."""
    permission_classes = [IsAdminUser]
    pagination_class = AdminPagination
    filterset_class = get_filter_for_model(AdminInsight, AdminInsightFilter)

    def get_serializer_class(self):
        from ..serializers.AdminInsightSerializer import AdminInsightSerializer
        return AdminInsightSerializer

    def get_queryset(self):
        return AdminInsight.objects.filter(
            is_dismissed=False,
        ).filter(
            __import__('django.db.models', fromlist=['Q']).Q(expires_at__isnull=True) |
            __import__('django.db.models', fromlist=['Q']).Q(expires_at__gte=timezone.now())
        ).order_by('-created_at')

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        insight = self.get_object()
        insight.mark_read()
        return Response({'success': True, 'is_read': True})

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        insight = self.get_object()
        insight.dismiss()
        return Response({'success': True, 'is_dismissed': True})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        count = AdminInsight.objects.filter(is_read=False, is_dismissed=False).update(is_read=True)
        return Response({'success': True, 'marked_read': count})

    @action(detail=False, methods=['post'])
    def generate_now(self, request):
        """Manually trigger insight generation."""
        try:
            from ..tasks import generate_daily_insights
            generate_daily_insights.delay()
            return Response({'success': True, 'message': 'Insight generation queued.'})
        except Exception:
            from ..tasks.insight_tasks import generate_insights
            result = generate_insights()
            return Response({'success': True, 'data': result})

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        count = AdminInsight.objects.filter(is_read=False, is_dismissed=False).count()
        return Response({'unread_count': count})

    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Get only critical-priority active insights."""
        insights = self.get_queryset().filter(priority='critical')
        serializer = self.get_serializer(insights, many=True)
        return Response({'success': True, 'data': serializer.data, 'count': insights.count()})