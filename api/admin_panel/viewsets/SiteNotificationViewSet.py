# api/admin_panel/viewsets/SiteNotificationViewSet.py
"""
SiteNotificationViewSet — migrated from views.py.
All original logic preserved.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from ..models.core import SiteNotification
from ..permissions import SystemAccessPermission
from ..pagination import AdminPagination
from ..filters import SiteNotificationFilter


class SiteNotificationViewSet(viewsets.ModelViewSet):
    """ViewSet for SiteNotification — migrated from views.py (all logic kept)."""
    queryset = SiteNotification.objects.all().order_by('-priority', '-created_at')
    permission_classes = [SystemAccessPermission]
    pagination_class = AdminPagination
    filterset_class = SiteNotificationFilter

    def get_serializer_class(self):
        from ..serializers.SiteNotificationSerializer import (
            SiteNotificationSerializer, NotificationCreateSerializer
        )
        if self.action == 'create':
            return NotificationCreateSerializer
        return SiteNotificationSerializer

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle is_active on a site notification."""
        notif = self.get_object()
        notif.is_active = not notif.is_active
        notif.save(update_fields=['is_active'])
        cache.delete('admin_panel:active_notifications')
        cache.delete('admin_panel:login_notifications')
        return Response({'success': True, 'is_active': notif.is_active})

    @action(detail=False, methods=['get'])
    def active_notifications(self, request):
        """Get active notifications (public — cached)."""
        cache_key = 'active_notifications'
        cached_data = cache.get(cache_key)

        if cached_data is None:
            notifications = SiteNotification.objects.filter(
                is_active=True,
                start_date__lte=timezone.now()
            ).filter(
                Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)
            ).order_by('-priority', '-created_at')
            serializer = self.get_serializer(notifications, many=True)
            cached_data = serializer.data
            cache.set(cache_key, cached_data, timeout=300)

        return Response(cached_data)

    @action(detail=False, methods=['get'])
    def login_notifications(self, request):
        """Get notifications to show on login."""
        notifications = SiteNotification.objects.filter(
            is_active=True,
            show_on_login=True,
            start_date__lte=timezone.now()
        ).filter(
            Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)
        ).order_by('-priority', '-created_at')

        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate notifications by type or all."""
        notification_type = request.data.get('notification_type')
        qs = SiteNotification.objects.filter(is_active=True)
        if notification_type:
            qs = qs.filter(notification_type=notification_type)
        count = qs.update(is_active=False)
        cache.delete('admin_panel:active_notifications')
        cache.delete('admin_panel:login_notifications')
        return Response({'success': True, 'deactivated': count})