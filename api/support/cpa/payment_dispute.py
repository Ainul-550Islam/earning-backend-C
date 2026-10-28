"""
api/support/cpa/payment_dispute.py
FILE 5 — Payment Dispute + Auto-Verify System

Publisher: "আমার payment পেলাম না।"
System: bKash/Nagad/PayPal logs verify করো।
"""
import logging
from django.utils import timezone
logger = logging.getLogger(__name__)

class PaymentDisputeSystem:
    def create_dispute(self, user, data: dict) -> dict:
        amount          = data.get('amount', 0)
        payment_method  = data.get('payment_method', '')
        payment_id      = data.get('payment_id', '')
        payment_date    = data.get('payment_date', '')
        account_number  = data.get('account_number', '')

        verification = self._verify_payment(user, payment_id, payment_method, amount)

        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'payment',
            subject     = f'[PAYMENT DISPUTE] {payment_method} | {amount} | {payment_id}'[:200],
            description = (
                f'PAYMENT DISPUTE\n'
                f'═══════════════════════════════\n'
                f'Method: {payment_method}\n'
                f'Amount: {amount}\n'
                f'Payment ID/TxID: {payment_id}\n'
                f'Date: {payment_date}\n'
                f'Account: {account_number}\n\n'
                f'Verification: {verification["status"]}\n'
                f'Details: {", ".join(verification.get("details",[]))}\n'
            ),
            priority    = 'high',
            status      = 'open',
            channel     = 'web',
            tenant      = getattr(user, 'tenant', None),
        )

        return {
            'ticket_id':    ticket.ticket_id,
            'status':       'investigating',
            'verification': verification,
            'message':      'Payment dispute submitted. Our finance team will review within 24 hours.',
            'priority':     'high',
        }

    def _verify_payment(self, user, payment_id: str, method: str, amount: float) -> dict:
        """Payment log check"""
        result = {'status': 'checking', 'details': [], 'found': False}

        try:
            from django.apps import apps
            for app_label, model_name in [('withdrawal','WithdrawalRequest'),('earning','Withdrawal'),('wallet','WithdrawalLog')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    qs    = model.objects.filter(user=user)
                    if payment_id:
                        qs = qs.filter(transaction_id=payment_id)
                    if qs.exists():
                        w = qs.first()
                        result['found']   = True
                        result['status']  = 'found_in_system'
                        result['details'] = [f'Found in {model_name}: status={getattr(w,"status","unknown")}']
                        return result
                except Exception:
                    continue
        except Exception as e:
            result['details'].append(f'Verification error: {str(e)[:50]}')

        result['status']  = 'not_found'
        result['details'] = ['Payment record not found in system. Agent will investigate.']
        return result

    def get_pending_disputes(self) -> list:
        """Admin: list pending payment disputes"""
        from api.support.models import SupportTicket
        return list(
            SupportTicket.objects.filter(
                category='payment',
                subject__startswith='[PAYMENT DISPUTE]',
                status__in=['open','in_progress'],
            ).select_related('user').values('ticket_id','subject','user__username','created_at','priority')[:50]
        )

payment_dispute_system = PaymentDisputeSystem()

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_payment_dispute(request):
    """POST /support/cpa/dispute/payment/"""
    result = payment_dispute_system.create_dispute(request.user, request.data)
    return Response({'success': True, **result}, status=http_status.HTTP_201_CREATED)