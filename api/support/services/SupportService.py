# api/support/services/SupportService.py  — WORLD #1
"""Main SupportService — orchestrates all sub-services."""
import logging
logger = logging.getLogger(__name__)

class SupportService:
    """Top-level service orchestrator for support system."""

    def get_ticket_stats(self) -> dict:
        from api.support.services import ticket_service
        return ticket_service.get_stats()

    def create_ticket(self, user, data: dict):
        from api.support.services import ticket_service
        return ticket_service.create(user, data)

    def get_portal_home(self, user) -> dict:
        from api.support.models import SupportTicket, SupportSettings
        from api.support.services.knowledge_base.KBRecommendService import kb_recommend_service
        from django.utils import timezone
        tickets  = SupportTicket.objects.filter(user=user)
        open_ct  = tickets.filter(status__in=['open','in_progress','waiting_user']).count()
        waiting  = tickets.filter(status='waiting_user').count()
        settings_obj, _ = SupportSettings.objects.get_or_create(id=1)
        return {
            'open_tickets':    open_ct,
            'waiting_reply':   waiting,
            'support_online':  settings_obj.is_support_online,
            'chat_enabled':    settings_obj.chat_widget_enabled,
        }

support_service = SupportService()