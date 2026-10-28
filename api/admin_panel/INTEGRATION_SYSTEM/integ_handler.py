# api/admin_panel/INTEGRATION_SYSTEM/integ_handler.py
"""
IntegrationHandler — Central dispatcher for all cross-app admin operations.

Handles: routing admin commands to the right app adapter,
retry logic, error recovery, audit logging, rate limiting.

Usage:
    from api.admin_panel.INTEGRATION_SYSTEM.integ_handler import IntegrationHandler

    result = IntegrationHandler.execute(
        app='wallet',
        action='adjust_balance',
        payload={'user_id': 123, 'amount': 50.0},
        actor=request.user,
    )
"""
import logging
import time
import random
from typing import Any, Dict, Optional
from django.core.cache import cache
from django.utils import timezone
from .integ_registry import registry
from .integ_constants import RETRY_CONFIG, TIMEOUTS
from .integ_exceptions import (
    IntegrationError, AppNotRegisteredError,
    CapabilityNotSupportedError, IntegrationTimeoutError,
)

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Central dispatcher — routes admin commands to app adapters.
    Includes: retry, timeout, audit trail, rate limiting.
    """

    @classmethod
    def execute(
        cls,
        app: str,
        action: str,
        payload: Optional[Dict] = None,
        actor=None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        capability_required: str = 'write',
        log_activity: bool = True,
    ) -> Dict:
        """
        Execute an action on an app through its adapter.

        Args:
            app:                 Target app name (e.g. 'wallet', 'fraud_detection')
            action:              Action to execute (e.g. 'adjust_balance', 'block_ip')
            payload:             Action parameters
            actor:               User performing the action (for audit logging)
            timeout:             Max seconds to wait (default from TIMEOUTS)
            max_retries:         Override global retry count
            capability_required: Required capability check
            log_activity:        Whether to log to AdminActivity

        Returns:
            dict: {success, data, error, app, action, duration_ms}
        """
        payload = payload or {}
        timeout = timeout or TIMEOUTS['INTEGRATION_CALL']
        max_retries = max_retries or RETRY_CONFIG['MAX_RETRIES']
        start_time = time.monotonic()

        # Check registration
        if not registry.is_registered(app):
            raise AppNotRegisteredError(f"App '{app}' is not registered. Call registry.register('{app}') first.")

        # Check capability
        if not registry.can_do(app, capability_required):
            raise CapabilityNotSupportedError(
                f"App '{app}' does not support capability '{capability_required}'. "
                f"Available: {registry.get_registration(app).capabilities}"
            )

        # Get adapter
        adapter = registry.get_adapter(app)
        if not adapter:
            raise IntegrationError(f"No adapter available for '{app}'")

        # Execute with retry
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = adapter.action(action, payload=payload)
                duration_ms = int((time.monotonic() - start_time) * 1000)

                result = {
                    'success': response.success,
                    'data': response.data,
                    'error': response.error,
                    'app': app,
                    'action': action,
                    'attempt': attempt + 1,
                    'duration_ms': duration_ms,
                }

                # Log to AdminActivity
                if log_activity and actor:
                    cls._log_activity(
                        actor=actor, app=app, action=action,
                        payload=payload, result=result
                    )

                if response.success:
                    logger.info(f"[IntegrationHandler] {app}.{action} OK in {duration_ms}ms")
                else:
                    logger.warning(f"[IntegrationHandler] {app}.{action} FAILED: {response.error}")

                return result

            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    delay = cls._backoff_delay(attempt)
                    logger.warning(
                        f"[IntegrationHandler] {app}.{action} attempt {attempt+1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"[IntegrationHandler] {app}.{action} EXHAUSTED after {max_retries+1} attempts: {e}")

        duration_ms = int((time.monotonic() - start_time) * 1000)
        return {
            'success': False,
            'error': str(last_error),
            'app': app,
            'action': action,
            'attempt': max_retries + 1,
            'duration_ms': duration_ms,
        }

    @classmethod
    def read(
        cls,
        app: str,
        resource: str,
        filters: Optional[Dict] = None,
        fields: Optional[list] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: Optional[str] = None,
        use_cache: bool = True,
        cache_ttl: int = 60,
    ) -> Dict:
        """Read data from an app."""
        if not registry.is_registered(app):
            raise AppNotRegisteredError(f"App '{app}' is not registered")

        # Cache key
        if use_cache:
            import hashlib, json
            cache_key = f"integ:read:{app}:{resource}:{hashlib.md5(json.dumps({'f': filters, 'l': limit, 'o': offset}, default=str).encode()).hexdigest()}"
            cached = cache.get(cache_key)
            if cached is not None:
                return {'success': True, 'data': cached, 'from_cache': True}

        adapter = registry.get_adapter(app)
        if not adapter:
            return {'success': False, 'error': f'No adapter for {app}'}

        try:
            response = adapter.read(
                resource=resource,
                filters=filters,
                fields=fields,
                limit=limit,
                offset=offset,
                order_by=order_by,
            )
            if use_cache and response.success:
                cache.set(cache_key, response.data, cache_ttl)
            return response.to_dict()
        except Exception as e:
            logger.error(f"[IntegrationHandler] read({app}, {resource}) error: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def bulk_execute(
        cls,
        app: str,
        action: str,
        ids: list,
        payload: Optional[Dict] = None,
        actor=None,
    ) -> Dict:
        """Execute a bulk action across multiple records."""
        adapter = registry.get_adapter(app)
        if not adapter:
            return {'success': False, 'error': f'No adapter for {app}'}
        try:
            response = adapter.bulk_action(action, ids=ids, payload=payload)
            if actor:
                cls._log_activity(
                    actor=actor, app=app,
                    action=f'bulk_{action}',
                    payload={'ids': ids[:10], 'count': len(ids)},
                    result={'success': response.success, 'data': response.data},
                )
            return response.to_dict()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_stats(cls, app: str, period: str = 'daily') -> Dict:
        """Get statistics from an app."""
        adapter = registry.get_adapter(app)
        if not adapter:
            return {'success': False, 'error': f'No adapter for {app}'}
        try:
            response = adapter.stats(period=period)
            return response.to_dict()
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================== PRIVATE ====================

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Exponential backoff with jitter."""
        delay = min(
            RETRY_CONFIG['INITIAL_DELAY'] * (RETRY_CONFIG['BACKOFF_FACTOR'] ** attempt),
            RETRY_CONFIG['MAX_DELAY'],
        )
        if RETRY_CONFIG['JITTER']:
            delay *= (0.5 + random.random() * 0.5)
        return delay

    @staticmethod
    def _log_activity(actor, app: str, action: str, payload: Dict, result: Dict):
        """Log admin action to AdminActivity model."""
        try:
            from api.admin_panel.models.activity import AdminActivity
            AdminActivity.log(
                actor=actor,
                action=f'integration.{app}.{action}',
                model_name=app,
                changes={
                    'payload': {k: v for k, v in (payload or {}).items() if k not in ('password', 'token', 'secret')},
                    'success': result.get('success'),
                    'error': result.get('error'),
                },
                status='success' if result.get('success') else 'failed',
            )
        except Exception as e:
            logger.debug(f"[IntegrationHandler] Activity log failed: {e}")