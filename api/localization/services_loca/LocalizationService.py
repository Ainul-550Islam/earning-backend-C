import json
import os
from django.conf import settings
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import logging
from django.core.cache import cache
from ..models import Translation, Language, TranslationKey, MissingTranslation

from ..models import (
    Language, Translation, TranslationKey, 
    TranslationCache, MissingTranslation
)

logger = logging.getLogger(__name__)


class LocalizationService:
    """
    Main service for localization management
    Handles translation loading, caching, and serving
    """
    
    def __init__(self):
        self.cache_timeout = getattr(settings, 'LOCALIZATION_CACHE_TIMEOUT', 3600)
        self.fallback_language = getattr(settings, 'FALLBACK_LANGUAGE', 'en')
        self.default_namespace = 'default'
    
    def get_translation(
        self, 
        key: str, 
        language_code: str = None, 
        **kwargs
    ) -> str:
        """
        Get translation for a key in specified language
        
        Args:
            key: Translation key
            language_code: Target language code (uses current language if None)
            **kwargs: Format arguments for the translation
        
        Returns:
            Translated string or key if not found
        """
        if not language_code:
            from django.utils import translation
            language_code = translation.get_language()
        
        # Try to get from cache first
        cache_key = self._get_cache_key(language_code, key)
        cached_value = cache.get(cache_key)
        
        if cached_value is not None:
            return self._format_translation(cached_value, **kwargs)
        
        # Get from database
        translation = self._get_translation_from_db(key, language_code)
        
        if translation:
            # Cache the result
            cache.set(cache_key, translation, self.cache_timeout)
            return self._format_translation(translation, **kwargs)
        
        # Try fallback language
        if language_code != self.fallback_language:
            fallback_translation = self._get_translation_from_db(key, self.fallback_language)
            if fallback_translation:
                # Cache fallback result
                cache.set(cache_key, fallback_translation, self.cache_timeout)
                
                # Log missing translation
                self._log_missing_translation(key, language_code)
                
                return self._format_translation(fallback_translation, **kwargs)
        
        # Return key as last resort
        self._log_missing_translation(key, language_code)
        return self._format_translation(key, **kwargs)
    
    def get_all_translations(
        self, 
        language_code: str, 
        namespace: str = 'default'
    ) -> Dict[str, str]:
        """
        Get all translations for a language
        
        Args:
            language_code: Target language code
            namespace: Translation namespace
        
        Returns:
            Dictionary of key-value translations
        """
        # Try to get from cache first
        cache_key = f"translations:{namespace}:{language_code}"
        cached_translations = cache.get(cache_key)
        
        if cached_translations is not None:
            return cached_translations
        
        # Check database cache table
        db_cache = TranslationCache.objects.filter(
            language_code=language_code,
            cache_key=cache_key,
            expires_at__gt=datetime.now()
        ).first()
        
        if db_cache:
            cache.set(cache_key, db_cache.cache_data, self.cache_timeout)
            db_cache.hits += 1
            db_cache.save()
            return db_cache.cache_data
        
        # Load translations
        translations = self._load_translations(language_code, namespace)
        
        # Cache in Redis
        cache.set(cache_key, translations, self.cache_timeout)
        
        # Store in database cache
        expires_at = datetime.now() + timedelta(seconds=self.cache_timeout)
        TranslationCache.objects.update_or_create(
            language_code=language_code,
            cache_key=cache_key,
            defaults={
                'cache_data': translations,
                'expires_at': expires_at,
                'hits': 1
            }
        )
        
        return translations
    
    def get_translations_batch(
        self, 
        keys: List[str], 
        language_code: str = None
    ) -> Dict[str, str]:
        """
        Get multiple translations at once
        
        Args:
            keys: List of translation keys
            language_code: Target language code
        
        Returns:
            Dictionary of key-value translations
        """
        if not language_code:
            from django.utils import translation
            language_code = translation.get_language()
        
        results = {}
        missing_keys = []
        
        # Try to get from cache first
        for key in keys:
            cache_key = self._get_cache_key(language_code, key)
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                results[key] = cached_value
            else:
                missing_keys.append(key)
        
        # Get missing keys from database
        if missing_keys:
            db_translations = self._get_translations_from_db_batch(missing_keys, language_code)
            results.update(db_translations)
            
            # Cache the new translations
            for key, value in db_translations.items():
                cache_key = self._get_cache_key(language_code, key)
                cache.set(cache_key, value, self.cache_timeout)
            
            # Check for still missing keys
            for key in missing_keys:
                if key not in results:
                    # Try fallback language
                    fallback_value = self._get_translation_from_db(key, self.fallback_language)
                    if fallback_value:
                        results[key] = fallback_value
                        
                        # Log missing translation
                        self._log_missing_translation(key, language_code)
                        
                        # Cache fallback
                        cache_key = self._get_cache_key(language_code, key)
                        cache.set(cache_key, fallback_value, self.cache_timeout)
                    else:
                        results[key] = key
                        self._log_missing_translation(key, language_code)
        
        return results
    
    def set_translation(
        self, 
        key: str, 
        value: str, 
        language_code: str,
        is_approved: bool = True,
        source: str = 'manual'
    ) -> bool:
        """
        Set or update a translation
        
        Args:
            key: Translation key
            value: Translation value
            language_code: Language code
            is_approved: Whether translation is approved
            source: Source of translation
        
        Returns:
            Success status
        """
        try:
            # Get or create translation key
            key_obj, created = TranslationKey.objects.get_or_create(key=key)
            
            # Get language
            try:
                language = Language.objects.get(code=language_code, is_active=True)
            except Language.DoesNotExist:
                logger.error(f"Language not found: {language_code}")
                return False
            
            # Create or update translation
            translation, created = Translation.objects.update_or_create(
                key=key_obj,
                language=language,
                defaults={
                    'value': value,
                    'is_approved': is_approved,
                    'source': source
                }
            )
            
            # Clear cache for this language
            self._clear_language_cache(language_code)
            
            # Clear database cache
            TranslationCache.objects.filter(language_code=language_code).delete()
            
            # Update missing translations if any
            MissingTranslation.objects.filter(
                key=key,
                language=language,
                resolved=False
            ).update(resolved=True, resolved_at=datetime.now())
            
            logger.info(f"Translation set: {key} -> {value} ({language_code})")
            return True
            
        except Exception as e:
            logger.error(f"Error setting translation: {e}")
            return False
    
    def set_translations_batch(
        self, 
        translations: Dict[str, str], 
        language_code: str,
        is_approved: bool = True,
        source: str = 'manual'
    ) -> Dict[str, bool]:
        """
        Set multiple translations at once
        
        Args:
            translations: Dictionary of key-value translations
            language_code: Language code
            is_approved: Whether translations are approved
            source: Source of translations
        
        Returns:
            Dictionary with success status for each key
        """
        results = {}
        
        try:
            # Get language
            language = Language.objects.get(code=language_code, is_active=True)
            
            for key, value in translations.items():
                try:
                    # Get or create translation key
                    key_obj, created = TranslationKey.objects.get_or_create(key=key)
                    
                    # Create or update translation
                    translation, created = Translation.objects.update_or_create(
                        key=key_obj,
                        language=language,
                        defaults={
                            'value': value,
                            'is_approved': is_approved,
                            'source': source
                        }
                    )
                    
                    results[key] = True
                    
                except Exception as e:
                    logger.error(f"Error setting translation for key {key}: {e}")
                    results[key] = False
            
            # Clear cache
            self._clear_language_cache(language_code)
            TranslationCache.objects.filter(language_code=language_code).delete()
            
            return results
            
        except Language.DoesNotExist:
            logger.error(f"Language not found: {language_code}")
            return {key: False for key in translations.keys()}
    
    def get_localization_statistics(self) -> Dict[str, Any]:
        """
        Get localization statistics
        """
        # Try to get from cache
        cache_key = 'localization_statistics'
        cached_stats = cache.get(cache_key)
        
        if cached_stats:
            return cached_stats
        
        # Calculate statistics
        total_keys = TranslationKey.objects.count()
        languages = Language.objects.filter(is_active=True)
        
        language_stats = []
        for lang in languages:
            translated_count = Translation.objects.filter(
                language=lang, 
                is_approved=True
            ).count()
            
            coverage = (translated_count / total_keys * 100) if total_keys > 0 else 0
            
            language_stats.append({
                'code': lang.code,
                'name': lang.name,
                'total_translations': translated_count,
                'coverage_percentage': round(coverage, 2),
                'is_default': lang.is_default,
                'is_rtl': lang.is_rtl
            })
        
        # Sort by coverage
        language_stats.sort(key=lambda x: x['coverage_percentage'], reverse=True)
        
        # Overall statistics
        overall_coverage = sum(stat['coverage_percentage'] for stat in language_stats)
        overall_coverage = overall_coverage / len(language_stats) if language_stats else 0
        
        stats = {
            'total_languages': len(language_stats),
            'total_translation_keys': total_keys,
            'overall_coverage': round(overall_coverage, 2),
            'languages': language_stats,
            'missing_translations': MissingTranslation.objects.filter(resolved=False).count(),
            'cache_hit_rate': self._get_cache_hit_rate(),
            'last_updated': datetime.now().isoformat()
        }
        
        # Cache statistics for 5 minutes
        cache.set(cache_key, stats, 300)
        
        return stats
    
    def export_translations(
        self, 
        language_code: str, 
        format: str = 'json'
    ) -> Any:
        """
        Export translations for a language
        
        Args:
            language_code: Language code
            format: Export format (json, csv, po)
        
        Returns:
            Exported data in specified format
        """
        translations = self.get_all_translations(language_code)
        
        if format == 'json':
            return json.dumps(translations, ensure_ascii=False, indent=2)
        
        elif format == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['key', 'value'])
            
            for key, value in translations.items():
                writer.writerow([key, value])
            
            return output.getvalue()
        
        elif format == 'po':
            # Generate PO file format
            po_content = f'msgid ""\nmsgstr ""\n"Language: {language_code}\\n"\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'
            
            for key, value in translations.items():
                po_content += f'msgid "{key}"\n'
                po_content += f'msgstr "{value}"\n\n'
            
            return po_content
        
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def import_translations(
        self, 
        language_code: str, 
        data: Dict[str, str],
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Import translations for a language
        
        Args:
            language_code: Language code
            data: Dictionary of key-value translations
            overwrite: Whether to overwrite existing translations
        
        Returns:
            Import results
        """
        results = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
        
        try:
            language = Language.objects.get(code=language_code, is_active=True)
        except Language.DoesNotExist:
            results['errors'].append(f"Language not found: {language_code}")
            return results
        
        for key, value in data.items():
            try:
                # Get or create translation key
                key_obj, created_key = TranslationKey.objects.get_or_create(key=key)
                
                # Check if translation exists
                existing = Translation.objects.filter(
                    key=key_obj,
                    language=language
                ).first()
                
                if existing:
                    if overwrite:
                        existing.value = value
                        existing.is_approved = True
                        existing.source = 'import'
                        existing.save()
                        results['updated'] += 1
                    else:
                        results['skipped'] += 1
                else:
                    Translation.objects.create(
                        key=key_obj,
                        language=language,
                        value=value,
                        is_approved=True,
                        source='import'
                    )
                    results['imported'] += 1
                    
            except Exception as e:
                results['errors'].append(f"Error importing key {key}: {str(e)}")
        
        # Clear cache
        self._clear_language_cache(language_code)
        TranslationCache.objects.filter(language_code=language_code).delete()
        
        return results
    
    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics
        """
        total_entries = TranslationCache.objects.count()
        active_entries = TranslationCache.objects.filter(
            expires_at__gt=datetime.now()
        ).count()
        
        # Get hit statistics
        total_hits = TranslationCache.objects.aggregate(total_hits=models.Sum('hits'))['total_hits'] or 0
        
        # Group by language
        by_language = TranslationCache.objects.values('language_code').annotate(
            count=models.Count('id'),
            hits=models.Sum('hits')
        ).order_by('-count')
        
        return {
            'total_entries': total_entries,
            'active_entries': active_entries,
            'expired_entries': total_entries - active_entries,
            'total_hits': total_hits,
            'average_hits_per_entry': total_hits / total_entries if total_entries > 0 else 0,
            'by_language': list(by_language)
        }
    
    def clear_cache(self, language_code: str = None, pattern: str = None) -> int:
        """
        Clear translation cache
        
        Args:
            language_code: Clear cache for specific language
            pattern: Redis pattern to delete
        
        Returns:
            Number of cache entries cleared
        """
        if pattern:
            # Use Redis pattern delete
            deleted_count = cache.delete_pattern(pattern)
        elif language_code:
            # Clear cache for specific language
            cache_pattern = f"translations:*:{language_code}"
            deleted_count = cache.delete_pattern(cache_pattern)
            
            # Clear database cache
            TranslationCache.objects.filter(language_code=language_code).delete()
        else:
            # Clear all translation cache
            cache_pattern = "translations:*"
            deleted_count = cache.delete_pattern(cache_pattern)
            
            # Clear all database cache
            TranslationCache.objects.all().delete()
        
        return deleted_count
    
    def warm_cache(self, language_code: str = None) -> Dict[str, Any]:
        """
        Warm up translation cache
        """
        start_time = datetime.now()
        results = {
            'languages_warmed': [],
            'keys_cached': 0,
            'duration_seconds': 0
        }
        
        languages = []
        if language_code:
            try:
                language = Language.objects.get(code=language_code, is_active=True)
                languages = [language]
            except Language.DoesNotExist:
                return results
        else:
            languages = Language.objects.filter(is_active=True)
        
        for language in languages:
            # Load all translations for this language
            translations = self.get_all_translations(language.code)
            results['languages_warmed'].append({
                'code': language.code,
                'keys_cached': len(translations)
            })
            results['keys_cached'] += len(translations)
        
        end_time = datetime.now()
        results['duration_seconds'] = (end_time - start_time).total_seconds()
        
        return results
    
    def _get_translation_from_db(self, key: str, language_code: str) -> Optional[str]:
        """
        Get translation from database
        """
        try:
            translation = Translation.objects.select_related('key', 'language').get(
                key__key=key,
                language__code=language_code,
                is_approved=True
            )
            return translation.value
        except Translation.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting translation from DB: {e}")
            return None
    
    def _get_translations_from_db_batch(
        self, 
        keys: List[str], 
        language_code: str
    ) -> Dict[str, str]:
        """
        Get multiple translations from database
        """
        translations = Translation.objects.select_related('key', 'language').filter(
            key__key__in=keys,
            language__code=language_code,
            is_approved=True
        )
        
        return {t.key.key: t.value for t in translations}
    
    def _load_translations(self, language_code: str, namespace: str) -> Dict[str, str]:
        """
        Load translations from multiple sources
        """
        translations = {}
        
        # 1. Load from static JSON files
        static_translations = self._load_static_translations(language_code)
        translations.update(static_translations)
        
        # 2. Load from database
        db_translations = self._load_db_translations(language_code)
        translations.update(db_translations)
        
        # 3. Load from custom sources (if any)
        custom_translations = self._load_custom_translations(language_code, namespace)
        translations.update(custom_translations)
        
        return translations
    
    def _load_static_translations(self, language_code: str) -> Dict[str, str]:
        """
        Load translations from static JSON files
        """
        translations = {}
        
        try:
            # Default path: translations/{language_code}/messages.json
            file_path = os.path.join(
                settings.BASE_DIR,
                'Api/localization/translations',
                language_code,
                'messages.json'
            )
            
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
        except Exception as e:
            logger.error(f"Error loading static translations for {language_code}: {e}")
        
        return translations
    
    def _load_db_translations(self, language_code: str) -> Dict[str, str]:
        """
        Load translations from database
        """
        translations = {}
        
        try:
            db_translations = Translation.objects.select_related('key', 'language').filter(
                language__code=language_code,
                is_approved=True
            )
            
            for translation in db_translations:
                translations[translation.key.key] = translation.value
                
                # Also include plural form if exists
                if translation.value_plural:
                    plural_key = f"{translation.key.key}_plural"
                    translations[plural_key] = translation.value_plural
                    
        except Exception as e:
            logger.error(f"Error loading DB translations for {language_code}: {e}")
        
        return translations
    
    def _load_custom_translations(self, language_code: str, namespace: str) -> Dict[str, str]:
        """
        Load translations from custom sources
        Override this method for custom translation sources
        """
        return {}
    
    def _get_cache_key(self, language_code: str, key: str) -> str:
        """
        Generate cache key for translation
        """
        key_hash = hashlib.md5(key.encode()).hexdigest()
        return f"translation:{language_code}:{key_hash}"
    
    def _clear_language_cache(self, language_code: str):
        """
        Clear cache for a specific language
        """
        # Clear Redis cache
        cache_pattern = f"translation:{language_code}:*"
        cache.delete_pattern(cache_pattern)
        
        # Clear namespace cache
        cache_key = f"translations:*:{language_code}"
        cache.delete_pattern(cache_key)
    
    def _format_translation(self, text: str, **kwargs) -> str:
        """
        Format translation with arguments
        """
        if not kwargs:
            return text
        
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"Error formatting translation: {e}")
            return text
    
    def _log_missing_translation(self, key: str, language_code: str):
        """
        Log missing translation for monitoring
        """
        try:
            # Check if already logged recently
            recently_logged = MissingTranslation.objects.filter(
                key=key,
                language__code=language_code,
                created__gte=datetime.now() - timedelta(hours=24),
                resolved=False
            ).exists()
            
            if not recently_logged:
                # Get language object
                try:
                    language = Language.objects.get(code=language_code)
                    
                    # Create missing translation record
                    MissingTranslation.objects.create(
                        key=key,
                        language=language
                    )
                    
                    logger.warning(f"Missing translation: {key} in {language_code}")
                    
                except Language.DoesNotExist:
                    pass
                    
        except Exception as e:
            logger.error(f"Error logging missing translation: {e}")
    
    def _get_cache_hit_rate(self) -> float:
        """
        Calculate cache hit rate
        """
        try:
            total_hits = TranslationCache.objects.aggregate(
                total_hits=models.Sum('hits')
            )['total_hits'] or 0
            
            total_entries = TranslationCache.objects.count()
            
            # Estimate requests (hits + misses)
            # This is an approximation
            estimated_misses = total_entries * 0.1  # Assuming 10% miss rate
            total_requests = total_hits + estimated_misses
            
            if total_requests > 0:
                return (total_hits / total_requests) * 100
            
        except Exception as e:
            logger.error(f"Error calculating cache hit rate: {e}")
        
        return 0.0
    
    def get_language_info(self, language_code: str) -> Dict[str, Any]:
        """
        Get detailed information about a language
        """
        try:
            language = Language.objects.get(code=language_code)
            
            # Get translation statistics
            total_keys = TranslationKey.objects.count()
            translated_count = Translation.objects.filter(
                language=language, 
                is_approved=True
            ).count()
            
            coverage = (translated_count / total_keys * 100) if total_keys > 0 else 0
            
            # Get recent translations
            recent_translations = Translation.objects.filter(
                language=language
            ).order_by('-modified')[:10].values(
                'key__key', 'value', 'modified', 'source'
            )
            
            return {
                'code': language.code,
                'name': language.name,
                'name_native': language.name_native,
                'is_active': language.is_active,
                'is_default': language.is_default,
                'is_rtl': language.is_rtl,
                'flag_emoji': language.flag_emoji,
                'locale_code': language.locale_code,
                'statistics': {
                    'total_keys': total_keys,
                    'translated_keys': translated_count,
                    'missing_keys': total_keys - translated_count,
                    'coverage_percentage': round(coverage, 2),
                    'total_translations': Translation.objects.filter(language=language).count(),
                    'approved_translations': translated_count,
                },
                'recent_translations': list(recent_translations),
                'created': language.created.isoformat(),
                'modified': language.modified.isoformat()
            }
            
        except Language.DoesNotExist:
            return {}
    
    def sync_static_files(self, language_code: str = None) -> Dict[str, Any]:
        """
        Sync database translations with static files
        """
        results = {
            'languages_synced': [],
            'files_created': 0,
            'files_updated': 0,
            'errors': []
        }
        
        languages = []
        if language_code:
            try:
                language = Language.objects.get(code=language_code, is_active=True)
                languages = [language]
            except Language.DoesNotExist:
                results['errors'].append(f"Language not found: {language_code}")
                return results
        else:
            languages = Language.objects.filter(is_active=True)
        
        for language in languages:
            try:
                # Get all translations for this language
                translations = self.get_all_translations(language.code)
                
                # Create directory if it doesn't exist
                dir_path = os.path.join(
                    settings.BASE_DIR,
                    'Api/localization/translations',
                    language.code
                )
                os.makedirs(dir_path, exist_ok=True)
                
                # File path
                file_path = os.path.join(dir_path, 'messages.json')
                
                # Check if file exists
                file_exists = os.path.exists(file_path)
                
                # Write to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(translations, f, ensure_ascii=False, indent=2)
                
                results['languages_synced'].append(language.code)
                
                if file_exists:
                    results['files_updated'] += 1
                else:
                    results['files_created'] += 1
                    
            except Exception as e:
                results['errors'].append(f"Error syncing {language.code}: {str(e)}")
        
        return results
    
    def get_user_preference(self, user):
        """ইউজারের ল্যাঙ্গুয়েজ প্রেফারেন্স খুঁজে বের করার ফাংশন"""
        try:
            return getattr(user, 'preferred_language', 'en') 
        except Exception:
            return 'en'
    
#     # Logger কনফিগারেশন
# logger = logging.getLogger(__name__)

# class LocalizationService:
#     def get_translations(self, lang_code):
#         """
#         নির্দিষ্ট ল্যাঙ্গুয়েজ কোডের জন্য সব ট্রান্সলেশন রিটার্ন করবে।
#         প্রথমে ক্যাশ চেক করবে, না থাকলে ডাটাবেস থেকে আনবে।
#         """
#         cache_key = f"translations:all:{lang_code}"
#         translations = cache.get(cache_key)

#         if translations is None:
#             translations = self.warm_cache(lang_code)
        
#         return translations or {}

#     def translate(self, key, lang_code, default=None):
#         """
#         একটি নির্দিষ্ট Key এর অনুবাদ দেবে। না থাকলে MissingTranslation এ সেভ করবে।
#         """
#         translations = self.get_translations(lang_code)
#         value = translations.get(key)
        
#         if value:
#             return value
        
#         # যদি অনুবাদ না পাওয়া যায়, তবে সেটি MissingTranslation এ রেকর্ড করুন
#         self._report_missing_key(key, lang_code)
#         return default or key

#     def _report_missing_key(self, key, lang_code):
#         """ডাটাবেসে নেই এমন কি-গুলো ট্র্যাক করা"""
#         try:
#             language = Language.objects.filter(code=lang_code).first()
#             if language:
#                 MissingTranslation.objects.get_or_create(
#                     key=key,
#                     language=language,
#                     defaults={'resolved': False}
#                 )
#         except Exception as e:
#             logger.warning(f"Failed to log missing translation: {e}")

#     def warm_cache(self, lang_code):
#         """ডাটাবেস থেকে ট্রান্সলেশন নিয়ে ক্যাশে সেভ করে।"""
#         try:
#             qs = Translation.objects.filter(
#                 language__code=lang_code, 
#                 is_approved=True
#             ).select_related('key')
            
#             translation_dict = {t.key.key: t.value for t in qs}
            
#             cache_key = f"translations:all:{lang_code}"
#             cache.set(cache_key, translation_dict, 86400)
#             return translation_dict
#         except Exception as e:
#             logger.error(f"Error warming cache for {lang_code}: {e}")
#             return {}