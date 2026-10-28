"""
middleware_tenant.py — Lightweight tenant middleware for the localization module.

Sits in front of LocalizationMiddleware. Resolves tenant_id from:
  1. Subdomain:  acme.yourapp.com → tenant_id = "acme"
  2. X-Tenant-ID header
  3. JWT claim  (if djangorestframework-simplejwt is installed)

Sets request.tenant_id so TenantQuerysetMixin and downstream code
can call get_tenant_id(request) without hitting the DB each time.
"""
from __future__ import annotations
import logging
import re

logger = logging.getLogger(__name__)

# Subdomains to ignore — these are NOT tenant identifiers
_IGNORED_SUBDOMAINS = frozenset([
    'www', 'api', 'app', 'admin', 'static',
    'media', 'mail', 'smtp', 'localhost',
])

# Override in settings: LOCALIZATION_TENANT_DOMAIN = "yourapp.com"
_DEFAULT_ROOT_DOMAIN = 'yourapp.com'


def _subdomain_from_host(host: str, root_domain: str) -> str | None:
    host = host.split(':')[0].lower()  # strip port
    if host.endswith('.' + root_domain):
        sub = host[: -(len(root_domain) + 1)]
        if sub and sub not in _IGNORED_SUBDOMAINS:
            return sub
    return None


def _tenant_from_jwt(request) -> str | None:
    """Extract tenant_id from JWT token claim without full auth."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    if not auth_header.startswith('Bearer '):
        return None
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        token = AccessToken(auth_header.split(' ', 1)[1])
        return str(token.get('tenant_id', '')) or None
    except Exception:
        return None


class TenantMiddleware:
    """
    Resolves tenant_id early in the request cycle and stores it on request.

    Add BEFORE LocalizationMiddleware in settings.MIDDLEWARE:

        MIDDLEWARE = [
            'localization.middleware_tenant.TenantMiddleware',
            'localization.middleware.LocalizationMiddleware',
            ...
        ]
    """

    def __init__(self, get_response):
        self.get_response = get_response
        from django.conf import settings
        self.root_domain = getattr(
            settings, 'LOCALIZATION_TENANT_DOMAIN', _DEFAULT_ROOT_DOMAIN
        )
        self.header_name = getattr(
            settings, 'LOCALIZATION_TENANT_HEADER', 'HTTP_X_TENANT_ID'
        )

    def __call__(self, request):
        request.tenant_id = self._resolve(request)
        if request.tenant_id:
            logger.debug('Tenant resolved: %s', request.tenant_id)
        return self.get_response(request)

    def _resolve(self, request) -> str | None:
        # 1. Subdomain
        host = request.META.get('HTTP_HOST', '')
        tenant = _subdomain_from_host(host, self.root_domain)
        if tenant:
            return tenant

        # 2. X-Tenant-ID header
        tenant = request.META.get(self.header_name)
        if tenant:
            return tenant.strip()

        # 3. JWT claim
        tenant = _tenant_from_jwt(request)
        if tenant:
            return tenant

        return None
