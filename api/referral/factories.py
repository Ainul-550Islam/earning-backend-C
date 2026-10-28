# api/referral/factories.py
# Test factories for all referral models using Factory Boy
# pip install factory-boy
# ============================================================

import factory
import random
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class UserFactory(factory.django.DjangoModelFactory):
    """Minimal user factory for referral tests."""
    class Meta:
        model = settings.AUTH_USER_MODEL
        skip_postgeneration_save = True

    username  = factory.Sequence(lambda n: f'user_{n}')
    email     = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    password  = factory.PostGenerationMethodCall('set_password', 'testpass123')
    is_active = True


class ReferralSettingsFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralSettings'

    level1_commission_rate = Decimal('10.00')
    level2_commission_rate = Decimal('5.00')
    level3_commission_rate = Decimal('2.00')
    direct_signup_bonus    = Decimal('20.00')
    referrer_signup_bonus  = Decimal('50.00')
    commission_hold_days   = 7
    is_active              = True
    max_referral_depth     = 3


class ReferralFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.Referral'

    referrer       = factory.SubFactory(UserFactory)
    referred_user  = factory.SubFactory(UserFactory)
    level          = 1
    signup_bonus_given = True
    is_suspicious  = False
    registration_ip = factory.LazyFunction(lambda: f'192.168.1.{random.randint(1,254)}')


class ReferralCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralCode'

    user       = factory.SubFactory(UserFactory)
    code       = factory.Sequence(lambda n: f'EARN{n:08d}')
    is_active  = True
    is_primary = True
    clicks     = 0
    conversions = 0


class ReferralEarningFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralEarning'

    referrer      = factory.SubFactory(UserFactory)
    referred_user = factory.SubFactory(UserFactory)
    level         = 1
    amount        = Decimal('10.00')
    commission_rate = Decimal('10.00')
    source_amount = Decimal('100.00')
    source_type   = 'task'
    status        = 'released'


class CommissionLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.CommissionLog'

    user          = factory.SubFactory(UserFactory)
    referred_user = factory.SubFactory(UserFactory)
    action_type   = 'task'
    amount        = Decimal('10.00')
    base_amount   = Decimal('100.00')
    commission_rate = Decimal('0.1000')
    level         = 1
    status        = 'pending'


class ReferralCampaignFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralCampaign'

    name             = factory.Sequence(lambda n: f'Campaign {n}')
    slug             = factory.Sequence(lambda n: f'campaign-{n}')
    bonus_multiplier = Decimal('1.5')
    start_date       = factory.LazyFunction(timezone.now)
    end_date         = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
    is_active        = True
    is_featured      = False


class ReferralFraudRuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralFraudRule'

    rule_type          = factory.Sequence(lambda n: f'rule_{n}')
    name               = factory.Sequence(lambda n: f'Fraud Rule {n}')
    action             = 'flag'
    threshold          = 3
    time_window_minutes = 60
    fraud_score_points = 20
    is_active          = True


class SuspiciousReferralFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.SuspiciousReferral'

    referral    = factory.SubFactory(ReferralFactory)
    fraud_score = 45
    flags       = factory.LazyFunction(dict)
    evidence    = factory.LazyFunction(dict)
    status      = 'pending'


class TopReferrerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.TopReferrer'

    user             = factory.SubFactory(UserFactory)
    date             = factory.LazyFunction(lambda: timezone.now().date())
    period           = 'daily'
    rank             = factory.Sequence(lambda n: n + 1)
    referral_count   = factory.LazyFunction(lambda: random.randint(1, 50))
    commission_earned = factory.LazyFunction(lambda: Decimal(str(random.uniform(10, 1000))))
    rank_change      = 0


class ReferralLTVFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralLTV'

    user             = factory.SubFactory(UserFactory)
    referred_by      = factory.SubFactory(UserFactory)
    lifetime_value   = Decimal('500.00')
    total_user_earnings = Decimal('1000.00')
    task_count       = 10
    days_active      = 30
    churn_risk       = 'low'
    value_category   = 'mid_value'


class ReferralQRCodeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.ReferralQRCode'

    referral_code    = factory.SubFactory(ReferralCodeFactory)
    qr_image_data    = ''
    scan_count       = 0
    conversions      = 0
    foreground_color = '#000000'
    background_color = '#FFFFFF'


class UserCommissionTierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.UserCommissionTier'

    user                    = factory.SubFactory(UserFactory)
    effective_l1_rate       = Decimal('10.00')
    effective_l2_rate       = Decimal('5.00')
    effective_l3_rate       = Decimal('2.00')
    total_active_referrals  = 0
    total_commission_earned = Decimal('0.00')


class AffiliateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = 'referral.AffiliateProfile'

    user         = factory.SubFactory(UserFactory)
    display_name = factory.LazyAttribute(lambda o: o.user.username)
    traffic_type = 'social'
    status       = 'active'
    is_public    = True


# ── Batch Helper ──────────────────────────────────────────────────────────────

def create_referral_network(root_user=None, depth: int = 3, width: int = 3) -> dict:
    """
    Create a referral network for testing.
    Returns dict with all created objects.
    """
    if root_user is None:
        root_user = UserFactory()

    created = {'root': root_user, 'l1': [], 'l2': [], 'l3': []}

    for _ in range(width):
        l1_user = UserFactory()
        ReferralFactory(referrer=root_user, referred_user=l1_user)
        created['l1'].append(l1_user)

        if depth >= 2:
            for __ in range(width):
                l2_user = UserFactory()
                ReferralFactory(referrer=l1_user, referred_user=l2_user)
                created['l2'].append(l2_user)

                if depth >= 3:
                    for ___ in range(width):
                        l3_user = UserFactory()
                        ReferralFactory(referrer=l2_user, referred_user=l3_user)
                        created['l3'].append(l3_user)

    return created