"""
Integration Constants

Constants for integration system configuration and types.
"""

from enum import Enum


class IntegrationType(Enum):
    """Integration types."""
    WEBHOOK = "webhook"
    API = "api"
    DATABASE = "database"
    MESSAGE_QUEUE = "message_queue"
    EMAIL = "email"
    SMS = "sms"
    PUSH_NOTIFICATION = "push_notification"
    FILE_STORAGE = "file_storage"
    CACHE = "cache"
    LOGGING = "logging"
    MONITORING = "monitoring"


class IntegrationStatus(Enum):
    """Integration status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"
    DISABLED = "disabled"
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


class IntegrationPriority(Enum):
    """Integration priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IntegrationEvent(Enum):
    """Integration event types."""
    REGISTERED = "registered"
    UPDATED = "updated"
    ENABLED = "enabled"
    DISABLED = "disabled"
    REMOVED = "removed"
    EXECUTED = "executed"
    FAILED = "failed"
    SYNCED = "synced"
    ERROR_OCCURRED = "error_occurred"


class IntegrationLogLevel(Enum):
    """Integration logging levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Integration configuration constants
DEFAULT_INTEGRATION_TIMEOUT = 30  # seconds
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1  # seconds
DEFAULT_BATCH_SIZE = 100
DEFAULT_SYNC_INTERVAL = 300  # seconds (5 minutes)
MAX_INTEGRATION_CONFIG_SIZE = 1024 * 1024  # 1MB
INTEGRATION_CACHE_TIMEOUT = 3600  # 1 hour
INTEGRATION_REGISTRY_CACHE_KEY = "integration_registry"
INTEGRATION_STATUS_CACHE_KEY = "integration_status"

# Integration error codes
INTEGRATION_ERROR_CODES = {
    "INVALID_CONFIG": "E001",
    "MISSING_DEPENDENCY": "E002",
    "TIMEOUT": "E003",
    "RATE_LIMIT": "E004",
    "AUTHENTICATION_FAILED": "E005",
    "AUTHORIZATION_DENIED": "E006",
    "ENDPOINT_UNREACHABLE": "E007",
    "INVALID_RESPONSE": "E008",
    "CONNECTION_FAILED": "E009",
    "DATA_VALIDATION_FAILED": "E010",
    "SYNC_FAILED": "E011",
    "VERSION_MISMATCH": "E012",
    "DEPENDENCY_CONFLICT": "E013",
    "CIRCULAR_DEPENDENCY": "E014"
}

# Integration performance thresholds
INTEGRATION_PERFORMANCE_THRESHOLDS = {
    "slow_response_time": 5.0,  # seconds
    "high_error_rate": 0.1,  # 10%
    "low_success_rate": 0.9,  # 90%
    "max_retry_count": 3,
    "max_timeout_count": 5,
    "slow_sync_time": 60.0  # seconds
}

# Integration security constants
INTEGRATION_SECURITY_CONSTANTS = {
    "max_api_key_length": 256,
    "max_secret_length": 512,
    "token_expiry": 3600,  # 1 hour
    "max_request_size": 1024 * 1024,  # 1MB
    "rate_limit_window": 3600,  # 1 hour
    "max_requests_per_window": 1000
}
