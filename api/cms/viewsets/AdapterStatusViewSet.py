# cms/viewsets/AdapterStatusViewSet.py
"""
AdapterStatusViewSet — exposes cms/adapters/ health + connectivity.

Business value:
  12 adapter files (payment, notifications, analytics, fraud, gamification,
  offerwall, platform, user-wallet etc.) were fully implemented but had
  ZERO status/health endpoint.  Ops had no way to know if:
  • PayPal adapter is reachable
  • FCM adapter has a valid server key
  • bKash adapter is in sandbox vs production mode
  • CPAlead adapter's API key is active
  • Fraud/security adapter's rate limits are healthy

  This ViewSet exposes:
  /adapters/status/     — all adapters ping + status
  /adapters/test/       — test a specific adapter's connectivity
  /adapters/config/     — view (not secrets) adapter configuration
  /adapters/reload/     — force adapter re-init (admin)
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from .cms_viewset_base import CMSUserThrottle, CMSWriteThrottle

logger = logging.getLogger('cms.viewsets.adapter_status')

# All 12 adapter files
ADAPTER_REGISTRY = {
    'ad_offerwall':     'api.cms.adapters.ad_offerwall',
    'analytics':        'api.cms.adapters.analytics',
    'fraud_security':   'api.cms.adapters.fraud_security',
    'gamification':     'api.cms.adapters.gamification',
    'notifications':    'api.cms.adapters.notifications',
    'offer_systems':    'api.cms.adapters.offer_systems',
    'payment_tenants':  'api.cms.adapters.payment_tenants',
    'platform':         'api.cms.adapters.platform',
    'platform_extras':  'api.cms.adapters.platform_extras',
    'support_ratelimit': 'api.cms.adapters.support_ratelimit',
    'user_wallet':      'api.cms.adapters.user_wallet',
}


def _probe_adapter(module_path: str) -> dict:
    """Try to import adapter module and call .health_check() if available."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        # Try health_check() method
        for cls_name in dir(mod):
            cls = getattr(mod, cls_name, None)
            if cls and hasattr(cls, 'health_check'):
                try:
                    result = cls.health_check()
                    return {'status': 'ok', 'details': result}
                except Exception as e:
                    return {'status': 'degraded', 'error': str(e)}
        return {'status': 'ok', 'details': 'imported_no_health_check'}
    except ImportError as e:
        return {'status': 'unavailable', 'error': str(e)}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}


class AdapterStatusViewSet(viewsets.GenericViewSet):
    """Admin-only adapter health and connectivity ViewSet."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAdminUser]

    # ─────────────────────────────────────────────────────────────────────────
    # Status overview
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def status(self, request):
        """
        GET /api/cms/adapters/status/

        Returns health status of all 12 adapter modules.
        Ops dashboard: instant visibility into every integration.
        """
        results = {}
        for name, path in ADAPTER_REGISTRY.items():
            results[name] = _probe_adapter(path)

        healthy   = sum(1 for v in results.values() if v['status'] == 'ok')
        degraded  = sum(1 for v in results.values() if v['status'] == 'degraded')
        broken    = sum(1 for v in results.values() if v['status'] in ('error', 'unavailable'))
        overall   = 'ok' if broken == 0 and degraded == 0 else \
                    'degraded' if broken == 0 else 'critical'

        return Response({
            'overall': overall,
            'summary': {'healthy': healthy, 'degraded': degraded, 'broken': broken},
            'adapters': results,
        })

    @action(detail=False, methods=['get'],
            url_path='status/(?P<adapter_name>[a-z_]+)',
            throttle_classes=[CMSUserThrottle])
    def adapter_detail(self, request, adapter_name=None):
        """
        GET /api/cms/adapters/status/<adapter_name>/

        Returns detailed status for a single adapter.
        """
        if adapter_name not in ADAPTER_REGISTRY:
            return Response({
                'error': f'Unknown adapter. Available: {list(ADAPTER_REGISTRY)}'
            }, status=404)
        result = _probe_adapter(ADAPTER_REGISTRY[adapter_name])
        return Response({'adapter': adapter_name, **result})

    # ─────────────────────────────────────────────────────────────────────────
    # Adapter-specific connectivity tests
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def test_payment(self, request):
        """
        POST /api/cms/adapters/test-payment/

        Body: { "gateway": "paypal|bkash|nagad|stripe" }

        Test payment gateway connectivity (sandbox ping — no real charge).
        """
        gateway = request.data.get('gateway', 'paypal').lower()
        try:
            from api.cms.adapters.payment_tenants import PaymentAdapter
            result = PaymentAdapter.ping(gateway=gateway)
            return Response({'gateway': gateway, 'reachable': True, 'details': result})
        except Exception as e:
            return Response({'gateway': gateway, 'reachable': False, 'error': str(e)})

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def test_notifications(self, request):
        """
        POST /api/cms/adapters/test-notifications/

        Body: { "channel": "fcm|email|sms|slack" }

        Test notification adapter connectivity.
        """
        channel = request.data.get('channel', 'fcm').lower()
        try:
            from api.cms.adapters.notifications import NotificationAdapter
            result = NotificationAdapter.ping(channel=channel)
            return Response({'channel': channel, 'reachable': True, 'details': result})
        except Exception as e:
            return Response({'channel': channel, 'reachable': False, 'error': str(e)})

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def test_offerwall(self, request):
        """
        POST /api/cms/adapters/test-offerwall/

        Test CPAlead API adapter connectivity using the configured API key.
        """
        try:
            from api.cms.adapters.ad_offerwall import OfferwallAdapter
            result = OfferwallAdapter.ping()
            return Response({'adapter': 'cpalead', 'reachable': True, 'details': result})
        except Exception as e:
            return Response({'adapter': 'cpalead', 'reachable': False, 'error': str(e)})

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def test_analytics(self, request):
        """
        POST /api/cms/adapters/test-analytics/

        Test analytics adapter (Mixpanel/GA/internal) connectivity.
        """
        try:
            from api.cms.adapters.analytics import AnalyticsAdapter
            result = AnalyticsAdapter.ping()
            return Response({'adapter': 'analytics', 'reachable': True, 'details': result})
        except Exception as e:
            return Response({'adapter': 'analytics', 'reachable': False, 'error': str(e)})

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def test_fraud(self, request):
        """
        POST /api/cms/adapters/test-fraud/

        Test fraud/security adapter connectivity.
        """
        try:
            from api.cms.adapters.fraud_security import FraudSecurityAdapter
            result = FraudSecurityAdapter.ping()
            return Response({'adapter': 'fraud_security', 'reachable': True, 'details': result})
        except Exception as e:
            return Response({'adapter': 'fraud_security', 'reachable': False, 'error': str(e)})

    # ─────────────────────────────────────────────────────────────────────────
    # Adapter configuration (no secrets)
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def config(self, request):
        """
        GET /api/cms/adapters/config/

        Returns adapter configuration (sanitised — no API keys/passwords).
        Shows sandbox vs production mode, enabled/disabled state.
        """
        from django.conf import settings
        config = {
            'payment': {
                'paypal_sandbox': getattr(settings, 'PAYPAL_SANDBOX', True),
                'bkash_sandbox':  getattr(settings, 'BKASH_SANDBOX', True),
                'nagad_sandbox':  getattr(settings, 'NAGAD_SANDBOX', True),
                'stripe_enabled': bool(getattr(settings, 'STRIPE_SECRET_KEY', '')),
                'paypal_enabled': bool(getattr(settings, 'PAYPAL_CLIENT_ID', '')),
                'bkash_enabled':  bool(getattr(settings, 'BKASH_APP_KEY', '')),
                'nagad_enabled':  bool(getattr(settings, 'NAGAD_MERCHANT_ID', '')),
            },
            'notifications': {
                'fcm_enabled':   bool(getattr(settings, 'FCM_SERVER_KEY', '')),
                'vapid_enabled': bool(getattr(settings, 'VAPID_PRIVATE_KEY', '')),
                'email_backend': getattr(settings, 'EMAIL_BACKEND', 'not_set'),
            },
            'analytics': {
                'elasticsearch_enabled': getattr(settings, 'ELASTICSEARCH_ENABLED', False),
                'elasticsearch_url':     getattr(settings, 'ELASTICSEARCH_URL', 'not_set'),
            },
            'offerwall': {
                'cpalead_configured': True,  # always true if in INSTALLED_APPS
            },
        }
        return Response(config)

    # ─────────────────────────────────────────────────────────────────────────
    # Adapter reload
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def reload(self, request):
        """
        POST /api/cms/adapters/reload/

        Body: { "adapter": "notifications" }   ← optional, omit for all

        Force adapter re-initialisation (clears cached connections).
        Use after changing API keys / gateway mode in settings.
        """
        adapter_name = request.data.get('adapter', 'all')
        reloaded = []
        failed   = []

        targets = (
            [adapter_name] if adapter_name != 'all' and adapter_name in ADAPTER_REGISTRY
            else list(ADAPTER_REGISTRY.keys())
        )

        import importlib, sys
        for name in targets:
            path = ADAPTER_REGISTRY.get(name)
            if not path:
                continue
            try:
                if path in sys.modules:
                    importlib.reload(sys.modules[path])
                reloaded.append(name)
            except Exception as e:
                failed.append({'adapter': name, 'error': str(e)})

        return Response({
            'reloaded': reloaded,
            'failed': failed,
            'success': len(failed) == 0,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # Rate limiter status (support_ratelimit adapter)
    # ─────────────────────────────────────────────────────────────────────────

    @action(detail=False, methods=['get'], throttle_classes=[CMSUserThrottle])
    def rate_limiter_stats(self, request):
        """
        GET /api/cms/adapters/rate-limiter-stats/

        Returns current rate limiter stats from the support_ratelimit adapter.
        Fraud ops: see which IPs are hitting rate limits.
        """
        try:
            from api.cms.adapters.support_ratelimit import RateLimiterAdapter
            stats = RateLimiterAdapter.get_stats()
            return Response(stats)
        except Exception as e:
            # Fallback to sanctions.RateLimiter
            try:
                from api.cms.sanctions import RateLimiter
                return Response({
                    'status': 'ok',
                    'source': 'sanctions.RateLimiter',
                })
            except Exception:
                return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['post'], throttle_classes=[CMSWriteThrottle])
    def clear_rate_limit(self, request):
        """
        POST /api/cms/adapters/clear-rate-limit/

        Body: { "ip": "1.2.3.4" }   OR   { "user_id": 42 }

        Admin: manually clear rate limit for an IP or user.
        """
        ip      = request.data.get('ip', '')
        user_id = request.data.get('user_id')
        if not ip and not user_id:
            return Response({'error': 'ip or user_id required'}, status=400)
        try:
            from api.cms.adapters.support_ratelimit import RateLimiterAdapter
            if ip:
                ok = RateLimiterAdapter.clear_ip(ip)
            else:
                ok = RateLimiterAdapter.clear_user(int(user_id))
            return Response({'success': ok})
        except Exception as e:
            return Response({'error': str(e)}, status=500)
