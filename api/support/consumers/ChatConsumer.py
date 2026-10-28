# api/support/consumers/ChatConsumer.py  — WORLD #1 COMPLETE
"""
WebSocket consumer for real-time user↔agent live chat.
Requires: django-channels, channels-redis

settings.py:
    INSTALLED_APPS += ["channels"]
    ASGI_APPLICATION = "yourproject.asgi.application"
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("127.0.0.1", 6379)]}}}
"""
import json
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async

    class ChatConsumer(AsyncWebsocketConsumer):
        """Real-time live chat WebSocket consumer."""

        async def connect(self):
            self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
            self.room_group  = f"chat_{self.session_id}"
            self.user        = self.scope.get("user")

            # Verify session access
            valid = await self._verify_session()
            if not valid:
                await self.close(code=4003)
                return

            # Join room
            await self.channel_layer.group_add(self.room_group, self.channel_name)
            await self.accept()
            logger.info(f"Chat WS connected: {self.session_id} by {self.user}")

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
            logger.info(f"Chat WS disconnected: {self.session_id}")

        async def receive(self, text_data):
            data    = json.loads(text_data)
            msg_type= data.get("type", "chat_message")

            if msg_type == "chat_message":
                content  = data.get("content", "").strip()
                if not content:
                    return

                # Save message to DB
                message = await self._save_message(content)
                if not message:
                    return

                # Broadcast to room
                await self.channel_layer.group_send(self.room_group, {
                    "type":       "chat_message",
                    "message_id": message["id"],
                    "content":    content,
                    "sender":     self.user.username if self.user else "User",
                    "is_agent":   self.user.is_staff if self.user else False,
                    "timestamp":  timezone.now().isoformat(),
                })

            elif msg_type == "typing":
                await self.channel_layer.group_send(self.room_group, {
                    "type":    "typing_indicator",
                    "user":    self.user.username if self.user else "User",
                    "is_typing": data.get("is_typing", True),
                })

        async def chat_message(self, event):
            await self.send(text_data=json.dumps({
                "type":      "chat_message",
                "id":        event.get("message_id"),
                "content":   event["content"],
                "sender":    event["sender"],
                "is_agent":  event.get("is_agent", False),
                "timestamp": event.get("timestamp"),
            }))

        async def typing_indicator(self, event):
            await self.send(text_data=json.dumps({
                "type":      "typing",
                "user":      event["user"],
                "is_typing": event["is_typing"],
            }))

        async def session_ended(self, event):
            await self.send(text_data=json.dumps({"type": "session_ended", "reason": event.get("reason", "")}))
            await self.close()

        @database_sync_to_async
        def _verify_session(self) -> bool:
            try:
                from api.support.models import LiveChatSession
                import uuid as _uuid
                session = LiveChatSession.objects.get(session_id=_uuid.UUID(self.session_id))
                if not self.user or not self.user.is_authenticated:
                    return False
                return session.user == self.user or (self.user.is_staff and session.status != "ended")
            except Exception:
                return False

        @database_sync_to_async
        def _save_message(self, content: str) -> dict | None:
            try:
                from api.support.models import LiveChatSession, LiveChatMessage
                import uuid as _uuid
                session = LiveChatSession.objects.get(session_id=_uuid.UUID(self.session_id))
                msg = LiveChatMessage.objects.create(
                    session  = session,
                    sender   = self.user,
                    content  = content,
                    is_agent = self.user.is_staff if self.user else False,
                )
                return {"id": msg.id}
            except Exception as e:
                logger.error(f"Save chat message failed: {e}")
                return None

except ImportError:
    logger.warning("django-channels not installed. Real-time chat not available.")
    class ChatConsumer:
        pass