# api/djoyalty/webhooks/webhook_payloads.py
"""
Webhook payload builders — outbound webhook data structure।
"""
from ..events.loyalty_events import LoyaltyEvent


# Supported webhook event types
WEBHOOK_EVENTS = [
    'points.earned',
    'points.burned',
    'points.expired',
    'points.transferred',
    'tier.changed',
    'tier.upgraded',
    'tier.downgraded',
    'badge.unlocked',
    'streak.milestone',
    'redemption.status_changed',
    'campaign.joined',
    'challenge.completed',
    'customer.registered',
    'voucher.used',
    'gift_card.redeemed',
    'fraud.detected',
    'subscription.renewed',
]


def build_payload(event: LoyaltyEvent) -> dict:
    """
    LoyaltyEvent থেকে standard webhook payload তৈরি করো।
    Structure সব integrations এর জন্য consistent।
    """
    return event.to_dict()


def build_points_earned_payload(customer, points_earned, balance_after, source='purchase') -> dict:
    """Points earned এর জন্য structured payload।"""
    return {
        'event': 'points.earned',
        'customer_code': customer.code if customer else None,
        'data': {
            'points_earned': str(points_earned),
            'balance_after': str(balance_after),
            'source': source,
        },
    }


def build_tier_changed_payload(customer, from_tier, to_tier, change_type) -> dict:
    """Tier change এর জন্য structured payload।"""
    return {
        'event': 'tier.changed',
        'customer_code': customer.code if customer else None,
        'data': {
            'from_tier': from_tier,
            'to_tier': to_tier,
            'change_type': change_type,
        },
    }


def build_redemption_payload(customer, redemption_request) -> dict:
    """Redemption status change এর জন্য payload।"""
    return {
        'event': 'redemption.status_changed',
        'customer_code': customer.code if customer else None,
        'data': {
            'redemption_id': redemption_request.id,
            'status': redemption_request.status,
            'points_used': str(redemption_request.points_used),
            'redemption_type': redemption_request.redemption_type,
        },
    }


def build_badge_payload(customer, badge) -> dict:
    """Badge unlock এর জন্য payload।"""
    return {
        'event': 'badge.unlocked',
        'customer_code': customer.code if customer else None,
        'data': {
            'badge_name': badge.name,
            'badge_icon': badge.icon,
            'points_reward': str(badge.points_reward),
        },
    }


def build_voucher_used_payload(customer, voucher, redemption) -> dict:
    """Voucher use এর জন্য payload।"""
    return {
        'event': 'voucher.used',
        'customer_code': customer.code if customer else None,
        'data': {
            'voucher_code': voucher.code,
            'voucher_type': voucher.voucher_type,
            'discount_applied': str(redemption.discount_applied),
            'order_reference': redemption.order_reference,
        },
    }
