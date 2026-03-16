# api/djoyalty/apps.py
from django.apps import AppConfig

class DjoyaltyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.djoyalty'
    label = 'djoyalty'
    verbose_name = '🎮 Djoyalty Management'
    
    def ready(self):
        """Initialize djoyalty app"""
        # Import signals
        try:
            import api.djoyalty.signals
            print("[OK] Djoyalty signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import Customer, Txn, Event
            
            print("[LOADING] Checking djoyalty admin registration...")
            
            # Try to import admin classes
            try:
                from .admin import CustomerAdmin, TxnAdmin, EventAdmin
                
                models_to_register = [
                    (Customer, CustomerAdmin),
                    (Txn, TxnAdmin),
                    (Event, EventAdmin),
                ]
                
                registered = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model, admin_class)
                            registered += 1
                            print(f"[OK] Registered: {model.__name__} from apps.py")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} djoyalty models registered from apps.py")
                else:
                    print("[OK] All djoyalty models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                # Fallback: register without custom admin
                for model in [Customer, Txn, Event]:
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model)
                            print(f"[OK] Registered: {model.__name__} (default)")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
        except Exception as e:
            print(f"[WARN] Djoyalty admin registration error: {e}")