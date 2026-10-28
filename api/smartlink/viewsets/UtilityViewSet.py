"""
UtilityViewSet
Groups all utility API endpoints:
  - /api/smartlink/currency/
  - /api/smartlink/geoip/
  - /api/smartlink/cache/
  - /api/smartlink/security/
  - /api/smartlink/notifications/
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from api.smartlink.serializers.UtilitySerializers import (
    CurrencyConvertSerializer,
    CurrencyConvertResultSerializer,
    CurrencyListSerializer,
    GeoIPLookupSerializer,
    GeoIPResultSerializer,
    CacheStatsSerializer,
    WarmupResultSerializer,
    WarmupSingleSerializer,
    RateLimitBanSerializer,
    ManualBanSerializer,
    ManualUnbanSerializer,
    NotificationPreferenceSerializer,
)

logger = logging.getLogger('smartlink.viewsets.utility')


# ─── CurrencyViewSet ──────────────────────────────────────────────────────────

class CurrencyViewSet(viewsets.ViewSet):
    """
    Multi-currency utility endpoints.

    GET  /api/smartlink/currency/rates/    → All supported currencies + rates
    POST /api/smartlink/currency/convert/  → Convert an amount between currencies
    POST /api/smartlink/currency/refresh-rates/ → Admin: refresh cached rates from API
    """
    permission_classes = [IsAuthenticated]

    def _get_service(self):
        from ..services.currency.MultiCurrencyService import MultiCurrencyService
        return MultiCurrencyService()

    @action(detail=False, methods=['get'], url_path='rates')
    @method_decorator(cache_page(60 * 5))  # Cache 5 minutes
    def rates(self, request):
        """
        GET /api/smartlink/currency/rates/
        Return all supported currencies with their rates to USD.
        """
        svc = self._get_service()
        currencies = svc.get_supported_currencies()
        from django.core.cache import cache
        rates_updated_at = cache.get('currency_rates_updated_at')

        rate_list = []
        for code in currencies:
            rate_to_usd = svc.to_usd(1.0, code)
            rate_list.append({
                'code': code,
                'name': code,
                'symbol': svc.CURRENCY_SYMBOLS.get(code, code),
                'rate_to_usd': round(rate_to_usd, 6),
                'formatted_1_usd': svc.format_currency(svc.from_usd(1.0, code), code),
            })

        return Response({
            'base': 'USD',
            'rates_updated_at': rates_updated_at,
            'currencies': rate_list,
        })

    @action(detail=False, methods=['post'], url_path='convert')
    def convert(self, request):
        """
        POST /api/smartlink/currency/convert/
        Body: {"amount": 100, "from_currency": "USD", "to_currency": "BDT"}
        """
        serializer = CurrencyConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        svc = self._get_service()
        converted = svc.convert(d['amount'], d['from_currency'], d['to_currency'])
        rate = svc.convert(1.0, d['from_currency'], d['to_currency'])

        return Response(CurrencyConvertResultSerializer({
            'amount': d['amount'],
            'from_currency': d['from_currency'],
            'to_currency': d['to_currency'],
            'converted_amount': round(converted, 6),
            'formatted': svc.format_currency(converted, d['to_currency']),
            'rate': round(rate, 6),
        }).data)

    @action(detail=False, methods=['post'], url_path='refresh-rates')
    def refresh_rates(self, request):
        """
        POST /api/smartlink/currency/refresh-rates/
        Admin-only: pull latest rates from external API and update cache.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        svc = self._get_service()
        success = svc.update_rates_from_api()
        if success:
            return Response({'message': 'Currency rates updated successfully.'})
        return Response(
            {'message': 'Rate update failed. Using cached/fallback rates.'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


# ─── GeoIPViewSet ─────────────────────────────────────────────────────────────

class GeoIPViewSet(viewsets.ViewSet):
    """
    IP intelligence lookup endpoint.

    POST /api/smartlink/geoip/lookup/  → Lookup IP details
    GET  /api/smartlink/geoip/my-ip/   → Lookup caller's IP
    """
    permission_classes = [IsAuthenticated]

    def _get_service(self):
        from ..services.geoip.GeoIPEnricher import GeoIPEnricher
        return GeoIPEnricher()

    @action(detail=False, methods=['post'], url_path='lookup')
    def lookup(self, request):
        """
        POST /api/smartlink/geoip/lookup/
        Body: {"ip": "1.2.3.4"}
        Returns full geo + ASN + proxy intelligence.
        """
        serializer = GeoIPLookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = serializer.validated_data['ip']

        svc = self._get_service()
        result = svc.enrich(ip)
        return Response(GeoIPResultSerializer(result).data)

    @action(detail=False, methods=['get'], url_path='my-ip')
    def my_ip(self, request):
        """
        GET /api/smartlink/geoip/my-ip/
        Enrich the caller's own IP address.
        """
        from api.smartlink.utils import get_client_ip
        ip = get_client_ip(request)
        svc = self._get_service()
        result = svc.enrich(ip)
        return Response(GeoIPResultSerializer(result).data)


# ─── CacheViewSet ─────────────────────────────────────────────────────────────

class CacheViewSet(viewsets.ViewSet):
    """
    Cache management endpoints.

    GET  /api/smartlink/cache/stats/          → Cache statistics
    POST /api/smartlink/cache/warmup/         → Warm all active SmartLinks
    POST /api/smartlink/cache/warmup-single/  → Warm a specific slug
    POST /api/smartlink/cache/predictive/     → Run predictive warmup
    DELETE /api/smartlink/cache/flush/        → Admin: flush all SmartLink caches
    """
    permission_classes = [IsAuthenticated]

    def _get_orchestrator(self):
        from ..services.cache.CacheWarmupOrchestrator import CacheWarmupOrchestrator
        return CacheWarmupOrchestrator()

    def _get_cache_svc(self):
        from api.smartlink.services.core.SmartLinkCacheService import SmartLinkCacheService
        return SmartLinkCacheService()

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """GET /api/smartlink/cache/stats/ — Current cache statistics."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        orchestrator = self._get_orchestrator()
        result = orchestrator.get_cache_stats()
        return Response(CacheStatsSerializer(result).data)

    @action(detail=False, methods=['post'], url_path='warmup')
    def warmup(self, request):
        """
        POST /api/smartlink/cache/warmup/
        Warm all active SmartLinks. Admin only.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        cache_svc = self._get_cache_svc()
        warmed = cache_svc.warmup_all_active()
        return Response(WarmupResultSerializer({
            'warmed': warmed,
            'failed': 0,
            'skipped': 0,
            'duration_seconds': 0,
        }).data)

    @action(detail=False, methods=['post'], url_path='warmup-single')
    def warmup_single(self, request):
        """
        POST /api/smartlink/cache/warmup-single/
        Body: {"slug": "abc123"}
        Deep-warm a single SmartLink (cache + pool + targeting).
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = WarmupSingleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        slug = serializer.validated_data['slug']

        orchestrator = self._get_orchestrator()
        result = orchestrator.warm_smartlink_deep(slug)
        return Response(result)

    @action(detail=False, methods=['post'], url_path='predictive')
    def predictive_warmup(self, request):
        """
        POST /api/smartlink/cache/predictive/
        Run ML-based predictive warmup for high-traffic links. Admin only.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        orchestrator = self._get_orchestrator()
        result = orchestrator.run_predictive_warmup()
        return Response(result)

    @action(detail=False, methods=['delete'], url_path='flush')
    def flush(self, request):
        """
        DELETE /api/smartlink/cache/flush/
        Flush all SmartLink-related Redis keys. Admin only. DESTRUCTIVE.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        from django.core.cache import cache
        # Only flush SmartLink keys (not the entire cache)
        deleted = 0
        try:
            # Use cache.delete_pattern if using django-redis
            deleted = cache.delete_pattern('sl:*')
        except AttributeError:
            # Fallback: standard cache doesn't support patterns
            pass
        logger.warning(f"Cache flush by admin={request.user.username} deleted≈{deleted} keys")
        return Response({'message': f'Cache flushed. Approximately {deleted} keys removed.'})


# ─── SecurityViewSet ──────────────────────────────────────────────────────────

class SecurityViewSet(viewsets.ViewSet):
    """
    Rate limiter admin endpoints.

    GET    /api/smartlink/security/bans/        → List active IP bans
    POST   /api/smartlink/security/ban/         → Manually ban an IP
    POST   /api/smartlink/security/unban/       → Remove an IP ban
    GET    /api/smartlink/security/rate-status/ → Check rate limit status for an IP
    """
    permission_classes = [IsAuthenticated]

    def _get_limiter(self):
        from ..security.RateLimiter import SlidingWindowRateLimiter
        from ..constants import API_RATE_LIMIT_REDIRECT
        return SlidingWindowRateLimiter(
            limit=API_RATE_LIMIT_REDIRECT,
            window_seconds=60,
            ban_threshold=10,
        )

    @action(detail=False, methods=['get'], url_path='bans')
    def bans(self, request):
        """GET /api/smartlink/security/bans/ — List all active ban entries (admin only)."""
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        from django.core.cache import cache
        limiter = self._get_limiter()
        active_bans = []

        try:
            keys = cache.keys('rl:ban:*') or []
            for key in keys[:200]:
                ban_data = cache.get(key)
                if ban_data:
                    active_bans.append(ban_data)
        except Exception:
            pass

        return Response({
            'count': len(active_bans),
            'bans': RateLimitBanSerializer(active_bans, many=True).data,
        })

    @action(detail=False, methods=['post'], url_path='ban')
    def ban(self, request):
        """
        POST /api/smartlink/security/ban/
        Body: {"ip": "1.2.3.4", "duration_hours": 24, "reason": "..."}
        Admin-only: manually ban an IP.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ManualBanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = str(serializer.validated_data['ip'])
        hours = serializer.validated_data['duration_hours']
        reason = serializer.validated_data.get('reason', '')

        from django.core.cache import cache
        import hashlib
        ban_key = f"rl:ban:{hashlib.md5(ip.encode()).hexdigest()}"
        from django.utils import timezone
        import datetime
        banned_until = timezone.now() + datetime.timedelta(hours=hours)
        cache.set(ban_key, {
            'identifier': ip,
            'identifier_type': 'ip',
            'violation_count': 999,
            'banned_until': banned_until.isoformat(),
            'is_permanent': False,
            'reason': reason,
            'banned_by': request.user.username,
        }, timeout=hours * 3600)

        logger.warning(f"Manual IP ban: {ip} for {hours}h by {request.user.username}. Reason: {reason}")
        return Response({
            'message': f'{ip} banned for {hours} hours.',
            'banned_until': banned_until.isoformat(),
        })

    @action(detail=False, methods=['post'], url_path='unban')
    def unban(self, request):
        """
        POST /api/smartlink/security/unban/
        Body: {"ip": "1.2.3.4"}
        Admin-only: remove an IP ban.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ManualUnbanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = str(serializer.validated_data['ip'])

        from django.core.cache import cache
        import hashlib
        ban_key = f"rl:ban:{hashlib.md5(ip.encode()).hexdigest()}"
        rl_key = f"rl:{hashlib.md5(ip.encode()).hexdigest()}"
        cache.delete(ban_key)
        cache.delete(rl_key)

        logger.info(f"IP unbanned: {ip} by {request.user.username}")
        return Response({'message': f'{ip} has been unbanned.'})

    @action(detail=False, methods=['get'], url_path='rate-status')
    def rate_status(self, request):
        """
        GET /api/smartlink/security/rate-status/?ip=1.2.3.4
        Check current rate limit and ban status for an IP. Admin only.
        """
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)

        ip = request.query_params.get('ip', '').strip()
        if not ip:
            return Response({'detail': 'ip query param required.'}, status=400)

        from django.core.cache import cache
        import hashlib
        ban_key = f"rl:ban:{hashlib.md5(ip.encode()).hexdigest()}"
        rl_key = f"rl:{hashlib.md5(ip.encode()).hexdigest()}"

        ban_data = cache.get(ban_key)
        rl_data = cache.get(rl_key)

        return Response({
            'ip': ip,
            'is_banned': bool(ban_data),
            'ban_details': ban_data,
            'recent_request_count': len(rl_data or []),
        })


# ─── NotificationViewSet ──────────────────────────────────────────────────────

class NotificationViewSet(viewsets.ViewSet):
    """
    Publisher notification preference endpoints.

    GET  /api/smartlink/notifications/preferences/  → Get preferences
    PUT  /api/smartlink/notifications/preferences/  → Update preferences
    POST /api/smartlink/notifications/test/         → Send a test notification
    """
    permission_classes = [IsAuthenticated]

    PREFS_CACHE_PREFIX = 'notif_prefs:'

    def _get_prefs(self, user):
        from django.core.cache import cache
        key = f'{self.PREFS_CACHE_PREFIX}{user.pk}'
        cached = cache.get(key)
        if cached:
            return cached
        # Fall back to user profile if available
        profile = getattr(user, 'publisher_profile', None)
        if profile and hasattr(profile, 'notification_preferences'):
            prefs = profile.notification_preferences or {}
        else:
            prefs = {}
        return prefs

    def _save_prefs(self, user, prefs):
        from django.core.cache import cache
        key = f'{self.PREFS_CACHE_PREFIX}{user.pk}'
        cache.set(key, prefs, 86400 * 7)
        # Persist to profile if available
        profile = getattr(user, 'publisher_profile', None)
        if profile and hasattr(profile, 'notification_preferences'):
            type(profile).objects.filter(pk=profile.pk).update(
                notification_preferences=prefs
            )

    @action(detail=False, methods=['get'], url_path='preferences')
    def get_preferences(self, request):
        """GET /api/smartlink/notifications/preferences/"""
        prefs = self._get_prefs(request.user)
        serializer = NotificationPreferenceSerializer(data=prefs)
        # Use defaults for any missing keys
        default_data = NotificationPreferenceSerializer().fields
        merged = {field: prefs.get(field, f.initial) for field, f in default_data.items()}
        return Response(NotificationPreferenceSerializer(merged).data
                        if False else merged)  # return raw merged dict

    @action(detail=False, methods=['put', 'patch'], url_path='preferences/update')
    def update_preferences(self, request):
        """PUT /api/smartlink/notifications/preferences/update/"""
        serializer = NotificationPreferenceSerializer(
            data=request.data, partial=request.method == 'PATCH'
        )
        serializer.is_valid(raise_exception=True)
        prefs = self._get_prefs(request.user)
        prefs.update(serializer.validated_data)
        self._save_prefs(request.user, prefs)
        return Response({
            'message': 'Notification preferences updated.',
            'preferences': prefs,
        })

    @action(detail=False, methods=['post'], url_path='test')
    def test_notification(self, request):
        """
        POST /api/smartlink/notifications/test/
        Send a test notification through all configured channels.
        """
        from api.smartlink.services.notification.NotificationService import NotificationService
        svc = NotificationService()
        prefs = self._get_prefs(request.user)
        channel = request.data.get('channel', 'email')

        try:
            if channel == 'telegram':
                chat_id = prefs.get('telegram_chat_id', '')
                if not chat_id:
                    return Response(
                        {'detail': 'No Telegram chat ID configured.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                from django.conf import settings as dj_settings
                telegram_token = getattr(dj_settings, 'TELEGRAM_BOT_TOKEN', '')
                if not telegram_token:
                    return Response(
                        {'detail': 'TELEGRAM_BOT_TOKEN not configured in settings.'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                    )
                svc._send_telegram(
                    chat_id=chat_id,
                    token=telegram_token,
                    message=(
                        '✅ SmartLink test notification!\n'
                        'Your Telegram alerts are working correctly.'
                    ),
                )
            elif channel == 'slack':
                webhook = prefs.get('slack_webhook_url', '')
                if not webhook:
                    return Response(
                        {'detail': 'No Slack webhook URL configured.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                svc._send_slack(
                    webhook_url=webhook,
                    message='✅ SmartLink test notification! Your Slack alerts are working.',
                )
            else:
                svc._send_email(
                    user=request.user,
                    subject='SmartLink Test Notification',
                    message='This is a test notification from SmartLink.',
                )
            return Response({'message': f'Test notification sent via {channel}.'})

        except Exception as e:
            logger.error(f"Test notification failed: {e}")
            return Response(
                {'detail': f'Notification failed: {str(e)}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )
