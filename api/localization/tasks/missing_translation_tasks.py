# tasks/missing_translation_tasks.py
"""Celery task: alert on new missing translations"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.missing_translation_tasks.alert_missing')
    def alert_missing_translations():
        """New missing translations-এর alert পাঠায়"""
        try:
            from ..models.translation import MissingTranslation
            from django.utils import timezone
            from datetime import timedelta
            recent = MissingTranslation.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24),
                resolved=False
            ).count()
            if recent > 10:
                logger.warning(f"ALERT: {recent} new missing translations in last 24h")
            return {'recent_missing': recent}
        except Exception as e:
            logger.error(f"alert_missing_translations failed: {e}")
            return {'error': str(e)}

except ImportError:
    pass
