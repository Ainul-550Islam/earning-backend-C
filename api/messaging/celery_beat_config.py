"""
Messaging Celery Beat Schedule — All periodic tasks.

Add to your project's CELERY_BEAT_SCHEDULE in settings.py:

    from messaging.celery_beat_config import MESSAGING_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(MESSAGING_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

MESSAGING_BEAT_SCHEDULE = {

    # ── Every minute ──────────────────────────────────────────────────────────
    "messaging.send_scheduled_messages": {
        "task":     "messaging.send_scheduled_messages",
        "schedule": 60,  # every 60 seconds
    },

    # ── Every 2 minutes ───────────────────────────────────────────────────────
    "messaging.cleanup_presence": {
        "task":     "messaging.cleanup_presence",
        "schedule": 120,
    },

    # ── Every 5 minutes ───────────────────────────────────────────────────────
    "messaging.expire_disappearing_messages": {
        "task":     "messaging.expire_disappearing_messages",
        "schedule": 300,
    },
    "messaging.expire_calls": {
        "task":     "messaging.expire_calls",
        "schedule": 300,
    },
    "messaging.cleanup_expired_polls": {
        "task":     "messaging.cleanup_expired_polls",
        "schedule": 300,
    },

    # ── Every 15 minutes ──────────────────────────────────────────────────────
    "messaging.expire_stories": {
        "task":     "messaging.expire_stories",
        "schedule": 900,
    },

    # ── Every 10 minutes ──────────────────────────────────────────────────────
    "messaging.scan_for_spam": {
        "task":     "messaging.scan_for_spam",
        "schedule": 600,
    },

    # ── Hourly ────────────────────────────────────────────────────────────────
    "messaging.send_scheduled_broadcasts": {
        "task":     "messaging.send_scheduled_broadcasts",
        "schedule": crontab(minute=0),  # top of every hour
    },
    "messaging.send_scheduled_cpa_broadcasts": {
        "task":     "messaging.send_scheduled_cpa_broadcasts",
        "schedule": crontab(minute=5),  # 5 past every hour
    },

    # ── Daily ─────────────────────────────────────────────────────────────────
    "messaging.send_payout_reminders": {
        "task":     "messaging.send_payout_reminders",
        "schedule": crontab(hour=9, minute=0),  # 9 AM daily
    },
    "messaging.review_reported_messages": {
        "task":     "messaging.review_reported_messages",
        "schedule": crontab(hour=6, minute=0),  # 6 AM daily
    },
    "messaging.cleanup_old_stories": {
        "task":     "messaging.cleanup_old_stories",
        "schedule": crontab(hour=2, minute=0),  # 2 AM daily
    },
    "messaging.cleanup_old_call_sessions": {
        "task":     "messaging.cleanup_old_call_sessions",
        "schedule": crontab(hour=3, minute=0),  # 3 AM daily
    },

    # ── Weekly ────────────────────────────────────────────────────────────────
    "messaging.cleanup_old_inbox_items": {
        "task":     "messaging.cleanup_old_inbox_items",
        "schedule": crontab(hour=1, minute=0, day_of_week="sunday"),
    },
    "messaging.cleanup_old_edit_history": {
        "task":     "messaging.cleanup_old_edit_history",
        "schedule": crontab(hour=1, minute=30, day_of_week="sunday"),
    },
    "messaging.cleanup_old_cpa_notifications": {
        "task":     "messaging.cleanup_old_cpa_notifications",
        "schedule": crontab(hour=2, minute=0, day_of_week="sunday"),
    },
    "messaging.cleanup_media_attachments": {
        "task":     "messaging.cleanup_media_attachments",
        "schedule": crontab(hour=2, minute=30, day_of_week="sunday"),
    },
}
