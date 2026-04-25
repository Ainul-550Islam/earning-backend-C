# api/payment_gateways/hooks.py
# Pre/post hooks for gateway operations

import logging
from typing import Callable, Optional
logger = logging.getLogger(__name__)

_pre_deposit_hooks  = []
_post_deposit_hooks = []
_pre_withdrawal_hooks  = []
_post_withdrawal_hooks = []


def register_pre_deposit_hook(func: Callable):
    """Register a hook called before every deposit. Raise to block."""
    _pre_deposit_hooks.append(func)


def register_post_deposit_hook(func: Callable):
    """Register a hook called after every successful deposit."""
    _post_deposit_hooks.append(func)


def run_pre_deposit_hooks(user, amount, gateway, **kwargs):
    for hook in _pre_deposit_hooks:
        try:
            hook(user=user, amount=amount, gateway=gateway, **kwargs)
        except Exception as e:
            logger.warning(f'Pre-deposit hook {hook.__name__} blocked: {e}')
            raise


def run_post_deposit_hooks(user, deposit):
    for hook in _post_deposit_hooks:
        try:
            hook(user=user, deposit=deposit)
        except Exception as e:
            logger.warning(f'Post-deposit hook {hook.__name__} failed: {e}')


def register_pre_withdrawal_hook(func: Callable):
    _pre_withdrawal_hooks.append(func)


def register_post_withdrawal_hook(func: Callable):
    _post_withdrawal_hooks.append(func)


def run_pre_withdrawal_hooks(user, amount, gateway, **kwargs):
    for hook in _pre_withdrawal_hooks:
        try:
            hook(user=user, amount=amount, gateway=gateway, **kwargs)
        except Exception as e:
            raise


def run_post_withdrawal_hooks(user, payout):
    for hook in _post_withdrawal_hooks:
        try:
            hook(user=user, payout=payout)
        except Exception as e:
            logger.warning(f'Post-withdrawal hook {hook.__name__} failed: {e}')
