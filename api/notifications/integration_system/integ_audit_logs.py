# integration_system/integ_audit_logs.py
"""Audit Logs — Full audit trail for all integration events and data changes."""
import json, logging, threading, uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from django.utils import timezone
from .integ_constants import AuditAction
logger = logging.getLogger(__name__)

@dataclass
class AuditEntry:
    action: str
    module: str
    actor_id: Optional[int] = None
    actor_type: str = "system"
    target_type: str = ""
    target_id: str = ""
    data_before: Optional[Dict] = None
    data_after: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=timezone.now)
    success: bool = True
    error: str = ""

    def to_dict(self) -> Dict:
        return {
            "entry_id": self.entry_id, "action": self.action, "module": self.module,
            "actor_id": self.actor_id, "actor_type": self.actor_type,
            "target_type": self.target_type, "target_id": self.target_id,
            "metadata": self.metadata, "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "success": self.success, "error": self.error,
        }


PII_FIELDS = {'email', 'phone', 'password', 'token', 'secret', 'key',
              'ssn', 'credit_card', 'bank_account', 'ip_address', 'device_id'}

def mask_pii(data: dict) -> dict:
    """Replace PII field values with masked versions for GDPR compliance."""
    if not isinstance(data, dict):
        return data
    masked = {}
    for k, v in data.items():
        if any(pii in k.lower() for pii in PII_FIELDS):
            if isinstance(v, str) and len(v) > 4:
                masked[k] = v[:2] + '*' * (len(v) - 4) + v[-2:]
            else:
                masked[k] = '***'
        elif isinstance(v, dict):
            masked[k] = mask_pii(v)
        else:
            masked[k] = v
    return masked


class IntegrationAuditLogger:
    """Thread-safe audit logger with DB persistence and in-memory buffer."""

    BUFFER_SIZE = 500

    def __init__(self):
        self._buffer: List[AuditEntry] = []
        self._lock = threading.Lock()

    def log(self, action: str, module: str, actor_id: int = None,
            target_type: str = "", target_id: str = "",
            data_before: Dict = None, data_after: Dict = None,
            metadata: Dict = None, ip_address: str = "", success: bool = True,
            error: str = "") -> str:
        entry = AuditEntry(
            action=action, module=module, actor_id=actor_id,
            target_type=target_type, target_id=str(target_id),
            # data_before handled above with PII masking
            data_before=mask_pii(data_before) if data_before else None, data_before=mask_pii(data_before) if data_before else None,
            data_after=mask_pii(data_after) if data_after else None,
            metadata=metadata or {}, ip_address=ip_address,
            success=success, error=error,
        )
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self.BUFFER_SIZE:
                self._flush()
        self._persist_async(entry)
        return entry.entry_id

    def log_api_call(self, module: str, endpoint: str, method: str, status_code: int,
                     actor_id: int = None, ip_address: str = "") -> str:
        return self.log(
            action=AuditAction.API_CALL.value, module=module, actor_id=actor_id,
            target_type="endpoint", target_id=endpoint,
            metadata={"method": method, "status_code": status_code},
            ip_address=ip_address, success=200 <= status_code < 400,
        )

    def log_webhook(self, provider: str, event_type: str, payload: Dict,
                    success: bool = True, error: str = "") -> str:
        return self.log(
            action=AuditAction.WEBHOOK.value, module=provider,
            target_type="webhook_event", target_id=event_type,
            data_after=payload, success=success, error=error,
        )

    def log_integration_event(self, integration: str, action: str, data: Dict,
                               actor_id: int = None, success: bool = True) -> str:
        return self.log(
            action=action, module=integration, actor_id=actor_id,
            target_type="integration", target_id=integration,
            data_after=data, success=success,
        )

    def _persist_async(self, entry: AuditEntry):
        try:
            from .tasks import persist_audit_log_task
            persist_audit_log_task.apply_async(args=[entry.to_dict()], queue="maintenance")
        except Exception:
            logger.debug(f"AuditLogger: async persist failed, keeping in buffer")

    def _flush(self):
        flushed = list(self._buffer)
        self._buffer.clear()
        logger.debug(f"AuditLogger: flushed {len(flushed)} entries")

    def get_buffer(self) -> List[Dict]:
        with self._lock:
            return [e.to_dict() for e in self._buffer]

    def query(self, module: str = None, actor_id: int = None,
              action: str = None, limit: int = 100) -> List[Dict]:
        results = list(self._buffer)
        if module:
            results = [e for e in results if e.module == module]
        if actor_id:
            results = [e for e in results if e.actor_id == actor_id]
        if action:
            results = [e for e in results if e.action == action]
        return [e.to_dict() for e in results[-limit:]]


audit_logger = IntegrationAuditLogger()
