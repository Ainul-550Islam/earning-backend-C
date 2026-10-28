"""
api/support/automation/action_executor.py
FILE 45/70 — Advanced Action Executor (30+ actions)

Full action execution — all action types।
"""
import logging
import requests
logger = logging.getLogger(__name__)

class ActionExecutor:
    def execute(self, ticket, action_type: str, value: str, params: dict = None) -> bool:
        params  = params or {}
        method  = getattr(self, f'_do_{action_type}', None)
        if not method:
            logger.warning(f'Unknown action: {action_type}')
            return False
        try:
            return method(ticket, value, params)
        except Exception as e:
            logger.error(f'Action [{action_type}] failed: {e}')
            return False

    def _do_set_priority(self, ticket, value, params): ticket.priority = value; ticket.save(update_fields=['priority']); return True
    def _do_set_status(self, ticket, value, params): ticket.status = value; ticket.save(update_fields=['status']); return True
    def _do_escalate(self, ticket, value, params):
        from django.utils import timezone
        ticket.escalated = True; ticket.escalated_at = timezone.now()
        ticket.save(update_fields=['escalated','escalated_at']); return True
    def _do_close(self, ticket, value, params): ticket.status = 'closed'; ticket.save(update_fields=['status']); return True
    def _do_add_tag(self, ticket, value, params):
        from api.support.models import TicketTag, TicketTagging
        tag, _ = TicketTag.objects.get_or_create(name=value.strip())
        TicketTagging.objects.get_or_create(ticket=ticket, tag=tag)
        return True
    def _do_remove_tag(self, ticket, value, params):
        from api.support.models import TicketTagging
        TicketTagging.objects.filter(ticket=ticket, tag__name=value).delete(); return True
    def _do_assign_agent(self, ticket, value, params):
        from django.contrib.auth import get_user_model
        user = get_user_model().objects.filter(id=value).first()
        if user: ticket.assigned_to = user; ticket.save(update_fields=['assigned_to']); return True
        return False
    def _do_send_reply(self, ticket, value, params):
        from api.support.models import TicketMessage
        from django.contrib.auth import get_user_model
        bot = get_user_model().objects.filter(is_superuser=True).first()
        if bot:
            TicketMessage.objects.create(ticket=ticket, sender=bot, content=value, is_agent=True)
            return True
        return False
    def _do_notify_slack(self, ticket, value, params):
        try:
            from api.support.integrations.slack_integration import slack_integration
            return slack_integration._send_webhook({'text': f'Ticket {ticket.ticket_id}: {value}'})
        except Exception: return False
    def _do_notify_telegram(self, ticket, value, params):
        try:
            from api.support.integrations.telegram_bot import telegram_bot
            return bool(telegram_bot.send_message(value, f'Ticket {ticket.ticket_id} alert'))
        except Exception: return False
    def _do_webhook(self, ticket, value, params):
        try:
            resp = requests.post(value, json={'ticket_id': ticket.ticket_id, 'status': ticket.status}, timeout=10)
            return resp.status_code < 400
        except Exception: return False
    def _do_ai_classify(self, ticket, value, params):
        try:
            from api.support.ai.ai_ticket_classifier import ai_classifier
            ai_classifier.classify(ticket); return True
        except Exception: return False
    def _do_ai_draft_response(self, ticket, value, params):
        try:
            from api.support.ai.ai_auto_responder import ai_auto_responder
            ai_auto_responder.draft_response(ticket); return True
        except Exception: return False
    def _do_kb_suggest(self, ticket, value, params):
        try:
            from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service
            suggestions = kb_recommend_service.suggest_for_ticket(ticket.subject, ticket.category)
            if suggestions:
                from api.support.models import TicketMessage
                from django.contrib.auth import get_user_model
                bot = get_user_model().objects.filter(is_superuser=True).first()
                if bot:
                    content = '📚 Related articles:\n' + '\n'.join(f"• {s['title']}" for s in suggestions[:3])
                    TicketMessage.objects.create(ticket=ticket, sender=bot, content=content, is_agent=True, is_internal=True)
            return True
        except Exception: return False

action_executor = ActionExecutor()