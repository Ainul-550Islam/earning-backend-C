# tasks/auto_translation_tasks.py
"""Celery task: bulk auto-translate missing keys"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.auto_translation_tasks.auto_translate_missing')
    def auto_translate_missing(language_code=None, limit=50):
        """Missing translations auto-translate করে — runs nightly"""
        try:
            from ..services.translation.AutoTranslationService import AutoTranslationService
            from ..models.core import Language
            service = AutoTranslationService()
            if language_code:
                languages = Language.objects.filter(code=language_code, is_active=True)
            else:
                # All non-default languages
                languages = Language.objects.filter(is_active=True, is_default=False)
            results = []
            for lang in languages:
                result = service.translate_missing(lang.code, limit=limit)
                results.append(result)
                logger.info(f"Auto-translated {result.get('translated', 0)} keys for {lang.code}")
            return {'success': True, 'languages_processed': len(results), 'results': results}
        except Exception as e:
            logger.error(f"auto_translate_missing task failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
