# api/cms/celery_schedule.py
"""
Celery Beat Schedule for CMS tasks.
Add this to your main celery.py or settings.py CELERY_BEAT_SCHEDULE.

Usage in settings.py:
    from api.cms.celery_schedule import CMS_CELERY_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(CMS_CELERY_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

CMS_CELERY_BEAT_SCHEDULE = {

    # ── Publish scheduled content every 5 minutes ─────────────────
    'cms-publish-scheduled-content': {
        'task': 'cms.tasks.publish_scheduled_content',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 240},
    },

    # ── Expire old content every hour ─────────────────────────────
    'cms-expire-old-content': {
        'task': 'cms.tasks.expire_old_content',
        'schedule': crontab(minute=0),
        'options': {'expires': 3500},
    },

    # ── Deactivate expired banners every 30 minutes ───────────────
    'cms-deactivate-expired-banners': {
        'task': 'cms.tasks.deactivate_expired_banners',
        'schedule': crontab(minute='*/30'),
        'options': {'expires': 1700},
    },

    # ── Regenerate sitemap weekly (Sunday 2am) ────────────────────
    'cms-regenerate-sitemap': {
        'task': 'cms.tasks.regenerate_sitemap',
        'schedule': crontab(hour=2, minute=0, day_of_week='sunday'),
    },

    # ── Generate missing media variants daily (3am) ───────────────
    'cms-regenerate-missing-variants': {
        'task': 'cms.tasks.regenerate_missing_variants',
        'schedule': crontab(hour=3, minute=0),
    },

    # ── Push unpushed media to CDN daily (4am) ────────────────────
    'cms-push-to-cdn': {
        'task': 'cms.tasks.push_all_unpushed_to_cdn',
        'schedule': crontab(hour=4, minute=0),
    },

    # ── Aggregate popup stats daily (midnight) ─────────────────────
    'cms-popup-stats': {
        'task': 'cms.tasks.aggregate_popup_stats',
        'schedule': crontab(hour=0, minute=10),
    },

    # ── Collect blog analytics daily (1am) ────────────────────────
    'cms-blog-analytics': {
        'task': 'cms.tasks.collect_blog_analytics',
        'schedule': crontab(hour=1, minute=0),
    },

    # ── SEO audit weekly (Monday 5am) ─────────────────────────────
    'cms-seo-audit': {
        'task': 'cms.tasks.run_seo_audit',
        'schedule': crontab(hour=5, minute=0, day_of_week='monday'),
    },

    # ── Auto-fill missing SEO weekly ──────────────────────────────
    'cms-auto-fill-seo': {
        'task': 'cms.tasks.auto_fill_missing_seo',
        'schedule': crontab(hour=5, minute=30, day_of_week='monday'),
    },

    # ── Cache invalidation — warm blog cache every 2 hours ────────
    'cms-warm-blog-cache': {
        'task': 'cms.tasks.warm_blog_cache',
        'schedule': crontab(minute=0, hour='*/2'),
    },

    # ── Cleanup unused redirects monthly (1st of month) ───────────
    'cms-cleanup-redirects': {
        'task': 'cms.tasks.cleanup_unused_redirects',
        'schedule': crontab(hour=6, minute=0, day_of_month=1),
    },

    # ── Cleanup expired redirects daily ───────────────────────────
    'cms-cleanup-expired-redirects': {
        'task': 'cms.tasks.cleanup_expired_redirects',
        'schedule': crontab(hour=6, minute=30),
    },

    # ── Cleanup orphaned media weekly ─────────────────────────────
    'cms-cleanup-orphaned-media': {
        'task': 'cms.tasks.delete_orphaned_media',
        'schedule': crontab(hour=7, minute=0, day_of_week='saturday'),
    },

    # ── Update folder stats daily ────────────────────────────────
    'cms-update-folder-stats': {
        'task': 'cms.tasks.update_folder_stats',
        'schedule': crontab(hour=7, minute=30),
    },

    # ── CPAlead daily earning cap reset (midnight) ────────────────
    'cms-daily-earning-cap-reset': {
        'task': 'cms.tasks.daily_earning_cap_reset',
        'schedule': crontab(hour=0, minute=0),
    },

    # ── CPAlead sync daily (6am) ──────────────────────────────────
    'cms-cpalead-sync': {
        'task': 'cms.tasks.cpalead_sync',
        'schedule': crontab(hour=6, minute=0),
    },

    # ── Cleanup old notifications monthly ────────────────────────
    'cms-cleanup-notifications': {
        'task': 'cms.tasks.cleanup_old_notifications',
        'schedule': crontab(hour=8, minute=0, day_of_month=1),
    },

    # ── Cleanup expired popup dismissals weekly ───────────────────
    'cms-cleanup-popup-dismissals': {
        'task': 'cms.tasks.cleanup_expired_popup_dismissals',
        'schedule': crontab(hour=8, minute=30, day_of_week='sunday'),
    },

    # ── Popup stats cleanup monthly ───────────────────────────────
    'cms-cleanup-old-popup-stats': {
        'task': 'cms.tasks.cleanup_old_popup_stats',
        'schedule': crontab(hour=9, minute=0, day_of_month=1),
    },

    # ── Process daily earning rewards (every hour) ────────────────
    'cms-process-earning-rewards': {
        'task': 'cms.tasks.process_daily_earning_rewards',
        'schedule': crontab(minute=0),
    },
}

# ── INTEGRATION_SYSTEM tasks ──────────────────────────────────────
INTEGRATION_BEAT_SCHEDULE = {
    # Health check every 5 minutes
    'cms-health-check': {
        'task': 'cms.tasks.run_health_check',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 240},
    },
    # Audit log cleanup monthly
    'cms-audit-log-cleanup': {
        'task': 'cms.tasks.cleanup_audit_logs',
        'schedule': crontab(hour=10, minute=0, day_of_month=1),
    },
    # Performance stats reset daily
    'cms-perf-stats-reset': {
        'task': 'cms.tasks.reset_performance_stats',
        'schedule': crontab(hour=0, minute=5),
    },
    # Integration registry health ping
    'cms-integration-ping': {
        'task': 'cms.tasks.ping_integration_services',
        'schedule': crontab(minute='*/10'),
        'options': {'expires': 480},
    },
    # Sync manager lock cleanup
    'cms-sync-lock-cleanup': {
        'task': 'cms.tasks.cleanup_stale_locks',
        'schedule': crontab(minute='*/15'),
    },
}

# Merge into main schedule
CMS_CELERY_BEAT_SCHEDULE.update(INTEGRATION_BEAT_SCHEDULE)

# ── New feature tasks ──────────────────────────────────────────
NEW_FEATURE_BEAT_SCHEDULE = {
    'cms-refresh-leaderboard-hourly': {
        'task': 'cms.tasks.refresh_leaderboard',
        'schedule': crontab(minute=0),  # Every hour
    },
    'cms-reset-broken-streaks': {
        'task': 'cms.tasks.reset_broken_streaks',
        'schedule': crontab(hour=0, minute=10),  # Daily at midnight
    },
    'cms-sync-offer-cache': {
        'task': 'cms.tasks.sync_offer_cache',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
    },
}
CMS_CELERY_BEAT_SCHEDULE.update(NEW_FEATURE_BEAT_SCHEDULE)
