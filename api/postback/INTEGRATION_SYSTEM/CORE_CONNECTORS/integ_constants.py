"""
integ_constants.py – Integration constants for postback module.

Provides comprehensive constant definitions including:
- Integration types and protocols
- Event types and statuses
- Error codes and messages
- Configuration constants
"""
from enum import Enum
from typing import Dict, Any


class IntegrationType(Enum):
    """Integration type enumeration."""
    WEBHOOK = "webhook"
    API = "api"
    MESSAGE_QUEUE = "message_queue"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    EMAIL = "email"
    SMS = "sms"
    PUSH_NOTIFICATION = "push_notification"
    WEBHOOK_OUTBOUND = "webhook_outbound"
    WEBHOOK_INBOUND = "webhook_inbound"
    REST_API = "rest_api"
    GRAPHQL_API = "graphql_api"
    SOAP_API = "soap_api"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    AWS_S3 = "aws_s3"
    GOOGLE_CLOUD = "google_cloud"
    AZURE = "azure"
    SALESFORCE = "salesforce"
    STRIPE = "stripe"
    TWILIO = "twilio"
    SENDGRID = "sendgrid"
    SLACK = "slack"
    DISCORD = "discord"
    TELEGRAM = "telegram"
    CUSTOM = "custom"


class IntegrationProtocol(Enum):
    """Integration protocol enumeration."""
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    TCP = "tcp"
    UDP = "udp"
    GRPC = "grpc"
    AMQP = "amqp"
    MQTT = "mqtt"
    SMTP = "smtp"
    FTP = "ftp"
    SFTP = "sftp"
    JDBC = "jdbc"
    ODBC = "odbc"
    SSH = "ssh"
    CUSTOM = "custom"


class IntegrationStatus(Enum):
    """Integration status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    MAINTENANCE = "maintenance"
    TESTING = "testing"
    DISABLED = "disabled"
    PENDING = "pending"
    DEPRECATED = "deprecated"


class IntegrationEventType(Enum):
    """Integration event type enumeration."""
    INTEGRATION_REGISTERED = "integration_registered"
    INTEGRATION_UNREGISTERED = "integration_unregistered"
    INTEGRATION_UPDATED = "integration_updated"
    INTEGRATION_STATUS_CHANGED = "integration_status_changed"
    INTEGRATION_ACTIVATED = "integration_activated"
    INTEGRATION_DEACTIVATED = "integration_deactivated"
    REQUEST_RECEIVED = "request_received"
    REQUEST_PROCESSED = "request_processed"
    REQUEST_FAILED = "request_failed"
    REQUEST_RETRY = "request_retry"
    REQUEST_TIMEOUT = "request_timeout"
    RESPONSE_RECEIVED = "response_received"
    RESPONSE_PROCESSED = "response_processed"
    RESPONSE_FAILED = "response_failed"
    SYSTEM_STARTED = "system_started"
    SYSTEM_STOPPED = "system_stopped"
    HEALTH_CHECK = "health_check"
    CACHE_CLEARED = "cache_cleared"
    CONFIGURATION_UPDATED = "configuration_updated"
    ERROR_OCCURRED = "error_occurred"
    WARNING_ISSUED = "warning_issued"


class IntegrationErrorCode(Enum):
    """Integration error code enumeration."""
    SUCCESS = "SUCCESS"
    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    TIMEOUT = "TIMEOUT"
    CONNECTION_ERROR = "CONNECTION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TRANSFORMATION_ERROR = "TRANSFORMATION_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    DEPENDENCY_ERROR = "DEPENDENCY_ERROR"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
    ENCRYPTION_ERROR = "ENCRYPTION_ERROR"
    DECRYPTION_ERROR = "DECRYPTION_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class IntegrationLogLevel(Enum):
    """Integration log level enumeration."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class IntegrationPriority(Enum):
    """Integration priority enumeration."""
    LOWEST = 1
    LOW = 25
    NORMAL = 50
    HIGH = 75
    HIGHEST = 100


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
    'UNPROCESSABLE_ENTITY': 422,
    'TOO_MANY_REQUESTS': 429,
    'INTERNAL_SERVER_ERROR': 500,
    'BAD_GATEWAY': 502,
    'SERVICE_UNAVAILABLE': 503,
    'GATEWAY_TIMEOUT': 504,
}

# Error Messages
ERROR_MESSAGES = {
    IntegrationErrorCode.SUCCESS: "Operation completed successfully",
    IntegrationErrorCode.INVALID_REQUEST: "Invalid request format or parameters",
    IntegrationErrorCode.INVALID_RESPONSE: "Invalid response format or structure",
    IntegrationErrorCode.TIMEOUT: "Request timed out",
    IntegrationErrorCode.CONNECTION_ERROR: "Failed to establish connection",
    IntegrationErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
    IntegrationErrorCode.AUTHORIZATION_ERROR: "Authorization failed",
    IntegrationErrorCode.RATE_LIMIT_EXCEEDED: "Rate limit exceeded",
    IntegrationErrorCode.QUOTA_EXCEEDED: "Quota exceeded",
    IntegrationErrorCode.SERVICE_UNAVAILABLE: "Service temporarily unavailable",
    IntegrationErrorCode.INTERNAL_ERROR: "Internal server error",
    IntegrationErrorCode.VALIDATION_ERROR: "Data validation failed",
    IntegrationErrorCode.TRANSFORMATION_ERROR: "Data transformation failed",
    IntegrationErrorCode.PROTOCOL_ERROR: "Protocol error occurred",
    IntegrationErrorCode.NETWORK_ERROR: "Network error occurred",
    IntegrationErrorCode.CONFIGURATION_ERROR: "Configuration error",
    IntegrationErrorCode.DEPENDENCY_ERROR: "Dependency error occurred",
    IntegrationErrorCode.VERSION_MISMATCH: "Version mismatch",
    IntegrationErrorCode.DATA_FORMAT_ERROR: "Data format error",
    IntegrationErrorCode.ENCRYPTION_ERROR: "Encryption error",
    IntegrationErrorCode.DECRYPTION_ERROR: "Decryption error",
    IntegrationErrorCode.UNKNOWN_ERROR: "Unknown error occurred",
}

# Default Configuration
DEFAULT_CONFIG = {
    'timeout': 30,
    'retry_attempts': 3,
    'retry_delay': 1.0,
    'verify_ssl': True,
    'allow_redirects': True,
    'max_response_size': 10485760,  # 10MB
    'cache_timeout': 300,
    'log_level': IntegrationLogLevel.INFO,
    'priority': IntegrationPriority.NORMAL,
}

# HTTP Configuration
HTTP_CONFIG = {
    'default_headers': {
        'User-Agent': 'PostbackIntegration/1.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    },
    'default_timeout': 30,
    'max_redirects': 5,
    'chunk_size': 8192,
    'pool_connections': 10,
    'pool_maxsize': 10,
}

# WebSocket Configuration
WEBSOCKET_CONFIG = {
    'default_timeout': 60,
    'ping_interval': 30,
    'ping_timeout': 10,
    'close_timeout': 10,
    'max_size': 2**20,  # 1MB
    'max_queue': 100,
}

# Message Queue Configuration
MESSAGE_QUEUE_CONFIG = {
    'default_exchange': 'postback',
    'default_queue': 'postback_queue',
    'durable': True,
    'auto_delete': False,
    'exclusive': False,
    'message_ttl': 86400,  # 24 hours
    'max_retries': 3,
    'retry_delay': 5,  # seconds
}

# Database Configuration
DATABASE_CONFIG = {
    'default_pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'isolation_level': 'READ_COMMITTED',
}

# File System Configuration
FILE_SYSTEM_CONFIG = {
    'default_mode': 0o644,
    'default_dir_mode': 0o755,
    'max_file_size': 104857600,  # 100MB
    'chunk_size': 8192,
    'encoding': 'utf-8',
}

# Email Configuration
EMAIL_CONFIG = {
    'default_from': 'noreply@postback.com',
    'default_reply_to': None,
    'default_subject_prefix': '[Postback]',
    'max_attachment_size': 10485760,  # 10MB
    'allowed_extensions': ['.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx'],
}

# SMS Configuration
SMS_CONFIG = {
    'default_from': '+1234567890',
    'max_message_length': 160,
    'encoding': 'UTF-8',
    'delivery_timeout': 300,  # 5 minutes
}

# Push Notification Configuration
PUSH_CONFIG = {
    'default_ttl': 86400,  # 24 hours
    'default_priority': 'normal',
    'max_payload_size': 4096,
    'collapse_key': None,
}

# Rate Limiting Configuration
RATE_LIMIT_CONFIG = {
    'default_rate': 100,  # requests per minute
    'default_window': 60,  # seconds
    'burst_size': 10,
    'penalty_time': 300,  # 5 minutes
}

# Circuit Breaker Configuration
CIRCUIT_BREAKER_CONFIG = {
    'default_failure_threshold': 5,
    'default_recovery_timeout': 60,
    'default_expected_exception': 'Exception',
    'default_max_timeout': 300,
}

# Cache Configuration
CACHE_CONFIG = {
    'default_timeout': 300,
    'max_keys': 10000,
    'max_memory': 104857600,  # 100MB
    'compression': True,
    'serializer': 'json',
}

# Logging Configuration
LOGGING_CONFIG = {
    'default_level': IntegrationLogLevel.INFO,
    'max_log_size': 1048576,  # 1MB
    'backup_count': 5,
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
}

# Validation Configuration
VALIDATION_CONFIG = {
    'max_field_length': 1000,
    'required_fields': [],
    'optional_fields': [],
    'field_types': {},
    'field_validators': {},
    'custom_validators': [],
}

# Transformation Configuration
TRANSFORMATION_CONFIG = {
    'default_input_format': 'json',
    'default_output_format': 'json',
    'preserve_nulls': False,
    'trim_strings': True,
    'convert_empty_to_null': True,
}

# Security Configuration
SECURITY_CONFIG = {
    'encryption_algorithm': 'AES-256',
    'hash_algorithm': 'SHA-256',
    'api_key_length': 32,
    'token_expiry': 3600,  # 1 hour
    'refresh_token_expiry': 2592000,  # 30 days
    'password_min_length': 8,
    'session_timeout': 1800,  # 30 minutes
}

# Monitoring Configuration
MONITORING_CONFIG = {
    'metrics_interval': 60,  # seconds
    'health_check_interval': 300,  # 5 minutes
    'alert_threshold': 0.95,  # 95%
    'max_alerts_per_hour': 10,
    'retention_period': 30,  # days
}

# Integration Type Mappings
INTEGRATION_TYPE_PROTOCOLS = {
    IntegrationType.WEBHOOK: [IntegrationProtocol.HTTP, IntegrationProtocol.HTTPS],
    IntegrationType.API: [IntegrationProtocol.HTTP, IntegrationProtocol.HTTPS],
    IntegrationType.MESSAGE_QUEUE: [IntegrationProtocol.AMQP, IntegrationProtocol.MQTT],
    IntegrationType.DATABASE: [IntegrationProtocol.JDBC, IntegrationProtocol.ODBC],
    IntegrationType.EMAIL: [IntegrationProtocol.SMTP],
    IntegrationType.SMS: [IntegrationProtocol.HTTP, IntegrationProtocol.HTTPS],
    IntegrationType.PUSH_NOTIFICATION: [IntegrationProtocol.HTTP, IntegrationProtocol.HTTPS],
}

# Integration Type Defaults
INTEGRATION_TYPE_DEFAULTS = {
    IntegrationType.WEBHOOK: {
        'protocol': IntegrationProtocol.HTTPS,
        'timeout': 30,
        'retry_attempts': 3,
    },
    IntegrationType.API: {
        'protocol': IntegrationProtocol.HTTPS,
        'timeout': 30,
        'retry_attempts': 3,
    },
    IntegrationType.MESSAGE_QUEUE: {
        'protocol': IntegrationProtocol.AMQP,
        'timeout': 60,
        'retry_attempts': 3,
    },
    IntegrationType.DATABASE: {
        'protocol': IntegrationProtocol.JDBC,
        'timeout': 30,
        'retry_attempts': 2,
    },
    IntegrationType.EMAIL: {
        'protocol': IntegrationProtocol.SMTP,
        'timeout': 60,
        'retry_attempts': 3,
    },
    IntegrationType.SMS: {
        'protocol': IntegrationProtocol.HTTP,
        'timeout': 30,
        'retry_attempts': 3,
    },
    IntegrationType.PUSH_NOTIFICATION: {
        'protocol': IntegrationProtocol.HTTP,
        'timeout': 15,
        'retry_attempts': 5,
    },
}

# Protocol Defaults
PROTOCOL_DEFAULTS = {
    IntegrationProtocol.HTTP: {
        'port': 80,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.HTTPS: {
        'port': 443,
        'secure': True,
        'timeout': 30,
    },
    IntegrationProtocol.WEBSOCKET: {
        'port': 80,
        'secure': False,
        'timeout': 60,
    },
    IntegrationProtocol.TCP: {
        'port': 80,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.UDP: {
        'port': 80,
        'secure': False,
        'timeout': 10,
    },
    IntegrationProtocol.GRPC: {
        'port': 50051,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.AMQP: {
        'port': 5672,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.MQTT: {
        'port': 1883,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.SMTP: {
        'port': 25,
        'secure': False,
        'timeout': 60,
    },
    IntegrationProtocol.FTP: {
        'port': 21,
        'secure': False,
        'timeout': 60,
    },
    IntegrationProtocol.SFTP: {
        'port': 22,
        'secure': True,
        'timeout': 60,
    },
    IntegrationProtocol.JDBC: {
        'port': 3306,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.ODBC: {
        'port': 3306,
        'secure': False,
        'timeout': 30,
    },
    IntegrationProtocol.SSH: {
        'port': 22,
        'secure': True,
        'timeout': 30,
    },
}

# Environment-specific configurations
ENVIRONMENT_CONFIG = {
    'development': {
        'debug': True,
        'log_level': IntegrationLogLevel.DEBUG,
        'timeout': 60,
        'retry_attempts': 5,
    },
    'testing': {
        'debug': False,
        'log_level': IntegrationLogLevel.WARNING,
        'timeout': 30,
        'retry_attempts': 1,
    },
    'staging': {
        'debug': False,
        'log_level': IntegrationLogLevel.INFO,
        'timeout': 30,
        'retry_attempts': 3,
    },
    'production': {
        'debug': False,
        'log_level': IntegrationLogLevel.ERROR,
        'timeout': 30,
        'retry_attempts': 3,
    },
}

# Feature flags
FEATURE_FLAGS = {
    'enable_monitoring': True,
    'enable_caching': True,
    'enable_circuit_breaker': True,
    'enable_rate_limiting': True,
    'enable_encryption': True,
    'enable_compression': True,
    'enable_metrics': True,
    'enable_health_checks': True,
    'enable_auto_retry': True,
    'enable_request_signing': False,
    'enable_response_validation': True,
}

# Constants for validation
MAX_STRING_LENGTH = 1000
MAX_FIELD_COUNT = 100
MAX_NESTING_DEPTH = 10
MAX_ARRAY_LENGTH = 1000
MAX_OBJECT_SIZE = 10485760  # 10MB

# Time constants
TIMEOUT_MINUTES = 60
TIMEOUT_HOURS = 3600
TIMEOUT_DAYS = 86400
TIMEOUT_WEEKS = 604800
TIMEOUT_MONTHS = 2592000
TIMEOUT_YEARS = 31536000

# Size constants
SIZE_KB = 1024
SIZE_MB = 1048576
SIZE_GB = 1073741824
SIZE_TB = 1099511627776

# Regular expressions
REGEX_PATTERNS = {
    'email': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
    'url': r'^https?://(?:[-\w.])+(?:\.[a-zA-Z]{2,})+(?:/[\w._]*/)*(?:/[^\s]*)?$',
    'phone': r'^\+?1?[0-9]{10,15}$',
    'uuid': r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
    'api_key': r'^[a-zA-Z0-9]{20,}$',
    'token': r'^[a-zA-Z0-9._-]{20,}$',
}

# Default values
DEFAULT_VALUES = {
    'timeout': 30,
    'retry_attempts': 3,
    'retry_delay': 1.0,
    'max_retries': 3,
    'cache_timeout': 300,
    'log_level': IntegrationLogLevel.INFO,
    'priority': IntegrationPriority.NORMAL,
    'status': IntegrationStatus.ACTIVE,
    'protocol': IntegrationProtocol.HTTP,
    'type': IntegrationType.WEBHOOK,
}

# Validation rules
VALIDATION_RULES = {
    'name': {
        'required': True,
        'min_length': 3,
        'max_length': 50,
        'pattern': r'^[a-zA-Z0-9_-]+$',
    },
    'endpoint': {
        'required': True,
        'max_length': 255,
        'pattern': REGEX_PATTERNS['url'],
    },
    'timeout': {
        'required': False,
        'min_value': 1,
        'max_value': 300,
    },
    'retry_attempts': {
        'required': False,
        'min_value': 0,
        'max_value': 10,
    },
}

# Export all constants for easy access
__all__ = [
    'IntegrationType',
    'IntegrationProtocol',
    'IntegrationStatus',
    'IntegrationEventType',
    'IntegrationErrorCode',
    'IntegrationLogLevel',
    'IntegrationPriority',
    'HTTP_STATUS_CODES',
    'ERROR_MESSAGES',
    'DEFAULT_CONFIG',
    'HTTP_CONFIG',
    'WEBSOCKET_CONFIG',
    'MESSAGE_QUEUE_CONFIG',
    'DATABASE_CONFIG',
    'FILE_SYSTEM_CONFIG',
    'EMAIL_CONFIG',
    'SMS_CONFIG',
    'PUSH_CONFIG',
    'RATE_LIMIT_CONFIG',
    'CIRCUIT_BREAKER_CONFIG',
    'CACHE_CONFIG',
    'LOGGING_CONFIG',
    'VALIDATION_CONFIG',
    'TRANSFORMATION_CONFIG',
    'SECURITY_CONFIG',
    'MONITORING_CONFIG',
    'INTEGRATION_TYPE_PROTOCOLS',
    'INTEGRATION_TYPE_DEFAULTS',
    'PROTOCOL_DEFAULTS',
    'ENVIRONMENT_CONFIG',
    'FEATURE_FLAGS',
    'MAX_STRING_LENGTH',
    'MAX_FIELD_COUNT',
    'MAX_NESTING_DEPTH',
    'MAX_ARRAY_LENGTH',
    'MAX_OBJECT_SIZE',
    'TIMEOUT_MINUTES',
    'TIMEOUT_HOURS',
    'TIMEOUT_DAYS',
    'TIMEOUT_WEEKS',
    'TIMEOUT_MONTHS',
    'TIMEOUT_YEARS',
    'SIZE_KB',
    'SIZE_MB',
    'SIZE_GB',
    'SIZE_TB',
    'REGEX_PATTERNS',
    'DEFAULT_VALUES',
    'VALIDATION_RULES',
]
