# cms/celery_beat_config.py
"""
Celery Beat Schedule — all CMS background jobs.

Auto-imported by settings_production.py via:
    from api.cms.celery_beat_config import CMS_BEAT_SCHEDULE
"""

from celery.schedules import crontab

CMS_BEAT_SCHEDULE = {
    # ── 1. Daily earnings calculation — 1 AM ─────────────────────────────────
    'cms-daily-earnings-calculation': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=1, minute=0),
        'args': ('daily_earnings_calculation',),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 2. Leaderboard update — 2 AM ─────────────────────────────────────────
    'cms-update-leaderboard': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=2, minute=0),
        'args': ('update_leaderboard',),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 3. Pending notifications — every 15 minutes ──────────────────────────
    'cms-send-pending-notifications': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(minute='*/15'),
        'args': ('send_pending_notifications',),
        'options': {'queue': 'cms_notifications'},
    },

    # ── 4. Weekly reports — Sunday 3 AM ──────────────────────────────────────
    'cms-generate-weekly-reports': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),
        'args': ('generate_reports',),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 5. Data cleanup — 4 AM daily ─────────────────────────────────────────
    'cms-cleanup-old-data': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=4, minute=0),
        'args': ('cleanup_old_data',),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 6. Cache warming — midnight ───────────────────────────────────────────
    'cms-warm-caches': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=0, minute=0),
        'args': ('warm_caches',),
        'options': {'queue': 'cms_cache'},
    },

    # ── 7. Analytics aggregation — 5 AM ──────────────────────────────────────
    'cms-aggregate-analytics': {
        'task': 'cms.batch.processor.execute_batch_job_task',
        'schedule': crontab(hour=5, minute=0),
        'args': ('aggregate_analytics',),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 8. RTB bid log cleanup — weekly Sunday 6 AM ───────────────────────────
    'cms-cleanup-rtb-bid-logs': {
        'task': 'cms.tasks.rtb_tasks.cleanup_old_bid_logs',
        'schedule': crontab(hour=6, minute=0, day_of_week=0),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 9. Referral stats refresh — daily 3:30 AM ─────────────────────────────
    'cms-refresh-referral-stats': {
        'task': 'cms.tasks.referral_tasks.refresh_referral_stats',
        'schedule': crontab(hour=3, minute=30),
        'options': {'queue': 'cms_scheduled'},
    },

    # ── 10. Smart link click aggregation — every hour ─────────────────────────
    'cms-aggregate-smartlink-clicks': {
        'task': 'cms.tasks.smartlink_tasks.aggregate_click_stats',
        'schedule': crontab(minute=0),
        'options': {'queue': 'cms_scheduled'},
    },
}

# ── background_jobs.py — BackgroundJobRunner wired to beat ───────────────────
CMS_BEAT_SCHEDULE.update({
    'cms-expire-quiz-attempts': {
        'task': 'cms.background_jobs.expire_incomplete_quiz_attempts_job',
        'schedule': crontab(minute=0, hour='*/2'),
        'options': {'queue': 'cms_scheduled'},
    },
    'cms-sync-leaderboard-cache': {
        'task': 'cms.background_jobs.sync_leaderboard_cache_job',
        'schedule': crontab(minute=30, hour='*/1'),
        'options': {'queue': 'cms_cache'},
    },
    'cms-cleanup-orphaned-media': {
        'task': 'cms.background_jobs.cleanup_orphaned_media_job',
        'schedule': crontab(hour=6, minute=30, day_of_week=1),
        'options': {'queue': 'cms_scheduled'},
    },
})
