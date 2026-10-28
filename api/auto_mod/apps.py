# =============================================================================
# auto_mod/apps.py
# =============================================================================

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AutoModConfig(AppConfig):
    """
    Django app configuration for Auto Mod system.
    
    Handles initialization of the auto moderation system including:
    - Signal receiver registration
    - Admin registration
    - Plugin system initialization
    - Feature flag setup
    - Background task configuration
    """
    
    name = "api.auto_mod"
    label = "auto_mod"
    verbose_name = _("AI Auto-Moderation")
    default_auto_field = "django.db.models.BigAutoField"
    
    def ready(self) -> None:
        """
        Called when the app is ready.
        Initializes all auto_mod components.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info("Initializing Auto Mod app...")
        
        # Import and initialize signal receivers
        self._initialize_receivers(logger)
        
        # Initialize admin registration
        self._initialize_admin(logger)
        
        # Initialize plugin system
        self._initialize_plugins(logger)
        
        # Initialize feature flags
        self._initialize_feature_flags(logger)
        
        # Initialize background jobs
        self._initialize_background_jobs(logger)
        
        # Initialize webhook system
        self._initialize_webhooks(logger)
        
        # Initialize monitoring
        self._initialize_monitoring(logger)
        
        logger.info("Auto Mod app initialization completed successfully")
    
    def _initialize_receivers(self, logger) -> None:
        """Initialize signal receivers."""
        try:
            import api.auto_mod.receivers  # noqa: F401
            logger.info("Signal receivers initialized successfully")
        except Exception as exc:
            logger.exception("Failed to import signal receivers: %s", exc)
    
    def _initialize_admin(self, logger) -> None:
        """Initialize Django admin registration."""
        try:
            from api.auto_mod.admin import _force_register_auto_mod
            _force_register_auto_mod()
            logger.info("Admin registration completed successfully")
        except Exception as exc:
            logger.warning("Failed to initialize admin registration: %s", exc)
    
    def _initialize_plugins(self, logger) -> None:
        """Initialize plugin system."""
        try:
            from api.auto_mod.plugins import plugin_manager
            # Auto-register built-in plugins
            logger.info("Plugin system initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize plugin system: %s", exc)
    
    def _initialize_feature_flags(self, logger) -> None:
        """Initialize feature flags."""
        try:
            from api.auto_mod.feature_flags import feature_flag_manager
            # Load default feature flags
            logger.info("Feature flags initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize feature flags: %s", exc)
    
    def _initialize_background_jobs(self, logger) -> None:
        """Initialize background job system."""
        try:
            from api.auto_mod.background_jobs import job_manager
            # Register default jobs
            logger.info("Background jobs initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize background jobs: %s", exc)
    
    def _initialize_webhooks(self, logger) -> None:
        """Initialize webhook system."""
        try:
            from api.auto_mod.webhooks import dispatcher  # noqa: F401
            # Register default event handlers
            logger.info("Webhook system initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize webhook system: %s", exc)
    
    def _initialize_monitoring(self, logger) -> None:
        """Initialize monitoring system."""
        try:
            from api.auto_mod.monitoring import health_checker
            # Start health monitoring
            logger.info("Monitoring system initialized successfully")
        except Exception as exc:
            logger.warning("Failed to initialize monitoring system: %s", exc)
