# api/support/services/ticket/TicketMergeService.py  — WORLD #1
import logging
logger = logging.getLogger(__name__)

class TicketMergeService:
    def merge(self, source_ticket, target_id, merged_by=None, reason: str = '') -> dict:
        from api.support.models import SupportTicket, TicketMessage, TicketMerge
        try:
            if str(target_id).startswith('TKT'):
                target = SupportTicket.objects.get(ticket_id=target_id)
            else:
                target = SupportTicket.objects.get(id=target_id)
        except SupportTicket.DoesNotExist:
            return {'error': f'Target ticket {target_id} not found.'}
        if source_ticket.id == target.id:
            return {'error': 'Cannot merge ticket with itself.'}
        # Move all messages to primary
        TicketMessage.objects.filter(ticket=source_ticket).update(ticket=target)
        # Log merge
        TicketMerge.objects.create(primary_ticket=target, merged_ticket=source_ticket, merged_by=merged_by, reason=reason)
        # Close merged ticket
        source_ticket.status = 'closed'
        from django.utils import timezone
        source_ticket.resolved_at = timezone.now()
        source_ticket.save(update_fields=['status','resolved_at'])
        # Add note to primary
        TicketMessage.objects.create(ticket=target, is_agent=True, is_internal=True,
            content=f'Merged from #{source_ticket.ticket_id}. Reason: {reason}',
            sender=merged_by)
        return {'success': True, 'primary': target.ticket_id, 'merged': source_ticket.ticket_id}

ticket_merge_service = TicketMergeService()