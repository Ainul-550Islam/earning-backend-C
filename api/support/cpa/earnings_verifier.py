"""
api/support/cpa/earnings_verifier.py
FILE 9 — Earnings Verification System

User: "আমার কয়েন মিলছে না।"
System: earning transactions cross-check করো।
"""
import logging
logger = logging.getLogger(__name__)

class EarningsVerifier:
    def verify_and_report(self, user, data: dict) -> dict:
        reported_amount = float(data.get('expected_amount', 0))
        period_start    = data.get('period_start', '')
        period_end      = data.get('period_end', '')

        system_balance  = self._get_system_balance(user)
        transaction_count = self._get_transaction_count(user, period_start, period_end)

        discrepancy = max(0, reported_amount - system_balance)
        has_issue   = discrepancy > 0

        from api.support.models import SupportTicket
        ticket = SupportTicket.objects.create(
            user        = user,
            category    = 'coins',
            subject     = f'Earnings Discrepancy: Expected {reported_amount}, System shows {system_balance}'[:200],
            description = (
                f'EARNINGS VERIFICATION\n'
                f'══════════════════════════\n'
                f'Expected Amount: {reported_amount}\n'
                f'System Balance: {system_balance}\n'
                f'Discrepancy: {discrepancy}\n'
                f'Period: {period_start} to {period_end}\n'
                f'Transactions Found: {transaction_count}\n\n'
                f'Description: {data.get("description","")}'
            ),
            priority    = 'high' if discrepancy > 100 else 'medium',
            status      = 'open',
            channel     = 'web',
            tenant      = getattr(user, 'tenant', None),
        )

        return {
            'ticket_id':      ticket.ticket_id,
            'system_balance': system_balance,
            'discrepancy':    discrepancy,
            'has_issue':      has_issue,
            'message':        'Earnings verification submitted. Our team will reconcile within 24 hours.' if has_issue else 'Your earnings appear to match our records.',
        }

    def _get_system_balance(self, user) -> float:
        try:
            from django.apps import apps
            for app_label, model_name in [('earning','EarningBalance'),('wallet','Balance'),('earning','UserBalance')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    obj   = model.objects.filter(user=user).first()
                    if obj:
                        return float(getattr(obj, 'balance', 0) or getattr(obj, 'amount', 0) or 0)
                except Exception:
                    continue
        except Exception:
            pass
        return 0.0

    def _get_transaction_count(self, user, start: str, end: str) -> int:
        try:
            from django.apps import apps
            for app_label, model_name in [('earning','EarningTransaction'),('earning','Transaction')]:
                try:
                    model = apps.get_model(app_label, model_name)
                    qs    = model.objects.filter(user=user)
                    return qs.count()
                except Exception:
                    continue
        except Exception:
            pass
        return 0

earnings_verifier = EarningsVerifier()