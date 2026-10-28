"""
Storage Adapter Factory - Adapter Pattern Implementation
Factory for creating and managing storage adapters.
"""

import logging
from typing import Dict, Any, Type, Optional, List
from .base import StorageAdapterFactory as BaseStorageFactory, StorageAdapterInterface
from .local_adapter import LocalStorageAdapter
from .s3_adapter import S3StorageAdapter

logger = logging.getLogger(__name__)


class BackupStorageFactory:
    """
    Factory for creating storage adapters using the Adapter Pattern.
    This replaces the old factory and provides a cleaner interface.
    """
    
    def __init__(self):
        """Initialize the storage factory."""
        self._register_default_adapters()
    
    def _register_default_adapters(self):
        """Register default storage adapters."""
        try:
            # Register adapters with the base factory
            BaseStorageFactory.register_adapter('local', LocalStorageAdapter)
            BaseStorageFactory.register_adapter('s3', S3StorageAdapter)
            
            logger.info("Default storage adapters registered successfully")
        except Exception as e:
            logger.error(f"Failed to register default adapters: {e}")
    
    def get_adapter(self, storage_type: str, config: Dict[str, Any] = None) -> StorageAdapterInterface:
        """
        Get storage adapter instance.
        
        Args:
            storage_type: Type of storage ('local', 's3', etc.)
            config: Storage configuration dictionary
            
        Returns:
            StorageAdapterInterface: Adapter instance
            
        Raises:
            ValueError: If storage type is not supported
            StorageValidationError: If configuration is invalid
        """
        try:
            adapter = BaseStorageFactory.get_adapter(storage_type, config or {})
            
            # Test connection if adapter supports it
            if hasattr(adapter, 'test_connection'):
                if not adapter.test_connection():
                    logger.warning(f"Storage adapter connection test failed for {storage_type}")
                    # Still return adapter - let caller handle connection issues
            
            logger.info(f"Created storage adapter: {adapter.__class__.__name__} for type: {storage_type}")
            return adapter
            
        except ValueError as e:
            logger.error(f"Unsupported storage type: {storage_type}")
            raise ValueError(f"Unsupported storage type: {storage_type}. Available: {self.get_available_types()}")
        except Exception as e:
            logger.error(f"Failed to create storage adapter for {storage_type}: {e}")
            raise
    
    def get_available_types(self) -> List[str]:
        """
        Get list of available storage types.
        
        Returns:
            List[str]: Available storage types
        """
        return BaseStorageFactory.get_available_adapters()
    
    def get_adapter_info(self, storage_type: str) -> Dict[str, Any]:
        """
        Get information about a specific adapter.
        
        Args:
            storage_type: Type of storage
            
        Returns:
            Dict: Adapter information
        """
        return BaseStorageFactory.get_adapter_info(storage_type)
    
    def validate_config(self, storage_type: str, config: Dict[str, Any]) -> bool:
        """
        Validate storage configuration.
        
        Args:
            storage_type: Type of storage
            config: Configuration to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            adapter = BaseStorageFactory.get_adapter(storage_type, config)
            return adapter.validate_config(config)
        except Exception as e:
            logger.error(f"Config validation failed for {storage_type}: {e}")
            return False
    
    def test_adapter_connection(self, storage_type: str, config: Dict[str, Any] = None) -> bool:
        """
        Test connection to storage adapter.
        
        Args:
            storage_type: Type of storage
            config: Storage configuration
            
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            adapter = BaseStorageFactory.get_adapter(storage_type, config or {})
            return adapter.test_connection()
        except Exception as e:
            logger.error(f"Connection test failed for {storage_type}: {e}")
            return False
    
    def get_adapter_capabilities(self, storage_type: str) -> List[str]:
        """
        Get capabilities of a specific adapter.
        
        Args:
            storage_type: Type of storage
            
        Returns:
            List[str]: List of supported capabilities
        """
        try:
            adapter_info = BaseStorageFactory.get_adapter_info(storage_type)
            return adapter_info.get('capabilities', [])
        except Exception:
            return []
    
    def register_custom_adapter(self, storage_type: str, adapter_class: Type[StorageAdapterInterface]):
        """
        Register a custom storage adapter.
        
        Args:
            storage_type: Type identifier for the adapter
            adapter_class: Adapter class to register
        """
        try:
            BaseStorageFactory.register_adapter(storage_type, adapter_class)
            logger.info(f"Custom adapter registered: {storage_type} -> {adapter_class.__name__}")
        except Exception as e:
            logger.error(f"Failed to register custom adapter {storage_type}: {e}")
            raise


# Convenience functions for backward compatibility
def get_storage_factory() -> BackupStorageFactory:
    """Get storage factory instance."""
    return BackupStorageFactory()


def create_storage_adapter(storage_type: str, config: Dict[str, Any] = None) -> StorageAdapterInterface:
    """
    Convenience function to create storage adapter.
    
    Args:
        storage_type: Type of storage
        config: Storage configuration
        
    Returns:
        StorageAdapterInterface: Adapter instance
    """
    factory = BackupStorageFactory()
    return factory.get_adapter(storage_type, config)


def get_available_storage_types() -> List[str]:
    """
    Convenience function to get available storage types.
    
    Returns:
        List[str]: Available storage types
    """
    factory = BackupStorageFactory()
    return factory.get_available_types()


# Legacy compatibility
class BackupServiceFactory(BackupStorageFactory):
    """
    Legacy factory class for backward compatibility.
    """
    
    def get_storage_service(self, storage_type: str, config: Dict[str, Any] = None):
        """
        Legacy method for backward compatibility.
        
        Args:
            storage_type: Type of storage
            config: Storage configuration
            
        Returns:
            StorageAdapterInterface: Adapter instance
        """
        logger.warning("Using legacy get_storage_service method. Consider updating to get_adapter.")
        return self.get_adapter(storage_type, config)
