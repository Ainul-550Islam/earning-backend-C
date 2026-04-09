# api/djoyalty/events/event_registry.py
import logging
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)

class EventRegistry:
    _handlers: Dict[str, List[Callable]] = {}

    @classmethod
    def register(cls, event_type: str, handler: Callable):
        if event_type not in cls._handlers:
            cls._handlers[event_type] = []
        cls._handlers[event_type].append(handler)

    @classmethod
    def get_handlers(cls, event_type: str) -> List[Callable]:
        return cls._handlers.get(event_type, [])

    @classmethod
    def clear(cls):
        cls._handlers = {}
