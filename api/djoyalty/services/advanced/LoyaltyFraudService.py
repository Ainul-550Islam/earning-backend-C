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
            LoyaltyFraudService._log_fraud(
                customer, 'high', 'flag',
                f'Rapid transactions: {count} in {FRAUD_RAPID_TXN_WINDOW_MINUTES}m',
            )
            # FIXED: fire fraud_detected signal so alert handlers run
            LoyaltyFraudService._fire_fraud_detected(
                customer=customer,
                fraud_type='rapid_transactions',
                risk_level='high',
                detail={
                    'transaction_count': count,
                    'window_minutes': FRAUD_RAPID_TXN_WINDOW_MINUTES,
                },
            )
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
            LoyaltyFraudService._log_fraud(
                customer, 'critical', 'block',
                f'Daily redemption exceeded: {daily_total + amount}',
            )
            # FIXED: fire fraud_detected signal so alert handlers run
            LoyaltyFraudService._fire_fraud_detected(
                customer=customer,
                fraud_type='daily_redemption_exceeded',
                risk_level='critical',
                detail={
                    'attempted_total': str(daily_total + amount),
                    'daily_limit': str(FRAUD_MAX_DAILY_REDEMPTION),
                    'existing_today': str(daily_total),
                    'attempted_amount': str(amount),
                },
            )
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

    @staticmethod
    def _fire_fraud_detected(customer, fraud_type: str, risk_level: str, detail: dict):
        """
        Fire the fraud_detected Django signal।
        Connected handlers in signals/ will send admin alerts,
        update customer risk scores, and trigger compliance workflows।

        FIXED: this method was missing -- fraud_detected signal was defined
        in signals.py but never sent anywhere, so no downstream alerts ran।
        """
        try:
            from ...signals import fraud_detected
            fraud_detected.send(
                sender=LoyaltyFraudService,
                customer=customer,
                fraud_type=fraud_type,
                risk_level=risk_level,
                detail=detail,
                timestamp=timezone.now(),
            )
            logger.info(
                'LoyaltyFraudService: fraud_detected signal sent -- customer=%s type=%s level=%s',
                getattr(customer, 'code', customer.pk), fraud_type, risk_level,
            )
        except Exception as e:
            # Never let signal failure block the fraud check itself
            logger.error('LoyaltyFraudService: failed to send fraud_detected signal: %s', e)
