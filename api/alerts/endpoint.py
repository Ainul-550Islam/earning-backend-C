"""
API endpoint definitions and routing for alerts app
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db.models import Count
from django.http import JsonResponse
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


# API Router
router = DefaultRouter()

# Register viewsets
try:
    from .viewsets.core import (
        AlertRuleViewSet, AlertLogViewSet, NotificationViewSet,
        SystemHealthViewSet, AlertOverviewViewSet
    )
    router.register(r'rules', AlertRuleViewSet, basename='alert-rules')
    router.register(r'logs', AlertLogViewSet, basename='alert-logs')
    router.register(r'notifications', NotificationViewSet, basename='alert-notifications')
    router.register(r'health', SystemHealthViewSet, basename='system-health')
    router.register(r'overview', AlertOverviewViewSet, basename='alert-overview')
except ImportError as e:
    logger.error(f"Could not import viewsets: {e}")


# API Endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_info(request):
    """API information endpoint"""
    return Response({
        'name': 'Alerts API',
        'version': '1.0.0',
        'description': 'Alert management and monitoring API',
        'endpoints': {
            'rules': '/api/v1/rules/',
            'logs': '/api/v1/logs/',
            'notifications': '/api/v1/notifications/',
            'health': '/api/v1/health/',
            'overview': '/api/v1/overview/',
            'webhooks': '/api/v1/webhooks/',
            'analytics': '/api/v1/analytics/',
            'export': '/api/v1/export/'
        },
        'timestamp': timezone.now().isoformat()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_alert(request):
    """Trigger an alert"""
    try:
        from .services import LegacyAlertProcessorService as AlertProcessorService
        
        rule_id = request.data.get('rule_id')
        trigger_value = request.data.get('trigger_value')
        message = request.data.get('message')
        details = request.data.get('details', {})
        
        if not all([rule_id, trigger_value, message]):
            return Response({
                'error': 'Missing required fields',
                'required': ['rule_id', 'trigger_value', 'message']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        alert_log = AlertProcessorService.process_alert(
            rule_id=rule_id,
            trigger_value=trigger_value,
            message=message,
            details=details
        )
        
        if alert_log:
            return Response({
                'success': True,
                'alert_id': alert_log.id,
                'message': 'Alert triggered successfully'
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                'success': False,
                'error': 'Failed to process alert'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    except Exception as e:
        logger.error(f"Error triggering alert: {e}")
        return Response({
            'error': 'Internal server error',
            'detail': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_statistics(request):
    """Get alert statistics"""
    try:
        from .models import AlertRule, AlertLog
        
        # Time range
        days = int(request.GET.get('days', 7))
        end_date = timezone.now()
        start_date = end_date - timezone.timedelta(days=days)
        
        # Rule statistics
        total_rules = AlertRule.objects.count()
        active_rules = AlertRule.objects.filter(is_active=True).count()
        
        # Alert statistics
        total_alerts = AlertLog.objects.count()
        resolved_alerts = AlertLog.objects.filter(is_resolved=True).count()
        unresolved_alerts = total_alerts - resolved_alerts
        
        # Time-based statistics
        recent_alerts = AlertLog.objects.filter(
            triggered_at__gte=start_date
        ).count()
        
        # Severity breakdown
        severity_breakdown = AlertLog.objects.filter(
            triggered_at__gte=start_date
        ).values('rule__severity').annotate(
            count=Count('id')
        ).order_by('rule__severity')
        
        # Resolution rate
        resolution_rate = (resolved_alerts / total_alerts * 100) if total_alerts > 0 else 0
        
        return Response({
            'time_range': {
                'days': days,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'rules': {
                'total': total_rules,
                'active': active_rules,
                'inactive': total_rules - active_rules
            },
            'alerts': {
                'total': total_alerts,
                'resolved': resolved_alerts,
                'unresolved': unresolved_alerts,
                'recent': recent_alerts,
                'resolution_rate': round(resolution_rate, 2)
            },
            'severity_breakdown': list(severity_breakdown)
        })
    
    except Exception as e:
        logger.error(f"Error getting alert statistics: {e}")
        return Response({
            'error': 'Internal server error',
            'detail': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_metrics(request):
    """Get system metrics"""
    try:
        from .models import SystemMetrics, SystemHealthCheck
        
        # Get latest metrics
        latest_metrics = SystemMetrics.objects.order_by('-timestamp').first()
        
        # Get health checks
        health_checks = SystemHealthCheck.objects.filter(
            is_active=True
        ).order_by('-last_checked')[:10]
        
        # Calculate overall health
        if health_checks.exists():
            healthy_count = health_checks.filter(status='healthy').count()
            total_count = health_checks.count()
            health_percentage = (healthy_count / total_count) * 100
        else:
            health_percentage = 0
        
        metrics_data = {}
        if latest_metrics:
            metrics_data = {
                'timestamp': latest_metrics.timestamp.isoformat(),
                'cpu_usage_percent': latest_metrics.cpu_usage_percent,
                'memory_usage_percent': latest_metrics.memory_usage_percent,
                'disk_usage_percent': latest_metrics.disk_usage_percent,
                'total_users': latest_metrics.total_users,
                'active_users_1h': latest_metrics.active_users_1h,
                'total_earnings_1h': latest_metrics.total_earnings_1h,
                'fraud_indicators_1h': latest_metrics.fraud_indicators_1h
            }
        
        return Response({
            'metrics': metrics_data,
            'health': {
                'overall_percentage': round(health_percentage, 1),
                'status': 'healthy' if health_percentage >= 80 else 'degraded' if health_percentage >= 60 else 'unhealthy',
                'checks': [
                    {
                        'name': check.check_name,
                        'type': check.check_type,
                        'status': check.status,
                        'response_time_ms': check.response_time_ms,
                        'checked_at': check.last_checked.isoformat() if check.last_checked else None
                    }
                    for check in health_checks
                ]
            }
        })
    
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return Response({
            'error': 'Internal server error',
            'detail': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def alert_rules_bulk(request):
    """Bulk operations on alert rules"""
    try:
        if request.method == 'GET':
            # Get bulk alert rules
            rule_ids = request.GET.getlist('ids')
            if not rule_ids:
                return Response({
                    'error': 'No rule IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from .models import AlertRule
            rules = AlertRule.objects.filter(id__in=rule_ids)
            
            from .serializers import AlertRuleSerializer
            serializer = AlertRuleSerializer(rules, many=True)
            
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Bulk update alert rules
            rule_ids = request.data.get('ids', [])
            updates = request.data.get('updates', {})
            
            if not rule_ids:
                return Response({
                    'error': 'No rule IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from .models import AlertRule
            updated_count = AlertRule.objects.filter(id__in=rule_ids).update(**updates)
            
            return Response({
                'message': f'Updated {updated_count} alert rules',
                'updated_count': updated_count
            })
    
    except Exception as e:
        logger.error(f"Error in bulk alert rules operation: {e}")
        return Response({
            'error': 'Internal server error',
            'detail': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def alert_logs_bulk(request):
    """Bulk operations on alert logs"""
    try:
        if request.method == 'GET':
            # Get bulk alert logs
            alert_ids = request.GET.getlist('ids')
            if not alert_ids:
                return Response({
                    'error': 'No alert IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from .models import AlertLog
            alerts = AlertLog.objects.filter(id__in=alert_ids).select_related('rule')
            
            from .serializers import AlertLogSerializer
            serializer = AlertLogSerializer(alerts, many=True)
            
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Bulk update alert logs
            alert_ids = request.data.get('ids', [])
            updates = request.data.get('updates', {})
            
            if not alert_ids:
                return Response({
                    'error': 'No alert IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            from .models import AlertLog
            updated_count = AlertLog.objects.filter(id__in=alert_ids).update(**updates)
            
            return Response({
                'message': f'Updated {updated_count} alert logs',
                'updated_count': updated_count
            })
    
    except Exception as e:
        logger.error(f"Error in bulk alert logs operation: {e}")
        return Response({
            'error': 'Internal server error',
            'detail': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_data(request):
    """Export alert data"""
    try:
        export_type = request.GET.get('type', 'alerts')
        format_type = request.GET.get('format', 'csv')
        
        if export_type not in ['alerts', 'rules', 'notifications']:
            return Response({
                'error': 'Invalid export type',
                'valid_types': ['alerts', 'rules', 'notifications']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if format_type not in ['csv', 'json', 'xlsx']:
            return Response({
                'error': 'Invalid export format',
                'valid_formats': ['csv', 'json', 'xlsx']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get data based on export type
        if export_type == 'alerts':
            from .models import AlertLog
            queryset = AlertLog.objects.select_related('rule').order_by('-triggered_at')
        elif export_type == 'rules':
            from .models import AlertRule
            queryset = AlertRule.objects.all().order_by('-created_at')
        elif export_type == 'notifications':
            from .models import Notification
            queryset = Notification.objects.select_related('alert_log').order_by('-created_at')
        
        # Apply filters
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        # Generate export
        if format_type == 'csv':
            return _export_csv(queryset, export_type)
        elif format_type == 'json':
            return _export_json(queryset, export_type)
        elif format_type == 'xlsx':
            return _export_xlsx(queryset, export_type)
    
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return Response({
            'error': 'Internal server error',
            'detail': 'Internal server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _export_csv(queryset, export_type):
    """Export queryset to CSV"""
    import csv
    from django.http import HttpResponse
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    if export_type == 'alerts':
        writer.writerow(['ID', 'Rule Name', 'Severity', 'Message', 'Triggered At', 'Resolved At', 'Status'])
        for alert in queryset:
            writer.writerow([
                alert.id,
                alert.rule.name,
                alert.rule.severity,
                alert.message,
                alert.triggered_at,
                alert.resolved_at,
                'Resolved' if alert.is_resolved else 'Unresolved'
            ])
    elif export_type == 'rules':
        writer.writerow(['ID', 'Name', 'Alert Type', 'Severity', 'Threshold', 'Is Active', 'Created At'])
        for rule in queryset:
            writer.writerow([
                rule.id,
                rule.name,
                rule.alert_type,
                rule.severity,
                rule.threshold_value,
                rule.is_active,
                rule.created_at
            ])
    elif export_type == 'notifications':
        writer.writerow(['ID', 'Type', 'Recipient', 'Status', 'Created At', 'Sent At'])
        for notification in queryset:
            writer.writerow([
                notification.id,
                notification.notification_type,
                notification.recipient,
                notification.status,
                notification.created_at,
                notification.sent_at
            ])
    
    response = HttpResponse(
        output.getvalue(),
        content_type='text/csv'
    )
    response['Content-Disposition'] = f'attachment; filename="{export_type}_export.csv"'
    return response


def _export_json(queryset, export_type):
    """Export queryset to JSON"""
    from django.http import HttpResponse
    import json
    
    data = []
    
    if export_type == 'alerts':
        for alert in queryset:
            data.append({
                'id': alert.id,
                'rule_name': alert.rule.name,
                'severity': alert.rule.severity,
                'message': alert.message,
                'triggered_at': alert.triggered_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                'status': 'resolved' if alert.is_resolved else 'unresolved'
            })
    elif export_type == 'rules':
        for rule in queryset:
            data.append({
                'id': rule.id,
                'name': rule.name,
                'alert_type': rule.alert_type,
                'severity': rule.severity,
                'threshold_value': rule.threshold_value,
                'is_active': rule.is_active,
                'created_at': rule.created_at.isoformat()
            })
    elif export_type == 'notifications':
        for notification in queryset:
            data.append({
                'id': notification.id,
                'type': notification.notification_type,
                'recipient': notification.recipient,
                'status': notification.status,
                'created_at': notification.created_at.isoformat(),
                'sent_at': notification.sent_at.isoformat() if notification.sent_at else None
            })
    
    response = HttpResponse(
        json.dumps(data, indent=2),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="{export_type}_export.json"'
    return response


def _export_xlsx(queryset, export_type):
    """Export queryset to XLSX"""
    try:
        import openpyxl
        from django.http import HttpResponse
        from io import BytesIO
        
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = f'{export_type.title()} Export'
        
        if export_type == 'alerts':
            worksheet.append(['ID', 'Rule Name', 'Severity', 'Message', 'Triggered At', 'Resolved At', 'Status'])
            for alert in queryset:
                worksheet.append([
                    alert.id,
                    alert.rule.name,
                    alert.rule.severity,
                    alert.message,
                    alert.triggered_at,
                    alert.resolved_at,
                    'Resolved' if alert.is_resolved else 'Unresolved'
                ])
        elif export_type == 'rules':
            worksheet.append(['ID', 'Name', 'Alert Type', 'Severity', 'Threshold', 'Is Active', 'Created At'])
            for rule in queryset:
                worksheet.append([
                    rule.id,
                    rule.name,
                    rule.alert_type,
                    rule.severity,
                    rule.threshold_value,
                    rule.is_active,
                    rule.created_at
                ])
        elif export_type == 'notifications':
            worksheet.append(['ID', 'Type', 'Recipient', 'Status', 'Created At', 'Sent At'])
            for notification in queryset:
                worksheet.append([
                    notification.id,
                    notification.notification_type,
                    notification.recipient,
                    notification.status,
                    notification.created_at,
                    notification.sent_at
                ])
        
        # Save to BytesIO
        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{export_type}_export.xlsx"'
        return response
    
    except ImportError:
        return JsonResponse({
            'error': 'openpyxl is required for XLSX export'
        }, status=501)


# URL patterns
urlpatterns = [
    # API endpoints
    path('api/v1/', include(router.urls)),
    
    # Direct API views
    path('api/v1/info/', api_info, name='api_info'),
    path('api/v1/trigger/', trigger_alert, name='trigger_alert'),
    path('api/v1/statistics/', alert_statistics, name='alert_statistics'),
    path('api/v1/metrics/', system_metrics, name='system_metrics'),
    path('api/v1/rules/bulk/', alert_rules_bulk, name='alert_rules_bulk'),
    path('api/v1/logs/bulk/', alert_logs_bulk, name='alert_logs_bulk'),
    path('api/v1/export/', export_data, name='export_data'),
    
    # Webhook endpoints
    path('api/v1/webhooks/', include('api.alerts.urls.webhooks_urls')),
]


# API versioning
API_VERSIONS = {
    'v1': {
        'path': 'api/v1/',
        'description': 'Version 1 of the Alerts API',
        'deprecated': False
    }
}


def get_api_urls():
    """Get all API URLs"""
    return urlpatterns


def get_api_version_info():
    """Get API version information"""
    return {
        'current_version': 'v1',
        'versions': API_VERSIONS,
        'supported_formats': ['json', 'csv', 'xlsx'],
        'authentication': ['Bearer Token', 'Session'],
        'rate_limiting': {
            'requests_per_minute': 100,
            'requests_per_hour': 1000
        }
    }
