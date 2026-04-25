# integration_system/bridge.py
"""
Bridge — Module-to-module data bridge for direct synchronous data exchange.
Provides typed channel objects between any two modules.
"""
import logging, threading
from typing import Any, Callable, Dict, Optional
from .integ_constants import IntegStatus
from .integ_exceptions import BridgeConnectionFailed
logger = logging.getLogger(__name__)

class BridgeChannel:
    def __init__(self, source: str, target: str):
        self.source = source
        self.target = target
        self.is_open = True
        self._transforms: list = []
        self._filters: list = []

    def transform(self, fn: Callable):
        self._transforms.append(fn)
        return self

    def filter(self, fn: Callable):
        self._filters.append(fn)
        return self

    def send(self, data: Dict, **kwargs) -> Dict:
        if not self.is_open:
            raise BridgeConnectionFailed(self.source, self.target, 'Channel closed')
        processed = dict(data)
        for f in self._filters:
            if not f(processed):
                return {'success': True, 'status': 'filtered', 'data': {}}
        for t in self._transforms:
            processed = t(processed)
        try:
            from .integ_handler import handler
            return handler.trigger(self.target, processed, **kwargs)
        except Exception as exc:
            raise BridgeConnectionFailed(self.source, self.target, str(exc))

    def close(self):
        self.is_open = False


class Bridge:
    """Central bridge manager. Create channels between any two modules."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._channels: Dict[str, BridgeChannel] = {}
        return cls._instance

    def connect(self, source: str, target: str) -> BridgeChannel:
        key = f'{source}→{target}'
        if key not in self._channels:
            self._channels[key] = BridgeChannel(source, target)
            logger.debug(f'Bridge: connected {source} → {target}')
        return self._channels[key]

    def get(self, source: str, target: str) -> Optional[BridgeChannel]:
        return self._channels.get(f'{source}→{target}')

    def send(self, source: str, target: str, data: Dict, **kwargs) -> Dict:
        channel = self.connect(source, target)
        return channel.send(data, **kwargs)

    def disconnect(self, source: str, target: str):
        key = f'{source}→{target}'
        if key in self._channels:
            self._channels[key].close()
            del self._channels[key]

    def list_channels(self):
        return list(self._channels.keys())


bridge = Bridge()
