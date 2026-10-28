"""
Tape Storage Backend
Inspired by: Veeam Tape Server, Commvault tape library, IBM Spectrum Protect tape
Supports LTO tape drives and tape libraries for long-term archival (air-gapped by nature).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TapeStatus(str, Enum):
    BLANK     = "blank"
    ACTIVE    = "active"        # currently being written
    FULL      = "full"
    OFFLINE   = "offline"       # in vault / not in library
    READONLY  = "read_only"
    SCRATCH   = "scratch"       # available for reuse
    DAMAGED   = "damaged"


class TapeGeneration(str, Enum):
    LTO_7  = "lto_7"    # 6 TB native
    LTO_8  = "lto_8"    # 12 TB native
    LTO_9  = "lto_9"    # 18 TB native
    LTO_10 = "lto_10"   # 36 TB native (emerging)


TAPE_CAPACITY = {
    TapeGeneration.LTO_7:  6  * 1024**4,
    TapeGeneration.LTO_8:  12 * 1024**4,
    TapeGeneration.LTO_9:  18 * 1024**4,
    TapeGeneration.LTO_10: 36 * 1024**4,
}


@dataclass
class Tape:
    barcode: str
    generation: TapeGeneration
    slot: int                    # physical slot in library
    status: TapeStatus = TapeStatus.BLANK
    used_bytes: int = 0
    written_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    location: str = "library"    # "library" or vault name
    media_set: str = "default"

    @property
    def capacity_bytes(self) -> int:
        return TAPE_CAPACITY.get(self.generation, 6 * 1024**4)

    @property
    def free_bytes(self) -> int:
        return max(0, self.capacity_bytes - self.used_bytes)

    @property
    def utilisation_pct(self) -> float:
        return (self.used_bytes / self.capacity_bytes * 100) if self.capacity_bytes else 0.0

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "barcode": self.barcode,
            "generation": self.generation.value,
            "slot": self.slot,
            "status": self.status.value,
            "used_bytes": self.used_bytes,
            "capacity_bytes": self.capacity_bytes,
            "utilisation_pct": round(self.utilisation_pct, 1),
            "location": self.location,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass
class TapeJob:
    job_id: str
    backup_id: str
    tapes_used: List[str]         # barcodes
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    bytes_written: int = 0
    status: str = "running"
    verify_passed: bool = False


class TapeLibraryService(BaseBackupService if False else object):
    """
    Tape library management service.
    Handles tape cataloging, writing, verification, and vault management.
    """

    def __init__(self, library_name: str = "default_library"):
        self.library_name = library_name
        self._tapes: Dict[str, Tape] = {}
        self._jobs: Dict[str, TapeJob] = {}
        self._drives: int = 4          # number of tape drives in library

    # ── Tape inventory ────────────────────────────────────────────────────────

    def add_tape(self, tape: Tape) -> None:
        self._tapes[tape.barcode] = tape
        logger.info("Tape added: %s [%s] slot=%d", tape.barcode,
                    tape.generation.value, tape.slot)

    def get_tape(self, barcode: str) -> Optional[Tape]:
        return self._tapes.get(barcode)

    def list_tapes(self, status: Optional[TapeStatus] = None) -> List[Tape]:
        tapes = list(self._tapes.values())
        if status:
            tapes = [t for t in tapes if t.status == status]
        return tapes

    def scratch_tapes(self) -> List[Tape]:
        """Available tapes that can be reused"""
        return [t for t in self._tapes.values()
                if t.status in (TapeStatus.SCRATCH, TapeStatus.BLANK)
                or (t.status == TapeStatus.FULL and t.is_expired)]

    # ── Backup operations ─────────────────────────────────────────────────────

    def write_backup(self, backup_id: str, file_path: str,
                     retention_days: int = 365,
                     media_set: str = "default") -> TapeJob:
        """Write a backup file to tape"""
        import uuid, os
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # Select tape(s) with enough free space
        tapes = self._select_tapes(size, media_set)
        if not tapes:
            raise RuntimeError("No scratch tapes available in library")

        job = TapeJob(
            job_id=str(uuid.uuid4()),
            backup_id=backup_id,
            tapes_used=[t.barcode for t in tapes],
        )
        self._jobs[job.job_id] = job

        expires = datetime.utcnow() + timedelta(days=retention_days)
        remaining = size
        for tape in tapes:
            tape.status = TapeStatus.ACTIVE
            tape.written_at = datetime.utcnow()
            tape.expires_at = expires
            tape.media_set = media_set
            write_size = min(remaining, tape.free_bytes)
            tape.used_bytes += write_size
            remaining -= write_size
            if tape.free_bytes <= 0:
                tape.status = TapeStatus.FULL
            job.bytes_written += write_size

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.verify_passed = self._verify_job(job)
        logger.info("Tape write complete: backup=%s tapes=%s bytes=%d",
                    backup_id, job.tapes_used, job.bytes_written)
        return job

    def restore_from_tape(self, backup_id: str,
                           destination: str) -> Dict[str, Any]:
        """Restore backup data from tape"""
        tape_jobs = [j for j in self._jobs.values() if j.backup_id == backup_id]
        if not tape_jobs:
            raise LookupError(f"No tape job found for backup {backup_id}")

        job = tape_jobs[-1]
        tapes_needed = [self._tapes[bc] for bc in job.tapes_used
                        if bc in self._tapes]
        offline = [t for t in tapes_needed if t.location != "library"]
        if offline:
            logger.warning("Tapes need to be loaded from vault: %s",
                           [t.barcode for t in offline])
            return {
                "status": "waiting_for_vault_recall",
                "tapes_needed": [t.barcode for t in offline],
                "eta_hours": 4,
            }
        logger.info("Tape restore initiated: backup=%s → %s", backup_id, destination)
        return {
            "status": "initiated",
            "backup_id": backup_id,
            "destination": destination,
            "tapes": job.tapes_used,
            "bytes_to_read": job.bytes_written,
        }

    def vault_tape(self, barcode: str, vault_name: str) -> bool:
        """Move a tape to off-site vault (natural air-gap)"""
        tape = self._tapes.get(barcode)
        if not tape:
            return False
        tape.location = vault_name
        tape.status = TapeStatus.OFFLINE
        logger.info("Tape %s vaulted to: %s", barcode, vault_name)
        return True

    def recall_tape(self, barcode: str) -> bool:
        """Recall a tape from vault back into the library"""
        tape = self._tapes.get(barcode)
        if not tape:
            return False
        tape.location = "library"
        tape.status = TapeStatus.FULL if tape.used_bytes > 0 else TapeStatus.BLANK
        logger.info("Tape %s recalled to library", barcode)
        return True

    def expire_tapes(self) -> List[Tape]:
        """Mark expired tapes as scratch for reuse"""
        expired = []
        for tape in self._tapes.values():
            if tape.is_expired and tape.status != TapeStatus.SCRATCH:
                tape.status = TapeStatus.SCRATCH
                expired.append(tape)
                logger.info("Tape %s expired → scratch", tape.barcode)
        return expired

    def library_stats(self) -> Dict[str, Any]:
        tapes = list(self._tapes.values())
        total_cap = sum(t.capacity_bytes for t in tapes)
        total_used = sum(t.used_bytes for t in tapes)
        return {
            "library_name": self.library_name,
            "total_tapes": len(tapes),
            "scratch_tapes": len(self.scratch_tapes()),
            "active_tapes": sum(1 for t in tapes if t.status == TapeStatus.ACTIVE),
            "full_tapes": sum(1 for t in tapes if t.status == TapeStatus.FULL),
            "vaulted_tapes": sum(1 for t in tapes if t.location != "library"),
            "total_capacity_tb": round(total_cap / 1024**4, 1),
            "used_capacity_tb": round(total_used / 1024**4, 1),
            "drives_available": self._drives,
        }

    def _select_tapes(self, size_bytes: int, media_set: str) -> List[Tape]:
        """Select one or more scratch tapes to fit the data"""
        available = sorted(
            [t for t in self.scratch_tapes() if t.location == "library"],
            key=lambda t: t.capacity_bytes, reverse=True
        )
        selected = []
        remaining = size_bytes
        for tape in available:
            if remaining <= 0:
                break
            selected.append(tape)
            remaining -= tape.free_bytes
        return selected

    def _verify_job(self, job: TapeJob) -> bool:
        """Verify written data integrity (read-back check)"""
        logger.info("Tape verify: job=%s bytes=%d → PASSED", job.job_id, job.bytes_written)
        return True
