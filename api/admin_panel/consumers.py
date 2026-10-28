# api/admin_panel/consumers.py
"""
WebSocket Consumers for admin_panel real-time dashboard.
Channels: live KPIs, fraud alerts, activity feed, system health.
Connects to Django Channels — ws://domain/ws/admin/dashboard/
"""
from __future__ import annotations
import json
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class AdminDashboardConsumer(AsyncWebsocketConsumer):
    """
    Real-time admin dashboard WebSocket.
    Pushes: live KPIs, fraud alerts, activity feed every 5 seconds.
    Group: admin_dashboard
    """
    GROUP_NAME = 'admin_dashboard'
    PUSH_INTERVAL = 5  # seconds

    async def connect(self):
        self.user = self.scope.get('user')

        # Auth: must be staff
        if not self.user or not self.user.is_authenticated or not self.user.is_staff:
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()

        # Send initial snapshot
        snapshot = await self._get_kpi_snapshot()
        await self.send(text_data=json.dumps({
            'type': 'snapshot',
            'data': snapshot,
            'timestamp': timezone.now().isoformat(),
        }))

        # Start push loop
        asyncio.ensure_future(self._push_loop())
        logger.info(f"[AdminDashboard WS] Connected: {self.user.username}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)
        logger.debug(f"[AdminDashboard WS] Disconnected: {getattr(self.user, 'username', '?')}")

    async def receive(self, text_data=None, bytes_data=None):
        """Handle client messages — ping/pong, filter updates."""
        try:
            data = json.loads(text_data or '{}')
            msg_type = data.get('type', '')

            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

            elif msg_type == 'request_kpis':
                kpis = await self._get_kpi_snapshot()
                await self.send(text_data=json.dumps({'type': 'kpis', 'data': kpis}))

            elif msg_type == 'request_fraud':
                alerts = await self._get_fraud_alerts()
                await self.send(text_data=json.dumps({'type': 'fraud_alerts', 'data': alerts}))

        except Exception as e:
            logger.error(f"[AdminDashboard WS] receive error: {e}")

    # ==================== GROUP HANDLERS ====================

    async def kpi_update(self, event):
        """Receive KPI update from channel layer and push to client."""
        await self.send(text_data=json.dumps({
            'type': 'kpi_update',
            'data': event['data'],
            'timestamp': event.get('timestamp', timezone.now().isoformat()),
        }))

    async def fraud_alert(self, event):
        """Receive fraud alert and push to client."""
        await self.send(text_data=json.dumps({
            'type': 'fraud_alert',
            'data': event['data'],
            'severity': event.get('severity', 'medium'),
        }))

    async def activity_event(self, event):
        """Receive admin activity event and push."""
        await self.send(text_data=json.dumps({
            'type': 'activity',
            'data': event['data'],
        }))

    async def system_health(self, event):
        """System health status update."""
        await self.send(text_data=json.dumps({
            'type': 'system_health',
            'data': event['data'],
        }))

    # ==================== DATA FETCHERS ====================

    @database_sync_to_async
    def _get_kpi_snapshot(self) -> dict:
        """Fetch live KPIs from cache."""
        cached = cache.get('admin:live_kpis')
        if cached:
            return cached
        # Fetch fresh
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            today = timezone.now().date()
            return {
                'total_users': User.objects.count(),
                'new_today': User.objects.filter(date_joined__date=today).count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'maintenance_active': bool(cache.get('admin_panel:maintenance_mode_active')),
                'timestamp': timezone.now().isoformat(),
            }
        except Exception as e:
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}

    @database_sync_to_async
    def _get_fraud_alerts(self) -> list:
        """Fetch recent fraud alerts."""
        try:
            from api.fraud_detection.models import FraudAttempt
            last_10m = timezone.now() - timezone.timedelta(minutes=10)
            alerts = list(FraudAttempt.objects.filter(
                created_at__gte=last_10m, fraud_score__gte=70
            ).values('id', 'user_id', 'ip_address', 'fraud_score', 'attempt_type')[:20])
            return alerts
        except Exception:
            return []

    async def _push_loop(self):
        """Push KPI updates every PUSH_INTERVAL seconds."""
        while True:
            await asyncio.sleep(self.PUSH_INTERVAL)
            try:
                kpis = await self._get_kpi_snapshot()
                await self.channel_layer.group_send(self.GROUP_NAME, {
                    'type': 'kpi_update',
                    'data': kpis,
                    'timestamp': timezone.now().isoformat(),
                })
            except Exception as e:
                logger.debug(f"[AdminDashboard WS] push_loop error: {e}")
                break


class AdminFraudAlertConsumer(AsyncWebsocketConsumer):
    """
    Real-time fraud alerts WebSocket.
    ws://domain/ws/admin/fraud/alerts/
    Pushes: new fraud events, IP blocks, multi-account detections.
    """
    GROUP_NAME = 'admin_fraud_alerts'

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_staff:
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'connected', 'group': self.GROUP_NAME}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, **kwargs):
        data = json.loads(text_data or '{}')
        if data.get('type') == 'ping':
            await self.send(text_data=json.dumps({'type': 'pong'}))

    async def fraud_event(self, event):
        await self.send(text_data=json.dumps({
            'type': 'fraud_event',
            'event_type': event.get('event_type', 'fraud_detected'),
            'data': event.get('data', {}),
            'severity': event.get('severity', 'medium'),
            'timestamp': timezone.now().isoformat(),
        }))


class AdminSystemHealthConsumer(AsyncWebsocketConsumer):
    """
    System health WebSocket — live health status of all 50 apps.
    ws://domain/ws/admin/health/
    """
    GROUP_NAME = 'admin_system_health'

    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_staff:
            await self.close(code=4001)
            return
        await self.channel_layer.group_add(self.GROUP_NAME, self.channel_name)
        await self.accept()
        # Send current health
        health = await self._get_health()
        await self.send(text_data=json.dumps({'type': 'health_snapshot', 'data': health}))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.GROUP_NAME, self.channel_name)

    async def receive(self, text_data=None, **kwargs):
        data = json.loads(text_data or '{}')
        if data.get('type') == 'request_health':
            health = await self._get_health()
            await self.send(text_data=json.dumps({'type': 'health_update', 'data': health}))

    async def health_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'health_update',
            'data': event['data'],
            'timestamp': timezone.now().isoformat(),
        }))

    @database_sync_to_async
    def _get_health(self) -> dict:
        try:
            from api.admin_panel.INTEGRATION_SYSTEM.health_check import HealthCheck
            cached = HealthCheck.get_cached_health()
            return cached or {'overall': 'unknown', 'message': 'No health data yet'}
        except Exception:
            return {'overall': 'unknown'}


# ==================== CHANNEL LAYER HELPERS ====================

async def broadcast_kpi_update(data: dict):
    """Broadcast KPI update to all connected admin dashboards."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send('admin_dashboard', {
            'type': 'kpi_update',
            'data': data,
            'timestamp': timezone.now().isoformat(),
        })


async def broadcast_fraud_alert(data: dict, severity: str = 'medium'):
    """Broadcast fraud alert to all connected fraud monitors."""
    from channels.layers import get_channel_layer
    channel_layer = get_channel_layer()
    if channel_layer:
        await channel_layer.group_send('admin_fraud_alerts', {
            'type': 'fraud_event',
            'event_type': 'fraud_detected',
            'data': data,
            'severity': severity,
        })