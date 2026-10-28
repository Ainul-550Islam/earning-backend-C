# engagement/integration_system/integ_constants.py
"""
Integration system constants and configuration.
Defines all constants used across the integration system.
"""

from enum import Enum
from typing import Dict, Any


class IntegrationType(Enum):
    """Types of integrations supported."""
    WEBHOOK = "webhook"
    API = "api"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    FILE_SYSTEM = "file_system"
    EMAIL = "email"
    SMS = "sms"
    PUSH_NOTIFICATION = "push_notification"
    THIRD_PARTY = "third_party"
    INTERNAL = "internal"


class IntegrationStatus(Enum):
    """Status of integrations."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"
    TESTING = "testing"


class EventPriority(Enum):
    """Priority levels for integration events."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    URGENT = "urgent"


class DataType(Enum):
    """Data types for integration."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    TEXT = "text"
    BINARY = "binary"
    FORM_DATA = "form_data"


class HttpMethod(Enum):
    """HTTP methods for API integrations."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class RetryStrategy(Enum):
    """Retry strategies for failed integrations."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_INTERVAL = "fixed_interval"
    NO_RETRY = "no_retry"


# Default configuration values
DEFAULT_CONFIG = {
    'TIMEOUT': 30,  # seconds
    'MAX_RETRIES': 3,
    'RETRY_DELAY': 1,  # seconds
    'BATCH_SIZE': 100,
    'MAX_BATCH_SIZE': 1000,
    'RATE_LIMIT': 100,  # requests per minute
    'CIRCUIT_BREAKER_THRESHOLD': 5,
    'CIRCUIT_BREAKER_TIMEOUT': 60,  # seconds
    'HEALTH_CHECK_INTERVAL': 300,  # seconds
    'AUDIT_RETENTION_DAYS': 90,
    'METRICS_RETENTION_DAYS': 30,
}

# Integration type configurations
INTEGRATION_TYPE_CONFIG = {
    IntegrationType.WEBHOOK: {
        'default_timeout': 30,
        'max_retries': 3,
        'retry_strategy': RetryStrategy.EXPONENTIAL_BACKOFF,
        'supported_methods': [HttpMethod.POST, HttpMethod.GET],
        'data_types': [DataType.JSON, DataType.FORM_DATA],
    },
    IntegrationType.API: {
        'default_timeout': 60,
        'max_retries': 5,
        'retry_strategy': RetryStrategy.EXPONENTIAL_BACKOFF,
        'supported_methods': list(HttpMethod),
        'data_types': [DataType.JSON, DataType.XML, DataType.FORM_DATA],
    },
    IntegrationType.DATABASE: {
        'default_timeout': 30,
        'max_retries': 2,
        'retry_strategy': RetryStrategy.LINEAR_BACKOFF,
        'connection_pool_size': 10,
        'data_types': [DataType.JSON, DataType.TEXT],
    },
    IntegrationType.MESSAGE_QUEUE: {
        'default_timeout': 300,
        'max_retries': 3,
        'retry_strategy': RetryStrategy.EXPONENTIAL_BACKOFF,
        'queue_size_limit': 10000,
        'data_types': [DataType.JSON, DataType.TEXT],
    },
    IntegrationType.EMAIL: {
        'default_timeout': 120,
        'max_retries': 3,
        'retry_strategy': RetryStrategy.LINEAR_BACKOFF,
        'max_attachment_size': 25 * 1024 * 1024,  # 25MB
        'data_types': [DataType.TEXT, DataType.BINARY],
    },
    IntegrationType.SMS: {
        'default_timeout': 60,
        'max_retries': 3,
        'retry_strategy': RetryStrategy.FIXED_INTERVAL,
        'max_message_length': 1600,
        'data_types': [DataType.TEXT],
    },
    IntegrationType.PUSH_NOTIFICATION: {
        'default_timeout': 30,
        'max_retries': 2,
        'retry_strategy': RetryStrategy.NO_RETRY,
        'max_payload_size': 4096,
        'data_types': [DataType.JSON],
    },
}

# Event type mappings
EVENT_TYPE_MAPPING = {
    'user_created': EventPriority.HIGH,
    'user_updated': EventPriority.NORMAL,
    'user_deleted': EventPriority.HIGH,
    'checkin_completed': EventPriority.NORMAL,
    'quest_completed': EventPriority.HIGH,
    'achievement_unlocked': EventPriority.HIGH,
    'purchase_completed': EventPriority.HIGH,
    'system_error': EventPriority.CRITICAL,
    'security_alert': EventPriority.CRITICAL,
    'data_sync': EventPriority.NORMAL,
    'backup_completed': EventPriority.LOW,
}

# Error codes
ERROR_CODES = {
    'INTEGRATION_NOT_FOUND': 'INT_001',
    'INVALID_CONFIGURATION': 'INT_002',
    'CONNECTION_FAILED': 'INT_003',
    'AUTHENTICATION_FAILED': 'INT_004',
    'PERMISSION_DENIED': 'INT_005',
    'DATA_VALIDATION_FAILED': 'INT_006',
    'TIMEOUT_EXCEEDED': 'INT_007',
    'RATE_LIMIT_EXCEEDED': 'INT_008',
    'CIRCUIT_BREAKER_OPEN': 'INT_009',
    'TRANSFORMATION_FAILED': 'INT_010',
    'VERSION_MISMATCH': 'INT_011',
    'DEPENDENCY_FAILED': 'INT_012',
    'DATA_CORRUPTION': 'INT_013',
    'SYSTEM_OVERLOADED': 'INT_014',
    'MAINTENANCE_MODE': 'INT_015',
}

# Success codes
SUCCESS_CODES = {
    'INTEGRATION_SUCCESS': 'INT_200',
    'DATA_PROCESSED': 'INT_201',
    'TRANSFORMATION_SUCCESS': 'INT_202',
    'CACHE_HIT': 'INT_203',
    'QUEUED_SUCCESS': 'INT_204',
}

# HTTP status code mappings
HTTP_STATUS_MAPPING = {
    200: SUCCESS_CODES['INTEGRATION_SUCCESS'],
    201: SUCCESS_CODES['DATA_PROCESSED'],
    400: ERROR_CODES['DATA_VALIDATION_FAILED'],
    401: ERROR_CODES['AUTHENTICATION_FAILED'],
    403: ERROR_CODES['PERMISSION_DENIED'],
    404: ERROR_CODES['INTEGRATION_NOT_FOUND'],
    408: ERROR_CODES['TIMEOUT_EXCEEDED'],
    429: ERROR_CODES['RATE_LIMIT_EXCEEDED'],
    500: ERROR_CODES['CONNECTION_FAILED'],
    502: ERROR_CODES['DEPENDENCY_FAILED'],
    503: ERROR_CODES['SYSTEM_OVERLOADED'],
    504: ERROR_CODES['TIMEOUT_EXCEEDED'],
}

# Circuit breaker states
class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# Data transformation rules
TRANSFORMATION_RULES = {
    'date_format': '%Y-%m-%dT%H:%M:%SZ',
    'timezone': 'UTC',
    'encoding': 'utf-8',
    'null_values': [None, '', 'null', 'NULL'],
    'boolean_mapping': {
        'true': True,
        'false': False,
        '1': True,
        '0': False,
        'yes': True,
        'no': False,
    },
}

# Security constants
SECURITY_CONFIG = {
    'MAX_REQUEST_SIZE': 10 * 1024 * 1024,  # 10MB
    'ALLOWED_ORIGINS': ['*'],  # Configure based on requirements
    'RATE_LIMIT_WINDOWS': {
        'minute': 60,
        'hour': 3600,
        'day': 86400,
    },
    'ENCRYPTION_ALGORITHM': 'AES-256-GCM',
    'HASH_ALGORITHM': 'SHA-256',
}

# Monitoring constants
MONITORING_CONFIG = {
    'METRICS_COLLECTION_INTERVAL': 60,  # seconds
    'HEALTH_CHECK_TIMEOUT': 10,  # seconds
    'PERFORMANCE_THRESHOLD': {
        'response_time_ms': 1000,
        'error_rate_percent': 5,
        'throughput_rpm': 1000,
    },
    'ALERT_THRESHOLDS': {
        'error_rate': 0.1,  # 10%
        'response_time': 5000,  # 5 seconds
        'circuit_breaker_trips': 3,
    },
}

# Cache keys
CACHE_KEYS = {
    'INTEGRATION_CONFIG': 'integ_config:{integration_id}',
    'CIRCUIT_BREAKER_STATE': 'cb_state:{integration_id}',
    'RATE_LIMIT': 'rate_limit:{integration_id}:{window}',
    'HEALTH_CHECK': 'health:{integration_id}',
    'TRANSFORMATION_CACHE': 'transform:{source}:{target}:{hash}',
    'METRICS': 'metrics:{integration_id}:{metric_type}',
}

# Queue names
QUEUE_NAMES = {
    'DEFAULT': 'integration_default',
    'HIGH_PRIORITY': 'integration_high',
    'LOW_PRIORITY': 'integration_low',
    'RETRY': 'integration_retry',
    'DEAD_LETTER': 'integration_dead_letter',
    'WEBHOOK': 'webhook_queue',
    'API': 'api_queue',
    'BATCH': 'batch_queue',
}

# Logging configuration
LOGGING_CONFIG = {
    'FORMAT': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'LEVEL': 'INFO',
    'HANDLERS': ['console', 'file'],
    'FILE_PATH': 'logs/integration_system.log',
    'MAX_FILE_SIZE': 100 * 1024 * 1024,  # 100MB
    'BACKUP_COUNT': 5,
    'LOG_LEVELS': {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50,
    },
}

# Version compatibility
VERSION_COMPATIBILITY = {
    'CURRENT_VERSION': '1.0.0',
    'SUPPORTED_VERSIONS': ['1.0.0'],
    'DEPRECATED_VERSIONS': ['0.9.x'],
    'MINIMUM_COMPATIBLE_VERSION': '1.0.0',
}

# Environment-specific configurations
ENVIRONMENT_CONFIG = {
    'development': {
        'DEBUG': True,
        'TIMEOUT': 10,
        'MAX_RETRIES': 1,
        'LOG_LEVEL': 'DEBUG',
        'RATE_LIMIT': 1000,
    },
    'staging': {
        'DEBUG': True,
        'TIMEOUT': 20,
        'MAX_RETRIES': 2,
        'LOG_LEVEL': 'INFO',
        'RATE_LIMIT': 500,
    },
    'production': {
        'DEBUG': False,
        'TIMEOUT': 30,
        'MAX_RETRIES': 3,
        'LOG_LEVEL': 'WARNING',
        'RATE_LIMIT': 100,
    },
}

# Integration categories
INTEGRATION_CATEGORIES = {
    'COMMUNICATION': ['email', 'sms', 'push_notification', 'webhook'],
    'DATA_STORAGE': ['database', 'file_system'],
    'PROCESSING': ['api', 'message_queue'],
    'ANALYTICS': ['third_party'],
    'INTERNAL': ['internal'],
}

# Default headers for HTTP integrations
DEFAULT_HTTP_HEADERS = {
    'User-Agent': 'Engagement-Integration-System/1.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'X-Integration-Version': '1.0.0',
}

# Transformation templates
TRANSFORMATION_TEMPLATES = {
    'user_profile': {
        'source_fields': ['id', 'username', 'email', 'created_at'],
        'target_fields': ['user_id', 'name', 'email_address', 'registration_date'],
        'field_mappings': {
            'id': 'user_id',
            'username': 'name',
            'email': 'email_address',
            'created_at': 'registration_date',
        },
    },
    'checkin_data': {
        'source_fields': ['user_id', 'date', 'coins_earned', 'xp_earned'],
        'target_fields': ['user', 'checkin_date', 'coins', 'experience'],
        'field_mappings': {
            'user_id': 'user',
            'date': 'checkin_date',
            'coins_earned': 'coins',
            'xp_earned': 'experience',
        },
    },
}

# Validation rules
VALIDATION_RULES = {
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'phone': r'^\+?1?-?\.?\s?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$',
    'uuid': r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    'json_schema': True,  # Enable JSON schema validation
}

# Integration priorities
INTEGRATION_PRIORITIES = {
    EventPriority.LOW: 1,
    EventPriority.NORMAL: 2,
    EventPriority.HIGH: 3,
    EventPriority.CRITICAL: 4,
    EventPriority.URGENT: 5,
}

# Batch processing settings
BATCH_CONFIG = {
    'DEFAULT_BATCH_SIZE': 100,
    'MAX_BATCH_SIZE': 1000,
    'MIN_BATCH_SIZE': 1,
    'BATCH_TIMEOUT': 300,  # seconds
    'MAX_BATCH_AGE': 3600,  # seconds
    'BATCH_RETRY_LIMIT': 3,
}

# Health check endpoints
HEALTH_CHECK_ENDPOINTS = {
    'database': '/health/db',
    'cache': '/health/cache',
    'message_queue': '/health/queue',
    'external_services': '/health/external',
    'system': '/health/system',
}

# Fallback configurations
FALLBACK_CONFIG = {
    'ENABLE_FALLBACK': True,
    'FALLBACK_TIMEOUT': 5,  # seconds
    'MAX_FALLBACK_ATTEMPTS': 3,
    'FALLBACK_STRATEGY': 'graceful_degradation',
}

# Integration metadata
INTEGRATION_METADATA = {
    'created_at': 'auto',
    'updated_at': 'auto',
    'version': '1.0.0',
    'author': 'engagement_system',
    'tags': ['engagement', 'integration', 'gamification'],
}

# Export all constants for easy access
__all__ = [
    # Enums
    'IntegrationType',
    'IntegrationStatus',
    'EventPriority',
    'DataType',
    'HttpMethod',
    'RetryStrategy',
    'CircuitBreakerState',
    
    # Configuration dictionaries
    'DEFAULT_CONFIG',
    'INTEGRATION_TYPE_CONFIG',
    'EVENT_TYPE_MAPPING',
    'ERROR_CODES',
    'SUCCESS_CODES',
    'HTTP_STATUS_MAPPING',
    'TRANSFORMATION_RULES',
    'SECURITY_CONFIG',
    'MONITORING_CONFIG',
    'CACHE_KEYS',
    'QUEUE_NAMES',
    'LOGGING_CONFIG',
    'VERSION_COMPATIBILITY',
    'ENVIRONMENT_CONFIG',
    'INTEGRATION_CATEGORIES',
    'DEFAULT_HTTP_HEADERS',
    'TRANSFORMATION_TEMPLATES',
    'VALIDATION_RULES',
    'INTEGRATION_PRIORITIES',
    'BATCH_CONFIG',
    'HEALTH_CHECK_ENDPOINTS',
    'FALLBACK_CONFIG',
    'INTEGRATION_METADATA',
]
