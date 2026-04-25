# earning_backend/api/notifications/viewsets/NotificationInsightViewSet.py
"""
NotificationInsightViewSet — read-only access to daily per-channel metrics.

Endpoints:
  GET /insights/              — list daily insights (filterable by date, channel)
  GET /insights/{id}/         — retrieve single insight
  GET /insights/summary/      — aggregate summary across date range
  POST /insights/generate/    — trigger daily insight generation (admin)
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Avg


class NotificationInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for NotificationInsight — daily per-channel analytics."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    class _Pagination(PageNumberPagination):
        page_size = 30
        page_size_query_param = 'page_size'
        max_page_size = 365

    pagination_class = _Pagination

    def get_queryset(self):
        from notifications.models.analytics import NotificationInsight
        qs = NotificationInsight.objects.all()

        channel = self.request.query_params.get('channel')
        if channel:
            qs = qs.filter(channel=channel)

        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        if from_date:
            qs = qs.filter(date__gte=from_date)
        if to_date:
            qs = qs.filter(date__lte=to_date)

        return qs.order_by('-date', 'channel')

    def get_serializer_class(self):
        from rest_framework import serializers
        from notifications.models.analytics import NotificationInsight

        class InsightSerializer(serializers.ModelSerializer):
            delivery_rate = serializers.FloatField(read_only=True)
            open_rate = serializers.FloatField(read_only=True)
            click_rate = serializers.FloatField(read_only=True)

            class Meta:
                model = NotificationInsight
                fields = [
                    'id', 'date', 'channel', 'sent', 'delivered', 'failed',
                    'opened', 'clicked', 'unsubscribed', 'unique_users_reached',
                    'delivery_rate', 'open_rate', 'click_rate',
                    'total_cost', 'cost_currency', 'breakdown', 'created_at',
                ]

        return InsightSerializer

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Aggregate summary across a date range, optionally per channel."""
        qs = self.get_queryset()
        agg = qs.aggregate(
            total_sent=Sum('sent'),
            total_delivered=Sum('delivered'),
            total_failed=Sum('failed'),
            total_opened=Sum('opened'),
            total_clicked=Sum('clicked'),
            total_unsubscribed=Sum('unsubscribed'),
        )
        sent = agg['total_sent'] or 0
        delivered = agg['total_delivered'] or 0
        agg['delivery_rate'] = round(delivered / sent * 100, 2) if sent else 0
        agg['open_rate'] = round((agg['total_opened'] or 0) / delivered * 100, 2) if delivered else 0
        agg['click_rate'] = round((agg['total_clicked'] or 0) / delivered * 100, 2) if delivered else 0
        return Response(agg)

    @action(detail=False, methods=['post'], permission_classes=[IsAdminUser])
    def generate(self, request):
        """Trigger daily insight generation for a specific date."""
        from notifications.tasks import generate_daily_analytics
        date_str = request.data.get('date')
        generate_daily_analytics.delay(date_str)
        return Response({'success': True, 'message': 'Analytics generation task queued.'})
