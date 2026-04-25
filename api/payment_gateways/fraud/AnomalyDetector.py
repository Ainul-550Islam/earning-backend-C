# api/payment_gateways/fraud/AnomalyDetector.py
# FILE 80 of 257 — Anomaly detection for unusual payment patterns

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detect anomalies in payment patterns:
        - Amount unusually large vs user's history
        - First-time use of a gateway
        - Unusual time of day
        - Repeated same amount (possible automation)
        - Account too new
    """

    def check(self, user, amount: Decimal, gateway: str, metadata: dict = None) -> dict:
        risk_score = 0
        reasons    = []

        checks = [
            self._check_amount_anomaly(user, amount, gateway),
            self._check_new_account(user),
            self._check_first_gateway_use(user, gateway),
            self._check_time_anomaly(),
            self._check_repeated_amount(user, amount),
        ]

        for check in checks:
            risk_score += check['score']
            reasons.extend(check['reasons'])

        return {
            'risk_score': min(40, risk_score),
            'reasons':    reasons,
        }

    def _check_amount_anomaly(self, user, amount: Decimal, gateway: str) -> dict:
        """Flag if amount is > 5x the user's average deposit."""
        from api.payment_gateways.models import GatewayTransaction
        from django.db.models import Avg

        avg_result = GatewayTransaction.objects.filter(
            user=user, status='completed', transaction_type='deposit',
            created_at__gte=timezone.now() - timedelta(days=30),
        ).aggregate(avg=Avg('amount'))

        avg = avg_result['avg']
        if avg and amount > avg * 5:
            return {
                'score':   20,
                'reasons': [f'Amount {amount} is {amount/avg:.1f}x user average ({avg:.0f})']
            }
        return {'score': 0, 'reasons': []}

    def _check_new_account(self, user) -> dict:
        """Higher risk for accounts created within 7 days."""
        date_joined = getattr(user, 'date_joined', None)
        if date_joined:
            age = (timezone.now() - date_joined).days
            if age < 1:
                return {'score': 20, 'reasons': ['Account created today']}
            if age < 7:
                return {'score': 10, 'reasons': [f'Account is only {age} days old']}
        return {'score': 0, 'reasons': []}

    def _check_first_gateway_use(self, user, gateway: str) -> dict:
        """Slight risk bump for first-ever use of a gateway."""
        from api.payment_gateways.models import GatewayTransaction
        exists = GatewayTransaction.objects.filter(
            user=user, gateway=gateway, status='completed'
        ).exists()
        if not exists:
            return {'score': 5, 'reasons': [f'First time using {gateway}']}
        return {'score': 0, 'reasons': []}

    def _check_time_anomaly(self) -> dict:
        """Slightly elevated risk for transactions between 1 AM – 5 AM BD time."""
        hour = timezone.localtime().hour
        if 1 <= hour <= 5:
            return {'score': 5, 'reasons': [f'Transaction at unusual hour ({hour}:00 BD time)']}
        return {'score': 0, 'reasons': []}

    def _check_repeated_amount(self, user, amount: Decimal) -> dict:
        """Flag if the exact same amount appears 3+ times in the last hour."""
        from api.payment_gateways.models import GatewayTransaction

        count = GatewayTransaction.objects.filter(
            user=user,
            amount=amount,
            transaction_type='deposit',
            created_at__gte=timezone.now() - timedelta(hours=1),
        ).count()

        if count >= 3:
            return {'score': 15, 'reasons': [f'Same amount {amount} repeated {count} times in 1 hour']}
        return {'score': 0, 'reasons': []}
