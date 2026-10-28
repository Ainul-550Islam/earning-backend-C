# api/djoyalty/factories.py
"""
Djoyalty Test Factories -- factory_boy factories for testing।
pip install factory-boy faker

Usage in tests:
    from djoyalty.factories import CustomerFactory, TxnFactory
    customer = CustomerFactory()
    txn = TxnFactory(customer=customer, value=500)
"""
import factory
from factory import fuzzy
from decimal import Decimal
from django.utils import timezone


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.Tenant'

    name = factory.Sequence(lambda n: f'Tenant {n}')
    is_active = True


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.Customer'

    code = factory.Sequence(lambda n: f'CUST{n:05d}')
    email = factory.LazyAttribute(lambda obj: f'{obj.code.lower()}@example.com')
    phone = factory.Sequence(lambda n: f'017{n:08d}')
    firstname = factory.Faker('first_name')
    lastname = factory.Faker('last_name')
    is_active = True
    is_verified = True
    tenant = factory.SubFactory(TenantFactory)


class LoyaltyTierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.LoyaltyTier'

    name = factory.Sequence(lambda n: ['Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond'][n % 5])
    label = factory.SelfAttribute('name')
    rank = factory.Sequence(lambda n: n + 1)
    min_points = factory.Sequence(lambda n: n * 1000)
    multiplier = Decimal('1.0')
    is_active = True


class LoyaltyPointsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.LoyaltyPoints'

    customer = factory.SubFactory(CustomerFactory)
    balance = fuzzy.FuzzyDecimal(0, 10000, precision=2)
    lifetime_earned = factory.SelfAttribute('balance')
    lifetime_redeemed = Decimal('0')


class TxnFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.Txn'

    customer = factory.SubFactory(CustomerFactory)
    value = fuzzy.FuzzyDecimal(50, 5000, precision=2)
    currency = 'BDT'
    source = 'purchase'


class PointsLedgerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.PointsLedger'

    customer = factory.SubFactory(CustomerFactory)
    txn_type = 'credit'
    source = 'purchase'
    points = fuzzy.FuzzyDecimal(1, 500, precision=2)
    balance_after = fuzzy.FuzzyDecimal(100, 10000, precision=2)


class VoucherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.Voucher'

    customer = factory.SubFactory(CustomerFactory)
    code = factory.Sequence(lambda n: f'VOUCHER{n:06d}')
    voucher_type = 'percent'
    discount_value = Decimal('10')
    status = 'active'
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + __import__('datetime').timedelta(days=30)
    )


class BadgeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.Badge'

    name = factory.Sequence(lambda n: f'Badge {n}')
    description = 'Test badge'
    icon = '🏅'
    is_active = True


class EarnRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.EarnRule'

    name = factory.Sequence(lambda n: f'Rule {n}')
    trigger = 'purchase'
    earn_type = 'per_currency_unit'
    earn_value = Decimal('1')
    is_active = True


class CampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.LoyaltyCampaign'

    name = factory.Sequence(lambda n: f'Campaign {n}')
    campaign_type = 'bonus_points'
    status = 'active'
    start_date = factory.LazyFunction(timezone.now)


class OfferWallFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.OfferWall'

    name = factory.Sequence(lambda n: f'OfferWall {n}')
    provider = 'internal'
    currency_name = 'Points'
    currency_ratio = Decimal('100')
    is_active = True


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.Offer'

    offer_wall = factory.SubFactory(OfferWallFactory)
    title = factory.Sequence(lambda n: f'Offer {n}')
    offer_type = 'app_install'
    points_reward = Decimal('50')
    status = 'active'


class ReferralLinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.ReferralLink'

    customer = factory.SubFactory(CustomerFactory)
    code = factory.Sequence(lambda n: f'REF{n:06d}')
    is_active = True


class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'djoyalty.NotificationCenter'

    customer = factory.SubFactory(CustomerFactory)
    title = 'Test Notification'
    body = 'Test notification body'
    notification_type = 'system'
    is_read = False
