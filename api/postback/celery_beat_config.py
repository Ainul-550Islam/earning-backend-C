"""
celery_beat_config.py – Celery Beat configuration for postback module.

Defines scheduled tasks for postback processing, analytics aggregation,
and maintenance operations using Celery Beat scheduler.
"""
import logging
from datetime import timedelta

from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone

from .tasks import (
    aggregate_postback_insights,
    cleanup_old_postback_logs,
    verify_postback_integrity,
    cleanup_duplicate_leads,
    send_health_alerts,
    archive_old_insights,
    update_network_health_scores,
    retry_failed_postbacks,
    generate_daily_reports,
    cleanup_temp_files,
    backup_postback_data,
)

logger = logging.getLogger(__name__)


# Celery Beat schedule configuration
beat_schedule = {
    # Daily tasks
    'aggregate-daily-insights': {
        'task': 'api.postback.tasks.aggregate_postback_insights',
        'schedule': crontab(hour=1, minute=0),  # Run at 1:00 AM daily
        'options': {
            'queue': 'postback_analytics',
            'priority': 5,
        },
        'description': 'Aggregate daily postback insights and analytics'
    },
    
    'generate-daily-reports': {
        'task': 'api.postback.tasks.generate_daily_reports',
        'schedule': crontab(hour=2, minute=0),  # Run at 2:00 AM daily
        'options': {
            'queue': 'postback_reports',
            'priority': 3,
        },
        'description': 'Generate daily postback reports'
    },
    
    'cleanup-duplicate-leads': {
        'task': 'api.postback.tasks.cleanup_duplicate_leads',
        'schedule': crontab(hour=3, minute=0),  # Run at 3:00 AM daily
        'options': {
            'queue': 'postback_maintenance',
            'priority': 2,
        },
        'description': 'Clean up old duplicate lead entries'
    },
    
    'backup-postback-data': {
        'task': 'api.postback.tasks.backup_postback_data',
        'schedule': crontab(hour=4, minute=0),  # Run at 4:00 AM daily
        'options': {
            'queue': 'postback_backup',
            'priority': 1,
        },
        'description': 'Create daily backup of postback data'
    },
    
    # Hourly tasks
    'update-network-health-scores': {
        'task': 'api.postback.tasks.update_network_health_scores',
        'schedule': crontab(minute=0),  # Run every hour at minute 0
        'options': {
            'queue': 'postback_health',
            'priority': 4,
        },
        'description': 'Update network health scores and metrics'
    },
    
    'send-health-alerts': {
        'task': 'api.postback.tasks.send_health_alerts',
        'schedule': crontab(minute=30),  # Run every hour at minute 30
        'options': {
            'queue': 'postback_alerts',
            'priority': 6,
        },
        'description': 'Send health alerts for critical issues'
    },
    
    # Every 15 minutes
    'retry-failed-postbacks': {
        'task': 'api.postback.tasks.retry_failed_postbacks',
        'schedule': crontab(minute='*/15'),  # Run every 15 minutes
        'options': {
            'queue': 'postback_retry',
            'priority': 7,
        },
        'description': 'Retry failed postback processing'
    },
    
    # Every 6 hours
    'verify-postback-integrity': {
        'task': 'api.postback.tasks.verify_postback_integrity',
        'schedule': crontab(hour='*/6', minute=0),  # Run every 6 hours
        'options': {
            'queue': 'postback_integrity',
            'priority': 3,
        },
        'description': 'Verify integrity of postback data'
    },
    
    # Weekly tasks (Sundays at 5:00 AM)
    'cleanup-old-postback-logs': {
        'task': 'api.postback.tasks.cleanup_old_postback_logs',
        'schedule': crontab(hour=5, minute=0, day_of_week=0),  # Sunday 5:00 AM
        'options': {
            'queue': 'postback_maintenance',
            'priority': 1,
        },
        'description': 'Clean up old postback log entries'
    },
    
    'archive-old-insights': {
        'task': 'api.postback.tasks.archive_old_insights',
        'schedule': crontab(hour=6, minute=0, day_of_week=0),  # Sunday 6:00 AM
        'options': {
            'queue': 'postback_archive',
            'priority': 1,
        },
        'description': 'Archive old insight data'
    },
    
    # Every 4 hours
    'cleanup-temp-files': {
        'task': 'api.postback.tasks.cleanup_temp_files',
        'schedule': crontab(hour='*/4', minute=0),  # Run every 4 hours
        'options': {
            'queue': 'postback_maintenance',
            'priority': 1,
        },
        'description': 'Clean up temporary files and uploads'
    },
}

# Environment-specific schedule overrides
if hasattr(settings, 'POSTBACK_BEAT_SCHEDULE_OVERRIDES'):
    beat_schedule.update(settings.POSTBACK_BEAT_SCHEDULE_OVERRIDES)

# Development mode adjustments
if settings.DEBUG:
    # In development, run tasks more frequently for testing
    beat_schedule.update({
        'aggregate-daily-insights': {
            'task': 'api.postback.tasks.aggregate_postback_insights',
            'schedule': crontab(minute='*/30'),  # Every 30 minutes in dev
            'options': {
                'queue': 'postback_analytics',
                'priority': 5,
            },
            'description': 'Aggregate daily postback insights (dev mode)'
        },
        'update-network-health-scores': {
            'task': 'api.postback.tasks.update_network_health_scores',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes in dev
            'options': {
                'queue': 'postback_health',
                'priority': 4,
            },
            'description': 'Update network health scores (dev mode)'
        }
    })

# Production mode optimizations
if not settings.DEBUG:
    # In production, add monitoring and alerting tasks
    beat_schedule.update({
        'monitor-celery-queues': {
            'task': 'api.postback.tasks.monitor_celery_queues',
            'schedule': crontab(minute='*/10'),  # Every 10 minutes
            'options': {
                'queue': 'monitoring',
                'priority': 8,
            },
            'description': 'Monitor Celery queue health and performance'
        },
        
        'check-disk-space': {
            'task': 'api.postback.tasks.check_disk_space',
            'schedule': crontab(hour='*/2', minute=0),  # Every 2 hours
            'options': {
                'queue': 'monitoring',
                'priority': 8,
            },
            'description': 'Check available disk space for postback storage'
        }
    })


def get_schedule_for_environment():
    """
    Get the appropriate schedule for the current environment.
    
    Returns:
        dict: Celery Beat schedule configuration
    """
    environment = getattr(settings, 'ENVIRONMENT', 'development')
    
    if environment == 'production':
        return get_production_schedule()
    elif environment == 'staging':
        return get_staging_schedule()
    else:
        return get_development_schedule()


def get_production_schedule():
    """Get production-optimized schedule."""
    production_schedule = beat_schedule.copy()
    
    # Add production-specific tasks
    production_schedule.update({
        'hourly-performance-metrics': {
            'task': 'api.postback.tasks.collect_performance_metrics',
            'schedule': crontab(minute=0),  # Every hour
            'options': {
                'queue': 'monitoring',
                'priority': 7,
            },
            'description': 'Collect hourly performance metrics'
        },
        
        'daily-security-scan': {
            'task': 'api.postback.tasks.run_security_scan',
            'schedule': crontab(hour=7, minute=0),  # Daily at 7:00 AM
            'options': {
                'queue': 'security',
                'priority': 9,
            },
            'description': 'Run daily security scan'
        }
    })
    
    return production_schedule


def get_staging_schedule():
    """Get staging environment schedule."""
    staging_schedule = beat_schedule.copy()
    
    # Staging runs tasks more frequently than production but less than dev
    staging_schedule.update({
        'aggregate-daily-insights': {
            'task': 'api.postback.tasks.aggregate_postback_insights',
            'schedule': crontab(hour='*/2', minute=0),  # Every 2 hours
            'options': {
                'queue': 'postback_analytics',
                'priority': 5,
            },
            'description': 'Aggregate daily postback insights (staging mode)'
        }
    })
    
    return staging_schedule


def get_development_schedule():
    """Get development environment schedule."""
    development_schedule = beat_schedule.copy()
    
    # Development runs tasks very frequently for testing
    development_schedule.update({
        'aggregate-daily-insights': {
            'task': 'api.postback.tasks.aggregate_postback_insights',
            'schedule': crontab(minute='*/15'),  # Every 15 minutes
            'options': {
                'queue': 'postback_analytics',
                'priority': 5,
            },
            'description': 'Aggregate daily postback insights (dev mode)'
        },
        
        'update-network-health-scores': {
            'task': 'api.postback.tasks.update_network_health_scores',
            'schedule': crontab(minute='*/10'),  # Every 10 minutes
            'options': {
                'queue': 'postback_health',
                'priority': 4,
            },
            'description': 'Update network health scores (dev mode)'
        }
    })
    
    return development_schedule


def validate_schedule():
    """
    Validate the Celery Beat schedule configuration.
    
    Returns:
        dict: Validation results
    """
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'task_count': len(beat_schedule)
    }
    
    for task_name, task_config in beat_schedule.items():
        try:
            # Validate task configuration
            if 'task' not in task_config:
                validation_results['errors'].append(
                    f"Task '{task_name}' missing 'task' field"
                )
                validation_results['valid'] = False
            
            if 'schedule' not in task_config:
                validation_results['errors'].append(
                    f"Task '{task_name}' missing 'schedule' field"
                )
                validation_results['valid'] = False
            
            # Check for potential scheduling conflicts
            if isinstance(task_config.get('schedule'), crontab):
                # Add validation logic for crontab schedules
                pass
            
        except Exception as e:
            validation_results['errors'].append(
                f"Task '{task_name}' validation error: {str(e)}"
            )
            validation_results['valid'] = False
    
    return validation_results


def get_task_info():
    """
    Get information about all scheduled tasks.
    
    Returns:
        dict: Task information
    """
    task_info = {
        'total_tasks': len(beat_schedule),
        'tasks': {},
        'queue_distribution': {},
        'priority_distribution': {}
    }
    
    for task_name, task_config in beat_schedule.items():
        task_info['tasks'][task_name] = {
            'task': task_config.get('task'),
            'schedule': str(task_config.get('schedule')),
            'queue': task_config.get('options', {}).get('queue', 'default'),
            'priority': task_config.get('options', {}).get('priority', 5),
            'description': task_config.get('description', ''),
        }
        
        # Count queue distribution
        queue = task_config.get('options', {}).get('queue', 'default')
        task_info['queue_distribution'][queue] = (
            task_info['queue_distribution'].get(queue, 0) + 1
        )
        
        # Count priority distribution
        priority = task_config.get('options', {}).get('priority', 5)
        task_info['priority_distribution'][priority] = (
            task_info['priority_distribution'].get(priority, 0) + 1
        )
    
    return task_info


# Export the schedule
if hasattr(settings, 'CELERY_BEAT_SCHEDULE'):
    # If settings already has a schedule, merge with ours
    settings.CELERY_BEAT_SCHEDULE.update(beat_schedule)
else:
    # Otherwise, use our schedule
    settings.CELERY_BEAT_SCHEDULE = beat_schedule

# Set default Celery Beat settings if not already set
if not hasattr(settings, 'CELERY_BEAT_SCHEDULE_TIMEZONE'):
    settings.CELERY_BEAT_SCHEDULE_TIMEZONE = getattr(settings, 'TIME_ZONE', 'UTC')

if not hasattr(settings, 'CELERY_BEAT_SCHEDULER'):
    settings.CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

if not hasattr(settings, 'CELERY_BEAT_MAX_LOOP_INTERVAL'):
    settings.CELERY_BEAT_MAX_LOOP_INTERVAL = 5 * 60  # 5 minutes

logger.info(f"Celery Beat schedule configured with {len(beat_schedule)} tasks")

# ── New earning-platform beat schedules ───────────────────────────────────────
from celery.schedules import crontab as _crontab

CELERY_BEAT_SCHEDULE_ADDITIONS = {
    "rebuild-leaderboard-daily": {
        "task": "postback.tasks.rebuild_leaderboard",
        "schedule": _crontab(hour=0, minute=5),
        "args": ("daily",),
    },
    "rebuild-leaderboard-weekly": {
        "task": "postback.tasks.rebuild_leaderboard",
        "schedule": _crontab(hour=0, minute=15, day_of_week="monday"),
        "args": ("weekly",),
    },
    "rebuild-leaderboard-monthly": {
        "task": "postback.tasks.rebuild_leaderboard",
        "schedule": _crontab(hour=0, minute=30, day_of_month="1"),
        "args": ("monthly",),
    },
    "process-pending-withdrawals": {
        "task": "postback.tasks.process_pending_withdrawals",
        "schedule": _crontab(hour="*/6", minute=0),
    },
    "recalculate-user-tiers": {
        "task": "postback.tasks.recalculate_user_tiers",
        "schedule": _crontab(hour=2, minute=0),
    },
}

# ── B2B beat schedules ────────────────────────────────────────────────────────
CELERY_BEAT_SCHEDULE_ADDITIONS.update({
    "generate-monthly-invoices": {
        "task": "postback.b2b_tasks.generate_monthly_invoices",
        "schedule": _crontab(hour=1, minute=0, day_of_month="1"),
    },
    "check-budget-caps": {
        "task": "postback.b2b_tasks.check_budget_caps",
        "schedule": _crontab(minute="*/30"),
    },
    "rebuild-b2b-analytics": {
        "task": "postback.b2b_tasks.rebuild_b2b_analytics",
        "schedule": _crontab(hour=3, minute=0),
    },
})
