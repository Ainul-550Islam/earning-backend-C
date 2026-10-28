"""
api/tasks/consumers.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Django Channels WebSocket consumers for real-time task events.
Requires: channels, channels_redis

Add to ASGI config:
    from api.tasks.routing import websocket_urlpatterns

WebSocket endpoints:
  ws://host/ws/tasks/live/          — Live task events for authenticated user
  ws://host/ws/tasks/leaderboard/   — Real-time leaderboard updates
  ws://host/ws/tasks/monitor/       — Admin: live Celery task monitor
  ws://host/ws/tasks/notifications/ — Real-time notifications
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# BASE CONSUMER
# ══════════════════════════════════════════════════════════════════════════════

class BaseTaskConsumer(AsyncWebsocketConsumer):
    """
    Base WebSocket consumer with authentication and group management.
    Subclass this for all task-related consumers.
    """

    requires_auth  = True
    group_prefix   = 'tasks'

    async def connect(self):
        """Accept connection after auth check."""
        if self.requires_auth and not await self._is_authenticated():
            await self.close(code=4001)
            return

        self.user_id = await self._get_user_id()
        self.group_name = self.get_group_name()

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send welcome message
        await self.send(text_data=json.dumps({
            'type':       'connection.established',
            'group':      self.group_name,
            'user_id':    self.user_id,
            'timestamp':  timezone.now().isoformat(),
        }))
        logger.debug(f"[WS] {self.__class__.__name__} connected: user={self.user_id}")

    async def disconnect(self, close_code):
        """Leave channel group on disconnect."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug(f"[WS] {self.__class__.__name__} disconnected: code={close_code}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')
            await self.handle_message(msg_type, data)
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON')

    async def handle_message(self, msg_type: str, data: dict):
        """Override in subclasses to handle specific message types."""
        if msg_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'timestamp': timezone.now().isoformat(),
            }))
        elif msg_type == 'subscribe':
            await self.send(text_data=json.dumps({
                'type': 'subscribed',
                'channel': data.get('channel', self.group_name),
            }))

    def get_group_name(self) -> str:
        """Override in subclasses to define the channel group name."""
        return f"{self.group_prefix}_global"

    async def send_json_data(self, data: dict):
        """Send a JSON message to this WebSocket connection."""
        await self.send(text_data=json.dumps(data, default=str))

    async def send_error(self, message: str, code: str = 'error'):
        """Send an error message."""
        await self.send_json_data({
            'type':    'error',
            'code':    code,
            'message': message,
        })

    # ── Channel layer event handlers ────────────────────────────────────────

    async def task_event(self, event):
        """Forward task events from channel layer to WebSocket."""
        await self.send_json_data({
            'type':    'task.event',
            'payload': event.get('payload', {}),
        })

    async def notification(self, event):
        """Forward notification events."""
        await self.send_json_data({
            'type':    'notification',
            'payload': event.get('payload', {}),
        })

    async def stats_update(self, event):
        """Forward stats update events."""
        await self.send_json_data({
            'type':    'stats.update',
            'payload': event.get('payload', {}),
        })

    # ── Auth helpers ───────────────────────────────────────────────────────

    async def _is_authenticated(self) -> bool:
        """Check if the WebSocket connection is authenticated."""
        try:
            scope = self.scope
            user  = scope.get('user')
            if user and user.is_authenticated:
                return True
            # Check JWT token in query string
            query_string = scope.get('query_string', b'').decode()
            if 'token=' in query_string:
                token = query_string.split('token=')[-1].split('&')[0]
                return await self._validate_jwt_token(token)
            return False
        except Exception:
            return False

    async def _get_user_id(self) -> int:
        """Get the authenticated user's ID."""
        try:
            user = self.scope.get('user')
            if user and user.is_authenticated:
                return user.pk
        except Exception:
            pass
        return 0

    async def _validate_jwt_token(self, token: str) -> bool:
        """Validate a JWT token for WebSocket auth."""
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            AccessToken(token)
            return True
        except Exception:
            return False

    @database_sync_to_async
    def _is_staff(self) -> bool:
        """Check if user is staff (database call)."""
        try:
            user = self.scope.get('user')
            return user.is_staff if user else False
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════════════════════
# LIVE TASK EVENTS CONSUMER
# ══════════════════════════════════════════════════════════════════════════════

class TaskLiveConsumer(BaseTaskConsumer):
    """
    WebSocket: ws://host/ws/tasks/live/
    Streams real-time task completion events for the authenticated user.
    Events: task.completed, reward.credited, streak.updated, level.up
    """

    def get_group_name(self) -> str:
        return f"task_live_{self.user_id}"

    async def handle_message(self, msg_type: str, data: dict):
        await super().handle_message(msg_type, data)

        if msg_type == 'request.recent_completions':
            completions = await self._get_recent_completions()
            await self.send_json_data({
                'type':        'recent_completions',
                'completions': completions,
                'timestamp':   timezone.now().isoformat(),
            })

        elif msg_type == 'request.wallet_balance':
            balance = await self._get_wallet_balance()
            await self.send_json_data({
                'type':    'wallet.balance',
                'balance': str(balance),
                'timestamp': timezone.now().isoformat(),
            })

    @database_sync_to_async
    def _get_recent_completions(self) -> list:
        try:
            from api.tasks.models import UserTaskCompletion
            qs = UserTaskCompletion.objects.filter(
                user_id=self.user_id, status='completed'
            ).select_related('task').order_by('-completed_at')[:10]
            return [
                {
                    'task_id':       c.task.task_id if c.task else '',
                    'task_name':     c.task.name if c.task else '',
                    'reward_amount': str(c.reward_amount or 0),
                    'completed_at':  c.completed_at.isoformat() if c.completed_at else '',
                }
                for c in qs
            ]
        except Exception:
            return []

    @database_sync_to_async
    def _get_wallet_balance(self):
        from decimal import Decimal
        try:
            from wallet.models import Wallet
            w = Wallet.objects.filter(user_id=self.user_id).values_list('balance', flat=True).first()
            return w or Decimal('0')
        except Exception:
            return Decimal('0')


# ══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD CONSUMER
# ══════════════════════════════════════════════════════════════════════════════

class LeaderboardConsumer(BaseTaskConsumer):
    """
    WebSocket: ws://host/ws/tasks/leaderboard/
    Broadcasts leaderboard updates every time the board changes.
    No auth required for viewing (public leaderboard).
    """

    requires_auth = False

    def get_group_name(self) -> str:
        return "task_leaderboard"

    async def connect(self):
        self.user_id    = 0
        self.group_name = self.get_group_name()
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial leaderboard data
        board = await self._get_leaderboard()
        await self.send_json_data({
            'type':        'leaderboard.initial',
            'leaderboard': board,
            'period':      'daily',
            'timestamp':   timezone.now().isoformat(),
        })

    async def leaderboard_update(self, event):
        """Forward leaderboard updates from channel layer."""
        await self.send_json_data({
            'type':        'leaderboard.update',
            'leaderboard': event.get('data', []),
            'period':      event.get('period', 'daily'),
            'timestamp':   timezone.now().isoformat(),
        })

    async def handle_message(self, msg_type: str, data: dict):
        if msg_type == 'request.leaderboard':
            period = data.get('period', 'daily')
            board  = await self._get_leaderboard(period)
            await self.send_json_data({
                'type':        'leaderboard.data',
                'leaderboard': board,
                'period':      period,
                'timestamp':   timezone.now().isoformat(),
            })

    @database_sync_to_async
    def _get_leaderboard(self, period: str = 'daily') -> list:
        from django.core.cache import cache
        return cache.get(f'leaderboard_{period}', [])[:20]


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN MONITOR CONSUMER
# ══════════════════════════════════════════════════════════════════════════════

class TaskMonitorConsumer(BaseTaskConsumer):
    """
    WebSocket: ws://host/ws/tasks/monitor/
    Staff-only: real-time Celery task monitor, worker health, queue depths.
    """

    def get_group_name(self) -> str:
        return "task_monitor_admin"

    async def connect(self):
        if not await self._is_staff():
            await self.close(code=4003)
            return
        await super().connect()

    async def handle_message(self, msg_type: str, data: dict):
        await super().handle_message(msg_type, data)

        if msg_type == 'request.system_status':
            status = await self._get_system_status()
            await self.send_json_data({
                'type':   'system.status',
                'status': status,
            })

        elif msg_type == 'request.queue_depths':
            depths = await self._get_queue_depths()
            await self.send_json_data({
                'type':   'queue.depths',
                'queues': depths,
            })

        elif msg_type == 'request.worker_health':
            workers = await self._get_worker_health()
            await self.send_json_data({
                'type':    'worker.health',
                'workers': workers,
            })

    async def monitor_update(self, event):
        """Forward monitoring updates from channel layer."""
        await self.send_json_data({
            'type':    'monitor.update',
            'payload': event.get('payload', {}),
        })

    @database_sync_to_async
    def _get_system_status(self) -> dict:
        from django.core.cache import cache
        return cache.get('system_diagnostics') or {'status': 'unknown'}

    @database_sync_to_async
    def _get_queue_depths(self) -> list:
        try:
            from api.tasks.services.QueueDepthService import QueueDepthService
            return QueueDepthService().get_all_depths()
        except Exception:
            return []

    @database_sync_to_async
    def _get_worker_health(self) -> dict:
        from django.core.cache import cache
        return cache.get('worker_health_all') or {}


# ══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION CONSUMER
# ══════════════════════════════════════════════════════════════════════════════

class NotificationConsumer(BaseTaskConsumer):
    """
    WebSocket: ws://host/ws/tasks/notifications/
    Real-time in-app notifications for the authenticated user.
    """

    def get_group_name(self) -> str:
        return f"notifications_{self.user_id}"

    async def connect(self):
        await super().connect()
        # Send unread notification count on connect
        count = await self._get_unread_count()
        await self.send_json_data({
            'type':   'notifications.unread_count',
            'count':  count,
        })

    async def handle_message(self, msg_type: str, data: dict):
        await super().handle_message(msg_type, data)

        if msg_type == 'mark.read':
            notification_id = data.get('id')
            if notification_id:
                await self._mark_read(notification_id)
                await self.send_json_data({'type': 'notification.marked_read', 'id': notification_id})

        elif msg_type == 'mark.all_read':
            await self._mark_all_read()
            await self.send_json_data({'type': 'notifications.all_marked_read'})

    async def send_notification(self, event):
        """Forward a new notification from channel layer."""
        await self.send_json_data({
            'type':         'notification.new',
            'notification': event.get('payload', {}),
        })

    @database_sync_to_async
    def _get_unread_count(self) -> int:
        try:
            from notifications.models import Notification
            return Notification.objects.filter(
                user_id=self.user_id, is_read=False
            ).count()
        except Exception:
            return 0

    @database_sync_to_async
    def _mark_read(self, notification_id: int) -> None:
        try:
            from notifications.models import Notification
            Notification.objects.filter(
                pk=notification_id, user_id=self.user_id
            ).update(is_read=True, read_at=timezone.now())
        except Exception:
            pass

    @database_sync_to_async
    def _mark_all_read(self) -> None:
        try:
            from notifications.models import Notification
            Notification.objects.filter(
                user_id=self.user_id, is_read=False
            ).update(is_read=True, read_at=timezone.now())
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# CHANNEL LAYER BROADCAST HELPERS
# ══════════════════════════════════════════════════════════════════════════════

async def broadcast_task_event(user_id: int, event_type: str, payload: dict) -> None:
    """
    Send a task event to a user's WebSocket connection via channel layer.
    Call this from Celery tasks after crediting rewards, etc.
    """
    try:
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        await layer.group_send(
            f"task_live_{user_id}",
            {
                'type':    'task.event',
                'payload': {'event_type': event_type, **payload},
            }
        )
    except Exception as e:
        logger.debug(f"[WS BROADCAST] task event: {e}")


def broadcast_task_event_sync(user_id: int, event_type: str, payload: dict) -> None:
    """Sync version of broadcast_task_event for use in Celery tasks."""
    try:
        from asgiref.sync import async_to_sync
        async_to_sync(broadcast_task_event)(user_id, event_type, payload)
    except Exception as e:
        logger.debug(f"[WS BROADCAST SYNC] {e}")


async def broadcast_leaderboard_update(period: str, data: list) -> None:
    """Broadcast leaderboard updates to all connected clients."""
    try:
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        await layer.group_send(
            "task_leaderboard",
            {'type': 'leaderboard.update', 'data': data, 'period': period}
        )
    except Exception as e:
        logger.debug(f"[WS BROADCAST] leaderboard: {e}")


async def broadcast_notification(user_id: int, notification: dict) -> None:
    """Send a notification to a specific user via WebSocket."""
    try:
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        await layer.group_send(
            f"notifications_{user_id}",
            {'type': 'send.notification', 'payload': notification}
        )
    except Exception as e:
        logger.debug(f"[WS BROADCAST] notification: {e}")


async def broadcast_monitor_update(payload: dict) -> None:
    """Send monitoring data to admin monitor WebSocket clients."""
    try:
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if not layer:
            return
        await layer.group_send(
            "task_monitor_admin",
            {'type': 'monitor.update', 'payload': payload}
        )
    except Exception as e:
        logger.debug(f"[WS BROADCAST] monitor: {e}")


__all__ = [
    'BaseTaskConsumer', 'TaskLiveConsumer', 'LeaderboardConsumer',
    'TaskMonitorConsumer', 'NotificationConsumer',
    'broadcast_task_event', 'broadcast_task_event_sync',
    'broadcast_leaderboard_update', 'broadcast_notification',
    'broadcast_monitor_update',
]
