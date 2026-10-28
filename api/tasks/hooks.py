"""
api/tasks/hooks.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lifecycle hooks — synchronous side effects that run inline
before/after critical operations in services and views.

Unlike EventBus (async pub/sub), hooks run SYNCHRONOUSLY
in the same transaction block. Use for:
  • Pre-validation before task completion
  • Post-credit DataBridge sync
  • Fraud score check before withdrawal
  • Cache invalidation after model save

Usage:
    from api.tasks.hooks import HookRegistry, hook

    # Register
    @hook('before_task_complete')
    def check_daily_limit(context):
        if context['user_completions_today'] >= 20:
            raise ValidationError('Daily limit reached')

    # Call in service
    HookRegistry.run('before_task_complete', {'user_id': 123, ...})
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HOOK REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

class HookRegistry:
    """
    Registry for synchronous lifecycle hooks.
    Hooks run in priority order (lower = earlier).
    If any hook raises an exception, execution stops.
    """

    _hooks: Dict[str, List[Dict]] = {}

    @classmethod
    def register(cls, event: str, handler: Callable,
                 priority: int = 50, label: str = '') -> None:
        cls._hooks.setdefault(event, []).append({
            'handler':  handler,
            'priority': priority,
            'label':    label or handler.__name__,
        })
        cls._hooks[event].sort(key=lambda x: x['priority'])

    @classmethod
    def run(cls, event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run all hooks for an event in priority order.
        Context is passed and mutated by each hook.
        Returns the final context.
        Raises if any hook raises.
        """
        for entry in cls._hooks.get(event, []):
            try:
                result = entry['handler'](context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception:
                raise   # Propagate — caller decides what to do
        return context

    @classmethod
    def run_safe(cls, event: str, context: Dict[str, Any],
                 on_error: Callable = None) -> Dict[str, Any]:
        """
        Run hooks but catch errors and call on_error if provided.
        Never raises — for non-critical side effects.
        """
        for entry in cls._hooks.get(event, []):
            try:
                result = entry['handler'](context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as e:
                logger.warning(f"[HOOK] '{entry['label']}' error: {e}")
                if on_error:
                    on_error(entry['label'], e, context)
        return context

    @classmethod
    def list_hooks(cls, event: str = None) -> Dict:
        if event:
            return {event: [
                {'label': h['label'], 'priority': h['priority']}
                for h in cls._hooks.get(event, [])
            ]}
        return {
            ev: [{'label': h['label'], 'priority': h['priority']} for h in hooks]
            for ev, hooks in cls._hooks.items()
        }

    @classmethod
    def clear(cls, event: str = None) -> None:
        if event:
            cls._hooks.pop(event, None)
        else:
            cls._hooks.clear()


def hook(event: str, priority: int = 50):
    """Decorator to register a function as a hook for an event."""
    def decorator(fn: Callable) -> Callable:
        HookRegistry.register(event, fn, priority=priority)
        return fn
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN TASK COMPLETION HOOKS
# ══════════════════════════════════════════════════════════════════════════════

@hook('before_task_complete', priority=1)
def hook_check_account_not_suspended(ctx: Dict) -> None:
    """Block task completion if account is suspended."""
    user_id = ctx.get('user_id')
    if user_id and cache.get(f'user_suspended_{user_id}'):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Your account has been suspended.')


@hook('before_task_complete', priority=5)
def hook_check_fraud_score(ctx: Dict) -> None:
    """Block task completion if fraud score is critical."""
    user_id = ctx.get('user_id')
    if user_id:
        score = int(cache.get(f'fraud_score_{user_id}', 0))
        if score >= 80:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Account flagged. Contact support.')
        ctx['current_fraud_score'] = score


@hook('before_task_complete', priority=10)
def hook_check_ip_not_blocked(ctx: Dict) -> None:
    """Block task completion from blocked IPs."""
    import hashlib
    ip = ctx.get('ip_address', '')
    if ip:
        ip_hash = hashlib.md5(ip.encode()).hexdigest()
        if cache.get(f'ip_blocked_{ip_hash}'):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Access denied from this IP.')


@hook('before_task_complete', priority=20)
def hook_check_daily_completion_limit(ctx: Dict) -> None:
    """Enforce per-user daily task completion velocity limit."""
    user_id = ctx.get('user_id')
    if not user_id:
        return
    from api.tasks.constants import MAX_COMPLETIONS_PER_HOUR
    vel_key = f'completion_velocity_{user_id}'
    count   = cache.get(vel_key, 0)
    if count >= MAX_COMPLETIONS_PER_HOUR:
        from rest_framework.exceptions import Throttled
        raise Throttled(detail='Completion rate limit reached. Please slow down.')
    cache.set(vel_key, count + 1, timeout=3600)


@hook('after_task_complete', priority=10)
def hook_sync_wallet_to_bridge(ctx: Dict) -> None:
    """Sync updated wallet balance to DataBridge after completion."""
    user_id = ctx.get('user_id')
    if user_id:
        try:
            from api.tasks.integration.data_bridge import DataBridge
            DataBridge.user(user_id).invalidate('wallet_balance')
        except Exception as e:
            logger.debug(f"[HOOK] sync_wallet_to_bridge: {e}")


@hook('after_task_complete', priority=20)
def hook_update_community_points(ctx: Dict) -> None:
    """Asynchronously update community points after task completion."""
    user_id       = ctx.get('user_id')
    reward_amount = ctx.get('reward_amount', '0')
    if user_id:
        try:
            from api.tasks.community_tasks import award_community_points
            award_community_points.apply_async(kwargs={
                'user_id':    user_id,
                'amount_usd': str(reward_amount),
                'source':     'task_completion',
            })
        except Exception as e:
            logger.debug(f"[HOOK] update_community_points: {e}")


@hook('after_task_complete', priority=30)
def hook_emit_completion_event(ctx: Dict) -> None:
    """Dispatch typed TaskCompletedEvent after successful completion."""
    try:
        from api.tasks.events import EventDispatcher, TaskCompletedEvent
        from decimal import Decimal
        EventDispatcher.dispatch(TaskCompletedEvent(
            user_id=ctx.get('user_id', 0),
            task_id=ctx.get('task_id', ''),
            completion_id=ctx.get('completion_id', 0),
            reward_amount=Decimal(str(ctx.get('reward_amount', '0'))),
            ip_address=ctx.get('ip_address', ''),
            device=ctx.get('device', ''),
            country=ctx.get('country', ''),
        ), broadcast_ws=True)
    except Exception as e:
        logger.debug(f"[HOOK] emit_completion_event: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN WITHDRAWAL HOOKS
# ══════════════════════════════════════════════════════════════════════════════

@hook('before_withdrawal', priority=1)
def hook_check_withdrawal_not_suspended(ctx: Dict) -> None:
    """Block withdrawal if account is suspended."""
    user_id = ctx.get('user_id')
    if user_id and cache.get(f'user_suspended_{user_id}'):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Account suspended. Withdrawals are blocked.')


@hook('before_withdrawal', priority=5)
def hook_check_payout_method_valid(ctx: Dict) -> None:
    """Block withdrawal if payout method details are missing."""
    user_id = ctx.get('user_id')
    if user_id and cache.get(f'payout_method_invalid_{user_id}'):
        from rest_framework.exceptions import ValidationError
        raise ValidationError('Please configure a valid payout method first.')


@hook('before_withdrawal', priority=10)
def hook_fraud_check_withdrawal(ctx: Dict) -> None:
    """Flag high-risk withdrawals for fraud review."""
    user_id = ctx.get('user_id')
    if not user_id:
        return
    score = int(cache.get(f'fraud_score_{user_id}', 0))
    if score >= 40:
        ctx['withdrawal_hold'] = True
        ctx['hold_reason']     = f'fraud_score:{score}'
        logger.warning(f"[HOOK] Withdrawal hold: user={user_id} score={score}")


@hook('after_withdrawal_complete', priority=10)
def hook_sync_balance_after_withdrawal(ctx: Dict) -> None:
    """Invalidate cached wallet balance after successful withdrawal."""
    user_id = ctx.get('user_id')
    if user_id:
        try:
            from api.tasks.integration.data_bridge import DataBridge
            DataBridge.user(user_id).invalidate('wallet_balance')
        except Exception as e:
            logger.debug(f"[HOOK] sync_balance_after_withdrawal: {e}")


@hook('after_withdrawal_complete', priority=20)
def hook_send_withdrawal_notification(ctx: Dict) -> None:
    """Send push + email notification after withdrawal is processed."""
    user_id = ctx.get('user_id')
    amount  = ctx.get('amount', '0')
    method  = ctx.get('payment_method', 'your account')
    if user_id:
        try:
            from api.tasks.notification_tasks import dispatch_in_app_notification
            dispatch_in_app_notification.apply_async(kwargs={
                'user_id':           user_id,
                'title':             '💸 Withdrawal Processed!',
                'message':           f'${amount} has been sent to {method}.',
                'notification_type': 'success',
            })
        except Exception as e:
            logger.debug(f"[HOOK] send_withdrawal_notification: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN OFFER HOOKS
# ══════════════════════════════════════════════════════════════════════════════

@hook('before_offer_serve', priority=10)
def hook_check_offer_not_capped(ctx: Dict) -> None:
    """Prevent serving a capped offer."""
    offer_id = ctx.get('offer_id')
    if offer_id:
        from api.tasks.integration.data_bridge import DataBridge
        daily_used = DataBridge.get_offer(offer_id, 'daily_clicks_used') or 0
        daily_cap  = DataBridge.get_offer(offer_id, 'daily_cap') or 0
        if daily_cap and daily_used >= daily_cap:
            ctx['offer_capped'] = True


@hook('after_postback_verified', priority=10)
def hook_emit_offer_converted(ctx: Dict) -> None:
    """Dispatch OfferConvertedEvent after postback verification."""
    try:
        from api.tasks.events import EventDispatcher, OfferConvertedEvent
        from decimal import Decimal
        EventDispatcher.dispatch(OfferConvertedEvent(
            user_id=int(ctx.get('publisher_id') or ctx.get('user_id') or 0),
            offer_id=ctx.get('offer_id', ''),
            transaction_id=ctx.get('transaction_id', ''),
            payout=Decimal(str(ctx.get('payout', '0'))),
            status=ctx.get('status', 'approved'),
            ip_address=ctx.get('ip_address', ''),
            country=ctx.get('country', ''),
        ))
    except Exception as e:
        logger.debug(f"[HOOK] emit_offer_converted: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# BUILT-IN USER REGISTRATION HOOKS
# ══════════════════════════════════════════════════════════════════════════════

@hook('after_user_register', priority=10)
def hook_emit_user_registered(ctx: Dict) -> None:
    """Dispatch UserRegisteredEvent after new user registration."""
    try:
        from api.tasks.events import EventDispatcher, UserRegisteredEvent
        EventDispatcher.dispatch(UserRegisteredEvent(
            user_id=ctx.get('user_id', 0),
            username=ctx.get('username', ''),
            email=ctx.get('email', ''),
            referral_code=ctx.get('referral_code', ''),
            ip_address=ctx.get('ip_address', ''),
            country=ctx.get('country', ''),
        ))
    except Exception as e:
        logger.debug(f"[HOOK] emit_user_registered: {e}")


__all__ = [
    'HookRegistry', 'hook',
    # Built-in hooks are auto-registered via @hook decorator
]
