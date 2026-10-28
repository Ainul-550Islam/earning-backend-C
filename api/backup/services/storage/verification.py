"""
Backup Verification Module
Provides SHA-256 checksum verification and integrity checking for backup files.
"""

import logging
import hashlib
import os
from typing import Dict, Any, Optional, BinaryIO, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of backup verification."""
    is_valid: bool
    expected_checksum: str
    actual_checksum: str
    algorithm: str
    file_size: int
    verification_time: datetime
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert verification result to dictionary."""
        return {
            'is_valid': self.is_valid,
            'expected_checksum': self.expected_checksum,
            'actual_checksum': self.actual_checksum,
            'algorithm': self.algorithm,
            'file_size': self.file_size,
            'verification_time': self.verification_time.isoformat(),
            'error_message': self.error_message
        }


@dataclass
class BackupIntegrity:
    """Integrity information for a backup."""
    backup_id: str
    checksum: str
    algorithm: str
    file_size: int
    created_at: datetime
    verified_at: Optional[datetime] = None
    verification_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert integrity info to dictionary."""
        return {
            'backup_id': self.backup_id,
            'checksum': self.checksum,
            'algorithm': self.algorithm,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat(),
            'verified_at': self.verified_at.isoformat() if self.verified_at else None,
            'verification_count': self.verification_count
        }


class BackupVerifier:
    """
    Verifies backup file integrity using checksums.
    Provides pre-restoration verification and ongoing integrity monitoring.
    """
    
    def __init__(self):
        """Initialize backup verifier."""
        self.supported_algorithms = ['sha256', 'sha512', 'md5', 'sha1']
        logger.info("Backup verifier initialized")
    
    def calculate_checksum(self, file_obj: BinaryIO, algorithm: str = 'sha256', 
                        chunk_size: int = 8192) -> str:
        """
        Calculate checksum of a file object.
        
        Args:
            file_obj: File-like object to calculate checksum for
            algorithm: Hash algorithm to use (sha256, sha512, md5, sha1)
            chunk_size: Size of chunks to read
            
        Returns:
            str: Hexadecimal checksum
        """
        if algorithm not in self.supported_algorithms:
            raise ValueError(f"Unsupported algorithm: {algorithm}. Supported: {self.supported_algorithms}")
        
        # Get appropriate hash algorithm
        if algorithm == 'sha256':
            hash_obj = hashlib.sha256()
        elif algorithm == 'sha512':
            hash_obj = hashlib.sha512()
        elif algorithm == 'md5':
            hash_obj = hashlib.md5()
        elif algorithm == 'sha1':
            hash_obj = hashlib.sha1()
        
        # Calculate hash in chunks to handle large files
        current_pos = file_obj.tell()
        file_obj.seek(0)
        
        try:
            while True:
                chunk = file_obj.read(chunk_size)
                if not chunk:
                    break
                hash_obj.update(chunk)
            
            return hash_obj.hexdigest()
        finally:
            file_obj.seek(current_pos)  # Reset file position
    
    def verify_backup_checksum(self, file_obj: BinaryIO, expected_checksum: str, 
                             algorithm: str = 'sha256') -> VerificationResult:
        """
        Verify backup file against expected checksum.
        
        Args:
            file_obj: File-like object to verify
            expected_checksum: Expected checksum value
            algorithm: Hash algorithm used
            
        Returns:
            VerificationResult: Verification result
        """
        try:
            # Calculate actual checksum
            actual_checksum = self.calculate_checksum(file_obj, algorithm)
            
            # Get file size
            current_pos = file_obj.tell()
            file_obj.seek(0, 2)  # Seek to end
            file_size = file_obj.tell()
            file_obj.seek(current_pos)  # Reset position
            
            # Compare checksums
            is_valid = actual_checksum.lower() == expected_checksum.lower()
            
            result = VerificationResult(
                is_valid=is_valid,
                expected_checksum=expected_checksum,
                actual_checksum=actual_checksum,
                algorithm=algorithm,
                file_size=file_size,
                verification_time=datetime.now()
            )
            
            logger.info(f"Checksum verification {'passed' if is_valid else 'failed'} for {algorithm}")
            return result
            
        except Exception as e:
            logger.error(f"Checksum verification failed: {e}")
            return VerificationResult(
                is_valid=False,
                expected_checksum=expected_checksum,
                actual_checksum="",
                algorithm=algorithm,
                file_size=0,
                verification_time=datetime.now(),
                error_message=str(e)
            )
    
    def verify_backup_file(self, file_path: str, expected_checksum: str, 
                         algorithm: str = 'sha256') -> VerificationResult:
        """
        Verify backup file against expected checksum.
        
        Args:
            file_path: Path to backup file
            expected_checksum: Expected checksum value
            algorithm: Hash algorithm used
            
        Returns:
            VerificationResult: Verification result
        """
        try:
            with open(file_path, 'rb') as file_obj:
                return self.verify_backup_checksum(file_obj, expected_checksum, algorithm)
        except Exception as e:
            logger.error(f"Failed to verify backup file {file_path}: {e}")
            return VerificationResult(
                is_valid=False,
                expected_checksum=expected_checksum,
                actual_checksum="",
                algorithm=algorithm,
                file_size=0,
                verification_time=datetime.now(),
                error_message=f"File access error: {str(e)}"
            )
    
    def create_backup_integrity(self, file_obj: BinaryIO, backup_id: str, 
                             algorithm: str = 'sha256') -> BackupIntegrity:
        """
        Create integrity record for a backup.
        
        Args:
            file_obj: File-like object for backup
            backup_id: Unique backup identifier
            algorithm: Hash algorithm to use
            
        Returns:
            BackupIntegrity: Integrity information
        """
        try:
            # Calculate checksum
            checksum = self.calculate_checksum(file_obj, algorithm)
            
            # Get file size
            current_pos = file_obj.tell()
            file_obj.seek(0, 2)
            file_size = file_obj.tell()
            file_obj.seek(current_pos)
            
            integrity = BackupIntegrity(
                backup_id=backup_id,
                checksum=checksum,
                algorithm=algorithm,
                file_size=file_size,
                created_at=datetime.now()
            )
            
            logger.info(f"Created integrity record for backup {backup_id}")
            return integrity
            
        except Exception as e:
            logger.error(f"Failed to create integrity record: {e}")
            raise
    
    def verify_before_restoration(self, storage_adapter, backup, expected_checksum: str = None,
                               algorithm: str = 'sha256') -> Tuple[bool, VerificationResult]:
        """
        Verify backup before attempting restoration.
        
        Args:
            storage_adapter: Storage adapter to retrieve backup from
            backup: Backup model instance
            expected_checksum: Expected checksum (optional, will use backup.checksum if None)
            algorithm: Hash algorithm to use
            
        Returns:
            Tuple[bool, VerificationResult]: (is_verified, verification_result)
        """
        try:
            # Get expected checksum
            if not expected_checksum:
                expected_checksum = getattr(backup, 'checksum', None)
            
            if not expected_checksum:
                logger.error("No checksum available for verification")
                return False, VerificationResult(
                    is_valid=False,
                    expected_checksum="",
                    actual_checksum="",
                    algorithm=algorithm,
                    file_size=0,
                    verification_time=datetime.now(),
                    error_message="No checksum available for verification"
                )
            
            # Retrieve backup file
            file_obj = storage_adapter.retrieve_backup(backup)
            if not file_obj:
                logger.error(f"Failed to retrieve backup {backup.backup_id}")
                return False, VerificationResult(
                    is_valid=False,
                    expected_checksum=expected_checksum,
                    actual_checksum="",
                    algorithm=algorithm,
                    file_size=0,
                    verification_time=datetime.now(),
                    error_message="Failed to retrieve backup file"
                )
            
            # Verify checksum
            verification_result = self.verify_backup_checksum(file_obj, expected_checksum, algorithm)
            
            # Close file object if it has a close method
            if hasattr(file_obj, 'close'):
                file_obj.close()
            
            is_verified = verification_result.is_valid
            
            if is_verified:
                logger.info(f"Pre-restoration verification passed for backup {backup.backup_id}")
            else:
                logger.error(f"Pre-restoration verification failed for backup {backup.backup_id}")
            
            return is_verified, verification_result
            
        except Exception as e:
            logger.error(f"Pre-restoration verification error: {e}")
            return False, VerificationResult(
                is_valid=False,
                expected_checksum=expected_checksum or "",
                actual_checksum="",
                algorithm=algorithm,
                file_size=0,
                verification_time=datetime.now(),
                error_message=f"Verification error: {str(e)}"
            )
    
    def batch_verify_backups(self, storage_adapter, backups: list, 
                           algorithm: str = 'sha256') -> Dict[str, VerificationResult]:
        """
        Verify multiple backups in batch.
        
        Args:
            storage_adapter: Storage adapter to retrieve backups from
            backups: List of backup objects
            algorithm: Hash algorithm to use
            
        Returns:
            Dict: Verification results keyed by backup_id
        """
        results = {}
        
        for backup in backups:
            try:
                # Get expected checksum
                expected_checksum = getattr(backup, 'checksum', None)
                if not expected_checksum:
                    logger.warning(f"No checksum available for backup {backup.backup_id}")
                    continue
                
                # Verify backup
                is_verified, verification_result = self.verify_before_restoration(
                    storage_adapter, backup, expected_checksum, algorithm
                )
                
                results[str(backup.backup_id)] = verification_result
                
            except Exception as e:
                logger.error(f"Batch verification error for backup {backup.backup_id}: {e}")
                results[str(backup.backup_id)] = VerificationResult(
                    is_valid=False,
                    expected_checksum=getattr(backup, 'checksum', ""),
                    actual_checksum="",
                    algorithm=algorithm,
                    file_size=0,
                    verification_time=datetime.now(),
                    error_message=f"Batch verification error: {str(e)}"
                )
        
        logger.info(f"Batch verification completed for {len(backups)} backups")
        return results
    
    def monitor_integrity(self, storage_adapter, backup, check_interval_hours: int = 24):
        """
        Monitor backup integrity over time.
        
        Args:
            storage_adapter: Storage adapter to use
            backup: Backup object to monitor
            check_interval_hours: Hours between integrity checks
        """
        import threading
        import time
        
        def integrity_monitor():
            """Background thread for integrity monitoring."""
            logger.info(f"Starting integrity monitoring for backup {backup.backup_id}")
            
            while True:
                try:
                    # Verify backup integrity
                    is_verified, verification_result = self.verify_before_restoration(
                        storage_adapter, backup
                    )
                    
                    if not is_verified:
                        logger.error(f"Integrity check failed for backup {backup.backup_id}")
                        # Here you could trigger alerts or backup recreation
                    
                    # Wait for next check
                    time.sleep(check_interval_hours * 3600)
                    
                except Exception as e:
                    logger.error(f"Integrity monitoring error: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=integrity_monitor, daemon=True)
        monitor_thread.start()
        
        return monitor_thread
    
    def get_supported_algorithms(self) -> list:
        """
        Get list of supported hash algorithms.
        
        Returns:
            list: Supported algorithm names
        """
        return self.supported_algorithms.copy()
    
    def validate_checksum_format(self, checksum: str, algorithm: str) -> bool:
        """
        Validate checksum format for given algorithm.
        
        Args:
            checksum: Checksum string to validate
            algorithm: Hash algorithm
            
        Returns:
            bool: True if format is valid, False otherwise
        """
        if algorithm == 'sha256':
            return len(checksum) == 64 and all(c in '0123456789abcdef' for c in checksum.lower())
        elif algorithm == 'sha512':
            return len(checksum) == 128 and all(c in '0123456789abcdef' for c in checksum.lower())
        elif algorithm == 'md5':
            return len(checksum) == 32 and all(c in '0123456789abcdef' for c in checksum.lower())
        elif algorithm == 'sha1':
            return len(checksum) == 40 and all(c in '0123456789abcdef' for c in checksum.lower())
        
        return False


# Convenience functions
def create_verifier() -> BackupVerifier:
    """Create a new backup verifier instance."""
    return BackupVerifier()


def quick_verify(file_obj: BinaryIO, expected_checksum: str, 
                algorithm: str = 'sha256') -> bool:
    """
    Quick verification of file checksum.
    
    Args:
        file_obj: File-like object to verify
        expected_checksum: Expected checksum
        algorithm: Hash algorithm
        
    Returns:
        bool: True if checksum matches, False otherwise
    """
    verifier = BackupVerifier()
    result = verifier.verify_backup_checksum(file_obj, expected_checksum, algorithm)
    return result.is_valid


def calculate_file_checksum(file_path: str, algorithm: str = 'sha256') -> str:
    """
    Calculate checksum for a file on disk.
    
    Args:
        file_path: Path to file
        algorithm: Hash algorithm
        
    Returns:
        str: Hexadecimal checksum
    """
    verifier = BackupVerifier()
    with open(file_path, 'rb') as file_obj:
        return verifier.calculate_checksum(file_obj, algorithm)
