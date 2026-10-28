# cms/apps.py
"""
CMS Application Configuration

This file configures the Django CMS application and ensures all signal receivers,
integrations, and services are properly initialized when Django starts.
"""

from django.apps import AppConfig
from django.db.models import signals
import logging

logger = logging.getLogger('cms.apps')


class CmsConfig(AppConfig):
    """
    CMS Application Configuration
    
    - Initializes all signal receivers (cache, notifications, audit, etc.)
    - Registers event bus and integration system
    - Loads feature flags from database
    - Initializes all adapters for business logic
    """
    
    name = 'api.cms'
    verbose_name = 'Content Management System'
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        # ── Architectural layers (DDD pattern) — imported to register ──────────
        try:
            from cms import logic          # Business logic layer
            from cms import selectors      # Query/selector layer
            from cms import interactors    # Interactor layer
            from cms import use_cases      # Use-case orchestration
            from cms import repositories   # Repository pattern
            from cms import resources      # Resource layer
            from cms import plugins        # Plugin system
            from cms import hooks          # Hook system
        except ImportError as e:
            import logging
            logging.getLogger('cms').debug(f'Optional module not loaded: {e}')

        """
        Initialize application on Django startup.
        
        This method is called when Django finishes setting up, ensuring that:
        1. All signal receivers are registered
        2. Event bus is initialized
        3. Feature flags are loaded
        4. Adapters are ready for use
        5. Validators are registered
        
        Critical: Without these imports, signal receivers won't work!
        """
        
        logger.info("Initializing CMS application...")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 1: IMPORT ALL SIGNAL MODULES
        # This is CRITICAL — without these imports, signal receivers don't register
        # ─────────────────────────────────────────────────────────────────────────
        
        logger.debug("Loading signal receivers...")
        
        try:
            import api.cms.signals
            logger.debug("✓ Loaded cms.signals (cache invalidation, content triggers)")
        except ImportError as e:
            logger.error(f"Failed to import api.cms.signals: {e}")
        
        try:
            import api.cms.signals_kb
            logger.debug("✓ Loaded cms.signals_kb (knowledge base signals)")
        except ImportError as e:
            logger.error(f"Failed to import api.cms.signals_kb: {e}")
        
        try:
            import api.cms.receivers
            logger.debug("✓ Loaded cms.receivers (additional signal receivers)")
        except ImportError as e:
            logger.error(f"Failed to import api.cms.receivers: {e}")
        
        try:
            import api.cms.signals_cap
            logger.debug("✓ Loaded cms.signals_cap (CAP integration signals)")
        except ImportError as e:
            logger.error(f"Failed to import api.cms.signals_cap: {e}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 2: INTEGRATION SYSTEM SIGNALS
        # Event bus and integration system must be initialized
        # ─────────────────────────────────────────────────────────────────────────
        
        logger.debug("Initializing integration system...")
        
        try:
            import api.cms.INTEGRATION_SYSTEM.integ_signals
            logger.debug("✓ Loaded integration system signals")
        except ImportError as e:
            logger.error(f"Failed to import integration signals: {e}")
        
        try:
            from api.cms.INTEGRATION_SYSTEM.event_bus import EventBus
            EventBus.initialize()
            logger.info("✓ Event bus initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize event bus: {e}")
        
        try:
            from api.cms.INTEGRATION_SYSTEM.integ_registry import IntegrationRegistry
            IntegrationRegistry.discover_and_register()
            logger.info("✓ Integration registry loaded")
        except Exception as e:
            logger.error(f"Failed to initialize integration registry: {e}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 3: FEATURE FLAGS
        # Load feature flags from database for runtime feature control
        # ─────────────────────────────────────────────────────────────────────────
        
        logger.debug("Loading feature flags...")
        
        try:
            from api.cms.feature_flags import EnhancedFeatureFlagManager
            EnhancedFeatureFlagManager()  # instantiate — registers enhanced flags
            logger.info("✓ Feature flags manager initialized")
        except Exception as e:
            logger.error(f"Failed to initialize feature flags: {e}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 4: VALIDATORS
        # Register custom validators for models
        # ─────────────────────────────────────────────────────────────────────────
        
        logger.debug("Registering custom validators...")
        
        try:
            from api.cms.validators import register_custom_validators
            register_custom_validators()
            logger.info("✓ Custom validators registered")
        except (ImportError, AttributeError):
            # register_custom_validators is optional — validators still work
            # via Django's built-in validator system
            logger.debug("register_custom_validators not defined — skipping")
        except Exception as e:
            logger.error(f"Failed to register custom validators: {e}")
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 5: ADAPTERS INITIALIZATION
        # Initialize all adapters for fraud, payment, notifications, etc.
        # ─────────────────────────────────────────────────────────────────────────
        
        logger.debug("Initializing adapters...")
        self._initialize_adapters()
        
        # ─────────────────────────────────────────────────────────────────────────
        # STEP 6: VERIFICATION
        # Verify all critical systems are properly initialized
        # ─────────────────────────────────────────────────────────────────────────
        
        logger.debug("Verifying initialization...")
        self._verify_signals_wired()
        self._verify_event_bus()
        self._verify_adapters()
        
        logger.info("✓ CMS application initialization complete")
    
    def _initialize_adapters(self):
        """
        Initialize all business logic adapters.
        
        These adapters handle:
        - Fraud detection and prevention
        - Payment gateway integration
        - User wallet management
        - Analytics tracking
        - Notification delivery
        - Support and rate limiting
        """
        logger.debug("Initializing business adapters...")
        
        adapters_to_init = []
        
        # Fraud & Security Adapter
        try:
            from api.cms.adapters.fraud_security import FraudSecurityAdapter
            adapter = FraudSecurityAdapter()
            adapter.initialize()
            adapters_to_init.append(('FraudSecurityAdapter', adapter))
            logger.debug("✓ Fraud detection adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize FraudSecurityAdapter: {e}")
        
        # Payment Tenant Adapter
        try:
            from api.cms.adapters.payment_tenants import PaymentTenantAdapter
            adapter = PaymentTenantAdapter()
            adapter.initialize()
            adapters_to_init.append(('PaymentTenantAdapter', adapter))
            logger.debug("✓ Payment tenant adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize PaymentTenantAdapter: {e}")
        
        # User Wallet Adapter
        try:
            from api.cms.adapters.user_wallet import UserWalletAdapter
            adapter = UserWalletAdapter()
            adapter.initialize()
            adapters_to_init.append(('UserWalletAdapter', adapter))
            logger.debug("✓ User wallet adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize UserWalletAdapter: {e}")
        
        # Analytics Adapter
        try:
            from api.cms.adapters.analytics import AnalyticsAdapter
            adapter = AnalyticsAdapter()
            adapter.initialize()
            adapters_to_init.append(('AnalyticsAdapter', adapter))
            logger.debug("✓ Analytics adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AnalyticsAdapter: {e}")
        
        # Notifications Adapter
        try:
            from api.cms.adapters.notifications import NotificationsAdapter
            adapter = NotificationsAdapter()
            adapter.initialize()
            adapters_to_init.append(('NotificationsAdapter', adapter))
            logger.debug("✓ Notifications adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize NotificationsAdapter: {e}")
        
        # Gamification Adapter
        try:
            from api.cms.adapters.gamification import GamificationAdapter
            adapter = GamificationAdapter()
            adapter.initialize()
            adapters_to_init.append(('GamificationAdapter', adapter))
            logger.debug("✓ Gamification adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize GamificationAdapter: {e}")
        
        # Ad/Offerwall Adapter
        try:
            from api.cms.adapters.ad_offerwall import AdOfferwallAdapter
            adapter = AdOfferwallAdapter()
            adapter.initialize()
            adapters_to_init.append(('AdOfferwallAdapter', adapter))
            logger.debug("✓ Ad/Offerwall adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AdOfferwallAdapter: {e}")
        
        # Support & Rate Limiting Adapter
        try:
            from api.cms.adapters.support_ratelimit import SupportRateLimitAdapter
            adapter = SupportRateLimitAdapter()
            adapter.initialize()
            adapters_to_init.append(('SupportRateLimitAdapter', adapter))
            logger.debug("✓ Support/Rate limit adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize SupportRateLimitAdapter: {e}")
        
        if adapters_to_init:
            logger.info(f"✓ Initialized {len(adapters_to_init)} adapters: {[a[0] for a in adapters_to_init]}")
        else:
            logger.warning("No adapters were successfully initialized")
    
    def _verify_signals_wired(self):
        """
        Verify that signal receivers are properly registered.
        
        Checks that we have a minimum number of signal receivers registered,
        which indicates that signal modules were properly imported.
        """
        from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
        
        signal_counts = {
            'post_save': len(post_save.receivers),
            'pre_save': len(pre_save.receivers),
            'pre_delete': len(pre_delete.receivers),
            'post_delete': len(post_delete.receivers),
        }
        
        total = sum(signal_counts.values())
        
        logger.debug(f"Signal receiver counts: {signal_counts}")
        
        if total < 15:  # Should have at least 15+ receivers
            logger.warning(
                f"⚠️  Low signal receiver count ({total}). Signal handlers may not work correctly. "
                "This typically means signal modules weren't imported in apps.py.ready()"
            )
        else:
            logger.info(f"✓ Signal receivers registered: {total} total receivers")
    
    def _verify_event_bus(self):
        """
        Verify that the event bus is properly initialized.
        
        The event bus is critical for the integration system to work.
        """
        try:
            from api.cms.INTEGRATION_SYSTEM.event_bus import EventBus
            
            if EventBus.is_initialized():
                logger.info("✓ Event bus verified as initialized")
            else:
                logger.warning("⚠️  Event bus not initialized. Check INTEGRATION_SYSTEM/event_bus.py")
        except Exception as e:
            logger.warning(f"Could not verify event bus: {e}")
    
    def _verify_adapters(self):
        """
        Verify that adapters are accessible.
        
        This is a simple check to ensure adapters can be imported,
        which indicates the adapter system is working.
        """
        try:
            from api.cms.adapters import AdapterRegistry
            
            adapters = AdapterRegistry.get_all()
            if adapters:
                logger.info(f"✓ Adapters verified: {len(adapters)} adapters registered")
            else:
                logger.warning("⚠️  No adapters registered in AdapterRegistry")
        except Exception as e:
            logger.warning(f"Could not verify adapters: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ALTERNATIVE CONFIGURATION (if using api.cms as separate app)
# ─────────────────────────────────────────────────────────────────────────────

class ApiCmsConfig(AppConfig):
    """
    API CMS Application Configuration
    
    This handles the REST API side of the CMS if api.cms is a separate app.
    """
    
    name = 'api.cms'
    verbose_name = 'CMS REST API'
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """Initialize API-specific configurations"""
        logger.info("Initializing API CMS application...")
        
        # Ensure models are loaded
        try:
            import api.cms.models_new  # noqa — register models without wildcard import
            logger.debug("✓ API models module loaded")
        except ImportError as e:
            logger.warning(f"Could not load API models: {e}")
        
        logger.info("✓ API CMS initialization complete")
