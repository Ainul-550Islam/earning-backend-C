# Copyright © 2026 Ainul Enterprise Engine. All Rights Reserved.
"""
Ainul Enterprise Engine — Celery Configuration
celery.py  (NEW FILE)

FIX: All 14 Celery tasks were defined and registered but NO beat schedule
existed anywhere in the codebase — tasks never ran automatically.
This file wires every task to a schedule.

Usage (in your root settings.py / celeryconfig.py):
    from api.webhooks.celery import WEBHOOK_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(WEBHOOK_BEAT_SCHEDULE)

Or point Celery directly:
    CELERY_BEAT_SCHEDULE = {
        **WEBHOOK_BEAT_SCHEDULE,
        # ... your other app schedules
    }

All task names match their @shared_task(name=...) declarations.
Adjust intervals in settings.py via WEBHOOKS['BEAT_OVERRIDES'] = {...}.
"""

from celery.schedules import crontab
from django.conf import settings

# ── Allow per-deployment overrides ───────────────────────────────────────────
_overrides = getattr(settings, "WEBHOOKS", {}).get("BEAT_OVERRIDES", {})


def _sched(key: str, default):
    """Return override schedule or default."""
    return _overrides.get(key, default)


# ── Beat schedule ─────────────────────────────────────────────────────────────
WEBHOOK_BEAT_SCHEDULE = {

    # ── Core: retry failed dispatches every 5 min ────────────────────────────
    "webhooks-retry-failed-dispatch": {
        "task":     "ainul.webhooks.retry_failed_dispatch",
        "schedule": _sched("retry_failed", 300),          # 5 min
        "options":  {"queue": "webhooks_core"},
    },

    # ── Core: auto-suspend unhealthy endpoints every hour ────────────────────
    "webhooks-auto-suspend-endpoints": {
        "task":     "ainul.webhooks.auto_suspend_endpoints",
        "schedule": _sched("auto_suspend", 3600),          # 1 hr
        "options":  {"queue": "webhooks_core"},
    },

    # ── Core: reap exhausted delivery logs every 12 hours ────────────────────
    "webhooks-reap-exhausted-logs": {
        "task":     "ainul.webhooks.reap_exhausted_logs",
        "schedule": _sched("reap_exhausted", 43200),       # 12 hr
        "options":  {"queue": "webhooks_core"},
    },

    # ── Health: check all endpoints every hour ────────────────────────────────
    "webhooks-health-check-all": {
        "task":     "webhooks.health.check_all_endpoints",
        "schedule": _sched("health_check", 3600),          # 1 hr
        "options":  {"queue": "webhooks_health"},
    },

    # ── Aging: full sweep every 6 hours ──────────────────────────────────────
    "webhooks-aging-full-sweep": {
        "task":     "webhooks.aging.full_sweep",
        "schedule": _sched("aging_sweep", 21600),          # 6 hr
        "options":  {"queue": "webhooks_aging"},
    },

    # ── Aging: archive due records every 12 hours ─────────────────────────────
    "webhooks-aging-archive-due": {
        "task":     "webhooks.aging.archive_due",
        "schedule": _sched("aging_archive", 43200),        # 12 hr
        "options":  {"queue": "webhooks_aging"},
    },

    # ── Aging: purge dry-run daily at 01:00 UTC ───────────────────────────────
    "webhooks-aging-purge-dry-run": {
        "task":     "webhooks.aging.purge_dry_run",
        "schedule": _sched("aging_purge_dry", crontab(hour=1, minute=0)),
        "options":  {"queue": "webhooks_aging"},
    },

    # ── Aging: destructive purge weekly Sunday 02:00 UTC ─────────────────────
    "webhooks-aging-purge-execute": {
        "task":     "webhooks.aging.purge_execute",
        "schedule": _sched("aging_purge_exec", crontab(hour=2, minute=0, day_of_week=0)),
        "options":  {"queue": "webhooks_aging"},
    },

    # ── Analytics: daily stats at 00:30 UTC ───────────────────────────────────
    "webhooks-analytics-daily": {
        "task":     "webhooks.analytics.generate_daily_analytics_all_endpoints",
        "schedule": _sched("analytics_daily", crontab(hour=0, minute=30)),
        "options":  {"queue": "webhooks_analytics"},
    },

    # ── Analytics: event statistics daily at 00:45 UTC ───────────────────────
    "webhooks-event-statistics": {
        "task":     "webhooks.analytics.generate_event_statistics_all_endpoints",
        "schedule": _sched("event_stats", crontab(hour=0, minute=45)),
        "options":  {"queue": "webhooks_analytics"},
    },

    # ── Analytics: performance metrics daily at 01:00 UTC ────────────────────
    "webhooks-performance-metrics": {
        "task":     "webhooks.analytics.calculate_performance_metrics_all_endpoints",
        "schedule": _sched("perf_metrics", crontab(hour=1, minute=0)),
        "options":  {"queue": "webhooks_analytics"},
    },

    # ── Rate limiting: reset counters hourly ─────────────────────────────────
    "webhooks-rate-limit-reset": {
        "task":     "webhooks.rate_limit.reset_rate_limits",
        "schedule": _sched("rate_reset", 3600),            # 1 hr
        "options":  {"queue": "webhooks_core"},
    },

    # ── Rate limiting: cleanup expired records daily at 03:00 UTC ─────────────
    "webhooks-rate-limit-cleanup": {
        "task":     "webhooks.rate_limit.cleanup_expired_rate_limits",
        "schedule": _sched("rate_cleanup", crontab(hour=3, minute=0)),
        "options":  {"queue": "webhooks_core"},
    },

    # ── Replay: cleanup old replay records weekly ─────────────────────────────
    "webhooks-cleanup-old-replays": {
        "task":     "webhooks.replay.cleanup_old_replays",
        "schedule": _sched("replay_cleanup", crontab(hour=4, minute=0, day_of_week=1)),
        "options":  {"queue": "webhooks_core"},
    },

    # ── Cleanup: purge old delivery logs weekly Monday 04:30 UTC ─────────────
    "webhooks-cleanup-all-old-data": {
        "task":     "webhooks.cleanup.cleanup_all_old_data",
        "schedule": _sched("data_cleanup", crontab(hour=4, minute=30, day_of_week=1)),
        "options":  {"queue": "webhooks_core"},
    },

    # ── Integration sync every 6 hours (only if INTEGRATION_ENABLED) ──────────
    "webhooks-integration-sync": {
        "task":     "webhooks.integration.sync_all_endpoints",
        "schedule": _sched("integration_sync", 21600),     # 6 hr
        "options":  {"queue": "webhooks_integration"},
        # Task skips itself gracefully when INTEGRATION_ENABLED = False
    },
}


# ── Celery Queue Definitions ─────────────────────────────────────────────────
# Add these to CELERY_TASK_ROUTES in your settings:
#
#   "api.webhooks.tasks.*":          {"queue": "webhooks_core"},
#   "api.webhooks.tasks.aging*":     {"queue": "webhooks_aging"},
#   "api.webhooks.tasks.health*":    {"queue": "webhooks_health"},
#   "api.webhooks.tasks.analytics*": {"queue": "webhooks_analytics"},
#   "api.webhooks.tasks.integration*": {"queue": "webhooks_integration"},

WEBHOOK_QUEUES = [
    "webhooks_core",
    "webhooks_aging",
    "webhooks_health",
    "webhooks_analytics",
    "webhooks_integration",
]
