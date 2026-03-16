# api/localization/services_loca/__init__.py
"""
Localization services package
"""

import logging
logger = logging.getLogger(__name__)

# Try to import services, with fallbacks
try:
    from .TranslationService import TranslationService
    from .LocalizationService import LocalizationService
    from .LanguageDetector import LanguageDetector
    from .UserPreferenceService import UserPreferenceService  # ← যোগ করুন
    
    # Create singleton instances
    translation_service = TranslationService()
    localization_service = LocalizationService()
    language_detector = LanguageDetector()
    user_preference_service = UserPreferenceService()  # ← যোগ করুন
    
    __all__ = [
        'TranslationService',
        'LocalizationService', 
        'LanguageDetector',
        'UserPreferenceService',  # ← যোগ করুন
        'translation_service',
        'localization_service',
        'language_detector',
        'user_preference_service',  # ← যোগ করুন
    ]
    
    logger.info("All localization services loaded successfully")
    
except ImportError as e:
    logger.warning(f"Could not import localization services: {e}")
    
    # Define placeholder classes
    class TranslationService:
        def __init__(self, *args, **kwargs): pass
        def translate(self, text, *args, **kwargs): return text
    
    class LocalizationService:
        def __init__(self, *args, **kwargs): pass
        def localize(self, data, *args, **kwargs): return data
    
    class LanguageDetector:
        def __init__(self, *args, **kwargs): pass
        def detect(self, text, *args, **kwargs): return 'en'
    
    class UserPreferenceService:  # ← যোগ করুন
        def __init__(self, *args, **kwargs): pass
        def get_user_preference(self, user): 
            return type('Preference', (), {'ui_language': 'en'})
        def set_user_preference(self, user, lang): 
            return True
    
    # Create placeholder instances
    translation_service = TranslationService()
    localization_service = LocalizationService()
    language_detector = LanguageDetector()
    user_preference_service = UserPreferenceService()  # ← যোগ করুন
    
    __all__ = [
        'TranslationService',
        'LocalizationService',
        'LanguageDetector',
        'UserPreferenceService',  # ← যোগ করুন
        'translation_service',
        'localization_service',
        'language_detector',
        'user_preference_service',  # ← যোগ করুন
    ]