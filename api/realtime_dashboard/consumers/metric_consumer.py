"""
Metric consumer for Real-time Dashboard Backend.

Authentication enforcement: MetricConsumer requires an authenticated
user (same pattern as DashboardConsumer). Close code 4001 = auth required.

Group name: metric_<metric_id>
Receives:  {'type': 'metric_update', 'data': {...}}
"""
import json
from typing import Any, Dict

from channels.generic.websocket import AsyncWebsocketConsumer

from .base_consumer import TrackedConsumerMixin


class MetricConsumer(TrackedConsumerMixin, AsyncWebsocketConsumer):
    """WebSocket consumer for per-metric real-time updates."""

    async def connect(self) -> None:
        user = self.scope.get('user')
        if user is None or not getattr(user, 'is_authenticated', False):
            await self.close(code=4001)
            return

        self.metric_id = self.scope['url_route']['kwargs']['metric_id']
        self.metric_group_name = f'metric_{self.metric_id}'

        await self.channel_layer.group_add(
            self.metric_group_name,
            self.channel_name,
        )
        await self.track_connect()
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        if hasattr(self, 'metric_group_name'):
            await self.channel_layer.group_discard(
                self.metric_group_name,
                self.channel_name,
            )
        await self.track_disconnect()

    async def receive(self, text_data: str) -> None:
        data = json.loads(text_data)
        if data.get('type') == 'ping':
            await self.track_ping()
            await self.send(text_data=json.dumps({'type': 'pong'}))
            return
        await self.channel_layer.group_send(
            self.metric_group_name,
            {'type': 'metric_update', 'data': data},
        )

    async def metric_update(self, event: Dict[str, Any]) -> None:
        await self.send(text_data=json.dumps(event['data']))
