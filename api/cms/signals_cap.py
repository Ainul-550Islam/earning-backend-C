# api/cms/signals_cap.py
"""CPAlead-specific signals (CAP = CPAlead Publisher)."""
from django.dispatch import Signal

# Postback lifecycle
cap_postback_received  = Signal()  # data, ip
cap_postback_validated = Signal()  # data, cleaned
cap_postback_approved  = Signal()  # user, payout_usd, lead_id, virtual_amount
cap_postback_rejected  = Signal()  # lead_id, reason

# Offer interactions
cap_offer_clicked      = Signal()  # user, offer_id, click_id, ip
cap_offer_feed_fetched = Signal()  # count, user_ip, device

# Offerwall
cap_offerwall_viewed   = Signal()  # user, offerwall_config
cap_offerwall_embedded = Signal()  # publisher_id, page_url

# Locker
cap_locker_viewed      = Signal()  # user, locker
cap_locker_unlocked    = Signal()  # user, locker, lead_id

# Virtual currency
cap_coins_awarded      = Signal()  # user, amount, reason, balance_after
cap_coins_spent        = Signal()  # user, amount, reason, balance_after
cap_daily_cap_hit      = Signal()  # user, cap_amount, earned_today

# Quiz
cap_quiz_started       = Signal()  # user, quiz
cap_quiz_completed     = Signal()  # user, quiz, result, reward_coins

# SmartLink
cap_smartlink_clicked  = Signal()  # user, smartlink, rule, ip, device

# Referral
cap_referral_applied   = Signal()  # referrer, referred, code
cap_referral_bonus     = Signal()  # referrer, referred, bonus_usd, bonus_coins
