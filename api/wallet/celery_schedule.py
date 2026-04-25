# api/wallet/celery_schedule.py
"""
Add to your project celery.py:

    from api.wallet.celery_schedule import WALLET_BEAT_SCHEDULE
    CELERY_BEAT_SCHEDULE.update(WALLET_BEAT_SCHEDULE)
"""
from celery.schedules import crontab

WALLET_BEAT_SCHEDULE = {
    # Every 15 min
    "wallet-process-withdrawals":   {"task": "wallet.process_pending_withdrawals", "schedule": crontab(minute="*/15")},
    # Every 30 min
    "wallet-check-alerts":          {"task": "wallet.check_balance_alerts",         "schedule": crontab(minute="*/30")},
    # Daily 00:05
    "wallet-daily-payouts":         {"task": "wallet.run_daily_payouts",            "schedule": crontab(hour=0, minute=5)},
    # Daily 00:30
    "wallet-expire-bonuses":        {"task": "wallet.expire_bonus_balances",        "schedule": crontab(hour=0, minute=30)},
    # Daily 01:00
    "wallet-auto-reject-stale":     {"task": "wallet.auto_reject_stale_withdrawals","schedule": crontab(hour=1, minute=0)},
    "wallet-release-holds":         {"task": "wallet.release_publisher_holds",      "schedule": crontab(hour=1, minute=15)},
    # Daily 02:00
    "wallet-publisher-upgrades":    {"task": "wallet.check_publisher_upgrades",     "schedule": crontab(hour=2, minute=0)},
    "wallet-daily-insights":        {"task": "wallet.compute_daily_insights",       "schedule": crontab(hour=2, minute=15)},
    # Daily 03:00
    "wallet-expire-referrals":      {"task": "wallet.expire_referrals",             "schedule": crontab(hour=3, minute=0)},
    "wallet-daily-report":          {"task": "wallet.generate_daily_report",        "schedule": crontab(hour=3, minute=30)},
    "wallet-cleanup-idem":          {"task": "wallet.cleanup_idempotency_keys",     "schedule": crontab(hour=4, minute=0)},
    # Monthly 1st
    "wallet-top-earner-bonuses":    {"task": "wallet.award_top_earner_bonuses",     "schedule": crontab(hour=4, minute=0, day_of_month=1)},
}
