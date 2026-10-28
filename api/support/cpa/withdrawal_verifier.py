"""
api/support/cpa/withdrawal_verifier.py
FILE 7 — Withdrawal Auto-Verify System

Withdrawal issue ticket আসলে auto-check করো।
bKash/Nagad/PayPal status verify করো।
"""
import logging
logger = logging.getLogger(__name__)

class WithdrawalVerifier:
    def verify_and_create_ticket(self, user, data: dict) -> dict:
        withdrawal_id = data.get('withdrawal_id', '')
        amount        = data.get('amount', 0)
        method        = data.get('method', '')
        account       = data.get('account', '')

        # Check withdrawal status
        status_info = self._check_withdrawal_status(user, withdrawal_id)

        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'withdrawal',
            subject     = f'Withdrawal Issue: {method} {amount}'[:200],
            description = (
                f'WITHDRAWAL VERIFICATION\n'
                f'══════════════════════════\n'
                f'Withdrawal ID: {withdrawal_id}\n'
                f'Method: {method}\n'
                f'Amount: {amount}\n'
                f'Account: {account}\n\n'
                f'System Status: {status_info["status"]}\n'
                f'Details: {status_info.get("details","N/A")}\n'
            ),
            priority    = 'high',
            status      = 'open',
            channel     = 'web',
            tenant      = getattr(user, 'tenant', None),
        )

        # Auto-resolve if already processed
        if status_info['status'] == 'completed':
            self._inform_completed(ticket, status_info)

        return {
            'ticket_id':   ticket.ticket_id,
            'auto_status': status_info['status'],
            'message':     status_info.get('user_message', 'Your withdrawal issue has been submitted.'),
        }

    def _check_withdrawal_status(self, user, withdrawal_id: str) -> dict:
        try:
            from django.apps import apps
            for app_label, model_name in [('withdrawal','WithdrawalRequest'),('wallet','Withdrawal'),('earning','WithdrawalRequest')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    qs    = model.objects.filter(user=user)
                    if withdrawal_id:
                        qs = qs.filter(id=withdrawal_id)
                    if qs.exists():
                        w = qs.first()
                        s = getattr(w, 'status', 'unknown')
                        return {
                            'status':       s,
                            'details':      f'Found in system. Status: {s}',
                            'user_message': self._get_status_message(s),
                            'found':        True,
                        }
                except Exception:
                    continue
        except Exception:
            pass
        return {'status': 'not_found', 'details': 'Not found in system', 'found': False,
                'user_message': 'Withdrawal record not found. Agent will investigate within 24 hours.'}

    def _get_status_message(self, status: str) -> str:
        messages = {
            'pending':    'Your withdrawal is pending processing. Please allow 1-3 business days.',
            'processing': 'Your withdrawal is being processed. Should arrive within 24 hours.',
            'completed':  'Your withdrawal was marked as completed in our system. Please check your account.',
            'failed':     'Your withdrawal failed. Our team will reprocess or refund within 24 hours.',
            'cancelled':  'Your withdrawal was cancelled. Please create a new withdrawal request.',
        }
        return messages.get(status, 'Status unknown. Agent will investigate.')

    def _inform_completed(self, ticket, status_info: dict) -> None:
        from api.support.models import TicketMessage
        from django.contrib.auth import get_user_model
        bot = get_user_model().objects.filter(is_superuser=True).first()
        if bot:
            TicketMessage.objects.create(
                ticket=ticket, sender=bot, is_agent=True,
                content='Our records show this withdrawal was completed. If you did not receive funds, please check with your payment provider. Reply with your payment provider reference for further assistance.'
            )
            ticket.status = 'waiting_user'
            ticket.save(update_fields=['status'])

withdrawal_verifier = WithdrawalVerifier()