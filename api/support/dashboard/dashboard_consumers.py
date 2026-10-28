"""
api/support/dashboard/dashboard_consumers.py
FILE 15/70 — Dashboard WebSocket Consumer

Django Channels WebSocket — real-time dashboard।
Agent dashboard-এ সব data live দেখাবে।

Connection: ws://domain/ws/support/dashboard/
Auth: JWT token via query param

pip install channels channels-redis
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {'hosts': [('127.0.0.1', 6379)]},
    }
}
"""
import json
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async

    class SupportDashboardConsumer(AsyncWebsocketConsumer):
        """
        Agent dashboard WebSocket consumer।
        Push করবে:
        - ticket_created, ticket_updated, ticket_resolved
        - agent_status_changed
        - sla_warning, sla_breach
        - chat_started, chat_ended
        - dashboard_refresh (full data every 30s)
        """

        DASHBOARD_GROUP = 'support_dashboard'
        REFRESH_INTERVAL= 30  # seconds

        async def connect(self):
            """WebSocket connection establish করো"""
            self.user = self.scope.get('user')

            # Authentication check
            if not self.user or not self.user.is_authenticated:
                await self.close(code=4001)
                return

            # Permission check — only agents/staff
            is_authorized = await self._is_authorized()
            if not is_authorized:
                await self.close(code=4003)
                return

            # Join dashboard group
            await self.channel_layer.group_add(
                self.DASHBOARD_GROUP,
                self.channel_name,
            )

            # Personal group (for direct messages)
            self.personal_group = f'agent_{self.user.id}'
            await self.channel_layer.group_add(
                self.personal_group,
                self.channel_name,
            )

            await self.accept()

            # Send initial data
            await self.send_dashboard_data()

            logger.info(f'Dashboard WS connected: {self.user.username}')

        async def disconnect(self, close_code):
            """WebSocket disconnect করো"""
            await self.channel_layer.group_discard(self.DASHBOARD_GROUP, self.channel_name)
            if hasattr(self, 'personal_group'):
                await self.channel_layer.group_discard(self.personal_group, self.channel_name)
            logger.info(f'Dashboard WS disconnected: {getattr(self.user, "username", "unknown")}')

        async def receive(self, text_data):
            """Client থেকে message পাও"""
            try:
                data = json.loads(text_data)
                msg_type = data.get('type', '')

                if msg_type == 'ping':
                    await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': timezone.now().isoformat()}))

                elif msg_type == 'refresh':
                    await self.send_dashboard_data()

                elif msg_type == 'subscribe_ticket':
                    ticket_id = data.get('ticket_id')
                    if ticket_id:
                        await self.channel_layer.group_add(f'ticket_{ticket_id}', self.channel_name)
                        await self.send(text_data=json.dumps({'type': 'subscribed', 'ticket_id': ticket_id}))

                elif msg_type == 'agent_status':
                    new_status = data.get('status')
                    if new_status:
                        await self._update_agent_status(new_status)

            except json.JSONDecodeError:
                pass
            except Exception as e:
                logger.error(f'Dashboard WS receive error: {e}')

        # ──────────────────────────────────────────
        # PUSH METHODS (called from Celery/signals)
        # ──────────────────────────────────────────
        async def send_dashboard_data(self):
            """Full dashboard data push করো"""
            from api.support.dashboard.realtime_dashboard import realtime_dashboard
            data = await database_sync_to_async(realtime_dashboard.get_full_dashboard)()
            await self.send(text_data=json.dumps({
                'type': 'dashboard_data',
                'data': data,
            }, default=str))

        async def ticket_created(self, event):
            """New ticket notification"""
            await self.send(text_data=json.dumps({
                'type':   'ticket_created',
                'ticket': event.get('ticket', {}),
                'sound':  'new_ticket',
            }))

        async def ticket_updated(self, event):
            """Ticket update notification"""
            await self.send(text_data=json.dumps({
                'type':   'ticket_updated',
                'ticket': event.get('ticket', {}),
            }))

        async def ticket_resolved(self, event):
            """Ticket resolved notification"""
            await self.send(text_data=json.dumps({
                'type':      'ticket_resolved',
                'ticket_id': event.get('ticket_id'),
                'sound':     'resolved',
            }))

        async def sla_warning(self, event):
            """SLA warning push"""
            await self.send(text_data=json.dumps({
                'type':      'sla_warning',
                'ticket_id': event.get('ticket_id'),
                'message':   event.get('message', 'SLA approaching deadline'),
                'sound':     'warning',
            }))

        async def sla_breach(self, event):
            """SLA breach push — urgent alert"""
            await self.send(text_data=json.dumps({
                'type':       'sla_breach',
                'ticket_id':  event.get('ticket_id'),
                'breach_type':event.get('breach_type'),
                'message':    event.get('message', 'SLA BREACHED'),
                'sound':      'alarm',
            }))

        async def agent_status_changed(self, event):
            """Agent status change notification"""
            await self.send(text_data=json.dumps({
                'type':     'agent_status',
                'username': event.get('username'),
                'status':   event.get('status'),
            }))

        async def chat_started(self, event):
            """New chat session notification"""
            await self.send(text_data=json.dumps({
                'type':       'chat_started',
                'session_id': event.get('session_id'),
                'user':       event.get('user'),
                'sound':      'chat_request',
            }))

        async def chat_ended(self, event):
            """Chat session ended"""
            await self.send(text_data=json.dumps({
                'type':       'chat_ended',
                'session_id': event.get('session_id'),
            }))

        async def new_message(self, event):
            """New ticket message notification"""
            await self.send(text_data=json.dumps({
                'type':      'new_message',
                'ticket_id': event.get('ticket_id'),
                'message':   event.get('message', ''),
                'from_user': event.get('from_user'),
                'sound':     'message',
            }))

        async def queue_update(self, event):
            """Queue position update"""
            await self.send(text_data=json.dumps({
                'type':         'queue_update',
                'queue_length': event.get('queue_length', 0),
                'data':         event.get('data', []),
            }))

        # ──────────────────────────────────────────
        # DB HELPERS
        # ──────────────────────────────────────────
        @database_sync_to_async
        def _is_authorized(self) -> bool:
            if self.user.is_staff:
                return True
            try:
                from api.support.models import SupportAgent
                return SupportAgent.objects.filter(user=self.user, is_active=True).exists()
            except Exception:
                return False

        @database_sync_to_async
        def _update_agent_status(self, status: str) -> None:
            try:
                from api.support.services.agent.AgentAvailabilityService import availability_service
                availability_service.set_status(self.user, status)
            except Exception as e:
                logger.warning(f'Agent status update failed: {e}')


    # ──────────────────────────────────────────
    # HELPER: PUSH FROM ANYWHERE
    # ──────────────────────────────────────────
    def push_dashboard_event(event_type: str, data: dict) -> None:
        """
        Signal/Celery থেকে dashboard-এ event push করো।
        Usage: push_dashboard_event('ticket_created', {'ticket': {...}})
        """
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            layer = get_channel_layer()
            async_to_sync(layer.group_send)(
                SupportDashboardConsumer.DASHBOARD_GROUP,
                {'type': event_type.replace('_', '.'), **data}
            )
        except Exception as e:
            logger.warning(f'Dashboard push failed [{event_type}]: {e}')


    def push_to_agent(agent_id: str, event_type: str, data: dict) -> None:
        """Specific agent-কে event push করো"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            layer = get_channel_layer()
            async_to_sync(layer.group_send)(
                f'agent_{agent_id}',
                {'type': event_type.replace('_', '.'), **data}
            )
        except Exception as e:
            logger.warning(f'Agent push failed [{event_type}]: {e}')


    # ──────────────────────────────────────────
    # CELERY TASK: Periodic Dashboard Refresh
    # ──────────────────────────────────────────
    def broadcast_dashboard_refresh() -> None:
        """
        Celery beat-এ প্রতি 30 সেকেন্ডে call করো।
        সব connected agents-এর dashboard refresh হবে।
        """
        try:
            from api.support.dashboard.realtime_dashboard import realtime_dashboard
            data = realtime_dashboard.get_full_dashboard()
            push_dashboard_event('dashboard_data', {'data': data})
        except Exception as e:
            logger.warning(f'Dashboard broadcast failed: {e}')


except ImportError:
    logger.warning('Django Channels not installed. Real-time dashboard disabled. pip install channels channels-redis')

    class SupportDashboardConsumer:
        pass

    def push_dashboard_event(event_type, data):
        pass

    def push_to_agent(agent_id, event_type, data):
        pass

    def broadcast_dashboard_refresh():
        pass