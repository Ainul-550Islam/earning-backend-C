# api/djoyalty/mixins.py
"""
Djoyalty — ViewSet mixins।
Tenant isolation, audit logging, customer resolution, response helpers।

DRY FIX (v3):
  Previously 55 viewset methods repeated:
    customer = getattr(request, 'loyalty_customer', None)
    if not customer:
        customer_id = request.data.get('customer_id') or request.query_params.get('customer_id')
        customer = get_object_or_404(Customer, pk=customer_id)

  And 72 methods repeated:
    if not customer:
        return Response({'error': 'Customer not found'}, status=404)

  And every response used a different Response() inline pattern।

  NEW: DjoyaltyBaseViewSet consolidates all of this into reusable methods।
  Every viewset that handles customer data MUST inherit DjoyaltyBaseViewSet
  instead of (or in addition to) DjoyaltyTenantMixin।

AUDIT FIX (2.5): DjoyaltyTenantMixin.get_queryset() previously used
  Q(tenant=tenant) | Q(tenant__isnull=True)  # BEFORE (removed)
which leaked orphaned/unassigned records to every tenant.  The filter
now uses Q(is_global=True) which only matches records explicitly flagged
as cross-tenant by an admin.  `is_global` is defined in TenantMixin
(abstracts.py) and propagates to all concrete models via LoyaltyBaseModel.

  Before (data-leak risk):
  # qs.filter(Q(tenant=tenant) | Q(tenant__isnull=True))  # BEFORE (removed)

  After (safe, explicit):
    qs.filter(Q(tenant=tenant) | Q(is_global=True))   # model has is_global
    qs.filter(tenant=tenant)                            # model lacks is_global
"""
import logging
from typing import Optional, Tuple, Any
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# EXISTING MIXINS (backward compatible — logic preserved, filter fixed)
# ═══════════════════════════════════════════════════════════════════════════════

class DjoyaltyTenantMixin:
    """
    Multi-tenant queryset filtering mixin।
    Request এ tenant থাকলে queryset tenant-filtered হবে।

    AUDIT FIX (2.5): tenant__isnull=True replaced with is_global=True.
    Only models that have the is_global field (via TenantMixin / LoyaltyBaseModel)
    get the cross-tenant visibility path.  Models without is_global get a
    strict tenant=tenant filter — no silent leakage.
    """

    def get_tenant(self):
        return getattr(self.request, 'tenant', None)

    def get_queryset(self):
        qs     = super().get_queryset()
        tenant = self.get_tenant()
        if tenant is not None:
            if hasattr(qs.model, 'tenant'):
                from django.db.models import Q
                if hasattr(qs.model, 'is_global'):
                    # AUDIT FIX 2.5: explicit global flag — no null-leak.
                    qs = qs.filter(Q(tenant=tenant) | Q(is_global=True))
                else:
                    # Model has tenant FK but no is_global field
                    # (e.g. legacy model not using TenantMixin).
                    # Strict filter: only this tenant's records.
                    qs = qs.filter(tenant=tenant)
        return qs

    def perform_create(self, serializer):
        tenant = self.get_tenant()
        if tenant and hasattr(serializer.Meta.model, 'tenant'):
            serializer.save(tenant=tenant)
        else:
            serializer.save()


class DjoyaltyAuditMixin:
    """Audit logging mixin — create/update/delete events log করে।"""

    def perform_create(self, serializer):
        obj = serializer.save()
        self._log_action('created', obj)
        return obj

    def perform_update(self, serializer):
        obj = serializer.save()
        self._log_action('updated', obj)
        return obj

    def perform_destroy(self, instance):
        self._log_action('deleted', instance)
        instance.delete()

    def _log_action(self, action: str, obj):
        user = getattr(self.request, 'user', None)
        logger.info(
            '[DjoyaltyAudit] %s %s id=%s by user=%s',
            action, type(obj).__name__,
            getattr(obj, 'id', '?'),
            str(user) if user else 'anonymous',
        )


class DjoyaltyReadOnlyMixin:
    """Read-only actions only — no create/update/delete।"""
    http_method_names = ['get', 'head', 'options']


class DjoyaltyBulkActionMixin:
    """Bulk action support for admin ViewSets।"""

    def bulk_deactivate(self, request, queryset):
        return queryset.update(is_active=False)

    def bulk_activate(self, request, queryset):
        return queryset.update(is_active=True)


class DjoyaltyCachedMixin:
    """Response caching mixin for read-heavy endpoints।"""
    cache_timeout = 300

    def _get_cache_key(self, request, view_name: str = '') -> str:
        from .utils import build_cache_key
        tenant_id = getattr(getattr(request, 'tenant', None), 'id', 'global')
        return build_cache_key('djoyalty', view_name, tenant_id, request.query_params.urlencode())


# ═══════════════════════════════════════════════════════════════════════════════
# DjoyaltyBaseViewSet  (DRY FIX v3)
# ═══════════════════════════════════════════════════════════════════════════════

class DjoyaltyBaseViewSet:
    """
    Base mixin for all Djoyalty ViewSets।
    Provides: customer resolution, response helpers, tenant helpers।

    DRY IMPACT:
      get_customer()       → eliminates 55 repeated customer-resolve blocks
      require_customer()   → eliminates 72 repeated 'if not customer: return 404'
      ok() / err()         → eliminates 200+ inline Response({'error': ...}) calls
      from_service()       → eliminates repeated service-result-to-response bridges
      get_tenant()         → consistent tenant access without getattr(request,…) scatter
    """

    # ── Customer resolution ────────────────────────────────────────────────────

    def get_customer(self, request, *, lookup_in_data: bool = True,
                     lookup_in_params: bool = True):
        """
        DRY: Resolve customer from request in one call।

        Previously each viewset repeated this block 1–3 times:
            customer = getattr(request, 'loyalty_customer', None)
            if not customer:
                customer_id = request.data.get('customer_id')
                customer = get_object_or_404(Customer, pk=customer_id)

        Now: customer = self.get_customer(request)

        Returns Customer instance or None।
        """
        # 1. Fastest path — already resolved by middleware
        customer = getattr(request, 'loyalty_customer', None)
        if customer:
            return customer

        # 2. Look up from request body (POST/PATCH)
        customer_id = None
        if lookup_in_data and hasattr(request, 'data'):
            customer_id = request.data.get('customer_id')

        # 3. Look up from query params (GET)
        if not customer_id and lookup_in_params and hasattr(request, 'query_params'):
            customer_id = request.query_params.get('customer_id')

        if not customer_id:
            return None

        try:
            from .models.core import Customer
            return Customer.objects.get(pk=customer_id, is_active=True)
        except Exception:
            return None

    def require_customer(
        self, request, *, lookup_in_data: bool = True, lookup_in_params: bool = True
    ) -> Tuple[Any, Optional[Response]]:
        """
        DRY: Get customer or return an error response।

        Previously 72 methods repeated:
            if not customer:
                return Response({'error': 'Customer not found'}, status=404)

        Now:
            customer, err = self.require_customer(request)
            if err: return err

        Returns (customer, None) on success।
        Returns (None, error_Response) on failure।
        """
        customer = self.get_customer(request, lookup_in_data=lookup_in_data,
                                     lookup_in_params=lookup_in_params)
        if customer:
            return customer, None
        from .response_helpers import DjoyaltyResponse
        if not self._has_customer_id(request, lookup_in_data, lookup_in_params):
            return None, DjoyaltyResponse.customer_required()
        return None, DjoyaltyResponse.customer_not_found()

    def _has_customer_id(self, request, lookup_in_data: bool, lookup_in_params: bool) -> bool:
        if lookup_in_data and hasattr(request, 'data') and request.data.get('customer_id'):
            return True
        if lookup_in_params and hasattr(request, 'query_params') and request.query_params.get('customer_id'):
            return True
        return False

    # ── Response helpers ───────────────────────────────────────────────────────

    def ok(self, data=None, http_status: int = 200) -> Response:
        """DRY: Successful response。Replaces: return Response(data, status=200)"""
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.ok(data, http_status=http_status)

    def created(self, data=None) -> Response:
        """DRY: 201 Created response。"""
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.created(data)

    def err(self, message: str, http_status: int = 400,
            code: Optional[str] = None) -> Response:
        """DRY: Error response。Replaces: return Response({'error': message}, status=400)"""
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.err(message, http_status=http_status, code=code)

    def not_found(self, message: str = 'Not found.') -> Response:
        """DRY: 404 response。"""
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.not_found(message)

    def forbidden(self, message: str = 'Access denied.') -> Response:
        """DRY: 403 response。"""
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.forbidden(message)

    def from_service(self, result, ok_status: int = 200,
                     err_status: int = 400) -> Response:
        """
        DRY: Convert service result dict to Response in one call。
        Replaces:
            if not result['success']:
                return Response({'error': result['error']}, status=400)
            return Response(result)
        """
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.from_service(result, ok_status=ok_status,
                                             err_status=err_status)

    def from_service_created(self, result) -> Response:
        """DRY: Service result → 201 on success, 400 on failure。"""
        from .response_helpers import DjoyaltyResponse
        return DjoyaltyResponse.from_service_created(result)

    # ── Tenant helper ──────────────────────────────────────────────────────────

    def get_tenant(self):
        """
        Get tenant from request।
        Safe even if no request attribute।
        Also respects ?tenant_id= query param for admin endpoints।
        """
        # Direct request attribute (set by middleware)
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            return tenant
        # Admin: explicit tenant_id query param
        tid = getattr(self.request, 'query_params', {}).get('tenant_id')
        if tid:
            try:
                from .models.core import Tenant
                return Tenant.objects.get(pk=tid)
            except Exception:
                pass
        return None
