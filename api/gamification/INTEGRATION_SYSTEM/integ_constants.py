"""
Integration Constants — Constants and configuration for integration system.

This module provides all constants, configuration values, and enums
used throughout the integration system.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Integration Status Constants
# ---------------------------------------------------------------------------

class IntegrationStatus(Enum):
    """Integration status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    FAILED = "failed"
    DISABLED = "disabled"
    MAINTENANCE = "maintenance"


class IntegrationType(Enum):
    """Integration type enumeration."""
    WEBHOOK = "webhook"
    API = "api"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    FILE_SYSTEM = "file_system"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL_SERVICE = "internal_service"


class MessageType(Enum):
    """Message type enumeration."""
    REQUEST = "request"
    RESPONSE = "response"
    EVENT = "event"
    COMMAND = "command"
    NOTIFICATION = "notification"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class Priority(Enum):
    """Priority enumeration."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4
    URGENT = 5


# ---------------------------------------------------------------------------
# Timeout and Retry Constants
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 60  # seconds
CIRCUIT_BREAKER_TIMEOUT = 60  # seconds
CIRCUIT_BREAKER_FAILURE_THRESHOLD = 5
HEALTH_CHECK_INTERVAL = 30  # seconds
MESSAGE_RETENTION_PERIOD = 86400  # 24 hours in seconds


# ---------------------------------------------------------------------------
# Size and Limit Constants
# ---------------------------------------------------------------------------

MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_BATCH_SIZE = 1000
MAX_CONCURRENT_CONNECTIONS = 100
MAX_QUEUE_SIZE = 10000
MAX_RETRY_QUEUE_SIZE = 1000
MAX_LOG_ENTRY_SIZE = 1024 * 1024  # 1MB


# ---------------------------------------------------------------------------
# Protocol and Format Constants
# ---------------------------------------------------------------------------

SUPPORTED_PROTOCOLS = [
    "http",
    "https",
    "ws",
    "wss",
    "amqp",
    "mqtt",
    "tcp",
    "udp"
]

SUPPORTED_FORMATS = [
    "json",
    "xml",
    "yaml",
    "csv",
    "text",
    "binary"
]

DEFAULT_CONTENT_TYPE = "application/json"
DEFAULT_ENCODING = "utf-8"


# ---------------------------------------------------------------------------
# Security Constants
# ---------------------------------------------------------------------------

SUPPORTED_AUTH_TYPES = [
    "none",
    "basic",
    "bearer",
    "oauth2",
    "api_key",
    "jwt",
    "certificate"
]

DEFAULT_AUTH_TYPE = "none"
ENCRYPTION_ALGORITHMS = [
    "AES-256-GCM",
    "AES-256-CBC",
    "ChaCha20-Poly1305"
]
HASH_ALGORITHMS = [
    "SHA-256",
    "SHA-512",
    "BLAKE2b"
]


# ---------------------------------------------------------------------------
# Monitoring and Logging Constants
# ---------------------------------------------------------------------------

LOG_LEVELS = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL"
]

DEFAULT_LOG_LEVEL = "INFO"
METRIC_COLLECTION_INTERVAL = 60  # seconds
PERFORMANCE_HISTORY_SIZE = 1000  # entries


# ---------------------------------------------------------------------------
# Error Codes
# ---------------------------------------------------------------------------

class ErrorCode(Enum):
    """Standard error codes for integration system."""
    
    # General errors
    UNKNOWN_ERROR = "INT_000"
    INVALID_REQUEST = "INT_001"
    TIMEOUT_ERROR = "INT_002"
    CONNECTION_ERROR = "INT_003"
    AUTHENTICATION_ERROR = "INT_004"
    AUTHORIZATION_ERROR = "INT_005"
    
    # Data errors
    DATA_VALIDATION_ERROR = "INT_010"
    DATA_FORMAT_ERROR = "INT_011"
    DATA_SIZE_ERROR = "INT_012"
    DATA_CORRUPTION_ERROR = "INT_013"
    
    # System errors
    SYSTEM_OVERLOAD = "INT_020"
    RESOURCE_EXHAUSTED = "INT_021"
    SERVICE_UNAVAILABLE = "INT_022"
    RATE_LIMIT_EXCEEDED = "INT_023"
    
    # Integration errors
    INTEGRATION_NOT_FOUND = "INT_030"
    INTEGRATION_DISABLED = "INT_031"
    INTEGRATION_FAILED = "INT_032"
    INTEGRATION_TIMEOUT = "INT_033"
    
    # Circuit breaker errors
    CIRCUIT_BREAKER_OPEN = "INT_040"
    CIRCUIT_BREAKER_HALF_OPEN = "INT_041"
    
    # Queue errors
    QUEUE_FULL = "INT_050"
    QUEUE_EMPTY = "INT_051"
    QUEUE_TIMEOUT = "INT_052"
    
    # Version errors
    VERSION_MISMATCH = "INT_060"
    VERSION_NOT_SUPPORTED = "INT_061"
    
    # Sync errors
    SYNC_CONFLICT = "INT_070"
    SYNC_TIMEOUT = "INT_071"
    SYNC_FAILED = "INT_072"


# ---------------------------------------------------------------------------
# Configuration Templates
# ---------------------------------------------------------------------------

DEFAULT_WEBHOOK_CONFIG = {
    "url": "",
    "method": "POST",
    "headers": {},
    "timeout": DEFAULT_TIMEOUT,
    "retry_attempts": DEFAULT_RETRY_ATTEMPTS,
    "retry_delay": DEFAULT_RETRY_DELAY,
    "auth_type": DEFAULT_AUTH_TYPE,
    "auth_config": {},
    "enabled": True
}

DEFAULT_API_CONFIG = {
    "base_url": "",
    "version": "v1",
    "timeout": DEFAULT_TIMEOUT,
    "retry_attempts": DEFAULT_RETRY_ATTEMPTS,
    "retry_delay": DEFAULT_RETRY_DELAY,
    "auth_type": DEFAULT_AUTH_TYPE,
    "auth_config": {},
    "rate_limit": {
        "requests_per_second": 10,
        "burst_size": 20
    },
    "enabled": True
}

DEFAULT_DATABASE_CONFIG = {
    "connection_string": "",
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "enabled": True
}

DEFAULT_MESSAGE_QUEUE_CONFIG = {
    "broker_url": "",
    "exchange": "",
    "queue": "",
    "routing_key": "",
    "durable": True,
    "auto_delete": False,
    "max_priority": 5,
    "message_ttl": MESSAGE_RETENTION_PERIOD,
    "enabled": True
}


# ---------------------------------------------------------------------------
# Environment Variables
# ---------------------------------------------------------------------------

ENV_INTEGRATION_DEBUG = "INTEGRATION_DEBUG"
ENV_INTEGRATION_LOG_LEVEL = "INTEGRATION_LOG_LEVEL"
ENV_INTEGRATION_TIMEOUT = "INTEGRATION_TIMEOUT"
ENV_INTEGRATION_RETRY_ATTEMPTS = "INTEGRATION_RETRY_ATTEMPTS"
ENV_INTEGRATION_MAX_QUEUE_SIZE = "INTEGRATION_MAX_QUEUE_SIZE"
ENV_INTEGRATION_CIRCUIT_BREAKER_THRESHOLD = "INTEGRATION_CIRCUIT_BREAKER_THRESHOLD"


# ---------------------------------------------------------------------------
# Default Headers
# ---------------------------------------------------------------------------

DEFAULT_HEADERS = {
    "User-Agent": "Gamification-Integration/1.0",
    "Accept": "application/json",
    "Content-Type": DEFAULT_CONTENT_TYPE
}

TRACE_HEADERS = [
    "X-Request-ID",
    "X-Trace-ID",
    "X-Correlation-ID",
    "X-Parent-Request-ID"
]


# ---------------------------------------------------------------------------
# Validation Patterns
# ---------------------------------------------------------------------------

URL_PATTERN = r"^https?://[^\s/$.?#].[^\s]*$"
EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
API_KEY_PATTERN = r"^[a-zA-Z0-9_-]{20,64}$"


# ---------------------------------------------------------------------------
# Integration Categories
# ---------------------------------------------------------------------------

INTEGRATION_CATEGORIES = {
    "analytics": ["google_analytics", "mixpanel", "segment"],
    "communication": ["slack", "discord", "email", "sms"],
    "payment": ["stripe", "paypal", "square"],
    "storage": ["aws_s3", "google_cloud", "azure_blob"],
    "monitoring": ["datadog", "new_relic", "prometheus"],
    "authentication": ["auth0", "okta", "firebase_auth"],
    "database": ["postgresql", "mysql", "mongodb", "redis"],
    "messaging": ["rabbitmq", "kafka", "sqs", "pubsub"]
}


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

FEATURE_FLAGS = {
    "enable_circuit_breaker": True,
    "enable_retry_mechanism": True,
    "enable_rate_limiting": True,
    "enable_health_checks": True,
    "enable_metrics_collection": True,
    "enable_audit_logging": True,
    "enable_message_encryption": False,
    "enable_compression": True,
    "enable_async_processing": True,
    "enable_fallback_logic": True
}


# ---------------------------------------------------------------------------
# Performance Thresholds
# ---------------------------------------------------------------------------

PERFORMANCE_THRESHOLDS = {
    "response_time_warning": 1000,  # milliseconds
    "response_time_critical": 5000,  # milliseconds
    "error_rate_warning": 0.05,  # 5%
    "error_rate_critical": 0.10,  # 10%
    "queue_size_warning": 1000,
    "queue_size_critical": 5000,
    "memory_usage_warning": 0.80,  # 80%
    "memory_usage_critical": 0.95,  # 95%
    "cpu_usage_warning": 0.80,  # 80%
    "cpu_usage_critical": 0.95   # 95%
}


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def get_error_description(error_code: ErrorCode) -> str:
    """Get human-readable description for error code."""
    descriptions = {
        ErrorCode.UNKNOWN_ERROR: "An unknown error occurred",
        ErrorCode.INVALID_REQUEST: "The request is invalid",
        ErrorCode.TIMEOUT_ERROR: "The operation timed out",
        ErrorCode.CONNECTION_ERROR: "Failed to establish connection",
        ErrorCode.AUTHENTICATION_ERROR: "Authentication failed",
        ErrorCode.AUTHORIZATION_ERROR: "Authorization failed",
        ErrorCode.DATA_VALIDATION_ERROR: "Data validation failed",
        ErrorCode.DATA_FORMAT_ERROR: "Data format is invalid",
        ErrorCode.DATA_SIZE_ERROR: "Data size exceeds limits",
        ErrorCode.DATA_CORRUPTION_ERROR: "Data corruption detected",
        ErrorCode.SYSTEM_OVERLOAD: "System is overloaded",
        ErrorCode.RESOURCE_EXHAUSTED: "Resources are exhausted",
        ErrorCode.SERVICE_UNAVAILABLE: "Service is unavailable",
        ErrorCode.RATE_LIMIT_EXCEEDED: "Rate limit exceeded",
        ErrorCode.INTEGRATION_NOT_FOUND: "Integration not found",
        ErrorCode.INTEGRATION_DISABLED: "Integration is disabled",
        ErrorCode.INTEGRATION_FAILED: "Integration failed",
        ErrorCode.INTEGRATION_TIMEOUT: "Integration timeout",
        ErrorCode.CIRCUIT_BREAKER_OPEN: "Circuit breaker is open",
        ErrorCode.CIRCUIT_BREAKER_HALF_OPEN: "Circuit breaker is half-open",
        ErrorCode.QUEUE_FULL: "Queue is full",
        ErrorCode.QUEUE_EMPTY: "Queue is empty",
        ErrorCode.QUEUE_TIMEOUT: "Queue operation timeout",
        ErrorCode.VERSION_MISMATCH: "Version mismatch",
        ErrorCode.VERSION_NOT_SUPPORTED: "Version not supported",
        ErrorCode.SYNC_CONFLICT: "Synchronization conflict",
        ErrorCode.SYNC_TIMEOUT: "Synchronization timeout",
        ErrorCode.SYNC_FAILED: "Synchronization failed"
    }
    return descriptions.get(error_code, "Unknown error code")


def get_config_template(integration_type: IntegrationType) -> Dict[str, Any]:
    """Get default configuration template for integration type."""
    templates = {
        IntegrationType.WEBHOOK: DEFAULT_WEBHOOK_CONFIG,
        IntegrationType.API: DEFAULT_API_CONFIG,
        IntegrationType.DATABASE: DEFAULT_DATABASE_CONFIG,
        IntegrationType.MESSAGE_QUEUE: DEFAULT_MESSAGE_QUEUE_CONFIG
    }
    return templates.get(integration_type, {})


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature flag is enabled."""
    return FEATURE_FLAGS.get(feature_name, False)


def get_performance_threshold(threshold_name: str) -> Any:
    """Get performance threshold value."""
    return PERFORMANCE_THRESHOLDS.get(threshold_name)


# Initialize logging
logger.info("Integration constants module initialized")
