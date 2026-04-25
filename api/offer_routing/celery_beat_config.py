"""
Celery Beat Configuration for Offer Routing System

This module contains scheduled tasks configuration for the offer routing system,
including periodic tasks for cache management, performance monitoring,
and data cleanup.
"""

import logging
from celery import Celery
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Get Celery app instance
from .celery_config import app

# Beat Schedule Configuration
beat_schedule = {
    # Cache Management Tasks
    'clear-expired-cache': {
        'task': 'api.offer_routing.tasks.clear_expired_cache',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
        'options': {'queue': 'cache_management'}
    },
    'refresh-performance-cache': {
        'task': 'api.offer_routing.tasks.refresh_performance_cache',
        'schedule': crontab(minute=15, hour='*/6'),  # Every 6 hours at minute 15
        'options': {'queue': 'performance_monitoring'}
    },
    'cleanup-orphaned-cache': {
        'task': 'api.offer_routing.tasks.cleanup_orphaned_cache',
        'schedule': crontab(minute=30, hour=2),  # Daily at 2:30 AM
        'options': {'queue': 'maintenance'}
    },
    
    # Performance Monitoring Tasks
    'collect-routing-metrics': {
        'task': 'api.offer_routing.tasks.collect_routing_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'analytics'}
    },
    'generate-performance-reports': {
        'task': 'api.offer_routing.tasks.generate_performance_reports',
        'schedule': crontab(minute=0, hour=6),  # Daily at 6:00 AM
        'options': {'queue': 'reporting'}
    },
    'analyze-routing-patterns': {
        'task': 'api.offer_routing.tasks.analyze_routing_patterns',
        'schedule': crontab(minute=0, hour=1, day_of_week=1),  # Weekly on Monday at 1:00 AM
        'options': {'queue': 'analytics'}
    },
    
    # Data Maintenance Tasks
    'cleanup-old-routing-logs': {
        'task': 'api.offer_routing.tasks.cleanup_old_routing_logs',
        'schedule': crontab(minute=0, hour=3),  # Daily at 3:00 AM
        'options': {'queue': 'maintenance'}
    },
    'archive-historical-data': {
        'task': 'api.offer_routing.tasks.archive_historical_data',
        'schedule': crontab(minute=30, hour=4, day_of_month=1),  # Monthly on 1st at 4:30 AM
        'options': {'queue': 'maintenance'}
    },
    'cleanup-expired-sessions': {
        'task': 'api.offer_routing.tasks.cleanup_expired_sessions',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {'queue': 'maintenance'}
    },
    
    # Fraud Detection Tasks
    'analyze-fraud-patterns': {
        'task': 'api.offer_routing.tasks.analyze_fraud_patterns',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {'queue': 'fraud_detection'}
    },
    'update-fraud-scores': {
        'task': 'api.offer_routing.tasks.update_fraud_scores',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
        'options': {'queue': 'fraud_detection'}
    },
    'generate-fraud-reports': {
        'task': 'api.offer_routing.tasks.generate_fraud_reports',
        'schedule': crontab(minute=0, hour=8),  # Daily at 8:00 AM
        'options': {'queue': 'reporting'}
    },
    
    # Quality Score Tasks
    'update-offer-quality-scores': {
        'task': 'api.offer_routing.tasks.update_offer_quality_scores',
        'schedule': crontab(minute=0, hour='*/3'),  # Every 3 hours
        'options': {'queue': 'quality_management'}
    },
    'recalculate-personalization-weights': {
        'task': 'api.offer_routing.tasks.recalculate_personalization_weights',
        'schedule': crontab(minute=0, hour=2, day_of_week=0),  # Weekly on Sunday at 2:00 AM
        'options': {'queue': 'personalization'}
    },
    'optimize-routing-algorithms': {
        'task': 'api.offer_routing.tasks.optimize_routing_algorithms',
        'schedule': crontab(minute=30, hour=1, day_of_week=6),  # Weekly on Saturday at 1:30 AM
        'options': {'queue': 'optimization'}
    },
    
    # A/B Testing Tasks
    'evaluate-ab-test-results': {
        'task': 'api.offer_routing.tasks.evaluate_ab_test_results',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {'queue': 'ab_testing'}
    },
    'finalize-completed-tests': {
        'task': 'api.offer_routing.tasks.finalize_completed_tests',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
        'options': {'queue': 'ab_testing'}
    },
    
    # Notification Tasks
    'send-performance-alerts': {
        'task': 'api.offer_routing.tasks.send_performance_alerts',
        'schedule': crontab(minute='*/20'),  # Every 20 minutes
        'options': {'queue': 'notifications'}
    },
    'send-daily-reports': {
        'task': 'api.offer_routing.tasks.send_daily_reports',
        'schedule': crontab(minute=0, hour=9),  # Daily at 9:00 AM
        'options': {'queue': 'notifications'}
    },
    'cleanup-old-notifications': {
        'task': 'api.offer_routing.tasks.cleanup_old_notifications',
        'schedule': crontab(minute=0, hour=5),  # Daily at 5:00 AM
        'options': {'queue': 'maintenance'}
    },
    
    # Health Check Tasks
    'system-health-check': {
        'task': 'api.offer_routing.tasks.system_health_check',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'health_monitoring'}
    },
    'database-optimization': {
        'task': 'api.offer_routing.tasks.database_optimization',
        'schedule': crontab(minute=0, hour=0, day_of_week=3),  # Weekly on Wednesday at midnight
        'options': {'queue': 'maintenance'}
    },
}

# Configure Celery Beat
app.conf.beat_schedule = beat_schedule
app.conf.timezone = getattr(settings, 'TIME_ZONE', 'UTC')
app.conf.enable_utc = True


class BeatScheduler:
    """
    Custom beat scheduler for offer routing system.
    
    Provides additional functionality for dynamic scheduling
    and task management.
    """
    
    def __init__(self):
        self.app = app
        self.logger = logging.getLogger(__name__)
    
    def add_periodic_task(self, name, task, schedule, **kwargs):
        """Add a new periodic task dynamically."""
        try:
            self.app.conf.beat_schedule[name] = {
                'task': task,
                'schedule': schedule,
                **kwargs
            }
            self.logger.info(f"Added periodic task: {name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add periodic task {name}: {str(e)}")
            return False
    
    def remove_periodic_task(self, name):
        """Remove a periodic task dynamically."""
        try:
            if name in self.app.conf.beat_schedule:
                del self.app.conf.beat_schedule[name]
                self.logger.info(f"Removed periodic task: {name}")
                return True
            else:
                self.logger.warning(f"Periodic task not found: {name}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to remove periodic task {name}: {str(e)}")
            return False
    
    def update_task_schedule(self, name, new_schedule):
        """Update schedule for an existing periodic task."""
        try:
            if name in self.app.conf.beat_schedule:
                self.app.conf.beat_schedule[name]['schedule'] = new_schedule
                self.logger.info(f"Updated schedule for task: {name}")
                return True
            else:
                self.logger.warning(f"Periodic task not found: {name}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to update schedule for task {name}: {str(e)}")
            return False
    
    def list_tasks(self):
        """List all configured periodic tasks."""
        return list(self.app.conf.beat_schedule.keys())
    
    def get_task_info(self, name):
        """Get information about a specific periodic task."""
        return self.app.conf.beat_schedule.get(name)


# Create global scheduler instance
scheduler = BeatScheduler()


def setup_beat_schedule():
    """
    Setup and configure the beat schedule.
    
    This function is called when the Celery beat starts
    to ensure all scheduled tasks are properly configured.
    """
    try:
        # Apply any environment-specific overrides
        if hasattr(settings, 'OFFER_ROUTING_BEAT_OVERRIDES'):
            for task_name, task_config in settings.OFFER_ROUTING_BEAT_OVERRIDES.items():
                if task_config.get('enabled', True):
                    app.conf.beat_schedule[task_name] = task_config
                elif task_name in app.conf.beat_schedule:
                    del app.conf.beat_schedule[task_name]
        
        # Log configured tasks
        logger.info(f"Configured {len(app.conf.beat_schedule)} periodic tasks")
        
        # Validate task configurations
        for task_name, task_config in app.conf.beat_schedule.items():
            if 'task' not in task_config:
                logger.error(f"Task {task_name} missing 'task' field")
            elif 'schedule' not in task_config:
                logger.error(f"Task {task_name} missing 'schedule' field")
        
        logger.info("Celery beat schedule setup completed")
        
    except Exception as e:
        logger.error(f"Failed to setup beat schedule: {str(e)}")
        raise


def get_next_run_time(task_name):
    """Get the next run time for a specific task."""
    try:
        task_config = app.conf.beat_schedule.get(task_name)
        if task_config:
            schedule = task_config['schedule']
            return schedule.now()
        return None
    except Exception as e:
        logger.error(f"Failed to get next run time for {task_name}: {str(e)}")
        return None


def enable_task(task_name):
    """Enable a specific periodic task."""
    if task_name in app.conf.beat_schedule:
        app.conf.beat_schedule[task_name]['enabled'] = True
        logger.info(f"Enabled task: {task_name}")
        return True
    return False


def disable_task(task_name):
    """Disable a specific periodic task."""
    if task_name in app.conf.beat_schedule:
        app.conf.beat_schedule[task_name]['enabled'] = False
        logger.info(f"Disabled task: {task_name}")
        return True
    return False


# Export the scheduler for use in other modules
__all__ = [
    'app',
    'beat_schedule',
    'scheduler',
    'setup_beat_schedule',
    'get_next_run_time',
    'enable_task',
    'disable_task',
]
