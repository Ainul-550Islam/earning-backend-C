# api/support/compliance.py
"""
Compliance module for support system.
GDPR / data privacy compliance utilities.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


class SupportComplianceManager:
    """
    GDPR / data protection compliance for support system.
    Handles: data export, anonymization, deletion, audit trails.
    """

    def export_user_data(self, user) -> dict:
        """
        Export all support data for a user (GDPR right to access).
        Returns dict of all support data for the user.
        """
        data = {
            'exported_at': timezone.now().isoformat(),
            'user_id':     user.id,
            'username':    user.username,
            'email':       user.email,
            'tickets':     [],
            'disputes':    [],
            'chat_sessions': [],
            'ratings':     [],
        }

        # Tickets
        try:
            from api.support.models import SupportTicket
            tickets = SupportTicket.objects.filter(user=user).select_related('assigned_to')
            for t in tickets:
                messages = list(t.messages.values('content', 'is_agent', 'created_at'))
                data['tickets'].append({
                    'ticket_id':   t.ticket_id,
                    'category':    t.category,
                    'subject':     t.subject,
                    'description': t.description,
                    'status':      t.status,
                    'created_at':  t.created_at.isoformat(),
                    'resolved_at': t.resolved_at.isoformat() if t.resolved_at else None,
                    'messages':    messages,
                })
        except Exception as e:
            logger.debug(f'export_user_data tickets: {e}')

        # Disputes
        try:
            from api.support.models import OfferDispute, WithdrawalDispute
            for d in OfferDispute.objects.filter(user=user):
                data['disputes'].append({
                    'type':             'offer',
                    'offer_id':         d.offer_id,
                    'expected_amount':  str(d.expected_amount),
                    'status':           d.status,
                    'created_at':       d.created_at.isoformat(),
                })
            for d in WithdrawalDispute.objects.filter(user=user):
                data['disputes'].append({
                    'type':            'withdrawal',
                    'transaction_id':  d.transaction_id,
                    'amount':          str(d.amount),
                    'status':          d.status,
                    'created_at':      d.created_at.isoformat(),
                })
        except Exception as e:
            logger.debug(f'export_user_data disputes: {e}')

        # Chat sessions
        try:
            from api.support.models import ChatSession
            for s in ChatSession.objects.filter(user=user):
                messages = list(s.messages.values('content', 'is_agent', 'created_at'))
                data['chat_sessions'].append({
                    'session_id':  str(s.session_id),
                    'started_at':  s.started_at.isoformat(),
                    'ended_at':    s.ended_at.isoformat() if s.ended_at else None,
                    'rating':      s.rating,
                    'messages':    messages,
                })
        except Exception as e:
            logger.debug(f'export_user_data chats: {e}')

        return data

    def anonymize_user_data(self, user, reason: str = 'user_request') -> dict:
        """
        Anonymize user's support data (GDPR right to erasure).
        Replaces PII with anonymized values.
        """
        from api.support.models import SupportTicket, TicketMessage
        results = {'tickets_anonymized': 0, 'messages_anonymized': 0}

        anon_subject = 'ANONYMIZED'
        anon_desc    = 'Data anonymized per user request.'
        anon_response= 'Data anonymized.'

        try:
            tickets = SupportTicket.objects.filter(user=user)
            count   = tickets.update(
                subject=anon_subject, description=anon_desc,
                admin_response=anon_response, source_email='',
            )
            results['tickets_anonymized'] = count

            msgs = TicketMessage.objects.filter(ticket__user=user)
            results['messages_anonymized'] = msgs.update(content='[ANONYMIZED]')
        except Exception as e:
            logger.error(f'anonymize_user_data: {e}')

        logger.info(f'User data anonymized: user={user.id} reason={reason} result={results}')
        return results

    def delete_old_logs(self, days: int = 365) -> int:
        """Delete old notification logs beyond retention period."""
        from api.support.models import SupportNotificationLog
        from datetime import timedelta
        cutoff  = timezone.now() - timedelta(days=days)
        deleted, _ = SupportNotificationLog.objects.filter(created_at__lte=cutoff).delete()
        logger.info(f'Deleted {deleted} notification logs older than {days} days')
        return deleted

    def get_data_retention_status(self) -> dict:
        """Get data retention stats for compliance dashboard."""
        from api.support.models import SupportTicket, SupportNotificationLog
        from datetime import timedelta
        now         = timezone.now()
        year_ago    = now - timedelta(days=365)
        old_tickets = SupportTicket.objects.filter(created_at__lte=year_ago).count()
        old_logs    = SupportNotificationLog.objects.filter(created_at__lte=year_ago).count()
        return {
            'tickets_older_than_1yr':     old_tickets,
            'notification_logs_old':      old_logs,
            'checked_at':                 now.isoformat(),
            'retention_period_days':      365,
        }

    def generate_audit_trail(self, user, days: int = 90) -> list:
        """Generate audit trail for a user — for compliance reporting."""
        try:
            from api.support.integrations.integ_audit_logs import audit_logger
            return audit_logger.get_user_audit_history(user, limit=100)
        except Exception:
            return []


compliance_manager = SupportComplianceManager()