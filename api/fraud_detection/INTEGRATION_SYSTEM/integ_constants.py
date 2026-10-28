# =============================================================================
# INTEGRATION_SYSTEM/integ_constants.py
# =============================================================================
"""
Integration System Constants and Configuration.

Provides centralized constants, enums, and configuration values
for the integration system.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Tuple, Any


class IntegrationType(Enum):
    """Types of integrations supported by the system."""
    API = "api"
    WEBHOOK = "webhook"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    FILE_TRANSFER = "file_transfer"
    EMAIL = "email"
    SMS = "sms"
    CUSTOM = "custom"


class IntegrationStatus(Enum):
    """Status of integration adapters."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"
    PENDING = "pending"
    MAINTENANCE = "maintenance"


class AuthenticationType(Enum):
    """Authentication types for integrations."""
    NONE = "none"
    BEARER_TOKEN = "bearer_token"
    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    CERTIFICATE = "certificate"
    CUSTOM = "custom"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class LogLevel(Enum):
    """Log levels for integration logging."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Priority(Enum):
    """Priority levels for integration operations."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


class DataFormat(Enum):
    """Supported data formats."""
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    YAML = "yaml"
    BINARY = "binary"
    TEXT = "text"


class HttpMethod(Enum):
    """HTTP methods."""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


# Default Configuration Values
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RATE_LIMIT = 1000
DEFAULT_RATE_LIMIT_WINDOW = 60
DEFAULT_CACHE_TTL = 3600
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_CONCURRENT = 50

# Circuit Breaker Defaults
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60
DEFAULT_CIRCUIT_BREAKER_EXPECTED_ERROR = "IntegrationConnectionError"

# Performance Monitoring Defaults
DEFAULT_PERFORMANCE_SAMPLE_SIZE = 1000
DEFAULT_PERFORMANCE_WINDOW_MINUTES = 60
DEFAULT_SLOW_REQUEST_THRESHOLD = 5.0
DEFAULT_ERROR_RATE_THRESHOLD = 0.1

# Health Check Defaults
DEFAULT_HEALTH_CHECK_INTERVAL = 30
DEFAULT_HEALTH_CHECK_TIMEOUT = 10
DEFAULT_HEALTH_CHECK_RETRIES = 3

# Webhook Defaults
DEFAULT_WEBHOOK_TIMEOUT = 30
DEFAULT_WEBHOOK_RETRY_ATTEMPTS = 3
DEFAULT_WEBHOOK_SIGNATURE_ALGORITHM = "sha256"

# Message Queue Defaults
DEFAULT_QUEUE_SIZE = 10000
DEFAULT_MESSAGE_TTL = 3600
DEFAULT_DEAD_LETTER_QUEUE = "dead_letter"

# Cache Keys
CACHE_KEYS = {
    'integration_config': 'integ_config_{name}',
    'integration_status': 'integ_status_{name}',
    'adapter_instance': 'integ_adapter_{name}',
    'circuit_breaker': 'integ_cb_{name}',
    'rate_limit': 'integ_rl_{name}',
    'health_check': 'integ_health_{name}',
    'performance_metrics': 'integ_perf_{name}',
    'last_execution': 'integ_last_{name}',
    'error_count': 'integ_errors_{name}',
    'success_count': 'integ_success_{name}',
}

# Cache TTL Values (in seconds)
CACHE_TTL = {
    'integration_config': 3600,  # 1 hour
    'integration_status': 300,   # 5 minutes
    'adapter_instance': 1800,    # 30 minutes
    'circuit_breaker': 300,     # 5 minutes
    'rate_limit': 60,           # 1 minute
    'health_check': 300,        # 5 minutes
    'performance_metrics': 300,  # 5 minutes
    'last_execution': 60,       # 1 minute
    'error_count': 300,         # 5 minutes
    'success_count': 300,       # 5 minutes
}

# HTTP Status Codes
HTTP_STATUS_CODES = {
    'OK': 200,
    'CREATED': 201,
    'ACCEPTED': 202,
    'NO_CONTENT': 204,
    'BAD_REQUEST': 400,
    'UNAUTHORIZED': 401,
    'FORBIDDEN': 403,
    'NOT_FOUND': 404,
    'METHOD_NOT_ALLOWED': 405,
    'CONFLICT': 409,
    'RATE_LIMITED': 429,
    'INTERNAL_SERVER_ERROR': 500,
    'BAD_GATEWAY': 502,
    'SERVICE_UNAVAILABLE': 503,
    'GATEWAY_TIMEOUT': 504,
}

# Retry Strategies
RETRY_STRATEGIES = {
    'exponential_backoff': {
        'base_delay': 1.0,
        'max_delay': 60.0,
        'multiplier': 2.0,
        'jitter': True
    },
    'linear_backoff': {
        'base_delay': 1.0,
        'max_delay': 30.0,
        'increment': 1.0,
        'jitter': False
    },
    'fixed_delay': {
        'delay': 1.0,
        'jitter': False
    },
    'no_retry': {
        'enabled': False
    }
}

# Rate Limiting Strategies
RATE_LIMITING_STRATEGIES = {
    'sliding_window': {
        'window_size': 60,
        'max_requests': 1000
    },
    'fixed_window': {
        'window_size': 60,
        'max_requests': 1000
    },
    'token_bucket': {
        'bucket_size': 1000,
        'refill_rate': 100,
        'refill_interval': 1
    }
}

# Data Transformation Rules
TRANSFORMATION_RULES = {
    'json_to_xml': {
        'root_element': 'data',
        'attribute_prefix': '@',
        'text_element': '#text'
    },
    'xml_to_json': {
        'strip_namespaces': True,
        'convert_attributes': True,
        'text_key': '#text'
    },
    'csv_to_json': {
        'delimiter': ',',
        'quote_char': '"',
        'escape_char': '\\',
        'headers': True
    },
    'json_to_csv': {
        'delimiter': ',',
        'quote_char': '"',
        'include_headers': True
    }
}

# Validation Rules
VALIDATION_RULES = {
    'email': {
        'pattern': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'required': True
    },
    'url': {
        'pattern': r'^https?://[^\s/$.?#].[^\s]*$',
        'required': True
    },
    'api_key': {
        'min_length': 16,
        'max_length': 256,
        'pattern': r'^[a-zA-Z0-9_-]+$'
    },
    'integration_name': {
        'min_length': 3,
        'max_length': 50,
        'pattern': r'^[a-zA-Z0-9_-]+$'
    }
}

# Error Codes
ERROR_CODES = {
    'INTEGRATION_NOT_FOUND': 'INT_001',
    'ADAPTER_CREATION_FAILED': 'INT_002',
    'CONNECTION_FAILED': 'INT_003',
    'AUTHENTICATION_FAILED': 'INT_004',
    'VALIDATION_FAILED': 'INT_005',
    'TIMEOUT_OCCURRED': 'INT_006',
    'RATE_LIMIT_EXCEEDED': 'INT_007',
    'CIRCUIT_BREAKER_OPEN': 'INT_008',
    'TRANSFORMATION_FAILED': 'INT_009',
    'VERSION_MISMATCH': 'INT_010',
    'CONFIGURATION_INVALID': 'INT_011',
    'PERMISSION_DENIED': 'INT_012',
    'QUOTA_EXCEEDED': 'INT_013',
    'SERVICE_UNAVAILABLE': 'INT_014',
    'DATA_CORRUPTION': 'INT_015',
}

# Event Types
EVENT_TYPES = {
    'integration_lifecycle': [
        'integration_registered',
        'integration_unregistered',
        'integration_updated',
        'integration_enabled',
        'integration_disabled'
    ],
    'execution_events': [
        'execution_started',
        'execution_completed',
        'execution_failed',
        'execution_timeout',
        'execution_retry'
    ],
    'performance_events': [
        'slow_request',
        'error_spike',
        'throughput_drop',
        'latency_increase'
    ],
    'health_events': [
        'health_check_started',
        'health_check_completed',
        'health_check_failed',
        'service_degraded',
        'service_restored'
    ],
    'circuit_breaker_events': [
        'circuit_breaker_opened',
        'circuit_breaker_closed',
        'circuit_breaker_half_open'
    ]
}

# Metrics Names
METRICS_NAMES = {
    'request_count': 'integration_requests_total',
    'success_count': 'integration_success_total',
    'error_count': 'integration_errors_total',
    'request_duration': 'integration_request_duration_seconds',
    'active_connections': 'integration_active_connections',
    'queue_size': 'integration_queue_size',
    'throughput': 'integration_throughput_requests_per_second',
    'error_rate': 'integration_error_rate',
    'availability': 'integration_availability_ratio'
}

# Monitoring Thresholds
MONITORING_THRESHOLDS = {
    'error_rate_warning': 0.05,  # 5%
    'error_rate_critical': 0.1,   # 10%
    'latency_warning': 2.0,      # 2 seconds
    'latency_critical': 5.0,     # 5 seconds
    'availability_warning': 0.99, # 99%
    'availability_critical': 0.95, # 95%
    'queue_size_warning': 1000,
    'queue_size_critical': 5000,
    'connection_pool_warning': 0.8,  # 80%
    'connection_pool_critical': 0.95, # 95%
}

# Security Settings
SECURITY_SETTINGS = {
    'max_request_size': 10485760,  # 10MB
    'max_response_size': 10485760, # 10MB
    'allowed_http_methods': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    'allowed_content_types': ['application/json', 'application/xml', 'text/plain'],
    'require_https': True,
    'validate_ssl': True,
    'timeout_ssl': 10,
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'max_log_size': 104857600,  # 100MB
    'backup_count': 5,
    'enable_structured_logging': True,
    'log_requests': True,
    'log_responses': False,
    'log_headers': False,
    'log_body': False,
}

# Feature Flags
FEATURE_FLAGS = {
    'enable_circuit_breaker': True,
    'enable_rate_limiting': True,
    'enable_retry': True,
    'enable_caching': True,
    'enable_monitoring': True,
    'enable_health_checks': True,
    'enable_fallback': True,
    'enable_versioning': True,
    'enable_audit_logging': True,
    'enable_performance_tracking': True,
    'enable_signal_emission': True,
}

# Environment-specific Settings
ENVIRONMENT_SETTINGS = {
    'development': {
        'debug': True,
        'log_level': 'DEBUG',
        'timeout': 60,
        'retry_attempts': 1,
        'enable_monitoring': False,
    },
    'testing': {
        'debug': True,
        'log_level': 'INFO',
        'timeout': 30,
        'retry_attempts': 0,
        'enable_monitoring': False,
    },
    'staging': {
        'debug': False,
        'log_level': 'INFO',
        'timeout': 30,
        'retry_attempts': 2,
        'enable_monitoring': True,
    },
    'production': {
        'debug': False,
        'log_level': 'WARNING',
        'timeout': 30,
        'retry_attempts': 3,
        'enable_monitoring': True,
    }
}

# Integration Type Specific Defaults
INTEGRATION_TYPE_DEFAULTS = {
    IntegrationType.API: {
        'timeout': 30,
        'retry_attempts': 3,
        'authentication_type': AuthenticationType.NONE,
        'rate_limit': 1000,
    },
    IntegrationType.WEBHOOK: {
        'timeout': 30,
        'retry_attempts': 3,
        'authentication_type': AuthenticationType.NONE,
        'rate_limit': 100,
    },
    IntegrationType.DATABASE: {
        'timeout': 60,
        'retry_attempts': 2,
        'authentication_type': AuthenticationType.BASIC_AUTH,
        'rate_limit': 500,
    },
    IntegrationType.MESSAGE_QUEUE: {
        'timeout': 30,
        'retry_attempts': 3,
        'authentication_type': AuthenticationType.NONE,
        'rate_limit': 10000,
    },
    IntegrationType.FILE_TRANSFER: {
        'timeout': 300,
        'retry_attempts': 2,
        'authentication_type': AuthenticationType.API_KEY,
        'rate_limit': 50,
    },
    IntegrationType.EMAIL: {
        'timeout': 60,
        'retry_attempts': 3,
        'authentication_type': AuthenticationType.BASIC_AUTH,
        'rate_limit': 100,
    },
    IntegrationType.SMS: {
        'timeout': 30,
        'retry_attempts': 3,
        'authentication_type': AuthenticationType.API_KEY,
        'rate_limit': 1000,
    },
}

# Utility Functions
def get_integration_type_choices() -> List[Tuple[str, str]]:
    """Get integration type choices for forms."""
    return [(itype.value, itype.name.replace('_', ' ').title()) for itype in IntegrationType]


def get_authentication_type_choices() -> List[Tuple[str, str]]:
    """Get authentication type choices for forms."""
    return [(atype.value, atype.name.replace('_', ' ').title()) for atype in AuthenticationType]


def get_status_choices() -> List[Tuple[str, str]]:
    """Get status choices for forms."""
    return [(status.value, status.title()) for status in IntegrationStatus]


def get_http_method_choices() -> List[Tuple[str, str]]:
    """Get HTTP method choices for forms."""
    return [(method.value, method.value) for method in HttpMethod]


def get_log_level_choices() -> List[Tuple[str, str]]:
    """Get log level choices for forms."""
    return [(level.value, level.value.upper()) for level in LogLevel]


def get_priority_choices() -> List[Tuple[str, str]]:
    """Get priority choices for forms."""
    return [(priority.value, priority.name.title()) for priority in Priority]


def get_default_config(integration_type: IntegrationType) -> Dict[str, Any]:
    """Get default configuration for integration type."""
    return INTEGRATION_TYPE_DEFAULTS.get(integration_type, {}).copy()


def get_error_code_description(error_code: str) -> str:
    """Get description for error code."""
    descriptions = {
        'INT_001': 'Integration not found in registry',
        'INT_002': 'Failed to create integration adapter',
        'INT_003': 'Connection to integration failed',
        'INT_004': 'Authentication with integration failed',
        'INT_005': 'Request validation failed',
        'INT_006': 'Request timeout occurred',
        'INT_007': 'Rate limit exceeded',
        'INT_008': 'Circuit breaker is open',
        'INT_009': 'Data transformation failed',
        'INT_010': 'Version mismatch detected',
        'INT_011': 'Invalid configuration provided',
        'INT_012': 'Permission denied for operation',
        'INT_013': 'Quota exceeded',
        'INT_014': 'Service unavailable',
        'INT_015': 'Data corruption detected',
    }
    return descriptions.get(error_code, 'Unknown error')


def is_success_status_code(status_code: int) -> bool:
    """Check if HTTP status code indicates success."""
    return 200 <= status_code < 300


def is_client_error_status_code(status_code: int) -> bool:
    """Check if HTTP status code indicates client error."""
    return 400 <= status_code < 500


def is_server_error_status_code(status_code: int) -> bool:
    """Check if HTTP status code indicates server error."""
    return 500 <= status_code < 600


def should_retry_status_code(status_code: int) -> bool:
    """Check if request should be retried based on status code."""
    # Retry on server errors and rate limiting
    return is_server_error_status_code(status_code) or status_code == 429


def get_retry_delay(attempt: int, strategy: str = 'exponential_backoff') -> float:
    """Calculate retry delay based on strategy and attempt number."""
    config = RETRY_STRATEGIES.get(strategy, RETRY_STRATEGIES['exponential_backoff'])
    
    if strategy == 'exponential_backoff':
        delay = config['base_delay'] * (config['multiplier'] ** attempt)
        delay = min(delay, config['max_delay'])
        if config.get('jitter', False):
            import random
            delay *= (0.5 + random.random() * 0.5)
    elif strategy == 'linear_backoff':
        delay = min(config['base_delay'] + (attempt * config['increment']), config['max_delay'])
        if config.get('jitter', False):
            import random
            delay *= (0.5 + random.random() * 0.5)
    elif strategy == 'fixed_delay':
        delay = config['delay']
    else:
        delay = 1.0
    
    return delay


def validate_integration_name(name: str) -> bool:
    """Validate integration name format."""
    import re
    pattern = VALIDATION_RULES['integration_name']['pattern']
    min_length = VALIDATION_RULES['integration_name']['min_length']
    max_length = VALIDATION_RULES['integration_name']['max_length']
    
    return (
        isinstance(name, str) and
        min_length <= len(name) <= max_length and
        re.match(pattern, name) is not None
    )


def validate_api_key(api_key: str) -> bool:
    """Validate API key format."""
    import re
    pattern = VALIDATION_RULES['api_key']['pattern']
    min_length = VALIDATION_RULES['api_key']['min_length']
    max_length = VALIDATION_RULES['api_key']['max_length']
    
    return (
        isinstance(api_key, str) and
        min_length <= len(api_key) <= max_length and
        re.match(pattern, api_key) is not None
    )


def validate_email(email: str) -> bool:
    """Validate email format."""
    import re
    pattern = VALIDATION_RULES['email']['pattern']
    
    return isinstance(email, str) and re.match(pattern, email) is not None


def validate_url(url: str) -> bool:
    """Validate URL format."""
    import re
    pattern = VALIDATION_RULES['url']['pattern']
    
    return isinstance(url, str) and re.match(pattern, url) is not None


def get_cache_key(key_type: str, name: str) -> str:
    """Get formatted cache key."""
    return CACHE_KEYS[key_type].format(name=name)


def get_metric_name(metric_type: str) -> str:
    """Get formatted metric name."""
    return METRICS_NAMES[metric_type]


def get_environment_settings(environment: str) -> Dict[str, Any]:
    """Get environment-specific settings."""
    return ENVIRONMENT_SETTINGS.get(environment.lower(), ENVIRONMENT_SETTINGS['production'])
