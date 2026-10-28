"""
api/notifications/payout_tasks.py
===================================
Notification Celery task for api.payout_queue.

HOW IT WORKS
------------
receivers._send_notification() calls this task when a payout batch
completes or fails, IF settings.PAYOUT_NOTIFICATION_TASK is set:

    PAYOUT_NOTIFICATION_TASK = "api.notifications.payout_tasks.send_payout_notification"

The task sends a push/in-app/email notification to the batch creator.

CHANNELS SUPPORTED (implement based on your api.notifications app)
-------------------------------------------------------------------
  push   — Firebase FCM / APNs push notification
  in_app — In-app notification (stored in DB, shown in UI)
  email  — Django email (send_mail)
  sms    — SMS via bKash SMS / Twilio (optional)

NOTIFICATION MODEL ASSUMPTIONS
-------------------------------
This task assumes your api.notifications app has roughly:

    class Notification(models.Model):
        user              = models.ForeignKey(User, on_delete=models.CASCADE)
        title             = models.CharField(max_length=255)
        body              = models.TextField()
        notification_type = models.CharField(max_length=50)
        channel           = models.CharField(max_length=20, default="push")
        is_read           = models.BooleanField(default=False)
        metadata          = models.JSONField(default=dict)
        created_at        = models.DateTimeField(auto_now_add=True)

Adjust field names and channel logic to match your actual implementation.

ADD TO settings/base.py
-----------------------
    PAYOUT_NOTIFICATION_TASK = "api.notifications.payout_tasks.send_payout_notification"
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    bind=True,
    name="notifications.send_payout_notification",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    soft_time_limit=25,
    time_limit=30,
)
def send_payout_notification(
    self,
    *,
    user_id: Any,
    event: str,
    data: dict,
) -> dict:
    """
    Send a push/in-app notification when a payout batch completes or fails.

    Called by: api.payout_queue.receivers._send_notification()
    Via:       settings.PAYOUT_NOTIFICATION_TASK

    Args:
        user_id: PK of the User to notify (batch creator).
        event:   "completed" | "failed"
        data:    Payload dict from _batch_payload():
                 {batch_id, batch_name, gateway, status,
                  success_count, failure_count, net_amount, ...}

    Returns:
        Dict with sent_channels list and status.
    """
    task_id = self.request.id or "unknown"

    if not user_id:
        logger.warning("[task=%s] send_payout_notification: user_id is None — skip.", task_id)
        return {"status": "skipped", "reason": "no user_id"}

    if event not in ("completed", "failed"):
        logger.warning(
            "[task=%s] send_payout_notification: unknown event=%r — skip.", task_id, event
        )
        return {"status": "skipped", "reason": f"unknown event: {event}"}

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.warning(
            "[task=%s] send_payout_notification: user pk=%s not found.", task_id, user_id
        )
        return {"status": "skipped", "reason": "user not found"}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

    title, body = _build_message(event=event, data=data)
    notification_type = "PAYOUT_SUCCESS" if event == "completed" else "PAYOUT_FAILED"
    sent_channels: list[str] = []

    # ── Channel 1: In-app notification (DB) ──────────────────────────────────
    try:
        from api.notifications.models import Notification
        Notification.objects.create(
            user=user,
            title=title,
            body=body,
            notification_type=notification_type,
            channel="in_app",
            is_read=False,
            metadata=data,
        )
        sent_channels.append("in_app")
        logger.debug(
            "[task=%s] send_payout_notification: in_app created for user=%s", task_id, user_id
        )
    except ImportError:
        logger.warning(
            "[task=%s] send_payout_notification: api.notifications.models.Notification "
            "not found — in_app channel skipped.",
            task_id,
        )
    except Exception as exc:
        logger.error(
            "[task=%s] send_payout_notification: in_app failed for user=%s: %s",
            task_id, user_id, exc,
        )

    # ── Channel 2: Push notification (FCM) ───────────────────────────────────
    # Uncomment when you have FCM configured in api.notifications:
    #
    # try:
    #     from api.notifications.services import send_push
    #     send_push(
    #         user=user,
    #         title=title,
    #         body=body,
    #         data={"type": notification_type, "batch_id": data.get("batch_id", "")},
    #     )
    #     sent_channels.append("push")
    # except Exception as exc:
    #     logger.warning("[task=%s] push failed: %s", task_id, exc)

    # ── Channel 3: Email notification ────────────────────────────────────────
    # Uncomment to enable email notifications:
    #
    # try:
    #     if user.email:
    #         _send_email_notification(user=user, event=event, title=title, body=body, data=data)
    #         sent_channels.append("email")
    # except Exception as exc:
    #     logger.warning("[task=%s] email failed: %s", task_id, exc)

    logger.info(
        "[task=%s] send_payout_notification: user=%s event=%s channels=%s",
        task_id, user_id, event, sent_channels,
    )
    return {
        "status":       "sent" if sent_channels else "no_channels",
        "user_id":      user_id,
        "event":        event,
        "sent_channels": sent_channels,
    }


def _build_message(event: str, data: dict) -> tuple[str, str]:
    """
    Build notification title and body from event type and batch data.
    Returns (title, body) tuple.
    Customise the messages to match your platform's tone/language.
    """
    batch_name  = data.get("batch_name", "Payout Batch")
    net_amount  = data.get("net_amount",  "0.00")
    success_cnt = data.get("success_count", 0)
    failure_cnt = data.get("failure_count", 0)
    gateway     = data.get("gateway", "")

    if event == "completed":
        title = "✅ Payout Completed"
        body  = (
            f"'{batch_name}' processed successfully. "
            f"{success_cnt} payment(s) totalling {net_amount} BDT sent via {gateway}."
        )
    else:
        title = "❌ Payout Failed"
        body  = (
            f"'{batch_name}' could not be processed. "
            f"{failure_cnt} payment(s) failed. Please review and retry."
        )
    return title, body


def _send_email_notification(
    *, user, event: str, title: str, body: str, data: dict
) -> None:
    """
    Send a payout result email to the batch creator.
    Called from send_payout_notification() if email channel is enabled.
    """
    from django.core.mail import send_mail
    from django.conf import settings as _settings

    from_email = getattr(_settings, "DEFAULT_FROM_EMAIL", "noreply@your-platform.com")

    html_message = _build_email_html(event=event, title=title, body=body, data=data)

    send_mail(
        subject=title,
        message=body,             # plain-text fallback
        from_email=from_email,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
    logger.info(
        "_send_email_notification: sent %s email to user=%s email=%s",
        event, user.pk, user.email,
    )


def _build_email_html(*, event: str, title: str, body: str, data: dict) -> str:
    """
    Build a simple HTML email body for payout notifications.
    Replace with your platform's email template system if available
    (e.g. Django templates, MJML, Sendgrid templates).
    """
    batch_name   = data.get("batch_name",   "Payout Batch")
    batch_id     = data.get("batch_id",     "")
    net_amount   = data.get("net_amount",   "0.00")
    success_cnt  = data.get("success_count", 0)
    failure_cnt  = data.get("failure_count", 0)
    gateway      = data.get("gateway",      "")
    status_color = "#1D9E75" if event == "completed" else "#E24B4A"

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:20px;margin:0">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:8px;
              overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.08)">
    <div style="background:{status_color};padding:20px 24px">
      <h1 style="color:#fff;margin:0;font-size:20px">{title}</h1>
    </div>
    <div style="padding:24px">
      <p style="color:#333;font-size:15px;line-height:1.6">{body}</p>
      <table style="width:100%;border-collapse:collapse;margin-top:16px;font-size:14px">
        <tr style="background:#f8f8f8">
          <td style="padding:8px 12px;color:#666;border:1px solid #eee">Batch Name</td>
          <td style="padding:8px 12px;font-weight:500;border:1px solid #eee">{batch_name}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;color:#666;border:1px solid #eee">Batch ID</td>
          <td style="padding:8px 12px;font-family:monospace;font-size:12px;border:1px solid #eee">{batch_id}</td>
        </tr>
        <tr style="background:#f8f8f8">
          <td style="padding:8px 12px;color:#666;border:1px solid #eee">Gateway</td>
          <td style="padding:8px 12px;font-weight:500;border:1px solid #eee">{gateway}</td>
        </tr>
        <tr>
          <td style="padding:8px 12px;color:#666;border:1px solid #eee">Net Amount</td>
          <td style="padding:8px 12px;font-weight:500;color:{status_color};border:1px solid #eee">{net_amount} BDT</td>
        </tr>
        <tr style="background:#f8f8f8">
          <td style="padding:8px 12px;color:#666;border:1px solid #eee">Successful</td>
          <td style="padding:8px 12px;color:#1D9E75;font-weight:500;border:1px solid #eee">{success_cnt}</td>
        </tr>
        {"" if not failure_cnt else f'''
        <tr>
          <td style="padding:8px 12px;color:#666;border:1px solid #eee">Failed</td>
          <td style="padding:8px 12px;color:#E24B4A;font-weight:500;border:1px solid #eee">{failure_cnt}</td>
        </tr>'''}
      </table>
    </div>
    <div style="background:#f8f8f8;padding:14px 24px;font-size:12px;color:#999;border-top:1px solid #eee">
      This is an automated notification from your payout system.
      Please do not reply to this email.
    </div>
  </div>
</body>
</html>
"""
