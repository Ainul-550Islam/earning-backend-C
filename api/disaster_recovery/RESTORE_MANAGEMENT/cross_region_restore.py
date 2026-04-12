"""
Cross-Region Restore — Restore data from a backup stored in a different cloud region.
"""
import logging
import os
import tempfile
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class CrossRegionRestore:
    """
    Restores backups stored in a remote cloud region to the local (DR) region.
    Handles data transfer, replication lag considerations, and latency optimization.
    Supports AWS, Azure, and GCP cross-region operations.
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.source_region = config.get("source_region", "us-east-1") if config else "us-east-1"
        self.target_region = config.get("target_region", "us-west-2") if config else "us-west-2"
        self.provider = config.get("provider", "aws") if config else "aws"
        self.temp_dir = tempfile.mkdtemp(prefix="cross_region_restore_")

    def restore_from_s3_cross_region(self, source_bucket: str, source_key: str,
                                       target_bucket: str, dest_key: str = None) -> dict:
        """
        Copy a backup from source region S3 bucket to target region S3 bucket.
        Uses server-side copy when possible to avoid local download.
        """
        import boto3
        started_at = datetime.utcnow()
        dest_key = dest_key or source_key
        logger.info(
            f"Cross-region S3 copy: "
            f"s3://{source_bucket}/{source_key} ({self.source_region}) -> "
            f"s3://{target_bucket}/{dest_key} ({self.target_region})"
        )
        # S3 copy object (server-side, no local download needed if regions support it)
        target_s3 = boto3.client(
            "s3",
            region_name=self.target_region,
            aws_access_key_id=self.config.get("access_key_id"),
            aws_secret_access_key=self.config.get("secret_access_key"),
        )
        copy_source = {"Bucket": source_bucket, "Key": source_key}
        # Get source object size for progress tracking
        source_s3 = boto3.client(
            "s3", region_name=self.source_region,
            aws_access_key_id=self.config.get("access_key_id"),
            aws_secret_access_key=self.config.get("secret_access_key"),
        )
        head = source_s3.head_object(Bucket=source_bucket, Key=source_key)
        size_bytes = head["ContentLength"]
        # For large files (> 1 GB), use multipart copy
        if size_bytes > 1024 ** 3:
            result = self._multipart_cross_region_copy(
                source_s3, target_s3, source_bucket, source_key,
                target_bucket, dest_key, size_bytes
            )
        else:
            target_s3.copy_object(
                CopySource=copy_source,
                Bucket=target_bucket,
                Key=dest_key,
                StorageClass="STANDARD_IA",
            )
            result = {"copied": True}
        duration = (datetime.utcnow() - started_at).total_seconds()
        transfer_rate_mbps = (size_bytes / 1e6) / max(duration, 0.001)
        logger.info(
            f"Cross-region copy complete: {size_bytes / 1e6:.1f} MB "
            f"in {duration:.1f}s ({transfer_rate_mbps:.1f} MB/s)"
        )
        return {
            "success": True,
            "source": f"s3://{source_bucket}/{source_key}",
            "destination": f"s3://{target_bucket}/{dest_key}",
            "source_region": self.source_region,
            "target_region": self.target_region,
            "size_bytes": size_bytes,
            "duration_seconds": round(duration, 2),
            "transfer_rate_mbps": round(transfer_rate_mbps, 2),
        }

    def restore_from_azure_cross_region(self, source_account: str, source_container: str,
                                         source_blob: str, target_account: str,
                                         target_container: str, dest_blob: str = None) -> dict:
        """Copy Azure blob across regions."""
        dest_blob = dest_blob or source_blob
        started_at = datetime.utcnow()
        logger.info(
            f"Cross-region Azure copy: "
            f"{source_account}/{source_container}/{source_blob} -> "
            f"{target_account}/{target_container}/{dest_blob}"
        )
        from azure.storage.blob import BlobServiceClient
        target_client = BlobServiceClient.from_connection_string(
            self.config.get("target_connection_string", "")
        )
        target_blob = target_client.get_blob_client(
            container=target_container, blob=dest_blob
        )
        source_url = (
            f"https://{source_account}.blob.core.windows.net/"
            f"{source_container}/{source_blob}"
        )
        target_blob.start_copy_from_url(source_url)
        # Wait for copy to complete
        import time
        for _ in range(120):  # max 2 minutes for small files
            props = target_blob.get_blob_properties()
            if props.copy.status == "success":
                break
            if props.copy.status == "failed":
                raise RuntimeError(f"Azure cross-region copy failed: {props.copy.status_description}")
            time.sleep(1)
        duration = (datetime.utcnow() - started_at).total_seconds()
        return {
            "success": True,
            "source": source_url,
            "destination": f"https://{target_account}.blob.core.windows.net/{target_container}/{dest_blob}",
            "duration_seconds": round(duration, 2),
        }

    def restore_with_local_transfer(self, source_storage, source_path: str,
                                     target_storage, target_path: str) -> dict:
        """
        Download from source region storage and upload to target.
        Used when server-side copy is not supported.
        """
        started_at = datetime.utcnow()
        local_temp = os.path.join(self.temp_dir, os.path.basename(source_path))
        logger.info(
            f"Local transfer cross-region: {source_path} -> {target_path} "
            f"(via {local_temp})"
        )
        # Download from source
        logger.info(f"  Downloading from source region ({self.source_region})...")
        dl_result = source_storage.download(source_path, local_temp)
        size_bytes = dl_result.get("size_bytes", 0)
        # Upload to target
        logger.info(f"  Uploading to target region ({self.target_region})...")
        ul_result = target_storage.upload(local_temp, target_path)
        # Cleanup
        if os.path.exists(local_temp):
            os.remove(local_temp)
        duration = (datetime.utcnow() - started_at).total_seconds()
        return {
            "success": True,
            "source_path": source_path,
            "target_path": target_path,
            "size_bytes": size_bytes,
            "duration_seconds": round(duration, 2),
            "transfer_type": "download+upload",
        }

    def estimate_transfer_time(self, size_bytes: int,
                                bandwidth_mbps: float = 100.0) -> dict:
        """Estimate cross-region transfer time based on size and bandwidth."""
        size_mb = size_bytes / 1e6
        seconds = (size_mb / bandwidth_mbps) * 8  # bits/byte conversion
        return {
            "size_mb": round(size_mb, 2),
            "estimated_bandwidth_mbps": bandwidth_mbps,
            "estimated_seconds": round(seconds),
            "estimated_minutes": round(seconds / 60, 1),
        }

    def _multipart_cross_region_copy(self, source_s3, target_s3,
                                      src_bucket: str, src_key: str,
                                      dst_bucket: str, dst_key: str,
                                      total_size: int) -> dict:
        """Multipart copy for large files (>1 GB)."""
        PART_SIZE = 500 * 1024 * 1024  # 500 MB parts
        mpu = target_s3.create_multipart_upload(Bucket=dst_bucket, Key=dst_key)
        upload_id = mpu["UploadId"]
        parts = []
        try:
            part_num = 1
            offset = 0
            while offset < total_size:
                end = min(offset + PART_SIZE - 1, total_size - 1)
                resp = target_s3.upload_part_copy(
                    Bucket=dst_bucket, Key=dst_key,
                    UploadId=upload_id, PartNumber=part_num,
                    CopySource={"Bucket": src_bucket, "Key": src_key},
                    CopySourceRange=f"bytes={offset}-{end}",
                )
                parts.append({"PartNumber": part_num, "ETag": resp["CopyPartResult"]["ETag"]})
                logger.debug(
                    f"  Multipart part {part_num}: "
                    f"bytes {offset}-{end} ({(end-offset)/1e6:.0f} MB)"
                )
                offset = end + 1
                part_num += 1
            target_s3.complete_multipart_upload(
                Bucket=dst_bucket, Key=dst_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
            return {"copied": True, "parts": len(parts)}
        except Exception as e:
            target_s3.abort_multipart_upload(
                Bucket=dst_bucket, Key=dst_key, UploadId=upload_id
            )
            raise

    def cleanup(self):
        """Remove temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
