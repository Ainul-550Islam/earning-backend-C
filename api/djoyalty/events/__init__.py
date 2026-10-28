# api/djoyalty/events/__init__.py
"""
Djoyalty Events Package -- re-exports domain events + dispatcher।

FIX: The flat events.py was shadowed by this package (Python prefers packages).
     Now domain_events.py is the canonical source.
     This __init__.py re-exports everything from domain_events.py so that
     code doing `from djoyalty.events import PointsEarnedEvent` still works।
"""
# ── Internal package exports ─────────────────────────────────────────────────
from .loyalty_events import make_points_event, make_tier_event, make_redemption_event
from .event_dispatcher import EventDispatcher

# ── Domain event classes (from canonical source) ─────────────────────────────
from ..domain_events import (
    LoyaltyEvent,
    PointsEarnedEvent,
    PointsRedeemedEvent,
    PointsExpiredEvent,
    TierUpgradedEvent,
    TierDowngradedEvent,
    BadgeUnlockedEvent,
    VoucherGeneratedEvent,
    CashoutCompletedEvent,
    OfferCompletedEvent,
    ReferralConvertedEvent,
    ChurnAlertEvent,
    FamilyPointsPooledEvent,
    EcoActionCompletedEvent,
    GamificationSpinEvent,
    EventFactory,
)

__all__ = [
    # Dispatcher
    'EventDispatcher',
    # Factories
    'make_points_event', 'make_tier_event', 'make_redemption_event',
    'EventFactory',
    # Domain events
    'LoyaltyEvent',
    'PointsEarnedEvent',
    'PointsRedeemedEvent',
    'PointsExpiredEvent',
    'TierUpgradedEvent',
    'TierDowngradedEvent',
    'BadgeUnlockedEvent',
    'VoucherGeneratedEvent',
    'CashoutCompletedEvent',
    'OfferCompletedEvent',
    'ReferralConvertedEvent',
    'ChurnAlertEvent',
    'FamilyPointsPooledEvent',
    'EcoActionCompletedEvent',
    'GamificationSpinEvent',
]
