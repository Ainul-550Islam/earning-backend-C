# services/providers/ProviderHealthChecker.py
"""Provider health monitoring"""
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ProviderHealthChecker:
    """Translation provider health periodic check করে"""

    def check_all(self) -> Dict:
        """সব configured providers check করে"""
        try:
            from django.conf import settings
            results = {'providers': {}, 'all_healthy': True}
            provider_config = getattr(settings, 'TRANSLATION_PROVIDERS', {})
            for name, config in provider_config.items():
                if not config.get('enabled', True):
                    results['providers'][name] = {'status': 'disabled'}
                    continue
                try:
                    from .ProviderRouter import ProviderRouter
                    router = ProviderRouter()
                    provider = router._providers.get(name)
                    if provider:
                        healthy = provider.health_check()
                        results['providers'][name] = {'status': 'healthy' if healthy else 'unhealthy', 'healthy': healthy}
                        if not healthy:
                            results['all_healthy'] = False
                    else:
                        results['providers'][name] = {'status': 'not_loaded'}
                        results['all_healthy'] = False
                except Exception as e:
                    results['providers'][name] = {'status': 'error', 'error': str(e)}
                    results['all_healthy'] = False
            return results
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'error': str(e), 'all_healthy': False}
