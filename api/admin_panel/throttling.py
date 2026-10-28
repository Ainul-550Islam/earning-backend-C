# api/admin_panel/throttling.py
"""
Custom throttle classes for admin_panel endpoints.
Rate limiting: per-user, per-IP, per-role, burst control.
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle, ScopedRateThrottle
from django.core.cache import cache


class AdminUserThrottle(UserRateThrottle):
    """Standard throttle for authenticated admin users."""
    scope = 'admin_user'
    THROTTLE_RATES = {'admin_user': '1000/hour'}

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f'admin_panel:throttle:user:{request.user.pk}'


class AdminBulkActionThrottle(UserRateThrottle):
    """Stricter throttle for bulk operations — prevent abuse."""
    scope = 'admin_bulk'
    THROTTLE_RATES = {'admin_bulk': '20/minute'}

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f'admin_panel:throttle:bulk:{request.user.pk}'


class AdminExportThrottle(UserRateThrottle):
    """Throttle for data exports — heavy DB operations."""
    scope = 'admin_export'
    THROTTLE_RATES = {'admin_export': '10/hour'}

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f'admin_panel:throttle:export:{request.user.pk}'


class AdminSearchThrottle(UserRateThrottle):
    """Throttle for admin search endpoints."""
    scope = 'admin_search'
    THROTTLE_RATES = {'admin_search': '100/minute'}

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f'admin_panel:throttle:search:{request.user.pk}'


class MaintenanceModeThrottle(AnonRateThrottle):
    """Throttle for public maintenance check endpoint."""
    scope = 'maintenance_check'
    THROTTLE_RATES = {'maintenance_check': '60/minute'}


class CriticalActionThrottle(UserRateThrottle):
    """Very strict throttle for critical actions — ban, failover, force-update."""
    scope = 'critical_action'
    THROTTLE_RATES = {'critical_action': '10/minute'}

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated:
            return None
        return f'admin_panel:throttle:critical:{request.user.pk}'


# ==================== THROTTLE RATES FOR SETTINGS ====================
ADMIN_THROTTLE_RATES = {
    'admin_user':       '1000/hour',
    'admin_bulk':       '20/minute',
    'admin_export':     '10/hour',
    'admin_search':     '100/minute',
    'maintenance_check':'60/minute',
    'critical_action':  '10/minute',
}