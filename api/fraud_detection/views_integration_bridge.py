# =============================================================================
# fraud_detection/views_integration_bridge.py
# =============================================================================
"""
API endpoints exposing INTEGRATION_SYSTEM bridge modules:

  File 2 — auth_bridge.py:
      AuthBridge, JWTAuthProvider, APIKeyAuthProvider
      → /fraud/integration/auth-bridge/*

  File 3 — bridge.py:
      BridgeSystem, BridgeRouter, HTTP/WebSocket/MQ bridge handlers
      → /fraud/integration/bridge/*

  File 4 — data_bridge.py:
      DataBridge, DatabaseConnector, APIConnector, FileConnector
      → /fraud/integration/data-bridge/*
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.fraud_detection.missing_components import (
    BurstProtectionThrottle,
    FraudEndpointRateThrottle,
)

logger = logging.getLogger(__name__)


def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result(timeout=30)
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# =============================================================================
# FILE 2 — auth_bridge.py
# =============================================================================

class AuthBridgeValidateTokenAPIView(APIView):
    """
    POST /fraud/integration/auth-bridge/validate-token/

    Validate an integration token using AuthBridge.
    Body: { token, token_type?, required_scopes? }
    token_type: jwt | api_key | service_account  — default: jwt
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        token        = request.data.get('token', '').strip()
        token_type   = request.data.get('token_type', 'jwt')
        required_scopes = request.data.get('required_scopes', [])

        if not token:
            return _err('token required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import (
                get_auth_bridge, TokenType,
            )
            bridge = get_auth_bridge()
            tt     = TokenType(token_type) if token_type in [t.value for t in TokenType] else TokenType.JWT
            result = _run_async(bridge.validate_token(token=token, token_type=tt))
            info = result.to_dict() if hasattr(result, 'to_dict') else vars(result) if hasattr(result, '__dict__') else result
            return _ok({'valid': True, 'token_info': info})
        except Exception as exc:
            logger.exception('AuthBridgeValidateTokenAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthBridgeCheckPermissionAPIView(APIView):
    """
    POST /fraud/integration/auth-bridge/check-permission/

    Check whether a token has permission for a resource + action.
    Body: { token, resource, action, token_type? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        token    = request.data.get('token', '').strip()
        resource = request.data.get('resource', '').strip()
        action   = request.data.get('action', 'read').strip()

        if not token or not resource:
            return _err('token and resource required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import (
                check_integration_permission, TokenType,
            )
            token_type_str = request.data.get('token_type', 'jwt')
            tt = TokenType(token_type_str) if token_type_str in [t.value for t in TokenType] else TokenType.JWT
            allowed = _run_async(check_integration_permission(
                token=token, token_type=tt,
                resource=resource, action=action,
            ))
            return _ok({'allowed': allowed, 'resource': resource, 'action': action})
        except Exception as exc:
            logger.exception('AuthBridgeCheckPermissionAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthBridgeGenerateTokenAPIView(APIView):
    """
    POST /fraud/integration/auth-bridge/generate-token/

    Generate an integration API key or service account token.
    Body: { integration_name, token_type?, scopes?, expires_in_hours? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get('integration_name', '').strip()
        token_type       = request.data.get('token_type', 'api_key')
        scopes           = request.data.get('scopes', [])
        expires_in_hours = int(request.data.get('expires_in_hours', 24))

        if not integration_name:
            return _err('integration_name required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import get_auth_bridge
            bridge = get_auth_bridge()
            token  = _run_async(bridge.generate_token(
                integration_name=integration_name,
                token_type=token_type,
                scopes=scopes,
                expires_in_hours=expires_in_hours,
            ))
            return _ok({'token': token, 'expires_in_hours': expires_in_hours},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('AuthBridgeGenerateTokenAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthBridgeRevokeTokenAPIView(APIView):
    """
    POST /fraud/integration/auth-bridge/revoke-token/
    Body: { token }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        token = request.data.get('token', '').strip()
        if not token:
            return _err('token required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import get_auth_bridge
            bridge  = get_auth_bridge()
            revoked = _run_async(bridge.revoke_token(token=token))
            return _ok({'revoked': revoked})
        except Exception as exc:
            logger.exception('AuthBridgeRevokeTokenAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthBridgeListTokensAPIView(APIView):
    """
    GET /fraud/integration/auth-bridge/tokens/?integration_name=X
    List active integration tokens.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        integration_name = request.query_params.get('integration_name')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import get_auth_bridge
            bridge = get_auth_bridge()
            tokens = _run_async(bridge.list_tokens(integration_name=integration_name))
            safe_tokens = [
                t.to_dict() if hasattr(t, 'to_dict') else t
                for t in (tokens or [])
            ]
            return _ok({'count': len(safe_tokens), 'tokens': safe_tokens})
        except Exception as exc:
            logger.exception('AuthBridgeListTokensAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuthBridgeStatsAPIView(APIView):
    """GET /fraud/integration/auth-bridge/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.auth_bridge import get_auth_bridge
            bridge = get_auth_bridge()
            stats  = _run_async(bridge.get_statistics()) if hasattr(bridge, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('AuthBridgeStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 3 — bridge.py (BridgeSystem)
# =============================================================================

class BridgeSendMessageAPIView(APIView):
    """
    POST /fraud/integration/bridge/send/

    Send a message from one module to another via the BridgeSystem.
    Body: {
        source_module, target_module, message_type,
        payload, protocol?  (http|websocket|message_queue)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        source_module = request.data.get('source_module', '').strip()
        target_module = request.data.get('target_module', '').strip()
        message_type  = request.data.get('message_type', '').strip()
        payload       = request.data.get('payload', {})
        protocol      = request.data.get('protocol', 'http')

        if not source_module or not target_module or not message_type:
            return _err('source_module, target_module, message_type required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import (
                send_bridge_message, BridgeProtocol,
            )
            bp = BridgeProtocol(protocol) if protocol in [p.value for p in BridgeProtocol] else BridgeProtocol.HTTP
            result = _run_async(send_bridge_message(
                source_module=source_module,
                target_module=target_module,
                message_type=message_type,
                payload=payload,
                protocol=bp,
            ))
            return _ok(result.to_dict() if hasattr(result, 'to_dict') else result,
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('BridgeSendMessageAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BridgeEstablishConnectionAPIView(APIView):
    """
    POST /fraud/integration/bridge/connect/
    Body: { module_name, protocol?, config? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        module_name = request.data.get('module_name', '').strip()
        protocol    = request.data.get('protocol', 'http')
        config      = request.data.get('config', {})
        if not module_name:
            return _err('module_name required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import (
                establish_bridge_connection, BridgeProtocol,
            )
            bp     = BridgeProtocol(protocol) if protocol in [p.value for p in BridgeProtocol] else BridgeProtocol.HTTP
            conn   = _run_async(establish_bridge_connection(module_name=module_name, protocol=bp, config=config))
            result = conn.to_dict() if hasattr(conn, 'to_dict') else {'connection_id': str(conn)} if conn else {}
            return _ok({'connected': True, **result}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('BridgeEstablishConnectionAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BridgeRoutesAPIView(APIView):
    """GET /fraud/integration/bridge/routes/ — list all registered bridge routes"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import get_bridge_system
            bridge  = get_bridge_system()
            routes  = bridge.get_routes() if hasattr(bridge, 'get_routes') else []
            return _ok({
                'count':  len(routes),
                'routes': [r.to_dict() if hasattr(r, 'to_dict') else r for r in routes],
            })
        except Exception as exc:
            logger.exception('BridgeRoutesAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BridgeConnectionsAPIView(APIView):
    """GET /fraud/integration/bridge/connections/ — list active connections"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import get_bridge_system
            bridge      = get_bridge_system()
            connections = bridge.get_connections() if hasattr(bridge, 'get_connections') else []
            return _ok({
                'count':       len(connections),
                'connections': [c.to_dict() if hasattr(c, 'to_dict') else c for c in connections],
            })
        except Exception as exc:
            logger.exception('BridgeConnectionsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BridgeStatsAPIView(APIView):
    """GET /fraud/integration/bridge/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import get_bridge_system
            bridge = get_bridge_system()
            stats  = _run_async(bridge.get_statistics()) if hasattr(bridge, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('BridgeStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class BridgeDisconnectAPIView(APIView):
    """
    POST /fraud/integration/bridge/disconnect/
    Body: { module_name }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        module_name = request.data.get('module_name', '').strip()
        if not module_name:
            return _err('module_name required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.bridge import get_bridge_system
            bridge  = get_bridge_system()
            success = _run_async(bridge.disconnect(module_name=module_name)) if hasattr(bridge, 'disconnect') else True
            return _ok({'disconnected': success, 'module': module_name})
        except Exception as exc:
            logger.exception('BridgeDisconnectAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 4 — data_bridge.py (DataBridge)
# =============================================================================

class DataBridgeRegisterAPIView(APIView):
    """
    POST /fraud/integration/data-bridge/register/

    Register a new data bridge (source → target sync config).
    Body: {
        name, source: {type, connection_string, ...},
        target: {type, connection_string, ...},
        sync_mode?,  field_mappings?, filters?
    }
    sync_mode: full | incremental | realtime — default: incremental
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        name    = request.data.get('name', '').strip()
        source  = request.data.get('source', {})
        target  = request.data.get('target', {})
        if not name or not source or not target:
            return _err('name, source, target required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import (
                register_data_bridge, DataSource, SyncMode,
            )
            sync_mode_str = request.data.get('sync_mode', 'incremental')
            sync_mode = SyncMode(sync_mode_str) if sync_mode_str in [s.value for s in SyncMode] else SyncMode.INCREMENTAL
            src_obj = DataSource(**source)
            tgt_obj = DataSource(**target)
            bridge  = register_data_bridge(
                name=name,
                source=src_obj,
                target=tgt_obj,
                sync_mode=sync_mode,
                field_mappings=request.data.get('field_mappings', []),
                filters=request.data.get('filters', {}),
            )
            return _ok({'registered': True, 'bridge_id': str(bridge.bridge_id) if hasattr(bridge, 'bridge_id') else name},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('DataBridgeRegisterAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeSyncAPIView(APIView):
    """
    POST /fraud/integration/data-bridge/sync/
    Body: { bridge_id, query? }
    Trigger a data sync operation.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        bridge_id = request.data.get('bridge_id', '').strip()
        query     = request.data.get('query')
        if not bridge_id:
            return _err('bridge_id required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import sync_bridge_data
            result = _run_async(sync_bridge_data(bridge_id=bridge_id, query=query))
            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r_dict)
        except Exception as exc:
            logger.exception('DataBridgeSyncAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeListAPIView(APIView):
    """GET /fraud/integration/data-bridge/list/ — list registered data bridges"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import get_data_bridge
            db     = get_data_bridge()
            bridges = db.list_bridges() if hasattr(db, 'list_bridges') else []
            return _ok({
                'count':   len(bridges),
                'bridges': [b.to_dict() if hasattr(b, 'to_dict') else b for b in bridges],
            })
        except Exception as exc:
            logger.exception('DataBridgeListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeStatusAPIView(APIView):
    """GET /fraud/integration/data-bridge/status/<bridge_id>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, bridge_id: str):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import get_data_bridge
            db     = get_data_bridge()
            status = db.get_bridge_status(bridge_id=bridge_id) if hasattr(db, 'get_bridge_status') else {}
            if not status:
                return _err('Bridge not found.', status_code=404)
            return _ok(status)
        except Exception as exc:
            logger.exception('DataBridgeStatusAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeStatsAPIView(APIView):
    """GET /fraud/integration/data-bridge/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import get_data_bridge
            db    = get_data_bridge()
            stats = _run_async(db.get_statistics()) if hasattr(db, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('DataBridgeStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeConflictsAPIView(APIView):
    """
    GET  /fraud/integration/data-bridge/conflicts/            — list unresolved conflicts
    POST /fraud/integration/data-bridge/conflicts/<id>/resolve/ — resolve a conflict
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import get_data_bridge
            db        = get_data_bridge()
            conflicts = _run_async(db.get_conflicts()) if hasattr(db, 'get_conflicts') else []
            return _ok({
                'count':     len(conflicts),
                'conflicts': [c.to_dict() if hasattr(c, 'to_dict') else c for c in conflicts],
            })
        except Exception as exc:
            logger.exception('DataBridgeConflictsAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class DataBridgeResolveConflictAPIView(APIView):
    """
    POST /fraud/integration/data-bridge/conflicts/<conflict_id>/resolve/
    Body: { resolution_strategy: source_wins|target_wins|merge|manual, merged_data? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request, conflict_id: str):
        strategy    = request.data.get('resolution_strategy', 'source_wins')
        merged_data = request.data.get('merged_data')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_bridge import (
                get_data_bridge, DataConflictResolution,
            )
            db  = get_data_bridge()
            res = DataConflictResolution(strategy) if strategy in [r.value for r in DataConflictResolution] else DataConflictResolution.SOURCE_WINS
            ok  = _run_async(db.resolve_conflict(
                conflict_id=conflict_id,
                resolution=res,
                merged_data=merged_data,
            )) if hasattr(db, 'resolve_conflict') else True
            return _ok({'resolved': ok, 'conflict_id': conflict_id, 'strategy': strategy})
        except Exception as exc:
            logger.exception('DataBridgeResolveConflictAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
IntegrationBridgeStatusAPIView = BridgeEstablishConnectionAPIView
IntegrationBridgeSyncAPIView   = BridgeSendMessageAPIView

from rest_framework.views import APIView as _BV
from rest_framework.response import Response as _BR
from rest_framework.permissions import IsAuthenticated as _BA

class IntegrationBridgeHealthAPIView(_BV):
    permission_classes = [_BA]
    def get(self, request):
        from api.fraud_detection.INTEGRATION_SYSTEM.health_check import IntegrationHealthChecker
        return _BR({"success": True, "data": IntegrationHealthChecker().run_all_checks()})
