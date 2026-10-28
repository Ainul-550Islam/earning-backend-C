# api/rate_limit/celery_beat_config.py
"""
Celery Beat Configuration for Rate Limit Module

Defines scheduled tasks for rate limit maintenance, cleanup, and analytics.
"""
from django.db import DatabaseError

from celery.schedules import crontab
from celery import Celery
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Import tasks
try:
    from api.rate_limit.tasks import (
        cleanup_old_rate_limit_logs,
        generate_rate_limit_insights,
        update_user_rate_limit_profiles,
        cleanup_expired_blocks,
        reset_daily_counters,
        sync_rate_limit_configurations,
        export_rate_limit_reports,
        analyze_abuse_patterns,
        update_health_metrics,
        archive_old_logs
    )
except ImportError as e:
    logger.warning(f"Could not import rate limit tasks: {e}")
    # Define dummy functions to prevent errors
    def cleanup_old_rate_limit_logs(): pass
    def generate_rate_limit_insights(): pass
    def update_user_rate_limit_profiles(): pass
    def cleanup_expired_blocks(): pass
    def reset_daily_counters(): pass
    def sync_rate_limit_configurations(): pass
    def export_rate_limit_reports(): pass
    def analyze_abuse_patterns(): pass
    def update_health_metrics(): pass
    def archive_old_logs(): pass


# Celery Beat Schedule Configuration
CELERY_BEAT_SCHEDULE = {
    # =================================================================
    # DAILY MAINTENANCE TASKS
    # =================================================================
    
    # Clean up old rate limit logs (runs daily at 2:00 AM)
    'cleanup-old-rate-limit-logs': {
        'task': 'api.rate_limit.tasks.cleanup_old_rate_limit_logs',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'rate_limit_maintenance'}
    },
    
    # Archive old logs to long-term storage (runs daily at 3:00 AM)
    'archive-old-logs': {
        'task': 'api.rate_limit.tasks.archive_old_logs',
        'schedule': crontab(hour=3, minute=0),
        'options': {'queue': 'rate_limit_maintenance'}
    },
    
    # Reset daily counters (runs daily at midnight)
    'reset-daily-counters': {
        'task': 'api.rate_limit.tasks.reset_daily_counters',
        'schedule': crontab(hour=0, minute=5),
        'options': {'queue': 'rate_limit_counters'}
    },
    
    # Generate daily rate limit insights (runs daily at 1:00 AM)
    'generate-rate-limit-insights': {
        'task': 'api.rate_limit.tasks.generate_rate_limit_insights',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'rate_limit_analytics'}
    },
    
    # Export daily reports (runs daily at 6:00 AM)
    'export-rate-limit-reports': {
        'task': 'api.rate_limit.tasks.export_rate_limit_reports',
        'schedule': crontab(hour=6, minute=0),
        'options': {'queue': 'rate_limit_reports'}
    },
    
    # =================================================================
    # HOURLY MAINTENANCE TASKS
    # =================================================================
    
    # Update user rate limit profiles (runs every hour at minute 15)
    'update-user-rate-limit-profiles': {
        'task': 'api.rate_limit.tasks.update_user_rate_limit_profiles',
        'schedule': crontab(minute=15),
        'options': {'queue': 'rate_limit_profiles'}
    },
    
    # Update health metrics (runs every hour at minute 30)
    'update-health-metrics': {
        'task': 'api.rate_limit.tasks.update_health_metrics',
        'schedule': crontab(minute=30),
        'options': {'queue': 'rate_limit_health'}
    },
    
    # Sync rate limit configurations (runs every hour at minute 45)
    'sync-rate-limit-configurations': {
        'task': 'api.rate_limit.tasks.sync_rate_limit_configurations',
        'schedule': crontab(minute=45),
        'options': {'queue': 'rate_limit_config'}
    },
    
    # =================================================================
    # FREQUENT MONITORING TASKS
    # =================================================================
    
    # Clean up expired blocks (runs every 30 minutes)
    'cleanup-expired-blocks': {
        'task': 'api.rate_limit.tasks.cleanup_expired_blocks',
        'schedule': crontab(minute='*/30'),
        'options': {'queue': 'rate_limit_cleanup'}
    },
    
    # Analyze abuse patterns (runs every 15 minutes)
    'analyze-abuse-patterns': {
        'task': 'api.rate_limit.tasks.analyze_abuse_patterns',
        'schedule': crontab(minute='*/15'),
        'options': {'queue': 'rate_limit_analysis'}
    },
    
    # =================================================================
    # WEEKLY MAINTENANCE TASKS
    # =================================================================
    
    # Weekly comprehensive cleanup (runs every Sunday at 4:00 AM)
    'weekly-rate-limit-cleanup': {
        'task': 'api.rate_limit.tasks.weekly_rate_limit_cleanup',
        'schedule': crontab(hour=4, minute=0, day_of_week='sunday'),
        'options': {'queue': 'rate_limit_maintenance'}
    },
    
    # Generate weekly analytics report (runs every Sunday at 7:00 AM)
    'generate-weekly-analytics': {
        'task': 'api.rate_limit.tasks.generate_weekly_analytics',
        'schedule': crontab(hour=7, minute=0, day_of_week='sunday'),
        'options': {'queue': 'rate_limit_analytics'}
    },
    
    # =================================================================
    # MONTHLY MAINTENANCE TASKS
    # =================================================================
    
    # Monthly data aggregation (runs on 1st of each month at 2:00 AM)
    'monthly-data-aggregation': {
        'task': 'api.rate_limit.tasks.monthly_data_aggregation',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),
        'options': {'queue': 'rate_limit_aggregation'}
    },
    
    # Monthly performance report (runs on 1st of each month at 8:00 AM)
    'monthly-performance-report': {
        'task': 'api.rate_limit.tasks.monthly_performance_report',
        'schedule': crontab(hour=8, minute=0, day_of_month=1),
        'options': {'queue': 'rate_limit_reports'}
    },
}


# Queue Configuration for Rate Limit Tasks
CELERY_TASK_ROUTES = {
    'api.rate_limit.tasks.*': {'queue': 'rate_limit'},
    
    # Specific task routing for better performance
    'api.rate_limit.tasks.cleanup_old_rate_limit_logs': {'queue': 'rate_limit_maintenance'},
    'api.rate_limit.tasks.generate_rate_limit_insights': {'queue': 'rate_limit_analytics'},
    'api.rate_limit.tasks.update_user_rate_limit_profiles': {'queue': 'rate_limit_profiles'},
    'api.rate_limit.tasks.cleanup_expired_blocks': {'queue': 'rate_limit_cleanup'},
    'api.rate_limit.tasks.reset_daily_counters': {'queue': 'rate_limit_counters'},
    'api.rate_limit.tasks.sync_rate_limit_configurations': {'queue': 'rate_limit_config'},
    'api.rate_limit.tasks.export_rate_limit_reports': {'queue': 'rate_limit_reports'},
    'api.rate_limit.tasks.analyze_abuse_patterns': {'queue': 'rate_limit_analysis'},
    'api.rate_limit.tasks.update_health_metrics': {'queue': 'rate_limit_health'},
    'api.rate_limit.tasks.archive_old_logs': {'queue': 'rate_limit_archive'},
}


# Task Configuration
CELERY_TASK_DEFAULT_QUEUE = 'rate_limit'
CELERY_TASK_QUEUE_MAX_PRIORITY = 10
CELERY_TASK_DEFAULT_PRIORITY = 5

# Priority settings for different task types
CELERY_TASK_PRIORITY_ROUTING = {
    'api.rate_limit.tasks.cleanup_expired_blocks': 8,  # High priority for security
    'api.rate_limit.tasks.analyze_abuse_patterns': 7,   # High priority for security
    'api.rate_limit.tasks.update_health_metrics': 6,     # Medium-high priority
    'api.rate_limit.tasks.reset_daily_counters': 5,      # Medium priority
    'api.rate_limit.tasks.update_user_rate_limit_profiles': 4,  # Medium priority
    'api.rate_limit.tasks.generate_rate_limit_insights': 3,     # Low-medium priority
    'api.rate_limit.tasks.cleanup_old_rate_limit_logs': 2,       # Low priority
    'api.rate_limit.tasks.export_rate_limit_reports': 1,         # Lowest priority
}


# Task Time Limits
CELERY_TASK_TIME_LIMIT = {
    'api.rate_limit.tasks.cleanup_old_rate_limit_logs': 1800,  # 30 minutes
    'api.rate_limit.tasks.generate_rate_limit_insights': 600,   # 10 minutes
    'api.rate_limit.tasks.update_user_rate_limit_profiles': 300, # 5 minutes
    'api.rate_limit.tasks.cleanup_expired_blocks': 300,        # 5 minutes
    'api.rate_limit.tasks.reset_daily_counters': 600,           # 10 minutes
    'api.rate_limit.tasks.sync_rate_limit_configurations': 180,  # 3 minutes
    'api.rate_limit.tasks.export_rate_limit_reports': 900,      # 15 minutes
    'api.rate_limit.tasks.analyze_abuse_patterns': 300,          # 5 minutes
    'api.rate_limit.tasks.update_health_metrics': 180,           # 3 minutes
    'api.rate_limit.tasks.archive_old_logs': 1200,              # 20 minutes
}

# Task Soft Time Limits (for graceful shutdown)
CELERY_TASK_SOFT_TIME_LIMIT = {
    'api.rate_limit.tasks.cleanup_old_rate_limit_logs': 1500,  # 25 minutes
    'api.rate_limit.tasks.generate_rate_limit_insights': 480,   # 8 minutes
    'api.rate_limit.tasks.update_user_rate_limit_profiles': 240, # 4 minutes
    'api.rate_limit.tasks.cleanup_expired_blocks': 240,        # 4 minutes
    'api.rate_limit.tasks.reset_daily_counters': 480,           # 8 minutes
    'api.rate_limit.tasks.sync_rate_limit_configurations': 150,  # 2.5 minutes
    'api.rate_limit.tasks.export_rate_limit_reports': 720,      # 12 minutes
    'api.rate_limit.tasks.analyze_abuse_patterns': 240,          # 4 minutes
    'api.rate_limit.tasks.update_health_metrics': 150,           # 2.5 minutes
    'api.rate_limit.tasks.archive_old_logs': 1080,              # 18 minutes
}


# Task Autoretry Settings
CELERY_TASK_AUTORETRY_FOR = {
    'api.rate_limit.tasks.generate_rate_limit_insights': [Exception, ConnectionError],
    'api.rate_limit.tasks.update_user_rate_limit_profiles': [Exception, DatabaseError],
    'api.rate_limit.tasks.sync_rate_limit_configurations': [Exception, ConnectionError],
    'api.rate_limit.tasks.export_rate_limit_reports': [Exception, IOError],
}

CELERY_TASK_RETRY_DELAY = {
    'api.rate_limit.tasks.generate_rate_limit_insights': 60,     # 1 minute
    'api.rate_limit.tasks.update_user_rate_limit_profiles': 30,  # 30 seconds
    'api.rate_limit.tasks.sync_rate_limit_configurations': 15,   # 15 seconds
    'api.rate_limit.tasks.export_rate_limit_reports': 120,      # 2 minutes
}

CELERY_TASK_MAX_RETRIES = {
    'api.rate_limit.tasks.generate_rate_limit_insights': 3,
    'api.rate_limit.tasks.update_user_rate_limit_profiles': 2,
    'api.rate_limit.tasks.sync_rate_limit_configurations': 3,
    'api.rate_limit.tasks.export_rate_limit_reports': 2,
}


# Monitoring and Alerting
def get_task_monitoring_config():
    """
    Get monitoring configuration for rate limit tasks.
    """
    return {
        'enabled_tasks': [
            'cleanup_old_rate_limit_logs',
            'generate_rate_limit_insights',
            'update_user_rate_limit_profiles',
            'cleanup_expired_blocks',
            'reset_daily_counters',
            'sync_rate_limit_configurations',
            'export_rate_limit_reports',
            'analyze_abuse_patterns',
            'update_health_metrics',
            'archive_old_logs'
        ],
        'alert_thresholds': {
            'failure_rate': 0.1,  # 10% failure rate triggers alert
            'execution_time': 3600,  # 1 hour execution time triggers alert
            'queue_size': 1000,  # 1000 tasks in queue triggers alert
        },
        'notification_channels': ['email', 'slack'],
        'monitoring_interval': 300,  # 5 minutes
    }


# Task Dependencies
def get_task_dependencies():
    """
    Define task execution order and dependencies.
    """
    return {
        'reset_daily_counters': {
            'depends_on': [],  # No dependencies, runs first
            'triggers': ['generate_rate_limit_insights']
        },
        'cleanup_expired_blocks': {
            'depends_on': [],
            'triggers': ['analyze_abuse_patterns']
        },
        'update_user_rate_limit_profiles': {
            'depends_on': ['reset_daily_counters'],
            'triggers': ['generate_rate_limit_insights']
        },
        'analyze_abuse_patterns': {
            'depends_on': ['cleanup_expired_blocks'],
            'triggers': ['update_health_metrics']
        },
        'update_health_metrics': {
            'depends_on': ['analyze_abuse_patterns', 'update_user_rate_limit_profiles'],
            'triggers': ['export_rate_limit_reports']
        },
        'generate_rate_limit_insights': {
            'depends_on': ['reset_daily_counters', 'update_user_rate_limit_profiles'],
            'triggers': ['export_rate_limit_reports']
        },
        'export_rate_limit_reports': {
            'depends_on': ['generate_rate_limit_insights', 'update_health_metrics'],
            'triggers': []
        },
        'cleanup_old_rate_limit_logs': {
            'depends_on': ['export_rate_limit_reports'],
            'triggers': ['archive_old_logs']
        },
        'archive_old_logs': {
            'depends_on': ['cleanup_old_rate_limit_logs'],
            'triggers': []
        }
    }


# Dynamic Schedule Configuration
def get_dynamic_schedule_config():
    """
    Get dynamic schedule configuration based on system load and time.
    """
    from django.utils import timezone
    import datetime
    
    now = timezone.now()
    
    # Adjust schedules based on time of day
    if 0 <= now.hour < 6:  # Night hours - less frequent
        return {
            'cleanup_interval': 60,  # Every hour instead of 30 minutes
            'analysis_interval': 30,  # Every 30 minutes instead of 15
            'profile_update_interval': 120,  # Every 2 hours instead of 1
        }
    elif 6 <= now.hour < 18:  # Business hours - more frequent
        return {
            'cleanup_interval': 15,  # Every 15 minutes
            'analysis_interval': 5,   # Every 5 minutes
            'profile_update_interval': 30,  # Every 30 minutes
        }
    else:  # Evening hours - normal frequency
        return {
            'cleanup_interval': 30,  # Every 30 minutes
            'analysis_interval': 15,  # Every 15 minutes
            'profile_update_interval': 60,  # Every hour
        }


# Configuration Validation
def validate_celery_config():
    """
    Validate Celery configuration for rate limit tasks.
    """
    errors = []
    warnings = []
    
    # Check if required tasks are defined
    required_tasks = [
        'cleanup_old_rate_limit_logs',
        'generate_rate_limit_insights',
        'update_user_rate_limit_profiles',
        'cleanup_expired_blocks',
        'reset_daily_counters'
    ]
    
    for task_name in required_tasks:
        if task_name not in CELERY_BEAT_SCHEDULE:
            errors.append(f"Missing required task: {task_name}")
    
    # Check queue configuration
    if 'rate_limit' not in CELERY_TASK_ROUTES.get('api.rate_limit.tasks.*', {}).get('queue', ''):
        warnings.append("Default rate_limit queue not configured")
    
    # Check time limits
    for task_name in required_tasks:
        if task_name not in CELERY_TASK_TIME_LIMIT:
            warnings.append(f"No time limit configured for task: {task_name}")
    
    return {
        'errors': errors,
        'warnings': warnings,
        'is_valid': len(errors) == 0
    }


# Initialize and validate configuration
def initialize_celery_config():
    """
    Initialize Celery configuration for rate limit module.
    """
    # Validate configuration
    validation_result = validate_celery_config()
    
    if not validation_result['is_valid']:
        logger.error("Celery configuration validation failed:")
        for error in validation_result['errors']:
            logger.error(f"  - {error}")
        raise ValueError("Invalid Celery configuration")
    
    if validation_result['warnings']:
        logger.warning("Celery configuration warnings:")
        for warning in validation_result['warnings']:
            logger.warning(f"  - {warning}")
    
    logger.info("Rate limit Celery configuration initialized successfully")
    
    # Log scheduled tasks
    logger.info(f"Scheduled {len(CELERY_BEAT_SCHEDULE)} rate limit tasks:")
    for task_name, task_config in CELERY_BEAT_SCHEDULE.items():
        schedule = task_config['schedule']
        logger.info(f"  - {task_name}: {schedule}")
    
    return True


# Auto-initialize when module is imported
try:
    initialize_celery_config()
except Exception as e:
    logger.error(f"Failed to initialize Celery config: {e}")


# Export configuration for external use
__all__ = [
    'CELERY_BEAT_SCHEDULE',
    'CELERY_TASK_ROUTES',
    'CELERY_TASK_DEFAULT_QUEUE',
    'CELERY_TASK_PRIORITY_ROUTING',
    'CELERY_TASK_TIME_LIMIT',
    'CELERY_TASK_SOFT_TIME_LIMIT',
    'CELERY_TASK_AUTORETRY_FOR',
    'CELERY_TASK_RETRY_DELAY',
    'CELERY_TASK_MAX_RETRIES',
    'get_task_monitoring_config',
    'get_task_dependencies',
    'get_dynamic_schedule_config',
    'validate_celery_config',
    'initialize_celery_config'
]
