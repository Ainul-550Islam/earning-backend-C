# tasks/insight_tasks.py
"""Celery task: daily localization usage stats"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.insight_tasks.aggregate_daily_insights')
    def aggregate_daily_insights():
        """Daily localization insight stats aggregate করে"""
        try:
            from django.utils import timezone
            from datetime import timedelta
            from ..models.analytics import LocalizationInsight
            from ..models.core import Language
            yesterday = (timezone.now() - timedelta(days=1)).date()
            languages = Language.objects.filter(is_active=True)
            created = 0
            for lang in languages:
                _, was_created = LocalizationInsight.objects.get_or_create(
                    date=yesterday, language=lang, country=None,
                    defaults={
                        'total_requests': 0,
                        'unique_users': 0,
                        'translation_hits': 0,
                    }
                )
                if was_created:
                    created += 1
            logger.info(f"Created {created} daily insight records for {yesterday}")
            return {'success': True, 'date': str(yesterday), 'created': created}
        except Exception as e:
            logger.error(f"aggregate_daily_insights failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
