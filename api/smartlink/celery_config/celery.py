"""
SmartLink Celery Configuration
World #1 SmartLink Platform — Async Task Queue
"""
import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('smartlink')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Queue definitions ────────────────────────────────────────────────
app.conf.task_queues = {
    'clicks':      {'exchange': 'clicks',      'routing_key': 'clicks'},
    'conversions': {'exchange': 'conversions', 'routing_key': 'conversions'},
    'analytics':   {'exchange': 'analytics',   'routing_key': 'analytics'},
    'fraud':       {'exchange': 'fraud',       'routing_key': 'fraud'},
    'email':       {'exchange': 'email',       'routing_key': 'email'},
    'maintenance': {'exchange': 'maintenance', 'routing_key': 'maintenance'},
    'default':     {'exchange': 'default',     'routing_key': 'default'},
}
app.conf.task_default_queue = 'default'

# ── Task routing ─────────────────────────────────────────────────────
app.conf.task_routes = {
    'smartlink.process_click_async':           {'queue': 'clicks'},
    'smartlink.record_bot_click':              {'queue': 'clicks'},
    'smartlink.log_redirect_async':            {'queue': 'clicks'},
    'smartlink.attribute_conversion':          {'queue': 'conversions'},
    'smartlink.hourly_stat_rollup':            {'queue': 'analytics'},
    'smartlink.daily_stat_rollup':             {'queue': 'analytics'},
    'smartlink.update_epc_scores':             {'queue': 'analytics'},
    'smartlink.update_offer_scores':           {'queue': 'analytics'},
    'smartlink.build_heatmaps':               {'queue': 'analytics'},
    'smartlink.evaluate_ab_tests':             {'queue': 'analytics'},
    'smartlink.hourly_fraud_scan':             {'queue': 'fraud'},
    'smartlink.scan_high_velocity_ips':        {'queue': 'fraud'},
    'smartlink.send_daily_publisher_reports':  {'queue': 'email'},
    'smartlink.send_weekly_publisher_reports': {'queue': 'email'},
    'smartlink.reset_daily_caps':              {'queue': 'default'},
    'smartlink.reset_monthly_caps':            {'queue': 'default'},
    'smartlink.warmup_resolver_cache':         {'queue': 'default'},
    'smartlink.verify_pending_domains':        {'queue': 'default'},
    'smartlink.check_ssl_expiry':              {'queue': 'default'},
    'smartlink.archive_old_clicks':            {'queue': 'maintenance'},
    'smartlink.cleanup_old_redirect_logs':     {'queue': 'maintenance'},
    'smartlink.check_broken_smartlinks':       {'queue': 'maintenance'},
}

# ── Celery Beat Schedule ─────────────────────────────────────────────
app.conf.beat_schedule = {
    # Every 5 minutes — cache warmup
    'warmup-cache-every-5min': {
        'task': 'smartlink.warmup_resolver_cache',
        'schedule': crontab(minute='*/5'),
    },
    # Every 15 minutes — fraud velocity scan
    'fraud-velocity-scan-every-15min': {
        'task': 'smartlink.scan_high_velocity_ips',
        'schedule': crontab(minute='*/15'),
    },
    # Every 30 minutes — EPC + offer scores
    'update-epc-every-30min': {
        'task': 'smartlink.update_epc_scores',
        'schedule': crontab(minute='*/30'),
    },
    'update-offer-scores-every-30min': {
        'task': 'smartlink.update_offer_scores',
        'schedule': crontab(minute='*/30'),
    },
    'build-heatmaps-every-30min': {
        'task': 'smartlink.build_heatmaps',
        'schedule': crontab(minute='*/30'),
    },
    # Every hour
    'hourly-stat-rollup': {
        'task': 'smartlink.hourly_stat_rollup',
        'schedule': crontab(minute=0),
    },
    'hourly-fraud-scan': {
        'task': 'smartlink.hourly_fraud_scan',
        'schedule': crontab(minute=5),
    },
    'evaluate-ab-tests-hourly': {
        'task': 'smartlink.evaluate_ab_tests',
        'schedule': crontab(minute=10),
    },
    'check-broken-smartlinks-every-6hr': {
        'task': 'smartlink.check_broken_smartlinks',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    'verify-pending-domains-every-6hr': {
        'task': 'smartlink.verify_pending_domains',
        'schedule': crontab(minute=30, hour='*/6'),
    },
    # Daily tasks
    'daily-stat-rollup': {
        'task': 'smartlink.daily_stat_rollup',
        'schedule': crontab(minute=5, hour=0),
    },
    'reset-daily-caps-midnight': {
        'task': 'smartlink.reset_daily_caps',
        'schedule': crontab(minute=0, hour=0),
    },
    'daily-publisher-reports': {
        'task': 'smartlink.send_daily_publisher_reports',
        'schedule': crontab(minute=0, hour=8),
    },
    'check-ssl-expiry-daily': {
        'task': 'smartlink.check_ssl_expiry',
        'schedule': crontab(minute=0, hour=2),
    },
    'cleanup-old-redirect-logs-daily': {
        'task': 'smartlink.cleanup_old_redirect_logs',
        'schedule': crontab(minute=0, hour=3),
    },
    # Weekly
    'archive-old-clicks-weekly': {
        'task': 'smartlink.archive_old_clicks',
        'schedule': crontab(minute=0, hour=4, day_of_week=0),
    },
    'weekly-publisher-reports': {
        'task': 'smartlink.send_weekly_publisher_reports',
        'schedule': crontab(minute=0, hour=8, day_of_week=1),
    },
    'reset-monthly-caps': {
        'task': 'smartlink.reset_monthly_caps',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),
    },
}

app.conf.timezone = 'UTC'
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'
app.conf.accept_content = ['json']
app.conf.task_track_started = True
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 4
app.conf.task_compression = 'gzip'

# Additional schedules
app.conf.beat_schedule.update({
    'process-schedules-every-minute': {
        'task': 'smartlink.process_schedules',
        'schedule': 60,  # every 60 seconds
    },
    'update-currency-rates-hourly': {
        'task': 'smartlink.update_currency_rates',
        'schedule': crontab(minute=15, hour='*'),
    },
    'evaluate-publisher-tiers-weekly': {
        'task': 'smartlink.evaluate_publisher_tiers',
        'schedule': crontab(minute=0, hour=6, day_of_week=1),
    },
})
