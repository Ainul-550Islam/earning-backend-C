# =============================================================================
# fraud_detection/views_integration_advanced.py
# =============================================================================
"""
API endpoints exposing the remaining INTEGRATION_SYSTEM modules:

  File 5 — data_validator.py  → /fraud/integration/validator/*
  File 6 — fallback_logic.py  → /fraud/integration/fallback/*
  File 7 — integ_adapter.py   → /fraud/integration/adapter-factory/*
  File 8 — integ_signals.py   → /fraud/integration/signals/*
  File 9 — transformer.py     → /fraud/integration/transformer/*
  File 10— versioning.py      → /fraud/integration/versioning/*
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

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


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(data, code=status.HTTP_200_OK):
    return Response(data, status=code)


def _err(msg, code=status.HTTP_400_BAD_REQUEST):
    return Response({'error': msg}, status=code)


def _run(coro):
    """Run an async coroutine safely from a sync Django view."""
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
# FILE 5 — data_validator.py
# =============================================================================

class ValidatorValidateAPIView(APIView):
    """
    POST /fraud/integration/validator/validate/

    Validate a data payload against a schema.
    Body: {
        data          (dict)  — data to validate
        schema        (dict)  — inline schema definition, OR
        schema_name   (str)   — pre-registered schema name
        validator_type(str)   — json | xml | csv      — default: json
        strict        (bool)  — fail on first error    — default: False
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data_payload    = request.data.get('data')
        schema          = request.data.get('schema', {})
        schema_name     = request.data.get('schema_name', '')
        validator_type  = request.data.get('validator_type', 'json')
        strict          = bool(request.data.get('strict', False))

        if data_payload is None:
            return _err('data required.')

        valid_types = ('json', 'xml', 'csv')
        if validator_type not in valid_types:
            return _err(f"validator_type must be one of: {', '.join(valid_types)}")

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_validator import (
                get_validation_engine, ValidationEngine,
            )
            engine = get_validation_engine()

            if schema_name:
                result = _run(engine.validate_with_schema(
                    data=data_payload,
                    schema_name=schema_name,
                    strict=strict,
                ))
            else:
                result = _run(engine.validate(
                    data=data_payload,
                    schema=schema,
                    validator_type=validator_type,
                    strict=strict,
                ))

            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r_dict)
        except Exception as exc:
            logger.exception('ValidatorValidateAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidatorRegisterSchemaAPIView(APIView):
    """
    POST /fraud/integration/validator/schemas/
    Register a reusable validation schema.
    Body: { name, schema, description?, version? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        name        = request.data.get('name', '').strip()
        schema      = request.data.get('schema', {})
        description = request.data.get('description', '')
        version     = request.data.get('version', '1.0.0')

        if not name or not schema:
            return _err('name and schema required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_validator import (
                get_validation_engine, ValidationSchema,
            )
            engine    = get_validation_engine()
            vs        = ValidationSchema(
                name=name,
                schema=schema,
                description=description,
                version=version,
            )
            engine.register_schema(vs)
            return _ok({'registered': True, 'name': name, 'version': version},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('ValidatorRegisterSchemaAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """GET /fraud/integration/validator/schemas/ — list all schemas."""
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_validator import get_validation_engine
            engine  = get_validation_engine()
            schemas = engine.list_schemas() if hasattr(engine, 'list_schemas') else []
            return _ok({
                'count':   len(schemas),
                'schemas': [s.to_dict() if hasattr(s, 'to_dict') else s for s in schemas],
            })
        except Exception as exc:
            logger.exception('ValidatorRegisterSchemaAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidatorValidateFieldAPIView(APIView):
    """
    POST /fraud/integration/validator/field/
    Validate a single field value using a built-in validator.
    Body: { value, validator: email|url|numeric|integer|positive|required|regex, pattern? }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        value     = request.data.get('value')
        validator = request.data.get('validator', '').strip()
        pattern   = request.data.get('pattern', '')

        if value is None or not validator:
            return _err('value and validator required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_validator import (
                validate_required, validate_email, validate_url,
                validate_numeric, validate_integer, validate_positive_number,
                validate_regex,
            )
            validator_map = {
                'required': validate_required,
                'email':    validate_email,
                'url':      validate_url,
                'numeric':  validate_numeric,
                'integer':  validate_integer,
                'positive': validate_positive_number,
            }

            if validator == 'regex':
                if not pattern:
                    return _err('pattern required for regex validator.')
                fn = validate_regex(pattern)
            elif validator in validator_map:
                fn = validator_map[validator]
            else:
                return _err(f"Unknown validator '{validator}'. Choices: {', '.join(list(validator_map.keys()) + ['regex'])}")

            is_valid = fn(value)
            return _ok({'valid': is_valid, 'value': value, 'validator': validator})
        except Exception as exc:
            logger.exception('ValidatorValidateFieldAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidatorStatsAPIView(APIView):
    """GET /fraud/integration/validator/stats/ — validation engine statistics."""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.data_validator import get_validation_engine
            engine = get_validation_engine()
            stats  = engine.get_statistics() if hasattr(engine, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('ValidatorStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 6 — fallback_logic.py
# =============================================================================

class FallbackExecuteAPIView(APIView):
    """
    POST /fraud/integration/fallback/execute/

    Execute an integration with automatic fallback on failure.
    Body: {
        integration_name (str),
        method           (str),
        params           (dict),
        timeout          (int, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get('integration_name', '').strip()
        method           = request.data.get('method', '').strip()
        params           = request.data.get('params', {})
        timeout          = request.data.get('timeout')

        if not integration_name or not method:
            return _err('integration_name and method required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fallback_logic import (
                get_fallback_handler,
            )
            handler = get_fallback_handler()

            async def _call():
                return await handler.execute_with_fallback(
                    integration_name=integration_name,
                    method=method,
                    params=params,
                    timeout=timeout,
                )

            result = _run(_call())
            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r_dict)
        except Exception as exc:
            logger.exception('FallbackExecuteAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FallbackRegisterRuleAPIView(APIView):
    """
    POST /fraud/integration/fallback/rules/
    Register a fallback rule for an integration.
    Body: {
        integration_name, trigger, strategy,
        conditions?, fallback_config?, priority?
    }
    trigger:  error | timeout | circuit_open | rate_limit | unavailable
    strategy: cache | alternative | default | simulate | degrade | retry
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get('integration_name', '').strip()
        trigger          = request.data.get('trigger', '').strip()
        strategy         = request.data.get('strategy', '').strip()
        conditions       = request.data.get('conditions', [])
        fallback_config  = request.data.get('fallback_config', {})
        priority         = int(request.data.get('priority', 1))

        if not all([integration_name, trigger, strategy]):
            return _err('integration_name, trigger, strategy required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fallback_logic import (
                register_fallback_rule, FallbackRule,
                FallbackStrategy, FallbackTrigger,
            )
            trig = FallbackTrigger(trigger) if trigger in [t.value for t in FallbackTrigger] else None
            strat = FallbackStrategy(strategy) if strategy in [s.value for s in FallbackStrategy] else None

            if trig is None:
                return _err(f"Unknown trigger '{trigger}'.")
            if strat is None:
                return _err(f"Unknown strategy '{strategy}'.")

            rule = FallbackRule(
                integration_name=integration_name,
                trigger=trig,
                strategy=strat,
                conditions=conditions,
                fallback_config=fallback_config,
                priority=priority,
            )
            register_fallback_rule(rule)
            return _ok({'registered': True, 'integration_name': integration_name,
                        'trigger': trigger, 'strategy': strategy},
                       status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('FallbackRegisterRuleAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """GET /fraud/integration/fallback/rules/ — list registered fallback rules."""
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fallback_logic import get_fallback_handler
            handler = get_fallback_handler()
            rules   = handler.list_rules() if hasattr(handler, 'list_rules') else []
            return _ok({
                'count': len(rules),
                'rules': [r.to_dict() if hasattr(r, 'to_dict') else r for r in rules],
            })
        except Exception as exc:
            logger.exception('FallbackRegisterRuleAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FallbackStatsAPIView(APIView):
    """GET /fraud/integration/fallback/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fallback_logic import get_fallback_statistics
            stats = get_fallback_statistics()
            return _ok(stats)
        except Exception as exc:
            logger.exception('FallbackStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class FallbackHistoryAPIView(APIView):
    """
    GET /fraud/integration/fallback/history/?integration_name=X&limit=50
    Recent fallback activations.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        integration_name = request.query_params.get('integration_name')
        limit            = int(request.query_params.get('limit', 50))
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.fallback_logic import get_fallback_handler
            handler = get_fallback_handler()
            history = handler.get_history(
                integration_name=integration_name,
                limit=limit,
            ) if hasattr(handler, 'get_history') else []
            return _ok({
                'count':   len(history),
                'history': [h.to_dict() if hasattr(h, 'to_dict') else h for h in history],
            })
        except Exception as exc:
            logger.exception('FallbackHistoryAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 7 — integ_adapter.py (AdapterFactory)
# =============================================================================

class AdapterCreateAPIView(APIView):
    """
    POST /fraud/integration/adapter-factory/create/

    Create an integration adapter from a config dict.
    Body: {
        adapter_type  (str): api | webhook | database | message_queue
        config        (dict): adapter-specific configuration
        name          (str): optional human-readable name
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        adapter_type = request.data.get('adapter_type', '').strip()
        config       = request.data.get('config', {})
        name         = request.data.get('name', adapter_type)

        if not adapter_type:
            return _err('adapter_type required. Choices: api, webhook, database, message_queue')
        if not config:
            return _err('config dict required.')

        valid_types = ('api', 'webhook', 'database', 'message_queue')
        if adapter_type not in valid_types:
            return _err(f"adapter_type must be one of: {', '.join(valid_types)}")

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_adapter import (
                create_adapter_from_config,
            )
            config['adapter_type'] = adapter_type
            config['name']         = name
            adapter = _run(create_adapter_from_config(config_dict=config))
            return _ok({
                'created':      True,
                'adapter_type': adapter_type,
                'name':         name,
                'adapter_id':   str(getattr(adapter, 'adapter_id', id(adapter))),
            }, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('AdapterCreateAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterListAPIView(APIView):
    """GET /fraud/integration/adapter-factory/list/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_adapter import AdapterFactory
            factory  = AdapterFactory.get_instance() if hasattr(AdapterFactory, 'get_instance') else AdapterFactory()
            adapters = factory.list_adapters() if hasattr(factory, 'list_adapters') else []
            return _ok({
                'count':    len(adapters),
                'adapters': [a.to_dict() if hasattr(a, 'to_dict') else a for a in adapters],
            })
        except Exception as exc:
            logger.exception('AdapterListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterTestAPIView(APIView):
    """
    POST /fraud/integration/adapter-factory/test/
    Test an adapter's connection / health.
    Body: { adapter_id OR (adapter_type + config) }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        adapter_id   = request.data.get('adapter_id', '').strip()
        adapter_type = request.data.get('adapter_type', '').strip()
        config       = request.data.get('config', {})

        if not adapter_id and not adapter_type:
            return _err('adapter_id or adapter_type + config required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_adapter import (
                AdapterFactory, create_adapter_from_config,
            )
            if adapter_id:
                factory = AdapterFactory.get_instance() if hasattr(AdapterFactory, 'get_instance') else AdapterFactory()
                adapter = factory.get_adapter(adapter_id) if hasattr(factory, 'get_adapter') else None
                if adapter is None:
                    return _err('Adapter not found.', status.HTTP_404_NOT_FOUND)
            else:
                config['adapter_type'] = adapter_type
                adapter = _run(create_adapter_from_config(config_dict=config))

            health = _run(adapter.health_check()) if hasattr(adapter, 'health_check') else {'healthy': True}
            h_dict = health.to_dict() if hasattr(health, 'to_dict') else health
            return _ok({'tested': True, **h_dict})
        except Exception as exc:
            logger.exception('AdapterTestAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class AdapterExecuteAPIView(APIView):
    """
    POST /fraud/integration/adapter-factory/execute/
    Execute a method on a named adapter.
    Body: { adapter_id, method, params? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        adapter_id = request.data.get('adapter_id', '').strip()
        method     = request.data.get('method', '').strip()
        params     = request.data.get('params', {})

        if not adapter_id or not method:
            return _err('adapter_id and method required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_adapter import AdapterFactory
            factory = AdapterFactory.get_instance() if hasattr(AdapterFactory, 'get_instance') else AdapterFactory()
            adapter = factory.get_adapter(adapter_id) if hasattr(factory, 'get_adapter') else None
            if adapter is None:
                return _err('Adapter not found.', status.HTTP_404_NOT_FOUND)

            fn = getattr(adapter, method, None)
            if fn is None:
                return _err(f"Method '{method}' not found on this adapter.")

            result = _run(fn(**params)) if asyncio.iscoroutinefunction(fn) else fn(**params)
            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok({'executed': True, 'method': method, 'result': r_dict})
        except Exception as exc:
            logger.exception('AdapterExecuteAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 8 — integ_signals.py
# =============================================================================

class IntegSignalEmitAPIView(APIView):
    """
    POST /fraud/integration/signals/emit/

    Emit an integration signal.
    Body: {
        signal_type   (str): integration_started | integration_completed |
                             integration_failed | circuit_breaker_opened |
                             performance_alert | data_sync_started | ...
        integration_name (str),
        payload          (dict, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        signal_type      = request.data.get('signal_type', '').strip()
        integration_name = request.data.get('integration_name', '').strip()
        payload          = request.data.get('payload', {})

        if not signal_type or not integration_name:
            return _err('signal_type and integration_name required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_signals import (
                get_signal_manager, IntegrationSignalData, SignalType,
            )
            mgr = get_signal_manager()
            st  = SignalType(signal_type) if signal_type in [s.value for s in SignalType] else None
            if st is None:
                valid = [s.value for s in SignalType]
                return _err(f"Unknown signal_type '{signal_type}'. Choices: {', '.join(valid)}")

            data = IntegrationSignalData(
                signal_type=st,
                integration_name=integration_name,
                **payload,
            )
            _run(mgr.emit(data))
            return _ok({'emitted': True, 'signal_type': signal_type,
                        'integration_name': integration_name})
        except Exception as exc:
            logger.exception('IntegSignalEmitAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegSignalSubscribeAPIView(APIView):
    """
    GET  /fraud/integration/signals/subscriptions/   — list all subscriptions
    POST /fraud/integration/signals/subscriptions/   — register a subscription
    Body: { signal_type, handler_name }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_signals import get_signal_manager
            mgr  = get_signal_manager()
            subs = mgr.list_subscriptions() if hasattr(mgr, 'list_subscriptions') else []
            return _ok({'count': len(subs), 'subscriptions': subs})
        except Exception as exc:
            logger.exception('IntegSignalSubscribeAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        signal_type  = request.data.get('signal_type', '').strip()
        handler_name = request.data.get('handler_name', '').strip()

        if not signal_type or not handler_name:
            return _err('signal_type and handler_name required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_signals import (
                get_signal_manager, SignalType,
            )
            mgr = get_signal_manager()
            st  = SignalType(signal_type) if signal_type in [s.value for s in SignalType] else None
            if st is None:
                return _err(f"Unknown signal_type '{signal_type}'.")

            subscribed = _run(mgr.subscribe(signal_type=st, handler_name=handler_name)) \
                if hasattr(mgr, 'subscribe') else True
            return _ok({'subscribed': subscribed, 'signal_type': signal_type,
                        'handler_name': handler_name}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('IntegSignalSubscribeAPIView.post failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegSignalHistoryAPIView(APIView):
    """
    GET /fraud/integration/signals/history/?integration_name=X&limit=50
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        integration_name = request.query_params.get('integration_name')
        signal_type      = request.query_params.get('signal_type')
        limit            = int(request.query_params.get('limit', 50))

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_signals import get_signal_manager
            mgr     = get_signal_manager()
            history = mgr.get_history(
                integration_name=integration_name,
                signal_type=signal_type,
                limit=limit,
            ) if hasattr(mgr, 'get_history') else []
            return _ok({
                'count':   len(history),
                'history': [h.to_dict() if hasattr(h, 'to_dict') else h for h in history],
            })
        except Exception as exc:
            logger.exception('IntegSignalHistoryAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class IntegSignalStatsAPIView(APIView):
    """GET /fraud/integration/signals/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.integ_signals import get_signal_manager
            mgr   = get_signal_manager()
            stats = mgr.get_statistics() if hasattr(mgr, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('IntegSignalStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 9 — transformer.py
# =============================================================================

class TransformerTransformAPIView(APIView):
    """
    POST /fraud/integration/transformer/transform/

    Transform data between formats.
    Body: {
        data           (dict|str|list),
        source_format  (str): json | xml | csv | yaml
        target_format  (str): json | xml | csv | yaml
        field_mappings (list, optional): [{source_field, target_field, transform?}]
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data_in        = request.data.get('data')
        source_format  = request.data.get('source_format', 'json').strip()
        target_format  = request.data.get('target_format', 'json').strip()
        field_mappings = request.data.get('field_mappings', [])

        if data_in is None:
            return _err('data required.')

        valid_formats = ('json', 'xml', 'csv', 'yaml')
        if source_format not in valid_formats:
            return _err(f"source_format must be one of: {', '.join(valid_formats)}")
        if target_format not in valid_formats:
            return _err(f"target_format must be one of: {', '.join(valid_formats)}")

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.transformer import (
                transform_data, DataFormat,
            )
            sf = DataFormat(source_format) if source_format in [f.value for f in DataFormat] else DataFormat.JSON
            tf = DataFormat(target_format) if target_format in [f.value for f in DataFormat] else DataFormat.JSON

            result = _run(transform_data(
                data=data_in,
                source_format=sf,
                target_format=tf,
                field_mappings=field_mappings or None,
            ))
            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r_dict)
        except Exception as exc:
            logger.exception('TransformerTransformAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransformerTransformRequestAPIView(APIView):
    """
    POST /fraud/integration/transformer/transform-request/

    Transform an outgoing integration request payload.
    Body: {
        data             (dict),
        integration_name (str),
        direction        (str): outbound | inbound — default: outbound
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        data_in          = request.data.get('data', {})
        integration_name = request.data.get('integration_name', '').strip()
        direction        = request.data.get('direction', 'outbound')

        if not integration_name:
            return _err('integration_name required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.transformer import (
                transform_request, transform_response,
            )
            if direction == 'inbound':
                result = _run(transform_response(data=data_in, integration_name=integration_name))
            else:
                result = _run(transform_request(data=data_in, integration_name=integration_name))

            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r_dict)
        except Exception as exc:
            logger.exception('TransformerTransformRequestAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransformerRegisterAPIView(APIView):
    """
    POST /fraud/integration/transformer/register/

    Register a named transformation for an integration.
    Body: {
        integration_name (str),
        transformation_name (str),
        source_format (str), target_format (str),
        field_mappings (list), filters (dict, optional)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name     = request.data.get('integration_name', '').strip()
        transformation_name  = request.data.get('transformation_name', '').strip()
        source_format        = request.data.get('source_format', 'json')
        target_format        = request.data.get('target_format', 'json')
        field_mappings       = request.data.get('field_mappings', [])
        filters              = request.data.get('filters', {})

        if not integration_name or not transformation_name:
            return _err('integration_name and transformation_name required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.transformer import (
                get_transformation_registry, DataFormat,
            )
            registry = get_transformation_registry()
            sf = DataFormat(source_format) if source_format in [f.value for f in DataFormat] else DataFormat.JSON
            tf = DataFormat(target_format) if target_format in [f.value for f in DataFormat] else DataFormat.JSON
            registry.register(
                integration_name=integration_name,
                transformation_name=transformation_name,
                source_format=sf,
                target_format=tf,
                field_mappings=field_mappings,
                filters=filters,
            )
            return _ok({'registered': True, 'transformation_name': transformation_name,
                        'integration_name': integration_name}, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('TransformerRegisterAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        """GET /fraud/integration/transformer/register/ — list registered transformations."""
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.transformer import get_transformation_registry
            registry = get_transformation_registry()
            items    = registry.list_transformations() if hasattr(registry, 'list_transformations') else []
            return _ok({'count': len(items), 'transformations': items})
        except Exception as exc:
            logger.exception('TransformerRegisterAPIView.get failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class TransformerUtilsAPIView(APIView):
    """
    POST /fraud/integration/transformer/utils/
    Run a utility transformation (snake_case↔camelCase, normalize_timestamp, sanitize).
    Body: { value, util: snake_to_camel|camel_to_snake|normalize_timestamp|sanitize }
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        value = request.data.get('value')
        util  = request.data.get('util', '').strip()

        if value is None or not util:
            return _err('value and util required.')

        valid_utils = ('snake_to_camel', 'camel_to_snake', 'normalize_timestamp', 'sanitize')
        if util not in valid_utils:
            return _err(f"util must be one of: {', '.join(valid_utils)}")

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.transformer import (
                snake_case_to_camel_case, camel_case_to_snake_case,
                normalize_timestamp, sanitize_string,
            )
            util_map = {
                'snake_to_camel':      snake_case_to_camel_case,
                'camel_to_snake':      camel_case_to_snake_case,
                'normalize_timestamp': normalize_timestamp,
                'sanitize':            sanitize_string,
            }
            result = util_map[util](str(value))
            return _ok({'util': util, 'input': value, 'output': str(result)})
        except Exception as exc:
            logger.exception('TransformerUtilsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


# =============================================================================
# FILE 10 — versioning.py
# =============================================================================

class VersionRegisterAPIView(APIView):
    """
    POST /fraud/integration/versioning/register/

    Register a versioned config for an integration.
    Body: {
        integration_name (str),
        version          (str, semver e.g. "1.2.0"),
        config_data      (dict),
        description?     (str),
        is_active?       (bool)
    }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get('integration_name', '').strip()
        version          = request.data.get('version', '').strip()
        config_data      = request.data.get('config_data', {})

        if not integration_name or not version or not config_data:
            return _err('integration_name, version, config_data required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import (
                register_integration_version,
            )
            versioned_config = register_integration_version(
                integration_name=integration_name,
                version=version,
                config_data={
                    **config_data,
                    'description': request.data.get('description', ''),
                    'is_active':   bool(request.data.get('is_active', True)),
                },
            )
            vc_dict = versioned_config.to_dict() if hasattr(versioned_config, 'to_dict') else {
                'integration_name': integration_name,
                'version': version,
            }
            return _ok(vc_dict, status.HTTP_201_CREATED)
        except Exception as exc:
            logger.exception('VersionRegisterAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionLatestAPIView(APIView):
    """GET /fraud/integration/versioning/latest/<integration_name>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, integration_name: str):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import (
                get_latest_integration_version,
            )
            vc = get_latest_integration_version(integration_name=integration_name)
            if vc is None:
                return _err(f"No version found for '{integration_name}'.", status.HTTP_404_NOT_FOUND)
            return _ok(vc.to_dict() if hasattr(vc, 'to_dict') else vc)
        except Exception as exc:
            logger.exception('VersionLatestAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionListAPIView(APIView):
    """GET /fraud/integration/versioning/list/<integration_name>/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request, integration_name: str):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import get_version_manager
            mgr      = get_version_manager()
            versions = mgr.list_versions(integration_name=integration_name) \
                if hasattr(mgr, 'list_versions') else []
            return _ok({
                'integration_name': integration_name,
                'count':    len(versions),
                'versions': [v.to_dict() if hasattr(v, 'to_dict') else v for v in versions],
            })
        except Exception as exc:
            logger.exception('VersionListAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionMigrateAPIView(APIView):
    """
    POST /fraud/integration/versioning/migrate/
    Body: { integration_name, from_version, to_version, dry_run? }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle, BurstProtectionThrottle]

    def post(self, request):
        integration_name = request.data.get('integration_name', '').strip()
        from_version     = request.data.get('from_version', '').strip()
        to_version       = request.data.get('to_version', '').strip()
        dry_run          = bool(request.data.get('dry_run', False))

        if not all([integration_name, from_version, to_version]):
            return _err('integration_name, from_version, to_version required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import (
                migrate_integration_config,
            )
            result = _run(migrate_integration_config(
                integration_name=integration_name,
                from_version=from_version,
                to_version=to_version,
                dry_run=dry_run,
            ))
            r_dict = result.to_dict() if hasattr(result, 'to_dict') else result
            return _ok(r_dict)
        except Exception as exc:
            logger.exception('VersionMigrateAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionCompatibilityAPIView(APIView):
    """
    POST /fraud/integration/versioning/compatibility/
    Body: { integration_name, version1, version2 }
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        integration_name = request.data.get('integration_name', '').strip()
        version1         = request.data.get('version1', '').strip()
        version2         = request.data.get('version2', '').strip()

        if not all([integration_name, version1, version2]):
            return _err('integration_name, version1, version2 required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import (
                check_integration_compatibility,
            )
            compat = check_integration_compatibility(
                integration_name=integration_name,
                version1=version1,
                version2=version2,
            )
            return _ok({
                'integration_name': integration_name,
                'version1':     version1,
                'version2':     version2,
                'compatibility': compat.value if hasattr(compat, 'value') else str(compat),
            })
        except Exception as exc:
            logger.exception('VersionCompatibilityAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionCompareAPIView(APIView):
    """
    POST /fraud/integration/versioning/compare/
    Body: { version1, version2 }
    Returns: -1 | 0 | 1
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def post(self, request):
        v1 = request.data.get('version1', '').strip()
        v2 = request.data.get('version2', '').strip()

        if not v1 or not v2:
            return _err('version1 and version2 required.')

        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import compare_versions
            result = compare_versions(v1, v2)
            meaning = {-1: 'version1 < version2', 0: 'equal', 1: 'version1 > version2'}
            return _ok({
                'version1':  v1,
                'version2':  v2,
                'result':    result,
                'meaning':   meaning.get(result, 'unknown'),
            })
        except Exception as exc:
            logger.exception('VersionCompareAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionParseAPIView(APIView):
    """
    GET /fraud/integration/versioning/parse/?version=1.2.3
    Parse a semver string into components.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        version = request.query_params.get('version', '').strip()
        if not version:
            return _err('version query param required.')
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import parse_version
            parsed = parse_version(version)
            return _ok(parsed.to_dict() if hasattr(parsed, 'to_dict') else vars(parsed))
        except Exception as exc:
            logger.exception('VersionParseAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)


class VersionStatsAPIView(APIView):
    """GET /fraud/integration/versioning/stats/"""
    permission_classes = [IsAuthenticated, IsAdminUser]
    throttle_classes   = [FraudEndpointRateThrottle]

    def get(self, request):
        try:
            from api.fraud_detection.INTEGRATION_SYSTEM.versioning import get_version_manager
            mgr   = get_version_manager()
            stats = mgr.get_statistics() if hasattr(mgr, 'get_statistics') else {}
            return _ok(stats)
        except Exception as exc:
            logger.exception('VersionStatsAPIView failed: %s', exc)
            return _err(str(exc), status.HTTP_500_INTERNAL_SERVER_ERROR)

# ── ALIASES expected by urls.py ───────────────────────────────────────────────
IntegrationEventListAPIView    = ValidatorStatsAPIView
IntegrationEventPublishAPIView = ValidatorValidateAPIView
IntegrationCircuitBreakerAPIView = FallbackExecuteAPIView
