"""
Event consumer for Real-time Dashboard Backend.

Authentication: EventConsumer intentionally allows unauthenticated
connections. The global `events` group is a public broadcast feed — any
client can subscribe to see metric-update events without being logged in.
This is appropriate for public dashboards or embedding scenarios.

If you want to restrict the event feed to authenticated users only,
add the same auth guard used in DashboardConsumer / MetricConsumer:

    user = self.scope.get('user')
    if not getattr(user, 'is_authenticated', False):
        await self.close(code=4001)
        return

Group name: events  (singleton — all EventConsumer clients share one group)
Receives:  {'type': 'event_update', 'data': {...}}
"""
import json
from typing import Any, Dict

from channels.generic.websocket import AsyncWebsocketConsumer

from .base_consumer import TrackedConsumerMixin


class EventConsumer(TrackedConsumerMixin, AsyncWebsocketConsumer):
    """
    WebSocket consumer for event updates.
    """

    async def connect(self) -> None:
        """
        Handle WebSocket connection.
        """
        self.event_group_name = 'events'

        # Join event group
        await self.channel_layer.group_add(
            self.event_group_name,
            self.channel_name
        )

        # NEW: register this connection in WebSocketConnection
        # (see consumers/base_consumer.py)
        await self.track_connect()

        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """
        Handle WebSocket disconnection.

        Args:
            close_code: Close code
        """
        # Leave event group
        await self.channel_layer.group_discard(
            self.event_group_name,
            self.channel_name
        )

        # NEW: mark this connection as disconnected
        # (see consumers/base_consumer.py)
        await self.track_disconnect()

    async def receive(self, text_data: str) -> None:
        """
        Receive message from WebSocket.

        Args:
            text_data: Text data
        """
        data = json.loads(text_data)

        # NEW: heartbeat handling - refresh last_ping instead of
        # broadcasting a 'ping' as if it were an event update.
        if data.get('type') == 'ping':
            await self.track_ping()
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return

        # Broadcast to event group
        await self.channel_layer.group_send(
            self.event_group_name,
            {
                'type': 'event_update',
                'data': data
            }
        )

    async def event_update(self, event: Dict[str, Any]) -> None:
        """
        Handle event update.

        Args:
            event: Event data
        """
        await self.send(text_data=json.dumps(event['data']))
