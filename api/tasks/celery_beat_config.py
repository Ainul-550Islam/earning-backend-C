"""
api/tasks/celery_beat_config.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Complete Celery app configuration for the task system.
Includes: app settings, routing, beat schedule, and queues.

Usage in celery.py:
    from api.tasks.celery_beat_config import configure_celery
    app = Celery('myproject')
    configure_celery(app)

Or manually:
    from api.tasks.celery_beat_config import (
        CELERY_TASK_ROUTES,
        CELERY_BEAT_SCHEDULE,
        CELERY_QUEUES,
    )
"""

from celery.schedules import crontab
from kombu import Queue, Exchange

# ══════════════════════════════════════════════════════════════════════════════
# QUEUES
# ══════════════════════════════════════════════════════════════════════════════

default_exchange  = Exchange('default',  type='direct')
high_exchange     = Exchange('high',     type='direct')
payments_exchange = Exchange('payments', type='direct')
emails_exchange   = Exchange('emails',   type='direct')
reports_exchange  = Exchange('reports',  type='direct')
ml_exchange       = Exchange('ml',       type='direct')
webhooks_exchange = Exchange('webhooks', type='direct')

CELERY_QUEUES = (
    Queue('high',     high_exchange,     routing_key='high'),
    Queue('default',  default_exchange,  routing_key='default'),
    Queue('payments', payments_exchange, routing_key='payments'),
    Queue('emails',   emails_exchange,   routing_key='emails'),
    Queue('reports',  reports_exchange,  routing_key='reports'),
    Queue('ml',       ml_exchange,       routing_key='ml'),
    Queue('webhooks', webhooks_exchange, routing_key='webhooks'),
    Queue('low',      default_exchange,  routing_key='low'),
)

CELERY_DEFAULT_QUEUE    = 'default'
CELERY_DEFAULT_EXCHANGE = 'default'
CELERY_DEFAULT_ROUTING_KEY = 'default'


# ══════════════════════════════════════════════════════════════════════════════
# TASK ROUTING
# ══════════════════════════════════════════════════════════════════════════════

CELERY_TASK_ROUTES = {
    # High priority
    'tasks.cpalead_tasks.*':             {'queue': 'high'},
    'tasks.fraud_detection_tasks.*':     {'queue': 'high'},
    'tasks.click_tracking_tasks.*':      {'queue': 'high'},
    'tasks.rtb_tasks.run_bid_auction':   {'queue': 'high'},
    'tasks.rtb_tasks.refresh_bid_cache': {'queue': 'high'},
    'tasks.tasks_cap.check_all_offer_caps': {'queue': 'high'},
    'tasks.ip_management_tasks.sync_ip_blacklist': {'queue': 'high'},
    'tasks.traffic_quality_tasks.detect_proxy_traffic': {'queue': 'high'},
    'tasks.cpi_tasks.sync_mmp_install_data': {'queue': 'high'},
    'tasks.email_submit_tasks.detect_email_fraud': {'queue': 'high'},
    'tasks.integration.*':               {'queue': 'high'},

    # Payments
    'tasks.payment_tasks.*':             {'queue': 'payments'},
    'tasks.daily_payout_tasks.*':        {'queue': 'payments'},
    'tasks.crypto_payout_tasks.*':       {'queue': 'payments'},
    'tasks.advertiser_tasks.process_advertiser_billing': {'queue': 'payments'},
    'tasks.referral_tasks.commission_processing': {'queue': 'payments'},
    'tasks.earning_tasks.distribute_bonus_rewards': {'queue': 'payments'},

    # Emails
    'tasks.notification_tasks.send_email_notification': {'queue': 'emails'},
    'tasks.notification_tasks.send_bulk_push_notifications': {'queue': 'emails'},
    'tasks.email_drip_tasks.*':          {'queue': 'emails'},
    'tasks.user_lifecycle_tasks.send_*': {'queue': 'emails'},
    'tasks.community_tasks.send_community_digest': {'queue': 'emails'},
    'tasks.api_key_tasks.*':             {'queue': 'emails'},

    # Reports
    'tasks.report_tasks.*':              {'queue': 'reports'},
    'tasks.analytics_tasks.daily_analytics_rollup': {'queue': 'reports'},
    'tasks.data_pipeline_tasks.export_to_s3': {'queue': 'reports'},

    # ML
    'tasks.ml_tasks.*':                  {'queue': 'ml'},

    # Webhooks
    'tasks.webhook_tasks.*':             {'queue': 'webhooks'},

    # Low priority
    'tasks.cleanup_tasks.*':             {'queue': 'low'},
    'tasks.backup_tasks.*':              {'queue': 'low'},
    'tasks.maintenance_tasks.*':         {'queue': 'low'},
    'tasks.compliance_tasks.anonymize_*': {'queue': 'low'},
}


# ══════════════════════════════════════════════════════════════════════════════
# CELERY SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

CELERY_SETTINGS = {
    # Serialization
    'task_serializer':   'json',
    'result_serializer': 'json',
    'accept_content':    ['json'],

    # Result backend
    'result_expires':    3600 * 24,   # 24 hours

    # Worker settings
    'worker_prefetch_multiplier': 1,
    'worker_max_tasks_per_child': 1000,
    'worker_max_memory_per_child': 200000,  # 200MB

    # Task settings
    'task_acks_late':           True,
    'task_reject_on_worker_lost': True,
    'task_track_started':       True,
    'task_time_limit':          1800,    # 30 min hard limit
    'task_soft_time_limit':     1740,    # 29 min soft limit
    'task_compression':         'gzip',  # Compress large payloads

    # Beat
    'beat_scheduler': 'django_celery_beat.schedulers.DatabaseScheduler',

    # Queues
    'task_default_queue':          'default',
    'task_queues':                 CELERY_QUEUES,
    'task_routes':                 CELERY_TASK_ROUTES,

    # Monitoring
    'worker_send_task_events':     True,
    'task_send_sent_event':        True,
}


# ══════════════════════════════════════════════════════════════════════════════
# BEAT SCHEDULE (core entries — extended in celery_beat_schedule.py)
# ══════════════════════════════════════════════════════════════════════════════

CELERY_BEAT_SCHEDULE = {

    # ── Real-time (every minute or less) ──────────────────────────────────

    'rtb-refresh-bids': {
        'task':     'tasks.rtb_tasks.refresh_bid_cache',
        'schedule': crontab(minute='*/1'),
        'options':  {'queue': 'high', 'expires': 55},
    },
    'check-offer-caps': {
        'task':     'tasks.tasks_cap.check_all_offer_caps',
        'schedule': crontab(minute='*/1'),
        'options':  {'queue': 'high', 'expires': 55},
    },
    'update-ad-rates': {
        'task':     'tasks.ad_unit_tasks.update_ad_cpm_rates',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'high', 'expires': 290},
    },
    'sync-crypto-rates': {
        'task':     'tasks.crypto_payout_tasks.sync_crypto_exchange_rates',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'default', 'expires': 290},
    },
    'sync-metaverse-rates': {
        'task':     'tasks.metaverse_tasks.sync_metaverse_exchange_rates',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'default', 'expires': 290},
    },
    # ── Internet Connectivity + Task Aging ───────────────────────────────
    'internet-connectivity': {
        'task':    'tasks.internet_check_tasks.check_internet_connectivity',
        'schedule': 60,                         # every 60 seconds
        'options': {'queue': 'default', 'expires': 55},
    },
    'detect-aging-tasks': {
        'task':    'tasks.internet_check_tasks.detect_aging_tasks',
        'schedule': 300,                        # every 5 minutes
        'options': {'queue': 'default', 'expires': 290},
    },
    'auto-recover-aging-tasks': {
        'task':    'tasks.internet_check_tasks.auto_recover_aging_tasks',
        'schedule': 600,                        # every 10 minutes
        'options': {'queue': 'default', 'expires': 590},
    },
    'expire-stale-locks': {
        'task':    'tasks.internet_check_tasks.expire_stale_task_locks',
        'schedule': 300,                        # every 5 minutes
        'options': {'queue': 'default', 'expires': 290},
    },
    # ── Existing health checks ────────────────────────────────────────────
    'system-health': {
        'task':     'tasks.health_check_tasks.system_health_ping',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'default', 'expires': 240},
    },
    'worker-health': {
        'task':     'tasks.celery_tasks.run_worker_health_refresh',
        'schedule': crontab(minute='*/2'),
        'options':  {'queue': 'default', 'expires': 90},
    },
    'platform-kpis': {
        'task':     'tasks.analytics_tasks.compute_platform_kpis',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'default'},
    },

    # ─ PART 9: CLEANUP ABANDONED TASK LOCKS ─────────────────────────────
    'cleanup-abandoned-locks': {
        'task':     'tasks.celery_tasks.cleanup_abandoned_task_locks',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options':  {'queue': 'default', 'expires': 240},  # 4 min timeout
    },

    # ── Every 15-30 minutes ────────────────────────────────────────────────

    'fraud-scan': {
        'task':     'tasks.fraud_detection_tasks.run_fraud_detection_scan',
        'schedule': crontab(minute='*/15'),
        'options':  {'queue': 'high'},
    },
    'process-withdrawals': {
        'task':     'tasks.payment_tasks.process_withdrawal_requests',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'payments'},
    },
    'check-advertiser-budgets': {
        'task':     'tasks.advertiser_tasks.check_advertiser_budgets',
        'schedule': crontab(minute='*/10'),
        'options':  {'queue': 'high'},
    },
    'click-attribution': {
        'task':     'tasks.click_tracking_tasks.calculate_click_attribution',
        'schedule': crontab(minute='*/5'),
        'options':  {'queue': 'high'},
    },
    'leaderboard-update': {
        'task':     'tasks.gamification_tasks.update_global_leaderboard',
        'schedule': crontab(minute='*/30'),
        'options':  {'queue': 'default'},
    },
    'ml-fraud-prediction': {
        'task':     'tasks.ml_tasks.run_fraud_prediction',
        'schedule': crontab(minute='*/30'),
        'options':  {'queue': 'ml'},
    },
    'detect-quiz-fraud': {
        'task':     'tasks.personality_quiz_tasks.detect_quiz_fraud',
        'schedule': crontab(minute='*/15'),
        'options':  {'queue': 'high'},
    },
    'sync-ip-blacklist': {
        'task':     'tasks.ip_management_tasks.sync_ip_blacklist',
        'schedule': crontab(minute=0, hour='*/1'),
        'options':  {'queue': 'high'},
    },
    'daily-payout-handle-failures': {
        'task':     'tasks.daily_payout_tasks.handle_payout_failures',
        'schedule': crontab(minute='*/30'),
        'options':  {'queue': 'payments'},
    },

    # ── Hourly ─────────────────────────────────────────────────────────────

    'recalculate-epc': {
        'task':     'tasks.smartlink_tasks.recalculate_epc',
        'schedule': crontab(minute=0, hour='*/1'),
        'options':  {'queue': 'default'},
    },
    'commission-processing': {
        'task':     'tasks.referral_tasks.commission_processing',
        'schedule': crontab(minute=0, hour='*/1'),
        'options':  {'queue': 'payments'},
    },
    'sync-vc-rates': {
        'task':     'tasks.virtual_currency_tasks.sync_vc_exchange_rates',
        'schedule': crontab(minute=30, hour='*/1'),
        'options':  {'queue': 'default'},
    },
    'update-community-leaderboard': {
        'task':     'tasks.community_tasks.update_community_leaderboard',
        'schedule': crontab(minute=0, hour='*/1'),
        'options':  {'queue': 'default'},
    },
    'sync-tracking-platforms': {
        'task':     'tasks.macro_tracking_tasks.sync_tracking_platforms',
        'schedule': crontab(minute='*/30'),
        'options':  {'queue': 'default'},
    },
    'advertiser-billing': {
        'task':     'tasks.advertiser_tasks.process_advertiser_billing',
        'schedule': crontab(minute=0, hour='*/1'),
        'options':  {'queue': 'payments'},
    },

    # ── Daily ──────────────────────────────────────────────────────────────

    'daily-analytics-rollup': {
        'task':     'tasks.analytics_tasks.daily_analytics_rollup',
        'schedule': crontab(minute=5, hour=0),
        'options':  {'queue': 'reports'},
    },
    'calculate-daily-earnings': {
        'task':     'tasks.earning_tasks.calculate_daily_user_earnings',
        'schedule': crontab(minute=10, hour=0),
        'options':  {'queue': 'default'},
    },
    'daily-payout-cycle': {
        'task':     'tasks.daily_payout_tasks.run_daily_payout_cycle',
        'schedule': crontab(minute=0, hour=12),
        'options':  {'queue': 'payments'},
    },
    'reset-daily-caps': {
        'task':     'tasks.tasks_cap.reset_daily_caps',
        'schedule': crontab(minute=1, hour=0),
        'options':  {'queue': 'high'},
    },
    'birthday-bonuses': {
        'task':     'tasks.user_lifecycle_tasks.send_birthday_bonus',
        'schedule': crontab(minute=0, hour=8),
        'options':  {'queue': 'emails'},
    },
    'reengagement-emails': {
        'task':     'tasks.user_lifecycle_tasks.send_reengagement',
        'schedule': crontab(minute=0, hour=10),
        'options':  {'queue': 'emails'},
    },
    'identify-vip-users': {
        'task':     'tasks.user_lifecycle_tasks.identify_vip_users',
        'schedule': crontab(minute=0, hour=3),
        'options':  {'queue': 'default'},
    },
    'backup-database': {
        'task':     'tasks.backup_tasks.backup_database',
        'schedule': crontab(minute=0, hour=1),
        'options':  {'queue': 'low'},
    },
    'churn-prediction': {
        'task':     'tasks.ml_tasks.run_churn_prediction',
        'schedule': crontab(minute=0, hour=4),
        'options':  {'queue': 'ml'},
    },
    'user-segments': {
        'task':     'tasks.ml_tasks.compute_user_segments',
        'schedule': crontab(minute=0, hour=3),
        'options':  {'queue': 'ml'},
    },
    'check-data-retention': {
        'task':     'tasks.compliance_tasks.check_data_retention_policies',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),
        'options':  {'queue': 'low'},
    },

    # ── Weekly ─────────────────────────────────────────────────────────────

    'retrain-fraud-model': {
        'task':     'tasks.ml_tasks.retrain_fraud_model',
        'schedule': crontab(minute=0, hour=3, day_of_week=0),
        'options':  {'queue': 'ml'},
    },
    'rebuild-search-index': {
        'task':     'tasks.search_tasks.rebuild_search_index',
        'schedule': crontab(minute=0, hour=5, day_of_week=1),
        'options':  {'queue': 'low'},
    },
    'cleanup-old-clicks': {
        'task':     'tasks.click_tracking_tasks.cleanup_old_clicks',
        'schedule': crontab(minute=0, hour=5, day_of_week=0),
        'options':  {'queue': 'low'},
    },
    'community-digest': {
        'task':     'tasks.community_tasks.send_community_digest',
        'schedule': crontab(minute=0, hour=9, day_of_week=1),
        'options':  {'queue': 'emails'},
    },

    # ── Monthly ────────────────────────────────────────────────────────────

    'publisher-tier-calc': {
        'task':     'tasks.publisher_tasks.calculate_publisher_tiers',
        'schedule': crontab(minute=0, hour=2, day_of_month=1),
        'options':  {'queue': 'default'},
    },
    'reset-monthly-points': {
        'task':     'tasks.community_tasks.reset_monthly_points',
        'schedule': crontab(minute=0, hour=0, day_of_month=1),
        'options':  {'queue': 'default'},
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def configure_celery(app) -> None:
    """
    Apply all task system settings to a Celery app instance.
    Call this in celery.py after creating the Celery app.
    """
    app.config_from_object('django.conf:settings', namespace='CELERY')
    app.conf.update(**CELERY_SETTINGS)
    app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
    app.autodiscover_tasks()


__all__ = [
    'CELERY_QUEUES', 'CELERY_TASK_ROUTES', 'CELERY_SETTINGS',
    'CELERY_BEAT_SCHEDULE', 'configure_celery',
]
