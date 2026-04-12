# tasks/provider_health_tasks.py
"""Celery task: ping translation API providers"""
import logging
logger = logging.getLogger(__name__)

try:
    from celery import shared_task

    @shared_task(name='localization.provider_health_tasks.check_provider_health')
    def check_provider_health():
        """All translation providers health check করে"""
        try:
            from ..services.providers.ProviderHealthChecker import ProviderHealthChecker
            checker = ProviderHealthChecker()
            results = checker.check_all()
            unhealthy = [p for p, r in results.get('providers', {}).items() if not r.get('healthy', False)]
            if unhealthy:
                logger.error(f"Unhealthy translation providers: {unhealthy}")
            return results
        except Exception as e:
            logger.error(f"check_provider_health failed: {e}")
            return {'success': False, 'error': str(e)}

except ImportError:
    pass
