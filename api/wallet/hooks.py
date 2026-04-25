# api/wallet/hooks.py
"""
Hook system — pre/post hooks for wallet operations.
Allows plugging in custom logic without modifying core services.

Usage:
    from .hooks import wallet_hooks

    @wallet_hooks.before("credit")
    def check_fraud_before_credit(wallet, amount, **kwargs):
        if amount > 10000:
            from .services_extra import FraudDetectionService
            FraudDetectionService.check_large_credit(wallet, amount)

    @wallet_hooks.after("credit")
    def update_leaderboard_after_credit(wallet, amount, txn, **kwargs):
        update_leaderboard.delay(wallet.user_id)
"""
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger("wallet.hooks")


class WalletHookRegistry:
    """Registry for pre/post operation hooks."""

    def __init__(self):
        self._before: Dict[str, List[Callable]] = {}
        self._after:  Dict[str, List[Callable]] = {}

    def before(self, operation: str):
        """Register a pre-hook for an operation."""
        def decorator(func: Callable) -> Callable:
            self._before.setdefault(operation, []).append(func)
            logger.debug(f"Hook registered: before:{operation} → {func.__name__}")
            return func
        return decorator

    def after(self, operation: str):
        """Register a post-hook for an operation."""
        def decorator(func: Callable) -> Callable:
            self._after.setdefault(operation, []).append(func)
            logger.debug(f"Hook registered: after:{operation} -> {func.__name__}")
            return func
        return decorator

    def run_before(self, operation: str, **kwargs) -> None:
        """Run all pre-hooks for an operation."""
        for hook in self._before.get(operation, []):
            try:
                hook(**kwargs)
            except Exception as e:
                logger.error(f"Before hook {hook.__name__} failed for {operation}: {e}")

    def run_after(self, operation: str, **kwargs) -> None:
        """Run all post-hooks for an operation."""
        for hook in self._after.get(operation, []):
            try:
                hook(**kwargs)
            except Exception as e:
                logger.error(f"After hook {hook.__name__} failed for {operation}: {e}")

    def clear(self, operation: str = None):
        """Clear hooks (for testing)."""
        if operation:
            self._before.pop(operation, None)
            self._after.pop(operation, None)
        else:
            self._before.clear()
            self._after.clear()

    def list_hooks(self) -> dict:
        """List all registered hooks."""
        return {
            "before": {op: [h.__name__ for h in hooks] for op, hooks in self._before.items()},
            "after":  {op: [h.__name__ for h in hooks] for op, hooks in self._after.items()},
        }


# ── Singleton ─────────────────────────────────────────────────
wallet_hooks = WalletHookRegistry()


# ── Built-in hooks ────────────────────────────────────────────

@wallet_hooks.after("credit")
def after_credit_push_websocket(wallet=None, amount=None, txn=None, **kwargs):
    """Push balance update to WebSocket after credit."""
    if wallet:
        try:
            from .consumers import push_balance_update
            push_balance_update(wallet.user_id, wallet)
        except Exception:
            pass


@wallet_hooks.after("credit")
def after_credit_update_user_stats(wallet=None, amount=None, **kwargs):
    """Update user statistics after credit."""
    if wallet and amount:
        try:
            from .integration.data_bridge import UserBridge
            UserBridge.update_user_stats_on_earn(wallet.user_id, amount)
        except Exception:
            pass


@wallet_hooks.after("withdrawal_complete")
def after_withdrawal_push_websocket(wallet=None, withdrawal=None, **kwargs):
    """Push status update after withdrawal completes."""
    if wallet:
        try:
            from .consumers import push_balance_update
            push_balance_update(wallet.user_id, wallet)
        except Exception:
            pass
