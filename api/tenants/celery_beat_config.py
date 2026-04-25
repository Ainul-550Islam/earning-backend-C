"""
Tenant Celery Beat Configuration - Scheduled Tasks Management

This module contains comprehensive Celery Beat configuration for tenant-related
scheduled tasks including billing, maintenance, reporting, and cleanup operations.
"""

from celery.schedules import crontab
from celery import Celery
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Celery Beat Schedule Configuration
CELERY_BEAT_SCHEDULE = {
    # Daily Tasks
    'tenants.daily_maintenance': {
        'task': 'tenants.tasks.daily_maintenance',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
        'options': {
            'queue': 'tenants_maintenance',
            'priority': 5,
        }
    },
    
    # Billing Tasks
    'tenants.check_trial_expirations': {
        'task': 'tenants.tasks.check_trial_expirations',
        'schedule': crontab(hour=1, minute=0),  # 1:00 AM daily
        'options': {
            'queue': 'tenants_billing',
            'priority': 8,
        }
    },
    
    'tenants.process_subscriptions': {
        'task': 'tenants.tasks.process_subscriptions',
        'schedule': crontab(hour=3, minute=30),  # 3:30 AM daily
        'options': {
            'queue': 'tenants_billing',
            'priority': 8,
        }
    },
    
    'tenants.generate_invoices': {
        'task': 'tenants.tasks.generate_invoices',
        'schedule': crontab(hour=4, minute=0),  # 4:00 AM daily
        'options': {
            'queue': 'tenants_billing',
            'priority': 7,
        }
    },
    
    'tenants.check_overdue_invoices': {
        'task': 'tenants.tasks.check_overdue_invoices',
        'schedule': crontab(hour=9, minute=0),  # 9:00 AM daily
        'options': {
            'queue': 'tenants_billing',
            'priority': 6,
        }
    },
    
    # Weekly Tasks
    'tenants.weekly_reports': {
        'task': 'tenants.tasks.generate_weekly_reports',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday 8:00 AM
        'options': {
            'queue': 'tenants_reports',
            'priority': 4,
        }
    },
    
    'tenants.cleanup_old_audit_logs': {
        'task': 'tenants.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=5, minute=0, day_of_week=0),  # Sunday 5:00 AM
        'options': {
            'queue': 'tenants_maintenance',
            'priority': 3,
        }
    },
    
    # Monthly Tasks
    'tenants.monthly_billing_reports': {
        'task': 'tenants.tasks.generate_monthly_billing_reports',
        'schedule': crontab(hour=6, minute=0, day_of_month=1),  # 1st of month 6:00 AM
        'options': {
            'queue': 'tenants_reports',
            'priority': 5,
        }
    },
    
    'tenants.archive_old_data': {
        'task': 'tenants.tasks.archive_old_data',
        'schedule': crontab(hour=7, minute=0, day_of_month=1),  # 1st of month 7:00 AM
        'options': {
            'queue': 'tenants_maintenance',
            'priority': 2,
        }
    },
    
    # Hourly Tasks
    'tenants.update_usage_stats': {
        'task': 'tenants.tasks.update_usage_stats',
        'schedule': crontab(minute=30),  # Every hour at 30 minutes
        'options': {
            'queue': 'tenants_stats',
            'priority': 3,
        }
    },
    
    'tenants.check_system_health': {
        'task': 'tenants.tasks.check_system_health',
        'schedule': crontab(minute=0),  # Every hour at 0 minutes
        'options': {
            'queue': 'tenants_monitoring',
            'priority': 6,
        }
    },
    
    # Security Tasks
    'tenants.security_audit': {
        'task': 'tenants.tasks.perform_security_audit',
        'schedule': crontab(hour=0, minute=0, day_of_week=6),  # Saturday midnight
        'options': {
            'queue': 'tenants_security',
            'priority': 7,
        }
    },
    
    'tenants.cleanup_failed_logins': {
        'task': 'tenants.tasks.cleanup_failed_logins',
        'schedule': crontab(hour=1, minute=30),  # 1:30 AM daily
        'options': {
            'queue': 'tenants_security',
            'priority': 3,
        }
    },
    
    # Notification Tasks
    'tenants.send_trial_expiry_reminders': {
        'task': 'tenants.tasks.send_trial_expiry_reminders',
        'schedule': crontab(hour=10, minute=0),  # 10:00 AM daily
        'options': {
            'queue': 'tenants_notifications',
            'priority': 6,
        }
    },
    
    'tenants.send_payment_reminders': {
        'task': 'tenants.tasks.send_payment_reminders',
        'schedule': crontab(hour=11, minute=0),  # 11:00 AM daily
        'options': {
            'queue': 'tenants_notifications',
            'priority': 5,
        }
    },
    
    # Cache Management
    'tenants.warm_cache': {
        'task': 'tenants.tasks.warm_cache',
        'schedule': crontab(minute=15),  # Every hour at 15 minutes
        'options': {
            'queue': 'tenants_cache',
            'priority': 4,
        }
    },
    
    'tenants.cleanup_cache': {
        'task': 'tenants.tasks.cleanup_cache',
        'schedule': crontab(hour=3, minute=45),  # 3:45 AM daily
        'options': {
            'queue': 'tenants_cache',
            'priority': 2,
        }
    },
    
    # Data Sync Tasks
    'tenants.sync_external_data': {
        'task': 'tenants.tasks.sync_external_data',
        'schedule': crontab(minute=45),  # Every hour at 45 minutes
        'options': {
            'queue': 'tenants_sync',
            'priority': 4,
        }
    },
    
    # Backup Tasks
    'tenants.backup_tenant_data': {
        'task': 'tenants.tasks.backup_tenant_data',
        'schedule': crontab(hour=2, minute=30),  # 2:30 AM daily
        'options': {
            'queue': 'tenants_backup',
            'priority': 5,
        }
    },
    
    # Performance Monitoring
    'tenants.collect_performance_metrics': {
        'task': 'tenants.tasks.collect_performance_metrics',
        'schedule': crontab(minute=0),  # Every hour
        'options': {
            'queue': 'tenants_monitoring',
            'priority': 3,
        }
    },
}

# Task Queue Configuration
CELERY_TASK_ROUTES = {
    'tenants.tasks.*': {'queue': 'tenants'},
    
    # Specific task routing
    'tenants.tasks.daily_maintenance': {'queue': 'tenants_maintenance'},
    'tenants.tasks.check_trial_expirations': {'queue': 'tenants_billing'},
    'tenants.tasks.process_subscriptions': {'queue': 'tenants_billing'},
    'tenants.tasks.generate_invoices': {'queue': 'tenants_billing'},
    'tenants.tasks.check_overdue_invoices': {'queue': 'tenants_billing'},
    'tenants.tasks.generate_weekly_reports': {'queue': 'tenants_reports'},
    'tenants.tasks.generate_monthly_billing_reports': {'queue': 'tenants_reports'},
    'tenants.tasks.cleanup_old_audit_logs': {'queue': 'tenants_maintenance'},
    'tenants.tasks.archive_old_data': {'queue': 'tenants_maintenance'},
    'tenants.tasks.update_usage_stats': {'queue': 'tenants_stats'},
    'tenants.tasks.check_system_health': {'queue': 'tenants_monitoring'},
    'tenants.tasks.perform_security_audit': {'queue': 'tenants_security'},
    'tenants.tasks.cleanup_failed_logins': {'queue': 'tenants_security'},
    'tenants.tasks.send_trial_expiry_reminders': {'queue': 'tenants_notifications'},
    'tenants.tasks.send_payment_reminders': {'queue': 'tenants_notifications'},
    'tenants.tasks.warm_cache': {'queue': 'tenants_cache'},
    'tenants.tasks.cleanup_cache': {'queue': 'tenants_cache'},
    'tenants.tasks.sync_external_data': {'queue': 'tenants_sync'},
    'tenants.tasks.backup_tenant_data': {'queue': 'tenants_backup'},
    'tenants.tasks.collect_performance_metrics': {'queue': 'tenants_monitoring'},
}

# Task Priority Configuration
CELERY_TASK_PRIORITY_ROUTING = {
    'tenants.tasks.check_trial_expirations': 8,
    'tenants.tasks.process_subscriptions': 8,
    'tenants.tasks.perform_security_audit': 7,
    'tenants.tasks.generate_invoices': 7,
    'tenants.tasks.check_system_health': 6,
    'tenants.tasks.send_trial_expiry_reminders': 6,
    'tenants.tasks.backup_tenant_data': 5,
    'tenants.tasks.generate_weekly_reports': 4,
    'tenants.tasks.update_usage_stats': 3,
    'tenants.tasks.cleanup_old_audit_logs': 2,
    'tenants.tasks.archive_old_data': 2,
}

# Task Time Limits
CELERY_TASK_TIME_LIMITS = {
    'tenants.tasks.daily_maintenance': 1800,  # 30 minutes
    'tenants.tasks.check_trial_expirations': 600,  # 10 minutes
    'tenants.tasks.process_subscriptions': 1800,  # 30 minutes
    'tenants.tasks.generate_invoices': 1200,  # 20 minutes
    'tenants.tasks.check_overdue_invoices': 900,  # 15 minutes
    'tenants.tasks.generate_weekly_reports': 2400,  # 40 minutes
    'tenants.tasks.generate_monthly_billing_reports': 3600,  # 60 minutes
    'tenants.tasks.cleanup_old_audit_logs': 1800,  # 30 minutes
    'tenants.tasks.archive_old_data': 3600,  # 60 minutes
    'tenants.tasks.update_usage_stats': 600,  # 10 minutes
    'tenants.tasks.check_system_health': 300,  # 5 minutes
    'tenants.tasks.perform_security_audit': 1800,  # 30 minutes
    'tenants.tasks.cleanup_failed_logins': 300,  # 5 minutes
    'tenants.tasks.send_trial_expiry_reminders': 900,  # 15 minutes
    'tenants.tasks.send_payment_reminders': 900,  # 15 minutes
    'tenants.tasks.warm_cache': 600,  # 10 minutes
    'tenants.tasks.cleanup_cache': 300,  # 5 minutes
    'tenants.tasks.sync_external_data': 1200,  # 20 minutes
    'tenants.tasks.backup_tenant_data': 3600,  # 60 minutes
    'tenants.tasks.collect_performance_metrics': 300,  # 5 minutes
}

# Task Soft Time Limits
CELERY_TASK_SOFT_TIME_LIMITS = {
    'tenants.tasks.daily_maintenance': 1500,  # 25 minutes
    'tenants.tasks.check_trial_expirations': 500,  # 8 minutes
    'tenants.tasks.process_subscriptions': 1500,  # 25 minutes
    'tenants.tasks.generate_invoices': 1000,  # 16 minutes
    'tenants.tasks.check_overdue_invoices': 750,  # 12 minutes
    'tenants.tasks.generate_weekly_reports': 2100,  # 35 minutes
    'tenants.tasks.generate_monthly_billing_reports': 3300,  # 55 minutes
    'tenants.tasks.cleanup_old_audit_logs': 1500,  # 25 minutes
    'tenants.tasks.archive_old_data': 3300,  # 55 minutes
    'tenants.tasks.update_usage_stats': 500,  # 8 minutes
    'tenants.tasks.check_system_health': 250,  # 4 minutes
    'tenants.tasks.perform_security_audit': 1500,  # 25 minutes
    'tenants.tasks.cleanup_failed_logins': 250,  # 4 minutes
    'tenants.tasks.send_trial_expiry_reminders': 750,  # 12 minutes
    'tenants.tasks.send_payment_reminders': 750,  # 12 minutes
    'tenants.tasks.warm_cache': 500,  # 8 minutes
    'tenants.tasks.cleanup_cache': 250,  # 4 minutes
    'tenants.tasks.sync_external_data': 1000,  # 16 minutes
    'tenants.tasks.backup_tenant_data': 3300,  # 55 minutes
    'tenants.tasks.collect_performance_metrics': 250,  # 4 minutes
}

# Task Default Configuration
CELERY_TASK_DEFAULT_QUEUE = 'tenants'
CELERY_TASK_DEFAULT_PRIORITY = 5
CELERY_TASK_DEFAULT_RATE_LIMIT = '100/m'

# Beat Configuration
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_TIMEZONE = getattr(settings, 'TIME_ZONE', 'UTC')

# Result Backend Configuration
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXPIRES = 86400  # 24 hours

# Worker Configuration
CELERY_WORKER_CONCURRENCY = getattr(settings, 'CELERY_WORKER_CONCURRENCY', 4)
CELERY_WORKER_PREFETCH_MULTIPLIER = getattr(settings, 'CELERY_WORKER_PREFETCH_MULTIPLIER', 1)
CELERY_WORKER_MAX_TASKS_PER_CHILD = getattr(settings, 'CELERY_WORKER_MAX_TASKS_PER_CHILD', 1000)

# Monitoring Configuration
CELERY_SEND_TASK_SENT_EVENT = True
CELERY_SEND_TASK_FAILURE_EVENT = True
CELERY_SEND_TASK_SUCCESS_EVENT = True

# Error Handling
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Task Serialization
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']

# Security Configuration
CELERY_BROKER_URL = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,
    'retry_policy': {
        'timeout': 5.0
    }
}

# Queue Configuration
CELERY_QUEUE_DEFAULTS = {
    'tenants': {
        'durable': True,
        'routing_key': 'tenants',
    },
    'tenants_maintenance': {
        'durable': True,
        'routing_key': 'tenants.maintenance',
    },
    'tenants_billing': {
        'durable': True,
        'routing_key': 'tenants.billing',
    },
    'tenants_reports': {
        'durable': True,
        'routing_key': 'tenants.reports',
    },
    'tenants_stats': {
        'durable': True,
        'routing_key': 'tenants.stats',
    },
    'tenants_monitoring': {
        'durable': True,
        'routing_key': 'tenants.monitoring',
    },
    'tenants_security': {
        'durable': True,
        'routing_key': 'tenants.security',
    },
    'tenants_notifications': {
        'durable': True,
        'routing_key': 'tenants.notifications',
    },
    'tenants_cache': {
        'durable': True,
        'routing_key': 'tenants.cache',
    },
    'tenants_sync': {
        'durable': True,
        'routing_key': 'tenants.sync',
    },
    'tenants_backup': {
        'durable': True,
        'routing_key': 'tenants.backup',
    },
}

# Exchange Configuration
CELERY_BROKER_TRANSPORT = 'redis'

# Task Annotations
CELERY_TASK_ANNOTATIONS = {
    'tenants.tasks.*': {
        'rate_limit': '100/m',
        'time_limit': 1800,
        'soft_time_limit': 1500,
        'priority': 5,
    },
    'tenants.tasks.check_trial_expirations': {
        'rate_limit': '10/m',
        'priority': 8,
    },
    'tenants.tasks.process_subscriptions': {
        'rate_limit': '5/m',
        'priority': 8,
    },
    'tenants.tasks.perform_security_audit': {
        'rate_limit': '1/m',
        'priority': 7,
    },
}

# Task Track Started
CELERY_TASK_TRACK_STARTED = True

# Task Compression
CELERY_TASK_COMPRESSION = 'gzip'

# Task Track Result
CELERY_TASK_TRACK_RESULT = True

# Task Ignore Result
CELERY_TASK_IGNORE_RESULT = False

# Task Eager Propagates
CELERY_TASK_EAGER_PROPAGATES = True

# Task Protocol
CELERY_TASK_PROTOCOL = 1

# Task Publisher Confirms
CELERY_TASK_PUBLISHER_CONFIRMS = True

# Task Publisher Retry
CELERY_TASK_PUBLISHER_RETRY = True

# Task Publisher Retry Policy
CELERY_TASK_PUBLISHER_RETRY_POLICY = {
    'timeout': 5.0
}

# Task Default Routing Key
CELERY_TASK_DEFAULT_ROUTING_KEY = 'tenants'

# Task Queue Hierarchy
CELERY_QUEUE_HIERARCHY = {
    'tenants': ['tenants_maintenance', 'tenants_billing', 'tenants_reports', 'tenants_stats'],
    'tenants_monitoring': ['tenants_security', 'tenants_notifications'],
    'tenants_system': ['tenants_cache', 'tenants_sync', 'tenants_backup'],
}

# Task Auto Delete
CELERY_TASK_AUTO_DELETE = False

# Task Store Errors Even If Ignored
CELERY_TASK_STORE_ERRORS_EVEN_IF_IGNORED = True

# Task Store Result Even If Ignored
CELERY_TASK_STORE_RESULT_EVEN_IF_IGNORED = True

# Task Store Result Immutable
CELERY_TASK_STORE_RESULT_IMMUTABLE = False

# Task Result Expiration
CELERY_TASK_RESULT_EXPIRES = 86400

# Task Result Backend Max Retries
CELERY_RESULT_BACKEND_MAX_RETRIES = 10

# Task Result Backend Base Options
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'master_name': 'mymaster',
    'retry_policy': {
        'timeout': 5.0
    }
}

# Task Result Backend Transport Options
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'master_name': 'mymaster',
    'retry_policy': {
        'timeout': 5.0
    }
}

# Task Result Backend Pool Limit
CELERY_RESULT_BACKEND_POOL_LIMIT = 10

# Task Result Backend Pool Reset
CELERY_RESULT_BACKEND_POOL_RESET = True

# Task Result Backend SSL
CELERY_RESULT_BACKEND_SSL = None

# Task Result Backend Use_ssl
CELERY_RESULT_BACKEND_USE_SSL = None

# Task Result Backend Credentials
CELERY_RESULT_BACKEND_PASSWORD = None

# Task Result Backend Username
CELERY_RESULT_BACKEND_USERNAME = None

# Task Result Backend Database
CELERY_RESULT_BACKEND_DATABASE = 0

# Task Result Backend Path
CELERY_RESULT_BACKEND_PATH = '/'

# Task Result Backend Host
CELERY_RESULT_BACKEND_HOST = 'localhost'

# Task Result Backend Port
CELERY_RESULT_BACKEND_PORT = 6379

# Task Result Backend Vhost
CELERY_RESULT_BACKEND_VHOST = '/'
