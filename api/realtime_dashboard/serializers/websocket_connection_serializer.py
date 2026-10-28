"""
WebSocket Connection serializer for Real-time Dashboard Backend.
"""

from ..models.websocket_connection import WebSocketConnection
from .base_serializer import BaseSerializer


class WebSocketConnectionSerializer(BaseSerializer):
    """
    Serializer for WebSocketConnection model.
    """

    class Meta:
        model = WebSocketConnection
        fields = [
            'id', 'connection_id', 'user_id', 'session_id', 'status',
            'connected_at', 'disconnected_at', 'last_ping', 'metadata',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'connected_at', 'last_ping']


class WebSocketConnectionListSerializer(BaseSerializer):
    """
    List serializer for WebSocketConnection model.
    """

    class Meta:
        model = WebSocketConnection
        fields = [
            'id', 'connection_id', 'user_id', 'status', 'connected_at', 'last_ping'
        ]
        read_only_fields = ['connected_at', 'last_ping']
