# api/support/services/ticket/TicketSearchService.py  — WORLD #1
import logging
from django.db.models import Q
logger = logging.getLogger(__name__)

class TicketSearchService:
    def search(self, query: str, user=None, is_agent: bool = False, limit: int = 20) -> list:
        from api.support.models import SupportTicket
        from api.support.serializers import SupportTicketListSerializer
        if not query or len(query.strip()) < 2:
            return []
        q = query.strip()
        qs = SupportTicket.objects.filter(
            Q(ticket_id__icontains=q) | Q(subject__icontains=q) |
            Q(description__icontains=q) | Q(user__username__icontains=q)
        )
        if not is_agent and user:
            qs = qs.filter(user=user)
        return list(SupportTicketListSerializer(qs[:limit], many=True).data)

ticket_search_service = TicketSearchService()