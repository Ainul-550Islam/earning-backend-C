"""
Advertiser Portal Django App Configuration

This module contains the Django app configuration for the Advertiser Portal,
including app settings, URLs, and initialization.
"""

from django.apps import AppConfig
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class AdvertiserPortalConfig(AppConfig):
    """Django app configuration for Advertiser Portal."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.advertiser_portal'
    verbose_name = 'Advertiser Portal'
    
    def ready(self):
        """Initialize app when Django starts."""
        # Import signals
        try:
            from . import signals
            logger.info("Advertiser Portal signals loaded successfully")
        except ImportError as e:
            logger.warning(f"Failed to load Advertiser Portal signals: {e}")
        
        # Initialize app components
        self._initialize_components()
        
        logger.info("Advertiser Portal app initialized successfully")
    
    def _initialize_components(self):
        """Initialize app components."""
        # Initialize cache
        try:
            from .cache import cache_manager
            cache_manager.initialize()
            logger.info("Cache manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize cache manager: {e}")
        
        # Initialize events
        try:
            from .events import event_publisher
            event_publisher.initialize()
            logger.info("Event publisher initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize event publisher: {e}")
        
        # Initialize hooks
        try:
            from .hooks import hook_manager
            hook_manager.initialize()
            logger.info("Hook manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize hook manager: {e}")
        
        # Initialize plugins
        try:
            from .plugins import plugin_manager
            plugin_manager.initialize()
            logger.info("Plugin manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize plugin manager: {e}")
        
        # Initialize tasks
        try:
            from .tasks import task_manager
            task_manager.initialize()
            logger.info("Task manager initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize task manager: {e}")


# App settings
ADVERTISER_PORTAL_SETTINGS = {
    # API Configuration
    'API_VERSION': 'v1',
    'API_PREFIX': 'api/v1',
    'API_DOCS_URL': '/api/v1/docs/',
    
    # Pagination
    'DEFAULT_PAGE_SIZE': 20,
    'MAX_PAGE_SIZE': 100,
    
    # Cache Configuration
    'CACHE_TIMEOUT': 300,  # 5 minutes
    'CACHE_KEY_PREFIX': 'advertiser_portal',
    
    # File Upload Configuration
    'MAX_FILE_SIZE': 10 * 1024 * 1024,  # 10MB
    'ALLOWED_FILE_TYPES': [
        'image/jpeg', 'image/png', 'image/gif',
        'video/mp4', 'video/quicktime',
        'text/html', 'application/pdf'
    ],
    
    # Email Configuration
    'EMAIL_FROM_ADDRESS': settings.DEFAULT_FROM_EMAIL,
    'EMAIL_ADMIN_ADDRESS': getattr(settings, 'ADMIN_EMAIL', settings.DEFAULT_FROM_EMAIL),
    
    # Security Configuration
    'TOKEN_EXPIRY_TIME': 24 * 60 * 60,  # 24 hours
    'PASSWORD_MIN_LENGTH': 8,
    'SESSION_TIMEOUT': 30 * 60,  # 30 minutes
    
    # Rate Limiting
    'RATE_LIMIT_REQUESTS': 1000,
    'RATE_LIMIT_WINDOW': 3600,  # 1 hour
    
    # Analytics Configuration
    'ANALYTICS_BATCH_SIZE': 1000,
    'ANALYTICS_RETENTION_DAYS': 365,
    
    # Billing Configuration
    'BILLING_TAX_DEFAULT_RATE': 0.0,
    'BILLING_CREDIT_DEFAULT_LIMIT': 1000.00,
    
    # Notification Configuration
    'NOTIFICATION_BATCH_SIZE': 100,
    'NOTIFICATION_RETRY_ATTEMPTS': 3,
    
    # Integration Configuration
    'INTEGRATION_TIMEOUT': 30,  # 30 seconds
    'INTEGRATION_RETRY_ATTEMPTS': 3,
    
    # Feature Flags
    'FEATURES': {
        'advanced_analytics': True,
        'real_time_metrics': True,
        'auto_optimization': True,
        'multi_currency': True,
        'custom_reports': True,
        'api_webhooks': True,
        'fraud_detection': True,
        'a_b_testing': True,
    }
}
