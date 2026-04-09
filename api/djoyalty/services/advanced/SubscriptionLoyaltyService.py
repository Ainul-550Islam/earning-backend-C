# api/djoyalty/services/advanced/SubscriptionLoyaltyService.py
import logging
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from ...models.advanced import LoyaltySubscription

logger = logging.getLogger(__name__)

class SubscriptionLoyaltyService:
    @staticmethod
    def process_monthly_renewals():
        due = LoyaltySubscription.objects.filter(
            is_active=True, next_renewal_at__lte=timezone.now(),
        )
        count = 0
        for sub in due:
            try:
                if sub.bonus_points_monthly > 0:
                    from ..earn.BonusEventService import BonusEventService
                    BonusEventService.award_bonus(
                        sub.customer, sub.bonus_points_monthly,
                        reason=f'Monthly subscription bonus: {sub.plan_name}',
                        triggered_by='subscription',
                    )
                sub.next_renewal_at = timezone.now() + timedelta(days=30)
                sub.save(update_fields=['next_renewal_at'])
                count += 1
            except Exception as e:
                logger.error('Subscription renewal error %s: %s', sub.id, e)
        return count
