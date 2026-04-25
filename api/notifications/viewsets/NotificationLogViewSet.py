# earning_backend/api/notifications/viewsets/NotificationLogViewSet.py
"""
NotificationLogViewSet — split from views.py (lines 2516-2541).
Read-only admin viewset for notification delivery logs.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from notifications.models import NotificationLog
from notifications.serializers import NotificationLogSerializer


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for NotificationLog model — admin only.

    Endpoints:
      GET /notification-logs/                — list all logs (admin)
      GET /notification-logs/{id}/           — retrieve single log
      GET /notification-logs/summary/        — summary stats
      GET /notification-logs/errors/         — error logs only
    """

    queryset = NotificationLog.objects.all().order_by('-created_at')
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['message', 'source', 'notification__title']
    ordering_fields = ['created_at', 'log_level']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        log_type = params.get('log_type')
        if log_type:
            qs = qs.filter(log_type=log_type)
        log_level = params.get('log_level')
        if log_level:
            qs = qs.filter(log_level=log_level)
        notification_id = params.get('notification_id')
        if notification_id:
            qs = qs.filter(notification_id=notification_id)
        user_id = params.get('user_id')
        if user_id:
            qs = qs.filter(notification__user_id=user_id)
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Summary stats for notification logs."""
        from django.db.models import Count
        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'by_level': list(qs.values('log_level').annotate(count=Count('id'))),
            'by_type': list(qs.values('log_type').annotate(count=Count('id'))),
        })

    @action(detail=False, methods=['get'])
    def errors(self, request):
        """Only error-level logs."""
        qs = self.get_queryset().filter(log_level__in=['error', 'critical'])
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)
