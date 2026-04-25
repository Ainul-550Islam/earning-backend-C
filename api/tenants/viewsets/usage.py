"""
Usage ViewSets

This module contains viewsets for usage tracking operations including
plan usage, quota monitoring, and analytics.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

from ..models.plan import PlanUsage, PlanQuota
from ..serializers.plan import PlanUsageSerializer, PlanQuotaSerializer
from ..viewsets.base import BaseTenantRelatedViewSet


class PlanUsageViewSet(BaseTenantRelatedViewSet):
    """
    ViewSet for plan usage operations.
    
    Provides endpoints for:
    - Usage tracking and monitoring
    - Usage analytics and reporting
    - Quota management
    - Usage alerts
    """
    
    queryset = PlanUsage.objects.all()
    serializer_class = PlanUsageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['period', 'quota_key', 'is_over_limit']
    
    @action(detail=True, methods=['post'])
    def record_usage(self, request, pk=None):
        """Record usage for a quota."""
        usage = self.get_object()
        amount = request.data.get('amount', 1)
        metadata = request.data.get('metadata', {})
        
        try:
            from ..services import PlanQuotaService
            
            result = PlanQuotaService.record_usage(
                usage.tenant, usage.quota_key, amount, metadata
            )
            
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def reset_usage(self, request, pk=None):
        """Reset usage for a quota."""
        usage = self.get_object()
        
        try:
            from ..services import PlanQuotaService
            
            count = PlanQuotaService.reset_quota_usage(
                usage.tenant, usage.quota_key, usage.period
            )
            
            return Response({
                'message': f'Reset {count} usage records',
                'reset_count': count
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def usage_trends(self, request, pk=None):
        """Get usage trends for a specific quota."""
        usage = self.get_object()
        days = request.query_params.get('days', 30)
        
        try:
            from ..services import PlanQuotaService
            
            # Get historical usage data
            from datetime import timedelta
            start_date = timezone.now() - timedelta(days=days)
            
            historical_usage = PlanUsage.objects.filter(
                tenant=usage.tenant,
                quota_key=usage.quota_key,
                period=usage.period,
                created_at__gte=start_date
            ).order_by('created_at')
            
            trends = {
                'quota_key': usage.quota_key,
                'period': usage.period,
                'days': days,
                'current_usage': usage.usage_value,
                'limit_value': usage.limit_value,
                'usage_percentage': usage.usage_percentage,
                'historical_data': [
                    {
                        'date': item.created_at.date(),
                        'usage': item.usage_value,
                        'limit': item.limit_value,
                        'percentage': item.usage_percentage
                    }
                    for item in historical_usage
                ]
            }
            
            return Response(trends)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def quota_status(self, request, pk=None):
        """Get detailed quota status."""
        usage = self.get_object()
        
        try:
            from ..services import PlanQuotaService
            
            quota = PlanQuotaService._get_tenant_quota(usage.tenant, usage.quota_key)
            
            status = {
                'quota_key': usage.quota_key,
                'current_usage': usage.usage_value,
                'limit_value': usage.limit_value,
                'usage_percentage': usage.usage_percentage,
                'remaining': max(0, usage.limit_value - usage.usage_value) if quota else None,
                'over_limit': usage.usage_value > usage.limit_value if quota else False,
                'quota': {
                    'quota_type': quota.quota_type if quota else None,
                    'is_active': quota.is_active if quota else None,
                    'is_hard_limit': quota.is_hard_limit if quota else None,
                    'alert_threshold': quota.alert_threshold if quota else None,
                } if quota else None,
                'alert_threshold_exceeded': usage.usage_percentage >= (quota.alert_threshold if quota else 80),
                'last_used_at': usage.last_used_at,
                'reset_date': usage.reset_date if quota else None,
            }
            
            return Response(status)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def tenant_usage_summary(self, request):
        """Get usage summary for a tenant."""
        tenant_id = request.query_params.get('tenant_id')
        
        if not tenant_id:
            return Response(
                {'error': 'tenant_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from ..models.core import Tenant
            from ..services import PlanQuotaService
            
            tenant = Tenant.objects.get(id=tenant_id, is_deleted=False)
            
            # Check permission
            if not request.user.is_staff and tenant.owner != request.user:
                return Response(
                    {'error': 'Permission denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            usage_summary = PlanQuotaService.get_quota_usage(tenant)
            
            return Response(usage_summary)
            
        except Tenant.DoesNotExist:
            return Response(
                {'error': 'Tenant not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def quota_alerts(self, request):
        """Get quota alerts for tenants."""
        tenant_id = request.query_params.get('tenant_id')
        
        try:
            from ..services import PlanQuotaService
            
            alerts = PlanQuotaService.get_quota_alerts(
                tenant_id=tenant_id if tenant_id else None
            )
            
            return Response(alerts)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def usage_analytics(self, request):
        """Get usage analytics."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        period = request.query_params.get('period', 'monthly')
        
        try:
            from ..services import PlanQuotaService
            
            analytics = PlanQuotaService.get_quota_statistics(period=period)
            return Response(analytics)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class PlanQuotaViewSet(BaseTenantRelatedViewSet):
    """
    ViewSet for plan quota operations.
    
    Provides endpoints for:
    - Quota configuration management
    - Quota enforcement
    - Quota monitoring
    - Quota analytics
    """
    
    queryset = PlanQuota.objects.all()
    serializer_class = PlanQuotaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quota_type', 'period', 'is_active', 'is_hard_limit']
    
    @action(detail=True, methods=['post'])
    def check_quota(self, request, pk=None):
        """Check if tenant has sufficient quota."""
        quota = self.get_object()
        usage_amount = request.data.get('usage_amount', 1)
        
        try:
            from ..services import PlanQuotaService
            
            # Get tenant from quota's plan
            tenant = None
            if hasattr(quota, 'plan') and quota.plan:
                tenant = quota.plan.tenant_set.filter(is_deleted=False).first()
            
            if not tenant:
                return Response(
                    {'error': 'No tenant found for quota'},
                    status=status.HTTP_400_BAD_REQUEST
            )
            
            result = PlanQuotaService.check_quota_usage(
                tenant, quota.quota_key, usage_amount
            )
            
            return Response(result)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def activate_quota(self, request, pk=None):
        """Activate a quota."""
        quota = self.get_object()
        
        try:
            from ..services import PlanQuotaService
            
            updated_quota = PlanQuotaService.activate_quota(quota)
            serializer = self.get_serializer(updated_quota)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def deactivate_quota(self, request, pk=None):
        """Deactivate a quota."""
        quota = self.get_object()
        
        try:
            from ..services import PlanQuotaService
            
            updated_quota = PlanQuotaService.deactivate_quota(quota)
            serializer = self.get_serializer(updated_quota)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_limit(self, request, pk=None):
        """Update quota limit."""
        quota = self.get_object()
        new_limit = request.data.get('limit_value')
        
        if not isinstance(new_limit, (int, float)) or new_limit < 0:
            return Response(
                {'error': 'limit_value must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            quota.limit_value = new_limit
            quota.save()
            
            serializer = self.get_serializer(quota)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def update_alert_threshold(self, request, pk=None):
        """Update alert threshold."""
        quota = self.get_object()
        alert_threshold = request.data.get('alert_threshold')
        
        if not isinstance(alert_threshold, (int, float)) or alert_threshold < 0 or alert_threshold > 100:
            return Response(
                {'error': 'alert_threshold must be a number between 0 and 100'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            quota.alert_threshold = alert_threshold
            quota.save()
            
            serializer = self.get_serializer(quota)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def toggle_hard_limit(self, request, pk=None):
        """Toggle hard limit setting."""
        quota = self.get_object()
        is_hard_limit = request.data.get('is_hard_limit')
        
        if isinstance(is_hard_limit, bool):
            quota.is_hard_limit = is_hard_limit
            quota.save()
            
            serializer = self.get_serializer(quota)
            return Response(serializer.data)
        else:
            return Response(
                {'error': 'is_hard_limit must be a boolean'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['get'])
    def quota_usage_report(self, request, pk=None):
        """Get usage report for a specific quota."""
        quota = self.get_object()
        days = request.query_params.get('days', 30)
        
        try:
            from datetime import timedelta
            from ..models.plan import PlanUsage
            
            start_date = timezone.now() - timedelta(days=days)
            
            usage_records = PlanUsage.objects.filter(
                quota_key=quota.quota_key,
                period=quota.period,
                created_at__gte=start_date
            ).order_by('-created_at')
            
            report = {
                'quota': {
                    'quota_key': quota.quota_key,
                    'quota_name': quota.quota_name,
                    'quota_type': quota.quota_type,
                    'limit_value': quota.limit_value,
                    'period': quota.period,
                    'is_active': quota.is_active,
                    'is_hard_limit': quota.is_hard_limit,
                    'alert_threshold': quota.alert_threshold,
                },
                'usage_summary': {
                    'total_records': usage_records.count(),
                    'over_limit_count': usage_records.filter(
                        usage_value__gt=quota.limit_value
                    ).count(),
                    'alert_threshold_count': usage_records.filter(
                        usage_percentage__gte=quota.alert_threshold
                    ).count(),
                    'average_usage': usage_records.aggregate(
                        avg=Avg('usage_value')
                    )['avg'] or 0,
                    'max_usage': usage_records.aggregate(
                        max=Max('usage_value')
                    )['max'] or 0,
                },
                'recent_usage': [
                    {
                        'date': record.created_at.date(),
                        'usage': record.usage_value,
                        'limit': record.limit_value,
                        'percentage': record.usage_percentage,
                        'over_limit': record.usage_value > quota.limit_value,
                        'alert_exceeded': record.usage_percentage >= quota.alert_threshold,
                    }
                    for record in usage_records[:10]
                ]
            }
            
            return Response(report)
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def bulk_create_quotas(self, request):
        """Create quotas in bulk for a plan."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        plan_id = request.data.get('plan_id')
        quotas_data = request.data.get('quotas', [])
        
        if not plan_id or not quotas_data:
            return Response(
                {'error': 'plan_id and quotas data are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from ..models.plan import Plan
            from ..services import PlanQuotaService
            
            plan = Plan.objects.get(id=plan_id)
            
            created_quotas = []
            for quota_data in quotas_data:
                quota_data['plan'] = plan
                created_quota = PlanQuotaService.create_quota(plan, quota_data)
                created_quotas.append(created_quota)
            
            serializer = PlanQuotaSerializer(created_quotas, many=True)
            return Response({
                'message': f'Created {len(created_quotas)} quotas',
                'quotas': serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def copy_quotas_to_plans(self, request):
        """Copy quotas to multiple plans."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        source_plan_id = request.data.get('source_plan_id')
        target_plan_ids = request.data.get('target_plan_ids', [])
        
        if not source_plan_id or not target_plan_ids:
            return Response(
                {'error': 'source_plan_id and target_plan_ids are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from ..models.plan import Plan
            from ..services import PlanQuotaService
            
            source_plan = Plan.objects.get(id=source_plan_id)
            target_plans = Plan.objects.filter(id__in=target_plan_ids)
            
            copied_quotas = []
            for target_plan in target_plans:
                copied = PlanQuotaService.copy_features_to_plan(
                    source_plan, target_plan, overwrite=False
                )
                copied_quotas.extend(copied)
            
            return Response({
                'message': f'Copied quotas to {len(target_plans)} plans',
                'copied_count': len(copied_quotas)
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def quota_templates(self, request):
        """Get available quota templates."""
        templates = {
            'api_basic': {
                'quota_key': 'api_calls',
                'quota_name': 'API Calls',
                'quota_type': 'numeric',
                'limit_value': 1000,
                'period': 'daily',
                'is_hard_limit': True,
                'alert_threshold': 80,
                'description': 'Daily API call limit',
            },
            'api_professional': {
                'quota_key': 'api_calls',
                'quota_name': 'API Calls',
                'quota_type': 'numeric',
                'limit_value': 10000,
                'period': 'daily',
                'is_hard_limit': True,
                'alert_threshold': 80,
                'description': 'Daily API call limit for professional plan',
            },
            'api_enterprise': {
                'quota_key': 'api_calls',
                'quota_name': 'API Calls',
                'quota_type': 'numeric',
                'limit_value': 100000,
                'period': 'daily',
                'is_hard_limit': False,
                'alert_threshold': 90,
                'description': 'Daily API call limit for enterprise plan',
            },
            'storage_basic': {
                'quota_key': 'storage',
                'quota_name': 'Storage',
                'quota_type': 'numeric',
                'limit_value': 10,
                'period': 'monthly',
                'is_hard_limit': True,
                'alert_threshold': 85,
                'description': 'Storage limit in GB',
            },
            'storage_professional': {
                'quota_key': 'storage',
                'quota_name': 'Storage',
                'quota_type': 'numeric',
                'limit_value': 100,
                'period': 'monthly',
                'is_hard_limit': True,
                'alert_threshold': 85,
                'description': 'Storage limit in GB for professional plan',
            },
            'storage_enterprise': {
                'quota_key': 'storage',
                'quota_name': 'Storage',
                'quota_type': 'numeric',
                'limit_value': 1000,
                'period': 'monthly',
                'is_hard_limit': False,
                'alert_threshold': 90,
                'description': 'Storage limit in GB for enterprise plan',
            },
            'users_basic': {
                'quota_key': 'users',
                'quota_name': 'Users',
                'quota_type': 'numeric',
                'limit_value': 5,
                'period': 'monthly',
                'is_hard_limit': True,
                'alert_threshold': 80,
                'description': 'Number of active users',
            },
            'users_professional': {
                'quota_key': 'users',
                'quota_name': 'Users',
                'quota_type': 'numeric',
                'limit_value': 25,
                'period': 'monthly',
                'is_hard_limit': True,
                'alert_threshold': 80,
                'description': 'Number of active users for professional plan',
            },
            'users_enterprise': {
                'quota_key': 'users',
                'quota_name': 'Users',
                'quota_type': 'numeric',
                'limit_value': 100,
                'period': 'monthly',
                'is_hard_limit': False,
                'alert_threshold': 90,
                'description': 'Number of active users for enterprise plan',
            },
        }
        
        return Response(templates)
    
    @action(detail=True, methods=['post'])
    def apply_template(self, request, pk=None):
        """Apply a quota template."""
        quota = self.get_object()
        template_name = request.data.get('template')
        
        if not template_name:
            return Response(
                {'error': 'Template name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get templates
        templates = PlanQuotaViewSet.quota_templates(None)
        
        if template_name not in templates:
            return Response(
                {'error': f'Template {template_name} not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        template_data = templates[template_name]
        
        try:
            # Update quota with template data
            for field, value in template_data.items():
                if hasattr(quota, field) and field not in ['id', 'plan', 'created_at']:
                    setattr(quota, field, value)
            
            quota.save()
            
            serializer = self.get_serializer(quota)
            return Response({
                'message': f'Template {template_name} applied successfully',
                'quota': serializer.data
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
