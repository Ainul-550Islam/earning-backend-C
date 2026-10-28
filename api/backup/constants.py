"""
Backup Module Constants
Configuration constants for backup operations and limits
"""

# Backup size limits
MAX_BACKUP_SIZE_GB = 100
MAX_BACKUP_SIZE_BYTES = MAX_BACKUP_SIZE_GB * 1024 * 1024 * 1024
MAX_BACKUP_SIZE_MB = MAX_BACKUP_SIZE_GB * 1024

# Retention policies
DEFAULT_RETENTION_DAYS = 30
MIN_RETENTION_DAYS = 1
MAX_RETENTION_DAYS = 365

# Backup processing
BACKUP_CHUNK_SIZE = 1024 * 1024 * 10  # 10MB chunks
MAX_CONCURRENT_BACKUPS = 2
BACKUP_TIMEOUT_SECONDS = 3600 * 24  # 24 hours
RESTORE_TIMEOUT_SECONDS = 3600 * 48  # 48 hours

# Compression settings
DEFAULT_COMPRESSION_LEVEL = 6
MIN_COMPRESSION_LEVEL = 1
MAX_COMPRESSION_LEVEL = 9
COMPRESSION_LEVELS = {
    'gzip': (1, 9),
    'bzip2': (1, 9),
    'lzma': (0, 9),
    'zip': (0, 9),
    'zstd': (1, 22)
}

# Encryption settings
ENCRYPTION_KEY_LENGTH = 32  # 256 bits
ENCRYPTION_IV_LENGTH = 16   # 128 bits
ENCRYPTION_SALT_LENGTH = 16  # 128 bits

# Storage settings
STORAGE_RETRY_ATTEMPTS = 3
STORAGE_RETRY_DELAY = 5  # seconds
STORAGE_CONNECTION_TIMEOUT = 30  # seconds
STORAGE_UPLOAD_TIMEOUT = 3600  # seconds (1 hour)

# Database settings
DATABASE_DUMP_TIMEOUT = 3600 * 4  # 4 hours
DATABASE_RESTORE_TIMEOUT = 3600 * 8  # 8 hours
MAX_DATABASE_SIZE_GB = 50  # Maximum database size for backup

# Verification settings
VERIFICATION_TIMEOUT = 3600 * 2  # 2 hours
VERIFICATION_RETRY_ATTEMPTS = 3
VERIFICATION_SAMPLE_SIZE = 1024 * 1024  # 1MB sample for hash verification

# Notification settings
NOTIFICATION_RETRY_ATTEMPTS = 3
NOTIFICATION_RETRY_DELAY = 60  # seconds
NOTIFICATION_TIMEOUT = 30  # seconds

# Logging settings
LOG_RETENTION_DAYS = 90
MAX_LOG_SIZE_MB = 100
LOG_BATCH_SIZE = 1000

# Performance settings
PERFORMANCE_SAMPLE_INTERVAL = 60  # seconds
MAX_MEMORY_USAGE_MB = 1024  # 1GB
MAX_CPU_USAGE_PERCENT = 80

# Security settings
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15
SESSION_TIMEOUT_MINUTES = 120

# Backup schedule settings
SCHEDULE_LEeway_MINUTES = 5  # Allow 5 minutes variance
MAX_SCHEDULED_BACKUPS_PER_DAY = 24
SCHEDULE_CLEANUP_HOURS = 2  # Run cleanup at 2 AM

# File system settings
MAX_FILENAME_LENGTH = 255
TEMP_FILE_CLEANUP_HOURS = 24
MAX_TEMP_STORAGE_GB = 10

# API settings
API_RATE_LIMIT = 100  # requests per minute
API_TIMEOUT_SECONDS = 300  # 5 minutes
MAX_API_RESPONSE_SIZE_MB = 100

# Monitoring settings
HEALTH_CHECK_INTERVAL_SECONDS = 300  # 5 minutes
METRICS_RETENTION_DAYS = 30
ALERT_COOLDOWN_MINUTES = 15

# Backup validation settings
MIN_BACKUP_SIZE_MB = 1  # Minimum backup size to consider valid
MAX_BACKUP_AGE_DAYS = 730  # Maximum age for backup to be considered valid
CORRUPTION_DETECTION_THRESHOLD = 0.1  # 10% corruption threshold

# Storage class mappings
AWS_STORAGE_CLASSES = {
    'STANDARD': 'STANDARD',
    'REDUCED_REDUNDANCY': 'REDUCED_REDUNDANCY',
    'STANDARD_IA': 'STANDARD_IA',
    'ONEZONE_IA': 'ONEZONE_IA',
    'INTELLIGENT_TIERING': 'INTELLIGENT_TIERING',
    'GLACIER': 'GLACIER',
    'DEEP_ARCHIVE': 'DEEP_ARCHIVE'
}

GCS_STORAGE_CLASSES = {
    'STANDARD': 'STANDARD',
    'NEARLINE': 'NEARLINE',
    'COLDLINE': 'COLDLINE',
    'ARCHIVE': 'ARCHIVE'
}

AZURE_STORAGE_TIERS = {
    'HOT': 'Hot',
    'COOL': 'Cool',
    'ARCHIVE': 'Archive'
}

# Database engine specific settings
DATABASE_ENGINE_DEFAULTS = {
    'postgresql': {
        'port': 5432,
        'timeout': 30,
        'dump_tool': 'pg_dump',
        'restore_tool': 'psql',
        'default_format': 'custom'
    },
    'mysql': {
        'port': 3306,
        'timeout': 30,
        'dump_tool': 'mysqldump',
        'restore_tool': 'mysql',
        'default_format': 'sql'
    },
    'sqlite': {
        'timeout': 30,
        'dump_tool': 'cp',
        'restore_tool': 'cp',
        'default_format': 'db'
    }
}

# Backup type specific settings
BACKUP_TYPE_SETTINGS = {
    'full': {
        'retention_multiplier': 1.0,
        'priority': 1,
        'max_age_days': 90
    },
    'incremental': {
        'retention_multiplier': 0.5,
        'priority': 2,
        'max_age_days': 30
    },
    'differential': {
        'retention_multiplier': 0.7,
        'priority': 2,
        'max_age_days': 60
    },
    'delta': {
        'retention_multiplier': 0.3,
        'priority': 3,
        'max_age_days': 14
    }
}

# Compression algorithm settings
COMPRESSION_ALGORITHM_SETTINGS = {
    'gzip': {
        'speed': 'fast',
        'ratio': 'medium',
        'cpu_usage': 'low',
        'memory_usage': 'low'
    },
    'bzip2': {
        'speed': 'slow',
        'ratio': 'high',
        'cpu_usage': 'high',
        'memory_usage': 'medium'
    },
    'lzma': {
        'speed': 'very_slow',
        'ratio': 'very_high',
        'cpu_usage': 'very_high',
        'memory_usage': 'high'
    },
    'zip': {
        'speed': 'medium',
        'ratio': 'medium',
        'cpu_usage': 'medium',
        'memory_usage': 'low'
    },
    'zstd': {
        'speed': 'fast',
        'ratio': 'high',
        'cpu_usage': 'medium',
        'memory_usage': 'low'
    }
}

# Encryption algorithm settings
ENCRYPTION_ALGORITHM_SETTINGS = {
    'AES-256-GCM': {
        'key_size': 32,
        'iv_size': 12,
        'tag_size': 16,
        'speed': 'fast',
        'security': 'high'
    },
    'AES-256-CBC': {
        'key_size': 32,
        'iv_size': 16,
        'speed': 'medium',
        'security': 'high'
    },
    'ChaCha20-Poly1305': {
        'key_size': 32,
        'nonce_size': 12,
        'speed': 'fast',
        'security': 'high'
    },
    'Fernet': {
        'key_size': 32,
        'iv_size': 16,
        'speed': 'medium',
        'security': 'high'
    }
}

# Notification channel settings
NOTIFICATION_CHANNEL_SETTINGS = {
    'email': {
        'timeout': 30,
        'retry_attempts': 3,
        'max_attachments': 5,
        'max_attachment_size_mb': 25
    },
    'webhook': {
        'timeout': 30,
        'retry_attempts': 3,
        'max_payload_size_mb': 10
    },
    'slack': {
        'timeout': 30,
        'retry_attempts': 3,
        'max_message_length': 4000
    },
    'teams': {
        'timeout': 30,
        'retry_attempts': 3,
        'max_message_length': 28000
    },
    'sms': {
        'timeout': 60,
        'retry_attempts': 3,
        'max_message_length': 160
    },
    'push': {
        'timeout': 30,
        'retry_attempts': 3,
        'max_payload_size_kb': 4
    }
}

# Alert severity settings
ALERT_SEVERITY_SETTINGS = {
    'low': {
        'priority': 1,
        'escalation_minutes': 60,
        'auto_resolve_hours': 24
    },
    'medium': {
        'priority': 2,
        'escalation_minutes': 30,
        'auto_resolve_hours': 12
    },
    'high': {
        'priority': 3,
        'escalation_minutes': 15,
        'auto_resolve_hours': 6
    },
    'critical': {
        'priority': 4,
        'escalation_minutes': 5,
        'auto_resolve_hours': 1
    }
}

# Health check thresholds
HEALTH_CHECK_THRESHOLDS = {
    'disk_usage_percent': 80,
    'memory_usage_percent': 85,
    'cpu_usage_percent': 90,
    'backup_success_rate_percent': 95,
    'storage_availability_percent': 99,
    'response_time_seconds': 5
}

# Performance metrics
PERFORMANCE_METRICS = {
    'backup_duration_seconds': {
        'good': 3600,      # 1 hour
        'warning': 7200,   # 2 hours
        'critical': 14400  # 4 hours
    },
    'restore_duration_seconds': {
        'good': 7200,      # 2 hours
        'warning': 14400,  # 4 hours
        'critical': 28800  # 8 hours
    },
    'compression_ratio': {
        'good': 0.5,      # 50% compression
        'warning': 0.7,   # 30% compression
        'critical': 0.9   # 10% compression
    },
    'verification_time_seconds': {
        'good': 300,      # 5 minutes
        'warning': 900,   # 15 minutes
        'critical': 1800  # 30 minutes
    }
}

# File naming patterns
BACKUP_FILENAME_PATTERNS = {
    'default': '{name}_{timestamp}.{extension}',
    'date_hierarchy': '{year}/{month}/{day}/{name}_{timestamp}.{extension}',
    'with_hash': '{name}_{timestamp}_{hash}.{extension}',
    'with_type': '{name}_{type}_{timestamp}.{extension}'
}

# Metadata fields
BACKUP_METADATA_FIELDS = [
    'backup_id',
    'backup_name',
    'backup_type',
    'database_name',
    'database_engine',
    'created_at',
    'created_by',
    'file_size',
    'file_hash',
    'compression_enabled',
    'compression_method',
    'compression_level',
    'encryption_enabled',
    'encryption_method',
    'storage_type',
    'storage_location',
    'retention_days',
    'tags',
    'description',
    'environment',
    'version'
]

# Export formats
EXPORT_FORMATS = {
    'csv': {
        'mime_type': 'text/csv',
        'extension': '.csv',
        'max_size_mb': 100
    },
    'json': {
        'mime_type': 'application/json',
        'extension': '.json',
        'max_size_mb': 200
    },
    'xlsx': {
        'mime_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'extension': '.xlsx',
        'max_size_mb': 50
    },
    'pdf': {
        'mime_type': 'application/pdf',
        'extension': '.pdf',
        'max_size_mb': 20
    }
}

# Pagination settings
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1

# Cache settings
CACHE_TIMEOUT_SECONDS = 300  # 5 minutes
CACHE_KEY_PREFIX = 'backup_'
CACHE_VERSION = 1

# Rate limiting settings
RATE_LIMITS = {
    'backup_create': '10/hour',
    'backup_restore': '5/hour',
    'backup_download': '20/hour',
    'backup_delete': '10/hour',
    'backup_list': '1000/hour'
}

# Security settings
ALLOWED_FILE_EXTENSIONS = [
    '.sql', '.sql.gz', '.sql.bz2', '.sql.xz', '.sql.zst',
    '.dump', '.backup', '.bak', '.zip', '.tar.gz'
]

BLOCKED_FILE_PATTERNS = [
    '*.exe', '*.bat', '*.cmd', '*.com', '*.pif',
    '*.scr', '*.vbs', '*.js', '*.jar', '*.app'
]

# Environment settings
ENVIRONMENT_TYPES = ['development', 'staging', 'production']
DEFAULT_ENVIRONMENT = 'production'

# Feature flags
FEATURE_FLAGS = {
    'enable_compression': True,
    'enable_encryption': True,
    'enable_verification': True,
    'enable_notifications': True,
    'enable_scheduling': True,
    'enable_monitoring': True,
    'enable_auditing': True
}

# Celery task settings
CELERY_TASK_SETTINGS = {
    'max_retries': 3,
    'retry_delay': 60,  # seconds
    'retry_backoff': True,
    'retry_jitter': True,
    'task_timeout': 3600 * 24,  # 24 hours
    'soft_time_limit': 3600 * 23,  # 23 hours
    'time_limit': 3600 * 24  # 24 hours
}

# GFS retention settings
GFS_RETENTION_SETTINGS = {
    'daily_backups': 7,      # Keep 7 daily backups
    'weekly_backups': 4,     # Keep 4 weekly backups
    'monthly_backups': 12,   # Keep 12 monthly backups
    'yearly_backups': 3      # Keep 3 yearly backups
}

# Backup verification settings
VERIFICATION_SETTINGS = {
    'hash_algorithms': ['sha256', 'md5', 'sha1'],
    'default_hash_algorithm': 'sha256',
    'test_restore_timeout': 3600,  # 1 hour
    'full_verification_timeout': 7200,  # 2 hours
    'sample_size_bytes': 1024 * 1024,  # 1MB
    'parallel_verifications': 2
}

# Cleanup settings
CLEANUP_SETTINGS = {
    'batch_size': 100,
    'max_concurrent_cleanups': 1,
    'cleanup_timeout': 3600,  # 1 hour
    'dry_run_mode': False,
    'confirm_deletion': True,
    'backup_before_cleanup': True
}

# Storage health check settings
STORAGE_HEALTH_CHECK_SETTINGS = {
    'connection_timeout': 30,
    'operation_timeout': 300,
    'max_retries': 3,
    'retry_delay': 5,
    'health_check_interval': 3600,  # 1 hour
    'failure_threshold': 3  # Number of failures before marking as unhealthy
}

# Analytics settings
ANALYTICS_SETTINGS = {
    'retention_days': 365,
    'aggregation_intervals': ['hourly', 'daily', 'weekly', 'monthly'],
    'max_aggregation_records': 10000,
    'report_cache_timeout': 3600,  # 1 hour
    'enable_real_time_analytics': True
}

# Encryption key rotation settings
KEY_ROTATION_SETTINGS = {
    'rotation_interval_days': 90,
    'grace_period_days': 7,
    'max_active_keys': 3,
    'key_derivation_iterations': 100000,
    'backup_keys': True,
    'key_backup_retention_days': 365
}

# Performance optimization settings
PERFORMANCE_OPTIMIZATION_SETTINGS = {
    'enable_parallel_processing': True,
    'max_workers': 4,
    'chunk_size_bytes': 1024 * 1024 * 10,  # 10MB
    'memory_limit_mb': 2048,
    'cpu_threshold_percent': 80,
    'io_threshold_percent': 85,
    'enable_compression_pipeline': True,
    'enable_encryption_pipeline': True
}

# Monitoring and alerting settings
MONITORING_SETTINGS = {
    'alert_cooldown_minutes': 15,
    'max_alerts_per_hour': 100,
    'alert_retention_days': 30,
    'metric_retention_days': 90,
    'health_check_interval_seconds': 300,
    'performance_check_interval_seconds': 600,
    'enable_auto_healing': True,
    'enable_predictive_alerts': True
}

# Compliance settings
COMPLIANCE_SETTINGS = {
    'audit_retention_days': 2555,  # 7 years
    'require_encryption': True,
    'require_verification': True,
    'require_audit_trail': True,
    'data_classification_levels': ['public', 'internal', 'confidential', 'restricted'],
    'gdpr_compliance': True,
    'hipaa_compliance': False,
    'sox_compliance': False
}

# WebSocket settings for real-time updates
WEBSOCKET_SETTINGS = {
    'enable_realtime_updates': True,
    'max_connections_per_user': 5,
    'connection_timeout_seconds': 3600,
    'heartbeat_interval_seconds': 30,
    'message_queue_size': 1000,
    'enable_broadcast': True
}

# API throttling settings
THROTTLING_SETTINGS = {
    'default_rate': '1000/hour',
    'backup_operations_rate': '100/hour',
    'restore_operations_rate': '50/hour',
    'admin_operations_rate': '5000/hour',
    'burst_size': 100,
    'enable_rate_limiting': True
}

# File processing settings
FILE_PROCESSING_SETTINGS = {
    'max_file_size_bytes': 100 * 1024 * 1024 * 1024,  # 100GB
    'allowed_mime_types': [
        'application/sql', 'application/x-sql',
        'application/gzip', 'application/x-gzip',
        'application/x-bzip2', 'application/x-xz',
        'application/zip', 'application/x-zstd-compressed',
        'application/octet-stream'
    ],
    'virus_scan_enabled': False,
    'content_inspection_enabled': True,
    'temporary_file_retention_hours': 24
}

# Database connection settings
DATABASE_CONNECTION_SETTINGS = {
    'max_connections': 20,
    'connection_timeout_seconds': 30,
    'query_timeout_seconds': 300,
    'retry_attempts': 3,
    'retry_delay_seconds': 5,
    'connection_pool_size': 10,
    'enable_connection_pooling': True
}

# Backup scheduling settings
SCHEDULING_SETTINGS = {
    'max_concurrent_schedules': 10,
    'schedule_buffer_minutes': 5,
    'missed_schedule_threshold_minutes': 15,
    'schedule_history_retention_days': 90,
    'enable_schedule_overlap_protection': True,
    'schedule_priority_levels': ['low', 'normal', 'high', 'urgent']
}

# Logging and audit settings
AUDIT_SETTINGS = {
    'log_all_operations': True,
    'log_sensitive_data': False,
    'audit_log_retention_days': 2555,  # 7 years
    'log_compression_enabled': True,
    'log_encryption_enabled': True,
    'structured_logging_enabled': True,
    'log_level': 'INFO'
}

# Security settings
SECURITY_SETTINGS = {
    'enable_access_logging': True,
    'session_timeout_minutes': 120,
    'max_login_attempts': 5,
    'lockout_duration_minutes': 15,
    'password_min_length': 12,
    'require_two_factor_auth': False,
    'enable_ip_whitelisting': False,
    'enable_rate_limiting': True
}

# Integration settings
INTEGRATION_SETTINGS = {
    'enable_slack_integration': False,
    'enable_teams_integration': False,
    'enable_email_integration': True,
    'enable_webhook_integration': True,
    'enable_prometheus_integration': False,
    'enable_grafana_integration': False,
    'enable_splunk_integration': False
}

# Deprecated settings (for migration)
DEPRECATED_SETTINGS = {
    'OLD_MAX_BACKUP_SIZE': 'Use MAX_BACKUP_SIZE_GB instead',
    'OLD_RETENTION_DAYS': 'Use DEFAULT_RETENTION_DAYS instead'
}
