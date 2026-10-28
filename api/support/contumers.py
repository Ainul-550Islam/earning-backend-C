# api/support/contumers.py  (WebSocket consumers)
import json
import logging

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async

    class TicketChatConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            self.session_id = self.scope['url_route']['kwargs']['session_id']
            self.group_name = f'chat_{self.session_id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send(text_data=json.dumps({'type':'connected','session_id':self.session_id}))

        async def disconnect(self, code):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        async def receive(self, text_data):
            try:
                data = json.loads(text_data)
                if data.get('type') == 'message':
                    await self.handle_message(data)
                elif data.get('type') == 'typing':
                    await self.handle_typing(data)
            except Exception as e:
                logger.error(f'ChatConsumer.receive: {e}')

        async def handle_message(self, data):
            content = data.get('content', '').strip()
            if not content:
                return
            user = self.scope['user']
            msg  = await self.save_message(content, user)
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat_message',
                'content': content,
                'is_agent': user.is_staff,
                'sender': user.username,
            })

        async def handle_typing(self, data):
            user = self.scope['user']
            await self.channel_layer.group_send(self.group_name, {
                'type': 'typing_indicator',
                'user': user.username,
                'is_typing': data.get('is_typing', True),
            })

        async def chat_message(self, event):
            await self.send(text_data=json.dumps({'type': 'message', **event}))

        async def typing_indicator(self, event):
            await self.send(text_data=json.dumps({'type': 'typing', **event}))

        @database_sync_to_async
        def save_message(self, content, user):
            try:
                from api.support.models import ChatSession, ChatMessage
                session = ChatSession.objects.get(session_id=self.session_id)
                return ChatMessage.objects.create(session=session, sender=user, content=content, is_agent=user.is_staff)
            except Exception:
                return None


    class AgentDashboardConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            user = self.scope['user']
            if not user.is_authenticated or not user.is_staff:
                await self.close()
                return
            self.group_name = 'agent_dashboard'
            self.user_group = f'agent_{user.id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.channel_layer.group_add(self.user_group, self.channel_name)
            await self.accept()

        async def disconnect(self, code):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

        async def receive(self, text_data):
            data = json.loads(text_data)
            if data.get('type') == 'heartbeat':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        async def new_ticket(self, event):
            await self.send(text_data=json.dumps({'type': 'new_ticket', **event}))

        async def sla_breach(self, event):
            await self.send(text_data=json.dumps({'type': 'sla_breach', **event}))

        async def dashboard_refresh(self, event):
            await self.send(text_data=json.dumps({'type': 'refresh'}))


    class SupportNotificationConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            user = self.scope['user']
            if not user.is_authenticated:
                await self.close()
                return
            self.group_name = f'user_support_{user.id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()

        async def disconnect(self, code):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

        async def ticket_update(self, event):
            await self.send(text_data=json.dumps({'type': 'ticket_update', **event}))

        async def support_notification(self, event):
            await self.send(text_data=json.dumps({'type': 'notification', **event}))

except ImportError:
    logger.warning('channels not installed - WebSocket consumers disabled')
    class TicketChatConsumer: pass
    class AgentDashboardConsumer: pass
    class SupportNotificationConsumer: pass