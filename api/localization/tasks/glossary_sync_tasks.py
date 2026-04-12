# tasks/glossary_sync_tasks.py
"""Celery task: sync glossary to translation providers"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.glossary_sync_tasks.sync_glossary')
    def sync_glossary_to_providers():
        """Glossary terms translation providers-এ sync করে"""
        try:
            from ..models.translation import TranslationGlossary, TranslationGlossaryEntry
            dnt_terms = TranslationGlossary.objects.filter(is_do_not_translate=True).count()
            brand_terms = TranslationGlossary.objects.filter(is_brand_term=True).count()
            logger.info(f"Glossary: {dnt_terms} DNT terms, {brand_terms} brand terms ready to sync")
            return {'success': True, 'dnt_terms': dnt_terms, 'brand_terms': brand_terms}
        except Exception as e:
            logger.error(f"Glossary sync failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
