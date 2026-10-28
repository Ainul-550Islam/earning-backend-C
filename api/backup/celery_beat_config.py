"""
Backup Module Celery Beat Configuration
Scheduled tasks configuration for backup operations
"""

from celery.schedules import crontab
from celery import Celery
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


# Celery Beat Schedule Configuration
CELERY_BEAT_SCHEDULE = {
    # Daily backup verification
    'verify-daily-backups': {
        'task': 'api.backup.tasks.verify_daily_backups',
        'schedule': crontab(hour=2, minute=0),  # Run daily at 2:00 AM
        'options': {
            'queue': 'backup',
            'priority': 5,
        }
    },
    
    # Weekly backup cleanup
    'cleanup-weekly-backups': {
        'task': 'api.backup.tasks.cleanup_old_backups',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Run weekly on Sunday at 3:00 AM
        'options': {
            'queue': 'backup',
            'priority': 3,
        }
    },
    
    # Monthly backup health check
    'health-check-backups': {
        'task': 'api.backup.tasks.backup_health_check',
        'schedule': crontab(hour=4, minute=0, day_of_month=1),  # Run monthly on 1st at 4:00 AM
        'options': {
            'queue': 'backup',
            'priority': 4,
        }
    },
    
    # Backup storage monitoring
    'monitor-backup-storage': {
        'task': 'api.backup.tasks.monitor_backup_storage',
        'schedule': crontab(hour='*/6', minute=0),  # Run every 6 hours
        'options': {
            'queue': 'backup',
            'priority': 2,
        }
    },
    
    # Backup retention policy enforcement
    'enforce-retention-policies': {
        'task': 'api.backup.tasks.enforce_retention_policies',
        'schedule': crontab(hour=5, minute=0),  # Run daily at 5:00 AM
        'options': {
            'queue': 'backup',
            'priority': 3,
        }
    },
    
    # Backup notification processing
    'process-backup-notifications': {
        'task': 'api.backup.tasks.process_backup_notifications',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
        'options': {
            'queue': 'notifications',
            'priority': 6,
        }
    },
    
    # Backup analytics aggregation
    'aggregate-backup-analytics': {
        'task': 'api.backup.tasks.aggregate_backup_analytics',
        'schedule': crontab(hour=1, minute=0),  # Run daily at 1:00 AM
        'options': {
            'queue': 'analytics',
            'priority': 2,
        }
    },
    
    # Backup schedule execution
    'execute-backup-schedules': {
        'task': 'api.backup.tasks.execute_backup_schedules',
        'schedule': crontab(minute='*/5'),  # Run every 5 minutes
        'options': {
            'queue': 'backup',
            'priority': 7,
        }
    },
    
    # Backup log cleanup
    'cleanup-backup-logs': {
        'task': 'api.backup.tasks.cleanup_backup_logs',
        'schedule': crontab(hour=6, minute=0, day_of_week=0),  # Run weekly on Sunday at 6:00 AM
        'options': {
            'queue': 'maintenance',
            'priority': 1,
        }
    },
    
    # Backup encryption key rotation
    'rotate-backup-encryption-keys': {
        'task': 'api.backup.tasks.rotate_backup_encryption_keys',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),  # Run monthly on 1st at 2:00 AM
        'options': {
            'queue': 'security',
            'priority': 4,
        }
    },
}


class BackupBeatScheduler:
    """
    Custom scheduler for backup tasks with dynamic scheduling
    """
    
    def __init__(self, app):
        self.app = app
        self._schedule = {}
        self._last_update = None
    
    def setup_schedule(self):
        """
        Setup the schedule with dynamic tasks
        """
        self._schedule = CELERY_BEAT_SCHEDULE.copy()
        
        # Add dynamic schedules from database
        self._add_dynamic_schedules()
        
        # Add conditional schedules based on settings
        self._add_conditional_schedules()
        
        logger.info(f"Backup scheduler initialized with {len(self._schedule)} tasks")
    
    def _add_dynamic_schedules(self):
        """
        Add schedules from BackupSchedule models
        """
        try:
            from .models import BackupSchedule
            
            # Get all active schedules
            active_schedules = BackupSchedule.objects.filter(is_active=True, is_paused=False)
            
            for schedule in active_schedules:
                try:
                    # Create dynamic task name
                    task_name = f"execute-scheduled-backup-{schedule.id}"
                    
                    # Parse cron expression
                    cron_expr = self._parse_cron_expression(schedule.frequency)
                    
                    # Add to schedule
                    self._schedule[task_name] = {
                        'task': 'api.backup.tasks.execute_scheduled_backup',
                        'schedule': cron_expr,
                        'args': (schedule.id,),
                        'options': {
                            'queue': 'backup',
                            'priority': 6,
                        }
                    }
                    
                    logger.debug(f"Added dynamic schedule: {task_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to add schedule {schedule.id}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to load dynamic schedules: {e}")
    
    def _add_conditional_schedules(self):
        """
        Add schedules based on configuration
        """
        # Add test restore schedule if enabled
        if getattr(settings, 'BACKUP_ENABLE_TEST_RESTORES', False):
            test_restore_frequency = getattr(settings, 'BACKUP_TEST_RESTORE_FREQUENCY', 'weekly')
            
            if test_restore_frequency == 'daily':
                cron_expr = crontab(hour=3, minute=30)
            elif test_restore_frequency == 'weekly':
                cron_expr = crontab(hour=3, minute=30, day_of_week=6)  # Saturday
            elif test_restore_frequency == 'monthly':
                cron_expr = crontab(hour=3, minute=30, day_of_month=15)
            else:
                cron_expr = crontab(hour=3, minute=30, day_of_week=6)  # Default to weekly
            
            self._schedule['test-restore-backup'] = {
                'task': 'api.backup.tasks.test_restore_latest_backup',
                'schedule': cron_expr,
                'options': {
                    'queue': 'backup',
                    'priority': 4,
                }
            }
        
        # Add compression optimization if enabled
        if getattr(settings, 'BACKUP_ENABLE_COMPRESSION_OPTIMIZATION', False):
            self._schedule['optimize-backup-compression'] = {
                'task': 'api.backup.tasks.optimize_backup_compression',
                'schedule': crontab(hour=2, minute=30, day_of_week=0),  # Weekly on Sunday
                'options': {
                    'queue': 'maintenance',
                    'priority': 2,
                }
            }
        
        # Add storage optimization if enabled
        if getattr(settings, 'BACKUP_ENABLE_STORAGE_OPTIMIZATION', False):
            self._schedule['optimize-backup-storage'] = {
                'task': 'api.backup.tasks.optimize_backup_storage',
                'schedule': crontab(hour=1, minute=0, day_of_week=0),  # Weekly on Sunday
                'options': {
                    'queue': 'maintenance',
                    'priority': 2,
                }
            }
    
    def _parse_cron_expression(self, frequency):
        """
        Parse frequency string to crontab expression
        """
        if frequency == 'hourly':
            return crontab(minute=0)
        elif frequency == 'daily':
            return crontab(hour=2, minute=0)
        elif frequency == 'weekly':
            return crontab(hour=2, minute=0, day_of_week=0)
        elif frequency == 'monthly':
            return crontab(hour=2, minute=0, day_of_month=1)
        elif frequency.startswith('cron:'):
            # Custom cron expression
            cron_parts = frequency[5:].split()
            if len(cron_parts) == 5:
                minute, hour, day, month, day_of_week = cron_parts
                return crontab(
                    minute=minute,
                    hour=hour,
                    day_of_month=day,
                    month_of_year=month,
                    day_of_week=day_of_week
                )
        else:
            # Default to daily
            return crontab(hour=2, minute=0)
        
        # Fallback
        return crontab(hour=2, minute=0)
    
    @property
    def schedule(self):
        """
        Get the current schedule
        """
        # Refresh schedule if needed
        if self._should_refresh_schedule():
            self.setup_schedule()
        
        return self._schedule
    
    def _should_refresh_schedule(self):
        """
        Check if schedule should be refreshed
        """
        # Refresh if never updated
        if self._last_update is None:
            return True
        
        # Refresh every hour
        from datetime import timedelta
        if timezone.now() - self._last_update > timedelta(hours=1):
            return True
        
        return False


class BackupTaskConfig:
    """
    Configuration for backup tasks
    """
    
    # Task priorities
    PRIORITY_CRITICAL = 9
    PRIORITY_HIGH = 7
    PRIORITY_NORMAL = 5
    PRIORITY_LOW = 3
    PRIORITY_BACKGROUND = 1
    
    # Task queues
    QUEUE_BACKUP = 'backup'
    QUEUE_MAINTENANCE = 'maintenance'
    QUEUE_NOTIFICATIONS = 'notifications'
    QUEUE_ANALYTICS = 'analytics'
    QUEUE_SECURITY = 'security'
    
    # Task timeouts (in seconds)
    TIMEOUT_SHORT = 300      # 5 minutes
    TIMEOUT_NORMAL = 1800    # 30 minutes
    TIMEOUT_LONG = 3600      # 1 hour
    TIMEOUT_EXTENDED = 7200  # 2 hours
    
    # Task retry settings
    MAX_RETRIES = 3
    RETRY_DELAY = 60  # seconds
    
    @classmethod
    def get_task_config(cls, task_name):
        """
        Get configuration for a specific task
        """
        configs = {
            'verify_daily_backups': {
                'queue': cls.QUEUE_BACKUP,
                'priority': cls.PRIORITY_NORMAL,
                'timeout': cls.TIMEOUT_NORMAL,
                'max_retries': cls.MAX_RETRIES,
                'retry_delay': cls.RETRY_DELAY,
            },
            'cleanup_old_backups': {
                'queue': cls.QUEUE_MAINTENANCE,
                'priority': cls.PRIORITY_LOW,
                'timeout': cls.TIMEOUT_EXTENDED,
                'max_retries': 2,
                'retry_delay': 300,  # 5 minutes
            },
            'backup_health_check': {
                'queue': cls.QUEUE_BACKUP,
                'priority': cls.PRIORITY_NORMAL,
                'timeout': cls.TIMEOUT_NORMAL,
                'max_retries': cls.MAX_RETRIES,
                'retry_delay': cls.RETRY_DELAY,
            },
            'monitor_backup_storage': {
                'queue': cls.QUEUE_BACKUP,
                'priority': cls.PRIORITY_LOW,
                'timeout': cls.TIMEOUT_SHORT,
                'max_retries': 2,
                'retry_delay': cls.RETRY_DELAY,
            },
            'enforce_retention_policies': {
                'queue': cls.QUEUE_MAINTENANCE,
                'priority': cls.PRIORITY_NORMAL,
                'timeout': cls.TIMEOUT_NORMAL,
                'max_retries': cls.MAX_RETRIES,
                'retry_delay': cls.RETRY_DELAY,
            },
            'process_backup_notifications': {
                'queue': cls.QUEUE_NOTIFICATIONS,
                'priority': cls.PRIORITY_HIGH,
                'timeout': cls.TIMEOUT_SHORT,
                'max_retries': 3,
                'retry_delay': 30,
            },
            'aggregate_backup_analytics': {
                'queue': cls.QUEUE_ANALYTICS,
                'priority': cls.PRIORITY_LOW,
                'timeout': cls.TIMEOUT_NORMAL,
                'max_retries': 2,
                'retry_delay': 300,
            },
            'execute_backup_schedules': {
                'queue': cls.QUEUE_BACKUP,
                'priority': cls.PRIORITY_CRITICAL,
                'timeout': cls.TIMEOUT_SHORT,
                'max_retries': 1,
                'retry_delay': 60,
            },
            'cleanup_backup_logs': {
                'queue': cls.QUEUE_MAINTENANCE,
                'priority': cls.PRIORITY_BACKGROUND,
                'timeout': cls.TIMEOUT_NORMAL,
                'max_retries': 2,
                'retry_delay': 300,
            },
            'rotate_backup_encryption_keys': {
                'queue': cls.QUEUE_SECURITY,
                'priority': cls.PRIORITY_NORMAL,
                'timeout': cls.TIMEOUT_NORMAL,
                'max_retries': 2,
                'retry_delay': 300,
            },
            'execute_scheduled_backup': {
                'queue': cls.QUEUE_BACKUP,
                'priority': cls.PRIORITY_HIGH,
                'timeout': cls.TIMEOUT_EXTENDED,
                'max_retries': 2,
                'retry_delay': 300,
            },
            'test_restore_latest_backup': {
                'queue': cls.QUEUE_BACKUP,
                'priority': cls.PRIORITY_NORMAL,
                'timeout': cls.TIMEOUT_EXTENDED,
                'max_retries': 1,
                'retry_delay': 600,
            },
            'optimize_backup_compression': {
                'queue': cls.QUEUE_MAINTENANCE,
                'priority': cls.PRIORITY_LOW,
                'timeout': cls.TIMEOUT_LONG,
                'max_retries': 1,
                'retry_delay': 600,
            },
            'optimize_backup_storage': {
                'queue': cls.QUEUE_MAINTENANCE,
                'priority': cls.PRIORITY_LOW,
                'timeout': cls.TIMEOUT_LONG,
                'max_retries': 1,
                'retry_delay': 600,
            },
        }
        
        return configs.get(task_name, {
            'queue': cls.QUEUE_BACKUP,
            'priority': cls.PRIORITY_NORMAL,
            'timeout': cls.TIMEOUT_NORMAL,
            'max_retries': cls.MAX_RETRIES,
            'retry_delay': cls.RETRY_DELAY,
        })


def setup_celery_beat(app):
    """
    Setup Celery Beat with backup scheduler
    """
    # Configure beat scheduler
    app.conf.beat_scheduler = 'api.backup.celery_beat_config.BackupBeatScheduler'
    
    # Set timezone
    app.conf.enable_utc = True
    app.conf.timezone = 'UTC'
    
    # Configure beat settings
    app.conf.beat_schedule = CELERY_BEAT_SCHEDULE
    
    # Task routing
    app.conf.task_routes = {
        'api.backup.tasks.*': {'queue': 'backup'},
        'api.backup.tasks.verify_*': {'queue': 'backup'},
        'api.backup.tasks.cleanup_*': {'queue': 'maintenance'},
        'api.backup.tasks.process_*': {'queue': 'notifications'},
        'api.backup.tasks.aggregate_*': {'queue': 'analytics'},
        'api.backup.tasks.rotate_*': {'queue': 'security'},
    }
    
    # Task serialization
    app.conf.task_serializer = 'json'
    app.conf.result_serializer = 'json'
    app.conf.accept_content = ['json']
    app.conf.result_expires = 3600  # 1 hour
    
    # Worker settings
    app.conf.worker_prefetch_multiplier = 1
    app.conf.task_acks_late = True
    app.conf.worker_disable_rate_limits = False
    
    logger.info("Celery Beat configured for backup module")


def get_schedule_info():
    """
    Get information about current schedules
    """
    schedule_info = {
        'static_schedules': len(CELERY_BEAT_SCHEDULE),
        'task_configs': len(BackupTaskConfig.__dict__),
        'queues': [
            BackupTaskConfig.QUEUE_BACKUP,
            BackupTaskConfig.QUEUE_MAINTENANCE,
            BackupTaskConfig.QUEUE_NOTIFICATIONS,
            BackupTaskConfig.QUEUE_ANALYTICS,
            BackupTaskConfig.QUEUE_SECURITY,
        ],
        'priorities': {
            'critical': BackupTaskConfig.PRIORITY_CRITICAL,
            'high': BackupTaskConfig.PRIORITY_HIGH,
            'normal': BackupTaskConfig.PRIORITY_NORMAL,
            'low': BackupTaskConfig.PRIORITY_LOW,
            'background': BackupTaskConfig.PRIORITY_BACKGROUND,
        }
    }
    
    return schedule_info


def validate_schedule_config():
    """
    Validate the schedule configuration
    """
    errors = []
    warnings = []
    
    # Check for duplicate task names
    task_names = set()
    for name, config in CELERY_BEAT_SCHEDULE.items():
        if name in task_names:
            errors.append(f"Duplicate task name: {name}")
        task_names.add(name)
        
        # Validate schedule configuration
        if 'task' not in config:
            errors.append(f"Missing task in schedule: {name}")
        
        if 'schedule' not in config:
            errors.append(f"Missing schedule in: {name}")
    
    # Check queue assignments
    queue_usage = {}
    for name, config in CELERY_BEAT_SCHEDULE.items():
        queue = config.get('options', {}).get('queue', 'default')
        queue_usage[queue] = queue_usage.get(queue, 0) + 1
    
    # Warn about queues with too many tasks
    for queue, count in queue_usage.items():
        if count > 5:
            warnings.append(f"Queue '{queue}' has {count} tasks, consider load balancing")
    
    return {
        'errors': errors,
        'warnings': warnings,
        'total_schedules': len(CELERY_BEAT_SCHEDULE),
        'queue_distribution': queue_usage
    }


# Environment-specific configurations
def get_environment_config():
    """
    Get environment-specific configuration
    """
    env = getattr(settings, 'ENVIRONMENT', 'development')
    
    if env == 'production':
        return {
            'enable_scheduler': True,
            'schedule_interval': 60,  # seconds
            'max_concurrent_tasks': 5,
            'enable_monitoring': True,
        }
    elif env == 'staging':
        return {
            'enable_scheduler': True,
            'schedule_interval': 300,  # 5 minutes
            'max_concurrent_tasks': 3,
            'enable_monitoring': True,
        }
    else:  # development
        return {
            'enable_scheduler': False,
            'schedule_interval': 600,  # 10 minutes
            'max_concurrent_tasks': 1,
            'enable_monitoring': False,
        }


# Export main configuration
__all__ = [
    'CELERY_BEAT_SCHEDULE',
    'BackupBeatScheduler',
    'BackupTaskConfig',
    'setup_celery_beat',
    'get_schedule_info',
    'validate_schedule_config',
    'get_environment_config',
]
