"""
tenant.py — Tenant resolution utilities for the localization module.

Architecture:
  - LocalizationConfig.tenant_id is the tenant key.
  - Global/shared models (Language, Country, Currency, Timezone, City,
    TranslationKey, Translation, ExchangeRate) are read-only reference data
    shared across ALL tenants — like a CDN. No isolation needed.
  - Per-tenant models (LocalizationConfig, TranslationRequest, MissingTranslation,
    UserLanguagePreference, LocalizedContent, LocalizedSEO, LocalizedImage,
    TranslationScreenshot, WebhookRegistration, WebhookDeliveryLog,
    TranslationMemory, TranslationGlossary, LocalizationInsight,
    TranslationCoverage, UserLanguagePreference) are scoped per tenant.

Tenant resolution order:
  1. request.tenant_id  (set by upstream TenantMiddleware / api.tenants)
  2. request.user.profile.tenant_id  (if user model has a profile)
  3. X-Tenant-ID header  (fallback for API clients)
  4. None  (superuser/admin sees all)
"""
from __future__ import annotations
import logging
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_TENANT_HEADER = 'HTTP_X_TENANT_ID'
_TENANT_ATTR   = 'tenant_id'          # attribute TenantMiddleware sets on request


def get_tenant_id(request) -> Optional[str]:
    """
    Resolve tenant_id from a DRF/Django request.
    Returns None for superusers (they see everything).
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return None

    # Superusers are not tenant-scoped
    if request.user.is_superuser:
        return None

    # 1. Upstream middleware already resolved it
    tid = getattr(request, _TENANT_ATTR, None)
    if tid:
        return tid

    # 2. User profile (works when api.tenants is present)
    profile = getattr(request.user, 'profile', None)
    if profile:
        tid = getattr(profile, 'tenant_id', None) or getattr(profile, 'tenant', None)
        if tid:
            return str(tid)

    # 3. X-Tenant-ID header (API clients, service-to-service)
    tid = request.META.get(_TENANT_HEADER)
    if tid:
        return tid

    return None


def get_tenant_config(tenant_id: str):
    """
    Fetch LocalizationConfig for a tenant. Returns None if not found.
    Uses per-process cache — invalidated on config save via signal.
    """
    if not tenant_id:
        return None
    try:
        from api.localization.models.settings import LocalizationConfig
        return LocalizationConfig.objects.select_related(
            'default_language', 'fallback_language', 'default_currency'
        ).get(tenant_id=tenant_id, is_active=True)
    except Exception:
        return None


class TenantQuerysetMixin:
    """
    Mixin for ModelViewSet / ReadOnlyModelViewSet.

    Subclasses set `tenant_field` to the model FK/CharField pointing
    to the tenant scope. Defaults are handled per-model type:

      - Models with a direct `tenant_id` CharField → filter by that
      - Models linked via a FK to LocalizationConfig → filter via that FK
      - Per-user models (UserLanguagePreference) → filter by request.user

    Usage:
        class MissingTranslationViewSet(TenantQuerysetMixin, viewsets.ModelViewSet):
            tenant_field = 'tenant_id'          # direct field
            # OR
            tenant_field = 'config__tenant_id'  # via FK

    The mixin wraps get_queryset() — subclasses still define their own
    get_queryset() and call super(); the mixin applies .filter() on top.
    """
    tenant_field: str = 'tenant_id'
    _skip_tenant_filter: bool = False   # set True on global/shared models

    def _apply_tenant_filter(self, qs):
        if self._skip_tenant_filter:
            return qs
        tenant_id = get_tenant_id(self.request)
        if tenant_id is None:
            return qs  # superuser — unfiltered
        return qs.filter(**{self.tenant_field: tenant_id})

    def get_queryset(self):
        qs = super().get_queryset()
        return self._apply_tenant_filter(qs)

    def perform_create(self, serializer):
        """Auto-stamp tenant_id on create if the model has a direct field."""
        tenant_id = get_tenant_id(self.request)
        kwargs = {}
        if tenant_id and self.tenant_field == 'tenant_id':
            kwargs['tenant_id'] = tenant_id
        serializer.save(**kwargs)
