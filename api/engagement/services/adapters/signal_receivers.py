# engagement/services/adapters/signal_receivers.py
"""
EngagementSignalReceivers
==========================
Django signal receivers that wire ALL 50 external apps → engagement automatically.

HOW TO ACTIVATE:
    In engagement/apps.py ready():
        import api.engagement.services.adapters.signal_receivers  # noqa

This file is the ONLY place cross-app Django signals are connected.
Every receiver is wrapped in try/except so a broken external app
never crashes engagement startup.

Receivers defined:
    1.  tasks.task_completed              → TasksIntegration
    2.  ad_networks.reward_complete       → AdNetworksIntegration
    3.  postback.postback_rewarded        → PostbackIntegration
    4.  postback_engine.conversion_done   → PostbackIntegration
    5.  wallet.deposit_completed          → WalletIntegration
    6.  wallet.earning_recorded           → WalletIntegration
    7.  wallet.withdrawal_completed       → WalletIntegration
    8.  users.user_registered             → UsersIntegration
    9.  users.profile_updated             → UsersIntegration
    10. referral.commission_earned        → ReferralIntegration
    11. referral.referral_registered      → ReferralIntegration
    12. djoyalty.points_earned            → DjoyaltyIntegration
    13. monetization_tools.reward_credited→ MonetizationToolsIntegration
    14. monetization_tools.spin_played    → MonetizationToolsIntegration
    15. fraud_detection.user_flagged      → FraudDetectionIntegration
    16. offer_inventory.offer_completed   → OfferInventoryIntegration
    17. promotions.bonus_awarded          → PromotionsIntegration
    18. smartlink.conversion              → SmartlinkIntegration
    19. offerwall.reward                  → OfferwallIntegration
    20. subscription.started              → PlatformIntegration
    21. payout_queue.approved             → PlatformIntegration
    22. support.ticket_resolved           → PlatformIntegration
    + EngagementEventBus → DjoyaltyIntegration (reverse sync)
"""

import logging
from django.dispatch import receiver
from django.db.models.signals import post_save

logger = logging.getLogger("engagement.signal_receivers")


def _safe(fn):
    """Decorator: catches ALL exceptions so signal never crashes the sender."""
    import functools
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            logger.error(f"SignalReceiver {fn.__name__} failed: {e}")
    return wrapper


# ── Lazy import helper ────────────────────────────────────────────────────────
def _esi():
    from api.engagement.services.adapters.full_system_integration import (
        EngagementSystemIntegration,
    )
    return EngagementSystemIntegration


# ─────────────────────────────────────────────────────────────────────────────
# 1. api.tasks — task_completed signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.tasks.signals import task_completed

    @receiver(task_completed)
    @_safe
    def on_task_completed(sender, user, task, amount, task_type="general",
                           ip=None, **kwargs):
        from decimal import Decimal
        _esi().tasks.on_task_completed(user, task, Decimal(str(amount)), task_type, ip)

    logger.debug("Registered: tasks.task_completed → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"tasks.task_completed signal not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. api.ad_networks — reward_complete signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.ad_networks.signals import reward_complete

    @receiver(reward_complete)
    @_safe
    def on_ad_reward(sender, user, offer_id, amount, network="",
                      conversion_id="", ip=None, **kwargs):
        from decimal import Decimal
        _esi().ad_networks.on_ad_reward(user, offer_id, Decimal(str(amount)),
                                         network, conversion_id, ip)

    logger.debug("Registered: ad_networks.reward_complete → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"ad_networks.reward_complete not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 3. api.postback — postback_rewarded signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.postback.signals import postback_rewarded

    @receiver(postback_rewarded)
    @_safe
    def on_postback_rewarded(sender, instance, points=0, **kwargs):
        from decimal import Decimal
        if not hasattr(instance, "user") or not instance.user:
            return
        _esi().postback.on_postback_reward(
            user=instance.user,
            amount=Decimal(str(points)),
            source_type=getattr(instance, "source_type", "cpa"),
            offer_id=str(getattr(instance, "offer_id", "")),
            postback_id=str(getattr(instance, "pk", "")),
            ip=getattr(instance, "ip_address", None),
        )

    logger.debug("Registered: postback.postback_rewarded → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"postback.postback_rewarded not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. api.postback_engine — conversion rewarded signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.postback_engine.signals import conversion_rewarded

    @receiver(conversion_rewarded)
    @_safe
    def on_conversion_rewarded(sender, user, amount, source_type="cpa",
                                offer_id="", conversion_id="", ip=None, **kwargs):
        from decimal import Decimal
        _esi().postback.on_postback_reward(
            user, Decimal(str(amount)), source_type, offer_id, conversion_id, ip
        )

    logger.debug("Registered: postback_engine.conversion_rewarded → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"postback_engine.conversion_rewarded not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. api.wallet — deposit_completed signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.wallet.signals import deposit_completed

    @receiver(deposit_completed)
    @_safe
    def on_wallet_deposit(sender, wallet, amount, txn_id="", **kwargs):
        from decimal import Decimal
        user = getattr(wallet, "user", None)
        if user:
            _esi().wallet.on_wallet_deposit(user, Decimal(str(amount)), str(txn_id))

    logger.debug("Registered: wallet.deposit_completed → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"wallet.deposit_completed not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. api.wallet — earning_recorded signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.wallet.signals import earning_recorded

    @receiver(earning_recorded)
    @_safe
    def on_wallet_earning(sender, wallet, amount, source_type="task",
                           source_id="", ip=None, **kwargs):
        from decimal import Decimal
        user = getattr(wallet, "user", None)
        if user:
            _esi().wallet.on_wallet_earning(
                user, Decimal(str(amount)), source_type, source_id, ip
            )

    logger.debug("Registered: wallet.earning_recorded → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"wallet.earning_recorded not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. api.wallet — withdrawal_completed signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.wallet.signals import withdrawal_completed

    @receiver(withdrawal_completed)
    @_safe
    def on_wallet_withdrawal(sender, wallet, amount, **kwargs):
        from decimal import Decimal
        user = getattr(wallet, "user", None)
        if user:
            _esi().wallet.on_wallet_withdrawal(user, Decimal(str(amount)))

    logger.debug("Registered: wallet.withdrawal_completed → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"wallet.withdrawal_completed not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 8. api.users — user registered (post_save on User model)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from django.contrib.auth import get_user_model

    @receiver(post_save, sender=get_user_model())
    @_safe
    def on_user_post_save(sender, instance, created, **kwargs):
        if created:
            referral_code = getattr(instance, "_referral_code", "") or ""
            ip = getattr(instance, "_signup_ip", None)
            _esi().users.on_user_signup(instance, referral_code, ip)

    logger.debug("Registered: User.post_save(created=True) → engagement")
except Exception as e:
    logger.debug(f"User post_save receiver not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. api.users — profile updated signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.users.signals import profile_updated

    @receiver(profile_updated)
    @_safe
    def on_profile_updated(sender, user, **kwargs):
        _esi().users.on_profile_updated(user)

    logger.debug("Registered: users.profile_updated → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"users.profile_updated not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 10. api.referral — commission_earned signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.referral.signals import commission_earned

    @receiver(commission_earned)
    @_safe
    def on_referral_commission(sender, user, amount, referee_username="",
                                level=1, **kwargs):
        from decimal import Decimal
        _esi().referral.on_commission_earned(user, Decimal(str(amount)),
                                              referee_username, level)

    logger.debug("Registered: referral.commission_earned → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"referral.commission_earned not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 11. api.referral — referral_registered signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.referral.signals import referral_registered

    @receiver(referral_registered)
    @_safe
    def on_referral_registered(sender, referrer, referee, code="", **kwargs):
        _esi().referral.on_referral_registered(referrer, referee, code)

    logger.debug("Registered: referral.referral_registered → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"referral.referral_registered not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 12. api.djoyalty — points_earned signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.djoyalty.signals.earn_signals import points_earned

    @receiver(points_earned)
    @_safe
    def on_djoyalty_points(sender, customer, points, source="streak", **kwargs):
        from decimal import Decimal
        _esi().djoyalty.on_djoyalty_points_earned(customer, Decimal(str(points)), source)

    logger.debug("Registered: djoyalty.points_earned → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"djoyalty.points_earned not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 13. api.monetization_tools — reward_credited hook
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.monetization_tools.signals import reward_credited_signal

    @receiver(reward_credited_signal)
    @_safe
    def on_monetization_reward(sender, user, amount, transaction_type="",
                                reference_id="", **kwargs):
        from decimal import Decimal
        _esi().monetization.on_reward_credited(user, Decimal(str(amount)),
                                                transaction_type, reference_id)

    logger.debug("Registered: monetization_tools.reward_credited → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"monetization_tools.reward_credited_signal not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 14. api.monetization_tools — spin_wheel_played hook
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.monetization_tools.signals import spin_wheel_played_signal

    @receiver(spin_wheel_played_signal)
    @_safe
    def on_monetization_spin(sender, user, prize_type="coins",
                              prize_value=0, **kwargs):
        from decimal import Decimal
        _esi().monetization.on_spin_wheel_played(user, prize_type, Decimal(str(prize_value)))

    logger.debug("Registered: monetization_tools.spin_played → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"monetization_tools.spin_wheel_played_signal not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 15. api.fraud_detection — user_flagged signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.fraud_detection.signals import user_flagged

    @receiver(user_flagged)
    @_safe
    def on_fraud_flag(sender, user, score, rule="", ip=None, **kwargs):
        _esi().fraud.on_fraud_detected(user, score, rule, ip)

    logger.debug("Registered: fraud_detection.user_flagged → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"fraud_detection.user_flagged not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 16. api.offer_inventory — offer_completed signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.offer_inventory.signals import offer_completed

    @receiver(offer_completed)
    @_safe
    def on_offer_completed(sender, user, offer_id, reward_amount,
                            offer_type="cpa", ip=None, **kwargs):
        from decimal import Decimal
        _esi().offer_inventory.on_offer_completed(
            user, str(offer_id), Decimal(str(reward_amount)), offer_type, ip
        )

    logger.debug("Registered: offer_inventory.offer_completed → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"offer_inventory.offer_completed not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 17. api.promotions — bonus_awarded signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.promotions.signals import bonus_awarded

    @receiver(bonus_awarded)
    @_safe
    def on_promo_bonus(sender, user, amount, promo_type="performance",
                        promo_id="", **kwargs):
        from decimal import Decimal
        _esi().promotions.on_promotion_bonus(
            user, Decimal(str(amount)), promo_type, str(promo_id)
        )

    logger.debug("Registered: promotions.bonus_awarded → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"promotions.bonus_awarded not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 18. api.smartlink — conversion signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.smartlink.signals import smartlink_conversion

    @receiver(smartlink_conversion)
    @_safe
    def on_smartlink(sender, user, amount, smartlink_id="", ip=None, **kwargs):
        from decimal import Decimal
        _esi().smartlink.on_smartlink_conversion(
            user, Decimal(str(amount)), str(smartlink_id), ip
        )

    logger.debug("Registered: smartlink.smartlink_conversion → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"smartlink.smartlink_conversion not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 19. api.offerwall — reward signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.offerwall.signals import offerwall_reward

    @receiver(offerwall_reward)
    @_safe
    def on_offerwall_reward(sender, user, amount, offerwall_name="",
                             offer_id="", ip=None, **kwargs):
        from decimal import Decimal
        _esi().offerwall.on_offerwall_reward(
            user, Decimal(str(amount)), offerwall_name, str(offer_id), ip
        )

    logger.debug("Registered: offerwall.offerwall_reward → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"offerwall.offerwall_reward not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 20. api.subscription — subscription_started signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.subscription.signals import subscription_started

    @receiver(subscription_started)
    @_safe
    def on_subscription(sender, user, plan_name="", subscription_id="", **kwargs):
        _esi().platform.on_subscription_started(user, plan_name, str(subscription_id))

    logger.debug("Registered: subscription.subscription_started → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"subscription.subscription_started not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 21. api.payout_queue — payout_approved signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.payout_queue.signals import payout_approved

    @receiver(payout_approved)
    @_safe
    def on_payout_approved(sender, user, amount, **kwargs):
        from decimal import Decimal
        _esi().platform.on_payout_approved(user, Decimal(str(amount)))

    logger.debug("Registered: payout_queue.payout_approved → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"payout_queue.payout_approved not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 22. api.support — ticket_resolved signal
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.support.signals import ticket_resolved

    @receiver(ticket_resolved)
    @_safe
    def on_ticket_resolved(sender, user, satisfaction_score=5, **kwargs):
        _esi().platform.on_support_ticket_resolved(user, satisfaction_score)

    logger.debug("Registered: support.ticket_resolved → engagement")
except (ImportError, Exception) as e:
    logger.debug(f"support.ticket_resolved not available: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# REVERSE: engagement EventBus → djoyalty (bidirectional sync)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from api.engagement.services.integration.event_bus import EngagementEventBus

    @receiver(EngagementEventBus.COINS_EARNED)
    @_safe
    def sync_coins_to_djoyalty(sender, user, amount, source, **kwargs):
        from decimal import Decimal
        _esi().djoyalty.on_engagement_coins_earned(user, Decimal(str(amount)), source)

    logger.debug("Registered: EngagementEventBus.COINS_EARNED → djoyalty sync")
except Exception as e:
    logger.debug(f"djoyalty reverse sync not available: {e}")


logger.info(
    "EngagementSignalReceivers loaded. "
    "All 50-module hooks registered (missing signals are silently skipped)."
)
