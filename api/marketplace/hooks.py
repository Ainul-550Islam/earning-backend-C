"""
marketplace/hooks.py — Lifecycle Hooks
========================================
Hook points for extending marketplace behaviour without modifying core code.
Usage:
    from api.marketplace.hooks import register_hook, ORDER_PRE_CREATE

    @register_hook(ORDER_PRE_CREATE)
    def my_hook(context):
        # Validate / modify context dict in place
        pass
"""

from __future__ import annotations
from typing import Callable, Dict, List

_hooks: Dict[str, List[Callable]] = {}

# Hook names
ORDER_PRE_CREATE    = "order.pre_create"
ORDER_POST_CREATE   = "order.post_create"
PAYMENT_PRE_PROCESS = "payment.pre_process"
PAYMENT_POST_PROCESS = "payment.post_process"
CART_CHECKOUT_PRE   = "cart.checkout.pre"
SELLER_PRE_PAYOUT   = "seller.pre_payout"


def register_hook(hook_name: str):
    def decorator(fn: Callable):
        _hooks.setdefault(hook_name, []).append(fn)
        return fn
    return decorator


def run_hooks(hook_name: str, context: dict) -> dict:
    """Run all registered hooks for hook_name; each hook mutates context."""
    for fn in _hooks.get(hook_name, []):
        fn(context)
    return context
