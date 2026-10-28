"""
Instant Recovery
Inspired by: Veeam Instant VM Recovery, Cohesity Instant Mass Restore
Mounts backup directly from storage — system is live in seconds, not hours.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InstantRecoveryStatus(str, Enum):
    MOUNTING   = "mounting"
    LIVE       = "live"         # VM/service running from backup
    MIGRATING  = "migrating"    # Data being copied to production storage
    COMPLETED  = "completed"    # Migration done, backup unmounted
    FAILED     = "failed"


class RecoveryScope(str, Enum):
    FULL_VM    = "full_vm"
    DATABASE   = "database"
    FILE       = "file"
    APPLICATION= "application"
    MASS       = "mass"         # Cohesity-style mass VM recovery


@dataclass
class InstantRecoverySession:
    session_id: str
    backup_id: str
    scope: RecoveryScope
    mount_point: str
    status: InstantRecoveryStatus = InstantRecoveryStatus.MOUNTING
    started_at: datetime = field(default_factory=datetime.utcnow)
    live_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    target_host: Optional[str] = None
    migration_progress_pct: float = 0.0

    @property
    def time_to_live_seconds(self) -> Optional[float]:
        if not self.live_at:
            return None
        return (self.live_at - self.started_at).total_seconds()

    @property
    def is_live(self) -> bool:
        return self.status == InstantRecoveryStatus.LIVE


class InstantRecoveryManager:
    """
    Manages instant recovery sessions.
    Mounts backup storage directly so workloads are immediately available.
    Migration to production storage happens in the background.
    """

    def __init__(self):
        self._sessions: Dict[str, InstantRecoverySession] = {}

    def start_recovery(self, backup_id: str, scope: RecoveryScope,
                        target_host: str, mount_point: str) -> InstantRecoverySession:
        import uuid
        session = InstantRecoverySession(
            session_id=str(uuid.uuid4()),
            backup_id=backup_id,
            scope=scope,
            mount_point=mount_point,
            target_host=target_host,
        )
        self._sessions[session.session_id] = session
        self._do_mount(session)
        return session

    def _do_mount(self, session: InstantRecoverySession) -> None:
        """Mount backup as live storage — in production hooks into hypervisor API"""
        session.status = InstantRecoveryStatus.LIVE
        session.live_at = datetime.utcnow()
        logger.info(
            "Instant recovery LIVE: backup=%s scope=%s mount=%s ttl=%.1fs",
            session.backup_id, session.scope.value,
            session.mount_point,
            session.time_to_live_seconds or 0,
        )

    def start_migration(self, session_id: str) -> None:
        """Begin migrating data from backup storage to production storage"""
        session = self._get(session_id)
        session.status = InstantRecoveryStatus.MIGRATING
        logger.info("Migration started for session %s", session_id)

    def update_migration_progress(self, session_id: str, pct: float) -> None:
        self._get(session_id).migration_progress_pct = min(100.0, pct)

    def complete_recovery(self, session_id: str) -> None:
        session = self._get(session_id)
        session.status = InstantRecoveryStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        logger.info("Instant recovery completed: %s", session_id)

    def list_live_sessions(self) -> List[InstantRecoverySession]:
        return [s for s in self._sessions.values() if s.is_live]

    def get_session(self, session_id: str) -> Optional[InstantRecoverySession]:
        return self._sessions.get(session_id)

    def _get(self, session_id: str) -> InstantRecoverySession:
        s = self._sessions.get(session_id)
        if not s:
            raise LookupError(f"Recovery session {session_id} not found")
        return s
