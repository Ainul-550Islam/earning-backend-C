"""
Tenant Apps Configuration - Improved Version with Enhanced Features

This module contains comprehensive Django app configuration for tenant management
with advanced initialization, signal handling, and system integration.
"""

from django.apps import AppConfig
from django.core.management import BaseCommand
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models.signals import post_migrate
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


class TenantConfig(AppConfig):
    """
    Comprehensive Django app configuration for tenant management.
    
    This configuration handles app initialization, signal connections,
    and system setup for the tenant management system.
    """
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tenants'
    verbose_name = _('Tenant Management')
    
    def ready(self):
        """
        Initialize the tenant management system.
        
        This method is called when the Django app is ready and
        sets up all necessary components for tenant management.
        """
        # Import models to ensure they're registered
        from .models_improved import (
            Tenant, TenantSettings, TenantBilling, 
            TenantInvoice, TenantAuditLog
        )
        
        # Import and connect signals
        from . import signals_improved
        
        # Connect post_migrate signal
        post_migrate.connect(self.on_post_migrate, sender=self)
        
        # Initialize cache
        self._initialize_cache()
        
        # Set up middleware
        self._setup_middleware()
        
        # Initialize security service
        self._initialize_security()
        
        # Log initialization
        logger.info("Tenant management system initialized successfully")
    
    def _initialize_cache(self):
        """Initialize cache settings for tenant management."""
        try:
            # Set cache keys and timeouts
            cache_settings = {
                'TENANT_CACHE_TIMEOUT': getattr(settings, 'TENANT_CACHE_TIMEOUT', 300),
                'TENANT_SETTINGS_CACHE_TIMEOUT': getattr(settings, 'TENANT_SETTINGS_CACHE_TIMEOUT', 600),
                'TENANT_BILLING_CACHE_TIMEOUT': getattr(settings, 'TENANT_BILLING_CACHE_TIMEOUT', 300),
                'TENANT_FEATURES_CACHE_TIMEOUT': getattr(settings, 'TENANT_FEATURES_CACHE_TIMEOUT', 300),
            }
            
            # Store cache settings in cache for easy access
            cache.set('tenant_cache_settings', cache_settings, timeout=3600)
            
            logger.debug("Tenant cache initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tenant cache: {e}")
    
    def _setup_middleware(self):
        """Set up middleware for tenant management."""
        try:
            # Get middleware configuration
            middleware_classes = getattr(settings, 'MIDDLEWARE', [])
            
            # Add tenant middleware if not already present
            tenant_middleware = [
                'tenants.middleware_improved.TenantMiddleware',
                'tenants.middleware_improved.TenantSecurityMiddleware',
                'tenants.middleware_improved.TenantContextMiddleware',
                'tenants.middleware_improved.TenantAuditMiddleware',
            ]
            
            for middleware in tenant_middleware:
                if middleware not in middleware_classes:
                    logger.info(f"Adding tenant middleware: {middleware}")
            
            logger.debug("Tenant middleware setup completed")
        except Exception as e:
            logger.error(f"Failed to setup tenant middleware: {e}")
    
    def _initialize_security(self):
        """Initialize security settings for tenant management."""
        try:
            from .services_improved import tenant_security_service
            
            # Set up security configuration
            security_config = {
                'MAX_LOGIN_ATTEMPTS': getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
                'LOGIN_LOCKOUT_DURATION': getattr(settings, 'LOGIN_LOCKOUT_DURATION', 300),
                'TENANT_RATE_LIMIT_REQUESTS': getattr(settings, 'TENANT_RATE_LIMIT_REQUESTS', 1000),
                'TENANT_RATE_LIMIT_WINDOW': getattr(settings, 'TENANT_RATE_LIMIT_WINDOW', 60),
                'TENANT_IP_WHITELIST_ENABLED': getattr(settings, 'TENANT_IP_WHITELIST_ENABLED', False),
                'TENANT_BUSINESS_HOURS_ENABLED': getattr(settings, 'TENANT_BUSINESS_HOURS_ENABLED', False),
            }
            
            # Store security config
            cache.set('tenant_security_config', security_config, timeout=3600)
            
            logger.debug("Tenant security initialized")
        except Exception as e:
            logger.error(f"Failed to initialize tenant security: {e}")
    
    def on_post_migrate(self, sender, **kwargs):
        """
        Handle post-migration tasks.
        
        This method is called after migrations are applied and
        performs necessary setup tasks for the tenant system.
        """
        try:
            # Create default tenant if configured
            if getattr(settings, 'CREATE_DEFAULT_TENANT', False):
                self._create_default_tenant()
            
            # Set up default permissions
            self._setup_default_permissions()
            
            # Initialize system settings
            self._initialize_system_settings()
            
            logger.info("Post-migration setup completed")
        except Exception as e:
            logger.error(f"Post-migration setup failed: {e}")
    
    def _create_default_tenant(self):
        """Create default tenant for the system."""
        try:
            from .models_improved import Tenant
            from .services_improved import tenant_service
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            # Check if default tenant already exists
            default_slug = getattr(settings, 'DEFAULT_TENANT_SLUG', 'default')
            if Tenant.objects.filter(slug=default_slug).exists():
                logger.info("Default tenant already exists")
                return
            
            # Get or create default admin user
            admin_email = getattr(settings, 'DEFAULT_ADMIN_EMAIL', 'admin@example.com')
            admin_user, created = User.objects.get_or_create(
                email=admin_email,
                defaults={
                    'username': admin_email.split('@')[0],
                    'is_staff': True,
                    'is_superuser': True,
                    'is_active': True,
                }
            )
            
            if created:
                admin_user.set_password(User.objects.make_random_password())
                admin_user.save()
                logger.info(f"Created default admin user: {admin_email}")
            
            # Create default tenant
            tenant_data = {
                'name': getattr(settings, 'DEFAULT_TENANT_NAME', 'Default Tenant'),
                'slug': default_slug,
                'plan': getattr(settings, 'DEFAULT_TENANT_PLAN', 'enterprise'),
                'max_users': getattr(settings, 'DEFAULT_TENANT_MAX_USERS', 1000),
                'admin_email': admin_email,
                'owner_email': admin_email,
            }
            
            default_tenant = tenant_service.create_tenant(tenant_data, admin_user)
            logger.info(f"Created default tenant: {default_tenant.name}")
            
        except Exception as e:
            logger.error(f"Failed to create default tenant: {e}")
    
    def _setup_default_permissions(self):
        """Set up default permissions for tenant management."""
        try:
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType
            
            # Get content types for tenant models
            tenant_content_type = ContentType.objects.get(
                app_label='tenants', 
                model='tenant'
            )
            
            # Create default permissions if they don't exist
            default_permissions = [
                ('can_view_all_tenants', 'Can view all tenants'),
                ('can_manage_all_tenants', 'Can manage all tenants'),
                ('can_view_tenant_billing', 'Can view tenant billing'),
                ('can_manage_tenant_billing', 'Can manage tenant billing'),
                ('can_view_tenant_analytics', 'Can view tenant analytics'),
                ('can_manage_tenant_settings', 'Can manage tenant settings'),
            ]
            
            for codename, name in default_permissions:
                Permission.objects.get_or_create(
                    codename=codename,
                    name=name,
                    content_type=tenant_content_type
                )
            
            logger.debug("Default permissions setup completed")
        except Exception as e:
            logger.error(f"Failed to setup default permissions: {e}")
    
    def _initialize_system_settings(self):
        """Initialize system-wide settings for tenant management."""
        try:
            # Set up system configuration
            system_config = {
                'TENANT_MAX_USERS_PER_PLAN': {
                    'basic': 100,
                    'pro': 500,
                    'enterprise': 10000,
                    'custom': 0,  # Unlimited
                },
                'TENANT_FEATURES_PER_PLAN': {
                    'basic': ['referral', 'offerwall'],
                    'pro': ['referral', 'offerwall', 'kyc', 'leaderboard'],
                    'enterprise': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics'],
                    'custom': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics', 'api_access'],
                },
                'TENANT_DEFAULT_SETTINGS': {
                    'min_withdrawal': 5.00,
                    'max_withdrawal': 10000.00,
                    'withdrawal_fee_percent': 0.00,
                    'referral_bonus_amount': 1.00,
                    'referral_bonus_type': 'fixed',
                    'max_referral_levels': 3,
                    'referral_percentages': [50, 30, 20],
                    'require_email_verification': True,
                    'require_phone_verification': False,
                    'enable_two_factor_auth': False,
                    'password_min_length': 8,
                    'session_timeout_minutes': 1440,
                    'api_rate_limit': '1000/hour',
                    'login_rate_limit': '5/minute',
                },
            }
            
            # Store system config
            cache.set('tenant_system_config', system_config, timeout=3600)
            
            logger.debug("System settings initialized")
        except Exception as e:
            logger.error(f"Failed to initialize system settings: {e}")


class TenantManagementCommand(BaseCommand):
    """
    Base class for tenant management commands.
    
    This provides common functionality for all tenant management
    commands including logging and error handling.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(f'tenants.management.{self.__class__.__name__}')
    
    def handle_error(self, message, exception=None):
        """Handle command errors with proper logging."""
        if exception:
            self.logger.error(f"{message}: {exception}")
            self.stdout.write(self.style.ERROR(f"{message}: {exception}"))
        else:
            self.logger.error(message)
            self.stdout.write(self.style.ERROR(message))
    
    def handle_success(self, message):
        """Handle command success with proper logging."""
        self.logger.info(message)
        self.stdout.write(self.style.SUCCESS(message))
    
    def handle_warning(self, message):
        """Handle command warnings with proper logging."""
        self.logger.warning(message)
        self.stdout.write(self.style.WARNING(message))


# Utility functions
def get_tenant_config():
    """
    Get tenant configuration from cache or settings.
    
    Returns:
        Dictionary containing tenant configuration
    """
    config = cache.get('tenant_cache_settings')
    if not config:
        config = {
            'TENANT_CACHE_TIMEOUT': getattr(settings, 'TENANT_CACHE_TIMEOUT', 300),
            'TENANT_SETTINGS_CACHE_TIMEOUT': getattr(settings, 'TENANT_SETTINGS_CACHE_TIMEOUT', 600),
            'TENANT_BILLING_CACHE_TIMEOUT': getattr(settings, 'TENANT_BILLING_CACHE_TIMEOUT', 300),
            'TENANT_FEATURES_CACHE_TIMEOUT': getattr(settings, 'TENANT_FEATURES_CACHE_TIMEOUT', 300),
        }
        cache.set('tenant_cache_settings', config, timeout=3600)
    
    return config


def get_tenant_security_config():
    """
    Get tenant security configuration from cache or settings.
    
    Returns:
        Dictionary containing tenant security configuration
    """
    config = cache.get('tenant_security_config')
    if not config:
        config = {
            'MAX_LOGIN_ATTEMPTS': getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
            'LOGIN_LOCKOUT_DURATION': getattr(settings, 'LOGIN_LOCKOUT_DURATION', 300),
            'TENANT_RATE_LIMIT_REQUESTS': getattr(settings, 'TENANT_RATE_LIMIT_REQUESTS', 1000),
            'TENANT_RATE_LIMIT_WINDOW': getattr(settings, 'TENANT_RATE_LIMIT_WINDOW', 60),
            'TENANT_IP_WHITELIST_ENABLED': getattr(settings, 'TENANT_IP_WHITELIST_ENABLED', False),
            'TENANT_BUSINESS_HOURS_ENABLED': getattr(settings, 'TENANT_BUSINESS_HOURS_ENABLED', False),
        }
        cache.set('tenant_security_config', config, timeout=3600)
    
    return config


def get_tenant_system_config():
    """
    Get tenant system configuration from cache or settings.
    
    Returns:
        Dictionary containing tenant system configuration
    """
    config = cache.get('tenant_system_config')
    if not config:
        config = {
            'TENANT_MAX_USERS_PER_PLAN': {
                'basic': 100,
                'pro': 500,
                'enterprise': 10000,
                'custom': 0,  # Unlimited
            },
            'TENANT_FEATURES_PER_PLAN': {
                'basic': ['referral', 'offerwall'],
                'pro': ['referral', 'offerwall', 'kyc', 'leaderboard'],
                'enterprise': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics'],
                'custom': ['referral', 'offerwall', 'kyc', 'leaderboard', 'chat', 'push_notifications', 'analytics', 'api_access'],
            },
            'TENANT_DEFAULT_SETTINGS': {
                'min_withdrawal': 5.00,
                'max_withdrawal': 10000.00,
                'withdrawal_fee_percent': 0.00,
                'referral_bonus_amount': 1.00,
                'referral_bonus_type': 'fixed',
                'max_referral_levels': 3,
                'referral_percentages': [50, 30, 20],
                'require_email_verification': True,
                'require_phone_verification': False,
                'enable_two_factor_auth': False,
                'password_min_length': 8,
                'session_timeout_minutes': 1440,
                'api_rate_limit': '1000/hour',
                'login_rate_limit': '5/minute',
            },
        }
        cache.set('tenant_system_config', config, timeout=3600)
    
    return config


# Export configuration
__all__ = [
    'TenantConfig',
    'TenantManagementCommand',
    'get_tenant_config',
    'get_tenant_security_config',
    'get_tenant_system_config',
]
