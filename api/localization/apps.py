import logging
logger = logging.getLogger(__name__)

# api/localization/apps.py
from django.apps import AppConfig


class LocalizationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.localization'
    label = 'localization'
    verbose_name = '🌍 World #1 Localization'

    def ready(self):
        """Initialize localization app — signals, admin registration"""
        try:
            from .signals import (
                core_signals, translation_signals, language_signals,
                currency_signals, preference_signals, missing_signals, cache_signals
            )
            logger.info("[OK] Localization signals loaded")
        except ImportError as e:
            logger.info(f"[WARN] Localization signals: {e}")

        # Force admin registration
        try:
            from django.contrib import admin
            from .models.core import (
                Language, Country, Currency, Timezone, City,
                TranslationKey, Translation, UserLanguagePreference
            )
            from .models.translation import (
                TranslationCache, MissingTranslation, TranslationMemory,
                TranslationGlossary, TranslationVersion
            )
            from .models.geo import Region, CountryLanguage, CountryCurrency, GeoIPMapping, PhoneFormat
            from .models.currency import ExchangeRate, ExchangeRateProvider, CurrencyFormat, CurrencyConversionLog
            from .models.content import LocalizedContent, LocalizedImage, LocalizedSEO, ContentLocaleMapping, TranslationRequest
            from .models.settings import LocalizationConfig, DateTimeFormat, NumberFormat, AddressFormat
            from .models.analytics import LocalizationInsight, TranslationCoverage, LanguageUsageStat, GeoInsight
            logger.info("[OK] Localization models loaded")
        except Exception as e:
            logger.info(f"[WARN] Localization model loading: {e}")
