"""
Rate Limit Constants

Default values and configuration constants for rate limiting module.
"""

from django.conf import settings
from django.utils.translation import gettext_lazy as _


# ============================================================================
# DEFAULT RATE LIMIT VALUES
# ============================================================================

# Default rate limits per time unit
DEFAULT_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_RATE_LIMIT_PER_HOUR = 3600
DEFAULT_RATE_LIMIT_PER_DAY = 86400
DEFAULT_RATE_LIMIT_PER_SECOND = 1

# Default burst limits (how many requests can be made in a short burst)
DEFAULT_BURST_LIMIT = 10
DEFAULT_BURST_WINDOW = 1  # seconds

# Default limits for different entity types
DEFAULT_IP_RATE_LIMIT = 100  # per hour
DEFAULT_USER_RATE_LIMIT = 60  # per minute
DEFAULT_ENDPOINT_RATE_LIMIT = 1000  # per hour
DEFAULT_GLOBAL_RATE_LIMIT = 10000  # per hour

# Earning app specific defaults
DEFAULT_REFERRAL_RATE_LIMIT = 10  # per hour
DEFAULT_TASK_RATE_LIMIT = 20  # per hour
DEFAULT_OFFER_RATE_LIMIT = 5  # per hour
DEFAULT_WITHDRAWAL_RATE_LIMIT = 3  # per day

# ============================================================================
# SANCTION CONFIGURATION
# ============================================================================

# Sanction thresholds and timeouts
SANCTION_WARNING_TIMEOUT = 86400  # 24 hours in seconds
SANCTION_TEMPORARY_BLOCK_HOURS = 24
SANCTION_RATE_LIMIT_REDUCTION_FACTOR = 0.5
SANCTION_PREMIUM_REVOCATION_DAYS = 30

# Sanction thresholds
SUSPICION_SCORE_HIGH_THRESHOLD = 80
ABUSE_REPORT_COUNT_THRESHOLD = 3
ABUSE_SEVERITY_CRITICAL_THRESHOLD = 4
ABUSE_SEVERITY_SEVERE_THRESHOLD = 5
BLOCK_RATE_THRESHOLD = 50

# Default rate limits for sanctions
SANCTION_DEFAULT_DAILY_LIMIT = 1000
SANCTION_DEFAULT_HOURLY_LIMIT = 100
SANCTION_PREMIUM_DAILY_LIMIT = 5000
SANCTION_PREMIUM_HOURLY_LIMIT = 500

# Sanction evaluation time windows
SANCTION_EVALUATION_HOURS = 24

# ============================================================================
# COMPLIANCE CONFIGURATION
# ============================================================================

# Compliance audit trail settings
COMPLIANCE_AUDIT_CACHE_TIMEOUT = 86400 * 30  # 30 days in seconds

# Data retention policies (in days)
RETENTION_RATE_LIMIT_LOGS_DAYS = 365
RETENTION_RATE_LIMIT_LOGS_ANONYMIZE_AFTER = 90
RETENTION_RATE_LIMIT_LOGS_DELETE_AFTER = 365 * 7

RETENTION_USER_PROFILES_DAYS = 365 * 10
RETENTION_USER_PROFILES_ANONYMIZE_AFTER = 365 * 2
RETENTION_USER_PROFILES_DELETE_AFTER = 365 * 10

RETENTION_ABUSE_REPORTS_DAYS = 365 * 5
RETENTION_ABUSE_REPORTS_ANONYMIZE_AFTER = 365
RETENTION_ABUSE_REPORTS_DELETE_AFTER = 365 * 7

RETENTION_IP_BLOCKS_DAYS = 365
RETENTION_IP_BLOCKS_ANONYMIZE_AFTER = 90
RETENTION_IP_BLOCKS_DELETE_AFTER = 365

# Consent management
CONSENT_DATA_PROCESSING_RETENTION_DAYS = 365
CONSENT_ANALYTICS_RETENTION_DAYS = 180
CONSENT_MARKETING_RETENTION_DAYS = 90
CONSENT_CACHE_TIMEOUT = 86400 * 30  # 30 days

# Compliance reporting
COMPLIANCE_REPORT_PERIOD_DAYS = 30
COMPLIANCE_AUDIT_RECENT_DAYS = 30

# ============================================================================
# REDIS CONFIGURATION
# ============================================================================

# Redis key prefixes
REDIS_KEY_PREFIX = 'rl:'
REDIS_USER_PREFIX = 'rl:user:'
REDIS_IP_PREFIX = 'rl:ip:'
REDIS_ENDPOINT_PREFIX = 'rl:endpoint:'
REDIS_GLOBAL_PREFIX = 'rl:global:'
REDIS_CONFIG_PREFIX = 'rl:config:'
REDIS_BLOCK_PREFIX = 'rl:block:'
REDIS_EXCEPTION_PREFIX = 'rl:exception:'
REDIS_ABUSE_PREFIX = 'rl:abuse:'
REDIS_INSIGHT_PREFIX = 'rl:insight:'

# Redis connection settings
REDIS_CONNECTION_TIMEOUT = 5  # seconds
REDIS_SOCKET_TIMEOUT = 3  # seconds
REDIS_MAX_CONNECTIONS = 50
REDIS_RETRY_ON_TIMEOUT = True
REDIS_RETRY_POLICY = 'backoff'

# Redis cache settings
REDIS_DEFAULT_TTL = 3600  # 1 hour
REDIS_BURST_TTL = 60  # 1 minute
REDIS_BLOCK_TTL = 86400  # 24 hours
REDIS_CONFIG_TTL = 1800  # 30 minutes
REDIS_ABUSE_TTL = 7200  # 2 hours

# ============================================================================
# EXEMPTIONS AND WHITELISTS
# ============================================================================

# Paths exempt from rate limiting
EXEMPT_PATHS = [
    '/health/',
    '/healthz/',
    '/ready/',
    '/metrics/',
    '/status/',
    '/ping/',
    '/favicon.ico',
    '/robots.txt',
    '/sitemap.xml',
]

# HTTP methods exempt from rate limiting
EXEMPT_METHODS = [
    'OPTIONS',
    'HEAD',
]

# User agents exempt from rate limiting (bots, monitoring tools)
EXEMPT_USER_AGENTS = [
    'Googlebot',
    'Bingbot',
    'Slackbot',
    'GitHub-Hookshot',
    'curl',
    'wget',
    'python-requests',
    'PostmanRuntime',
    'insomnia',
]

# IP ranges exempt from rate limiting (internal networks)
EXEMPT_IP_RANGES = [
    '127.0.0.0/8',     # localhost
    '10.0.0.0/8',      # private network
    '172.16.0.0/12',   # private network
    '192.168.0.0/16',  # private network
    '169.254.0.0/16',  # link-local
]

# ============================================================================
# THROTTLING AND BACKOFF
# ============================================================================

# Default throttle action
DEFAULT_THROTTLE_ACTION = 'block'

# Default backoff strategy
DEFAULT_BACKOFF_STRATEGY = 'exponential'

# Backoff calculation parameters
DEFAULT_BACKOFF_BASE_DELAY = 1  # seconds
DEFAULT_BACKOFF_MAX_DELAY = 300  # 5 minutes
DEFAULT_BACKOFF_MULTIPLIER = 2

# Retry configuration
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1  # seconds

# ============================================================================
# BLOCKING AND SECURITY
# ============================================================================

# Default block settings
DEFAULT_BLOCK_DURATION = 3600  # 1 hour
DEFAULT_MAX_BLOCK_DURATION = 86400 * 30  # 30 days
DEFAULT_AUTO_BLOCK_THRESHOLD = 100  # abuse reports

# IP block settings
DEFAULT_IP_BLOCK_TTL = 86400  # 24 hours
DEFAULT_MAX_IP_BLOCKS = 10000  # maximum active blocks

# Abuse detection thresholds
DEFAULT_ABUSE_THRESHOLD_IP = 50  # reports per hour
DEFAULT_ABUSE_THRESHOLD_USER = 20  # reports per hour
DEFAULT_SUSPICION_THRESHOLD = 70  # suspicion score

# ============================================================================
# LOGGING AND MONITORING
# ============================================================================

# Log levels
DEFAULT_LOG_LEVEL = 'INFO'
DEFAULT_SECURITY_LOG_LEVEL = 'WARNING'

# Log retention
DEFAULT_LOG_RETENTION_DAYS = 30
DEFAULT_SECURITY_LOG_RETENTION_DAYS = 90

# Monitoring settings
DEFAULT_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
DEFAULT_METRICS_COLLECTION_INTERVAL = 60  # 1 minute

# Alert thresholds
DEFAULT_ALERT_BLOCK_RATE = 20  # percentage
DEFAULT_ALERT_ERROR_RATE = 5  # percentage
DEFAULT_ALERT_ABUSE_SPIKE = 100  # reports per hour

# ============================================================================
# PERFORMANCE AND SCALING
# ============================================================================

# Cache settings
DEFAULT_CACHE_TIMEOUT = 300  # 5 minutes
DEFAULT_CONFIG_CACHE_TIMEOUT = 1800  # 30 minutes
DEFAULT_STATS_CACHE_TIMEOUT = 60  # 1 minute

# Batch processing
DEFAULT_BATCH_SIZE = 1000
DEFAULT_MAX_BATCH_SIZE = 10000

# Connection pooling
DEFAULT_CONNECTION_POOL_SIZE = 20
DEFAULT_MAX_CONNECTION_POOL_SIZE = 100

# Rate limiting performance
DEFAULT_MAX_REQUESTS_PER_CHECK = 1000
DEFAULT_CONCURRENT_CHECKS = 10

# ============================================================================
# VALIDATION LIMITS
# ============================================================================

# Maximum values for validation
MAX_REQUESTS_PER_UNIT = 1000000
MAX_WINDOW_SECONDS = 86400 * 30  # 30 days
MAX_ENDPOINT_LENGTH = 500
MAX_USER_AGENT_LENGTH = 500
MAX_IP_RANGE_SIZE = 65536  # /24 network
MAX_SUBNET_PREFIX = 24  # /24
MAX_MULTIPLIER = 100.0

# Minimum values for validation
MIN_REQUESTS_PER_UNIT = 1
MIN_WINDOW_SECONDS = 1
MIN_ENDPOINT_LENGTH = 1

# ============================================================================
# EARNING APP SPECIFIC
# ============================================================================

# Task completion rate limits
DEFAULT_TASK_COMPLETION_LIMIT = 20  # per hour
DEFAULT_TASK_COMPLETION_BURST = 5
DEFAULT_TASK_COMPLETION_WINDOW = 300  # 5 minutes

# Offer access rate limits
DEFAULT_OFFER_ACCESS_LIMIT = 5  # per hour
DEFAULT_OFFER_ACCESS_BURST = 2
DEFAULT_OFFER_ACCESS_WINDOW = 3600  # 1 hour

# Referral click rate limits
DEFAULT_REFERRAL_CLICK_LIMIT = 10  # per hour
DEFAULT_REFERRAL_CLICK_BURST = 3
DEFAULT_REFERRAL_CLICK_WINDOW = 3600  # 1 hour

# Withdrawal rate limits
DEFAULT_WITHDRAWAL_LIMIT = 3  # per day
DEFAULT_WITHDRAWAL_BURST = 1
DEFAULT_WITHDRAWAL_WINDOW = 86400  # 24 hours

# ============================================================================
# PREMIUM USER SETTINGS
# ============================================================================

# Premium user multipliers
DEFAULT_PREMIUM_MULTIPLIER = 5.0
DEFAULT_PREMIUM_BURST_MULTIPLIER = 2.0

# Premium user limits
DEFAULT_PREMIUM_DAILY_LIMIT = 10000
DEFAULT_PREMIUM_HOURLY_LIMIT = 1000
DEFAULT_PREMIUM_MINUTE_LIMIT = 100

# ============================================================================
# DEVELOPMENT AND TESTING
# ============================================================================

# Development mode settings
DEV_MODE_RATE_LIMIT_MULTIPLIER = 10.0
DEV_MODE_DISABLE_BLOCKING = False
DEV_MODE_LOG_ALL_REQUESTS = True

# Testing settings
TEST_MODE_RATE_LIMITS = 1000  # very high limits for testing
TEST_MODE_DISABLE_REDIS = False
TEST_MODE_CACHE_TIMEOUT = 1  # 1 second for fast cache clearing

# Debug settings
DEBUG_RATE_LIMITING = False
DEBUG_LOG_ALL_CHECKS = False
DEBUG_INCLUDE_BACKTRACE = False

# ============================================================================
# CONFIGURATION OVERRIDES
# ============================================================================

def get_rate_limit_per_minute():
    """Get rate limit per minute from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_PER_MINUTE', DEFAULT_RATE_LIMIT_PER_MINUTE)

def get_rate_limit_per_hour():
    """Get rate limit per hour from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_PER_HOUR', DEFAULT_RATE_LIMIT_PER_HOUR)

def get_rate_limit_per_day():
    """Get rate limit per day from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_PER_DAY', DEFAULT_RATE_LIMIT_PER_DAY)

def get_burst_limit():
    """Get burst limit from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_BURST_LIMIT', DEFAULT_BURST_LIMIT)

def get_redis_key_prefix():
    """Get Redis key prefix from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_REDIS_KEY_PREFIX', REDIS_KEY_PREFIX)

def get_exempt_paths():
    """Get exempt paths from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_EXEMPT_PATHS', EXEMPT_PATHS)

def get_exempt_methods():
    """Get exempt methods from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_EXEMPT_METHODS', EXEMPT_METHODS)

def get_exempt_user_agents():
    """Get exempt user agents from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_EXEMPT_USER_AGENTS', EXEMPT_USER_AGENTS)

def get_exempt_ip_ranges():
    """Get exempt IP ranges from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_EXEMPT_IP_RANGES', EXEMPT_IP_RANGES)

def get_throttle_action():
    """Get default throttle action from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_DEFAULT_THROTTLE_ACTION', DEFAULT_THROTTLE_ACTION)

def get_backoff_strategy():
    """Get default backoff strategy from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_DEFAULT_BACKOFF_STRATEGY', DEFAULT_BACKOFF_STRATEGY)

def get_block_duration():
    """Get default block duration from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_DEFAULT_BLOCK_DURATION', DEFAULT_BLOCK_DURATION)

def get_abuse_threshold_ip():
    """Get abuse threshold for IP from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_ABUSE_THRESHOLD_IP', DEFAULT_ABUSE_THRESHOLD_IP)

def get_abuse_threshold_user():
    """Get abuse threshold for user from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_ABUSE_THRESHOLD_USER', DEFAULT_ABUSE_THRESHOLD_USER)

def get_suspicion_threshold():
    """Get suspicion threshold from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_SUSPICION_THRESHOLD', DEFAULT_SUSPICION_THRESHOLD)

def get_log_retention_days():
    """Get log retention days from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_LOG_RETENTION_DAYS', DEFAULT_LOG_RETENTION_DAYS)

def get_cache_timeout():
    """Get cache timeout from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_CACHE_TIMEOUT', DEFAULT_CACHE_TIMEOUT)

def get_batch_size():
    """Get batch size from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_BATCH_SIZE', DEFAULT_BATCH_SIZE)

def get_premium_multiplier():
    """Get premium user multiplier from settings or use default."""
    return getattr(settings, 'RATE_LIMIT_PREMIUM_MULTIPLIER', DEFAULT_PREMIUM_MULTIPLIER)

def is_dev_mode():
    """Check if development mode is enabled."""
    return getattr(settings, 'RATE_LIMIT_DEV_MODE', False)

def is_test_mode():
    """Check if test mode is enabled."""
    return getattr(settings, 'RATE_LIMIT_TEST_MODE', False)

def is_debug_mode():
    """Check if debug mode is enabled."""
    return getattr(settings, 'RATE_LIMIT_DEBUG', DEBUG_RATE_LIMITING)

# ============================================================================
# DYNAMIC CONFIGURATION
# ============================================================================

class RateLimitConfig:
    """Dynamic rate limit configuration class."""
    
    def __init__(self):
        self.load_from_settings()
    
    def load_from_settings(self):
        """Load configuration from Django settings."""
        # Rate limits
        self.per_minute = get_rate_limit_per_minute()
        self.per_hour = get_rate_limit_per_hour()
        self.per_day = get_rate_limit_per_day()
        self.burst_limit = get_burst_limit()
        
        # Redis
        self.redis_key_prefix = get_redis_key_prefix()
        
        # Exemptions
        self.exempt_paths = get_exempt_paths()
        self.exempt_methods = get_exempt_methods()
        self.exempt_user_agents = get_exempt_user_agents()
        self.exempt_ip_ranges = get_exempt_ip_ranges()
        
        # Actions and strategies
        self.throttle_action = get_throttle_action()
        self.backoff_strategy = get_backoff_strategy()
        
        # Blocking
        self.block_duration = get_block_duration()
        self.abuse_threshold_ip = get_abuse_threshold_ip()
        self.abuse_threshold_user = get_abuse_threshold_user()
        self.suspicion_threshold = get_suspicion_threshold()
        
        # Performance
        self.cache_timeout = get_cache_timeout()
        self.batch_size = get_batch_size()
        
        # Premium
        self.premium_multiplier = get_premium_multiplier()
        
        # Modes
        self.dev_mode = is_dev_mode()
        self.test_mode = is_test_mode()
        self.debug_mode = is_debug_mode()
    
    def get_limits_for_type(self, limit_type):
        """Get rate limits for a specific type."""
        if limit_type == 'per_minute':
            return self.per_minute
        elif limit_type == 'per_hour':
            return self.per_hour
        elif limit_type == 'per_day':
            return self.per_day
        elif limit_type == 'per_ip':
            return DEFAULT_IP_RATE_LIMIT
        elif limit_type == 'per_user':
            return DEFAULT_USER_RATE_LIMIT if not self.dev_mode else DEFAULT_USER_RATE_LIMIT * 10
        elif limit_type == 'per_endpoint':
            return DEFAULT_ENDPOINT_RATE_LIMIT
        elif limit_type == 'per_global':
            return DEFAULT_GLOBAL_RATE_LIMIT
        elif limit_type == 'per_referral':
            return DEFAULT_REFERRAL_RATE_LIMIT
        elif limit_type == 'per_task':
            return DEFAULT_TASK_RATE_LIMIT
        elif limit_type == 'per_offer':
            return DEFAULT_OFFER_RATE_LIMIT
        elif limit_type == 'per_withdrawal':
            return DEFAULT_WITHDRAWAL_RATE_LIMIT
        else:
            return self.per_minute
    
    def is_path_exempt(self, path):
        """Check if a path is exempt from rate limiting."""
        for exempt_path in self.exempt_paths:
            if path.startswith(exempt_path):
                return True
        return False
    
    def is_method_exempt(self, method):
        """Check if an HTTP method is exempt from rate limiting."""
        return method.upper() in self.exempt_methods
    
    def is_user_agent_exempt(self, user_agent):
        """Check if a user agent is exempt from rate limiting."""
        if not user_agent:
            return False
        user_agent_lower = user_agent.lower()
        for exempt_ua in self.exempt_user_agents:
            if exempt_ua.lower() in user_agent_lower:
                return True
        return False
    
    def is_ip_exempt(self, ip_address):
        """Check if an IP address is exempt from rate limiting."""
        import ipaddress
        try:
            ip = ipaddress.ip_address(ip_address)
            for exempt_range in self.exempt_ip_ranges:
                network = ipaddress.ip_network(exempt_range)
                if ip in network:
                    return True
        except ValueError:
            pass
        return False
    
    def apply_premium_multiplier(self, limit):
        """Apply premium user multiplier to a limit."""
        if self.premium_multiplier and self.premium_multiplier > 1:
            return int(limit * self.premium_multiplier)
        return limit
    
    def apply_dev_mode_multiplier(self, limit):
        """Apply development mode multiplier to a limit."""
        if self.dev_mode:
            return int(limit * DEV_MODE_RATE_LIMIT_MULTIPLIER)
        return limit
    
    def apply_test_mode_limits(self, limit):
        """Apply test mode limits."""
        if self.test_mode:
            return TEST_MODE_RATE_LIMITS
        return limit

# Global configuration instance
rate_limit_config = RateLimitConfig()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_redis_key(key_type, identifier, suffix=None):
    """
    Generate Redis key for rate limiting.
    
    Args:
        key_type: Type of key (user, ip, endpoint, global)
        identifier: Identifier (user_id, ip_address, endpoint_name)
        suffix: Optional suffix for the key
        
    Returns:
        str: Redis key
    """
    prefix = f"{rate_limit_config.redis_key_prefix}{key_type}:"
    key = f"{prefix}{identifier}"
    if suffix:
        key = f"{key}:{suffix}"
    return key

def get_ttl_for_key_type(key_type):
    """
    Get TTL for a specific key type.
    
    Args:
        key_type: Type of key (user, ip, endpoint, global, block, config)
        
    Returns:
        int: TTL in seconds
    """
    ttl_map = {
        'user': REDIS_DEFAULT_TTL,
        'ip': REDIS_DEFAULT_TTL,
        'endpoint': REDIS_DEFAULT_TTL,
        'global': REDIS_DEFAULT_TTL,
        'block': REDIS_BLOCK_TTL,
        'config': REDIS_CONFIG_TTL,
        'abuse': REDIS_ABUSE_TTL,
        'insight': REDIS_INSIGHT_TTL,
    }
    return ttl_map.get(key_type, REDIS_DEFAULT_TTL)

def format_rate_limit_headers(limit, remaining, reset_time):
    """
    Format rate limit headers for HTTP responses.
    
    Args:
        limit: Rate limit
        remaining: Remaining requests
        reset_time: Reset time (Unix timestamp)
        
    Returns:
        dict: HTTP headers
    """
    return {
        'X-RateLimit-Limit': str(limit),
        'X-RateLimit-Remaining': str(remaining),
        'X-RateLimit-Reset': str(reset_time),
        'X-RateLimit-Retry-After': str(max(0, reset_time - int(time.time()))),
    }

# Import time for timestamp calculations
import time
