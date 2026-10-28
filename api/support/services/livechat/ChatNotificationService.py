# api/support/services/livechat/ChatNotificationService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

class ChatNotificationService:
    def push_new_message(self, session, message) -> None:
        """Push new chat message via WebSocket."""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            cl = get_channel_layer()
            if cl:
                async_to_sync(cl.group_send)(
                    f"chat_{session.session_id}",
                    {"type":"chat_message","content":message.content,"is_agent":message.is_agent,"created_at":message.created_at.isoformat()}
                )
        except Exception as e:
            logger.debug(f"Push new message failed: {e}")

    def push_typing(self, session_id: str, user: str, is_typing: bool) -> None:
        """Broadcast typing indicator."""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            cl = get_channel_layer()
            if cl:
                async_to_sync(cl.group_send)(
                    f"chat_{session_id}",
                    {"type":"typing_indicator","user":user,"is_typing":is_typing}
                )
        except Exception as e:
            logger.debug(f"Push typing failed: {e}")

chat_notification_service = ChatNotificationService()