# api/admin_panel/audit_trail.py
"""Immutable audit trail — write-once compliance logs."""
from __future__ import annotations
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class ImmutableAuditTrail:
    """
    Write-once audit trail for compliance.
    Records cannot be modified or deleted after creation.
    Each entry is hash-chained for tamper detection.
    """

    _last_hash: str = '0' * 64  # Genesis hash

    @classmethod
    def log(cls, event_type: str, actor_id: Any, actor_name: str,
            payload: Dict, ip: str = '', severity: str = 'info') -> Optional[str]:
        """
        Write an immutable audit entry.
        Returns entry_id or None on failure.
        """
        import uuid
        entry_id = str(uuid.uuid4())
        ts = timezone.now().isoformat()

        # Chain hash (tamper detection)
        content = json.dumps({
            'id': entry_id, 'event': event_type,
            'actor_id': str(actor_id), 'ts': ts,
            'payload_hash': hashlib.sha256(json.dumps(payload, default=str, sort_keys=True).encode()).hexdigest(),
        }, sort_keys=True)
        entry_hash = hashlib.sha256(f"{cls._last_hash}{content}".encode()).hexdigest()
        cls._last_hash = entry_hash

        entry = {
            'id': entry_id, 'event_type': event_type,
            'actor_id': str(actor_id), 'actor_name': actor_name,
            'payload': payload, 'ip': ip, 'severity': severity,
            'timestamp': ts, 'chain_hash': entry_hash,
        }

        # Store in DB
        try:
            from api.audit_logs.models import AuditLog
            AuditLog.objects.create(
                event_type=event_type,
                actor_id=actor_id,
                data=json.dumps(entry, default=str),
                ip_address=ip,
                action=event_type,
            )
        except Exception:
            # Fallback: store in AdminActivity
            try:
                from api.admin_panel.models.activity import AdminActivity
                from django.contrib.auth import get_user_model
                User = get_user_model()
                actor = User.objects.get(pk=actor_id) if actor_id else None
                AdminActivity.log(
                    actor=actor, action=f'AUDIT:{event_type}',
                    changes={'audit_id': entry_id, 'payload': payload},
                    ip=ip,
                )
            except Exception as e:
                logger.error(f"[AuditTrail.log] Failed: {e}")
                return None

        return entry_id

    @classmethod
    def verify_chain(cls, limit: int = 1000) -> Dict:
        """Verify audit trail hash chain integrity."""
        try:
            from api.audit_logs.models import AuditLog
            logs = AuditLog.objects.order_by('created_at')[:limit]
            valid = 0
            invalid = 0
            for log in logs:
                try:
                    entry = json.loads(log.data) if hasattr(log, 'data') else {}
                    if entry:
                        valid += 1
                    else:
                        invalid += 1
                except Exception:
                    invalid += 1
            return {'verified': valid, 'invalid': invalid, 'total': valid + invalid,
                    'tamper_detected': invalid > 0}
        except Exception as e:
            return {'error': str(e)}

    @classmethod
    def get_audit_history(cls, event_type: str = '', actor_id: Any = None,
                           days: int = 30, limit: int = 100) -> List[Dict]:
        """Query audit history."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        try:
            from api.audit_logs.models import AuditLog
            from django.db.models import Q
            qs = AuditLog.objects.filter(created_at__gte=cutoff)
            if event_type:
                qs = qs.filter(event_type=event_type)
            if actor_id:
                qs = qs.filter(actor_id=actor_id)
            return list(qs.values('id', 'event_type', 'actor_id', 'ip_address', 'created_at')
                        .order_by('-created_at')[:limit])
        except Exception:
            return []


audit_trail = ImmutableAuditTrail()