# api/rate_limit/apps.py
from django.apps import AppConfig

class RateLimitAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.rate_limit'
    label = 'rate_limit'
    verbose_name = '⏱️ Rate Limit Management'
    
    def ready(self):
        """Initialize rate_limit app"""
        try:
            import api.rate_limit.signals
            print("[OK] Rate limit signals loaded")
        except ImportError:
            pass
        
        # Initialize integration system
        try:
            from .INTEGRATION_SYSTEM import initialize_integration_system
            if initialize_integration_system():
                print("[OK] Integration system initialized")
            else:
                print("[WARN] Integration system initialization failed")
        except ImportError:
            print("[WARN] Integration system not available")
        except Exception as e:
            print(f"[WARN] Integration system error: {e}")
        
        # Register integration signals (user creation → profile auto-create)
        try:
            from api.rate_limit.integration_service import register_integration_signals
            register_integration_signals()
        except Exception as e:
            print(f"[WARN] Integration signals error: {e}")

        # Register all app-specific rate limit action configs
        try:
            from api.rate_limit.adapters.remaining_apps import register_new_actions
            register_new_actions()
        except Exception as e:
            print(f"[WARN] register_new_actions error: {e}")

        # Admin registration handled by admin.py decorators and blocks
        # No need for manual registration in apps.py