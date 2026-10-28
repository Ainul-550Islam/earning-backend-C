# engagement/celery_beat.py
"""
Celery Beat schedule for all engagement periodic tasks.

Add to your Django settings:

    from engagement.celery_beat import ENGAGEMENT_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {
        **CELERY_BEAT_SCHEDULE,          # your existing schedules
        **ENGAGEMENT_BEAT_SCHEDULE,      # engagement tasks
    }

Or if you have no existing schedule:

    from engagement.celery_beat import ENGAGEMENT_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = ENGAGEMENT_BEAT_SCHEDULE
"""
from celery.schedules import crontab

ENGAGEMENT_BEAT_SCHEDULE = {

    # ── Leaderboard ───────────────────────────────────────────────────────────

    # Rebuild leaderboard every hour (so rankings stay fresh during the day)
    "engagement-rebuild-leaderboard-hourly": {
        "task":     "engagement.tasks.rebuild_daily_leaderboard",
        "schedule": crontab(minute=0),          # top of every hour
        "options":  {"expires": 55 * 60},       # expire if not picked up in 55 min
    },

    # Distribute yesterday's rewards at 00:05 UTC every day
    "engagement-distribute-rewards-daily": {
        "task":     "engagement.tasks.distribute_daily_rewards",
        "schedule": crontab(hour=0, minute=5),
        "options":  {"expires": 30 * 60},
    },

    # ── Quests ────────────────────────────────────────────────────────────────

    # Init daily quest rows for all active users at 00:01 UTC
    "engagement-init-daily-quests": {
        "task":     "engagement.tasks.init_daily_quests_all_users",
        "schedule": crontab(hour=0, minute=1),
        "options":  {"expires": 20 * 60},
    },

    # Expire yesterday's incomplete daily quests at 00:02 UTC
    "engagement-expire-daily-quests": {
        "task":     "engagement.tasks.expire_old_quests",
        "schedule": crontab(hour=0, minute=2),
        "options":  {"expires": 15 * 60},
    },

    # ── Shop ──────────────────────────────────────────────────────────────────

    # Expire timed shop items (streak shields, spin boosts, etc.) every hour
    "engagement-expire-shop-inventory": {
        "task":     "engagement.tasks.expire_shop_inventory",
        "schedule": crontab(minute=30),         # half past every hour
        "options":  {"expires": 25 * 60},
    },

    # ── Notifications ─────────────────────────────────────────────────────────

    # Send streak-at-risk reminders at 20:00 UTC (8 PM)
    "engagement-streak-reminders": {
        "task":     "engagement.tasks.send_streak_reminders",
        "schedule": crontab(hour=20, minute=0),
        "options":  {"expires": 60 * 60},
    },

    # Send daily leaderboard snapshot notification at 18:00 UTC (6 PM)
    "engagement-leaderboard-snapshot": {
        "task":     "engagement.tasks.send_leaderboard_snapshot",
        "schedule": crontab(hour=18, minute=0),
        "options":  {"expires": 60 * 60},
    },
}

# ── Advanced system tasks ─────────────────────────────────────────────────────
ENGAGEMENT_BEAT_SCHEDULE.update({
    "engagement-aggregate-analytics":      {"task": "engagement.tasks.aggregate_daily_analytics",      "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(hour=0,  minute=15)},
    "engagement-compute-retention":        {"task": "engagement.tasks.compute_retention_cohorts",      "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(hour=1,  minute=0)},
    "engagement-retry-webhooks":           {"task": "engagement.tasks.retry_failed_webhooks",          "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(minute="*/5")},
    "engagement-anticheat-scan":           {"task": "engagement.tasks.run_anticheat_scan",             "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(minute=0, hour="*/2")},
    "engagement-guild-leaderboard":        {"task": "engagement.tasks.rebuild_guild_leaderboard",      "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(minute=30, hour="*/2")},
    "engagement-expire-events":            {"task": "engagement.tasks.expire_seasonal_events",         "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(minute=0)},
    "engagement-close-auctions":           {"task": "engagement.tasks.close_expired_auctions",         "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(minute="*/5")},
    "engagement-deliver-campaigns":        {"task": "engagement.tasks.deliver_scheduled_campaigns",    "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(minute="*/5")},
    "engagement-sync-segments":            {"task": "engagement.tasks.sync_all_segments",              "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(hour=2, minute=0)},
    "engagement-check-milestones":         {"task": "engagement.tasks.check_milestones_all_users",     "schedule": __import__("celery.schedules", fromlist=["crontab"]).crontab(hour=3, minute=0)},
})
