"""
AWS Backup Integration — AWS Backup service integration for centralized cloud backup management.
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class AWSBackupIntegration:
    """
    AWS Backup integration managing:
    - Backup Plans and Rules
    - Backup Vaults
    - On-demand backup jobs
    - Cross-region backup copies
    - Recovery Point management
    - RDS, EFS, DynamoDB, EBS backups
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.region = config.get("region","us-east-1") if config else "us-east-1"
        self.account_id = config.get("account_id","") if config else ""
        self.vault_name = config.get("vault_name","dr-backup-vault") if config else "dr-backup-vault"

    def _client(self, service: str = "backup"):
        import boto3
        return boto3.client(service, region_name=self.region,
                            aws_access_key_id=self.config.get("access_key_id"),
                            aws_secret_access_key=self.config.get("secret_access_key"))

    def create_backup_vault(self, vault_name: str = None, tags: dict = None) -> dict:
        """Create an AWS Backup vault."""
        vault = vault_name or self.vault_name
        try:
            r = self._client().create_backup_vault(BackupVaultName=vault,
                                                   BackupVaultTags=tags or {"managed-by":"dr-system"})
            logger.info(f"AWS Backup vault created: {vault}")
            return {"vault_name": vault, "arn": r.get("BackupVaultArn",""), "status": "created"}
        except Exception as e:
            if "already exists" in str(e).lower(): return {"vault_name": vault, "status": "exists"}
            return {"vault_name": vault, "error": str(e)}

    def create_backup_plan(self, plan_name: str, schedule: str = "cron(0 2 * * ? *)",
                           retention_days: int = 30, vault_name: str = None) -> dict:
        """Create an AWS Backup plan."""
        try:
            r = self._client().create_backup_plan(BackupPlan={
                "BackupPlanName": plan_name,
                "Rules": [{"RuleName": "DailyBackup", "TargetBackupVaultName": vault_name or self.vault_name,
                            "ScheduleExpression": schedule, "Lifecycle": {"DeleteAfterDays": retention_days}}]})
            return {"plan_id": r.get("BackupPlanId",""), "plan_name": plan_name,
                    "arn": r.get("BackupPlanArn","")}
        except Exception as e:
            return {"plan_name": plan_name, "error": str(e)}

    def start_backup_job(self, resource_arn: str, vault_name: str = None,
                         iam_role_arn: str = None, lifecycle_days: int = 30) -> dict:
        """Start an on-demand backup job."""
        try:
            r = self._client().start_backup_job(BackupVaultName=vault_name or self.vault_name,
                ResourceArn=resource_arn, IamRoleArn=iam_role_arn or self.config.get("iam_role_arn",""),
                Lifecycle={"DeleteAfterDays": lifecycle_days})
            return {"job_id": r.get("BackupJobId",""), "status": "started"}
        except Exception as e:
            return {"resource_arn": resource_arn, "error": str(e)}

    def get_backup_job_status(self, job_id: str) -> dict:
        """Get status of a backup job."""
        try:
            r = self._client().describe_backup_job(BackupJobId=job_id)
            return {"job_id": job_id, "status": r.get("State",""),
                    "percent_done": r.get("PercentDone",""),
                    "backup_size_bytes": r.get("BackupSizeInBytes",0)}
        except Exception as e:
            return {"job_id": job_id, "error": str(e)}

    def list_recovery_points(self, resource_arn: str = None, vault_name: str = None) -> List[dict]:
        """List recovery points."""
        try:
            params = {"BackupVaultName": vault_name or self.vault_name, "MaxResults": 50}
            if resource_arn: params["ByResourceArn"] = resource_arn
            r = self._client().list_recovery_points_by_backup_vault(**params)
            return [{"arn": p.get("RecoveryPointArn",""), "status": p.get("Status",""),
                     "creation_date": str(p.get("CreationDate",""))} for p in r.get("RecoveryPoints",[])]
        except Exception as e:
            return []

    def start_restore_job(self, recovery_point_arn: str, metadata: dict = None, iam_role_arn: str = None) -> dict:
        """Start a restore from a recovery point."""
        try:
            r = self._client().start_restore_job(
                RecoveryPointArn=recovery_point_arn,
                Metadata=metadata or {"DBInstanceIdentifier": "restored-db"},
                IamRoleArn=iam_role_arn or self.config.get("iam_role_arn",""))
            return {"restore_job_id": r.get("RestoreJobId",""), "status": "started"}
        except Exception as e:
            return {"recovery_point_arn": recovery_point_arn, "error": str(e)}

    def get_compliance_report(self) -> dict:
        """Get backup compliance status."""
        try:
            cutoff = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
            failed = self._client().list_backup_jobs(ByState="FAILED", ByCreatedAfter=cutoff)
            completed = self._client().list_backup_jobs(ByState="COMPLETED", ByCreatedAfter=cutoff)
            f_count = len(failed.get("BackupJobs",[]))
            c_count = len(completed.get("BackupJobs",[]))
            total = f_count + c_count
            return {"period": "last_7_days", "total_jobs": total, "completed_jobs": c_count,
                    "failed_jobs": f_count, "success_rate_percent": round(c_count/max(total,1)*100,2),
                    "vault": self.vault_name, "region": self.region}
        except Exception as e:
            return {"error": str(e), "region": self.region}

    def list_backup_plans(self) -> List[dict]:
        """List all backup plans."""
        try:
            r = self._client().list_backup_plans()
            return [{"plan_id": p.get("BackupPlanId",""), "plan_name": p.get("BackupPlanName",""),
                     "arn": p.get("BackupPlanArn","")} for p in r.get("BackupPlansList",[])]
        except Exception as e:
            return []

    def delete_recovery_point(self, vault_name: str, recovery_point_arn: str) -> bool:
        """Delete a recovery point."""
        try:
            self._client().delete_recovery_point(BackupVaultName=vault_name,
                                                  RecoveryPointArn=recovery_point_arn)
            return True
        except Exception: return False
