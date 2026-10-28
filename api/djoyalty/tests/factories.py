# api/djoyalty/tests/factories.py
"""
Model Factories for Testing -- UPDATED।
Added factories for all new models:
  - make_cashout_rate, make_bank_account, make_mobile_wallet, make_cashout_request
  - make_spin_wheel, make_lottery, make_scratch_card, make_quiz
  - make_ai_profile, make_personalized_offer, make_churn_alert
  - make_family_account, make_eco_action, make_charity_cause
  - make_tenant, make_system_config
"""
import random
import string
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta


# ─── Core Factories (unchanged) ───────────────────────────────────────────────

def make_customer(code=None, **kwargs):
    from djoyalty.models.core import Customer
    code = code or ''.join(random.choices(string.ascii_uppercase, k=8))
    defaults = {
        'code': code, 'firstname': 'Test', 'lastname': 'User',
        'email': f'{code.lower()}@example.com', 'newsletter': True, 'is_active': True,
    }
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
    lp, _ = LoyaltyPoints.objects.get_or_create(
        customer=customer,
        defaults={'balance': balance, **kwargs},
    )
    return lp


def make_tier(name='bronze', **kwargs):
    from djoyalty.models.tiers import LoyaltyTier
    defaults = {
        'label': name.title(), 'min_points': Decimal('0'),
        'earn_multiplier': Decimal('1.0'), 'color': '#888888',
        'icon': '⭐', 'rank': 1, 'is_active': True,
    }
    defaults.update(kwargs)
    tier, _ = LoyaltyTier.objects.get_or_create(name=name, defaults=defaults)
    return tier


def make_earn_rule(name=None, **kwargs):
    from djoyalty.models.earn_rules import EarnRule
    name = name or 'Test Rule'
    defaults = {
        'rule_type': 'percentage', 'trigger': 'purchase',
        'points_value': Decimal('1'), 'multiplier': Decimal('1'),
        'is_active': True, 'priority': 0,
    }
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
    name = name or 'Test Campaign'
    defaults = {
        'campaign_type': 'bonus_points', 'status': 'active',
        'multiplier': Decimal('2'), 'bonus_points': Decimal('50'),
        'start_date': timezone.now() - timedelta(days=1),
        'end_date':   timezone.now() + timedelta(days=30),
    }
    defaults.update(kwargs)
    return LoyaltyCampaign.objects.create(name=name, **defaults)


# ─── NEW: Cashout Factories ───────────────────────────────────────────────────

def make_cashout_rate(cashout_method='mobile_wallet', points_per_unit=Decimal('10'), **kwargs):
    from djoyalty.models.cashout import CashoutRate
    defaults = {
        'cashout_method':             cashout_method,
        'points_per_unit':            points_per_unit,
        'min_cashout_points':         Decimal('100'),
        'max_cashout_points_per_day': Decimal('5000'),
        'processing_fee_percent':     Decimal('0'),
        'is_active':                  True,
    }
    defaults.update(kwargs)
    rate, _ = CashoutRate.objects.get_or_create(
        cashout_method=cashout_method, defaults=defaults
    )
    return rate


def make_bank_account(customer, account_number=None, **kwargs):
    from djoyalty.models.cashout import CustomerBankAccount
    account_number = account_number or ''.join(random.choices(string.digits, k=10))
    defaults = {
        'bank_name':          'Test Bank',
        'account_number':     account_number,
        'account_holder_name': customer.firstname,
        'is_primary':         True,
        'is_active':          True,
    }
    defaults.update(kwargs)
    return CustomerBankAccount.objects.create(customer=customer, **defaults)


def make_mobile_wallet(customer, provider='bkash', phone=None, **kwargs):
    from djoyalty.models.cashout import CustomerMobileWallet
    phone = phone or f'017{random.randint(10000000, 99999999)}'
    defaults = {
        'wallet_provider': provider,
        'phone_number':    phone,
        'account_name':    customer.firstname,
        'is_primary':      True,
        'is_active':       True,
    }
    defaults.update(kwargs)
    return CustomerMobileWallet.objects.create(customer=customer, **defaults)


def make_cashout_request(customer, points=Decimal('500'), method='mobile_wallet', **kwargs):
    import uuid
    from djoyalty.models.cashout import CashoutRequest
    defaults = {
        'points_to_redeem': points,
        'cash_amount':      points / Decimal('10'),
        'conversion_rate':  Decimal('0.1'),
        'currency':         'BDT',
        'cashout_method':   method,
        'status':           'pending',
        'reference':        f'CO-{uuid.uuid4().hex[:8].upper()}',
    }
    defaults.update(kwargs)
    return CashoutRequest.objects.create(customer=customer, **defaults)


# ─── NEW: Gamification Factories ─────────────────────────────────────────────

def make_spin_wheel(name='Test Wheel', **kwargs):
    from djoyalty.models.gamification import SpinWheelConfig, SpinWheelSlice
    defaults = {
        'trigger': 'manual', 'spins_per_day': 3, 'is_active': True,
    }
    defaults.update(kwargs)
    wheel = SpinWheelConfig.objects.create(name=name, **defaults)
    # Add one default slice
    SpinWheelSlice.objects.create(
        wheel=wheel, label='100 Points', prize_type='points',
        points_value=Decimal('100'), probability=Decimal('100'),
        color='#FFD700', sort_order=1,
    )
    return wheel


def make_lottery(name='Test Lottery', status='open', **kwargs):
    from djoyalty.models.gamification import LotteryDraw
    defaults = {
        'ticket_cost_points':     Decimal('50'),
        'max_tickets_per_customer': 5,
        'prize_description':      'Grand Prize',
        'prize_points_value':     Decimal('10000'),
        'status':                 status,
        'draw_date':              timezone.now() + timedelta(days=7),
        'start_date':             timezone.now(),
        'total_tickets_sold':     0,
    }
    defaults.update(kwargs)
    return LotteryDraw.objects.create(name=name, **defaults)


def make_scratch_card(customer, code=None, status='unscratched', **kwargs):
    from djoyalty.models.gamification import ScratchCard
    code = code or f'SCR-{random.randint(100000, 999999)}'
    defaults = {
        'issued_for':   'purchase',
        'status':       status,
        'prize_type':   'points',
        'points_value': Decimal('100'),
    }
    defaults.update(kwargs)
    return ScratchCard.objects.create(customer=customer, code=code, **defaults)


def make_quiz(name='Test Quiz', **kwargs):
    from djoyalty.models.gamification import QuizReward
    defaults = {
        'points_reward':     Decimal('200'),
        'pass_score':        70,
        'max_attempts':      3,
        'time_limit_minutes': 10,
        'is_active':         True,
    }
    defaults.update(kwargs)
    return QuizReward.objects.create(title=name, **defaults)


def make_leaderboard_season(name='Test Season', status='active', **kwargs):
    from djoyalty.models.gamification import LeaderboardSeason
    defaults = {
        'season_type':               'monthly',
        'start_date':                timezone.now(),
        'end_date':                  timezone.now() + timedelta(days=30),
        'status':                    status,
        'first_prize_points':        Decimal('5000'),
        'second_prize_points':       Decimal('2000'),
        'third_prize_points':        Decimal('1000'),
        'participation_prize_points': Decimal('100'),
        'metric':                    'points_earned',
    }
    defaults.update(kwargs)
    return LeaderboardSeason.objects.create(name=name, **defaults)


# ─── NEW: AI Personalization Factories ───────────────────────────────────────

def make_ai_profile(customer, rfm_segment='loyal', churn_risk='low', **kwargs):
    from djoyalty.models.ai_personalization import CustomerAIProfile
    risk_to_prob = {'low': '0.10', 'medium': '0.45', 'high': '0.75', 'critical': '0.92'}
    defaults = {
        'recency_score':    Decimal('4'),
        'frequency_score':  Decimal('3'),
        'monetary_score':   Decimal('4'),
        'rfm_total':        Decimal('11'),
        'rfm_segment':      rfm_segment,
        'churn_probability': Decimal(risk_to_prob.get(churn_risk, '0.10')),
        'churn_risk_level': churn_risk,
        'predicted_clv_30d': Decimal('300'),
        'predicted_clv_90d': Decimal('800'),
        'predicted_clv_1y':  Decimal('3000'),
        'actual_clv':        Decimal('2000'),
        'engagement_score':  Decimal('75'),
        'model_version':     'v2',
    }
    defaults.update(kwargs)
    profile, _ = CustomerAIProfile.objects.get_or_create(
        customer=customer, defaults=defaults
    )
    return profile


def make_personalized_offer(customer, offer_type='bonus_points', **kwargs):
    from djoyalty.models.ai_personalization import PersonalizedOffer
    defaults = {
        'title':            'Special Offer',
        'description':      'Earn bonus points!',
        'offer_type':       offer_type,
        'points_bonus':     Decimal('100'),
        'multiplier':       Decimal('1'),
        'ai_generated':     True,
        'confidence_score': Decimal('0.85'),
        'trigger':          'purchase',
        'status':           'active',
        'valid_until':      timezone.now() + timedelta(days=7),
    }
    defaults.update(kwargs)
    return PersonalizedOffer.objects.create(customer=customer, **defaults)


def make_churn_alert(customer, risk_level='high', **kwargs):
    from djoyalty.models.ai_personalization import ChurnAlert
    defaults = {
        'risk_level':        risk_level,
        'churn_probability': Decimal('0.75'),
        'signals':           {'days_since_purchase': 45},
        'is_resolved':       False,
        'detected_at':       timezone.now(),
    }
    defaults.update(kwargs)
    return ChurnAlert.objects.create(customer=customer, **defaults)


# ─── NEW: Eco / Family / Charity Factories ────────────────────────────────────

def make_family_account(owner, name='Test Family', **kwargs):
    from djoyalty.models.family_eco import FamilyAccount
    import uuid
    defaults = {
        'account_code': f'FAM-{uuid.uuid4().hex[:6].upper()}',
        'pool_points':  True,
        'max_members':  5,
        'is_active':    True,
    }
    defaults.update(kwargs)
    return FamilyAccount.objects.create(owner=owner, name=name, **defaults)


def make_eco_action(name='Recycling', action_type='recycling', **kwargs):
    from djoyalty.models.family_eco import EcoAction
    defaults = {
        'points_reward':             Decimal('50'),
        'co2_saved_kg':              Decimal('0.5'),
        'max_per_customer_per_day':  3,
        'is_active':                 True,
    }
    defaults.update(kwargs)
    action, _ = EcoAction.objects.get_or_create(name=name, defaults={**defaults, 'action_type': action_type})
    return action


def make_charity_cause(name='Test Charity', **kwargs):
    from djoyalty.models.family_eco import CharityCause
    defaults = {
        'category':                'education',
        'points_per_donation_unit': Decimal('10'),
        'min_donation_points':     Decimal('100'),
        'total_points_donated':    Decimal('0'),
        'total_currency_donated':  Decimal('0'),
        'is_active':               True,
    }
    defaults.update(kwargs)
    cause, _ = CharityCause.objects.get_or_create(name=name, defaults=defaults)
    return cause


# ─── NEW: Admin / Tenant Factories ───────────────────────────────────────────

def make_tenant(name=None, **kwargs):
    from djoyalty.models.core import Tenant
    import secrets
    name = name or f'Tenant-{random.randint(1000, 9999)}'
    slug = name.lower().replace(' ', '-')
    defaults = {
        'slug':    slug,
        'plan':    'starter',
        'api_key': secrets.token_urlsafe(16),
        'is_active': True,
    }
    defaults.update(kwargs)
    tenant, _ = Tenant.objects.get_or_create(name=name, defaults=defaults)
    return tenant


def make_system_config(tenant=None, key='test_config', value='test_value', **kwargs):
    from djoyalty.models.audit import SystemConfig
    defaults = {
        'value':       value,
        'value_type':  'string',
        'is_sensitive': False,
    }
    defaults.update(kwargs)
    cfg, _ = SystemConfig.objects.get_or_create(
        tenant=tenant, key=key, defaults=defaults
    )
    return cfg
