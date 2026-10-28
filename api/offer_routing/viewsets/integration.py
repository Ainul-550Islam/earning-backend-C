"""
Integration System Viewsets for Offer Routing System

Exposes all integration_system logic via REST API:
- IntegrationHandlerViewSet  (register/execute/list/update/remove integrations)
- IntegrationRegistryViewSet (registry CRUD, dependency checks, export)
- AuthBridgeViewSet          (authenticate, authorize, token ops)
- DataBridgeViewSet          (sync, conflict resolution, status)
- EventBusViewSet            (publish, subscribe, history, stats)
- HealthCheckViewSet         (health runs, component status, thresholds)
- PerformanceMonitorViewSet  (start/stop, record, metrics, history)
- AuditLogViewSet            (audit log read, query)
- WebhookViewSet             (webhook register, execute, status)
"""

from ..throttling import BulkOperationThrottle, RoutingEngineThrottle, AnalyticsThrottle, BulkOperationThrottle, EvaluatorThrottle
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from ..permissions import IsAuthenticatedOrReadOnly, CanManageOffers
from ..integration_system import (
    integration_handler, integration_registry,
    auth_bridge, data_bridge, event_bus,
    health_check_service, performance_monitor,
    audit_logger,
)
from ..integration_system.integ_exceptions import IntegrationError


class IntegrationHandlerViewSet(viewsets.ViewSet):
    """
    ViewSet for managing integrations via IntegrationHandler.

    register, execute, list, update config, enable/disable, remove,
    sync all, metrics, health check.
    """
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def register_integration(self, request):
        """Register a new integration."""
        try:
            name = request.data.get('name')
            config = request.data.get('config', {})
            if not name:
                return Response({'success': False, 'error': 'name is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.register_integration(name, config)
            return Response({'success': True, 'result': result})
        except IntegrationError as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def execute_integration(self, request):
        """Execute an action on a registered integration."""
        try:
            integration_id = request.data.get('integration_id')
            action_name = request.data.get('action')
            data = request.data.get('data', {})
            if not integration_id or not action_name:
                return Response({'success': False,
                                 'error': 'integration_id and action are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.execute_integration(integration_id, action_name, data)
            return Response({'success': True, 'result': result})
        except IntegrationError as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def list_integrations(self, request):
        """List all registered integrations, optionally filtered by type."""
        try:
            integration_type = request.query_params.get('type')
            result = integration_handler.list_integrations(integration_type)
            return Response({'success': True, 'integrations': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def integration_status(self, request):
        """Get status of a specific integration."""
        try:
            integration_id = request.query_params.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.get_integration_status(integration_id)
            return Response({'success': True, 'status': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_config(self, request):
        """Update configuration of an integration."""
        try:
            integration_id = request.data.get('integration_id')
            config_updates = request.data.get('config', {})
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.update_integration_config(integration_id, config_updates)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def enable_integration(self, request):
        """Enable a disabled integration."""
        try:
            integration_id = request.data.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.enable_integration(integration_id)
            return Response({'success': result, 'integration_id': integration_id})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def disable_integration(self, request):
        """Disable an active integration."""
        try:
            integration_id = request.data.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.disable_integration(integration_id)
            return Response({'success': result, 'integration_id': integration_id})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def remove_integration(self, request):
        """Remove an integration entirely."""
        try:
            integration_id = request.data.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_handler.remove_integration(integration_id)
            return Response({'success': result, 'integration_id': integration_id})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def sync_all(self, request):
        """Sync all integrations."""
        try:
            result = integration_handler.sync_all_integrations()
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def integration_metrics(self, request):
        """Get metrics for one or all integrations."""
        try:
            integration_id = request.query_params.get('integration_id')
            result = integration_handler.get_integration_metrics(integration_id)
            return Response({'success': True, 'metrics': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Health check of the integration handler."""
        try:
            result = integration_handler.health_check()
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationRegistryViewSet(viewsets.ViewSet):
    """
    ViewSet for IntegrationRegistry — register, query, dependency checks, export.
    """
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register an integration in the registry."""
        try:
            name = request.data.get('name')
            config = request.data.get('config', {})
            if not name:
                return Response({'success': False, 'error': 'name is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            integration_id = integration_registry.register(name, config)
            return Response({'success': True, 'integration_id': integration_id},
                            status=status.HTTP_201_CREATED)
        except IntegrationError as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['delete'])
    def unregister(self, request):
        """Unregister an integration from the registry."""
        try:
            integration_id = request.data.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_registry.unregister(integration_id)
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_integration(self, request):
        """Get a specific integration from the registry."""
        try:
            integration_id = request.query_params.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_registry.get_integration(integration_id)
            if result is None:
                return Response({'success': False, 'error': 'Integration not found'},
                                status=status.HTTP_404_NOT_FOUND)
            return Response({'success': True, 'integration': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def active_integrations(self, request):
        """List all active integrations."""
        try:
            result = integration_registry.get_active_integrations()
            return Response({'success': True, 'integrations': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def integrations_by_type(self, request):
        """Get integrations filtered by type."""
        try:
            integration_type = request.query_params.get('type')
            if not integration_type:
                return Response({'success': False, 'error': 'type is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_registry.get_integrations_by_type(integration_type)
            return Response({'success': True, 'integrations': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_status(self, request):
        """Update integration status in the registry."""
        try:
            integration_id = request.data.get('integration_id')
            new_status = request.data.get('status')
            if not integration_id or not new_status:
                return Response({'success': False,
                                 'error': 'integration_id and status are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_registry.update_integration_status(integration_id, new_status)
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def check_dependencies(self, request):
        """Check dependency resolution for an integration."""
        try:
            integration_id = request.query_params.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = integration_registry.check_dependencies(integration_id)
            return Response({'success': True, 'dependencies': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def registry_stats(self, request):
        """Get registry statistics."""
        try:
            result = integration_registry.get_registry_stats()
            return Response({'success': True, 'stats': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def validate_registry(self, request):
        """Validate the entire registry for consistency."""
        try:
            result = integration_registry.validate_registry()
            return Response({'success': True, 'validation': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def export_registry(self, request):
        """Export the full registry."""
        try:
            result = integration_registry.export_registry()
            return Response({'success': True, 'registry': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthBridgeViewSet(viewsets.ViewSet):
    """
    ViewSet for AuthBridge — authenticate, authorize, token lifecycle.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def authenticate(self, request):
        """Authenticate an integration with provided auth data."""
        try:
            integration_id = request.data.get('integration_id')
            auth_data = request.data.get('auth_data', {})
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = auth_bridge.authenticate_integration(integration_id, auth_data)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def authorize(self, request):
        """Check authorization for an integration action."""
        try:
            integration_id = request.data.get('integration_id')
            action_name = request.data.get('action')
            if not integration_id or not action_name:
                return Response({'success': False,
                                 'error': 'integration_id and action are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = auth_bridge.authorize_integration_action(integration_id, action_name)
            return Response({'success': True, 'authorized': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate_token(self, request):
        """Validate an integration token."""
        try:
            token = request.data.get('token')
            integration_id = request.data.get('integration_id')
            if not token or not integration_id:
                return Response({'success': False,
                                 'error': 'token and integration_id are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = auth_bridge.validate_token(token, integration_id)
            return Response({'success': True, 'validation': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def refresh_token(self, request):
        """Refresh an integration token."""
        try:
            integration_id = request.data.get('integration_id')
            refresh_token = request.data.get('refresh_token')
            if not integration_id or not refresh_token:
                return Response({'success': False,
                                 'error': 'integration_id and refresh_token are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = auth_bridge.refresh_token(integration_id, refresh_token)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def revoke_token(self, request):
        """Revoke an integration token."""
        try:
            integration_id = request.data.get('integration_id')
            token = request.data.get('token')
            if not integration_id or not token:
                return Response({'success': False,
                                 'error': 'integration_id and token are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = auth_bridge.revoke_token(integration_id, token)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def auth_stats(self, request):
        """Get authentication statistics."""
        try:
            result = auth_bridge.get_auth_stats()
            return Response({'success': True, 'stats': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Health check of the auth bridge."""
        try:
            result = auth_bridge.health_check()
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeViewSet(viewsets.ViewSet):
    """
    ViewSet for DataBridge — sync, conflict resolution, bridge status.
    """
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Sync integrations to routing."""
        try:
            integration_id = request.data.get('integration_id')
            result = data_bridge.sync_integrations_to_routing(integration_id)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def resolve_conflicts(self, request):
        """Resolve data conflicts for an integration."""
        try:
            integration_id = request.data.get('integration_id')
            if not integration_id:
                return Response({'success': False, 'error': 'integration_id is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = data_bridge.resolve_conflicts(integration_id)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def sync_status(self, request):
        """Get current sync status."""
        try:
            integration_id = request.query_params.get('integration_id')
            result = data_bridge.get_sync_status(integration_id)
            return Response({'success': True, 'status': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def bridge_stats(self, request):
        """Get data bridge statistics."""
        try:
            result = data_bridge.get_bridge_stats()
            return Response({'success': True, 'stats': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Health check of the data bridge."""
        try:
            result = data_bridge.health_check()
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EventBusViewSet(viewsets.ViewSet):
    """
    ViewSet for EventBus — publish events, query history, bus stats.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def publish(self, request):
        """Publish an event to the event bus."""
        try:
            event_type = request.data.get('event_type')
            data = request.data.get('data', {})
            if not event_type:
                return Response({'success': False, 'error': 'event_type is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = event_bus.publish(event_type, data)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def event_history(self, request):
        """Get event history, optionally filtered by type."""
        try:
            event_type = request.query_params.get('event_type')
            limit = int(request.query_params.get('limit', 100))
            result = event_bus.get_event_history(event_type, limit=limit)
            return Response({'success': True, 'history': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def subscribers(self, request):
        """Get current subscribers, optionally filtered by event type."""
        try:
            event_type = request.query_params.get('event_type')
            result = event_bus.get_subscribers(event_type)
            # Handlers are callables — return their names only
            summary = {
                k: [getattr(h, '__name__', str(h)) for h in v]
                for k, v in result.items()
            }
            return Response({'success': True, 'subscribers': summary})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def clear_history(self, request):
        """Clear event history."""
        try:
            event_type = request.data.get('event_type')
            result = event_bus.clear_history(event_type)
            return Response({'success': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def bus_stats(self, request):
        """Get event bus statistics."""
        try:
            result = event_bus.get_bus_stats()
            return Response({'success': True, 'stats': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Health check of the event bus."""
        try:
            result = event_bus.health_check()
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegrationHealthViewSet(viewsets.ViewSet):
    """
    ViewSet for HealthCheck — run checks, get status, set thresholds.
    """
    permission_classes = [IsAuthenticatedOrReadOnly]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def run_health_check(self, request):
        """Run a full health check."""
        try:
            result = health_check_service.run_health_check()
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_status(self, request):
        """Get current health status."""
        try:
            result = health_check_service.get_health_status()
            return Response({'success': True, 'status': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def component_health(self, request):
        """Get health of a specific component."""
        try:
            component = request.query_params.get('component')
            if not component:
                return Response({'success': False, 'error': 'component is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = health_check_service.get_component_health(component)
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def set_alert_thresholds(self, request):
        """Set alert thresholds for health checks."""
        try:
            thresholds = request.data.get('thresholds', {})
            if not thresholds:
                return Response({'success': False, 'error': 'thresholds is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = health_check_service.set_alert_thresholds(thresholds)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def integration_health_check(self, request):
        """Delegate to health_check_service.health_check()."""
        try:
            result = health_check_service.health_check()
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PerformanceMonitorViewSet(viewsets.ViewSet):
    """
    ViewSet for PerformanceMonitor — start/stop, record, metrics, history.
    """
    permission_classes = [IsAuthenticatedOrReadOnly, CanManageOffers]
    throttle_classes = [BulkOperationThrottle]

    @action(detail=False, methods=['post'])
    def start_monitoring(self, request):
        """Start performance monitoring."""
        try:
            result = performance_monitor.start_monitoring()
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def stop_monitoring(self, request):
        """Stop performance monitoring."""
        try:
            result = performance_monitor.stop_monitoring()
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def record_execution(self, request):
        """Record an integration execution metric."""
        try:
            integration_id = request.data.get('integration_id')
            execution_time_ms = request.data.get('execution_time_ms')
            success = request.data.get('success', True)
            if not integration_id or execution_time_ms is None:
                return Response({'success': False,
                                 'error': 'integration_id and execution_time_ms are required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = performance_monitor.record_integration_execution(
                integration_id, float(execution_time_ms), success
            )
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def performance_metrics(self, request):
        """Get current performance metrics."""
        try:
            result = performance_monitor.get_performance_metrics()
            return Response({'success': True, 'metrics': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def performance_history(self, request):
        """Get historical performance data."""
        try:
            hours = int(request.query_params.get('hours', 24))
            result = performance_monitor.get_performance_history(hours)
            return Response({'success': True, 'history': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def set_alert_thresholds(self, request):
        """Set performance alert thresholds."""
        try:
            thresholds = request.data.get('thresholds', {})
            if not thresholds:
                return Response({'success': False, 'error': 'thresholds is required'},
                                status=status.HTTP_400_BAD_REQUEST)
            result = performance_monitor.set_alert_thresholds(thresholds)
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def reset_metrics(self, request):
        """Reset all collected metrics."""
        try:
            result = performance_monitor.reset_metrics()
            return Response({'success': True, 'result': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_check(self, request):
        """Health check for the performance monitor."""
        try:
            result = performance_monitor.health_check()
            return Response({'success': True, 'health': result})
        except Exception as e:
            return Response({'success': False, 'error': str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
