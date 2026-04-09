# api/djoyalty/services/earn/EarnRuleEvaluator.py
import logging
from decimal import Decimal
from .EarnRuleEngine import EarnRuleEngine
from ..points.PointsEngine import PointsEngine
from ...models.earn_rules import EarnTransaction
from ...choices import LEDGER_SOURCE_PURCHASE

logger = logging.getLogger(__name__)

class EarnRuleEvaluator:
    @staticmethod
    def evaluate_and_earn(customer, spend_amount: Decimal, trigger: str = 'purchase', txn=None, tenant=None) -> Decimal:
        points = EarnRuleEngine.calculate_points(customer, spend_amount, trigger, tenant=tenant)
        if points > 0:
            PointsEngine.process_earn(customer, spend_amount, txn=txn, tenant=tenant, source=LEDGER_SOURCE_PURCHASE)
            EarnTransaction.objects.create(
                tenant=tenant or customer.tenant,
                customer=customer, points_earned=points, spend_amount=spend_amount,
            )
        return points
