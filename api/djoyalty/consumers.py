# api/djoyalty/consumers.py
"""
Djoyalty WebSocket Consumers -- Real-time loyalty updates।
Django Channels consumer for live point balance, notifications।
pip install channels channels-redis

Add to INSTALLED_APPS: 'channels'
ASGI_APPLICATION = 'your_project.routing.application'
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
                'CONFIG': {'hosts': [('localhost', 6379)]}}
}
"""
import json
import logging

logger = logging.getLogger(__name__)


class LoyaltyConsumer:
    """
    WebSocket consumer for real-time loyalty updates।
    Customers connect -> receive live point updates, notifications।

    ws://yourdomain.com/ws/loyalty/{customer_code}/
    """

    async def websocket_connect(self, message):
        try:
            from channels.generic.websocket import AsyncWebsocketConsumer
        except ImportError:
            logger.warning('consumers.py: channels package not installed. pip install channels')
            return

        self.customer_code = self.scope['url_route']['kwargs']['customer_code']
        self.group_name = f'loyalty_{self.customer_code}'

        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial balance
        balance = await self._get_balance()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'customer_code': self.customer_code,
            'balance': str(balance),
        }))

    async def websocket_disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def websocket_receive(self, text_data):
        """Handle incoming WebSocket messages।"""
        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')

            if msg_type == 'get_balance':
                balance = await self._get_balance()
                await self.send(text_data=json.dumps({
                    'type': 'balance_update',
                    'balance': str(balance),
                }))

            elif msg_type == 'mark_notification_read':
                notif_id = data.get('notification_id')
                if notif_id:
                    await self._mark_notification_read(notif_id)

        except json.JSONDecodeError:
            pass

    # ─── Group message handlers ─────────────────────────────────

    async def loyalty_points_update(self, event):
        """Receive points update from group।"""
        await self.send(text_data=json.dumps({
            'type': 'points_update',
            'points_earned': event.get('points_earned'),
            'new_balance': event.get('new_balance'),
            'source': event.get('source', ''),
        }))

    async def loyalty_tier_upgrade(self, event):
        """Receive tier upgrade from group।"""
        await self.send(text_data=json.dumps({
            'type': 'tier_upgrade',
            'new_tier': event.get('new_tier'),
            'old_tier': event.get('old_tier'),
        }))

    async def loyalty_notification(self, event):
        """Receive new notification from group।"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'title': event.get('title'),
            'body': event.get('body'),
            'icon': event.get('icon', '🔔'),
            'notification_type': event.get('notification_type'),
        }))

    async def loyalty_badge_unlocked(self, event):
        """Receive badge unlock from group।"""
        await self.send(text_data=json.dumps({
            'type': 'badge_unlocked',
            'badge_name': event.get('badge_name'),
            'badge_icon': event.get('badge_icon', '🏅'),
        }))

    # ─── DB helpers (sync_to_async) ─────────────────────────────

    async def _get_balance(self):
        from asgiref.sync import sync_to_async

        @sync_to_async
        def get():
            from .models.points import LoyaltyPoints
            from .models.core import Customer
            try:
                customer = Customer.objects.get(code=self.customer_code)
                lp = LoyaltyPoints.objects.filter(customer=customer).first()
                return lp.balance if lp else 0
            except Exception:
                return 0

        return await get()

    async def _mark_notification_read(self, notif_id: int):
        from asgiref.sync import sync_to_async

        @sync_to_async
        def mark():
            from .models.notifications import NotificationCenter
            from django.utils import timezone
            NotificationCenter.objects.filter(id=notif_id).update(
                is_read=True, read_at=timezone.now()
            )

        await mark()


def push_loyalty_event_to_customer(customer_code: str, event_type: str, data: dict):
    """
    Push a real-time event to a specific customer's WebSocket।
    Call from services/tasks after points earned, tier upgrade, etc।

    Usage:
        push_loyalty_event_to_customer(
            'CUST001', 'points_update',
            {'points_earned': 100, 'new_balance': 500}
        )
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        group_name = f'loyalty_{customer_code}'

        async_to_sync(channel_layer.group_send)(
            group_name,
            {'type': f'loyalty_{event_type}', **data},
        )
    except Exception as e:
        logger.debug('push_loyalty_event_to_customer error: %s', e)
