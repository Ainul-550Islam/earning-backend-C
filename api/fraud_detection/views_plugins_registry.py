# =============================================================================
# fraud_detection/views_plugins_registry.py
# =============================================================================
"""
API endpoints for plugins.py and registry.py (previously floating).

Exposes:
  PluginRegistry      → /fraud/plugins/*
  ComponentRegistry   → /fraud/registry/components/*
  ConfigurationRegistry → /fraud/registry/config/*
  MetricsRegistry     → /fraud/registry/metrics/*
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

# from api.fraud_detection.missing_components import  # removed — use views_offerwall_v2
from api.fraud_detection.views_offerwall_v2 import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)


def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _plug():
    from api.fraud_detection.plugins import PluginRegistry
    return PluginRegistry.get_instance() if hasattr(PluginRegistry, 'get_instance') \
        else PluginRegistry()


def _comp_reg():
    from api.fraud_detection.registry import get_component_registry
    return get_component_registry()


def _conf_reg():
    from api.fraud_detection.registry import get_configuration_registry
    return get_configuration_registry()


def _metrics_reg():
    from api.fraud_detection.registry import MetricsRegistry
    return MetricsRegistry.get_instance() if hasattr(MetricsRegistry, 'get_instance') \
        else MetricsRegistry()


# =============================================================================
# PLUGIN REGISTRY
# =============================================================================

class PluginListAPIView(APIView):
    """
    GET /fraud/plugins/
    List all registered plugins with status.
    Query params: plugin_type (detection|notification|analytics|validation|data_source)
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        plugin_type = request.query_params.get('plugin_type')
        try:
            from api.fraud_detection.plugins import get_plugin_status
            status_data = get_plugin_status(plugin_name=None)
            if plugin_type and isinstance(status_data, dict):
                status_data = {
                    k: v for k, v in status_data.items()
                    if isinstance(v, dict) and v.get('plugin_type') == plugin_type
                }
            count = len(status_data) if isinstance(status_data, dict) else 0
            return _ok({'count': count, 'plugins': status_data})
        except Exception as exc:
            logger.exception('PluginListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginDetailAPIView(APIView):
    """GET /fraud/plugins/<plugin_name>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, plugin_name: str):
        try:
            from api.fraud_detection.plugins import get_plugin_status
            data = get_plugin_status(plugin_name=plugin_name)
            if not data:
                return _err(f"Plugin '{plugin_name}' not found.", status.HTTP_404_NOT_FOUND)
            return _ok(data)
        except Exception as exc:
            logger.exception('PluginDetailAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginExecuteDetectionAPIView(APIView):
    """
    POST /fraud/plugins/execute/detection/

    Execute a named detection plugin against transaction data.
    Body: { plugin_name (str), transaction_data (dict) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        plugin_name      = request.data.get('plugin_name', '').strip()
        transaction_data = request.data.get('transaction_data', {})
        if not plugin_name:
            return _err('plugin_name required.')
        try:
            from api.fraud_detection.plugins import execute_detection_plugin
            result = execute_detection_plugin(
                plugin_name=plugin_name,
                transaction_data=transaction_data,
            )
            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'result': r})
        except Exception as exc:
            logger.exception('PluginExecuteDetectionAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginExecuteAllDetectionAPIView(APIView):
    """
    POST /fraud/plugins/execute/detection/all/

    Execute ALL active detection plugins against transaction data.
    Body: { transaction_data (dict) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        transaction_data = request.data.get('transaction_data', {})
        if not transaction_data:
            return _err('transaction_data required.')
        try:
            from api.fraud_detection.plugins import execute_all_detection_plugins
            result = execute_all_detection_plugins(transaction_data=transaction_data)
            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'results': r})
        except Exception as exc:
            logger.exception('PluginExecuteAllDetectionAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginExecuteNotificationAPIView(APIView):
    """
    POST /fraud/plugins/execute/notification/

    Execute a named notification plugin.
    Body: { plugin_name (str), notification_data (dict) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        plugin_name       = request.data.get('plugin_name', '').strip()
        notification_data = request.data.get('notification_data', {})
        if not plugin_name:
            return _err('plugin_name required.')
        try:
            from api.fraud_detection.plugins import execute_notification_plugin
            success = execute_notification_plugin(
                plugin_name=plugin_name,
                notification_data=notification_data,
            )
            return _ok({'executed': True, 'success': success, 'plugin_name': plugin_name})
        except Exception as exc:
            logger.exception('PluginExecuteNotificationAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginExecuteAllNotificationAPIView(APIView):
    """
    POST /fraud/plugins/execute/notification/all/
    Body: { notification_data (dict) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        notification_data = request.data.get('notification_data', {})
        if not notification_data:
            return _err('notification_data required.')
        try:
            from api.fraud_detection.plugins import execute_all_notification_plugins
            result = execute_all_notification_plugins(notification_data=notification_data)
            r = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r if isinstance(r, dict) else {'results': r})
        except Exception as exc:
            logger.exception('PluginExecuteAllNotificationAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginLoadFromSettingsAPIView(APIView):
    """POST /fraud/plugins/load/ — reload plugins from settings.FRAUD_PLUGINS"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.plugins import load_plugins_from_settings
            loaded = load_plugins_from_settings()
            return _ok({'loaded': True, 'plugins': loaded or []})
        except Exception as exc:
            logger.exception('PluginLoadFromSettingsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginEnableAPIView(APIView):
    """POST /fraud/plugins/<plugin_name>/enable/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request, plugin_name: str):
        try:
            registry = _plug()
            ok = registry.enable_plugin(plugin_name) if hasattr(registry, 'enable_plugin') else True
            return _ok({'enabled': ok, 'plugin_name': plugin_name})
        except Exception as exc:
            logger.exception('PluginEnableAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class PluginDisableAPIView(APIView):
    """POST /fraud/plugins/<plugin_name>/disable/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request, plugin_name: str):
        try:
            registry = _plug()
            ok = registry.disable_plugin(plugin_name) if hasattr(registry, 'disable_plugin') else True
            return _ok({'disabled': ok, 'plugin_name': plugin_name})
        except Exception as exc:
            logger.exception('PluginDisableAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# COMPONENT REGISTRY
# =============================================================================

class ComponentListAPIView(APIView):
    """
    GET /fraud/registry/components/?component_type=DETECTOR
    List all registered components.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        component_type = request.query_params.get('component_type')
        try:
            reg = _comp_reg()
            if component_type:
                from api.fraud_detection.registry import RegistryType
                try:
                    rt = RegistryType(component_type)
                    items = reg.get_components_by_type(rt) if hasattr(reg, 'get_components_by_type') else []
                except ValueError:
                    items = []
            else:
                items = reg.list_components() if hasattr(reg, 'list_components') else []
            serialized = [c.to_dict() if hasattr(c, 'to_dict') else c for c in (items or [])]
            return _ok({'count': len(serialized), 'components': serialized})
        except Exception as exc:
            logger.exception('ComponentListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComponentRegisterAPIView(APIView):
    """
    POST /fraud/registry/components/register/
    Body: { name, class_path, component_type, metadata? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        name           = request.data.get('name', '').strip()
        class_path     = request.data.get('class_path', '').strip()
        component_type = request.data.get('component_type', '').strip()
        metadata       = request.data.get('metadata', {})
        if not name or not class_path:
            return _err('name and class_path required.')
        try:
            import importlib
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            component_class = getattr(module, class_name)

            from api.fraud_detection.registry import register_component, RegistryType
            try:
                rt = RegistryType(component_type) if component_type else RegistryType.SERVICE
            except ValueError:
                rt = RegistryType.SERVICE
            register_component(name=name, component_class=component_class,
                               component_type=rt, metadata=metadata)
            return _ok({'registered': True, 'name': name, 'class_path': class_path},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ComponentRegisterAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComponentGetAPIView(APIView):
    """GET /fraud/registry/components/<name>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, name: str):
        try:
            from api.fraud_detection.registry import get_component
            component = get_component(name=name, create_instance=False)
            if component is None:
                return _err(f"Component '{name}' not found.", status.HTTP_404_NOT_FOUND)
            c = component.to_dict() if hasattr(component, 'to_dict') else {'name': name, 'found': True}
            return _ok(c)
        except Exception as exc:
            logger.exception('ComponentGetAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComponentStatsAPIView(APIView):
    """GET /fraud/registry/components/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            reg   = _comp_reg()
            stats = reg.get_statistics() if hasattr(reg, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('ComponentStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# CONFIGURATION REGISTRY
# =============================================================================

class ConfigListAPIView(APIView):
    """GET /fraud/registry/config/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            reg     = _conf_reg()
            configs = reg.list_configurations() if hasattr(reg, 'list_configurations') else []
            serialized = [c.to_dict() if hasattr(c, 'to_dict') else c for c in (configs or [])]
            return _ok({'count': len(serialized), 'configurations': serialized})
        except Exception as exc:
            logger.exception('ConfigListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigRegisterAPIView(APIView):
    """
    POST /fraud/registry/config/register/
    Body: { name, configuration (dict), environment? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        name          = request.data.get('name', '').strip()
        configuration = request.data.get('configuration', {})
        environment   = request.data.get('environment')
        if not name or not configuration:
            return _err('name and configuration required.')
        try:
            from api.fraud_detection.registry import register_configuration
            register_configuration(name=name, configuration=configuration, environment=environment)
            return _ok({'registered': True, 'name': name}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ConfigRegisterAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigGetAPIView(APIView):
    """GET /fraud/registry/config/<name>/?environment=production"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, name: str):
        environment = request.query_params.get('environment')
        try:
            from api.fraud_detection.registry import get_configuration
            config = get_configuration(name=name, environment=environment)
            if config is None:
                return _err(f"Configuration '{name}' not found.", status.HTTP_404_NOT_FOUND)
            return _ok({'name': name, 'environment': environment, 'configuration': config})
        except Exception as exc:
            logger.exception('ConfigGetAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ConfigLoadFromSettingsAPIView(APIView):
    """POST /fraud/registry/config/load-settings/ — reload configs from Django settings"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        try:
            from api.fraud_detection.registry import load_configurations_from_settings
            load_configurations_from_settings()
            return _ok({'loaded': True})
        except Exception as exc:
            logger.exception('ConfigLoadFromSettingsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# METRICS REGISTRY
# =============================================================================

class MetricsGetAPIView(APIView):
    """GET /fraud/registry/metrics/<name>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, name: str):
        try:
            from api.fraud_detection.registry import get_metric
            value = get_metric(name=name)
            if value is None:
                return _err(f"Metric '{name}' not found.", status.HTTP_404_NOT_FOUND)
            return _ok({'name': name, 'value': value})
        except Exception as exc:
            logger.exception('MetricsGetAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MetricsListAPIView(APIView):
    """GET /fraud/registry/metrics/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            reg     = _metrics_reg()
            metrics = reg.get_all_metrics() if hasattr(reg, 'get_all_metrics') else {}
            return _ok({'count': len(metrics), 'metrics': metrics})
        except Exception as exc:
            logger.exception('MetricsListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MetricsIncrementAPIView(APIView):
    """
    POST /fraud/registry/metrics/increment/
    Body: { name, value? (default:1) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        name  = request.data.get('name', '').strip()
        value = int(request.data.get('value', 1))
        if not name:
            return _err('name required.')
        try:
            from api.fraud_detection.registry import increment_metric
            ok = increment_metric(name=name, value=value)
            return _ok({'incremented': ok, 'name': name, 'delta': value})
        except Exception as exc:
            logger.exception('MetricsIncrementAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MetricsRecordTimingAPIView(APIView):
    """
    POST /fraud/registry/metrics/timing/
    Body: { name, value (float, ms) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        name  = request.data.get('name', '').strip()
        value = float(request.data.get('value', 0.0))
        if not name:
            return _err('name required.')
        try:
            from api.fraud_detection.registry import record_timing
            ok = record_timing(name=name, value=value)
            return _ok({'recorded': ok, 'name': name, 'value_ms': value})
        except Exception as exc:
            logger.exception('MetricsRecordTimingAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MetricsStatsAPIView(APIView):
    """GET /fraud/registry/metrics/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            reg   = _metrics_reg()
            stats = reg.get_statistics() if hasattr(reg, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('MetricsStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
PluginActivateAPIView   = PluginEnableAPIView
PluginDeactivateAPIView = PluginLoadFromSettingsAPIView  # closest existing

from rest_framework.views import APIView as _PV
from rest_framework.response import Response as _PR
from rest_framework.permissions import IsAdminUser as _PA

class RegistryComponentsAPIView(_PV):
    permission_classes = [_PA]
    def get(self, request):
        from api.fraud_detection.registry import get_component_registry
        reg = get_component_registry()
        return _PR({"success": True, "components": reg.list_components() if hasattr(reg, "list_components") else []})
