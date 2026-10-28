# api/djoyalty/ab_testing.py
"""
Djoyalty A/B Testing -- Split test loyalty campaigns।
Test different earn rates, messages, reward amounts on customer segments।
"Do not summarize or skip any logic. Provide the full code."
"""
import hashlib
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class ABTestVariant:
    def __init__(self, name: str, weight: int, config: dict):
        self.name = name
        self.weight = weight  # percentage 0-100
        self.config = config  # variant-specific overrides


class LoyaltyABTest:
    """
    A/B test for loyalty programs।
    Assigns customers to variants deterministically (same customer = same variant always)।

    Usage:
        test = LoyaltyABTest('double_points_test', [
            ABTestVariant('control', 50, {'earn_multiplier': '1'}),
            ABTestVariant('treatment', 50, {'earn_multiplier': '2'}),
        ])
        variant = test.get_variant(customer)
        multiplier = Decimal(variant.config['earn_multiplier'])
    """

    def __init__(self, test_name: str, variants: list):
        self.test_name = test_name
        self.variants = variants
        assert sum(v.weight for v in variants) == 100, 'Variant weights must sum to 100'

    def get_variant(self, customer) -> ABTestVariant:
        """Deterministically assign customer to a variant।"""
        # Create hash from test name + customer code
        hash_input = f'{self.test_name}:{customer.code}'
        hash_val = int(hashlib.md5(hash_input.encode()).hexdigest(), 16) % 100

        # Assign based on cumulative weights
        cumulative = 0
        for variant in self.variants:
            cumulative += variant.weight
            if hash_val < cumulative:
                return variant

        return self.variants[-1]

    def record_exposure(self, customer, variant: ABTestVariant):
        """Record that customer was exposed to this variant।"""
        try:
            from .models.audit import AdminAuditLog
            AdminAuditLog.log(
                action=f'ab_test_exposure',
                category='campaign',
                customer=customer,
                new_value={'test': self.test_name, 'variant': variant.name},
                severity='info',
            )
        except Exception:
            pass

    def record_conversion(self, customer, variant: ABTestVariant, value: Decimal = Decimal('0')):
        """Record a conversion (e.g., redemption, purchase)।"""
        try:
            from .models.audit import AdminAuditLog
            AdminAuditLog.log(
                action=f'ab_test_conversion',
                category='campaign',
                customer=customer,
                new_value={'test': self.test_name, 'variant': variant.name,
                           'value': str(value)},
                severity='info',
            )
        except Exception:
            pass
