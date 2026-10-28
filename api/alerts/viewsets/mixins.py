"""
alerts/viewsets/mixins.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEW FILE — DRY shared mixins for all ViewSets.

Previously every viewset had copy-pasted caching, filtering, and
throttling boilerplate. This file consolidates it once.

Mixins provided:
  1. CacheMixin          — wraps list() with cache_manager.CacheManager
  2. SelectorFilterMixin — wires alert_selectors.py to ?filter= query params
  3. ThrottlingMixin     — applies throttling.py throttle classes per action
  4. AuditLogMixin       — records every write action to audit log
  5. BulkActionMixin     — DRY bulk create/update/delete pattern
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from functools import wraps
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import PermissionDenied as _DjangoPermissionDenied
from django.http import Http404 as _Http404
from rest_framework.exceptions import APIException as _APIException

# Exceptions DRF already knows how to turn into proper 4xx responses.  Action methods
# that wrap their body in a blanket ``except Exception`` must re-raise these first,
# otherwise a missing object (Http404), a validation error or a permission error
# comes back to the client as HTTP 500.
PASSTHROUGH_EXCEPTIONS = (_Http404, _DjangoPermissionDenied, _APIException)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# 1. CacheMixin
# ─────────────────────────────────────────────────────────────────
class CacheMixin:
    """
    Cache the list() response using Django's cache backend.
    Uses alerts/cache_manager.py CacheManager when available,
    falls back to django.core.cache.cache directly.

    Subclass settings:
        cache_timeout_seconds = 300      # TTL
        cache_key_prefix      = 'vs'     # unique per viewset
    """
    cache_timeout_seconds = 300
    cache_key_prefix = "viewset"

    def _cache_version(self):
        """Per-prefix version counter. Bumping it (see _invalidate_cache)
        instantly makes every previously-generated cache key unreachable,
        without needing wildcard/pattern-delete support from the cache
        backend — works identically on locmem, redis, memcached, etc."""
        version_key = f"alerts:{self.cache_key_prefix}:version"
        version = cache.get(version_key)
        if version is None:
            version = 1
            cache.set(version_key, version, None)  # no expiry on the counter itself
        return version

    def _cache_key(self, request):
        qs = request.query_params.urlencode()
        tenant = getattr(request, "tenant_id", "global")
        version = self._cache_version()
        return f"alerts:{self.cache_key_prefix}:{tenant}:v{version}:{hash(qs)}"

    def list(self, request, *args, **kwargs):
        key = self._cache_key(request)
        cached = cache.get(key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(key, response.data, self.cache_timeout_seconds)
        return response

    def _invalidate_cache(self, pattern=None):
        """Call after write operations to bust the list cache.

        Bumps this viewset's cache version so every key generated from
        now on is a guaranteed miss (previously: this method only did
        anything when called WITH an explicit pattern AND a working
        cache_manager, but perform_create/update/destroy below never
        pass a pattern — making invalidation a silent no-op on every
        write). Stale entries under the old version simply expire via
        their existing TTL in the background.
        """
        version_key = f"alerts:{self.cache_key_prefix}:version"
        try:
            cache.incr(version_key)
        except ValueError:
            # incr() raises ValueError if the key doesn't exist yet
            cache.set(version_key, 2, None)

        # Best-effort: also attempt cache_manager pattern invalidation for
        # backends that support it, if an explicit pattern was given.
        if pattern:
            try:
                from api.alerts.cache_manager import get_cache_manager
                mgr = get_cache_manager()
                if mgr:
                    mgr.invalidate_pattern(pattern)
            except Exception:
                pass  # graceful fallback — version bump above already covers us

    def perform_create(self, serializer):
        obj = super().perform_create(serializer)
        self._invalidate_cache()
        return obj

    def perform_update(self, serializer):
        obj = super().perform_update(serializer)
        self._invalidate_cache()
        return obj

    def perform_destroy(self, instance):
        super().perform_destroy(instance)
        self._invalidate_cache()


# ─────────────────────────────────────────────────────────────────
# 2. SelectorFilterMixin
# ─────────────────────────────────────────────────────────────────
class SelectorFilterMixin:
    """
    Wires alert_selectors.py to URL query parameters.

    Previously the alert_selectors.py module had 6 selector classes
    with 40+ filter methods but was NEVER called from any viewset.

    Usage — declare in your ViewSet:
        selector_class = AlertRuleSelector   # from alert_selectors
        selector_param_map = {
            'severity': 'by_severity',       # ?severity=high → .by_severity('high')
            'active':   'active',            # ?active=1      → .active()
            'search':   'search',            # ?search=cpu    → .search('cpu')
        }
    """
    selector_class = None
    selector_param_map = {}

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.selector_class:
            return qs

        try:
            selector = self.selector_class(queryset=qs)
            result_qs = selector.get_queryset()
            for param, method_name in self.selector_param_map.items():
                value = self.request.query_params.get(param)
                if value is not None:
                    method = getattr(selector, method_name, None)
                    if method and callable(method):
                        if value in ('1', 'true', 'yes', ''):
                            result_qs = method()
                        else:
                            result_qs = method(value)
                        # Keep the selector's internal queryset in sync so the
                        # NEXT selector_param_map entry chains on top of this
                        # result, instead of re-filtering from the original qs.
                        selector.queryset = result_qs
            return result_qs
        except Exception as e:
            logger.warning("SelectorFilterMixin error: %s", e)
            return qs


# ─────────────────────────────────────────────────────────────────
# 3. ThrottlingMixin
# ─────────────────────────────────────────────────────────────────
class ThrottlingMixin:
    """
    Applies throttling.py throttle classes per action.

    Previously throttling.py had 8 throttle classes (AlertRateThrottle,
    AlertCreateRateThrottle, etc.) that were NEVER applied to any viewset.

    Provides sensible defaults — override in subclass if needed:
        throttle_map = {
            'list':    ['api.alerts.throttling.AlertRateThrottle'],
            'create':  ['api.alerts.throttling.AlertCreateRateThrottle'],
            'export':  ['api.alerts.throttling.ExportRateThrottle'],
        }
    """
    # Default throttle map; override per viewset
    throttle_map = {
        "list":   "api.alerts.throttling.AlertRateThrottle",
        "create": "api.alerts.throttling.AlertCreateRateThrottle",
    }

    def get_throttles(self):
        action = getattr(self, "action", None)
        throttle_path = self.throttle_map.get(action) if action else None
        if throttle_path:
            try:
                module_path, class_name = throttle_path.rsplit(".", 1)
                import importlib
                mod = importlib.import_module(module_path)
                ThrottleClass = getattr(mod, class_name)
                return [ThrottleClass()]
            except Exception:
                pass
        return super().get_throttles()


# ─────────────────────────────────────────────────────────────────
# 4. AuditLogMixin — already wired, DRY stub here
# ─────────────────────────────────────────────────────────────────
class AuditLogMixin:
    """
    Records write actions to the alerts audit trail.
    Uses integration/integ_audit_logs.py AuditLogger.
    """
    def _audit(self, action_name, obj=None, request=None):
        try:
            from api.alerts.integration.integ_audit_logs import AuditLogger, AuditEventType, AuditSeverity
            logger_inst = AuditLogger()
            logger_inst.log_event(
                event_type=AuditEventType.INTEGRATION_UPDATED,
                severity=AuditSeverity.LOW,
                integration_name=self.__class__.__name__,
                description=f"{action_name} by {getattr(request, 'user', 'unknown')}",
            )
        except Exception:
            pass

    def perform_create(self, serializer):
        obj = super().perform_create(serializer)
        self._audit("create", obj, self.request)
        return obj

    def perform_update(self, serializer):
        obj = super().perform_update(serializer)
        self._audit("update", obj, self.request)
        return obj

    def perform_destroy(self, instance):
        self._audit("delete", instance, self.request)
        super().perform_destroy(instance)


# ─────────────────────────────────────────────────────────────────
# 5. BulkActionMixin
# ─────────────────────────────────────────────────────────────────
class BulkActionMixin:
    """
    DRY bulk operations: create_many, update_many, delete_many.
    Avoids N+1 queries. Re-used by AlertRuleViewSet, AlertLogViewSet, etc.
    """
    def bulk_create(self, request, serializer_class=None):
        SerializerClass = serializer_class or self.get_serializer_class()
        items = request.data if isinstance(request.data, list) else request.data.get("items", [])
        serializer = SerializerClass(data=items, many=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        objects = serializer.save()
        return Response(
            {"created": len(objects), "items": SerializerClass(objects, many=True).data},
            status=status.HTTP_201_CREATED,
        )

    def bulk_delete(self, request, queryset=None):
        qs = queryset or self.get_queryset()
        ids = request.data.get("ids", [])
        if not ids:
            return Response({"error": "ids list required"}, status=status.HTTP_400_BAD_REQUEST)
        total, breakdown = qs.filter(pk__in=ids).delete()
        # total includes any CASCADE-deleted related objects (e.g. history
        # rows), which misrepresents how many of the requested IDs were
        # actually removed. Report the count for the queryset's own model
        # specifically, falling back to total only if the label is absent
        # (e.g. a queryset with zero matches, where breakdown is empty).
        model_label = qs.model._meta.label
        deleted = breakdown.get(model_label, total)
        return Response({"deleted": deleted, "breakdown": breakdown})

    def bulk_update_field(self, request, field_name, queryset=None):
        qs = queryset or self.get_queryset()
        ids = request.data.get("ids", [])
        value = request.data.get(field_name)
        if not ids or value is None:
            return Response(
                {"error": f"ids and {field_name} required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = qs.filter(pk__in=ids).update(**{field_name: value})
        return Response({"updated": updated, field_name: value})
