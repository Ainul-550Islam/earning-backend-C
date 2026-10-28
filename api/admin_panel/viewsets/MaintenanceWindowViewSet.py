# api/admin_panel/viewsets/MaintenanceWindowViewSet.py
"""MaintenanceWindowViewSet — schedule + activate + notify."""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone

from ..models.config import MaintenanceWindow
from ..pagination import AdminPagination
from ..filters import MaintenanceWindowFilter, get_filter_for_model


class MaintenanceWindowViewSet(viewsets.ModelViewSet):
    """Manage maintenance windows. Supports activate, deactivate, notify."""
    permission_classes = [IsAdminUser]
    pagination_class = AdminPagination
    filterset_class = get_filter_for_model(MaintenanceWindow, MaintenanceWindowFilter)

    def get_serializer_class(self):
        from ..serializers.MaintenanceWindowSerializer import MaintenanceWindowSerializer
        return MaintenanceWindowSerializer

    def get_queryset(self):
        return MaintenanceWindow.objects.all().order_by('-start_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Immediately activate maintenance mode for this window."""
        window = self.get_object()
        window.is_active = True
        window.save(update_fields=['is_active'])
        cache.set('admin_panel:maintenance_mode_active', True, 86400)
        cache.set('admin_panel:maintenance_message', window.message, 86400)
        return Response({
            'success': True,
            'message': f'Maintenance window "{window.title}" is now ACTIVE.',
        })

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate maintenance mode for this window."""
        window = self.get_object()
        window.is_active = False
        window.save(update_fields=['is_active'])
        # Only clear cache if no other window is active
        if not MaintenanceWindow.objects.filter(is_active=True).exists():
            cache.delete('admin_panel:maintenance_mode_active')
        return Response({
            'success': True,
            'message': f'Maintenance window "{window.title}" is now INACTIVE.',
        })

    @action(detail=True, methods=['post'])
    def notify_users(self, request, pk=None):
        """Manually trigger pre-maintenance user notification."""
        window = self.get_object()
        try:
            from ..tasks import notify_pre_maintenance
            notify_pre_maintenance.delay(window.pk)
            return Response({'success': True, 'message': 'Notification task queued.'})
        except Exception as e:
            # Sync fallback
            from ..tasks.maintenance_tasks import send_pre_maintenance_notification
            result = send_pre_maintenance_notification(window.pk)
            return Response({'success': True, 'data': result})

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get the currently active maintenance window (if any)."""
        now = timezone.now()
        window = MaintenanceWindow.objects.filter(
            is_active=True
        ).first() or MaintenanceWindow.objects.filter(
            start_at__lte=now, end_at__gte=now
        ).first()

        if window:
            serializer = self.get_serializer(window)
            return Response({'active': True, 'window': serializer.data})
        return Response({'active': False, 'window': None})

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming scheduled maintenance windows."""
        now = timezone.now()
        windows = MaintenanceWindow.objects.filter(
            start_at__gt=now
        ).order_by('start_at')[:10]
        serializer = self.get_serializer(windows, many=True)
        return Response({'success': True, 'data': serializer.data})

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Quick maintenance mode status check."""
        is_active = cache.get('admin_panel:maintenance_mode_active', False)
        message = cache.get('admin_panel:maintenance_message', '')
        return Response({
            'maintenance_mode': bool(is_active),
            'message': message,
        })