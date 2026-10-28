# api/referral/consumers.py
# Real-time WebSocket consumers for referral module
# Django Channels required: pip install channels channels-redis
#
# settings.py এ যোগ করুন:
#   INSTALLED_APPS += ['channels']
#   ASGI_APPLICATION = 'config.asgi.application'
#   CHANNEL_LAYERS = {
#       'default': {
#           'BACKEND': 'channels_redis.core.RedisChannelLayer',
#           'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
#       }
#   }
# ============================================================

import json
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    import asyncio

    class ReferralLeaderboardConsumer(AsyncWebsocketConsumer):
        """
        Real-time referral leaderboard WebSocket.
        ws://yoursite.com/ws/referral/leaderboard/
        ws://yoursite.com/ws/referral/leaderboard/?period=weekly

        Broadcasts:
        - leaderboard updates every 30 seconds
        - instant update when new commission is paid
        """

        GROUP_NAME = 'referral_leaderboard'
        UPDATE_INTERVAL = 30  # seconds

        async def connect(self):
            self.period = self.scope['query_string'].decode()
            if 'period=weekly' in self.period:
                self.period = 'weekly'
            elif 'period=monthly' in self.period:
                self.period = 'monthly'
            else:
                self.period = 'daily'

            self.group_name = f'referral_leaderboard_{self.period}'

            # Join group
            await self.channel_layer.group_add(
                self.group_name, self.channel_name
            )
            await self.accept()

            # Send initial leaderboard immediately
            leaderboard = await self._get_leaderboard()
            await self.send(text_data=json.dumps({
                'type': 'leaderboard',
                'period': self.period,
                'data': leaderboard,
                'timestamp': timezone.now().isoformat(),
            }))

            # Start periodic updates
            self._update_task = asyncio.ensure_future(self._periodic_update())

        async def disconnect(self, close_code):
            if hasattr(self, '_update_task'):
                self._update_task.cancel()
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )

        async def receive(self, text_data):
            """Handle client messages (e.g., request refresh)."""
            try:
                data = json.loads(text_data)
                if data.get('type') == 'refresh':
                    leaderboard = await self._get_leaderboard()
                    await self.send(text_data=json.dumps({
                        'type': 'leaderboard',
                        'period': self.period,
                        'data': leaderboard,
                        'timestamp': timezone.now().isoformat(),
                    }))
            except Exception as e:
                logger.debug(f'[WS] receive error: {e}')

        async def leaderboard_update(self, event):
            """Called when group receives a leaderboard update message."""
            await self.send(text_data=json.dumps(event))

        async def commission_paid(self, event):
            """Called when a commission is paid — instant notification."""
            await self.send(text_data=json.dumps({
                'type': 'commission_paid',
                'data': event.get('data', {}),
                'timestamp': timezone.now().isoformat(),
            }))

        async def _periodic_update(self):
            """Broadcast leaderboard update every 30 seconds."""
            while True:
                await asyncio.sleep(self.UPDATE_INTERVAL)
                try:
                    leaderboard = await self._get_leaderboard()
                    await self.channel_layer.group_send(
                        self.group_name,
                        {
                            'type': 'leaderboard_update',
                            'period': self.period,
                            'data': leaderboard,
                            'timestamp': timezone.now().isoformat(),
                        }
                    )
                except Exception as e:
                    logger.debug(f'[WS] periodic update error: {e}')

        async def _get_leaderboard(self) -> list:
            """Get current leaderboard data (sync DB call wrapped in async)."""
            from asgiref.sync import sync_to_async
            return await sync_to_async(self._sync_get_leaderboard)()

        def _sync_get_leaderboard(self) -> list:
            try:
                from api.referral.models import TopReferrer
                today = timezone.now().date()
                entries = TopReferrer.objects.filter(
                    period=self.period,
                    date=today,
                ).select_related('user').order_by('rank')[:50]
                return [
                    {
                        'rank': e.rank,
                        'username': e.user.username,
                        'referral_count': e.referral_count,
                        'commission_earned': float(e.commission_earned),
                        'rank_change': e.rank_change,
                        'avatar': getattr(e.user, 'avatar_url', '') or '',
                    }
                    for e in entries
                ]
            except Exception as e:
                logger.debug(f'[WS] _sync_get_leaderboard error: {e}')
                return []


    class ReferralStatsConsumer(AsyncWebsocketConsumer):
        """
        Personal referral stats WebSocket.
        ws://yoursite.com/ws/referral/stats/  (auth required)

        Broadcasts:
        - instant update when user earns a commission
        - stats update every 60 seconds
        """

        UPDATE_INTERVAL = 60

        async def connect(self):
            user = self.scope.get('user')
            if not user or not user.is_authenticated:
                await self.close(code=4001)
                return

            self.user = user
            self.group_name = f'referral_user_{user.id}'

            await self.channel_layer.group_add(
                self.group_name, self.channel_name
            )
            await self.accept()

            # Send initial stats
            stats = await self._get_stats()
            await self.send(text_data=json.dumps({
                'type': 'stats',
                'data': stats,
                'timestamp': timezone.now().isoformat(),
            }))

            self._update_task = asyncio.ensure_future(self._periodic_update())

        async def disconnect(self, close_code):
            if hasattr(self, '_update_task'):
                self._update_task.cancel()
            if hasattr(self, 'group_name'):
                await self.channel_layer.group_discard(
                    self.group_name, self.channel_name
                )

        async def stats_update(self, event):
            await self.send(text_data=json.dumps(event))

        async def commission_received(self, event):
            """Instant notification when commission arrives."""
            await self.send(text_data=json.dumps({
                'type': 'commission_received',
                'data': event.get('data', {}),
                'timestamp': timezone.now().isoformat(),
            }))

        async def _periodic_update(self):
            while True:
                await asyncio.sleep(self.UPDATE_INTERVAL)
                try:
                    stats = await self._get_stats()
                    await self.send(text_data=json.dumps({
                        'type': 'stats',
                        'data': stats,
                        'timestamp': timezone.now().isoformat(),
                    }))
                except Exception as e:
                    logger.debug(f'[WS] personal stats update error: {e}')

        async def _get_stats(self) -> dict:
            from asgiref.sync import sync_to_async
            return await sync_to_async(self._sync_get_stats)()

        def _sync_get_stats(self) -> dict:
            try:
                from api.referral.INTEGRATION_SYSTEM.bridge import get_bridge
                return get_bridge().get_user_referral_summary(self.user)
            except Exception as e:
                logger.debug(f'[WS] _sync_get_stats error: {e}')
                return {}


    # ── WebSocket URL Routing ──────────────────────────────────────────────────

    def get_websocket_urlpatterns():
        """
        Include in config/routing.py:
            from api.referral.consumers import get_websocket_urlpatterns
            websocket_urlpatterns = get_websocket_urlpatterns()
        """
        from django.urls import re_path
        return [
            re_path(
                r'^ws/referral/leaderboard/$',
                ReferralLeaderboardConsumer.as_asgi(),
            ),
            re_path(
                r'^ws/referral/stats/$',
                ReferralStatsConsumer.as_asgi(),
            ),
        ]


    # ── Broadcast Helpers (call from signals/tasks) ───────────────────────────

    async def broadcast_commission_paid(user_id: int, amount: float, level: int):
        """
        Call this when a commission is paid — instantly pushes to user's WS.
        Usage from signal:
            from asgiref.sync import async_to_sync
            async_to_sync(broadcast_commission_paid)(user.id, float(amount), level)
        """
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                await channel_layer.group_send(
                    f'referral_user_{user_id}',
                    {
                        'type': 'commission_received',
                        'data': {
                            'amount': amount,
                            'level': level,
                            'message': f'৳{amount:.2f} L{level} commission received!',
                        }
                    }
                )
        except Exception as e:
            logger.debug(f'[WS] broadcast_commission_paid error: {e}')


    async def broadcast_leaderboard_update(period: str = 'daily'):
        """Trigger leaderboard refresh for all connected clients."""
        try:
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            if channel_layer:
                await channel_layer.group_send(
                    f'referral_leaderboard_{period}',
                    {'type': 'leaderboard_update', 'trigger': 'manual'}
                )
        except Exception as e:
            logger.debug(f'[WS] broadcast_leaderboard_update error: {e}')


    WEBSOCKET_AVAILABLE = True

except ImportError:
    # Django Channels not installed
    logger.debug('[WS] Django Channels not installed — WebSocket features disabled')
    WEBSOCKET_AVAILABLE = False

    def get_websocket_urlpatterns():
        return []

    async def broadcast_commission_paid(*args, **kwargs):
        pass

    async def broadcast_leaderboard_update(*args, **kwargs):
        pass