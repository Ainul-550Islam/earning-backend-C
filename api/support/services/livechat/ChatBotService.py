# api/support/services/livechat/ChatBotService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

GREETING = (
    "Hi! I am the support bot. How can I help you today?\n"
    "1. Payment issue\n"
    "2. Withdrawal issue\n"
    "3. Account problem\n"
    "4. Talk to agent"
)


class ChatBotService:
    """AI-assisted chatbot for first-line support."""

    def handle(self, session, content: str):
        """Return bot response string, or None to hand off to human agent."""
        text = content.lower().strip()

        if any(kw in text for kw in ['hi', 'hello', 'hey', 'help', 'start']):
            return GREETING

        if text in ('1', 'payment', 'pay'):
            articles = self._suggest_kb('payment issue')
            return "For payment issues:\n" + articles + "\n\nType 'agent' to talk to a human."

        if text in ('2', 'withdrawal', 'withdraw'):
            articles = self._suggest_kb('withdrawal')
            return "For withdrawal issues:\n" + articles + "\n\nType 'agent' to talk to a human."

        if text in ('3', 'account'):
            return "For account issues, please describe the problem.\n\nType 'agent' to talk to a human."

        if text in ('4', 'agent', 'human', 'support'):
            return None  # Hand off to human

        articles = self._suggest_kb(content)
        if articles:
            return "I found these articles:\n" + articles + "\n\nType 'agent' for human support."

        return "I'm not sure I understand. Type 'agent' to connect with a human agent."

    def _suggest_kb(self, query: str) -> str:
        try:
            from api.support.services.knowledge_base.KBSearchService import kb_search_service
            results = kb_search_service.search(query, limit=3)
            if results:
                return "\n".join("- " + r['title'] for r in results)
        except Exception:
            pass
        return ''


chat_bot_service = ChatBotService()