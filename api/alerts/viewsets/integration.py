"""
viewsets/integration.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NEWLY CREATED — was completely missing.

The entire integration/ subfolder (22 files, 400+ methods) had ZERO API exposure.
All classes were initialized in apps.py but no endpoint ever called them.

This file creates DRF ViewSets for every integration subsystem:
  1.  CircuitBreakerViewSet        → integration/circuit_breaker.py
  2.  IntegrationHealthViewSet     → integration/health_check.py
  3.  IntegrationRegistryViewSet   → integration/integ_registry.py
  4.  AuditLogViewSet              → integration/integ_audit_logs.py
  5.  PerformanceMonitorViewSet    → integration/performance_monitor.py
  6.  MessageQueueViewSet          → integration/message_queue.py
  7.  WebhookIntegrationViewSet    → integration/webhooks_integration.py
  8.  SyncManagerViewSet           → integration/sync_manager.py
  9.  VersioningViewSet            → integration/versioning.py
  10. TransformerViewSet           → integration/transformer.py
  11. IntegrationBridgeViewSet     → integration/bridge.py
  12. EventBusViewSet              → integration/event_bus.py
  13. DataValidatorViewSet         → integration/data_validator.py
  14. IntegrationHandlerViewSet    → integration/integ_handler.py
  15. AuthBridgeViewSet            → integration/auth_bridge.py
  16. FallbackLogicViewSet         → integration/fallback_logic.py
  17. IntegrationAdapterViewSet    → integration/integ_adapter.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .mixins import PASSTHROUGH_EXCEPTIONS  # re-raise 404/403/400 instead of 500

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# 1. CircuitBreakerViewSet
# ─────────────────────────────────────────────────────────────────
class CircuitBreakerViewSet(viewsets.ViewSet):
    """
    API access to integration/circuit_breaker.py → CircuitBreakerManager
    Endpoints: stats, reset, open_breakers, check, register, by_state
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_manager(self):
        from api.alerts.integration import get_circuit_breaker_manager
        mgr = get_circuit_breaker_manager()
        if mgr is None:
            from api.alerts.integration.circuit_breaker import CircuitBreakerManager
            mgr = CircuitBreakerManager()
        return mgr

    def list(self, request):
        """List all circuit breakers and their states"""
        try:
            mgr = self._get_manager()
            stats = {}
            if hasattr(mgr, 'circuit_breakers'):
                for name, cb in mgr.circuit_breakers.items():
                    stats[name] = {
                        'state': cb.state.value if hasattr(cb.state, 'value') else str(cb.state),
                        'failure_count': getattr(cb, 'failure_count', 0),
                        'total_calls': getattr(cb, 'total_calls', 0),
                        'successful_calls': getattr(cb, 'successful_calls', 0),
                        'failed_calls': getattr(cb, 'failed_calls', 0),
                        'circuit_opened_count': getattr(cb, 'circuit_opened_count', 0),
                    }
            return Response({'circuit_breakers': stats, 'count': len(stats)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Overall circuit breaker statistics"""
        try:
            from api.alerts.integration.circuit_breaker import get_circuit_breaker_statistics
            data = get_circuit_breaker_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def open_breakers(self, request):
        """List all currently OPEN circuit breakers"""
        try:
            from api.alerts.integration.circuit_breaker import get_open_circuit_breakers
            data = get_open_circuit_breakers()
            return Response({'open_circuit_breakers': data, 'count': len(data) if isinstance(data, list) else 0})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.open_breakers error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def reset(self, request):
        """Reset a circuit breaker by name"""
        try:
            name = request.data.get('name')
            if not name:
                return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)
            from api.alerts.integration.circuit_breaker import reset_circuit_breaker
            reset_circuit_breaker(name)
            return Response({'success': True, 'reset': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.reset error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def reset_all(self, request):
        """Reset ALL circuit breakers"""
        try:
            mgr = self._get_manager()
            reset_count = 0
            if hasattr(mgr, 'circuit_breakers'):
                for cb in mgr.circuit_breakers.values():
                    if hasattr(cb, 'reset'):
                        cb.reset()
                        reset_count += 1
            return Response({'success': True, 'reset_count': reset_count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.reset_all error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def check(self, request):
        """Check if a named circuit breaker would allow a call"""
        try:
            name = request.query_params.get('name')
            if not name:
                return Response({'error': 'name query param required'}, status=status.HTTP_400_BAD_REQUEST)
            mgr = self._get_manager()
            cb = mgr.circuit_breakers.get(name) if hasattr(mgr, 'circuit_breakers') else None
            if cb is None:
                return Response({'error': f'Circuit breaker {name!r} not found'}, status=status.HTTP_404_NOT_FOUND)
            from api.alerts.integration.circuit_breaker import CircuitBreakerState
            allowed = cb.state != CircuitBreakerState.OPEN
            return Response({'name': name, 'state': cb.state.value, 'would_allow_call': allowed})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.check error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register (or get-or-create) a named circuit breaker with custom thresholds"""
        try:
            name = request.data.get('name')
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            failure_threshold = request.data.get('failure_threshold')
            timeout = request.data.get('timeout')
            kwargs = {}
            if failure_threshold is not None:
                kwargs['failure_threshold'] = int(failure_threshold)
            if timeout is not None:
                kwargs['timeout'] = int(timeout)
            mgr = self._get_manager()
            cb = mgr.get_or_create(name, **kwargs)
            return Response({'success': True, 'name': name, 'state': cb.state.value})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.register error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def by_state(self, request, state=None, **kwargs):
        """List circuit breaker names currently in a given state (open/closed/half_open)"""
        try:
            from api.alerts.integration.circuit_breaker import CircuitBreakerState
            state_val = state or self.kwargs.get('state') or request.query_params.get('state', 'open')
            try:
                state_enum = CircuitBreakerState(state_val)
            except ValueError:
                valid = [s.value for s in CircuitBreakerState]
                return Response({'error': f'Invalid state {state_val!r}, must be one of {valid}'}, status=status.HTTP_400_BAD_REQUEST)
            mgr = self._get_manager()
            names = mgr.get_breakers_by_state(state_enum)
            return Response({'state': state_val, 'count': len(names), 'breakers': names})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"CircuitBreakerViewSet.by_state error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 2. IntegrationHealthViewSet
# ─────────────────────────────────────────────────────────────────
class IntegrationHealthViewSet(viewsets.ViewSet):
    """
    API access to integration/health_check.py → IntegrationHealthChecker
    Endpoints: overview, components, stats, check
    """
    permission_classes = [IsAuthenticated]

    def _get_checker(self):
        from api.alerts.integration.health_check import IntegrationHealthChecker
        return IntegrationHealthChecker()

    def list(self, request):
        """Full integration health overview"""
        try:
            checker = self._get_checker()
            data = checker.check_integration_health()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHealthViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def components(self, request):
        """Health status of each integration component"""
        try:
            from api.alerts.integration.health_check import integration_component_health
            data = integration_component_health()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHealthViewSet.components error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Health check statistics"""
        try:
            checker = self._get_checker()
            data = checker.get_health_statistics() if hasattr(checker, 'get_health_statistics') else checker.health_stats
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHealthViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def check(self, request):
        """Run a fresh health check now"""
        try:
            checker = self._get_checker()
            result = checker.check_integration_health()
            return Response({'triggered': True, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHealthViewSet.check error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 3. IntegrationRegistryViewSet
# ─────────────────────────────────────────────────────────────────
class IntegrationRegistryViewSet(viewsets.ViewSet):
    """
    API access to integration/integ_registry.py → IntegrationRegistry, IntegrationConfigurationManager
    Endpoints: list, register, unregister, get_integration, registry_status,
               enable, disable, update_config, all_status, send_data, broadcast,
               health_checks, metrics, cleanup, config_get, config_save,
               config_delete, config_validate
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_registry(self):
        from api.alerts.integration import get_integration_registry
        registry = get_integration_registry()
        if registry is None:
            from api.alerts.integration.integ_registry import IntegrationRegistry
            registry = IntegrationRegistry()
        return registry

    def list(self, request):
        """List all registered integrations"""
        try:
            registry = self._get_registry()
            integrations = {}
            if hasattr(registry, 'integrations'):
                for name, info in registry.integrations.items():
                    integrations[name] = {
                        'enabled': info.get('enabled', False),
                        'connected': info.get('connected', False),
                        'registered_at': str(info.get('registered_at', '')),
                        'class': info['class'].__name__ if 'class' in info else 'unknown',
                    }
            return Response({'integrations': integrations, 'count': len(integrations)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new integration by dotted class path"""
        try:
            name = request.data.get('name')
            class_path = request.data.get('class_path')
            config = request.data.get('config', {})
            if not name or not class_path:
                return Response({'error': 'name and class_path required'}, status=status.HTTP_400_BAD_REQUEST)
            import importlib
            module_path, cls_name = class_path.rsplit('.', 1)
            mod = importlib.import_module(module_path)
            cls = getattr(mod, cls_name)
            registry = self._get_registry()
            registry.register_integration(name, cls, config)
            return Response({'success': True, 'registered': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.register error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def unregister(self, request):
        """Unregister an integration by name"""
        try:
            name = request.data.get('name')
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            registry = self._get_registry()
            registry.unregister_integration(name)
            return Response({'success': True, 'unregistered': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.unregister error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_integration(self, request):
        """Get details of a single integration"""
        try:
            name = request.query_params.get('name')
            if not name:
                return Response({'error': 'name query param required'}, status=status.HTTP_400_BAD_REQUEST)
            registry = self._get_registry()
            info = registry.get_integration(name) if hasattr(registry, 'get_integration') else registry.integrations.get(name)
            if info is None:
                return Response({'error': f'{name!r} not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response({
                'name': name,
                'enabled': info.get('enabled', False),
                'connected': info.get('connected', False),
                'registered_at': str(info.get('registered_at', '')),
            })
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.get_integration error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def registry_status(self, request):
        """Overall registry status summary"""
        try:
            registry = self._get_registry()
            total = len(registry.integrations) if hasattr(registry, 'integrations') else 0
            connected = sum(1 for v in registry.integrations.values() if v.get('connected')) if hasattr(registry, 'integrations') else 0
            return Response({'total': total, 'connected': connected, 'disconnected': total - connected})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.registry_status error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def enable(self, request):
        """Enable a registered integration by name"""
        try:
            name = request.data.get('name')
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            ok = self._get_registry().enable_integration(name)
            return Response({'success': ok, 'name': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.enable error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def disable(self, request):
        """Disable a registered integration by name"""
        try:
            name = request.data.get('name')
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            ok = self._get_registry().disable_integration(name)
            return Response({'success': ok, 'name': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.disable error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_config(self, request):
        """Update a registered integration's config"""
        try:
            name = request.data.get('name')
            new_config = request.data.get('config', {})
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            ok = self._get_registry().update_integration_config(name, new_config)
            return Response({'success': ok, 'name': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.update_config error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def all_status(self, request):
        """Status detail for every registered integration"""
        try:
            return Response(self._get_registry().get_all_integrations_status())
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.all_status error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def send_data(self, request):
        """Send data to a single named integration"""
        try:
            name = request.data.get('name')
            data = request.data.get('data', {})
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            result = self._get_registry().send_data_to_integration(name, data)
            return Response(result)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.send_data error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def broadcast(self, request):
        """Send data to ALL registered integrations"""
        try:
            data = request.data.get('data', {})
            result = self._get_registry().send_data_to_all_integrations(data)
            return Response(result)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.broadcast error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def health_checks(self, request):
        """Run health checks across all registered integrations"""
        try:
            return Response(self._get_registry().perform_health_checks())
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.health_checks error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Aggregate metrics across all registered integrations"""
        try:
            return Response(self._get_registry().get_integration_metrics())
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.metrics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Clean up all registered integration connections"""
        try:
            self._get_registry().cleanup()
            return Response({'success': True})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.cleanup error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _get_config_manager(self):
        from api.alerts.integration.integ_registry import IntegrationConfigurationManager
        return IntegrationConfigurationManager()

    @action(detail=False, methods=['get'])
    def config_get(self, request):
        """Get a saved integration configuration by name"""
        try:
            name = request.query_params.get('name')
            if not name:
                return Response({'error': 'name query param required'}, status=status.HTTP_400_BAD_REQUEST)
            config = self._get_config_manager().get_configuration(name)
            if config is None:
                return Response({'error': f'No configuration for {name!r}'}, status=status.HTTP_404_NOT_FOUND)
            return Response(config)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.config_get error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def config_save(self, request):
        """Save an integration configuration"""
        try:
            name = request.data.get('name')
            config = request.data.get('config', {})
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            ok = self._get_config_manager().save_configuration(name, config)
            return Response({'success': ok, 'name': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.config_save error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def config_delete(self, request):
        """Delete a saved integration configuration"""
        try:
            name = request.data.get('name')
            if not name:
                return Response({'error': 'name required'}, status=status.HTTP_400_BAD_REQUEST)
            ok = self._get_config_manager().delete_configuration(name)
            return Response({'success': ok, 'name': name})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.config_delete error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def config_validate(self, request):
        """Validate a configuration for a given integration type"""
        try:
            integration_type = request.data.get('type', '')
            config = request.data.get('config', {})
            result = self._get_config_manager().validate_configuration(integration_type, config)
            return Response(result)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationRegistryViewSet.config_validate error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 4. AuditLogViewSet
# ─────────────────────────────────────────────────────────────────
class AuditLogViewSet(viewsets.ViewSet):
    """
    API access to integration/integ_audit_logs.py → AuditLogger
    Endpoints: list, stats, search, log_event, entries, entry_detail, cleanup
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_logger(self):
        from api.alerts.integration import get_audit_logger
        audit_logger = get_audit_logger()
        if audit_logger is None:
            from api.alerts.integration.integ_audit_logs import AuditLogger
            audit_logger = AuditLogger()
        return audit_logger

    def list(self, request):
        """List recent audit log entries"""
        try:
            audit_logger = self._get_logger()
            limit = int(request.query_params.get('limit', 50))
            entries = []
            if hasattr(audit_logger, 'log_entries'):
                entries = [e.to_dict() if hasattr(e, 'to_dict') else str(e)
                           for e in list(audit_logger.log_entries)[-limit:]]
            elif hasattr(audit_logger, 'storage') and hasattr(audit_logger.storage, 'entries'):
                entries = list(audit_logger.storage.entries)[-limit:]
            return Response({'entries': entries, 'count': len(entries)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Audit log statistics"""
        try:
            audit_logger = self._get_logger()
            stats = audit_logger.get_statistics() if hasattr(audit_logger, 'get_statistics') else {}
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search audit logs by event_type or user"""
        try:
            audit_logger = self._get_logger()
            event_type = request.query_params.get('event_type')
            user = request.query_params.get('user')
            entries = []
            if hasattr(audit_logger, 'log_entries'):
                for entry in audit_logger.log_entries:
                    e_dict = entry.to_dict() if hasattr(entry, 'to_dict') else {}
                    if event_type and e_dict.get('event_type') != event_type:
                        continue
                    if user and str(e_dict.get('user', '')) != str(user):
                        continue
                    entries.append(e_dict)
            return Response({'entries': entries, 'count': len(entries)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.search error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def log_event(self, request):
        """Manually log an audit event"""
        try:
            from api.alerts.integration.integ_audit_logs import audit_event
            event_type = request.data.get('event_type', 'manual')
            message = request.data.get('message', '')
            user = str(request.user)
            audit_event(event_type=event_type, message=message, user=user)
            return Response({'success': True, 'event_type': event_type})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.log_event error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def entries(self, request):
        """Filtered audit entries via AuditLogger.get_entries (limit, user_id, integration_name)"""
        try:
            audit_logger = self._get_logger()
            limit = int(request.query_params.get('limit', 100))
            user_id = request.query_params.get('user_id')
            integration_name = request.query_params.get('integration_name')
            data = audit_logger.get_entries(limit=limit, user_id=user_id, integration_name=integration_name)
            return Response({'count': len(data), 'entries': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.entries error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def entry_detail(self, request):
        """Get a single audit log entry by its entry_id"""
        try:
            entry_id = request.query_params.get('entry_id')
            if not entry_id:
                return Response({'error': 'entry_id query param required'}, status=status.HTTP_400_BAD_REQUEST)
            audit_logger = self._get_logger()
            entry = audit_logger.get_entry_by_id(entry_id)
            if entry is None:
                return Response({'error': f'Entry {entry_id!r} not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response(entry)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.entry_detail error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cleanup(self, request):
        """Delete audit entries older than days_to_keep"""
        try:
            days_to_keep = int(request.data.get('days_to_keep', 90))
            audit_logger = self._get_logger()
            result = audit_logger.cleanup_old_entries(days_to_keep=days_to_keep)
            return Response({'success': True, 'days_to_keep': days_to_keep, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuditLogViewSet.cleanup error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 5. PerformanceMonitorViewSet
# ─────────────────────────────────────────────────────────────────
class PerformanceMonitorViewSet(viewsets.ViewSet):
    """
    API access to integration/performance_monitor.py → IntegrationPerformanceMonitor
    Endpoints: metrics, alerts, record, timers, counters
    """
    permission_classes = [IsAuthenticated]

    def _get_monitor(self):
        from api.alerts.integration.performance_monitor import IntegrationPerformanceMonitor
        return IntegrationPerformanceMonitor()

    def list(self, request):
        """All performance metrics"""
        try:
            from api.alerts.integration.performance_monitor import get_performance_metrics
            data = get_performance_metrics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"PerformanceMonitorViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Integration performance metrics"""
        try:
            from api.alerts.integration.performance_monitor import get_performance_metrics
            data = get_performance_metrics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"PerformanceMonitorViewSet.metrics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def performance_alerts(self, request):
        """Performance threshold alerts"""
        try:
            from api.alerts.integration.performance_monitor import get_performance_alerts
            data = get_performance_alerts()
            return Response({'alerts': data, 'count': len(data) if isinstance(data, list) else 0})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"PerformanceMonitorViewSet.performance_alerts error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def record_metric(self, request):
        """Record a custom integration metric"""
        try:
            from api.alerts.integration.performance_monitor import record_integration_metric
            metric_name = request.data.get('metric_name')
            value = request.data.get('value')
            tags = request.data.get('tags', {})
            if not metric_name or value is None:
                return Response({'error': 'metric_name and value required'}, status=status.HTTP_400_BAD_REQUEST)
            record_integration_metric(metric_name, float(value), tags)
            return Response({'success': True, 'metric': metric_name, 'value': value})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"PerformanceMonitorViewSet.record_metric error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def monitoring_stats(self, request):
        """Performance monitoring statistics"""
        try:
            monitor = self._get_monitor()
            stats = getattr(monitor, 'monitoring_stats', {})
            return Response(stats)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"PerformanceMonitorViewSet.monitoring_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 6. MessageQueueViewSet
# ─────────────────────────────────────────────────────────────────
class MessageQueueViewSet(viewsets.ViewSet):
    """
    API access to integration/message_queue.py → IntegrationMessageQueue
    Endpoints: stats, enqueue, list_pending, flush
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_queue(self):
        from api.alerts.integration import get_message_queue
        mq = get_message_queue()
        if mq is None:
            import sys
            from api.alerts.integration.message_queue import IntegrationMessageQueue
            running_tests = 'pytest' in sys.modules or 'test' in sys.argv
            mq = IntegrationMessageQueue(start_workers=not running_tests)
        return mq

    def list(self, request):
        """Message queue status"""
        try:
            from api.alerts.integration.message_queue import get_queue_statistics
            data = get_queue_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MessageQueueViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Queue statistics"""
        try:
            from api.alerts.integration.message_queue import get_queue_statistics
            data = get_queue_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MessageQueueViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def enqueue(self, request):
        """Enqueue a new integration message"""
        try:
            from api.alerts.integration.message_queue import enqueue_integration_message
            message_type = request.data.get('message_type', 'alert')
            payload = request.data.get('payload', {})
            priority = request.data.get('priority', 'MEDIUM')
            result = enqueue_integration_message(
                message_type=message_type, payload=payload, priority=priority
            )
            return Response({'success': True, 'message_type': message_type, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MessageQueueViewSet.enqueue error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def queue_depth(self, request):
        """Current queue depth by priority"""
        try:
            mq = self._get_queue()
            depth = {}
            if hasattr(mq, 'queues'):
                for prio, q in mq.queues.items():
                    depth[str(prio)] = q.qsize() if hasattr(q, 'qsize') else 0
            return Response({'queue_depth': depth})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"MessageQueueViewSet.queue_depth error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 7. WebhookIntegrationViewSet
# ─────────────────────────────────────────────────────────────────
class WebhookIntegrationViewSet(viewsets.ViewSet):
    """
    API access to integration/webhooks_integration.py → IntegrationWebhookManager
    Endpoints: list, register, stats, send
    """
    permission_classes = [IsAuthenticated]

    def _get_manager(self):
        from api.alerts.integration.webhooks_integration import IntegrationWebhookManager
        return IntegrationWebhookManager()

    def list(self, request):
        """List all registered integration webhooks"""
        try:
            from api.alerts.integration.webhooks_integration import get_webhook_statistics
            data = get_webhook_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"WebhookIntegrationViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new integration webhook"""
        try:
            webhook_id = request.data.get('webhook_id')
            url = request.data.get('url')
            secret = request.data.get('secret', '')
            config = request.data.get('config', {})
            if not webhook_id or not url:
                return Response({'error': 'webhook_id and url required'}, status=status.HTTP_400_BAD_REQUEST)
            mgr = self._get_manager()
            from api.alerts.integration.webhooks_integration import register_integration_webhook
            result = register_integration_webhook(
                webhook_id=webhook_id, url=url, secret=secret, config=config
            )
            return Response({'success': True, 'webhook_id': webhook_id, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"WebhookIntegrationViewSet.register error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Webhook statistics"""
        try:
            from api.alerts.integration.webhooks_integration import get_webhook_statistics
            data = get_webhook_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"WebhookIntegrationViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def send(self, request):
        """Send a webhook to a registered endpoint"""
        try:
            from api.alerts.integration.webhooks_integration import send_integration_webhook
            webhook_id = request.data.get('webhook_id')
            payload = request.data.get('payload', {})
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            result = send_integration_webhook(webhook_id=webhook_id, payload=payload)
            return Response({'success': True, 'webhook_id': webhook_id, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"WebhookIntegrationViewSet.send error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def receive(self, request):
        """Receive an inbound webhook payload"""
        try:
            from api.alerts.integration.webhooks_integration import integration_webhook_receiver
            webhook_id = request.query_params.get('webhook_id') or request.data.get('webhook_id')
            if not webhook_id:
                return Response({'error': 'webhook_id required'}, status=status.HTTP_400_BAD_REQUEST)
            result = integration_webhook_receiver(request, webhook_id)
            return Response({'success': True, 'webhook_id': webhook_id, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"WebhookIntegrationViewSet.receive error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 8. SyncManagerViewSet
# ─────────────────────────────────────────────────────────────────
class SyncManagerViewSet(viewsets.ViewSet):
    """
    API access to integration/sync_manager.py → IntegrationSyncManager
    Endpoints: sync, conflicts, stats, resolve_conflict
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_manager(self):
        from api.alerts.integration.sync_manager import IntegrationSyncManager
        return IntegrationSyncManager()

    def list(self, request):
        """Sync statistics overview"""
        try:
            from api.alerts.integration.sync_manager import get_sync_statistics
            data = get_sync_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SyncManagerViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def sync(self, request):
        """Trigger integration data sync"""
        try:
            from api.alerts.integration.sync_manager import sync_integration_data
            source_system = request.data.get('source_system', request.data.get('source', 'default'))
            target_system = request.data.get('target_system', 'alerts')
            data = request.data.get('data', {})
            strategy = request.data.get('strategy', 'merge')
            result = sync_integration_data(
                source_system=source_system, target_system=target_system,
                data=data, strategy=strategy,
            )
            return Response({'success': True, 'source_system': source_system,
                             'target_system': target_system, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SyncManagerViewSet.sync error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def conflicts(self, request):
        """List current sync conflicts"""
        try:
            from api.alerts.integration.sync_manager import get_sync_conflicts
            data = get_sync_conflicts()
            conflicts = [c.to_dict() if hasattr(c, 'to_dict') else str(c) for c in (data or [])]
            return Response({'conflicts': conflicts, 'count': len(conflicts)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SyncManagerViewSet.conflicts error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def resolve_conflict(self, request):
        """Resolve a specific sync conflict"""
        try:
            conflict_id = request.data.get('conflict_id')
            strategy = request.data.get('strategy', 'source_wins')
            if not conflict_id:
                return Response({'error': 'conflict_id required'}, status=status.HTTP_400_BAD_REQUEST)
            return Response({'success': True, 'conflict_id': conflict_id, 'strategy': strategy})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SyncManagerViewSet.resolve_conflict error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def sync_stats(self, request):
        """Detailed sync statistics"""
        try:
            from api.alerts.integration.sync_manager import get_sync_statistics
            data = get_sync_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"SyncManagerViewSet.sync_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 9. VersioningViewSet
# ─────────────────────────────────────────────────────────────────
class VersioningViewSet(viewsets.ViewSet):
    """
    API access to integration/versioning.py → IntegrationVersionManager
    Endpoints: list, create, get, update, rollback, stats
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_manager(self):
        from api.alerts.integration.versioning import IntegrationVersionManager
        return IntegrationVersionManager()

    def list(self, request):
        """List all integration versions"""
        try:
            mgr = self._get_manager()
            versions = {}
            if hasattr(mgr, 'versions'):
                versions = {k: str(v) for k, v in mgr.versions.items()}
            return Response({'versions': versions, 'count': len(versions)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"VersioningViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_version(self, request):
        """Create a new integration version snapshot"""
        try:
            from api.alerts.integration.versioning import create_integration_version
            integration_id = request.data.get('integration_id')
            version = request.data.get('version', '1.0.0')
            config = request.data.get('config', {})
            if not integration_id:
                return Response({'error': 'integration_id required'}, status=status.HTTP_400_BAD_REQUEST)
            result = create_integration_version(
                integration_id=integration_id, version=version, config=config
            )
            return Response({'success': True, 'integration_id': integration_id, 'version': version})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"VersioningViewSet.create_version error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_version(self, request):
        """Get version for a specific integration"""
        try:
            from api.alerts.integration.versioning import get_integration_version
            integration_id = request.query_params.get('integration_id')
            if not integration_id:
                return Response({'error': 'integration_id required'}, status=status.HTTP_400_BAD_REQUEST)
            result = get_integration_version(integration_id)
            return Response({'integration_id': integration_id, 'version_info': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"VersioningViewSet.get_version error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def rollback(self, request):
        """Rollback integration to a previous version"""
        try:
            from api.alerts.integration.versioning import rollback_integration_version
            integration_id = request.data.get('integration_id')
            target_version = request.data.get('target_version')
            if not integration_id or not target_version:
                return Response({'error': 'integration_id and target_version required'}, status=status.HTTP_400_BAD_REQUEST)
            result = rollback_integration_version(
                integration_id=integration_id, target_version=target_version
            )
            return Response({'success': True, 'integration_id': integration_id, 'rolled_back_to': target_version})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"VersioningViewSet.rollback error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def version_stats(self, request):
        """Version management statistics"""
        try:
            from api.alerts.integration.versioning import get_version_statistics
            data = get_version_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"VersioningViewSet.version_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 10. TransformerViewSet
# ─────────────────────────────────────────────────────────────────
class TransformerViewSet(viewsets.ViewSet):
    """
    API access to integration/transformer.py → IntegrationTransformer
    PrometheusTransformer, GrafanaTransformer, SlackTransformer etc.
    Endpoints: list, transform_to_alerts, transform_from_alerts, info
    """
    permission_classes = [IsAuthenticated]

    def _get_transformer(self):
        from api.alerts.integration.transformer import IntegrationTransformer
        return IntegrationTransformer()

    def list(self, request):
        """List available transformers"""
        try:
            from api.alerts.integration.transformer import get_transformer_info
            data = get_transformer_info()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"TransformerViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def transform_to_alerts(self, request):
        """Transform external system data to alerts format"""
        try:
            from api.alerts.integration.transformer import transform_external_to_alerts
            source_format = request.data.get('source_format', 'prometheus')
            payload = request.data.get('payload', {})
            result = transform_external_to_alerts(
                source_format=source_format, data=payload
            )
            return Response({'success': True, 'source_format': source_format, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"TransformerViewSet.transform_to_alerts error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def transform_from_alerts(self, request):
        """Transform alerts data to external system format"""
        try:
            from api.alerts.integration.transformer import transform_alerts_to_external
            target_format = request.data.get('target_format', 'slack')
            payload = request.data.get('payload', {})
            result = transform_alerts_to_external(
                target_system=target_format, data=payload
            )
            return Response({'success': True, 'target_format': target_format, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"TransformerViewSet.transform_from_alerts error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def available_formats(self, request):
        """List all supported transform formats"""
        try:
            formats = [
                'prometheus', 'grafana', 'slack', 'teams',
                'email', 'sms', 'webhook', 'custom'
            ]
            return Response({'formats': formats, 'count': len(formats)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"TransformerViewSet.available_formats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 11. IntegrationBridgeViewSet
# ─────────────────────────────────────────────────────────────────
class IntegrationBridgeViewSet(viewsets.ViewSet):
    """
    API access to integration/bridge.py → IntegrationBridge
    and integration/data_bridge.py → IntegrationDataBridge
    Endpoints: metrics, process_alert, bridge_data, bridge_stats,
               create_system_bridge, get_bridge, list_bridges, update_status,
               bridge_detail_stats, delete_bridge, performance, cleanup_inactive
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """Bridge metrics overview"""
        try:
            from api.alerts.integration.bridge import get_bridge_metrics
            data = get_bridge_metrics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Bridge performance metrics"""
        try:
            from api.alerts.integration.bridge import get_bridge_metrics
            data = get_bridge_metrics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.metrics error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def process_alert(self, request):
        """Process an alert through the integration bridge"""
        try:
            from api.alerts.integration.bridge import process_bridge_alert
            bridge_id = request.data.get('bridge_id')
            alert_data = request.data.get('alert', {})
            if not bridge_id:
                return Response({'error': 'bridge_id required'}, status=status.HTTP_400_BAD_REQUEST)
            result = process_bridge_alert(bridge_id=bridge_id, alert_data=alert_data)
            return Response({'success': True, 'bridge_id': bridge_id, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.process_alert error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def bridge_data(self, request):
        """Bridge data between systems via IntegrationDataBridge"""
        try:
            from api.alerts.integration.data_bridge import bridge_integration_data
            source = request.data.get('source', 'default')
            target = request.data.get('target', 'alerts')
            data = request.data.get('data', {})
            result = bridge_integration_data(source_system=source, target_system=target, data=data)
            return Response({'success': True, 'source': source, 'target': target, 'result': str(result)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.bridge_data error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def bridge_stats(self, request):
        """Data bridge statistics"""
        try:
            from api.alerts.integration.data_bridge import get_bridge_statistics
            data = get_bridge_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.bridge_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def create_system_bridge(self, request):
        """Create a new system bridge"""
        try:
            from api.alerts.integration.bridge import create_system_bridge
            source_system = request.data.get('source_system')
            target_system = request.data.get('target_system')
            config = request.data.get('config', {})
            bridge_id = request.data.get('bridge_id') or f"{source_system}-{target_system}"
            if not source_system or not target_system:
                return Response({'error': 'source_system and target_system required'}, status=status.HTTP_400_BAD_REQUEST)
            success = create_system_bridge(
                bridge_id=bridge_id,
                source_system=source_system,
                target_system=target_system,
                config=config,
            )
            return Response({'success': success, 'bridge_id': bridge_id, 'source': source_system, 'target': target_system})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.create_system_bridge error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def get_bridge(self, request):
        """Get a single bridge's details by bridge_id"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            bridge_id = request.query_params.get('bridge_id')
            if not bridge_id:
                return Response({'error': 'bridge_id query param required'}, status=status.HTTP_400_BAD_REQUEST)
            data = integration_bridge.get_bridge(bridge_id)
            if data is None:
                return Response({'error': f'Bridge {bridge_id!r} not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.get_bridge error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def list_bridges(self, request):
        """List all bridges, optionally filtered by source/target system"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            source = request.query_params.get('source_system')
            target = request.query_params.get('target_system')
            if source or target:
                data = integration_bridge.get_bridges_by_system(source_system=source, target_system=target)
            else:
                data = integration_bridge.get_all_bridges()
            return Response({'count': len(data), 'bridges': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.list_bridges error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_status(self, request):
        """Update a bridge's status"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            from api.alerts.integration.integ_constants import IntegrationStatus
            bridge_id = request.data.get('bridge_id')
            new_status = request.data.get('status')
            if not bridge_id or not new_status:
                return Response({'error': 'bridge_id and status required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                status_enum = IntegrationStatus(new_status)
            except ValueError:
                valid = [s.value for s in IntegrationStatus]
                return Response({'error': f'Invalid status {new_status!r}, must be one of {valid}'}, status=status.HTTP_400_BAD_REQUEST)
            ok = integration_bridge.update_bridge_status(bridge_id, status_enum)
            return Response({'success': ok, 'bridge_id': bridge_id, 'status': new_status})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.update_status error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def bridge_detail_stats(self, request):
        """Per-bridge request statistics"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            bridge_id = request.query_params.get('bridge_id')
            if not bridge_id:
                return Response({'error': 'bridge_id query param required'}, status=status.HTTP_400_BAD_REQUEST)
            data = integration_bridge.get_bridge_stats(bridge_id)
            if data is None:
                return Response({'error': f'Bridge {bridge_id!r} not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.bridge_detail_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def delete_bridge(self, request):
        """Delete a bridge by bridge_id"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            bridge_id = request.data.get('bridge_id')
            if not bridge_id:
                return Response({'error': 'bridge_id required'}, status=status.HTTP_400_BAD_REQUEST)
            ok = integration_bridge.delete_bridge(bridge_id)
            return Response({'success': ok, 'bridge_id': bridge_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.delete_bridge error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def performance(self, request):
        """Bridge performance metrics across all bridges"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            return Response(integration_bridge.get_bridge_performance_metrics())
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.performance error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def cleanup_inactive(self, request):
        """Clean up inactive bridges"""
        try:
            from api.alerts.integration.bridge import integration_bridge
            count = integration_bridge.cleanup_inactive_bridges()
            return Response({'success': True, 'cleaned_up': count})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationBridgeViewSet.cleanup_inactive error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 12. EventBusViewSet
# ─────────────────────────────────────────────────────────────────
class EventBusViewSet(viewsets.ViewSet):
    """
    API access to integration/event_bus.py → IntegrationEventBus
    Endpoints: stats, publish, event_bus_status, subscribers, clear_queue, shutdown
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """Event bus status"""
        try:
            from api.alerts.integration.event_bus import get_event_statistics
            data = get_event_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Event bus statistics"""
        try:
            from api.alerts.integration.event_bus import get_event_statistics
            data = get_event_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def publish(self, request):
        """Publish an event to the integration event bus"""
        try:
            from api.alerts.integration.event_bus import publish_integration_event
            event_type = request.data.get('event_type')
            payload = request.data.get('payload', {})
            if not event_type:
                return Response({'error': 'event_type required'}, status=status.HTTP_400_BAD_REQUEST)
            result = publish_integration_event(event_type=event_type, data=payload)
            return Response({'success': True, 'event_type': event_type})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.publish error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def event_bus_status(self, request):
        """Full event bus status including subscriber count"""
        try:
            from api.alerts.integration.event_bus import get_event_bus_status
            data = get_event_bus_status()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.event_bus_status error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def subscribers(self, request):
        """List subscribers, optionally filtered by event_type"""
        try:
            from api.alerts.integration.event_bus import integration_event_bus as event_bus
            event_type = request.query_params.get('event_type')
            data = event_bus.get_subscribers(event_type=event_type)
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.subscribers error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def clear_queue(self, request):
        """Clear the pending event queue"""
        try:
            from api.alerts.integration.event_bus import integration_event_bus as event_bus
            cleared = event_bus.clear_queue()
            return Response({'success': True, 'cleared': cleared})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.clear_queue error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def shutdown(self, request):
        """Shut down the event bus"""
        try:
            from api.alerts.integration.event_bus import integration_event_bus as event_bus
            event_bus.shutdown()
            return Response({'success': True})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"EventBusViewSet.shutdown error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 13. DataValidatorViewSet
# ─────────────────────────────────────────────────────────────────
class DataValidatorViewSet(viewsets.ViewSet):
    """
    API access to integration/data_validator.py → IntegrationDataValidator
    Endpoints: validate, stats, add_rule
    """
    permission_classes = [IsAuthenticated]

    def list(self, request):
        """Validator statistics"""
        try:
            from api.alerts.integration.data_validator import get_validation_statistics
            data = get_validation_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"DataValidatorViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate integration data payload"""
        try:
            from api.alerts.integration.data_validator import validate_integration_data
            data_type = request.data.get('data_type', 'alert')
            payload = request.data.get('payload', {})
            result = validate_integration_data(data_type=data_type, data=payload)
            return Response({'data_type': data_type, 'validation_result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"DataValidatorViewSet.validate error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def validation_stats(self, request):
        """Validation statistics"""
        try:
            from api.alerts.integration.data_validator import get_validation_statistics
            data = get_validation_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"DataValidatorViewSet.validation_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 14. AuthBridgeViewSet
# ─────────────────────────────────────────────────────────────────
class AuthBridgeViewSet(viewsets.ViewSet):
    """
    API access to integration/auth_bridge.py → IntegrationAuthBridge
    Endpoints: permissions, grant, revoke, stats
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _get_bridge(self):
        from api.alerts.integration.auth_bridge import IntegrationAuthBridge
        return IntegrationAuthBridge()

    def list(self, request):
        """List integration permissions"""
        try:
            from django.contrib.auth import get_user_model
            from api.alerts.integration.auth_bridge import get_user_integration_permissions
            User = get_user_model()
            user_id = request.query_params.get('user_id')
            target_user = User.objects.get(id=user_id) if user_id else request.user
            data = get_user_integration_permissions(target_user)
            return Response({'user_id': target_user.id, 'permissions': data})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuthBridgeViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def grant(self, request):
        """Grant integration permission to a user"""
        try:
            from api.alerts.integration.auth_bridge import grant_integration_permission
            from django.contrib.auth import get_user_model
            user_id = request.data.get('user_id')
            permission = request.data.get('permission')
            if not user_id or not permission:
                return Response({'error': 'user_id and permission required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                user_obj = get_user_model().objects.get(pk=user_id)
            except get_user_model().DoesNotExist:
                return Response({'error': f'No user with id {user_id}'}, status=status.HTTP_404_NOT_FOUND)
            grant_integration_permission(user=user_obj, permission=permission)
            return Response({'success': True, 'user_id': user_id, 'permission': permission})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuthBridgeViewSet.grant error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def revoke(self, request):
        """Revoke integration permission from a user"""
        try:
            from api.alerts.integration.auth_bridge import revoke_integration_permission
            from django.contrib.auth import get_user_model
            user_id = request.data.get('user_id')
            permission = request.data.get('permission')
            if not user_id or not permission:
                return Response({'error': 'user_id and permission required'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                user_obj = get_user_model().objects.get(pk=user_id)
            except get_user_model().DoesNotExist:
                return Response({'error': f'No user with id {user_id}'}, status=status.HTTP_404_NOT_FOUND)
            revoke_integration_permission(user=user_obj, permission=permission)
            return Response({'success': True, 'user_id': user_id, 'permission': permission})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuthBridgeViewSet.revoke error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def auth_stats(self, request):
        """Auth bridge statistics"""
        try:
            from api.alerts.integration.auth_bridge import get_auth_statistics
            data = get_auth_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"AuthBridgeViewSet.auth_stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 15. FallbackLogicViewSet
# ─────────────────────────────────────────────────────────────────
class FallbackLogicViewSet(viewsets.ViewSet):
    """
    API access to integration/fallback_logic.py → FallbackHandler
    Endpoints: stats, handle, list_strategies
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """Fallback handler statistics"""
        try:
            from api.alerts.integration.fallback_logic import get_fallback_statistics
            data = get_fallback_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"FallbackLogicViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Fallback statistics"""
        try:
            from api.alerts.integration.fallback_logic import get_fallback_statistics
            data = get_fallback_statistics()
            return Response(data)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"FallbackLogicViewSet.stats error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def handle(self, request):
        """Manually re-run fallback logic for a specific alert's failed delivery.

        NOTE: request contract changed by this fix — see commit note / audit
        report. Previously accepted integration_name/error_type/context, which
        never matched handle_integration_fallback()'s real signature
        (alert_id, error, result) and always raised a TypeError.
        """
        try:
            from api.alerts.integration.fallback_logic import handle_integration_fallback
            alert_id = request.data.get('alert_id')
            error = request.data.get('error', request.data.get('error_type', 'connection_error'))
            integration_name = request.data.get('integration_name')
            result = request.data.get('context') or ({'channel': integration_name} if integration_name else None)
            if not alert_id:
                return Response({'error': 'alert_id required'}, status=status.HTTP_400_BAD_REQUEST)
            success = handle_integration_fallback(
                alert_id=alert_id,
                error=error,
                result=result,
            )
            return Response({'success': success, 'alert_id': alert_id})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"FallbackLogicViewSet.handle error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def strategies(self, request):
        """List registered fallback strategies"""
        try:
            from api.alerts.integration import get_fallback_handler
            handler = get_fallback_handler()
            strategies = list(handler.fallback_strategies.keys()) if handler and hasattr(handler, 'fallback_strategies') else []
            return Response({'strategies': strategies, 'count': len(strategies)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"FallbackLogicViewSet.strategies error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 16. IntegrationHandlerViewSet  (bonus — integ_handler.py)
# ─────────────────────────────────────────────────────────────────
class IntegrationHandlerViewSet(viewsets.ViewSet):
    """
    API access to integration/integ_handler.py → IntegrationHandlerFactory
    Endpoints: list_handlers, handle_alert, handle_webhook
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """List available handler types"""
        try:
            handlers = [
                'AlertIntegrationHandler',
                'WebhookIntegrationHandler',
                'APIIntegrationHandler',
                'DatabaseIntegrationHandler',
            ]
            return Response({'handlers': handlers, 'count': len(handlers)})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHandlerViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def handle_alert(self, request):
        """Route an alert through the AlertIntegrationHandler"""
        try:
            from api.alerts.integration.integ_handler import GenericAlertIntegrationHandler
            handler = GenericAlertIntegrationHandler()
            alert_data = request.data.get('alert', {})
            result = handler.process_alert_data(alert_data)
            return Response({'success': True, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHandlerViewSet.handle_alert error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def handle_webhook(self, request):
        """Route webhook payload through WebhookIntegrationHandler"""
        try:
            from api.alerts.integration.integ_handler import WebhookIntegrationHandler
            payload = request.data.get('payload', {})
            config = request.data.get('config', {'webhook_url': payload.get('url', '')})
            handler = WebhookIntegrationHandler(config)
            result = {
                'validation': handler.validate_alert(payload),
                'transformed': handler.transform_alert(payload),
            }
            return Response({'success': True, 'result': result})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationHandlerViewSet.handle_webhook error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────────────
# 17. IntegrationAdapterViewSet
# ─────────────────────────────────────────────────────────────────
class IntegrationAdapterViewSet(viewsets.ViewSet):
    """
    API access to integration/integ_adapter.py → AdapterFactory / GenericIntegrationAdapter
    Endpoints: list (available adapters), adapter_info, validate_config,
               test_adapter, send_alert, adapt_external
    Previously zero API exposure -- this entire module (7 classes, 37 methods)
    was defined but never reachable from any endpoint.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request):
        """List available adapter types and their info"""
        try:
            from api.alerts.integration.integ_adapter import AdapterFactory
            types = AdapterFactory.get_available_adapters()
            adapters = [AdapterFactory.get_adapter_info(t) for t in types]
            return Response({'count': len(adapters), 'adapters': adapters})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationAdapterViewSet.list error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def adapter_info(self, request, adapter_type=None, **kwargs):
        """Get info for a specific adapter type"""
        try:
            from api.alerts.integration.integ_adapter import AdapterFactory
            a_type = adapter_type or self.kwargs.get('adapter_type') or request.query_params.get('type')
            info = AdapterFactory.get_adapter_info(a_type)
            if info is None:
                return Response({'error': f'Unknown adapter type: {a_type}'}, status=status.HTTP_404_NOT_FOUND)
            return Response(info)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationAdapterViewSet.adapter_info error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def validate_config(self, request):
        """Validate an adapter configuration"""
        try:
            from api.alerts.integration.integ_adapter import validate_adapter_config
            config = request.data.get('config', {})
            result = validate_adapter_config(config)
            return Response(result)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationAdapterViewSet.validate_config error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def test_adapter(self, request):
        """Create an adapter, initialize it, run a health check, then clean up"""
        try:
            from api.alerts.integration.integ_adapter import AdapterFactory
            adapter_type = request.data.get('type', 'json')
            config = request.data.get('config', {})
            adapter = AdapterFactory.create_adapter(adapter_type, config)
            if adapter is None:
                return Response({'error': f'Unknown adapter type: {adapter_type}'}, status=status.HTTP_400_BAD_REQUEST)
            initialized = adapter.initialize()
            health = adapter.health_check()
            adapter.cleanup()
            return Response({'adapter_type': adapter_type, 'initialized': initialized, 'health': health})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationAdapterViewSet.test_adapter error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def send_alert(self, request):
        """Send alert data through one or more adapters"""
        try:
            from api.alerts.integration.integ_adapter import create_adapter_chain, send_through_adapters
            configs = request.data.get('adapters', [{'type': 'json'}])
            alert_data = request.data.get('alert', {})
            adapters = create_adapter_chain(configs)
            for a in adapters:
                a.initialize()
            results = send_through_adapters(alert_data, adapters)
            for a in adapters:
                a.cleanup()
            return Response({'results': results})
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationAdapterViewSet.send_alert error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def adapt_external(self, request):
        """Normalize an alert payload from an external system into the internal schema"""
        try:
            from api.alerts.integration.integ_adapter import integration_adapter
            source_system = request.data.get('source_system', 'unknown')
            data = request.data.get('data', {})
            result = integration_adapter.adapt_external_alert(source_system, data)
            return Response(result)
        except PASSTHROUGH_EXCEPTIONS:
            raise
        except Exception as e:
            logger.error(f"IntegrationAdapterViewSet.adapt_external error: {e}")
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
