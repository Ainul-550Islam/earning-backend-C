# api/localization/apps.py
from django.apps import AppConfig

class LocalizationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.localization'
    label = 'localization'
    verbose_name = '🌍 Localization Management'
    
    def ready(self):
        """Initialize localization app"""
        try:
            import api.localization.signals
            print("[OK] Localization signals loaded")
        except ImportError:
            pass
        
        # Force admin registration
        try:
            from django.contrib import admin
            from .models import (
                City, Country, Currency, Language, MissingTranslation,
                Timezone, Translation, TranslationCache, TranslationKey,
                UserLanguagePreference
            )
            
            print("[LOADING] Checking localization admin registration...")
            
            try:
                from .admin import (
                    CountryAdmin, CityAdmin, CurrencyAdmin, LanguageAdmin,
                    TimezoneAdmin, TranslationKeyAdmin, TranslationAdmin,
                    TranslationCacheAdmin, MissingTranslationAdmin,
                    UserLanguagePreferenceAdmin
                )
                
                models_to_register = [
                    (Country, CountryAdmin),
                    (City, CityAdmin),
                    (Currency, CurrencyAdmin),
                    (Language, LanguageAdmin),
                    (Timezone, TimezoneAdmin),
                    (TranslationKey, TranslationKeyAdmin),
                    (Translation, TranslationAdmin),
                    (TranslationCache, TranslationCacheAdmin),
                    (MissingTranslation, MissingTranslationAdmin),
                    (UserLanguagePreference, UserLanguagePreferenceAdmin),
                ]
                
                registered = 0
                for model, admin_class in models_to_register:
                    if not admin.site.is_registered(model):
                        admin.site.register(model, admin_class)
                        registered += 1
                        print(f"[OK] Registered: {model.__name__}")
                
                if registered > 0:
                    print(f"[OK][OK][OK] {registered} localization models registered from apps.py")
                else:
                    print("[OK] All localization models already registered")
                    
            except ImportError as e:
                print(f"[WARN] Could not import admin classes: {e}")
                
        except Exception as e:
            print(f"[WARN] Localization admin registration error: {e}")