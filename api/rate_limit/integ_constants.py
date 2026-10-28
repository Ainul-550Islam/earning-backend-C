# api/rate_limit/integ_constants.py
"""
Constants for integration system.

Provides enums and constants for integration management.
"""

from enum import Enum
from typing import Dict, Any, List


class IntegrationType:
    """Integration type constants."""
    
    WEBHOOK = 'webhook'
    API = 'api'
    DATABASE = 'database'
    MESSAGE_QUEUE = 'message_queue'
    EMAIL = 'email'
    SLACK = 'slack'
    CUSTOM = 'custom'
    
    CHOICES = [
        (WEBHOOK, 'Webhook'),
        (API, 'REST API'),
        (DATABASE, 'Database'),
        (MESSAGE_QUEUE, 'Message Queue'),
        (EMAIL, 'Email'),
        (SLACK, 'Slack'),
        (CUSTOM, 'Custom'),
    ]
    
    DESCRIPTIONS = {
        WEBHOOK: 'HTTP webhook integration for real-time event delivery',
        API: 'REST API integration for external service communication',
        DATABASE: 'Database integration for data storage and retrieval',
        MESSAGE_QUEUE: 'Message queue integration for asynchronous processing',
        EMAIL: 'Email integration for notification delivery',
        SLACK: 'Slack integration for team communication',
        CUSTOM: 'Custom integration for specialized requirements'
    }


class IntegrationStatus:
    """Integration status constants."""
    
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    ERROR = 'error'
    DEGRADED = 'degraded'
    MAINTENANCE = 'maintenance'
    
    CHOICES = [
        (ACTIVE, 'Active'),
        (INACTIVE, 'Inactive'),
        (ERROR, 'Error'),
        (DEGRADED, 'Degraded'),
        (MAINTENANCE, 'Maintenance'),
    ]
    
    DESCRIPTIONS = {
        ACTIVE: 'Integration is fully operational',
        INACTIVE: 'Integration is not active',
        ERROR: 'Integration has encountered an error',
        DEGRADED: 'Integration is operational with reduced functionality',
        MAINTENANCE: 'Integration is under maintenance'
    }


class IntegrationEvent:
    """Integration event constants."""
    
    RATE_LIMIT_EXCEEDED = 'rate_limit_exceeded'
    RATE_LIMIT_ALLOWED = 'rate_limit_allowed'
    ABUSE_DETECTED = 'abuse_detected'
    CONFIG_CREATED = 'config_created'
    CONFIG_UPDATED = 'config_updated'
    CONFIG_DELETED = 'config_deleted'
    USER_PROFILE_CREATED = 'user_profile_created'
    USER_PROFILE_UPDATED = 'user_profile_updated'
    USER_PROFILE_DELETED = 'user_profile_deleted'
    IP_BLOCKED = 'ip_blocked'
    IP_UNBLOCKED = 'ip_unblocked'
    SYSTEM_ALERT = 'system_alert'
    HEALTH_CHECK = 'health_check'
    INTEGRATION_SUCCESS = 'integration_success'
    INTEGRATION_FAILURE = 'integration_failure'
    INTEGRATION_ERROR = 'integration_error'
    STATUS_CHANGE = 'status_change'
    PERFORMANCE_UPDATE = 'performance_update'
    
    CHOICES = [
        (RATE_LIMIT_EXCEEDED, 'Rate Limit Exceeded'),
        (RATE_LIMIT_ALLOWED, 'Rate Limit Allowed'),
        (ABUSE_DETECTED, 'Abuse Detected'),
        (CONFIG_CREATED, 'Config Created'),
        (CONFIG_UPDATED, 'Config Updated'),
        (CONFIG_DELETED, 'Config Deleted'),
        (USER_PROFILE_CREATED, 'User Profile Created'),
        (USER_PROFILE_UPDATED, 'User Profile Updated'),
        (USER_PROFILE_DELETED, 'User Profile Deleted'),
        (IP_BLOCKED, 'IP Blocked'),
        (IP_UNBLOCKED, 'IP Unblocked'),
        (SYSTEM_ALERT, 'System Alert'),
        (HEALTH_CHECK, 'Health Check'),
        (INTEGRATION_SUCCESS, 'Integration Success'),
        (INTEGRATION_FAILURE, 'Integration Failure'),
        (INTEGRATION_ERROR, 'Integration Error'),
        (STATUS_CHANGE, 'Status Change'),
        (PERFORMANCE_UPDATE, 'Performance Update'),
    ]
    
    CATEGORIES = {
        'rate_limit': [RATE_LIMIT_EXCEEDED, RATE_LIMIT_ALLOWED],
        'abuse': [ABUSE_DETECTED],
        'config': [CONFIG_CREATED, CONFIG_UPDATED, CONFIG_DELETED],
        'user': [USER_PROFILE_CREATED, USER_PROFILE_UPDATED, USER_PROFILE_DELETED],
        'security': [IP_BLOCKED, IP_UNBLOCKED],
        'system': [SYSTEM_ALERT, HEALTH_CHECK],
        'integration': [INTEGRATION_SUCCESS, INTEGRATION_FAILURE, INTEGRATION_ERROR, STATUS_CHANGE, PERFORMANCE_UPDATE]
    }


class IntegrationPriority:
    """Integration priority constants."""
    
    LOW = 'low'
    NORMAL = 'normal'
    HIGH = 'high'
    CRITICAL = 'critical'
    
    CHOICES = [
        (LOW, 'Low'),
        (NORMAL, 'Normal'),
        (HIGH, 'High'),
        (CRITICAL, 'Critical'),
    ]
    
    NUMERIC_VALUES = {
        LOW: 1,
        NORMAL: 2,
        HIGH: 3,
        CRITICAL: 4
    }


class IntegrationCategory:
    """Integration category constants."""
    
    MONITORING = 'monitoring'
    NOTIFICATION = 'notification'
    ANALYTICS = 'analytics'
    SECURITY = 'security'
    DATA_STORAGE = 'data_storage'
    COMMUNICATION = 'communication'
    AUTOMATION = 'automation'
    COMPLIANCE = 'compliance'
    
    CHOICES = [
        (MONITORING, 'Monitoring'),
        (NOTIFICATION, 'Notification'),
        (ANALYTICS, 'Analytics'),
        (SECURITY, 'Security'),
        (DATA_STORAGE, 'Data Storage'),
        (COMMUNICATION, 'Communication'),
        (AUTOMATION, 'Automation'),
        (COMPLIANCE, 'Compliance'),
    ]
    
    DESCRIPTIONS = {
        MONITORING: 'Integrations for system monitoring and health checks',
        NOTIFICATION: 'Integrations for sending notifications and alerts',
        ANALYTICS: 'Integrations for analytics and reporting',
        SECURITY: 'Integrations for security and threat detection',
        DATA_STORAGE: 'Integrations for data storage and archiving',
        COMMUNICATION: 'Integrations for team communication',
        AUTOMATION: 'Integrations for workflow automation',
        COMPLIANCE: 'Integrations for compliance and audit'
    }


class IntegrationTag:
    """Integration tag constants."""
    
    REAL_TIME = 'real_time'
    BATCH = 'batch'
    ASYNC = 'async'
    SYNC = 'sync'
    SECURE = 'secure'
    PUBLIC = 'public'
    INTERNAL = 'internal'
    THIRD_PARTY = 'third_party'
    ENTERPRISE = 'enterprise'
    OPEN_SOURCE = 'open_source'
    
    CHOICES = [
        (REAL_TIME, 'Real-time'),
        (BATCH, 'Batch'),
        (ASYNC, 'Asynchronous'),
        (SYNC, 'Synchronous'),
        (SECURE, 'Secure'),
        (PUBLIC, 'Public'),
        (INTERNAL, 'Internal'),
        (THIRD_PARTY, 'Third-party'),
        (ENTERPRISE, 'Enterprise'),
        (OPEN_SOURCE, 'Open Source'),
    ]
    
    DESCRIPTIONS = {
        REAL_TIME: 'Real-time event processing',
        BATCH: 'Batch processing capabilities',
        ASYNC: 'Asynchronous processing',
        SYNC: 'Synchronous processing',
        SECURE: 'Secure communication',
        PUBLIC: 'Publicly accessible',
        INTERNAL: 'Internal use only',
        THIRD_PARTY: 'Third-party service',
        ENTERPRISE: 'Enterprise-grade',
        OPEN_SOURCE: 'Open source solution'
    }


class IntegrationConfig:
    """Default configuration constants."""
    
    DEFAULT_TIMEOUT = 30  # seconds
    DEFAULT_RETRY_ATTEMPTS = 3
    DEFAULT_RETRY_DELAY = 1  # seconds
    DEFAULT_RATE_LIMIT = 100  # requests per minute
    DEFAULT_BATCH_SIZE = 100
    DEFAULT_CACHE_TIMEOUT = 300  # seconds
    
    WEBHOOK_DEFAULTS = {
        'timeout': DEFAULT_TIMEOUT,
        'retry_attempts': DEFAULT_RETRY_ATTEMPTS,
        'retry_delay': DEFAULT_RETRY_DELAY,
        'verify_ssl': True,
        'user_agent': 'RateLimit-Integration/1.0'
    }
    
    API_DEFAULTS = {
        'timeout': DEFAULT_TIMEOUT,
        'retry_attempts': DEFAULT_RETRY_ATTEMPTS,
        'retry_delay': DEFAULT_RETRY_DELAY,
        'verify_ssl': True,
        'rate_limit': DEFAULT_RATE_LIMIT,
        'user_agent': 'RateLimit-Integration/1.0'
    }
    
    DATABASE_DEFAULTS = {
        'connection_timeout': DEFAULT_TIMEOUT,
        'query_timeout': DEFAULT_TIMEOUT,
        'pool_size': 10,
        'max_overflow': 20
    }
    
    MESSAGE_QUEUE_DEFAULTS = {
        'connection_timeout': DEFAULT_TIMEOUT,
        'prefetch_count': 10,
        'ack_timeout': 30,
        'retry_delay': DEFAULT_RETRY_DELAY,
        'max_retries': DEFAULT_RETRY_ATTEMPTS
    }
    
    EMAIL_DEFAULTS = {
        'smtp_timeout': DEFAULT_TIMEOUT,
        'retry_attempts': DEFAULT_RETRY_ATTEMPTS,
        'retry_delay': DEFAULT_RETRY_DELAY,
        'use_tls': True
    }
    
    SLACK_DEFAULTS = {
        'timeout': DEFAULT_TIMEOUT,
        'retry_attempts': DEFAULT_RETRY_ATTEMPTS,
        'retry_delay': DEFAULT_RETRY_DELAY,
        'username': 'RateLimitBot'
    }


class IntegrationMetrics:
    """Integration performance metrics constants."""
    
    METRICS = [
        'total_requests',
        'successful_requests',
        'failed_requests',
        'avg_response_time',
        'max_response_time',
        'min_response_time',
        'error_rate',
        'throughput',
        'last_request_time',
        'uptime_percentage',
        'memory_usage',
        'cpu_usage'
    ]
    
    THRESHOLDS = {
        'response_time_warning': 5.0,  # seconds
        'response_time_critical': 10.0,  # seconds
        'error_rate_warning': 0.05,  # 5%
        'error_rate_critical': 0.10,  # 10%
        'throughput_warning': 10,  # requests per minute
        'uptime_warning': 0.95,  # 95%
        'uptime_critical': 0.90,  # 90%
    }
    
    RETENTION_PERIODS = {
        'real_time_metrics': 3600,  # 1 hour
        'hourly_metrics': 86400 * 7,  # 7 days
        'daily_metrics': 86400 * 30,  # 30 days
        'monthly_metrics': 86400 * 365,  # 1 year
    }


class IntegrationSecurity:
    """Integration security constants."""
    
    ENCRYPTION_ALGORITHMS = ['AES-256-GCM', 'AES-256-CBC', 'Fernet']
    
    AUTH_TYPES = [
        'api_key',
        'oauth2',
        'basic_auth',
        'bearer_token',
        'signature',
        'certificate'
    ]
    
    PERMISSION_LEVELS = [
        'read',
        'write',
        'admin',
        'owner'
    ]
    
    RATE_LIMIT_POLICIES = {
        'conservative': {
            'requests_per_minute': 10,
            'burst_size': 20
        },
        'moderate': {
            'requests_per_minute': 60,
            'burst_size': 120
        },
        'aggressive': {
            'requests_per_minute': 300,
            'burst_size': 600
        }
    }
    
    SECURITY_HEADERS = [
        'X-RateLimit-Limit',
        'X-RateLimit-Remaining',
        'X-RateLimit-Reset',
        'X-Integration-ID',
        'X-Request-ID'
    ]


class IntegrationErrors:
    """Integration error codes and messages."""
    
    ERROR_CODES = {
        'CONNECTION_FAILED': 'E001',
        'TIMEOUT': 'E002',
        'AUTHENTICATION_FAILED': 'E003',
        'AUTHORIZATION_FAILED': 'E004',
        'RATE_LIMIT_EXCEEDED': 'E005',
        'INVALID_REQUEST': 'E006',
        'SERVER_ERROR': 'E007',
        'NETWORK_ERROR': 'E008',
        'PARSING_ERROR': 'E009',
        'VALIDATION_ERROR': 'E010',
        'CONFIGURATION_ERROR': 'E011',
        'ADAPTER_NOT_FOUND': 'E012',
        'INTEGRATION_DISABLED': 'E013'
    }
    
    ERROR_MESSAGES = {
        'CONNECTION_FAILED': 'Failed to establish connection to integration service',
        'TIMEOUT': 'Request timed out',
        'AUTHENTICATION_FAILED': 'Authentication credentials are invalid',
        'AUTHORIZATION_FAILED': 'Insufficient permissions for requested action',
        'RATE_LIMIT_EXCEEDED': 'Rate limit has been exceeded',
        'INVALID_REQUEST': 'Request format or parameters are invalid',
        'SERVER_ERROR': 'Integration service returned server error',
        'NETWORK_ERROR': 'Network connectivity issue',
        'PARSING_ERROR': 'Failed to parse response data',
        'VALIDATION_ERROR': 'Request data validation failed',
        'CONFIGURATION_ERROR': 'Integration configuration is invalid',
        'ADAPTER_NOT_FOUND': 'Integration adapter not found',
        'INTEGRATION_DISABLED': 'Integration is currently disabled'
    }
    
    RECOVERY_ACTIONS = {
        'CONNECTION_FAILED': 'Check network connectivity and service availability',
        'TIMEOUT': 'Increase timeout or check service performance',
        'AUTHENTICATION_FAILED': 'Verify authentication credentials',
        'AUTHORIZATION_FAILED': 'Check user permissions',
        'RATE_LIMIT_EXCEEDED': 'Wait and retry with exponential backoff',
        'INVALID_REQUEST': 'Validate request format and parameters',
        'SERVER_ERROR': 'Retry with exponential backoff',
        'NETWORK_ERROR': 'Check network configuration',
        'PARSING_ERROR': 'Verify response format and data types',
        'VALIDATION_ERROR': 'Check request data against schema',
        'CONFIGURATION_ERROR': 'Review and fix integration configuration',
        'ADAPTER_NOT_FOUND': 'Register the required adapter',
        'INTEGRATION_DISABLED': 'Enable the integration'
    }


# Validation schemas
INTEGRATION_SCHEMA = {
    'type': 'object',
    'properties': {
        'id': {'type': 'string', 'minLength': 1},
        'name': {'type': 'string', 'minLength': 1},
        'type': {'type': 'string', 'enum': IntegrationType.CHOICES},
        'config': {'type': 'object'},
        'enabled': {'type': 'boolean'},
        'category': {'type': 'string', 'enum': IntegrationCategory.CHOICES},
        'tags': {
            'type': 'array',
            'items': {'type': 'string', 'enum': IntegrationTag.CHOICES}
        }
    },
    'required': ['id', 'name', 'type', 'enabled']
}

WEBHOOK_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'webhook_url': {'type': 'string', 'format': 'uri'},
        'secret_key': {'type': 'string'},
        'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 300},
        'headers': {'type': 'object'},
        'verify_ssl': {'type': 'boolean'}
    },
    'required': ['webhook_url']
}

API_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'base_url': {'type': 'string', 'format': 'uri'},
        'api_key': {'type': 'string'},
        'auth_type': {'type': 'string', 'enum': IntegrationSecurity.AUTH_TYPES},
        'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 300},
        'headers': {'type': 'object'},
        'verify_ssl': {'type': 'boolean'}
    },
    'required': ['base_url']
}

DATABASE_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'database_url': {'type': 'string'},
        'table_name': {'type': 'string'},
        'connection_timeout': {'type': 'integer', 'minimum': 1},
        'pool_size': {'type': 'integer', 'minimum': 1}
    },
    'required': ['database_url']
}

MESSAGE_QUEUE_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'connection_url': {'type': 'string'},
        'queue_name': {'type': 'string'},
        'exchange': {'type': 'string'},
        'prefetch_count': {'type': 'integer', 'minimum': 1}
    },
    'required': ['connection_url', 'queue_name']
}

EMAIL_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'smtp_host': {'type': 'string'},
        'smtp_port': {'type': 'integer', 'minimum': 1, 'maximum': 65535},
        'smtp_username': {'type': 'string'},
        'smtp_password': {'type': 'string'},
        'from_email': {'type': 'string', 'format': 'email'},
        'to_emails': {
            'type': 'array',
            'items': {'type': 'string', 'format': 'email'}
        },
        'use_tls': {'type': 'boolean'}
    },
    'required': ['smtp_host', 'smtp_port', 'from_email']
}

SLACK_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'webhook_url': {'type': 'string', 'format': 'uri'},
        'channel': {'type': 'string'},
        'username': {'type': 'string'},
        'timeout': {'type': 'integer', 'minimum': 1, 'maximum': 300}
    },
    'required': ['webhook_url', 'channel']
}


# Export all constants
__all__ = [
    'IntegrationType',
    'IntegrationStatus',
    'IntegrationEvent',
    'IntegrationPriority',
    'IntegrationCategory',
    'IntegrationTag',
    'IntegrationConfig',
    'IntegrationMetrics',
    'IntegrationSecurity',
    'IntegrationErrors',
    'INTEGRATION_SCHEMA',
    'WEBHOOK_CONFIG_SCHEMA',
    'API_CONFIG_SCHEMA',
    'DATABASE_CONFIG_SCHEMA',
    'MESSAGE_QUEUE_CONFIG_SCHEMA',
    'EMAIL_CONFIG_SCHEMA',
    'SLACK_CONFIG_SCHEMA'
]
