# api/promotions/auditing/transaction_audit.py
# Transaction Audit — Every financial transaction immutable log করে
import hashlib, json, logging, time
from dataclasses import dataclass, field
from decimal import Decimal
from django.core.cache import cache
logger = logging.getLogger('auditing.transaction')

@dataclass
class AuditEntry:
    entity_type:   str         # 'transaction', 'campaign', 'user', 'payout'
    entity_id:     int
    action:        str         # 'create', 'update', 'delete', 'approve', 'reject'
    actor_id:      int         # Who did it
    before_state:  dict
    after_state:   dict
    metadata:      dict        = field(default_factory=dict)
    timestamp:     float       = field(default_factory=time.time)
    hash:          str         = ''

    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = json.dumps({
            'entity_type': self.entity_type, 'entity_id': self.entity_id,
            'action': self.action, 'actor_id': self.actor_id,
            'before': self.before_state, 'after': self.after_state,
            'timestamp': self.timestamp,
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

class TransactionAuditor:
    """
    Immutable financial audit trail.
    Each entry hashed (SHA-256) — tamper detection.
    Append-only — no updates or deletes.
    """
    def log(self, entry: AuditEntry) -> str:
        try:
            from api.promotions.models import AuditLog
            AuditLog.objects.create(
                entity_type=entry.entity_type, entity_id=entry.entity_id,
                action=entry.action, actor_id=entry.actor_id,
                before_state=entry.before_state, after_state=entry.after_state,
                entry_hash=entry.hash, metadata=entry.metadata,
            )
            logger.info(f'Audit: {entry.entity_type}#{entry.entity_id} {entry.action} by user#{entry.actor_id}')
        except Exception as e:
            logger.error(f'Audit log failed: {e}')
            # Buffer in Redis fallback
            buf = cache.get('audit:buffer') or []
            buf.append(entry.__dict__)
            cache.set('audit:buffer', buf[-1000:], timeout=86400)
        return entry.hash

    def log_transaction(self, tx_id: int, actor_id: int, before: dict, after: dict, action: str = 'update') -> str:
        return self.log(AuditEntry('transaction', tx_id, action, actor_id, before, after))

    def log_payout(self, payout_id: int, actor_id: int, amount: Decimal, status: str) -> str:
        return self.log(AuditEntry('payout', payout_id, 'process', actor_id, {}, {'amount': str(amount), 'status': status}))

    def verify_integrity(self, entity_type: str, entity_id: int) -> dict:
        """Audit trail integrity verify করে।"""
        try:
            from api.promotions.models import AuditLog
            entries = list(AuditLog.objects.filter(entity_type=entity_type, entity_id=entity_id).order_by('created_at'))
            invalid = []
            for e in entries:
                computed = AuditEntry(
                    e.entity_type, e.entity_id, e.action, e.actor_id,
                    e.before_state, e.after_state, e.metadata, e.created_at.timestamp()
                )._compute_hash()
                if computed != e.entry_hash:
                    invalid.append(e.id)
            return {'total': len(entries), 'invalid': invalid, 'integrity': len(invalid) == 0}
        except Exception as e:
            return {'error': str(e)}

    def get_history(self, entity_type: str, entity_id: int, limit: int = 50) -> list:
        try:
            from api.promotions.models import AuditLog
            return list(AuditLog.objects.filter(entity_type=entity_type, entity_id=entity_id)
                        .order_by('-created_at').values()[:limit])
        except Exception:
            return []
