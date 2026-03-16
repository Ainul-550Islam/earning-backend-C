# api/promotions/auditing/compliance_checker.py
# Compliance Checker — KYC, AML, transaction limits
import logging
from decimal import Decimal
logger = logging.getLogger('auditing.compliance')

# AML thresholds
AML_DAILY_THRESHOLD   = Decimal('1000')   # $1000/day triggers review
AML_MONTHLY_THRESHOLD = Decimal('5000')   # $5000/month triggers SAR

class ComplianceChecker:
    """
    AML (Anti-Money Laundering) + KYC checks.
    Flags suspicious transactions for manual review.
    """
    def check_transaction(self, user_id: int, amount_usd: Decimal) -> dict:
        from django.utils import timezone
        from datetime import timedelta
        flags = []

        try:
            from api.promotions.models import PromotionTransaction
            from django.db.models import Sum

            today  = timezone.now().date()
            daily  = PromotionTransaction.objects.filter(
                user_id=user_id, created_at__date=today
            ).aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')

            month_start = today.replace(day=1)
            monthly = PromotionTransaction.objects.filter(
                user_id=user_id, created_at__date__gte=month_start
            ).aggregate(total=Sum('amount_usd'))['total'] or Decimal('0')

            if (daily + amount_usd) > AML_DAILY_THRESHOLD:
                flags.append('daily_limit_exceeded')
            if (monthly + amount_usd) > AML_MONTHLY_THRESHOLD:
                flags.append('monthly_limit_exceeded')
        except Exception as e:
            logger.error(f'Compliance check failed: {e}')

        return {'flags': flags, 'requires_review': len(flags) > 0, 'amount_usd': float(amount_usd)}

    def check_kyc_status(self, user_id: int) -> dict:
        """User KYC status check।"""
        try:
            from api.promotions.models import UserVerification
            v = UserVerification.objects.filter(user_id=user_id).first()
            if not v:
                return {'kyc_status': 'not_submitted', 'payout_allowed': False}
            return {'kyc_status': v.status, 'payout_allowed': v.status == 'verified',
                    'verified_at': str(v.verified_at) if v.verified_at else None}
        except Exception:
            return {'kyc_status': 'unknown', 'payout_allowed': False}
