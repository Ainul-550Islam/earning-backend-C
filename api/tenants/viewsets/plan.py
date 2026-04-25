"""
Plan Viewsets

This module contains viewsets for plan-related models including
Plan, PlanFeature, PlanUpgrade, PlanUsage, and PlanQuota.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q

from ..models.plan import Plan, PlanFeature, PlanUpgrade, PlanUsage, PlanQuota
from ..serializers.plan import (
    PlanSerializer, PlanCreateSerializer, PlanUpdateSerializer,
    PlanFeatureSerializer, PlanUpgradeSerializer, PlanUsageSerializer,
    PlanQuotaSerializer
)
from ..services import PlanService, PlanUsageService


class PlanViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subscription plans.
    """
    queryset = Plan.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['plan_type', 'is_active', 'is_public', 'is_featured']
    search_fields = ['name', 'slug', 'description']
    ordering_fields = ['sort_order', 'name', 'price_monthly']
    ordering = ['sort_order', 'name']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return PlanCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return PlanUpdateSerializer
        return PlanSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny]  # Plans are public
        elif self.action == 'create':
            return [permissions.IsAdminUser]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate plan."""
        plan = self.get_object()
        plan.is_active = True
        plan.save()
        
        return Response({'message': 'Plan activated successfully'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate plan."""
        plan = self.get_object()
        plan.is_active = False
        plan.save()
        
        return Response({'message': 'Plan deactivated successfully'}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def available(self, request):
        """Get available plans for upgrade."""
        tenant_id = request.query_params.get('tenant_id')
        if tenant_id:
            # Get plans available for specific tenant
            from ..models import Tenant
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                plans = PlanService.get_available_plans(tenant)
            except Tenant.DoesNotExist:
                return Response(
                    {'error': 'Tenant not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get all public active plans
            plans = Plan.objects.filter(is_active=True, is_public=True)
        
        serializer = PlanSerializer(plans, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def compare(self, request):
        """Compare multiple plans."""
        plan_ids = request.query_params.getlist('plan_ids')
        
        if not plan_ids:
            return Response(
                {'error': 'plan_ids parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            plans = Plan.objects.filter(id__in=plan_ids)
            comparison = PlanService.get_plan_comparison(plans)
            return Response(comparison, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def usage_stats(self, request, pk=None):
        """Get usage statistics for plan."""
        plan = self.get_object()
        
        # Get all tenants on this plan
        from ..models import Tenant
        tenants = Tenant.objects.filter(plan=plan)
        
        stats = {
            'total_tenants': tenants.count(),
            'active_tenants': tenants.filter(status='active').count(),
            'trial_tenants': tenants.filter(status='trial').count(),
            'suspended_tenants': tenants.filter(status='suspended').count(),
        }
        
        return Response(stats, status=status.HTTP_200_OK)


class PlanFeatureViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plan features.
    """
    serializer_class = PlanFeatureSerializer
    queryset = PlanFeature.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['feature_type', 'is_active', 'is_public', 'category']
    search_fields = ['name', 'key', 'description']
    ordering_fields = ['category', 'sort_order', 'name']
    ordering = ['category', 'sort_order', 'name']
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAdminUser]


class PlanUpgradeViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plan upgrades.
    """
    serializer_class = PlanUpgradeSerializer
    queryset = PlanUpgrade.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'from_plan', 'to_plan']
    search_fields = ['reason', 'notes']
    ordering_fields = ['upgraded_at']
    ordering = ['-upgraded_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        if self.request.user.is_superuser:
            return PlanUpgrade.objects.all()
        return PlanUpgrade.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve plan upgrade request."""
        upgrade = self.get_object()
        notes = request.data.get('notes')
        
        if upgrade.status != 'requested':
            return Response(
                {'error': 'Upgrade request is not in requested status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        upgrade.approve(request.user, notes)
        return Response({'message': 'Upgrade approved'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject plan upgrade request."""
        upgrade = self.get_object()
        reason = request.data.get('reason')
        
        if upgrade.status != 'requested':
            return Response(
                {'error': 'Upgrade request is not in requested status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        upgrade.reject(request.user, reason)
        return Response({'message': 'Upgrade rejected'}, status=status.HTTP_200_OK)


class PlanUsageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing plan usage data.
    """
    serializer_class = PlanUsageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'period', 'period_start', 'period_end']
    search_fields = ['tenant__name']
    ordering_fields = ['period_start', 'period_end']
    ordering = ['-period_start']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        if self.request.user.is_superuser:
            return PlanUsage.objects.all()
        return PlanUsage.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['get'])
    def breakdown(self, request, pk=None):
        """Get detailed usage breakdown."""
        usage = self.get_object()
        
        # Get detailed breakdown by metric
        breakdown = {
            'api_calls': {
                'used': usage.api_calls_used,
                'limit': usage.api_calls_limit,
                'percentage': usage.api_calls_percentage,
                'remaining': max(0, usage.api_calls_limit - usage.api_calls_used),
            },
            'storage': {
                'used': float(usage.storage_used_gb),
                'limit': usage.storage_limit_gb,
                'percentage': usage.storage_percentage,
                'remaining': max(0, usage.storage_limit_gb - usage.storage_used_gb),
            },
            'users': {
                'used': usage.users_used,
                'limit': usage.users_limit,
                'percentage': usage.users_percentage,
                'remaining': max(0, usage.users_limit - usage.users_used),
            },
            'over_limit_metrics': [],
        }
        
        # Check for overages
        for metric_name in ['api_calls', 'storage', 'users']:
            if usage.is_over_limit(metric_name):
                breakdown['over_limit_metrics'].append(metric_name)
        
        return Response(breakdown, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get usage summary for all tenants."""
        if not self.request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        summary = PlanUsageService.get_tenant_usage_summary()
        return Response(summary, status=status.HTTP_200_OK)


class PlanQuotaViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing plan quotas.
    """
    serializer_class = PlanQuotaSerializer
    queryset = PlanQuota.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['plan', 'feature_key', 'quota_type']
    search_fields = ['feature_key', 'display_name']
    ordering_fields = ['plan', 'feature_key']
    ordering = ['plan', 'feature_key']
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAdminUser]
    
    @action(detail=True, methods=['post'])
    def test_quota(self, request, pk=None):
        """Test quota with given usage value."""
        quota = self.get_object()
        test_value = request.data.get('test_value')
        
        if test_value is None:
            return Response(
                {'error': 'test_value parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            test_value = float(test_value)
        except ValueError:
            return Response(
                {'error': 'test_value must be a number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = {
            'is_over_limit': quota.is_over_limit(test_value),
            'should_warn': quota.should_warn(test_value),
            'overage_cost': quota.calculate_overage_cost(test_value),
        }
        
        return Response(result, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def calculate_overage_cost(self, request, pk=None):
        """Calculate overage cost for current usage."""
        quota = self.get_object()
        current_usage = request.data.get('current_usage')
        
        if current_usage is None:
            return Response(
                {'error': 'current_usage parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            current_usage = float(current_usage)
        except ValueError:
            return Response(
                {'error': 'current_usage must be a number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        overage_cost = quota.calculate_overage_cost(current_usage)
        
        return Response({
            'overage_cost': float(overage_cost),
            'current_usage': current_usage,
            'is_over_limit': quota.is_over_limit(current_usage),
        }, status=status.HTTP_200_OK)
