"""
api/monetization_tools/hooks.py
==================================
Extension hooks — lets other apps plug into monetization events
without tight coupling.
"""

import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

_registry: Dict[str, List[Callable]] = {}


def register_hook(event: str, callback: Callable) -> None:
    """Register a callback for a named event."""
    _registry.setdefault(event, []).append(callback)
    logger.debug("Hook registered: event='%s' callback=%s", event, callback.__name__)


def fire_hook(event: str, **kwargs) -> None:
    """Call all callbacks registered for an event."""
    for cb in _registry.get(event, []):
        try:
            cb(**kwargs)
        except Exception as exc:
            logger.error("Hook error (event='%s' cb=%s): %s", event, cb.__name__, exc)


# ---------------------------------------------------------------------------
# Named hook constants — use these instead of raw strings
# ---------------------------------------------------------------------------

HOOK_OFFER_STARTED    = 'offer_started'
HOOK_OFFER_APPROVED   = 'offer_approved'
HOOK_OFFER_REJECTED   = 'offer_rejected'
HOOK_REWARD_CREDITED  = 'reward_credited'
HOOK_SUBSCRIPTION_NEW = 'subscription_new'
HOOK_SUBSCRIPTION_CANCELLED = 'subscription_cancelled'
HOOK_PAYMENT_SUCCESS  = 'payment_success'
HOOK_PAYMENT_FAILED   = 'payment_failed'
HOOK_SPIN_WHEEL_PLAYED = 'spin_wheel_played'
HOOK_ACHIEVEMENT_UNLOCKED = 'achievement_unlocked'
HOOK_LEVEL_UP         = 'level_up'


# ---------------------------------------------------------------------------
# New hook constants for Phase-2 models
# ---------------------------------------------------------------------------

HOOK_REFERRAL_EARNED        = 'referral_earned'
HOOK_REFERRAL_JOINED        = 'referral_joined'
HOOK_PAYOUT_REQUESTED       = 'payout_requested'
HOOK_PAYOUT_APPROVED        = 'payout_approved'
HOOK_PAYOUT_PAID            = 'payout_paid'
HOOK_PAYOUT_REJECTED        = 'payout_rejected'
HOOK_COUPON_REDEEMED        = 'coupon_redeemed'
HOOK_COUPON_EXPIRED         = 'coupon_expired'
HOOK_FLASH_SALE_STARTED     = 'flash_sale_started'
HOOK_FLASH_SALE_ENDED       = 'flash_sale_ended'
HOOK_FRAUD_ALERT_CREATED    = 'fraud_alert_created'
HOOK_FRAUD_ALERT_RESOLVED   = 'fraud_alert_resolved'
HOOK_USER_BLOCKED           = 'user_blocked'
HOOK_PUBLISHER_VERIFIED     = 'publisher_verified'
HOOK_PUBLISHER_SUSPENDED    = 'publisher_suspended'
HOOK_GOAL_ACHIEVED          = 'goal_achieved'
HOOK_CREATIVE_APPROVED      = 'creative_approved'
HOOK_CREATIVE_REJECTED      = 'creative_rejected'
HOOK_SEGMENT_COMPUTED       = 'segment_computed'
HOOK_POSTBACK_ACCEPTED      = 'postback_accepted'
HOOK_POSTBACK_REJECTED      = 'postback_rejected'
HOOK_DAILY_CHECK_IN         = 'daily_check_in'
HOOK_STREAK_BROKEN          = 'streak_broken'
HOOK_STREAK_MILESTONE       = 'streak_milestone'
HOOK_AB_TEST_WINNER         = 'ab_test_winner'
HOOK_OFFER_EXPIRED          = 'offer_expired'
HOOK_SUBSCRIPTION_RENEWED   = 'subscription_renewed'
HOOK_SUBSCRIPTION_PAST_DUE  = 'subscription_past_due'
HOOK_BILLING_FAILED         = 'billing_failed'
HOOK_NETWORK_STAT_SYNCED    = 'network_stat_synced'
HOOK_REVENUE_GOAL_PROGRESS  = 'revenue_goal_progress'
