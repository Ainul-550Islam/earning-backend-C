# api/djoyalty/viewsets/advanced/TenantViewSet.py
"""
Djoyalty Tenant ViewSet -- NEW।
SaaS tenant management -- create, configure, monitor tenants।
Tenant model existed with no serializer or viewset -- entire SaaS admin layer was unreachable।
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from ...models.core import Tenant
from ...models.audit import AdminAuditLog, SystemConfig, MultiCurrencyRate, ProductCatalogRule
from ...serializers.TenantSerializer import (
    TenantSerializer, TenantAdminSerializer, TenantCreateSerializer,
)
from ...serializers.AuditSerializer import (
    AdminAuditLogSerializer, SystemConfigSerializer,
    MultiCurrencyRateSerializer, ProductCatalogRuleSerializer,
)
from ...permissions import IsLoyaltyAdmin
from ...pagination import DjoyaltyPagePagination
from ...mixins import DjoyaltyBaseViewSet


class TenantViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    """
    Super-admin management of tenants (SaaS layer):
    GET    /tenants/                -- list all tenants
    POST   /tenants/                -- create new tenant
    GET    /tenants/{id}/           -- tenant detail
    PUT    /tenants/{id}/           -- update tenant
    GET    /tenants/{id}/stats/     -- tenant usage stats
    GET    /tenants/{id}/audit-log/ -- tenant audit trail
    GET    /tenants/{id}/config/    -- tenant system config
    PATCH  /tenants/{id}/config/    -- update config key
    """
    permission_classes  = [IsLoyaltyAdmin]
    serializer_class    = TenantAdminSerializer
    pagination_class    = DjoyaltyPagePagination

    def get_queryset(self):
        return Tenant.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return TenantCreateSerializer
        return TenantAdminSerializer

    @action(detail=True, methods=['get'], url_path='stats')
    def stats(self, request, pk=None):
        """Tenant usage stats -- customer count, points in circulation, etc."""
        tenant = get_object_or_404(Tenant, pk=pk)
        from ...models.points import LoyaltyPoints
        from django.db.models import Sum, Count
        agg = LoyaltyPoints.objects.filter(customer__tenant=tenant).aggregate(
            total_balance=Sum('balance'),
            total_lifetime_earned=Sum('lifetime_earned'),
            total_lifetime_redeemed=Sum('lifetime_redeemed'),
            active_customers=Count('customer'),
        )
        return Response({
            'tenant': TenantSerializer(tenant).data,
            'customers': {
                'total': tenant.customers.count(),
                'active': tenant.customers.filter(is_active=True).count(),
            },
            'points': {
                'total_in_circulation': str(agg['total_balance'] or 0),
                'lifetime_earned': str(agg['total_lifetime_earned'] or 0),
                'lifetime_redeemed': str(agg['total_lifetime_redeemed'] or 0),
            },
            'earn_rules': tenant.earn_rules.filter(is_active=True).count(),
        })

    @action(detail=True, methods=['get'], url_path='audit-log')
    def audit_log(self, request, pk=None):
        """Tenant's admin audit trail."""
        tenant   = get_object_or_404(Tenant, pk=pk)
        category = request.query_params.get('category')
        severity = request.query_params.get('severity')
        qs = AdminAuditLog.objects.filter(tenant=tenant).order_by('-timestamp')
        if category:
            qs = qs.filter(action_category=category)
        if severity:
            qs = qs.filter(severity=severity)
        page = self.paginate_queryset(qs[:500])
        serializer = AdminAuditLogSerializer(page or qs[:50], many=True)
        return self.get_paginated_response(serializer.data) if page else Response(serializer.data)

    @action(detail=True, methods=['get', 'patch'], url_path='config')
    def config(self, request, pk=None):
        """Get or update tenant system config."""
        tenant = get_object_or_404(Tenant, pk=pk)

        if request.method == 'GET':
            qs         = SystemConfig.objects.filter(tenant=tenant).order_by('key')
            serializer = SystemConfigSerializer(qs, many=True)
            return Response(serializer.data)

        # PATCH -- update/create config key
        key   = request.data.get('key')
        value = request.data.get('value')
        if not key or value is None:
            return self.err('key and value required.')

        obj, created = SystemConfig.objects.update_or_create(
            tenant=tenant, key=key,
            defaults={
                'value': str(value),
                'updated_by': str(request.user),
            },
        )
        return Response(SystemConfigSerializer(obj).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class AdminAuditLogViewSet(DjoyaltyBaseViewSet, viewsets.ReadOnlyModelViewSet):
    """
    GET /audit-logs/            -- all logs (super-admin)
    GET /audit-logs/?customer=X -- logs for a customer
    GET /audit-logs/?category=X -- logs by category
    """
    permission_classes = [IsLoyaltyAdmin]
    serializer_class   = AdminAuditLogSerializer
    pagination_class   = DjoyaltyPagePagination

    def get_queryset(self):
        qs = AdminAuditLog.objects.all().select_related('customer').order_by('-timestamp')
        customer_id = self.request.query_params.get('customer')
        category    = self.request.query_params.get('category')
        severity    = self.request.query_params.get('severity')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        if category:
            qs = qs.filter(action_category=category)
        if severity:
            qs = qs.filter(severity=severity)
        return qs


class SystemConfigViewSet(DjoyaltyBaseViewSet, viewsets.ModelViewSet):
    """
    GET   /config/              -- list all config for current tenant
    POST  /config/              -- create config entry
    PUT   /config/{id}/         -- update
    DELETE /config/{id}/        -- delete
    POST  /config/bulk-set/     -- set multiple keys at once
    """
    permission_classes = [IsLoyaltyAdmin]
    serializer_class   = SystemConfigSerializer

    def get_queryset(self):
        # In multi-tenant: filter by request's tenant
        tenant_id = self.request.query_params.get('tenant_id')
        qs = SystemConfig.objects.all()
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs.order_by('key')

    @action(detail=False, methods=['post'], url_path='bulk-set')
    def bulk_set(self, request):
        """Set multiple config keys at once: {"keys": {"max_points_per_day": "5000", ...}}"""
        keys      = request.data.get('keys', {})
        tenant_id = request.data.get('tenant_id')
        if not isinstance(keys, dict):
            return self.err('keys must be an object.')
        updated = []
        for key, value in keys.items():
            obj, _ = SystemConfig.objects.update_or_create(
                tenant_id=tenant_id, key=key,
                defaults={'value': str(value), 'updated_by': str(request.user)},
            )
            updated.append(key)
        return Response({'status': 'updated', 'keys': updated})
