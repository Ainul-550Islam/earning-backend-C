# api/offer_inventory/compliance_legal/dmca_handler.py
"""DMCA Takedown Request Handler."""
import logging
import uuid
from django.utils import timezone

logger = logging.getLogger(__name__)


class DMCAHandler:
    """Handle DMCA copyright takedown requests."""

    @staticmethod
    def submit_takedown(reporter_email: str, content_url: str,
                         description: str, original_url: str = '') -> dict:
        """Record a DMCA takedown request."""
        from api.offer_inventory.models import FeedbackTicket
        ticket_no = f'DMCA-{str(uuid.uuid4())[:6].upper()}'
        FeedbackTicket.objects.create(
            ticket_no=ticket_no,
            subject  =f'DMCA Takedown: {content_url[:100]}',
            message  =(
                f'Reporter: {reporter_email}\n'
                f'Infringing URL: {content_url}\n'
                f'Original URL: {original_url}\n'
                f'Description: {description}'
            ),
            priority ='high',
        )
        logger.info(f'DMCA submitted: {ticket_no} by {reporter_email}')
        return {'ticket_no': ticket_no, 'status': 'received', 'message': 'We will review within 24 hours.'}

    @staticmethod
    def get_pending_dmca() -> list:
        """Get open DMCA tickets."""
        from api.offer_inventory.models import FeedbackTicket
        return list(
            FeedbackTicket.objects.filter(
                subject__startswith='DMCA', status='open'
            ).values('ticket_no', 'subject', 'created_at')[:50]
        )
