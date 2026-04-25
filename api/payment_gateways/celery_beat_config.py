# api/payment_gateways/celery_beat_config.py
# Complete Celery Beat periodic task configuration
# Add to your celery.py: app.conf.beat_schedule.update(BEAT_SCHEDULE)

from datetime import timedelta
from celery.schedules import crontab

BEAT_SCHEDULE = {
    # ── Gateway Health (every 5 min) ──────────────────────────────────────────
    'pg-gateway-health':          {'task': 'api.payment_gateways.tasks.gateway_health_tasks.check_all_gateways',                   'schedule': crontab(minute='*/5')},
    'pg-alert-gateway-down':      {'task': 'api.payment_gateways.tasks.alert_tasks.check_failure_rate_alerts',                      'schedule': crontab(minute='*/15')},

    # ── Deposits (every 10 min) ───────────────────────────────────────────────
    'pg-verify-deposits':         {'task': 'api.payment_gateways.tasks.deposit_verification_tasks.verify_pending_deposits',         'schedule': crontab(minute='*/10')},
    'pg-expire-deposits':         {'task': 'api.payment_gateways.tasks.deposit_verification_tasks.expire_old_deposits',             'schedule': crontab(minute=0, hour='*/2')},

    # ── USDT Fast Pay (every 30 min) ──────────────────────────────────────────
    'pg-usdt-fastpay':            {'task': 'api.payment_gateways.tasks.usdt_fastpay_tasks.process_usdt_fastpay_requests',          'schedule': crontab(minute='*/30')},

    # ── Payouts (5 PM daily — CPAlead style) ──────────────────────────────────
    'pg-daily-fastpay':           {'task': 'api.payment_gateways.tasks.usdt_fastpay_tasks.process_daily_fastpay',                  'schedule': crontab(hour=17, minute=0)},
    'pg-process-payouts':         {'task': 'api.payment_gateways.tasks.withdrawal_processing_tasks.process_approved_payouts',      'schedule': crontab(hour=17, minute=30)},

    # ── Reconciliation (3 AM nightly) ─────────────────────────────────────────
    'pg-nightly-reconcile':       {'task': 'api.payment_gateways.tasks.reconciliation_tasks.nightly_reconciliation',               'schedule': crontab(hour=3, minute=0)},

    # ── Exchange Rates (hourly) ───────────────────────────────────────────────
    'pg-sync-rates':              {'task': 'api.payment_gateways.tasks.analytics_tasks.update_success_rates',                      'schedule': crontab(minute=15)},

    # ── Analytics (hourly) ────────────────────────────────────────────────────
    'pg-daily-analytics':         {'task': 'api.payment_gateways.tasks.analytics_tasks.aggregate_daily_analytics',                 'schedule': crontab(minute=45)},

    # ── Webhooks (every 5 min) ────────────────────────────────────────────────
    'pg-retry-webhooks':          {'task': 'api.payment_gateways.tasks.webhook_retry_tasks.retry_all_failed_webhooks',             'schedule': crontab(minute='*/5')},

    # ── Referral (9 AM daily) ─────────────────────────────────────────────────
    'pg-referral-commissions':    {'task': 'api.payment_gateways.tasks.analytics_tasks.update_success_rates',                      'schedule': crontab(hour=9, minute=30)},

    # ── Alerts & Credentials ─────────────────────────────────────────────────
    'pg-credential-expiry':       {'task': 'api.payment_gateways.tasks.alert_tasks.credential_expiry_reminder',                    'schedule': crontab(hour=9, minute=0)},

    # ── Cleanup (Sunday 2 AM) ─────────────────────────────────────────────────
    'pg-cleanup-logs':            {'task': 'api.payment_gateways.tasks.cleanup_tasks.cleanup_old_webhook_logs',                    'schedule': crontab(hour=2, minute=0, day_of_week=0)},
    'pg-cleanup-health-logs':     {'task': 'api.payment_gateways.tasks.cleanup_tasks.cleanup_health_logs',                         'schedule': crontab(hour=2, minute=30, day_of_week=0)},
    'pg-cleanup-deposits':        {'task': 'api.payment_gateways.tasks.cleanup_tasks.cleanup_expired_deposits',                    'schedule': crontab(hour=3, minute=0, day_of_week=0)},

    # ── Quality & Blacklist (Monday 3 AM) ─────────────────────────────────────
    'pg-auto-blacklist':          {'task': 'api.payment_gateways.tasks.analytics_tasks.auto_blacklist_low_quality_publishers',     'schedule': crontab(hour=3, minute=0, day_of_week=1)},
    'pg-quality-scores':          {'task': 'api.payment_gateways.tasks.analytics_tasks.update_offer_quality_scores',              'schedule': crontab(hour=4, minute=0)},

    # ── Monthly Bonuses (1st of month, 6 AM) ─────────────────────────────────
    'pg-monthly-bonuses':         {'task': 'api.payment_gateways.tasks.analytics_tasks.aggregate_daily_analytics',                 'schedule': crontab(day_of_month=1, hour=6, minute=0)},
}
