# integration_system/integ_handler.py
"""
Integration Handler — Master request dispatcher for all cross-module operations.

The IntegrationHandler is the single entry point for any module that needs to
interact with another module. Instead of direct imports between apps, all
cross-module calls go through this handler.

Usage:
    from .integ_handler import handler

    # Trigger a notification from wallet module
    handler.trigger('notifications', {
        'user_id': 1, 'notification_type': 'wallet_credited',
        'title': 'Wallet Credited!', 'message': '৳500 added.',
    })

    # Credit wallet from task module
    handler.trigger('wallet', {
        'user_id': 1, 'amount': 100, 'transaction_type': 'task_reward',
    })
"""

import logging
from typing import Any, Dict, List, Optional

from .integ_constants import IntegStatus, IntegPriority
from .integ_registry import registry
from .integ_exceptions import (
    IntegrationNotRegistered, IntegrationDisabled,
    IntegrationTimeout, FallbackFailed,
)
from .event_bus import event_bus, Events

logger = logging.getLogger(__name__)


class IntegrationHandler:
    """
    Master handler: routes integration requests to the correct adapter,
    handles fallback, publishes lifecycle events, and logs everything.
    """

    def trigger(
        self,
        integration_name: str,
        payload: Dict,
        priority: int = IntegPriority.MEDIUM,
        async_fallback: bool = False,
        raise_on_error: bool = False,
    ) -> Dict:
        """
        Trigger an integration operation.

        Args:
            integration_name: Name of the registered integration.
            payload:          Data dict passed to the adapter.send().
            priority:         Operation priority (affects queue selection).
            async_fallback:   If sync fails, queue for async retry.
            raise_on_error:   If True, raise exceptions instead of returning error dict.

        Returns:
            Dict with 'success', 'status', 'data', 'error'.
        """
        try:
            adapter = registry.get(integration_name)
        except IntegrationNotRegistered as exc:
            logger.error(f'Handler: integration "{integration_name}" not registered')
            if raise_on_error:
                raise
            return self._error_response(str(exc), integration_name)
        except IntegrationDisabled as exc:
            logger.info(f'Handler: integration "{integration_name}" is disabled — skipped')
            return {'success': True, 'status': IntegStatus.SKIPPED, 'data': {}, 'error': ''}

        try:
            result = adapter.send(payload, priority=priority)
            if result.get('success'):
                registry.on_success(integration_name)
                event_bus.publish(
                    event_type=f'integration.{integration_name}.success',
                    data={'integration': integration_name, 'result': result},
                    source_module='integration_handler',
                    async_dispatch=True,
                )
            else:
                registry.on_error(integration_name, result.get('error', ''))
                if async_fallback and not result.get('success'):
                    self._queue_for_retry(integration_name, payload, priority)
            return result

        except Exception as exc:
            registry.on_error(integration_name, str(exc))
            logger.error(f'Handler.trigger "{integration_name}": {exc}')

            if async_fallback:
                self._queue_for_retry(integration_name, payload, priority)
                return {'success': False, 'status': IntegStatus.RETRYING,
                        'data': {}, 'error': str(exc)}

            if raise_on_error:
                raise
            return self._error_response(str(exc), integration_name)

    def trigger_bulk(
        self,
        operations: List[Dict],
        stop_on_error: bool = False,
    ) -> List[Dict]:
        """
        Trigger multiple integration operations.

        Each operation dict: {'integration': str, 'payload': dict, ...}

        Returns list of results in same order as operations.
        """
        results = []
        for op in operations:
            name = op.get('integration', '')
            payload = op.get('payload', {})
            priority = op.get('priority', IntegPriority.MEDIUM)

            result = self.trigger(name, payload, priority=priority)
            results.append({**result, 'integration': name})

            if stop_on_error and not result.get('success'):
                logger.warning(f'Handler.trigger_bulk: stopping after error in "{name}"')
                break

        return results

    def notify_user(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        channel: str = 'in_app',
        priority: str = 'medium',
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """
        Convenience method: trigger a notification for a user.
        Used by all modules (wallet, tasks, referrals, etc.).
        """
        return self.trigger('notifications', {
            'user_id': user_id,
            'notification_type': notification_type,
            'title': title,
            'message': message,
            'channel': channel,
            'priority': priority,
            'metadata': metadata or {},
        })

    def credit_wallet(
        self,
        user_id: int,
        amount,
        transaction_type: str,
        description: str = '',
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Convenience method: credit a user's wallet."""
        return self.trigger('wallet', {
            'user_id': user_id,
            'amount': amount,
            'transaction_type': transaction_type,
            'description': description,
            'metadata': metadata or {},
        })

    def publish_event(
        self,
        event_type,
        data: Optional[Dict] = None,
        user_id: Optional[int] = None,
        source_module: str = '',
        priority: int = IntegPriority.MEDIUM,
    ) -> str:
        """Convenience method: publish an event on the event bus."""
        return event_bus.publish(
            event_type=event_type,
            data=data,
            user_id=user_id,
            source_module=source_module,
            priority=priority,
        )

    def _queue_for_retry(self, integration_name: str, payload: Dict, priority: int):
        """Queue a failed operation for async retry via Celery."""
        try:
            from .tasks import retry_integration_task
            retry_integration_task.apply_async(
                args=[integration_name, payload],
                countdown=60,
                max_retries=3,
            )
            logger.info(f'Handler: queued "{integration_name}" for retry')
        except Exception as exc:
            logger.error(f'Handler: failed to queue retry for "{integration_name}": {exc}')

    @staticmethod
    def _error_response(error: str, integration: str = '') -> Dict:
        return {
            'success': False,
            'status': IntegStatus.FAILED,
            'data': {},
            'error': error,
            'integration': integration,
        }


# Singleton
handler = IntegrationHandler()
