# api/rate_limit/viewset.py
"""
ViewSet classes for rate limit module.

Provides DRF ViewSets for rate limiting APIs.
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

from api.tenants.mixins import TenantMixin
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


class RateLimitConfigViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RateLimitConfig model.
    """
    
    queryset = RateLimitConfig.objects.all()
    serializer_class = RateLimitConfigSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['rate_limit_type', 'is_active', 'user', 'endpoint']
    
    def get_serializer_class(self):
        """Get appropriate serializer class based on action."""
        if self.action == 'create':
            return RateLimitConfigCreateSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['post'])
    def bulk_activate(self, request):
        """Bulk activate configurations."""
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
    
    @action(detail=True, methods=['post'])
    def test_config(self, request, pk=None):
        """Test configuration with sample request."""
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


class RateLimitLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RateLimitLog model.
    """
    
    queryset = RateLimitLog.objects.all()
    serializer_class = RateLimitLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['user', 'status', 'config', 'request_method']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users can only see their own logs
        if not user.is_superuser and not user.groups.filter(name='rate_limit_managers').exists():
            queryset = queryset.filter(user=user)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get rate limit analytics."""
        days = int(request.query_params.get('days', 7))
        since_time = timezone.now() - timedelta(days=days)
        
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
        hours = int(request.data.get('hours', 24))
        user_id = request.data.get('user_id')
        
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
        log = self.get_object()
        
        # Check permission
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            if log.user != request.user:
                raise PermissionDenied("Cannot create abuse report for other users")
        
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


class UserRateLimitProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for UserRateLimitProfile model.
    """
    
    queryset = UserRateLimitProfile.objects.all()
    serializer_class = UserRateLimitProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users can only see their own profile
        if not user.is_superuser and not user.groups.filter(name='rate_limit_managers').exists():
            queryset = queryset.filter(user=user)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def reset_usage(self, request, pk=None):
        """Reset user usage statistics."""
        profile = self.get_object()
        
        # Check permission
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            if profile.user != request.user:
                raise PermissionDenied("Cannot reset usage for other users")
        
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
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            raise PermissionDenied("Cannot upgrade users to premium")
        
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
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            raise PermissionDenied("Cannot downgrade users")
        
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
        user_ids = request.query_params.get('user_ids', '').split(',')
        user_ids = [int(uid) for uid in user_ids if uid.isdigit()]
        
        if not user_ids:
            raise ValidationError("user_ids parameter is required")
        
        # Check permission
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            # Users can only get their own stats
            if len(user_ids) != 1 or user_ids[0] != request.user.id:
                raise PermissionDenied("Can only get own statistics")
        
        profiles = UserRateLimitProfile.objects.filter(user_id__in=user_ids)
        serializer = self.get_serializer(profiles, many=True)
        
        return Response(serializer.data)


class AbuseReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AbuseReport model.
    """
    
    queryset = AbuseReport.objects.all()
    serializer_class = AbuseReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['abuse_type', 'severity', 'is_investigated']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # Non-admin users can only see their own reports
        if not user.is_superuser and not user.groups.filter(name='rate_limit_managers').exists():
            queryset = queryset.filter(user=user)
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def investigate(self, request, pk=None):
        """Mark abuse report as investigated."""
        report = self.get_object()
        
        # Check permission
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            raise PermissionDenied("Cannot investigate abuse reports")
        
        report.is_investigated = True
        report.investigated_by = request.user
        report.investigated_at = timezone.now()
        report.save(update_fields=['is_investigated', 'investigated_by', 'investigated_at'])
        
        return Response({
            'success': True,
            'message': 'Abuse report marked as investigated'
        })
    
    @action(detail=True, methods=['post'])
    def block_user(self, request, pk=None):
        """Block user associated with abuse report."""
        if not request.user.is_superuser and not request.user.groups.filter(name='rate_limit_managers').exists():
            raise PermissionDenied("Cannot block users")
        
        report = self.get_object()
        
        if report.user:
            # Create IP block for user's recent IPs
            recent_logs = RateLimitLog.objects.filter(
                user=report.user,
                timestamp__gte=timezone.now() - timedelta(days=7)
            ).values('ip_address').distinct()
            
            blocked_ips = []
            for ip_data in recent_logs:
                ip_address = ip_data['ip_address']
                
                block = IPBlockList.objects.create(
                    ip_address=ip_address,
                    block_type='single',
                    block_reason='abuse_report',
                    is_active=True
                )
                blocked_ips.append(ip_address)
            
            return Response({
                'success': True,
                'message': f'Blocked {len(blocked_ips)} IP addresses for user',
                'blocked_ips': blocked_ips
            })
        else:
            return Response({
                'success': False,
                'message': 'No user associated with this report'
            })


class IPBlockListViewSet(viewsets.ModelViewSet):
    """
    ViewSet for IPBlockList model.
    """
    
    queryset = IPBlockList.objects.all()
    serializer_class = IPBlockListSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['block_type', 'block_reason', 'is_active', 'permanent']
    
    @action(detail=False, methods=['post'])
    def bulk_block(self, request):
        """Bulk block IP addresses."""
        ip_addresses = request.data.get('ip_addresses', [])
        block_type = request.data.get('block_type', 'single')
        block_reason = request.data.get('block_reason', 'manual')
        
        if not ip_addresses:
            raise ValidationError("ip_addresses is required")
        
        blocked_count = 0
        for ip_address in ip_addresses:
            try:
                block = IPBlockList.objects.create(
                    ip_address=ip_address,
                    block_type=block_type,
                    block_reason=block_reason,
                    is_active=True
                )
                blocked_count += 1
            except Exception as e:
                logger.error("Failed to block IP %s: %s", ip_address, e, exc_info=True)
        
        return Response({
            'success': True,
            'message': f'Blocked {blocked_count} IP addresses',
            'blocked_count': blocked_count
        })
    
    @action(detail=True, methods=['post'])
    def unblock(self, request, pk=None):
        """Unblock IP address."""
        block = self.get_object()
        
        block.is_active = False
        block.save(update_fields=['is_active'])
        
        return Response({
            'success': True,
            'message': f'IP {block.ip_address} unblocked'
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get IP blocking statistics."""
        total_blocks = IPBlockList.objects.count()
        active_blocks = IPBlockList.objects.filter(is_active=True).count()
        permanent_blocks = IPBlockList.objects.filter(permanent=True).count()
        
        # Blocks by reason
        blocks_by_reason = list(
            IPBlockList.objects.values('block_reason')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        # Blocks by type
        blocks_by_type = list(
            IPBlockList.objects.values('block_type')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        
        return Response({
            'total_blocks': total_blocks,
            'active_blocks': active_blocks,
            'permanent_blocks': permanent_blocks,
            'temporary_blocks': total_blocks - permanent_blocks,
            'blocks_by_reason': blocks_by_reason,
            'blocks_by_type': blocks_by_type
        })


class RateLimitInsightViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for RateLimitInsight model.
    """
    
    queryset = RateLimitInsight.objects.all()
    serializer_class = RateLimitInsightSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['date']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get insights summary."""
        days = int(request.query_params.get('days', 30))
        since_date = timezone.now().date() - timedelta(days=days)
        
        insights = RateLimitInsight.objects.filter(date__gte=since_date)
        
        summary = {
            'period_days': days,
            'total_insights': insights.count(),
            'avg_requests_per_day': insights.aggregate(avg=Avg('total_requests'))['avg'] or 0,
            'avg_blocked_per_day': insights.aggregate(avg=Avg('blocked_requests'))['avg'] or 0,
            'avg_block_rate': 0,
            'peak_hour': insights.aggregate(avg=Avg('peak_hour'))['avg'] or 12,
            'total_unique_ips': insights.aggregate(total=Sum('unique_ips'))['total'] or 0,
            'total_unique_users': insights.aggregate(total=Sum('unique_users'))['total'] or 0
        }
        
        # Calculate average block rate
        if summary['avg_requests_per_day'] > 0:
            summary['avg_block_rate'] = (summary['avg_blocked_per_day'] / summary['avg_requests_per_day']) * 100
        
        return Response(summary)


class RateLimitExceptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RateLimitException model.
    """
    
    queryset = RateLimitException.objects.all()
    serializer_class = RateLimitExceptionSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrRateLimitManager]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_fields = ['exception_type', 'is_active', 'permanent']
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate rate limit exception."""
        exception = self.get_object()
        
        exception.is_active = True
        exception.save(update_fields=['is_active'])
        
        return Response({
            'success': True,
            'message': f'Exception {exception.id} activated'
        })
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate rate limit exception."""
        exception = self.get_object()
        
        exception.is_active = False
        exception.save(update_fields=['is_active'])
        
        return Response({
            'success': True,
            'message': f'Exception {exception.id} deactivated'
        })


# Import needed serializer for create action
from rest_framework import serializers

class RateLimitConfigCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RateLimitConfig
        fields = [
            'name', 'rate_limit_type', 'requests_per_unit',
            'time_unit', 'time_value', 'user', 'endpoint',
            'ip_address', 'task_type', 'offer_wall', 'is_active'
        ]
    
    def validate(self, data):
        # Validate that at least one target field is set
        target_fields = ['user', 'endpoint', 'ip_address', 'task_type', 'offer_wall']
        if not any(data.get(field) for field in target_fields):
            raise serializers.ValidationError(
                "At least one target field (user, endpoint, ip_address, task_type, offer_wall) must be set"
            )
        
        # Validate rate limit values
        if data['requests_per_unit'] <= 0:
            raise serializers.ValidationError("Requests per unit must be greater than 0")
        
        if data['time_value'] <= 0:
            raise serializers.ValidationError("Time value must be greater than 0")
        
        return data


# Export ViewSets
__all__ = [
    'RateLimitConfigViewSet',
    'RateLimitLogViewSet',
    'UserRateLimitProfileViewSet',
    'AbuseReportViewSet',
    'IPBlockListViewSet',
    'RateLimitInsightViewSet',
    'RateLimitExceptionViewSet'
]
