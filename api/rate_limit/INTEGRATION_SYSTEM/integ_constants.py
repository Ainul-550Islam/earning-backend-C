"""
Integration Constants - System-wide Constants and Enums

Central location for all integration-related constants, enums,
and configuration values used across the integration system.
"""

from enum import Enum
from typing import Dict, Any, List, Union
from datetime import timedelta


class IntegrationEvent(Enum):
    """Integration event types."""
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    ABUSE_DETECTED = "abuse_detected"
    IP_BLOCKED = "ip_blocked"
    SANCTION_APPLIED = "sanction_applied"
    CONFIG_UPDATED = "config_updated"
    SYSTEM_HEALTH = "system_health"
    PERFORMANCE_ALERT = "performance_alert"
    DATA_INTEGRITY = "data_integrity"
    COMPLIANCE_EVENT = "compliance_event"
    USER_SUSPICION_UPDATED = "user_suspicion_updated"
    WEBHOOK_DELIVERED = "webhook_delivered"
    WEBHOOK_FAILED = "webhook_failed"
    CACHE_CLEARED = "cache_cleared"
    BACKUP_COMPLETED = "backup_completed"
    MIGRATION_COMPLETED = "migration_completed"


class IntegrationStatus(Enum):
    """Integration operation status."""
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RETRY = "retry"
    PARTIAL = "partial"


class IntegrationPriority(Enum):
    """Integration operation priority."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


class IntegrationProtocol(Enum):
    """Supported integration protocols."""
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    AMQP = "amqp"
    MQTT = "mqtt"
    TCP = "tcp"
    UDP = "udp"
    GRPC = "grpc"


class IntegrationDataType(Enum):
    """Integration data types."""
    JSON = "json"
    XML = "xml"
    FORM = "form"
    BINARY = "binary"
    TEXT = "text"
    CSV = "csv"


class IntegrationLogLevel(Enum):
    """Integration logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Integration System Configuration
INTEGRATION_CONFIG = {
    # System settings
    "MAX_CONCURRENT_REQUESTS": 100,
    "DEFAULT_TIMEOUT": 30,
    "MAX_RETRY_ATTEMPTS": 3,
    "RETRY_DELAY_BASE": 1.0,
    "CIRCUIT_BREAKER_THRESHOLD": 5,
    "CIRCUIT_BREAKER_TIMEOUT": 60,
    "HEALTH_CHECK_INTERVAL": 300,
    "CLEANUP_INTERVAL": 3600,
    "MAX_IDLE_TIME": timedelta(hours=1),
    
    # Performance settings
    "PERFORMANCE_SAMPLE_SIZE": 1000,
    "PERFORMANCE_ALERT_THRESHOLD": 1000,  # milliseconds
    "SLOW_REQUEST_THRESHOLD": 500,  # milliseconds
    "MEMORY_USAGE_THRESHOLD": 0.8,  # 80%
    "CPU_USAGE_THRESHOLD": 0.7,  # 70%
    
    # Security settings
    "MAX_REQUEST_SIZE": 10485760,  # 10MB
    "MAX_RESPONSE_SIZE": 52428800,  # 50MB
    "RATE_LIMIT_PER_MINUTE": 1000,
    "RATE_LIMIT_PER_HOUR": 10000,
    "AUTH_TOKEN_EXPIRY": 3600,  # 1 hour
    "WEBHOOK_SIGNATURE_TIMEOUT": 300,  # 5 minutes
    
    # Cache settings
    "CACHE_DEFAULT_TIMEOUT": 3600,  # 1 hour
    "CACHE_REGISTRY_TIMEOUT": 86400,  # 24 hours
    "CACHE_INSTANCE_TIMEOUT": 1800,  # 30 minutes
    "CACHE_STATS_TIMEOUT": 300,  # 5 minutes
    
    # Queue settings
    "QUEUE_MAX_SIZE": 10000,
    "QUEUE_BATCH_SIZE": 100,
    "QUEUE_PROCESSING_TIMEOUT": 300,
    "QUEUE_RETRY_DELAY": 60,
    "QUEUE_MAX_RETRIES": 5,
    
    # Monitoring settings
    "METRICS_RETENTION_DAYS": 30,
    "ALERT_COOLDOWN_PERIOD": 300,  # 5 minutes
    "HEALTH_CHECK_TIMEOUT": 10,
    "METRICS_COLLECTION_INTERVAL": 60,  # 1 minute
    
    # Webhook settings
    "WEBHOOK_TIMEOUT": 30,
    "WEBHOOK_RETRY_ATTEMPTS": 3,
    "WEBHOOK_RETRY_DELAY": 5,
    "WEBHOOK_MAX_PAYLOAD_SIZE": 1048576,  # 1MB
    "WEBHOOK_SIGNATURE_ALGORITHM": "sha256",
    
    # Database settings
    "DB_CONNECTION_POOL_SIZE": 20,
    "DB_QUERY_TIMEOUT": 30,
    "DB_BATCH_SIZE": 1000,
    "DB_MAX_CONNECTIONS": 100,
    
    # File system settings
    "FS_MAX_FILE_SIZE": 104857600,  # 100MB
    "FS_ALLOWED_EXTENSIONS": [".json", ".xml", ".csv", ".txt"],
    "FS_UPLOAD_TIMEOUT": 300,
    "FS_CLEANUP_INTERVAL": 86400,  # 24 hours
}


# Integration Event Mappings
EVENT_HANDLERS = {
    IntegrationEvent.RATE_LIMIT_EXCEEDED: [
        "rate_limit_handler",
        "ip_blocking_handler",
        "notification_handler"
    ],
    IntegrationEvent.ABUSE_DETECTED: [
        "abuse_detection_handler",
        "sanction_handler",
        "compliance_handler"
    ],
    IntegrationEvent.IP_BLOCKED: [
        "ip_blocking_handler",
        "cache_handler",
        "notification_handler"
    ],
    IntegrationEvent.SANCTION_APPLIED: [
        "sanction_handler",
        "user_profile_handler",
        "compliance_handler"
    ],
    IntegrationEvent.SYSTEM_HEALTH: [
        "health_monitor_handler",
        "alert_handler",
        "admin_notification_handler"
    ],
    IntegrationEvent.DATA_INTEGRITY: [
        "integrity_handler",
        "security_handler",
        "admin_alert_handler"
    ]
}


# Integration Priority Mappings
PRIORITY_CONFIG = {
    IntegrationPriority.LOW: {
        "max_retries": 1,
        "retry_delay": 2.0,
        "timeout": 60,
        "queue_priority": 0
    },
    IntegrationPriority.NORMAL: {
        "max_retries": 3,
        "retry_delay": 1.0,
        "timeout": 30,
        "queue_priority": 1
    },
    IntegrationPriority.HIGH: {
        "max_retries": 5,
        "retry_delay": 0.5,
        "timeout": 15,
        "queue_priority": 2
    },
    IntegrationPriority.CRITICAL: {
        "max_retries": 10,
        "retry_delay": 0.1,
        "timeout": 5,
        "queue_priority": 3
    },
    IntegrationPriority.URGENT: {
        "max_retries": 20,
        "retry_delay": 0.05,
        "timeout": 2,
        "queue_priority": 4
    }
}


# Integration Error Codes
INTEGRATION_ERROR_CODES = {
    "SUCCESS": 0,
    "GENERAL_ERROR": 1000,
    "TIMEOUT_ERROR": 1001,
    "AUTHENTICATION_ERROR": 1002,
    "AUTHORIZATION_ERROR": 1003,
    "VALIDATION_ERROR": 1004,
    "NETWORK_ERROR": 1005,
    "PARSE_ERROR": 1006,
    "RATE_LIMIT_ERROR": 1007,
    "CIRCUIT_BREAKER_ERROR": 1008,
    "DEPENDENCY_ERROR": 1009,
    "CONFIGURATION_ERROR": 1010,
    "REGISTRATION_ERROR": 1011,
    "HEALTH_CHECK_ERROR": 1012,
    "PERFORMANCE_ERROR": 1013,
    "SECURITY_ERROR": 1014,
    "DATA_INTEGRITY_ERROR": 1015,
    "COMPLIANCE_ERROR": 1016,
    "WEBHOOK_ERROR": 1017,
    "QUEUE_ERROR": 1018,
    "CACHE_ERROR": 1019,
    "DATABASE_ERROR": 1020,
    "FILE_SYSTEM_ERROR": 1021
}


# Integration Status Codes
INTEGRATION_STATUS_CODES = {
    IntegrationStatus.SUCCESS: 200,
    IntegrationStatus.FAILED: 500,
    IntegrationStatus.PENDING: 102,
    IntegrationStatus.TIMEOUT: 408,
    IntegrationStatus.CANCELLED: 499,
    IntegrationStatus.RETRY: 429,
    IntegrationStatus.PARTIAL: 206
}


# Integration Protocol Mappings
PROTOCOL_CONFIG = {
    IntegrationProtocol.HTTP: {
        "default_port": 80,
        "secure": False,
        "timeout": 30
    },
    IntegrationProtocol.HTTPS: {
        "default_port": 443,
        "secure": True,
        "timeout": 30
    },
    IntegrationProtocol.WEBSOCKET: {
        "default_port": 80,
        "secure": False,
        "timeout": 300
    },
    IntegrationProtocol.AMQP: {
        "default_port": 5672,
        "secure": False,
        "timeout": 60
    },
    IntegrationProtocol.MQTT: {
        "default_port": 1883,
        "secure": False,
        "timeout": 30
    },
    IntegrationProtocol.TCP: {
        "default_port": 80,
        "secure": False,
        "timeout": 30
    },
    IntegrationProtocol.UDP: {
        "default_port": 80,
        "secure": False,
        "timeout": 10
    },
    IntegrationProtocol.GRPC: {
        "default_port": 50051,
        "secure": True,
        "timeout": 30
    }
}


# Integration Data Type Mappings
DATA_TYPE_CONFIG = {
    IntegrationDataType.JSON: {
        "content_type": "application/json",
        "parser": "json",
        "validator": "json_schema"
    },
    IntegrationDataType.XML: {
        "content_type": "application/xml",
        "parser": "xml",
        "validator": "xml_schema"
    },
    IntegrationDataType.FORM: {
        "content_type": "application/x-www-form-urlencoded",
        "parser": "form",
        "validator": "form_fields"
    },
    IntegrationDataType.BINARY: {
        "content_type": "application/octet-stream",
        "parser": "binary",
        "validator": "file_type"
    },
    IntegrationDataType.TEXT: {
        "content_type": "text/plain",
        "parser": "text",
        "validator": "text_length"
    },
    IntegrationDataType.CSV: {
        "content_type": "text/csv",
        "parser": "csv",
        "validator": "csv_schema"
    }
}


# Integration Service Types
SERVICE_TYPES = {
    "adapter": {
        "description": "External service adapters",
        "examples": ["REST API", "Webhook", "Message Queue", "Database"]
    },
    "handler": {
        "description": "Event handlers",
        "examples": ["Rate Limit Handler", "Abuse Detection Handler", "IP Blocking Handler"]
    },
    "middleware": {
        "description": "Request/response middleware",
        "examples": ["Authentication", "Validation", "Logging", "Rate Limiting"]
    },
    "validator": {
        "description": "Data validators",
        "examples": ["Schema Validator", "Security Validator", "Format Validator"]
    },
    "transformer": {
        "description": "Data transformers",
        "examples": ["JSON Transformer", "XML Transformer", "Format Converter"]
    },
    "monitor": {
        "description": "Monitoring and health checks",
        "examples": ["Health Monitor", "Performance Monitor", "Security Monitor"]
    }
}


# Integration Tags
INTEGRATION_TAGS = {
    "protocol": ["http", "https", "websocket", "amqp", "mqtt", "tcp", "udp", "grpc"],
    "data_type": ["json", "xml", "form", "binary", "text", "csv"],
    "auth_type": ["none", "api_key", "bearer_token", "basic_auth", "oauth2", "hmac"],
    "security": ["encrypted", "signed", "authenticated", "public"],
    "performance": ["high_performance", "low_latency", "batch", "stream"],
    "reliability": ["fault_tolerant", "retry", "circuit_breaker", "fallback"],
    "monitoring": ["health_check", "metrics", "logging", "alerting"],
    "compliance": ["gdpr", "ccpa", "hipaa", "sox", "pci_dss"],
    "category": ["security", "performance", "monitoring", "integration", "data"]
}


# Integration Environment Settings
ENVIRONMENT_CONFIG = {
    "development": {
        "debug": True,
        "log_level": IntegrationLogLevel.DEBUG,
        "timeout_multiplier": 2.0,
        "retry_multiplier": 2.0,
        "circuit_breaker_threshold": 3,
        "health_check_interval": 60
    },
    "testing": {
        "debug": True,
        "log_level": IntegrationLogLevel.INFO,
        "timeout_multiplier": 1.5,
        "retry_multiplier": 1.5,
        "circuit_breaker_threshold": 4,
        "health_check_interval": 120
    },
    "staging": {
        "debug": False,
        "log_level": IntegrationLogLevel.WARNING,
        "timeout_multiplier": 1.2,
        "retry_multiplier": 1.2,
        "circuit_breaker_threshold": 5,
        "health_check_interval": 180
    },
    "production": {
        "debug": False,
        "log_level": IntegrationLogLevel.ERROR,
        "timeout_multiplier": 1.0,
        "retry_multiplier": 1.0,
        "circuit_breaker_threshold": 5,
        "health_check_interval": 300
    }
}


# Integration Default Headers
DEFAULT_HEADERS = {
    "User-Agent": "RateLimit-Integration/1.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Integration-Version": "1.0",
    "X-Request-ID": None,  # Will be generated per request
    "X-Timestamp": None,  # Will be generated per request
}


# Integration Rate Limiting Rules
RATE_LIMITING_RULES = {
    "default": {
        "requests_per_minute": 1000,
        "requests_per_hour": 10000,
        "requests_per_day": 100000,
        "burst_size": 100
    },
    "webhook": {
        "requests_per_minute": 500,
        "requests_per_hour": 5000,
        "requests_per_day": 50000,
        "burst_size": 50
    },
    "api": {
        "requests_per_minute": 2000,
        "requests_per_hour": 20000,
        "requests_per_day": 200000,
        "burst_size": 200
    },
    "monitoring": {
        "requests_per_minute": 100,
        "requests_per_hour": 1000,
        "requests_per_day": 10000,
        "burst_size": 20
    }
}


# Integration Circuit Breaker Rules
CIRCUIT_BREAKER_RULES = {
    "default": {
        "failure_threshold": 5,
        "recovery_timeout": 60,
        "expected_exception": "IntegrationError",
        "fallback_function": None
    },
    "critical": {
        "failure_threshold": 3,
        "recovery_timeout": 30,
        "expected_exception": "IntegrationError",
        "fallback_function": None
    },
    "non_critical": {
        "failure_threshold": 10,
        "recovery_timeout": 120,
        "expected_exception": "IntegrationError",
        "fallback_function": None
    }
}


# Integration Webhook Configuration
WEBHOOK_CONFIG = {
    "default_timeout": 30,
    "max_retry_attempts": 3,
    "retry_delay": 5,
    "max_payload_size": 1048576,  # 1MB
    "signature_algorithm": "sha256",
    "signature_header": "X-Signature",
    "timestamp_header": "X-Timestamp",
    "idempotency_header": "X-Idempotency-Key",
    "allowed_events": [
        "rate_limit_exceeded",
        "abuse_detected",
        "ip_blocked",
        "sanction_applied",
        "system_health",
        "data_integrity"
    ]
}


# Integration Monitoring Metrics
MONITORING_METRICS = {
    "request_count": {
        "type": "counter",
        "description": "Total number of integration requests"
    },
    "request_duration": {
        "type": "histogram",
        "description": "Request duration in milliseconds",
        "buckets": [10, 50, 100, 500, 1000, 5000]
    },
    "error_count": {
        "type": "counter",
        "description": "Total number of integration errors"
    },
    "circuit_breaker_state": {
        "type": "gauge",
        "description": "Circuit breaker state (0=closed, 1=open, 2=half_open)"
    },
    "active_connections": {
        "type": "gauge",
        "description": "Number of active connections"
    },
    "queue_size": {
        "type": "gauge",
        "description": "Current queue size"
    },
    "cache_hit_rate": {
        "type": "gauge",
        "description": "Cache hit rate (0-1)"
    },
    "memory_usage": {
        "type": "gauge",
        "description": "Memory usage percentage"
    },
    "cpu_usage": {
        "type": "gauge",
        "description": "CPU usage percentage"
    }
}


# Integration Alert Rules
ALERT_RULES = {
    "high_error_rate": {
        "condition": "error_rate > 0.1",
        "duration": 300,  # 5 minutes
        "severity": "high",
        "message": "High error rate detected"
    },
    "slow_requests": {
        "condition": "avg_request_duration > 1000",
        "duration": 300,  # 5 minutes
        "severity": "medium",
        "message": "Slow requests detected"
    },
    "circuit_breaker_open": {
        "condition": "circuit_breaker_state == 1",
        "duration": 60,  # 1 minute
        "severity": "high",
        "message": "Circuit breaker is open"
    },
    "queue_full": {
        "condition": "queue_size > 8000",
        "duration": 60,  # 1 minute
        "severity": "medium",
        "message": "Queue is nearly full"
    },
    "high_memory_usage": {
        "condition": "memory_usage > 0.8",
        "duration": 300,  # 5 minutes
        "severity": "high",
        "message": "High memory usage detected"
    }
}


# Integration Compliance Rules
COMPLIANCE_RULES = {
    "gdpr": {
        "data_retention_days": 365,
        "anonymization_days": 90,
        "consent_required": True,
        "right_to_be_forgotten": True,
        "audit_trail_required": True
    },
    "ccpa": {
        "data_retention_days": 365,
        "anonymization_days": 90,
        "consent_required": True,
        "right_to_delete": True,
        "audit_trail_required": True
    },
    "hipaa": {
        "data_retention_days": 2555,  # 7 years
        "anonymization_days": 365,
        "consent_required": True,
        "audit_trail_required": True,
        "encryption_required": True
    },
    "sox": {
        "data_retention_days": 2555,  # 7 years
        "audit_trail_required": True,
        "access_control_required": True,
        "integrity_checks_required": True
    },
    "pci_dss": {
        "data_retention_days": 365,
        "encryption_required": True,
        "audit_trail_required": True,
        "access_control_required": True,
        "network_security_required": True
    }
}


# Utility Functions
def get_config_value(key: str, default: Any = None) -> Any:
    """Get configuration value with fallback to default."""
    return INTEGRATION_CONFIG.get(key, default)


def get_priority_config(priority: IntegrationPriority) -> Dict[str, Any]:
    """Get priority configuration."""
    return PRIORITY_CONFIG.get(priority, PRIORITY_CONFIG[IntegrationPriority.NORMAL])


def get_protocol_config(protocol: IntegrationProtocol) -> Dict[str, Any]:
    """Get protocol configuration."""
    return PROTOCOL_CONFIG.get(protocol, {})


def get_data_type_config(data_type: IntegrationDataType) -> Dict[str, Any]:
    """Get data type configuration."""
    return DATA_TYPE_CONFIG.get(data_type, {})


def get_environment_config(environment: str) -> Dict[str, Any]:
    """Get environment configuration."""
    return ENVIRONMENT_CONFIG.get(environment, ENVIRONMENT_CONFIG["production"])


def get_rate_limiting_rules(rule_type: str = "default") -> Dict[str, Any]:
    """Get rate limiting rules."""
    return RATE_LIMITING_RULES.get(rule_type, RATE_LIMITING_RULES["default"])


def get_circuit_breaker_rules(rule_type: str = "default") -> Dict[str, Any]:
    """Get circuit breaker rules."""
    return CIRCUIT_BREAKER_RULES.get(rule_type, CIRCUIT_BREAKER_RULES["default"])


def get_compliance_rules(standard: str) -> Dict[str, Any]:
    """Get compliance rules for a standard."""
    return COMPLIANCE_RULES.get(standard, {})


def validate_event_type(event_type: str) -> bool:
    """Validate event type."""
    try:
        IntegrationEvent(event_type)
        return True
    except ValueError:
        return False


def validate_status(status: str) -> bool:
    """Validate status."""
    try:
        IntegrationStatus(status)
        return True
    except ValueError:
        return False


def validate_priority(priority: Union[str, int]) -> bool:
    """Validate priority."""
    if isinstance(priority, int):
        return priority in [p.value for p in IntegrationPriority]
    else:
        try:
            IntegrationPriority[priority.upper()]
            return True
        except (ValueError, AttributeError):
            return False
