import re
import logging
from datetime import datetime
"""
Integration Constants Module
Constants for integration system
"""

from enum import Enum
from typing import Dict, List, Any

# Integration types
class IntegrationType(Enum):
    HTTP_API = "http_api"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    WEBHOOK = "webhook"
    FILE_SYSTEM = "file_system"
    EMAIL = "email"
    SMS = "sms"
    CUSTOM = "custom"

# Integration status
class IntegrationStatus(Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DISABLED = "disabled"

# Adapter types
class AdapterType(Enum):
    HTTP = "http"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    FILE_SYSTEM = "file_system"
    SOAP = "soap"
    GRPC = "grpc"

# Connection status
class ConnectionStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    TIMEOUT = "timeout"

# Health status
class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

# Event types
class EventType(Enum):
    SECURITY_EVENT = "security_event"
    THREAT_DETECTED = "threat_detected"
    INCIDENT_CREATED = "incident_created"
    INCIDENT_RESOLVED = "incident_resolved"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    DATA_ACCESS = "data_access"
    SYSTEM_ALERT = "system_alert"
    COMPLIANCE_CHECK = "compliance_check"

# Event severity
class EventSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Message formats
class MessageFormat(Enum):
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    PLAIN_TEXT = "plain_text"
    BINARY = "binary"

# Authentication types
class AuthType(Enum):
    NONE = "none"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    CERTIFICATE = "certificate"

# HTTP methods
class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"

# Queue types
class QueueType(Enum):
    RABBITMQ = "rabbitmq"
    KAFKA = "redis"
    AWS_SQS = "aws_sqs"
    AZURE_SERVICE_BUS = "azure_service_bus"
    GOOGLE_PUBSUB = "google_pubsub"

# Database types
class DatabaseType(Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    ORACLE = "oracle"
    MSSQL = "mssql"

# File formats
class FileFormat(Enum):
    JSON = "json"
    XML = "xml"
    CSV = "csv"
    EXCEL = "excel"
    PDF = "pdf"
    TXT = "txt"
    BINARY = "binary"

# Retry strategies
class RetryStrategyType(Enum):
    NONE = "none"
    FIXED = "fixed"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    CUSTOM = "custom"

# Circuit breaker states
class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

# Monitoring levels
class MonitoringLevel(Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# Validation levels
class ValidationLevel(Enum):
    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"
    CUSTOM = "custom" 

# Constants
DEFAULT_TIMEOUT = 30
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1.0
MAX_QUEUE_SIZE = 1000
MAX_HISTORY_SIZE = 10000
HEALTH_CHECK_INTERVAL = 300
METRICS_RETENTION_DAYS = 30

# Error codes
ERROR_CODES = {
    'CONNECTION_FAILED': 'E001',
    'AUTHENTICATION_FAILED': 'E002',
    'VALIDATION_FAILED': 'E003',
    'TIMEOUT_ERROR': 'E004',
    'RATE_LIMIT_EXCEEDED': 'E005',
    'CONFIGURATION_ERROR': 'E006',
    'DEPENDENCY_ERROR': 'E007',
    'TRANSFORMATION_ERROR': 'E008',
    'SERIALIZATION_ERROR': 'E009',
    'NETWORK_ERROR': 'E010',
    'SYSTEM_ERROR': 'E011',
    'UNKNOWN_ERROR': 'E999'
}

# Success codes
SUCCESS_CODES = {
    'SUCCESS': 'S001',
    'PROCESSED': 'S002',
    'QUEUED': 'S003',
    'DELIVERED': 'S004',
    'ACKNOWLEDGED': 'S005'
}

# Configuration templates
HTTP_ADAPTER_CONFIG = {
    'base_url': '',
    'headers': {},
    'auth': {
        'type': 'none',
        'username': '',
        'password': '',
        'token': ''
    },
    'timeout': DEFAULT_TIMEOUT,
    'retry_count': DEFAULT_RETRY_COUNT,
    'retry_delay': DEFAULT_RETRY_DELAY,
    'send_endpoint': '/api/data',
    'receive_endpoint': '/api/data',
    'send_method': HTTPMethod.POST.value,
    'ssl_verify': True,
    'ssl_cert': '',
    'ssl_key': ''
}

DATABASE_ADAPTER_CONFIG = {
    'connection_string': '',
    'table': 'integration_data',
    'timeout': DEFAULT_TIMEOUT,
    'retry_count': DEFAULT_RETRY_COUNT,
    'retry_delay': DEFAULT_RETRY_DELAY,
    'pool_size': 5,
    'max_overflow': 10,
    'pool_timeout': 30,
    'pool_recycle': 3600
}

MESSAGE_QUEUE_ADAPTER_CONFIG = {
    'queue_url': '',
    'queue_name': 'security_events',
    'exchange': '',
    'routing_key': '',
    'durable': True,
    'auto_ack': False,
    'prefetch_count': 1,
    'heartbeat': 600,
    'connection_timeout': DEFAULT_TIMEOUT
}

WEBHOOK_CONFIG = {
    'url': '',
    'secret': '',
    'signature_header': 'X-Signature',
    'timeout': DEFAULT_TIMEOUT,
    'retry_count': DEFAULT_RETRY_COUNT,
    'retry_delay': DEFAULT_RETRY_DELAY,
    'ssl_verify': True
}

EMAIL_ADAPTER_CONFIG = {
    'smtp_server': '',
    'smtp_port': 587,
    'username': '',
    'password': '',
    'use_tls': True,
    'use_ssl': False,
    'timeout': DEFAULT_TIMEOUT,
    'from_email': '',
    'reply_to': ''
}

SMS_ADAPTER_CONFIG = {
    'provider': '',
    'api_key': '',
    'api_secret': '',
    'from_number': '',
    'timeout': DEFAULT_TIMEOUT,
    'retry_count': DEFAULT_RETRY_COUNT,
    'retry_delay': DEFAULT_RETRY_DELAY
}

# Event mappings
EVENT_TYPE_MAPPINGS = {
    'security_event': EventType.SECURITY_EVENT.value,
    'threat_detected': EventType.THREAT_DETECTED.value,
    'incident_created': EventType.INCIDENT_CREATED.value,
    'incident_resolved': EventType.INCIDENT_RESOLVED.value,
    'user_login': EventType.USER_LOGIN.value,
    'user_logout': EventType.USER_LOGOUT.value,
    'data_access': EventType.DATA_ACCESS.value,
    'system_alert': EventType.SYSTEM_ALERT.value,
    'compliance_check': EventType.COMPLIANCE_CHECK.value
}

# Severity mappings
SEVERITY_MAPPINGS = {
    'low': EventSeverity.LOW.value,
    'medium': EventSeverity.MEDIUM.value,
    'high': EventSeverity.HIGH.value,
    'critical': EventSeverity.CRITICAL.value,
    'info': EventSeverity.LOW.value,
    'warning': EventSeverity.MEDIUM.value,
    'error': EventSeverity.HIGH.value,
    'critical': EventSeverity.CRITICAL.value
}

# Format mappings
FORMAT_MAPPINGS = {
    'json': MessageFormat.JSON.value,
    'xml': MessageFormat.XML.value,
    'csv': MessageFormat.CSV.value,
    'text': MessageFormat.PLAIN_TEXT.value,
    'binary': MessageFormat.BINARY.value,
    'xlsx': FileFormat.EXCEL.value,
    'pdf': FileFormat.PDF.value,
    'txt': FileFormat.TXT.value
}

# Authentication mappings
AUTH_MAPPINGS = {
    'none': AuthType.NONE.value,
    'basic': AuthType.BASIC.value,
    'bearer': AuthType.BEARER.value,
    'api_key': AuthType.API_KEY.value,
    'oauth2': AuthType.OAUTH2.value,
    'certificate': AuthType.CERTIFICATE.value
}

# Default field mappings
DEFAULT_FIELD_MAPPINGS = {
    'id': 'id',
    'timestamp': 'created_at',
    'user_id': 'user',
    'event_type': 'type',
    'severity': 'severity',
    'description': 'message',
    'metadata': 'data'
}

# Transformation functions
TRANSFORMATION_FUNCTIONS = {
    'to_upper': lambda x: str(x).upper(),
    'to_lower': lambda x: str(x).lower(),
    'to_string': lambda x: str(x),
    'to_int': lambda x: int(x) if str(x).isdigit() else 0,
    'to_float': lambda x: float(x) if self._is_number(x) else 0.0,
    'to_bool': lambda x: bool(x),
    'timestamp_to_iso': lambda x: x.isoformat() if hasattr(x, 'isoformat') else str(x),
    'iso_to_timestamp': lambda x: datetime.fromisoformat(x) if isinstance(x, str) else x
}

# Validation rules
VALIDATION_RULES = {
    'required': lambda x: x is not None and x != '',
    'email': lambda x: '@' in str(x) if x else False,
    'url': lambda x: str(x).startswith(('http://', 'https://')) if x else False,
    'numeric': lambda x: str(x).replace('.', '').replace('-', '').isdigit() if x else False,
    'positive': lambda x: float(x) > 0 if self._is_number(x) else False,
    'non_negative': lambda x: float(x) >= 0 if self._is_number(x) else False,
    'max_length': lambda max_len: lambda x: len(str(x)) <= max_len,
    'min_length': lambda min_len: lambda x: len(str(x)) >= min_len,
    'regex': lambda pattern: lambda x: bool(re.match(pattern, str(x))) if x else False
}

# Monitoring thresholds
MONITORING_THRESHOLDS = {
    'error_rate_warning': 0.05,  # 5%
    'error_rate_critical': 0.10,  # 10%
    'response_time_warning': 1000,  # 1 second
    'response_time_critical': 5000,  # 5 seconds
    'queue_size_warning': 100,
    'queue_size_critical': 500,
    'connection_failures_warning': 3,
    'connection_failures_critical': 5
}

# Rate limiting
RATE_LIMITS = {
    'default': {
        'requests_per_minute': 100,
        'burst_size': 10
    },
    'high_priority': {
        'requests_per_minute': 1000,
        'burst_size': 100
    },
    'low_priority': {
        'requests_per_minute': 10,
        'burst_size': 5
    }
}

# Circuit breaker thresholds
CIRCUIT_BREAKER_THRESHOLDS = {
    'failure_threshold': 5,
    'recovery_timeout': 60,
    'expected_exception': Exception,
    'success_threshold': 3
}

# Cache keys
CACHE_KEYS = {
    'integration_status': 'integration_status:{name}',
    'adapter_status': 'adapter_status:{name}',
    'health_check': 'health_check:{name}',
    'metrics': 'metrics:{name}',
    'configuration': 'configuration:{name}',
    'error_count': 'error_count:{name}'
}

# Cache timeouts (in seconds)
CACHE_TIMEOUTS = {
    'status': 60,  # 1 minute
    'health_check': 300,  # 5 minutes
    'metrics': 300,  # 5 minutes
    'configuration': 3600,  # 1 hour
    'error_count': 300  # 5 minutes
}

# Logging levels
LOGGING_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# Integration categories
INTEGRATION_CATEGORIES = {
    'security': ['security_event', 'threat_detected', 'incident_created'],
    'user_management': ['user_login', 'user_logout'],
    'data_management': ['data_access'],
    'system': ['system_alert'],
    'compliance': ['compliance_check']
}

# Priority levels
PRIORITY_LEVELS = {
    'low': 1,
    'medium': 2,
    'high': 3,
    'critical': 4
}

# Export all constants
__all__ = [
    # Enums
    'IntegrationType',
    'IntegrationStatus',
    'AdapterType',
    'ConnectionStatus',
    'HealthStatus',
    'EventType',
    'EventSeverity',
    'MessageFormat',
    'AuthType',
    'HTTPMethod',
    'QueueType',
    'DatabaseType',
    'FileFormat',
    'RetryStrategyType',
    'CircuitBreakerState',
    'MonitoringLevel',
    'ValidationLevel',
    
    # Constants
    'DEFAULT_TIMEOUT',
    'DEFAULT_RETRY_COUNT',
    'DEFAULT_RETRY_DELAY',
    'MAX_QUEUE_SIZE',
    'MAX_HISTORY_SIZE',
    'HEALTH_CHECK_INTERVAL',
    'METRICS_RETENTION_DAYS',
    
    # Error and success codes
    'ERROR_CODES',
    'SUCCESS_CODES',
    
    # Configuration templates
    'HTTP_ADAPTER_CONFIG',
    'DATABASE_ADAPTER_CONFIG',
    'MESSAGE_QUEUE_ADAPTER_CONFIG',
    'WEBHOOK_CONFIG',
    'EMAIL_ADAPTER_CONFIG',
    'SMS_ADAPTER_CONFIG',
    
    # Mappings
    'EVENT_TYPE_MAPPINGS',
    'SEVERITY_MAPPINGS',
    'FORMAT_MAPPINGS',
    'AUTH_MAPPINGS',
    'DEFAULT_FIELD_MAPPINGS',
    
    # Functions and rules
    'TRANSFORMATION_FUNCTIONS',
    'VALIDATION_RULES',
    
    # Thresholds and limits
    'MONITORING_THRESHOLDS',
    'RATE_LIMITS',
    'CIRCUIT_BREAKER_THRESHOLDS',
    
    # Cache
    'CACHE_KEYS',
    'CACHE_TIMEOUTS',
    
    # Other
    'LOGGING_LEVELS',
    'INTEGRATION_CATEGORIES',
    'PRIORITY_LEVELS'
]