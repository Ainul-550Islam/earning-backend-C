# =============================================================================
# promotions/celery_config/beat_schedule.py
# 🔴 CRITICAL — Celery Beat Schedule
# ছাড়া কোনো task auto-run হবে না!
# settings.py তে add করো:
#   from api.promotions.celery_config.beat_schedule import PROMOTIONS_BEAT_SCHEDULE
#   CELERY_BEAT_SCHEDULE = {**CELERY_BEAT_SCHEDULE, **PROMOTIONS_BEAT_SCHEDULE}
# =============================================================================
from celery.schedules import crontab

PROMOTIONS_BEAT_SCHEDULE = {

    # ── Currency ─────────────────────────────────────────────────────────────
    'sync-currency-rates-hourly': {
        'task': 'promotions.tasks.sync_currency_rates',
        'schedule': crontab(minute=0),           # হর ঘণ্টার শুরুতে
        'options': {'expires': 3000},
    },

    # ── Campaign lifecycle ────────────────────────────────────────────────────
    'expire-old-campaigns-every-15min': {
        'task': 'promotions.tasks.expire_old_campaigns',
        'schedule': crontab(minute='*/15'),       # প্রতি ১৫ মিনিটে
        'options': {'expires': 600},
    },
    'activate-scheduled-campaigns-every-5min': {
        'task': 'promotions.tasks.activate_scheduled_campaigns',
        'schedule': crontab(minute='*/5'),        # প্রতি ৫ মিনিটে
        'options': {'expires': 240},
    },

    # ── Daily analytics ──────────────────────────────────────────────────────
    'generate-daily-analytics-midnight': {
        'task': 'promotions.tasks.generate_daily_analytics',
        'schedule': crontab(hour=0, minute=5),    # রাত ১২:০৫ AM
        'options': {'expires': 3600},
    },

    # ── Fraud & cleanup ──────────────────────────────────────────────────────
    'cleanup-expired-blacklists-daily': {
        'task': 'promotions.tasks.cleanup_expired_blacklists',
        'schedule': crontab(hour=2, minute=0),    # রাত ২:০০ AM
        'options': {'expires': 3600},
    },

    # ── RTB Auction ──────────────────────────────────────────────────────────
    'run-rtb-auction-every-minute': {
        'task': 'promotions.rtb_auction.tasks.run_rtb_auction',
        'schedule': crontab(minute='*/1'),        # প্রতি মিনিটে
        'options': {'expires': 50},
    },

    # ── Payout processing ────────────────────────────────────────────────────
    'process-daily-payouts-morning': {
        'task': 'promotions.crypto_payments.tasks.process_pending_payouts',
        'schedule': crontab(hour=6, minute=0),    # সকাল ৬:০০ AM
        'options': {'expires': 3600},
    },

    # ── Reputation ───────────────────────────────────────────────────────────
    'recalculate-reputations-nightly': {
        'task': 'promotions.tasks.recalculate_user_reputation',
        'schedule': crontab(hour=1, minute=30),   # রাত ১:৩০ AM
        'options': {'expires': 3600},
    },

    # ── Virtual currency ─────────────────────────────────────────────────────
    'sync-virtual-currency-rates-hourly': {
        'task': 'promotions.virtual_currency.tasks.sync_vc_rates',
        'schedule': crontab(minute=30),           # হর ঘণ্টার ৩০ মিনিটে
        'options': {'expires': 3000},
    },

    # ── Leaderboard cache refresh ─────────────────────────────────────────────
    'refresh-leaderboard-cache-every-5min': {
        'task': 'promotions.leaderboard.tasks.refresh_leaderboard_cache',
        'schedule': crontab(minute='*/5'),
        'options': {'expires': 240},
    },

    # ── SmartLink re-scoring ─────────────────────────────────────────────────
    'rescore-smartlink-offers-every-10min': {
        'task': 'promotions.smartlink.tasks.rescore_all_offers',
        'schedule': crontab(minute='*/10'),
        'options': {'expires': 500},
    },

    # ── CPI installs verification ────────────────────────────────────────────
    'verify-cpi-installs-every-30min': {
        'task': 'promotions.cpi_offers.tasks.verify_pending_installs',
        'schedule': crontab(minute='*/30'),
        'options': {'expires': 1500},
    },

    # ── Performance bonus check ──────────────────────────────────────────────
    'check-milestone-bonuses-daily': {
        'task': 'promotions.performance_bonus.tasks.check_all_milestones',
        'schedule': crontab(hour=3, minute=0),    # রাত ৩:০০ AM
        'options': {'expires': 3600},
    },

    # ── Quiz/Survey campaign refresh ─────────────────────────────────────────
    'refresh-quiz-offers-hourly': {
        'task': 'promotions.quiz_survey.tasks.refresh_active_quizzes',
        'schedule': crontab(minute=15),
        'options': {'expires': 3000},
    },

    # ── SubID analytics aggregation ──────────────────────────────────────────
    'aggregate-subid-stats-hourly': {
        'task': 'promotions.subid_tracking.tasks.aggregate_subid_stats',
        'schedule': crontab(minute=45),
        'options': {'expires': 3000},
    },

    # ── Email campaign delivery ──────────────────────────────────────────────
    'send-daily-publisher-report': {
        'task': 'promotions.notifications.tasks.send_daily_report',
        'schedule': crontab(hour=8, minute=0),    # সকাল ৮:০০ AM
        'options': {'expires': 3600},
    },

    # ── Traffic quality scoring ──────────────────────────────────────────────
    'score-publisher-traffic-quality-nightly': {
        'task': 'promotions.traffic_quality.tasks.score_all_publishers',
        'schedule': crontab(hour=4, minute=0),    # রাত ৪:০০ AM
        'options': {'expires': 3600},
    },
    # ── New tasks ────────────────────────────────────────────────────────────
    'auto-upgrade-publisher-tiers-nightly': {
        'task': 'promotions.tier_upgrade.auto_upgrade.auto_upgrade_all_publishers',
        'schedule': crontab(hour=1, minute=0),
        'options': {'expires': 3600},
    },
    'process-daily-auto-payouts-morning': {
        'task': 'promotions.tasks.process_daily_auto_payouts',
        'schedule': crontab(hour=6, minute=0),
        'options': {'expires': 3600},
    },

}