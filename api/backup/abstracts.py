"""
Backup Module Abstract Base Classes
Defines interfaces and abstract contracts for backup services and handlers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, BinaryIO
from datetime import datetime


class AbstractBackupService(ABC):
    """Contract all backup storage services must implement"""

    @abstractmethod
    def upload_file(self, file_obj: BinaryIO, filename: str) -> Dict[str, Any]:
        """Upload a backup file to the storage backend"""
        raise NotImplementedError

    @abstractmethod
    def download_file(self, filename: str, destination: str) -> bool:
        """Download a backup file from the storage backend"""
        raise NotImplementedError

    @abstractmethod
    def delete_backup(self, filename: str) -> bool:
        """Delete a backup file from storage"""
        raise NotImplementedError

    @abstractmethod
    def list_backups(self) -> List[Dict[str, Any]]:
        """Return a list of all backups in storage"""
        raise NotImplementedError

    @abstractmethod
    def get_backup_metadata(self, filename: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a specific backup"""
        raise NotImplementedError

    def health_check(self) -> bool:
        """Check connectivity to the storage backend"""
        try:
            self.list_backups()
            return True
        except Exception:
            return False


class AbstractNotificationService(ABC):
    """Contract for all notification backends"""

    @abstractmethod
    def send_email(self, recipients: List[str], subject: str, body: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def send_webhook(self, url: str, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def send_slack(self, webhook_url: str, message: str) -> bool:
        """Default: delegate to send_webhook"""
        return self.send_webhook(webhook_url, {"text": message})


class AbstractEncryptionService(ABC):
    """Contract for encryption/decryption services"""

    @abstractmethod
    def encrypt(self, data: bytes) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def decrypt(self, data: bytes) -> bytes:
        raise NotImplementedError

    def encrypt_file(self, src: str, dst: str) -> None:
        with open(src, "rb") as f:
            plaintext = f.read()
        ciphertext = self.encrypt(plaintext)
        with open(dst, "wb") as f:
            f.write(ciphertext)

    def decrypt_file(self, src: str, dst: str) -> None:
        with open(src, "rb") as f:
            ciphertext = f.read()
        plaintext = self.decrypt(ciphertext)
        with open(dst, "wb") as f:
            f.write(plaintext)


class AbstractCompressionService(ABC):
    """Contract for compression services"""

    @abstractmethod
    def compress(self, src: str, dst: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def decompress(self, src: str, dst: str) -> None:
        raise NotImplementedError

    def get_compression_ratio(self, original: str, compressed: str) -> float:
        import os
        orig_size = os.path.getsize(original)
        comp_size = os.path.getsize(compressed)
        if comp_size == 0:
            return 0.0
        return orig_size / comp_size


class AbstractBackupScheduler(ABC):
    """Contract for scheduling backends"""

    @abstractmethod
    def schedule_backup(self, schedule_id: str, cron_expression: str, config: Dict[str, Any]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def cancel_schedule(self, schedule_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_schedules(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def get_next_run_time(self, cron_expression: str) -> Optional[datetime]:
        raise NotImplementedError


class AbstractAuditLogger(ABC):
    """Contract for audit logging"""

    @abstractmethod
    def log_action(self, action: str, user_id: Optional[str], resource_id: str,
                   metadata: Optional[Dict] = None) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_audit_trail(self, resource_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
