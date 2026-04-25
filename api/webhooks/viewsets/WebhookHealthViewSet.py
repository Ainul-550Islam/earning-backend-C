"""Webhook Health ViewSet

This module contains the ViewSet for webhook health monitoring.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from ..models import WebhookHealthLog, WebhookEndpoint
from ..serializers import (
    WebhookHealthLogSerializer,
    WebhookHealthLogListSerializer,
    WebhookHealthLogDetailSerializer,
    WebhookHealthCheckSerializer,
    WebhookHealthCheckResultSerializer,
    WebhookHealthStatsSerializer,
    WebhookHealthTrendSerializer,
    WebhookHealthFilterSerializer,
    WebhookHealthBatchSerializer,
    WebhookHealthAlertSerializer
)
from ..permissions import IsOwnerOrReadOnly
from ..filters import WebhookHealthLogFilter


class WebhookHealthViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook health monitoring."""
    
    queryset = WebhookHealthLog.objects.all()
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_class = WebhookHealthLogFilter
    
    def get_serializer_class(self):
        """Get appropriate serializer based on action."""
        if self.action == 'retrieve':
            return WebhookHealthLogDetailSerializer
        elif self.action == 'list':
            return WebhookHealthLogListSerializer
        else:
            return WebhookHealthLogSerializer
    
    def get_queryset(self):
        """Filter queryset to user's own health logs."""
        return super().get_queryset().filter(endpoint__owner=self.request.user)
    
    def perform_create(self, serializer):
        """Set created_by field on creation."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def check_health(self, request):
        """Check health for endpoints."""
        serializer = WebhookHealthCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_id = serializer.validated_data.get('endpoint_id')
        all_endpoints = serializer.validated_data.get('all_endpoints', False)
        
        try:
            from ..services.analytics import HealthMonitorService
            health_service = HealthMonitorService()
            
            if all_endpoints:
                # Check all endpoints
                endpoints = WebhookEndpoint.objects.filter(owner=request.user)
                results = []
                
                for endpoint in endpoints:
                    try:
                        health_result = health_service.check_endpoint_health(endpoint)
                        results.append({
                            'endpoint_id': str(endpoint.id),
                            'endpoint_label': endpoint.label,
                            'endpoint_url': endpoint.url,
                            'is_healthy': health_result['is_healthy'],
                            'status_code': health_result.get('status_code'),
                            'response_time_ms': health_result.get('response_time_ms'),
                            'error': health_result.get('error'),
                            'checked_at': timezone.now().isoformat()
                        })
                    except Exception as e:
                        results.append({
                            'endpoint_id': str(endpoint.id),
                            'endpoint_label': endpoint.label,
                            'endpoint_url': endpoint.url,
                            'is_healthy': False,
                            'error': str(e),
                            'checked_at': timezone.now().isoformat()
                        })
                
                return Response({
                    'success': True,
                    'results': results,
                    'total_endpoints': len(results)
                })
            else:
                # Check specific endpoint
                endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
                health_result = health_service.check_endpoint_health(endpoint)
                
                result = {
                    'endpoint_id': str(endpoint.id),
                    'endpoint_label': endpoint.label,
                    'endpoint_url': endpoint.url,
                    'is_healthy': health_result['is_healthy'],
                    'status_code': health_result.get('status_code'),
                    'response_time_ms': health_result.get('response_time_ms'),
                    'error': health_result.get('error'),
                    'checked_at': timezone.now().isoformat()
                }
                
                return Response(result)
                
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['post'])
    def batch_check(self, request):
        """Check health for multiple endpoints."""
        serializer = WebhookHealthBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        endpoint_ids = serializer.validated_data['endpoint_ids']
        
        try:
            from ..services.analytics import HealthMonitorService
            health_service = HealthMonitorService()
            
            results = []
            for endpoint_id in endpoint_ids:
                try:
                    endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
                    health_result = health_service.check_endpoint_health(endpoint)
                    
                    results.append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'is_healthy': health_result['is_healthy'],
                        'status_code': health_result.get('status_code'),
                        'response_time_ms': health_result.get('response_time_ms'),
                        'error': health_result.get('error'),
                        'checked_at': timezone.now().isoformat()
                    })
                except WebhookEndpoint.DoesNotExist:
                    results.append({
                        'endpoint_id': str(endpoint_id),
                        'endpoint_label': 'Unknown',
                        'endpoint_url': 'Unknown',
                        'is_healthy': False,
                        'error': 'Endpoint not found',
                        'checked_at': timezone.now().isoformat()
                    })
                except Exception as e:
                    results.append({
                        'endpoint_id': str(endpoint_id),
                        'endpoint_label': 'Unknown',
                        'endpoint_url': 'Unknown',
                        'is_healthy': False,
                        'error': str(e),
                        'checked_at': timezone.now().isoformat()
                    })
            
            return Response({
                'success': True,
                'results': results,
                'total_endpoints': len(results)
            })
            
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get health statistics for an endpoint."""
        health_log = self.get_object()
        endpoint = health_log.endpoint
        
        # Get health statistics for this endpoint
        health_logs = endpoint.health_logs.all()
        
        total_checks = health_logs.count()
        healthy_checks = health_logs.filter(is_healthy=True).count()
        unhealthy_checks = health_logs.filter(is_healthy=False).count()
        uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Get performance statistics
        if healthy_checks > 0:
            avg_response_time = healthy_logs.aggregate(
                models.Avg('response_time_ms')
            )['response_time_ms__avg'] or 0
            
            min_response_time = healthy_logs.aggregate(
                models.Min('response_time_ms')
            )['response_time_ms__min'] or 0
            
            max_response_time = healthy_logs.aggregate(
                models.Max('response_time_ms')
            )['response_time_ms__max'] or 0
        else:
            avg_response_time = 0
            min_response_time = 0
            max_response_time = 0
        
        # Get recent statistics
        from datetime import timedelta
        recent_logs = health_logs.filter(
            checked_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        recent_total = recent_logs.count()
        recent_healthy = recent_logs.filter(is_healthy=True).count()
        recent_uptime = (recent_healthy / recent_total * 100) if recent_total > 0 else 0
        
        return Response({
            'endpoint_id': str(endpoint.id),
            'endpoint_label': endpoint.label,
            'endpoint_url': endpoint.url,
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': unhealthy_checks,
            'uptime_percentage': round(uptime_percentage, 2),
            'avg_response_time_ms': round(avg_response_time, 2),
            'min_response_time_ms': min_response_time,
            'max_response_time_ms': max_response_time,
            'recent_uptime_24h': round(recent_uptime, 2),
            'last_check': health_log.checked_at.isoformat()
        })
    
    @action(detail=False, methods=['get'])
    def by_endpoint(self, request):
        """Get health logs by endpoint ID."""
        endpoint_id = request.query_params.get('endpoint_id')
        if not endpoint_id:
            return Response({
                'error': 'endpoint_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            endpoint = WebhookEndpoint.objects.get(id=endpoint_id, owner=request.user)
        except WebhookEndpoint.DoesNotExist:
            return Response({
                'error': 'Endpoint not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        health_logs = self.get_queryset().filter(endpoint=endpoint)
        
        page = self.paginate_queryset(health_logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(health_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_status(self, request):
        """Get health logs by status."""
        is_healthy = request.query_params.get('is_healthy')
        if is_healthy is not None:
            health_logs = self.get_queryset().filter(is_healthy=is_healthy.lower() == 'true')
        else:
            health_logs = self.get_queryset()
        
        page = self.paginate_queryset(health_logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(health_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent health logs."""
        hours = int(request.query_params.get('hours', 24))
        since = timezone.now() - timezone.timedelta(hours=hours)
        
        health_logs = self.get_queryset().filter(checked_at__gte=since)
        
        page = self.paginate_queryset(health_logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(health_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unhealthy(self, request):
        """Get unhealthy endpoints."""
        # Get endpoints with recent unhealthy checks
        from datetime import timedelta
        since = timezone.now() - timedelta(hours=24)
        
        unhealthy_logs = self.get_queryset().filter(
            is_healthy=False,
            checked_at__gte=since
        )
        
        page = self.paginate_queryset(unhealthy_logs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(unhealthy_logs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get health overview for all endpoints."""
        endpoints = WebhookEndpoint.objects.filter(owner=request.user)
        
        overview = []
        for endpoint in endpoints:
            # Get recent health logs
            from datetime import timedelta
            since = timezone.now() - timedelta(hours=24)
            
            health_logs = endpoint.health_logs.filter(checked_at__gte=since)
            
            if health_logs.exists():
                total_checks = health_logs.count()
                healthy_checks = health_logs.filter(is_healthy=True).count()
                uptime = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
                
                last_check = health_logs.order_by('-checked_at').first()
                
                overview.append({
                    'endpoint_id': str(endpoint.id),
                    'endpoint_label': endpoint.label,
                    'endpoint_url': endpoint.url,
                    'status': endpoint.status,
                    'uptime_24h': round(uptime, 2),
                    'total_checks_24h': total_checks,
                    'healthy_checks_24h': healthy_checks,
                    'last_check': last_check.checked_at.isoformat(),
                    'is_healthy': last_check.is_healthy
                })
            else:
                overview.append({
                    'endpoint_id': str(endpoint.id),
                    'endpoint_label': endpoint.label,
                    'endpoint_url': endpoint.url,
                    'status': endpoint.status,
                    'uptime_24h': 0,
                    'total_checks_24h': 0,
                    'healthy_checks_24h': 0,
                    'last_check': None,
                    'is_healthy': None
                })
        
        return Response({
            'overview': overview,
            'total_endpoints': len(overview)
        })
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Get health trends over time."""
        days = int(request.query_params.get('days', 7))
        since = timezone.now() - timezone.timedelta(days=days)
        
        # Get daily trends
        trends = []
        for day in range(days):
            date = (timezone.now() - timezone.timedelta(days=day)).date()
            
            day_logs = self.get_queryset().filter(checked_at__date=date)
            total_checks = day_logs.count()
            healthy_checks = day_logs.filter(is_healthy=True).count()
            uptime = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
            
            # Get average response time
            avg_response_time = 0
            if healthy_checks > 0:
                avg_response_time = day_logs.filter(is_healthy=True).aggregate(
                    models.Avg('response_time_ms')
                )['response_time_ms__avg'] or 0
            
            trends.append({
                'date': date.isoformat(),
                'total_checks': total_checks,
                'healthy_checks': healthy_checks,
                'unhealthy_checks': total_checks - healthy_checks,
                'uptime_percentage': round(uptime, 2),
                'avg_response_time_ms': round(avg_response_time, 2)
            })
        
        return Response({
            'trends': trends,
            'days': days
        })
    
    @action(detail=False, methods=['get'])
    def alerts(self, request):
        """Get health alerts for endpoints."""
        alerts = []
        
        endpoints = WebhookEndpoint.objects.filter(owner=request.user)
        
        for endpoint in endpoints:
            # Check for consecutive failures
            from datetime import timedelta
            since = timezone.now() - timedelta(hours=24)
            
            recent_logs = endpoint.health_logs.filter(checked_at__gte=since).order_by('-checked_at')
            
            if recent_logs.count() >= 3:
                # Check last 3 checks
                last_three = recent_logs[:3]
                if all(not log.is_healthy for log in last_three):
                    alerts.append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'alert_type': 'consecutive_failures',
                        'message': 'Endpoint has 3 consecutive health check failures',
                        'severity': 'high',
                        'created_at': last_three[0].checked_at.isoformat()
                    })
            
            # Check for high response times
            recent_healthy = recent_logs.filter(is_healthy=True)
            if recent_healthy.exists():
                avg_response_time = recent_healthy.aggregate(
                    models.Avg('response_time_ms')
                )['response_time_ms__avg'] or 0
                
                if avg_response_time > 5000:  # 5 seconds threshold
                    alerts.append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_label': endpoint.label,
                        'endpoint_url': endpoint.url,
                        'alert_type': 'high_response_time',
                        'message': f'Endpoint has high average response time: {round(avg_response_time, 2)}ms',
                        'severity': 'medium',
                        'created_at': recent_healthy[0].checked_at.isoformat()
                    })
        
        # Sort by severity and creation time
        severity_order = {'high': 3, 'medium': 2, 'low': 1}
        alerts.sort(key=lambda x: (severity_order.get(x['severity'], 0), x['created_at']), reverse=True)
        
        return Response({
            'alerts': alerts[:50],  # Limit to 50 most recent alerts
            'total_alerts': len(alerts)
        })
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get overall health statistics."""
        endpoints = WebhookEndpoint.objects.filter(owner=request.user)
        
        # Get overall statistics
        from django.db.models import Count, Avg
        
        health_logs = WebhookHealthLog.objects.filter(endpoint__in=endpoints)
        
        total_checks = health_logs.count()
        healthy_checks = health_logs.filter(is_healthy=True).count()
        unhealthy_checks = health_logs.filter(is_healthy=False).count()
        uptime_percentage = (healthy_checks / total_checks * 100) if total_checks > 0 else 0
        
        # Get performance statistics
        avg_response_time = 0
        if healthy_checks > 0:
            avg_response_time = health_logs.filter(is_healthy=True).aggregate(
                avg_time=Avg('response_time_ms')
            )['avg_time'] or 0
        
        # Get endpoint status breakdown
        status_breakdown = endpoints.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        return Response({
            'total_endpoints': endpoints.count(),
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': unhealthy_checks,
            'overall_uptime': round(uptime_percentage, 2),
            'avg_response_time_ms': round(avg_response_time, 2),
            'status_breakdown': list(status_breakdown)
        })
    
    @action(detail=False, methods=['post'])
    def schedule_checks(self, request):
        """Schedule health checks for all endpoints."""
        try:
            from ..tasks.health_check_tasks import schedule_health_checks
            
            # Queue the task
            schedule_health_checks.delay()
            
            return Response({
                'success': True,
                'message': 'Health check scheduling task queued successfully'
            })
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Failed to schedule health checks'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
