"""
ScheduleViewSet
Exposes SmartLinkSchedule CRUD + scheduler status.
Service: SmartLinkSchedulerService
Model:   SmartLinkSchedule (models/extensions/smartlink_schedule.py)
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from api.smartlink.models import SmartLink
from api.smartlink.models.extensions.smartlink_schedule import SmartLinkSchedule
from api.smartlink.serializers.SmartLinkScheduleSerializer import (
    SmartLinkScheduleSerializer,
    SmartLinkScheduleListSerializer,
)
from api.smartlink.permissions import IsSmartLinkOwnerOrAdmin
from ..services.scheduler.SmartLinkSchedulerService import SmartLinkSchedulerService

import logging
logger = logging.getLogger('smartlink.viewsets.schedule')


class ScheduleViewSet(viewsets.ModelViewSet):
    """
    Manage SmartLink activation/deactivation schedules.

    list   GET    /api/smartlink/smartlinks/{sl_pk}/schedule/
    create POST   /api/smartlink/smartlinks/{sl_pk}/schedule/
    detail GET    /api/smartlink/smartlinks/{sl_pk}/schedule/{id}/
    update PATCH  /api/smartlink/smartlinks/{sl_pk}/schedule/{id}/
    delete DELETE /api/smartlink/smartlinks/{sl_pk}/schedule/{id}/

    Actions:
      POST /api/smartlink/smartlinks/{sl_pk}/schedule/{id}/enable/
      POST /api/smartlink/smartlinks/{sl_pk}/schedule/{id}/disable/
      GET  /api/smartlink/smartlinks/{sl_pk}/schedule/{id}/status/
    """
    permission_classes = [IsAuthenticated, IsSmartLinkOwnerOrAdmin]
    serializer_class = SmartLinkScheduleSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._scheduler_svc = SmartLinkSchedulerService()

    def _get_smartlink(self):
        smartlink_pk = self.kwargs.get('smartlink_pk')
        user = self.request.user
        qs = SmartLink.objects.all() if user.is_staff else SmartLink.objects.filter(publisher=user)
        from django.shortcuts import get_object_or_404
        return get_object_or_404(qs, pk=smartlink_pk)

    def get_queryset(self):
        sl = self._get_smartlink()
        return SmartLinkSchedule.objects.filter(smartlink=sl).select_related('smartlink')

    def get_serializer_class(self):
        if self.action == 'list':
            return SmartLinkScheduleListSerializer
        return SmartLinkScheduleSerializer

    def perform_create(self, serializer):
        sl = self._get_smartlink()
        serializer.save(smartlink=sl)
        logger.info(
            f"Schedule created for [{sl.slug}] by {self.request.user.username}"
        )

    def perform_update(self, serializer):
        serializer.save()
        sl = serializer.instance.smartlink
        logger.info(
            f"Schedule updated for [{sl.slug}] by {self.request.user.username}"
        )

    # ── Extra actions ──────────────────────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='enable')
    def enable(self, request, smartlink_pk=None, pk=None):
        """Enable a schedule without changing its config."""
        schedule = self.get_object()
        SmartLinkSchedule.objects.filter(pk=schedule.pk).update(is_enabled=True)
        schedule.refresh_from_db()
        return Response(SmartLinkScheduleSerializer(schedule).data)

    @action(detail=True, methods=['post'], url_path='disable')
    def disable(self, request, smartlink_pk=None, pk=None):
        """Disable a schedule without deleting it."""
        schedule = self.get_object()
        SmartLinkSchedule.objects.filter(pk=schedule.pk).update(is_enabled=False)
        schedule.refresh_from_db()
        return Response(SmartLinkScheduleSerializer(schedule).data)

    @action(detail=True, methods=['get'], url_path='status')
    def schedule_status(self, request, smartlink_pk=None, pk=None):
        """
        Real-time status of a single schedule.
        Returns whether it should currently be active and seconds to next event.
        """
        schedule = self.get_object()
        serializer = SmartLinkScheduleSerializer(schedule)
        return Response({
            'schedule': serializer.data,
            'smartlink_is_active': schedule.smartlink.is_active,
            'schedule_says_active': schedule.should_be_active(),
            'in_sync': schedule.smartlink.is_active == schedule.should_be_active(),
        })

    @action(detail=False, methods=['post'], url_path='run-now',
            permission_classes=[IsAuthenticated])
    def run_now(self, request, smartlink_pk=None):
        """
        Admin-only: immediately trigger the scheduler for this SmartLink.
        POST /api/smartlink/smartlinks/{sl_pk}/schedule/run-now/
        """
        if not request.user.is_staff:
            return Response(
                {'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN
            )
        result = self._scheduler_svc.process_all_schedules()
        return Response(result)
