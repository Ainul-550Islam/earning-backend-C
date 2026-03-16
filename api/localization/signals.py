# signals.py
from django.db.models.signals import (
    pre_save, post_save, pre_delete, post_delete,
    m2m_changed, class_prepared
)
from django.dispatch import receiver
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.db import transaction
import logging
from typing import Type, Any, Dict, Optional
from .models import (
    Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, TranslationCache,
    UserLanguagePreference, MissingTranslation
)

logger = logging.getLogger(__name__)

# ======================== Cache Keys ========================
CACHE_KEYS = {
    'languages': 'languages_list_v1',
    'countries': 'countries_list_v1',
    'currencies': 'currencies_list_v1',
    'timezones': 'timezones_list_v1',
}


# ======================== Base Signal Handler ========================

class BaseSignalHandler:
    """Base class for signal handlers with common functionality"""
    
    @staticmethod
    def log_signal(signal_name: str, instance: Any, action: str = None):
        """Log signal execution"""
        logger.debug(
            f"Signal {signal_name} triggered for {instance.__class__.__name__} "
            f"ID: {getattr(instance, 'id', 'None')} Action: {action or 'N/A'}"
        )
    
    @staticmethod
    def clear_model_cache(model_name: str, instance_id: Any = None):
        """Clear cache for specific model"""
        try:
            if model_name in CACHE_KEYS:
                cache.delete(CACHE_KEYS[model_name])
                logger.info(f"Cleared cache for {model_name}")
            
            # Clear instance-specific cache if ID provided
            if instance_id:
                cache.delete(f"{model_name}:{instance_id}")
                
        except Exception as e:
            logger.error(f"Failed to clear cache for {model_name}: {e}")
    
    @staticmethod
    def safe_execute(func, *args, **kwargs):
        """Safely execute a function with error handling"""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in signal handler: {e}", exc_info=True)
            return None


# ======================== Language Signals ========================

@receiver(pre_save, sender=Language)
def language_pre_save(sender: Type[Language], instance: Language, **kwargs):
    """Handle language pre-save operations"""
    BaseSignalHandler.log_signal('pre_save', instance)
    
    def _pre_save():
        # If this language is being set as default, ensure no other default exists
        if instance.is_default:
            # This will be handled in the model's save method
            # But we log it here for debugging
            logger.info(f"Language {instance.code} is being set as default")
        
        # Validate language code format
        if instance.code and not instance.code.islower():
            logger.warning(f"Language code {instance.code} should be lowercase")
    
    BaseSignalHandler.safe_execute(_pre_save)


@receiver(post_save, sender=Language)
def language_post_save(sender: Type[Language], instance: Language, created: bool, **kwargs):
    """Handle language post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear cache
        BaseSignalHandler.clear_model_cache('languages', instance.code)
        
        # Clear translation cache for this language
        TranslationCache.objects.filter(language_code=instance.code).delete()
        
        if created:
            logger.info(f"New language created: {instance.code} - {instance.name}")
        else:
            logger.info(f"Language updated: {instance.code}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(pre_delete, sender=Language)
def language_pre_delete(sender: Type[Language], instance: Language, **kwargs):
    """Handle language pre-delete operations"""
    BaseSignalHandler.log_signal('pre_delete', instance)
    
    def _pre_delete():
        # Check if this is the default language
        if instance.is_default:
            logger.warning(f"Deleting default language: {instance.code}")
        
        # Check if there are translations using this language
        translation_count = Translation.objects.filter(language=instance).count()
        if translation_count > 0:
            logger.warning(
                f"Deleting language {instance.code} which has "
                f"{translation_count} translations"
            )
    
    BaseSignalHandler.safe_execute(_pre_delete)


@receiver(post_delete, sender=Language)
def language_post_delete(sender: Type[Language], instance: Language, **kwargs):
    """Handle language post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear cache
        BaseSignalHandler.clear_model_cache('languages')
        
        # Clear translation cache
        TranslationCache.objects.filter(language_code=instance.code).delete()
        
        # If this was the default language, set a new default
        if instance.is_default:
            new_default = Language.objects.filter(is_active=True).first()
            if new_default:
                new_default.is_default = True
                new_default.save()
                logger.info(f"Set {new_default.code} as new default language")
        
        logger.info(f"Language deleted: {instance.code}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== Country Signals ========================

@receiver(post_save, sender=Country)
def country_post_save(sender: Type[Country], instance: Country, created: bool, **kwargs):
    """Handle country post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear cache
        BaseSignalHandler.clear_model_cache('countries', instance.code)
        
        # Clear related city cache
        cache.delete_pattern(f"cities_list_{instance.code}_*")
        
        if created:
            logger.info(f"New country created: {instance.code} - {instance.name}")
        else:
            logger.info(f"Country updated: {instance.code}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(pre_delete, sender=Country)
def country_pre_delete(sender: Type[Country], instance: Country, **kwargs):
    """Handle country pre-delete operations"""
    BaseSignalHandler.log_signal('pre_delete', instance)
    
    def _pre_delete():
        # Check for cities
        city_count = City.objects.filter(country=instance).count()
        if city_count > 0:
            logger.warning(
                f"Deleting country {instance.code} which has {city_count} cities"
            )
    
    BaseSignalHandler.safe_execute(_pre_delete)


@receiver(post_delete, sender=Country)
def country_post_delete(sender: Type[Country], instance: Country, **kwargs):
    """Handle country post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear cache
        BaseSignalHandler.clear_model_cache('countries')
        logger.info(f"Country deleted: {instance.code}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== Currency Signals ========================

@receiver(pre_save, sender=Currency)
def currency_pre_save(sender: Type[Currency], instance: Currency, **kwargs):
    """Handle currency pre-save operations"""
    BaseSignalHandler.log_signal('pre_save', instance)
    
    def _pre_save():
        # Track exchange rate changes
        if instance.pk:
            try:
                old = Currency.objects.get(pk=instance.pk)
                if old.exchange_rate != instance.exchange_rate:
                    logger.info(
                        f"Exchange rate changed for {instance.code}: "
                        f"{old.exchange_rate} -> {instance.exchange_rate}"
                    )
                    instance.exchange_rate_updated_at = timezone.now()
            except Currency.DoesNotExist:
                pass
    
    BaseSignalHandler.safe_execute(_pre_save)


@receiver(post_save, sender=Currency)
def currency_post_save(sender: Type[Currency], instance: Currency, created: bool, **kwargs):
    """Handle currency post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear cache
        BaseSignalHandler.clear_model_cache('currencies', instance.code)
        
        # Clear exchange rate cache
        cache.delete_pattern(f"exchange_rate:*:{instance.code}")
        cache.delete_pattern(f"exchange_rate:{instance.code}:*")
        
        if created:
            logger.info(f"New currency created: {instance.code}")
        elif instance.is_default:
            logger.info(f"Default currency changed to: {instance.code}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(pre_delete, sender=Currency)
def currency_pre_delete(sender: Type[Currency], instance: Currency, **kwargs):
    """Handle currency pre-delete operations"""
    BaseSignalHandler.log_signal('pre_delete', instance)
    
    def _pre_delete():
        # Check if this is the default currency
        if instance.is_default:
            logger.warning(f"Deleting default currency: {instance.code}")
    
    BaseSignalHandler.safe_execute(_pre_delete)


@receiver(post_delete, sender=Currency)
def currency_post_delete(sender: Type[Currency], instance: Currency, **kwargs):
    """Handle currency post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear cache
        BaseSignalHandler.clear_model_cache('currencies')
        logger.info(f"Currency deleted: {instance.code}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== Timezone Signals ========================

@receiver(post_save, sender=Timezone)
def timezone_post_save(sender: Type[Timezone], instance: Timezone, created: bool, **kwargs):
    """Handle timezone post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear cache
        BaseSignalHandler.clear_model_cache('timezones')
        
        if created:
            logger.info(f"New timezone created: {instance.name}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(post_delete, sender=Timezone)
def timezone_post_delete(sender: Type[Timezone], instance: Timezone, **kwargs):
    """Handle timezone post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear cache
        BaseSignalHandler.clear_model_cache('timezones')
        logger.info(f"Timezone deleted: {instance.name}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== City Signals ========================

@receiver(post_save, sender=City)
def city_post_save(sender: Type[City], instance: City, created: bool, **kwargs):
    """Handle city post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear city cache for this country
        if instance.country:
            cache.delete_pattern(f"cities_list_{instance.country.code}_*")
        
        if created:
            logger.info(f"New city created: {instance.name} in {instance.country.code if instance.country else 'Unknown'}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(post_delete, sender=City)
def city_post_delete(sender: Type[City], instance: City, **kwargs):
    """Handle city post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear city cache for this country
        if instance.country:
            cache.delete_pattern(f"cities_list_{instance.country.code}_*")
        
        logger.info(f"City deleted: {instance.name}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== Translation Key Signals ========================

@receiver(post_save, sender=TranslationKey)
def translation_key_post_save(sender: Type[TranslationKey], instance: TranslationKey, created: bool, **kwargs):
    """Handle translation key post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear all translation cache since keys changed
        TranslationCache.objects.all().delete()
        cache.delete_pattern("translation:*")
        
        if created:
            logger.info(f"New translation key created: {instance.key}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(pre_delete, sender=TranslationKey)
def translation_key_pre_delete(sender: Type[TranslationKey], instance: TranslationKey, **kwargs):
    """Handle translation key pre-delete operations"""
    BaseSignalHandler.log_signal('pre_delete', instance)
    
    def _pre_delete():
        # Check for translations
        translation_count = Translation.objects.filter(key=instance).count()
        if translation_count > 0:
            logger.warning(
                f"Deleting translation key {instance.key} which has "
                f"{translation_count} translations"
            )
    
    BaseSignalHandler.safe_execute(_pre_delete)


@receiver(post_delete, sender=TranslationKey)
def translation_key_post_delete(sender: Type[TranslationKey], instance: TranslationKey, **kwargs):
    """Handle translation key post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear all translation cache
        TranslationCache.objects.all().delete()
        cache.delete_pattern("translation:*")
        logger.info(f"Translation key deleted: {instance.key}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== Translation Signals ========================

@receiver(post_save, sender=Translation)
def translation_post_save(sender: Type[Translation], instance: Translation, created: bool, **kwargs):
    """Handle translation post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear cache for this language
        if instance.language:
            cache.delete_pattern(f"translation:{instance.language.code}:*")
            cache.delete_pattern(f"translations_api_{instance.language.code}")
            
            # Also clear TranslationCache
            TranslationCache.objects.filter(
                language_code=instance.language.code
            ).delete()
        
        if created:
            logger.info(f"New translation created: {instance.key.key} in {instance.language.code if instance.language else 'Unknown'}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(post_delete, sender=Translation)
def translation_post_delete(sender: Type[Translation], instance: Translation, **kwargs):
    """Handle translation post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear cache for this language
        if instance.language:
            cache.delete_pattern(f"translation:{instance.language.code}:*")
            cache.delete_pattern(f"translations_api_{instance.language.code}")
            
            # Also clear TranslationCache
            TranslationCache.objects.filter(
                language_code=instance.language.code
            ).delete()
        
        logger.info(f"Translation deleted: {instance.key.key} in {instance.language.code if instance.language else 'Unknown'}")
    
    BaseSignalHandler.safe_execute(_post_delete)


# ======================== User Preference Signals ========================

@receiver(post_save, sender=UserLanguagePreference)
def user_preference_post_save(sender: Type[UserLanguagePreference], instance: UserLanguagePreference, created: bool, **kwargs):
    """Handle user preference post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        # Clear user preference cache
        if instance.user_id:
            cache.delete(f"user_pref:{instance.user_id}")
        
        if created:
            logger.info(f"New language preference created for user {instance.user_id}")
    
    BaseSignalHandler.safe_execute(_post_save)


@receiver(post_delete, sender=UserLanguagePreference)
def user_preference_post_delete(sender: Type[UserLanguagePreference], instance: UserLanguagePreference, **kwargs):
    """Handle user preference post-delete operations"""
    BaseSignalHandler.log_signal('post_delete', instance)
    
    def _post_delete():
        # Clear user preference cache
        if instance.user_id:
            cache.delete(f"user_pref:{instance.user_id}")
        
        logger.info(f"Language preference deleted for user {instance.user_id}")
    
    BaseSignalHandler.safe_execute(_post_delete)


@receiver(m2m_changed, sender=UserLanguagePreference.preferred_languages.through)
def user_preference_languages_changed(sender, instance: UserLanguagePreference, action: str, **kwargs):
    """Handle many-to-many changes for preferred languages"""
    BaseSignalHandler.log_signal('m2m_changed', instance, action)
    
    def _m2m_changed():
        if action in ['post_add', 'post_remove', 'post_clear']:
            # Clear user preference cache
            if instance.user_id:
                cache.delete(f"user_pref:{instance.user_id}")
            
            logger.info(f"Preferred languages changed for user {instance.user_id}: {action}")
    
    BaseSignalHandler.safe_execute(_m2m_changed)


# ======================== Missing Translation Signals ========================

@receiver(post_save, sender=MissingTranslation)
def missing_translation_post_save(sender: Type[MissingTranslation], instance: MissingTranslation, created: bool, **kwargs):
    """Handle missing translation post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        if created:
            # Log warning for missing translation
            logger.warning(
                f"Missing translation logged: '{instance.key}' "
                f"in {instance.language.code if instance.language else 'Unknown'}"
            )
            
            # If too many missing translations, trigger alert
            recent_count = MissingTranslation.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(hours=1)
            ).count()
            
            if recent_count > 100:  # Threshold
                logger.error(
                    f"High number of missing translations detected: {recent_count} in last hour"
                )
                # TODO: Send alert to admin
    
    BaseSignalHandler.safe_execute(_post_save)


# ======================== Translation Cache Signals ========================

@receiver(post_save, sender=TranslationCache)
def translation_cache_post_save(sender: Type[TranslationCache], instance: TranslationCache, created: bool, **kwargs):
    """Handle translation cache post-save operations"""
    BaseSignalHandler.log_signal('post_save', instance, 'created' if created else 'updated')
    
    def _post_save():
        if created:
            logger.debug(f"Translation cache created for {instance.language_code}:{instance.cache_key}")
    
    BaseSignalHandler.safe_execute(_post_save)


# ======================== Bulk Operation Signals ========================

class BulkOperationSignal:
    """Custom signal for bulk operations"""
    
    def __init__(self):
        self.handlers = []
    
    def connect(self, handler):
        self.handlers.append(handler)
    
    def send(self, sender, **kwargs):
        results = []
        for handler in self.handlers:
            try:
                result = handler(sender, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in bulk operation signal handler: {e}")
        return results


# Create custom signals
bulk_translation_import = BulkOperationSignal()
bulk_currency_update = BulkOperationSignal()


@receiver(bulk_translation_import)
def handle_bulk_translation_import(sender, **kwargs):
    """Handle bulk translation import"""
    try:
        language_code = kwargs.get('language_code')
        count = kwargs.get('count', 0)
        
        logger.info(f"Bulk import completed for {language_code}: {count} translations")
        
        # Clear cache
        if language_code:
            TranslationCache.objects.filter(language_code=language_code).delete()
            cache.delete_pattern(f"translation:{language_code}:*")
        
    except Exception as e:
        logger.error(f"Error handling bulk translation import: {e}")


@receiver(bulk_currency_update)
def handle_bulk_currency_update(sender, **kwargs):
    """Handle bulk currency update"""
    try:
        count = kwargs.get('count', 0)
        
        logger.info(f"Bulk currency update completed: {count} currencies updated")
        
        # Clear all currency cache
        cache.delete_pattern("exchange_rate:*")
        BaseSignalHandler.clear_model_cache('currencies')
        
    except Exception as e:
        logger.error(f"Error handling bulk currency update: {e}")


# ======================== Transaction Signals ========================

@receiver(pre_save)
@receiver(post_save)
@receiver(pre_delete)
@receiver(post_delete)
def log_all_signals(sender, **kwargs):
    """Debug signal to log all signals (disabled by default)"""
    # Enable only in debug mode
    if settings.DEBUG:
        signal = kwargs.get('signal')
        if signal and hasattr(sender, '__name__'):
            logger.debug(
                f"Signal {signal} received for {sender.__name__}"
            )


# ======================== App Ready Signal ========================

def ready():
    """Called when the app is ready"""
    logger.info("Localization signals registered")


# ======================== Signal Disconnect Helpers ========================

def disconnect_all_signals():
    """Disconnect all signals (useful for testing)"""
    signals_to_disconnect = [
        (language_pre_save, Language, pre_save),
        (language_post_save, Language, post_save),
        (language_pre_delete, Language, pre_delete),
        (language_post_delete, Language, post_delete),
        (country_post_save, Country, post_save),
        (country_pre_delete, Country, pre_delete),
        (country_post_delete, Country, post_delete),
        (currency_pre_save, Currency, pre_save),
        (currency_post_save, Currency, post_save),
        (currency_pre_delete, Currency, pre_delete),
        (currency_post_delete, Currency, post_delete),
        (timezone_post_save, Timezone, post_save),
        (timezone_post_delete, Timezone, post_delete),
        (city_post_save, City, post_save),
        (city_post_delete, City, post_delete),
        (translation_key_post_save, TranslationKey, post_save),
        (translation_key_pre_delete, TranslationKey, pre_delete),
        (translation_key_post_delete, TranslationKey, post_delete),
        (translation_post_save, Translation, post_save),
        (translation_post_delete, Translation, post_delete),
        (user_preference_post_save, UserLanguagePreference, post_save),
        (user_preference_post_delete, UserLanguagePreference, post_delete),
        (user_preference_languages_changed, UserLanguagePreference, m2m_changed),
        (missing_translation_post_save, MissingTranslation, post_save),
        (translation_cache_post_save, TranslationCache, post_save),
    ]
    
    for handler, sender, signal in signals_to_disconnect:
        try:
            signal.disconnect(handler, sender=sender)
            logger.debug(f"Disconnected {handler.__name__} from {sender.__name__}")
        except Exception as e:
            logger.error(f"Error disconnecting signal: {e}")


def reconnect_all_signals():
    """Reconnect all signals"""
    # This function would need to re-import all the decorated functions
    # For testing purposes, you can reload the module
    import importlib
    import sys
    module_name = __name__
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
    logger.info("All signals reconnected")