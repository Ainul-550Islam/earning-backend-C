# earning_backend/api/notifications/consumers.py
"""
Django Channels WebSocket consumer for real-time notifications.

Features:
  - Real-time notification delivery to connected clients
  - Per-user notification group channels
  - In-app message broadcast
  - Online status tracking
  - Notification read/dismiss acknowledgement

Setup (requires django-channels):
    pip install channels channels-redis

Add to settings.py:
    INSTALLED_APPS += ['channels']
    ASGI_APPLICATION = 'config.asgi.application'
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
        }
    }

Add to asgi.py:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.auth import AuthMiddlewareStack
    from api.notifications.routing import websocket_urlpatterns

    application = ProtocolTypeRouter({
        'http': django_asgi_app,
        'websocket': AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    })
"""

import json
import logging
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async
    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False
    # Fallback base class when channels not installed
    class AsyncWebsocketConsumer:
        pass


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notification delivery.

    URL: ws://your-domain/ws/notifications/

    Client → Server messages:
        {"type": "mark_read", "notification_id": 123}
        {"type": "mark_all_read"}
        {"type": "dismiss", "message_id": 456}
        {"type": "ping"}

    Server → Client messages:
        {"type": "new_notification", "data": {...}}
        {"type": "new_in_app_message", "message": {...}}
        {"type": "notification_count", "unread": 5}
        {"type": "pong"}
        {"type": "error", "message": "..."}
    """

    async def connect(self):
        """Handle WebSocket connection."""
        user = self.scope.get('user')

        if not user or not user.is_authenticated:
            logger.warning('WebSocket connection rejected: unauthenticated user')
            await self.close(code=4001)
            return

        self.user_id = user.pk
        self.group_name = f'notifications_{self.user_id}'

        # Join user's notification group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current unread count on connect
        unread_count = await self._get_unread_count()
        await self.send(json.dumps({
            'type': 'notification_count',
            'unread': unread_count,
            'connected_at': timezone.now().isoformat(),
        }))

        # Send any pending in-app messages
        await self._send_pending_in_app_messages()

        logger.info(f'WebSocket connected: user #{self.user_id}')

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f'WebSocket disconnected: user #{getattr(self, "user_id", "?")} code={close_code}')

    async def receive(self, text_data):
        """Handle message from WebSocket client."""
        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')

            if msg_type == 'mark_read':
                await self._handle_mark_read(data.get('notification_id'))
            elif msg_type == 'mark_all_read':
                await self._handle_mark_all_read()
            elif msg_type == 'dismiss':
                await self._handle_dismiss(data.get('message_id'))
            elif msg_type == 'ping':
                await self.send(json.dumps({'type': 'pong', 'ts': timezone.now().isoformat()}))
            elif msg_type == 'get_count':
                count = await self._get_unread_count()
                await self.send(json.dumps({'type': 'notification_count', 'unread': count}))
            else:
                await self.send(json.dumps({'type': 'error', 'message': f'Unknown type: {msg_type}'}))

        except json.JSONDecodeError:
            await self.send(json.dumps({'type': 'error', 'message': 'Invalid JSON'}))
        except Exception as exc:
            logger.error(f'WebSocket receive error user #{getattr(self, "user_id", "?")}: {exc}')

    # ------------------------------------------------------------------
    # Group message handlers (called when group_send is used)
    # ------------------------------------------------------------------

    async def new_notification(self, event):
        """Broadcast a new notification to the client."""
        await self.send(json.dumps({
            'type': 'new_notification',
            'data': event.get('data', {}),
        }))

    async def new_in_app_message(self, event):
        """Broadcast a new in-app message to the client."""
        await self.send(json.dumps({
            'type': 'new_in_app_message',
            'message': event.get('message', {}),
        }))

    async def notification_update(self, event):
        """Broadcast a notification update (read, deleted, etc.)."""
        await self.send(json.dumps({
            'type': 'notification_update',
            'notification_id': event.get('notification_id'),
            'action': event.get('action'),
        }))

    async def notification_count_update(self, event):
        """Broadcast updated unread count."""
        await self.send(json.dumps({
            'type': 'notification_count',
            'unread': event.get('unread', 0),
        }))

    async def system_message(self, event):
        """Broadcast a system-level message."""
        await self.send(json.dumps({
            'type': 'system_message',
            'message': event.get('message', ''),
            'level': event.get('level', 'info'),
        }))

    # ------------------------------------------------------------------
    # Handlers for client messages
    # ------------------------------------------------------------------

    async def _handle_mark_read(self, notification_id):
        if not notification_id:
            return
        success = await self._mark_notification_read(notification_id)
        if success:
            count = await self._get_unread_count()
            await self.send(json.dumps({
                'type': 'notification_update',
                'notification_id': notification_id,
                'action': 'marked_read',
                'unread': count,
            }))

    async def _handle_mark_all_read(self):
        count = await self._mark_all_read()
        await self.send(json.dumps({
            'type': 'all_marked_read',
            'marked_count': count,
            'unread': 0,
        }))

    async def _handle_dismiss(self, message_id):
        if not message_id:
            return
        success = await self._dismiss_in_app_message(message_id)
        if success:
            await self.send(json.dumps({
                'type': 'message_dismissed',
                'message_id': message_id,
            }))

    async def _send_pending_in_app_messages(self):
        """Send unread/undismissed in-app messages on connect."""
        messages = await self._get_pending_in_app_messages()
        for msg in messages:
            await self.send(json.dumps({
                'type': 'new_in_app_message',
                'message': msg,
            }))

    # ------------------------------------------------------------------
    # Database helpers (sync_to_async)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _get_unread_count(self):
        try:
            from api.notifications.models import Notification
            return Notification.objects.filter(
                user_id=self.user_id,
                is_read=False,
                is_deleted=False,
            ).count()
        except Exception:
            return 0

    @database_sync_to_async
    def _mark_notification_read(self, notification_id):
        try:
            from api.notifications.models import Notification
            notif = Notification.objects.get(pk=notification_id, user_id=self.user_id)
            notif.mark_as_read()
            return True
        except Exception:
            return False

    @database_sync_to_async
    def _mark_all_read(self):
        try:
            from api.notifications.models import Notification
            count = Notification.objects.filter(
                user_id=self.user_id, is_read=False, is_deleted=False
            ).update(is_read=True, read_at=timezone.now(), updated_at=timezone.now())
            return count
        except Exception:
            return 0

    @database_sync_to_async
    def _dismiss_in_app_message(self, message_id):
        try:
            from api.notifications.models.channel import InAppMessage
            msg = InAppMessage.objects.get(pk=message_id, user_id=self.user_id)
            msg.dismiss()
            return True
        except Exception:
            return False

    @database_sync_to_async
    def _get_pending_in_app_messages(self):
        try:
            from api.notifications.models.channel import InAppMessage
            from django.db.models import Q
            messages = InAppMessage.objects.filter(
                user_id=self.user_id,
                is_dismissed=False,
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            ).order_by('display_priority', '-created_at')[:10]
            return [m.to_dict() for m in messages]
        except Exception:
            return []


# ------------------------------------------------------------------
# Utility function to broadcast from anywhere in the codebase
# ------------------------------------------------------------------

def send_notification_to_user(user_id: int, notification_data: dict):
    """
    Send a real-time notification to a specific user's WebSocket.

    Usage:
        from api.notifications.consumers import send_notification_to_user
        send_notification_to_user(user.pk, notification.to_dict())
    """
    if not CHANNELS_AVAILABLE:
        return False

    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if not channel_layer:
            return False

        group_name = f'notifications_{user_id}'
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'new_notification',
                'data': notification_data,
            }
        )
        return True
    except Exception as exc:
        logger.warning(f'send_notification_to_user user #{user_id}: {exc}')
        return False


def send_count_update_to_user(user_id: int, unread_count: int):
    """Broadcast updated unread count to a user."""
    if not CHANNELS_AVAILABLE:
        return False
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if not channel_layer:
            return False

        async_to_sync(channel_layer.group_send)(
            f'notifications_{user_id}',
            {'type': 'notification_count_update', 'unread': unread_count},
        )
        return True
    except Exception as exc:
        logger.warning(f'send_count_update_to_user #{user_id}: {exc}')
        return False


def broadcast_system_message(user_ids: list, message: str, level: str = 'info'):
    """Broadcast a system message to multiple users."""
    if not CHANNELS_AVAILABLE:
        return 0
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if not channel_layer:
            return 0

        sent = 0
        for user_id in user_ids:
            try:
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{user_id}',
                    {'type': 'system_message', 'message': message, 'level': level},
                )
                sent += 1
            except Exception:
                pass
        return sent
    except Exception:
        return 0
