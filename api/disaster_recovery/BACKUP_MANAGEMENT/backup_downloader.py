"""
Backup Downloader — Downloads backup files from cloud storage for restore
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class BackupDownloader:
    """Downloads backup files from storage backends for restore operations."""

    def __init__(self, provider: str, config: dict):
        self.provider = provider
        self.config = config

    def download(self, remote_path: str, local_path: str) -> dict:
        logger.info(f"Downloading {self.provider}:{remote_path} -> {local_path}")
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        if self.provider == "aws_s3":
            return self._download_s3(remote_path, local_path)
        elif self.provider == "azure_blob":
            return self._download_azure(remote_path, local_path)
        elif self.provider == "gcp":
            return self._download_gcp(remote_path, local_path)
        elif self.provider == "local":
            return self._download_local(remote_path, local_path)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _download_s3(self, remote_path: str, local_path: str) -> dict:
        import boto3
        s3 = boto3.client(
            "s3",
            aws_access_key_id=self.config.get("access_key_id"),
            aws_secret_access_key=self.config.get("secret_access_key"),
            region_name=self.config.get("region", "us-east-1"),
        )
        bucket = self.config["bucket"]
        s3.download_file(bucket, remote_path, local_path)
        size = os.path.getsize(local_path)
        logger.info(f"S3 download complete: {local_path} ({size} bytes)")
        return {"local_path": local_path, "size_bytes": size}

    def _download_azure(self, remote_path: str, local_path: str) -> dict:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(self.config["connection_string"])
        blob = client.get_blob_client(container=self.config["container"], blob=remote_path)
        with open(local_path, "wb") as f:
            data = blob.download_blob()
            data.readinto(f)
        return {"local_path": local_path, "size_bytes": os.path.getsize(local_path)}

    def _download_gcp(self, remote_path: str, local_path: str) -> dict:
        from google.cloud import storage
        client = storage.Client(project=self.config.get("project_id"))
        bucket = client.bucket(self.config["bucket"])
        blob = bucket.blob(remote_path)
        blob.download_to_filename(local_path)
        return {"local_path": local_path, "size_bytes": os.path.getsize(local_path)}

    def _download_local(self, remote_path: str, local_path: str) -> dict:
        import shutil
        src = Path(self.config.get("base_path", "/var/backups")) / remote_path
        shutil.copy2(str(src), local_path)
        return {"local_path": local_path, "size_bytes": os.path.getsize(local_path)}
