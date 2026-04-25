# api/wallet/mixins.py
"""
Reusable mixins for views, viewsets, and models.
"""
import logging
from decimal import Decimal
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

logger = logging.getLogger("wallet.mixins")


# ── ViewSet Mixins ────────────────────────────────────────────

class WalletOwnerMixin:
    """Ensure queryset is filtered to current user's wallet."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(wallet__user=user)


class UserOwnedMixin:
    """Filter queryset by request.user."""

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff:
            return qs
        return qs.filter(user=user)


class StandardResponseMixin:
    """Wrap all responses in standard {success, data, error} format."""

    def success(self, data=None, status_code=200, message=""):
        return Response({"success": True, "data": data, "message": message}, status=status_code)

    def error(self, message, status_code=400, code=None):
        return Response({"success": False, "error": message, "code": code}, status=status_code)


class AuditMixin:
    """Log all write operations to AuditLog."""

    def perform_create(self, serializer):
        obj = serializer.save()
        self._audit("created", obj)
        return obj

    def perform_update(self, serializer):
        obj = serializer.save()
        self._audit("updated", obj)
        return obj

    def _audit(self, action: str, obj):
        try:
            from .audit_log import AuditLogger
            AuditLogger.log(
                action=action,
                user_id=self.request.user.id,
                target_type=obj.__class__.__name__.lower(),
                target_id=obj.pk,
                ip_address=self.request.META.get("REMOTE_ADDR", ""),
            )
        except Exception as e:
            logger.debug(f"AuditMixin log skip: {e}")


class CacheInvalidateMixin:
    """Invalidate wallet cache after write operations."""

    def perform_create(self, serializer):
        obj = serializer.save()
        self._invalidate(obj)
        return obj

    def perform_update(self, serializer):
        obj = serializer.save()
        self._invalidate(obj)
        return obj

    def _invalidate(self, obj):
        try:
            wallet_id = getattr(obj, "wallet_id", None) or getattr(getattr(obj, "wallet", None), "id", None)
            if wallet_id:
                from .cache_manager import WalletCacheManager
                WalletCacheManager.invalidate_wallet(wallet_id)
        except Exception:
            pass


class RateLimitMixin:
    """Apply rate limiting per action."""
    rate_limit_action = "api_global"

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.user.is_authenticated:
            from .rate_limiter import WalletRateLimiter
            allowed, remaining, _ = WalletRateLimiter.check(
                request.user.id, self.rate_limit_action
            )
            if not allowed:
                from rest_framework.exceptions import Throttled
                raise Throttled(detail=f"Rate limit exceeded for {self.rate_limit_action}.")


class SerializerContextMixin:
    """Inject extra context into serializers."""

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["wallet_user"] = self.request.user
        return ctx


class PaginatedResponseMixin:
    """Helper to return paginated responses cleanly."""

    def paginated_response(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


# ── Model Mixins ──────────────────────────────────────────────

class VersionedMixin(models.Model if False else object):
    """Add optimistic locking via version field."""

    def increment_version(self):
        """Increment version field atomically."""
        from django.db import models as djmodels
        type(self).objects.filter(pk=self.pk, version=self.version).update(
            version=djmodels.F("version") + 1
        )
        self.version += 1


class BalanceValidationMixin:
    """Clamp wallet balances to non-negative on save."""

    def clean_balances(self):
        zero = Decimal("0")
        for field in ["current_balance", "pending_balance", "frozen_balance",
                      "bonus_balance", "reserved_balance"]:
            val = getattr(self, field, zero) or zero
            if val < zero:
                setattr(self, field, zero)

    def save(self, *args, **kwargs):
        self.clean_balances()
        super().save(*args, **kwargs)
