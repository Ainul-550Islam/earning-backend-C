# integration_system/sync_manager.py
"""Sync Manager — Data conflict resolver for cross-module data synchronization."""
import logging, threading, uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from django.utils import timezone
from .integ_constants import SyncStrategy
from .integ_exceptions import SyncConflict
logger = logging.getLogger(__name__)

@dataclass
class SyncRecord:
    record_id: str
    source_module: str
    target_module: str
    data: Dict
    strategy: SyncStrategy = SyncStrategy.LATEST_WINS
    sync_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=timezone.now)
    resolved_at: Optional[datetime] = None
    conflict: bool = False
    conflict_fields: List[str] = field(default_factory=list)
    resolution: str = ""

    def to_dict(self) -> Dict:
        return {
            "sync_id": self.sync_id, "record_id": self.record_id,
            "source_module": self.source_module, "target_module": self.target_module,
            "strategy": self.strategy.value, "conflict": self.conflict,
            "conflict_fields": self.conflict_fields, "resolution": self.resolution,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class SyncManager:
    """Manages cross-module data synchronization with conflict resolution."""

    def __init__(self):
        self._pending: List[SyncRecord] = []
        self._resolved: List[SyncRecord] = []
        self._lock = threading.Lock()
        self._custom_resolvers: Dict[str, Callable] = {}

    def register_resolver(self, source: str, target: str, resolver: Callable):
        self._custom_resolvers[f"{source}→{target}"] = resolver

    def sync(self, source_module: str, target_module: str, record_id: str,
             source_data: Dict, target_data: Optional[Dict] = None,
             strategy: SyncStrategy = SyncStrategy.LATEST_WINS) -> Tuple[Dict, bool]:
        """Sync data from source to target, resolving conflicts."""
        if not target_data:
            return source_data, False
        conflicts = self._detect_conflicts(source_data, target_data)
        if not conflicts:
            return source_data, False
        record = SyncRecord(
            record_id=record_id, source_module=source_module, target_module=target_module,
            data=source_data, strategy=strategy, conflict=True, conflict_fields=conflicts,
        )
        resolved_data = self._resolve(source_data, target_data, conflicts, strategy, source_module, target_module)
        record.resolved_at = timezone.now()
        record.resolution = strategy.value
        with self._lock:
            self._resolved.append(record)
        logger.info(f"SyncManager: resolved {len(conflicts)} conflicts for {source_module}→{target_module} [{strategy.value}]")
        return resolved_data, True

    def _detect_conflicts(self, source: Dict, target: Dict) -> List[str]:
        conflicts = []
        for key in source:
            if key in target and source[key] != target[key]:
                # Skip timestamps — handled by strategy
                if key not in ("updated_at", "created_at", "last_modified"):
                    conflicts.append(key)
        return conflicts

    def _resolve(self, source: Dict, target: Dict, conflicts: List[str],
                 strategy: SyncStrategy, src_mod: str, tgt_mod: str) -> Dict:
        key = f"{src_mod}→{tgt_mod}"
        if key in self._custom_resolvers:
            return self._custom_resolvers[key](source, target, conflicts)

        if strategy == SyncStrategy.LATEST_WINS:
            src_ts = source.get("updated_at", "")
            tgt_ts = target.get("updated_at", "")
            return source if src_ts >= tgt_ts else target

        elif strategy == SyncStrategy.SOURCE_WINS:
            return {**target, **source}

        elif strategy == SyncStrategy.TARGET_WINS:
            return {**source, **target}

        elif strategy == SyncStrategy.MERGE:
            merged = {**target}
            for k, v in source.items():
                if k not in conflicts:
                    merged[k] = v
            return merged

        elif strategy == SyncStrategy.MANUAL_REVIEW:
            logger.warning(f"SyncManager: manual review required for {key} fields={conflicts}")
            return target  # Keep target until reviewed

        return source

    def get_pending_conflicts(self) -> List[Dict]:
        return [r.to_dict() for r in self._pending]

    def get_sync_stats(self) -> Dict:
        with self._lock:
            total = len(self._resolved)
            conflicts = sum(1 for r in self._resolved if r.conflict)
        return {"total_syncs": total, "conflicts_resolved": conflicts, "pending": len(self._pending)}


sync_manager = SyncManager()
