"""
Integration System ViewSets - Django REST Framework

ViewSet classes for the integration system API endpoints providing
CRUD operations, bulk actions, and advanced filtering capabilities.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db import transaction
import logging

from .integ_constants import IntegrationEvent, IntegrationStatus, IntegrationPriority
from .webhooks_integration import webhook_manager
from .health_check import health_checker
from .performance_monitor import performance_monitor
from .integ_audit_logs import audit_logger, AuditLogLevel, AuditCategory
from .sync_manager import sync_manager, ConflictType, ResolutionStrategy
from .auth_bridge import auth_bridge
from .integ_registry import integration_registry
from .event_bus import event_bus
from .circuit_breaker import circuit_breaker_manager
from .data_bridge import data_bridge_manager
from .message_queue import message_queue_manager
from .serializers import (
    WebhookSerializer, WebhookDetailSerializer, SystemHealthSerializer,
    PerformanceStatsSerializer, AuditLogSerializer, SyncConflictSerializer,
    UserPermissionSerializer, IntegrationServiceSerializer,
    CircuitBreakerSerializer, MessageQueueSerializer,
    IntegrationConfigSerializer, ConflictResolutionSerializer
)

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for integration system."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class WebhookViewSet(viewsets.ModelViewSet):
    """ViewSet for webhook management."""
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['active', 'events']
    
    def get_queryset(self):
        """Get webhook list."""
        webhooks = webhook_manager.list_webhooks()
        return webhooks
    
    def get_serializer_class(self):
        """Get appropriate serializer."""
        if self.action == 'list':
            return WebhookDetailSerializer
        elif self.action == 'create':
            return WebhookSerializer
        else:
            return WebhookDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Create new webhook."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            webhook_id = webhook_manager.register_webhook(serializer.validated_data)
            
            # Log webhook creation
            audit_logger.log_configuration_change(
                action="create",
                resource_type="webhook",
                resource_id=str(webhook_id),
                user_id=str(request.user.id),
                new_values=serializer.validated_data
            )
            
            return Response(
                {"webhook_id": webhook_id, **serializer.validated_data},
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"Failed to create webhook: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def update(self, request, *args, **kwargs):
        """Update webhook."""
        webhook_id = kwargs.get('pk')
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        try:
            success = webhook_manager.update_webhook(webhook_id, serializer.validated_data)
            
            if success:
                # Log webhook update
                audit_logger.log_configuration_change(
                    action="update",
                    resource_type="webhook",
                    resource_id=webhook_id,
                    user_id=str(request.user.id),
                    new_values=serializer.validated_data
                )
                
                return Response({"status": "updated"})
            else:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Failed to update webhook: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        """Delete webhook."""
        webhook_id = kwargs.get('pk')
        
        try:
            success = webhook_manager.delete_webhook(webhook_id)
            
            if success:
                # Log webhook deletion
                audit_logger.log_configuration_change(
                    action="delete",
                    resource_type="webhook",
                    resource_id=webhook_id,
                    user_id=str(request.user.id)
                )
                
                return Response({"status": "deleted"})
            else:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(f"Failed to delete webhook: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test webhook delivery."""
        try:
            webhook = webhook_manager.get_webhook(pk)
            if not webhook:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Send test event
            test_data = {
                "event": "webhook_test",
                "timestamp": timezone.now().isoformat(),
                "user_id": str(request.user.id)
            }
            
            result = webhook_manager.deliver_webhook(pk, test_data)
            
            return Response({
                "test_result": result,
                "test_data": test_data
            })
            
        except Exception as e:
            logger.error(f"Failed to test webhook: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get webhook statistics."""
        try:
            webhook = webhook_manager.get_webhook(pk)
            if not webhook:
                return Response(
                    {"error": "Webhook not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            stats = webhook_manager.get_webhook_statistics(pk)
            
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Failed to get webhook statistics: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class HealthCheckViewSet(viewsets.ViewSet):
    """ViewSet for health check management."""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get system health status."""
        try:
            health = health_checker.get_system_health()
            serializer = SystemHealthSerializer(health)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Failed to get health status: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def trigger_check(self, request):
        """Trigger health check."""
        check_name = request.data.get('check_name')
        
        try:
            if check_name:
                # Run specific check
                result = health_checker.run_check(check_name)
                
                return Response({
                    "check_name": check_name,
                    "status": result.status.value,
                    "message": result.message,
                    "execution_time": result.execution_time,
                    "timestamp": result.timestamp.isoformat(),
                    "details": result.details
                })
            else:
                # Run all checks
                health = health_checker.get_system_health()
                
                return Response({
                    "overall_status": health.status.value,
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
            logger.error(f"Failed to trigger health check: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get health check statistics."""
        try:
            stats = health_checker.get_statistics()
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Failed to get health statistics: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PerformanceMonitorViewSet(viewsets.ViewSet):
    """ViewSet for performance monitoring."""
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """Get performance metrics."""
        try:
            stats = performance_monitor.get_statistics()
            serializer = PerformanceStatsSerializer(stats)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Failed to get performance stats: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Get detailed metrics."""
        try:
            metric_name = request.query_params.get('metric_name')
            since = request.query_params.get('since')
            limit = int(request.query_params.get('limit', 100))
            
            # Parse since parameter
            since_date = None
            if since:
                try:
                    since_date = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
                except ValueError:
                    return Response(
                        {"error": "Invalid date format. Use ISO 8601 format."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            if metric_name:
                values = performance_monitor.get_metric_values(metric_name, since_date, limit)
                return Response({
                    "metric_name": metric_name,
                    "values": [
                        {
                            "value": v.value,
                            "timestamp": v.timestamp.isoformat(),
                            "labels": v.labels
                        }
                        for v in values
                    ]
                })
            else:
                # Get all metrics
                metrics = {}
                for name in performance_monitor.metrics.keys():
                    values = performance_monitor.get_metric_values(name, since_date, limit)
                    if values:
                        metrics[name] = [
                            {
                                "value": v.value,
                                "timestamp": v.timestamp.isoformat(),
                                "labels": v.labels
                            }
                            for v in values
                        ]
                
                return Response({"metrics": metrics})
                
        except Exception as e:
            logger.error(f"Failed to get metrics: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export metrics in specified format."""
        try:
            export_format = request.query_params.get('format', 'prometheus')
            
            if export_format not in ['prometheus', 'json']:
                return Response(
                    {"error": "Invalid format. Use 'prometheus' or 'json'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            metrics_data = performance_monitor.export_metrics(export_format)
            
            return Response({
                "format": export_format,
                "data": metrics_data,
                "timestamp": timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to export metrics: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def record_metric(self, request):
        """Record a custom metric."""
        try:
            metric_name = request.data.get('metric_name')
            value = request.data.get('value')
            labels = request.data.get('labels', {})
            
            if not metric_name or value is None:
                return Response(
                    {"error": "metric_name and value are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            performance_monitor.record_metric(metric_name, float(value), labels)
            
            return Response({"status": "recorded"})
            
        except Exception as e:
            logger.error(f"Failed to record metric: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AuditLogViewSet(viewsets.ViewSet):
    """ViewSet for audit log management."""
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def list(self, request):
        """Get audit logs."""
        try:
            # Get query parameters
            limit = int(request.query_params.get('limit', 100))
            level = request.query_params.get('level')
            category = request.query_params.get('category')
            user_id = request.query_params.get('user_id')
            
            # Build criteria
            criteria = {}
            if level:
                criteria['level'] = level
            if category:
                criteria['category'] = category
            if user_id:
                criteria['user_id'] = user_id
            
            # Get logs
            logs = audit_logger.search_logs(criteria, limit)
            
            # Serialize logs
            serializer = AuditLogSerializer(logs, many=True)
            
            return Response({
                "logs": serializer.data,
                "statistics": audit_logger.get_statistics()
            })
            
        except Exception as e:
            logger.error(f"Failed to get audit logs: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get audit statistics."""
        try:
            stats = audit_logger.get_statistics()
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Failed to get audit statistics: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def export(self, request):
        """Export audit logs."""
        try:
            export_format = request.data.get('format', 'json')
            criteria = request.data.get('criteria', {})
            limit = int(request.data.get('limit', 10000))
            
            if export_format not in ['json', 'csv']:
                return Response(
                    {"error": "Invalid format. Use 'json' or 'csv'."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            logs_data = audit_logger.export_logs(export_format, criteria, limit)
            
            return Response({
                "format": export_format,
                "data": logs_data,
                "timestamp": timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to export audit logs: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SyncConflictViewSet(viewsets.ViewSet):
    """ViewSet for sync conflict management."""
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    
    def list(self, request):
        """Get sync conflicts."""
        try:
            # Get query parameters
            bridge_name = request.query_params.get('bridge_name')
            resolved = request.query_params.get('resolved')
            
            # Convert resolved to boolean
            resolved_bool = None
            if resolved is not None:
                resolved_bool = resolved.lower() == 'true'
            
            # Get conflicts
            conflicts = sync_manager.get_conflicts(
                bridge_name=bridge_name,
                resolved=resolved_bool
            )
            
            # Serialize conflicts
            serializer = SyncConflictSerializer(conflicts, many=True)
            
            return Response({
                "conflicts": serializer.data,
                "statistics": sync_manager.get_statistics()
            })
            
        except Exception as e:
            logger.error(f"Failed to get sync conflicts: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """Resolve a sync conflict."""
        try:
            data = request.data
            
            conflict_id = data.get('conflict_id')
            resolution_strategy = data.get('resolution_strategy')
            resolved_value = data.get('resolved_value')
            
            if not all([conflict_id, resolution_strategy]):
                return Response(
                    {"error": "conflict_id and resolution_strategy are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Convert string to enum
            try:
                strategy = ResolutionStrategy(resolution_strategy)
            except ValueError:
                return Response(
                    {"error": f"Invalid resolution strategy: {resolution_strategy}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Resolve conflict
            sync_manager.manually_resolve_conflict(
                sync_id=pk,
                conflict_id=conflict_id,
                resolution_strategy=strategy,
                resolved_value=resolved_value,
                resolved_by=str(request.user.id)
            )
            
            # Log conflict resolution
            audit_logger.log_configuration_change(
                action="resolve",
                resource_type="sync_conflict",
                resource_id=pk,
                user_id=str(request.user.id),
                new_values={
                    "conflict_id": conflict_id,
                    "resolution_strategy": resolution_strategy,
                    "resolved_value": resolved_value
                }
            )
            
            return Response({"status": "resolved"})
            
        except Exception as e:
            logger.error(f"Failed to resolve conflict: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get sync statistics."""
        try:
            stats = sync_manager.get_statistics()
            return Response(stats)
            
        except Exception as e:
            logger.error(f"Failed to get sync statistics: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PermissionViewSet(viewsets.ViewSet):
    """ViewSet for permission management."""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def my_permissions(self, request):
        """Get current user's permissions."""
        try:
            user_id = str(request.user.id)
            permissions = auth_bridge.get_user_permissions(user_id)
            
            serializer = UserPermissionSerializer(permissions)
            
            return Response(serializer.data)
            
        except Exception as e:
            logger.error(f"Failed to get user permissions: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def all_permissions(self, request):
        """Get all available permissions (admin only)."""
        if not request.user.is_staff:
            return Response(
                {"error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            permissions = auth_bridge.list_permissions()
            return Response({"permissions": permissions})
            
        except Exception as e:
            logger.error(f"Failed to get all permissions: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def all_roles(self, request):
        """Get all available roles (admin only)."""
        if not request.user.is_staff:
            return Response(
                {"error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            roles = auth_bridge.list_roles()
            return Response({"roles": roles})
            
        except Exception as e:
            logger.error(f"Failed to get all roles: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IntegrationRegistryViewSet(viewsets.ViewSet):
    """ViewSet for integration registry management."""
    permission_classes = [IsAdminUser]
    
    def list(self, request):
        """Get integration registry."""
        try:
            registry_data = integration_registry.export_registry()
            
            return Response({
                "services": registry_data['services'],
                "instances": registry_data['instances'],
                "statistics": integration_registry.get_statistics()
            })
            
        except Exception as e:
            logger.error(f"Failed to get integration registry: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def register_service(self, request):
        """Register a new integration service."""
        try:
            serializer = IntegrationConfigSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Register service
            service_id = integration_registry.register_service(
                serializer.validated_data['service_name'],
                serializer.validated_data
            )
            
            # Log service registration
            audit_logger.log_configuration_change(
                action="create",
                resource_type="integration_service",
                resource_id=service_id,
                user_id=str(request.user.id),
                new_values=serializer.validated_data
            )
            
            return Response({
                "service_id": service_id,
                "status": "registered"
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Failed to register service: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def health_check_all(self, request):
        """Run health check on all registered services."""
        try:
            results = integration_registry.health_check_all()
            
            return Response({
                "health_check_results": results,
                "timestamp": timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Failed to run health checks: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CircuitBreakerViewSet(viewsets.ViewSet):
    """ViewSet for circuit breaker management."""
    permission_classes = [IsAdminUser]
    
    def list(self, request):
        """Get all circuit breakers."""
        try:
            breakers = circuit_breaker_manager.get_all_breakers()
            
            serializer = CircuitBreakerSerializer(breakers, many=True)
            
            return Response({
                "circuit_breakers": serializer.data,
                "statistics": circuit_breaker_manager.get_statistics()
            })
            
        except Exception as e:
            logger.error(f"Failed to get circuit breakers: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def reset(self, request, pk=None):
        """Reset a circuit breaker."""
        try:
            circuit_breaker_manager.reset_breaker(pk)
            
            # Log circuit breaker reset
            audit_logger.log_configuration_change(
                action="reset",
                resource_type="circuit_breaker",
                resource_id=pk,
                user_id=str(request.user.id)
            )
            
            return Response({"status": "reset"})
            
        except Exception as e:
            logger.error(f"Failed to reset circuit breaker: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MessageQueueViewSet(viewsets.ViewSet):
    """ViewSet for message queue management."""
    permission_classes = [IsAdminUser]
    
    def list(self, request):
        """Get all message queues."""
        try:
            queues = message_queue_manager.get_all_queues()
            
            serializer = MessageQueueSerializer(queues, many=True)
            
            return Response({
                "queues": serializer.data,
                "statistics": message_queue_manager.get_statistics()
            })
            
        except Exception as e:
            logger.error(f"Failed to get message queues: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def purge(self, request, pk=None):
        """Purge a message queue."""
        try:
            message_queue_manager.purge_queue(pk)
            
            # Log queue purge
            audit_logger.log_configuration_change(
                action="purge",
                resource_type="message_queue",
                resource_id=pk,
                user_id=str(request.user.id)
            )
            
            return Response({"status": "purged"})
            
        except Exception as e:
            logger.error(f"Failed to purge queue: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
