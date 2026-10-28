# api/djoyalty/promotion_engine.py
"""
Djoyalty Promotion Engine -- Talon.One style rule-based promotions।
Configure complex earn/redeem rules without code changes।
Rules: conditions + effects। All evaluated in real-time।

World reference: Talon.One rule engine, Voucherify rule builder।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger(__name__)


class PromotionCondition:
    """A single condition that must be met for a promotion to apply।"""

    OPERATORS = {
        'eq':  lambda a, b: a == b,
        'neq': lambda a, b: a != b,
        'gt':  lambda a, b: a > b,
        'gte': lambda a, b: a >= b,
        'lt':  lambda a, b: a < b,
        'lte': lambda a, b: a <= b,
        'in':  lambda a, b: a in b,
        'nin': lambda a, b: a not in b,
        'contains': lambda a, b: b in str(a),
    }

    def __init__(self, attribute: str, operator: str, value):
        """
        attribute: what to check -- 'customer.tier', 'order.amount', 'product.category'
        operator: 'eq', 'gt', 'gte', 'lt', 'lte', 'in', 'contains'
        value: value to compare against
        """
        self.attribute = attribute
        self.operator = operator
        self.value = value

    def evaluate(self, context: dict) -> bool:
        """Evaluate condition against context।"""
        try:
            actual = self._resolve_attribute(context, self.attribute)
            fn = self.OPERATORS.get(self.operator)
            if not fn:
                return False
            return fn(actual, self.value)
        except Exception as e:
            logger.debug('PromotionCondition.evaluate error [%s %s %s]: %s',
                         self.attribute, self.operator, self.value, e)
            return False

    @staticmethod
    def _resolve_attribute(context: dict, attribute: str):
        """Resolve nested attribute like 'customer.tier.rank'."""
        parts = attribute.split('.')
        val = context
        for part in parts:
            if isinstance(val, dict):
                val = val.get(part)
            else:
                val = getattr(val, part, None)
            if val is None:
                return None
        return val


class PromotionEffect:
    """The effect of a promotion -- what bonus to apply।"""

    def __init__(self, effect_type: str, value):
        """
        effect_type: 'bonus_points', 'multiply_points', 'free_item', 'discount_pct', 'discount_fixed'
        value: amount or multiplier
        """
        self.effect_type = effect_type
        self.value = value

    def apply(self, base_points: Decimal, order_amount: Decimal) -> dict:
        """Apply the effect and return result।"""
        if self.effect_type == 'bonus_points':
            return {'bonus_points': Decimal(str(self.value))}

        elif self.effect_type == 'multiply_points':
            multiplier = Decimal(str(self.value))
            return {'bonus_points': base_points * (multiplier - 1)}  # Extra points on top

        elif self.effect_type == 'discount_pct':
            discount = (order_amount * Decimal(str(self.value)) / 100).quantize(Decimal('0.01'))
            return {'discount': discount}

        elif self.effect_type == 'discount_fixed':
            return {'discount': Decimal(str(self.value))}

        elif self.effect_type == 'points_pct_of_order':
            # Points = percentage of order value
            return {'bonus_points': (order_amount * Decimal(str(self.value)) / 100).quantize(Decimal('1'))}

        return {}


class PromotionRule:
    """A complete promotion rule: conditions + effect + priority।"""

    def __init__(self, name: str, conditions: list, effect: PromotionEffect,
                  priority: int = 0, stackable: bool = True):
        self.name = name
        self.conditions = conditions  # List[PromotionCondition]
        self.effect = effect
        self.priority = priority
        self.stackable = stackable

    def matches(self, context: dict) -> bool:
        """Check if all conditions are met।"""
        return all(c.evaluate(context) for c in self.conditions)

    def apply(self, base_points: Decimal, order_amount: Decimal) -> dict:
        """Apply the effect।"""
        return self.effect.apply(base_points, order_amount)


class PromotionEngine:
    """
    Real-time promotion rule engine।
    Evaluates all active rules against checkout context,
    applies effects in priority order।

    Usage:
        engine = PromotionEngine()
        result = engine.evaluate(
            customer=customer,
            order_amount=Decimal('1500'),
            base_points=Decimal('1500'),
            context={'product_category': 'electronics', 'store_id': 'STORE1'},
        )
        total_points = result['total_points']
        discount = result['total_discount']
    """

    @staticmethod
    def build_context(customer, order_amount: Decimal, items: list = None,
                       extra: dict = None) -> dict:
        """Build evaluation context from customer + order data।"""
        from .selectors import get_points_balance, get_current_tier

        tier = get_current_tier(customer)
        balance = get_points_balance(customer)

        ctx = {
            'customer': {
                'id': customer.id,
                'code': customer.code,
                'tier': tier.name.lower() if tier else 'bronze',
                'tier_rank': tier.rank if tier else 0,
                'balance': float(balance),
                'is_verified': getattr(customer, 'is_verified', True),
            },
            'order': {
                'amount': float(order_amount),
                'items': items or [],
                'item_count': len(items) if items else 0,
            },
        }
        if extra:
            ctx.update(extra)
        return ctx

    @staticmethod
    def get_active_rules(tenant=None) -> list:
        """
        Get active promotion rules from DB।
        Rules stored as JSON in LoyaltyCampaign.rules_config।
        """
        rules = []
        try:
            from .models.campaigns import LoyaltyCampaign
            from django.utils import timezone
            from django.db.models import Q

            now = timezone.now()
            campaigns = LoyaltyCampaign.objects.filter(
                status='active',
                campaign_type__in=['bonus_points', 'multiplier', 'discount'],
            ).filter(
                Q(start_date__isnull=True) | Q(start_date__lte=now)
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=now)
            )

            for campaign in campaigns:
                rule_config = getattr(campaign, 'rules_config', None) or {}
                if not rule_config:
                    continue

                conditions = [
                    PromotionCondition(c['attribute'], c['operator'], c['value'])
                    for c in rule_config.get('conditions', [])
                ]

                effect_cfg = rule_config.get('effect', {})
                if effect_cfg:
                    effect = PromotionEffect(
                        effect_cfg.get('type', 'bonus_points'),
                        effect_cfg.get('value', 0),
                    )
                    rule = PromotionRule(
                        name=campaign.name,
                        conditions=conditions,
                        effect=effect,
                        priority=rule_config.get('priority', 0),
                        stackable=rule_config.get('stackable', True),
                    )
                    rules.append(rule)
        except Exception as e:
            logger.debug('PromotionEngine.get_active_rules error: %s', e)

        return sorted(rules, key=lambda r: r.priority, reverse=True)

    @staticmethod
    def evaluate(customer, order_amount: Decimal, base_points: Decimal,
                  items: list = None, extra: dict = None,
                  tenant=None) -> dict:
        """
        Evaluate all active promotion rules against the order।
        Returns: {
            'bonus_points': Decimal,
            'total_points': Decimal,
            'total_discount': Decimal,
            'applied_rules': list of rule names,
        }
        """
        context = PromotionEngine.build_context(customer, order_amount, items, extra)
        rules = PromotionEngine.get_active_rules(tenant)

        bonus_points = Decimal('0')
        total_discount = Decimal('0')
        applied_rules = []
        non_stackable_applied = False

        for rule in rules:
            if non_stackable_applied and not rule.stackable:
                continue  # Skip non-stackable rules if one already applied

            if rule.matches(context):
                effect_result = rule.apply(base_points, order_amount)
                bonus_points += effect_result.get('bonus_points', Decimal('0'))
                total_discount += effect_result.get('discount', Decimal('0'))
                applied_rules.append(rule.name)

                if not rule.stackable:
                    non_stackable_applied = True

                logger.debug('PromotionEngine: rule "%s" matched for %s',
                             rule.name, customer.code)

        return {
            'base_points': base_points,
            'bonus_points': bonus_points,
            'total_points': base_points + bonus_points,
            'total_discount': total_discount,
            'applied_rules': applied_rules,
            'rules_evaluated': len(rules),
        }
