# api/djoyalty/signals/earn_signals.py
"""
Earn signals — EarnTransaction post_save এ tier evaluation trigger করে।
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='djoyalty.EarnTransaction')
def on_earn_transaction(sender, instance, created, **kwargs):
    """
    নতুন EarnTransaction তৈরি হলে:
    1. Customer এর tier re-evaluate করো
    2. Badge check করো (transaction_count trigger)
    3. Milestone check করো
    """
    if not created:
        return

    try:
        from ..services.tiers.TierEvaluationService import TierEvaluationService
        TierEvaluationService.evaluate(instance.customer, tenant=instance.tenant)
    except Exception as e:
        logger.warning('earn_signals: tier eval error for %s: %s', instance.customer, e)

    try:
        from ..models.core import Txn
        txn_count = Txn.objects.filter(customer=instance.customer).count()
        from ..services.engagement.BadgeService import BadgeService
        from decimal import Decimal
        BadgeService.check_and_award(
            instance.customer,
            'transaction_count',
            current_value=Decimal(str(txn_count)),
            tenant=instance.tenant,
        )
    except Exception as e:
        logger.warning('earn_signals: badge check error for %s: %s', instance.customer, e)

    try:
        from ..models.points import LoyaltyPoints
        from decimal import Decimal
        lp = LoyaltyPoints.objects.filter(customer=instance.customer).first()
        if lp:
            from ..services.engagement.MilestoneService import MilestoneService
            MilestoneService.check_milestones(
                instance.customer,
                'total_points',
                current_value=lp.lifetime_earned,
                tenant=instance.tenant,
            )
            if instance.spend_amount:
                from django.db.models import Sum
                from ..models.core import Txn
                total_spend = Txn.objects.filter(
                    customer=instance.customer, value__gt=0
                ).aggregate(s=Sum('value'))['s'] or Decimal('0')
                MilestoneService.check_milestones(
                    instance.customer,
                    'total_spend',
                    current_value=total_spend,
                    tenant=instance.tenant,
                )
    except Exception as e:
        logger.warning('earn_signals: milestone check error for %s: %s', instance.customer, e)
