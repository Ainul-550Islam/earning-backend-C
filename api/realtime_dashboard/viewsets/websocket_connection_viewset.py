"""
WebSocket Connection viewset for Real-time Dashboard Backend.

WIRED (v1.2.0):
  - broadcast_to_user() action → WebSocketManagerService.broadcast_to_user()
    POST /api/connections/broadcast_to_user/  (staff only)
    WebSocketManagerService.broadcast_to_user() was defined but had NO
    HTTP endpoint — impossible to trigger a targeted push from outside
    the module without going through Celery tasks.

DRY: by_user() now uses @require_query_param, matching the pattern used
in UserDashboardViewSet.by_user() and replacing the manual check.
"""
from typing import Type

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer, OpenApiParameter
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from django_filters.rest_framework import DjangoFilterBackend

from ..managers.websocket_manager import WebSocketConnectionQuerySet
from ..models.websocket_connection import WebSocketConnection
from ..serializers.websocket_connection_serializer import (
    WebSocketConnectionSerializer,
    WebSocketConnectionListSerializer,
)
from ..pagination import StandardResultsSetPagination
from ..filters import WebSocketConnectionFilter
from ..decorators import require_query_param
from ..services.websocket_manager_service import WebSocketManagerService


@extend_schema_view(
    list=extend_schema(tags=['connections'], summary='List WebSocket connections'),
    retrieve=extend_schema(tags=['connections'], summary='Get a WebSocket connection'),
)
class WebSocketConnectionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only ViewSet for WebSocketConnection.

    Write operations (create/update/delete) are managed internally by
    the consumer lifecycle (connect → track_connect → disconnect →
    track_disconnect). The API exposes read + broadcast only.
    """

    serializer_class = WebSocketConnectionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WebSocketConnectionFilter
    search_fields = ['connection_id', 'session_id']
    ordering_fields = ['status', 'connected_at', 'last_ping']
    ordering = ['-connected_at']

    def get_queryset(self) -> WebSocketConnectionQuerySet:
        """Return own connections. Staff sees all."""
        user = self.request.user
        if user.is_staff:
            return WebSocketConnection.objects.all()
        return WebSocketConnection.objects.by_user(str(user.pk))

    def get_serializer_class(self) -> Type[BaseSerializer]:
        if self.action == 'list':
            return WebSocketConnectionListSerializer
        return WebSocketConnectionSerializer

    @extend_schema(tags=['connections'], summary='List your active connections',
                   responses={200: WebSocketConnectionListSerializer(many=True)})
    @action(detail=False, methods=['get'])
    def active(self, request: Request) -> Response:
        """GET /api/connections/active/ — list own active connections."""
        connections = self.get_queryset().active()
        serializer = self.get_serializer(connections, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['connections'],
        summary='List connections for a given user (staff only)',
        parameters=[
            OpenApiParameter(
                name='user_id', type=str, location=OpenApiParameter.QUERY,
                required=True, description='Look up connections owned by this user ID. Requires is_staff.',
            ),
        ],
        responses={
            200: WebSocketConnectionListSerializer(many=True),
            403: inline_serializer(
                name='ConnectionByUserForbidden',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
        },
    )
    @require_query_param('user_id')
    @action(detail=False, methods=['get'])
    def by_user(self, request: Request) -> Response:
        """
        GET /api/connections/by_user/?user_id=X  (staff only)

        DRY: @require_query_param replaces the manual missing-param check.
        """
        if not request.user.is_staff:
            return Response(
                {'success': False, 'error': 'Only staff users can query by arbitrary user_id.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        user_id = request.query_params['user_id']
        connections = WebSocketConnection.objects.by_user(user_id)
        serializer = self.get_serializer(connections, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=['connections'],
        summary='Broadcast a message to a user (staff only)',
        description='Sends `data` to every active WebSocket connection owned by user_id.',
        request=inline_serializer(
            name='BroadcastToUserRequest',
            fields={
                'user_id': serializers.CharField(),
                'data': serializers.DictField(),
            },
        ),
        responses={
            200: inline_serializer(
                name='BroadcastToUserResponse',
                fields={
                    'success': serializers.BooleanField(),
                    'user_id': serializers.CharField(),
                    'connections_reached': serializers.IntegerField(),
                },
            ),
            400: inline_serializer(
                name='BroadcastToUserBadRequest',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
            403: inline_serializer(
                name='BroadcastToUserForbidden',
                fields={'success': serializers.BooleanField(), 'error': serializers.CharField()},
            ),
        },
    )
    @action(detail=False, methods=['post'])
    def broadcast_to_user(self, request: Request) -> Response:
        """
        POST /api/connections/broadcast_to_user/  (staff only)

        WIRED (v1.2.0): WebSocketManagerService.broadcast_to_user() was
        defined but had no HTTP endpoint. Previously impossible to send a
        targeted push message to all connections of a specific user from
        outside the module without Celery.

        Request body:
            {
                "user_id": "123",
                "data": {"type": "notification", "message": "Your payout was sent"}
            }

        Sends `data` to all active WebSocket connections owned by user_id.
        Staff only — regular users cannot push to arbitrary user IDs.
        """
        if not request.user.is_staff:
            return Response(
                {'success': False, 'error': 'Only staff users can broadcast to arbitrary users.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_id = request.data.get('user_id')
        data = request.data.get('data')

        if not user_id:
            return Response(
                {'success': False, 'error': "'user_id' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if data is None:
            return Response(
                {'success': False, 'error': "'data' payload is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = WebSocketManagerService().broadcast_to_user(str(user_id), data)
        active_count = WebSocketConnection.objects.by_user(str(user_id)).active().count()

        return Response({
            'success': result,
            'user_id': user_id,
            'connections_reached': active_count,
        })
