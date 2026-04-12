# tasks/cleanup_tasks.py
"""Celery task: cleanup old/expired data"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.cleanup_tasks.cleanup_all')
    def cleanup_all():
        """All expired/old data cleanup করে — daily"""
        try:
            results = {}
            # Clean expired translation cache
            from ..models.translation import TranslationCache
            deleted, _ = TranslationCache.bulk_clean_expired(days=7)
            results['translation_cache_deleted'] = deleted
            # Clean old geo lookups
            from ..models.geo import GeoIPMapping
            from django.utils import timezone
            from datetime import timedelta
            # Clean resolved missing translations older than 30 days
            from ..models.translation import MissingTranslation
            old_resolved = MissingTranslation.objects.filter(
                resolved=True,
                resolved_at__lt=timezone.now() - timedelta(days=30)
            ).delete()
            results['old_resolved_missing'] = old_resolved[0]
            logger.info(f"Cleanup completed: {results}")
            return {'success': True, 'results': results}
        except Exception as e:
            logger.error(f"cleanup_all failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
