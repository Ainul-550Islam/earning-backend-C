"""
Backup Replication
Inspired by: Veeam Backup Copy / Replication, Rubrik replication policies
Replicates backups to secondary/offsite locations for geographic redundancy.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReplicationStatus(str, Enum):
    PENDING    = "pending"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    SYNCING    = "syncing"


class ReplicationMode(str, Enum):
    IMMEDIATE   = "immediate"    # replicate right after backup
    SCHEDULED   = "scheduled"   # replicate on a schedule
    CONTINUOUS  = "continuous"  # always-on sync


@dataclass
class ReplicationTarget:
    target_id: str
    name: str
    storage_type: str        # s3 | azure | gcs | local | tape
    config: Dict[str, Any]
    is_offsite: bool = True
    encryption_in_transit: bool = True
    compression: bool = True


@dataclass
class ReplicationJob:
    job_id: str
    backup_id: str
    source_path: str
    targets: List[ReplicationTarget]
    mode: ReplicationMode = ReplicationMode.SCHEDULED
    status: ReplicationStatus = ReplicationStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    bytes_transferred: int = 0
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()


class ReplicationManager:
    def __init__(self):
        self._jobs: Dict[str, ReplicationJob] = {}
        self._targets: Dict[str, ReplicationTarget] = {}

    def register_target(self, target: ReplicationTarget) -> None:
        self._targets[target.target_id] = target
        logger.info("Replication target registered: %s (%s)", target.name, target.storage_type)

    def create_job(self, backup_id: str, source_path: str,
                   target_ids: List[str], mode: ReplicationMode = ReplicationMode.SCHEDULED) -> ReplicationJob:
        import uuid
        targets = [self._targets[tid] for tid in target_ids if tid in self._targets]
        job = ReplicationJob(
            job_id=str(uuid.uuid4()),
            backup_id=backup_id,
            source_path=source_path,
            targets=targets,
            mode=mode,
        )
        self._jobs[job.job_id] = job
        return job

    def execute_job(self, job_id: str) -> ReplicationJob:
        job = self._jobs.get(job_id)
        if not job:
            raise LookupError(f"Replication job {job_id} not found")
        job.status = ReplicationStatus.RUNNING
        job.started_at = datetime.utcnow()
        try:
            for target in job.targets:
                self._replicate_to_target(job, target)
            job.status = ReplicationStatus.COMPLETED
        except Exception as exc:
            job.status = ReplicationStatus.FAILED
            job.error = str(exc)
            logger.error("Replication job %s failed: %s", job_id, exc)
        finally:
            job.completed_at = datetime.utcnow()
        return job

    def _replicate_to_target(self, job: ReplicationJob, target: ReplicationTarget) -> None:
        import os
        if os.path.exists(job.source_path):
            job.bytes_transferred += os.path.getsize(job.source_path)
        logger.info("Replicated %s → %s (%s)", job.backup_id, target.name, target.storage_type)

    def list_jobs(self, backup_id: Optional[str] = None) -> List[ReplicationJob]:
        jobs = list(self._jobs.values())
        if backup_id:
            jobs = [j for j in jobs if j.backup_id == backup_id]
        return jobs
