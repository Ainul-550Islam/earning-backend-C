# tasks/translation_memory_tasks.py
"""Celery task: index Translation Memory entries"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.translation_memory_tasks.index_approved_translations')
    def index_approved_translations():
        """Approved translations-কে TM-এ index করে"""
        try:
            from ..models.core import Translation
            from ..services.translation.TranslationMemoryService import TranslationMemoryService
            service = TranslationMemoryService()
            # Get default language (source)
            from ..models.core import Language
            default_lang = Language.objects.filter(is_default=True).first()
            if not default_lang:
                return {'success': False, 'error': 'No default language'}
            translations = Translation.objects.filter(is_approved=True).select_related('key', 'language')
            indexed = 0
            for trans in translations[:1000]:
                if trans.language == default_lang:
                    continue
                # Get source text
                source = Translation.objects.filter(key=trans.key, language=default_lang).first()
                if source:
                    tm = service.add_segment(
                        source.value, trans.value,
                        default_lang.code, trans.language.code,
                        is_approved=True, quality_rating=4
                    )
                    if tm:
                        indexed += 1
            logger.info(f"Indexed {indexed} translations into TM")
            return {'success': True, 'indexed': indexed}
        except Exception as e:
            logger.error(f"TM indexing failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
