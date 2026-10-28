# api/referral/celery_beat_config.py
# Celery Beat schedule — alternate format (dict-based)
# Choose ONE of: celery_schedule.py OR celery_beat_config.py
#
# settings.py এ যোগ করুন:
#   from api.referral.celery_beat_config import REFERRAL_BEAT_CONFIG
#   CELERY_BEAT_SCHEDULE.update(REFERRAL_BEAT_CONFIG)
# ============================================================

from celery.schedules import crontab

REFERRAL_BEAT_CONFIG = {

    # ── Commission Processing (High Priority) ─────────────────────────────────
    'referral-release-held-commissions': {
        'task': 'referral.release_expired_commission_holds',
        'schedule': crontab(minute='*/30'),  # Every 30 min
        'options': {'queue': 'referral_high'},
    },
    'referral-process-pending-commissions': {
        'task': 'referral.process_pending_commissions_to_wallet',
        'schedule': crontab(hour='*/2'),  # Every 2 hours
        'options': {'queue': 'referral_high'},
    },
    'referral-create-weekly-payouts': {
        'task': 'referral.create_weekly_payouts',
        'schedule': crontab(day_of_week='monday', hour=9, minute=0),
        'options': {'queue': 'referral_high'},
    },
    'referral-process-clawbacks': {
        'task': 'referral.process_approved_clawbacks',
        'schedule': crontab(hour='*/4'),
        'options': {'queue': 'referral_high'},
    },

    # ── Fraud Scanning ─────────────────────────────────────────────────────────
    'referral-daily-fraud-scan': {
        'task': 'referral.daily_fraud_scan',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
        'options': {'queue': 'referral_normal'},
    },
    'referral-auto-clear-low-risk': {
        'task': 'referral.auto_clear_low_risk_suspicious',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'referral_normal'},
    },
    'referral-expire-blacklist': {
        'task': 'referral.expire_blacklist_entries',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'referral_low'},
    },

    # ── Campaigns & Contests ──────────────────────────────────────────────────
    'referral-check-campaign-schedules': {
        'task': 'referral.check_campaign_schedules',
        'schedule': crontab(minute='*/15'),  # Every 15 min
        'options': {'queue': 'referral_normal'},
    },
    'referral-update-contest-leaderboards': {
        'task': 'referral.update_all_contest_leaderboards',
        'schedule': crontab(minute='*/10'),  # Every 10 min (real-time feel)
        'options': {'queue': 'referral_normal'},
    },
    'referral-finalize-contests': {
        'task': 'referral.check_and_finalize_contests',
        'schedule': crontab(hour='*/1'),  # Hourly
        'options': {'queue': 'referral_normal'},
    },

    # ── Tree Maintenance ───────────────────────────────────────────────────────
    'referral-rebuild-stale-trees': {
        'task': 'referral.rebuild_stale_trees',
        'schedule': crontab(hour=1, minute=0),  # 1 AM daily
        'options': {'queue': 'referral_low'},
    },
    'referral-tree-snapshots': {
        'task': 'referral.take_weekly_tree_snapshots',
        'schedule': crontab(day_of_week='sunday', hour=23, minute=0),
        'options': {'queue': 'referral_low'},
    },

    # ── Analytics ─────────────────────────────────────────────────────────────
    'referral-daily-insights': {
        'task': 'referral.calculate_daily_insights',
        'schedule': crontab(hour=0, minute=5),  # 00:05 daily
        'options': {'queue': 'referral_normal'},
    },
    'referral-top-referrer-daily': {
        'task': 'referral.daily_top_referrer_snapshot',
        'schedule': crontab(hour=0, minute=10),
        'options': {'queue': 'referral_normal'},
    },
    'referral-top-referrer-weekly': {
        'task': 'referral.weekly_top_referrer_snapshot',
        'schedule': crontab(day_of_week='monday', hour=0, minute=30),
        'options': {'queue': 'referral_normal'},
    },

    # ── LTV & Churn ───────────────────────────────────────────────────────────
    'referral-weekly-ltv': {
        'task': 'referral.weekly_ltv_recalculation',
        'schedule': crontab(day_of_week='sunday', hour=2, minute=0),
        'options': {'queue': 'referral_low'},
    },
    'referral-churn-risk': {
        'task': 'referral.flag_high_churn_risk',
        'schedule': crontab(day_of_week='monday', hour=3, minute=0),
        'options': {'queue': 'referral_low'},
    },

    # ── Notifications ─────────────────────────────────────────────────────────
    'referral-weekly-summary': {
        'task': 'referral.send_weekly_referral_summary',
        'schedule': crontab(day_of_week='monday', hour=9, minute=30),
        'options': {'queue': 'referral_normal'},
    },

    # ── World-Class Cap Tasks ─────────────────────────────────────────────────
    'referral-viral-coefficient': {
        'task': 'referral.update_viral_coefficient',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
        'options': {'queue': 'referral_low'},
    },
    'referral-streak-bonuses': {
        'task': 'referral.check_streak_bonuses',
        'schedule': crontab(hour=8, minute=0),  # Daily at 8 AM
        'options': {'queue': 'referral_normal'},
    },
    'referral-tier-progression': {
        'task': 'referral.update_user_tier_progressions',
        'schedule': crontab(hour=5, minute=0),  # Daily at 5 AM
        'options': {'queue': 'referral_low'},
    },
    'referral-recurring-commissions': {
        'task': 'referral.process_recurring_commissions',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6 AM
        'options': {'queue': 'referral_high'},
    },
    'referral-expire-commissions': {
        'task': 'referral.expire_commissions',
        'schedule': crontab(hour=7, minute=0),  # Daily at 7 AM
        'options': {'queue': 'referral_normal'},
    },
    'referral-expire-credits': {
        'task': 'referral.expire_referral_credits',
        'schedule': crontab(day_of_week='sunday', hour=4, minute=0),
        'options': {'queue': 'referral_low'},
    },

    # ── Cleanup ───────────────────────────────────────────────────────────────
    'referral-cleanup': {
        'task': 'referral.run_all_cleanups',
        'schedule': crontab(day_of_week='sunday', hour=3, minute=0),
        'options': {'queue': 'referral_low'},
    },

    # ── Sync Manager ─────────────────────────────────────────────────────────
    'referral-periodic-sync': {
        'task': 'referral.run_periodic_sync',
        'schedule': crontab(hour=1, minute=30),  # Daily at 1:30 AM
        'options': {'queue': 'referral_low'},
    },
}