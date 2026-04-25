"""Webhook Analytics ViewSet

This viewset handles webhook analytics CRUD operations
including statistics, performance metrics, and health monitoring.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ...models import WebhookAnalytics
from ...serializers import WebhookAnalyticsSerializer
from ...services.analytics import HealthMonitorService
from ...constants import DeliveryStatus


class WebhookAnalyticsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook analytics CRUD operations.
    Provides comprehensive analytics and performance monitoring.
    """
    
    queryset = WebhookAnalytics.objects.all()
    serializer_class = WebhookAnalyticsSerializer
    lookup_field = 'id'
    
    def get_permissions(self):
        """Get permissions for analytics viewset."""
        if self.action in ['list', 'retrieve']:
            return ['webhooks.view_webhook_analytics']
        return ['webhooks.manage_webhook_analytics']
    
    @action(detail=True, methods=['get'], url_path='health-summary')
    def health_summary(self, request, pk=None):
        """Get health summary for all endpoints."""
        health_service = HealthMonitorService()
        
        # Get all active endpoints
        from ...models import WebhookEndpoint
        active_endpoints = WebhookEndpoint.objects.filter(status='active')
        
        summaries = []
        for endpoint in active_endpoints:
            summary = health_service.get_endpoint_health_summary(endpoint, hours=24)
            if summary:
                summaries.append(summary)
        
        return Response({
            'success': True,
            'data': {
                'total_endpoints': len(active_endpoints),
                'health_summaries': summaries,
                'generated_at': timezone.now(),
            }
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='performance-report')
    def performance_report(self, request, pk=None):
        """Get performance report for specified period."""
        days = request.query_params.get('days', 30)
        
        # Get analytics data for period
        from django.utils import timezone
        since = timezone.now() - timezone.timedelta(days=int(days))
        
        analytics_data = WebhookAnalytics.objects.filter(
            date__gte=since.date()
        ).order_by('date', 'endpoint')
        
        # Calculate performance metrics
        total_sent = sum(data.total_sent for data in analytics_data)
        total_success = sum(data.success_count for data in analytics_data)
        total_failed = sum(data.failed_count for data in analytics_data)
        avg_latency = sum(data.avg_latency_ms for data in analytics_data) / len(analytics_data) if analytics_data else 0
        
        # Group by endpoint
        endpoint_performance = {}
        for data in analytics_data:
            endpoint_id = data.endpoint.id
            if endpoint_id not in endpoint_performance:
                endpoint_performance[endpoint_id] = {
                    'endpoint_url': data.endpoint.url,
                    'total_sent': 0,
                    'success_count': 0,
                    'failed_count': 0,
                    'avg_latency': 0,
                }
            
            endpoint_performance[endpoint_id]['total_sent'] += data.total_sent
            endpoint_performance[endpoint_id]['success_count'] += data.success_count
            endpoint_performance[endpoint_id]['failed_count'] += data.failed_count
            endpoint_performance[endpoint_id]['avg_latency'] = (
                (endpoint_performance[endpoint_id]['avg_latency'] + data.avg_latency_ms) / 2
            )
        
        return Response({
            'success': True,
            'data': {
                'period_days': int(days),
                'total_sent': total_sent,
                'total_success': total_success,
                'total_failed': total_failed,
                'avg_latency_ms': round(avg_latency, 2),
                'overall_success_rate': round((total_success / total_sent) * 100, 2) if total_sent > 0 else 0,
                'endpoint_performance': list(endpoint_performance.values()),
                'generated_at': timezone.now(),
            }
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], url_path='event-stats')
    def event_statistics(self, request, pk=None):
        """Get event type statistics for specified period."""
        days = request.query_params.get('days', 30)
        event_type = request.query_params.get('event_type')
        
        # Get event statistics
        from ...models import WebhookEventStat
        from django.utils import timezone
        since = timezone.now() - timezone.timedelta(days=int(days))
        
        queryset = WebhookEventStat.objects.filter(date__gte=since.date())
        
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        event_stats = queryset.order_by('-date')
        
        serializer = WebhookEventStatSerializer(event_stats, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], url_path='export-csv')
    def export_csv(self, request, pk=None):
        """Export analytics data as CSV."""
        days = request.query_params.get('days', 30)
        
        # Get analytics data
        from django.utils import timezone
        since = timezone.now() - timezone.timedelta(days=int(days))
        
        analytics_data = WebhookAnalytics.objects.filter(
            date__gte=since.date()
        ).order_by('date', 'endpoint')
        
        # Generate CSV response
        import csv
        from io import StringIO
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="webhook_analytics_{timezone.now().strftime("%Y%m%d")}.csv"'
        
        writer = csv.writer(response)
        
        # Write header
        writer.writerow([
            'Date', 'Endpoint', 'Total Sent', 'Success Count', 
            'Failed Count', 'Success Rate (%)', 'Avg Latency (ms)'
        ])
        
        # Write data
        for data in analytics_data:
            success_rate = round((data.success_count / data.total_sent) * 100, 2) if data.total_sent > 0 else 0
            writer.writerow([
                data.date.strftime('%Y-%m-%d'),
                data.endpoint.url,
                data.total_sent,
                data.success_count,
                data.failed_count,
                success_rate,
                round(data.avg_latency_ms, 2),
            ])
        
        return response
