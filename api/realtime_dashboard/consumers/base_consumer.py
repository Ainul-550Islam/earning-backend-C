"""
Base WebSocket consumer mixin for Real-time Dashboard Backend.

WIRED (v1.1.0): WebSocketConnectThrottle — cache-counter rate limiting.
FIXED (v1.3.0): track_disconnect() now sets disconnected_at = timezone.now().

Previous gap: WebSocketConnection.disconnected_at was always NULL because
track_disconnect() only updated status, never set disconnected_at. This
broke connection-duration analytics and cleanup-by-duration queries.

OWNERSHIP FIX (v1.5.0 — 360-degree audit): track_ping() used to run its
own inline `WebSocketConnection.objects.filter(...).update(last_ping=...)`
— a raw ORM write straight from the consumer, bypassing the service layer
that every other write path (cleanup_stale_connections, add_connection,
broadcast_metric_update) already goes through. Meanwhile
WebSocketManagerService.record_ping() / WebSocketManager.record_ping()
existed for exactly this purpose — their own docstring warns that without
something calling record_ping(), cleanup_old_connections() will eventually
mark every connection disconnected regardless of real activity — but had
zero callers anywhere in the codebase. Two independent implementations of
"refresh last_ping" is the same class of DRY violation the audit found in
the service/viewset CRUD methods, just at the consumer layer. track_ping()
now calls the service, matching the OWNERSHIP FIX pattern already used in
tasks.py's cleanup_stale_connections.
"""
import json
import logging
from typing import Optional, TYPE_CHECKING, TypeAlias

from django.core.cache import cache
from django.utils import timezone

if TYPE_CHECKING:
    # TrackedConsumerMixin is always combined with AsyncWebsocketConsumer
    # via multiple inheritance in the actual consumer classes (see
    # DashboardConsumer, MetricConsumer, EventConsumer), which is where
    # .scope/.channel_name/.close()/.send() actually come from at runtime.
    # Deriving from it only under TYPE_CHECKING gives mypy those attributes
    # without changing the real MRO (at runtime _MixinBase is `object`,
    # identical to the mixin's previous no-base declaration).
    from channels.generic.websocket import AsyncWebsocketConsumer
    _MixinBase: TypeAlias = AsyncWebsocketConsumer
else:
    _MixinBase = object

logger = logging.getLogger(__name__)

WS_CLOSE_NORMAL = 1000
WS_CLOSE_UNAUTHORIZED = 4001
WS_CLOSE_THROTTLED = 4029


class TrackedConsumerMixin(_MixinBase):
    """Mixin adding throttle enforcement and WebSocketConnection lifecycle management."""

    def _throttle_cache_key(self) -> str:
        user = self.scope.get('user')
        if user and getattr(user, 'is_authenticated', False):
            return f"ws_connect_rate:user:{user.pk}"
        headers = dict(self.scope.get('headers', []))
        forwarded = headers.get(b'x-forwarded-for', b'').decode()
        ip = forwarded.split(',')[0].strip() if forwarded else (
            self.scope.get('client', ('unknown',))[0]
        )
        return f"ws_connect_rate:ip:{ip}"

    def _check_and_increment_rate(self, window_seconds: int = 60, max_rate: int = 10) -> bool:
        key = self._throttle_cache_key()
        cache.add(key, 0, timeout=window_seconds)
        try:
            count = cache.incr(key)
        except ValueError:
            count = 1
        return count <= max_rate

    async def track_connect(self) -> bool:
        from asgiref.sync import sync_to_async
        from channels.db import database_sync_to_async
        from ..app_settings import app_settings

        allowed = await sync_to_async(self._check_and_increment_rate)(
            window_seconds=60,
            max_rate=app_settings.MAX_CONNECTIONS_PER_USER,
        )
        if not allowed:
            user = self.scope.get('user')
            logger.warning('WebSocket connect throttled',
                           extra={'user_pk': getattr(user, 'pk', 'anon')})
            await self.close(code=WS_CLOSE_THROTTLED)
            return False

        from ..models.websocket_connection import WebSocketConnection
        user = self.scope.get('user')
        user_id = str(user.pk) if (user and getattr(user, 'is_authenticated', False)) else 'anonymous'

        await database_sync_to_async(WebSocketConnection.objects.create)(
            connection_id=self.channel_name,
            user_id=user_id,
            session_id=getattr(self.scope.get('session'), 'session_key', '') or '',
            status=WebSocketConnection.ConnectionStatus.CONNECTED,
            metadata={},
        )
        logger.info('WebSocket connected',
                    extra={'user_pk': user_id, 'channel': self.channel_name})
        return True

    async def track_disconnect(self, close_code: Optional[int] = None) -> None:
        """
        FIXED (v1.3.0): disconnected_at is now set to timezone.now() alongside
        status update in a single .update() call — no extra DB round-trip.
        Previously disconnected_at was never set (always NULL).
        """
        from channels.db import database_sync_to_async
        from ..models.websocket_connection import WebSocketConnection
        try:
            await database_sync_to_async(
                WebSocketConnection.objects.filter(
                    connection_id=self.channel_name
                ).update
            )(
                status=WebSocketConnection.ConnectionStatus.DISCONNECTED,
                disconnected_at=timezone.now(),
            )
        except Exception:
            # A tracking failure must never break the disconnect flow —
            # but silently swallowing it (bare `pass`, flagged by bandit
            # B110) hides real bugs (DB connectivity, migration mismatch)
            # with zero observability. Log and continue, same pattern as
            # signals.py's dashboard_updated() broadcast-failure handling.
            logger.exception(
                'track_disconnect: failed to update connection status',
                extra={'channel': getattr(self, 'channel_name', '')},
            )
        logger.info('WebSocket disconnected',
                    extra={'close_code': close_code,
                           'channel': getattr(self, 'channel_name', '')})

    async def track_ping(self) -> None:
        """
        OWNERSHIP FIX (v1.5.0): delegates to
        WebSocketManagerService.record_ping() — see the module docstring
        for why this replaced a duplicate inline ORM write.
        """
        from channels.db import database_sync_to_async
        from ..services.websocket_manager_service import WebSocketManagerService
        await database_sync_to_async(WebSocketManagerService().record_ping)(self.channel_name)
        logger.debug('WebSocket ping', extra={'channel': self.channel_name})

    async def connection_message(self, event: dict) -> None:
        """Forward direct channel messages to the WebSocket client."""
        await self.send(text_data=json.dumps(event['data']))
