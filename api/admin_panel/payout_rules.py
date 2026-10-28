# api/admin_panel/payout_rules.py
"""Payout eligibility rules — min amount, KYC, account age, fraud check."""
from __future__ import annotations
import logging
from decimal import Decimal
from typing import Any, Dict, Tuple
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


class PayoutRulesEngine:
    """Evaluate payout eligibility for a user."""

    @classmethod
    def check_eligibility(cls, user_id: Any, amount: Decimal) -> Tuple[bool, List[str]]:
        """
        Full eligibility check.
        Returns (eligible: bool, failed_rules: list).
        """
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        failed = []

        # Rule 1: Minimum amount
        min_payout = Decimal(str(SystemConfigService.get('min_payout_amount', default=10)))
        if amount < min_payout:
            failed.append(f'Amount ৳{amount} below minimum ৳{min_payout}')

        # Rule 2: Maximum amount
        max_payout = Decimal(str(SystemConfigService.get('max_single_payout', default=50000)))
        if amount > max_payout:
            failed.append(f'Amount ৳{amount} exceeds maximum ৳{max_payout}')

        # Rule 3: Account age
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
            min_days = int(SystemConfigService.get('payout_min_account_age_days', default=3))
            age_days = (timezone.now() - user.date_joined).days
            if age_days < min_days:
                failed.append(f'Account only {age_days} days old (minimum: {min_days})')
        except Exception:
            failed.append('User not found')
            return False, failed

        # Rule 4: KYC requirement
        kyc_required = SystemConfigService.get('kyc_required_for_payout', default=False)
        if kyc_required:
            try:
                from api.kyc.models import KYC
                if not KYC.objects.filter(user_id=user_id, status='approved').exists():
                    failed.append('KYC verification required for withdrawal')
            except Exception:
                pass

        # Rule 5: Fraud check
        try:
            from api.admin_panel.logic import calculate_user_risk_score
            risk = calculate_user_risk_score(user_id)
            if risk['score'] >= 80:
                failed.append(f'High fraud risk score: {risk["score"]}/100')
        except Exception:
            pass

        # Rule 6: Daily withdrawal limit
        daily_limit = Decimal(str(SystemConfigService.get('daily_withdrawal_limit', default=50000)))
        try:
            from api.payout_queue.models import PayoutItem
            from django.db.models import Sum
            today_total = Decimal(str(PayoutItem.objects.filter(
                user_id=user_id,
                status__in=['SUCCESS', 'QUEUED', 'PROCESSING'],
                batch__created_at__date=timezone.now().date()
            ).aggregate(t=Sum('gross_amount'))['t'] or 0))
            if today_total + amount > daily_limit:
                failed.append(f'Daily limit ৳{daily_limit} would be exceeded (today: ৳{today_total})')
        except Exception:
            pass

        return len(failed) == 0, failed

    @classmethod
    def get_user_payout_limits(cls, user_id: Any) -> Dict:
        """Get payout limits for a specific user."""
        from api.admin_panel.services.SystemConfigService import SystemConfigService
        return {
            'min_amount':  float(SystemConfigService.get('min_payout_amount', 10)),
            'max_amount':  float(SystemConfigService.get('max_single_payout', 50000)),
            'daily_limit': float(SystemConfigService.get('daily_withdrawal_limit', 50000)),
            'min_age_days': int(SystemConfigService.get('payout_min_account_age_days', 3)),
            'kyc_required': bool(SystemConfigService.get('kyc_required_for_payout', False)),
        }


from typing import List
payout_rules = PayoutRulesEngine()