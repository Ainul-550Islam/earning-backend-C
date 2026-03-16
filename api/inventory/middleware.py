"""middleware.py – Inventory-related middleware."""
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class InventoryContextMiddleware(MiddlewareMixin):
    """
    Attaches a lazy-loading inventory helper to request.
    Avoids DB queries on non-inventory pages.

    Usage in templates: {{ request.user_inventory_count }}
    """

    def process_request(self, request):
        request._user_inventory_count = None

    @property
    def user_inventory_count(self):
        if not hasattr(self, "_request"):
            return 0
        if self._request._user_inventory_count is None and self._request.user.is_authenticated:
            from .models import UserInventory
            from .choices import InventoryStatus
            self._request._user_inventory_count = UserInventory.objects.filter(
                user=self._request.user,
                status__in=[InventoryStatus.DELIVERED, InventoryStatus.PENDING],
            ).count()
        return self._request._user_inventory_count or 0
