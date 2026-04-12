# api/offer_inventory/middleware.py
import logging
from django.utils import timezone
from django.core.cache import cache
from django.http import JsonResponse

logger = logging.getLogger(__name__)


class OfferInventoryMiddleware:
    """
    Offer Inventory-র জন্য global middleware।
    1. Maintenance mode check
    2. IP blacklist check (fast cache)
    3. Request logging
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # শুধু offer_inventory URL-এ apply
        if not request.path.startswith('/api/offer-inventory/'):
            return self.get_response(request)

        # 1. Maintenance mode
        if self._is_maintenance(request):
            return JsonResponse({
                'success': False,
                'message': 'সিস্টেম রক্ষণাবেক্ষণে আছে। অনুগ্রহ করে পরে চেষ্টা করুন।',
                'code': 'maintenance_mode',
            }, status=503)

        # 2. IP blacklist fast-check
        ip = self._get_ip(request)
        if self._is_ip_blocked(ip):
            logger.warning(f'Blocked IP attempted access: {ip}')
            return JsonResponse({
                'success': False,
                'message': 'Access denied।',
                'code': 'ip_blocked',
            }, status=403)

        # 3. Rate limit header
        request.META['OFFER_INV_IP']  = ip
        request.META['OFFER_INV_TIME'] = timezone.now()

        response = self.get_response(request)

        # 4. Add security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options']        = 'DENY'

        return response

    def _get_ip(self, request) -> str:
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

    def _is_maintenance(self, request) -> bool:
        cache_key = 'maintenance_mode:offer_inventory'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from .models import MaintenanceMode
            mode = MaintenanceMode.objects.filter(
                is_active=True
            ).first()
            if not mode:
                cache.set(cache_key, False, 60)
                return False

            # Whitelist check
            ip = self._get_ip(request)
            if ip in mode.whitelist_ips:
                return False

            cache.set(cache_key, True, 60)
            return True
        except Exception:
            return False

    def _is_ip_blocked(self, ip: str) -> bool:
        if not ip:
            return False
        cache_key = f'ip_blocked:{ip}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            from .models import BlacklistedIP
            from django.db.models import Q
            blocked = BlacklistedIP.objects.filter(
                ip_address=ip
            ).filter(
                Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
            ).exists()
            cache.set(cache_key, blocked, 300)
            return blocked
        except Exception:
            return False


class AuditLogMiddleware:
    """
    Write operations-এ audit log।
    POST/PUT/PATCH/DELETE → log।
    """
    SKIP_PATHS = ['/api/offer-inventory/health/', '/api/offer-inventory/postback/']
    LOG_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (request.method in self.LOG_METHODS and
                request.path.startswith('/api/offer-inventory/') and
                request.path not in self.SKIP_PATHS and
                hasattr(request, 'user') and request.user.is_authenticated and
                response.status_code < 400):
            try:
                from .models import AuditLog
                AuditLog.objects.create(
                    user=request.user,
                    action=f'{request.method} {request.path}',
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    metadata={'status_code': response.status_code},
                )
            except Exception as e:
                logger.error(f'AuditLog error: {e}')

        return response
