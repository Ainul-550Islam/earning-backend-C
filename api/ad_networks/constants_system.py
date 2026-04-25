# api/ad_networks/constants.py
# System-Level Constants Only

# ============================================================================
# SYSTEM CONFIGURATION CONSTANTS
# ============================================================================

# Database Configuration
DEFAULT_DB_TIMEOUT = 30
MAX_DB_CONNECTIONS = 100
DB_CONNECTION_RETRY_ATTEMPTS = 3
DB_CONNECTION_RETRY_DELAY = 1

# Cache Configuration
DEFAULT_CACHE_TIMEOUT = 300  # 5 minutes
CACHE_KEY_PREFIX = 'ad_networks'
CACHE_VERSION = 1

# API Configuration
API_VERSION = 'v1'
API_TIMEOUT = 30
API_RETRY_ATTEMPTS = 3
API_RETRY_DELAY = 1

# File Upload Configuration
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
UPLOAD_CHUNK_SIZE = 8192

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE = 60
RATE_LIMIT_REQUESTS_PER_HOUR = 1000
RATE_LIMIT_REQUESTS_PER_DAY = 10000

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# ============================================================================
# BUSINESS LOGIC CONSTANTS
# ============================================================================

# Offer Configuration
MIN_OFFER_REWARD = 0.01
MAX_OFFER_REWARD = 1000.00
DEFAULT_OFFER_DURATION_DAYS = 30

# User Configuration
MAX_DAILY_OFFERS_PER_USER = 50
MAX_CONCURRENT_OFFERS_PER_USER = 5
USER_INACTIVITY_TIMEOUT = 3600  # 1 hour

# Fraud Detection
FRAUD_SCORE_THRESHOLD_HIGH = 80
FRAUD_SCORE_THRESHOLD_MEDIUM = 50
FRAUD_SCORE_THRESHOLD_LOW = 20

# Payment Configuration
MIN_PAYOUT_AMOUNT = 1.00
MAX_PAYOUT_AMOUNT = 10000.00
PAYMENT_PROCESSING_FEE = 0.02  # 2%

# ============================================================================
# SECURITY CONSTANTS
# ============================================================================

# Token Configuration
TOKEN_EXPIRE_MINUTES = 60
TOKEN_REFRESH_EXPIRE_DAYS = 7
TOKEN_ALGORITHM = 'HS256'

# Password Configuration
MIN_PASSWORD_LENGTH = 8
PASSWORD_REGEX = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d@$!%*?&]{8,}$'

# Session Configuration
SESSION_TIMEOUT_MINUTES = 30
MAX_CONCURRENT_SESSIONS = 5

# Encryption
ENCRYPTION_KEY_LENGTH = 32
ENCRYPTION_ALGORITHM = 'AES-256-CBC'

# ============================================================================
# PERFORMANCE CONSTANTS
# ============================================================================

# Query Optimization
QUERY_TIMEOUT_SECONDS = 30
MAX_QUERY_RESULTS = 10000
BATCH_SIZE = 1000

# Memory Management
MAX_MEMORY_USAGE_MB = 512
GARBAGE_COLLECTION_INTERVAL = 300  # 5 minutes

# Background Tasks
TASK_TIMEOUT_SECONDS = 300
TASK_RETRY_DELAY = 60
MAX_TASK_RETRIES = 3

# ============================================================================
# MONITORING CONSTANTS
# ============================================================================

# Health Check Intervals
HEALTH_CHECK_INTERVAL_SECONDS = 60
HEALTH_CHECK_TIMEOUT_SECONDS = 10

# Metrics Collection
METRICS_COLLECTION_INTERVAL = 300  # 5 minutes
METRICS_RETENTION_DAYS = 30

# Alert Thresholds
CPU_USAGE_THRESHOLD = 80  # percentage
MEMORY_USAGE_THRESHOLD = 85  # percentage
DISK_USAGE_THRESHOLD = 90  # percentage

# ============================================================================
# INTEGRATION CONSTANTS
# ============================================================================

# External API Configuration
EXTERNAL_API_TIMEOUT = 30
EXTERNAL_API_RETRY_ATTEMPTS = 3
EXTERNAL_API_RETRY_DELAY = 2

# Webhook Configuration
WEBHOOK_TIMEOUT = 10
WEBHOOK_RETRY_ATTEMPTS = 5
WEBHOOK_RETRY_DELAY = 30

# Third-party Services
MAX_EXTERNAL_REQUESTS_PER_MINUTE = 100
EXTERNAL_SERVICE_TIMEOUT = 15

# ============================================================================
# LOGGING CONSTANTS
# ============================================================================

# Log Configuration
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Log Rotation
LOG_ROTATION_INTERVAL = 'daily'
LOG_RETENTION_DAYS = 30

# ============================================================================
# TENANT CONFIGURATION
# ============================================================================

# Tenant Limits
DEFAULT_TENANT_LIMITS = {
    'max_users': 1000,
    'max_offers': 10000,
    'max_storage_mb': 1024,
    'max_api_requests_per_day': 100000,
}

# Tenant Isolation
TENANT_DATA_ISOLATION = True
TENANT_CACHE_ISOLATION = True
TENANT_QUEUE_ISOLATION = True

# ============================================================================
# NOTIFICATION CONSTANTS
# ============================================================================

# Email Configuration
EMAIL_SEND_TIMEOUT = 30
EMAIL_RETRY_ATTEMPTS = 3
EMAIL_RETRY_DELAY = 60

# SMS Configuration
SMS_SEND_TIMEOUT = 15
SMS_RETRY_ATTEMPTS = 3
SMS_RETRY_DELAY = 30

# Push Notification Configuration
PUSH_NOTIFICATION_TIMEOUT = 10
PUSH_NOTIFICATION_RETRY_ATTEMPTS = 2

# ============================================================================
# BACKUP CONSTANTS
# ============================================================================

# Backup Configuration
BACKUP_INTERVAL_HOURS = 24
BACKUP_RETENTION_DAYS = 30
BACKUP_COMPRESSION = True

# Backup Storage
BACKUP_STORAGE_TYPE = 'local'
BACKUP_ENCRYPTION = True
BACKUP_CHUNK_SIZE = 1024 * 1024  # 1MB

# ============================================================================
# COMPLIANCE CONSTANTS
# ============================================================================

# Data Retention
DATA_RETENTION_DAYS = 365
AUDIT_LOG_RETENTION_DAYS = 1825  # 5 years
USER_DATA_RETENTION_DAYS = 2555  # 7 years

# Privacy
ANONYMIZATION_ENABLED = True
DATA_DELETION_TIMEOUT_DAYS = 30
CONSENT_EXPIRY_DAYS = 365

# ============================================================================
# DEVELOPMENT CONSTANTS
# ============================================================================

# Debug Configuration
DEBUG_MODE = False
VERBOSE_LOGGING = False
PROFILING_ENABLED = False

# Testing
TEST_DB_NAME = 'test_ad_networks'
TEST_CACHE_PREFIX = 'test_'
TEST_TIMEOUT_MULTIPLIER = 2

# ============================================================================
# MIGRATION CONSTANTS
# ============================================================================

# Migration Configuration
MIGRATION_BATCH_SIZE = 1000
MIGRATION_TIMEOUT = 3600  # 1 hour
MIGRATION_RETRY_ATTEMPTS = 3

# Data Migration
DATA_MIGRATION_CHUNK_SIZE = 500
DATA_MIGRATION_TIMEOUT = 1800  # 30 minutes

# ============================================================================
# SCALING CONSTANTS
# ============================================================================

# Auto-scaling
MIN_WORKERS = 2
MAX_WORKERS = 10
WORKER_TIMEOUT = 300

# Load Balancing
LOAD_BALANCER_HEALTH_CHECK_INTERVAL = 30
LOAD_BALANCER_TIMEOUT = 10

# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Feature Toggles
ENABLE_ANALYTICS = True
ENABLE_FRAUD_DETECTION = True
ENABLE_REAL_TIME_NOTIFICATIONS = True
ENABLE_ADVANCED_REPORTING = True

# Beta Features
ENABLE_BETA_FEATURES = False
ENABLE_EXPERIMENTAL_FEATURES = False

# ============================================================================
# EXPORT CONSTANTS
# ============================================================================

__all__ = [
    # System configuration
    'DEFAULT_DB_TIMEOUT',
    'MAX_DB_CONNECTIONS',
    'DEFAULT_CACHE_TIMEOUT',
    'API_VERSION',
    'MAX_FILE_SIZE',
    'RATE_LIMIT_REQUESTS_PER_MINUTE',
    'DEFAULT_PAGE_SIZE',
    
    # Business logic
    'MIN_OFFER_REWARD',
    'MAX_OFFER_REWARD',
    'MAX_DAILY_OFFERS_PER_USER',
    'FRAUD_SCORE_THRESHOLD_HIGH',
    'MIN_PAYOUT_AMOUNT',
    
    # Security
    'TOKEN_EXPIRE_MINUTES',
    'MIN_PASSWORD_LENGTH',
    'SESSION_TIMEOUT_MINUTES',
    'ENCRYPTION_KEY_LENGTH',
    
    # Performance
    'QUERY_TIMEOUT_SECONDS',
    'MAX_QUERY_RESULTS',
    'TASK_TIMEOUT_SECONDS',
    
    # Monitoring
    'HEALTH_CHECK_INTERVAL_SECONDS',
    'METRICS_COLLECTION_INTERVAL',
    'CPU_USAGE_THRESHOLD',
    
    # Integration
    'EXTERNAL_API_TIMEOUT',
    'WEBHOOK_TIMEOUT',
    'MAX_EXTERNAL_REQUESTS_PER_MINUTE',
    
    # Logging
    'LOG_LEVEL',
    'LOG_FORMAT',
    'LOG_RETENTION_DAYS',
    
    # Tenant
    'DEFAULT_TENANT_LIMITS',
    'TENANT_DATA_ISOLATION',
    
    # Notification
    'EMAIL_SEND_TIMEOUT',
    'SMS_SEND_TIMEOUT',
    
    # Backup
    'BACKUP_INTERVAL_HOURS',
    'BACKUP_RETENTION_DAYS',
    
    # Compliance
    'DATA_RETENTION_DAYS',
    'AUDIT_LOG_RETENTION_DAYS',
    
    # Development
    'DEBUG_MODE',
    'TEST_DB_NAME',
    
    # Migration
    'MIGRATION_BATCH_SIZE',
    'DATA_MIGRATION_CHUNK_SIZE',
    
    # Scaling
    'MIN_WORKERS',
    'MAX_WORKERS',
    
    # Feature flags
    'ENABLE_ANALYTICS',
    'ENABLE_FRAUD_DETECTION',
]
