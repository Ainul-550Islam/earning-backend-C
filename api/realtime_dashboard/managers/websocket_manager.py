"""
WebSocket Connection manager for Real-time Dashboard Backend.
"""
from django.db import models


class WebSocketConnectionQuerySet(models.QuerySet):
    """
    Custom QuerySet for WebSocketConnection.

    See managers/widget_manager.py (WidgetQuerySet) for the full
    explanation of why the from_queryset() pattern is used here instead
    of a plain models.Manager subclass.

    The class (and the Manager created from it) is named
    WebSocketConnection* to distinguish it from the lifecycle coordinator
    class WebSocketManager in realtime_dashboard/websocket_manager.py.
    """

    def by_user(self, user_id):
        """Return connections belonging to the given user_id."""
        return self.filter(user_id=user_id)

    def by_status(self, status):
        """Return connections matching the given status."""
        return self.filter(status=status)

    def active(self):
        """
        Return only active (connected) connections.

        Note: WebSocketConnection uses 'connected' (not 'active') as its
        live-state value; this method encapsulates that domain detail so
        callers never hard-code the string.
        """
        return self.filter(status='connected')


WebSocketConnectionManager = models.Manager.from_queryset(WebSocketConnectionQuerySet)
