"""
Configuration Management for Advertiser Portal

This module handles application configuration settings,
environment variables, and runtime configuration management.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from .constants import *
from .enums import *


logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration."""
    host: str = 'localhost'
    port: int = 5432
    name: str = 'advertiser_portal'
    user: str = 'postgres'
    password: str = ''
    engine: str = 'django.db.backends.postgresql'
    options: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_settings(cls) -> 'DatabaseConfig':
        """Create config from Django settings."""
        return cls(
            host=getattr(settings, 'DATABASE_HOST', 'localhost'),
            port=getattr(settings, 'DATABASE_PORT', 5432),
            name=getattr(settings, 'DATABASE_NAME', 'advertiser_portal'),
            user=getattr(settings, 'DATABASE_USER', 'postgres'),
            password=getattr(settings, 'DATABASE_PASSWORD', ''),
            engine=getattr(settings, 'DATABASE_ENGINE', 'django.db.backends.postgresql'),
            options=getattr(settings, 'DATABASE_OPTIONS', {})
        )


@dataclass
class CacheConfig:
    """Cache configuration."""
    backend: str = 'django.core.cache.backends.redis.RedisCache'
    location: str = 'redis://127.0.0.1:6379/1'
    key_prefix: str = 'advertiser_portal'
    timeout: int = 300
    options: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_settings(cls) -> 'CacheConfig':
        """Create config from Django settings."""
        return cls(
            backend=getattr(settings, 'CACHE_BACKEND', 'django.core.cache.backends.redis.RedisCache'),
            location=getattr(settings, 'CACHE_LOCATION', 'redis://127.0.0.1:6379/1'),
            key_prefix=getattr(settings, 'CACHE_KEY_PREFIX', 'advertiser_portal'),
            timeout=getattr(settings, 'CACHE_DEFAULT_TIMEOUT', 300),
            options=getattr(settings, 'CACHE_OPTIONS', {})
        )


@dataclass
class APIConfig:
    """API configuration."""
    version: str = 'v1'
    default_page_size: int = 20
    max_page_size: int = 100
    rate_limit_per_hour: int = 1000
    rate_limit_per_hour_premium: int = 5000
    cors_origins: List[str] = field(default_factory=list)
    allowed_hosts: List[str] = field(default_factory=list)
    
    @classmethod
    def from_settings(cls) -> 'APIConfig':
        """Create config from Django settings."""
        return cls(
            version=getattr(settings, 'API_VERSION', 'v1'),
            default_page_size=getattr(settings, 'API_DEFAULT_PAGE_SIZE', 20),
            max_page_size=getattr(settings, 'API_MAX_PAGE_SIZE', 100),
            rate_limit_per_hour=getattr(settings, 'API_RATE_LIMIT_PER_HOUR', 1000),
            rate_limit_per_hour_premium=getattr(settings, 'API_RATE_LIMIT_PER_HOUR_PREMIUM', 5000),
            cors_origins=getattr(settings, 'CORS_ALLOWED_ORIGINS', []),
            allowed_hosts=getattr(settings, 'ALLOWED_HOSTS', [])
        )


@dataclass
class BillingConfig:
    """Billing configuration."""
    default_currency: str = 'USD'
    supported_currencies: List[str] = field(default_factory=lambda: ['USD', 'EUR', 'GBP'])
    payment_gateways: Dict[str, Dict[str, str]] = field(default_factory=dict)
    tax_rates: Dict[str, Decimal] = field(default_factory=dict)
    invoice_number_prefix: str = 'INV'
    payment_terms_days: int = 30
    late_fee_rate: Decimal = Decimal('0.02')
    
    @classmethod
    def from_settings(cls) -> 'BillingConfig':
        """Create config from Django settings."""
        return cls(
            default_currency=getattr(settings, 'BILLING_DEFAULT_CURRENCY', 'USD'),
            supported_currencies=getattr(settings, 'BILLING_SUPPORTED_CURRENCIES', ['USD', 'EUR', 'GBP']),
            payment_gateways=getattr(settings, 'BILLING_PAYMENT_GATEWAYS', {}),
            tax_rates=getattr(settings, 'BILLING_TAX_RATES', {}),
            invoice_number_prefix=getattr(settings, 'BILLING_INVOICE_PREFIX', 'INV'),
            payment_terms_days=getattr(settings, 'BILLING_PAYMENT_TERMS_DAYS', 30),
            late_fee_rate=Decimal(str(getattr(settings, 'BILLING_LATE_FEE_RATE', '0.02')))
        )


@dataclass
class SecurityConfig:
    """Security configuration."""
    secret_key: str = ''
    allowed_hosts: List[str] = field(default_factory=list)
    debug: bool = False
    session_timeout: int = 1800
    max_login_attempts: int = 5
    lockout_duration: int = 900
    password_min_length: int = 8
    require_https: bool = True
    
    @classmethod
    def from_settings(cls) -> 'SecurityConfig':
        """Create config from Django settings."""
        return cls(
            secret_key=getattr(settings, 'SECRET_KEY', ''),
            allowed_hosts=getattr(settings, 'ALLOWED_HOSTS', []),
            debug=getattr(settings, 'DEBUG', False),
            session_timeout=getattr(settings, 'SESSION_TIMEOUT', 1800),
            max_login_attempts=getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
            lockout_duration=getattr(settings, 'LOCKOUT_DURATION', 900),
            password_min_length=getattr(settings, 'PASSWORD_MIN_LENGTH', 8),
            require_https=getattr(settings, 'REQUIRE_HTTPS', True)
        )


@dataclass
class StorageConfig:
    """Storage configuration."""
    backend: str = 'django.core.files.storage.FileSystemStorage'
    media_root: str = '/var/www/advertiser_portal/media'
    media_url: str = '/media/'
    aws_access_key_id: str = ''
    aws_secret_access_key: str = ''
    aws_bucket_name: str = ''
    max_file_size: int = 50 * 1024 * 1024  # 50MB
    
    @classmethod
    def from_settings(cls) -> 'StorageConfig':
        """Create config from Django settings."""
        return cls(
            backend=getattr(settings, 'STORAGE_BACKEND', 'django.core.files.storage.FileSystemStorage'),
            media_root=getattr(settings, 'MEDIA_ROOT', '/var/www/advertiser_portal/media'),
            media_url=getattr(settings, 'MEDIA_URL', '/media/'),
            aws_access_key_id=getattr(settings, 'AWS_ACCESS_KEY_ID', ''),
            aws_secret_access_key=getattr(settings, 'AWS_SECRET_ACCESS_KEY', ''),
            aws_bucket_name=getattr(settings, 'AWS_STORAGE_BUCKET_NAME', ''),
            max_file_size=getattr(settings, 'MAX_FILE_SIZE', 50 * 1024 * 1024)
        )


@dataclass
class EmailConfig:
    """Email configuration."""
    backend: str = 'django.core.mail.backends.smtp.EmailBackend'
    host: str = 'localhost'
    port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    host_user: str = ''
    host_password: str = ''
    default_from_email: str = 'noreply@advertiserportal.com'
    
    @classmethod
    def from_settings(cls) -> 'EmailConfig':
        """Create config from Django settings."""
        return cls(
            backend=getattr(settings, 'EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend'),
            host=getattr(settings, 'EMAIL_HOST', 'localhost'),
            port=getattr(settings, 'EMAIL_PORT', 587),
            use_tls=getattr(settings, 'EMAIL_USE_TLS', True),
            use_ssl=getattr(settings, 'EMAIL_USE_SSL', False),
            host_user=getattr(settings, 'EMAIL_HOST_USER', ''),
            host_password=getattr(settings, 'EMAIL_HOST_PASSWORD', ''),
            default_from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@advertiserportal.com')
        )


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = 'INFO'
    format: str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_file: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    handlers: List[str] = field(default_factory=lambda: ['console'])
    
    @classmethod
    def from_settings(cls) -> 'LoggingConfig':
        """Create config from Django settings."""
        return cls(
            level=getattr(settings, 'LOG_LEVEL', 'INFO'),
            format=getattr(settings, 'LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            log_file=getattr(settings, 'LOG_FILE', None),
            max_file_size=getattr(settings, 'LOG_MAX_FILE_SIZE', 10 * 1024 * 1024),
            backup_count=getattr(settings, 'LOG_BACKUP_COUNT', 5),
            handlers=getattr(settings, 'LOG_HANDLERS', ['console'])
        )


@dataclass
class IntegrationConfig:
    """Third-party integration configuration."""
    google_ads: Dict[str, str] = field(default_factory=dict)
    facebook_ads: Dict[str, str] = field(default_factory=dict)
    google_analytics: Dict[str, str] = field(default_factory=dict)
    stripe: Dict[str, str] = field(default_factory=dict)
    paypal: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_settings(cls) -> 'IntegrationConfig':
        """Create config from Django settings."""
        return cls(
            google_ads=getattr(settings, 'GOOGLE_ADS_CONFIG', {}),
            facebook_ads=getattr(settings, 'FACEBOOK_ADS_CONFIG', {}),
            google_analytics=getattr(settings, 'GOOGLE_ANALYTICS_CONFIG', {}),
            stripe=getattr(settings, 'STRIPE_CONFIG', {}),
            paypal=getattr(settings, 'PAYPAL_CONFIG', {})
        )


@dataclass
class FeatureFlagsConfig:
    """Feature flags configuration."""
    advanced_targeting: bool = True
    real_time_bidding: bool = True
    machine_learning_optimization: bool = False
    multi_currency_billing: bool = False
    api_v2: bool = False
    beta_features: bool = False
    
    @classmethod
    def from_settings(cls) -> 'FeatureFlagsConfig':
        """Create config from Django settings."""
        return cls(
            advanced_targeting=getattr(settings, 'FEATURE_ADVANCED_TARGETING', True),
            real_time_bidding=getattr(settings, 'FEATURE_REAL_TIME_BIDDING', True),
            machine_learning_optimization=getattr(settings, 'FEATURE_MACHINE_LEARNING_OPTIMIZATION', False),
            multi_currency_billing=getattr(settings, 'FEATURE_MULTI_CURRENCY_BILLING', False),
            api_v2=getattr(settings, 'FEATURE_API_V2', False),
            beta_features=getattr(settings, 'FEATURE_BETA_FEATURES', False)
        )


class ConfigManager:
    """Central configuration manager."""
    
    def __init__(self):
        self._config_cache: Dict[str, Any] = {}
        self._environment = self._get_environment()
    
    def _get_environment(self) -> str:
        """Get current environment."""
        return getattr(settings, 'ENVIRONMENT', 'development')
    
    def get_database_config(self) -> DatabaseConfig:
        """Get database configuration."""
        if 'database' not in self._config_cache:
            self._config_cache['database'] = DatabaseConfig.from_settings()
        return self._config_cache['database']
    
    def get_cache_config(self) -> CacheConfig:
        """Get cache configuration."""
        if 'cache' not in self._config_cache:
            self._config_cache['cache'] = CacheConfig.from_settings()
        return self._config_cache['cache']
    
    def get_api_config(self) -> APIConfig:
        """Get API configuration."""
        if 'api' not in self._config_cache:
            self._config_cache['api'] = APIConfig.from_settings()
        return self._config_cache['api']
    
    def get_billing_config(self) -> BillingConfig:
        """Get billing configuration."""
        if 'billing' not in self._config_cache:
            self._config_cache['billing'] = BillingConfig.from_settings()
        return self._config_cache['billing']
    
    def get_security_config(self) -> SecurityConfig:
        """Get security configuration."""
        if 'security' not in self._config_cache:
            self._config_cache['security'] = SecurityConfig.from_settings()
        return self._config_cache['security']
    
    def get_storage_config(self) -> StorageConfig:
        """Get storage configuration."""
        if 'storage' not in self._config_cache:
            self._config_cache['storage'] = StorageConfig.from_settings()
        return self._config_cache['storage']
    
    def get_email_config(self) -> EmailConfig:
        """Get email configuration."""
        if 'email' not in self._config_cache:
            self._config_cache['email'] = EmailConfig.from_settings()
        return self._config_cache['email']
    
    def get_logging_config(self) -> LoggingConfig:
        """Get logging configuration."""
        if 'logging' not in self._config_cache:
            self._config_cache['logging'] = LoggingConfig.from_settings()
        return self._config_cache['logging']
    
    def get_integration_config(self) -> IntegrationConfig:
        """Get integration configuration."""
        if 'integration' not in self._config_cache:
            self._config_cache['integration'] = IntegrationConfig.from_settings()
        return self._config_cache['integration']
    
    def get_feature_flags(self) -> FeatureFlagsConfig:
        """Get feature flags configuration."""
        if 'feature_flags' not in self._config_cache:
            self._config_cache['feature_flags'] = FeatureFlagsConfig.from_settings()
        return self._config_cache['feature_flags']
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self._environment == 'development'
    
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self._environment == 'staging'
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self._environment == 'production'
    
    def get_setting(self, name: str, default: Any = None) -> Any:
        """Get setting value with fallback."""
        return getattr(settings, name, default)
    
    def get_env_var(self, name: str, default: Any = None) -> Any:
        """Get environment variable with fallback."""
        return os.getenv(name, default)
    
    def reload_config(self) -> None:
        """Reload configuration from settings."""
        self._config_cache.clear()
        logger.info("Configuration reloaded")
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Validate security config
        security = self.get_security_config()
        if not security.secret_key:
            issues.append("SECRET_KEY is not configured")
        
        if self.is_production() and security.debug:
            issues.append("DEBUG is True in production environment")
        
        # Validate database config
        db = self.get_database_config()
        if not db.name:
            issues.append("Database name is not configured")
        
        # Validate API config
        api = self.get_api_config()
        if api.default_page_size <= 0:
            issues.append("API default page size must be positive")
        
        if api.max_page_size < api.default_page_size:
            issues.append("API max page size must be greater than or equal to default page size")
        
        # Validate billing config
        billing = self.get_billing_config()
        if billing.default_currency not in billing.supported_currencies:
            issues.append("Default currency must be in supported currencies list")
        
        return issues
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary (without sensitive data)."""
        return {
            'environment': self._environment,
            'database': {
                'host': self.get_database_config().host,
                'port': self.get_database_config().port,
                'engine': self.get_database_config().engine,
            },
            'cache': {
                'backend': self.get_cache_config().backend,
                'location': self.get_cache_config().location,
                'timeout': self.get_cache_config().timeout,
            },
            'api': {
                'version': self.get_api_config().version,
                'default_page_size': self.get_api_config().default_page_size,
                'max_page_size': self.get_api_config().max_page_size,
            },
            'billing': {
                'default_currency': self.get_billing_config().default_currency,
                'supported_currencies': self.get_billing_config().supported_currencies,
            },
            'security': {
                'session_timeout': self.get_security_config().session_timeout,
                'max_login_attempts': self.get_security_config().max_login_attempts,
                'require_https': self.get_security_config().require_https,
            },
            'feature_flags': {
                'advanced_targeting': self.get_feature_flags().advanced_targeting,
                'real_time_bidding': self.get_feature_flags().real_time_bidding,
                'machine_learning_optimization': self.get_feature_flags().machine_learning_optimization,
            }
        }


class DynamicConfig:
    """Dynamic configuration that can be updated at runtime."""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._dynamic_settings: Dict[str, Any] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get dynamic setting value."""
        return self._dynamic_settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set dynamic setting value."""
        self._dynamic_settings[key] = value
        logger.info(f"Dynamic setting updated: {key}")
    
    def update(self, settings_dict: Dict[str, Any]) -> None:
        """Update multiple dynamic settings."""
        self._dynamic_settings.update(settings_dict)
        logger.info(f"Dynamic settings updated: {list(settings_dict.keys())}")
    
    def delete(self, key: str) -> None:
        """Delete dynamic setting."""
        if key in self._dynamic_settings:
            del self._dynamic_settings[key]
            logger.info(f"Dynamic setting deleted: {key}")
    
    def clear(self) -> None:
        """Clear all dynamic settings."""
        self._dynamic_settings.clear()
        logger.info("All dynamic settings cleared")
    
    def get_all(self) -> Dict[str, Any]:
        """Get all dynamic settings."""
        return self._dynamic_settings.copy()
    
    def load_from_file(self, file_path: str) -> None:
        """Load dynamic settings from file."""
        try:
            with open(file_path, 'r') as f:
                settings_data = json.load(f)
                self.update(settings_data)
                logger.info(f"Dynamic settings loaded from {file_path}")
        except Exception as e:
            logger.error(f"Failed to load dynamic settings from {file_path}: {e}")
    
    def save_to_file(self, file_path: str) -> None:
        """Save dynamic settings to file."""
        try:
            with open(file_path, 'w') as f:
                json.dump(self._dynamic_settings, f, indent=2)
                logger.info(f"Dynamic settings saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save dynamic settings to {file_path}: {e}")


class ConfigValidator:
    """Configuration validator."""
    
    @staticmethod
    def validate_database_config(config: DatabaseConfig) -> List[str]:
        """Validate database configuration."""
        issues = []
        
        if not config.host:
            issues.append("Database host is required")
        
        if not config.name:
            issues.append("Database name is required")
        
        if not config.user:
            issues.append("Database user is required")
        
        if config.port <= 0 or config.port > 65535:
            issues.append("Database port must be between 1 and 65535")
        
        return issues
    
    @staticmethod
    def validate_cache_config(config: CacheConfig) -> List[str]:
        """Validate cache configuration."""
        issues = []
        
        if not config.location:
            issues.append("Cache location is required")
        
        if config.timeout <= 0:
            issues.append("Cache timeout must be positive")
        
        return issues
    
    @staticmethod
    def validate_api_config(config: APIConfig) -> List[str]:
        """Validate API configuration."""
        issues = []
        
        if not config.version:
            issues.append("API version is required")
        
        if config.default_page_size <= 0:
            issues.append("API default page size must be positive")
        
        if config.max_page_size < config.default_page_size:
            issues.append("API max page size must be greater than or equal to default page size")
        
        if config.rate_limit_per_hour <= 0:
            issues.append("API rate limit must be positive")
        
        return issues
    
    @staticmethod
    def validate_billing_config(config: BillingConfig) -> List[str]:
        """Validate billing configuration."""
        issues = []
        
        if not config.default_currency:
            issues.append("Default currency is required")
        
        if not config.supported_currencies:
            issues.append("Supported currencies list cannot be empty")
        
        if config.default_currency not in config.supported_currencies:
            issues.append("Default currency must be in supported currencies list")
        
        if config.payment_terms_days <= 0:
            issues.append("Payment terms days must be positive")
        
        if config.late_fee_rate < 0:
            issues.append("Late fee rate cannot be negative")
        
        return issues
    
    @staticmethod
    def validate_security_config(config: SecurityConfig) -> List[str]:
        """Validate security configuration."""
        issues = []
        
        if not config.secret_key:
            issues.append("Secret key is required")
        
        if len(config.secret_key) < 50:
            issues.append("Secret key should be at least 50 characters long")
        
        if config.session_timeout <= 0:
            issues.append("Session timeout must be positive")
        
        if config.max_login_attempts <= 0:
            issues.append("Max login attempts must be positive")
        
        if config.lockout_duration <= 0:
            issues.append("Lockout duration must be positive")
        
        if config.password_min_length < 8:
            issues.append("Password minimum length should be at least 8")
        
        return issues


# Global configuration manager instance
config_manager = ConfigManager()
dynamic_config = DynamicConfig(config_manager)


def get_config() -> ConfigManager:
    """Get global configuration manager."""
    return config_manager


def get_dynamic_config() -> DynamicConfig:
    """Get global dynamic configuration."""
    return dynamic_config


def validate_all_configs() -> List[str]:
    """Validate all configurations and return list of issues."""
    all_issues = []
    
    validator = ConfigValidator()
    
    # Validate each config
    db_issues = validator.validate_database_config(config_manager.get_database_config())
    all_issues.extend([f"Database: {issue}" for issue in db_issues])
    
    cache_issues = validator.validate_cache_config(config_manager.get_cache_config())
    all_issues.extend([f"Cache: {issue}" for issue in cache_issues])
    
    api_issues = validator.validate_api_config(config_manager.get_api_config())
    all_issues.extend([f"API: {issue}" for issue in api_issues])
    
    billing_issues = validator.validate_billing_config(config_manager.get_billing_config())
    all_issues.extend([f"Billing: {issue}" for issue in billing_issues])
    
    security_issues = validator.validate_security_config(config_manager.get_security_config())
    all_issues.extend([f"Security: {issue}" for issue in security_issues])
    
    return all_issues


# Additional Configuration Classes for Main Models
@dataclass
class OfferConfig:
    """Offer-related configuration."""
    max_payout_amount: Decimal = Decimal('10000')
    min_payout_amount: Decimal = Decimal('0.01')
    default_payout_amount: Decimal = Decimal('1.00')
    max_offers_per_advertiser: int = 100
    offer_approval_required: bool = True
    auto_approve_threshold: Decimal = Decimal('100')
    verification_required: bool = True
    
    @classmethod
    def from_settings(cls) -> 'OfferConfig':
        """Create config from Django settings."""
        return cls(
            max_payout_amount=Decimal(getattr(settings, 'OFFER_MAX_PAYOUT', '10000')),
            min_payout_amount=Decimal(getattr(settings, 'OFFER_MIN_PAYOUT', '0.01')),
            default_payout_amount=Decimal(getattr(settings, 'OFFER_DEFAULT_PAYOUT', '1.00')),
            max_offers_per_advertiser=getattr(settings, 'OFFER_MAX_PER_ADVERTISER', 100),
            offer_approval_required=getattr(settings, 'OFFER_APPROVAL_REQUIRED', True),
            auto_approve_threshold=Decimal(getattr(settings, 'OFFER_AUTO_APPROVE_THRESHOLD', '100')),
            verification_required=getattr(settings, 'OFFER_VERIFICATION_REQUIRED', True)
        )


@dataclass
class TrackingConfig:
    """Tracking-related configuration."""
    pixel_id_length: int = 32
    conversion_window_days: int = 30
    max_conversions_per_ip: int = 10
    tracking_domain_required: bool = True
    ssl_required: bool = True
    postback_timeout_seconds: int = 30
    conversion_deduplication_window: int = 300  # 5 minutes
    
    @classmethod
    def from_settings(cls) -> 'TrackingConfig':
        """Create config from Django settings."""
        return cls(
            pixel_id_length=getattr(settings, 'TRACKING_PIXEL_ID_LENGTH', 32),
            conversion_window_days=getattr(settings, 'TRACKING_CONVERSION_WINDOW_DAYS', 30),
            max_conversions_per_ip=getattr(settings, 'TRACKING_MAX_CONVERSIONS_PER_IP', 10),
            tracking_domain_required=getattr(settings, 'TRACKING_DOMAIN_REQUIRED', True),
            ssl_required=getattr(settings, 'TRACKING_SSL_REQUIRED', True),
            postback_timeout_seconds=getattr(settings, 'TRACKING_POSTBACK_TIMEOUT', 30),
            conversion_deduplication_window=getattr(settings, 'TRACKING_DEDUP_WINDOW', 300)
        )


@dataclass
class FraudConfig:
    """Fraud detection configuration."""
    enabled: bool = True
    risk_score_threshold: float = 0.7
    auto_block_enabled: bool = False
    manual_review_threshold: float = 0.5
    max_daily_conversions_per_ip: int = 50
    suspicious_user_agents: List[str] = field(default_factory=lambda: ['bot', 'crawler', 'spider'])
    ip_blacklist_enabled: bool = True
    device_fingerprinting_enabled: bool = True
    
    @classmethod
    def from_settings(cls) -> 'FraudConfig':
        """Create config from Django settings."""
        return cls(
            enabled=getattr(settings, 'FRAUD_DETECTION_ENABLED', True),
            risk_score_threshold=getattr(settings, 'FRAUD_RISK_THRESHOLD', 0.7),
            auto_block_enabled=getattr(settings, 'FRAUD_AUTO_BLOCK_ENABLED', False),
            manual_review_threshold=getattr(settings, 'FRAUD_MANUAL_REVIEW_THRESHOLD', 0.5),
            max_daily_conversions_per_ip=getattr(settings, 'FRAUD_MAX_DAILY_CONVERSIONS_PER_IP', 50),
            suspicious_user_agents=getattr(settings, 'FRAUD_SUSPICIOUS_USER_AGENTS', ['bot', 'crawler', 'spider']),
            ip_blacklist_enabled=getattr(settings, 'FRAUD_IP_BLACKLIST_ENABLED', True),
            device_fingerprinting_enabled=getattr(settings, 'FRAUD_DEVICE_FINGERPRINTING_ENABLED', True)
        )


@dataclass
class NotificationConfig:
    """Notification configuration."""
    email_enabled: bool = True
    sms_enabled: bool = False
    push_enabled: bool = True
    webhook_enabled: bool = True
    max_notifications_per_hour: int = 100
    batch_notifications: bool = True
    notification_retention_days: int = 30
    
    @classmethod
    def from_settings(cls) -> 'NotificationConfig':
        """Create config from Django settings."""
        return cls(
            email_enabled=getattr(settings, 'NOTIFICATION_EMAIL_ENABLED', True),
            sms_enabled=getattr(settings, 'NOTIFICATION_SMS_ENABLED', False),
            push_enabled=getattr(settings, 'NOTIFICATION_PUSH_ENABLED', True),
            webhook_enabled=getattr(settings, 'NOTIFICATION_WEBHOOK_ENABLED', True),
            max_notifications_per_hour=getattr(settings, 'NOTIFICATION_MAX_PER_HOUR', 100),
            batch_notifications=getattr(settings, 'NOTIFICATION_BATCH_ENABLED', True),
            notification_retention_days=getattr(settings, 'NOTIFICATION_RETENTION_DAYS', 30)
        )


@dataclass
class ReportConfig:
    """Reporting configuration."""
    max_report_rows: int = 100000
    report_retention_days: int = 90
    async_report_generation: bool = True
    cache_report_results: bool = True
    cache_timeout_minutes: int = 60
    export_formats: List[str] = field(default_factory=lambda: ['csv', 'xlsx', 'pdf'])
    
    @classmethod
    def from_settings(cls) -> 'ReportConfig':
        """Create config from Django settings."""
        return cls(
            max_report_rows=getattr(settings, 'REPORT_MAX_ROWS', 100000),
            report_retention_days=getattr(settings, 'REPORT_RETENTION_DAYS', 90),
            async_report_generation=getattr(settings, 'REPORT_ASYNC_GENERATION', True),
            cache_report_results=getattr(settings, 'REPORT_CACHE_RESULTS', True),
            cache_timeout_minutes=getattr(settings, 'REPORT_CACHE_TIMEOUT', 60),
            export_formats=getattr(settings, 'REPORT_EXPORT_FORMATS', ['csv', 'xlsx', 'pdf'])
        )


@dataclass
class MLConfig:
    """Machine learning configuration."""
    enabled: bool = True
    model_training_enabled: bool = True
    prediction_cache_enabled: bool = True
    model_update_frequency_hours: int = 24
    confidence_threshold: float = 0.5
    feature_retention_days: int = 30
    
    @classmethod
    def from_settings(cls) -> 'MLConfig':
        """Create config from Django settings."""
        return cls(
            enabled=getattr(settings, 'ML_ENABLED', True),
            model_training_enabled=getattr(settings, 'ML_TRAINING_ENABLED', True),
            prediction_cache_enabled=getattr(settings, 'ML_PREDICTION_CACHE_ENABLED', True),
            model_update_frequency_hours=getattr(settings, 'ML_MODEL_UPDATE_FREQUENCY', 24),
            confidence_threshold=getattr(settings, 'ML_CONFIDENCE_THRESHOLD', 0.5),
            feature_retention_days=getattr(settings, 'ML_FEATURE_RETENTION_DAYS', 30)
        )


@dataclass
class CreativeConfig:
    """Creative management configuration."""
    max_file_size_mb: int = 50
    allowed_image_formats: List[str] = field(default_factory=lambda: ['jpg', 'jpeg', 'png', 'gif', 'webp'])
    allowed_video_formats: List[str] = field(default_factory=lambda: ['mp4', 'webm', 'mov'])
    auto_approval_enabled: bool = False
    creative_review_required: bool = True
    max_creatives_per_campaign: int = 50
    
    @classmethod
    def from_settings(cls) -> 'CreativeConfig':
        """Create config from Django settings."""
        return cls(
            max_file_size_mb=getattr(settings, 'CREATIVE_MAX_FILE_SIZE_MB', 50),
            allowed_image_formats=getattr(settings, 'CREATIVE_ALLOWED_IMAGE_FORMATS', ['jpg', 'jpeg', 'png', 'gif', 'webp']),
            allowed_video_formats=getattr(settings, 'CREATIVE_ALLOWED_VIDEO_FORMATS', ['mp4', 'webm', 'mov']),
            auto_approval_enabled=getattr(settings, 'CREATIVE_AUTO_APPROVAL_ENABLED', False),
            creative_review_required=getattr(settings, 'CREATIVE_REVIEW_REQUIRED', True),
            max_creatives_per_campaign=getattr(settings, 'CREATIVE_MAX_PER_CAMPAIGN', 50)
        )


@dataclass
class TargetingConfig:
    """Targeting configuration."""
    max_targeting_rules_per_campaign: int = 100
    geo_targeting_enabled: bool = True
    demographic_targeting_enabled: bool = True
    behavioral_targeting_enabled: bool = True
    device_targeting_enabled: bool = True
    time_targeting_enabled: bool = True
    
    @classmethod
    def from_settings(cls) -> 'TargetingConfig':
        """Create config from Django settings."""
        return cls(
            max_targeting_rules_per_campaign=getattr(settings, 'TARGETING_MAX_RULES_PER_CAMPAIGN', 100),
            geo_targeting_enabled=getattr(settings, 'TARGETING_GEO_ENABLED', True),
            demographic_targeting_enabled=getattr(settings, 'TARGETING_DEMOGRAPHIC_ENABLED', True),
            behavioral_targeting_enabled=getattr(settings, 'TARGETING_BEHAVIORAL_ENABLED', True),
            device_targeting_enabled=getattr(settings, 'TARGETING_DEVICE_ENABLED', True),
            time_targeting_enabled=getattr(settings, 'TARGETING_TIME_ENABLED', True)
        )


# Extended Configuration Manager
class ExtendedConfigManager(ConfigManager):
    """Extended configuration manager with additional configs."""
    
    def __init__(self):
        super().__init__()
        self._offer_config = None
        self._tracking_config = None
        self._fraud_config = None
        self._notification_config = None
        self._report_config = None
        self._ml_config = None
        self._creative_config = None
        self._targeting_config = None
    
    def get_offer_config(self) -> OfferConfig:
        """Get offer configuration."""
        if self._offer_config is None:
            self._offer_config = OfferConfig.from_settings()
        return self._offer_config
    
    def get_tracking_config(self) -> TrackingConfig:
        """Get tracking configuration."""
        if self._tracking_config is None:
            self._tracking_config = TrackingConfig.from_settings()
        return self._tracking_config
    
    def get_fraud_config(self) -> FraudConfig:
        """Get fraud detection configuration."""
        if self._fraud_config is None:
            self._fraud_config = FraudConfig.from_settings()
        return self._fraud_config
    
    def get_notification_config(self) -> NotificationConfig:
        """Get notification configuration."""
        if self._notification_config is None:
            self._notification_config = NotificationConfig.from_settings()
        return self._notification_config
    
    def get_report_config(self) -> ReportConfig:
        """Get reporting configuration."""
        if self._report_config is None:
            self._report_config = ReportConfig.from_settings()
        return self._report_config
    
    def get_ml_config(self) -> MLConfig:
        """Get machine learning configuration."""
        if self._ml_config is None:
            self._ml_config = MLConfig.from_settings()
        return self._ml_config
    
    def get_creative_config(self) -> CreativeConfig:
        """Get creative configuration."""
        if self._creative_config is None:
            self._creative_config = CreativeConfig.from_settings()
        return self._creative_config
    
    def get_targeting_config(self) -> TargetingConfig:
        """Get targeting configuration."""
        if self._targeting_config is None:
            self._targeting_config = TargetingConfig.from_settings()
        return self._targeting_config
    
    def reload_all_configs(self) -> None:
        """Reload all configurations."""
        super().reload_all_configs()
        self._offer_config = None
        self._tracking_config = None
        self._fraud_config = None
        self._notification_config = None
        self._report_config = None
        self._ml_config = None
        self._creative_config = None
        self._targeting_config = None


# Use extended config manager
config_manager = ExtendedConfigManager()


def setup_logging() -> None:
    """Setup logging based on configuration."""
    log_config = config_manager.get_logging_config()
    
    logging.basicConfig(
        level=getattr(logging, log_config.level.upper()),
        format=log_config.format,
        handlers=[]
    )
    
    # Add console handler
    if 'console' in log_config.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_config.format))
        logging.getLogger().addHandler(console_handler)
    
    # Add file handler if configured
    if log_config.log_file and 'file' in log_config.handlers:
        from logging.handlers import RotatingFileHandler
        
        file_handler = RotatingFileHandler(
            log_config.log_file,
            maxBytes=log_config.max_file_size,
            backupCount=log_config.backup_count
        )
        file_handler.setFormatter(logging.Formatter(log_config.format))
        logging.getLogger().addHandler(file_handler)


def load_dynamic_settings() -> None:
    """Load dynamic settings from file if configured."""
    dynamic_settings_file = config_manager.get_env_var('DYNAMIC_SETTINGS_FILE')
    if dynamic_settings_file and os.path.exists(dynamic_settings_file):
        dynamic_config.load_from_file(dynamic_settings_file)
