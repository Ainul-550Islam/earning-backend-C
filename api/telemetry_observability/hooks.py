"""
Hook system for Telemetry Observability.

Hooks are synchronous callbacks that fire BEFORE or AFTER a data operation.
They differ from events.py (which is post-fact publishing) — hooks can
mutate the context dict or veto an operation by raising an exception.

WIRING (apps.py ready()):
    from .hooks import hook_manager, HookType
    hook_manager.register(HookType.AFTER_ALERT_TRIGGER, notify_slack)

Usage inside a service/logic layer:
    from .hooks import hook_manager, HookType
    hook_manager.run(HookType.BEFORE_METRIC_RECORD, {'data': validated_data})
"""
from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hook types
# ---------------------------------------------------------------------------

class HookType(Enum):
    """All hook points in the telemetry system."""
    BEFORE_METRIC_RECORD  = 'before_metric_record'
    AFTER_METRIC_RECORD   = 'after_metric_record'
    BEFORE_LOG_RECORD     = 'before_log_record'
    AFTER_LOG_RECORD      = 'after_log_record'
    BEFORE_TRACE_START    = 'before_trace_start'
    AFTER_TRACE_START     = 'after_trace_start'
    BEFORE_TRACE_FINISH   = 'before_trace_finish'
    AFTER_TRACE_FINISH    = 'after_trace_finish'
    BEFORE_ALERT_TRIGGER  = 'before_alert_trigger'
    AFTER_ALERT_TRIGGER   = 'after_alert_trigger'
    BEFORE_HEALTH_CHECK   = 'before_health_check'
    AFTER_HEALTH_CHECK    = 'after_health_check'


# ---------------------------------------------------------------------------
# Hook
# ---------------------------------------------------------------------------

class Hook:
    """
    Single registered hook callback with metadata.
    """

    __slots__ = ('name', 'hook_type', 'callback', 'priority',
                 'enabled', 'execution_count', 'last_executed', 'last_error')

    def __init__(
        self,
        name: str,
        hook_type: HookType,
        callback: Callable[[Dict[str, Any]], None],
        priority: int = 0,
        enabled: bool = True,
    ):
        self.name            = name
        self.hook_type       = hook_type
        self.callback        = callback
        self.priority        = priority
        self.enabled         = enabled
        self.execution_count = 0
        self.last_executed:  Optional[datetime] = None
        self.last_error:     Optional[str] = None

    def execute(self, context: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            self.callback(context)
            self.execution_count += 1
            self.last_executed = datetime.utcnow()
            self.last_error    = None
        except Exception as exc:
            self.last_error = str(exc)
            raise

    def __repr__(self) -> str:
        return f'<Hook {self.name} ({self.hook_type.value}) priority={self.priority}>'


# ---------------------------------------------------------------------------
# HookManager — singleton
# ---------------------------------------------------------------------------

class HookManager:
    """
    Singleton registry for all hooks.

    Hooks for the same HookType are executed in descending priority order.
    Exceptions in a hook propagate to the caller (unlike EventBus which swallows them).
    """

    _instance: Optional['HookManager'] = None

    def __new__(cls) -> 'HookManager':
        if cls._instance is None:
            inst = super().__new__(cls)
            inst._hooks: Dict[HookType, List[Hook]] = {}
            cls._instance = inst
        return cls._instance

    # -- registration --

    def register(
        self,
        hook_type: HookType,
        callback: Callable[[Dict[str, Any]], None],
        name: Optional[str] = None,
        priority: int = 0,
        enabled: bool = True,
    ) -> Hook:
        """
        Register a callback for hook_type.

        Args:
            hook_type: When to fire the hook
            callback:  Function receiving a context dict
            name:      Human-readable name (defaults to callback.__qualname__)
            priority:  Higher = runs first
            enabled:   Can be toggled later via enable()/disable()

        Returns:
            The created Hook instance
        """
        hook = Hook(
            name      = name or callback.__qualname__,
            hook_type = hook_type,
            callback  = callback,
            priority  = priority,
            enabled   = enabled,
        )
        bucket = self._hooks.setdefault(hook_type, [])
        bucket.append(hook)
        bucket.sort(key=lambda h: h.priority, reverse=True)
        return hook

    def unregister(self, name: str, hook_type: Optional[HookType] = None) -> int:
        """
        Remove hooks by name.

        Args:
            name:      Hook name to remove
            hook_type: Limit removal to a specific type (or all types if None)

        Returns:
            Number of hooks removed
        """
        removed = 0
        types   = [hook_type] if hook_type else list(self._hooks.keys())
        for ht in types:
            before = len(self._hooks.get(ht, []))
            self._hooks[ht] = [h for h in self._hooks.get(ht, []) if h.name != name]
            removed += before - len(self._hooks[ht])
        return removed

    def enable(self, name: str) -> None:
        """Enable a hook by name."""
        for hooks in self._hooks.values():
            for h in hooks:
                if h.name == name:
                    h.enabled = True

    def disable(self, name: str) -> None:
        """Disable a hook by name (it stays registered but is skipped)."""
        for hooks in self._hooks.values():
            for h in hooks:
                if h.name == name:
                    h.enabled = False

    def reset(self) -> None:
        """Clear all registered hooks. Useful in tests."""
        self._hooks.clear()

    # -- execution --

    def run(self, hook_type: HookType, context: Dict[str, Any]) -> None:
        """
        Execute all hooks registered for hook_type in priority order.

        Raises:
            Any exception raised by a hook (propagates to caller).
        """
        for hook in self._hooks.get(hook_type, []):
            hook.execute(context)

    def run_safe(self, hook_type: HookType, context: Dict[str, Any]) -> List[str]:
        """
        Execute all hooks, catching and logging exceptions instead of raising.

        Returns:
            List of error messages from any hooks that failed.
        """
        errors: List[str] = []
        for hook in self._hooks.get(hook_type, []):
            try:
                hook.execute(context)
            except Exception as exc:  # noqa: BLE001
                msg = f'Hook {hook.name} failed: {exc}'
                logger.exception(msg)
                errors.append(msg)
        return errors

    # -- introspection --

    def list_hooks(self, hook_type: Optional[HookType] = None) -> List[Hook]:
        """Return all registered hooks, optionally filtered by type."""
        if hook_type:
            return list(self._hooks.get(hook_type, []))
        return [h for bucket in self._hooks.values() for h in bucket]

    def __repr__(self) -> str:
        total = sum(len(v) for v in self._hooks.values())
        return f'<HookManager hooks={total}>'


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

hook_manager = HookManager()
