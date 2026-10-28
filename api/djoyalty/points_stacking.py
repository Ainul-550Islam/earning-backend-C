# api/djoyalty/points_stacking.py
"""
Djoyalty Points Stacking -- Control how earn rules and promotions stack।
Prevent or allow combining multiple earn rules at checkout।
Reference: Voucherify stacking logic, Talon.One stacking rules।
"Do not summarize or skip any logic. Provide the full code."
"""
import logging
from decimal import Decimal
from typing import List

logger = logging.getLogger(__name__)


class StackingPolicy:
    """
    Defines how points earn rules and promotions stack।
    Controls: max rules, max multiplier, exclusions।
    """

    def __init__(self,
                 allow_stacking: bool = True,
                 max_rules: int = 5,
                 max_total_multiplier: Decimal = Decimal('5'),
                 max_bonus_points: Decimal = None,
                 exclusive_rule_types: list = None):
        """
        allow_stacking: if False, only the highest-value rule applies
        max_rules: max number of rules to apply simultaneously
        max_total_multiplier: cap on total earn multiplier
        max_bonus_points: cap on total bonus points per transaction
        exclusive_rule_types: rule types that can't combine with others
        """
        self.allow_stacking = allow_stacking
        self.max_rules = max_rules
        self.max_total_multiplier = max_total_multiplier
        self.max_bonus_points = max_bonus_points
        self.exclusive_rule_types = exclusive_rule_types or []


class PointsStackingEngine:
    """
    Apply stacking policy to a set of matched earn rules/promotions।

    Usage:
        engine = PointsStackingEngine(policy=StackingPolicy(max_rules=3))
        final_points = engine.apply(
            base_points=Decimal('1000'),
            matched_rules=[rule1, rule2, rule3, rule4],
        )
    """

    def __init__(self, policy: StackingPolicy = None):
        self.policy = policy or StackingPolicy()

    def apply(self, base_points: Decimal, matched_rules: list) -> dict:
        """
        Apply stacking rules and return final points calculation।

        matched_rules: list of rule dicts with keys:
            - 'name': rule name
            - 'type': rule type (e.g. 'multiplier', 'bonus', 'campaign')
            - 'bonus_points': Decimal
            - 'multiplier': Decimal
            - 'stackable': bool

        Returns: {
            'base_points': Decimal,
            'total_bonus': Decimal,
            'final_points': Decimal,
            'applied_rules': [names],
            'excluded_rules': [names],
        }
        """
        if not matched_rules:
            return {
                'base_points': base_points,
                'total_bonus': Decimal('0'),
                'final_points': base_points,
                'applied_rules': [],
                'excluded_rules': [],
            }

        if not self.policy.allow_stacking:
            # Only apply the best single rule
            best_rule = max(
                matched_rules,
                key=lambda r: r.get('bonus_points', Decimal('0')),
            )
            bonus = best_rule.get('bonus_points', Decimal('0'))
            return {
                'base_points': base_points,
                'total_bonus': bonus,
                'final_points': base_points + bonus,
                'applied_rules': [best_rule['name']],
                'excluded_rules': [r['name'] for r in matched_rules if r != best_rule],
            }

        # Apply rules with stacking
        applied = []
        excluded = []
        total_bonus = Decimal('0')
        total_multiplier = Decimal('1')
        exclusive_applied = False

        for rule in sorted(matched_rules, key=lambda r: r.get('priority', 0), reverse=True):
            # Check if we've hit the max rules limit
            if len(applied) >= self.policy.max_rules:
                excluded.append(rule['name'])
                continue

            # Check exclusive types
            rule_type = rule.get('type', '')
            if rule_type in self.policy.exclusive_rule_types:
                if exclusive_applied:
                    excluded.append(rule['name'])
                    continue
                exclusive_applied = True

            # Check stackable flag
            if not rule.get('stackable', True) and applied:
                excluded.append(rule['name'])
                continue

            # Accumulate bonus
            rule_bonus = rule.get('bonus_points', Decimal('0'))
            rule_mult = rule.get('multiplier', Decimal('1'))

            # Check multiplier cap
            new_multiplier = total_multiplier * rule_mult
            if new_multiplier > self.policy.max_total_multiplier:
                rule_mult = Decimal('1')  # Skip multiplier but allow bonus

            total_multiplier = max(total_multiplier, rule_mult)
            total_bonus += rule_bonus
            applied.append(rule['name'])

        # Cap bonus if set
        if self.policy.max_bonus_points and total_bonus > self.policy.max_bonus_points:
            total_bonus = self.policy.max_bonus_points

        # Apply multiplier to base points
        multiplied_base = base_points * (total_multiplier - 1)  # Extra from multiplier
        final_points = base_points + multiplied_base + total_bonus

        return {
            'base_points': base_points,
            'multiplier_bonus': multiplied_base,
            'flat_bonus': total_bonus,
            'total_bonus': multiplied_base + total_bonus,
            'final_points': final_points.quantize(Decimal('0.01')),
            'applied_rules': applied,
            'excluded_rules': excluded,
            'applied_multiplier': total_multiplier,
        }


# Default engine instance
default_stacking_engine = PointsStackingEngine(
    policy=StackingPolicy(
        allow_stacking=True,
        max_rules=5,
        max_total_multiplier=Decimal('10'),
        exclusive_rule_types=['flash_sale', 'birthday'],
    )
)
