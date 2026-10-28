"""
tasks/integration/registry.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Integration Registry — Central handler/plugin registry
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Register task handlers, integrations, and plugins in one place.
Auto-discovers handlers from all installed task modules.
"""

import logging
from typing import Callable, Dict, Any, List, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class IntegrationRegistry:
    """
    Central registry for all integration handlers.
    Handlers can be functions or Celery task names.
    """

    _registry: Dict[str, List[Dict]] = {}

    @classmethod
    def register(
        cls,
        trigger: str,
        handler,
        priority: int = 50,
        async_exec: bool = True,
        description: str = '',
    ) -> None:
        """
        Register a handler for a trigger.

        Args:
            trigger:     Trigger name (e.g. 'after_task_complete')
            handler:     Function or Celery task name string
            priority:    Execution order (lower = earlier)
            async_exec:  True = Celery dispatch, False = sync
            description: Human-readable description
        """
        cls._registry.setdefault(trigger, []).append({
            'handler':     handler,
            'priority':    priority,
            'async_exec':  async_exec,
            'description': description,
        })
        cls._registry[trigger].sort(key=lambda x: x['priority'])
        logger.debug(f"[Registry] Registered '{trigger}' → {handler}")

    @classmethod
    def execute(cls, trigger: str, context: Dict[str, Any] = None) -> List[Any]:
        """Execute all handlers for a trigger in priority order."""
        handlers = cls._registry.get(trigger, [])
        context  = context or {}
        results  = []

        for h in handlers:
            handler   = h['handler']
            async_exc = h['async_exec']
            try:
                if async_exc and isinstance(handler, str):
                    # Celery task name
                    from celery import current_app
                    current_app.send_task(handler, kwargs={'context': context})
                    results.append({'handler': handler, 'dispatched': True})
                elif callable(handler):
                    result = handler(context)
                    results.append({'handler': handler.__name__, 'result': result})
            except Exception as e:
                logger.error(f"[Registry] Handler error ({handler}): {e}")
                results.append({'handler': str(handler), 'error': str(e)})

        return results

    @classmethod
    def list_handlers(cls, trigger: str = None) -> Dict:
        """List all registered handlers."""
        if trigger:
            return {trigger: cls._registry.get(trigger, [])}
        return dict(cls._registry)

    @classmethod
    def clear(cls, trigger: str = None) -> None:
        """Clear handlers (used in testing)."""
        if trigger:
            cls._registry.pop(trigger, None)
        else:
            cls._registry.clear()


def register_handler(trigger: str, priority: int = 50, async_exec: bool = True, description: str = ''):
    """Decorator to register a function as a trigger handler."""
    def decorator(func: Callable) -> Callable:
        IntegrationRegistry.register(
            trigger=trigger,
            handler=func,
            priority=priority,
            async_exec=async_exec,
            description=description or func.__doc__ or '',
        )
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ─── Default Handler Registrations ────────────────────────────────────────────

def register_default_integration_handlers():
    """Register all default integration handlers."""

    # After task completion
    IntegrationRegistry.register(
        'after_task_complete',
        'tasks.gamification_tasks.update_streak_status',
        priority=10, async_exec=True,
        description='Update user streak after task completion',
    )
    IntegrationRegistry.register(
        'after_task_complete',
        'tasks.gamification_tasks.award_badges',
        priority=20, async_exec=True,
        description='Check and award achievement badges',
    )
    IntegrationRegistry.register(
        'after_task_complete',
        'tasks.gamification_tasks.process_milestone_rewards',
        priority=30, async_exec=True,
        description='Credit milestone bonuses',
    )

    # After registration
    IntegrationRegistry.register(
        'after_user_register',
        'tasks.user_lifecycle_tasks.send_welcome_sequence',
        priority=10, async_exec=True,
        description='Send 3-step welcome email sequence',
    )
    IntegrationRegistry.register(
        'after_user_register',
        'tasks.user_lifecycle_tasks.assign_onboarding_tasks',
        priority=20, async_exec=True,
        description='Assign starter tasks to new user',
    )

    # After CPA conversion
    IntegrationRegistry.register(
        'after_cpa_conversion',
        'tasks.cpalead_tasks.cpalead_credit_publisher',
        priority=10, async_exec=True,
        description='Credit publisher for CPA conversion',
    )
    IntegrationRegistry.register(
        'after_cpa_conversion',
        'tasks.cpalead_tasks.cpalead_update_offer_stats',
        priority=20, async_exec=True,
        description='Update offer statistics',
    )

    logger.info("[Registry] Default integration handlers registered")
