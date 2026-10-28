# api/support/services/ticket/TicketEscalationService.py  — WORLD #1
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class TicketEscalationService:
    def escalate(self, ticket, reason: str = 'SLA breach', by=None) -> dict:
        if ticket.escalated:
            return {'already_escalated': True}
        ticket.escalated    = True
        ticket.escalated_at = timezone.now()
        if ticket.priority != 'urgent':
            ticket.priority = 'high'
        ticket.save(update_fields=['escalated','escalated_at','priority'])
        # Notify supervisors
        try:
            from api.support.notifications.escalation_notifier import escalation_notifier
            escalation_notifier.notify_ticket_escalated(ticket, reason=reason)
        except Exception as e:
            logger.warning(f"Escalation notification failed: {e}")
        return {'success': True, 'ticket_id': ticket.ticket_id, 'reason': reason}

    def auto_escalate_sla_breaches(self) -> dict:
        from api.support.models import SupportTicket
        tickets = SupportTicket.objects.filter(status__in=['open','in_progress','waiting_user'],escalated=False,sla__first_response_breached=True)
        count = 0
        for ticket in tickets[:50]:
            result = self.escalate(ticket, reason='SLA first_response breach')
            if result.get('success'):
                count += 1
        return {'escalated': count}

ticket_escalation_service = TicketEscalationService()