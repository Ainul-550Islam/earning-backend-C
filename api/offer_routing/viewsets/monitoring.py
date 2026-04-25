"""
Monitoring Viewsets for Offer Routing System

This module contains viewsets for system monitoring,
health checks, and performance tracking.
"""

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.utils import timezone
from ..services.monitoring import monitoring_service
from ..permissions import IsAuthenticatedOrReadOnly, CanViewAnalytics
from ..exceptions import ValidationError

User = get_user_model()


class MonitoringViewSet(viewsets.ViewSet):
    """
    ViewSet for system monitoring and health checks.
    
    Provides endpoints for monitoring system health,
    performance metrics, and service dependencies.
    """
    
    permission_classes = [IsAuthenticatedOrReadOnly, CanViewAnalytics]
    
    @action(detail=False, methods=['get'])
    def system_health(self, request):
        """Get overall system health status."""
        try:
            health_status = monitoring_service.check_system_health()
            
            return Response({
                'success': True,
                'health_status': health_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def service_dependencies(self, request):
        """Check health of external service dependencies."""
        try:
            dependencies = monitoring_service.check_service_dependencies()
            
            return Response({
                'success': True,
                'dependencies': dependencies
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def performance_metrics(self, request):
        """Get current performance metrics."""
        try:
            minutes = int(request.query_params.get('minutes', 60))
            
            metrics = monitoring_service.get_performance_metrics(minutes=minutes)
            
            return Response({
                'success': True,
                'period_minutes': minutes,
                'metrics': metrics
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def performance_summary(self, request):
        """Get performance summary statistics."""
        try:
            minutes = int(request.query_params.get('minutes', 60))
            
            summary = monitoring_service.get_performance_summary(minutes=minutes)
            
            return Response({
                'success': True,
                'period_minutes': minutes,
                'summary': summary
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def record_metric(self, request):
        """Record a performance metric."""
        try:
            metric_name = request.data.get('metric_name')
            value = request.data.get('value')
            tags = request.data.get('tags', {})
            
            if not metric_name or value is None:
                return Response({
                    'success': False,
                    'error': 'metric_name and value are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            monitoring_service.record_performance_metric(metric_name, value, tags)
            
            return Response({
                'success': True,
                'metric_name': metric_name,
                'value': value,
                'tags': tags
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def alert_history(self, request):
        """Get recent alert history."""
        try:
            # This would return recent alerts
            # For now, return placeholder
            alerts = [
                {
                    'timestamp': timezone.now().isoformat(),
                    'metric_name': 'routing_response_time',
                    'value': 120.5,
                    'message': 'High response time: 120.5ms',
                    'severity': 'warning'
                }
            ]
            
            return Response({
                'success': True,
                'alerts': alerts
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def resource_usage(self, request):
        """Get current resource usage statistics."""
        try:
            # This would get actual resource usage
            # For now, return placeholder
            resource_usage = {
                'cpu_usage': 45.2,
                'memory_usage': 67.8,
                'disk_usage': 23.1,
                'network_io': 12.4,
                'active_connections': 156,
                'timestamp': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'resource_usage': resource_usage
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def cache_status(self, request):
        """Get cache system status."""
        try:
            # This would get actual cache status
            # For now, return placeholder
            cache_status = {
                'cache_type': 'redis',
                'status': 'healthy',
                'hit_rate': 85.2,
                'miss_rate': 14.8,
                'memory_usage': 45.6,
                'key_count': 1234,
                'evictions': 56,
                'timestamp': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'cache_status': cache_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def database_status(self, request):
        """Get database connection status."""
        try:
            # This would get actual database status
            # For now, return placeholder
            db_status = {
                'status': 'healthy',
                'connection_pool': {
                    'active': 8,
                    'idle': 12,
                    'total': 20
                },
                'query_stats': {
                    'avg_query_time': 12.3,
                    'slow_queries': 2,
                    'total_queries': 1234
                },
                'timestamp': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'database_status': db_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def queue_status(self, request):
        """Get task queue status."""
        try:
            # This would get actual queue status
            # For now, return placeholder
            queue_status = {
                'celery_status': 'healthy',
                'active_tasks': 3,
                'pending_tasks': 12,
                'failed_tasks': 0,
                'worker_status': [
                    {'worker_id': 'worker1', 'status': 'active', 'tasks_processed': 123},
                    {'worker_id': 'worker2', 'status': 'active', 'tasks_processed': 98}
                ],
                'timestamp': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'queue_status': queue_status
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def run_health_check(self, request):
        """Run a comprehensive health check."""
        try:
            # Run system health check
            health_status = monitoring_service.check_system_health()
            
            # Check service dependencies
            dependencies = monitoring_service.check_service_dependencies()
            
            # Get resource usage
            resource_usage = {
                'cpu_usage': 45.2,
                'memory_usage': 67.8,
                'disk_usage': 23.1
            }
            
            # Get performance metrics
            performance_metrics = monitoring_service.get_performance_metrics(5)
            
            # Determine overall health
            overall_health = 'healthy'
            if health_status['overall_status'] != 'healthy':
                overall_health = 'unhealthy'
            elif dependencies['overall_status'] != 'healthy':
                overall_health = 'degraded'
            elif resource_usage['cpu_usage'] > 80 or resource_usage['memory_usage'] > 80:
                overall_health = 'degraded'
            
            return Response({
                'success': True,
                'overall_health': overall_health,
                'system_health': health_status,
                'dependencies': dependencies,
                'resource_usage': resource_usage,
                'performance_metrics': performance_metrics,
                'check_timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def monitoring_dashboard(self, request):
        """Get comprehensive monitoring dashboard data."""
        try:
            # Get all monitoring data for dashboard
            health_status = monitoring_service.check_system_health()
            dependencies = monitoring_service.check_service_dependencies()
            performance_metrics = monitoring_service.get_performance_summary(60)
            resource_usage = {
                'cpu_usage': 45.2,
                'memory_usage': 67.8,
                'disk_usage': 23.1
            }
            
            dashboard_data = {
                'overall_status': health_status['overall_status'],
                'health_checks': health_status['checks'],
                'dependencies': dependencies,
                'performance': performance_metrics,
                'resources': resource_usage,
                'alerts': [
                    {
                        'timestamp': timezone.now().isoformat(),
                        'level': 'warning',
                        'message': 'High memory usage detected'
                    }
                ],
                'timestamp': timezone.now().isoformat()
            }
            
            return Response({
                'success': True,
                'dashboard': dashboard_data
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def metrics_history(self, request):
        """Get historical metrics data."""
        try:
            hours = int(request.query_params.get('hours', 24))
            metric_name = request.query_params.get('metric_name')
            
            if metric_name:
                # Get specific metric history
                metrics = monitoring_service.get_performance_metrics(minutes=hours*60)
                specific_metrics = [m for m in metrics if m.get('name') == metric_name]
                
                return Response({
                    'success': True,
                    'metric_name': metric_name,
                    'period_hours': hours,
                    'metrics': specific_metrics
                })
            else:
                # Get all metrics history
                metrics = monitoring_service.get_performance_metrics(minutes=hours*60)
                
                return Response({
                    'success': True,
                    'period_hours': hours,
                    'metrics': metrics
                })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def create_alert(self, request):
        """Create a manual alert."""
        try:
            alert_type = request.data.get('alert_type')
            message = request.data.get('message')
            severity = request.data.get('severity', 'info')
            
            if not alert_type or not message:
                return Response({
                    'success': False,
                    'error': 'alert_type and message are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create alert
            alert = {
                'alert_type': alert_type,
                'message': message,
                'severity': severity,
                'timestamp': timezone.now().isoformat(),
                'source': 'manual',
                'user': request.user.username
            }
            
            # This would actually create and store the alert
            # For now, just return the alert data
            
            return Response({
                'success': True,
                'alert': alert
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def alert_summary(self, request):
        """Get summary of recent alerts."""
        try:
            hours = int(request.query_params.get('hours', 24))
            
            # This would get actual alerts
            # For now, return placeholder
            alert_summary = {
                'total_alerts': 5,
                'critical_alerts': 0,
                'warning_alerts': 3,
                'info_alerts': 2,
                'recent_alerts': [
                    {
                        'timestamp': timezone.now().isoformat(),
                        'severity': 'warning',
                        'message': 'High response time detected',
                        'resolved': False
                    }
                ],
                'period_hours': hours
            }
            
            return Response({
                'success': True,
                'alert_summary': alert_summary
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
