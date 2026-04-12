# tasks/translation_cache_tasks.py
"""Celery task: clean stale translation cache"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.translation_cache_tasks.clean_expired_cache')
    def clean_expired_cache():
        """Expired translation cache entries delete করে — hourly"""
        try:
            from ..models.translation import TranslationCache
            deleted_count, _ = TranslationCache.clean_expired()
            logger.info(f"Cleaned {deleted_count} expired translation cache entries")
            return {'deleted': deleted_count}
        except Exception as e:
            logger.error(f"clean_expired_cache failed: {e}")
            return {'error': str(e)}

    @shared_task(name='localization.translation_cache_tasks.rebuild_popular_cache')
    def rebuild_popular_cache():
        """Top 10 languages-এর cache pre-warm করে"""
        try:
            from ..models.core import Language, Translation
            from ..models.translation import TranslationCache
            from django.utils import timezone
            from datetime import timedelta
            top_langs = Language.objects.filter(is_active=True)[:10]
            rebuilt = 0
            for lang in top_langs:
                try:
                    translations = Translation.objects.filter(
                        language=lang, is_approved=True
                    ).select_related('key')
                    data = {t.key.key: t.value for t in translations}
                    cache_key = f"translations:global:{lang.code}"
                    TranslationCache.objects.update_or_create(
                        language_code=lang.code,
                        cache_key=cache_key,
                        defaults={
                            'cache_data': data,
                            'expires_at': timezone.now() + timedelta(hours=24),
                        }
                    )
                    rebuilt += 1
                except Exception as e:
                    logger.error(f"Cache rebuild failed for {lang.code}: {e}")
            return {'rebuilt': rebuilt}
        except Exception as e:
            logger.error(f"rebuild_popular_cache failed: {e}")
            return {'error': str(e)}

except ImportError:
    pass
