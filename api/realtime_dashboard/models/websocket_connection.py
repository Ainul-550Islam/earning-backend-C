"""
WebSocket Connection model for Real-time Dashboard Backend.
"""
from django.db import models
from django.utils import timezone

from .base import BaseModel
from ..managers.websocket_manager import WebSocketConnectionManager


class WebSocketConnection(BaseModel):
    """
    Model for WebSocket connections.
    """

    class ConnectionStatus(models.TextChoices):
        CONNECTED = 'connected', 'Connected'
        DISCONNECTED = 'disconnected', 'Disconnected'
        ERROR = 'error', 'Error'

    # Custom manager - exposes .active(), .by_user(), .by_status() so
    # viewsets and services never repeat raw .filter(status='connected') etc.
    objects = WebSocketConnectionManager()  # type: ignore[django-manager-missing]

    # Connection information
    connection_id = models.CharField(max_length=255, unique=True, db_index=True)
    user_id = models.CharField(max_length=255, blank=True, db_index=True)
    session_id = models.CharField(max_length=255, blank=True, db_index=True)

    # Status
    status = models.CharField(
        max_length=50, choices=ConnectionStatus.choices, default=ConnectionStatus.CONNECTED, db_index=True,
    )

    # Connection details
    connected_at = models.DateTimeField(auto_now_add=True)
    disconnected_at = models.DateTimeField(blank=True, null=True)
    # FIXED: was `models.DateTimeField(auto_now=True)`. With auto_now=True,
    # Django silently overwrites last_ping to the current time on EVERY
    # .save() call - including saves that change unrelated fields such as
    # `status` or `disconnected_at` (see remove_connection() in
    # websocket_manager.py). This made it impossible to ever have a
    # "stale" last_ping, which broke cleanup_old_connections(): any
    # manually-set old timestamp was discarded the instant .save() ran.
    #
    # last_ping is now a plain DateTimeField defaulting to "now" at
    # creation time, and is explicitly refreshed by
    # WebSocketManager.add_connection() (on connect/reconnect) and the new
    # WebSocketManager.record_ping() (on heartbeat). See migration
    # 0006_alter_websocketconnection_last_ping.
    last_ping = models.DateTimeField(default=timezone.now)

    # Metadata
    metadata = models.JSONField(default=dict)

    class Meta:
        verbose_name = 'WebSocket Connection'
        verbose_name_plural = 'WebSocket Connections'
        ordering = ['-connected_at']
        indexes = [
            models.Index(fields=['connection_id'], name='wsc_connection_id_idx'),
            models.Index(fields=['user_id'], name='wsc_user_idx'),
            models.Index(fields=['status'], name='wsc_status_idx'),
            models.Index(fields=['last_ping'], name='wsc_last_ping_idx'),
        ]

    def __str__(self):
        return f"{self.connection_id} ({self.status})"
