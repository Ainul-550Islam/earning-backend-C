"""
Storage Adapters Package
Adapter pattern implementation for different storage backends.
"""

from .base import (
    StorageAdapterInterface,
    StorageAdapterFactory,
    StorageError,
    StorageConnectionError,
    StorageValidationError,
    StorageNotFoundError,
    StoragePermissionError
)

from .local_adapter import LocalStorageAdapter
from .s3_adapter import S3StorageAdapter
from .factory import BackupStorageFactory, create_storage_adapter, get_available_storage_types
from .health_check import (
    StorageHealthChecker,
    HealthCheckResult,
    create_health_checker,
    quick_health_check,
    get_all_adapter_health
)
from .monitoring import (
    StorageMonitor,
    MonitoringConfig,
    MonitoringAlert,
    create_monitor,
    quick_health_check_with_alerts
)
from .failover import (
    StorageFailoverManager,
    FailoverConfig,
    FailoverStrategy,
    FailoverStatus,
    create_failover_manager
)
from .verification import (
    BackupVerifier,
    VerificationResult,
    BackupIntegrity,
    create_verifier,
    quick_verify,
    calculate_file_checksum
)
from .compression import (
    BackupCompressor,
    CompressionResult,
    CompressionConfig,
    create_compressor,
    quick_compress,
    quick_decompress
)

# Register adapters with factory
StorageAdapterFactory.register_adapter('local', LocalStorageAdapter)
StorageAdapterFactory.register_adapter('s3', S3StorageAdapter)

__all__ = [
    'StorageAdapterInterface',
    'StorageAdapterFactory',
    'LocalStorageAdapter',
    'S3StorageAdapter',
    'BackupStorageFactory',
    'StorageHealthChecker',
    'HealthCheckResult',
    'create_storage_adapter',
    'get_available_storage_types',
    'create_health_checker',
    'quick_health_check',
    'get_all_adapter_health',
    'StorageError',
    'StorageConnectionError',
    'StorageValidationError',
    'StorageNotFoundError',
    'StoragePermissionError'
]
