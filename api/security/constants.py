"""
Security Constants and Configuration
Centralized security-related constants
Version: 1.0.0
"""

from typing import Dict, List, Any
from datetime import timedelta


# ==================== LOCKOUT DURATION CONSTANTS ====================

class LockoutDuration:
    """Account lockout duration constants"""
    
    FAILED_LOGIN_LOCKOUT_MINUTES = 15
    BRUTE_FORCE_LOCKOUT_MINUTES = 30
    SUSPICIOUS_ACTIVITY_LOCKOUT_MINUTES = 60
    SECURITY_BREACH_LOCKOUT_HOURS = 24
    
    # Progressive lockout durations
    PROGRESSIVE_LOCKOUT = {
        3: timedelta(minutes=15),    # 3 failed attempts - 15 minutes
        5: timedelta(minutes=30),    # 5 failed attempts - 30 minutes
        7: timedelta(hours=1),       # 7 failed attempts - 1 hour
        10: timedelta(hours=6),     # 10 failed attempts - 6 hours
        15: timedelta(hours=24),    # 15 failed attempts - 24 hours
        20: timedelta(days=7),      # 20 failed attempts - 7 days
    }
    
    @classmethod
    def get_lockout_duration(cls, failed_attempts: int) -> timedelta:
        """Get progressive lockout duration based on failed attempts"""
        for threshold, duration in sorted(cls.PROGRESSIVE_LOCKOUT.items(), reverse=True):
            if failed_attempts >= threshold:
                return duration
        return timedelta(minutes=cls.FAILED_LOGIN_LOCKOUT_MINUTES)


# ==================== PASSWORD POLICY CONSTANTS ====================

class PasswordPolicyConstants:
    """Password security policy constants"""
    
    # Length requirements
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    RECOMMENDED_LENGTH = 12
    
    # Complexity requirements
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGITS = True
    REQUIRE_SPECIAL_CHARS = True
    
    # Special characters allowed
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    FORBIDDEN_CHARS = ["'", '"', '\\', '/', ' ', '\t', '\n', '\r']
    
    # Common password patterns to block
    COMMON_PASSWORDS = [
        "password", "123456", "123456789", "qwerty", "abc123",
        "password123", "admin", "letmein", "welcome", "monkey",
        "1234567890", "password1", "123123", "qwertyuiop",
        "password!", "admin123", "root", "toor", "pass"
    ]
    
    # Sequential patterns to block
    SEQUENTIAL_PATTERNS = [
        "abcdefghijklmnopqrstuvwxyz",
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm",
        "1234567890",
        "0123456789"
    ]
    
    # Password history
    PASSWORD_HISTORY_COUNT = 12  # Remember last 12 passwords
    PASSWORD_REUSE_DAYS = 365    # Cannot reuse passwords within 1 year
    
    # Expiration
    PASSWORD_EXPIRY_DAYS = 90   # Force password change every 90 days
    EXPIRY_WARNING_DAYS = 7     # Start warning 7 days before expiry
    
    @classmethod
    def get_complexity_requirements(cls) -> Dict[str, Any]:
        """Get password complexity requirements"""
        return {
            'min_length': cls.MIN_LENGTH,
            'max_length': cls.MAX_LENGTH,
            'require_uppercase': cls.REQUIRE_UPPERCASE,
            'require_lowercase': cls.REQUIRE_LOWERCASE,
            'require_digits': cls.REQUIRE_DIGITS,
            'require_special_chars': cls.REQUIRE_SPECIAL_CHARS,
            'special_chars': cls.SPECIAL_CHARS,
            'forbidden_chars': cls.FORBIDDEN_CHARS
        }


# ==================== RATE LIMITING CONSTANTS ====================

class RateLimiting:
    """Rate limiting constants"""
    
    # Authentication endpoints
    LOGIN_ATTEMPTS_PER_MINUTE = 5
    LOGIN_ATTEMPTS_PER_HOUR = 20
    PASSWORD_RESET_PER_HOUR = 3
    
    # API endpoints
    API_REQUESTS_PER_MINUTE = 100
    API_REQUESTS_PER_HOUR = 1000
    API_REQUESTS_PER_DAY = 10000
    
    # Sensitive operations
    PASSWORD_CHANGE_PER_HOUR = 5
    EMAIL_CHANGE_PER_DAY = 3
    WITHDRAWAL_ATTEMPTS_PER_HOUR = 10
    
    # IP-based limits
    IP_REQUESTS_PER_MINUTE = 200
    IP_REQUESTS_PER_HOUR = 2000
    
    # User-based limits
    USER_REQUESTS_PER_MINUTE = 60
    USER_REQUESTS_PER_HOUR = 600
    
    @classmethod
    def get_rate_limits(cls) -> Dict[str, Dict[str, int]]:
        """Get all rate limits"""
        return {
            'authentication': {
                'login_per_minute': cls.LOGIN_ATTEMPTS_PER_MINUTE,
                'login_per_hour': cls.LOGIN_ATTEMPTS_PER_HOUR,
                'password_reset_per_hour': cls.PASSWORD_RESET_PER_HOUR
            },
            'api': {
                'requests_per_minute': cls.API_REQUESTS_PER_MINUTE,
                'requests_per_hour': cls.API_REQUESTS_PER_HOUR,
                'requests_per_day': cls.API_REQUESTS_PER_DAY
            },
            'sensitive_operations': {
                'password_change_per_hour': cls.PASSWORD_CHANGE_PER_HOUR,
                'email_change_per_day': cls.EMAIL_CHANGE_PER_DAY,
                'withdrawal_per_hour': cls.WITHDRAWAL_ATTEMPTS_PER_HOUR
            },
            'ip_based': {
                'requests_per_minute': cls.IP_REQUESTS_PER_MINUTE,
                'requests_per_hour': cls.IP_REQUESTS_PER_HOUR
            },
            'user_based': {
                'requests_per_minute': cls.USER_REQUESTS_PER_MINUTE,
                'requests_per_hour': cls.USER_REQUESTS_PER_HOUR
            }
        }


# ==================== THREAT INTELLIGENCE CONSTANTS ====================

class ThreatIntelligenceConstants:
    """Threat intelligence constants"""
    
    # IOC (Indicators of Compromise) types
    IOC_TYPES = [
        'ip_address',
        'domain',
        'url',
        'email',
        'hash',
        'filename',
        'registry_key'
    ]
    
    # Confidence levels
    CONFIDENCE_LEVELS = {
        'high': 0.9,
        'medium': 0.7,
        'low': 0.5,
        'unknown': 0.3
    }
    
    # Threat score thresholds
    THREAT_SCORE_THRESHOLDS = {
        'critical': 0.9,
        'high': 0.7,
        'medium': 0.5,
        'low': 0.3
    }
    
    # IOC expiration times (in days)
    IOC_EXPIRY_DAYS = {
        'ip_address': 30,
        'domain': 90,
        'url': 60,
        'email': 180,
        'hash': 365,
        'filename': 180,
        'registry_key': 365
    }
    
    # Feed update intervals (in hours)
    FEED_UPDATE_INTERVALS = {
        'real_time': 1,
        'hourly': 1,
        'daily': 24,
        'weekly': 168
    }
    
    @classmethod
    def get_ioc_expiry(cls, ioc_type: str) -> int:
        """Get IOC expiry in days"""
        return cls.IOC_EXPIRY_DAYS.get(ioc_type, 30)


# ==================== INCIDENT MANAGEMENT CONSTANTS ====================

class IncidentManagement:
    """Incident management constants"""
    
    # Response SLAs (in minutes)
    RESPONSE_SLA = {
        'critical': 15,    # 15 minutes
        'high': 60,        # 1 hour
        'medium': 240,     # 4 hours
        'low': 1440        # 24 hours
    }
    
    # Resolution SLAs (in hours)
    RESOLUTION_SLA = {
        'critical': 4,     # 4 hours
        'high': 24,        # 1 day
        'medium': 72,      # 3 days
        'low': 168         # 1 week
    }
    
    # Escalation thresholds (in minutes)
    ESCALATION_THRESHOLDS = {
        'critical': 30,    # Escalate if not resolved in 30 minutes
        'high': 120,       # Escalate if not resolved in 2 hours
        'medium': 480,     # Escalate if not resolved in 8 hours
        'low': 1440        # Escalate if not resolved in 24 hours
    }
    
    # Auto-resolution conditions
    AUTO_RESOLUTION_CONDITIONS = {
        'false_positive': {
            'min_confidence': 0.8,
            'no_activity_hours': 1
        },
        'resolved': {
            'no_activity_hours': 24,
            'all_indicators_clean': True
        }
    }
    
    @classmethod
    def get_response_sla(cls, severity: str) -> int:
        """Get response SLA in minutes"""
        return cls.RESPONSE_SLA.get(severity, 1440)
    
    @classmethod
    def get_resolution_sla(cls, severity: str) -> int:
        """Get resolution SLA in hours"""
        return cls.RESOLUTION_SLA.get(severity, 168)


# ==================== DEVICE SECURITY CONSTANTS ====================

class DeviceSecurity:
    """Device security constants"""
    
    # Device risk scores
    DEVICE_RISK_FACTORS = {
        'rooted_jailbroken': 40,
        'emulator': 30,
        'vpn_proxy': 25,
        'suspicious_fingerprint': 20,
        'multiple_accounts': 15,
        'new_device': 10,
        'old_app_version': 5
    }
    
    # Trust levels
    TRUST_LEVELS = {
        'trusted': 0.9,
        'known': 0.7,
        'suspicious': 0.4,
        'blocked': 0.1
    }
    
    # Device fingerprint expiration
    FINGERPRINT_EXPIRY_DAYS = 30
    
    # Maximum devices per user
    MAX_DEVICES_PER_USER = 10
    
    @classmethod
    def calculate_device_risk(cls, risk_factors: List[str]) -> int:
        """Calculate device risk score"""
        total_risk = 0
        for factor in risk_factors:
            total_risk += cls.DEVICE_RISK_FACTORS.get(factor, 0)
        return min(total_risk, 100)


# ==================== CACHE CONSTANTS ====================

class CacheSettings:
    """Cache configuration constants"""
    
    # Cache TTLs (in seconds)
    CACHE_TTL = {
        'user_session': 1800,      # 30 minutes
        'device_info': 3600,       # 1 hour
        'ip_reputation': 300,      # 5 minutes
        'rate_limit': 60,          # 1 minute
        'security_config': 3600,   # 1 hour
        'threat_intel': 1800,      # 30 minutes
        'incident_data': 300,      # 5 minutes
        'password_policy': 3600,   # 1 hour
    }
    
    # Cache key prefixes
    CACHE_PREFIXES = {
        'security': 'sec',
        'threat_intel': 'ti',
        'incident': 'inc',
        'rate_limit': 'rl',
        'device': 'dev',
        'user': 'usr'
    }
    
    @classmethod
    def get_cache_ttl(cls, cache_type: str) -> int:
        """Get cache TTL in seconds"""
        return cls.CACHE_TTL.get(cache_type, 300)


# ==================== LOGGING CONSTANTS ====================

class LoggingConfig:
    """Security logging configuration"""
    
    # Log levels for different event types
    EVENT_LOG_LEVELS = {
        'authentication': 'INFO',
        'authorization': 'WARNING',
        'security_incident': 'ERROR',
        'fraud_detection': 'ERROR',
        'system_change': 'INFO',
        'data_access': 'INFO'
    }
    
    # Log retention periods (in days)
    LOG_RETENTION_DAYS = {
        'authentication': 90,
        'authorization': 365,
        'security_incident': 2555,  # 7 years
        'fraud_detection': 2555,    # 7 years
        'system_change': 365,
        'data_access': 365
    }
    
    # Sensitive data to mask in logs
    SENSITIVE_FIELDS = [
        'password', 'token', 'secret', 'key', 'hash',
        'credit_card', 'ssn', 'api_key', 'private_key'
    ]
    
    @classmethod
    def get_log_level(cls, event_type: str) -> str:
        """Get log level for event type"""
        return cls.EVENT_LOG_LEVELS.get(event_type, 'INFO')


# ==================== NOTIFICATION CONSTANTS ====================

class NotificationConfig:
    """Security notification configuration"""
    
    # Notification channels
    CHANNELS = ['email', 'sms', 'push', 'webhook', 'slack']
    
    # Severity-based channel preferences
    SEVERITY_CHANNELS = {
        'critical': ['email', 'sms', 'push', 'slack'],
        'high': ['email', 'push', 'slack'],
        'medium': ['email', 'push'],
        'low': ['email']
    }
    
    # Rate limiting for notifications
    NOTIFICATION_RATE_LIMITS = {
        'email': {'per_hour': 10, 'per_day': 100},
        'sms': {'per_hour': 5, 'per_day': 50},
        'push': {'per_hour': 20, 'per_day': 200}
    }
    
    @classmethod
    def get_channels_for_severity(cls, severity: str) -> List[str]:
        """Get notification channels for severity"""
        return cls.SEVERITY_CHANNELS.get(severity, ['email'])


# ==================== INTEGRATION CONSTANTS ====================

class IntegrationConfig:
    """External integration configuration"""
    
    # VPN detection services
    VPN_SERVICES = {
        'ipinfo': {
            'endpoint': 'https://ipinfo.io',
            'rate_limit': 1000,  # requests per hour
            'timeout': 5
        },
        'vpnapi': {
            'endpoint': 'https://vpnapi.io',
            'rate_limit': 500,
            'timeout': 10
        }
    }
    
    # Threat intelligence feeds
    THREAT_FEEDS = {
        'abuse_ch': {
            'endpoint': 'https://abuse.ch',
            'update_interval': 3600,  # 1 hour
            'format': 'json'
        },
        'phishtank': {
            'endpoint': 'https://phishtank.com',
            'update_interval': 3600,
            'format': 'json'
        }
    }
    
    @classmethod
    def get_service_config(cls, service_name: str) -> Dict[str, Any]:
        """Get service configuration"""
        return cls.VPN_SERVICES.get(service_name, {})


# ==================== VALIDATION CONSTANTS ====================

class ValidationRules:
    """Field validation constants"""
    
    # IP address validation
    IP_ADDRESS_PATTERNS = {
        'ipv4': r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$',
        'ipv6': r'^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$'
    }
    
    # Email validation
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    # Device fingerprint patterns
    DEVICE_FINGERPRINT_PATTERN = r'^[a-zA-Z0-9]{32,64}$'
    
    # Hash patterns
    SHA256_PATTERN = r'^[a-fA-F0-9]{64}$'
    MD5_PATTERN = r'^[a-fA-F0-9]{32}$'
    
    # Max field lengths
    MAX_FIELD_LENGTHS = {
        'username': 150,
        'email': 254,
        'device_fingerprint': 128,
        'ip_address': 45,  # IPv6 max length
        'user_agent': 500,
        'description': 1000,
        'notes': 5000
    }
    
    # Security policy validation
    POLICY_VALIDATION = {
        'min_password_length': 8,
        'max_password_length': 128,
        'min_session_timeout': 300,  # 5 minutes
        'max_session_timeout': 86400,  # 24 hours
        'max_login_attempts': 10,
        'max_trusted_devices': 10,
        'password_history_count': 12
    }
    
    # Trusted device validation
    TRUSTED_DEVICE_VALIDATION = {
        'min_trust_score': 0.0,
        'max_trust_score': 1.0,
        'default_trust_expiry_days': 30,
        'max_device_name_length': 100
    }
    
    # Password history validation
    PASSWORD_HISTORY_VALIDATION = {
        'min_password_strength': 1,
        'max_password_strength': 6,
        'password_change_cooldown_minutes': 5,
        'max_password_reuse_days': 365
    }
    
    # Security insights validation
    INSIGHTS_VALIDATION = {
        'min_risk_score': 0,
        'max_risk_score': 100,
        'trend_analysis_days': 30,
        'analytics_retention_days': 2555  # 7 years
    }
    
    # Threat intelligence validation
    THREAT_INTEL_VALIDATION = {
        'min_confidence_score': 0.0,
        'max_confidence_score': 1.0,
        'ioc_max_length': 1000,
        'threat_feed_max_items': 10000
    }
    
    # Incident management validation
    INCIDENT_VALIDATION = {
        'min_incident_title_length': 10,
        'max_incident_title_length': 200,
        'min_incident_description_length': 20,
        'max_incident_description_length': 5000,
        'max_incident_attachments': 10,
        'incident_auto_close_days': 7
    }


# ==================== ENVIRONMENT-SPECIFIC CONSTANTS ====================

class EnvironmentConfig:
    """Environment-specific security configuration"""
    
    DEVELOPMENT = {
        'debug': True,
        'log_level': 'DEBUG',
        'rate_limiting': False,
        'vpn_detection': False,
        'threat_intelligence': False
    }
    
    STAGING = {
        'debug': True,
        'log_level': 'INFO',
        'rate_limiting': True,
        'vpn_detection': True,
        'threat_intelligence': True
    }
    
    PRODUCTION = {
        'debug': False,
        'log_level': 'WARNING',
        'rate_limiting': True,
        'vpn_detection': True,
        'threat_intelligence': True
    }
    
    @classmethod
    def get_config(cls, environment: str) -> Dict[str, Any]:
        """Get environment configuration"""
        return getattr(cls, environment.upper(), cls.PRODUCTION)


# ==================== CORE SECURITY CONSTANTS ====================

# Authentication and Login Security
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
SESSION_TIMEOUT_MINUTES = 60
PASSWORD_MIN_LENGTH = 8

# Geographic Security
SUSPICIOUS_COUNTRIES = [
    'CN',  # China
    'RU',  # Russia
    'KP',  # North Korea
    'IR',  # Iran
    'SY',  # Syria
    'AF',  # Afghanistan
    'MM',  # Myanmar
    'BY',  # Belarus
    'CU',  # Cuba
    'VE',  # Venezuela
    'ZW',  # Zimbabwe
    'SD',  # Sudan
    'LR',  # Liberia
    'SS',  # South Sudan
    'ER',  # Eritrea
    'YE',  # Yemen
    'SO',  # Somalia
    'CD',  # Democratic Republic of Congo
    'CF',  # Central African Republic
]

# VPN and Proxy Detection
VPN_DETECTION_ENABLED = True
PROXY_DETECTION_ENABLED = True
VPN_CONFIDENCE_THRESHOLD = 0.7
PROXY_CONFIDENCE_THRESHOLD = 0.6

# Rate Limiting
RATE_LIMIT_ENABLED = True
RATE_LIMIT_REQUESTS_PER_MINUTE = 60
RATE_LIMIT_REQUESTS_PER_HOUR = 1000
RATE_LIMIT_REQUESTS_PER_DAY = 10000

# Security Monitoring
SECURITY_MONITORING_ENABLED = True
SUSPICIOUS_ACTIVITY_THRESHOLD = 3
HIGH_RISK_ACTIVITY_THRESHOLD = 5
CRITICAL_RISK_ACTIVITY_THRESHOLD = 10

# Device Security
MAX_TRUSTED_DEVICES_PER_USER = 5
DEVICE_TRUST_EXPIRY_DAYS = 30
DEVICE_FINGERPRINT_EXPIRY_DAYS = 90

# Password Security
PASSWORD_HISTORY_COUNT = 12
PASSWORD_REUSE_PREVENTION_DAYS = 365
PASSWORD_CHANGE_COOLDOWN_MINUTES = 5
PASSWORD_STRENGTH_THRESHOLD = 3

# Session Security
SESSION_INACTIVITY_TIMEOUT_MINUTES = 30
SESSION_MAX_DURATION_HOURS = 24
SESSION_SECURE_COOKIE = True
SESSION_HTTP_ONLY_COOKIE = True

# IP Security
IP_BLACKLIST_AUTO_EXPIRY_DAYS = 30
IP_WHITELIST_CHECK_ENABLED = True
IP_REPUTATION_CHECK_ENABLED = True

# Threat Intelligence
THREAT_INTEL_AUTO_UPDATE_ENABLED = True
THREAT_INTEL_UPDATE_INTERVAL_HOURS = 6
THREAT_INTEL_CONFIDENCE_THRESHOLD = 0.8
THREAT_INTEL_AUTO_BLACKLIST_ENABLED = True

# Security Logging
SECURITY_LOG_RETENTION_DAYS = 90
SECURITY_LOG_LEVEL = 'INFO'
SECURITY_AUDIT_LOG_ENABLED = True

# Email Notifications
SECURITY_EMAIL_NOTIFICATIONS_ENABLED = True
SECURITY_EMAIL_ADMIN_NOTIFICATIONS = True
SECURITY_EMAIL_USER_NOTIFICATIONS = True

# Two-Factor Authentication
TWO_FACTOR_AUTH_ENABLED = True
TWO_FACTOR_AUTH_BACKUP_CODES_COUNT = 10
TWO_FACTOR_AUTH_BACKUP_CODE_LENGTH = 8
TWO_FACTOR_AUTH_CODE_LENGTH = 6
TWO_FACTOR_AUTH_CODE_EXPIRY_MINUTES = 5

# Account Security
ACCOUNT_LOCKOUT_ENABLED = True
ACCOUNT_LOCKOUT_PROGRESSIVE = True
ACCOUNT_LOCKOUT_MAX_ATTEMPTS = 5
ACCOUNT_LOCKOUT_BASE_DURATION_MINUTES = 15

# API Security
API_RATE_LIMIT_ENABLED = True
API_KEY_EXPIRY_DAYS = 365
API_REQUEST_TIMEOUT_SECONDS = 30
API_MAX_REQUEST_SIZE_MB = 10

# File Upload Security
FILE_UPLOAD_MAX_SIZE_MB = 10
FILE_UPLOAD_ALLOWED_EXTENSIONS = [
    'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx', 'txt', 'csv'
]
FILE_UPLOAD_VIRUS_SCAN_ENABLED = True

# Database Security
DATABASE_CONNECTION_TIMEOUT_SECONDS = 30
DATABASE_QUERY_TIMEOUT_SECONDS = 60
DATABASE_MAX_CONNECTIONS = 100

# Cache Security
CACHE_TIMEOUT_SECONDS = 300
CACHE_ENCRYPTION_ENABLED = True
CACHE_KEY_PREFIX = 'security_'

# Encryption
ENCRYPTION_KEY_ROTATION_DAYS = 90
ENCRYPTION_ALGORITHM = 'AES-256-GCM'
HASH_ALGORITHM = 'SHA-256'

# Backup Security
BACKUP_ENCRYPTION_ENABLED = True
BACKUP_RETENTION_DAYS = 30
BACKUP_COMPRESSION_ENABLED = True

# Compliance
COMPLIANCE_AUDIT_ENABLED = True
COMPLIANCE_REPORT_GENERATION_ENABLED = True
COMPLIANCE_DATA_RETENTION_YEARS = 7

# Performance
SECURITY_PERFORMANCE_MONITORING_ENABLED = True
SECURITY_METRICS_COLLECTION_ENABLED = True
SECURITY_ALERT_PROCESSING_BATCH_SIZE = 100

# Development/Testing
SECURITY_DEBUG_MODE = False
SECURITY_MOCK_EXTERNAL_SERVICES = False
SECURITY_TEST_MODE = False
ThreatIntelligence = ThreatIntelligenceConstants
