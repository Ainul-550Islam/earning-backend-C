# api/offer_inventory/compliance_legal/aml_checks.py
"""AML Checks — Anti-Money Laundering transaction monitoring."""
import logging
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

LARGE_TX_THRESHOLD   = 50000    # BDT
RAPID_TX_LIMIT       = 5        # transactions per hour


class AMLService:
    """Anti-Money Laundering compliance checks."""

    @staticmethod
    def check_withdrawal(user, amount: Decimal) -> dict:
        """Check withdrawal for AML flags."""
        from api.offer_inventory.models import WithdrawalRequest, WalletAudit
        from django.db.models import Count, Sum
        from datetime import timedelta

        flags = []

        # Large transaction check
        if float(amount) >= LARGE_TX_THRESHOLD:
            flags.append(f'large_transaction:{amount}')

        # Rapid transaction check (multiple withdrawals per hour)
        since_hour = timezone.now() - timedelta(hours=1)
        recent_count = WithdrawalRequest.objects.filter(
            user=user, created_at__gte=since_hour
        ).count()
        if recent_count >= RAPID_TX_LIMIT:
            flags.append(f'rapid_transactions:{recent_count}')

        # Structuring check (just below reporting threshold)
        if LARGE_TX_THRESHOLD * Decimal('0.9') <= amount < Decimal(str(LARGE_TX_THRESHOLD)):
            flags.append('possible_structuring')

        is_flagged = len(flags) > 0
        if is_flagged:
            AMLService._record_flag(user, flags, float(amount))

        return {
            'flagged': is_flagged,
            'flags'  : flags,
            'amount' : float(amount),
            'action' : 'review' if is_flagged else 'allow',
        }

    @staticmethod
    def _record_flag(user, flags: list, amount: float):
        from api.offer_inventory.models import SuspiciousActivity
        import json
        try:
            SuspiciousActivity.objects.create(
                user      =user,
                activity  ='aml_flag',
                details   ={'flags': flags, 'amount': amount},
                risk_score=70.0,
            )
        except Exception as e:
            logger.error(f'AML record error: {e}')
        logger.warning(f'AML flag: user={user.id} flags={flags} amount={amount}')

    @staticmethod
    def get_flagged_users(days: int = 30) -> list:
        from api.offer_inventory.models import SuspiciousActivity
        from datetime import timedelta
        since = timezone.now() - timedelta(days=days)
        return list(
            SuspiciousActivity.objects.filter(
                activity='aml_flag', created_at__gte=since
            ).select_related('user')
            .values('user__username', 'details', 'created_at')[:100]
        )
