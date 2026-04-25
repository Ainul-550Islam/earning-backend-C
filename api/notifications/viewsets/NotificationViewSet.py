# earning_backend/api/notifications/viewsets/NotificationViewSet.py
"""
NotificationViewSet — split from views.py.

Keeps ALL existing logic intact from views.py. 
Added: mark_all_read action (already present in views.py — confirmed here).
This split file is the canonical viewsets/ version. views.py remains for
backward compatibility with existing url registrations.
"""

from datetime import datetime

from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import viewsets, filters, status
from rest_framework import decorators
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from notifications.models import Notification, NotificationLog
from notifications.serializers import (
    NotificationSerializer,
    CreateNotificationSerializer,
    UpdateNotificationSerializer,
    BulkDeleteSerializer,
    BatchActionSerializer,
    MarkAllAsReadSerializer,
    NotificationActionSerializer,
)


class IsOwnerOrAdmin:
    """Reuse permission from views.py — imported at runtime to avoid circular import."""
    pass


def _get_owner_permission():
    from notifications.views import IsOwnerOrAdmin as _P
    return _P


class StandardPagination:
    pass


def _get_pagination():
    from notifications.views import StandardPagination as _P
    return _P


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Notification model.

    Endpoints (all kept from views.py):
      GET    /notifications/                    — list
      POST   /notifications/                    — create
      GET    /notifications/{id}/               — retrieve
      PUT    /notifications/{id}/               — update
      DELETE /notifications/{id}/               — destroy
      GET    /notifications/unread/             — unread list
      GET    /notifications/count_unread/       — unread count
      GET    /notifications/pinned/             — pinned list
      GET    /notifications/archived/           — archived list
      POST   /notifications/mark-all-read/      — mark all read ← PLAN FIX
      POST   /notifications/send-bulk/          — bulk send
      POST   /notifications/bulk_delete/        — bulk delete
      POST   /notifications/bulk_action/        — batch action
      POST   /notifications/{id}/feedback/      — submit feedback
      POST   /notifications/{id}/track-impression/ — record impression
      POST   /notifications/{id}/mark-read/     — mark read
      POST   /notifications/{id}/mark-unread/   — mark unread
      POST   /notifications/{id}/pin/           — pin
      POST   /notifications/{id}/unpin/         — unpin
      POST   /notifications/{id}/archive/       — archive
      POST   /notifications/{id}/unarchive/     — unarchive
      POST   /notifications/{id}/track-click/   — track click
      GET    /notifications/{id}/replies/       — get replies
      POST   /notifications/{id}/reply/         — add reply
      GET    /notifications/{id}/thread/        — full thread
      GET    /notifications/{id}/analytics/     — notification analytics
      POST   /notifications/{id}/action/        — perform action
      GET    /notifications/summary/            — user summary
    """

    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['notification_type', 'priority', 'channel', 'status', 'is_read', 'is_archived']
    search_fields = ['title', 'message', 'tags']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'is_read']
    ordering = ['-created_at']

    def get_permissions(self):
        from notifications.views import IsOwnerOrAdmin
        return [IsAuthenticated(), IsOwnerOrAdmin()]

    def get_pagination_class(self):
        from notifications.views import StandardPagination
        return StandardPagination

    @property
    def pagination_class(self):
        from notifications.views import StandardPagination
        return StandardPagination

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user, is_deleted=False)

        params = self.request.query_params
        filter_kwargs = {}

        if params.get('is_read') is not None:
            filter_kwargs['is_read'] = params['is_read'].lower() == 'true'
        if params.get('is_archived') is not None:
            filter_kwargs['is_archived'] = params['is_archived'].lower() == 'true'
        if params.get('is_pinned') is not None:
            filter_kwargs['is_pinned'] = params['is_pinned'].lower() == 'true'
        if params.get('notification_type'):
            filter_kwargs['notification_type'] = params['notification_type']
        if params.get('priority'):
            filter_kwargs['priority'] = params['priority']
        if params.get('channel'):
            filter_kwargs['channel'] = params['channel']
        if params.get('status'):
            filter_kwargs['status'] = params['status']

        if filter_kwargs:
            queryset = queryset.filter(**filter_kwargs)

        start_date = params.get('start_date')
        if start_date:
            try:
                queryset = queryset.filter(
                    created_at__gte=datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                )
            except (ValueError, TypeError):
                pass

        end_date = params.get('end_date')
        if end_date:
            try:
                queryset = queryset.filter(
                    created_at__lte=datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                )
            except (ValueError, TypeError):
                pass

        tags = params.getlist('tags')
        if tags:
            for tag in tags:
                queryset = queryset.filter(tags__contains=[tag])

        if params.get('campaign_id'):
            queryset = queryset.filter(campaign_id=params['campaign_id'])
        if params.get('group_id'):
            queryset = queryset.filter(group_id=params['group_id'])

        include_expired = params.get('include_expired', 'false').lower() == 'true'
        if not include_expired:
            queryset = queryset.filter(
                Q(expire_date__isnull=True) | Q(expire_date__gt=timezone.now())
            )

        return queryset

    # ------------------------------------------------------------------
    # Serializer routing
    # ------------------------------------------------------------------

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateNotificationSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateNotificationSerializer
        return NotificationSerializer

    # ------------------------------------------------------------------
    # Create override
    # ------------------------------------------------------------------

    def perform_create(self, serializer):
        if self.request.user.is_staff:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save(user=self.request.user, created_by=self.request.user)

    # ------------------------------------------------------------------
    # List actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications."""
        queryset = self.get_queryset().filter(is_read=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def count_unread(self, request):
        """Get count of unread notifications."""
        return Response({'unread_count': self.get_queryset().filter(is_read=False).count()})

    @action(detail=False, methods=['get'])
    def pinned(self, request):
        """Get pinned notifications."""
        queryset = self.get_queryset().filter(is_pinned=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['get'])
    def archived(self, request):
        """Get archived notifications."""
        queryset = self.get_queryset().filter(is_archived=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        """
        Mark ALL notifications as read for the current user.
        PLAN FIX: This action was required by the plan spec.
        """
        serializer = MarkAllAsReadSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            return Response(result)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='send-bulk')
    def send_bulk(self, request):
        """Bulk send notifications to multiple users."""
        from notifications.serializers import BulkNotificationSerializer
        serializer = BulkNotificationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def bulk_delete(self, request):
        """Bulk delete notifications."""
        serializer = BulkDeleteSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            return Response(serializer.save())
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def bulk_action(self, request):
        """Bulk action on notifications (mark_read, pin, archive, delete, etc.)."""
        serializer = BatchActionSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            return Response(serializer.save())
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @decorators.action(detail=False, methods=['get'])
    def summary(self, request):
        """Get notification summary for current user."""
        queryset = self.get_queryset()
        return Response({
            'total': queryset.count(),
            'unread': queryset.filter(is_read=False).count(),
            'pinned': queryset.filter(is_pinned=True).count(),
            'archived': queryset.filter(is_archived=True).count(),
            'by_type': list(queryset.values('notification_type').annotate(
                count=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            ).order_by('-count')),
            'by_priority': list(queryset.values('priority').annotate(
                count=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            ).order_by('-count')),
            'by_channel': list(queryset.values('channel').annotate(
                count=Count('id'),
                unread=Count('id', filter=Q(is_read=False))
            ).order_by('-count')),
            'recent_activity': list(queryset.order_by('-created_at')[:5].values(
                'id', 'title', 'notification_type', 'is_read', 'created_at'
            )),
        })

    # ------------------------------------------------------------------
    # Detail actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='feedback')
    def feedback(self, request, pk=None):
        """Submit feedback for a notification."""
        notification = self.get_object()
        from notifications.serializers import NotificationFeedbackSerializer
        serializer = NotificationFeedbackSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(user=request.user, notification=notification)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='track-impression')
    def track_impression(self, request, pk=None):
        """Record notification impression (view)."""
        notification = self.get_object()
        if hasattr(notification, 'increment_impression_count'):
            notification.increment_impression_count()
        elif hasattr(notification, 'impression_count'):
            from django.db.models import F
            type(notification).objects.filter(pk=notification.pk).update(
                impression_count=F('impression_count') + 1
            )
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        notification.mark_as_read()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'], url_path='mark-unread')
    def mark_unread(self, request, pk=None):
        """Mark notification as unread."""
        notification = self.get_object()
        notification.mark_as_unread()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin notification."""
        notification = self.get_object()
        notification.pin()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin notification."""
        notification = self.get_object()
        notification.unpin()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archive notification."""
        notification = self.get_object()
        notification.archive()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Unarchive notification."""
        notification = self.get_object()
        notification.unarchive()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['post'], url_path='track-click')
    def click(self, request, pk=None):
        """Record notification click."""
        notification = self.get_object()
        notification.increment_click_count()
        NotificationLog.log_click(notification)
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        """Get replies to notification."""
        notification = self.get_object()
        replies = notification.get_replies()
        page = self.paginate_queryset(replies)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(replies, many=True).data)

    @action(detail=True, methods=['post'])
    def reply(self, request, pk=None):
        """Add reply to notification."""
        notification = self.get_object()
        serializer = CreateNotificationSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            reply_notification = notification.add_reply(
                title=serializer.validated_data['title'],
                message=serializer.validated_data['message'],
                user=request.user,
                **serializer.validated_data,
            )
            return Response(
                self.get_serializer(reply_notification).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def thread(self, request, pk=None):
        """Get complete notification thread."""
        notification = self.get_object()
        ancestors = notification.get_thread_ancestors()
        descendants = notification.get_thread_descendants()
        thread = sorted(
            list(ancestors) + [notification] + list(descendants),
            key=lambda x: x.created_at,
        )
        return Response(self.get_serializer(thread, many=True).data)

    @action(detail=True, methods=['get'])
    def analytics(self, request, pk=None):
        """Get notification analytics."""
        notification = self.get_object()
        return Response(notification.get_analytics_summary())

    @action(detail=True, methods=['post'])
    def action(self, request, pk=None):
        """Perform action on notification."""
        notification = self.get_object()
        serializer = NotificationActionSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            notification = serializer.update(notification, serializer.validated_data)
            return Response(self.get_serializer(notification).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
