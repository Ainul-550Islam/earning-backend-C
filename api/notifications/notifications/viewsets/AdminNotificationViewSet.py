# earning_backend/api/notifications/viewsets/AdminNotificationViewSet.py
"""
AdminNotificationViewSet — admin-only endpoints.

Endpoints:
  GET    /admin/notifications/          — list all notifications
  POST   /admin/notifications/bulk_send/ — bulk send to users/segment
  POST   /admin/notifications/preview/  — preview a template render
  POST   /admin/notifications/broadcast/ — send to ALL active users
  GET    /admin/notifications/stats/    — system-wide stats
  DELETE /admin/notifications/cleanup/  — delete old/expired notifications
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import serializers

from notifications.models import (
    Notification, NotificationTemplate, NotificationLog
)
from notifications.serializers import NotificationSerializer
from notifications.services import notification_service, template_service

logger = logging.getLogger(__name__)
User = get_user_model()


class AdminPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500


class BulkSendSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text='Explicit list of user PKs. If omitted, sends to all active users.',
    )
    title = serializers.CharField(max_length=255)
    message = serializers.CharField()
    notification_type = serializers.CharField(default='announcement')
    channel = serializers.ChoiceField(
        choices=['in_app', 'push', 'email', 'sms', 'all'],
        default='in_app',
    )
    priority = serializers.ChoiceField(
        choices=['lowest', 'low', 'medium', 'high', 'urgent', 'critical'],
        default='medium',
    )
    template_name = serializers.CharField(required=False, allow_blank=True)
    context = serializers.DictField(required=False, default=dict)
    schedule_at = serializers.DateTimeField(required=False, allow_null=True)


class TemplatePreviewSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    context = serializers.DictField(required=False, default=dict)
    language = serializers.CharField(default='en')


class AdminNotificationViewSet(viewsets.ModelViewSet):
    """
    Admin-only notification management viewset.
    Provides bulk send, broadcast, template preview, and cleanup operations.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = AdminPagination

    def get_queryset(self):
        qs = Notification.objects.all().select_related('user').order_by('-created_at')

        user_id = self.request.query_params.get('user_id')
        if user_id:
            qs = qs.filter(user_id=user_id)

        notification_type = self.request.query_params.get('type')
        if notification_type:
            qs = qs.filter(notification_type=notification_type)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        channel = self.request.query_params.get('channel')
        if channel:
            qs = qs.filter(channel=channel)

        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(title__icontains=search) | Q(message__icontains=search)
            )

        return qs.filter(is_deleted=False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='bulk_send')
    def bulk_send(self, request):
        """
        Send a notification to a list of users (or all active users).
        Queues a Celery task for large batches.
        """
        serializer = BulkSendSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        user_ids = data.get('user_ids')

        if user_ids:
            users = User.objects.filter(pk__in=user_ids, is_active=True)
        else:
            users = User.objects.filter(is_active=True)

        if not users.exists():
            return Response({'error': 'No target users found.'}, status=status.HTTP_400_BAD_REQUEST)

        total = users.count()

        # For large batches — delegate to Celery task
        if total > 500:
            try:
                from notifications.tasks import send_bulk_notifications_task
                send_bulk_notifications_task.delay(
                    user_ids=list(users.values_list('pk', flat=True)),
                    title=data['title'],
                    message=data['message'],
                    notification_type=data.get('notification_type', 'announcement'),
                    channel=data.get('channel', 'in_app'),
                    priority=data.get('priority', 'medium'),
                )
                return Response({
                    'success': True,
                    'message': f'Bulk send queued for {total} users.',
                    'total_users': total,
                    'async': True,
                })
            except Exception as exc:
                logger.error(f'AdminNotificationViewSet.bulk_send queue error: {exc}')

        # For small batches — process inline
        result = notification_service.create_bulk_notifications(
            users=list(users),
            title=data['title'],
            message=data['message'],
            notification_type=data.get('notification_type', 'announcement'),
            channel=data.get('channel', 'in_app'),
            priority=data.get('priority', 'medium'),
            created_by=request.user,
        )

        return Response({
            'success': True,
            'total_users': total,
            'successful': result.get('successful', 0),
            'failed': result.get('failed', 0),
            'async': False,
        })

    @action(detail=False, methods=['post'], url_path='broadcast')
    def broadcast(self, request):
        """Send a notification to ALL active users. Queues a Celery task."""
        title = request.data.get('title', '').strip()
        message = request.data.get('message', '').strip()
        channel = request.data.get('channel', 'in_app')
        priority = request.data.get('priority', 'medium')

        if not title or not message:
            return Response(
                {'error': 'title and message are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_ids = list(User.objects.filter(is_active=True).values_list('pk', flat=True))

        try:
            from notifications.tasks import send_bulk_notifications_task
            send_bulk_notifications_task.delay(
                user_ids=user_ids,
                title=title,
                message=message,
                notification_type='announcement',
                channel=channel,
                priority=priority,
            )
            return Response({
                'success': True,
                'message': f'Broadcast queued for {len(user_ids)} active users.',
                'total_users': len(user_ids),
            })
        except Exception as exc:
            logger.error(f'AdminNotificationViewSet.broadcast error: {exc}')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request):
        """Preview a template render with given context variables."""
        serializer = TemplatePreviewSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            template = NotificationTemplate.objects.get(pk=data['template_id'])
            preview = template_service.render_template(
                template_name=template.name,
                context=data.get('context', {}),
                language=data.get('language', 'en'),
            )
            return Response({
                'template_id': template.pk,
                'template_name': template.name,
                'preview': preview,
            })
        except NotificationTemplate.DoesNotExist:
            return Response({'error': 'Template not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """Return system-wide notification statistics."""
        try:
            stats = notification_service.get_system_stats(force_refresh=True)
            return Response(stats)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['delete'], url_path='cleanup')
    def cleanup(self, request):
        """Delete old/expired notifications. Days param controls cutoff (default 90)."""
        days = int(request.query_params.get('days', 90))
        try:
            result = notification_service.cleanup_old_notifications(days=days)
            return Response(result)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'], url_path='resend')
    def resend(self, request, pk=None):
        """Resend a specific notification."""
        notification = self.get_object()
        try:
            notification.prepare_for_retry()
            success = notification_service.send_notification(notification)
            return Response({'success': success, 'notification_id': notification.pk})
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
