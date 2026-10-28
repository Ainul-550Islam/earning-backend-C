# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/views.py  — NEW FILE
#
# Exposes all INTEGRATION_SYSTEM components via DRF APIViews.
# WAS FLOATING: bridge.py, auth_bridge.py, data_bridge.py, event_bus.py,
#   circuit_breaker.py, message_queue.py, performance_monitor.py,
#   sync_manager.py, webhooks_integration.py, versioning.py,
#   integ_audit_logs.py, integ_registry.py, health_check.py
#   — all had logic but zero API exposure.
# =============================================================================
from __future__ import annotations

import logging
from typing import Any, Dict

from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ok(data: Dict[str, Any], http_status=status.HTTP_200_OK) -> Response:
    return Response({"success": True, "data": data}, status=http_status)


def _err(message: str, http_status=status.HTTP_400_BAD_REQUEST) -> Response:
    return Response({"success": False, "error": message}, status=http_status)


# ─────────────────────────────────────────────────────────────────────────────
# BRIDGE — core integration bridge
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationBridgeStatusView(APIView):
    """GET /integration/bridge/status/ — connection + health summary."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .bridge import get_integration_bridge
            bridge = get_integration_bridge()
            return _ok(bridge.get_status())
        except Exception as exc:
            logger.error("bridge status error: %s", exc)
            return _err(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)


class IntegrationBridgeSyncView(APIView):
    """POST /integration/bridge/sync/ — trigger full sync cycle."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .bridge import get_integration_bridge
            result = get_integration_bridge().sync()
            return _ok(result)
        except Exception as exc:
            logger.error("bridge sync error: %s", exc)
            return _err(str(exc))


class IntegrationBridgeHealthView(APIView):
    """GET /integration/bridge/health/ — detailed health report."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .health_check import IntegrationHealthChecker
            return _ok(IntegrationHealthChecker().run_all_checks())
        except Exception as exc:
            return _err(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)


# ─────────────────────────────────────────────────────────────────────────────
# AUTH BRIDGE
# ─────────────────────────────────────────────────────────────────────────────

class AuthBridgeVerifyView(APIView):
    """POST /integration/auth/verify/ — verify external auth token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .auth_bridge import get_auth_bridge
            token  = request.data.get("token")
            result = get_auth_bridge().verify_token(token)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


class AuthBridgeRefreshView(APIView):
    """POST /integration/auth/refresh/ — refresh external session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .auth_bridge import get_auth_bridge
            result = get_auth_bridge().refresh_session(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


class AuthBridgeStatusView(APIView):
    """GET /integration/auth/status/ — external auth service status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .auth_bridge import get_auth_bridge
            return _ok(get_auth_bridge().get_status())
        except Exception as exc:
            return _err(str(exc), status.HTTP_503_SERVICE_UNAVAILABLE)


# ─────────────────────────────────────────────────────────────────────────────
# DATA BRIDGE
# ─────────────────────────────────────────────────────────────────────────────

class DataBridgeSyncView(APIView):
    """POST /integration/data/sync/ — push data to external system."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .data_bridge import get_data_bridge
            result = get_data_bridge().sync(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


class DataBridgeFetchView(APIView):
    """POST /integration/data/fetch/ — pull data from external system."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .data_bridge import get_data_bridge
            result = get_data_bridge().fetch(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


class DataBridgeValidateView(APIView):
    """POST /integration/data/validate/ — validate payload via data_validator."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .data_validator import IntegrationDataValidator
            result = IntegrationDataValidator().validate(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# EVENT BUS
# ─────────────────────────────────────────────────────────────────────────────

class EventBusPublishView(APIView):
    """POST /integration/events/publish/ — publish event to the bus."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            from .event_bus import get_event_bus
            result = get_event_bus().publish(request.data)
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            return _err(str(exc))


class EventBusSubscriptionsView(APIView):
    """GET /integration/events/subscriptions/ — list active subscriptions."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .event_bus import get_event_bus
            return _ok({"subscriptions": get_event_bus().list_subscriptions()})
        except Exception as exc:
            return _err(str(exc))


class EventBusStatsView(APIView):
    """GET /integration/events/stats/ — event bus metrics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .event_bus import get_event_bus
            return _ok(get_event_bus().get_stats())
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# CIRCUIT BREAKER
# ─────────────────────────────────────────────────────────────────────────────

class CircuitBreakerStatusView(APIView):
    """GET /integration/circuit-breaker/status/ — open/closed/half-open."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .circuit_breaker import get_circuit_breaker_registry
            return _ok(get_circuit_breaker_registry().get_all_states())
        except Exception as exc:
            return _err(str(exc))


class CircuitBreakerResetView(APIView):
    """POST /integration/circuit-breaker/reset/ — force-reset a breaker."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .circuit_breaker import get_circuit_breaker_registry
            name   = request.data.get("name")
            result = get_circuit_breaker_registry().reset(name)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# MESSAGE QUEUE
# ─────────────────────────────────────────────────────────────────────────────

class MessageQueueStatsView(APIView):
    """GET /integration/queue/stats/ — queue depth + throughput."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .message_queue import get_message_queue
            return _ok(get_message_queue().get_stats())
        except Exception as exc:
            return _err(str(exc))


class MessageQueueEnqueueView(APIView):
    """POST /integration/queue/enqueue/ — manually enqueue a message."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .message_queue import get_message_queue
            msg_id = get_message_queue().enqueue(request.data)
            return _ok({"message_id": msg_id}, status.HTTP_201_CREATED)
        except Exception as exc:
            return _err(str(exc))


class MessageQueuePurgeView(APIView):
    """POST /integration/queue/purge/ — purge dead-letter queue."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .message_queue import get_message_queue
            result = get_message_queue().purge_dead_letter(request.data.get("queue_name"))
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# PERFORMANCE MONITOR
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationPerformanceView(APIView):
    """GET /integration/performance/ — latency + error-rate metrics."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .performance_monitor import IntegrationPerformanceMonitor
            return _ok(IntegrationPerformanceMonitor().get_metrics())
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# SYNC MANAGER
# ─────────────────────────────────────────────────────────────────────────────

class SyncManagerStatusView(APIView):
    """GET /integration/sync/status/ — running / paused / last-run."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .sync_manager import get_sync_manager
            return _ok(get_sync_manager().get_status())
        except Exception as exc:
            return _err(str(exc))


class SyncManagerTriggerView(APIView):
    """POST /integration/sync/trigger/ — manual sync trigger."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .sync_manager import get_sync_manager
            result = get_sync_manager().trigger_sync(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# WEBHOOKS
# ─────────────────────────────────────────────────────────────────────────────

class WebhookListView(APIView):
    """GET /integration/webhooks/ — list registered webhooks."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .webhooks_integration import get_webhook_manager
            return _ok({"webhooks": get_webhook_manager().list_webhooks()})
        except Exception as exc:
            return _err(str(exc))


class WebhookRegisterView(APIView):
    """POST /integration/webhooks/register/ — register a new webhook."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .webhooks_integration import get_webhook_manager
            result = get_webhook_manager().register(request.data)
            return _ok(result, status.HTTP_201_CREATED)
        except Exception as exc:
            return _err(str(exc))


class WebhookDeliverView(APIView):
    """POST /integration/webhooks/deliver/ — manually trigger delivery."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .webhooks_integration import get_webhook_manager
            result = get_webhook_manager().deliver(request.data)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# VERSIONING
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationVersionView(APIView):
    """GET /integration/version/ — API version + compatibility matrix."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .versioning import IntegrationVersionManager
            return _ok(IntegrationVersionManager().get_version_info())
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# AUDIT LOGS
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationAuditLogView(APIView):
    """GET /integration/audit-logs/ — paginated integration audit trail."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .integ_audit_logs import IntegrationAuditLogger
            page    = int(request.query_params.get("page", 1))
            limit   = min(int(request.query_params.get("limit", 50)), 200)
            filters = {
                "action":     request.query_params.get("action"),
                "adapter":    request.query_params.get("adapter"),
                "start_date": request.query_params.get("start_date"),
                "end_date":   request.query_params.get("end_date"),
            }
            result = IntegrationAuditLogger().query_logs(
                page=page, limit=limit,
                filters={k: v for k, v in filters.items() if v}
            )
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

class IntegrationRegistryView(APIView):
    """GET /integration/registry/ — all registered adapters + their status."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from .integ_registry import get_integration_registry
            return _ok({"adapters": get_integration_registry().list_adapters()})
        except Exception as exc:
            return _err(str(exc))


class IntegrationRegistryAdapterView(APIView):
    """GET /integration/registry/<name>/ — single adapter detail."""
    permission_classes = [IsAdminUser]

    def get(self, request, adapter_name: str):
        try:
            from .integ_registry import get_integration_registry
            adapter = get_integration_registry().get_adapter(adapter_name)
            if not adapter:
                return _err(f"Adapter '{adapter_name}' not found", status.HTTP_404_NOT_FOUND)
            return _ok(adapter)
        except Exception as exc:
            return _err(str(exc))


# ─────────────────────────────────────────────────────────────────────────────
# FALLBACK LOGIC
# ─────────────────────────────────────────────────────────────────────────────

class FallbackStatusView(APIView):
    """GET /integration/fallback/status/ — active fallback policies."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            from .fallback_logic import FallbackManager
            return _ok(FallbackManager().get_active_fallbacks())
        except Exception as exc:
            return _err(str(exc))


class FallbackTriggerView(APIView):
    """POST /integration/fallback/trigger/ — manually activate a fallback."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        try:
            from .fallback_logic import FallbackManager
            result = FallbackManager().trigger(request.data.get("policy_name"))
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))
