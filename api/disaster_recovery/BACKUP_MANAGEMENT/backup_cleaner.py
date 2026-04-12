"""
Backup Cleaner — Removes expired/orphaned backup files from storage
"""
import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


class BackupCleaner:
    """Deletes expired backup files from local and cloud storage."""

    def __init__(self, provider: str, config: dict):
        self.provider = provider
        self.config = config

    def delete(self, remote_path: str) -> bool:
        logger.info(f"Deleting backup: {self.provider}:{remote_path}")
        try:
            if self.provider == "aws_s3":
                return self._delete_s3(remote_path)
            elif self.provider == "azure_blob":
                return self._delete_azure(remote_path)
            elif self.provider == "gcp":
                return self._delete_gcp(remote_path)
            elif self.provider == "local":
                return self._delete_local(remote_path)
        except Exception as e:
            logger.error(f"Delete failed for {remote_path}: {e}")
            return False
        return True

    def bulk_delete(self, paths: List[str]) -> dict:
        results = {"deleted": 0, "failed": 0, "paths": []}
        for path in paths:
            if self.delete(path):
                results["deleted"] += 1
                results["paths"].append(path)
            else:
                results["failed"] += 1
        logger.info(f"Bulk delete: {results['deleted']} deleted, {results['failed']} failed")
        return results

    def _delete_s3(self, path: str) -> bool:
        import boto3
        s3 = boto3.client("s3",
            aws_access_key_id=self.config.get("access_key_id"),
            aws_secret_access_key=self.config.get("secret_access_key"),
            region_name=self.config.get("region", "us-east-1"),
        )
        s3.delete_object(Bucket=self.config["bucket"], Key=path)
        return True

    def _delete_azure(self, path: str) -> bool:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(self.config["connection_string"])
        client.get_blob_client(container=self.config["container"], blob=path).delete_blob()
        return True

    def _delete_gcp(self, path: str) -> bool:
        from google.cloud import storage
        client = storage.Client()
        bucket = client.bucket(self.config["bucket"])
        bucket.blob(path).delete()
        return True

    def _delete_local(self, path: str) -> bool:
        import os
        from pathlib import Path
        full_path = Path(self.config.get("base_path", "/var/backups")) / path
        if full_path.exists():
            full_path.unlink()
        return True
