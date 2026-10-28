# api/support/services/ticket/TicketAssignmentService.py  — WORLD #1
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class TicketAssignmentService:
    def assign(self, ticket, agent_id: int, assigned_by=None, reason: str = '') -> dict:
        from api.support.models import SupportAgent, TicketAssignment
        try:
            agent = SupportAgent.objects.get(id=agent_id, is_active=True)
        except SupportAgent.DoesNotExist:
            return {'error': f'Agent {agent_id} not found or inactive.'}
        old_agent = ticket.assigned_to
        ticket.assigned_to = agent.user
        ticket.save(update_fields=['assigned_to'])
        # Log assignment
        TicketAssignment.objects.create(
            ticket=ticket, agent=agent.user, assigned_by=assigned_by, reason=reason,
        )
        if old_agent:
            TicketAssignment.objects.filter(ticket=ticket, agent=old_agent, unassigned_at__isnull=True).update(unassigned_at=timezone.now())
        # Notify agent
        try:
            from api.support.notifications.email_notifier import email_notifier
            email_notifier.agent_assignment(ticket, agent.user)
        except Exception as e:
            logger.warning(f"Assignment notification failed: {e}")
        return {'success': True, 'assigned_to': agent.user.username}

    def reassign(self, ticket, new_agent_id: int, by=None, reason: str = '') -> dict:
        return self.assign(ticket, new_agent_id, assigned_by=by, reason=reason)

    def unassign(self, ticket, by=None) -> dict:
        from api.support.models import TicketAssignment
        if ticket.assigned_to:
            TicketAssignment.objects.filter(ticket=ticket, agent=ticket.assigned_to, unassigned_at__isnull=True).update(unassigned_at=timezone.now())
        ticket.assigned_to = None
        ticket.save(update_fields=['assigned_to'])
        return {'success': True}

    def auto_assign(self, ticket) -> dict:
        from api.support.services import ticket_service
        ticket_service._auto_assign(ticket)
        return {'assigned_to': ticket.assigned_to.username if ticket.assigned_to else None}

ticket_assignment_service = TicketAssignmentService()