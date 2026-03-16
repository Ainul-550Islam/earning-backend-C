# api/rate_limit/apps.py
from django.apps import AppConfig

class RateLimitConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.rate_limit'
    label = 'rate_limit'
    verbose_name = '⏱️ Rate Limit Management'
    
    def ready(self):
        """Initialize rate_limit app"""
        import api.rate_limit.signals
        try:
            import api.rate_limit.signals
            print("[OK] Rate limit signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import RateLimitConfig, RateLimitLog, UserRateLimitProfile
            
            print("[LOADING] Checking rate_limit admin registration...")
            registered = 0
            
            # Register RateLimitConfig
            if not admin.site.is_registered(RateLimitConfig):
                try:
                    from .admin import RateLimitConfigAdmin
                    admin.site.register(RateLimitConfig, RateLimitConfigAdmin)
                    registered += 1
                    print("[OK] Registered: RateLimitConfig")
                except ImportError:
                    admin.site.register(RateLimitConfig)
                    registered += 1
                    print("[OK] Registered: RateLimitConfig (default)")
            
            # Register RateLimitLog
            if not admin.site.is_registered(RateLimitLog):
                try:
                    from .admin import RateLimitLogAdmin
                    admin.site.register(RateLimitLog, RateLimitLogAdmin)
                    registered += 1
                    print("[OK] Registered: RateLimitLog")
                except ImportError:
                    admin.site.register(RateLimitLog)
                    registered += 1
                    print("[OK] Registered: RateLimitLog (default)")
            
            # Register UserRateLimitProfile
            if not admin.site.is_registered(UserRateLimitProfile):
                try:
                    from .admin import UserRateLimitProfileAdmin
                    admin.site.register(UserRateLimitProfile, UserRateLimitProfileAdmin)
                    registered += 1
                    print("[OK] Registered: UserRateLimitProfile")
                except ImportError:
                    admin.site.register(UserRateLimitProfile)
                    registered += 1
                    print("[OK] Registered: UserRateLimitProfile (default)")
            
            if registered > 0:
                print(f"[OK][OK][OK] {registered} rate_limit models registered from apps.py")
            else:
                print("[OK] All rate_limit models already registered")
                
        except Exception as e:
            print(f"[WARN] Rate limit admin registration error: {e}")