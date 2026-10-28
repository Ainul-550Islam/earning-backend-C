"""
Local Storage Adapter - Adapter Pattern Implementation
Implements StorageAdapterInterface for local filesystem storage.
"""

import os
import shutil
import hashlib
import logging
from typing import Dict, Any, Optional, BinaryIO
from datetime import datetime, timedelta
from pathlib import Path

from .base import (
    StorageAdapterInterface, 
    StorageError, 
    StorageConnectionError, 
    StorageValidationError,
    StorageNotFoundError,
    StoragePermissionError
)
from api.backup.models import Backup

logger = logging.getLogger(__name__)


class LocalStorageAdapter(StorageAdapterInterface):
    """
    Local filesystem storage adapter implementation.
    Handles all local file storage operations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local storage adapter with configuration.
        
        Args:
            config: Local storage configuration dictionary containing:
                - base_path: Base directory for storage (required)
                - create_dirs: Create directories if they don't exist (default: True)
                - permissions: File permissions (default: 0o644)
                - dir_permissions: Directory permissions (default: 0o755)
                - backup_subdir: Subdirectory for backups (default: 'backups')
        """
        self.config = config
        self._validate_config()
        self._initialize_storage()
    
    def _validate_config(self):
        """Validate local storage configuration."""
        base_path = self.config.get('base_path')
        if not base_path:
            raise StorageValidationError("Local adapter requires 'base_path' in configuration")
        
        # Convert to Path object
        self.base_path = Path(base_path).resolve()
        
        # Check if parent directory exists
        if not self.base_path.parent.exists():
            raise StorageValidationError(f"Parent directory does not exist: {self.base_path.parent}")
        
        # Check permissions on parent directory
        if not os.access(self.base_path.parent, os.W_OK):
            raise StoragePermissionError(f"No write permission on parent directory: {self.base_path.parent}")
        
        self.create_dirs = self.config.get('create_dirs', True)
        self.file_permissions = self.config.get('permissions', 0o644)
        self.dir_permissions = self.config.get('dir_permissions', 0o755)
        self.backup_subdir = self.config.get('backup_subdir', 'backups')
    
    def _initialize_storage(self):
        """Initialize local storage directory."""
        try:
            if self.create_dirs:
                self.base_path.mkdir(parents=True, exist_ok=True)
                os.chmod(self.base_path, self.dir_permissions)
            
            # Test write permissions
            test_file = self.base_path / '.write_test'
            test_file.write_text('test')
            test_file.unlink()
            
        except Exception as e:
            raise StorageConnectionError(f"Failed to initialize local storage: {str(e)}")
    
    def save_backup(self, file_obj: BinaryIO, backup: 'Backup') -> bool:
        """
        Save backup file to local storage.
        
        Args:
            file_obj: File-like object containing backup data
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Generate file path
            file_path = self._generate_file_path(backup)
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Reset file pointer
            file_obj.seek(0)
            
            # Write file
            with open(file_path, 'wb') as f:
                shutil.copyfileobj(file_obj, f)
            
            # Set permissions
            os.chmod(file_path, self.file_permissions)
            
            # Update backup with file path
            backup.file_path = str(file_path.relative_to(self.base_path))
            backup.save()
            
            logger.info(f"Successfully saved backup {backup.name} to local storage: {file_path}")
            return True
            
        except Exception as e:
            error_info = self.handle_error(e, 'save_backup', backup)
            logger.error(f"Local storage save failed: {error_info}")
            return False
    
    def retrieve_backup(self, backup: 'Backup') -> Optional[BinaryIO]:
        """
        Retrieve backup file from local storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            BinaryIO: File-like object or None if not found
        """
        try:
            file_path = self._get_file_path(backup)
            
            if not file_path.exists():
                logger.warning(f"Backup file not found in local storage: {file_path}")
                return None
            
            # Return file object
            return open(file_path, 'rb')
            
        except Exception as e:
            error_info = self.handle_error(e, 'retrieve_backup', backup)
            logger.error(f"Local storage retrieval failed: {error_info}")
            return None
    
    def delete_backup(self, backup: 'Backup') -> bool:
        """
        Delete backup file from local storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_path = self._get_file_path(backup)
            
            if not file_path.exists():
                logger.warning(f"Backup file not found for deletion: {file_path}")
                return True  # Already deleted
            
            # Delete file
            file_path.unlink()
            
            # Try to remove empty parent directories
            try:
                parent = file_path.parent
                while parent != self.base_path and parent.exists():
                    if not any(parent.iterdir()):
                        parent.rmdir()
                    parent = parent.parent
            except OSError:
                pass  # Directory not empty or permission denied
            
            logger.info(f"Successfully deleted backup {backup.name} from local storage: {file_path}")
            return True
            
        except Exception as e:
            error_info = self.handle_error(e, 'delete_backup', backup)
            logger.error(f"Local storage deletion failed: {error_info}")
            return False
    
    def backup_exists(self, backup: 'Backup') -> bool:
        """
        Check if backup file exists in local storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if exists, False otherwise
        """
        try:
            file_path = self._get_file_path(backup)
            return file_path.exists()
            
        except Exception as e:
            error_info = self.handle_error(e, 'backup_exists', backup)
            logger.error(f"Local storage existence check failed: {error_info}")
            return False
    
    def get_backup_size(self, backup: 'Backup') -> Optional[int]:
        """
        Get backup file size from local storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            int: File size in bytes or None if not found
        """
        try:
            file_path = self._get_file_path(backup)
            
            if not file_path.exists():
                return None
            
            return file_path.stat().st_size
            
        except Exception as e:
            error_info = self.handle_error(e, 'get_backup_size', backup)
            logger.error(f"Local storage size check failed: {error_info}")
            return None
    
    def get_backup_url(self, backup: 'Backup', expires_in: int = 3600) -> Optional[str]:
        """
        Generate URL for backup download (not applicable to local storage).
        
        Args:
            backup: Backup model instance
            expires_in: URL expiration time in seconds
            
        Returns:
            str: File path or None if not supported
        """
        try:
            file_path = self._get_file_path(backup)
            
            if not file_path.exists():
                return None
            
            # Return file:// URL for local access
            return f"file://{file_path.absolute()}"
            
        except Exception as e:
            error_info = self.handle_error(e, 'get_backup_url', backup)
            logger.error(f"Local storage URL generation failed: {error_info}")
            return None
    
    def list_backups(self, prefix: str = '') -> list:
        """
        List all backup files in local storage.
        
        Args:
            prefix: Path prefix to filter results
            
        Returns:
            list: List of backup file information
        """
        try:
            backup_dir = self.base_path / self.backup_subdir
            
            if not backup_dir.exists():
                return []
            
            backups = []
            pattern = f"*{prefix}*" if prefix else "*"
            
            for file_path in backup_dir.rglob(pattern):
                if file_path.is_file():
                    stat = file_path.stat()
                    backups.append({
                        'key': str(file_path.relative_to(self.base_path)),
                        'size': stat.st_size,
                        'last_modified': datetime.fromtimestamp(stat.st_mtime),
                        'etag': self._calculate_file_hash(file_path)
                    })
            
            return sorted(backups, key=lambda x: x['last_modified'], reverse=True)
            
        except Exception as e:
            error_info = self.handle_error(e, 'list_backups')
            logger.error(f"Local storage listing failed: {error_info}")
            return []
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get local storage usage statistics.
        
        Returns:
            Dict: Storage statistics
        """
        try:
            backup_dir = self.base_path / self.backup_subdir
            
            if not backup_dir.exists():
                return {
                    'base_path': str(self.base_path),
                    'backup_directory': str(backup_dir),
                    'total_objects': 0,
                    'total_size_bytes': 0,
                    'total_size_mb': 0,
                    'free_space_bytes': 0,
                    'free_space_mb': 0,
                    'adapter': 'Local'
                }
            
            total_size = 0
            total_files = 0
            
            for file_path in backup_dir.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    total_files += 1
            
            # Get disk space
            disk_usage = shutil.disk_usage(self.base_path)
            free_space = disk_usage.free
            
            return {
                'base_path': str(self.base_path),
                'backup_directory': str(backup_dir),
                'total_objects': total_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'free_space_bytes': free_space,
                'free_space_mb': round(free_space / (1024 * 1024), 2),
                'disk_total_bytes': disk_usage.total,
                'disk_total_mb': round(disk_usage.total / (1024 * 1024), 2),
                'adapter': 'Local'
            }
            
        except Exception as e:
            error_info = self.handle_error(e, 'get_storage_stats')
            logger.error(f"Local storage stats failed: {error_info}")
            return {}
    
    def test_connection(self) -> bool:
        """
        Test connection to local storage.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Check if base path exists and is writable
            if not self.base_path.exists():
                return False
            
            if not os.access(self.base_path, os.W_OK):
                return False
            
            # Test write operation
            test_file = self.base_path / '.connection_test'
            test_file.write_text('test')
            test_file.unlink()
            
            return True
            
        except Exception as e:
            logger.error(f"Local storage connection test failed: {str(e)}")
            return False
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate local storage configuration.
        
        Args:
            config: Local storage configuration dictionary
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            base_path = config.get('base_path')
            if not base_path:
                return False
            
            path_obj = Path(base_path).resolve()
            
            # Check if parent directory exists
            if not path_obj.parent.exists():
                return False
            
            # Check permissions
            if not os.access(path_obj.parent, os.W_OK):
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_adapter_info(self) -> Dict[str, str]:
        """
        Get local storage adapter information.
        
        Returns:
            Dict: Adapter information
        """
        return {
            'name': 'LocalStorageAdapter',
            'type': 'storage_adapter',
            'version': '1.0.0',
            'capabilities': [
                'save_backup',
                'retrieve_backup',
                'delete_backup',
                'backup_exists',
                'get_backup_size',
                'get_backup_url',
                'list_backups',
                'get_storage_stats',
                'test_connection'
            ],
            'supported_filesystems': [
                'ext4', 'ext3', 'ext2', 'ntfs', 'fat32', 'apfs', 'btrfs'
            ]
        }
    
    def _generate_file_path(self, backup: 'Backup') -> Path:
        """
        Generate file path for backup.
        
        Args:
            backup: Backup model instance
            
        Returns:
            Path: File path
        """
        # Create directory structure: backups/year/month/day/
        created_date = backup.created_at
        year = created_date.strftime('%Y')
        month = created_date.strftime('%m')
        day = created_date.strftime('%d')
        
        # Generate filename
        filename = f"{backup.backup_id}_{backup.name.replace(' ', '_')}.sql"
        if backup.compression_enabled:
            filename += '.gz'
        
        # Build full path
        backup_dir = self.base_path / self.backup_subdir / year / month / day
        return backup_dir / filename
    
    def _get_file_path(self, backup: 'Backup') -> Path:
        """
        Get file path for backup.
        
        Args:
            backup: Backup model instance
            
        Returns:
            Path: File path
        """
        if backup.file_path:
            return self.base_path / backup.file_path
        
        # Generate path if not stored
        return self._generate_file_path(backup)
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate file hash for ETag equivalent.
        
        Args:
            file_path: Path to file
            
        Returns:
            str: MD5 hash
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _cleanup_old_backups(self, days: int = 30) -> int:
        """
        Clean up old backups from local storage.
        
        Args:
            days: Number of days to keep backups
            
        Returns:
            int: Number of deleted backups
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0
            
            backup_dir = self.base_path / self.backup_subdir
            
            for file_path in backup_dir.rglob('*'):
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        file_path.unlink()
                        deleted_count += 1
            
            # Clean up empty directories
            for dir_path in backup_dir.rglob('*'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                    except OSError:
                        pass
            
            return deleted_count
            
        except Exception as e:
            error_info = self.handle_error(e, 'cleanup_old_backups')
            logger.error(f"Local storage cleanup failed: {error_info}")
            return 0
