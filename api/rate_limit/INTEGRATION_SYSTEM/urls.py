from django.utils import timezone
import json
from typing import Dict, Any, List, Optional, Union, Tuple, Set, Callable
"""
Integration System URLs - API Endpoints

URL configuration for integration system API endpoints including
webhook receivers, health checks, monitoring endpoints, and admin interfaces.
"""

from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .integ_handler import integration_handler
from .webhooks_integration import webhook_manager
from .health_check import health_checker
from .performance_monitor import performance_monitor
from .integ_audit_logs import audit_logger
from .sync_manager import sync_manager
from .auth_bridge import auth_bridge
from .integ_registry import integration_registry
from .event_bus import event_bus
from .circuit_breaker import circuit_breaker_manager
from .data_bridge import data_bridge_manager
from .message_queue import message_queue_manager


class WebhookReceiverView(View):
    """Webhook receiver for external services."""
    
    def post(self, request, webhook_id):
        """Handle incoming webhook."""
        try:
            # Get webhook configuration
            webhook = webhook_manager.get_webhook(webhook_id)
            if not webhook:
                return JsonResponse({"error": "Webhook not found"}, status=404)
            
            # Verify webhook signature if configured
            if webhook.get("secret"):
                signature = request.headers.get("X-Webhook-Signature")
                if not webhook_manager.verify_webhook_signature(webhook_id, request.body, signature):
                    return JsonResponse({"error": "Invalid signature"}, status=401)
            
            # Process webhook
            event_data = {
                "webhook_id": webhook_id,
                "headers": dict(request.headers),
                "body": request.body.decode('utf-8'),
                "method": request.method,
                "timestamp": timezone.now().isoformat()
            }
            
            # Deliver webhook
            result = webhook_manager.deliver_webhook(webhook_id, event_data)
            
            if result.get("success"):
                return JsonResponse({"status": "success"}, status=200)
            else:
                return JsonResponse({"error": result.get("error", "Unknown error")}, status=500)
                
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    
    def get(self, request, webhook_id):
        """Webhook verification endpoint."""
        webhook = webhook_manager.get_webhook(webhook_id)
        if not webhook:
            return JsonResponse({"error": "Webhook not found"}, status=404)
        
        return JsonResponse({
            "webhook_id": webhook_id,
            "status": "active",
            "events": webhook.get("events", [])
        })


@method_decorator(csrf_exempt, name='dispatch')
class IntegrationEventView(View):
    """Integration event receiver."""
    
    def post(self, request):
        """Handle integration events."""
        try:
            # Parse event data
            try:
                event_data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({"error": "Invalid JSON"}, status=400)
            
            # Validate required fields
            if "event_type" not in event_data:
                return JsonResponse({"error": "Missing event_type"}, status=400)
            
            # Process event
            result = integration_handler.process_event(event_data)
            
            if result:
                return JsonResponse({"status": "success", "result": result}, status=200)
            else:
                return JsonResponse({"error": "Event processing failed"}, status=500)
                
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


# API Views
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def integration_status(request):
    """Get integration system status."""
    try:
        # Get health status
        health = health_checker.get_system_health()
        
        # Get performance stats
        perf_stats = performance_monitor.get_statistics()
        
        # Get circuit breaker status
        cb_stats = circuit_breaker_manager.get_statistics()
        
        # Get queue stats
        queue_stats = message_queue_manager.get_statistics()
        
        return Response({
            "status": "healthy",
            "health": {
                "overall_status": health.status.value,
                "score": health.score,
                "uptime_hours": health.uptime_seconds / 3600,
                "issues": health.issues,
                "recommendations": health.recommendations
            },
            "performance": {
                "total_metrics": perf_stats['total_metrics'],
                "total_snapshots": perf_stats['total_snapshots'],
                "average_execution_time": perf_stats['average_execution_time'],
                "uptime_hours": perf_stats['uptime_hours']
            },
            "circuit_breakers": {
                "total_breakers": cb_stats['total_breakers'],
                "open_breakers": cb_stats['open_breakers'],
                "half_open_breakers": cb_stats['half_open_breakers']
            },
            "message_queues": {
                "total_queues": queue_stats['total_queues'],
                "total_messages": queue_stats['total_messages'],
                "processing_rate": queue_stats['processing_rate']
            }
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def integration_metrics(request):
    """Get detailed integration metrics."""
    try:
        # Get performance metrics
        metrics = performance_monitor.export_metrics("prometheus")
        
        return Response({
            "metrics": metrics,
            "statistics": performance_monitor.get_statistics(),
            "health_checks": health_checker.get_statistics(),
            "audit_logs": audit_logger.get_statistics()
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def integration_webhooks(request):
    """Manage integration webhooks."""
    try:
        if request.method == 'GET':
            # List all webhooks
            webhooks = webhook_manager.list_webhooks()
            return Response({"webhooks": webhooks})
        
        elif request.method == 'POST':
            # Create new webhook
            webhook_config = request.data
            
            # Validate required fields
            required_fields = ['url', 'events']
            for field in required_fields:
                if field not in webhook_config:
                    return Response(
                        {"error": f"Missing required field: {field}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Register webhook
            webhook_id = webhook_manager.register_webhook(webhook_config)
            
            return Response({
                "webhook_id": webhook_id,
                "status": "created"
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def integration_webhook_detail(request, webhook_id):
    """Manage individual webhook."""
    try:
        if request.method == 'GET':
            # Get webhook details
            webhook = webhook_manager.get_webhook(webhook_id)
            if not webhook:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(webhook)
        
        elif request.method == 'PUT':
            # Update webhook
            webhook_config = request.data
            success = webhook_manager.update_webhook(webhook_id, webhook_config)
            
            if success:
                return Response({"status": "updated"})
            else:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif request.method == 'DELETE':
            # Delete webhook
            success = webhook_manager.delete_webhook(webhook_id)
            
            if success:
                return Response({"status": "deleted"})
            else:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def integration_health(request):
    """Get system health check."""
    try:
        health = health_checker.get_system_health()
        
        return Response({
            "status": health.status.value,
            "score": health.score,
            "timestamp": health.timestamp.isoformat(),
            "uptime_seconds": health.uptime_seconds,
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "execution_time": result.execution_time,
                    "timestamp": result.timestamp.isoformat()
                }
                for name, result in health.checks.items()
            },
            "issues": health.issues,
            "recommendations": health.recommendations,
            "summary": health.summary
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def integration_audit_logs(request):
    """Get audit logs."""
    try:
        # Get query parameters
        limit = int(request.GET.get('limit', 100))
        level = request.GET.get('level')
        category = request.GET.get('category')
        
        # Build criteria
        criteria = {}
        if level:
            criteria['level'] = level
        if category:
            criteria['category'] = category
        
        # Get logs
        logs = audit_logger.search_logs(criteria, limit)
        
        return Response({
            "logs": logs,
            "statistics": audit_logger.get_statistics()
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def integration_conflicts(request):
    """Get sync conflicts."""
    try:
        # Get query parameters
        bridge_name = request.GET.get('bridge_name')
        resolved = request.GET.get('resolved')
        
        # Convert resolved to boolean
        resolved_bool = None
        if resolved is not None:
            resolved_bool = resolved.lower() == 'true'
        
        # Get conflicts
        conflicts = sync_manager.get_conflicts(
            bridge_name=bridge_name,
            resolved=resolved_bool
        )
        
        return Response({
            "conflicts": [
                {
                    "sync_id": conflict.sync_id,
                    "bridge_name": conflict.bridge_name,
                    "conflict_count": len(conflict.conflicts),
                    "created_at": conflict.created_at.isoformat(),
                    "resolved_at": conflict.resolved_at.isoformat() if conflict.resolved_at else None,
                    "auto_resolved": conflict.auto_resolved,
                    "requires_manual_intervention": conflict.requires_manual_intervention,
                    "resolution_summary": conflict.resolution_summary
                }
                for conflict in conflicts
            ],
            "statistics": sync_manager.get_statistics()
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def resolve_conflict(request, sync_id):
    """Manually resolve a sync conflict."""
    try:
        data = request.data
        
        conflict_id = data.get('conflict_id')
        resolution_strategy = data.get('resolution_strategy')
        resolved_value = data.get('resolved_value')
        
        if not all([conflict_id, resolution_strategy]):
            return Response(
                {"error": "Missing conflict_id or resolution_strategy"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Convert string to enum
        from .sync_manager import ResolutionStrategy
        try:
            strategy = ResolutionStrategy(resolution_strategy)
        except ValueError:
            return Response(
                {"error": f"Invalid resolution strategy: {resolution_strategy}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Resolve conflict
        sync_manager.manually_resolve_conflict(
            sync_id=sync_id,
            conflict_id=conflict_id,
            resolution_strategy=strategy,
            resolved_value=resolved_value,
            resolved_by=str(request.user.id)
        )
        
        return Response({"status": "resolved"})
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def integration_permissions(request):
    """Get user permissions."""
    try:
        user_id = str(request.user.id)
        permissions = auth_bridge.get_user_permissions(user_id)
        
        return Response(permissions)
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def integration_registry(request):
    """Get integration registry."""
    try:
        registry_data = integration_registry.export_registry()
        
        return Response({
            "services": registry_data['services'],
            "instances": registry_data['instances'],
            "statistics": integration_registry.get_statistics()
        })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def trigger_health_check(request):
    """Trigger manual health check."""
    try:
        check_name = request.data.get('check_name')
        
        if check_name:
            # Run specific check
            result = health_checker.run_check(check_name)
            return Response({
                "check_name": check_name,
                "status": result.status.value,
                "message": result.message,
                "execution_time": result.execution_time,
                "timestamp": result.timestamp.isoformat()
            })
        else:
            # Run all checks
            health = health_checker.get_system_health()
            return Response({
                "status": health.status.value,
                "score": health.score,
                "checks": {
                    name: {
                        "status": result.status.value,
                        "message": result.message,
                        "execution_time": result.execution_time
                    }
                    for name, result in health.checks.items()
                }
            })
        
    except Exception as e:
        return Response(
            {"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# URL patterns
urlpatterns = [
    # Webhook endpoints
    path('webhooks/<uuid:webhook_id>/', WebhookReceiverView.as_view(), name='integration_webhook_receiver'),
    path('webhooks/', integration_webhooks, name='integration_webhooks'),
    path('webhooks/<uuid:webhook_id>/detail/', integration_webhook_detail, name='integration_webhook_detail'),
    
    # Event receiver
    path('events/', IntegrationEventView.as_view(), name='integration_events'),
    
    # Status and monitoring
    path('status/', integration_status, name='integration_status'),
    path('health/', integration_health, name='integration_health'),
    path('metrics/', integration_metrics, name='integration_metrics'),
    
    # Audit and logging
    path('audit-logs/', integration_audit_logs, name='integration_audit_logs'),
    
    # Conflict management
    path('conflicts/', integration_conflicts, name='integration_conflicts'),
    path('conflicts/<str:sync_id>/resolve/', resolve_conflict, name='resolve_conflict'),
    
    # Permissions and registry
    path('permissions/', integration_permissions, name='integration_permissions'),
    path('registry/', integration_registry, name='integration_registry'),
    
    # Health checks
    path('health-check/trigger/', trigger_health_check, name='trigger_health_check'),
]

# Admin URLs (for Django admin integration)
admin_urlpatterns = [
    path('admin/', include('django.contrib.auth.urls')),
    path('admin/health/', health_checker.get_system_health, name='admin_health'),
    path('admin/performance/', performance_monitor.get_statistics, name='admin_performance'),
    path('admin/audit/', audit_logger.get_statistics, name='admin_audit'),
]
