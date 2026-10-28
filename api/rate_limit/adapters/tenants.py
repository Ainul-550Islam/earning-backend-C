# api/rate_limit/adapters/tenants.py
"""
Tenants System ↔ Rate Limit Adapter
======================================
Covers: per-tenant API quota, plan-based limits, tenant export.

Usage in api/tenants/viewsets/settings.py:
    from api.rate_limit.adapters.tenants import TenantsRateLimitAdapter

    class TenantSettingsViewSet(viewsets.ModelViewSet):
        def list(self, request, *args, **kwargs):
            TenantsRateLimitAdapter.check_api_call(
                request=request,
                tenant=request.tenant,
            ).raise_if_blocked()
            ...
"""

import logging
from api.rate_limit.integration_service import RateLimitIntegrationService, RateLimitResult

logger = logging.getLogger('rate_limit.adapters.tenants')


class TenantsRateLimitAdapter:
    """Adapter for api/tenants system."""

    @staticmethod
    def check_api_call(request, tenant=None) -> RateLimitResult:
        """
        Check per-tenant API quota.
        Where to call:
            api/tenants/viewsets/settings.py
            api/tenants/viewsets/ → all tenant viewsets
        """
        tenant = tenant or getattr(request, 'tenant', None)
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'tenant_api_call',
            request=request,
            user=user,
            tenant=tenant,
        )

    @staticmethod
    def check_export(request, tenant=None) -> RateLimitResult:
        """
        Check before data export (expensive operation).
        Where to call:
            api/tenants/ → export endpoints
        """
        tenant = tenant or getattr(request, 'tenant', None)
        user = getattr(request, 'user', None)
        return RateLimitIntegrationService.check(
            'tenant_export',
            request=request,
            user=user,
            tenant=tenant,
        )

    @staticmethod
    def on_plan_changed(tenant, plan_name: str, api_quota: int = 0) -> bool:
        """
        Sync rate limits when tenant changes plan.
        Where to call:
            api/tenants/ → plan upgrade/downgrade signal
            api/tenants/models_improved.py → on plan change
        """
        return RateLimitIntegrationService.sync_tenant_limits(
            tenant=tenant,
            plan_name=plan_name,
            api_quota=api_quota,
        )

    @staticmethod
    def get_tenant_usage(tenant) -> dict:
        """
        Get current rate limit usage for a tenant.
        Where to call:
            api/tenants/viewsets/settings.py → tenant dashboard
            api/admin_panel/ → tenant management
        """
        try:
            from api.rate_limit.models import RateLimitLog, RateLimitConfig
            from django.utils import timezone
            from datetime import timedelta

            now = timezone.now()
            configs = RateLimitConfig.objects.filter(tenant=tenant, is_active=True)
            today = RateLimitLog.objects.filter(
                config__in=configs,
                timestamp__gte=now - timedelta(days=1),
            )
            return {
                'tenant_id': getattr(tenant, 'id', None),
                'active_configs': configs.count(),
                'requests_today': today.count(),
                'blocked_today': today.filter(status='blocked').count(),
            }
        except Exception as e:
            logger.error(f'get_tenant_usage error: {e}')
            return {'error': str(e)}
