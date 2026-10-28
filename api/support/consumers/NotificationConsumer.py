# api/support/consumers/NotificationConsumer.py  — WORLD #1 COMPLETE
"""
User notification WebSocket consumer.
Pushes ticket status updates to logged-in users.
"""
import json
import logging
logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer

    class NotificationConsumer(AsyncWebsocketConsumer):
        """Per-user notification WebSocket."""

        async def connect(self):
            self.user = self.scope.get("user")
            if not self.user or not self.user.is_authenticated:
                await self.close(code=4003)
                return
            self.user_group = f"user_notifications_{self.user.id}"
            await self.channel_layer.group_add(self.user_group, self.channel_name)
            await self.accept()

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

        async def ticket_update(self, event):
            await self.send(text_data=json.dumps({
                "type":      "ticket_update",
                "ticket_id": event.get("ticket_id"),
                "status":    event.get("status"),
                "message":   event.get("message"),
            }))

        async def new_message(self, event):
            await self.send(text_data=json.dumps({
                "type":      "new_message",
                "ticket_id": event.get("ticket_id"),
                "content":   event.get("content", "")[:100],
            }))

        async def announcement(self, event):
            await self.send(text_data=json.dumps({
                "type":    "announcement",
                "title":   event.get("title"),
                "content": event.get("content"),
                "ann_type":event.get("ann_type", "info"),
            }))

        async def receive(self, text_data):
            data = json.loads(text_data)
            if data.get("type") == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))

except ImportError:
    class NotificationConsumer:
        pass