# api/support/integrations/health_check.py  — WORLD #1
"""
Health Check — সব integration-এর health monitor।
Admin dashboard-এ দেখা যাবে কোন integration কাজ করছে।
"""
import logging
import time
from typing import Dict

from django.core.cache import cache
from django.utils import timezone

from .integ_constants import HEALTH_CHECK_TIMEOUT, CACHE_TTL_HEALTH, CACHE_PREFIX
from .integ_registry import get_registry

logger = logging.getLogger(__name__)


class IntegrationHealthChecker:
    """Check health of all integration adapters."""

    def check_all(self, use_cache: bool = True) -> Dict[str, dict]:
        """Run health checks on all registered adapters."""
        cache_key = f'{CACHE_PREFIX}:health:all'
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached

        registry = get_registry()
        results  = {}

        checks = {
            'wallet':        self.check_wallet,
            'fraud':         self.check_fraud,
            'postback':      self.check_postback,
            'offerwall':     self.check_offerwall,
            'notifications': self.check_notifications,
            'kyc':           self.check_kyc,
        }

        for name, check_fn in checks.items():
            start  = time.perf_counter()
            result = {'name': name, 'healthy': False, 'message': '', 'latency_ms': 0}
            try:
                ok, msg   = check_fn()
                result['healthy']    = ok
                result['message']    = msg
            except Exception as e:
                result['message'] = f'Exception: {str(e)[:200]}'
            finally:
                result['latency_ms'] = round((time.perf_counter()-start)*1000, 1)
                result['checked_at'] = timezone.now().isoformat()

            results[name] = result
            registry.set_health(name, result['healthy'], result)

        # Overall status
        all_healthy = all(r['healthy'] for r in results.values())
        results['_overall'] = {
            'healthy':  all_healthy,
            'checked_at': timezone.now().isoformat(),
            'healthy_count': sum(1 for r in results.values() if r.get('healthy')),
        }

        cache.set(cache_key, results, timeout=CACHE_TTL_HEALTH)
        return results

    def check_wallet(self) -> tuple:
        """Check wallet app is accessible."""
        try:
            from django.apps import apps
            apps.get_model('wallet', 'Wallet')
            return True, 'Wallet model accessible.'
        except LookupError:
            return False, 'wallet app not installed or Wallet model missing.'

    def check_fraud(self) -> tuple:
        """Check fraud_detection app."""
        try:
            from django.apps import apps
            apps.get_model('fraud_detection', 'UserRiskProfile')
            return True, 'FraudDetection model accessible.'
        except LookupError:
            return False, 'fraud_detection app not installed.'

    def check_postback(self) -> tuple:
        """Check postback app."""
        try:
            from django.apps import apps
            apps.get_model('postback', 'PostbackLog')
            return True, 'PostbackLog model accessible.'
        except LookupError:
            return False, 'postback app not installed or PostbackLog missing.'

    def check_offerwall(self) -> tuple:
        """Check offerwall app."""
        try:
            from django.apps import apps
            apps.get_model('offerwall', 'Offer')
            return True, 'Offerwall Offer model accessible.'
        except LookupError:
            return False, 'offerwall app not installed.'

    def check_notifications(self) -> tuple:
        """Check notifications app."""
        try:
            from django.apps import apps
            apps.get_model('notifications', 'Notification')
            return True, 'Notification model accessible.'
        except LookupError:
            return False, 'notifications app not installed.'

    def check_kyc(self) -> tuple:
        """Check KYC app."""
        try:
            from django.apps import apps
            apps.get_model('kyc', 'KYC')
            return True, 'KYC model accessible.'
        except LookupError:
            return False, 'kyc app not installed.'

    def check_database(self) -> tuple:
        """Check support database tables."""
        try:
            from api.support.models import SupportTicket, SupportSettings
            SupportTicket.objects.count()
            return True, f'DB healthy. Tickets: {SupportTicket.objects.count()}'
        except Exception as e:
            return False, f'DB error: {e}'

    def check_cache(self) -> tuple:
        """Check Redis/cache availability."""
        try:
            test_key = f'{CACHE_PREFIX}:health_ping'
            cache.set(test_key, 'pong', timeout=10)
            val = cache.get(test_key)
            return val == 'pong', 'Cache healthy.' if val == 'pong' else 'Cache read failed.'
        except Exception as e:
            return False, f'Cache error: {e}'

    def get_health_summary(self) -> dict:
        """Get quick health summary."""
        results   = self.check_all(use_cache=True)
        healthy   = [k for k, v in results.items() if k != '_overall' and v.get('healthy')]
        unhealthy = [k for k, v in results.items() if k != '_overall' and not v.get('healthy')]
        return {
            'status':   'healthy' if not unhealthy else 'degraded',
            'healthy':  healthy,
            'unhealthy':unhealthy,
            'timestamp':timezone.now().isoformat(),
        }


health_checker = IntegrationHealthChecker()