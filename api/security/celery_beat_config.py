"""
Security Celery Beat Configuration
Scheduled tasks for security operations
Author: System Security Team
Version: 1.0.0
"""

from celery.schedules import crontab
from celery import Celery
import os
from datetime import timedelta

# Security Celery Beat Schedule Configuration
SECURITY_BEAT_SCHEDULE = {
    # Daily security tasks
    'security-daily-cleanup': {
        'task': 'api.security.tasks.daily_security_cleanup',
        'schedule': crontab(hour=2, minute=0),  # 2:00 AM daily
        'options': {'queue': 'security'}
    },
    
    'security-daily-report': {
        'task': 'api.security.tasks.generate_daily_security_report',
        'schedule': crontab(hour=6, minute=0),  # 6:00 AM daily
        'options': {'queue': 'security'}
    },
    
    'security-risk-assessment': {
        'task': 'api.security.tasks.perform_risk_assessment',
        'schedule': crontab(hour=1, minute=30),  # 1:30 AM daily
        'options': {'queue': 'security'}
    },
    
    # Hourly security tasks
    'security-hourly-monitoring': {
        'task': 'api.security.tasks.hourly_security_monitoring',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'security'}
    },
    
    'security-rate-limit-cleanup': {
        'task': 'api.security.tasks.cleanup_rate_limits',
        'schedule': crontab(minute=15),  # Every hour at 15 minutes
        'options': {'queue': 'security'}
    },
    
    # Every 15 minutes
    'security-threat-intel-update': {
        'task': 'api.security.tasks.update_threat_intelligence',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'security'}
    },
    
    'security-real-time-monitoring': {
        'task': 'api.security.tasks.real_time_security_monitoring',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {'queue': 'security'}
    },
    
    # Every 5 minutes
    'security-alert-processing': {
        'task': 'api.security.tasks.process_security_alerts',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'security'}
    },
    
    # Weekly tasks
    'security-weekly-report': {
        'task': 'api.security.tasks.generate_weekly_security_report',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday 8:00 AM
        'options': {'queue': 'security'}
    },
    
    'security-password-policy-audit': {
        'task': 'api.security.tasks.audit_password_policies',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 3:00 AM
        'options': {'queue': 'security'}
    },
    
    'security-vulnerability-scan': {
        'task': 'api.security.tasks.perform_vulnerability_scan',
        'schedule': crontab(hour=4, minute=0, day_of_week=6),  # Saturday 4:00 AM
        'options': {'queue': 'security'}
    },
    
    # Monthly tasks
    'security-monthly-report': {
        'task': 'api.security.tasks.generate_monthly_security_report',
        'schedule': crontab(hour=9, minute=0, day_of_month=1),  # 1st of month 9:00 AM
        'options': {'queue': 'security'}
    },
    
    'security-log-rotation': {
        'task': 'api.security.tasks.rotate_security_logs',
        'schedule': crontab(hour=0, minute=30, day_of_month=1),  # 1st of month 12:30 AM
        'options': {'queue': 'security'}
    },
    
    'security-compliance-check': {
        'task': 'api.security.tasks.perform_compliance_check',
        'schedule': crontab(hour=10, minute=0, day_of_month=15),  # 15th of month 10:00 AM
        'options': {'queue': 'security'}
    },
    
    # Special security tasks
    'security-ip-reputation-update': {
        'task': 'api.security.tasks.update_ip_reputation',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'options': {'queue': 'security'}
    },
    
    'security-device-trust-cleanup': {
        'task': 'api.security.tasks.cleanup_device_trust',
        'schedule': crontab(hour=5, minute=0),  # 5:00 AM daily
        'options': {'queue': 'security'}
    },
    
    'security-session-cleanup': {
        'task': 'api.security.tasks.cleanup_expired_sessions',
        'schedule': crontab(minute=30),  # Every hour at 30 minutes
        'options': {'queue': 'security'}
    },
    
    'security-threat-intel-cleanup': {
        'task': 'api.security.tasks.cleanup_expired_threat_intel',
        'schedule': crontab(hour=0, minute=45),  # 12:45 AM daily
        'options': {'queue': 'security'}
    },
    
    'security-blacklist-cleanup': {
        'task': 'api.security.tasks.cleanup_expired_blacklists',
        'schedule': crontab(hour=1, minute=0),  # 1:00 AM daily
        'options': {'queue': 'security'}
    },
    
    # Backup and maintenance
    'security-database-backup': {
        'task': 'api.security.tasks.backup_security_data',
        'schedule': crontab(hour=3, minute=30),  # 3:30 AM daily
        'options': {'queue': 'security'}
    },
    
    'security-index-optimization': {
        'task': 'api.security.tasks.optimize_security_indexes',
        'schedule': crontab(hour=2, minute=30, day_of_week=0),  # Sunday 2:30 AM
        'options': {'queue': 'security'}
    },
    
    # Monitoring and alerts
    'security-health-check': {
        'task': 'api.security.tasks.perform_security_health_check',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'queue': 'security'}
    },
    
    'security-performance-monitoring': {
        'task': 'api.security.tasks.monitor_security_performance',
        'schedule': crontab(minute='*/20'),  # Every 20 minutes
        'options': {'queue': 'security'}
    },
    
    'security-anomaly-detection': {
        'task': 'api.security.tasks.detect_security_anomalies',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'security'}
    },
    
    # Data retention and cleanup
    'security-log-retention-cleanup': {
        'task': 'api.security.tasks.cleanup_old_security_logs',
        'schedule': crontab(hour=4, minute=30),  # 4:30 AM daily
        'options': {'queue': 'security'}
    },
    
    'security-audit-log-cleanup': {
        'task': 'api.security.tasks.cleanup_old_audit_logs',
        'schedule': crontab(hour=5, minute=30, day_of_week=0),  # Sunday 5:30 AM
        'options': {'queue': 'security'}
    },
    
    'security-temp-data-cleanup': {
        'task': 'api.security.tasks.cleanup_temporary_security_data',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
        'options': {'queue': 'security'}
    },
}

# Environment-specific schedules
DEVELOPMENT_SCHEDULE = {
    # More frequent schedules for development
    'security-dev-monitoring': {
        'task': 'api.security.tasks.development_monitoring',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'development'}
    },
}

PRODUCTION_SCHEDULE = {
    # Additional production-specific tasks
    'security-production-backup': {
        'task': 'api.security.tasks.production_backup',
        'schedule': crontab(hour=1, minute=0),  # 1:00 AM daily
        'options': {'queue': 'production'}
    },
    
    'security-production-monitoring': {
        'task': 'api.security.tasks.production_monitoring',
        'schedule': crontab(minute='*/2'),  # Every 2 minutes
        'options': {'queue': 'production'}
    },
}

STAGING_SCHEDULE = {
    # Staging-specific tasks
    'security-staging-cleanup': {
        'task': 'api.security.tasks.staging_cleanup',
        'schedule': crontab(hour=6, minute=0),  # 6:00 AM daily
        'options': {'queue': 'staging'}
    },
}


def get_beat_schedule():
    """
    Get the appropriate beat schedule based on environment
    """
    from django.conf import settings
    
    # Start with base security schedule
    schedule = SECURITY_BEAT_SCHEDULE.copy()
    
    # Add environment-specific schedules
    env = getattr(settings, 'ENVIRONMENT', 'development')
    
    if env == 'production':
        schedule.update(PRODUCTION_SCHEDULE)
    elif env == 'staging':
        schedule.update(STAGING_SCHEDULE)
    else:
        schedule.update(DEVELOPMENT_SCHEDULE)
    
    return schedule


def configure_celery_beat(app):
    """
    Configure Celery Beat with security schedules
    """
    app.conf.beat_schedule = get_beat_schedule()
    
    # Configure beat settings
    app.conf.beat_scheduler = 'django_celery_beat.schedulers:DatabaseScheduler'
    app.conf.timezone = 'UTC'
    
    # Configure task routing
    app.conf.task_routes = {
        'api.security.tasks.*': {'queue': 'security'},
        'api.security.tasks.daily_*': {'queue': 'security_daily'},
        'api.security.tasks.hourly_*': {'queue': 'security_hourly'},
        'api.security.tasks.real_time_*': {'queue': 'security_realtime'},
    }
    
    # Configure task priorities
    app.conf.task_default_priority = 5
    app.conf.worker_prefetch_multiplier = 1
    app.conf.task_acks_late = True
    
    return app


class SecurityBeatConfig:
    """
    Security Beat Configuration Manager
    """
    
    def __init__(self):
        self.schedule = get_beat_schedule()
    
    def add_task(self, name, task_path, schedule, **options):
        """
        Add a new task to the beat schedule
        """
        self.schedule[name] = {
            'task': task_path,
            'schedule': schedule,
            'options': options
        }
    
    def remove_task(self, name):
        """
        Remove a task from the beat schedule
        """
        if name in self.schedule:
            del self.schedule[name]
    
    def update_task_schedule(self, name, new_schedule):
        """
        Update task schedule
        """
        if name in self.schedule:
            self.schedule[name]['schedule'] = new_schedule
    
    def get_task_info(self, name):
        """
        Get information about a specific task
        """
        return self.schedule.get(name)
    
    def list_all_tasks(self):
        """
        List all scheduled tasks
        """
        return list(self.schedule.keys())
    
    def get_tasks_by_frequency(self):
        """
        Group tasks by frequency
        """
        tasks_by_frequency = {
            'every_minute': [],
            'every_5_minutes': [],
            'every_10_minutes': [],
            'every_15_minutes': [],
            'every_30_minutes': [],
            'hourly': [],
            'daily': [],
            'weekly': [],
            'monthly': []
        }
        
        for name, task_config in self.schedule.items():
            schedule = task_config['schedule']
            
            if hasattr(schedule, 'minute'):
                if schedule.minute == '*/1':
                    tasks_by_frequency['every_minute'].append(name)
                elif schedule.minute == '*/5':
                    tasks_by_frequency['every_5_minutes'].append(name)
                elif schedule.minute == '*/10':
                    tasks_by_frequency['every_10_minutes'].append(name)
                elif schedule.minute == '*/15':
                    tasks_by_frequency['every_15_minutes'].append(name)
                elif schedule.minute == '*/30':
                    tasks_by_frequency['every_30_minutes'].append(name)
                elif schedule.minute == 0:
                    if hasattr(schedule, 'hour'):
                        if schedule.hour == '*/1':
                            tasks_by_frequency['hourly'].append(name)
                        else:
                            tasks_by_frequency['daily'].append(name)
                    else:
                        tasks_by_frequency['hourly'].append(name)
            
            if hasattr(schedule, 'day_of_week'):
                tasks_by_frequency['weekly'].append(name)
            
            if hasattr(schedule, 'day_of_month'):
                tasks_by_frequency['monthly'].append(name)
        
        return tasks_by_frequency
    
    def validate_schedule(self):
        """
        Validate the beat schedule for common issues
        """
        issues = []
        
        for name, task_config in self.schedule.items():
            # Check if task path is valid
            task_path = task_config['task']
            if not task_path or '.' not in task_path:
                issues.append(f"Invalid task path for {name}: {task_path}")
            
            # Check if schedule is valid
            schedule = task_config['schedule']
            if not hasattr(schedule, '__class__'):
                issues.append(f"Invalid schedule for {name}")
            
            # Check for duplicate task names
            task_names = [config['task'] for config in self.schedule.values()]
            if task_names.count(task_path) > 1:
                issues.append(f"Duplicate task path: {task_path}")
        
        return issues


# Global beat configuration instance
security_beat_config = SecurityBeatConfig()

# Export configuration for use in settings.py
CELERY_BEAT_SCHEDULE = get_beat_schedule()

# Task priority configuration
SECURITY_TASK_PRIORITIES = {
    'critical': 10,
    'high': 8,
    'medium': 5,
    'low': 2,
    'background': 1,
}

# Task timeout configuration
SECURITY_TASK_TIMEOUTS = {
    'short': 60,      # 1 minute
    'medium': 300,    # 5 minutes
    'long': 1800,     # 30 minutes
    'extended': 3600, # 1 hour
}

# Task retry configuration
SECURITY_TASK_RETRY_POLICY = {
    'max_retries': 3,
    'retry_backoff': True,
    'retry_backoff_max': 300,
    'retry_jitter': True,
}