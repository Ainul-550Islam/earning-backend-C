# earning_backend/api/notifications/viewsets/InAppMessageViewSet.py
"""
InAppMessageViewSet — CRUD + actions for InAppMessage.

Endpoints:
  GET    /in-app-messages/          — list user's in-app messages
  GET    /in-app-messages/{id}/     — retrieve single message
  POST   /in-app-messages/{id}/read/   — mark as read
  POST   /in-app-messages/{id}/dismiss/ — dismiss
  POST   /in-app-messages/mark_all_read/ — mark all read
  DELETE /in-app-messages/{id}/     — delete single message
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from django.db.models import Q


class InAppMessageViewSet(viewsets.ModelViewSet):
    """ViewSet for InAppMessage model."""

    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 100

    pagination_class = _Pagination

    def get_queryset(self):
        from api.notifications.models.channel import InAppMessage
        qs = InAppMessage.objects.filter(
            user=self.request.user,
            is_dismissed=False,
        ).select_related('notification')

        # Exclude expired messages by default
        include_expired = self.request.query_params.get('include_expired', 'false').lower() == 'true'
        if not include_expired:
            qs = qs.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            )

        # Read filter
        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            qs = qs.filter(is_read=is_read.lower() == 'true')

        # Type filter
        message_type = self.request.query_params.get('type')
        if message_type:
            qs = qs.filter(message_type=message_type)

        return qs.order_by('display_priority', '-created_at')

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.notifications.models.channel import InAppMessage

        class InAppMessageSerializer(serializers.ModelSerializer):
            is_expired = serializers.SerializerMethodField()

            class Meta:
                model = InAppMessage
                fields = [
                    'id', 'message_type', 'title', 'body', 'image_url', 'icon_url',
                    'cta_text', 'cta_url', 'extra_data', 'is_read', 'read_at',
                    'is_dismissed', 'expires_at', 'display_priority', 'is_expired',
                    'created_at',
                ]
                read_only_fields = ['id', 'is_read', 'read_at', 'is_dismissed', 'created_at', 'is_expired']

            def get_is_expired(self, obj):
                return obj.is_expired()

        return InAppMessageSerializer

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        serializer = self.get_serializer(page or qs, many=True)
        unread_count = qs.filter(is_read=False).count()

        if page is not None:
            resp = self.get_paginated_response(serializer.data)
            resp.data['unread_count'] = unread_count
            return resp

        return Response({'results': serializer.data, 'unread_count': unread_count})

    @action(detail=True, methods=['post'])
    def read(self, request, pk=None):
        """Mark a single in-app message as read."""
        msg = self.get_object()
        msg.mark_read()
        return Response({'success': True, 'id': msg.pk, 'read_at': msg.read_at.isoformat()})

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss (hide) a single in-app message."""
        msg = self.get_object()
        msg.dismiss()
        return Response({'success': True, 'id': msg.pk, 'dismissed_at': msg.dismissed_at.isoformat()})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all unread in-app messages as read."""
        now = timezone.now()
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=now, updated_at=now
        )
        return Response({'success': True, 'marked_read': updated})

    @action(detail=False, methods=['post'])
    def dismiss_all(self, request):
        """Dismiss all in-app messages."""
        now = timezone.now()
        updated = self.get_queryset().update(
            is_dismissed=True, dismissed_at=now, updated_at=now
        )
        return Response({'success': True, 'dismissed': updated})

    def destroy(self, request, *args, **kwargs):
        msg = self.get_object()
        msg.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
