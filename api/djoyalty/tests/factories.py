# api/djoyalty/tests/factories.py
"""Model factories for testing।"""
import random
import string
from decimal import Decimal
from django.utils import timezone

def make_customer(code=None, **kwargs):
    from djoyalty.models.core import Customer
    code = code or ''.join(random.choices(string.ascii_uppercase, k=8))
    defaults = {'code': code, 'firstname': 'Test', 'lastname': 'User', 'email': f'{code.lower()}@example.com', 'newsletter': True, 'is_active': True}
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)

def make_txn(customer, value=Decimal('100'), is_discount=False, **kwargs):
    from djoyalty.models.core import Txn
    return Txn.objects.create(customer=customer, value=value, is_discount=is_discount, **kwargs)

def make_event(customer=None, action='test_action', **kwargs):
    from djoyalty.models.core import Event
    return Event.objects.create(customer=customer, action=action, **kwargs)

def make_loyalty_points(customer, balance=Decimal('100'), **kwargs):
    from djoyalty.models.points import LoyaltyPoints
    lp, _ = LoyaltyPoints.objects.get_or_create(customer=customer, defaults={'balance': balance, **kwargs})
    return lp

def make_tier(name='bronze', **kwargs):
    from djoyalty.models.tiers import LoyaltyTier
    defaults = {'label': name.title(), 'min_points': Decimal('0'), 'earn_multiplier': Decimal('1.0'), 'color': '#888888', 'icon': '⭐', 'rank': 1, 'is_active': True}
    defaults.update(kwargs)
    tier, _ = LoyaltyTier.objects.get_or_create(name=name, defaults=defaults)
    return tier

def make_earn_rule(name=None, **kwargs):
    from djoyalty.models.earn_rules import EarnRule
    name = name or 'Test Rule'
    defaults = {'rule_type': 'percentage', 'trigger': 'purchase', 'points_value': Decimal('1'), 'multiplier': Decimal('1'), 'is_active': True, 'priority': 0}
    defaults.update(kwargs)
    return EarnRule.objects.create(name=name, **defaults)

def make_voucher(customer, code=None, **kwargs):
    from djoyalty.models.redemption import Voucher
    code = code or ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
    defaults = {'voucher_type': 'percent', 'discount_value': Decimal('10'), 'status': 'active'}
    defaults.update(kwargs)
    return Voucher.objects.create(customer=customer, code=code, **defaults)

def make_campaign(name=None, **kwargs):
    from djoyalty.models.campaigns import LoyaltyCampaign
    from datetime import timedelta
    name = name or 'Test Campaign'
    defaults = {'campaign_type': 'bonus_points', 'status': 'active', 'multiplier': Decimal('2'), 'bonus_points': Decimal('50'), 'start_date': timezone.now() - timedelta(days=1), 'end_date': timezone.now() + timedelta(days=30)}
    defaults.update(kwargs)
    return LoyaltyCampaign.objects.create(name=name, **defaults)
