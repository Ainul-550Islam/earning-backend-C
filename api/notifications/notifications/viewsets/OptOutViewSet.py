# earning_backend/api/notifications/viewsets/OptOutViewSet.py
"""
OptOutViewSet — user unsubscribe / resubscribe endpoints.

Endpoints:
  GET    /opt-outs/                  — list current user's opt-out records
  POST   /opt-outs/                  — opt out of a channel
  POST   /opt-outs/resubscribe/      — resubscribe to a channel
  GET    /opt-outs/status/           — get full opt-out status for current user
  POST   /opt-outs/opt_out_all/      — opt out of all channels
  POST   /opt-outs/resubscribe_all/  — resubscribe to all channels
  GET    /opt-outs/export/           — export GDPR opt-out data
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class OptOutViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for user opt-out (unsubscribe) management."""

    permission_classes = [IsAuthenticated]

    class _Pagination(PageNumberPagination):
        page_size = 20
        page_size_query_param = 'page_size'
        max_page_size = 100

    pagination_class = _Pagination

    def get_queryset(self):
        from api.notifications.models.analytics import OptOutTracking
        return OptOutTracking.objects.filter(user=self.request.user).order_by('-opted_out_at')

    def get_serializer_class(self):
        from rest_framework import serializers
        from api.notifications.models.analytics import OptOutTracking

        class OptOutSerializer(serializers.ModelSerializer):
            class Meta:
                model = OptOutTracking
                fields = [
                    'id', 'channel', 'is_active', 'reason', 'notes',
                    'opted_out_at', 'opted_in_at', 'created_at',
                ]
                read_only_fields = ['id', 'created_at']

        return OptOutSerializer

    @action(detail=False, methods=['post'])
    def opt_out(self, request):
        """Opt out of a channel."""
        from api.notifications.services.OptOutService import opt_out_service
        channel = request.data.get('channel', 'all')
        reason = request.data.get('reason', 'user_request')
        notes = request.data.get('notes', '')
        result = opt_out_service.opt_out(
            user=request.user,
            channel=channel,
            reason=reason,
            notes=notes,
            actioned_by=request.user,
        )
        code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=False, methods=['post'])
    def resubscribe(self, request):
        """Resubscribe to a channel."""
        from api.notifications.services.OptOutService import opt_out_service
        channel = request.data.get('channel', 'all')
        result = opt_out_service.resubscribe(
            user=request.user,
            channel=channel,
            actioned_by=request.user,
        )
        code = status.HTTP_200_OK if result['success'] else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)

    @action(detail=False, methods=['get'])
    def opt_out_status(self, request):
        """Get full opt-out status across all channels for current user."""
        from api.notifications.services.OptOutService import opt_out_service
        opted_out_channels = opt_out_service.get_opted_out_channels(request.user)
        all_channels = ['in_app', 'push', 'email', 'sms', 'telegram', 'whatsapp', 'browser']
        return Response({
            'user_id': request.user.pk,
            'opted_out_channels': opted_out_channels,
            'subscribed_channels': [c for c in all_channels if c not in opted_out_channels],
        })

    @action(detail=False, methods=['post'])
    def opt_out_all(self, request):
        """Opt out of all notification channels."""
        from api.notifications.services.OptOutService import opt_out_service
        result = opt_out_service.opt_out(
            user=request.user,
            channel='all',
            reason=request.data.get('reason', 'user_request'),
            notes=request.data.get('notes', ''),
            actioned_by=request.user,
        )
        return Response(result)

    @action(detail=False, methods=['post'])
    def resubscribe_all(self, request):
        """Resubscribe to all channels."""
        from api.notifications.services.OptOutService import opt_out_service
        result = opt_out_service.resubscribe(user=request.user, channel='all')
        return Response(result)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export GDPR-compliant opt-out history for the current user."""
        from api.notifications.services.OptOutService import opt_out_service
        data = opt_out_service.export_user_opt_outs(request.user)
        return Response(data)
