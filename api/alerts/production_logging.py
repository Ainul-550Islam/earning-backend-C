"""
Production-grade logging configuration for alerts app
"""
import logging
import logging.config
import sys
import os
from pathlib import Path
from django.conf import settings
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import json
from datetime import datetime


class CustomJSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'process': record.process,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'tenant_id'):
            log_entry['tenant_id'] = record.tenant_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'alert_id'):
            log_entry['alert_id'] = record.alert_id
        if hasattr(record, 'execution_time'):
            log_entry['execution_time'] = record.execution_time
            
        return json.dumps(log_entry)


class AlertsLoggerAdapter(logging.LoggerAdapter):
    """Custom logger adapter for alerts context"""
    
    def process(self, msg, kwargs):
        # Add context information to log records
        extra = kwargs.get('extra', {})
        
        if hasattr(self.extra, 'user_id'):
            extra['user_id'] = self.extra.get('user_id')
        if hasattr(self.extra, 'tenant_id'):
            extra['tenant_id'] = self.extra.get('tenant_id')
        if hasattr(self.extra, 'request_id'):
            extra['request_id'] = self.extra.get('request_id')
        if hasattr(self.extra, 'alert_id'):
            extra['alert_id'] = self.extra.get('alert_id')
            
        kwargs['extra'] = extra
        return msg, kwargs


def get_production_logging_config():
    """Get production logging configuration"""
    
    # Ensure log directory exists
    log_dir = Path(settings.LOGGING_ROOT if hasattr(settings, 'LOGGING_ROOT') else '/var/log/alerts')
    log_dir.mkdir(parents=True, exist_ok=True)
    
    LOGGING_CONFIG = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
            'json': {
                '()': 'api.alerts.production_logging.CustomJSONFormatter',
            },
            'detailed': {
                'format': '{levelname} {asctime} {module} {funcName} {lineno:d} {message}',
                'style': '{',
            },
        },
        'filters': {
            'require_debug_false': {
                '()': 'django.utils.log.RequireDebugFalse',
            },
            'require_debug_true': {
                '()': 'django.utils.log.RequireDebugTrue',
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'filters': ['require_debug_true'],
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
            },
            'console_production': {
                'level': 'WARNING',
                'filters': ['require_debug_false'],
                'class': 'logging.StreamHandler',
                'formatter': 'json',
            },
            'file': {
                'level': 'INFO',
                'filters': ['require_debug_false'],
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'alerts.log',
                'maxBytes': 50 * 1024 * 1024,  # 50MB
                'backupCount': 5,
                'formatter': 'json',
            },
            'file_error': {
                'level': 'ERROR',
                'filters': ['require_debug_false'],
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'alerts_error.log',
                'maxBytes': 50 * 1024 * 1024,  # 50MB
                'backupCount': 10,
                'formatter': 'json',
            },
            'file_alerts': {
                'level': 'INFO',
                'filters': ['require_debug_false'],
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'alerts_business.log',
                'maxBytes': 100 * 1024 * 1024,  # 100MB
                'backupCount': 7,
                'formatter': 'json',
            },
            'file_performance': {
                'level': 'INFO',
                'filters': ['require_debug_false'],
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_dir / 'alerts_performance.log',
                'maxBytes': 50 * 1024 * 1024,  # 50MB
                'backupCount': 5,
                'formatter': 'json',
            },
            'mail_admins': {
                'level': 'ERROR',
                'filters': ['require_debug_false'],
                'class': 'django.utils.log.AdminEmailHandler',
                'formatter': 'detailed',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['mail_admins', 'file_error'],
                'level': 'ERROR',
                'propagate': False,
            },
            'alerts': {
                'handlers': ['console', 'file', 'file_alerts', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'api.alerts.models': {
                'handlers': ['file_alerts'],
                'level': 'INFO',
                'propagate': False,
            },
            'api.alerts.views': {
                'handlers': ['file_alerts'],
                'level': 'INFO',
                'propagate': False,
            },
            'api.alerts.tasks': {
                'handlers': ['file_alerts', 'file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'api.alerts.throttling': {
                'handlers': ['file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'api.alerts.middleware': {
                'handlers': ['file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery': {
                'handlers': ['console', 'file', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.task': {
                'handlers': ['file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'redis': {
                'handlers': ['file', 'file_error'],
                'level': 'WARNING',
                'propagate': False,
            },
        },
        'root': {
            'handlers': ['console_production', 'file', 'file_error'],
            'level': 'WARNING',
        },
    }
    
    return LOGGING_CONFIG


def configure_sentry():
    """Configure Sentry for error tracking and performance monitoring"""
    
    # Check if Sentry DSN is configured
    sentry_dsn = getattr(settings, 'SENTRY_DSN', None)
    if not sentry_dsn:
        print("Sentry DSN not configured - skipping Sentry integration")
        return
    
    # Configure Sentry logging integration
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.WARNING  # Send warnings as events
    )
    
    # Initialize Sentry SDK
    sentry_init(
        dsn=sentry_dsn,
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_sp=True,
                signals_sp=True,
            ),
            CeleryIntegration(
                monitor_beat_tasks=True,
                propagate_traces=True,
            ),
            RedisIntegration(),
            sentry_logging,
        ],
        
        # Performance monitoring
        traces_sample_rate=getattr(settings, 'SENTRY_TRACES_SAMPLE_RATE', 0.1),
        
        # Environment info
        environment=getattr(settings, 'ENVIRONMENT', 'development'),
        release=getattr(settings, 'ALERTS_VERSION', '1.0.0'),
        
        # Before send callback for filtering
        before_send=lambda event, hint: _filter_sentry_event(event, hint),
        
        # User feedback
        send_default_pii=True,
        
        # Debug mode (only in development)
        debug=getattr(settings, 'DEBUG', False),
    )
    
    print("Sentry integration configured successfully")


def _filter_sentry_event(event, hint):
    """Filter Sentry events before sending"""
    
    # Filter out certain exceptions
    exc_info = hint.get('exc_info')
    if exc_info:
        exc_type, exc_value, exc_traceback = exc_info
        
        # Don't send HTTP 404 errors to Sentry
        if hasattr(exc_value, 'status_code') and exc_value.status_code == 404:
            return None
        
        # Don't send certain Django exceptions
        if exc_type.__name__ in ['PermissionDenied', 'SuspiciousOperation']:
            return None
    
    # Add custom context
    event['contexts'] = event.get('contexts', {})
    event['contexts']['app'] = {
        'version': getattr(settings, 'ALERTS_VERSION', '1.0.0'),
        'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
    }
    
    return event


def setup_production_logging():
    """Setup production logging configuration"""
    
    # Configure logging
    logging.config.dictConfig(get_production_logging_config())
    
    # Configure Sentry
    configure_sentry()
    
    # Create logger for alerts
    logger = logging.getLogger('alerts')
    
    # Log startup message
    logger.info(
        "Alerts system logging initialized",
        extra={
            'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
            'version': getattr(settings, 'ALERTS_VERSION', '1.0.0'),
            'debug_mode': getattr(settings, 'DEBUG', False)
        }
    )
    
    return logger


def get_alerts_logger(name='alerts', **context):
    """Get a contextual logger for alerts"""
    
    logger = logging.getLogger(name)
    
    if context:
        return AlertsLoggerAdapter(logger, context)
    
    return logger


# Performance monitoring decorator
def log_performance(func):
    """Decorator to log function performance"""
    def wrapper(*args, **kwargs):
        logger = get_alerts_logger('alerts.performance')
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.info(
                f"Function {func.__name__} completed successfully",
                extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'success': True
                }
            )
            
            return result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            
            logger.error(
                f"Function {func.__name__} failed with error: {str(e)}",
                extra={
                    'function': func.__name__,
                    'execution_time': execution_time,
                    'success': False,
                    'error': str(e)
                },
                exc_info=True
            )
            
            raise
    
    return wrapper


# Alert-specific logging functions
def log_alert_event(event_type, alert_id, user_id=None, tenant_id=None, **kwargs):
    """Log alert-specific events"""
    logger = get_alerts_logger('alerts.business')
    
    logger.info(
        f"Alert event: {event_type}",
        extra={
            'alert_id': alert_id,
            'user_id': user_id,
            'tenant_id': tenant_id,
            'event_type': event_type,
            **kwargs
        }
    )


def log_throttling_event(request_path, user_id, limit_info, **kwargs):
    """Log throttling events"""
    logger = get_alerts_logger('api.alerts.throttling')
    
    logger.warning(
        f"Rate limit exceeded for {request_path}",
        extra={
            'request_path': request_path,
            'user_id': user_id,
            'limit': limit_info.get('limit'),
            'remaining': limit_info.get('remaining'),
            'retry_after': limit_info.get('retry_after'),
            **kwargs
        }
    )


def log_celery_task(task_name, task_id, status, **kwargs):
    """Log Celery task events"""
    logger = get_alerts_logger('api.alerts.tasks')
    
    log_level = logging.INFO if status == 'success' else logging.ERROR
    
    logger.log(
        log_level,
        f"Celery task {task_name} {status}",
        extra={
            'task_name': task_name,
            'task_id': task_id,
            'status': status,
            **kwargs
        }
    )
