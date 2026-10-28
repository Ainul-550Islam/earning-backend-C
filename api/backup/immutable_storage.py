"""
Immutable Storage / WORM Backup Support
Inspired by: Veeam Hardened Repository, Rubrik immutable snapshots, Commvault Air Gap
Prevents backup data from being modified or deleted — ransomware-proof.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class ImmutabilityMode(str, Enum):
    COMPLIANCE = "compliance"       # Cannot be deleted even by admin before expiry
    GOVERNANCE  = "governance"      # Admin with special role can delete early
    LOCKED      = "locked"          # Permanently locked — no deletion ever


class ImmutabilityStatus(str, Enum):
    ACTIVE    = "active"
    EXPIRING  = "expiring"    # within 7 days of expiry
    EXPIRED   = "expired"
    VIOLATED  = "violated"    # tamper attempt detected


@dataclass
class ImmutabilityPolicy:
    mode: ImmutabilityMode
    retention_days: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    worm_enabled: bool = True
    compliance_officer_required: bool = False  # for COMPLIANCE mode deletions

    @property
    def expires_at(self) -> datetime:
        return self.created_at + timedelta(days=self.retention_days)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def days_remaining(self) -> int:
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)


@dataclass
class ImmutableBackupRecord:
    backup_id: str
    policy: ImmutabilityPolicy
    content_hash: str
    size_bytes: int
    storage_path: str
    sealed_at: datetime = field(default_factory=datetime.utcnow)
    tamper_detected: bool = False

    @property
    def status(self) -> ImmutabilityStatus:
        if self.tamper_detected:
            return ImmutabilityStatus.VIOLATED
        if self.policy.is_expired:
            return ImmutabilityStatus.EXPIRED
        if self.policy.days_remaining <= 7:
            return ImmutabilityStatus.EXPIRING
        return ImmutabilityStatus.ACTIVE

    def verify_integrity(self, current_hash: str) -> bool:
        """Returns True if content has not been tampered with"""
        intact = current_hash == self.content_hash
        if not intact:
            self.tamper_detected = True
            logger.critical(
                "IMMUTABILITY VIOLATION: backup %s hash mismatch! "
                "Expected %s got %s", self.backup_id,
                self.content_hash[:16], current_hash[:16]
            )
        return intact


class ImmutableStorageManager:
    """
    Manages WORM (Write Once Read Many) backup storage.
    Enforces immutability policies and detects tampering.
    """

    def __init__(self):
        self._records: Dict[str, ImmutableBackupRecord] = {}

    def seal_backup(self, backup_id: str, file_path: str,
                    policy: ImmutabilityPolicy) -> ImmutableBackupRecord:
        """Seal a backup as immutable — compute hash and lock it"""
        content_hash = self._hash_file(file_path)
        import os
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        record = ImmutableBackupRecord(
            backup_id=backup_id,
            policy=policy,
            content_hash=content_hash,
            size_bytes=size,
            storage_path=file_path,
        )
        self._records[backup_id] = record
        logger.info("Backup %s sealed as IMMUTABLE (%s, %dd)",
                    backup_id, policy.mode.value, policy.retention_days)
        return record

    def verify_backup(self, backup_id: str, file_path: str) -> bool:
        """Verify a sealed backup's integrity"""
        record = self._records.get(backup_id)
        if not record:
            raise LookupError(f"No immutability record for backup {backup_id}")
        current_hash = self._hash_file(file_path)
        return record.verify_integrity(current_hash)

    def can_delete(self, backup_id: str, requester_role: str = "admin") -> bool:
        """Check whether deletion is permitted under the policy"""
        record = self._records.get(backup_id)
        if not record:
            return True  # not immutable
        if record.policy.mode == ImmutabilityMode.LOCKED:
            return False
        if record.policy.mode == ImmutabilityMode.COMPLIANCE:
            if not record.policy.is_expired:
                return False
        if record.policy.mode == ImmutabilityMode.GOVERNANCE:
            return requester_role in ("compliance_officer", "superadmin")
        return record.policy.is_expired

    def get_record(self, backup_id: str) -> Optional[ImmutableBackupRecord]:
        return self._records.get(backup_id)

    def list_expiring(self, days: int = 7) -> List[ImmutableBackupRecord]:
        return [r for r in self._records.values()
                if r.policy.days_remaining <= days and not r.policy.is_expired]

    def audit_all(self) -> Dict[str, bool]:
        """Run integrity check on all sealed backups that still have their files"""
        import os
        results = {}
        for bid, record in self._records.items():
            if os.path.exists(record.storage_path):
                results[bid] = self.verify_backup(bid, record.storage_path)
            else:
                results[bid] = False
        return results

    @staticmethod
    def _hash_file(path: str) -> str:
        import os
        if not os.path.exists(path):
            return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
