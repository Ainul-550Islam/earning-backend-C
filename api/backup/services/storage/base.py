"""
Base Storage Interface - Adapter Pattern
Defines the interface that all storage adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, BinaryIO
from datetime import datetime
import logging
from api.backup.models import Backup

logger = logging.getLogger(__name__)


class StorageAdapterInterface(ABC):
    """
    Abstract base class for storage adapters.
    All storage implementations must inherit from this interface.
    """
    
    @abstractmethod
    def save_backup(self, file_obj: BinaryIO, backup: 'Backup') -> bool:
        """
        Save backup file to storage.
        
        Args:
            file_obj: File-like object containing backup data
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def retrieve_backup(self, backup: 'Backup') -> Optional[BinaryIO]:
        """
        Retrieve backup file from storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            BinaryIO: File-like object or None if not found
        """
        pass
    
    @abstractmethod
    def delete_backup(self, backup: 'Backup') -> bool:
        """
        Delete backup file from storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def backup_exists(self, backup: 'Backup') -> bool:
        """
        Check if backup file exists in storage.
        
        Args:
            backup: Backup model instance
            
        Returns:
            bool: True if exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_backup_size(self, backup: 'Backup') -> Optional[int]:
        """
        Get backup file size.
        
        Args:
            backup: Backup model instance
            
        Returns:
            int: File size in bytes or None if not found
        """
        pass
    
    @abstractmethod
    def get_backup_url(self, backup: 'Backup', expires_in: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for backup download.
        
        Args:
            backup: Backup model instance
            expires_in: URL expiration time in seconds
            
        Returns:
            str: Presigned URL or None if not supported
        """
        pass
    
    @abstractmethod
    def list_backups(self, prefix: str = '') -> list:
        """
        List all backup files in storage.
        
        Args:
            prefix: Path prefix to filter results
            
        Returns:
            list: List of backup file information
        """
        pass
    
    @abstractmethod
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage usage statistics.
        
        Returns:
            Dict: Storage statistics (total_space, used_space, free_space, etc.)
        """
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test connection to storage backend.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate storage configuration.
        
        Args:
            config: Storage configuration dictionary
            
        Returns:
            bool: True if valid, False otherwise
        """
        # Default implementation - can be overridden by adapters
        return bool(config)
    
    def get_adapter_info(self) -> Dict[str, str]:
        """
        Get adapter information.
        
        Returns:
            Dict: Adapter information (name, version, capabilities)
        """
        return {
            'name': self.__class__.__name__,
            'type': 'storage_adapter',
            'version': '1.0.0'
        }
    
    def handle_error(self, error: Exception, operation: str, backup: 'Backup' = None) -> Dict[str, Any]:
        """
        Handle storage errors consistently.
        
        Args:
            error: Exception that occurred
            operation: Operation being performed
            backup: Backup instance (optional)
            
        Returns:
            Dict: Error information
        """
        error_info = {
            'error': str(error),
            'operation': operation,
            'timestamp': datetime.now().isoformat(),
            'adapter': self.__class__.__name__
        }
        
        if backup:
            error_info['backup_id'] = str(backup.backup_id)
            error_info['backup_name'] = backup.name
        
        logger.error(f"Storage error in {self.__class__.__name__}: {error_info}")
        return error_info


class StorageAdapterFactory:
    """
    Factory for creating storage adapters.
    """
    
    _adapters = {}
    
    @classmethod
    def register_adapter(cls, storage_type: str, adapter_class):
        """Register a storage adapter."""
        cls._adapters[storage_type] = adapter_class
    
    @classmethod
    def get_adapter(cls, storage_type: str, config: Dict[str, Any] = None):
        """Get storage adapter instance."""
        adapter_class = cls._adapters.get(storage_type)
        if not adapter_class:
            raise ValueError(f"Unknown storage type: {storage_type}")
        
        return adapter_class(config or {})
    
    @classmethod
    def get_available_adapters(cls) -> list:
        """Get list of available storage adapters."""
        return list(cls._adapters.keys())
    
    @classmethod
    def get_adapter_info(cls, storage_type: str) -> Dict[str, str]:
        """Get information about a specific adapter."""
        adapter_class = cls._adapters.get(storage_type)
        if not adapter_class:
            return {}
        
        temp_adapter = adapter_class({})
        return temp_adapter.get_adapter_info()


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageConnectionError(StorageError):
    """Exception for storage connection issues."""
    pass


class StorageValidationError(StorageError):
    """Exception for storage validation issues."""
    pass


class StorageNotFoundError(StorageError):
    """Exception for missing storage resources."""
    pass


class StoragePermissionError(StorageError):
    """Exception for storage permission issues."""
    pass
