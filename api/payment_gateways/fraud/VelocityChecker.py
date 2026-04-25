# api/payment_gateways/fraud/VelocityChecker.py
# FILE 78 of 257 — Transaction velocity / rate-limit fraud check

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


class VelocityChecker:
    """
    Check how many transactions a user has made in recent windows.
    High frequency = higher risk score.
    """

    LIMITS = {
        '1min':   {'count': 3,  'amount': Decimal('5000'),   'score': 25},
        '10min':  {'count': 10, 'amount': Decimal('20000'),  'score': 20},
        '1hour':  {'count': 20, 'amount': Decimal('50000'),  'score': 15},
        '24hour': {'count': 50, 'amount': Decimal('200000'), 'score': 10},
    }

    def check(self, user, amount: Decimal, gateway: str) -> dict:
        from api.payment_gateways.models import GatewayTransaction
        from django.db.models import Sum, Count

        risk_score = 0
        reasons    = []
        windows    = {
            '1min':   timedelta(minutes=1),
            '10min':  timedelta(minutes=10),
            '1hour':  timedelta(hours=1),
            '24hour': timedelta(hours=24),
        }

        for window_name, delta in windows.items():
            since = timezone.now() - delta
            agg   = GatewayTransaction.objects.filter(
                user=user,
                created_at__gte=since,
                transaction_type='deposit',
            ).aggregate(count=Count('id'), total=Sum('amount'))

            count = agg['count'] or 0
            total = agg['total'] or Decimal('0')
            limit = self.LIMITS[window_name]

            if count >= limit['count']:
                risk_score += limit['score']
                reasons.append(f'{count} transactions in last {window_name} (limit: {limit["count"]})')

            if total + amount > limit['amount']:
                risk_score += limit['score'] // 2
                reasons.append(f'Total {total + amount} in {window_name} exceeds {limit["amount"]}')

        return {
            'risk_score': min(50, risk_score),
            'reasons':    reasons,
        }
