# api/payment_gateways/consumers.py
# Django Channels WebSocket consumers for real-time payment events

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import logging

logger = logging.getLogger(__name__)


class PaymentEventConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time payment events.
    Publishers connect to get live earnings updates.

    Connect: ws://yourdomain.com/ws/payment/events/
    """

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user_id   = user.id
        self.room_name = f'payment_user_{user.id}'
        self.room_group = f'pg_{self.room_name}'

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()
        await self.send_initial_state()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        """Handle messages from client."""
        try:
            data    = json.loads(text_data or '{}')
            msg_type= data.get('type', '')
            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif msg_type == 'subscribe':
                await self.send(text_data=json.dumps({'type': 'subscribed', 'channel': data.get('channel','')}))
        except Exception as e:
            logger.warning(f'WS receive error: {e}')

    async def payment_event(self, event):
        """Receive payment event from channel layer and forward to WebSocket."""
        await self.send(text_data=json.dumps({
            'type':    event.get('event_type', 'payment_update'),
            'data':    event.get('data', {}),
        }))

    async def send_initial_state(self):
        """Send current balance and stats on connection."""
        try:
            stats = await self.get_user_stats()
            await self.send(text_data=json.dumps({'type': 'initial_state', 'data': stats}))
        except Exception:
            pass

    @database_sync_to_async
    def get_user_stats(self):
        from django.contrib.auth import get_user_model
        from decimal import Decimal
        User  = get_user_model()
        user  = User.objects.get(id=self.user_id)
        return {
            'balance':    float(getattr(user, 'balance', 0) or 0),
            'user_id':    self.user_id,
        }


class GatewayHealthConsumer(AsyncWebsocketConsumer):
    """WebSocket for real-time gateway health status. Admin only."""

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_staff:
            await self.close()
            return
        await self.channel_layer.group_add('pg_gateway_health', self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard('pg_gateway_health', self.channel_name)

    async def gateway_health_update(self, event):
        await self.send(text_data=json.dumps({'type': 'health_update', 'data': event.get('data', {})}))
