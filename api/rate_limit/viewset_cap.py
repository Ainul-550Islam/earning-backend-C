# api/rate_limit/viewset_cap.py
"""
Capability-based ViewSets for rate limit module.

Provides ViewSets with capability-based access control and advanced features.
"""
from datetime import timedelta

import logging
from typing import Dict, Any, List, Optional
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg
from django.http import Http404
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters import rest_framework as filters

from api.rate_limit.models import (
    RateLimitConfig, RateLimitLog, UserRateLimitProfile, 
    AbuseReport, IPBlockList, RateLimitInsight, RateLimitException
)
from api.rate_limit.serializers import (
    RateLimitConfigSerializer, RateLimitLogSerializer,
    UserRateLimitProfileSerializer, AbuseReportSerializer,
    IPBlockListSerializer, RateLimitInsightSerializer,
    RateLimitExceptionSerializer
)
from api.rate_limit.permissions import IsAdminOrRateLimitManager
from api.rate_limit.services import RateLimitService
from api.rate_limit.logic import AbuseDetectionLogic, RateLimitOptimization

logger = logging.getLogger(__name__)


class CapabilityViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet with capability-based access control.
    """
    
    capability_map = {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
    }
    
    def get_serializer_class(self):
        """Get serializer class based on action."""
        if self.action == 'create':
            return self.get_create_serializer_class()
        elif self.action in ['update', 'partial_update']:
            return self.get_update_serializer_class()
        return self.get_list_serializer_class()
    
    def get_list_serializer_class(self):
        """Get serializer for list actions."""
        return self.serializer_class
    
    def get_create_serializer_class(self):
        """Get serializer for create action."""
        return self.serializer_class
    
    def get_update_serializer_class(self):
        """Get serializer for update action."""
        return self.serializer_class
    
    def check_capability(self, capability: str):
        """Check if user has required capability."""
        user = self.request.user
        
        if not user.is_authenticated:
            raise PermissionDenied("Authentication required")
        
        # Superusers have all capabilities
        if user.is_superuser:
            return True
        
        # Check user capabilities
        user_capabilities = self.get_user_capabilities(user)
        
        if capability not in user_capabilities:
            raise PermissionDenied(f"Insufficient capabilities: {capability}")
        
        return True
    
    def get_user_capabilities(self, user) -> List[str]:
        """Get user capabilities."""
        capabilities = []
        
        # Base capabilities for authenticated users
        capabilities.extend(['view'])
        
        # Staff capabilities
        if user.is_staff:
            capabilities.extend(['create', 'edit'])
        
        # Rate limit manager capabilities
        if user.groups.filter(name='rate_limit_managers').exists():
            capabilities.extend(['create', 'edit', 'delete'])
        
        return capabilities
    
    def check_object_permission(self, obj):
        """Check object-level permission."""
        user = self.request.user
        
        # Superusers can access everything
        if user.is_superuser:
            return True
        
        # Rate limit managers can access everything
        if user.groups.filter(name='rate_limit_managers').exists():
            return True
        
        # Check ownership
        if hasattr(obj, 'user') and obj.user == user:
            return True
        
        return False
    
    def list(self, request, *args, **kwargs):
        """List objects with capability check."""
        self.check_capability('view')
        return super().list(request, *args, **kwargs)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve object with capability check."""
        self.check_capability('view')
        instance = self.get_object()
        
        if not self.check_object_permission(instance):
            raise PermissionDenied("Object access denied")
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        """Create object with capability check."""
        self.check_capability('create')
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update object with capability check."""
        self.check_capability('edit')
        instance = self.get_object()
        
        if not self.check_object_permission(instance):
            raise PermissionDenied("Object edit access denied")
        
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update object with capability check."""
        self.check_capability('edit')
        instance = self.get_object()
        
        if not self.check_object_permission(instance):
            raise PermissionDenied("Object edit access denied")
        
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete object with capability check."""
        self.check_capability('delete')
        instance = self.get_object()
        
        if not self.check_object_permission(instance):
            raise PermissionDenied("Object delete access denied")
        
        return super().destroy(request, *args, **kwargs)


class RateLimitConfigCapabilityViewSet(CapabilityViewSet):
    """
    Capability-based ViewSet for RateLimitConfig.
    """
    
    queryset = RateLimitConfig.objects.all()
    serializer_class = RateLimitConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['rate_limit_type', 'is_active', 'user', 'endpoint']
    
    def get_user_capabilities(self, user):
        """Get user capabilities for rate limit configs."""
        capabilities = super().get_user_capabilities(user)
        
        # Rate limit managers have full access
        if user.groups.filter(name='rate_limit_managers').exists():
            capabilities.extend(['create', 'edit', 'delete'])
        
        return capabilities
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate configurations."""
        self.check_capability('edit')
        
        config_ids = request.data.get('config_ids', [])
        if not config_ids:
            raise ValidationError("config_ids is required")
        
        updated = RateLimitConfig.objects.filter(
            id__in=config_ids
        ).update(is_active=True)
        
        return Response({
            'success': True,
            'message': f'Activated {updated} configurations',
            'updated_count': updated
        })
    
    @action(detail=False, methods=['post'])
    def bulk_deactivate(self, request):
        """Bulk deactivate configurations."""
        self.check_capability('edit')
        
        config_ids = request.data.get('config_ids', [])
        if not config_ids:
            raise ValidationError("config_ids is required")
        
        updated = RateLimitConfig.objects.filter(
            id__in=config_ids
        ).update(is_active=False)
        
        return Response({
            'success': True,
            'message': f'Deactivated {updated} configurations',
            'updated_count': updated
        })
    
    @action(detail=False, methods=['post'])
    def optimize_configs(self, request):
        """Optimize rate limit configurations."""
        self.check_capability('edit')
        
        optimizer = RateLimitOptimization()
        
        # Get all active configs
        configs = RateLimitConfig.objects.filter(is_active=True)
        results = []
        
        for config in configs:
            try:
                suggestion = optimizer.suggest_config_adjustments(config.id)
                if 'suggestions' in suggestion:
                    results.append(suggestion)
            except Exception as e:
                logger.error("Failed to optimize config %s: %s", config.id, e, exc_info=True)
        
        return Response({
            'success': True,
            'results': results,
            'total_analyzed': len(configs)
        })
    
    @action(detail=True, methods=['post'])
    def test_config(self, request, pk=None):
        """Test configuration with sample request."""
        self.check_capability('view')
        
        config = self.get_object()
        test_data = request.data.get('test_data', {})
        
        # Create mock request data
        mock_request_data = {
            'user': request.user,
            'ip_address': test_data.get('ip_address', '127.0.0.1'),
            'endpoint': test_data.get('endpoint', '/api/test/'),
            'method': test_data.get('method', 'GET'),
        }
        
        # Test rate limit
        rate_limit_service = RateLimitService()
        result = rate_limit_service.is_rate_limited(
            identifier=mock_request_data['ip_address'],
            limit_type=config.rate_limit_type,
            max_requests=config.requests_per_unit,
            user=mock_request_data['user'],
            ip_address=mock_request_data['ip_address'],
            endpoint=mock_request_data['endpoint']
        )
        
        return Response({
            'success': True,
            'config': {
                'name': config.name,
                'rate_limit_type': config.rate_limit_type,
                'requests_per_unit': config.requests_per_unit,
                'time_unit': config.time_unit,
                'time_value': config.time_value,
            },
            'test_result': {
                'is_allowed': not result[0],
                'remaining': result[1],
                'metadata': result[2],
            }
        })


class RateLimitLogCapabilityViewSet(CapabilityViewSet):
    """
    Capability-based ViewSet for RateLimitLog.
    """
    
    queryset = RateLimitLog.objects.all()
    serializer_class = RateLimitLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['user', 'status', 'config', 'request_method']
    
    def get_queryset(self):
        """Filter queryset based on user capabilities."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users can only see their own logs
        if not user.is_superuser and not user.groups.filter(name='rate_limit_managers').exists():
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def get_user_capabilities(self, user):
        """Get user capabilities for rate limit logs."""
        capabilities = super().get_user_capabilities(user)
        
        # All authenticated users can view logs
        if user.is_authenticated:
            capabilities.append('view')
        
        # Rate limit managers can create abuse reports from logs
        if user.groups.filter(name='rate_limit_managers').exists():
            capabilities.append('create')  # For abuse reports
        
        return capabilities
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get rate limit analytics."""
        self.check_capability('view')
        
        # Get time range
        days = int(request.query_params.get('days', 7))
        since_time = timezone.now() - timedelta(days=days)
        
        # Get analytics data
        logs = RateLimitLog.objects.filter(timestamp__gte=since_time)
        
        analytics = {
            'total_requests': logs.count(),
            'blocked_requests': logs.filter(status='blocked').count(),
            'allowed_requests': logs.filter(status='allowed').count(),
            'unique_users': logs.values('user').distinct().count(),
            'unique_ips': logs.values('ip_address').distinct().count(),
            'top_endpoints': list(
                logs.values('endpoint')
                .annotate(count=Count('id'))
                .order_by('-count')[:10]
                .values('endpoint', 'count')
            ),
            'hourly_distribution': list(
                logs.extra({'hour': "strftime('%%H', timestamp)"})
                .values('hour')
                .annotate(count=Count('id'))
                .order_by('hour')
            ),
            'status_distribution': list(
                logs.values('status')
                .annotate(count=Count('id'))
                .order_by('-count')
                .values('status', 'count')
            ),
        }
        
        # Calculate block rate
        if analytics['total_requests'] > 0:
            analytics['block_rate'] = (analytics['blocked_requests'] / analytics['total_requests']) * 100
        else:
            analytics['block_rate'] = 0
        
        return Response(analytics)
    
    @action(detail=False, methods=['post'])
    def detect_abuse(self, request):
        """Detect abuse patterns from logs."""
        self.check_capability('view')
        
        # Get parameters
        hours = int(request.data.get('hours', 24))
        user_id = request.data.get('user_id')
        
        # Get logs
        since_time = timezone.now() - timedelta(hours=hours)
        logs = RateLimitLog.objects.filter(timestamp__gte=since_time)
        
        if user_id:
            logs = logs.filter(user_id=user_id)
        
        # Convert to dict format
        log_data = []
        for log in logs:
            log_data.append({
                'timestamp': log.timestamp,
                'ip_address': log.ip_address,
                'endpoint': log.endpoint,
                'status': log.status,
                'user_agent': log.user_agent,
            })
        
        # Detect patterns
        detector = AbuseDetectionLogic()
        patterns = detector.detect_patterns(log_data)
        
        return Response({
            'success': True,
            'patterns': patterns,
            'analyzed_logs': len(log_data),
            'analysis_period_hours': hours
        })
    
    @action(detail=True, methods=['post'])
    def create_abuse_report(self, request, pk=None):
        """Create abuse report from log entry."""
        self.check_capability('create')
        
        log = self.get_object()
        
        # Create abuse report
        abuse_report = AbuseReport.objects.create(
            user=log.user,
            ip_address=log.ip_address,
            abuse_type=request.data.get('abuse_type', 'suspicious_pattern'),
            severity=int(request.data.get('severity', 3)),
            description=request.data.get('description', f"Suspicious activity detected in log {log.id}"),
            evidence={
                'log_id': log.id,
                'endpoint': log.endpoint,
                'status': log.status,
                'suspicion_score': log.suspicion_score,
            },
            created_by=request.user
        )
        
        serializer = AbuseReportSerializer(abuse_report)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class UserRateLimitProfileCapabilityViewSet(CapabilityViewSet):
    """
    Capability-based ViewSet for UserRateLimitProfile.
    """
    
    queryset = UserRateLimitProfile.objects.all()
    serializer_class = UserRateLimitProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user capabilities."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users can only see their own profile
        if not user.is_superuser and not user.groups.filter(name='rate_limit_managers').exists():
            queryset = queryset.filter(user=user)
        
        return queryset
    
    def get_user_capabilities(self, user):
        """Get user capabilities for user profiles."""
        capabilities = super().get_user_capabilities(user)
        
        # All authenticated users can view their own profile
        if user.is_authenticated:
            capabilities.append('view')
        
        # Users can edit their own profile
        capabilities.append('edit')
        
        # Rate limit managers have full access
        if user.groups.filter(name='rate_limit_managers').exists():
            capabilities.extend(['create', 'delete'])
        
        return capabilities
    
    @action(detail=True, methods=['post'])
    def reset_usage(self, request, pk=None):
        """Reset user usage statistics."""
        profile = self.get_object()
        
        # Check permission
        if not self.check_object_permission(profile):
            raise PermissionDenied("Cannot reset usage for this user")
        
        # Reset usage
        profile.daily_usage = 0
        profile.hourly_usage = 0
        profile.current_usage = 0
        profile.save(update_fields=['daily_usage', 'hourly_usage', 'current_usage'])
        
        return Response({
            'success': True,
            'message': 'Usage statistics reset successfully'
        })
    
    @action(detail=True, methods=['post'])
    def upgrade_to_premium(self, request, pk=None):
        """Upgrade user to premium status."""
        self.check_capability('edit')
        
        profile = self.get_object()
        days = int(request.data.get('days', 30))
        
        # Set premium status
        profile.is_premium = True
        profile.premium_until = timezone.now() + timedelta(days=days)
        profile.save(update_fields=['is_premium', 'premium_until'])
        
        return Response({
            'success': True,
            'message': f'User upgraded to premium for {days} days',
            'premium_until': profile.premium_until
        })
    
    @action(detail=True, methods=['post'])
    def downgrade_to_standard(self, request, pk=None):
        """Downgrade user to standard status."""
        self.check_capability('edit')
        
        profile = self.get_object()
        
        # Remove premium status
        profile.is_premium = False
        profile.premium_until = None
        profile.save(update_fields=['is_premium', 'premium_until'])
        
        return Response({
            'success': True,
            'message': 'User downgraded to standard status'
        })
    
    @action(detail=False, methods=['get'])
    def bulk_stats(self, request):
        """Get bulk statistics for multiple users."""
        self.check_capability('view')
        
        user_ids = request.query_params.get('user_ids', '').split(',')
        user_ids = [int(uid) for uid in user_ids if uid.isdigit()]
        
        if not user_ids:
            raise ValidationError("user_ids parameter is required")
        
        profiles = UserRateLimitProfile.objects.filter(user_id__in=user_ids)
        serializer = self.get_serializer(profiles, many=True)
        
        return Response(serializer.data)


# Export ViewSets
__all__ = [
    'CapabilityViewSet',
    'RateLimitConfigCapabilityViewSet',
    'RateLimitLogCapabilityViewSet',
    'UserRateLimitProfileCapabilityViewSet'
]
