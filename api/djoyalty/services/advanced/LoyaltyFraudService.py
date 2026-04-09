# api/djoyalty/services/advanced/LoyaltyFraudService.py
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from ...models.advanced import LoyaltyFraudRule, PointsAbuseLog
from ...constants import FRAUD_MAX_DAILY_REDEMPTION, FRAUD_RAPID_TXN_WINDOW_MINUTES, FRAUD_RAPID_TXN_COUNT

logger = logging.getLogger(__name__)

class LoyaltyFraudService:
    @staticmethod
    def check_rapid_transactions(customer) -> bool:
        from ...models.core import Txn
        cutoff = timezone.now() - timedelta(minutes=FRAUD_RAPID_TXN_WINDOW_MINUTES)
        count = Txn.objects.filter(customer=customer, timestamp__gte=cutoff).count()
        if count >= FRAUD_RAPID_TXN_COUNT:
            LoyaltyFraudService._log_fraud(customer, 'high', 'flag', f'Rapid transactions: {count} in {FRAUD_RAPID_TXN_WINDOW_MINUTES}m')
            return True
        return False

    @staticmethod
    def check_daily_redemption(customer, amount: Decimal) -> bool:
        from ...models.redemption import RedemptionRequest
        today = timezone.now().date()
        daily_total = sum(
            r.points_used for r in RedemptionRequest.objects.filter(
                customer=customer,
                created_at__date=today,
                status__in=['pending', 'approved', 'completed'],
            )
        )
        if daily_total + amount > FRAUD_MAX_DAILY_REDEMPTION:
            LoyaltyFraudService._log_fraud(customer, 'critical', 'block', f'Daily redemption exceeded: {daily_total + amount}')
            return True
        return False

    @staticmethod
    def _log_fraud(customer, risk_level: str, action: str, description: str):
        try:
            PointsAbuseLog.objects.create(
                tenant=customer.tenant, customer=customer,
                risk_level=risk_level, action_taken=action, description=description,
            )
        except Exception as e:
            logger.error('Fraud log error: %s', e)
