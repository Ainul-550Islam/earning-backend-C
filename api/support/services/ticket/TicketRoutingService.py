# api/support/services/ticket/TicketRoutingService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

KEYWORD_DEPARTMENT_MAP = {
    'payment':    ['payment','bkash','nagad','transaction','billing'],
    'withdrawal': ['withdraw','cashout','payout','redeem'],
    'kyc':        ['kyc','verification','nid','passport','document'],
    'fraud':      ['fraud','hack','scam','unauthorized','stolen'],
    'technical':  ['error','bug','crash','not working','broken'],
}

class TicketRoutingService:
    def route_by_content(self, ticket) -> str | None:
        """Auto-detect department from ticket content."""
        text = f"{ticket.subject or ''} {ticket.description or ''}".lower()
        for dept_slug, keywords in KEYWORD_DEPARTMENT_MAP.items():
            if any(kw in text for kw in keywords):
                return dept_slug
        return ticket.category

    def get_best_department(self, ticket):
        from api.support.models import Department
        slug = self.route_by_content(ticket)
        if slug:
            try:
                return Department.objects.get(slug=slug, is_active=True)
            except Department.DoesNotExist:
                pass
        return Department.objects.filter(is_active=True).first()

    def route(self, ticket) -> dict:
        dept = self.get_best_department(ticket)
        if dept:
            from api.support.services.agent.AgentService import workload_balancer
            agent = workload_balancer.get_best_agent()
            if agent:
                ticket.assigned_to = agent.user
                ticket.save(update_fields=['assigned_to'])
                return {'department': dept.name, 'agent': agent.user.username}
        return {'department': None, 'agent': None}

ticket_routing_service = TicketRoutingService()