# api/support/hooks.py
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class TicketHooks:
    @staticmethod
    def pre_create(data: dict, user) -> dict:
        from api.support.choices import CATEGORY_PRIORITY_MAP
        if not data.get('priority') and data.get('category'):
            data['priority'] = CATEGORY_PRIORITY_MAP.get(data['category'], 'medium')
        if not data.get('tenant') and hasattr(user, 'tenant'):
            data['tenant'] = user.tenant
        return data

    @staticmethod
    def post_create(ticket) -> None:
        try:
            from api.support.services import sla_service
            sla_service._setup_sla(ticket)
        except Exception as e:
            logger.debug(f'SLA setup: {e}')
        try:
            from api.support.services import ticket_service
            ticket_service._auto_assign(ticket)
        except Exception as e:
            logger.debug(f'Auto-assign: {e}')
        try:
            from api.support.integrations.project_specific.messaging_bridge import messaging_bridge
            messaging_bridge.sync_ticket_to_thread(ticket)
        except Exception:
            pass
        try:
            from api.support.integrations.project_specific.ai_engine_adapter import ai_engine_adapter
            result = ai_engine_adapter.process_ticket_with_ai(ticket)
            if result.get('action') == 'mark_spam':
                ticket.status = 'spam'
                ticket.save(update_fields=['status'])
        except Exception:
            pass

    @staticmethod
    def post_resolve(ticket) -> None:
        try:
            from api.support.integrations.project_specific.gamification_bridge import gamification_bridge
            gamification_bridge.award_resolution_points(ticket)
        except Exception:
            pass


ticket_hooks = TicketHooks()