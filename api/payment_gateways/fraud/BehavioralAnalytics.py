# api/payment_gateways/fraud/BehavioralAnalytics.py
# Behavioral analytics for detecting unusual payment patterns

from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class BehavioralAnalytics:
    """
    Analyze user behavioral patterns to detect fraud:
        - Session-based velocity (many actions in short time)
        - Round-number deposits (bots often use round numbers)
        - Systematic amount testing (small amounts before large)
        - Deposit-immediately-withdraw pattern (money laundering)
        - Unusual time patterns vs user's normal hours
    """

    def analyze(self, user, amount: Decimal, gateway: str, metadata: dict = None) -> dict:
        metadata   = metadata or {}
        risk_score = 0
        reasons    = []

        checks = [
            self._check_round_number(amount),
            self._check_systematic_testing(user, amount),
            self._check_deposit_withdraw_cycle(user, amount),
            self._check_session_velocity(user, metadata),
            self._check_normal_hour_deviation(user),
        ]

        for check in checks:
            risk_score += check['score']
            reasons.extend(check['reasons'])

        return {
            'risk_score': min(40, risk_score),
            'reasons':    reasons,
        }

    def _check_round_number(self, amount: Decimal) -> dict:
        """Round numbers (100, 500, 1000) are more common in bot activity."""
        amount_f = float(amount)
        # Check if perfectly round
        if amount_f > 100 and amount_f % 100 == 0:
            # Not suspicious alone, but a signal
            return {'score': 3, 'reasons': [f'Round number deposit: {amount_f}']}
        return {'score': 0, 'reasons': []}

    def _check_systematic_testing(self, user, amount: Decimal) -> dict:
        """
        Detect pattern: small test → medium → large (common card testing).
        Example: 10 → 50 → 500 in short time.
        """
        from api.payment_gateways.models import GatewayTransaction
        from django.db.models import Min

        recent = GatewayTransaction.objects.filter(
            user=user,
            transaction_type='deposit',
            created_at__gte=timezone.now() - timedelta(hours=2),
        ).order_by('created_at').values_list('amount', flat=True)

        amounts = [float(a) for a in recent]
        if len(amounts) >= 2:
            # Check if amounts are strictly increasing and all different orders of magnitude
            is_escalating = all(amounts[i] < amounts[i+1] for i in range(len(amounts)-1))
            if is_escalating and float(amount) > (amounts[-1] if amounts else 0) * 2:
                return {
                    'score':   20,
                    'reasons': ['Escalating amount pattern detected (possible card testing)']
                }
        return {'score': 0, 'reasons': []}

    def _check_deposit_withdraw_cycle(self, user, amount: Decimal) -> dict:
        """
        Detect deposit-then-immediately-withdraw pattern.
        Money laundering indicator.
        """
        from api.payment_gateways.models import GatewayTransaction

        recent_deposit = GatewayTransaction.objects.filter(
            user=user,
            transaction_type='deposit',
            status='completed',
            created_at__gte=timezone.now() - timedelta(hours=1),
        ).first()

        recent_withdrawal = GatewayTransaction.objects.filter(
            user=user,
            transaction_type='withdrawal',
            created_at__gte=timezone.now() - timedelta(hours=1),
        ).exists()

        if recent_deposit and recent_withdrawal:
            return {
                'score':   25,
                'reasons': ['Rapid deposit-then-withdrawal pattern detected']
            }
        return {'score': 0, 'reasons': []}

    def _check_session_velocity(self, user, metadata: dict) -> dict:
        """Check if many payment attempts happen in one session."""
        session_key = metadata.get('session_key', '')
        if not session_key:
            return {'score': 0, 'reasons': []}

        from django.core.cache import cache
        session_count = cache.get(f'session_pay:{session_key}', 0)
        cache.set(f'session_pay:{session_key}', session_count + 1, timeout=3600)

        if session_count >= 5:
            return {
                'score':   20,
                'reasons': [f'{session_count} payment attempts in current session']
            }
        if session_count >= 3:
            return {
                'score':   10,
                'reasons': [f'{session_count} payment attempts in current session']
            }
        return {'score': 0, 'reasons': []}

    def _check_normal_hour_deviation(self, user) -> dict:
        """Check if current transaction happens at an unusual hour for this user."""
        from api.payment_gateways.models import GatewayTransaction

        current_hour = timezone.localtime().hour

        # Get user's historical transaction hours
        hours = list(GatewayTransaction.objects.filter(
            user=user,
            status='completed',
        ).values_list('created_at__hour', flat=True)[:100])

        if len(hours) < 10:
            return {'score': 0, 'reasons': []}  # Not enough history

        # Calculate most common hours (mode)
        from collections import Counter
        common_hours = {h for h, _ in Counter(hours).most_common(12)}  # Top 12 hours

        if current_hour not in common_hours:
            return {
                'score':   8,
                'reasons': [f'Transaction at unusual hour for this user ({current_hour}:00)']
            }
        return {'score': 0, 'reasons': []}
