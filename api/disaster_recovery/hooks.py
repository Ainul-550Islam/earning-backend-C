"""Hooks — Pre/post operation hooks for extending DR system behavior."""
import logging
from typing import Callable, List
logger = logging.getLogger(__name__)

class HookRegistry:
    def __init__(self):
        self._pre_hooks: dict = {}
        self._post_hooks: dict = {}

    def register_pre(self, operation: str, fn: Callable):
        self._pre_hooks.setdefault(operation, []).append(fn)

    def register_post(self, operation: str, fn: Callable):
        self._post_hooks.setdefault(operation, []).append(fn)

    def run_pre(self, operation: str, context: dict) -> dict:
        for fn in self._pre_hooks.get(operation, []):
            try:
                result = fn(context)
                if isinstance(result, dict):
                    context.update(result)
            except Exception as e:
                logger.error(f"Pre-hook error [{operation}]: {e}")
        return context

    def run_post(self, operation: str, context: dict, result: dict) -> dict:
        for fn in self._post_hooks.get(operation, []):
            try:
                fn(context, result)
            except Exception as e:
                logger.error(f"Post-hook error [{operation}]: {e}")
        return result

hook_registry = HookRegistry()
