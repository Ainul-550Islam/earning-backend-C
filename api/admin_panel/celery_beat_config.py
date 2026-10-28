# api/admin_panel/celery_beat_config.py
"""
Celery Beat full configuration for admin_panel.
Replaces beat_schedule.py with extended config including routes, queues, retries.

Usage in settings.py:
    from api.admin_panel.celery_beat_config import ADMIN_BEAT_SCHEDULE, ADMIN_TASK_ROUTES
    CELERY_BEAT_SCHEDULE.update(ADMIN_BEAT_SCHEDULE)
    CELERY_TASK_ROUTES.update(ADMIN_TASK_ROUTES)
"""
from celery.schedules import crontab

# ==================== QUEUES ====================
ADMIN_PANEL_QUEUES = [
    'admin_panel',          # Default admin tasks
    'admin_panel.high',     # High-priority: health, fraud alerts
    'admin_panel.bulk',     # Bulk operations: exports, mass emails
    'admin_panel.reports',  # Report generation
    'admin_panel.ai',       # AI/ML tasks
]

# ==================== BEAT SCHEDULE ====================
ADMIN_BEAT_SCHEDULE = {

    # ── REAL-TIME (every minute) ──────────────────────────────
    'admin-system-health-check': {
        'task': 'api.admin_panel.tasks.system_health_tasks.run_health_check_task',
        'schedule': 60,
        'options': {'queue': 'admin_panel.high', 'expires': 55},
    },
    'admin-fraud-stats-refresh': {
        'task': 'api.admin_panel.tasks.system_health_tasks.refresh_fraud_stats_cache',
        'schedule': 60,
        'options': {'queue': 'admin_panel.high', 'expires': 55},
    },

    # ── FREQUENT (every 5 minutes) ───────────────────────────
    'admin-dashboard-kpis-refresh': {
        'task': 'api.admin_panel.tasks.dashboard_refresh_tasks.refresh_dashboard_kpis_task',
        'schedule': 300,
        'options': {'queue': 'admin_panel', 'expires': 290},
    },
    'admin-feature-flags-refresh': {
        'task': 'api.admin_panel.tasks.feature_flag_tasks.refresh_all_flags_task',
        'schedule': 300,
        'options': {'queue': 'admin_panel', 'expires': 290},
    },
    'admin-maintenance-auto-activate': {
        'task': 'api.admin_panel.tasks.maintenance_tasks.auto_activate_maintenance_windows',
        'schedule': 120,
        'options': {'queue': 'admin_panel', 'expires': 115},
    },

    # ── SEMI-FREQUENT (every 10-30 minutes) ──────────────────
    'admin-config-cache-refresh': {
        'task': 'api.admin_panel.tasks.config_cache_tasks.refresh_config_cache_task',
        'schedule': 600,
        'options': {'queue': 'admin_panel'},
    },
    'admin-scheduled-reports': {
        'task': 'api.admin_panel.tasks.report_generation_tasks.run_scheduled_reports',
        'schedule': 1800,
        'options': {'queue': 'admin_panel.reports'},
    },
    'admin-integration-health': {
        'task': 'api.admin_panel.tasks.system_health_tasks.check_integration_health',
        'schedule': 600,
        'options': {'queue': 'admin_panel'},
    },
    'admin-perf-stats-push': {
        'task': 'api.admin_panel.tasks.system_health_tasks.push_perf_stats_to_cache',
        'schedule': 300,
        'options': {'queue': 'admin_panel'},
    },

    # ── HOURLY ───────────────────────────────────────────────
    'admin-rtb-floor-sync': {
        'task': 'api.admin_panel.tasks.config_cache_tasks.sync_rtb_floors',
        'schedule': crontab(minute=0),
        'options': {'queue': 'admin_panel'},
    },
    'admin-wallet-integrity-spot-check': {
        'task': 'api.admin_panel.tasks.system_health_tasks.wallet_integrity_spot_check',
        'schedule': crontab(minute=30),
        'options': {'queue': 'admin_panel'},
    },

    # ── EVERY 6 HOURS ────────────────────────────────────────
    'admin-session-cleanup': {
        'task': 'api.admin_panel.tasks.session_cleanup_tasks.cleanup_stale_sessions_task',
        'schedule': crontab(hour='*/6', minute=0),
        'options': {'queue': 'admin_panel'},
    },
    'admin-sync-manager-run': {
        'task': 'api.admin_panel.tasks.system_health_tasks.run_sync_manager',
        'schedule': crontab(hour='*/6', minute=15),
        'options': {'queue': 'admin_panel'},
    },

    # ── DAILY ────────────────────────────────────────────────
    'admin-ai-daily-insights': {
        'task': 'api.admin_panel.tasks.insight_tasks.generate_daily_insights_task',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'admin_panel.ai'},
    },
    'admin-activity-cleanup': {
        'task': 'api.admin_panel.tasks.activity_cleanup_tasks.cleanup_old_activity_task',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'admin_panel'},
    },
    'admin-digest-email': {
        'task': 'api.admin_panel.tasks.admin_digest_tasks.send_admin_digest_task',
        'schedule': crontab(hour=8, minute=0),
        'options': {'queue': 'admin_panel.bulk'},
    },
    'admin-export-cleanup': {
        'task': 'api.admin_panel.tasks.data_export_tasks.cleanup_expired_exports',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'admin_panel'},
    },
    'admin-leaderboard-refresh': {
        'task': 'api.admin_panel.tasks.dashboard_refresh_tasks.refresh_leaderboard_snapshot',
        'schedule': crontab(hour=0, minute=30),
        'options': {'queue': 'admin_panel'},
    },
    'admin-daily-cap-reset': {
        'task': 'api.admin_panel.tasks.config_cache_tasks.reset_daily_offer_caps',
        'schedule': crontab(hour=0, minute=1),
        'options': {'queue': 'admin_panel.high'},
    },

    # ── WEEKLY ───────────────────────────────────────────────
    'admin-weekly-report': {
        'task': 'api.admin_panel.tasks.report_generation_tasks.generate_weekly_summary',
        'schedule': crontab(day_of_week='monday', hour=7, minute=0),
        'options': {'queue': 'admin_panel.reports'},
    },
    'admin-churn-prediction': {
        'task': 'api.admin_panel.tasks.insight_tasks.run_churn_prediction',
        'schedule': crontab(day_of_week='sunday', hour=3, minute=0),
        'options': {'queue': 'admin_panel.ai'},
    },
}

# ==================== TASK ROUTES ──────────────────────────
ADMIN_TASK_ROUTES = {
    'api.admin_panel.tasks.system_health_tasks.*':   {'queue': 'admin_panel.high'},
    'api.admin_panel.tasks.insight_tasks.*':         {'queue': 'admin_panel.ai'},
    'api.admin_panel.tasks.report_generation_tasks.*': {'queue': 'admin_panel.reports'},
    'api.admin_panel.tasks.data_export_tasks.*':     {'queue': 'admin_panel.bulk'},
    'api.admin_panel.tasks.admin_digest_tasks.*':    {'queue': 'admin_panel.bulk'},
    'api.admin_panel.tasks.*':                       {'queue': 'admin_panel'},
}

# ==================== RETRY CONFIG ─────────────────────────
ADMIN_TASK_DEFAULT_RETRY = {
    'max_retries': 3,
    'default_retry_delay': 60,
    'autoretry_for': (Exception,),
    'retry_backoff': True,
    'retry_backoff_max': 300,
    'retry_jitter': True,
}