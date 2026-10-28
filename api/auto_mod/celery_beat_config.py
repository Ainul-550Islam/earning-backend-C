# =============================================================================
# auto_mod/celery_beat_config.py
# =============================================================================

"""
Celery Beat configuration for auto moderation system.
Defines periodic tasks for automated moderation workflows.
"""

from celery import Celery
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Import tasks
from .tasks import (
    process_queue_items,
    escalate_overdue_items,
    process_appeals,
    train_ml_model,
    deploy_ml_model,
    process_content_signals,
    cleanup_old_decisions,
    generate_moderation_metrics,
    check_system_health,
    scan_submission,
    evaluate_rules,
    bot_process_task
)

# Import task names from constants
from .constants import (
    TASK_PROCESS_QUEUE_ITEMS,
    TASK_ESCALATE_OVERDUE_ITEMS,
    TASK_PROCESS_APPEALS,
    TASK_TRAIN_MODEL,
    TASK_DEPLOY_MODEL,
    TASK_PROCESS_SIGNALS,
    TASK_CLEANUP_DECISIONS,
    TASK_GENERATE_METRICS,
    TASK_CHECK_HEALTH,
    TASK_SCAN_SUBMISSION,
    TASK_EVALUATE_RULES,
    TASK_BOT_PROCESS
)


class AutoModCeleryBeatConfig:
    """
    Celery Beat configuration for auto moderation system.
    """
    
    def __init__(self):
        self.beat_schedule = self._get_beat_schedule()
        self.timezone = getattr(settings, 'TIME_ZONE', 'UTC')
    
    def _get_beat_schedule(self):
        """
        Define periodic tasks for auto moderation.
        """
        return {
            # Queue Management Tasks
            TASK_PROCESS_QUEUE_ITEMS: {
                'task': f'api.auto_mod.tasks.{TASK_PROCESS_QUEUE_ITEMS}',
                'schedule': crontab(minute='*/5'),  # Every 5 minutes
                'options': {
                    'queue': 'auto_mod_queue',
                    'priority': 5,
                    'expires': 300,  # 5 minutes
                }
            },
            TASK_ESCALATE_OVERDUE_ITEMS: {
                'task': f'api.auto_mod.tasks.{TASK_ESCALATE_OVERDUE_ITEMS}',
                'schedule': crontab(minute=0, hour='*/1'),  # Every hour
                'options': {
                    'queue': 'auto_mod_queue',
                    'priority': 3,
                    'expires': 600,  # 10 minutes
                }
            },
            
            # Appeal Processing
            TASK_PROCESS_APPEALS: {
                'task': f'api.auto_mod.tasks.{TASK_PROCESS_APPEALS}',
                'schedule': crontab(minute='*/10'),  # Every 10 minutes
                'options': {
                    'queue': 'auto_mod_queue',
                    'priority': 4,
                    'expires': 300,  # 5 minutes
                }
            },
            
            # ML Model Management
            TASK_TRAIN_MODEL: {
                'task': f'api.auto_mod.tasks.{TASK_TRAIN_MODEL}',
                'schedule': crontab(minute=0, hour='2', day_of_week='1'),  # Monday 2 AM
                'options': {
                    'queue': 'ml_training_queue',
                    'priority': 2,
                    'expires': 3600,  # 1 hour
                }
            },
            TASK_DEPLOY_MODEL: {
                'task': f'api.auto_mod.tasks.{TASK_DEPLOY_MODEL}',
                'schedule': crontab(minute=30, hour='2', day_of_week='1'),  # Monday 2:30 AM
                'options': {
                    'queue': 'ml_training_queue',
                    'priority': 2,
                    'expires': 1800,  # 30 minutes
                }
            },
            
            # Content Signal Processing
            TASK_PROCESS_SIGNALS: {
                'task': f'api.auto_mod.tasks.{TASK_PROCESS_SIGNALS}',
                'schedule': crontab(minute='*/2'),  # Every 2 minutes
                'options': {
                    'queue': 'signal_processing_queue',
                    'priority': 6,
                    'expires': 120,  # 2 minutes
                }
            },
            
            # Cleanup Tasks
            TASK_CLEANUP_DECISIONS: {
                'task': f'api.auto_mod.tasks.{TASK_CLEANUP_DECISIONS}',
                'schedule': crontab(minute=0, hour='3', day_of_month='1'),  # 1st of month 3 AM
                'options': {
                    'queue': 'cleanup_queue',
                    'priority': 1,
                    'expires': 7200,  # 2 hours
                }
            },
            
            # Metrics and Monitoring
            TASK_GENERATE_METRICS: {
                'task': f'api.auto_mod.tasks.{TASK_GENERATE_METRICS}',
                'schedule': crontab(minute='*/15'),  # Every 15 minutes
                'options': {
                    'queue': 'metrics_queue',
                    'priority': 3,
                    'expires': 600,  # 10 minutes
                }
            },
            TASK_CHECK_HEALTH: {
                'task': f'api.auto_mod.tasks.{TASK_CHECK_HEALTH}',
                'schedule': crontab(minute='*/5'),  # Every 5 minutes
                'options': {
                    'queue': 'health_check_queue',
                    'priority': 7,
                    'expires': 240,  # 4 minutes
                }
            },
            
            # Bot Processing
            TASK_BOT_PROCESS: {
                'task': f'api.auto_mod.tasks.{TASK_BOT_PROCESS}',
                'schedule': crontab(minute='*/1'),  # Every minute
                'options': {
                    'queue': 'bot_processing_queue',
                    'priority': 6,
                    'expires': 60,  # 1 minute
                }
            },
            
            # Rule Evaluation
            TASK_EVALUATE_RULES: {
                'task': f'api.auto_mod.tasks.{TASK_EVALUATE_RULES}',
                'schedule': crontab(minute='*/30'),  # Every 30 minutes
                'options': {
                    'queue': 'rule_evaluation_queue',
                    'priority': 4,
                    'expires': 900,  # 15 minutes
                }
            },
            
            # Submission Scanning
            TASK_SCAN_SUBMISSION: {
                'task': f'api.auto_mod.tasks.{TASK_SCAN_SUBMISSION}',
                'schedule': crontab(minute='*/3'),  # Every 3 minutes
                'options': {
                    'queue': 'scanning_queue',
                    'priority': 5,
                    'expires': 180,  # 3 minutes
                }
            }
        }
    
    def get_schedule(self):
        """Get the complete beat schedule."""
        return self.beat_schedule
    
    def add_custom_task(self, task_name, task_path, schedule, options=None):
        """
        Add a custom task to the beat schedule.
        
        Args:
            task_name: Name of the task
            task_path: Full path to the task (e.g., 'api.auto_mod.tasks.my_task')
            schedule: Celery schedule object
            options: Additional task options
        """
        if options is None:
            options = {}
        
        self.beat_schedule[task_name] = {
            'task': task_path,
            'schedule': schedule,
            'options': options
        }
        
        logger.info(f"Added custom task {task_name} to beat schedule")
    
    def remove_task(self, task_name):
        """
        Remove a task from the beat schedule.
        
        Args:
            task_name: Name of the task to remove
        """
        if task_name in self.beat_schedule:
            del self.beat_schedule[task_name]
            logger.info(f"Removed task {task_name} from beat schedule")
        else:
            logger.warning(f"Task {task_name} not found in beat schedule")
    
    def update_task_schedule(self, task_name, new_schedule):
        """
        Update the schedule for an existing task.
        
        Args:
            task_name: Name of the task to update
            new_schedule: New Celery schedule object
        """
        if task_name in self.beat_schedule:
            self.beat_schedule[task_name]['schedule'] = new_schedule
            logger.info(f"Updated schedule for task {task_name}")
        else:
            logger.warning(f"Task {task_name} not found in beat schedule")
    
    def get_task_info(self, task_name):
        """
        Get information about a specific task.
        
        Args:
            task_name: Name of the task
            
        Returns:
            Task configuration dictionary or None if not found
        """
        return self.beat_schedule.get(task_name)
    
    def list_all_tasks(self):
        """
        List all tasks in the beat schedule.
        
        Returns:
            List of task names
        """
        return list(self.beat_schedule.keys())
    
    def get_tasks_by_queue(self, queue_name):
        """
        Get all tasks that use a specific queue.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Dictionary of tasks using the specified queue
        """
        queue_tasks = {}
        for task_name, task_config in self.beat_schedule.items():
            if task_config.get('options', {}).get('queue') == queue_name:
                queue_tasks[task_name] = task_config
        
        return queue_tasks


# Create global beat configuration instance
beat_config = AutoModCeleryBeatConfig()


# Celery Beat configuration for Django settings
CELERY_BEAT_SCHEDULE = beat_config.get_schedule()
CELERY_TIMEZONE = beat_config.timezone


# Dynamic schedule management functions
def add_periodic_task(task_name, task_path, schedule, **options):
    """
    Add a new periodic task to the beat schedule.
    
    Example:
        add_periodic_task(
            'my_custom_task',
            'api.auto_mod.tasks.my_custom_task',
            crontab(minute='*/10'),
            queue='custom_queue',
            priority=5
        )
    """
    beat_config.add_custom_task(task_name, task_path, schedule, options)


def remove_periodic_task(task_name):
    """
    Remove a periodic task from the beat schedule.
    
    Args:
        task_name: Name of the task to remove
    """
    beat_config.remove_task(task_name)


def update_task_schedule(task_name, new_schedule):
    """
    Update the schedule for an existing periodic task.
    
    Args:
        task_name: Name of the task to update
        new_schedule: New Celery schedule object
    """
    beat_config.update_task_schedule(task_name, new_schedule)


def get_periodic_tasks():
    """
    Get all periodic tasks.
    
    Returns:
        List of task names
    """
    return beat_config.list_all_tasks()


def get_task_configuration(task_name):
    """
    Get configuration for a specific periodic task.
    
    Args:
        task_name: Name of the task
        
    Returns:
        Task configuration dictionary
    """
    return beat_config.get_task_info(task_name)


# Queue-specific task management
def get_queue_tasks(queue_name):
    """
    Get all tasks for a specific queue.
    
    Args:
        queue_name: Name of the queue
        
    Returns:
        Dictionary of tasks for the queue
    """
    return beat_config.get_tasks_by_queue(queue_name)


# Predefined schedules for common use cases
class CommonSchedules:
    """Common schedule patterns for auto moderation."""
    
    @staticmethod
    def every_minutes(minutes):
        """Run every N minutes."""
        return crontab(minute=f'*/{minutes}')
    
    @staticmethod
    def every_hours(hours):
        """Run every N hours."""
        return crontab(minute=0, hour=f'*/{hours}')
    
    @staticmethod
    def daily_at(hour, minute=0):
        """Run daily at specific time."""
        return crontab(minute=minute, hour=hour)
    
    @staticmethod
    def weekly_on(day_of_week, hour=0, minute=0):
        """Run weekly on specific day."""
        return crontab(minute=minute, hour=hour, day_of_week=day_of_week)
    
    @staticmethod
    def monthly_on(day_of_month, hour=0, minute=0):
        """Run monthly on specific day."""
        return crontab(minute=minute, hour=hour, day_of_month=day_of_month)
    
    @staticmethod
    def business_hours():
        """Run during business hours (9 AM - 5 PM, Monday-Friday)."""
        return crontab(minute='*/30', hour='9-17', day_of_week='1-5')
    
    @staticmethod
    def off_hours():
        """Run during off hours (outside 9 AM - 5 PM, Monday-Friday)."""
        return crontab(minute='0', hour='0-8,18-23')


# Task priority levels
class TaskPriority:
    """Task priority levels for auto moderation."""
    
    CRITICAL = 7    # Health checks, urgent escalations
    HIGH = 6        # Bot processing, signal processing
    NORMAL = 5      # Queue processing, scanning
    MEDIUM = 4      # Appeals, rule evaluation
    LOW = 3         # Metrics, escalations
    MAINTENANCE = 2 # ML training, deployment
    CLEANUP = 1     # Cleanup tasks


# Queue names
class QueueNames:
    """Queue names for auto moderation tasks."""
    
    AUTO_MOD = 'auto_mod_queue'
    ML_TRAINING = 'ml_training_queue'
    SIGNAL_PROCESSING = 'signal_processing_queue'
    CLEANUP = 'cleanup_queue'
    METRICS = 'metrics_queue'
    HEALTH_CHECK = 'health_check_queue'
    BOT_PROCESSING = 'bot_processing_queue'
    RULE_EVALUATION = 'rule_evaluation_queue'
    SCANNING = 'scanning_queue'


# Task expiration times (in seconds)
class TaskExpiry:
    """Task expiration times."""
    
    VERY_SHORT = 60      # 1 minute
    SHORT = 300          # 5 minutes
    MEDIUM = 600         # 10 minutes
    LONG = 1800          # 30 minutes
    VERY_LONG = 3600     # 1 hour
    EXTENDED = 7200      # 2 hours


# Helper function to create task configurations
def create_task_config(task_path, schedule, queue=QueueNames.AUTO_MOD, 
                      priority=TaskPriority.NORMAL, expiry=TaskExpiry.MEDIUM, 
                      **kwargs):
    """
    Create a standardized task configuration.
    
    Args:
        task_path: Full path to the task
        schedule: Celery schedule object
        queue: Queue name
        priority: Task priority
        expiry: Task expiration time in seconds
        **kwargs: Additional options
        
    Returns:
        Task configuration dictionary
    """
    options = {
        'queue': queue,
        'priority': priority,
        'expires': expiry,
        **kwargs
    }
    
    return {
        'task': task_path,
        'schedule': schedule,
        'options': options
    }


# Logging configuration for Celery Beat
def setup_celery_beat_logging():
    """Setup logging for Celery Beat tasks."""
    import logging
    
    # Create logger for Celery Beat
    beat_logger = logging.getLogger('celery.beat')
    beat_logger.setLevel(logging.INFO)
    
    # Create handler
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    # Add handler to logger
    beat_logger.addHandler(handler)
    
    logger.info("Celery Beat logging configured")


# Initialize logging when module is imported
setup_celery_beat_logging()
