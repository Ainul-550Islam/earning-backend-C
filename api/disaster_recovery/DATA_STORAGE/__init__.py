"""Data Storage Module"""
from .backup_storage_manager import BackupStorageManager
from .s3_storage import S3Storage
from .glacier_storage import GlacierStorage
from .azure_blob_storage import AzureBlobStorage
from .google_cloud_storage import GoogleCloudStorage
from .local_storage import LocalStorage
from .nas_storage import NASStorage
from .san_storage import SANStorage
from .tape_storage import TapeStorage
from .storage_tiering import StorageTiering
from .data_lifecycle import DataLifecycleManager
from .archive_manager import ArchiveManager
from .retention_policy import RetentionPolicyManager
from .storage_encryption import StorageEncryption
from .storage_compression import StorageCompression
