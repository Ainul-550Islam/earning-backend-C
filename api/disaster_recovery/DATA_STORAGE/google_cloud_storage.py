"""
Google Cloud Storage Backend — Full GCS integration for DR backups.
"""
import os
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class GoogleCloudStorage:
    """
    Google Cloud Storage backend for DR backups.
    Supports multi-regional buckets, nearline/coldline/archive storage,
    signed URLs, customer-managed encryption keys (CMEK), and lifecycle rules.
    """

    STORAGE_CLASSES = {
        "standard": "STANDARD",
        "nearline": "NEARLINE",
        "coldline": "COLDLINE",
        "archive": "ARCHIVE",
    }

    def __init__(self, config: dict):
        self.config = config
        self.project_id = config.get("project_id", "")
        self.bucket_name = config.get("bucket", "dr-backups")
        self.prefix = config.get("prefix", "backups/")
        self.credentials_file = config.get("credentials_file", "")
        self.default_storage_class = config.get("storage_class", "NEARLINE")
        self.cmek_key = config.get("cmek_key", "")
        self._client = None
        self._bucket = None

    @property
    def client(self):
        if not self._client:
            from google.cloud import storage
            if self.credentials_file and os.path.exists(self.credentials_file):
                self._client = storage.Client.from_service_account_json(
                    self.credentials_file, project=self.project_id
                )
            else:
                self._client = storage.Client(project=self.project_id)
        return self._client

    @property
    def bucket(self):
        if not self._bucket:
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket

    def ensure_bucket(self) -> bool:
        """Create bucket if it doesn't exist."""
        try:
            self.client.get_bucket(self.bucket_name)
            return True
        except Exception:
            bucket = self.client.create_bucket(
                self.bucket_name,
                location=self.config.get("location", "US"),
            )
            bucket.storage_class = self.default_storage_class
            bucket.patch()
            logger.info(f"GCS bucket created: {self.bucket_name}")
            return True

    def upload(self, local_path: str, remote_path: str,
               metadata: dict = None, storage_class: str = None) -> dict:
        """Upload file to GCS with resumable upload for large files."""
        self.ensure_bucket()
        blob_name = f"{self.prefix}{remote_path}"
        file_size = os.path.getsize(local_path)
        logger.info(
            f"Uploading to GCS: {local_path} -> "
            f"gs://{self.bucket_name}/{blob_name} ({file_size:,} bytes)"
        )
        blob = self.bucket.blob(blob_name)
        if storage_class or self.default_storage_class:
            blob.storage_class = storage_class or self.default_storage_class
        if self.cmek_key:
            blob.kms_key_name = self.cmek_key
        if metadata:
            blob.metadata = {k: str(v) for k, v in metadata.items()}
        # Use resumable upload for files > 5 MB
        if file_size > 5 * 1024 * 1024:
            blob.upload_from_filename(local_path, timeout=3600)
        else:
            blob.upload_from_filename(local_path)
        url = f"gs://{self.bucket_name}/{blob_name}"
        logger.info(f"GCS upload complete: {url}")
        return {
            "url": url,
            "blob_name": blob_name,
            "bucket": self.bucket_name,
            "size_bytes": file_size,
            "storage_class": blob.storage_class,
            "etag": blob.etag,
        }

    def download(self, remote_path: str, local_path: str) -> dict:
        """Download blob from GCS."""
        blob_name = (
            f"{self.prefix}{remote_path}"
            if not remote_path.startswith(self.prefix) else remote_path
        )
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading from GCS: gs://{self.bucket_name}/{blob_name} -> {local_path}")
        blob = self.bucket.blob(blob_name)
        blob.download_to_filename(local_path, timeout=3600)
        size = os.path.getsize(local_path)
        logger.info(f"GCS download complete: {local_path} ({size:,} bytes)")
        return {"local_path": local_path, "size_bytes": size, "blob_name": blob_name}

    def delete(self, remote_path: str) -> bool:
        """Delete a blob from GCS."""
        blob_name = f"{self.prefix}{remote_path}"
        self.bucket.blob(blob_name).delete()
        logger.info(f"GCS blob deleted: {blob_name}")
        return True

    def bulk_delete(self, remote_paths: List[str]) -> dict:
        """Delete multiple blobs in parallel."""
        from google.cloud import storage
        blobs = [
            self.bucket.blob(f"{self.prefix}{p}") if not p.startswith(self.prefix) else self.bucket.blob(p)
            for p in remote_paths
        ]
        self.bucket.delete_blobs(blobs, on_error=lambda blob: logger.error(f"Failed to delete: {blob.name}"))
        return {"deleted": len(remote_paths)}

    def list_blobs(self, prefix: str = "", max_results: int = 10000) -> List[dict]:
        """List blobs with optional prefix filter."""
        full_prefix = f"{self.prefix}{prefix}"
        blobs = []
        for blob in self.client.list_blobs(
            self.bucket_name, prefix=full_prefix, max_results=max_results
        ):
            blobs.append({
                "name": blob.name,
                "size_bytes": blob.size,
                "created": blob.time_created.isoformat() if blob.time_created else None,
                "updated": blob.updated.isoformat() if blob.updated else None,
                "storage_class": blob.storage_class,
                "md5_hash": blob.md5_hash,
            })
        return blobs

    def generate_signed_url(self, remote_path: str, expiry_hours: int = 24,
                             method: str = "GET") -> str:
        """Generate a signed URL for temporary access."""
        blob_name = f"{self.prefix}{remote_path}"
        blob = self.bucket.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(hours=expiry_hours),
            method=method,
        )
        return url

    def change_storage_class(self, remote_path: str, new_class: str) -> bool:
        """Change the storage class of a blob (rewrite operation)."""
        blob_name = f"{self.prefix}{remote_path}"
        blob = self.bucket.blob(blob_name)
        blob.update_storage_class(self.STORAGE_CLASSES.get(new_class.lower(), new_class))
        logger.info(f"GCS storage class changed: {blob_name} -> {new_class}")
        return True

    def set_lifecycle_policy(self, transition_days: int = 30,
                              delete_days: int = 365) -> bool:
        """Set lifecycle rules: transition to coldline then delete."""
        from google.cloud.storage import Bucket
        bucket = self.client.get_bucket(self.bucket_name)
        rules = [
            {
                "action": {"type": "SetStorageClass", "storageClass": "NEARLINE"},
                "condition": {"age": 7},
            },
            {
                "action": {"type": "SetStorageClass", "storageClass": "COLDLINE"},
                "condition": {"age": transition_days},
            },
            {
                "action": {"type": "SetStorageClass", "storageClass": "ARCHIVE"},
                "condition": {"age": transition_days * 3},
            },
            {
                "action": {"type": "Delete"},
                "condition": {"age": delete_days},
            },
        ]
        bucket.lifecycle_rules = rules
        bucket.patch()
        logger.info(
            f"GCS lifecycle policy set: NEARLINE@7d, COLDLINE@{transition_days}d, "
            f"ARCHIVE@{transition_days * 3}d, DELETE@{delete_days}d"
        )
        return True

    def get_bucket_stats(self) -> dict:
        """Get storage statistics for the bucket."""
        blobs = self.list_blobs()
        total_bytes = sum(b["size_bytes"] or 0 for b in blobs)
        by_class: dict = {}
        for blob in blobs:
            sc = blob.get("storage_class", "STANDARD")
            by_class[sc] = by_class.get(sc, 0) + (blob["size_bytes"] or 0)
        return {
            "bucket": self.bucket_name,
            "total_objects": len(blobs),
            "total_size_gb": round(total_bytes / 1e9, 3),
            "by_storage_class_gb": {k: round(v / 1e9, 3) for k, v in by_class.items()},
        }
