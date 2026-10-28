"""
WebSocket Manager service for Real-time Dashboard Backend.

This service is the SINGLE OWNER of all WebSocket connection-lifecycle
and broadcast operations. Nothing outside this service should instantiate
WebSocketManager directly.

Ownership model:
  Consumers  → WebSocketManagerService (add/remove/ping)
  Signals    → WebSocketManagerService (broadcast_metric_update)
  Tasks      → WebSocketManagerService (cleanup)
  Middleware → WebSocketManager is ok here (it only injects the manager,
               not calls business methods; see middleware.py)

  WebSocketManagerService → WebSocketManager → channel layer / ORM
"""
import logging
from typing import Dict, Any

from ..websocket_manager import WebSocketManager
from ..models.websocket_connection import WebSocketConnection
from ..models.real_time_metric import RealTimeMetric

logger = logging.getLogger(__name__)


class WebSocketManagerService:
    """Service for WebSocket manager and broadcast operations."""

    def __init__(self) -> None:
        self.manager = WebSocketManager()

    # ── Connection lifecycle ─────────────────────────────────────────────────

    def add_connection(self, connection_id: str, user_id: str, session_id: str = '') -> WebSocketConnection:
        """
        Register a new WebSocket connection.

        FIXED: previously returned a bool (True/False), discarding the
        WebSocketConnection instance. Tests assert on connection_id of the
        returned object; exceptions now propagate rather than being hidden
        by a bare except-return-False.
        """
        return self.manager.add_connection(connection_id, user_id, session_id)

    def remove_connection(self, connection_id: str) -> bool:
        """Mark a WebSocket connection as disconnected."""
        return self.manager.remove_connection(connection_id)

    def record_ping(self, connection_id: str) -> bool:
        """
        Refresh last_ping for a connection (heartbeat).

        OWNERSHIP FIX: consumers previously called
        WebSocketManager().record_ping() directly. This method delegates
        to WebSocketManager but is the only entry point that should be
        called from outside this service.
        """
        return self.manager.record_ping(connection_id)

    def cleanup_old_connections(self, timeout_seconds: int = 3600) -> int:
        """Mark stale connections (silent >timeout_seconds) as disconnected."""
        count = self.manager.cleanup_old_connections(timeout_seconds)
        logger.info('cleanup_old_connections: %d stale connection(s) disconnected', count)
        return count

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_active_connections(self) -> list:
        """Return all currently connected WebSocketConnection instances."""
        return list(WebSocketConnection.objects.filter(status='connected'))

    # ── Broadcasting ─────────────────────────────────────────────────────────

    def broadcast_metric_update(self, metric: RealTimeMetric) -> bool:
        """
        Broadcast a RealTimeMetric update to all subscribed WebSocket clients.

        OWNERSHIP FIX: signals.py and consumers previously called
        WebSocketManager().broadcast_metric_update() directly. All broadcast
        operations are now routed through this service so there is exactly
        one place to add cross-cutting concerns (logging, error handling,
        feature flags).

        Returns True if a channel layer is configured, False otherwise.
        """
        result = self.manager.broadcast_metric_update(metric)
        if result:
            logger.debug(
                'broadcast_metric_update: metric_id=%d name=%s value=%s',
                metric.id, metric.name, metric.value
            )
        return result

    def broadcast_to_user(self, user_id: str, data: Dict[str, Any]) -> bool:
        """
        Send a direct payload to every active connection for a given user.

        Used for targeted, user-specific notifications (e.g. "your export
        is ready") that don't belong to a Channels group.
        """
        connections = WebSocketConnection.objects.filter(
            user_id=user_id,
            status='connected',
        )
        for connection in connections:
            self.manager._send_to_connection(connection.connection_id, data)
        return True

    def broadcast_to_connection(self, connection_id: str, data: Dict[str, Any]) -> bool:
        """
        Send a direct payload to a single connection by its connection_id.

        This is the public API for single-connection delivery; nothing
        outside this service should call WebSocketManager._send_to_connection
        directly.
        """
        return self.manager._send_to_connection(connection_id, data)
