"""viewsets/TenantViewSet.py"""
import logging
from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.apps import apps

logger = logging.getLogger(__name__)


class TenantViewSet(viewsets.ModelViewSet):
    """Manage multi-tenant organisations."""
    permission_classes = [permissions.IsAdminUser]
    filter_backends    = [filters.SearchFilter, filters.OrderingFilter]
    search_fields      = ['name', 'slug', 'domain']
    ordering_fields    = ['name', 'subscription_expires_at']
    ordering           = ['name']

    def get_queryset(self):
        Tenant = apps.get_model('tasks', 'Tenant')
        return Tenant.objects.prefetch_related('subscription_plan').all()

    def get_serializer_class(self):
        from api.tasks.serializers import TenantSerializer
        return TenantSerializer

    @action(detail=True, methods=['get'], url_path='usage')
    def usage(self, request, pk=None):
        """Return resource usage stats for this tenant."""
        tenant = self.get_object()
        return Response({
            'tenant_id': str(tenant.id),
            'name': tenant.name,
            'is_trial': tenant.is_trial,
            'max_users': tenant.max_users,
            'subscription_expires_at': tenant.subscription_expires_at,
        })

    @action(detail=True, methods=['post'], url_path='extend-trial')
    def extend_trial(self, request, pk=None):
        """Extend trial period by N days."""
        from datetime import timedelta
        from django.utils import timezone
        tenant = self.get_object()
        days = int(request.data.get('days', 7))
        base = tenant.subscription_expires_at or timezone.now()
        tenant.subscription_expires_at = base + timedelta(days=days)
        tenant.save(update_fields=['subscription_expires_at'])
        return Response({'extended_until': tenant.subscription_expires_at})
