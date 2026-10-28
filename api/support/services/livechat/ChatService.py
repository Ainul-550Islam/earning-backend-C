# api/support/services/livechat/ChatService.py  — WORLD #1 COMPLETE
import logging, uuid as uuid_module
from django.utils import timezone
logger = logging.getLogger(__name__)

class ChatService:
    def start_session(self, user, department=None):
        from api.support.services import livechat_service
        return livechat_service.start_session(user)

    def send_message(self, session_id: str, sender, content: str, is_agent: bool = False, msg_type: str = "text"):
        from api.support.models import LiveChatSession, LiveChatMessage
        try:
            session = LiveChatSession.objects.get(session_id=uuid_module.UUID(str(session_id)))
        except Exception:
            try:
                session = LiveChatSession.objects.get(session_id=session_id)
            except Exception:
                raise ValueError(f"Chat session {session_id} not found.")
        if session.status == "ended":
            raise ValueError("Chat session has ended.")
        return LiveChatMessage.objects.create(session=session, sender=sender, content=content, is_agent=is_agent, msg_type=msg_type)

    def get_messages(self, session_id: str) -> list:
        from api.support.models import LiveChatSession, LiveChatMessage
        try:
            session = LiveChatSession.objects.get(session_id=uuid_module.UUID(str(session_id)))
        except Exception:
            return []
        return [{"id":m.id,"content":m.content,"is_agent":m.is_agent,"sender":m.sender.username if m.sender else "","created_at":m.created_at.isoformat()} for m in LiveChatMessage.objects.filter(session=session).order_by("created_at")]

    def end_session(self, session_id: str) -> bool:
        from api.support.models import LiveChatSession
        return LiveChatSession.objects.filter(session_id=session_id).update(status="ended", ended_at=timezone.now()) > 0

chat_service = ChatService()