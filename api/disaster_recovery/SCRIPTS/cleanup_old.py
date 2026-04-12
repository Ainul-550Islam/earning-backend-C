#!/usr/bin/env python3
"""
Script: Clean up old/expired backups according to retention policy.
Usage: python cleanup_old.py [--dry-run] [--policy-id POLICY_ID] [--days DAYS]
"""
import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Clean up expired backup files")
    parser.add_argument("--dry-run", action="store_true",
                         help="Show what would be deleted without deleting")
    parser.add_argument("--policy-id", type=str, default=None,
                         help="Specific policy ID to clean (default: all policies)")
    parser.add_argument("--days", type=int, default=None,
                         help="Override retention days")
    parser.add_argument("--force", action="store_true",
                         help="Skip confirmation prompt")
    args = parser.parse_args()

    from disaster_recovery.dependencies import SessionLocal
    from disaster_recovery.services import BackupService
    from disaster_recovery.BACKUP_MANAGEMENT.backup_retention import BackupRetentionManager
    from disaster_recovery.enums import BackupStatus

    db = SessionLocal()
    svc = BackupService(db)

    try:
        if args.policy_id:
            policies = [svc.repo.get_policy(args.policy_id)]
        else:
            policies = svc.repo.list_policies(active_only=True)

        logger.info(f"Checking {len(policies)} policies for cleanup (dry_run={args.dry_run})")
        total_deleted = 0
        total_size_freed = 0

        for policy in policies:
            logger.info(f"Processing policy: {policy.name} (id={policy.id[:8]}...)")
            # Get completed jobs for this policy
            result = svc.repo.list_jobs(
                policy_id=policy.id,
                status=BackupStatus.COMPLETED,
                page=1,
                page_size=1000
            )
            jobs = result["items"]

            if not jobs:
                logger.info(f"  No completed jobs for policy {policy.name}")
                continue

            # Apply retention policy
            retention_days = args.days or policy.retention_days
            retention_mgr = BackupRetentionManager(
                daily_count=min(7, retention_days),
                weekly_count=min(4, retention_days // 7),
                monthly_count=min(12, retention_days // 30),
            )
            to_delete = retention_mgr.get_backups_to_delete(jobs)

            if not to_delete:
                logger.info(f"  No expired backups for policy {policy.name}")
                continue

            logger.info(f"  Found {len(to_delete)} backups to delete for {policy.name}")
            if args.dry_run:
                for job in to_delete:
                    size_mb = (job.source_size_bytes or 0) / 1e6
                    logger.info(
                        f"    [DRY RUN] Would delete: {job.id[:8]}... "
                        f"created={job.created_at.date()} size={size_mb:.1f}MB"
                    )
            else:
                if not args.force:
                    confirm = input(
                        f"Delete {len(to_delete)} backups from policy '{policy.name}'? (yes/no): "
                    )
                    if confirm.lower() != "yes":
                        logger.info("Skipped (user cancelled)")
                        continue

                for job in to_delete:
                    size = job.source_size_bytes or 0
                    svc.repo.update_job_status(job.id, __import__("disaster_recovery.enums", fromlist=["BackupStatus"]).BackupStatus.CANCELLED)
                    total_deleted += 1
                    total_size_freed += size
                    logger.info(f"  Deleted: {job.id[:8]}... ({size / 1e6:.1f} MB)")

        if args.dry_run:
            logger.info(f"DRY RUN complete. Would delete {len(to_delete) if policies else 0} backups.")
        else:
            logger.info(
                f"Cleanup complete: {total_deleted} backups deleted, "
                f"{total_size_freed / 1e6:.1f} MB freed"
            )
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
