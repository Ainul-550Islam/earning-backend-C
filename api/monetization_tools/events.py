"""
api/monetization_tools/events.py
===================================
Structured event emitters that fire hooks and optionally
send analytics events (Firebase, Amplitude, etc.).
"""

import logging
from decimal import Decimal

from .hooks import fire_hook, HOOK_OFFER_APPROVED, HOOK_REWARD_CREDITED, HOOK_SUBSCRIPTION_NEW
from .hooks import HOOK_PAYMENT_SUCCESS, HOOK_PAYMENT_FAILED, HOOK_SPIN_WHEEL_PLAYED
from .hooks import HOOK_ACHIEVEMENT_UNLOCKED, HOOK_LEVEL_UP, HOOK_SUBSCRIPTION_CANCELLED
from .hooks import HOOK_OFFER_STARTED, HOOK_OFFER_REJECTED

logger = logging.getLogger(__name__)


def emit_offer_started(user_id, offer_id, transaction_id: str):
    logger.info("EVENT offer_started user=%s offer=%s txn=%s", user_id, offer_id, transaction_id)
    fire_hook(HOOK_OFFER_STARTED, user_id=user_id, offer_id=offer_id, transaction_id=transaction_id)


def emit_offer_approved(user_id, offer_id, transaction_id: str, reward: Decimal):
    logger.info("EVENT offer_approved user=%s offer=%s reward=%s", user_id, offer_id, reward)
    fire_hook(HOOK_OFFER_APPROVED, user_id=user_id, offer_id=offer_id,
              transaction_id=transaction_id, reward=reward)


def emit_offer_rejected(user_id, offer_id, transaction_id: str, reason: str):
    logger.info("EVENT offer_rejected user=%s offer=%s reason=%s", user_id, offer_id, reason)
    fire_hook(HOOK_OFFER_REJECTED, user_id=user_id, offer_id=offer_id,
              transaction_id=transaction_id, reason=reason)


def emit_reward_credited(user_id, amount: Decimal, transaction_type: str, reference_id: str = ''):
    logger.info("EVENT reward_credited user=%s amount=%s type=%s", user_id, amount, transaction_type)
    fire_hook(HOOK_REWARD_CREDITED, user_id=user_id, amount=amount,
              transaction_type=transaction_type, reference_id=reference_id)


def emit_subscription_new(user_id, plan_name: str, subscription_id: str):
    logger.info("EVENT subscription_new user=%s plan=%s sub=%s", user_id, plan_name, subscription_id)
    fire_hook(HOOK_SUBSCRIPTION_NEW, user_id=user_id, plan_name=plan_name,
              subscription_id=subscription_id)


def emit_subscription_cancelled(user_id, subscription_id: str, reason: str):
    logger.info("EVENT subscription_cancelled user=%s sub=%s", user_id, subscription_id)
    fire_hook(HOOK_SUBSCRIPTION_CANCELLED, user_id=user_id,
              subscription_id=subscription_id, reason=reason)


def emit_payment_success(user_id, txn_id: str, amount: Decimal, gateway: str):
    logger.info("EVENT payment_success user=%s txn=%s amount=%s gw=%s", user_id, txn_id, amount, gateway)
    fire_hook(HOOK_PAYMENT_SUCCESS, user_id=user_id, txn_id=txn_id, amount=amount, gateway=gateway)


def emit_payment_failed(user_id, txn_id: str, reason: str):
    logger.info("EVENT payment_failed user=%s txn=%s reason=%s", user_id, txn_id, reason)
    fire_hook(HOOK_PAYMENT_FAILED, user_id=user_id, txn_id=txn_id, reason=reason)


def emit_spin_wheel_played(user_id, prize_type: str, prize_value: Decimal):
    logger.info("EVENT spin_wheel user=%s prize=%s %s", user_id, prize_type, prize_value)
    fire_hook(HOOK_SPIN_WHEEL_PLAYED, user_id=user_id, prize_type=prize_type, prize_value=prize_value)


def emit_achievement_unlocked(user_id, key: str, title: str, xp: int, coins: Decimal):
    logger.info("EVENT achievement_unlocked user=%s key=%s", user_id, key)
    fire_hook(HOOK_ACHIEVEMENT_UNLOCKED, user_id=user_id, key=key,
              title=title, xp=xp, coins=coins)


def emit_level_up(user_id, old_level: int, new_level: int):
    logger.info("EVENT level_up user=%s %d→%d", user_id, old_level, new_level)
    fire_hook(HOOK_LEVEL_UP, user_id=user_id, old_level=old_level, new_level=new_level)


def emit_referral_earned(referrer_id, referee_id: str, coins: Decimal, level: int):
    logger.info("EVENT referral_earned referrer=%s coins=%s level=%s", referrer_id, coins, level)
    fire_hook('referral_earned', referrer_id=referrer_id, referee_id=referee_id,
              coins=coins, level=level)


def emit_referral_joined(referrer_id, referee_id: str, program_id=None):
    logger.info("EVENT referral_joined referrer=%s referee=%s", referrer_id, referee_id)
    fire_hook('referral_joined', referrer_id=referrer_id, referee_id=referee_id,
              program_id=program_id)


def emit_payout_requested(user_id, request_id: str, amount: Decimal, currency: str):
    logger.info("EVENT payout_requested user=%s amount=%s %s", user_id, amount, currency)
    fire_hook('payout_requested', user_id=user_id, request_id=request_id,
              amount=amount, currency=currency)


def emit_payout_approved(user_id, request_id: str, amount: Decimal, currency: str):
    logger.info("EVENT payout_approved user=%s amount=%s", user_id, amount)
    fire_hook('payout_approved', user_id=user_id, request_id=request_id,
              amount=amount, currency=currency)


def emit_payout_paid(user_id, request_id: str, amount: Decimal, currency: str, gateway_ref: str = ''):
    logger.info("EVENT payout_paid user=%s amount=%s %s ref=%s", user_id, amount, currency, gateway_ref)
    fire_hook('payout_paid', user_id=user_id, request_id=request_id,
              amount=amount, currency=currency, gateway_ref=gateway_ref)


def emit_payout_rejected(user_id, request_id: str, reason: str):
    logger.info("EVENT payout_rejected user=%s reason=%s", user_id, reason)
    fire_hook('payout_rejected', user_id=user_id, request_id=request_id, reason=reason)


def emit_coupon_redeemed(user_id, coupon_code: str, coins_granted: Decimal, discount_pct: Decimal):
    logger.info("EVENT coupon_redeemed user=%s code=%s coins=%s", user_id, coupon_code, coins_granted)
    fire_hook('coupon_redeemed', user_id=user_id, coupon_code=coupon_code,
              coins_granted=coins_granted, discount_pct=discount_pct)


def emit_coupon_expired(coupon_id, coupon_code: str):
    logger.info("EVENT coupon_expired code=%s", coupon_code)
    fire_hook('coupon_expired', coupon_id=coupon_id, coupon_code=coupon_code)


def emit_flash_sale_started(sale_id, sale_name: str, multiplier: Decimal,
                              starts_at: str, ends_at: str):
    logger.info("EVENT flash_sale_started name=%s multiplier=%s", sale_name, multiplier)
    fire_hook('flash_sale_started', sale_id=sale_id, sale_name=sale_name,
              multiplier=multiplier, starts_at=starts_at, ends_at=ends_at)


def emit_flash_sale_ended(sale_id, sale_name: str, total_participants: int):
    logger.info("EVENT flash_sale_ended name=%s participants=%d", sale_name, total_participants)
    fire_hook('flash_sale_ended', sale_id=sale_id, sale_name=sale_name,
              total_participants=total_participants)


def emit_fraud_alert_created(user_id, alert_id: str, alert_type: str, severity: str):
    logger.warning("EVENT fraud_alert_created user=%s type=%s severity=%s", user_id, alert_type, severity)
    fire_hook('fraud_alert_created', user_id=user_id, alert_id=alert_id,
              alert_type=alert_type, severity=severity)


def emit_fraud_alert_resolved(user_id, alert_id: str, resolution: str):
    logger.info("EVENT fraud_alert_resolved user=%s resolution=%s", user_id, resolution)
    fire_hook('fraud_alert_resolved', user_id=user_id, alert_id=alert_id, resolution=resolution)


def emit_user_blocked(user_id, reason: str):
    logger.warning("EVENT user_blocked user=%s reason=%s", user_id, reason)
    fire_hook('user_blocked', user_id=user_id, reason=reason)


def emit_publisher_verified(account_id: str, company_name: str):
    logger.info("EVENT publisher_verified account=%s", account_id)
    fire_hook('publisher_verified', account_id=account_id, company_name=company_name)


def emit_publisher_suspended(account_id: str, reason: str):
    logger.warning("EVENT publisher_suspended account=%s reason=%s", account_id, reason)
    fire_hook('publisher_suspended', account_id=account_id, reason=reason)


def emit_goal_achieved(goal_id, goal_name: str, target: Decimal, achieved: Decimal):
    logger.info("EVENT goal_achieved name=%s target=%s achieved=%s", goal_name, target, achieved)
    fire_hook('goal_achieved', goal_id=goal_id, goal_name=goal_name,
              target=target, achieved=achieved)


def emit_creative_approved(creative_id: str, ad_unit_id: int):
    logger.info("EVENT creative_approved creative=%s unit=%s", creative_id, ad_unit_id)
    fire_hook('creative_approved', creative_id=creative_id, ad_unit_id=ad_unit_id)


def emit_creative_rejected(creative_id: str, reason: str):
    logger.info("EVENT creative_rejected creative=%s reason=%s", creative_id, reason)
    fire_hook('creative_rejected', creative_id=creative_id, reason=reason)


def emit_daily_check_in(user_id, streak_day: int, coins_awarded: Decimal):
    logger.info("EVENT daily_check_in user=%s day=%d coins=%s", user_id, streak_day, coins_awarded)
    fire_hook('daily_check_in', user_id=user_id, streak_day=streak_day, coins_awarded=coins_awarded)


def emit_streak_broken(user_id, broken_at_day: int):
    logger.info("EVENT streak_broken user=%s at_day=%d", user_id, broken_at_day)
    fire_hook('streak_broken', user_id=user_id, broken_at_day=broken_at_day)


def emit_streak_milestone(user_id, milestone_days: int, coins_awarded: Decimal):
    logger.info("EVENT streak_milestone user=%s days=%d coins=%s", user_id, milestone_days, coins_awarded)
    fire_hook('streak_milestone', user_id=user_id, milestone_days=milestone_days,
              coins_awarded=coins_awarded)


def emit_postback_accepted(postback_id: str, network_name: str, reward: Decimal):
    logger.info("EVENT postback_accepted id=%s net=%s reward=%s", postback_id, network_name, reward)
    fire_hook('postback_accepted', postback_id=postback_id, network_name=network_name, reward=reward)


def emit_postback_rejected(postback_id: str, network_name: str, reason: str):
    logger.warning("EVENT postback_rejected id=%s reason=%s", postback_id, reason)
    fire_hook('postback_rejected', postback_id=postback_id,
              network_name=network_name, reason=reason)


def emit_ab_test_winner(test_id: str, test_name: str, winner_variant: str, criteria: str):
    logger.info("EVENT ab_test_winner test=%s winner=%s by=%s", test_name, winner_variant, criteria)
    fire_hook('ab_test_winner', test_id=test_id, test_name=test_name,
              winner_variant=winner_variant, criteria=criteria)


def emit_subscription_renewed(user_id, subscription_id: str, plan_name: str, next_period_end: str):
    logger.info("EVENT subscription_renewed user=%s plan=%s", user_id, plan_name)
    fire_hook('subscription_renewed', user_id=user_id, subscription_id=subscription_id,
              plan_name=plan_name, next_period_end=next_period_end)


def emit_subscription_past_due(user_id, subscription_id: str, plan_name: str):
    logger.warning("EVENT subscription_past_due user=%s plan=%s", user_id, plan_name)
    fire_hook('subscription_past_due', user_id=user_id,
              subscription_id=subscription_id, plan_name=plan_name)


def emit_billing_failed(user_id, billing_id: int, reason: str, attempt: int):
    logger.error("EVENT billing_failed user=%s billing=%s attempt=%d", user_id, billing_id, attempt)
    fire_hook('billing_failed', user_id=user_id, billing_id=billing_id,
              reason=reason, attempt=attempt)
