"""
Backup Storage Manager — Unified interface for all storage backends.
"""
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class BackupStorageManager:
    """
    Unified storage manager that abstracts all backend implementations.
    Routes operations to the correct backend based on provider configuration.
    Handles failover between storage backends automatically.
    """

    BACKEND_MAP = {
        "aws_s3":     "S3Storage",
        "aws_glacier":"GlacierStorage",
        "azure_blob": "AzureBlobStorage",
        "gcp":        "GoogleCloudStorage",
        "local":      "LocalStorage",
        "nas":        "NASStorage",
        "san":        "SANStorage",
    }

    def __init__(self, primary_config: dict, fallback_config: dict = None):
        self.primary_config = primary_config
        self.fallback_config = fallback_config
        self._primary = None
        self._fallback = None
        self._stats = {
            "uploads": 0, "downloads": 0, "deletes": 0,
            "bytes_uploaded": 0, "bytes_downloaded": 0,
            "failures": 0,
        }

    def _get_backend(self, config: dict):
        """Instantiate the appropriate storage backend."""
        provider = config.get("provider", "local")
        class_name = self.BACKEND_MAP.get(provider)
        if not class_name:
            raise ValueError(f"Unknown storage provider: {provider}")
        if provider == "aws_s3":
            from .s3_storage import S3Storage
            return S3Storage(config)
        elif provider == "aws_glacier":
            from .glacier_storage import GlacierStorage
            return GlacierStorage(config)
        elif provider == "azure_blob":
            from .azure_blob_storage import AzureBlobStorage
            return AzureBlobStorage(config)
        elif provider == "gcp":
            from .google_cloud_storage import GoogleCloudStorage
            return GoogleCloudStorage(config)
        elif provider == "local":
            from .local_storage import LocalStorage
            return LocalStorage(config)
        elif provider == "nas":
            from .nas_storage import NASStorage
            return NASStorage(config)
        elif provider == "san":
            from .san_storage import SANStorage
            return SANStorage(config)
        raise ValueError(f"Cannot instantiate backend: {provider}")

    @property
    def primary(self):
        if not self._primary:
            self._primary = self._get_backend(self.primary_config)
        return self._primary

    @property
    def fallback(self):
        if self.fallback_config and not self._fallback:
            self._fallback = self._get_backend(self.fallback_config)
        return self._fallback

    def upload(self, local_path: str, remote_path: str, metadata: dict = None) -> dict:
        """Upload to primary storage, fall back to secondary on failure."""
        try:
            result = self.primary.upload(local_path, remote_path, metadata)
            self._stats["uploads"] += 1
            self._stats["bytes_uploaded"] += result.get("size_bytes", 0)
            # Also upload to fallback if configured (redundancy)
            if self.fallback:
                try:
                    self.fallback.upload(local_path, remote_path, metadata)
                    result["fallback_stored"] = True
                    logger.info(f"Also stored in fallback: {self.fallback_config.get('provider')}")
                except Exception as fe:
                    logger.warning(f"Fallback storage failed: {fe}")
                    result["fallback_stored"] = False
            return result
        except Exception as e:
            self._stats["failures"] += 1
            logger.error(f"Primary storage upload failed: {e}")
            if self.fallback:
                logger.warning(f"Falling back to {self.fallback_config.get('provider')}")
                result = self.fallback.upload(local_path, remote_path, metadata)
                result["used_fallback"] = True
                return result
            raise

    def download(self, remote_path: str, local_path: str,
                 prefer_fallback: bool = False) -> dict:
        """Download from storage, trying fallback on failure."""
        source = self.fallback if (prefer_fallback and self.fallback) else self.primary
        try:
            result = source.download(remote_path, local_path)
            self._stats["downloads"] += 1
            self._stats["bytes_downloaded"] += result.get("size_bytes", 0)
            return result
        except Exception as e:
            self._stats["failures"] += 1
            logger.error(f"Download failed from primary: {e}")
            alt = self.fallback if source == self.primary else self.primary
            if alt:
                logger.warning("Trying alternative storage for download")
                return alt.download(remote_path, local_path)
            raise

    def delete(self, remote_path: str, delete_from_all: bool = True) -> bool:
        """Delete from storage, optionally from all backends."""
        success = True
        try:
            self.primary.delete(remote_path)
            self._stats["deletes"] += 1
        except Exception as e:
            logger.error(f"Delete from primary failed: {e}")
            success = False
        if delete_from_all and self.fallback:
            try:
                self.fallback.delete(remote_path)
            except Exception as e:
                logger.warning(f"Delete from fallback failed: {e}")
        return success

    def get_stats(self) -> dict:
        """Get operational statistics for this storage manager."""
        return {
            **self._stats,
            "primary_provider": self.primary_config.get("provider"),
            "fallback_provider": self.fallback_config.get("provider") if self.fallback_config else None,
            "bytes_uploaded_gb": round(self._stats["bytes_uploaded"] / 1e9, 3),
            "bytes_downloaded_gb": round(self._stats["bytes_downloaded"] / 1e9, 3),
            "collected_at": datetime.utcnow().isoformat(),
        }
