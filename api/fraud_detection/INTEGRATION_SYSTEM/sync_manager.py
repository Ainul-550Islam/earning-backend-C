# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/sync_manager.py
# =============================================================================
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger('fraud_detection.sync')


class SyncStatus(Enum):
    PENDING    = 'pending'
    RUNNING    = 'running'
    COMPLETED  = 'completed'
    FAILED     = 'failed'
    CANCELLED  = 'cancelled'


@dataclass
class SyncOperation:
    operation_id : str = field(default_factory=lambda: str(uuid.uuid4()))
    name         : str = ''
    payload      : Dict[str, Any] = field(default_factory=dict)
    status       : SyncStatus = SyncStatus.PENDING
    created_at   : float = field(default_factory=time.time)
    started_at   : Optional[float] = None
    finished_at  : Optional[float] = None
    error        : Optional[str] = None
    result       : Any = None

    def to_dict(self) -> dict:
        return {
            'operation_id': self.operation_id,
            'name':         self.name,
            'status':       self.status.value,
            'created_at':   self.created_at,
            'started_at':   self.started_at,
            'finished_at':  self.finished_at,
            'error':        self.error,
        }


class SyncManager:
    def __init__(self):
        self._lock   = threading.Lock()
        self._ops    : Dict[str, SyncOperation] = {}
        self._handlers: Dict[str, Callable] = {}

    def register_handler(self, name: str, handler: Callable) -> None:
        self._handlers[name] = handler

    def create_operation(self, name: str, payload: Dict[str, Any]) -> SyncOperation:
        op = SyncOperation(name=name, payload=payload)
        with self._lock:
            self._ops[op.operation_id] = op
        return op

    def execute(self, op: SyncOperation) -> SyncOperation:
        handler = self._handlers.get(op.name)
        op.status     = SyncStatus.RUNNING
        op.started_at = time.time()
        try:
            if handler:
                op.result = handler(op.payload)
            op.status = SyncStatus.COMPLETED
        except Exception as exc:
            op.status = SyncStatus.FAILED
            op.error  = str(exc)
            logger.error('SyncOperation %s failed: %s', op.operation_id, exc)
        finally:
            op.finished_at = time.time()
        return op

    def get(self, operation_id: str) -> Optional[SyncOperation]:
        return self._ops.get(operation_id)

    def get_statistics(self) -> dict:
        with self._lock:
            ops = list(self._ops.values())
        from collections import Counter
        by_status = dict(Counter(o.status.value for o in ops).most_common())
        return {'total': len(ops), 'by_status': by_status}


_sm : SyncManager | None = None
_sm_lock = threading.Lock()


def get_sync_manager() -> SyncManager:
    global _sm
    if _sm is None:
        with _sm_lock:
            if _sm is None:
                _sm = SyncManager()
    return _sm


def create_sync_operation(name: str, payload: Dict[str, Any]) -> SyncOperation:
    return get_sync_manager().create_operation(name, payload)


def execute_sync(op: SyncOperation) -> SyncOperation:
    return get_sync_manager().execute(op)


def get_sync_statistics() -> dict:
    return get_sync_manager().get_statistics()
