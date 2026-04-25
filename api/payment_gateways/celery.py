# api/payment_gateways/celery.py
# Celery Beat schedule for all payment gateway tasks

from celery import Celery
from celery.schedules import crontab

app = Celery('payment_gateways')

app.conf.beat_schedule = {
    # ── Health monitoring (every 5 min) ───────────────────────────────────────
    'check-gateway-health': {
        'task':     'api.payment_gateways.tasks.gateway_health_tasks.check_all_gateways',
        'schedule': crontab(minute='*/5'),
    },
    # ── Deposit verification (every 10 min) ───────────────────────────────────
    'verify-pending-deposits': {
        'task':     'api.payment_gateways.tasks.deposit_verification_tasks.verify_pending_deposits',
        'schedule': crontab(minute='*/10'),
    },
    'expire-old-deposits': {
        'task':     'api.payment_gateways.tasks.deposit_verification_tasks.expire_old_deposits',
        'schedule': crontab(minute=0, hour='*/2'),
    },
    # ── Reconciliation (nightly 3 AM) ─────────────────────────────────────────
    'nightly-reconciliation': {
        'task':     'api.payment_gateways.tasks.reconciliation_tasks.nightly_reconciliation',
        'schedule': crontab(hour=3, minute=0),
    },
    # ── Payouts (5 PM daily, like CPAlead) ────────────────────────────────────
    'process-approved-payouts': {
        'task':     'api.payment_gateways.tasks.withdrawal_processing_tasks.process_approved_payouts',
        'schedule': crontab(hour=17, minute=0),
    },
    # ── Schedules ──────────────────────────────────────────────────────────────
    'process-due-scheduled-payouts': {
        'task':     'api.payment_gateways.tasks.schedule_tasks.process_due_payouts',
        'schedule': crontab(hour=17, minute=30),
    },
    # ── Analytics (hourly) ────────────────────────────────────────────────────
    'aggregate-daily-analytics': {
        'task':     'api.payment_gateways.tasks.analytics_tasks.aggregate_daily_analytics',
        'schedule': crontab(minute=0),
    },
    'update-success-rates': {
        'task':     'api.payment_gateways.tasks.analytics_tasks.update_success_rates',
        'schedule': crontab(minute=30),
    },
    # ── Exchange rates (hourly) ────────────────────────────────────────────────
    'sync-exchange-rates': {
        'task':     'api.payment_gateways.tasks.exchange_rate_tasks.sync_exchange_rates',
        'schedule': crontab(minute=15),
    },
    # ── Tracking stats ────────────────────────────────────────────────────────
    'aggregate-tracking-stats': {
        'task':     'api.payment_gateways.tasks.exchange_rate_tasks.aggregate_daily_stats',
        'schedule': crontab(minute=45),
    },
    # ── Alerts ─────────────────────────────────────────────────────────────────
    'check-failure-rate-alerts': {
        'task':     'api.payment_gateways.tasks.alert_tasks.check_failure_rate_alerts',
        'schedule': crontab(hour='*/4', minute=0),
    },
    'credential-expiry-reminder': {
        'task':     'api.payment_gateways.tasks.alert_tasks.credential_expiry_reminder',
        'schedule': crontab(hour=9, minute=0),
    },
    'cleanup-old-logs': {
        'task':     'api.payment_gateways.tasks.alert_tasks.cleanup_old_logs',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Weekly Sunday 2AM
    },
    # ── Referral ───────────────────────────────────────────────────────────────
    'pay-referral-commissions': {
        'task':     'api.payment_gateways.tasks.referral_tasks.pay_pending_commissions',
        'schedule': crontab(hour=9, minute=30),
    },
    'expire-inactive-referrals': {
        'task':     'api.payment_gateways.tasks.referral_tasks.expire_inactive_referrals',
        'schedule': crontab(hour=0, minute=0),
    },
    # ── Offer metrics ──────────────────────────────────────────────────────────
    'update-offer-metrics': {
        'task':     'api.payment_gateways.tasks.exchange_rate_tasks.update_offer_metrics',
        'schedule': crontab(minute=45),
    },
}

# ── New: blacklist + quality tasks ────────────────────────────────────────────
app.conf.beat_schedule.update({
    'auto-blacklist-weekly': {
        'task':     'api.payment_gateways.tasks.analytics_tasks.auto_blacklist_low_quality_publishers',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3AM
    },
    'update-quality-scores-daily': {
        'task':     'api.payment_gateways.tasks.analytics_tasks.update_offer_quality_scores',
        'schedule': crontab(hour=4, minute=0),
    },
})

# ── Fast Pay + Bonuses ─────────────────────────────────────────────────────────
app.conf.beat_schedule.update({
    'daily-fast-pay': {
        'task':     'api.payment_gateways.tasks.usdt_fastpay_tasks.process_daily_fastpay',
        'schedule': crontab(hour=17, minute=0),   # 5 PM daily (CPAlead style)
    },
    'usdt-fastpay': {
        'task':     'api.payment_gateways.tasks.usdt_fastpay_tasks.process_usdt_fastpay_requests',
        'schedule': crontab(minute='*/30'),
    },
    'monthly-bonuses': {
        'task':     'api.payment_gateways.tasks.analytics_tasks.auto_blacklist_low_quality_publishers',
        'schedule': crontab(day_of_month=1, hour=6, minute=0),
    },
})
