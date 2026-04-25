# api/wallet/celery_beat_config.py
"""
Complete Celery Beat schedule for the wallet app.
Include in celery.py:
    from api.wallet.celery_beat_config import WALLET_BEAT_SCHEDULE
    app.conf.beat_schedule.update(WALLET_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

WALLET_BEAT_SCHEDULE = {
    # ── CPAlead Publisher Tasks ──────────────────────────
    "wallet-daily-payouts": {
        "task":     "wallet_cap.process_daily_payouts",
        "schedule": crontab(hour=0, minute=5),     # 00:05 daily
        "options":  {"queue": "wallet_payouts"},
    },
    "wallet-release-holds": {
        "task":     "wallet_cap.release_publisher_holds",
        "schedule": crontab(hour=2, minute=0),     # 02:00 daily
    },
    "wallet-check-publisher-upgrades": {
        "task":     "wallet_cap.check_publisher_upgrades",
        "schedule": crontab(hour=3, minute=0),     # 03:00 daily
    },
    "wallet-reset-offer-caps": {
        "task":     "wallet_cap.reset_offer_daily_caps",
        "schedule": crontab(hour=0, minute=1),     # 00:01 daily
    },
    "wallet-award-top-earners": {
        "task":     "wallet_cap.award_top_earner_bonuses",
        "schedule": crontab(hour=1, minute=0, day_of_month=1),  # 1st of month
    },
    "wallet-expire-referrals": {
        "task":     "wallet_cap.expire_referral_programs",
        "schedule": crontab(hour=3, minute=30),    # 03:30 daily
    },

    # ── Core Wallet Tasks ────────────────────────────────
    "wallet-expire-bonuses": {
        "task":     "wallet.expire_bonus_balances",
        "schedule": crontab(hour=1, minute=0),     # 01:00 daily
    },
    "wallet-reset-earning-caps": {
        "task":     "wallet.reset_daily_earning_caps",
        "schedule": crontab(hour=0, minute=0),     # midnight
    },
    "wallet-sync-balances": {
        "task":     "wallet.sync_balance",
        "schedule": crontab(minute="*/15"),        # every 15 min
    },
    "wallet-auto-reject-stale": {
        "task":     "wallet.auto_reject_stale_withdrawals",
        "schedule": crontab(hour="*/6"),           # every 6 hours
    },
    "wallet-process-batches": {
        "task":     "wallet.process_withdrawal_batches",
        "schedule": crontab(hour="*/4"),           # every 4 hours
    },
    "wallet-fraud-check": {
        "task":     "wallet.run_fraud_checks",
        "schedule": crontab(hour="*/2"),           # every 2 hours
    },
    "wallet-aml-scan": {
        "task":     "wallet.run_aml_scan",
        "schedule": crontab(hour=4, minute=0),     # 04:00 daily
    },

    # ── Ledger / Reconciliation ──────────────────────────
    "wallet-daily-reconciliation": {
        "task":     "wallet.run_daily_reconciliation",
        "schedule": crontab(hour=5, minute=0),     # 05:00 daily
    },
    "wallet-weekly-snapshots": {
        "task":     "wallet.take_weekly_snapshots",
        "schedule": crontab(hour=6, minute=0, day_of_week=0),  # Sunday 06:00
    },
    "wallet-daily-liability": {
        "task":     "wallet.compute_daily_liability",
        "schedule": crontab(hour=23, minute=55),   # 23:55 daily
    },
    "wallet-daily-insights": {
        "task":     "wallet.compute_daily_insights",
        "schedule": crontab(hour=23, minute=45),   # 23:45 daily
    },

    # ── Currency & Notifications ─────────────────────────
    "wallet-update-exchange-rates": {
        "task":     "wallet.update_exchange_rates",
        "schedule": crontab(minute=0),             # every hour
    },
    "wallet-notify-bonus-expiring": {
        "task":     "wallet.notify_bonus_expiring",
        "schedule": crontab(hour=9, minute=0),     # 09:00 daily
    },
    "wallet-cleanup-idempotency": {
        "task":     "wallet.cleanup_idempotency_keys",
        "schedule": crontab(hour=7, minute=0),     # 07:00 daily
    },
    "wallet-cleanup-webhook-logs": {
        "task":     "wallet.cleanup_old_webhook_logs",
        "schedule": crontab(hour=7, minute=30),    # 07:30 daily
    },
    "wallet-withdrawal-reminders": {
        "task":     "wallet.send_withdrawal_reminders",
        "schedule": crontab(hour=10, minute=0),    # 10:00 daily
    },

    # ── Monthly Tasks ────────────────────────────────────
    "wallet-monthly-statements": {
        "task":     "wallet.generate_monthly_statements",
        "schedule": crontab(hour=3, minute=0, day_of_month=1),  # 1st of month 03:00
    },
    "wallet-annual-tax-records": {
        "task":     "wallet.generate_annual_tax_records",
        "schedule": crontab(hour=4, minute=0, month_of_year=1, day_of_month=1),  # Jan 1st
    },
}
