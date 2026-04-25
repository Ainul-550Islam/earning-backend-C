# earning_backend/api/notifications/viewsets/NotificationScheduleViewSet.py
"""
NotificationScheduleViewSet — manage scheduled notification sends.

Endpoints:
  GET    /schedules/              — list schedules
  POST   /schedules/              — create schedule
  GET    /schedules/{id}/         — retrieve
  DELETE /schedules/{id}/         — cancel / delete schedule
  POST   /schedules/{id}/cancel/  — cancel without deleting
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone


class NotificationScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for NotificationSchedule model."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 100

    pagination_class = _Pagination

    def get_queryset(self):
        from notifications.models.schedule import NotificationSchedule
        qs = NotificationSchedule.objects.all().select_related(
            'notification', 'notification__user', 'created_by'
        )
        schedule_status = self.request.query_params.get('status')
        if schedule_status:
            qs = qs.filter(status=schedule_status)
        # Date range
        from_dt = self.request.query_params.get('from')
        to_dt = self.request.query_params.get('to')
        if from_dt:
            try:
                from datetime import datetime
                qs = qs.filter(send_at__gte=datetime.fromisoformat(from_dt))
            except ValueError:
                pass
        if to_dt:
            try:
                from datetime import datetime
                qs = qs.filter(send_at__lte=datetime.fromisoformat(to_dt))
            except ValueError:
                pass
        return qs.order_by('send_at')

    def get_serializer_class(self):
        from rest_framework import serializers
        from notifications.models.schedule import NotificationSchedule

        class ScheduleSerializer(serializers.ModelSerializer):
            is_due = serializers.SerializerMethodField()
            is_overdue = serializers.SerializerMethodField()

            class Meta:
                model = NotificationSchedule
                fields = [
                    'id', 'notification', 'send_at', 'timezone', 'status',
                    'sent_at', 'failure_reason', 'created_by', 'is_due',
                    'is_overdue', 'created_at', 'updated_at',
                ]
                read_only_fields = [
                    'id', 'status', 'sent_at', 'failure_reason',
                    'created_by', 'created_at', 'updated_at',
                ]

            def get_is_due(self, obj):
                return obj.is_due()

            def get_is_overdue(self, obj):
                return obj.is_overdue()

        return ScheduleSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a pending schedule."""
        schedule = self.get_object()
        success = schedule.cancel()
        if success:
            return Response({'success': True, 'id': schedule.pk, 'status': schedule.status})
        return Response(
            {'success': False, 'error': f'Cannot cancel schedule in status: {schedule.status}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=False, methods=['get'])
    def due_now(self, request):
        """List schedules that are due to be sent now."""
        from notifications.models.schedule import NotificationSchedule
        now = timezone.now()
        qs = NotificationSchedule.objects.filter(
            status='pending', send_at__lte=now
        ).order_by('send_at')
        serializer = self.get_serializer(qs, many=True)
        return Response({'count': qs.count(), 'results': serializer.data})
