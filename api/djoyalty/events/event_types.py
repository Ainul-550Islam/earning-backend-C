# api/djoyalty/events/event_types.py
POINTS_EARNED = 'points.earned'
POINTS_BURNED = 'points.burned'
POINTS_EXPIRED = 'points.expired'
POINTS_TRANSFERRED = 'points.transferred'
TIER_CHANGED = 'tier.changed'
TIER_UPGRADED = 'tier.upgraded'
TIER_DOWNGRADED = 'tier.downgraded'
BADGE_UNLOCKED = 'badge.unlocked'
STREAK_MILESTONE = 'streak.milestone'
REDEMPTION_STATUS_CHANGED = 'redemption.status_changed'
CAMPAIGN_JOINED = 'campaign.joined'
CHALLENGE_COMPLETED = 'challenge.completed'
CUSTOMER_REGISTERED = 'customer.registered'
VOUCHER_USED = 'voucher.used'

ALL_EVENTS = [
    POINTS_EARNED, POINTS_BURNED, POINTS_EXPIRED, POINTS_TRANSFERRED,
    TIER_CHANGED, TIER_UPGRADED, TIER_DOWNGRADED,
    BADGE_UNLOCKED, STREAK_MILESTONE,
    REDEMPTION_STATUS_CHANGED, CAMPAIGN_JOINED, CHALLENGE_COMPLETED,
    CUSTOMER_REGISTERED, VOUCHER_USED,
]
