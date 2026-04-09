# api/djoyalty/services/earn/EarnRuleEngine.py
import logging
from decimal import Decimal
from ...models.earn_rules import EarnRule, EarnTransaction
from ...utils import get_tier_multiplier

logger = logging.getLogger(__name__)

class EarnRuleEngine:
    @staticmethod
    def get_applicable_rules(customer, trigger: str, tenant=None):
        tier_name = 'bronze'
        ut = customer.current_tier
        if ut and ut.tier:
            tier_name = ut.tier.name
        rules = EarnRule.active.filter(trigger=trigger).filter(
            tenant=tenant or customer.tenant
        )
        applicable = []
        for rule in rules:
            if rule.applicable_tiers and tier_name not in rule.applicable_tiers:
                continue
            applicable.append(rule)
        return sorted(applicable, key=lambda r: -r.priority)

    @staticmethod
    def calculate_points(customer, spend_amount: Decimal, trigger: str, tenant=None) -> Decimal:
        rules = EarnRuleEngine.get_applicable_rules(customer, trigger, tenant=tenant)
        if not rules:
            return Decimal('0')
        rule = rules[0]
        if spend_amount < rule.min_spend:
            return Decimal('0')
        ut = customer.current_tier
        tier_name = ut.tier.name if ut and ut.tier else 'bronze'
        multiplier = get_tier_multiplier(tier_name)
        tier_mult_obj = rule.tier_multipliers.filter(tier__name=tier_name).first()
        if tier_mult_obj:
            multiplier = tier_mult_obj.multiplier
        if rule.rule_type == 'fixed':
            points = rule.points_value
        elif rule.rule_type == 'percentage':
            points = spend_amount * (rule.points_value / 100)
        elif rule.rule_type == 'multiplier':
            points = spend_amount * rule.multiplier * multiplier
        else:
            points = spend_amount * multiplier
        if rule.max_earn_per_txn:
            points = min(points, rule.max_earn_per_txn)
        return points.quantize(Decimal('0.01'))
