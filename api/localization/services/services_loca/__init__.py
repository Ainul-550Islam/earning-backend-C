# services/services_loca/__init__.py
"""
services_loca — High-level service facades used by middleware and views.
All services handle their own errors gracefully.
"""
from .LocalizationService import LocalizationService
from .TranslationService import TranslationService
from .LanguageDetector import LanguageDetector
from .UserPreferenceService import UserPreferenceService
from .CurrencyService import CurrencyService
from .GeoService import GeoService

__all__ = [
    'LocalizationService',
    'TranslationService',
    'LanguageDetector',
    'UserPreferenceService',
    'CurrencyService',
    'GeoService',
]
