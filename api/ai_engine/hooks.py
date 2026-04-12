"""
api/ai_engine/hooks.py
=======================
AI Engine — Lifecycle Hooks।
Pre/Post hooks for model training, prediction, recommendation।
"""

import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

_pre_hooks:  Dict[str, List[Callable]] = {}
_post_hooks: Dict[str, List[Callable]] = {}


def register_pre_hook(stage: str, fn: Callable):
    _pre_hooks.setdefault(stage, []).append(fn)


def register_post_hook(stage: str, fn: Callable):
    _post_hooks.setdefault(stage, []).append(fn)


def run_pre_hooks(stage: str, context: dict) -> dict:
    for hook in _pre_hooks.get(stage, []):
        try:
            result = hook(context)
            if result:
                context.update(result)
        except Exception as e:
            logger.error(f"Pre-hook error [{stage}]: {e}")
    return context


def run_post_hooks(stage: str, context: dict, result: dict) -> dict:
    for hook in _post_hooks.get(stage, []):
        try:
            hook(context, result)
        except Exception as e:
            logger.error(f"Post-hook error [{stage}]: {e}")
    return result


# Hook stage constants
HOOK_PRE_TRAINING       = 'pre_training'
HOOK_POST_TRAINING      = 'post_training'
HOOK_PRE_PREDICTION     = 'pre_prediction'
HOOK_POST_PREDICTION    = 'post_prediction'
HOOK_PRE_RECOMMEND      = 'pre_recommend'
HOOK_POST_RECOMMEND     = 'post_recommend'
