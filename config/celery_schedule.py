"""
Celery configuration for earning backend
"""

from celery.schedules import crontab
from datetime import timedelta

# Task schedules (for development - in production use django_celery_beat)
CELERY_BEAT_SCHEDULE = {
    # Daily earnings calculation - midnight
    'calculate-daily-earnings': {
        'task': 'api.tasks.earning_tasks.calculate_daily_user_earnings',
        'schedule': crontab(hour=0, minute=0),
        'args': (),
    },
    
    # Withdrawal processing - every hour
    'process-withdrawals': {
        'task': 'api.tasks.payment_tasks.process_withdrawal_requests',
        'schedule': timedelta(hours=1),
        'args': (20,),
    },
    
    # Blacklist cleanup - every 6 hours
    'cleanup-blacklist': {
        'task': 'api.tasks.ad_networks_tasks.cleanup_expired_blacklist_task',
        'schedule': timedelta(hours=6),
        'args': (100,),
    },
    
    # Fraud detection - every 15 minutes
    'fraud-detection': {
        'task': 'api.tasks.fraud_detection_tasks.run_fraud_detection_scan',
        'schedule': timedelta(minutes=15),
        'args': (),
    },
    
    # Database backup - daily at 2 AM
    'backup-database': {
        'task': 'api.tasks.backup_tasks.backup_database',
        'schedule': crontab(hour=2, minute=0),
        'args': (),
    },
}

# Task routing
CELERY_TASK_ROUTES = {
    'api.tasks.earning_tasks.*': {'queue': 'earnings'},
    'api.tasks.payment_tasks.*': {'queue': 'payments'},
    'api.tasks.ad_networks_tasks.*': {'queue': 'ad_networks'},
    'api.tasks.fraud_detection_tasks.*': {'queue': 'fraud'},
    'api.tasks.backup_tasks.*': {'queue': 'backup'},
}

# Task settings
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
