"""
SmartLink Celery Configuration
World #1 SmartLink Platform — Async Task Queue

Queues:
  clicks        — redirect-critical click processing
  conversions   — S2S postback / conversion attribution
  analytics     — EPC, stat rollup, heatmaps, AB tests
  fraud         — fraud scanning (separate so it never blocks analytics)
  email         — report emails, payout notifications
  webhooks      — outbound webhook delivery + retry
  notifications — in-app / push notifications
  maintenance   — cleanup, archival, health checks
  default       — everything else (cache warmup, domains, scheduling)
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('smartlink')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Queue definitions ─────────────────────────────────────────────────────────
app.conf.task_queues = {
    'clicks':        {'exchange': 'clicks',        'routing_key': 'clicks'},
    'conversions':   {'exchange': 'conversions',   'routing_key': 'conversions'},
    'analytics':     {'exchange': 'analytics',     'routing_key': 'analytics'},
    'fraud':         {'exchange': 'fraud',          'routing_key': 'fraud'},
    'email':         {'exchange': 'email',          'routing_key': 'email'},
    'maintenance':   {'exchange': 'maintenance',    'routing_key': 'maintenance'},
    'webhooks':      {'exchange': 'webhooks',       'routing_key': 'webhooks'},
    'notifications': {'exchange': 'notifications',  'routing_key': 'notifications'},
    'default':       {'exchange': 'default',        'routing_key': 'default'},
}
app.conf.task_default_queue = 'default'

# ── Task routing ──────────────────────────────────────────────────────────────
# Every task that exists in tasks/ must appear here.
# Event-driven tasks (process_click_async, deliver_webhook_event, etc.) are
# triggered by .delay()/.apply_async() — they are in task_routes but NOT in
# beat_schedule (beat is only for periodic/cron tasks).
app.conf.task_routes = {
    # Click pipeline (event-driven, NOT beat)
    'smartlink.process_click_async':             {'queue': 'clicks'},
    'smartlink.record_bot_click':                {'queue': 'clicks'},
    'smartlink.log_redirect_async':              {'queue': 'clicks'},
    'smartlink.update_cap_tracker_db':           {'queue': 'clicks'},

    # Conversion / attribution (event-driven, NOT beat)
    'smartlink.attribute_conversion':            {'queue': 'conversions'},

    # Analytics (beat)
    'smartlink.hourly_stat_rollup':              {'queue': 'analytics'},
    'smartlink.daily_stat_rollup':               {'queue': 'analytics'},
    'smartlink.update_epc_scores':               {'queue': 'analytics'},
    'smartlink.update_epc_for_smartlink':        {'queue': 'analytics'},
    'smartlink.update_offer_scores':             {'queue': 'analytics'},
    'smartlink.update_offer_performance_stats':  {'queue': 'analytics'},
    'smartlink.build_heatmaps':                  {'queue': 'analytics'},
    'smartlink.build_heatmap_for_smartlink':     {'queue': 'analytics'},
    'smartlink.evaluate_ab_tests':               {'queue': 'analytics'},

    # Fraud (beat)
    'smartlink.hourly_fraud_scan':               {'queue': 'fraud'},
    'smartlink.scan_high_velocity_ips':          {'queue': 'fraud'},

    # Email reports (beat)
    'smartlink.send_daily_publisher_reports':    {'queue': 'email'},
    'smartlink.send_weekly_publisher_reports':   {'queue': 'email'},
    'smartlink.alert_cap_nearly_reached':        {'queue': 'email'},

    # Notifications (beat + event-driven)
    'smartlink.send_daily_report_emails':        {'queue': 'notifications'},
    'smartlink.send_payout_ready_notifications': {'queue': 'notifications'},

    # Webhooks (event-driven + beat retry)
    'smartlink.deliver_webhook_event':           {'queue': 'webhooks'},
    'smartlink.retry_webhook_deliveries':        {'queue': 'webhooks'},
    'smartlink.purge_old_webhook_logs':          {'queue': 'maintenance'},

    # Billing (event-driven — triggered by admin action, NOT beat)
    'smartlink.process_payout_payment':          {'queue': 'default'},
    'smartlink.process_batch_payments_async':    {'queue': 'default'},
    'smartlink.release_pending_balances':        {'queue': 'default'},
    'smartlink.check_smartlink_expiry':          {'queue': 'default'},

    # Cache (beat)
    'smartlink.warmup_resolver_cache':           {'queue': 'default'},
    'smartlink.invalidate_smartlink_cache':      {'queue': 'default'},
    'smartlink.warmup_offer_pool_cache':         {'queue': 'default'},

    # Cap reset (beat)
    'smartlink.reset_daily_caps':                {'queue': 'default'},
    'smartlink.reset_monthly_caps':              {'queue': 'default'},

    # Domains (beat)
    'smartlink.verify_pending_domains':          {'queue': 'default'},
    'smartlink.check_ssl_expiry':                {'queue': 'default'},

    # Scheduler / tiers (beat)
    'smartlink.process_schedules':               {'queue': 'default'},
    'smartlink.evaluate_publisher_tiers':        {'queue': 'analytics'},
    'smartlink.update_currency_rates':           {'queue': 'default'},

    # Maintenance (beat)
    'smartlink.check_broken_smartlinks':         {'queue': 'maintenance'},
    'smartlink.check_smartlink_redirect_health': {'queue': 'maintenance'},
    'smartlink.check_offer_pool_health':         {'queue': 'default'},
    'smartlink.archive_old_clicks':              {'queue': 'maintenance'},
    'smartlink.cleanup_old_redirect_logs':       {'queue': 'maintenance'},
    'smartlink.cleanup_old_rotation_logs':       {'queue': 'maintenance'},
    'smartlink.cleanup_bot_clicks':              {'queue': 'maintenance'},
    'smartlink.cleanup_expired_unique_clicks':   {'queue': 'maintenance'},
}

# ── Celery Beat Schedule ──────────────────────────────────────────────────────
# Only PERIODIC tasks go here. Event-driven tasks must NOT be in beat_schedule.
#
# Cron reference (crontab):
#   crontab(minute='*/5')              → every 5 min
#   crontab(minute=0)                  → top of every hour
#   crontab(minute=0, hour=8)          → 08:00 UTC daily
#   crontab(minute=0, hour='*/6')      → every 6 hours
#   crontab(minute=0, hour=0, day_of_month=1) → first of month
#   crontab(minute=0, hour=8, day_of_week=1)  → Monday 08:00 UTC
#
# Integer schedule = seconds (e.g. 120 = every 2 minutes).

app.conf.beat_schedule = {

    # ── Every 1 minute ────────────────────────────────────────────────────────
    'process-schedules-every-minute': {
        'task':     'smartlink.process_schedules',
        'schedule': 60,
    },

    # ── Every 2 minutes ───────────────────────────────────────────────────────
    'retry-webhook-deliveries-every-2min': {
        'task':     'smartlink.retry_webhook_deliveries',
        'schedule': 120,
    },

    # ── Every 5 minutes ───────────────────────────────────────────────────────
    'warmup-resolver-cache-5min': {
        'task':     'smartlink.warmup_resolver_cache',
        'schedule': crontab(minute='*/5'),
    },
    'warmup-offer-pool-cache-5min': {
        'task':     'smartlink.warmup_offer_pool_cache',
        'schedule': crontab(minute='*/5'),
    },

    # ── Every 10 minutes ──────────────────────────────────────────────────────
    'check-smartlink-redirect-health-10min': {
        'task':     'smartlink.check_smartlink_redirect_health',
        'schedule': crontab(minute='*/10'),
    },

    # ── Every 15 minutes ──────────────────────────────────────────────────────
    'fraud-velocity-scan-15min': {
        'task':     'smartlink.scan_high_velocity_ips',
        'schedule': crontab(minute='*/15'),
    },
    'check-smartlink-expiry-15min': {
        'task':     'smartlink.check_smartlink_expiry',
        'schedule': crontab(minute='*/15'),
    },

    # ── Every 30 minutes ──────────────────────────────────────────────────────
    'update-epc-scores-30min': {
        'task':     'smartlink.update_epc_scores',
        'schedule': crontab(minute='*/30'),
    },
    'update-offer-scores-30min': {
        'task':     'smartlink.update_offer_scores',
        'schedule': crontab(minute='*/30'),
    },
    'build-heatmaps-30min': {
        'task':     'smartlink.build_heatmaps',
        'schedule': crontab(minute='*/30'),
    },
    'update-offer-performance-stats-30min': {
        'task':     'smartlink.update_offer_performance_stats',
        'schedule': crontab(minute='*/30'),
    },
    'alert-cap-nearly-reached-30min': {
        'task':     'smartlink.alert_cap_nearly_reached',
        'schedule': crontab(minute='*/30'),
    },

    # ── Every hour ────────────────────────────────────────────────────────────
    'hourly-stat-rollup': {
        'task':     'smartlink.hourly_stat_rollup',
        'schedule': crontab(minute=0),
    },
    'hourly-fraud-scan': {
        'task':     'smartlink.hourly_fraud_scan',
        'schedule': crontab(minute=5),
    },
    'evaluate-ab-tests-hourly': {
        'task':     'smartlink.evaluate_ab_tests',
        'schedule': crontab(minute=10),
    },
    'update-currency-rates-hourly': {
        'task':     'smartlink.update_currency_rates',
        'schedule': crontab(minute=15),
    },
    'send-payout-ready-notifications-hourly': {
        'task':     'smartlink.send_payout_ready_notifications',
        'schedule': crontab(minute=45),
    },

    # ── Every 6 hours ─────────────────────────────────────────────────────────
    'check-broken-smartlinks-6hr': {
        'task':     'smartlink.check_broken_smartlinks',
        'schedule': crontab(minute=0, hour='*/6'),
    },
    'verify-pending-domains-6hr': {
        'task':     'smartlink.verify_pending_domains',
        'schedule': crontab(minute=30, hour='*/6'),
    },
    'check-offer-pool-health-6hr': {
        'task':     'smartlink.check_offer_pool_health',
        'schedule': crontab(minute=45, hour='*/6'),
    },

    # ── Daily tasks ───────────────────────────────────────────────────────────
    # Midnight UTC
    'reset-daily-caps-midnight': {
        'task':     'smartlink.reset_daily_caps',
        'schedule': crontab(minute=0, hour=0),
    },
    'daily-stat-rollup-midnight': {
        'task':     'smartlink.daily_stat_rollup',
        'schedule': crontab(minute=5, hour=0),
    },

    # 02:00 UTC — low-traffic window
    'check-ssl-expiry-daily': {
        'task':     'smartlink.check_ssl_expiry',
        'schedule': crontab(minute=0, hour=2),
    },
    'release-pending-balances-daily': {
        'task':     'smartlink.release_pending_balances',
        'schedule': crontab(minute=30, hour=2),
    },

    # 03:00 UTC — cleanup window
    'cleanup-old-redirect-logs-daily': {
        'task':     'smartlink.cleanup_old_redirect_logs',
        'schedule': crontab(minute=0, hour=3),
    },
    'cleanup-expired-unique-clicks-daily': {
        'task':     'smartlink.cleanup_expired_unique_clicks',
        'schedule': crontab(minute=20, hour=3),
    },
    'cleanup-old-rotation-logs-daily': {
        'task':     'smartlink.cleanup_old_rotation_logs',
        'schedule': crontab(minute=40, hour=3),
    },
    'purge-webhook-logs-daily': {
        'task':     'smartlink.purge_old_webhook_logs',
        'schedule': crontab(minute=0, hour=4),
    },

    # 04:00 UTC — additional cleanup
    'cleanup-bot-clicks-daily': {
        'task':     'smartlink.cleanup_bot_clicks',
        'schedule': crontab(minute=30, hour=4),
    },

    # 08:00 UTC — report delivery
    'daily-publisher-reports': {
        'task':     'smartlink.send_daily_publisher_reports',
        'schedule': crontab(minute=0, hour=8),
    },
    'send-daily-report-emails': {
        'task':     'smartlink.send_daily_report_emails',
        'schedule': crontab(minute=15, hour=8),
    },

    # ── Weekly tasks ──────────────────────────────────────────────────────────
    # Sunday 04:00 UTC — archival
    'archive-old-clicks-weekly': {
        'task':     'smartlink.archive_old_clicks',
        'schedule': crontab(minute=0, hour=4, day_of_week=0),
    },

    # Monday 06:00 UTC — tier re-evaluation
    'evaluate-publisher-tiers-weekly': {
        'task':     'smartlink.evaluate_publisher_tiers',
        'schedule': crontab(minute=0, hour=6, day_of_week=1),
    },

    # Monday 08:00 UTC — weekly reports
    'weekly-publisher-reports': {
        'task':     'smartlink.send_weekly_publisher_reports',
        'schedule': crontab(minute=0, hour=8, day_of_week=1),
    },

    # ── Monthly tasks ─────────────────────────────────────────────────────────
    # 1st of month 00:00 UTC
    'reset-monthly-caps': {
        'task':     'smartlink.reset_monthly_caps',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),
    },
}

# ── Celery worker settings ────────────────────────────────────────────────────
app.conf.timezone                   = 'UTC'
app.conf.task_serializer            = 'json'
app.conf.result_serializer          = 'json'
app.conf.accept_content             = ['json']
app.conf.task_track_started         = True
app.conf.task_acks_late             = True
app.conf.worker_prefetch_multiplier = 4
app.conf.task_compression           = 'gzip'
app.conf.task_soft_time_limit       = 300   # 5 min soft limit
app.conf.task_time_limit            = 600   # 10 min hard limit
app.conf.worker_max_tasks_per_child = 1000  # prevent memory leaks
