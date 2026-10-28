# api/admin_panel/beat_schedule.py
"""
Celery Beat periodic task schedule for admin_panel.
Add this to your project's settings.py:

    from api.admin_panel.beat_schedule import ADMIN_PANEL_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(ADMIN_PANEL_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

ADMIN_PANEL_BEAT_SCHEDULE = {

    # ==================== Dashboard KPI Refresh (every 5 min) ====================
    'admin-panel-refresh-dashboard-kpis': {
        'task': 'admin_panel.tasks.dashboard_refresh_tasks.refresh_dashboard_kpis_task',
        'schedule': 300,  # every 5 minutes
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Report Schedules (every 30 min) ====================
    'admin-panel-run-scheduled-reports': {
        'task': 'admin_panel.tasks.report_generation_tasks.run_scheduled_reports',
        'schedule': 1800,  # every 30 minutes
        'options': {'queue': 'admin_panel'},
    },

    # ==================== AI Insights (daily 2 AM) ====================
    'admin-panel-generate-daily-insights': {
        'task': 'admin_panel.tasks.insight_tasks.generate_daily_insights_task',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Admin Digest Email (daily 8 AM) ====================
    'admin-panel-send-daily-digest': {
        'task': 'admin_panel.tasks.admin_digest_tasks.send_admin_digest_task',
        'schedule': crontab(hour=8, minute=0),
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Activity Log Cleanup (daily 3 AM) ====================
    'admin-panel-cleanup-old-activity': {
        'task': 'admin_panel.tasks.activity_cleanup_tasks.cleanup_old_activity_task',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Session Cleanup (every 6 hours) ====================
    'admin-panel-cleanup-stale-sessions': {
        'task': 'admin_panel.tasks.session_cleanup_tasks.cleanup_stale_sessions_task',
        'schedule': crontab(hour='*/6', minute=0),
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Config Cache Refresh (every 10 min) ====================
    'admin-panel-refresh-config-cache': {
        'task': 'admin_panel.tasks.config_cache_tasks.refresh_config_cache_task',
        'schedule': 600,  # every 10 minutes
        'options': {'queue': 'admin_panel'},
    },

    # ==================== System Health Check (every 1 min) ====================
    'admin-panel-check-system-health': {
        'task': 'admin_panel.tasks.system_health_tasks.run_health_check_task',
        'schedule': 60,  # every 1 minute
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Feature Flag Refresh (every 5 min) ====================
    'admin-panel-refresh-feature-flags': {
        'task': 'admin_panel.tasks.feature_flag_tasks.refresh_all_flags_task',
        'schedule': 300,
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Maintenance Window Auto-Activate (every 2 min) ====================
    'admin-panel-auto-activate-maintenance': {
        'task': 'admin_panel.tasks.maintenance_tasks.auto_activate_maintenance_windows',
        'schedule': 120,  # every 2 minutes
        'options': {'queue': 'admin_panel'},
    },

    # ==================== Expired Export Cleanup (daily 4 AM) ====================
    'admin-panel-cleanup-expired-exports': {
        'task': 'admin_panel.tasks.data_export_tasks.cleanup_expired_exports',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'admin_panel'},
    },
}