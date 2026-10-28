# api/support/services/livechat/ChatTranscriptService.py  — WORLD #1
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)


class ChatTranscriptService:
    """Generate and email chat transcripts."""

    def generate(self, session) -> str:
        session_short = str(session.session_id)[:8]
        agent_name = session.agent.username if session.agent else 'Bot'
        lines = [
            "Chat Transcript - Session " + session_short,
            "User: " + session.user.username,
            "Agent: " + agent_name,
            "Started: " + str(session.started_at),
            "Ended: " + str(session.ended_at or 'ongoing'),
            "-" * 50,
        ]
        for msg in session.messages.all().order_by('created_at'):
            if msg.is_agent:
                prefix = "[Agent]"
            else:
                prefix = "[" + session.user.username + "]"
            time_str = msg.created_at.strftime('%H:%M')
            lines.append(time_str + " " + prefix + ": " + msg.content)
        return "\n".join(lines)

    def save_transcript(self, session) -> object:
        from api.support.models import ChatTranscript
        text = self.generate(session)
        html = "<pre>" + text + "</pre>"
        obj, _ = ChatTranscript.objects.update_or_create(
            session=session,
            defaults={'content_text': text, 'content_html': html},
        )
        return obj

    def email_transcript(self, session) -> bool:
        obj = self.save_transcript(session)
        try:
            from api.support.services import notification_service
            notification_service._send_email(
                to=session.user.email,
                subject="Your chat transcript - " + str(session.session_id)[:8],
                body=obj.content_text,
            )
            obj.emailed_at = timezone.now()
            obj.email_sent_to = session.user.email
            obj.save(update_fields=['emailed_at', 'email_sent_to'])
            return True
        except Exception as e:
            logger.error("Transcript email failed: %s", e)
            return False


chat_transcript_service = ChatTranscriptService()