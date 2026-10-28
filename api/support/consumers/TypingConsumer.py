# api/support/consumers/TypingConsumer.py  — WORLD #1 COMPLETE
"""
Typing indicator WebSocket consumer.
Broadcasts typing status between user and agent.
"""
import json
import logging
logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    class TypingConsumer(AsyncWebsocketConsumer):
        async def connect(self):
            self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
            self.room_group  = f"typing_{self.session_id}"
            self.user        = self.scope.get("user")
            if not self.user or not self.user.is_authenticated:
                await self.close(code=4003)
                return
            await self.channel_layer.group_add(self.room_group, self.channel_name)
            await self.accept()

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(self.room_group, self.channel_name)

        async def receive(self, text_data):
            data = json.loads(text_data)
            if data.get("type") == "typing":
                await self.channel_layer.group_send(self.room_group, {
                    "type":      "typing_event",
                    "user":      self.user.username,
                    "is_agent":  self.user.is_staff,
                    "is_typing": data.get("is_typing", True),
                })

        async def typing_event(self, event):
            # Don"t echo back to sender
            if event.get("user") != self.user.username:
                await self.send(text_data=json.dumps({
                    "type":      "typing",
                    "user":      event["user"],
                    "is_agent":  event.get("is_agent", False),
                    "is_typing": event["is_typing"],
                }))

except ImportError:
    class TypingConsumer:
        pass