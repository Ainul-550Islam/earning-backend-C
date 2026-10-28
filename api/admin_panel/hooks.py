# api/admin_panel/hooks.py
"""
Admin Panel Hooks — pluggable pre/post action hooks.
Other apps register hooks; admin_panel fires them at key points.

Usage:
    # Register a hook from another app
    from api.admin_panel.hooks import hook_registry
    hook_registry.register('before_user_ban', my_handler)

    # Fire from admin_panel action
    from api.admin_panel.hooks import fire_hook
    fire_hook('before_user_ban', user_id=123, reason='fraud')
"""
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class HookRegistry:
    """Central registry for all admin_panel hooks."""

    def __init__(self):
        self._hooks: Dict[str, List[Callable]] = {}

    def register(self, hook_name: str, handler: Callable, priority: int = 10) -> None:
        """Register a hook handler."""
        if hook_name not in self._hooks:
            self._hooks[hook_name] = []
        self._hooks[hook_name].append({'handler': handler, 'priority': priority})
        self._hooks[hook_name].sort(key=lambda x: x['priority'])
        logger.debug(f"[HookRegistry] Registered: {hook_name} -> {handler.__name__}")

    def unregister(self, hook_name: str, handler: Callable) -> bool:
        hooks = self._hooks.get(hook_name, [])
        before = len(hooks)
        self._hooks[hook_name] = [h for h in hooks if h['handler'] != handler]
        return len(self._hooks[hook_name]) < before

    def fire(self, hook_name: str, **kwargs) -> List[Any]:
        """Fire all handlers for a hook. Returns list of results."""
        results = []
        for entry in self._hooks.get(hook_name, []):
            try:
                result = entry['handler'](**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"[HookRegistry] Hook '{hook_name}' handler error: {e}")
        return results

    def fire_until_false(self, hook_name: str, **kwargs) -> bool:
        """Fire handlers; stop and return False if any returns False."""
        for entry in self._hooks.get(hook_name, []):
            try:
                result = entry['handler'](**kwargs)
                if result is False:
                    return False
            except Exception as e:
                logger.error(f"[HookRegistry] Hook '{hook_name}' error: {e}")
        return True

    def list_hooks(self) -> Dict[str, int]:
        return {name: len(handlers) for name, handlers in self._hooks.items()}

    def clear(self, hook_name: Optional[str] = None):
        if hook_name:
            self._hooks.pop(hook_name, None)
        else:
            self._hooks.clear()


# Global singleton
hook_registry = HookRegistry()


def fire_hook(hook_name: str, **kwargs) -> List[Any]:
    """Convenience function to fire a hook."""
    return hook_registry.fire(hook_name, **kwargs)


def register_hook(hook_name: str, priority: int = 10):
    """Decorator to register a function as a hook."""
    def decorator(func: Callable) -> Callable:
        hook_registry.register(hook_name, func, priority=priority)
        return func
    return decorator


# ==================== BUILT-IN HOOKS ====================

# Hook names used across admin_panel
HOOK_BEFORE_USER_BAN    = 'before_user_ban'
HOOK_AFTER_USER_BAN     = 'after_user_ban'
HOOK_BEFORE_USER_UNBAN  = 'before_user_unban'
HOOK_AFTER_USER_UNBAN   = 'after_user_unban'
HOOK_BEFORE_WITHDRAWAL_APPROVE = 'before_withdrawal_approve'
HOOK_AFTER_WITHDRAWAL_APPROVE  = 'after_withdrawal_approve'
HOOK_BEFORE_KYC_APPROVE = 'before_kyc_approve'
HOOK_AFTER_KYC_APPROVE  = 'after_kyc_approve'
HOOK_BEFORE_MAINTENANCE = 'before_maintenance_start'
HOOK_AFTER_MAINTENANCE  = 'after_maintenance_end'
HOOK_ON_FRAUD_DETECTED  = 'on_fraud_detected'
HOOK_ON_CONFIG_CHANGE   = 'on_config_change'
HOOK_ON_FLAG_CHANGE     = 'on_feature_flag_change'
HOOK_ON_BROADCAST_SENT  = 'on_broadcast_sent'


# ==================== DEFAULT HOOK HANDLERS ====================

@register_hook(HOOK_AFTER_USER_BAN)
def _default_freeze_wallet_on_ban(user_id=None, **kwargs):
    """Auto-freeze wallet when user is banned."""
    if not user_id:
        return
    try:
        from api.wallet.models import Wallet
        Wallet.objects.filter(user_id=user_id, is_locked=False).update(is_locked=True)
    except Exception as e:
        logger.debug(f"[hook:after_user_ban] wallet freeze failed: {e}")


@register_hook(HOOK_AFTER_USER_BAN)
def _default_cancel_payouts_on_ban(user_id=None, **kwargs):
    """Auto-cancel pending payouts when user is banned."""
    if not user_id:
        return
    try:
        from api.payout_queue.models import PayoutItem
        PayoutItem.objects.filter(user_id=user_id, status='QUEUED').update(status='CANCELLED')
    except Exception as e:
        logger.debug(f"[hook:after_user_ban] payout cancel failed: {e}")


@register_hook(HOOK_ON_CONFIG_CHANGE)
def _default_clear_config_cache(config_key=None, **kwargs):
    """Clear config cache when a key changes."""
    from django.core.cache import cache
    if config_key:
        cache.delete(f'admin_panel:config:{config_key}')
    cache.delete('admin_panel:config_all')


@register_hook(HOOK_ON_FLAG_CHANGE)
def _default_clear_flag_cache(flag_key=None, **kwargs):
    """Clear feature flag cache when a flag changes."""
    from django.core.cache import cache
    if flag_key:
        cache.delete(f'admin_panel:feature_flag:{flag_key}')
    cache.delete('admin_panel:feature_flags_all')