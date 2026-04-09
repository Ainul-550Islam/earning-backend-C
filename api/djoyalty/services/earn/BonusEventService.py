# api/djoyalty/services/earn/BonusEventService.py
import logging
from decimal import Decimal
from django.db import transaction
from ...models.earn_rules import BonusEvent
from ...models.points import LoyaltyPoints, PointsLedger
from ...choices import LEDGER_CREDIT, LEDGER_SOURCE_BONUS

logger = logging.getLogger(__name__)

class BonusEventService:
    @staticmethod
    @transaction.atomic
    def award_bonus(customer, points: Decimal, reason: str, triggered_by: str = None, tenant=None) -> BonusEvent:
        lp, _ = LoyaltyPoints.objects.get_or_create(
            customer=customer,
            defaults={'tenant': tenant or customer.tenant, 'balance': Decimal('0')},
        )
        lp.credit(points)
        bonus = BonusEvent.objects.create(
            tenant=tenant or customer.tenant,
            customer=customer, points=points, reason=reason, triggered_by=triggered_by,
        )
        PointsLedger.objects.create(
            tenant=tenant or customer.tenant, customer=customer,
            txn_type=LEDGER_CREDIT, source=LEDGER_SOURCE_BONUS,
            points=points, balance_after=lp.balance,
            description=f'Bonus: {reason}',
        )
        return bonus
