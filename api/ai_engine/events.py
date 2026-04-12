"""
api/ai_engine/events.py
========================
AI Engine — Event system।
"""

import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

_handlers: Dict[str, List[Callable]] = {}


def on(event: str, handler: Callable):
    """Event handler register করো।"""
    _handlers.setdefault(event, []).append(handler)


def emit(event: str, **payload):
    """Event emit করো।"""
    for handler in _handlers.get(event, []):
        try:
            handler(**payload)
        except Exception as e:
            logger.error(f"Event handler error [{event}]: {e}")


# Built-in events
AI_EVENT_MODEL_DEPLOYED   = 'ai.model.deployed'
AI_EVENT_TRAINING_DONE    = 'ai.training.completed'
AI_EVENT_ANOMALY_DETECTED = 'ai.anomaly.detected'
AI_EVENT_CHURN_HIGH       = 'ai.churn.high_risk'
AI_EVENT_DRIFT_CRITICAL   = 'ai.drift.critical'
AI_EVENT_INSIGHT_CREATED  = 'ai.insight.created'
