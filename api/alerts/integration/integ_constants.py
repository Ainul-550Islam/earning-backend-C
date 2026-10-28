
# ── Validation patterns (used by data_validator and sync_manager) ─────────────
import re as _re
PATTERNS = {
    'email':    _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'),
    'phone':    _re.compile(r'^\+?[1-9]\d{1,14}$'),
    'url':      _re.compile(r'^https?://[^\s/$.?#].[^\s]*$'),
    'uuid':     _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.I),
    'ipv4':     _re.compile(r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'),
    'slug':     _re.compile(r'^[-a-zA-Z0-9_]+$'),
    'semver':   _re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$'),
}
"""
Integration constants for alerts app - Constants for external system integrations
"""
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)

# Integration types
INTEGRATION_TYPES = {
    'webhook': 'Webhook Integration',
    'api': 'REST API Integration',
    'database': 'Database Integration',
    'message_queue': 'Message Queue Integration',
    'file_transfer': 'File Transfer Integration',
    'email': 'Email Integration',
    'sms': 'SMS Integration',
    'slack': 'Slack Integration',
    'teams': 'Microsoft Teams Integration',
    'discord': 'Discord Integration',
    'telegram': 'Telegram Integration',
    'webhook': 'Webhook Integration'
}

# Integration status
INTEGRATION_STATUS = {
    'active': 'Active',
    'inactive': 'Inactive',
    'error': 'Error',
    'connecting': 'Connecting',
    'disconnecting': 'Disconnecting',
    'maintenance': 'Maintenance'
}

# Data formats
DATA_FORMATS = {
    'json': 'JSON',
    'xml': 'XML',
    'csv': 'CSV',
    'yaml': 'YAML',
    'protobuf': 'Protocol Buffers',
    'avro': 'Apache Avro',
    'parquet': 'Apache Parquet'
}

# Protocols
PROTOCOLS = {
    'http': 'HTTP',
    'https': 'HTTPS',
    'tcp': 'TCP',
    'udp': 'UDP',
    'websocket': 'WebSocket',
    'mqtt': 'MQTT',
    'amqp': 'AMQP',
    'kafka': 'Apache Kafka',
    'redis': 'Redis',
    'grpc': 'gRPC'
}

# Authentication types
AUTH_TYPES = {
    'none': 'No Authentication',
    'basic': 'Basic Authentication',
    'bearer': 'Bearer Token',
    'api_key': 'API Key',
    'oauth2': 'OAuth 2.0',
    'jwt': 'JWT Token',
    'certificate': 'Client Certificate',
    'aws_sigv4': 'AWS Signature Version 4',
    'custom': 'Custom Authentication'
}

# Error codes
ERROR_CODES = {
    'SUCCESS': 0,
    'CONNECTION_FAILED': 1001,
    'AUTHENTICATION_FAILED': 1002,
    'AUTHORIZATION_FAILED': 1003,
    'VALIDATION_FAILED': 1004,
    'TIMEOUT': 1005,
    'RATE_LIMITED': 1006,
    'SERVER_ERROR': 1007,
    'CLIENT_ERROR': 1008,
    'NETWORK_ERROR': 1009,
    'CONFIGURATION_ERROR': 1010,
    'DATA_FORMAT_ERROR': 1011,
    'PROTOCOL_ERROR': 1012,
    'UNKNOWN_ERROR': 1999
}

# Error messages
ERROR_MESSAGES = {
    ERROR_CODES['SUCCESS']: 'Operation completed successfully',
    ERROR_CODES['CONNECTION_FAILED']: 'Failed to establish connection',
    ERROR_CODES['AUTHENTICATION_FAILED']: 'Authentication credentials invalid',
    ERROR_CODES['AUTHORIZATION_FAILED']: 'Insufficient permissions',
    ERROR_CODES['VALIDATION_FAILED']: 'Data validation failed',
    ERROR_CODES['TIMEOUT']: 'Operation timed out',
    ERROR_CODES['RATE_LIMITED']: 'Rate limit exceeded',
    ERROR_CODES['SERVER_ERROR']: 'Server error occurred',
    ERROR_CODES['CLIENT_ERROR']: 'Client error occurred',
    ERROR_CODES['NETWORK_ERROR']: 'Network error occurred',
    ERROR_CODES['CONFIGURATION_ERROR']: 'Configuration error',
    ERROR_CODES['DATA_FORMAT_ERROR']: 'Data format error',
    ERROR_CODES['PROTOCOL_ERROR']: 'Protocol error occurred',
    ERROR_CODES['UNKNOWN_ERROR']: 'Unknown error occurred'
}

# Retry strategies
RETRY_STRATEGIES = {
    'fixed': 'Fixed Delay',
    'exponential_backoff': 'Exponential Backoff',
    'linear_backoff': 'Linear Backoff',
    'no_retry': 'No Retry'
}

# Default timeouts (in seconds)
DEFAULT_TIMEOUTS = {
    'connection': 30,
    'read': 60,
    'write': 60,
    'health_check': 10,
    'data_transfer': 300,
    'api_call': 30
}

# Default retry settings
DEFAULT_RETRY_SETTINGS = {
    'max_attempts': 3,
    'initial_delay': 1,
    'max_delay': 60,
    'backoff_multiplier': 2,
    'strategy': 'exponential_backoff'
}

# Data transfer settings
DATA_TRANSFER_SETTINGS = {
    'chunk_size': 1024 * 1024,  # 1MB
    'max_file_size': 100 * 1024 * 1024,  # 100MB
    'supported_extensions': ['.json', '.xml', '.csv', '.txt', '.log'],
    'compression_types': ['gzip', 'zip', 'bz2'],
    'encoding': 'utf-8'
}

# Rate limiting settings
RATE_LIMITING = {
    'default_limit': 1000,  # requests per hour
    'burst_limit': 100,     # requests per minute
    'window_size': 3600,   # 1 hour in seconds
    'cleanup_interval': 300   # 5 minutes in seconds
}

# Health check settings
HEALTH_CHECK_SETTINGS = {
    'interval': 60,          # seconds
    'timeout': 10,           # seconds
    'failure_threshold': 3,   # consecutive failures
    'recovery_threshold': 2,  # consecutive successes
    'grace_period': 30       # seconds
}

# Logging levels
LOG_LEVELS = {
    'DEBUG': 10,
    'INFO': 20,
    'WARNING': 30,
    'ERROR': 40,
    'CRITICAL': 50
}

# Event types
EVENT_TYPES = {
    'connection_established': 'Connection Established',
    'connection_lost': 'Connection Lost',
    'data_sent': 'Data Sent',
    'data_received': 'Data Received',
    'error_occurred': 'Error Occurred',
    'health_check': 'Health Check',
    'configuration_updated': 'Configuration Updated',
    'integration_enabled': 'Integration Enabled',
    'integration_disabled': 'Integration Disabled'
}

# Data flow types
DATA_FLOW_TYPES = {
    'inbound': 'Inbound Data Flow',
    'outbound': 'Outbound Data Flow',
    'bidirectional': 'Bidirectional Data Flow',
    'sync': 'Synchronous Data Flow',
    'async': 'Asynchronous Data Flow'
}

# Transformation types
TRANSFORMATION_TYPES = {
    'none': 'No Transformation',
    'field_mapping': 'Field Mapping',
    'data_type_conversion': 'Data Type Conversion',
    'format_conversion': 'Format Conversion',
    'validation': 'Data Validation',
    'enrichment': 'Data Enrichment',
    'filtering': 'Data Filtering',
    'aggregation': 'Data Aggregation'
}

# Validation rules
VALIDATION_RULES = {
    'required_fields': 'Required Fields',
    'field_types': 'Field Types',
    'field_values': 'Field Values',
    'data_structure': 'Data Structure',
    'business_rules': 'Business Rules',
    'security_rules': 'Security Rules'
}

# Security settings
SECURITY_SETTINGS = {
    'encryption_algorithms': ['AES-256', 'RSA-2048', 'ChaCha20'],
    'hash_algorithms': ['SHA-256', 'SHA-512', 'MD5'],
    'signature_algorithms': ['HMAC-SHA256', 'HMAC-SHA512', 'RSA-SHA256'],
    'certificate_types': ['PEM', 'DER', 'PKCS12'],
    'ssl_versions': ['TLSv1.2', 'TLSv1.3'],
    'cipher_suites': ['ECDHE-RSA-AES256-GCM-SHA384', 'ECDHE-RSA-AES128-GCM-SHA256']
}

# Performance monitoring settings
PERFORMANCE_MONITORING = {
    'metrics_collection_interval': 60,  # seconds
    'retention_period': 7 * 24 * 3600,  # 7 days in seconds
    'sampling_rate': 1.0,  # 100% sampling
    'buffer_size': 10000,  # number of metrics to buffer
    'flush_interval': 30   # seconds
}

# Cache settings
CACHE_SETTINGS = {
    'default_timeout': 300,     # 5 minutes
    'status_timeout': 60,       # 1 minute
    'config_timeout': 3600,     # 1 hour
    'metrics_timeout': 1800,    # 30 minutes
    'max_cache_size': 1000,    # number of items
    'cleanup_interval': 300     # 5 minutes
}

# Integration capabilities
INTEGRATION_CAPABILITIES = {
    'send_data': 'Send Data',
    'receive_data': 'Receive Data',
    'bidirectional': 'Bidirectional Communication',
    'real_time': 'Real-time Communication',
    'batch_processing': 'Batch Processing',
    'streaming': 'Data Streaming',
    'file_transfer': 'File Transfer',
    'health_monitoring': 'Health Monitoring',
    'error_handling': 'Error Handling',
    'retry_logic': 'Retry Logic',
    'rate_limiting': 'Rate Limiting',
    'authentication': 'Authentication',
    'encryption': 'Encryption',
    'compression': 'Compression'
}

# Configuration schema templates
CONFIGURATION_SCHEMAS = {
    'webhook': {
        'type': 'object',
        'required': ['webhook_url'],
        'properties': {
            'webhook_url': {'type': 'string', 'format': 'uri'},
            'secret_key': {'type': 'string'},
            'timeout': {'type': 'integer', 'minimum': 1},
            'retry_count': {'type': 'integer', 'minimum': 0},
            'headers': {'type': 'object'},
            'verify_ssl': {'type': 'boolean'}
        }
    },
    'api': {
        'type': 'object',
        'required': ['api_base_url', 'auth_type'],
        'properties': {
            'api_base_url': {'type': 'string', 'format': 'uri'},
            'auth_type': {'type': 'string', 'enum': list(AUTH_TYPES.keys())},
            'api_key': {'type': 'string'},
            'username': {'type': 'string'},
            'password': {'type': 'string'},
            'timeout': {'type': 'integer', 'minimum': 1},
            'version': {'type': 'string'}
        }
    },
    'database': {
        'type': 'object',
        'required': ['database_type', 'connection_string'],
        'properties': {
            'database_type': {'type': 'string', 'enum': ['postgresql', 'mysql', 'sqlite']},
            'connection_string': {'type': 'string'},
            'table_name': {'type': 'string'},
            'timeout': {'type': 'integer', 'minimum': 1}
        }
    }
}

# Default field mappings
DEFAULT_FIELD_MAPPINGS = {
    'alert_id': 'id',
    'alert_name': 'name',
    'alert_type': 'type',
    'severity': 'severity',
    'message': 'message',
    'timestamp': 'timestamp',
    'source': 'source',
    'details': 'details'
}

# Default severity mappings
DEFAULT_SEVERITY_MAPPINGS = {
    'low': 'low',
    'medium': 'medium',
    'high': 'high',
    'critical': 'critical'
}

# Integration metadata
INTEGRATION_METADATA = {
    'version': '1.0.0',
    'created_at': '2024-01-01',
    'updated_at': '2024-01-01',
    'author': 'Alert System',
    'description': 'Integration system for external alert management',
    'documentation_url': 'https://docs.example.com/integrations',
    'support_email': 'support@example.com'
}

# Environment-specific settings
ENVIRONMENT_SETTINGS = {
    'development': {
        'log_level': 'DEBUG',
        'timeout_multiplier': 2.0,
        'retry_multiplier': 1.5,
        'cache_timeout_multiplier': 0.5
    },
    'testing': {
        'log_level': 'INFO',
        'timeout_multiplier': 1.0,
        'retry_multiplier': 1.0,
        'cache_timeout_multiplier': 0.1
    },
    'staging': {
        'log_level': 'INFO',
        'timeout_multiplier': 1.2,
        'retry_multiplier': 1.2,
        'cache_timeout_multiplier': 0.8
    },
    'production': {
        'log_level': 'WARNING',
        'timeout_multiplier': 1.0,
        'retry_multiplier': 1.0,
        'cache_timeout_multiplier': 1.0
    }
}

# Utility functions for constants
def get_error_message(error_code: int) -> str:
    """Get error message by code"""
    return ERROR_MESSAGES.get(error_code, ERROR_MESSAGES[ERROR_CODES['UNKNOWN_ERROR']])


def get_integration_type_name(integration_type: str) -> str:
    """Get integration type display name"""
    return INTEGRATION_TYPES.get(integration_type, integration_type.title())


def get_data_format_name(data_format: str) -> str:
    """Get data format display name"""
    return DATA_FORMATS.get(data_format, data_format.upper())


def get_protocol_name(protocol: str) -> str:
    """Get protocol display name"""
    return PROTOCOLS.get(protocol, protocol.upper())


def get_auth_type_name(auth_type: str) -> str:
    """Get authentication type display name"""
    return AUTH_TYPES.get(auth_type, auth_type.replace('_', ' ').title())


def is_valid_error_code(error_code: int) -> bool:
    """Check if error code is valid"""
    return error_code in ERROR_CODES


def get_environment_settings(environment: str = None) -> Dict[str, Any]:
    """Get environment-specific settings"""
    if not environment:
        import os
        environment = os.getenv('ENVIRONMENT', 'development')
    
    return ENVIRONMENT_SETTINGS.get(environment, ENVIRONMENT_SETTINGS['development'])


def get_configuration_schema(integration_type: str) -> Dict[str, Any]:
    """Get configuration schema for integration type"""
    return CONFIGURATION_SCHEMAS.get(integration_type, {})


def merge_default_settings(custom_settings: Dict[str, Any], integration_type: str) -> Dict[str, Any]:
    """Merge custom settings with defaults"""
    defaults = {
        'timeout': DEFAULT_TIMEOUTS['connection'],
        'retry_count': DEFAULT_RETRY_SETTINGS['max_attempts'],
        'retry_delay': DEFAULT_RETRY_SETTINGS['initial_delay'],
        'retry_strategy': DEFAULT_RETRY_SETTINGS['strategy'],
        'enabled': True,
        'data_format': 'json',
        'field_mappings': DEFAULT_FIELD_MAPPINGS,
        'severity_mappings': DEFAULT_SEVERITY_MAPPINGS
    }
    
    # Merge with integration-specific defaults
    schema = get_configuration_schema(integration_type)
    if 'properties' in schema:
        for prop, config in schema['properties'].items():
            if 'default' in config:
                defaults[prop] = config['default']
    
    # Merge with custom settings
    merged = defaults.copy()
    merged.update(custom_settings)
    
    return merged


def validate_integration_config(integration_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate integration configuration against schema"""
    schema = get_configuration_schema(integration_type)
    if not schema:
        return {'valid': True, 'errors': []}
    
    # Simple validation (in production, use jsonschema library)
    errors = []
    
    # Check required fields
    required_fields = schema.get('required', [])
    for field in required_fields:
        if field not in config:
            errors.append(f"Missing required field: {field}")
    
    # Check field types
    properties = schema.get('properties', {})
    for field, field_schema in properties.items():
        if field in config:
            expected_type = field_schema.get('type')
            actual_value = config[field]
            
            if expected_type == 'string' and not isinstance(actual_value, str):
                errors.append(f"Field {field} must be a string")
            elif expected_type == 'integer' and not isinstance(actual_value, int):
                errors.append(f"Field {field} must be an integer")
            elif expected_type == 'boolean' and not isinstance(actual_value, bool):
                errors.append(f"Field {field} must be a boolean")
            elif expected_type == 'object' and not isinstance(actual_value, dict):
                errors.append(f"Field {field} must be an object")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


# Constants for integration testing
TEST_CONSTANTS = {
    'test_webhook_url': 'https://httpbin.org/post',
    'test_api_url': 'https://jsonplaceholder.typicode.com',
    'test_timeout': 5,
    'test_retry_count': 1,
    'test_data_size': 1024,  # 1KB
    'test_concurrent_connections': 10
}


# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '%(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'detailed',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'integration.log',
            'formatter': 'detailed',
            'level': 'DEBUG'
        }
    },
    'loggers': {
        'api.alerts.integration': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False
        }
    }
}


# ─────────────────────────────────────────────────────────────────
# Backward-compatible aliases used by performance_monitor.py
# ─────────────────────────────────────────────────────────────────
CACHE_KEYS = {
    'integration_status': 'integration:status:{name}',
    'integration_metrics': 'integration:metrics:{name}',
    'circuit_breaker_state': 'integration:circuit_breaker:{name}',
    'health_check': 'integration:health:{name}',
    'performance_metric': 'integration:performance:{metric_name}',
}

CACHE_TIMEOUTS = {
    'default': CACHE_SETTINGS['default_timeout'],
    'status': CACHE_SETTINGS['status_timeout'],
    'config': CACHE_SETTINGS['config_timeout'],
    'metrics': CACHE_SETTINGS['metrics_timeout'],
    'integration': CACHE_SETTINGS['config_timeout'],
}

PERFORMANCE_THRESHOLDS = {
    'response_time_warning_ms': 1000,
    'response_time_critical_ms': 5000,
    'error_rate_warning': 0.05,
    'error_rate_critical': 0.15,
    'queue_depth_warning': 1000,
    'queue_depth_critical': 5000,
}

# Webhook signing / secret settings (used by webhooks_integration.py)
HASH_ALGORITHM = 'sha256'
SECRET_MIN_LENGTH = 16

# Circuit breaker defaults (used by circuit_breaker.py)
CIRCUIT_BREAKER_DEFAULTS = {
    'failure_threshold': 5,
    'recovery_timeout': 60,
    'half_open_max_calls': 3,
    'success_threshold': 2,
}

# IntegrationStatus enum (used by bridge.py and others that expect
# Enum-style access: IntegrationStatus.ACTIVE.value)
from enum import Enum as _Enum

class IntegrationStatus(_Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ERROR = 'error'
    CONNECTING = 'connecting'
    DISCONNECTING = 'disconnecting'
    MAINTENANCE = 'maintenance'


class CircuitBreakerState(_Enum):
    """Circuit breaker states (mirrors integration/circuit_breaker.py)"""
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


# ════════════════════════════════════════════════════════════════════════════
# PRODUCTION BUG FIXES — missing constants that several integration/*.py files
# import but were never defined, causing ImportError on every import of those
# files. Placed at the end of the file so they can safely reference dicts
# defined earlier above (HEALTH_CHECK_SETTINGS, DEFAULT_SEVERITY_MAPPINGS).
# ════════════════════════════════════════════════════════════════════════════

# health_check.py imports these as flat names; only the nested
# HEALTH_CHECK_SETTINGS dict existed.
HEALTH_CHECK_INTERVAL = HEALTH_CHECK_SETTINGS['interval']   # 60 seconds
HEALTH_CHECK_TIMEOUT = HEALTH_CHECK_SETTINGS['timeout']     # 10 seconds

# data_validator.py imports these for field-length validation.
MAX_TITLE_LENGTH = 255
MAX_MESSAGE_LENGTH = 5000
MAX_EMAIL_LENGTH = 254          # RFC 5321 max mailbox length
MAX_PHONE_LENGTH = 20
MAX_WEBHOOK_URL_LENGTH = 2048   # common practical URL length ceiling

# data_bridge.py imports this to cap bulk-transfer batch sizes.
MAX_BATCH_SIZE = 500

# transformer.py imports these two names but never references them elsewhere
# in the file (vestigial import left over from an earlier refactor). Defined
# here so the import succeeds; SEVERITY_MAPPING mirrors the existing
# DEFAULT_SEVERITY_MAPPINGS dict for consistency with the rest of this module.
SEVERITY_MAPPING = DEFAULT_SEVERITY_MAPPINGS

class AlertSeverity(_Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'
