"""
S3 Storage Backend — Full AWS S3 integration for backup storage.
"""
import os
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class S3Storage:
    """
    Complete AWS S3 storage backend.
    Supports multipart upload, presigned URLs, lifecycle management,
    versioning, and server-side encryption.
    """

    def __init__(self, config: dict):
        self.config = config
        self.bucket = config["bucket"]
        self.region = config.get("region", "us-east-1")
        self.prefix = config.get("prefix", "backups/")
        self.sse = config.get("server_side_encryption", "AES256")
        self.storage_class = config.get("storage_class", "STANDARD_IA")
        self._client = None
        self._transfer_config = None

    @property
    def client(self):
        if not self._client:
            import boto3
            session = boto3.Session(
                aws_access_key_id=self.config.get("access_key_id"),
                aws_secret_access_key=self.config.get("secret_access_key"),
                region_name=self.region,
            )
            self._client = session.client("s3")
        return self._client

    @property
    def transfer_config(self):
        if not self._transfer_config:
            from boto3.s3.transfer import TransferConfig
            self._transfer_config = TransferConfig(
                multipart_threshold=100 * 1024 * 1024,   # 100 MB
                max_concurrency=10,
                multipart_chunksize=50 * 1024 * 1024,    # 50 MB chunks
                use_threads=True,
            )
        return self._transfer_config

    def upload(self, local_path: str, remote_key: str, metadata: dict = None) -> dict:
        """Upload file to S3 with multipart support and progress tracking."""
        full_key = f"{self.prefix}{remote_key}"
        file_size = os.path.getsize(local_path)
        uploaded_bytes = [0]
        lock = threading.Lock()

        def progress_callback(bytes_transferred):
            with lock:
                uploaded_bytes[0] += bytes_transferred
                pct = (uploaded_bytes[0] / file_size) * 100
                logger.debug(f"S3 upload progress: {pct:.1f}% ({full_key})")

        extra_args = {
            "StorageClass": self.storage_class,
            "ServerSideEncryption": self.sse,
        }
        if metadata:
            extra_args["Metadata"] = {k: str(v) for k, v in metadata.items()}

        logger.info(f"Uploading to S3: {local_path} -> s3://{self.bucket}/{full_key} ({file_size:,} bytes)")
        self.client.upload_file(
            local_path, self.bucket, full_key,
            Config=self.transfer_config,
            ExtraArgs=extra_args,
            Callback=progress_callback,
        )
        url = f"s3://{self.bucket}/{full_key}"
        logger.info(f"S3 upload complete: {url}")
        return {"url": url, "key": full_key, "bucket": self.bucket,
                "size_bytes": file_size, "storage_class": self.storage_class}

    def download(self, remote_key: str, local_path: str) -> dict:
        """Download file from S3 with multipart support."""
        full_key = f"{self.prefix}{remote_key}" if not remote_key.startswith(self.prefix) else remote_key
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading from S3: s3://{self.bucket}/{full_key} -> {local_path}")
        self.client.download_file(self.bucket, full_key, local_path, Config=self.transfer_config)
        size = os.path.getsize(local_path)
        logger.info(f"S3 download complete: {local_path} ({size:,} bytes)")
        return {"local_path": local_path, "size_bytes": size, "key": full_key}

    def delete(self, remote_key: str) -> bool:
        """Delete a single object from S3."""
        full_key = f"{self.prefix}{remote_key}" if not remote_key.startswith(self.prefix) else remote_key
        self.client.delete_object(Bucket=self.bucket, Key=full_key)
        logger.info(f"Deleted from S3: s3://{self.bucket}/{full_key}")
        return True

    def bulk_delete(self, remote_keys: List[str]) -> dict:
        """Delete multiple objects in a single API call (max 1000)."""
        objects = [{"Key": f"{self.prefix}{k}" if not k.startswith(self.prefix) else k}
                   for k in remote_keys]
        # S3 batch delete max 1000 per call
        deleted = 0
        errors = []
        for i in range(0, len(objects), 1000):
            batch = objects[i:i+1000]
            response = self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": batch, "Quiet": False}
            )
            deleted += len(response.get("Deleted", []))
            errors.extend(response.get("Errors", []))
        logger.info(f"S3 bulk delete: {deleted} deleted, {len(errors)} errors")
        return {"deleted": deleted, "errors": errors}

    def list_objects(self, prefix: str = "", max_keys: int = 1000) -> List[dict]:
        """List objects under a prefix."""
        full_prefix = f"{self.prefix}{prefix}"
        paginator = self.client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                objects.append({
                    "key": obj["Key"],
                    "size_bytes": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"].strip('"'),
                    "storage_class": obj.get("StorageClass", "STANDARD"),
                })
            if len(objects) >= max_keys:
                break
        return objects[:max_keys]

    def get_presigned_url(self, remote_key: str, expiry_seconds: int = 3600) -> str:
        """Generate a pre-signed download URL."""
        full_key = f"{self.prefix}{remote_key}"
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": full_key},
            ExpiresIn=expiry_seconds,
        )
        return url

    def object_exists(self, remote_key: str) -> bool:
        """Check if an object exists in S3."""
        full_key = f"{self.prefix}{remote_key}"
        try:
            self.client.head_object(Bucket=self.bucket, Key=full_key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def get_object_size(self, remote_key: str) -> int:
        """Get size of an S3 object in bytes."""
        full_key = f"{self.prefix}{remote_key}"
        response = self.client.head_object(Bucket=self.bucket, Key=full_key)
        return response["ContentLength"]

    def get_bucket_size(self) -> dict:
        """Get total size and object count for this bucket prefix."""
        objects = self.list_objects(max_keys=10000)
        total_bytes = sum(o["size_bytes"] for o in objects)
        return {
            "total_objects": len(objects),
            "total_bytes": total_bytes,
            "total_gb": round(total_bytes / 1e9, 3),
            "prefix": self.prefix,
        }

    def copy_object(self, source_key: str, dest_key: str) -> dict:
        """Copy an object within the same bucket."""
        src = f"{self.prefix}{source_key}"
        dst = f"{self.prefix}{dest_key}"
        self.client.copy_object(
            CopySource={"Bucket": self.bucket, "Key": src},
            Bucket=self.bucket, Key=dst,
            StorageClass=self.storage_class,
        )
        return {"source": src, "destination": dst, "bucket": self.bucket}

    def transition_to_glacier(self, remote_key: str) -> bool:
        """Move an object to Glacier storage class."""
        full_key = f"{self.prefix}{remote_key}"
        self.client.copy_object(
            CopySource={"Bucket": self.bucket, "Key": full_key},
            Bucket=self.bucket, Key=full_key,
            StorageClass="GLACIER",
            MetadataDirective="COPY",
        )
        logger.info(f"Transitioned to Glacier: {full_key}")
        return True

    def restore_from_glacier(self, remote_key: str, days: int = 7, tier: str = "Standard") -> dict:
        """Initiate restore from Glacier (async — takes hours)."""
        full_key = f"{self.prefix}{remote_key}"
        self.client.restore_object(
            Bucket=self.bucket, Key=full_key,
            RestoreRequest={"Days": days, "GlacierJobParameters": {"Tier": tier}},
        )
        logger.info(f"Glacier restore initiated: {full_key} (tier={tier}, days={days})")
        return {"key": full_key, "restore_tier": tier, "available_in_days": 1 if tier == "Expedited" else 3}

    def enable_versioning(self) -> bool:
        """Enable versioning on the bucket."""
        self.client.put_bucket_versioning(
            Bucket=self.bucket,
            VersioningConfiguration={"Status": "Enabled"},
        )
        logger.info(f"Versioning enabled: {self.bucket}")
        return True

    def set_lifecycle_policy(self, transition_days: int = 30, expiry_days: int = 365) -> bool:
        """Set lifecycle rules: transition to IA after N days, delete after M days."""
        policy = {
            "Rules": [{
                "ID": "DR-Lifecycle",
                "Status": "Enabled",
                "Filter": {"Prefix": self.prefix},
                "Transitions": [
                    {"Days": transition_days, "StorageClass": "STANDARD_IA"},
                    {"Days": transition_days * 3, "StorageClass": "GLACIER"},
                ],
                "Expiration": {"Days": expiry_days},
            }]
        }
        self.client.put_bucket_lifecycle_configuration(
            Bucket=self.bucket, LifecycleConfiguration=policy
        )
        logger.info(f"Lifecycle policy set: IA@{transition_days}d, Glacier@{transition_days*3}d, Expire@{expiry_days}d")
        return True
