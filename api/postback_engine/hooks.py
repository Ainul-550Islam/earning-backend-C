"""
hooks.py
─────────
Lifecycle hooks for Postback Engine processing pipeline.
Hooks allow external code to inject custom logic at specific pipeline stages
without modifying the core handler code.

Hook points:
  PRE_VALIDATE     → Before signature/IP validation
  POST_VALIDATE    → After validation passes
  PRE_DEDUP        → Before deduplication check
  PRE_REWARD       → Before wallet credit
  POST_REWARD      → After successful wallet credit
  ON_REJECTION     → When postback is rejected
  ON_FRAUD         → When fraud is detected
  ON_CONVERSION    → When conversion is created

Usage:
    from api.postback_engine.hooks import hook_registry

    @hook_registry.register("POST_REWARD")
    def my_custom_hook(context):
        # Send notification to user
        send_push_notification(context.user, f"You earned {context.points} points!")
"""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

# Hook point identifiers
PRE_VALIDATE  = "PRE_VALIDATE"
POST_VALIDATE = "POST_VALIDATE"
PRE_DEDUP     = "PRE_DEDUP"
PRE_REWARD    = "PRE_REWARD"
POST_REWARD   = "POST_REWARD"
ON_REJECTION  = "ON_REJECTION"
ON_FRAUD      = "ON_FRAUD"
ON_CONVERSION = "ON_CONVERSION"
ON_CLICK      = "ON_CLICK"

ALL_HOOK_POINTS = [
    PRE_VALIDATE, POST_VALIDATE, PRE_DEDUP,
    PRE_REWARD, POST_REWARD, ON_REJECTION,
    ON_FRAUD, ON_CONVERSION, ON_CLICK,
]


class HookRegistry:
    """
    Central registry for pipeline hooks.
    Thread-safe for read operations (hooks are registered at startup).
    """

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)

    def register(self, hook_point: str, name: str = ""):
        """
        Decorator to register a function as a hook.
        Usage:
            @hook_registry.register("POST_REWARD")
            def my_hook(context):
                ...
        """
        def decorator(fn: Callable) -> Callable:
            fn._hook_name = name or fn.__name__
            self._hooks[hook_point].append(fn)
            logger.debug("Hook registered: %s → %s", hook_point, fn._hook_name)
            return fn
        return decorator

    def add(self, hook_point: str, fn: Callable, name: str = "") -> None:
        """Programmatically add a hook."""
        fn._hook_name = name or getattr(fn, "__name__", "anonymous")
        self._hooks[hook_point].append(fn)

    def fire(self, hook_point: str, context: Any) -> None:
        """
        Fire all hooks for a hook point.
        Each hook receives the context object.
        Hook failures are logged but never propagate to caller.
        """
        for fn in self._hooks.get(hook_point, []):
            hook_name = getattr(fn, "_hook_name", fn.__name__)
            try:
                fn(context)
            except Exception as exc:
                logger.error(
                    "Hook %s at %s raised: %s",
                    hook_name, hook_point, exc, exc_info=True,
                )

    def remove(self, hook_point: str, fn: Callable) -> None:
        """Remove a specific hook."""
        self._hooks[hook_point] = [
            h for h in self._hooks[hook_point] if h is not fn
        ]

    def clear(self, hook_point: str = None) -> None:
        """Clear all hooks for a point, or all hooks if None."""
        if hook_point:
            self._hooks[hook_point].clear()
        else:
            self._hooks.clear()

    def list_hooks(self) -> dict:
        """Return dict of registered hooks per point (for admin display)."""
        return {
            point: [getattr(fn, "_hook_name", fn.__name__) for fn in fns]
            for point, fns in self._hooks.items()
        }


# Module-level registry singleton
hook_registry = HookRegistry()


# ── Built-in hooks ─────────────────────────────────────────────────────────────
# These are sensible defaults that can be overridden or disabled.

@hook_registry.register(POST_REWARD, name="realtime_counter")
def _increment_realtime_counters(context) -> None:
    """Increment real-time dashboard counters after every successful reward."""
    try:
        from .analytics_reporting.real_time_dashboard import realtime_dashboard
        payout = float(getattr(context, "payout", 0))
        realtime_dashboard.increment_conversion(revenue_usd=payout)
    except Exception as exc:
        logger.debug("realtime_counter hook failed: %s", exc)


@hook_registry.register(ON_FRAUD, name="fraud_realtime_counter")
def _increment_fraud_counter(context) -> None:
    """Increment real-time fraud counter."""
    try:
        from .analytics_reporting.real_time_dashboard import realtime_dashboard
        realtime_dashboard.increment_fraud()
    except Exception as exc:
        logger.debug("fraud_realtime_counter hook failed: %s", exc)


@hook_registry.register(ON_CLICK, name="click_realtime_counter")
def _increment_click_counter(context) -> None:
    """Increment real-time click counter."""
    try:
        from .analytics_reporting.real_time_dashboard import realtime_dashboard
        realtime_dashboard.increment_click()
    except Exception as exc:
        logger.debug("click_realtime_counter hook failed: %s", exc)


@hook_registry.register(ON_CONVERSION, name="velocity_increment")
def _increment_velocity_counters(context) -> None:
    """Increment velocity counters after a conversion."""
    try:
        from .fraud_detection.velocity_checker import velocity_checker
        ip = getattr(context, "source_ip", "") or ""
        user = getattr(context, "user", None)
        if ip:
            velocity_checker.increment_ip(ip)
        if user:
            velocity_checker.increment_user(str(getattr(user, "id", "")))
    except Exception as exc:
        logger.debug("velocity_increment hook failed: %s", exc)
