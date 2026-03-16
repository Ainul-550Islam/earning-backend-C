# earning_backend/celery.py
"""
📦 Celery Configuration - Complete & Bulletproof
With Defensive Coding, Error Handling & Graceful Degradation
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from functools import wraps

# Django imports
from celery import Celery, signals
from celery.exceptions import CeleryError, TimeoutError
from kombu.exceptions import OperationalError

# Logger setup
logger = logging.getLogger(__name__)


# ==================== DEFENSIVE DECORATORS ====================

def safe_celery_task(default_return=None):
    """Decorator for safe celery task execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Task {func.__name__} failed: {str(e)}", exc_info=True)
                return default_return
        return wrapper
    return decorator


def retry_on_failure(max_retries: int = 3, countdown: int = 5):
    """Retry decorator for celery tasks"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    logger.warning(f"Task {func.__name__} failed (attempt {retries}/{max_retries}): {e}")
                    if retries == max_retries:
                        logger.error(f"Task {func.__name__} failed after {max_retries} attempts")
                        raise
                    import time
                    time.sleep(countdown)
            return None
        return wrapper
    return decorator


# ==================== SAFE CONFIGURATION ====================

class SafeCeleryConfig:
    """Safe configuration loader with fallback values"""
    
    @staticmethod
    def get_env(key: str, default: Any = None) -> Any:
        """Safely get environment variable"""
        try:
            value = os.environ.get(key)
            return value if value is not None else default
        except Exception:
            return default
    
    @staticmethod
    def get_bool_env(key: str, default: bool = False) -> bool:
        """Safely get boolean environment variable"""
        try:
            value = os.environ.get(key, '').lower()
            return value in ['true', '1', 'yes', 'y', 'on']
        except Exception:
            return default
    
    @staticmethod
    def get_int_env(key: str, default: int = 0) -> int:
        """Safely get integer environment variable"""
        try:
            return int(os.environ.get(key, default))
        except (ValueError, TypeError):
            return default


# ==================== CELERY APP INITIALIZATION ====================

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

# Create Celery app with defensive coding
try:
    app = Celery('earning_backend')
    logger.info("✅ Celery app initialized successfully")
except Exception as e:
    logger.critical(f"❌ Failed to create Celery app: {e}")
    # Fallback to minimal app
    app = Celery('earning_backend')
    app.conf.update(
        task_always_eager=True,
        task_eager_propagates=False
    )


# ==================== CONFIGURATION WITH FALLBACKS ====================

# Namespace for Celery config in Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Default configurations with fallbacks
default_configs = {
    # Broker settings
    'broker_url': SafeCeleryConfig.get_env('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    'result_backend': SafeCeleryConfig.get_env('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    
    # Serialization
    'accept_content': ['application/json', 'application/x-python-serialize'],
    'task_serializer': 'json',
    'result_serializer': 'json',
    'timezone': SafeCeleryConfig.get_env('CELERY_TIMEZONE', 'Asia/Dhaka'),
    
    # Task settings
    'task_always_eager': SafeCeleryConfig.get_bool_env('CELERY_TASK_ALWAYS_EAGER', False),
    'task_eager_propagates': SafeCeleryConfig.get_bool_env('CELERY_TASK_EAGER_PROPAGATES', True),
    'task_ignore_result': SafeCeleryConfig.get_bool_env('CELERY_TASK_IGNORE_RESULT', False),
    'task_store_errors_even_if_ignored': True,
    
    # Task execution
    'task_acks_late': True,
    'task_reject_on_worker_lost': True,
    'task_time_limit': SafeCeleryConfig.get_int_env('CELERY_TASK_TIME_LIMIT', 600),
    'task_soft_time_limit': SafeCeleryConfig.get_int_env('CELERY_TASK_SOFT_TIME_LIMIT', 300),
    
    # Retry settings
    'task_publish_retry': True,
    'task_publish_retry_policy': {
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.2,
    },
    
    # Worker settings
    'worker_concurrency': SafeCeleryConfig.get_int_env('CELERY_WORKER_CONCURRENCY', 4),
    'worker_prefetch_multiplier': 4,
    'worker_max_tasks_per_child': SafeCeleryConfig.get_int_env('CELERY_WORKER_MAX_TASKS', 1000),
    
    # Result settings
    'result_expires': SafeCeleryConfig.get_int_env('CELERY_RESULT_EXPIRES', 3600),
    'result_cache_max': 10000,
    
    # Beat settings
    'beat_schedule': {},
    'beat_scheduler': 'django_celery_beat.schedulers:DatabaseScheduler',
}

# Apply default configs with error handling
for key, value in default_configs.items():
    try:
        if not app.conf.get(key):
            app.conf.update({key: value})
    except Exception as e:
        logger.warning(f"Could not set config {key}: {e}")


# ==================== AUTO-DISCOVER TASKS ====================

try:
    # Auto-discover tasks from all installed apps
    app.autodiscover_tasks()
    logger.info("✅ Celery tasks auto-discovered")
except Exception as e:
    logger.error(f"❌ Failed to auto-discover tasks: {e}")


# ==================== SIGNAL HANDLERS ====================

@signals.task_prerun.connect
def task_prerun_handler(task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Log task before execution"""
    logger.info(f"▶️ Task started: {task.name}[{task_id}]")


@signals.task_postrun.connect
def task_postrun_handler(task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **kwds):
    """Log task after execution"""
    logger.info(f"✅ Task completed: {task.name}[{task_id}] - State: {state}")


@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kwds):
    """Log task failure"""
    logger.error(f"❌ Task failed: {sender.name}[{task_id}] - Error: {exception}")


@signals.worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log worker ready"""
    logger.info("🚀 Celery worker ready and listening")


@signals.worker_shutdown.connect
def worker_shutdown_handler(sender=None, **kwargs):
    """Log worker shutdown"""
    logger.info("👋 Celery worker shutting down")


# ==================== HELPER FUNCTIONS ====================

def get_celery_app() -> Celery:
    """Safely get celery app instance"""
    try:
        return app
    except NameError:
        logger.error("Celery app not initialized")
        return None


def is_celery_available() -> bool:
    """Check if celery is available and working"""
    try:
        # Try to ping celery
        from celery.utils import uuid
        task_id = uuid()
        app.send_task('celery.ping', task_id=task_id)
        return True
    except (CeleryError, OperationalError, TimeoutError) as e:
        logger.warning(f"Celery not available: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking celery: {e}")
        return False


def get_broker_status() -> Dict[str, Any]:
    """Get broker connection status"""
    status = {
        'connected': False,
        'broker_url': app.conf.get('broker_url', 'unknown'),
        'error': None
    }
    
    try:
        with app.connection() as conn:
            conn.ensure_connection(max_retries=1)
            status['connected'] = True
    except Exception as e:
        status['error'] = str(e)
        logger.error(f"Broker connection failed: {e}")
    
    return status


# ==================== TASK DECORATORS ====================

def safe_task(*args, **kwargs):
    """Safe task decorator with error handling"""
    def decorator(func):
        @safe_celery_task()
        @retry_on_failure()
        @app.task(*args, **kwargs)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ==================== EXPORTS ====================

__all__ = [
    'app',
    'safe_task',
    'get_celery_app',
    'is_celery_available',
    'get_broker_status',
]

logger.info("✅ Celery configuration loaded successfully")