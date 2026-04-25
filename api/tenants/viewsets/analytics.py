"""
Analytics Viewsets

This module contains viewsets for analytics-related models including
TenantMetric, TenantHealthScore, TenantFeatureFlag, and TenantNotification.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from django.utils import timezone

from ..models.analytics import TenantMetric, TenantHealthScore, TenantFeatureFlag, TenantNotification
from ..serializers.analytics import (
    TenantMetricSerializer, TenantHealthScoreSerializer,
    TenantFeatureFlagSerializer, TenantFeatureFlagCreateSerializer,
    TenantNotificationSerializer
)
from ..services import TenantMetricService, FeatureFlagService


class TenantMetricViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant metrics.
    """
    serializer_class = TenantMetricSerializer
    queryset = TenantMetric.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'metric_type', 'unit']
    search_fields = ['metric_type']
    ordering_fields = ['date', 'metric_type', 'value']
    ordering = ['-date']
    
    def get_queryset(self):
        """Filter queryset to tenant's metrics."""
        if self.request.user.is_superuser:
            return TenantMetric.objects.all()
        return TenantMetric.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def record_metric(self, request):
        """Record a new metric."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant and not request.user.is_superuser:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        metric_type = request.data.get('metric_type')
        value = request.data.get('value')
        date = request.data.get('date')
        metadata = request.data.get('metadata', {})
        
        if not metric_type or value is None:
            return Response(
                {'error': 'metric_type and value are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            if date:
                from datetime import datetime
                date = datetime.fromisoformat(date.replace('Z', '+00:00')).date()
            
            metric = TenantMetricService.record_metric(
                tenant, metric_type, float(value), date, metadata
            )
            serializer = self.get_serializer(metric)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def collect_daily_metrics(self, request):
        """Collect daily metrics for all tenants."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        date = request.data.get('date')
        if date:
            from datetime import datetime
            date = datetime.fromisoformat(date.replace('Z', '+00:00')).date()
        
        results = TenantMetricService.collect_daily_metrics(date)
        return Response(results, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def trend_analysis(self, request, pk=None):
        """Get trend analysis for metric."""
        metric = self.get_object()
        days = int(request.query_params.get('days', 30))
        
        # Get historical data
        from datetime import timedelta
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        metrics = TenantMetric.objects.filter(
            tenant=metric.tenant,
            metric_type=metric.metric_type,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Calculate trend
        values = [float(m.value) for m in metrics]
        if len(values) >= 2:
            first_value = values[0]
            last_value = values[-1]
            change_pct = ((last_value - first_value) / first_value) * 100 if first_value != 0 else 0
            
            if change_pct > 5:
                trend = 'up'
            elif change_pct < -5:
                trend = 'down'
            else:
                trend = 'stable'
        else:
            change_pct = 0
            trend = 'stable'
        
        return Response({
            'metric_type': metric.metric_type,
            'period': f'{days} days',
            'trend': trend,
            'change_percentage': round(change_pct, 2),
            'data_points': len(metrics),
            'values': values,
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def dashboard_metrics(self, request):
        """Get dashboard metrics for tenant."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        dashboard = TenantMetricService.get_dashboard_metrics(tenant)
        return Response(dashboard, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export metrics data."""
        format_type = request.query_params.get('format', 'csv')
        days = int(request.query_params.get('days', 30))
        
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant and not request.user.is_superuser:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if format_type not in ['csv', 'json', 'xlsx']:
            return Response(
                {'error': 'Invalid format. Use csv, json, or xlsx'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            export_data = TenantMetricService.export_metrics(tenant, format_type, days)
            
            if format_type == 'json':
                return Response(export_data, status=status.HTTP_200_OK)
            elif format_type == 'csv':
                return Response(export_data, content_type='text/csv', status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'XLSX export not implemented yet'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TenantHealthScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing tenant health scores.
    """
    serializer_class = TenantHealthScoreSerializer
    queryset = TenantHealthScore.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'health_grade', 'risk_level']
    search_fields = []
    ordering_fields = ['overall_score', 'last_activity_at']
    ordering = ['-last_activity_at']
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        if self.request.user.is_superuser:
            return TenantHealthScore.objects.all()
        return TenantHealthScore.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        """Recalculate health score."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        health_score = self.get_object()
        
        # This would trigger health score recalculation
        # For now, just return success
        return Response({'message': 'Health score recalculation triggered'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def detailed_analysis(self, request, pk=None):
        """Get detailed health analysis."""
        health_score = self.get_object()
        
        analysis = {
            'engagement_analysis': {
                'score': health_score.engagement_score,
                'factors': health_score.positive_factors.get('engagement', []),
                'issues': health_score.negative_factors.get('engagement', []),
            },
            'usage_analysis': {
                'score': health_score.usage_score,
                'factors': health_score.positive_factors.get('usage', []),
                'issues': health_score.negative_factors.get('usage', []),
            },
            'payment_analysis': {
                'score': health_score.payment_score,
                'factors': health_score.positive_factors.get('payment', []),
                'issues': health_score.negative_factors.get('payment', []),
            },
            'support_analysis': {
                'score': health_score.support_score,
                'factors': health_score.positive_factors.get('support', []),
                'issues': health_score.negative_factors.get('support', []),
            },
            'risk_signals': health_score.risk_signals,
            'recommendations': health_score.recommendations,
        }
        
        return Response(analysis, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def health_summary(self, request):
        """Get health summary for all tenants."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get health statistics
        from django.db.models import Count, Avg
        
        summary = {
            'total_tenants': TenantHealthScore.objects.count(),
            'health_grades': {},
            'risk_levels': {},
            'average_scores': {},
        }
        
        # Health grades breakdown
        grades = TenantHealthScore.objects.values('health_grade').annotate(count=Count('id'))
        summary['health_grades'] = {g['health_grade']: g['count'] for g in grades}
        
        # Risk levels breakdown
        risks = TenantHealthScore.objects.values('risk_level').annotate(count=Count('id'))
        summary['risk_levels'] = {r['risk_level']: r['count'] for r in risks}
        
        # Average scores
        scores = TenantHealthScore.objects.aggregate(
            avg_engagement=Avg('engagement_score'),
            avg_usage=Avg('usage_score'),
            avg_payment=Avg('payment_score'),
            avg_support=Avg('support_score'),
            avg_overall=Avg('overall_score'),
            avg_churn=Avg('churn_probability')
        )
        summary['average_scores'] = {k: round(v or 0, 2) for k, v in scores.items()}
        
        return Response(summary, status=status.HTTP_200_OK)


class TenantFeatureFlagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant feature flags.
    """
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'flag_type', 'is_enabled']
    search_fields = ['flag_key', 'name', 'description']
    ordering_fields = ['flag_key', 'name', 'created_at']
    ordering = ['flag_key', 'name']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TenantFeatureFlagCreateSerializer
        return TenantFeatureFlagSerializer
    
    def get_queryset(self):
        """Filter queryset to tenant's feature flags."""
        if self.request.user.is_superuser:
            return TenantFeatureFlag.objects.all()
        return TenantFeatureFlag.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def enable(self, request, pk=None):
        """Enable feature flag."""
        feature_flag = self.get_object()
        
        enabled_flag = FeatureFlagService.enable_feature_flag(feature_flag, request.user)
        serializer = self.get_serializer(enabled_flag)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def disable(self, request, pk=None):
        """Disable feature flag."""
        feature_flag = self.get_object()
        
        disabled_flag = FeatureFlagService.disable_feature_flag(feature_flag, request.user)
        serializer = self.get_serializer(disabled_flag)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def rollout_to_percentage(self, request, pk=None):
        """Rollout feature flag to percentage."""
        feature_flag = self.get_object()
        percentage = request.data.get('percentage')
        
        if percentage is None:
            return Response(
                {'error': 'percentage parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            percentage = int(percentage)
            if percentage < 0 or percentage > 100:
                raise ValueError()
        except ValueError:
            return Response(
                {'error': 'percentage must be an integer between 0 and 100'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        rolled_out_flag = FeatureFlagService.rollout_to_percentage(
            feature_flag, percentage, request.user
        )
        serializer = self.get_serializer(rolled_out_flag)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def check_user(self, request, pk=None):
        """Check if feature is enabled for user."""
        feature_flag = self.get_object()
        
        # Get user from request
        user = request.user if request.user.is_authenticated else None
        
        if not user:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        is_enabled = FeatureFlagService.is_feature_enabled(
            feature_flag.tenant, feature_flag.flag_key, user
        )
        
        variant = FeatureFlagService.get_variant_for_user(
            feature_flag.tenant, feature_flag.flag_key, user
        )
        
        return Response({
            'flag_key': feature_flag.flag_key,
            'is_enabled': is_enabled,
            'variant': variant,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'])
    def user_flags(self, request, pk=None):
        """Get all enabled flags for user."""
        feature_flag = self.get_object()
        
        user = request.user if request.user.is_authenticated else None
        
        if not user:
            return Response(
                {'error': 'User authentication required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user_flags = FeatureFlagService.get_user_feature_flags(feature_flag.tenant, user)
        return Response(user_flags, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def create_ab_test(self, request, pk=None):
        """Create A/B test from feature flag."""
        feature_flag = self.get_object()
        
        test_data = {
            'name': request.data.get('name', f"AB Test for {feature_flag.name}"),
            'variants': request.data.get('variants', ['control', 'test']),
            'rollout_pct': request.data.get('rollout_pct', 50),
        }
        
        try:
            result = FeatureFlagService.create_ab_test(feature_flag.tenant, test_data, request.user)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get feature flag analytics."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        days = int(request.query_params.get('days', 30))
        flag_key = request.query_params.get('flag_key')
        
        analytics = FeatureFlagService.get_feature_flag_analytics(tenant, flag_key, days)
        return Response(analytics, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def recommendations(self, request):
        """Get feature flag recommendations."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        recommendations = FeatureFlagService.get_feature_flag_recommendations(tenant)
        return Response(recommendations, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['post'])
    def cleanup_expired(self, request):
        """Clean up expired feature flags."""
        if not request.user.is_superuser:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        results = FeatureFlagService.cleanup_expired_flags()
        return Response(results, status=status.HTTP_200_OK)


class TenantNotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenant notifications.
    """
    serializer_class = TenantNotificationSerializer
    queryset = TenantNotification.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['tenant', 'notification_type', 'priority', 'status', 'is_read']
    search_fields = ['title', 'message']
    ordering_fields = ['created_at', 'priority', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter queryset to tenant's notifications."""
        if self.request.user.is_superuser:
            return TenantNotification.objects.all()
        return TenantNotification.objects.filter(tenant__owner=self.request.user)
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        return [permissions.IsAuthenticated]
    
    @action(detail=True, methods=['post'])
    def mark_as_read(self, request, pk=None):
        """Mark notification as read."""
        notification = self.get_object()
        
        if notification.is_read:
            return Response(
                {'error': 'Notification is already read'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification.mark_as_read()
        return Response({'message': 'Notification marked as read'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def mark_as_unread(self, request, pk=None):
        """Mark notification as unread."""
        notification = self.get_object()
        
        if not notification.is_read:
            return Response(
                {'error': 'Notification is already unread'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        notification.is_read = False
        notification.read_at = None
        notification.save(update_fields=['is_read', 'read_at'])
        
        return Response({'message': 'Notification marked as unread'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def send_now(self, request, pk=None):
        """Send notification immediately."""
        notification = self.get_object()
        
        if notification.status == 'sent':
            return Response(
                {'error': 'Notification has already been sent'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # This would integrate with your notification system
        # For now, just mark as sent
        notification.status = 'sent'
        notification.save(update_fields=['status'])
        
        return Response({'message': 'Notification sent'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def schedule(self, request, pk=None):
        """Schedule notification for later delivery."""
        notification = self.get_object()
        scheduled_at = request.data.get('scheduled_at')
        
        if not scheduled_at:
            return Response(
                {'error': 'scheduled_at parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from datetime import datetime
            scheduled_at = datetime.fromisoformat(scheduled_at.replace('Z', '+00:00'))
            
            if scheduled_at <= timezone.now():
                return Response(
                    {'error': 'Scheduled time must be in the future'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            notification.scheduled_at = scheduled_at
            notification.status = 'scheduled'
            notification.save(update_fields=['scheduled_at', 'status'])
            
            return Response({'message': 'Notification scheduled'}, status=status.HTTP_200_OK)
        except ValueError:
            return Response(
                {'error': 'Invalid datetime format'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def mark_all_as_read(self, request):
        """Mark all notifications as read for user."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        unread_count = TenantNotification.objects.filter(
            tenant=tenant, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({
            'message': f'Marked {unread_count} notifications as read',
            'unread_count': unread_count
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get unread notifications count."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        unread_count = TenantNotification.objects.filter(
            tenant=tenant, is_read=False
        ).count()
        
        return Response({'unread_count': unread_count}, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get notifications summary."""
        tenant = request.user.tenant if hasattr(request.user, 'tenant') else None
        if not tenant:
            return Response(
                {'error': 'Tenant context required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.db.models import Count
        
        summary = {
            'total_notifications': TenantNotification.objects.filter(tenant=tenant).count(),
            'unread_notifications': TenantNotification.objects.filter(tenant=tenant, is_read=False).count(),
            'urgent_notifications': TenantNotification.objects.filter(
                tenant=tenant, priority='urgent', is_read=False
            ).count(),
            'by_type': {},
            'by_status': {},
        }
        
        # By type
        types = TenantNotification.objects.filter(tenant=tenant).values('notification_type').annotate(count=Count('id'))
        summary['by_type'] = {t['notification_type']: t['count'] for t in types}
        
        # By status
        statuses = TenantNotification.objects.filter(tenant=tenant).values('status').annotate(count=Count('id'))
        summary['by_status'] = {s['status']: s['count'] for s in statuses}
        
        return Response(summary, status=status.HTTP_200_OK)
