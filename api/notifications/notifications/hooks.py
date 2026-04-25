# earning_backend/api/notifications/hooks.py
"""
Hooks — Lifecycle hooks for the notification send pipeline.

Hooks allow external code to intercept and modify notifications
at specific points in the send pipeline without modifying core service code.

Pipeline order:
  1. pre_validate   — before data validation
  2. post_validate  — after validation passes
  3. pre_send       — before sending to provider
  4. post_send      — after provider responds (success or fail)
  5. post_deliver   — after delivery confirmed
  6. pre_delete     — before soft-delete

Usage (register a hook):
    from notifications.hooks import pipeline

    @pipeline.hook('pre_send')
    def my_hook(notification, context):
        if notification.priority == 'low':
            context['delay_seconds'] = 300  # delay low-priority
        return notification, context

Usage (register in apps.py ready()):
    from notifications.hooks import pipeline
    pipeline.register('post_send', my_custom_hook)
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hook pipeline
# ---------------------------------------------------------------------------

class NotificationPipeline:
    """
    Manages lifecycle hooks for the notification send pipeline.

    Hooks are callables with signature:
        hook(notification, context: dict) -> Tuple[notification, dict]
    If a hook returns None, the original inputs are preserved.
    If a hook raises StopPipeline, processing stops and the notification is skipped.
    """

    VALID_STAGES = [
        'pre_validate',
        'post_validate',
        'pre_send',
        'post_send',
        'post_deliver',
        'pre_delete',
        'on_failure',
        'on_retry',
        'on_fatigue',
        'on_opt_out',
    ]

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {s: [] for s in self.VALID_STAGES}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, stage: str, hook: Callable, priority: int = 5):
        """
        Register a hook for a pipeline stage.

        Args:
            stage:    One of VALID_STAGES.
            hook:     Callable(notification, context) -> (notification, context) | None
            priority: Lower numbers run first (1 = first, 10 = last).
        """
        if stage not in self.VALID_STAGES:
            raise ValueError(
                f'Invalid hook stage: "{stage}". Valid: {self.VALID_STAGES}'
            )
        # Attach priority as attribute for sorting
        hook._hook_priority = getattr(hook, '_hook_priority', priority)
        self._hooks[stage].append(hook)
        self._hooks[stage].sort(key=lambda h: getattr(h, '_hook_priority', 5))
        logger.debug(f'Pipeline: registered hook "{hook.__name__}" at stage "{stage}"')

    def hook(self, stage: str, priority: int = 5):
        """Decorator to register a hook."""
        def decorator(func: Callable) -> Callable:
            self.register(stage, func, priority)
            return func
        return decorator

    def unregister(self, stage: str, hook: Callable):
        """Remove a hook from a stage."""
        self._hooks[stage] = [h for h in self._hooks[stage] if h != hook]

    def clear(self, stage: str = None):
        """Clear hooks for a stage, or all stages if stage=None."""
        if stage:
            self._hooks[stage] = []
        else:
            for s in self.VALID_STAGES:
                self._hooks[s] = []

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, stage: str, notification, context: Optional[Dict] = None) -> Tuple:
        """
        Run all hooks for a stage in priority order.

        Returns:
            (notification, context) — potentially modified by hooks.

        Raises:
            StopPipeline — if a hook signals that processing should stop.
        """
        context = context or {}
        hooks = self._hooks.get(stage, [])

        for hook in hooks:
            try:
                result = hook(notification, context)
                if result is not None:
                    if isinstance(result, tuple) and len(result) == 2:
                        notification, context = result
                    else:
                        notification = result
            except StopPipeline:
                raise
            except Exception as exc:
                logger.error(
                    f'Pipeline hook "{hook.__name__}" at stage "{stage}" failed: {exc}'
                )
                # Don't stop pipeline on hook error — just log and continue
                context.setdefault('hook_errors', []).append(
                    {'hook': hook.__name__, 'stage': stage, 'error': str(exc)}
                )

        return notification, context

    def run_safe(self, stage: str, notification, context: Optional[Dict] = None) -> Tuple:
        """
        Same as run() but catches StopPipeline and returns (None, context).
        """
        try:
            return self.run(stage, notification, context)
        except StopPipeline as sp:
            ctx = context or {}
            ctx['pipeline_stopped'] = True
            ctx['stop_reason'] = str(sp)
            return None, ctx

    def list_hooks(self, stage: str = None) -> Dict:
        """List all registered hooks."""
        if stage:
            return {stage: [h.__name__ for h in self._hooks.get(stage, [])]}
        return {s: [h.__name__ for h in hooks] for s, hooks in self._hooks.items()}


# ---------------------------------------------------------------------------
# StopPipeline exception
# ---------------------------------------------------------------------------

class StopPipeline(Exception):
    """
    Raise this inside a hook to abort the entire send pipeline.
    The notification will not be sent.

    Usage:
        @pipeline.hook('pre_send')
        def block_during_maintenance(notification, context):
            if settings.MAINTENANCE_MODE:
                raise StopPipeline('System is in maintenance mode.')
    """
    pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

pipeline = NotificationPipeline()


# ---------------------------------------------------------------------------
# Built-in hooks — registered by default
# ---------------------------------------------------------------------------

@pipeline.hook('pre_send', priority=1)
def _check_fatigue_hook(notification, context: dict):
    """
    Block send if user is notification-fatigued.
    Exempt: critical and urgent priority notifications.
    """
    priority = getattr(notification, 'priority', 'medium') or 'medium'
    if priority in ('critical', 'urgent'):
        return notification, context

    user = getattr(notification, 'user', None)
    if user:
        try:
            from notifications.services.FatigueService import fatigue_service
            if fatigue_service.is_fatigued(user, priority=priority):
                context['blocked_by'] = 'fatigue'
                context['fatigue_exceeded'] = True
                raise StopPipeline(f'User #{user.pk} is notification-fatigued.')
        except StopPipeline:
            raise
        except Exception as exc:
            logger.debug(f'_check_fatigue_hook: {exc}')

    return notification, context


@pipeline.hook('pre_send', priority=2)
def _check_opt_out_hook(notification, context: dict):
    """
    Block send if user has opted out of the notification channel.
    Critical notifications bypass opt-out.
    """
    priority = getattr(notification, 'priority', 'medium') or 'medium'
    if priority == 'critical':
        return notification, context

    user = getattr(notification, 'user', None)
    channel = getattr(notification, 'channel', 'in_app') or 'in_app'

    if user and channel not in ('all',):
        try:
            from notifications.services.OptOutService import opt_out_service
            if opt_out_service.is_opted_out(user, channel):
                context['blocked_by'] = 'opt_out'
                context['opted_out_channel'] = channel
                raise StopPipeline(
                    f'User #{user.pk} opted out of {channel} notifications.'
                )
        except StopPipeline:
            raise
        except Exception as exc:
            logger.debug(f'_check_opt_out_hook: {exc}')

    return notification, context


@pipeline.hook('pre_send', priority=3)
def _check_dnd_hook(notification, context: dict):
    """
    Check if notification should be delayed due to Do Not Disturb.
    Non-critical notifications get delayed to after DND window.
    """
    priority = getattr(notification, 'priority', 'medium') or 'medium'
    if priority in ('critical', 'urgent'):
        return notification, context

    user = getattr(notification, 'user', None)
    if user:
        try:
            from notifications.models import NotificationPreference
            pref = NotificationPreference.objects.filter(user=user).first()
            dnd_enabled = (
                getattr(pref, 'quiet_hours_enabled', False) or
                getattr(pref, 'do_not_disturb', False)
            ) if pref else False

            if dnd_enabled:
                context['dnd_active'] = True
                context['send_note'] = 'Delayed due to DND — will send after quiet hours'
                # Don't stop — let the scheduler handle the delay
        except Exception as exc:
            logger.debug(f'_check_dnd_hook: {exc}')

    return notification, context


@pipeline.hook('post_send', priority=1)
def _record_send_metrics_hook(notification, context: dict):
    """
    After a send: increment fatigue counters and record analytics.
    """
    user = getattr(notification, 'user', None)
    if not user:
        return notification, context

    # Only record for successful sends
    if context.get('send_success', True):
        try:
            from notifications.services.FatigueService import fatigue_service
            fatigue_service.record_send(user)
        except Exception as exc:
            logger.debug(f'_record_send_metrics_hook fatigue: {exc}')

    return notification, context


@pipeline.hook('on_failure', priority=1)
def _log_failure_hook(notification, context: dict):
    """Log notification failures to audit trail."""
    try:
        from notifications.integration_system.integ_audit_logs import audit_logger
        audit_logger.log(
            action='send_failed',
            module='notifications',
            actor_id=getattr(getattr(notification, 'user', None), 'pk', None),
            target_type='Notification',
            target_id=str(getattr(notification, 'pk', '')),
            success=False,
            error=context.get('error', 'Unknown error'),
        )
    except Exception as exc:
        logger.debug(f'_log_failure_hook: {exc}')
    return notification, context
