"""
SmartLink WebSocket Consumers
Real-time live click + conversion counters for publisher dashboard.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache

logger = logging.getLogger('smartlink.websocket')


class SmartLinkLiveConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer: live stats for a single SmartLink.
    Connect: ws://domain/ws/smartlink/<slug>/live/
    Broadcasts: clicks, conversions, revenue every second.
    """

    async def connect(self):
        self.slug = self.scope['url_route']['kwargs']['slug']
        self.group_name = f'smartlink_live_{self.slug}'
        self.user = self.scope.get('user')

        # Auth check
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        # Verify publisher owns this SmartLink
        owns = await self._verify_ownership()
        if not owns:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial stats snapshot
        stats = await self._get_live_stats()
        await self.send(text_data=json.dumps({'type': 'snapshot', 'data': stats}))
        logger.debug(f"WS connected: {self.slug} user={self.user.username}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.debug(f"WS disconnected: {self.slug}")

    async def receive(self, text_data):
        """Handle ping from client to keep connection alive."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))
            elif data.get('type') == 'subscribe_stats':
                stats = await self._get_live_stats()
                await self.send(text_data=json.dumps({'type': 'stats', 'data': stats}))
        except Exception as e:
            logger.warning(f"WS receive error: {e}")

    async def live_click(self, event):
        """Receive click event from channel layer and forward to WebSocket client."""
        await self.send(text_data=json.dumps({
            'type': 'click',
            'data': event['data'],
        }))

    async def live_conversion(self, event):
        """Receive conversion event."""
        await self.send(text_data=json.dumps({
            'type': 'conversion',
            'data': event['data'],
        }))

    async def stats_update(self, event):
        """Receive aggregated stats update."""
        await self.send(text_data=json.dumps({
            'type': 'stats_update',
            'data': event['data'],
        }))

    @database_sync_to_async
    def _verify_ownership(self) -> bool:
        from ..models import SmartLink
        if self.user.is_staff:
            return SmartLink.objects.filter(slug=self.slug).exists()
        return SmartLink.objects.filter(slug=self.slug, publisher=self.user).exists()

    @database_sync_to_async
    def _get_live_stats(self) -> dict:
        from ..models import SmartLink
        from django.utils import timezone
        import datetime

        try:
            sl = SmartLink.objects.get(slug=self.slug)
            today = timezone.now().date()
            cutoff = timezone.now() - datetime.timedelta(hours=1)

            from ..models import Click
            from django.db.models import Count, Sum, Q
            last_hour = Click.objects.filter(
                smartlink=sl,
                created_at__gte=cutoff,
                is_bot=False,
            ).aggregate(
                clicks=Count('id'),
                unique=Count('id', filter=Q(is_unique=True)),
                conversions=Count('id', filter=Q(is_converted=True)),
                revenue=Sum('payout'),
            )

            return {
                'slug': self.slug,
                'total_clicks': sl.total_clicks,
                'total_conversions': sl.total_conversions,
                'total_revenue': float(sl.total_revenue),
                'last_hour_clicks': last_hour['clicks'] or 0,
                'last_hour_conversions': last_hour['conversions'] or 0,
                'last_hour_revenue': float(last_hour['revenue'] or 0),
                'is_active': sl.is_active,
                'last_click_at': sl.last_click_at.isoformat() if sl.last_click_at else None,
            }
        except Exception:
            return {}


class PublisherDashboardConsumer(AsyncWebsocketConsumer):
    """
    Publisher-level live dashboard: aggregate stats across all SmartLinks.
    Connect: ws://domain/ws/publisher/dashboard/
    """

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.group_name = f'publisher_dashboard_{self.user.pk}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        stats = await self._get_publisher_stats()
        await self.send(text_data=json.dumps({'type': 'snapshot', 'data': stats}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))
        elif data.get('type') == 'refresh':
            stats = await self._get_publisher_stats()
            await self.send(text_data=json.dumps({'type': 'stats', 'data': stats}))

    async def dashboard_update(self, event):
        await self.send(text_data=json.dumps({'type': 'update', 'data': event['data']}))

    @database_sync_to_async
    def _get_publisher_stats(self) -> dict:
        from ..services.analytics.SmartLinkAnalyticsService import SmartLinkAnalyticsService
        svc = SmartLinkAnalyticsService()
        return svc.get_publisher_totals(self.user, days=1)
