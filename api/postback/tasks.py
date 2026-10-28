"""tasks.py – Celery tasks for the postback module."""
import logging
from celery import shared_task
from django.utils import timezone

from .constants import (
    MAX_POSTBACK_PROCESSING_RETRIES,
    POSTBACK_RETRY_COUNTDOWN_SECONDS,
    TASK_PROCESS_POSTBACK,
    TASK_CLEANUP_OLD_LOGS,
    TASK_RETRY_FAILED,
    POSTBACK_LOG_RETENTION_DAYS,
    DUPLICATE_LOG_RETENTION_DAYS,
)

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name=TASK_PROCESS_POSTBACK,
    max_retries=MAX_POSTBACK_PROCESSING_RETRIES,
    acks_late=True,
    reject_on_worker_lost=True,
)
def process_postback(
    self,
    log_id: str,
    *,
    signature: str,
    timestamp_str: str,
    nonce: str,
    body_bytes_hex: str,
    path: str,
    query_params: dict,
):
    """
    Process a postback through the full validation pipeline.
    Retries on unexpected errors with exponential back-off.
    """
    from .models import PostbackLog
    from .services import process_postback_sync

    try:
        log = PostbackLog.objects.select_related("network").get(pk=log_id)
    except PostbackLog.DoesNotExist:
        logger.error("[process_postback] PostbackLog %s not found – cannot process.", log_id)
        return

    try:
        process_postback_sync(
            log,
            signature=signature,
            timestamp_str=timestamp_str,
            nonce=nonce,
            body_bytes=bytes.fromhex(body_bytes_hex),
            path=path,
            query_params=query_params,
        )
    except Exception as exc:
        retry_n = self.request.retries
        if retry_n < MAX_POSTBACK_PROCESSING_RETRIES:
            countdown = POSTBACK_RETRY_COUNTDOWN_SECONDS[
                min(retry_n, len(POSTBACK_RETRY_COUNTDOWN_SECONDS) - 1)
            ]
            logger.warning(
                "[process_postback] Log %s – retry %d in %ds: %s",
                log_id, retry_n + 1, countdown, exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        logger.error(
            "[process_postback] Log %s permanently failed after %d retries: %s",
            log_id, MAX_POSTBACK_PROCESSING_RETRIES, exc,
        )


@shared_task(
    bind=True,
    name=TASK_RETRY_FAILED,
    max_retries=1,
)
def retry_failed_postbacks(self):
    """Re-queue failed postbacks that are eligible for retry."""
    from .models import PostbackLog

    retryable = PostbackLog.objects.retryable().values_list("id", flat=True)
    queued = 0
    for log_id in retryable:
        # Re-queue with empty security params – the log already has raw_payload.
        # The retry path in process_postback_sync handles this gracefully.
        process_postback.delay(
            str(log_id),
            signature="",
            timestamp_str="",
            nonce="",
            body_bytes_hex="",
            path="",
            query_params={},
        )
        queued += 1
    logger.info("[retry_failed_postbacks] Queued %d retries.", queued)
    return {"queued": queued}


@shared_task(
    bind=True,
    name=TASK_CLEANUP_OLD_LOGS,
    max_retries=2,
)
def cleanup_old_logs(self):
    """
    Delete PostbackLog records beyond the retention window.
    DuplicateLeadCheck records are cleaned based on their own retention window.
    """
    from .models import PostbackLog, DuplicateLeadCheck

    log_threshold = timezone.now() - timezone.timedelta(days=POSTBACK_LOG_RETENTION_DAYS)
    dedup_threshold = timezone.now() - timezone.timedelta(days=DUPLICATE_LOG_RETENTION_DAYS)

    log_count, _ = PostbackLog.objects.filter(received_at__lt=log_threshold).delete()
    dedup_count, _ = DuplicateLeadCheck.objects.filter(first_seen_at__lt=dedup_threshold).delete()

    logger.info(
        "[cleanup_old_logs] Deleted %d postback logs and %d dedup records.",
        log_count, dedup_count,
    )
    return {"logs_deleted": log_count, "dedup_deleted": dedup_count}


# ══════════════════════════════════════════════════════════════════════════════
# NEW EARNING-PLATFORM TASKS
# ══════════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def rebuild_leaderboard(self, period: str = "weekly"):
    """
    Rebuild the materialized LeaderboardEntry table for a given period.
    Scheduled: daily for daily, Sunday night for weekly, 1st of month for monthly.

    Args:
        period: "daily" | "weekly" | "monthly" | "all_time"
    """
    import datetime
    from django.utils import timezone
    from django.db.models import Sum, Count
    from .models import LeaderboardEntry, UserOfferCompletion
    from django.contrib.auth import get_user_model

    User = get_user_model()
    today = timezone.now().date()

    period_map = {
        "daily":   today - datetime.timedelta(days=1),
        "weekly":  today - datetime.timedelta(days=7),
        "monthly": today - datetime.timedelta(days=30),
        "all_time": None,
    }
    if period not in period_map:
        raise ValueError(f"Unknown period: {period}")

    since = period_map[period]
    qs = UserOfferCompletion.objects.filter(is_reversed=False)
    if since:
        qs = qs.filter(completed_at__date__gte=since)

    rankings = (
        qs.values("user_id")
        .annotate(
            points_earned=Sum("points_awarded"),
            offers_completed=Count("id"),
        )
        .order_by("-points_earned")[:500]
    )

    # Bulk-create new entries; clear stale period+date rows first
    period_start = since or datetime.date(2000, 1, 1)
    LeaderboardEntry.objects.filter(period=period, period_start=period_start).delete()

    user_ids = [r["user_id"] for r in rankings]
    user_map = {u.pk: u for u in User.objects.filter(pk__in=user_ids)}

    entries = []
    for rank, row in enumerate(rankings, start=1):
        user = user_map.get(row["user_id"])
        entries.append(
            LeaderboardEntry(
                period=period,
                period_start=period_start,
                user_id=row["user_id"],
                rank=rank,
                points_earned=row["points_earned"],
                offers_completed=row["offers_completed"],
                display_name=getattr(user, "username", "—") if user else "—",
            )
        )
    LeaderboardEntry.objects.bulk_create(entries, ignore_conflicts=True)
    logger.info("Leaderboard rebuilt: period=%s entries=%d", period, len(entries))
    return {"period": period, "entries_created": len(entries)}


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def process_pending_withdrawals(self):
    """
    Sweep pending withdrawal requests older than 24h and mark them processing.
    Actual payout dispatch is handled by the payment gateway service.
    """
    import datetime
    from django.utils import timezone
    from .models import WithdrawalRequest

    cutoff = timezone.now() - datetime.timedelta(hours=24)
    pending = WithdrawalRequest.objects.filter(
        status="pending", created_at__lte=cutoff
    ).select_related("user", "payment_method")[:50]

    updated = 0
    for w in pending:
        try:
            w.status = "processing"
            w.save(update_fields=["status"])
            logger.info("Withdrawal %s moved to processing", w.pk)
            updated += 1
        except Exception as exc:
            logger.error("Failed to update withdrawal %s: %s", w.pk, exc)

    return {"processed": updated}


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def recalculate_user_tiers(self):
    """
    Recalculate UserTierMembership for all users whose lifetime_points
    have changed since their last tier check.
    Run nightly.
    """
    from .models import UserTierMembership

    memberships = UserTierMembership.objects.select_related("tier", "user").all()
    upgraded = 0
    for m in memberships:
        old_tier = m.tier_id
        m.recalculate_tier()
        if m.tier_id != old_tier:
            upgraded += 1
            logger.info("User %s tier changed to %s", m.user_id, m.tier)

    return {"total_checked": memberships.count(), "tier_changes": upgraded}


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def fire_referral_commission(self, postback_log_id: str):
    """
    Check if the rewarded user was referred by someone, and if so,
    calculate and award the referral commission.
    """
    from decimal import Decimal
    from .models import PostbackLog, UserReferral, ReferralCommission

    try:
        log = PostbackLog.objects.select_related(
            "network", "resolved_user"
        ).get(pk=postback_log_id)
    except PostbackLog.DoesNotExist:
        logger.error("fire_referral_commission: PostbackLog %s not found", postback_log_id)
        return

    if not log.resolved_user or not log.points_awarded:
        return

    try:
        referral = UserReferral.objects.select_related("program", "referrer").get(
            referee=log.resolved_user, is_active=True
        )
    except UserReferral.DoesNotExist:
        return

    program = referral.program
    if program.commission_type == "percent":
        commission_points = int(
            Decimal(str(log.points_awarded)) * program.commission_value / 100
        )
    else:
        commission_points = int(program.commission_value)

    if commission_points <= 0:
        return

    # Check minimum earning threshold
    if program.minimum_earning_for_commission > 0:
        from .models import UserOfferCompletion
        from django.db.models import Sum
        total_earned = (
            UserOfferCompletion.objects.filter(
                user=log.resolved_user, is_reversed=False
            ).aggregate(total=Sum("points_awarded"))["total"] or 0
        )
        if total_earned < program.minimum_earning_for_commission:
            logger.info(
                "Referral commission skipped: referee %s hasn't hit threshold (%d/%d)",
                log.resolved_user_id, total_earned, program.minimum_earning_for_commission,
            )
            return

    ReferralCommission.objects.create(
        referral=referral,
        postback_log=log,
        points_awarded=commission_points,
        commission_rate=program.commission_value,
    )

    # Update running total on UserReferral
    from django.db.models import F
    UserReferral.objects.filter(pk=referral.pk).update(
        total_commission_earned=F("total_commission_earned") + commission_points
    )

    logger.info(
        "Referral commission fired: referrer=%s referee=%s points=%d postback=%s",
        referral.referrer_id, log.resolved_user_id, commission_points, postback_log_id,
    )


@shared_task(bind=True, max_retries=2)
def sync_offer_catalogue(self, network_key: str):
    """
    Pull the latest offer list from a network's API and upsert Offer records.
    Only networks with a registered adapter that implements get_offers() are supported.
    """
    from .adapters.registry import get_adapter
    from .models import NetworkPostbackConfig, Offer

    try:
        network = NetworkPostbackConfig.objects.get(network_key=network_key, status="active")
    except NetworkPostbackConfig.DoesNotExist:
        logger.error("sync_offer_catalogue: network %s not found", network_key)
        return

    try:
        adapter = get_adapter(network_key)
        if not hasattr(adapter, "get_offers"):
            logger.info("Adapter %s does not support get_offers()", network_key)
            return
        offers_data = adapter.get_offers()
    except Exception as exc:
        logger.error("sync_offer_catalogue: adapter error for %s: %s", network_key, exc)
        raise self.retry(exc=exc)

    created = updated = 0
    for offer_data in offers_data:
        ext_id = offer_data.get("external_offer_id") or offer_data.get("id")
        if not ext_id:
            continue
        _, was_created = Offer.objects.update_or_create(
            network=network,
            external_offer_id=str(ext_id),
            defaults={
                "name": offer_data.get("name", ""),
                "description": offer_data.get("description", ""),
                "points_reward": offer_data.get("points_reward", 0),
                "payout_usd": offer_data.get("payout", 0),
                "countries_allowed": offer_data.get("countries_allowed", []),
                "is_active": offer_data.get("is_active", True),
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    logger.info(
        "Offer catalogue synced: network=%s created=%d updated=%d",
        network_key, created, updated,
    )
    return {"created": created, "updated": updated}


# ── Push notification tasks ────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def send_push_notification(self, user_id: str, title: str, body: str,
                            data: dict = None, platform: str = "all"):
    """
    Send a push notification to all active FCM devices for a user.
    Integrates with Firebase Cloud Messaging (FCM) HTTP v1 API.
    Set GATEWAY_FCM_SERVER_KEY in settings.
    """
    import requests
    from django.conf import settings as djs
    from .models import FCMDevice

    devices = FCMDevice.objects.filter(
        user_id=user_id, is_active=True
    )
    if platform != "all":
        devices = devices.filter(platform=platform)

    server_key = getattr(djs, "GATEWAY_FCM_SERVER_KEY", "")
    if not server_key:
        logger.warning("FCM server key not configured — push skipped for user %s", user_id)
        return {"sent": 0, "reason": "FCM not configured"}

    sent = failed = 0
    for device in devices:
        try:
            payload = {
                "to": device.registration_id,
                "notification": {"title": title, "body": body},
                "data": data or {},
            }
            resp = requests.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={
                    "Authorization": f"key={server_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=10,
            )
            if resp.status_code == 200 and resp.json().get("success") == 1:
                sent += 1
                from django.utils import timezone
                device.last_used_at = timezone.now()
                device.save(update_fields=["last_used_at"])
            else:
                # Token invalid — deactivate device
                if resp.json().get("results", [{}])[0].get("error") == "NotRegistered":
                    device.is_active = False
                    device.save(update_fields=["is_active"])
                failed += 1
        except Exception as exc:
            logger.error("FCM send failed for device %s: %s", device.pk, exc)
            failed += 1

    logger.info("Push sent: user=%s sent=%d failed=%d title=%r", user_id, sent, failed, title)
    return {"sent": sent, "failed": failed}


@shared_task(bind=True, max_retries=2)
def notify_withdrawal_approved(self, withdrawal_id: str):
    """Fire push + in-app notification when a withdrawal is approved."""
    from .models import WithdrawalRequest
    try:
        wr = WithdrawalRequest.objects.select_related("user").get(pk=withdrawal_id)
    except WithdrawalRequest.DoesNotExist:
        return
    send_push_notification.delay(
        user_id=str(wr.user_id),
        title="Withdrawal Approved ✅",
        body=f"Your withdrawal of {wr.amount_bdt} BDT has been approved and is being processed.",
        data={"type": "withdrawal_approved", "withdrawal_id": withdrawal_id},
    )


@shared_task(bind=True, max_retries=2)
def notify_tier_upgrade(self, user_id: str, new_tier_name: str):
    """Fire push notification when a user achieves a new tier."""
    send_push_notification.delay(
        user_id=user_id,
        title=f"🏆 You reached {new_tier_name}!",
        body=f"Congratulations! You've been promoted to {new_tier_name}. "
             f"Enjoy higher earning multipliers and faster withdrawal processing.",
        data={"type": "tier_upgrade", "tier": new_tier_name},
    )


@shared_task(bind=True, max_retries=2)
def notify_daily_bonus_reminder(self, user_id: str, streak_day: int, points: int):
    """Remind user to claim daily bonus (sent if unclaimed after 20h)."""
    send_push_notification.delay(
        user_id=user_id,
        title=f"🎁 Day {streak_day} bonus waiting!",
        body=f"Don't break your streak — claim your {points} point bonus today!",
        data={"type": "daily_bonus_reminder", "day": streak_day, "points": points},
    )


@shared_task(bind=True, max_retries=2)
def notify_referral_commission_earned(self, user_id: str, points: int, referee_name: str):
    """Notify referrer when they earn a commission."""
    send_push_notification.delay(
        user_id=user_id,
        title="💰 Referral commission earned!",
        body=f"You earned {points} points because {referee_name} completed an offer.",
        data={"type": "referral_commission", "points": points},
    )
