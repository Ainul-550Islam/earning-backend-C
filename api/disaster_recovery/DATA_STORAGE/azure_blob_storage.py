"""
Azure Blob Storage Backend — Full Microsoft Azure Blob integration.
"""
import os
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AzureBlobStorage:
    """
    Azure Blob Storage backend for DR backups.
    Supports block blobs (large files), access tiers (Hot/Cool/Archive),
    lifecycle management, SAS tokens, and geo-redundancy.
    """

    def __init__(self, config: dict):
        self.config = config
        self.connection_string = config.get("connection_string", "")
        self.account_name = config.get("account_name", "")
        self.account_key = config.get("account_key", "")
        self.container_name = config.get("container", "dr-backups")
        self.prefix = config.get("prefix", "backups/")
        self.default_tier = config.get("default_tier", "Cool")   # Hot, Cool, Archive
        self._service_client = None

    @property
    def service_client(self):
        if not self._service_client:
            from azure.storage.blob import BlobServiceClient
            if self.connection_string:
                self._service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            else:
                account_url = f"https://{self.account_name}.blob.core.windows.net"
                from azure.storage.blob import BlobServiceClient
                from azure.core.credentials import AzureNamedKeyCredential
                credential = AzureNamedKeyCredential(self.account_name, self.account_key)
                self._service_client = BlobServiceClient(account_url, credential=credential)
        return self._service_client

    def ensure_container(self) -> bool:
        """Create the container if it doesn't exist."""
        try:
            container = self.service_client.get_container_client(self.container_name)
            container.get_container_properties()
            return True
        except Exception:
            self.service_client.create_container(
                self.container_name,
                metadata={"purpose": "disaster-recovery", "managed-by": "dr-system"}
            )
            logger.info(f"Azure container created: {self.container_name}")
            return True

    def upload(self, local_path: str, remote_path: str,
               metadata: dict = None, tier: str = None) -> dict:
        """Upload file to Azure Blob Storage with tier management."""
        from azure.storage.blob import StandardBlobTier
        self.ensure_container()
        blob_name = f"{self.prefix}{remote_path}"
        file_size = os.path.getsize(local_path)
        logger.info(
            f"Uploading to Azure: {local_path} -> "
            f"azure://{self.container_name}/{blob_name} ({file_size:,} bytes)"
        )
        blob_client = self.service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        tier = tier or self.default_tier
        tier_map = {"Hot": StandardBlobTier.HOT, "Cool": StandardBlobTier.COOL}
        upload_kwargs = {"overwrite": True}
        if metadata:
            upload_kwargs["metadata"] = {k: str(v) for k, v in metadata.items()}
        with open(local_path, "rb") as data:
            blob_client.upload_blob(data, **upload_kwargs)
        # Set access tier
        if tier in tier_map:
            blob_client.set_standard_blob_tier(tier_map[tier])
        url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"
        logger.info(f"Azure upload complete: {url}")
        return {
            "url": url,
            "blob_name": blob_name,
            "container": self.container_name,
            "size_bytes": file_size,
            "tier": tier,
        }

    def download(self, remote_path: str, local_path: str) -> dict:
        """Download blob from Azure to local file."""
        blob_name = f"{self.prefix}{remote_path}" if not remote_path.startswith(self.prefix) else remote_path
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading from Azure: {blob_name} -> {local_path}")
        blob_client = self.service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        with open(local_path, "wb") as f:
            download = blob_client.download_blob()
            download.readinto(f)
        size = os.path.getsize(local_path)
        logger.info(f"Azure download complete: {local_path} ({size:,} bytes)")
        return {"local_path": local_path, "size_bytes": size, "blob_name": blob_name}

    def delete(self, remote_path: str) -> bool:
        """Delete a blob from Azure."""
        blob_name = f"{self.prefix}{remote_path}"
        blob_client = self.service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        blob_client.delete_blob(delete_snapshots="include")
        logger.info(f"Azure blob deleted: {blob_name}")
        return True

    def list_blobs(self, prefix: str = "", include_metadata: bool = False) -> List[dict]:
        """List blobs in the container."""
        full_prefix = f"{self.prefix}{prefix}"
        container_client = self.service_client.get_container_client(self.container_name)
        blobs = []
        for blob in container_client.list_blobs(name_starts_with=full_prefix,
                                                 include=["metadata"] if include_metadata else []):
            blobs.append({
                "name": blob.name,
                "size_bytes": blob.size,
                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                "tier": blob.blob_tier,
                "content_md5": blob.content_settings.content_md5 if blob.content_settings else None,
                "metadata": blob.metadata or {},
            })
        return blobs

    def generate_sas_url(self, remote_path: str, expiry_hours: int = 24,
                          permissions: str = "r") -> str:
        """Generate a SAS URL for temporary access."""
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions
        blob_name = f"{self.prefix}{remote_path}"
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,
            permission=BlobSasPermissions(read="r" in permissions, write="w" in permissions),
            expiry=datetime.utcnow() + timedelta(hours=expiry_hours),
        )
        return (
            f"https://{self.account_name}.blob.core.windows.net/"
            f"{self.container_name}/{blob_name}?{sas_token}"
        )

    def set_blob_tier(self, remote_path: str, tier: str) -> bool:
        """Change the access tier of a blob (Hot/Cool/Archive)."""
        from azure.storage.blob import StandardBlobTier
        blob_name = f"{self.prefix}{remote_path}"
        blob_client = self.service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        tier_map = {"Hot": StandardBlobTier.HOT, "Cool": StandardBlobTier.COOL,
                    "Archive": StandardBlobTier.ARCHIVE}
        blob_client.set_standard_blob_tier(tier_map[tier])
        logger.info(f"Azure blob tier set to {tier}: {blob_name}")
        return True

    def rehydrate_from_archive(self, remote_path: str, priority: str = "Standard") -> dict:
        """Rehydrate an archived blob (required before downloading from Archive tier)."""
        from azure.storage.blob import RehydratePriority
        blob_name = f"{self.prefix}{remote_path}"
        blob_client = self.service_client.get_blob_client(
            container=self.container_name, blob=blob_name
        )
        priority_map = {"High": RehydratePriority.HIGH, "Standard": RehydratePriority.STANDARD}
        blob_client.set_standard_blob_tier(
            "Cool", rehydrate_priority=priority_map.get(priority, RehydratePriority.STANDARD)
        )
        eta = "1 hour" if priority == "High" else "15 hours"
        logger.info(f"Azure rehydration initiated: {blob_name} (priority={priority}, ETA={eta})")
        return {"blob_name": blob_name, "priority": priority, "estimated_time": eta}

    def get_container_stats(self) -> dict:
        """Get total size and blob count for the container."""
        blobs = self.list_blobs()
        total_bytes = sum(b["size_bytes"] for b in blobs)
        return {
            "container": self.container_name,
            "total_blobs": len(blobs),
            "total_size_gb": round(total_bytes / 1e9, 3),
            "prefix": self.prefix,
        }
