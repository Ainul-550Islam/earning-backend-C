"""
Dashboard consumer for Real-time Dashboard Backend.

Authentication enforcement: DashboardConsumer requires an authenticated
user. The ASGI application wraps routing with AuthMiddlewareStack (see
asgi.py), which populates scope['user'] from the session cookie/token
before the consumer sees the connection. If the user is not authenticated,
the consumer closes the connection immediately with code 4001.

Group name: dashboard_<dashboard_id>
Receives:  {'type': 'dashboard_update', 'data': {...}}
"""
import json
from typing import Any, Dict

from channels.generic.websocket import AsyncWebsocketConsumer

from .base_consumer import TrackedConsumerMixin


class DashboardConsumer(TrackedConsumerMixin, AsyncWebsocketConsumer):
    """WebSocket consumer for dashboard-scoped updates."""

    async def connect(self) -> None:
        user = self.scope.get('user')
        if user is None or not getattr(user, 'is_authenticated', False):
            # 4001 = custom close code for "authentication required".
            # The client should redirect to login on receiving this code.
            await self.close(code=4001)
            return

        self.dashboard_id = self.scope['url_route']['kwargs']['dashboard_id']
        self.dashboard_group_name = f'dashboard_{self.dashboard_id}'

        await self.channel_layer.group_add(
            self.dashboard_group_name,
            self.channel_name,
        )
        await self.track_connect()
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        if hasattr(self, 'dashboard_group_name'):
            await self.channel_layer.group_discard(
                self.dashboard_group_name,
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
            self.dashboard_group_name,
            {'type': 'dashboard_update', 'data': data},
        )

    async def dashboard_update(self, event: Dict[str, Any]) -> None:
        await self.send(text_data=json.dumps(event['data']))
