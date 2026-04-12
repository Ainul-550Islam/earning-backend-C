"""
api/ai_engine/plugins.py
=========================
AI Engine — Plugin Registry।
3rd party model backends বা custom engines register করো।
"""

import logging
from typing import Dict, Type, Any

logger = logging.getLogger(__name__)

_registry: Dict[str, Any] = {}


def register_plugin(name: str, plugin_class):
    """Plugin register করো।"""
    _registry[name] = plugin_class
    logger.info(f"AI Plugin registered: {name}")


def get_plugin(name: str):
    """Plugin নিয়ে আসো।"""
    plugin = _registry.get(name)
    if not plugin:
        raise KeyError(f"AI Plugin not found: {name}. Registered: {list(_registry.keys())}")
    return plugin


def list_plugins() -> list:
    return list(_registry.keys())


# Built-in plugin names
PLUGIN_SKLEARN    = 'sklearn'
PLUGIN_XGBOOST    = 'xgboost'
PLUGIN_LIGHTGBM   = 'lightgbm'
PLUGIN_TENSORFLOW = 'tensorflow'
PLUGIN_PYTORCH    = 'pytorch'
PLUGIN_HUGGINGFACE = 'huggingface'
PLUGIN_OPENAI     = 'openai'
PLUGIN_ANTHROPIC  = 'anthropic'
