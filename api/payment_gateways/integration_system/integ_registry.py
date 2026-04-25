# api/payment_gateways/integration_system/integ_registry.py
# Central registry of all integrations — which modules handle which events

from typing import Callable, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Central registry that maps events to handler functions.

    All integration modules register themselves here.
    When an event fires, the registry calls all registered handlers.

    Usage:
        registry = IntegrationRegistry.get_instance()
        registry.register('deposit.completed', WalletAdapter().credit_deposit)
        registry.emit('deposit.completed', user=user, amount=amount, ...)
    """
    _instance = None
    _handlers: Dict[str, List[dict]] = {}

    @classmethod
    def get_instance(cls) -> 'IntegrationRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, event: str, handler: Callable,
                  module: str = '', priority: int = 2,
                  is_async: bool = False):
        """
        Register a handler for an event.

        Args:
            event:    Event name (e.g. 'deposit.completed')
            handler:  Callable to invoke
            module:   Module name for logging/debugging
            priority: 0=critical, 1=high, 2=normal, 3=low, 4=async
            is_async: Run in background thread/Celery task
        """
        if event not in self._handlers:
            self._handlers[event] = []

        entry = {
            'handler':  handler,
            'module':   module,
            'priority': priority,
            'is_async': is_async,
        }

        # Insert in priority order
        inserted = False
        for i, h in enumerate(self._handlers[event]):
            if priority < h['priority']:
                self._handlers[event].insert(i, entry)
                inserted = True
                break
        if not inserted:
            self._handlers[event].append(entry)

        logger.debug(f'Registered handler: {event} → {module or handler.__name__}')

    def emit(self, event: str, **kwargs) -> List[dict]:
        """
        Fire an event and call all registered handlers.

        Args:
            event:  Event name
            **kwargs: Data passed to each handler

        Returns:
            list: Results from each handler
        """
        handlers = self._handlers.get(event, [])
        if not handlers:
            logger.debug(f'No handlers for event: {event}')
            return []

        results = []
        for entry in handlers:
            handler  = entry['handler']
            module   = entry['module']
            is_async = entry['is_async']

            try:
                if is_async:
                    self._run_async(handler, kwargs)
                    results.append({'module': module, 'status': 'queued'})
                else:
                    result = handler(**kwargs)
                    results.append({'module': module, 'status': 'success', 'result': result})
                    logger.debug(f'Event {event} handled by {module}: success')
            except Exception as e:
                results.append({'module': module, 'status': 'failed', 'error': str(e)})
                logger.error(f'Event {event} handler {module} failed: {e}')
                # Continue to next handler — don't abort chain

        return results

    def emit_critical(self, event: str, **kwargs):
        """Emit event and raise if any CRITICAL handler fails."""
        results = self.emit(event, **kwargs)
        failures = [r for r in results if r['status'] == 'failed']
        if failures:
            failed_modules = [f['module'] for f in failures]
            raise RuntimeError(
                f'Critical event {event} failed in: {", ".join(failed_modules)}'
            )
        return results

    def get_handlers(self, event: str) -> list:
        """Get all registered handlers for an event."""
        return self._handlers.get(event, [])

    def list_events(self) -> list:
        """List all registered events."""
        return list(self._handlers.keys())

    def unregister(self, event: str, module: str):
        """Remove a handler by module name."""
        if event in self._handlers:
            self._handlers[event] = [
                h for h in self._handlers[event] if h['module'] != module
            ]

    def reset(self):
        """Clear all handlers (for testing)."""
        self._handlers = {}

    def _run_async(self, handler: Callable, kwargs: dict):
        """Run handler asynchronously via threading."""
        import threading
        thread = threading.Thread(
            target=self._safe_call,
            args=(handler, kwargs),
            daemon=True
        )
        thread.start()

    def _safe_call(self, handler: Callable, kwargs: dict):
        try:
            handler(**kwargs)
        except Exception as e:
            logger.error(f'Async handler failed: {handler.__name__}: {e}')


# Global singleton
registry = IntegrationRegistry.get_instance()
