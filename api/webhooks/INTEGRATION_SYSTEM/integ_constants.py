"""Integration Constants

This module contains constants and choices used by integration system.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class IntegrationType(models.TextChoices):
    """Integration type choices."""
    WEBHOOK = 'webhook', _('Webhook')
    API = 'api', _('API')
    DATABASE = 'database', _('Database')
    QUEUE = 'queue', _('Queue')
    EMAIL = 'email', _('Email')
    SMS = 'sms', _('SMS')
    CUSTOM = 'custom', _('Custom')


class HandlerType(models.TextChoices):
    """Handler type choices."""
    SYNC = 'sync', _('Synchronous')
    ASYNC = 'async', _('Asynchronous')
    BATCH = 'batch', _('Batch')
    STREAM = 'stream', _('Stream')
    SCHEDULED = 'scheduled', _('Scheduled')


class AdapterType(models.TextChoices):
    """Adapter type choices."""
    WEBHOOK = 'webhook', _('Webhook')
    API = 'api', _('API')
    DATABASE = 'database', _('Database')
    FILE = 'file', _('File')
    CUSTOM = 'custom', _('Custom')


class SignalType(models.TextChoices):
    """Signal type choices."""
    WEBHOOK_RECEIVED = 'webhook_received', _('Webhook Received')
    WEBHOOK_PROCESSED = 'webhook_processed', _('Webhook Processed')
    WEBHOOK_FAILED = 'webhook_failed', _('Webhook Failed')
    WEBHOOK_RETRIED = 'webhook_retried', _('Webhook Retried')
    BATCH_STARTED = 'batch_started', _('Batch Started')
    BATCH_COMPLETED = 'batch_completed', _('Batch Completed')
    BATCH_FAILED = 'batch_failed', _('Batch Failed')
    INTEGRATION_CONNECTED = 'integration_connected', _('Integration Connected')
    INTEGRATION_DISCONNECTED = 'integration_disconnected', _('Integration Disconnected')
    INTEGRATION_ERROR = 'integration_error', _('Integration Error')
    DATA_VALIDATED = 'data_validated', _('Data Validated')
    DATA_TRANSFORMED = 'data_transformed', _('Data Transformed')
    DATA_ROUTED = 'data_routed', _('Data Routed')
    PERFORMANCE_ALERT = 'performance_alert', _('Performance Alert')
    HEALTH_CHECK_FAILED = 'health_check_failed', _('Health Check Failed')
    SYSTEM_MAINTENANCE = 'system_maintenance', _('System Maintenance')


class HandlerStatus(models.TextChoices):
    """Handler status choices."""
    REGISTERED = 'registered', _('Registered')
    ACTIVE = 'active', _('Active')
    INACTIVE = 'inactive', _('Inactive')
    ERROR = 'error', _('Error')
    DISABLED = 'disabled', _('Disabled')


class BridgeType(models.TextChoices):
    """Bridge type choices."""
    EVENT_BUS = 'event_bus', _('Event Bus')
    MESSAGE_QUEUE = 'message_queue', _('Message Queue')
    DATA_PIPE = 'data_pipe', _('Data Pipe')
    STREAM = 'stream', _('Stream')
    CUSTOM = 'custom', _('Custom')


class QueueType(models.TextChoices):
    """Message queue type choices."""
    REDIS = 'redis', _('Redis')
    RABBITMQ = 'rabbitmq', _('RabbitMQ')
    KAFKA = 'kafka', _('Kafka')
    SQS = 'sqs', _('AWS SQS')
    CELERY = 'celery', _('Celery')
    CUSTOM = 'custom', _('Custom')


class ValidationType(models.TextChoices):
    """Validation type choices."""
    SCHEMA = 'schema', _('Schema Validation')
    BUSINESS = 'business', _('Business Rules')
    SECURITY = 'security', _('Security Check')
    FORMAT = 'format', _('Format Validation')
    CUSTOM = 'custom', _('Custom Validation')


class LogLevel(models.TextChoices):
    """Log level choices."""
    DEBUG = 'debug', _('Debug')
    INFO = 'info', _('Info')
    WARNING = 'warning', _('Warning')
    ERROR = 'error', _('Error')
    CRITICAL = 'critical', _('Critical')


class HealthStatus(models.TextChoices):
    """Health status choices."""
    HEALTHY = 'healthy', _('Healthy')
    UNHEALTHY = 'unhealthy', _('Unhealthy')
    DEGRADED = 'degraded', _('Degraded')
    UNKNOWN = 'unknown', _('Unknown')


class SyncStatus(models.TextChoices):
    """Sync status choices."""
    SYNCED = 'synced', _('Synced')
    PENDING = 'pending', _('Pending')
    CONFLICT = 'conflict', _('Conflict')
    ERROR = 'error', _('Error')
    IN_PROGRESS = 'in_progress', _('In Progress')


# Performance thresholds
PERFORMANCE_THRESHOLDS = {
    'response_time_ms': {
        'warning': 1000,  # 1 second
        'critical': 5000   # 5 seconds
    },
    'memory_usage_mb': {
        'warning': 512,    # 512 MB
        'critical': 1024   # 1 GB
    },
    'cpu_usage_percent': {
        'warning': 70,    # 70%
        'critical': 90    # 90%
    },
    'error_rate_percent': {
        'warning': 5,     # 5%
        'critical': 10    # 10%
    }
}

# Default configurations
DEFAULT_ADAPTER_CONFIG = {
    'timeout': 30,
    'retry_attempts': 3,
    'max_payload_size': 1024 * 1024,  # 1MB
    'enable_validation': True,
    'enable_transformation': True
}

DEFAULT_REGISTRY_CONFIG = {
    'cache_timeout': 300,  # 5 minutes
    'auto_discovery': True,
    'max_handlers': 1000,
    'max_integrations': 100
}

DEFAULT_SIGNAL_CONFIG = {
    'enabled_signals': [
        'webhook_received',
        'webhook_processed',
        'webhook_failed',
        'integration_error'
    ],
    'max_history': 1000,
    'stats_enabled': True
}

# Queue configurations
QUEUE_CONFIGS = {
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'password': None,
        'max_connections': 10
    },
    'rabbitmq': {
        'host': 'localhost',
        'port': 5672,
        'username': 'guest',
        'password': 'guest',
        'virtual_host': '/',
        'max_connections': 10
    },
    'kafka': {
        'bootstrap_servers': ['localhost:9092'],
        'topic_prefix': 'webhook',
        'max_connections': 10
    }
}

# Validation schemas
SCHEMA_DEFINITIONS = {
    'webhook': {
        'type': 'object',
        'required': ['event_type', 'payload'],
        'properties': {
            'event_type': {'type': 'string'},
            'payload': {'type': 'object'},
            'timestamp': {'type': 'string'},
            'signature': {'type': 'string'},
            'headers': {'type': 'object'}
        }
    },
    'api': {
        'type': 'object',
        'required': ['method', 'endpoint', 'data'],
        'properties': {
            'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']},
            'endpoint': {'type': 'string'},
            'data': {'type': 'object'},
            'headers': {'type': 'object'},
            'params': {'type': 'object'}
        }
    }
}

# Error codes
ERROR_CODES = {
    'HANDLER_NOT_FOUND': 'E001',
    'HANDLER_ERROR': 'E002',
    'VALIDATION_ERROR': 'E003',
    'TRANSFORMATION_ERROR': 'E004',
    'ADAPTER_ERROR': 'E005',
    'REGISTRY_ERROR': 'E006',
    'SIGNAL_ERROR': 'E007',
    'BRIDGE_ERROR': 'E008',
    'QUEUE_ERROR': 'E009',
    'AUTH_ERROR': 'E010',
    'SYNC_ERROR': 'E011'
}

# Event type mappings
EVENT_TYPE_MAPPINGS = {
    'user': ['user.created', 'user.updated', 'user.deleted'],
    'payment': ['payment.success', 'payment.failed', 'payment.pending'],
    'order': ['order.created', 'order.completed', 'order.cancelled'],
    'webhook': ['webhook.test', 'webhook.ping', 'webhook.health'],
    'system': ['system.maintenance', 'system.alert', 'system.error']
}

# Integration priorities
INTEGRATION_PRIORITIES = {
    'high': 1,
    'medium': 2,
    'low': 3,
    'critical': 0
}

# Retry policies
RETRY_POLICIES = {
    'exponential_backoff': {
        'base_delay': 1,  # seconds
        'max_delay': 300,  # 5 minutes
        'multiplier': 2
    },
    'linear_backoff': {
        'base_delay': 5,  # seconds
        'max_delay': 60,  # 1 minute
        'increment': 5
    },
    'fixed_delay': {
        'delay': 10  # seconds
    }
}

# Cache keys
CACHE_KEYS = {
    'handler_info': 'handler_info:{name}',
    'integration_info': 'integration_info:{type}',
    'adapter_status': 'adapter_status:{type}',
    'registry_stats': 'registry_stats',
    'signal_stats': 'signal_stats',
    'health_check': 'health_check'
}

# Monitoring metrics
MONITORING_METRICS = {
    'handler_performance': {
        'response_time': 'avg',
        'success_rate': 'percentage',
        'error_count': 'count',
        'usage_count': 'count'
    },
    'adapter_performance': {
        'throughput': 'rate',
        'latency': 'avg',
        'error_rate': 'percentage',
        'active_connections': 'count'
    },
    'system_performance': {
        'memory_usage': 'bytes',
        'cpu_usage': 'percentage',
        'disk_usage': 'percentage',
        'network_io': 'bytes'
    }
}

# Security settings
SECURITY_SETTINGS = {
    'max_payload_size': 10 * 1024 * 1024,  # 10MB
    'allowed_origins': ['*'],
    'rate_limit_per_minute': 1000,
    'enable_signature_validation': True,
    'enable_ip_whitelist': False,
    'default_timeout': 30
}

# Feature flags
FEATURE_FLAGS = {
    'enable_webhook_adapter': True,
    'enable_api_adapter': True,
    'enable_auto_discovery': True,
    'enable_performance_monitoring': True,
    'enable_health_checks': True,
    'enable_audit_logging': True,
    'enable_retry_mechanism': True,
    'enable_circuit_breaker': True
}
