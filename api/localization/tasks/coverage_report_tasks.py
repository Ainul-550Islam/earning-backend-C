# tasks/coverage_report_tasks.py
"""Celery task: daily coverage report"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.coverage_report_tasks.update_coverage')
    def update_coverage():
        """Daily translation coverage stats update করে"""
        try:
            from ..services.translation.TranslationCoverageService import TranslationCoverageService
            service = TranslationCoverageService()
            results = service.calculate_all()
            logger.info(f"Coverage updated for {len(results)} languages")
            return {'success': True, 'languages': len(results), 'results': results}
        except Exception as e:
            logger.error(f"update_coverage task failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
