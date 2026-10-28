"""
Forensic Backup
Inspired by: Acronis Forensic Backup, eDiscovery capabilities
Creates forensically sound, tamper-evident backup images with chain of custody.
Used for legal investigations, incident response, and compliance audits.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ForensicImageType(str, Enum):
    DISK_IMAGE    = "disk_image"    # Full raw disk image (dd-style)
    MEMORY_DUMP   = "memory_dump"   # Live RAM capture
    FILE_SYSTEM   = "file_system"   # File-level forensic copy
    DATABASE      = "database"      # Consistent DB snapshot
    LOG_ARCHIVE   = "log_archive"   # Security/audit log preservation


class ChainOfCustodyEvent(str, Enum):
    CREATED      = "created"
    ACCESSED     = "accessed"
    TRANSFERRED  = "transferred"
    VERIFIED     = "verified"
    PRESENTED    = "presented"
    DESTROYED    = "destroyed"


@dataclass
class ChainOfCustodyEntry:
    event: ChainOfCustodyEvent
    actor: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    location: str = ""
    purpose: str = ""
    signature: str = ""    # Digital signature of the actor
    notes: str = ""


@dataclass
class ForensicMetadata:
    """Metadata embedded in every forensic backup for legal admissibility"""
    case_id: str
    examiner_name: str
    examiner_badge: str
    acquisition_start: datetime
    acquisition_end: Optional[datetime] = None
    source_device: str = ""
    source_serial: str = ""
    tool_name: str = "BackupSystem Forensic Module"
    tool_version: str = "1.0.0"
    hash_algorithm: str = "SHA-256"
    source_hash: str = ""     # hash of original
    image_hash: str = ""      # hash of forensic copy
    notes: str = ""

    @property
    def is_verified(self) -> bool:
        return bool(self.source_hash and self.image_hash and
                    self.source_hash == self.image_hash)


@dataclass
class ForensicBackupRecord:
    record_id: str
    image_type: ForensicImageType
    metadata: ForensicMetadata
    storage_path: str
    size_bytes: int = 0
    is_encrypted: bool = True
    is_compressed: bool = False
    chain_of_custody: List[ChainOfCustodyEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def add_custody_event(self, event: ChainOfCustodyEvent, actor: str,
                           purpose: str = "", notes: str = "") -> ChainOfCustodyEntry:
        entry = ChainOfCustodyEntry(
            event=event,
            actor=actor,
            purpose=purpose,
            notes=notes,
        )
        self.chain_of_custody.append(entry)
        return entry

    def export_chain(self) -> List[Dict[str, Any]]:
        return [
            {
                "event": e.event.value,
                "actor": e.actor,
                "timestamp": e.timestamp.isoformat(),
                "location": e.location,
                "purpose": e.purpose,
                "notes": e.notes,
            }
            for e in self.chain_of_custody
        ]

    def to_evidence_manifest(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "case_id": self.metadata.case_id,
            "image_type": self.image_type.value,
            "examiner": self.metadata.examiner_name,
            "acquired": self.metadata.acquisition_start.isoformat(),
            "source_hash": self.metadata.source_hash,
            "image_hash": self.metadata.image_hash,
            "integrity_verified": self.metadata.is_verified,
            "size_bytes": self.size_bytes,
            "chain_of_custody": self.export_chain(),
        }


class ForensicAcquisitionEngine:
    """
    Creates forensically sound backup images with integrity verification.
    Follows NIST/ACPO forensic acquisition guidelines.
    """

    def __init__(self):
        self._records: Dict[str, ForensicBackupRecord] = {}

    def acquire(self, source_path: str, dest_path: str,
                metadata: ForensicMetadata,
                image_type: ForensicImageType = ForensicImageType.FILE_SYSTEM,
                encrypt: bool = True) -> ForensicBackupRecord:
        """
        Acquire a forensic image of source_path to dest_path.
        Computes source hash before copying, image hash after, verifies match.
        """
        import uuid, shutil

        record_id = str(uuid.uuid4())
        metadata.acquisition_start = datetime.utcnow()

        logger.info("Forensic acquisition started: case=%s source=%s",
                    metadata.case_id, source_path)

        # 1. Hash source before acquisition
        if os.path.exists(source_path):
            metadata.source_hash = self._hash_path(source_path)
            # 2. Copy to destination
            if os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(source_path, dest_path)
            # 3. Hash destination
            metadata.image_hash = self._hash_path(dest_path)
            size = (os.path.getsize(dest_path) if os.path.isfile(dest_path)
                    else self._dir_size(dest_path))
        else:
            metadata.source_hash = ""
            metadata.image_hash = ""
            size = 0

        metadata.acquisition_end = datetime.utcnow()

        record = ForensicBackupRecord(
            record_id=record_id,
            image_type=image_type,
            metadata=metadata,
            storage_path=dest_path,
            size_bytes=size,
            is_encrypted=encrypt,
        )

        # Initial chain-of-custody entry
        record.add_custody_event(
            ChainOfCustodyEvent.CREATED,
            actor=metadata.examiner_name,
            purpose=f"Forensic acquisition for case {metadata.case_id}",
        )

        self._records[record_id] = record

        if metadata.is_verified:
            logger.info("Forensic acquisition VERIFIED: record=%s hash=%s...",
                        record_id, metadata.image_hash[:16])
        else:
            logger.error("Forensic acquisition INTEGRITY FAILURE: record=%s", record_id)

        return record

    def verify_integrity(self, record_id: str) -> bool:
        """Re-verify the forensic image against its stored hash"""
        record = self._records.get(record_id)
        if not record:
            raise LookupError(f"Forensic record {record_id} not found")
        current_hash = self._hash_path(record.storage_path)
        intact = current_hash == record.metadata.image_hash
        record.add_custody_event(
            ChainOfCustodyEvent.VERIFIED,
            actor="system",
            notes=f"Integrity {'PASSED' if intact else 'FAILED'}",
        )
        return intact

    def transfer_custody(self, record_id: str, from_actor: str,
                          to_actor: str, purpose: str) -> None:
        record = self._records.get(record_id)
        if not record:
            raise LookupError(f"Forensic record {record_id} not found")
        record.add_custody_event(
            ChainOfCustodyEvent.TRANSFERRED,
            actor=f"{from_actor} → {to_actor}",
            purpose=purpose,
        )

    def export_manifest(self, record_id: str) -> Dict[str, Any]:
        record = self._records.get(record_id)
        if not record:
            raise LookupError(f"Forensic record {record_id} not found")
        return record.to_evidence_manifest()

    def list_by_case(self, case_id: str) -> List[ForensicBackupRecord]:
        return [r for r in self._records.values()
                if r.metadata.case_id == case_id]

    @staticmethod
    def _hash_path(path: str) -> str:
        h = hashlib.sha256()
        if os.path.isfile(path):
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for fname in sorted(files):
                    fpath = os.path.join(root, fname)
                    with open(fpath, "rb") as f:
                        for chunk in iter(lambda: f.read(65536), b""):
                            h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _dir_size(path: str) -> int:
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        return total
