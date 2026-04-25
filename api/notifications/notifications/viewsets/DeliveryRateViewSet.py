# earning_backend/api/notifications/viewsets/DeliveryRateViewSet.py
"""
DeliveryRateViewSet — read-only delivery/open/click rate metrics per channel per day.

Endpoints:
  GET  /delivery-rates/           — list all delivery rate records (admin)
  GET  /delivery-rates/{id}/      — retrieve single record
  GET  /delivery-rates/summary/   — aggregate summary across channels/dates
  POST /delivery-rates/refresh/   — trigger recalculation from insights (admin)
"""

import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from api.notifications.models.analytics import DeliveryRate, NotificationInsight

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline serializers
# ---------------------------------------------------------------------------

class DeliveryRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRate
        fields = [
            'id', 'date', 'channel', 'delivery_pct', 'open_pct',
            'click_pct', 'sample_size', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class DeliveryRateViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only endpoint for pre-computed delivery/open/click rates.
    Restricted to admin users.
    """

    serializer_class = DeliveryRateSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        qs = DeliveryRate.objects.all().order_by('-date', 'channel')

        # Optional filters
        channel = self.request.query_params.get('channel')
        if channel:
            qs = qs.filter(channel=channel)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)

        days = self.request.query_params.get('days')
        if days:
            try:
                cutoff = timezone.now().date() - timedelta(days=int(days))
                qs = qs.filter(date__gte=cutoff)
            except (ValueError, TypeError):
                pass

        return qs

    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """
        Return average delivery / open / click rates across all channels
        for the requested date range (default: last 30 days).
        """
        days = int(request.query_params.get('days', 30))
        cutoff = timezone.now().date() - timedelta(days=days)
        channel = request.query_params.get('channel')

        qs = DeliveryRate.objects.filter(date__gte=cutoff)
        if channel:
            qs = qs.filter(channel=channel)

        from django.db.models import Avg, Count
        agg = qs.aggregate(
            avg_delivery=Avg('delivery_pct'),
            avg_open=Avg('open_pct'),
            avg_click=Avg('click_pct'),
            records=Count('id'),
        )

        return Response({
            'period_days': days,
            'channel': channel or 'all',
            'avg_delivery_pct': round(agg['avg_delivery'] or 0, 2),
            'avg_open_pct': round(agg['avg_open'] or 0, 2),
            'avg_click_pct': round(agg['avg_click'] or 0, 2),
            'data_points': agg['records'] or 0,
        })

    @action(detail=False, methods=['post'], url_path='refresh')
    def refresh(self, request):
        """
        Re-compute DeliveryRate records from the latest NotificationInsight rows.
        Admin only.
        """
        if not request.user.is_staff:
            return Response({'error': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        days = int(request.data.get('days', 7))
        cutoff = timezone.now().date() - timedelta(days=days)
        insights = NotificationInsight.objects.filter(date__gte=cutoff)
        updated = 0

        for insight in insights:
            try:
                DeliveryRate.upsert_from_insight(insight)
                updated += 1
            except Exception as exc:
                logger.warning(f'DeliveryRateViewSet.refresh: {exc}')

        return Response({'refreshed_count': updated, 'period_days': days})
