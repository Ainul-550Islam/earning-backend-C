# tasks/translation_qa_tasks.py
"""Celery task: nightly QA check on all translations"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.translation_qa_tasks.run_qa_check')
    def run_qa_check(language_code=None):
        """All translations-এর QA check করে — nightly"""
        try:
            from ..services.translation.TranslationQAService import TranslationQAService
            from ..models.core import Language
            service = TranslationQAService()
            if language_code:
                langs = Language.objects.filter(code=language_code, is_active=True)
            else:
                langs = Language.objects.filter(is_active=True, is_default=False)
            all_results = {}
            for lang in langs:
                result = service.run_batch_qa(lang.code)
                all_results[lang.code] = result
                failed = result.get('failed', 0)
                if failed > 0:
                    logger.warning(f"QA: {failed} issues found for {lang.code}")
            return {'success': True, 'results': all_results}
        except Exception as e:
            logger.error(f"run_qa_check failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
