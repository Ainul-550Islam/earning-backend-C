# api/support/openai.py
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful support agent for a CPA/earning app.
Help users with: payment issues, offer completions, account problems, withdrawals.
Be concise, professional, empathetic. Max 150 words per response."""


def get_ai_response(ticket_description: str, category: str = '', context: dict = None) -> str:
    # 1. Try your ai_engine chatbot
    try:
        from api.support.integrations.project_specific.ai_engine_adapter import ai_engine_adapter
        resp = ai_engine_adapter.get_chatbot_response(ticket_description, context or {})
        if resp:
            return resp
    except Exception:
        pass

    # 2. Try Anthropic Claude
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=getattr(settings, 'ANTHROPIC_API_KEY', ''))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{'role': 'user', 'content': ticket_description}],
        )
        return msg.content[0].text if msg.content else ''
    except Exception as e:
        logger.debug(f'Claude API: {e}')

    # 3. Rule-based fallback
    return _fallback(category)


def _fallback(category: str) -> str:
    responses = {
        'payment':    'We received your payment issue. Our team investigates within 24 hours.',
        'withdrawal': 'Withdrawal query received. Processing takes 1-3 business days.',
        'coins':      'Checking your offer completion. Allow 24 hours for verification.',
        'kyc':        'KYC query received. Verification team reviews within 48 hours.',
        'fraud':      'Security issue reported. Our security team will investigate immediately.',
        'technical':  'Technical issue noted. Our team will investigate and respond shortly.',
    }
    return responses.get(category,
        'Thank you for contacting support. Our team will respond within 24 hours.')


def auto_respond_to_ticket(ticket) -> bool:
    try:
        from api.support.models import SupportSettings, TicketMessage
        from django.contrib.auth import get_user_model
        from django.utils import timezone
        obj, _ = SupportSettings.objects.get_or_create(id=1)
        if not obj.ai_auto_response_enabled:
            return False
        cats = obj.ai_auto_send_categories or []
        if cats and ticket.category not in cats:
            return False
        resp_text = get_ai_response(ticket.description, ticket.category)
        if not resp_text:
            return False
        bot = get_user_model().objects.filter(is_superuser=True).first()
        TicketMessage.objects.create(ticket=ticket, sender=bot, content=resp_text, is_agent=True)
        ticket.admin_response = resp_text
        ticket.admin_responded_at = timezone.now()
        ticket.status = 'in_progress'
        ticket.save(update_fields=['admin_response', 'admin_responded_at', 'status'])
        return True
    except Exception as e:
        logger.error(f'auto_respond_to_ticket: {e}')
        return False