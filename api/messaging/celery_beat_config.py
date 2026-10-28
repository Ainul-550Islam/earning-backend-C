"""
Messaging Celery Beat Schedule — All periodic tasks for the messaging module.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIRED SETUP — add these lines to your project's settings.py:

    from api.messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE

    CELERY_BEAT_SCHEDULE = {
        # ... your existing tasks ...
    }
    CELERY_BEAT_SCHEDULE.update(MESSAGING_BEAT_SCHEDULE)

Without this, the following will NOT work automatically:
  - Scheduled messages (send_scheduled_messages)
  - Presence cleanup  (cleanup_presence)
  - Disappearing messages (expire_disappearing_messages)
  - Call expiry       (expire_calls)
  - Story expiry      (expire_stories)
  - Broadcast sends   (send_scheduled_broadcasts, send_scheduled_cpa_broadcasts)
  - Payout reminders  (send_payout_reminders)
  - All cleanup jobs  (inbox, edit history, calls, polls, media, CPA notifications)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

All task names match the @shared_task(name=...) decorators in:
  - messaging/tasks.py
  - messaging/tasks_cpa.py
"""
from celery.schedules import crontab

MESSAGING_BEAT_SCHEDULE: dict = {

    # ── Every 60 seconds ──────────────────────────────────────────────────────
    # Picks up ScheduledMessage rows whose send_at <= now and status=PENDING.
    "messaging.send_scheduled_messages": {
        "task":     "messaging.send_scheduled_messages",
        "schedule": 60,
    },

    # ── Every 2 minutes ───────────────────────────────────────────────────────
    # Marks UserPresence rows as OFFLINE when last_seen > PRESENCE_TIMEOUT.
    "messaging.cleanup_presence": {
        "task":     "messaging.cleanup_presence",
        "schedule": 120,
    },

    # ── Every 5 minutes ───────────────────────────────────────────────────────
    # Hard-deletes or blanks ChatMessage rows past their disappearing timer.
    "messaging.expire_disappearing_messages": {
        "task":     "messaging.expire_disappearing_messages",
        "schedule": 300,
    },
    # Closes CallSession rows stuck in INITIATED/RINGING for > 2 minutes.
    "messaging.expire_calls": {
        "task":     "messaging.expire_calls",
        "schedule": 300,
    },
    # Marks PollVote rows as closed after their deadline passes.
    "messaging.cleanup_expired_polls": {
        "task":     "messaging.cleanup_expired_polls",
        "schedule": 300,
    },

    # ── Every 10 minutes ──────────────────────────────────────────────────────
    # Batch-scan recent messages for spam patterns (supplementary to per-send check).
    "messaging.scan_for_spam": {
        "task":     "messaging.scan_for_spam",
        "schedule": 600,
    },

    # ── Every 15 minutes ──────────────────────────────────────────────────────
    # Expires UserStory rows whose created_at + 24h < now.
    "messaging.expire_stories": {
        "task":     "messaging.expire_stories",
        "schedule": 900,
    },

    # ── Hourly ────────────────────────────────────────────────────────────────
    # Sends AdminBroadcast rows whose scheduled_at <= now and status=SCHEDULED.
    "messaging.send_scheduled_broadcasts": {
        "task":     "messaging.send_scheduled_broadcasts",
        "schedule": crontab(minute=0),   # top of every hour
    },
    # Sends CPABroadcast rows whose scheduled_at <= now and status=SCHEDULED.
    "messaging.send_scheduled_cpa_broadcasts": {
        "task":     "messaging.send_scheduled_cpa_broadcasts",
        "schedule": crontab(minute=5),   # 5 past every hour
    },

    # ── Daily ─────────────────────────────────────────────────────────────────
    # Sends payout reminder notifications to affiliates whose balance >= threshold
    # but haven't been paid in the configured window.
    "messaging.send_payout_reminders": {
        "task":     "messaging.send_payout_reminders",
        "schedule": crontab(hour=9, minute=0),   # 09:00 daily (UTC)
    },
    # Auto-reviews MessageReport rows flagged by the spam detector.
    "messaging.review_reported_messages": {
        "task":     "messaging.review_reported_messages",
        "schedule": crontab(hour=6, minute=0),   # 06:00 daily (UTC)
    },
    # Deletes UserStory rows older than settings.STORY_RETENTION_DAYS (default 7).
    "messaging.cleanup_old_stories": {
        "task":     "messaging.cleanup_old_stories",
        "schedule": crontab(hour=2, minute=0),   # 02:00 daily (UTC)
    },
    # Deletes CallSession rows older than 30 days.
    "messaging.cleanup_old_call_sessions": {
        "task":     "messaging.cleanup_old_call_sessions",
        "schedule": crontab(hour=3, minute=0),   # 03:00 daily (UTC)
    },

    # ── Weekly (Sunday early morning UTC) ─────────────────────────────────────
    # Deletes UserInbox rows older than settings.INBOX_RETENTION_DAYS (default 90).
    "messaging.cleanup_old_inbox_items": {
        "task":     "messaging.cleanup_old_inbox_items",
        "schedule": crontab(hour=1, minute=0, day_of_week="sunday"),
    },
    # Deletes MessageEditHistory rows older than 365 days.
    "messaging.cleanup_old_edit_history": {
        "task":     "messaging.cleanup_old_edit_history",
        "schedule": crontab(hour=1, minute=30, day_of_week="sunday"),
    },
    # Deletes CPANotification rows older than 90 days.
    "messaging.cleanup_old_cpa_notifications": {
        "task":     "messaging.cleanup_old_cpa_notifications",
        "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
    },
    # Deletes MediaAttachment rows (and S3 objects) older than 365 days.
    "messaging.cleanup_media_attachments": {
        "task":     "messaging.cleanup_media_attachments",
        "schedule": crontab(hour=2, minute=30, day_of_week="sunday"),
    },
}
