"""
receivers.py – Signal handlers for the postback module.

Design:
  • Every handler is wrapped in try/except — signal failures must NEVER
    break the postback pipeline or affect the HTTP response.
  • Wallet/points integration: postback_rewarded fires with (instance, points).
    The wallet app connects its own handler to this signal in its apps.py.
    This file provides a stub handler so the signal is always consumed and
    logged even if the wallet app is not installed.
  • Inventory integration: handled inside services.py via lazy import.
    No receiver needed here.
  • S2S outbound: queued from on_postback_rewarded via Celery task.
"""
import logging

logger = logging.getLogger(__name__)


# ── Received ──────────────────────────────────────────────────────────────────

def on_postback_received(sender, instance, **kwargs):
    logger.info(
        "Postback received: id=%s network=%s ip=%s",
        instance.pk, instance.network.network_key, instance.source_ip,
    )


# ── Rejected ──────────────────────────────────────────────────────────────────

def on_postback_rejected(sender, instance, reason=None, **kwargs):
    logger.warning(
        "Postback rejected: id=%s network=%s reason=%s",
        instance.pk, instance.network.network_key, reason,
    )


# ── Rewarded ──────────────────────────────────────────────────────────────────

def on_postback_rewarded(sender, instance, points=0, **kwargs):
    """
    Called after a postback is successfully rewarded.

    Responsibilities here (postback app only):
      1. Log the reward event.
      2. Queue S2S outbound postback to advertiser (if callback_url configured).

    Wallet/points deduction:
      The wallet app MUST connect its own handler to postback_rewarded signal.
      Example in wallet/apps.py ready():

          from api.postback.signals import postback_rewarded
          from api.wallet.receivers import on_postback_award_points
          postback_rewarded.connect(on_postback_award_points)

      Handler signature:
          def on_postback_award_points(sender, instance, points, **kwargs):
              # instance = PostbackLog
              # points   = int, points to award
              WalletTransaction.objects.credit(
                  user=instance.resolved_user,
                  points=points,
                  reference=str(instance.pk),
                  source="postback",
                  network=instance.network.network_key,
              )
    """
    logger.info(
        "Postback rewarded: id=%s user=%s points=%d network=%s offer=%s",
        instance.pk,
        instance.resolved_user.pk if instance.resolved_user else "N/A",
        points,
        instance.network.network_key,
        instance.offer_id,
    )

    # ── Wallet credit via wallet_bridge ──────────────────────────────────────
    # Uses api.wallet.services.core.WalletService.credit() via lazy import.
    # If wallet app not installed: logs warning, postback still marked REWARDED.
    # Idempotency key = postback_log.pk → double-credit impossible.
    try:
        from .adapters.wallet_bridge import credit_wallet_for_postback
        credit_wallet_for_postback(postback_log=instance)
    except Exception as exc:
        logger.error(
            "wallet_bridge credit failed for postback %s: %s (non-blocking)",
            instance.pk, exc,
        )

    # ── S2S outbound postback ─────────────────────────────────────────────────
    try:
        callback_url = getattr(instance.network, "callback_url", "") or ""
        if callback_url.strip():
            from .tasks import fire_s2s_postback_task
            fire_s2s_postback_task.delay(str(instance.pk))
            logger.debug(
                "S2S postback task queued: log=%s network=%s",
                instance.pk, instance.network.network_key,
            )
    except Exception as exc:
        logger.error(
            "Failed to queue S2S task for log=%s: %s", instance.pk, exc
        )


def _warn_if_wallet_not_connected(instance, points: int) -> None:
    """
    Emit a clear warning if no external wallet handler is connected to
    postback_rewarded. This prevents silent point-loss bugs in production.

    Detection strategy: if the only receiver for postback_rewarded is
    the one in this file (on_postback_rewarded), the wallet is not wired.
    """
    if points <= 0:
        return
    try:
        from .signals import postback_rewarded
        receivers = postback_rewarded.receivers
        # Count non-postback-app receivers
        external = [
            r for r in receivers
            if "postback.receivers" not in str(r)
        ]
        if not external:
            logger.warning(
                "WALLET NOT CONNECTED: postback %s awarded %d points to user %s "
                "but no wallet handler is connected to postback_rewarded signal. "
                "Connect your wallet app handler in wallet/apps.py ready().",
                instance.pk, points,
                instance.resolved_user.pk if instance.resolved_user else "N/A",
            )
    except Exception:
        pass  # Never break the reward flow


# ── Duplicate ─────────────────────────────────────────────────────────────────

def on_postback_duplicate(sender, instance, **kwargs):
    logger.info(
        "Postback duplicate: id=%s lead_id=%s network=%s",
        instance.pk, instance.lead_id, instance.network.network_key,
    )


# ── Failed ────────────────────────────────────────────────────────────────────

def on_postback_failed(sender, instance, error="", **kwargs):
    logger.error(
        "Postback failed: id=%s network=%s error=%s (retries=%d)",
        instance.pk, instance.network.network_key, error, instance.retry_count,
    )


# ── Reversed / Chargeback ─────────────────────────────────────────────────────

def on_postback_reversed(sender, instance, points_to_deduct=0, **kwargs):
    """
    Called after a chargeback/reversal postback is processed.

    Wallet rollback:
      The wallet app MUST connect its own handler to postback_reversed signal.
      Example in wallet/apps.py ready():

          from api.postback.signals import postback_reversed
          from api.wallet.receivers import on_postback_deduct_points
          postback_reversed.connect(on_postback_deduct_points)

      Handler signature:
          def on_postback_deduct_points(sender, instance, points_to_deduct, **kwargs):
              WalletTransaction.objects.debit(
                  user=instance.resolved_user,
                  points=points_to_deduct,
                  reference=str(instance.pk),
                  source="postback_reversal",
              )
    """
    logger.info(
        "Postback reversed: id=%s lead_id=%s network=%s points_to_deduct=%d",
        instance.pk, instance.lead_id,
        instance.network.network_key if instance.network else "?",
        points_to_deduct,
    )

    # ── Wallet debit via wallet_bridge ───────────────────────────────────────
    if points_to_deduct > 0:
        try:
            from .adapters.wallet_bridge import debit_wallet_for_reversal
            debit_wallet_for_reversal(reversal_log=instance)
        except Exception as exc:
            logger.error(
                "wallet_bridge debit failed for reversal %s: %s (non-blocking)",
                instance.pk, exc,
            )


# ── New platform signal handlers ──────────────────────────────────────────────

def on_tier_upgraded(sender, old_tier, new_tier, **kwargs):
    """Fire push notification + in-app when user's tier changes."""
    instance = sender  # UserTierMembership
    logger.info(
        "Tier upgraded: user=%s %s → %s",
        instance.user_id,
        getattr(old_tier, "name", old_tier),
        getattr(new_tier, "name", new_tier),
    )
    try:
        from .notifications_push import NotificationManager, NotificationChannel
        mgr = NotificationManager()
        mgr.send(
            recipient=str(instance.user_id),
            channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
            title="🏆 Tier Upgraded!",
            body=f"Congratulations! You've reached {getattr(new_tier, 'name', 'a new tier')}.",
            data={"type": "tier_upgrade", "new_tier": getattr(new_tier, "slug", "")},
        )
    except Exception as exc:
        logger.error("Tier upgrade notification failed: %s", exc)


def on_daily_bonus_claimed(sender, points, streak_day, **kwargs):
    """Log daily bonus and trigger tier points update."""
    instance = sender  # UserLoginStreak
    logger.info(
        "Daily bonus claimed: user=%s points=%d streak_day=%d",
        instance.user_id, points, streak_day,
    )
    # Update lifetime points for tier recalculation
    try:
        from .models import UserTierMembership
        from django.db.models import F
        UserTierMembership.objects.filter(user_id=instance.user_id).update(
            lifetime_points=F("lifetime_points") + points
        )
        membership = UserTierMembership.objects.select_related("tier").get(user_id=instance.user_id)
        membership.recalculate_tier()
    except Exception as exc:
        logger.error("Tier update after daily bonus failed: %s", exc)


def on_withdrawal_status_changed(sender, old_status, new_status, **kwargs):
    """Notify user when withdrawal status changes."""
    instance = sender  # WithdrawalRequest
    logger.info(
        "Withdrawal %s: %s → %s (user=%s amount=%s BDT)",
        instance.pk, old_status, new_status, instance.user_id, instance.amount_bdt,
    )
    try:
        status_messages = {
            "approved":   ("✅ Withdrawal Approved", "Your withdrawal request has been approved and is being processed."),
            "completed":  ("💰 Payment Sent!", f"Your withdrawal of {instance.amount_bdt} BDT has been sent."),
            "rejected":   ("❌ Withdrawal Rejected", f"Your withdrawal was rejected. Reason: {instance.rejection_reason or 'See support.'}"),
            "failed":     ("⚠️ Withdrawal Failed", "Your withdrawal failed. Your points have been refunded."),
        }
        if new_status in status_messages:
            from .notifications_push import NotificationManager, NotificationChannel
            title, body = status_messages[new_status]
            NotificationManager().send(
                recipient=str(instance.user_id),
                channels=[NotificationChannel.IN_APP, NotificationChannel.PUSH],
                title=title, body=body,
                data={"type": "withdrawal_status", "status": new_status,
                      "withdrawal_id": str(instance.pk)},
            )
    except Exception as exc:
        logger.error("Withdrawal status notification failed: %s", exc)


def on_referral_commission_earned(sender, referrer, points, **kwargs):
    """Notify referrer when they earn a commission."""
    instance = sender  # ReferralCommission
    logger.info("Referral commission: referrer=%s points=%d", referrer.pk if hasattr(referrer, 'pk') else referrer, points)
    try:
        from .notifications_push import NotificationManager, NotificationChannel
        NotificationManager().send(
            recipient=str(referrer.pk if hasattr(referrer, 'pk') else referrer),
            channels=[NotificationChannel.IN_APP],
            title="💸 Referral Bonus!",
            body=f"You earned {points} points from your referral's completion.",
            data={"type": "referral_commission", "points": points},
        )
    except Exception as exc:
        logger.error("Referral commission notification failed: %s", exc)


def on_offer_completed(sender, user, offer, points, **kwargs):
    """Update tier lifetime points and fire tier recalculation on each completion."""
    try:
        from .models import UserTierMembership
        from django.db.models import F
        UserTierMembership.objects.filter(user=user).update(
            lifetime_points=F("lifetime_points") + points
        )
        membership = UserTierMembership.objects.select_related("tier").get(user=user)
        membership.recalculate_tier()
    except Exception as exc:
        logger.error("Tier update after offer completion failed: %s", exc)


# ── Push notification hooks (wired to existing signals) ───────────────────────

def on_withdrawal_approved(sender, instance, **kwargs):
    """Fire push when a WithdrawalRequest moves to 'approved'."""
    if instance.status == "approved":
        from .tasks import notify_withdrawal_approved
        notify_withdrawal_approved.delay(str(instance.pk))


def on_tier_recalculated(sender, instance, old_tier_name, **kwargs):
    """Fire push when a user reaches a new tier."""
    from .tasks import notify_tier_upgrade
    notify_tier_upgrade.delay(str(instance.user_id), instance.tier.name)


def on_referral_commission_created(sender, instance, created, **kwargs):
    """Fire push to referrer when a commission row is created."""
    if created:
        from .tasks import notify_referral_commission_earned
        try:
            referee_name = instance.referral.referee.username
        except Exception:
            referee_name = "your referral"
        notify_referral_commission_earned.delay(
            str(instance.referral.referrer_id),
            instance.points_awarded,
            referee_name,
        )
