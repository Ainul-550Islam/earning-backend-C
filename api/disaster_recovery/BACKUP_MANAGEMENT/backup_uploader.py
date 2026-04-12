"""
Backup Uploader — Uploads backup files to cloud storage providers
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class BackupUploader:
    """Uploads backup files to configured storage backends (S3, Azure, GCP, local)."""

    def __init__(self, provider: str, config: dict):
        self.provider = provider
        self.config = config

    def upload(self, local_path: str, remote_path: str) -> dict:
        logger.info(f"Uploading {local_path} -> {self.provider}:{remote_path}")
        size = os.path.getsize(local_path)
        if self.provider == "aws_s3":
            return self._upload_s3(local_path, remote_path, size)
        elif self.provider == "azure_blob":
            return self._upload_azure(local_path, remote_path, size)
        elif self.provider == "gcp":
            return self._upload_gcp(local_path, remote_path, size)
        elif self.provider == "local":
            return self._upload_local(local_path, remote_path, size)
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _upload_s3(self, local_path: str, remote_path: str, size: int) -> dict:
        import boto3
        from boto3.s3.transfer import TransferConfig
        s3 = boto3.client(
            "s3",
            aws_access_key_id=self.config.get("access_key_id"),
            aws_secret_access_key=self.config.get("secret_access_key"),
            region_name=self.config.get("region", "us-east-1"),
        )
        bucket = self.config["bucket"]
        cfg = TransferConfig(multipart_threshold=1024**3, max_concurrency=10)
        s3.upload_file(local_path, bucket, remote_path, Config=cfg)
        url = f"s3://{bucket}/{remote_path}"
        logger.info(f"S3 upload complete: {url}")
        return {"url": url, "size_bytes": size, "provider": "aws_s3"}

    def _upload_azure(self, local_path: str, remote_path: str, size: int) -> dict:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(self.config["connection_string"])
        container = self.config["container"]
        blob_client = client.get_blob_client(container=container, blob=remote_path)
        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        url = f"azure://{container}/{remote_path}"
        return {"url": url, "size_bytes": size, "provider": "azure_blob"}

    def _upload_gcp(self, local_path: str, remote_path: str, size: int) -> dict:
        from google.cloud import storage
        client = storage.Client(project=self.config.get("project_id"))
        bucket = client.bucket(self.config["bucket"])
        blob = bucket.blob(remote_path)
        blob.upload_from_filename(local_path)
        url = f"gs://{self.config['bucket']}/{remote_path}"
        return {"url": url, "size_bytes": size, "provider": "gcp"}

    def _upload_local(self, local_path: str, remote_path: str, size: int) -> dict:
        import shutil
        dest = Path(self.config.get("base_path", "/var/backups")) / remote_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, str(dest))
        return {"url": str(dest), "size_bytes": size, "provider": "local"}
