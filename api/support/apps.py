# api/support/apps.py
from django.apps import AppConfig

class SupportConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.support'
    verbose_name = '🆘 Support Management'
    
    def ready(self):
        """Initialize support app"""
        try:
            import api.support.signals
            print("[OK] Support signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import FAQ, SupportSettings, SupportTicket
            from .admin import FAQAdmin, SupportTicketAdmin
            
            print("[LOADING] Loading support admin...")
            registered = 0
            
            # Register FAQ
            if not admin.site.is_registered(FAQ):
                admin.site.register(FAQ, FAQAdmin)
                registered += 1
                print("[OK] Registered: FAQ")
            
            # Register SupportTicket
            if not admin.site.is_registered(SupportTicket):
                admin.site.register(SupportTicket, SupportTicketAdmin)
                registered += 1
                print("[OK] Registered: SupportTicket")
            
            # Register SupportSettings
            if not admin.site.is_registered(SupportSettings):
                # Try to import SupportSettingsAdmin if exists
                try:
                    from .admin import SupportSettingsAdmin
                    admin.site.register(SupportSettings, SupportSettingsAdmin)
                except ImportError:
                    admin.site.register(SupportSettings)
                registered += 1
                print("[OK] Registered: SupportSettings")
            
            if registered > 0:
                print(f"[OK][OK][OK] {registered} support models registered from apps.py")
            else:
                print("[OK] All support models already registered")
                
        except Exception as e:
            print(f"[WARN] Support admin registration error: {e}")