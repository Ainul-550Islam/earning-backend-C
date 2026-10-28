# api/support/consumers/AgentConsumer.py  — WORLD #1 COMPLETE
"""
Agent dashboard WebSocket consumer.
Pushes: new ticket alerts, queue updates, agent status changes.
"""
import json
import logging
logger = logging.getLogger(__name__)

try:
    from channels.generic.websocket import AsyncWebsocketConsumer
    from channels.db import database_sync_to_async

    class AgentConsumer(AsyncWebsocketConsumer):
        """Agent dashboard real-time WebSocket."""

        AGENT_GROUP = "agent_dashboard"

        async def connect(self):
            self.user = self.scope.get("user")
            if not self.user or not self.user.is_authenticated or not self.user.is_staff:
                await self.close(code=4003)
                return
            await self.channel_layer.group_add(self.AGENT_GROUP, self.channel_name)
            # Personal channel for direct notifications
            self.personal_group = f"agent_{self.user.id}"
            await self.channel_layer.group_add(self.personal_group, self.channel_name)
            await self.accept()
            # Send current dashboard stats
            stats = await self._get_stats()
            await self.send(text_data=json.dumps({"type": "dashboard_stats", **stats}))

        async def disconnect(self, close_code):
            await self.channel_layer.group_discard(self.AGENT_GROUP, self.channel_name)
            await self.channel_layer.group_discard(self.personal_group, self.channel_name)

        async def receive(self, text_data):
            data = json.loads(text_data)
            msg_type = data.get("type")
            if msg_type == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            elif msg_type == "request_stats":
                stats = await self._get_stats()
                await self.send(text_data=json.dumps({"type": "dashboard_stats", **stats}))

        async def new_ticket_alert(self, event):
            await self.send(text_data=json.dumps({"type": "new_ticket", **event.get("ticket", {})}))

        async def ticket_update(self, event):
            await self.send(text_data=json.dumps({"type": "ticket_update", **event.get("data", {})}))

        async def queue_update(self, event):
            await self.send(text_data=json.dumps({"type": "queue_update", **event.get("data", {})}))

        async def sla_breach_alert(self, event):
            await self.send(text_data=json.dumps({"type": "sla_breach", **event.get("data", {})}))

        async def dashboard_stats(self, event):
            await self.send(text_data=json.dumps({"type": "dashboard_stats", **event.get("stats", {})}))

        @database_sync_to_async
        def _get_stats(self) -> dict:
            try:
                from api.support.services import ticket_service
                return ticket_service.get_stats()
            except Exception:
                return {}

except ImportError:
    class AgentConsumer:
        pass