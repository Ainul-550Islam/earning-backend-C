"""signals.py – Postback module signals."""
from django.dispatch import Signal

postback_received = Signal()     # instance
postback_validated = Signal()    # instance
postback_rejected = Signal()     # instance, reason
postback_rewarded = Signal()     # instance, points
postback_duplicate = Signal()    # instance
postback_failed = Signal()       # instance, error
network_created = Signal()       # instance
network_activated = Signal()     # instance
network_deactivated = Signal()   # instance

postback_reversed = Signal()  # args: instance, points_to_deduct

# ── New earning-platform signals ──────────────────────────────────────────────
tier_upgraded          = Signal()   # sender=UserTierMembership, old_tier, new_tier
daily_bonus_claimed    = Signal()   # sender=UserLoginStreak, points, streak_day
withdrawal_status_changed = Signal() # sender=WithdrawalRequest, old_status, new_status
referral_commission_earned = Signal() # sender=ReferralCommission, referrer, points
offer_completed        = Signal()   # sender=UserOfferCompletion, user, offer, points
offer_cap_exceeded     = Signal()   # sender=Offer, user_id, reason
