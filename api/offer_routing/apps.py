"""
Django App Configuration for Offer Routing System
"""

from django.apps import AppConfig


class OfferRoutingConfig(AppConfig):
    """Configuration for the offer routing application."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offer_routing'
    verbose_name = 'Offer Routing'
    
    def ready(self):
        """Initialize app when Django starts."""
        # Import signal handlers
        try:
            from . import signals
            from .services.core import RoutingCacheService
            # Warm up routing cache
            RoutingCacheService.warmup_common_routes()
        except ImportError:
            # Signals or services might not be ready yet
            pass
        
        # Register custom exception handler
        from django.conf import settings
        if 'api.offer_routing.exceptions' not in settings.INSTALLED_APPS:
            from .exceptions import custom_exception_handler
            settings.REST_FRAMEWORK['EXCEPTION_HANDLER'] = 'api.offer_routing.exceptions.custom_exception_handler'
