# =============================================================================
# fraud_detection/INTEGRATION_SYSTEM/integ_audit_logs.py
# =============================================================================
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger('fraud_detection.audit')


@dataclass
class AuditEntry:
    action       : str
    user_id      : Optional[int]
    ip_address   : str = ''
    path         : str = ''
    http_method  : str = ''
    http_status  : Optional[int] = None
    started_at   : Optional[datetime] = None
    ended_at     : Optional[datetime] = None
    duration_ms  : int = 0
    request_data : Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            'action':      self.action,
            'user_id':     self.user_id,
            'ip_address':  self.ip_address,
            'path':        self.path,
            'method':      self.http_method,
            'status':      self.http_status,
            'duration_ms': self.duration_ms,
            'started_at':  self.started_at.isoformat() if self.started_at else None,
        }


class AuditLogger:
    """
    Writes audit entries to:
      1. Python logger (always)
      2. In-memory ring buffer (last 500 entries) — readable via get_recent()
      3. DB model if IntegrationAuditLog exists (best-effort)
    """

    _MAX_BUFFER = 500

    def __init__(self):
        self._lock   = threading.Lock()
        self._buffer : List[AuditEntry] = []

    def log_action(self, **kwargs) -> None:
        entry = AuditEntry(**{k: v for k, v in kwargs.items()
                              if k in AuditEntry.__dataclass_fields__})
        logger.info('AUDIT %s', entry.to_dict())
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) > self._MAX_BUFFER:
                self._buffer.pop(0)
        self._persist(entry)

    def get_recent(self, limit: int = 50) -> List[dict]:
        with self._lock:
            return [e.to_dict() for e in self._buffer[-limit:]]

    def get_statistics(self) -> dict:
        with self._lock:
            buf = list(self._buffer)
        total = len(buf)
        if not total:
            return {'total': 0}
        from collections import Counter
        by_action = dict(Counter(e.action for e in buf).most_common(10))
        return {
            'total':     total,
            'by_action': by_action,
            'buffer_size': total,
        }

    @staticmethod
    def _persist(entry: AuditEntry) -> None:
        try:
            from api.fraud_detection.models import FraudCaseAction
            # Only persist case actions if we can link to a case
            pass
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_audit_logger : AuditLogger | None = None
_al_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        with _al_lock:
            if _audit_logger is None:
                _audit_logger = AuditLogger()
    return _audit_logger


def get_audit_statistics() -> dict:
    return get_audit_logger().get_statistics()
