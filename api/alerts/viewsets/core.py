"""
Core Alert ViewSets
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from django.db.models import Count, Avg, Q
from datetime import timedelta
import logging

from ..models.core import AlertRule, AlertLog, Notification, SystemHealthCheck
from ..services.core import AlertProcessorService, AnalyticsService, AlertGroupService, AlertMaintenanceService

logger = logging.getLogger(__name__)


class AlertRuleViewSet(viewsets.ModelViewSet):
    """AlertRule ViewSet for CRUD operations"""
    queryset = AlertRule.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Apply filters
        severity = self.request.query_params.get('severity')
        alert_type = self.request.query_params.get('alert_type')
        is_active = self.request.query_params.get('is_active')
        
        if severity:
            queryset = queryset.filter(severity=severity)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)
        if is_active is not None and is_active != '':
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.core import AlertRuleSerializer
        return AlertRuleSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Alert rules statistics"""
        try:
            qs = AlertRule.objects.all()
            
            by_severity = {}
            for s in ['low', 'medium', 'high', 'critical']:
                by_severity[s] = qs.filter(severity=s).count()
            
            by_type = {}
            valid_types = ['high_earning', 'mass_signup', 'payment_spike', 'fraud_spike', 'server_error', 'low_balance']
            for t in valid_types:
                by_type[t] = qs.filter(alert_type=t).count()
            
            return Response({
                'total': qs.count(),
                'active': qs.filter(is_active=True).count(),
                'inactive': qs.filter(is_active=False).count(),
                'by_severity': by_severity,
                'by_type': by_type,
                'high_trigger_count': list(qs.order_by('-trigger_count')[:5].values('id', 'name', 'trigger_count')),
            })
        except Exception as e:
            logger.error(f"Error getting alert rules stats: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        """Toggle rule active/inactive"""
        try:
            rule = self.get_object()
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
            return Response({'success': True, 'is_active': rule.is_active})
        except Exception as e:
            logger.error(f"Error toggling rule: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Manually trigger test alert"""
        try:
            rule = self.get_object()
            
            # Create test alert log
            log = AlertLog.objects.create(
                rule=rule,
                trigger_value=rule.threshold_value + 1,
                threshold_value=rule.threshold_value,
                message=f'[TEST] Alert rule "{rule.name}" manually tested',
                is_resolved=True,
                resolved_at=timezone.now(),
                resolution_note='Auto-resolved: manual test',
            )
            
            return Response({'success': True, 'log_id': log.id, 'message': log.message})
        except Exception as e:
            logger.error(f"Error testing rule: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['patch'])
    def bulk_update_status(self, request):
        """Bulk update rule active/inactive status"""
        try:
            ids = request.data.get('ids', [])
            is_active = request.data.get('is_active', True)
            
            if not ids:
                return Response({'error': 'No ids provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            count = AlertRule.objects.filter(id__in=ids).update(is_active=is_active)
            return Response({'success': True, 'updated': count})
        except Exception as e:
            logger.error(f"Error bulk updating rules: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertLogViewSet(viewsets.ModelViewSet):
    """AlertLog ViewSet for CRUD operations"""
    queryset = AlertLog.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('rule')
        
        # Apply filters
        severity = self.request.query_params.get('severity')
        resolved = self.request.query_params.get('is_resolved')
        rule_id = self.request.query_params.get('rule_id')
        
        if severity:
            queryset = queryset.filter(rule__severity=severity)
        if resolved is not None and resolved != '':
            queryset = queryset.filter(is_resolved=resolved.lower() == 'true')
        if rule_id:
            queryset = queryset.filter(rule_id=rule_id)
        
        return queryset.order_by('-triggered_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.core import AlertLogSerializer
        return AlertLogSerializer
    
    def get_permissions(self):
        if self.action in ['resolve', 'bulk_resolve', 'delete']:
            return [IsAuthenticated, IsAdminUser]
        return [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Alert logs statistics"""
        try:
            qs = AlertLog.objects.all()
            week_ago = timezone.now() - timedelta(days=7)
            unresolved = qs.filter(is_resolved=False)
            
            return Response({
                'total': qs.count(),
                'resolved': qs.filter(is_resolved=True).count(),
                'unresolved': unresolved.count(),
                'escalated': qs.filter(escalation_level__gt=0).count(),
                'critical_unresolved': unresolved.filter(rule__severity='critical').count(),
                'this_week': qs.filter(triggered_at__gte=week_ago).count(),
                'avg_resolution_time': None,  # Can compute if needed
            })
        except Exception as e:
            logger.error(f"Error getting alert logs stats: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a single alert log"""
        try:
            log = self.get_object()
            
            if log.is_resolved:
                return Response({'error': 'Already resolved'}, status=status.HTTP_400_BAD_REQUEST)
            
            log.is_resolved = True
            log.resolved_at = timezone.now()
            log.resolved_by = request.user
            
            # Accept both 'note' and 'resolution_note' keys
            note = request.data.get('note') or request.data.get('resolution_note', 'Manually resolved')
            log.resolution_note = note
            log.save()
            
            return Response({'success': True})
        except Exception as e:
            logger.error(f"Error resolving alert log: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def bulk_resolve(self, request):
        """Bulk resolve alert logs"""
        try:
            ids = request.data.get('ids', [])
            note = request.data.get('note') or request.data.get('resolution_note', 'Bulk resolved by admin')
            
            if not ids:
                return Response({'error': 'No ids provided'}, status=status.HTTP_400_BAD_REQUEST)
            
            count = AlertLog.objects.filter(id__in=ids, is_resolved=False).update(
                is_resolved=True,
                resolved_at=timezone.now(),
                resolution_note=note,
            )
            
            return Response({'success': True, 'resolved': count})
        except Exception as e:
            logger.error(f"Error bulk resolving alerts: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    """Notification ViewSet for viewing notifications"""
    queryset = Notification.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('alert_log', 'alert_log__rule')
        
        # Apply filters
        status = self.request.query_params.get('status')
        notification_type = self.request.query_params.get('notification_type')
        
        if status:
            queryset = queryset.filter(status=status)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        return queryset.order_by('-created_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.core import NotificationSerializer
        return NotificationSerializer
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Notification statistics"""
        try:
            from ..services.channel import NotificationService
            stats = NotificationService.get_notification_statistics()
            return Response(stats)
        except Exception as e:
            logger.error(f"Error getting notification stats: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def retry_failed(self, request):
        """Retry failed notifications"""
        try:
            from ..services.channel import NotificationService
            retry_count = NotificationService.retry_failed_notifications()
            return Response({'success': True, 'retried': retry_count})
        except Exception as e:
            logger.error(f"Error retrying notifications: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SystemHealthViewSet(viewsets.ReadOnlyModelViewSet):
    """SystemHealthCheck ViewSet for monitoring"""
    queryset = SystemHealthCheck.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return super().get_queryset().order_by('-checked_at')
    
    def get_serializer_class(self):
        # Will be defined in serializers
        from ..serializers.core import SystemHealthCheckSerializer
        return SystemHealthCheckSerializer
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """System health overview"""
        try:
            overall = SystemHealthCheck.get_overall_status()
            checks = list(SystemHealthCheck.objects.order_by('-checked_at')[:10].values(
                'id', 'check_name', 'check_type', 'status', 'response_time_ms', 
                'status_message', 'checked_at'
            ))
            return Response({'overall_status': overall, 'checks': checks})
        except Exception as e:
            logger.error(f"Error getting system health overview: {e}")
            return Response({'overall_status': 'unknown', 'checks': [], 'error': str(e)})
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """System metrics"""
        try:
            metrics = AnalyticsService.get_system_metrics()
            return Response(metrics)
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertOverviewViewSet(viewsets.ViewSet):
    """Alert overview dashboard ViewSet"""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Alert overview statistics"""
        try:
            today = timezone.now().date()
            week_ago = timezone.now() - timedelta(days=7)
            unresolved = AlertLog.objects.filter(is_resolved=False)
            
            return Response({
                'total_rules': AlertRule.objects.count(),
                'active_rules': AlertRule.objects.filter(is_active=True).count(),
                'alerts_today': AlertLog.objects.filter(triggered_at__date=today).count(),
                'alerts_this_week': AlertLog.objects.filter(triggered_at__gte=week_ago).count(),
                'unresolved_alerts': unresolved.count(),
                'resolved_today': AlertLog.objects.filter(is_resolved=True, resolved_at__date=today).count(),
                'critical_active': unresolved.filter(rule__severity='critical').count(),
                'high_active': unresolved.filter(rule__severity='high').count(),
            })
        except Exception as e:
            logger.error(f"Error getting alert overview: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Alert analytics data"""
        try:
            days = int(request.query_params.get('days', 7))
            stats = AnalyticsService.get_alert_statistics(days)
            return Response(stats)
        except Exception as e:
            logger.error(f"Error getting alert analytics: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Alert performance metrics"""
        try:
            days = int(request.query_params.get('days', 30))
            performance = AnalyticsService.get_rule_performance(days)
            return Response(performance)
        except Exception as e:
            logger.error(f"Error getting alert performance: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlertMaintenanceViewSet(viewsets.ViewSet):
    """Alert maintenance operations ViewSet"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @action(detail=False, methods=['post'])
    def cleanup_old_alerts(self, request):
        """Clean up old resolved alerts"""
        try:
            days = int(request.data.get('days', 90))
            deleted_count = AlertMaintenanceService.cleanup_old_alerts(days)
            return Response({'success': True, 'deleted_count': deleted_count})
        except Exception as e:
            logger.error(f"Error cleaning up old alerts: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def update_rule_health(self, request):
        """Update health status for alert rules"""
        try:
            updated_count = AlertMaintenanceService.update_rule_health()
            return Response({'success': True, 'updated_count': updated_count})
        except Exception as e:
            logger.error(f"Error updating rule health: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def optimize_indexes(self, request):
        """Optimize database indexes"""
        try:
            success = AlertMaintenanceService.optimize_alert_indexes()
            return Response({'success': success})
        except Exception as e:
            logger.error(f"Error optimizing indexes: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
