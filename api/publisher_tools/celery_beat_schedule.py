# publisher_tools/celery_beat_schedule.py
"""
Celery Beat Schedule — earning_backend/settings.py-তে merge করতে হবে।

settings.py-তে এভাবে যোগ করো:

    from publisher_tools.celery_beat_schedule import PUBLISHER_TOOLS_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE = {
        **PUBLISHER_TOOLS_BEAT_SCHEDULE,
        # ... অন্য app-এর schedules
    }

tasks_missing.py-এর নতুন tasks অন্তর্ভুক্ত।
Import করো tasks.py-এর শেষে:

    from .tasks_missing import (
        finalize_daily_earnings,
        detect_fraud_patterns,
        recalculate_site_quality_metrics,
        retry_failed_webhook_deliveries,
        cleanup_old_webhook_logs,
        evaluate_ab_tests,
        process_automatic_payouts,
        update_publisher_performance_snapshots,
        refresh_publisher_fraud_scores,
        expire_kyc_records,
        notify_subscription_renewals,
        generate_monthly_report_data,
        cleanup_expired_velocity_records,
    )
"""

from celery.schedules import crontab

PUBLISHER_TOOLS_BEAT_SCHEDULE = {

    # ── Earnings ──────────────────────────────────────────────────────────────

    'publisher_tools.aggregate_hourly_earnings': {
        'task':     'publisher_tools.tasks.aggregate_hourly_earnings',
        'schedule': crontab(minute=5),
        'options':  {'queue': 'earnings'},
    },

    # NEW — finalize yesterday's earnings daily at 01:00
    'publisher_tools.finalize_daily_earnings': {
        'task':     'publisher_tools.tasks.finalize_daily_earnings',
        'schedule': crontab(hour=1, minute=0),
        'options':  {'queue': 'earnings'},
    },

    'publisher_tools.finalize_previous_month_earnings': {
        'task':     'publisher_tools.tasks.finalize_previous_month_earnings',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),
        'options':  {'queue': 'earnings'},
    },

    'publisher_tools.update_publisher_revenue_totals': {
        'task':     'publisher_tools.tasks.update_publisher_revenue_totals',
        'schedule': crontab(hour=3, minute=0),
        'options':  {'queue': 'earnings'},
    },

    # NEW — daily performance snapshot for all publishers at 02:30
    'publisher_tools.update_publisher_performance_snapshots': {
        'task':     'publisher_tools.tasks.update_publisher_performance_snapshots',
        'schedule': crontab(hour=2, minute=30),
        'options':  {'queue': 'earnings'},
    },

    # ── Invoices ──────────────────────────────────────────────────────────────

    'publisher_tools.generate_monthly_invoices': {
        'task':     'publisher_tools.tasks.generate_monthly_invoices',
        'schedule': crontab(day_of_month=2, hour=9, minute=0),
        'options':  {'queue': 'invoices'},
    },

    'publisher_tools.send_overdue_invoice_reminders': {
        'task':     'publisher_tools.tasks.send_overdue_invoice_reminders',
        'schedule': crontab(hour=8, minute=0),
        'options':  {'queue': 'invoices'},
    },

    # NEW — monthly report data pre-computed on 1st at 03:00
    'publisher_tools.generate_monthly_report_data': {
        'task':     'publisher_tools.tasks.generate_monthly_report_data',
        'schedule': crontab(day_of_month=1, hour=3, minute=0),
        'options':  {'queue': 'invoices'},
    },

    # ── Payouts ───────────────────────────────────────────────────────────────

    # NEW — automatic payout requests on 16th at 10:00
    'publisher_tools.process_automatic_payouts': {
        'task':     'publisher_tools.tasks.process_automatic_payouts',
        'schedule': crontab(day_of_month=16, hour=10, minute=0),
        'options':  {'queue': 'payouts'},
    },

    # ── Fraud & Traffic Safety ────────────────────────────────────────────────

    'publisher_tools.scan_invalid_traffic': {
        'task':     'publisher_tools.tasks.scan_invalid_traffic',
        'schedule': crontab(minute=30),
        'options':  {'queue': 'fraud'},
    },

    # NEW — fraud pattern detection every 6h at XX:15
    'publisher_tools.detect_fraud_patterns': {
        'task':     'publisher_tools.tasks.detect_fraud_patterns',
        'schedule': crontab(hour='*/6', minute=15),
        'options':  {'queue': 'fraud'},
    },

    # NEW — refresh per-publisher fraud scores daily at 05:00
    'publisher_tools.refresh_publisher_fraud_scores': {
        'task':     'publisher_tools.tasks.refresh_publisher_fraud_scores',
        'schedule': crontab(hour=5, minute=0),
        'options':  {'queue': 'fraud'},
    },

    'publisher_tools.cleanup_old_traffic_logs': {
        'task':     'publisher_tools.tasks.cleanup_old_traffic_logs',
        'schedule': crontab(hour=4, minute=0),
        'options':  {'queue': 'maintenance'},
    },

    # NEW — purge orphaned Redis velocity keys daily at 04:30
    'publisher_tools.cleanup_expired_velocity_records': {
        'task':     'publisher_tools.tasks.cleanup_expired_velocity_records',
        'schedule': crontab(hour=4, minute=30),
        'options':  {'queue': 'maintenance'},
    },

    # ── Ads.txt / Site Quality ────────────────────────────────────────────────

    'publisher_tools.check_all_ads_txt': {
        'task':     'publisher_tools.tasks.check_all_ads_txt',
        'schedule': crontab(hour=6, minute=0),
        'options':  {'queue': 'site_quality'},
    },

    # NEW — site quality recalculation every Sunday at 02:00
    'publisher_tools.recalculate_site_quality_metrics': {
        'task':     'publisher_tools.tasks.recalculate_site_quality_metrics',
        'schedule': crontab(day_of_week=0, hour=2, minute=0),
        'options':  {'queue': 'site_quality'},
    },

    'publisher_tools.update_site_quality_metrics': {
        'task':     'publisher_tools.tasks.update_site_quality_metrics',
        'schedule': crontab(hour=6, minute=30),
        'options':  {'queue': 'site_quality'},
    },

    # ── KYC / Verification ────────────────────────────────────────────────────

    # NEW — expire overdue KYC records daily at 06:30
    'publisher_tools.expire_kyc_records': {
        'task':     'publisher_tools.tasks.expire_kyc_records',
        'schedule': crontab(hour=6, minute=30),
        'options':  {'queue': 'maintenance'},
    },

    # ── Subscriptions ─────────────────────────────────────────────────────────

    # NEW — 7-day renewal reminders daily at 09:00
    'publisher_tools.notify_subscription_renewals': {
        'task':     'publisher_tools.tasks.notify_subscription_renewals',
        'schedule': crontab(hour=9, minute=0),
        'options':  {'queue': 'notifications'},
    },

    # ── Optimization ──────────────────────────────────────────────────────────

    'publisher_tools.auto_optimize_waterfalls': {
        'task':     'publisher_tools.tasks.auto_optimize_waterfalls',
        'schedule': crontab(hour=0, minute=30),
        'options':  {'queue': 'optimization'},
    },

    # ── Webhooks ──────────────────────────────────────────────────────────────

    # NEW — retry failed webhook deliveries every 2h
    'publisher_tools.retry_failed_webhook_deliveries': {
        'task':     'publisher_tools.tasks.retry_failed_webhook_deliveries',
        'schedule': crontab(hour='*/2', minute=45),
        'options':  {'queue': 'webhooks'},
    },

    # NEW — clean up 90-day-old webhook logs daily at 07:00
    'publisher_tools.cleanup_old_webhook_logs': {
        'task':     'publisher_tools.tasks.cleanup_old_webhook_logs',
        'schedule': crontab(hour=7, minute=0),
        'options':  {'queue': 'maintenance'},
    },

    # ── A/B Testing ───────────────────────────────────────────────────────────

    # NEW — evaluate running A/B tests every hour
    'publisher_tools.evaluate_ab_tests': {
        'task':     'publisher_tools.tasks.evaluate_ab_tests',
        'schedule': crontab(minute=50),
        'options':  {'queue': 'analytics'},
    },
}
