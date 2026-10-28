# api/djoyalty/events/loyalty_events.py
"""
Djoyalty -- LoyaltyEvent data class।
Internal event bus এর জন্য standard event object।
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Any
from django.utils import timezone

logger = logging.getLogger(__name__)


@dataclass
class LoyaltyEvent:
    """
    Standard loyalty event।
    Webhook dispatcher, signal handlers, সব এই format ব্যবহার করে।
    """
    event_type: str
    data: dict = field(default_factory=dict)
    customer: Optional[Any] = None
    tenant: Optional[Any] = None
    timestamp: Optional[str] = None
    source: str = 'system'
    version: str = '1.0'

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = timezone.now().isoformat()

    def to_dict(self) -> dict:
        """Webhook payload এর জন্য dict।"""
        return {
            'event': self.event_type,
            'timestamp': self.timestamp,
            'version': self.version,
            'source': self.source,
            'customer_code': self.customer.code if self.customer else None,
            'tenant_id': getattr(self.tenant, 'id', None) if self.tenant else None,
            'data': self.data,
        }

    def __str__(self):
        return f'LoyaltyEvent(type={self.event_type}, customer={self.customer})'


# ─── Event Type Constants ───

POINTS_EARNED = 'points.earned'
POINTS_BURNED = 'points.burned'
POINTS_EXPIRED = 'points.expired'
POINTS_TRANSFERRED = 'points.transferred'
POINTS_ADJUSTED = 'points.adjusted'

TIER_CHANGED = 'tier.changed'
TIER_UPGRADED = 'tier.upgraded'
TIER_DOWNGRADED = 'tier.downgraded'

BADGE_UNLOCKED = 'badge.unlocked'
STREAK_MILESTONE = 'streak.milestone'
CHALLENGE_COMPLETED = 'challenge.completed'
MILESTONE_ACHIEVED = 'milestone.achieved'

REDEMPTION_CREATED = 'redemption.created'
REDEMPTION_STATUS_CHANGED = 'redemption.status_changed'
VOUCHER_USED = 'voucher.used'
GIFT_CARD_REDEEMED = 'gift_card.redeemed'

CAMPAIGN_JOINED = 'campaign.joined'
CUSTOMER_REGISTERED = 'customer.registered'
FRAUD_DETECTED = 'fraud.detected'
SUBSCRIPTION_RENEWED = 'subscription.renewed'


# ─── Factory Functions ───

def make_points_event(event_type: str, customer, points, balance_after, source='purchase', tenant=None) -> LoyaltyEvent:
    from decimal import Decimal
    return LoyaltyEvent(
        event_type=event_type,
        customer=customer,
        tenant=tenant,
        data={
            'points': str(points),
            'balance_after': str(balance_after),
            'source': source,
        },
    )


def make_tier_event(customer, from_tier, to_tier, change_type, tenant=None) -> LoyaltyEvent:
    event_type = TIER_UPGRADED if change_type == 'upgrade' else (
        TIER_DOWNGRADED if change_type == 'downgrade' else TIER_CHANGED
    )
    return LoyaltyEvent(
        event_type=event_type,
        customer=customer,
        tenant=tenant,
        data={
            'from_tier': from_tier,
            'to_tier': to_tier,
            'change_type': change_type,
        },
    )


def make_redemption_event(customer, redemption_request, tenant=None) -> LoyaltyEvent:
    return LoyaltyEvent(
        event_type=REDEMPTION_STATUS_CHANGED,
        customer=customer,
        tenant=tenant,
        data={
            'redemption_id': redemption_request.id,
            'status': redemption_request.status,
            'points_used': str(redemption_request.points_used),
            'redemption_type': redemption_request.redemption_type,
        },
    )
