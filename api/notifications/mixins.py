# earning_backend/api/notifications/mixins.py
"""
Mixins — Reusable DRF ViewSet mixins for notification endpoints.

These mixins are composed into ViewSets to add common behaviour
without duplicating code across 16 viewsets.
"""

import logging
from typing import Optional

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Ownership mixin
# ---------------------------------------------------------------------------

class NotificationOwnerMixin:
    """
    Restricts queryset to the authenticated user's own notifications.
    Staff users see everything.
    """

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ---------------------------------------------------------------------------
# Soft-delete mixin
# ---------------------------------------------------------------------------

class SoftDeleteMixin:
    """
    Overrides destroy() to soft-delete instead of hard-delete.
    """

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if hasattr(instance, 'is_deleted'):
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])
            return Response(status=status.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Mark-read mixin
# ---------------------------------------------------------------------------

class MarkReadMixin:
    """
    Adds mark_read and mark_all_read actions to a notification ViewSet.
    """

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """Mark a single notification as read."""
        notification = self.get_object()
        if not getattr(notification, 'is_read', True):
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=['is_read', 'read_at', 'updated_at'])
        return Response({'success': True, 'is_read': True})

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """Mark all notifications as read for the current user."""
        count = self.get_queryset().filter(is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return Response({'success': True, 'marked_count': count})

    @action(detail=True, methods=['post'], url_path='mark-unread')
    def mark_unread(self, request, pk=None):
        """Mark a notification as unread."""
        notification = self.get_object()
        notification.is_read = False
        notification.read_at = None
        notification.save(update_fields=['is_read', 'read_at', 'updated_at'])
        return Response({'success': True, 'is_read': False})


# ---------------------------------------------------------------------------
# Archive mixin
# ---------------------------------------------------------------------------

class ArchiveMixin:
    """Adds archive/unarchive/pin/unpin actions."""

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive a notification."""
        obj = self.get_object()
        obj.is_archived = True
        obj.save(update_fields=['is_archived', 'updated_at'])
        return Response({'success': True, 'is_archived': True})

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive a notification."""
        obj = self.get_object()
        obj.is_archived = False
        obj.save(update_fields=['is_archived', 'updated_at'])
        return Response({'success': True, 'is_archived': False})

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin a notification to the top."""
        obj = self.get_object()
        obj.is_pinned = True
        obj.save(update_fields=['is_pinned', 'updated_at'])
        return Response({'success': True, 'is_pinned': True})

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin a notification."""
        obj = self.get_object()
        obj.is_pinned = False
        obj.save(update_fields=['is_pinned', 'updated_at'])
        return Response({'success': True, 'is_pinned': False})


# ---------------------------------------------------------------------------
# Unread count mixin
# ---------------------------------------------------------------------------

class UnreadCountMixin:
    """Adds a fast unread_count action."""

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        """Return the number of unread notifications for the current user."""
        count = self.get_queryset().filter(is_read=False, is_deleted=False).count()
        return Response({'unread_count': count})


# ---------------------------------------------------------------------------
# Bulk action mixin
# ---------------------------------------------------------------------------

class BulkActionMixin:
    """
    Adds bulk operations: bulk_delete, bulk_mark_read, bulk_archive.
    Accepts {'ids': [1, 2, 3]} in request body.
    """

    @action(detail=False, methods=['post'], url_path='bulk-delete')
    def bulk_delete(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'ids required'}, status=status.HTTP_400_BAD_REQUEST)
        count = self.get_queryset().filter(pk__in=ids).update(
            is_deleted=True,
            deleted_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return Response({'success': True, 'deleted_count': count})

    @action(detail=False, methods=['post'], url_path='bulk-read')
    def bulk_mark_read(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'ids required'}, status=status.HTTP_400_BAD_REQUEST)
        count = self.get_queryset().filter(pk__in=ids, is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
            updated_at=timezone.now(),
        )
        return Response({'success': True, 'marked_count': count})

    @action(detail=False, methods=['post'], url_path='bulk-archive')
    def bulk_archive(self, request):
        ids = request.data.get('ids', [])
        if not ids:
            return Response({'error': 'ids required'}, status=status.HTTP_400_BAD_REQUEST)
        count = self.get_queryset().filter(pk__in=ids).update(
            is_archived=True,
            updated_at=timezone.now(),
        )
        return Response({'success': True, 'archived_count': count})


# ---------------------------------------------------------------------------
# Filter mixin
# ---------------------------------------------------------------------------

class NotificationFilterMixin:
    """
    Adds standard filtering to notification querysets via query params.
    """

    def filter_queryset_by_params(self, queryset):
        params = self.request.query_params

        if channel := params.get('channel'):
            queryset = queryset.filter(channel=channel)
        if priority := params.get('priority'):
            queryset = queryset.filter(priority=priority)
        if is_read := params.get('is_read'):
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        if notification_type := params.get('notification_type'):
            queryset = queryset.filter(notification_type=notification_type)
        if search := params.get('search'):
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(message__icontains=search)
            )
        if date_from := params.get('date_from'):
            queryset = queryset.filter(created_at__date__gte=date_from)
        if date_to := params.get('date_to'):
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset


# ---------------------------------------------------------------------------
# Audit mixin
# ---------------------------------------------------------------------------

class AuditMixin:
    """
    Logs create/update/delete operations to the audit trail.
    """

    def perform_create(self, serializer):
        instance = serializer.save()
        self._audit('create', instance)
        return instance

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit('update', instance)
        return instance

    def perform_destroy(self, instance):
        self._audit('delete', instance)
        super().perform_destroy(instance)

    def _audit(self, action: str, instance):
        try:
            from api.notifications.integration_system.integ_audit_logs import audit_logger
            audit_logger.log(
                action=action,
                module='notifications',
                actor_id=self.request.user.pk,
                target_type=type(instance).__name__,
                target_id=str(instance.pk),
                ip_address=self.request.META.get('REMOTE_ADDR', ''),
            )
        except Exception as exc:
            logger.debug(f'AuditMixin._audit: {exc}')


# ---------------------------------------------------------------------------
# Pagination mixin
# ---------------------------------------------------------------------------

class NotificationPaginationMixin:
    """
    Adds paginated list responses with consistent envelope format.
    """

    def get_paginated_data(self, queryset, serializer_class=None):
        serializer_cls = serializer_class or self.get_serializer_class()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = serializer_cls(page, many=True, context=self.get_serializer_context())
            return self.get_paginated_response(serializer.data)
        serializer = serializer_cls(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Tenant mixin (multi-tenant)
# ---------------------------------------------------------------------------

class TenantScopedMixin:
    """
    Scopes queryset to the current tenant (if multi-tenant is enabled).
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        if tenant and hasattr(qs.model, 'tenant'):
            qs = qs.filter(tenant=tenant)
        return qs


# ---------------------------------------------------------------------------
# Status action mixin
# ---------------------------------------------------------------------------

class StatusActionMixin:
    """
    Adds status/health endpoint to any viewset for monitoring dashboards.
    """

    @action(detail=False, methods=['get'], url_path='status')
    def system_status(self, request):
        """Return system status info for this resource."""
        if not request.user.is_staff:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()

        qs = self.get_queryset()
        return Response({
            'total': qs.count(),
            'model': self.queryset.model.__name__ if hasattr(self, 'queryset') else 'unknown',
            'timestamp': timezone.now().isoformat(),
        })
