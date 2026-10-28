# api/djoyalty/hooks.py
"""
Djoyalty Hooks -- Pluggable lifecycle hooks for loyalty events।
Register hooks to run custom logic at key points।

Usage:
    @LoyaltyHooks.register('after_earn')
    def my_custom_earn_hook(customer, points, **kwargs):
        # custom logic after points earned
        pass
"""
import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

_hooks: Dict[str, List[Callable]] = {}


class LoyaltyHooks:
    """Pluggable hook system for loyalty lifecycle events।"""

    SUPPORTED = [
        'before_earn', 'after_earn',
        'before_redeem', 'after_redeem',
        'after_tier_upgrade', 'after_tier_downgrade',
        'after_badge_unlock',
        'before_cashout', 'after_cashout',
        'after_offer_complete',
        'after_referral_conversion',
        'on_fraud_detected',
        'on_churn_alert',
    ]

    @classmethod
    def register(cls, hook_name: str):
        """Decorator to register a hook function।"""
        def decorator(func: Callable) -> Callable:
            if hook_name not in _hooks:
                _hooks[hook_name] = []
            _hooks[hook_name].append(func)
            logger.debug('LoyaltyHooks: registered %s -> %s', hook_name, func.__name__)
            return func
        return decorator

    @classmethod
    def fire(cls, hook_name: str, **kwargs) -> list:
        """Fire all registered hooks for a given event।"""
        results = []
        for hook in _hooks.get(hook_name, []):
            try:
                result = hook(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error('LoyaltyHooks.fire [%s] error in %s: %s',
                             hook_name, hook.__name__, e)
        return results

    @classmethod
    def list_hooks(cls) -> dict:
        return {name: [f.__name__ for f in funcs] for name, funcs in _hooks.items()}

    @classmethod
    def clear(cls, hook_name: str = ''):
        if hook_name:
            _hooks.pop(hook_name, None)
        else:
            _hooks.clear()
