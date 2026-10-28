"""
Continuous Data Protection (CDP)
Inspired by: Veeam Universal CDP, Zerto continuous replication
Achieves near-zero RPO by continuously journaling I/O changes.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CDPStatus(str, Enum):
    STOPPED    = "stopped"
    STARTING   = "starting"
    RUNNING    = "running"
    PAUSED     = "paused"
    ERROR      = "error"


@dataclass
class CDPJournalEntry:
    """A single journal write entry"""
    sequence_id: int
    timestamp: datetime
    data_offset: int
    data_length: int
    checksum: str
    volume_id: str


@dataclass
class CDPSession:
    """Active CDP replication session"""
    session_id: str
    source_volume: str
    target_location: str
    status: CDPStatus = CDPStatus.STOPPED
    started_at: Optional[datetime] = None
    journal: List[CDPJournalEntry] = field(default_factory=list)
    last_sync_at: Optional[datetime] = None
    rpo_seconds: int = 5        # near-zero — journal every N seconds
    bytes_replicated: int = 0

    @property
    def current_rpo_seconds(self) -> float:
        if not self.last_sync_at:
            return float("inf")
        return (datetime.utcnow() - self.last_sync_at).total_seconds()

    @property
    def is_rpo_met(self) -> bool:
        return self.current_rpo_seconds <= self.rpo_seconds

    def get_recovery_points(self, window_minutes: int = 60) -> List[datetime]:
        """Return available point-in-time recovery points within window"""
        cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)
        timestamps = sorted({e.timestamp for e in self.journal if e.timestamp >= cutoff})
        return timestamps


class CDPEngine:
    """Manages continuous data protection sessions"""

    def __init__(self):
        self._sessions: Dict[str, CDPSession] = {}
        self._seq = 0

    def create_session(self, source_volume: str, target_location: str,
                       rpo_seconds: int = 5) -> CDPSession:
        import uuid
        session = CDPSession(
            session_id=str(uuid.uuid4()),
            source_volume=source_volume,
            target_location=target_location,
            rpo_seconds=rpo_seconds,
        )
        self._sessions[session.session_id] = session
        logger.info("CDP session created: %s → %s", source_volume, target_location)
        return session

    def start(self, session_id: str) -> None:
        s = self._get(session_id)
        s.status = CDPStatus.RUNNING
        s.started_at = datetime.utcnow()
        logger.info("CDP started: %s", session_id)

    def pause(self, session_id: str) -> None:
        self._get(session_id).status = CDPStatus.PAUSED

    def stop(self, session_id: str) -> None:
        self._get(session_id).status = CDPStatus.STOPPED

    def record_write(self, session_id: str, offset: int, length: int,
                     volume_id: str, checksum: str) -> CDPJournalEntry:
        """Record an I/O write event to the CDP journal"""
        s = self._get(session_id)
        if s.status != CDPStatus.RUNNING:
            raise RuntimeError(f"CDP session {session_id} is not running")
        self._seq += 1
        entry = CDPJournalEntry(
            sequence_id=self._seq,
            timestamp=datetime.utcnow(),
            data_offset=offset,
            data_length=length,
            checksum=checksum,
            volume_id=volume_id,
        )
        s.journal.append(entry)
        s.bytes_replicated += length
        s.last_sync_at = entry.timestamp
        return entry

    def restore_to_point_in_time(self, session_id: str,
                                  target_time: datetime) -> Dict[str, Any]:
        """Select journal entries up to target_time for PIT restore"""
        s = self._get(session_id)
        entries = [e for e in s.journal if e.timestamp <= target_time]
        logger.info("CDP PIT restore: session=%s target=%s entries=%d",
                    session_id, target_time.isoformat(), len(entries))
        return {
            "session_id": session_id,
            "target_time": target_time.isoformat(),
            "journal_entries": len(entries),
            "bytes_to_apply": sum(e.data_length for e in entries),
        }

    def get_all_recovery_points(self, session_id: str) -> List[datetime]:
        return self._get(session_id).get_recovery_points()

    def _get(self, session_id: str) -> CDPSession:
        s = self._sessions.get(session_id)
        if not s:
            raise LookupError(f"CDP session {session_id} not found")
        return s
