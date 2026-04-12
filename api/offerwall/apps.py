# api/offerwall/apps.py
from django.apps import AppConfig

class OfferwallConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.offerwall'
    label = 'offerwall'
    verbose_name = '🎯 Offerwall Management'
    
    def ready(self):
        """Initialize offerwall app"""
        try:
            import api.offerwall.signals
            print("[OK] Offerwall signals loaded")
        except ImportError:
            pass
        
        # Force admin registration with duplicate check
        try:
            from django.contrib import admin
            from .models import Offer, OfferCategory, OfferClick, OfferConversion, OfferProvider, OfferWall
            
            print("[LOADING] Checking offerwall admin registration...")
            
            try:
                from .admin import (
                    OfferProviderAdmin, OfferCategoryAdmin, OfferAdmin,
                    OfferClickAdmin, OfferConversionAdmin, OfferWallAdmin
                )
                
                models_to_register = {
                    OfferCategory: OfferCategoryAdmin,
                    OfferProvider: OfferProviderAdmin,
                    Offer: OfferAdmin,
                    OfferClick: OfferClickAdmin,
                    OfferConversion: OfferConversionAdmin,
                    OfferWall: OfferWallAdmin,
                }
                
                registered = 0
                for model, admin_class in models_to_register.items():
                    if not admin.site.is_registered(model):
                        try:
                            admin.site.register(model, admin_class)
                            registered += 1
                            print(f"[OK] Registered: {model.__name__} from apps.py")
                        except Exception as e:
                            print(f"[WARN] Could not register {model.__name__}: {e}")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} offerwall models registered from apps.py")
                else:
                    print("[OK] All offerwall models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                
        except Exception as e:
            print(f"[WARN] Offerwall admin registration error: {e}")
        try:
            from api.offerwall.admin import _force_register_offerwall
            _force_register_offerwall()
        except Exception as e:
            pass
