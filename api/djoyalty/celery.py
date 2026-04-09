# api/djoyalty/celery.py
"""
Djoyalty Celery configuration।
project এর celery.py তে import করুন:
    from api.djoyalty.celery import djoyalty_celery_app
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

djoyalty_celery_app = Celery('djoyalty')
djoyalty_celery_app.config_from_object('django.conf:settings', namespace='CELERY')
djoyalty_celery_app.autodiscover_tasks(['api.djoyalty.tasks'])

# ==================== BEAT SCHEDULE ====================
djoyalty_celery_app.conf.beat_schedule = {
    # Points expiry — daily at 01:00 AM
    'djoyalty-expire-points-daily': {
        'task': 'djoyalty.expire_points',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Expiry warnings — daily at 08:00 AM
    'djoyalty-send-expiry-warnings': {
        'task': 'djoyalty.send_expiry_warnings',
        'schedule': crontab(hour=8, minute=0),
        'options': {'queue': 'djoyalty_notifications'},
    },
    # Tier evaluation — monthly on 1st at 02:00 AM
    'djoyalty-evaluate-all-tiers-monthly': {
        'task': 'djoyalty.evaluate_all_tiers',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Streak reset — daily at 00:05 AM
    'djoyalty-check-broken-streaks': {
        'task': 'djoyalty.check_broken_streaks',
        'schedule': crontab(hour=0, minute=5),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Campaign activation — every 15 minutes
    'djoyalty-activate-due-campaigns': {
        'task': 'djoyalty.activate_due_campaigns',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Leaderboard refresh — every hour
    'djoyalty-refresh-leaderboard': {
        'task': 'djoyalty.refresh_leaderboard',
        'schedule': crontab(minute=0),
        'options': {'queue': 'djoyalty_cache'},
    },
    # Daily insight — daily at 00:30 AM
    'djoyalty-generate-daily-insight': {
        'task': 'djoyalty.generate_daily_insight',
        'schedule': crontab(hour=0, minute=30),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Fraud scan — every hour
    'djoyalty-fraud-scan': {
        'task': 'djoyalty.fraud_scan',
        'schedule': crontab(minute=5),
        'options': {'queue': 'djoyalty_fraud'},
    },
    # Auto approve redemptions — every 15 min
    'djoyalty-auto-approve-redemptions': {
        'task': 'djoyalty.auto_approve_redemptions',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'djoyalty_redemption'},
    },
    # Expire vouchers — daily at 00:30 AM
    'djoyalty-expire-vouchers': {
        'task': 'djoyalty.expire_vouchers',
        'schedule': crontab(hour=0, minute=30),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Expire gift cards — daily at 00:35 AM
    'djoyalty-expire-gift-cards': {
        'task': 'djoyalty.expire_gift_cards',
        'schedule': crontab(hour=0, minute=35),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Partner sync — every 60 minutes
    'djoyalty-sync-partners': {
        'task': 'djoyalty.sync_partners',
        'schedule': crontab(minute=0),
        'options': {'queue': 'djoyalty_partner'},
    },
    # Subscription renewals — daily at 03:00 AM
    'djoyalty-process-subscription-renewals': {
        'task': 'djoyalty.process_subscription_renewals',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Deactivate expired earn rules — daily at 01:30 AM
    'djoyalty-deactivate-expired-earn-rules': {
        'task': 'djoyalty.deactivate_expired_earn_rules',
        'schedule': crontab(hour=1, minute=30),
        'options': {'queue': 'djoyalty_cron'},
    },
    # Send pending notifications — every 30 minutes
    'djoyalty-send-pending-notifications': {
        'task': 'djoyalty.send_pending_notifications',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'djoyalty_notifications'},
    },
    # Rapid transaction scan — every 5 minutes
    'djoyalty-scan-rapid-transactions': {
        'task': 'djoyalty.scan_rapid_transactions',
        'schedule': crontab(minute='*/5'),
        'options': {'queue': 'djoyalty_fraud'},
    },
    # Expire old pending redemptions — daily at 04:00 AM
    'djoyalty-expire-old-pending-redemptions': {
        'task': 'djoyalty.expire_old_pending_redemptions',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'djoyalty_redemption'},
    },
}

djoyalty_celery_app.conf.task_routes = {
    'djoyalty.*': {'queue': 'djoyalty'},
    'djoyalty.fraud_*': {'queue': 'djoyalty_fraud'},
    'djoyalty.send_*': {'queue': 'djoyalty_notifications'},
    'djoyalty.sync_*': {'queue': 'djoyalty_partner'},
    'djoyalty.*redemption*': {'queue': 'djoyalty_redemption'},
}
