"""
CPA Messaging Celery Tasks — Async notification delivery and scheduling.
"""
from __future__ import annotations
import logging
from typing import Any
from celery import shared_task
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30, name="messaging.deliver_cpa_notification")
def deliver_cpa_notification_task(self, notification_id: str) -> dict:
    """
    Deliver a CPANotification via push, email, and/or SMS based on priority.
    - NORMAL: push only
    - HIGH: push + inbox badge update
    - URGENT: push + email + SMS

    Part 6 audit note: SMS is not implemented - CPANotification.sms_sent
    exists as a real model field (confirming it was intended, not just
    docstring aspiration), but no SMS provider is configured anywhere in
    this codebase. Flagged rather than guessed at (no provider chosen, no
    credentials) - sms_sent stays False and results["sms"] reports
    "not_configured" rather than silently claiming success.
    """
    from .models import CPANotification
    from .utils.notifier import _send_push_to_user
    from django.utils import timezone

    try:
        notif = CPANotification.objects.select_related("recipient").get(pk=notification_id)
    except CPANotification.DoesNotExist:
        return {"ok": False, "error": "not_found"}

    results = {"notification_id": notification_id}

    # Part 6 audit fix: CPABroadcast has explicit send_push/send_email/
    # send_sms fields an admin configures per-campaign, but
    # send_cpa_broadcast_task's created notifications were previously
    # delivered purely by this task's own priority-based heuristic,
    # completely ignoring them - a broadcast explicitly configured with
    # send_email=False would still get an email if its priority happened
    # to be HIGH/URGENT, and send_email=True had no effect at NORMAL
    # priority. Broadcast-originated notifications now carry their
    # channel intent in payload (set by send_cpa_broadcast_task below);
    # anything else - every notify_*() call in services_cpa.py - has no
    # such keys and falls back to the original priority-based behavior
    # unchanged.
    channel_prefs = notif.payload if isinstance(notif.payload, dict) else {}
    want_push  = channel_prefs.get("send_push", True)
    want_email = channel_prefs.get("send_email", notif.priority in ("HIGH", "URGENT"))
    want_sms   = channel_prefs.get("send_sms", False)

    # Push notification
    if want_push:
        try:
            ok = _send_push_to_user(
                user_id=notif.recipient_id,
                title=notif.title,
                body=notif.body[:200],
                data={
                    "type": notif.notification_type,
                    "object_type": notif.object_type,
                    "object_id": notif.object_id,
                    "action_url": notif.action_url,
                },
                priority="high" if notif.priority in ("HIGH", "URGENT") else "normal",
            )
            if ok:
                # Part 6 audit fix: this update used to run unconditionally
                # right after the call, regardless of whether `ok` was True
                # or False - marking push_sent=True (and stamping
                # push_sent_at) for pushes that had actually failed (e.g.
                # no active device tokens, every platform failed), as long
                # as _send_push_to_user() itself didn't raise. push_sent is
                # meant to record success, not "an attempt was made".
                CPANotification.objects.filter(pk=notification_id).update(
                    push_sent=True, push_sent_at=timezone.now()
                )
            results["push"] = "sent" if ok else "failed"
        except Exception as exc:
            results["push_error"] = str(exc)
    else:
        results["push"] = "skipped"

    # Email
    if want_email:
        try:
            _send_notification_email(
                user_id=notif.recipient_id,
                title=notif.title,
                body=notif.body,
                action_url=notif.action_url,
                action_label=notif.action_label,
            )
            CPANotification.objects.filter(pk=notification_id).update(
                email_sent=True, email_sent_at=timezone.now()
            )
            results["email"] = "sent"
        except Exception as exc:
            results["email_error"] = str(exc)
    else:
        results["email"] = "skipped"

    # SMS - not implemented, see docstring note above.
    if want_sms:
        logger.warning(
            "deliver_cpa_notification_task: SMS requested for notification=%s "
            "but no SMS provider is configured - skipping.",
            notification_id,
        )
        results["sms"] = "not_configured"

    # Real-time WebSocket (if user is connected)
    try:
        from .utils.notifier import send_websocket_event
        send_websocket_event(
            group_name=f"user_devices_{notif.recipient_id}",
            event_type="cpa.notification",
            data={
                "id": str(notif.id),
                "type": notif.notification_type,
                "title": notif.title,
                "body": notif.body,
                "priority": notif.priority,
                "action_url": notif.action_url,
                "action_label": notif.action_label,
                "payload": notif.payload,
                "created_at": notif.created_at.isoformat(),
            },
        )
        results["websocket"] = "sent"
    except Exception as exc:
        results["websocket_error"] = str(exc)

    logger.info("deliver_cpa_notification_task: %s → %s", notification_id, results)
    return results


def _send_notification_email(user_id, title, body, action_url, action_label):
    """Send email for high-priority CPA notifications. Integrate with your email system."""
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        if not user.email:
            return
        send_mail(
            subject=title,
            message=body + (f"\n\n{action_label}: {action_url}" if action_url else ""),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning("_send_notification_email: user=%s error=%s", user_id, exc)


@shared_task(bind=True, max_retries=2, name="messaging.send_cpa_broadcast")
def send_cpa_broadcast_task(self, broadcast_id: str) -> dict:
    """Execute a CPA broadcast — resolve audience and send notifications."""
    from .models import CPABroadcast, CPANotification
    from .services_cpa import _resolve_cpa_broadcast_audience, _create_notification
    from django.utils import timezone

    try:
        broadcast = CPABroadcast.objects.get(pk=broadcast_id)
    except CPABroadcast.DoesNotExist:
        return {"ok": False, "error": "not_found"}

    CPABroadcast.objects.filter(pk=broadcast_id).update(status="SENDING")

    try:
        recipient_ids = _resolve_cpa_broadcast_audience(broadcast)
        total = len(recipient_ids)
        CPABroadcast.objects.filter(pk=broadcast_id).update(recipient_count=total)

        # Part 6 audit fix: on a retry after partial failure (this task
        # has max_retries=2 and a broad except below that can re-run the
        # whole function), audience resolution and notification creation
        # both re-ran from scratch, re-notifying everyone including
        # recipients who'd already gotten a notification in the earlier,
        # failed attempt - duplicate pushes/emails for a subset of the
        # audience on any retry. CPANotification has no direct FK to
        # CPABroadcast, but every notification this task creates carries
        # the broadcast's id in its payload (below), so that's used to
        # find and skip recipients already notified for *this* broadcast.
        already_notified = set(
            CPANotification.objects.filter(
                payload__broadcast_id=str(broadcast.id)
            ).values_list("recipient_id", flat=True)
        )
        delivered = len(already_notified)
        BATCH_SIZE = 500
        for i in range(0, total, BATCH_SIZE):
            batch = recipient_ids[i:i + BATCH_SIZE]
            for uid in batch:
                if uid in already_notified:
                    continue
                try:
                    _create_notification(
                        recipient_id=uid,
                        notification_type=broadcast.notification_type,
                        title=broadcast.title,
                        body=broadcast.body,
                        priority=broadcast.priority,
                        action_url=broadcast.action_url,
                        action_label=broadcast.action_label,
                        payload={
                            "broadcast_id": str(broadcast.id),
                            "audience_filter": broadcast.audience_filter,
                            # Part 6 audit fix: the broadcast's own
                            # delivery-channel configuration was
                            # previously created here but never actually
                            # read by anything - deliver_cpa_notification_
                            # task now reads these to decide which
                            # channels to attempt for this notification.
                            "send_push": broadcast.send_push,
                            "send_email": broadcast.send_email,
                            "send_sms": broadcast.send_sms,
                        },
                        tenant=broadcast.tenant,
                    )
                    delivered += 1
                except Exception as exc:
                    logger.warning("send_cpa_broadcast_task: failed for user=%s: %s", uid, exc)

            CPABroadcast.objects.filter(pk=broadcast_id).update(delivered_count=delivered)

        CPABroadcast.objects.filter(pk=broadcast_id).update(
            status="SENT", sent_at=timezone.now(), delivered_count=delivered
        )
        logger.info("send_cpa_broadcast_task: id=%s delivered=%d/%d", broadcast_id, delivered, total)
        return {"ok": True, "broadcast_id": broadcast_id, "delivered": delivered, "total": total}

    except Exception as exc:
        logger.error("send_cpa_broadcast_task: FAILED id=%s: %s", broadcast_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=30)
        CPABroadcast.objects.filter(pk=broadcast_id).update(
            status="FAILED", error_message=str(exc)[:500]
        )
        raise


@shared_task(name="messaging.send_scheduled_cpa_broadcasts")
def send_scheduled_cpa_broadcasts() -> dict:
    """Beat task: send due scheduled CPA broadcasts."""
    from django.utils import timezone
    from .models import CPABroadcast
    due = CPABroadcast.objects.filter(status="SCHEDULED", scheduled_at__lte=timezone.now())
    count = 0
    for b in due:
        send_cpa_broadcast_task.delay(str(b.id))
        count += 1
    return {"dispatched": count}


@shared_task(name="messaging.send_payout_reminders")
def send_payout_reminders() -> dict:
    """
    Beat task: send payout reminder notifications day before scheduled payout.
    Integrate with your payout/billing system.
    """
    from .services_cpa import notify_payout_pending_reminder
    from django.utils import timezone
    from datetime import timedelta

    tomorrow = timezone.now().date() + timedelta(days=1)
    sent = 0

    # Stub: Integrate with your payout model
    # Example:
    # from api.earnings.models import ScheduledPayout
    # payouts = ScheduledPayout.objects.filter(
    #     scheduled_date=tomorrow, status='pending'
    # ).select_related('affiliate')
    # for payout in payouts:
    #     notify_payout_pending_reminder(
    #         affiliate_id=payout.affiliate_id,
    #         amount=f"${payout.amount:.2f}",
    #         payout_date=tomorrow.strftime("%B %d, %Y"),
    #     )
    #     sent += 1

    logger.info("send_payout_reminders: sent=%d (integrate with your payout model)", sent)
    return {"sent": sent, "date": str(tomorrow)}


@shared_task(name="messaging.cleanup_old_cpa_notifications")
def cleanup_old_cpa_notifications(days: int = 90) -> dict:
    """Delete read+dismissed notifications older than days."""
    from django.utils import timezone
    from datetime import timedelta
    from .models import CPANotification

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = CPANotification.objects.filter(
        is_read=True, is_dismissed=True, created_at__lt=cutoff
    ).delete()
    logger.info("cleanup_old_cpa_notifications: deleted %d records", deleted)
    return {"deleted": deleted}