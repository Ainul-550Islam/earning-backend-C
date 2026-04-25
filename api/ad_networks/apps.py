# api/ad_networks/apps.py
# SaaS-Ready Multi-Tenant Ad Networks App Configuration

from django.apps import AppConfig
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)

class AdNetworksConfig(AppConfig):
    """
    SaaS-Ready Ad Networks App Configuration
    Multi-tenant architecture with complete feature set
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.ad_networks'
    label = 'ad_networks'
    verbose_name = 'Ad Networks Management'
    
    # App metadata
    description = 'SaaS-Ready Multi-Tenant Ad Networks Management System'
    version = '2.0.0'
    author = 'Development Team'
    
    # Required apps
    requires = [
        'api.tenants',
        'core',
        'rest_framework',
        'django_filters',
        'django_celery_beat',
        'django_celery_results',
    ]
    
    def ready(self):
        """
        Initialize ad_networks app with SaaS-ready features
        """
        logger.info("Initializing Ad Networks SaaS-Ready App...")
        
        # Import and initialize signals
        self._initialize_signals()
        
        # Initialize admin registration
        self._initialize_admin()
        
        # Initialize cache configuration
        self._initialize_cache()
        
        # Initialize task scheduling
        self._initialize_tasks()
        
        # Initialize event system
        self._initialize_events()
        
        # Initialize hooks system
        self._initialize_hooks()
        
        # Initialize registry system
        self._initialize_registry()
        
        # Initialize fraud detection
        self._initialize_fraud_detection()
        
        # Initialize analytics
        self._initialize_analytics()
        
        # Initialize middleware
        self._initialize_middleware()
        
        logger.info("Ad Networks SaaS-Ready App initialized successfully!")
    
    def _initialize_signals(self):
        """Initialize signal handlers"""
        try:
            import api.ad_networks.signals
            logger.info("Ad Networks signals loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not load signals: {e}")
    
    def _initialize_admin(self):
        """Initialize admin registration"""
        try:
            from django.contrib import admin
            from .models import (
                # Core Models
                AdNetwork, OfferCategory, Offer, UserOfferEngagement,
                OfferConversion, OfferWall, OfferClick, OfferReward,
                
                # Network Models
                NetworkAPILog, NetworkStatistic, NetworkHealthCheck,
                
                # Fraud Models
                BlacklistedIP, FraudDetectionRule, KnownBadIP,
                
                # Analytics Models
                SmartOfferRecommendation, OfferPerformanceAnalytics,
                
                # System Models
                UserOfferLimit, OfferSyncLog, OfferTag, OfferTagging,
                OfferDailyLimit, AdNetworkWebhookLog
            )
            
            logger.info("Loading Ad Networks admin registration...")
            
            # Try to import admin classes
            try:
                from .admin import (
                    AdNetworkAdmin, OfferCategoryAdmin, OfferAdmin,
                    UserOfferEngagementAdmin, OfferConversionAdmin,
                    OfferWallAdmin, OfferClickAdmin, OfferRewardAdmin,
                    NetworkAPILogAdmin, NetworkStatisticAdmin,
                    NetworkHealthCheckAdmin, BlacklistedIPAdmin,
                    FraudDetectionRuleAdmin, KnownBadIPAdmin,
                    SmartOfferRecommendationAdmin, OfferPerformanceAnalyticsAdmin,
                    UserOfferLimitAdmin, OfferSyncLogAdmin, OfferTagAdmin,
                    OfferTaggingAdmin, OfferDailyLimitAdmin,
                    AdNetworkWebhookLogAdmin
                )
                
                # Model-Admin registration mapping
                models_to_register = [
                    (AdNetwork, AdNetworkAdmin),
                    (OfferCategory, OfferCategoryAdmin),
                    (Offer, OfferAdmin),
                    (UserOfferEngagement, UserOfferEngagementAdmin),
                    (OfferConversion, OfferConversionAdmin),
                    (OfferWall, OfferWallAdmin),
                    (OfferClick, OfferClickAdmin),
                    (OfferReward, OfferRewardAdmin),
                    (NetworkAPILog, NetworkAPILogAdmin),
                    (NetworkStatistic, NetworkStatisticAdmin),
                    (NetworkHealthCheck, NetworkHealthCheckAdmin),
                    (BlacklistedIP, BlacklistedIPAdmin),
                    (FraudDetectionRule, FraudDetectionRuleAdmin),
                    (KnownBadIP, KnownBadIPAdmin),
                    (SmartOfferRecommendation, SmartOfferRecommendationAdmin),
                    (OfferPerformanceAnalytics, OfferPerformanceAnalyticsAdmin),
                    (UserOfferLimit, UserOfferLimitAdmin),
                    (OfferSyncLog, OfferSyncLogAdmin),
                    (OfferTag, OfferTagAdmin),
                    (OfferTagging, OfferTaggingAdmin),
                    (OfferDailyLimit, OfferDailyLimitAdmin),
                    (AdNetworkWebhookLog, AdNetworkWebhookLogAdmin),
                ]
                
                registered_count = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model, admin_class)
                            registered_count += 1
                            logger.debug(f"Registered: {model.__name__} with {admin_class.__name__}")
                        except Exception as e:
                            logger.error(f"Could not register {model.__name__}: {e}")
                
                if registered_count > 0:
                    logger.info(f"Successfully registered {registered_count} Ad Networks models")
                else:
                    logger.info("All Ad Networks models already registered")
                    
            except ImportError as e:
                logger.warning(f"Could not import admin classes: {e}")
                # Fallback: register without custom admin
                fallback_models = [
                    AdNetwork, OfferCategory, Offer, UserOfferEngagement,
                    OfferConversion, OfferWall, OfferClick, OfferReward,
                    NetworkAPILog, NetworkStatistic, NetworkHealthCheck,
                    BlacklistedIP, FraudDetectionRule, KnownBadIP,
                    SmartOfferRecommendation, OfferPerformanceAnalytics,
                    UserOfferLimit, OfferSyncLog, OfferTag, OfferTagging,
                    OfferDailyLimit, AdNetworkWebhookLog
                ]
                
                for model in fallback_models:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model)
                            logger.info(f"Registered: {model.__name__} (default admin)")
                        except Exception as e:
                            logger.error(f"Could not register {model.__name__}: {e}")
                
        except Exception as e:
            logger.error(f"Ad Networks admin registration error: {e}")
    
    def _initialize_cache(self):
        """Initialize cache configuration"""
        try:
            from django.core.cache import cache
            from .constants import CACHE_TIMEOUTS
            
            # Test cache connectivity
            cache.set('ad_networks_test', 'test_value', timeout=60)
            test_value = cache.get('ad_networks_test')
            
            if test_value == 'test_value':
                cache.delete('ad_networks_test')
                logger.info("Cache initialized successfully")
            else:
                logger.warning("Cache test failed")
                
        except Exception as e:
            logger.error(f"Cache initialization error: {e}")
    
    def _initialize_tasks(self):
        """Initialize Celery tasks and scheduling"""
        try:
            from .tasks import (
                sync_offers_task, cleanup_expired_blacklist_task,
                generate_analytics_task, process_fraud_detection_task,
                update_network_health_task, cleanup_old_logs_task
            )
            
            # Register periodic tasks
            from django_celery_beat.models import PeriodicTask, CrontabSchedule
            from django.utils import timezone
            
            # Sync offers every hour
            sync_schedule, created = CrontabSchedule.objects.get_or_create(
                minute='0',
                hour='*',
                defaults={'timezone': timezone.get_current_timezone()}
            )
            
            PeriodicTask.objects.get_or_create(
                name='Sync Ad Networks Offers',
                defaults={
                    'crontab': sync_schedule,
                    'task': 'api.ad_networks.tasks.sync_offers_task',
                    'enabled': True
                }
            )
            
            # Cleanup blacklist daily
            cleanup_schedule, created = CrontabSchedule.objects.get_or_create(
                minute='0',
                hour='2',
                defaults={'timezone': timezone.get_current_timezone()}
            )
            
            PeriodicTask.objects.get_or_create(
                name='Cleanup Expired Blacklist',
                defaults={
                    'crontab': cleanup_schedule,
                    'task': 'api.ad_networks.tasks.cleanup_expired_blacklist_task',
                    'enabled': True
                }
            )
            
            # Generate analytics daily
            analytics_schedule, created = CrontabSchedule.objects.get_or_create(
                minute='30',
                hour='1',
                defaults={'timezone': timezone.get_current_timezone()}
            )
            
            PeriodicTask.objects.get_or_create(
                name='Generate Analytics',
                defaults={
                    'crontab': analytics_schedule,
                    'task': 'api.ad_networks.tasks.generate_analytics_task',
                    'enabled': True
                }
            )
            
            logger.info("Celery tasks initialized successfully")
            
        except Exception as e:
            logger.warning(f"Task initialization error: {e}")
    
    def _initialize_events(self):
        """Initialize event system"""
        try:
            from .events import EventSystem
            EventSystem.initialize()
            logger.info("Event system initialized successfully")
        except Exception as e:
            logger.warning(f"Event system initialization error: {e}")
    
    def _initialize_hooks(self):
        """Initialize hooks system"""
        try:
            from .hooks import HookSystem
            HookSystem.initialize()
            logger.info("Hooks system initialized successfully")
        except Exception as e:
            logger.warning(f"Hooks system initialization error: {e}")
    
    def _initialize_registry(self):
        """Initialize registry system"""
        try:
            from .registry import ComponentRegistry
            ComponentRegistry.initialize()
            logger.info("Registry system initialized successfully")
        except Exception as e:
            logger.warning(f"Registry system initialization error: {e}")
    
    def _initialize_fraud_detection(self):
        """Initialize fraud detection system"""
        try:
            from .fraud import FraudDetectionSystem
            FraudDetectionSystem.initialize()
            logger.info("Fraud detection system initialized successfully")
        except Exception as e:
            logger.warning(f"Fraud detection initialization error: {e}")
    
    def _initialize_analytics(self):
        """Initialize analytics system"""
        try:
            from .analytics import AnalyticsSystem
            AnalyticsSystem.initialize()
            logger.info("Analytics system initialized successfully")
        except Exception as e:
            logger.warning(f"Analytics system initialization error: {e}")
    
    def _initialize_middleware(self):
        """Initialize middleware configuration"""
        try:
            # Register custom middleware if needed
            from django.conf import settings
            
            middleware_list = getattr(settings, 'MIDDLEWARE', [])
            
            # Add tenant middleware if not present
            tenant_middleware = 'api.tenants.middleware.TenantMiddleware'
            if tenant_middleware not in middleware_list:
                middleware_list.insert(0, tenant_middleware)
                settings.MIDDLEWARE = middleware_list
                logger.info("Tenant middleware added to settings")
            
        except Exception as e:
            logger.warning(f"Middleware initialization error: {e}")
    
    def get_tenant_config(self, tenant_id):
        """
        Get tenant-specific configuration
        """
        try:
            from api.tenants.models import Tenant
            tenant = Tenant.objects.get(tenant_id=tenant_id)
            return tenant.config
        except Exception as e:
            logger.error(f"Error getting tenant config for {tenant_id}: {e}")
            return {}
    
    def is_ready(self):
        """
        Check if app is fully initialized
        """
        try:
            from django.core.cache import cache
            return cache.get('ad_networks_app_ready', False)
        except:
            return False
    
    def mark_ready(self):
        """
        Mark app as ready
        """
        try:
            from django.core.cache import cache
            cache.set('ad_networks_app_ready', True, timeout=3600)
        except:
            pass
    
    def get_health_status(self):
        """
        Get app health status
        """
        status = {
            'app': 'ad_networks',
            'status': 'healthy',
            'version': self.version,
            'checks': {}
        }
        
        # Check database connectivity
        try:
            from .models import AdNetwork
            AdNetwork.objects.count()
            status['checks']['database'] = 'healthy'
        except Exception as e:
            status['checks']['database'] = f'unhealthy: {str(e)}'
            status['status'] = 'unhealthy'
        
        # Check cache connectivity
        try:
            from django.core.cache import cache
            cache.set('health_check', 'ok', timeout=10)
            cache.get('health_check')
            status['checks']['cache'] = 'healthy'
        except Exception as e:
            status['checks']['cache'] = f'unhealthy: {str(e)}'
            status['status'] = 'degraded'
        
        # Check task queue
        try:
            from celery import current_app
            current_app.inspect().stats()
            status['checks']['tasks'] = 'healthy'
        except Exception as e:
            status['checks']['tasks'] = f'unhealthy: {str(e)}'
            status['status'] = 'degraded'
        
        return status
    
    def get_metrics(self):
        """
        Get app metrics
        """
        try:
            from .models import (
                AdNetwork, Offer, UserOfferEngagement,
                OfferConversion, BlacklistedIP
            )
            
            metrics = {
                'ad_networks': AdNetwork.objects.count(),
                'offers': Offer.objects.count(),
                'engagements': UserOfferEngagement.objects.count(),
                'conversions': OfferConversion.objects.count(),
                'blacklisted_ips': BlacklistedIP.objects.count(),
            }
            
            # Get tenant metrics
            from api.tenants.models import Tenant
            metrics['tenants'] = Tenant.objects.count()
            
            return metrics
        except Exception as e:
            logger.error(f"Error getting metrics: {e}")
            return {}
    
    def cleanup(self):
        """
        Cleanup app resources
        """
        try:
            # Clear cache
            from django.core.cache import cache
            cache.delete_pattern('ad_networks_*')
            
            # Mark as not ready
            cache.delete('ad_networks_app_ready')
            
            logger.info("Ad Networks app cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# ============================================================================
# APP FACTORY
# ============================================================================

class AdNetworksAppFactory:
    """
    Factory for creating Ad Networks app instances
    """
    
    @staticmethod
    def create_app(config=None):
        """
        Create Ad Networks app instance with custom config
        """
        if config is None:
            return AdNetworksConfig
        
        class CustomAdNetworksConfig(AdNetworksConfig):
            def __init__(self, app_name, app_module):
                super().__init__(app_name, app_module)
                # Apply custom config
                for key, value in config.items():
                    setattr(self, key, value)
        
        return CustomAdNetworksConfig
    
    @staticmethod
    def get_default_config():
        """
        Get default app configuration
        """
        return {
            'default_auto_field': 'django.db.models.BigAutoField',
            'name': 'api.ad_networks',
            'label': 'ad_networks',
            'verbose_name': 'Ad Networks Management',
            'description': 'SaaS-Ready Multi-Tenant Ad Networks Management System',
            'version': '2.0.0',
        }

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'AdNetworksConfig',
    'AdNetworksAppFactory',
]
