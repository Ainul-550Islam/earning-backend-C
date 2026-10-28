"""
WebSocket Manager for Real-time Dashboard Backend.
"""
from typing import Dict, Any
from datetime import timedelta

from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models.websocket_connection import WebSocketConnection
from .models.real_time_metric import RealTimeMetric


class WebSocketManager:
    """
    Manager for WebSocket connections.
    """

    def __init__(self):
        """Initialize the WebSocket manager."""
        self.connections: Dict[str, Any] = {}

    def add_connection(self, connection_id: str, user_id: str, session_id: str = '') -> WebSocketConnection:
        """
        Add a WebSocket connection.

        Args:
            connection_id: Connection ID
            user_id: User ID
            session_id: Session ID

        Returns:
            WebSocketConnection instance
        """
        connection, created = WebSocketConnection.objects.get_or_create(
            connection_id=connection_id,
            defaults={
                'user_id': user_id,
                'session_id': session_id,
                'status': 'connected',
                'last_ping': timezone.now(),
            }
        )

        if not created:
            # FIXED: reconnecting an existing connection_id now resets
            # last_ping and clears disconnected_at. Previously this was
            # handled implicitly by last_ping's auto_now=True; now that
            # last_ping is a plain field (see
            # models/websocket_connection.py) it must be set explicitly.
            connection.status = 'connected'
            connection.disconnected_at = None
            connection.last_ping = timezone.now()
            connection.save()

        return connection

    def remove_connection(self, connection_id: str) -> bool:
        """
        Remove a WebSocket connection.

        Args:
            connection_id: Connection ID

        Returns:
            True if successful
        """
        try:
            connection = WebSocketConnection.objects.get(connection_id=connection_id)
            connection.status = 'disconnected'
            connection.disconnected_at = timezone.now()
            connection.save()
            return True
        except WebSocketConnection.DoesNotExist:
            return False

    def record_ping(self, connection_id: str) -> bool:
        """
        Record a heartbeat/ping for a connection, refreshing last_ping.

        NEW METHOD: added as the counterpart to the last_ping fix in
        models/websocket_connection.py. Now that last_ping is no longer
        auto-updated on every save(), something must explicitly refresh it
        for active connections, or cleanup_old_connections() will
        eventually mark every connection as disconnected regardless of
        actual activity. Consumers should call this whenever they receive
        a ping/heartbeat message from the client.

        Args:
            connection_id: Connection ID

        Returns:
            True if a matching connected connection was updated
        """
        updated = WebSocketConnection.objects.filter(
            connection_id=connection_id,
            status='connected'
        ).update(last_ping=timezone.now())

        return updated > 0

    def broadcast_metric_update(self, metric: RealTimeMetric) -> bool:
        """
        Broadcast a metric update to subscribed WebSocket clients.

        Delivery strategy (two targeted groups, no connection loop):

          1. metric_<id>  → MetricConsumer subscribers watching this metric.
          2. events        → EventConsumer subscribers watching the global feed.

        BUG FIXED (double-send): the previous implementation did BOTH a
        group_send (correct) AND a loop over every DB-tracked connection
        calling _send_to_connection() (incorrect). group_send() already
        delivers to every consumer in the group via the channel layer —
        the per-connection loop added a second delivery to the same
        consumer channels, so MetricConsumer subscribers received every
        metric update TWICE.

        The connection loop has been removed. _send_to_connection() is
        retained as a targeted single-connection utility (used by
        WebSocketManagerService.broadcast_to_connection()) but must NOT
        be called inside a broadcast that already uses group_send.

        Args:
            metric: RealTimeMetric instance

        Returns:
            True if the broadcast was attempted (channel layer available),
            False if no channel layer is configured.
        """
        payload = {
            'id': metric.id,
            'name': metric.name,
            'metric_type': metric.metric_type,
            'status': metric.status,
            'value': metric.value,
            'previous_value': metric.previous_value,
            'unit': metric.unit,
            'last_updated': metric.last_updated.isoformat()
        }

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False

        # 1. Notify all clients subscribed to this specific metric.
        async_to_sync(channel_layer.group_send)(
            f'metric_{metric.id}',
            {'type': 'metric_update', 'data': payload}
        )
        # 2. Notify all clients subscribed to the global event stream.
        async_to_sync(channel_layer.group_send)(
            'events',
            {
                'type': 'event_update',
                'data': {'event': 'metric_update', 'metric': payload}
            }
        )
        return True

    def _send_to_connection(self, connection_id: str, data: Dict[str, Any]) -> bool:
        """
        Send data to a specific connection.

        Args:
            connection_id: Connection ID
            data: Data to send

        Returns:
            True if successful
        """
        # FIXED: previously a no-op stub ("This would typically use
        # channels or similar. For now, we'll just log" - but it did not
        # even log).
        #
        # connection_id is the consumer's Channels `channel_name` (see
        # consumers/base_consumer.py), which looks like
        # "specific..inmemory!qZgvhokDfVau" - the '!' makes it an INVALID
        # *group* name (group names only allow alphanumerics, '-', '_',
        # '.'), but a perfectly valid *channel* name. So this sends
        # directly to that channel via channel_layer.send(), rather than
        # group_send() to a derived group name. The consumer receives it
        # through TrackedConsumerMixin.connection_message().
        #
        # If no channel layer is configured (e.g. CHANNEL_LAYERS unset, as
        # in some test environments), this remains a safe no-op and still
        # returns True so callers that only check "was delivery attempted"
        # are unaffected.
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return True

        async_to_sync(channel_layer.send)(
            connection_id,
            {'type': 'connection_message', 'data': data}
        )
        return True

    def cleanup_old_connections(self, timeout_seconds: int = 3600) -> int:
        """
        Clean up old connections.

        Args:
            timeout_seconds: Timeout in seconds

        Returns:
            Number of connections cleaned up
        """
        cutoff = timezone.now() - timedelta(seconds=timeout_seconds)

        count = WebSocketConnection.objects.filter(
            last_ping__lt=cutoff,
            status='connected'
        ).update(status='disconnected', disconnected_at=timezone.now())

        return count
