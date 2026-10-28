# api/djoyalty/domain_events.py
"""
Djoyalty Domain Events -- All loyalty event dataclass definitions।
Used by EventBus, signals, and integration layer।

FIX: Previously named events.py -- conflicts with the events/ package folder।
Python resolves the events/ package over events.py, making this file
unreachable. Renamed to domain_events.py।

Migration:
    Old: from djoyalty.events import PointsEarnedEvent
    New: from djoyalty.domain_events import PointsEarnedEvent

For backwards compatibility, events/__init__.py re-exports from here।
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from django.utils import timezone


@dataclass
class LoyaltyEvent:
    """Base loyalty domain event।"""
    event_type: str
    customer_id: Optional[int] = None
    tenant_id: Optional[int] = None
    data: dict = field(default_factory=dict)
    occurred_at: str = field(default_factory=lambda: timezone.now().isoformat())

    def to_dict(self) -> dict:
        return {
            'event_type': self.event_type,
            'customer_id': self.customer_id,
            'tenant_id': self.tenant_id,
            'data': self.data,
            'occurred_at': self.occurred_at,
        }


@dataclass
class PointsEarnedEvent(LoyaltyEvent):
    event_type: str = 'points.earned'
    points: Decimal = Decimal('0')
    new_balance: Decimal = Decimal('0')
    source: str = 'purchase'
    reference_id: str = ''


@dataclass
class PointsRedeemedEvent(LoyaltyEvent):
    event_type: str = 'points.redeemed'
    points: Decimal = Decimal('0')
    reward_type: str = ''


@dataclass
class PointsExpiredEvent(LoyaltyEvent):
    event_type: str = 'points.expired'
    points: Decimal = Decimal('0')


@dataclass
class TierUpgradedEvent(LoyaltyEvent):
    event_type: str = 'tier.upgraded'
    old_tier: str = ''
    new_tier: str = ''


@dataclass
class TierDowngradedEvent(LoyaltyEvent):
    event_type: str = 'tier.downgraded'
    old_tier: str = ''
    new_tier: str = ''


@dataclass
class BadgeUnlockedEvent(LoyaltyEvent):
    event_type: str = 'badge.unlocked'
    badge_name: str = ''
    badge_icon: str = '🏅'


@dataclass
class VoucherGeneratedEvent(LoyaltyEvent):
    event_type: str = 'voucher.generated'
    code: str = ''
    discount: str = ''


@dataclass
class CashoutCompletedEvent(LoyaltyEvent):
    event_type: str = 'cashout.completed'
    amount: Decimal = Decimal('0')
    method: str = ''
    reference: str = ''


@dataclass
class OfferCompletedEvent(LoyaltyEvent):
    event_type: str = 'offer.completed'
    offer_id: int = 0
    points_awarded: Decimal = Decimal('0')
    payout_usd: Decimal = Decimal('0')


@dataclass
class ReferralConvertedEvent(LoyaltyEvent):
    event_type: str = 'referral.conversion'
    referral_code: str = ''
    referred_customer_id: Optional[int] = None
    referrer_points: Decimal = Decimal('0')


@dataclass
class ChurnAlertEvent(LoyaltyEvent):
    event_type: str = 'ai.churn_alert'
    risk_level: str = 'medium'
    probability: Decimal = Decimal('0')


@dataclass
class FamilyPointsPooledEvent(LoyaltyEvent):
    event_type: str = 'family.points_pooled'
    family_account_id: int = 0
    contributing_member_id: Optional[int] = None
    points_contributed: Decimal = Decimal('0')


@dataclass
class EcoActionCompletedEvent(LoyaltyEvent):
    event_type: str = 'eco.action_completed'
    action_type: str = ''
    co2_saved_kg: Decimal = Decimal('0')
    points_awarded: Decimal = Decimal('0')


@dataclass
class GamificationSpinEvent(LoyaltyEvent):
    event_type: str = 'gamification.spin'
    wheel_id: int = 0
    prize_type: str = ''
    points_awarded: Decimal = Decimal('0')


# ─── Event Factory ─────────────────────────────────────────────────────────────

class EventFactory:
    """Create typed loyalty events from raw data।"""

    _registry = {
        'points.earned':          PointsEarnedEvent,
        'points.redeemed':        PointsRedeemedEvent,
        'points.expired':         PointsExpiredEvent,
        'tier.upgraded':          TierUpgradedEvent,
        'tier.downgraded':        TierDowngradedEvent,
        'badge.unlocked':         BadgeUnlockedEvent,
        'voucher.generated':      VoucherGeneratedEvent,
        'cashout.completed':      CashoutCompletedEvent,
        'offer.completed':        OfferCompletedEvent,
        'referral.conversion':    ReferralConvertedEvent,
        'ai.churn_alert':         ChurnAlertEvent,
        'family.points_pooled':   FamilyPointsPooledEvent,
        'eco.action_completed':   EcoActionCompletedEvent,
        'gamification.spin':      GamificationSpinEvent,
    }

    @classmethod
    def create(cls, event_type: str, **kwargs) -> LoyaltyEvent:
        event_cls = cls._registry.get(event_type, LoyaltyEvent)
        return event_cls(event_type=event_type, **kwargs)

    @classmethod
    def register(cls, event_type: str, event_class):
        """Register a custom event type (for plugins/extensions)।"""
        cls._registry[event_type] = event_class
