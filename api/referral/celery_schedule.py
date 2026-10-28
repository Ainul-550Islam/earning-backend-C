# api/referral/celery_schedule.py
# Complete Celery Beat Schedule for referral module
# settings.py তে এটা import করো:
#   from api.referral.celery_schedule import REFERRAL_CELERY_BEAT_SCHEDULE
#   CELERY_BEAT_SCHEDULE.update(REFERRAL_CELERY_BEAT_SCHEDULE)
# ============================================================

from celery.schedules import crontab

REFERRAL_CELERY_BEAT_SCHEDULE = {

    # ── Commission Processing ─────────────────────────────────────────────────
    'referral-release-held-commissions': {
        'task': 'referral.release_expired_commission_holds',
        'schedule': crontab(minute=30),          # Every hour at :30
        'options': {'expires': 3000},
    },
    'referral-process-pending-commissions': {
        'task': 'referral.process_pending_commissions_to_wallet',
        'schedule': crontab(hour=2, minute=0),   # 2 AM daily
        'options': {'expires': 86400},
    },
    'referral-create-weekly-payouts': {
        'task': 'referral.create_weekly_payouts',
        'schedule': crontab(hour=6, minute=0, day_of_week=1),  # Monday 6 AM
        'options': {'expires': 86400},
    },

    # ── Fraud Detection ───────────────────────────────────────────────────────
    'referral-daily-fraud-scan': {
        'task': 'referral.daily_fraud_scan',
        'schedule': crontab(hour=3, minute=0),   # 3 AM daily
        'options': {'expires': 86400},
    },
    'referral-expire-blacklist-entries': {
        'task': 'referral.expire_blacklist_entries',
        'schedule': crontab(hour=4, minute=0),   # 4 AM daily
        'options': {'expires': 86400},
    },
    'referral-auto-clear-low-risk': {
        'task': 'referral.auto_clear_low_risk_suspicious',
        'schedule': crontab(hour=5, minute=0, day_of_week=1),  # Monday 5 AM
        'options': {'expires': 86400},
    },

    # ── Clawbacks ─────────────────────────────────────────────────────────────
    'referral-process-clawbacks': {
        'task': 'referral.process_approved_clawbacks',
        'schedule': crontab(hour=1, minute=0),   # 1 AM daily
        'options': {'expires': 86400},
    },
    'referral-initiate-fraud-clawbacks': {
        'task': 'referral.initiate_fraud_clawbacks',
        'schedule': crontab(hour=2, minute=30),  # 2:30 AM daily
        'options': {'expires': 86400},
    },

    # ── Campaigns ────────────────────────────────────────────────────────────
    'referral-campaign-schedules': {
        'task': 'referral.check_campaign_schedules',
        'schedule': crontab(minute='*/15'),       # Every 15 minutes
        'options': {'expires': 800},
    },
    'referral-campaign-budget-check': {
        'task': 'referral.check_campaign_budget',
        'schedule': crontab(minute=45),           # Every hour at :45
        'options': {'expires': 3000},
    },

    # ── Contests ─────────────────────────────────────────────────────────────
    'referral-update-leaderboards': {
        'task': 'referral.update_all_contest_leaderboards',
        'schedule': crontab(minute=15),           # Every hour at :15
        'options': {'expires': 3000},
    },
    'referral-finalize-contests': {
        'task': 'referral.check_and_finalize_contests',
        'schedule': crontab(hour=0, minute=30),  # 12:30 AM daily
        'options': {'expires': 86400},
    },
    'referral-contest-status': {
        'task': 'referral.update_contest_statuses',
        'schedule': crontab(minute=5),            # Every hour at :05
        'options': {'expires': 3000},
    },
    'referral-notify-rank-changes': {
        'task': 'referral.notify_contest_rank_changes',
        'schedule': crontab(hour=18, minute=0),  # 6 PM daily
        'options': {'expires': 86400},
    },

    # ── Tree Management ───────────────────────────────────────────────────────
    'referral-rebuild-stale-trees': {
        'task': 'referral.rebuild_stale_trees',
        'schedule': crontab(hour=4, minute=30),  # 4:30 AM daily
        'options': {'expires': 86400},
    },
    'referral-full-tree-rebuild': {
        'task': 'referral.full_tree_rebuild',
        'schedule': crontab(hour=2, minute=0, day_of_week=0),  # Sunday 2 AM
        'options': {'expires': 86400},
    },
    'referral-tree-consistency': {
        'task': 'referral.tree_consistency_check',
        'schedule': crontab(hour=6, minute=0),   # 6 AM daily
        'options': {'expires': 86400},
    },
    'referral-weekly-tree-snapshots': {
        'task': 'referral.take_weekly_tree_snapshots',
        'schedule': crontab(hour=3, minute=0, day_of_week=1),  # Monday 3 AM
        'options': {'expires': 86400},
    },

    # ── LTV ───────────────────────────────────────────────────────────────────
    'referral-weekly-ltv-recalc': {
        'task': 'referral.weekly_ltv_recalculation',
        'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Sunday 1 AM
        'options': {'expires': 86400},
    },
    'referral-flag-churn-risk': {
        'task': 'referral.flag_high_churn_risk',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),  # Monday 9 AM
        'options': {'expires': 86400},
    },

    # ── Analytics & Insights ──────────────────────────────────────────────────
    'referral-daily-insights': {
        'task': 'referral.calculate_daily_insights',
        'schedule': crontab(hour=0, minute=5),   # 12:05 AM daily
        'options': {'expires': 86400},
    },
    'referral-code-conversion-rates': {
        'task': 'referral.update_code_conversion_rates',
        'schedule': crontab(hour=1, minute=15),  # 1:15 AM daily
        'options': {'expires': 86400},
    },

    # ── Top Referrers ─────────────────────────────────────────────────────────
    'referral-daily-top-referrer': {
        'task': 'referral.daily_top_referrer_snapshot',
        'schedule': crontab(hour=23, minute=55), # 11:55 PM daily
        'options': {'expires': 86400},
    },
    'referral-weekly-top-referrer': {
        'task': 'referral.weekly_top_referrer_snapshot',
        'schedule': crontab(hour=5, minute=0, day_of_week=1),  # Monday 5 AM
        'options': {'expires': 86400},
    },
    'referral-monthly-top-referrer': {
        'task': 'referral.monthly_top_referrer_snapshot',
        'schedule': crontab(hour=5, minute=30, day_of_month=1),  # 1st of month
        'options': {'expires': 86400},
    },
    'referral-rank-changes': {
        'task': 'referral.compute_rank_changes',
        'schedule': crontab(hour=0, minute=10),  # After midnight snapshot
        'options': {'expires': 86400},
    },

    # ── Notifications ─────────────────────────────────────────────────────────
    'referral-check-milestones': {
        'task': 'referral.check_milestone_achievements',
        'schedule': crontab(hour='*/6', minute=0),  # Every 6 hours
        'options': {'expires': 21600},
    },
    'referral-weekly-summary': {
        'task': 'referral.send_weekly_referral_summary',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday 8 AM
        'options': {'expires': 86400},
    },

    # ── Cleanup ───────────────────────────────────────────────────────────────
    'referral-run-all-cleanups': {
        'task': 'referral.run_all_cleanups',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),  # 1st of month
        'options': {'expires': 86400},
    },
}