# api/referral/apps.py
from django.apps import AppConfig

class ReferralConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.referral'
    label = 'referral'
    verbose_name = '👥 Referral Management'
    
    def ready(self):
        """Initialize referral app when Django starts"""
        
        # 1. Import signals (if any)
        try:
            import api.referral.signals
            print("[OK] Referral signals loaded")
        except ImportError:
            print("[WARN] No signals found for referral app")
        except Exception as e:
            print(f"[WARN] Error loading referral signals: {e}")
        
        # 2. Force admin registration (safety net)
        try:
            from django.contrib import admin
            from .models import Referral, ReferralEarning, ReferralSettings
            
            print("[LOADING] Checking referral admin registration...")
            registered = 0
            
            # Register Referral if not registered
            if not admin.site.is_registered(Referral):
                try:
                    from .admin import ReferralAdmin
                    admin.site.register(Referral, ReferralAdmin)
                    registered += 1
                    print("[OK] Registered: Referral")
                except ImportError:
                    admin.site.register(Referral)
                    registered += 1
                    print("[OK] Registered: Referral (default)")
            
            # Register ReferralEarning if not registered
            if not admin.site.is_registered(ReferralEarning):
                try:
                    from .admin import ReferralEarningAdmin
                    admin.site.register(ReferralEarning, ReferralEarningAdmin)
                    registered += 1
                    print("[OK] Registered: ReferralEarning")
                except ImportError:
                    admin.site.register(ReferralEarning)
                    registered += 1
                    print("[OK] Registered: ReferralEarning (default)")
            
            # Register ReferralSettings if not registered
            if not admin.site.is_registered(ReferralSettings):
                try:
                    from .admin import ReferralSettingsAdmin
                    admin.site.register(ReferralSettings, ReferralSettingsAdmin)
                    registered += 1
                    print("[OK] Registered: ReferralSettings")
                except ImportError:
                    admin.site.register(ReferralSettings)
                    registered += 1
                    print("[OK] Registered: ReferralSettings (default)")
            
            if registered > 0:
                print(f"[OK][OK][OK] {registered} referral models registered from apps.py")
            else:
                print("[OK] All referral models already registered")
                
        except Exception as e:
            print(f"[WARN] Referral admin registration error: {e}")