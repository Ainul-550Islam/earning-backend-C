# tasks/language_pack_tasks.py
"""Celery tasks for language pack build and publish"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.language_pack_tasks.build_all_packs', bind=True, max_retries=3)
    def build_all_packs(self):
        """All active languages-এর language packs build করে"""
        try:
            from ..models.core import Language
            from ..services.translation.LanguagePackBuilder import LanguagePackBuilder
            builder = LanguagePackBuilder()
            languages = Language.objects.filter(is_active=True)
            results = {}
            for lang in languages:
                result = builder.build(lang.code)
                results[lang.code] = {
                    'success': result['success'],
                    'count': result.get('count', 0),
                    'coverage': result.get('coverage', 0),
                }
            logger.info(f"Built packs for {len(results)} languages")
            return {'success': True, 'results': results}
        except Exception as exc:
            logger.error(f"build_all_packs failed: {exc}")
            self.retry(exc=exc, countdown=60)

    @shared_task(name='localization.language_pack_tasks.build_language_pack')
    def build_language_pack(language_code: str, namespace: str = 'global', version: str = '1.0.0'):
        """Single language pack build করে"""
        try:
            from ..services.translation.LanguagePackBuilder import LanguagePackBuilder
            result = LanguagePackBuilder().build(language_code, namespace, version)
            if result['success']:
                logger.info(f"Pack built: {language_code}/{namespace} v{version} — {result['count']} keys")
            else:
                logger.error(f"Pack build failed: {result.get('error')}")
            return result
        except Exception as e:
            logger.error(f"build_language_pack task failed: {e}")
            return {'success': False, 'error': str(e)}

    @shared_task(name='localization.language_pack_tasks.invalidate_pack_cache')
    def invalidate_pack_cache(language_code: str = None):
        """Language pack cache invalidate করে"""
        try:
            from django.core.cache import cache
            if language_code:
                keys = [f"lang_pack_{language_code}_*"]
                cache.delete_pattern(f"lang_pack_{language_code}_*")
            else:
                cache.delete_pattern("lang_pack_*")
            logger.info(f"Pack cache invalidated for: {language_code or 'all'}")
            return {'success': True}
        except Exception as e:
            logger.error(f"invalidate_pack_cache failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    logger.warning("Celery not installed — language pack tasks disabled")
