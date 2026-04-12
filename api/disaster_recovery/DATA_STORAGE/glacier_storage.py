"""
AWS Glacier Storage Backend — Long-term archival storage.
"""
import logging
import json
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class GlacierStorage:
    """
    AWS S3 Glacier storage for long-term backup archival.
    Retrieval times: Expedited (1-5 min), Standard (3-5 hours), Bulk (5-12 hours).
    """

    def __init__(self, config: dict):
        self.config = config
        self.vault_name = config.get("vault_name", "dr-archive")
        self.region = config.get("region", "us-east-1")
        self._client = None

    @property
    def client(self):
        if not self._client:
            import boto3
            self._client = boto3.client(
                "glacier",
                region_name=self.region,
                aws_access_key_id=self.config.get("access_key_id"),
                aws_secret_access_key=self.config.get("secret_access_key"),
            )
        return self._client

    def create_vault(self) -> dict:
        """Create the Glacier vault if it doesn't exist."""
        response = self.client.create_vault(
            accountId="-",
            vaultName=self.vault_name,
        )
        logger.info(f"Glacier vault created/verified: {self.vault_name}")
        return {"vault": self.vault_name, "location": response.get("location", "")}

    def upload_archive(self, local_path: str, description: str = "") -> dict:
        """Upload a file to Glacier. Returns archive ID."""
        import hashlib
        # Compute tree hash (required by Glacier)
        tree_hash = self._compute_tree_hash(local_path)
        with open(local_path, "rb") as f:
            data = f.read()
        file_size = len(data)
        logger.info(f"Uploading to Glacier: {local_path} ({file_size:,} bytes)")
        response = self.client.upload_archive(
            vaultName=self.vault_name,
            archiveDescription=description or f"DR backup {datetime.utcnow().isoformat()}",
            checksum=tree_hash,
            body=data,
        )
        archive_id = response["archiveId"]
        logger.info(f"Glacier upload complete: archive_id={archive_id[:20]}...")
        return {
            "archive_id": archive_id,
            "checksum": tree_hash,
            "size_bytes": file_size,
            "vault": self.vault_name,
            "location": response.get("location", ""),
        }

    def initiate_retrieval(self, archive_id: str, tier: str = "Standard",
                           sns_topic: str = None) -> dict:
        """
        Initiate a retrieval job. Returns job_id.
        tier: Expedited (1-5 min, expensive), Standard (3-5h), Bulk (5-12h, cheapest)
        """
        job_params = {
            "Type": "archive-retrieval",
            "ArchiveId": archive_id,
            "Tier": tier,
        }
        if sns_topic:
            job_params["SNSTopic"] = sns_topic
        response = self.client.initiate_job(
            vaultName=self.vault_name,
            jobParameters=job_params,
        )
        job_id = response["jobId"]
        eta = {"Expedited": "5 minutes", "Standard": "5 hours", "Bulk": "12 hours"}.get(tier, "unknown")
        logger.info(f"Glacier retrieval initiated: job_id={job_id[:20]}..., tier={tier}, ETA={eta}")
        return {"job_id": job_id, "tier": tier, "estimated_time": eta, "archive_id": archive_id}

    def check_job_status(self, job_id: str) -> dict:
        """Check if a retrieval job is complete."""
        response = self.client.describe_job(vaultName=self.vault_name, jobId=job_id)
        return {
            "job_id": job_id,
            "status": response["StatusCode"],   # InProgress, Succeeded, Failed
            "completed": response["Completed"],
            "creation_date": response.get("CreationDate", ""),
            "completion_date": response.get("CompletionDate", ""),
            "size_bytes": response.get("ArchiveSizeInBytes", 0),
        }

    def download_archive(self, job_id: str, output_path: str) -> dict:
        """Download completed retrieval job output."""
        from pathlib import Path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        response = self.client.get_job_output(vaultName=self.vault_name, jobId=job_id)
        content = response["body"].read()
        with open(output_path, "wb") as f:
            f.write(content)
        size = len(content)
        logger.info(f"Glacier download complete: {output_path} ({size:,} bytes)")
        return {"output_path": output_path, "size_bytes": size}

    def delete_archive(self, archive_id: str) -> bool:
        """Permanently delete an archive from Glacier."""
        self.client.delete_archive(
            vaultName=self.vault_name,
            archiveId=archive_id,
        )
        logger.info(f"Glacier archive deleted: {archive_id[:20]}...")
        return True

    def list_jobs(self) -> List[dict]:
        """List all pending/completed jobs for this vault."""
        response = self.client.list_jobs(vaultName=self.vault_name)
        jobs = []
        for job in response.get("JobList", []):
            jobs.append({
                "job_id": job["JobId"],
                "type": job["Action"],
                "status": job["StatusCode"],
                "completed": job["Completed"],
                "creation_date": job.get("CreationDate", ""),
            })
        return jobs

    def get_vault_info(self) -> dict:
        """Get vault metadata including size and archive count."""
        response = self.client.describe_vault(accountId="-", vaultName=self.vault_name)
        return {
            "vault_name": self.vault_name,
            "number_of_archives": response.get("NumberOfArchives", 0),
            "size_bytes": response.get("SizeInBytes", 0),
            "size_gb": round(response.get("SizeInBytes", 0) / 1e9, 3),
            "last_inventory_date": response.get("LastInventoryDate", ""),
        }

    @staticmethod
    def _compute_tree_hash(file_path: str) -> str:
        """Compute SHA256 tree hash required by Glacier for integrity verification."""
        import hashlib
        chunk_size = 1024 * 1024  # 1 MB chunks
        hashes = []
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hashes.append(hashlib.sha256(chunk).digest())
        # Build the tree by pairing and hashing
        while len(hashes) > 1:
            new_hashes = []
            for i in range(0, len(hashes), 2):
                if i + 1 < len(hashes):
                    combined = hashlib.sha256(hashes[i] + hashes[i + 1]).digest()
                    new_hashes.append(combined)
                else:
                    new_hashes.append(hashes[i])
            hashes = new_hashes
        return hashes[0].hex() if hashes else ""
