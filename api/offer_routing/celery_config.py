"""
Celery Configuration for Offer Routing System

This module provides Celery configuration for scheduled tasks,
including task routing, worker settings, and monitoring configuration.
"""

import os
import logging
from celery import Celery
from django.conf import settings
from kombu import Queue, Exchange
from kombu.common import Queue, Exchange as KombuExchange

logger = logging.getLogger(__name__)

# Celery app instance
app = Celery('offer_routing')

# Configure Celery from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Task routing configuration
CELERY_ROUTES = {
    'offer_routing.tasks.core': {
        'queue': 'routing_core',
        'routing_key': 'routing.core',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.analytics': {
        'queue': 'analytics',
        'routing_key': 'analytics',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.monitoring': {
        'queue': 'monitoring',
        'routing_key': 'monitoring',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.ab_test': {
        'queue': 'ab_testing',
        'routing_key': 'ab_test',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.personalization': {
        'queue': 'personalization',
        'routing_key': 'personalization',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.scoring': {
        'queue': 'scoring',
        'routing_key': 'scoring',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.cap': {
        'queue': 'cap_management',
        'routing_key': 'cap_management',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
    'offer_routing.tasks.fallback': {
        'queue': 'fallback',
        'routing_key': 'fallback',
        'exchange': 'offer_routing',
        'exchange_type': 'topic',
    },
}

# Queue configuration
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'offer_routing'
CELERY_TASK_DEFAULT_EXCHANGE_TYPE = 'topic'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'routing.default'

# Queue definitions
CELERY_QUEUES = {
    'routing_core': Queue(
        'routing_core',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='routing.core',
        queue_arguments={'x-max-length': 10000}
    ),
    'analytics': Queue(
        'analytics',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='analytics',
        queue_arguments={'x-max-length': 5000}
    ),
    'monitoring': Queue(
        'monitoring',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='monitoring',
        queue_arguments={'x-max-length': 2000}
    ),
    'ab_testing': Queue(
        'ab_testing',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='ab_test',
        queue_arguments={'x-max-length': 1000}
    ),
    'personalization': Queue(
        'personalization',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='personalization',
        queue_arguments={'x-max-length': 3000}
    ),
    'scoring': Queue(
        'scoring',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='scoring',
        queue_arguments={'x-max-length': 2000}
    ),
    'cap_management': Queue(
        'cap_management',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='cap_management',
        queue_arguments={'x-max-length': 1500}
    ),
    'fallback': Queue(
        'fallback',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='fallback',
        queue_arguments={'x-max-length': 1000}
    ),
    'high_priority': Queue(
        'high_priority',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='high_priority',
        queue_arguments={'x-max-length': 5000}
    ),
    'low_priority': Queue(
        'low_priority',
        exchange=KombuExchange('offer_routing', 'topic'),
        routing_key='low_priority',
        queue_arguments={'x-max-length': 10000}
    ),
}

# Worker configuration
CELERY_WORKER_CONCURRENCY = {
    'routing_core': 4,
    'analytics': 2,
    'monitoring': 1,
    'ab_testing': 2,
    'personalization': 3,
    'scoring': 2,
    'cap_management': 1,
    'fallback': 1,
    'high_priority': 2,
    'low_priority': 1,
}

CELERY_WORKER_PREFETCH_MULTIPLIER = {
    'routing_core': 2,
    'analytics': 1,
    'monitoring': 1,
    'ab_testing': 1,
    'personalization': 2,
    'scoring': 1,
    'cap_management': 1,
    'fallback': 1,
    'high_priority': 2,
    'low_priority': 1,
}

# Task configuration
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'

# Beat schedule configuration
from celery.schedules import crontab
from celery.decorators import periodic_task

CELERYBEAT_SCHEDULE = {
    # Daily cap reset at midnight
    'reset-daily-caps': {
        'task': 'offer_routing.tasks.cap.reset_daily_caps',
        'schedule': crontab(minute=0, hour=0),  # Midnight every day
        'options': {
            'queue': 'cap_management',
            'priority': 9,
        }
    },
    
    # Cleanup old data at 2 AM
    'cleanup-old-data': {
        'task': 'offer_routing.tasks.core.cleanup_old_data',
        'schedule': crontab(minute=0, hour=2),  # 2 AM every day
        'options': {
            'queue': 'low_priority',
            'priority': 5,
        }
    },
    
    # Update analytics every hour
    'update-analytics': {
        'task': 'offer_routing.tasks.analytics.update_hourly_stats',
        'schedule': crontab(minute=0),  # Every hour
        'options': {
            'queue': 'analytics',
            'priority': 7,
        }
    },
    
    # Update performance metrics every 5 minutes
    'update-performance-metrics': {
        'task': 'offer_routing.tasks.monitoring.update_performance_metrics',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {
            'queue': 'monitoring',
            'priority': 8,
        }
    },
    
    # Process A/B test results every 30 minutes
    'process-ab-test-results': {
        'task': 'offer_routing.tasks.ab_test.process_test_results',
        'schedule': crontab(minute='*/30'),  # Every 30 minutes
        'options': {
            'queue': 'ab_testing',
            'priority': 6,
        }
    },
    
    # Update personalization models every 2 hours
    'update-personalization-models': {
        'task': 'offer_routing.tasks.personalization.update_preference_models',
        'schedule': crontab(minute=0, hour='*/2'),  # Every 2 hours
        'options': {
            'queue': 'personalization',
            'priority': 6,
        }
    },
    
    # Score offers every 15 minutes
    'score-offers': {
        'task': 'offer_routing.tasks.scoring.update_offer_scores',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
        'options': {
            'queue': 'scoring',
            'priority': 7,
        }
    },
    
    # Update fallback pools every hour
    'update-fallback-pools': {
        'task': 'offer_routing.tasks.fallback.update_pools',
        'schedule': crontab(minute=0),  # Every hour
        'options': {
            'queue': 'fallback',
            'priority': 5,
        }
    },
    
    # Health check every 10 minutes
    'health-check': {
        'task': 'offer_routing.tasks.monitoring.system_health_check',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
        'options': {
            'queue': 'monitoring',
            'priority': 9,
        }
    },
    
    # Generate daily reports at 6 AM
    'generate-daily-reports': {
        'task': 'offer_routing.tasks.analytics.generate_daily_reports',
        'schedule': crontab(minute=0, hour=6),  # 6 AM every day
        'options': {
            'queue': 'analytics',
            'priority': 8,
        }
    },
    
    # Optimize routing configuration every 4 hours
    'optimize-routing-config': {
        'task': 'offer_routing.tasks.optimizer.optimize_routing_config',
        'schedule': crontab(minute=0, hour='*/4'),  # Every 4 hours
        'options': {
            'queue': 'low_priority',
            'priority': 4,
        }
    },
}

# Task routing based on priority
def route_task(name, args=None, kwargs=None, queue=None, priority=None):
    """
    Route task to appropriate queue based on priority.
    """
    if priority is None:
        priority = 5  # Default priority
    
    # High priority tasks
    if priority >= 8:
        queue = 'high_priority'
    # Low priority tasks
    elif priority <= 3:
        queue = 'low_priority'
    # Use provided queue or default
    elif queue:
        queue = queue
    else:
        # Route based on task name
        if 'analytics' in name:
            queue = 'analytics'
        elif 'monitoring' in name:
            queue = 'monitoring'
        elif 'ab_test' in name:
            queue = 'ab_testing'
        elif 'personalization' in name:
            queue = 'personalization'
        elif 'scoring' in name:
            queue = 'scoring'
        elif 'cap' in name:
            queue = 'cap_management'
        elif 'fallback' in name:
            queue = 'fallback'
        else:
            queue = 'routing_core'
    
    return app.send_task(name, args=args, kwargs=kwargs, queue=queue, priority=priority)

# Task decorators
@app.task(bind=True, name='offer_routing.tasks.core.reset_daily_caps')
def reset_daily_caps_task(self):
    """
    Daily cap reset task with error handling.
    """
    try:
        logger.info("Starting daily cap reset task")
        # Task logic here
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Daily cap reset task failed: {e}")
        self.retry(exc=e, countdown=60)

@app.task(bind=True, name='offer_routing.tasks.analytics.update_analytics')
def update_analytics_task(self):
    """
    Analytics update task with error handling.
    """
    try:
        logger.info("Starting analytics update task")
        # Task logic here
        return {'status': 'success'}
    except Exception as e:
        logger.error(f"Analytics update task failed: {e}")
        self.retry(exc=e, countdown=60)

# Worker configuration
class CeleryConfig:
    """Celery configuration class for offer routing system."""
    
    @staticmethod
    def get_broker_url():
        """Get broker URL from environment or settings."""
        broker_url = os.environ.get('CELERY_BROKER_URL')
        if broker_url:
            return broker_url
        
        # Fallback to Django settings
        return getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
    
    @staticmethod
    def get_result_backend():
        """Get result backend from settings."""
        return getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
    
    @staticmethod
    def get_task_serializer():
        """Get task serializer from settings."""
        return getattr(settings, 'CELERY_TASK_SERIALIZER', 'json')
    
    @staticmethod
    def get_worker_config():
        """Get worker configuration from settings."""
        return {
            'concurrency': getattr(settings, 'CELERY_WORKER_CONCURRENCY', 4),
            'prefetch_multiplier': getattr(settings, 'CELERY_WORKER_PREFETCH_MULTIPLIER', 1),
            'max_tasks_per_child': getattr(settings, 'CELERY_WORKER_MAX_TASKS_PER_CHILD', 1000),
            'max_memory_per_child': getattr(settings, 'CELERY_WORKER_MAX_MEMORY_PER_CHILD', 200000),  # 200MB
            'time_limit': getattr(settings, 'CELERY_WORKER_TIME_LIMIT', 300),  # 5 minutes
            'soft_time_limit': getattr(settings, 'CELERY_WORKER_SOFT_TIME_LIMIT', 240),  # 4 minutes
            'optimize': getattr(settings, 'CELERY_WORKER_OPTIMIZE', True),
        }
    
    @staticmethod
    def get_monitoring_config():
        """Get monitoring configuration from settings."""
        return {
            'worker_send_task_events': getattr(settings, 'CELERY_WORKER_SEND_TASK_EVENTS', True),
            'worker_send_task_events_level': getattr(settings, 'CELERY_WORKER_SEND_TASK_EVENTS_LEVEL', 'INFO'),
            'task_track_started': getattr(settings, 'CELERY_TASK_TRACK_STARTED', True),
            'task_track_success': getattr(settings, 'CELERY_TASK_TRACK_SUCCESS', True),
            'task_track_failure': getattr(settings, 'CELERY_TASK_TRACK_FAILURE', True),
            'task_publish_retry': getattr(settings, 'CELERY_TASK_PUBLISH_RETRY', True),
            'task_publish_retry_policy': getattr(settings, 'CELERY_TASK_PUBLISH_RETRY_POLICY', {'max_retries': 3}),
            'task_acks_late': getattr(settings, 'CELERY_TASK_ACKS_LATE', True),
            'task_reject_on_worker_lost': getattr(settings, 'CELERY_TASK_REJECT_ON_WORKER_LOST', True),
        }

# Configure Celery app
app.conf.update(
    broker_url=CeleryConfig.get_broker_url(),
    result_backend=CeleryConfig.get_result_backend(),
    task_serializer=CeleryConfig.get_task_serializer(),
    accept_content=CELERY_ACCEPT_CONTENT,
    timezone=CELERY_TIMEZONE,
    enable_utc=True,
    task_routes=CELERY_ROUTES,
    task_queues=CELERY_QUEUES,
    task_default_queue=CELERY_TASK_DEFAULT_QUEUE,
    task_default_exchange=CELERY_TASK_DEFAULT_EXCHANGE,
    task_default_exchange_type=CELERY_TASK_DEFAULT_EXCHANGE_TYPE,
    task_default_routing_key=CELERY_TASK_DEFAULT_ROUTING_KEY,
    worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_annotations={
        'tasks.default_queue': 'offer_routing_default',
        'tasks.default_exchange': 'offer_routing',
        'tasks.default_exchange_type': 'topic',
        'tasks.default_routing_key': 'routing.default',
    },
    beat_schedule=CELERYBEAT_SCHEDULE,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=5,
    broker_connection_retry_delay=5,
    broker_connection_retry_backoff=2,
    broker_pool_limit=None,
    broker_heartbeat=30,
    broker_heartbeat_checkrate=2,
    worker_disable_rate_limits=False,
    worker_max_tasks_per_child=1000,
    worker_max_memory_per_child=200000,  # 200MB
    worker_prefetch_multiplier=1,
    worker_direct=False,
    worker_log_color=False,
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_log_level='INFO',
    worker_send_task_events=True,
    worker_send_task_events_level='INFO',
    task_track_started=True,
    task_track_success=True,
    task_track_failure=True,
    task_publish_retry=True,
    task_publish_retry_policy={'max_retries': 3},
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    task_default_queue='default',
    task_default_exchange='default',
    task_default_exchange_type='direct',
    task_default_routing_key='default',
    task_send_sent_event=True,
    task_publish_retry=False,
    task_inherit_parent_priority=True,
    task_compression='gzip',
    task_compression_level=6,
    task_compression_threshold=1024,
    task_ignore_result=False,
    task_store_errors_even_if_ignored=False,
    task_serializer='json',
    task_result_serializer='json',
    task_time_limit=300,
    task_soft_time_limit=240,
    task_track_started=True,
    task_track_success=True,
    task_track_failure=True,
    task_publish_retry=True,
    task_publish_retry_policy={'max_retries': 3},
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    task_store_eager_result=False,
    task_send_sent_event=True,
    task_publish_retry=False,
    task_inherit_parent_priority=True,
    task_compression='gzip',
    task_compression_level=6,
    task_compression_threshold=1024,
    task_ignore_result=False,
    task_store_errors_even_if_ignored=False,
    task_serializer='json',
    task_result_serializer='json',
    task_time_limit=300,
    task_soft_time_limit=240,
    task_track_started=True,
    task_track_success=True,
    task_track_failure=True,
    task_publish_retry=True,
    task_publish_retry_policy={'max_retries': 3},
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_ignore_result=False,
    task_store_eager_result=False,
    task_send_sent_event=True,
    task_publish_retry=False,
    task_inherit_parent_priority=True,
    task_compression='gzip',
    task_compression_level=6,
    task_compression_threshold=1024,
    task_ignore_result=False,
    task_store_errors_even_if_ignored=False,
    task_serializer='json',
    task_result_serializer='json',
    task_time_limit=300,
    task_soft_time_limit=240,
)

# Task decorators with custom routing
def routing_task(name=None, queue=None, priority=None):
    """
    Decorator for routing tasks with custom queue routing.
    """
    def decorator(func):
        return app.task(
            name=name,
            queue=queue,
            priority=priority,
            bind=True,
            max_retries=3,
            default_retry_delay=60,
            retry_backoff=True,
            retry_backoff_max=300,
            retry_jitter=True,
            autoretry_for=(Exception,),
            retry_backoff_policy={'max_retries': 3},
            time_limit=300,
            soft_time_limit=240,
        )(func)
    
    return decorator

# Monitoring and health check tasks
@periodic_task(run_every=300.0)  # Every 5 minutes
def health_check():
    """
    Periodic health check for Celery workers.
    """
    try:
        # Check active workers
        inspect = app.control.inspect()
        active_workers = inspect.active()
        
        logger.info(f"Active Celery workers: {len(active_workers)}")
        
        # Check queue lengths
        active_queues = inspect.active_queues()
        
        for queue_name, queue_info in active_queues.items():
            logger.info(f"Queue {queue_name}: {queue_info}")
            
            # Alert on long queues
            if queue_info.get('messages', 0) > 1000:
                logger.warning(f"Queue {queue_name} has {queue_info['messages']} pending tasks")
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")

# Utility functions
def get_task_info(task_id):
    """
    Get information about a specific task.
    """
    try:
        result = app.AsyncResult(task_id)
        
        return {
            'task_id': task_id,
            'status': result.status,
            'result': result.result if result.ready() else None,
            'traceback': result.traceback if result.failed() else None,
            'date_done': result.date_done if result.ready() else None,
        }
    
    except Exception as e:
        logger.error(f"Error getting task info: {e}")
        return None

def cancel_task(task_id, terminate=False):
    """
    Cancel a running task.
    """
    try:
        app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task {task_id} cancelled")
        
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {e}")

def get_worker_stats():
    """
    Get statistics about Celery workers.
    """
    try:
        inspect = app.control.inspect()
        stats = inspect.stats()
        
        return {
            'workers': stats,
            'total_workers': len(stats),
            'active_tasks': sum(worker.get('pool', {}).get('max-concurrency', 0) for worker in stats.values()),
        }
    
    except Exception as e:
        logger.error(f"Error getting worker stats: {e}")
        return None
